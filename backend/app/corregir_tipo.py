"""Corregir el TIPO de un movimiento de tarjeta YA importado como ingreso cuando en realidad era una compra.

Caso de origen (tarjeta Nu): el lector viejo no veía el signo de la línea y leyó las compras como ingresos
(`income`). El lector de hoy tipa bien: compra / compra en cuotas / cuota de manejo / comisión = gasto
(`expense`); solo el pago es ingreso. Sin esto, al releer el extracto la compra entraría como una línea NUEVA
(el tipo es parte de la huella) y quedaría duplicada: un ingreso falso y un gasto.

Política (docs/RELECTURA_DE_TARJETAS.md):
  · Solo cuando el LECTOR de tarjeta lo declara (`corrige_tipo` = {de: income, a: expense} en la línea nueva).
    Nunca por simple parecido de una línea cualquiera.
  · Solo toca movimientos que ESE extracto importó (vínculo `movimiento_id` o huella del extracto, fuente
    conciliacion_extracto/auto). Nunca lo creado a mano, por atajo o por correo, ni un pago de tarjeta.
  · Línea nueva (gasto) + movimiento viejo (ingreso; misma cuenta, ±1 día, monto ±$1, comercio parecido, 1:1)
        -> la línea pasa a `corregir_tipo`; al importar se ACTUALIZA el mismo movimiento a gasto (id, fecha, vínculos
           y huella se conservan), el saldo cambia en −2·monto y NO se crea otro movimiento.
  · Si ya están los dos (el ingreso viejo y la compra nueva importada), la línea vieja pasa a `quitar_repetido`
    (con `quita_por = "tipo"`): se borra con motivo «error» (sin fantasma), se revierte su saldo.
  · Idempotente: un movimiento ya corregido deja de ser ingreso, así que no vuelve a salir.
Modelo de signos (regla única, contabilidad.delta_saldo): una compra es `expense` y resta del saldo (en una tarjeta
la deuda es negativa); un pago es `income` y la reduce. Sin columnas nuevas."""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.orm import Session

from app import corregir_pago
from app import duplicados as dup
from app.compartidos import bloquear_cuenta
from app.conciliacion import parse_bank_date
from app.contabilidad import CATEGORIA_PAGO_TARJETA, MARCA_TRASLADO_PROPIO, delta_saldo
from app.models import Movimiento
from app.reasignar_extracto import FUENTES_IMPORTADAS, movimientos_del_extracto
from app.utiles import ahora_co

CORREGIR_TIPO = corregir_pago.CORREGIR_TIPO
QUITAR = corregir_pago.QUITAR
TIPOS_DE_COMPRA = ("compra", "compra_en_cuotas", "cuota_manejo", "comision")
TOL_MONTO = 1.0
VENTANA_DIAS = 1
SIMILITUD_MINIMA = 0.75
CATEGORIAS_SIN_ELEGIR = {"otros", "ingresos", "sin categoría", "sin categoria"}


def declara(item: dict) -> bool:
    """¿El lector de tarjeta declara que esta línea es un gasto que antes se leía como ingreso?"""
    r = item.get("corrige_tipo")
    return (isinstance(r, dict) and r.get("de") == "income" and r.get("a") == "expense"
            and item.get("tipo") == "expense" and item.get("linea_tipo") in TIPOS_DE_COMPRA)


def _es_pago(mov: Movimiento, item: dict | None = None) -> bool:
    """Un pago de tarjeta es un ingreso correcto: nunca se toca."""
    return bool(
        (mov.categoria or "") == CATEGORIA_PAGO_TARJETA or MARCA_TRASLADO_PROPIO in (mov.notas or "")
        or (item or {}).get("pago_tarjeta") or (item or {}).get("linea_tipo") == "pago"
        or (mov.descripcion or "").strip().lower().startswith("pago"))


def _elegible(mov: Movimiento | None, item_viejo: dict | None = None) -> bool:
    return (mov is not None and mov.tipo == "income" and (mov.fuente or "") in FUENTES_IMPORTADAS
            and not _es_pago(mov, item_viejo))


def _igual(a, b, tol=TOL_MONTO) -> bool:
    return abs(float(a or 0) - float(b or 0)) <= tol


def _puntaje(nuevo: dict, mov: Movimiento) -> float | None:
    """None = no es la misma compra; si lo es, qué tan cerca (menor = mejor)."""
    f = parse_bank_date(nuevo.get("fecha"))
    if not f or not mov.fecha or abs((f.date() - mov.fecha.date()).days) > VENTANA_DIAS:
        return None
    if not _igual(mov.monto, nuevo.get("monto")):
        return None
    sim = dup.similitud_comercio(mov.descripcion, nuevo.get("descripcion"))
    if sim is not None and sim < SIMILITUD_MINIMA:
        return None
    return abs((f.date() - mov.fecha.date()).days) + (1 - (sim if sim is not None else 0.5))


def _vinculados(db: Session, usuario_id: str, cuenta_id: str, review: list[dict]) -> list[tuple[dict, Movimiento]]:
    """(línea, movimiento) de lo que ese extracto importó como ingreso. Una línea ya marcada «quitar por tipo»
    sigue contando (si no, la marca se desharía sola en la siguiente lectura)."""
    ref = SimpleNamespace(usuario_id=usuario_id, cuenta_id=cuenta_id)
    vista, original = [], {}
    for i in review:
        v = {**i, "estado": "importado"} if (i.get("estado") == QUITAR and i.get("quita_por") == "tipo") else i
        original[id(v)] = i
        vista.append(v)
    return [(original[id(i)], m) for i, m in movimientos_del_extracto(db, ref, vista) if _elegible(m, i)]


# ── Marcar la revisión (relectura y procesar) ─────────────────────────────────────────────────────
def marcar(db: Session, usuario_id: str, cuenta_id: str, review: list[dict]) -> int:
    """Pone `corregir_tipo` (o `quitar_repetido` por tipo) donde el lector lo declara. Devuelve cuántas líneas
    cambió. No toca la base de datos."""
    if not any(declara(i) for i in review):
        # Sin líneas declaradas: solo deshacer marcas que ya no aplican.
        return _limpiar(review, set(), set())
    viejos = _vinculados(db, usuario_id, cuenta_id, review)
    reclamados: set[str] = set()
    cambios = 0
    confirmados_nuevo: set[int] = set()

    # 1) Compra nueva sin importar + ingreso viejo que es la misma: corregir el tipo, no crear otra.
    for it in review:
        if not declara(it) or it.get("estado") not in ("faltante", CORREGIR_TIPO):
            continue
        mejor = None
        for i_v, mov in viejos:
            if mov.id in reclamados:
                continue
            p = _puntaje(it, mov)
            if p is not None and (mejor is None or p < mejor[0]):
                mejor = (p, mov)
        if mejor is not None:
            mov = mejor[1]
            reclamados.add(mov.id)
            confirmados_nuevo.add(id(it))
            if it.get("estado") != CORREGIR_TIPO or it.get("corrige_movimiento_id") != mov.id:
                cambios += 1
            it.update({"estado": CORREGIR_TIPO, "corrige_movimiento_id": mov.id, "tipo_anterior": "income",
                       "monto_anterior": float(mov.monto), "marcar_por_defecto": True, "aviso_linea": None})

    # 2) Ya están los dos (el ingreso viejo y la compra nueva ya importada): ofrecer quitar el ingreso repetido.
    confirmados_viejo: set[int] = set()
    for it in review:
        if not declara(it) or it.get("estado") != "importado" or not it.get("movimiento_id"):
            continue
        nuevo_mov = db.get(Movimiento, it["movimiento_id"])
        if (nuevo_mov is None or nuevo_mov.usuario_id != usuario_id or nuevo_mov.cuenta_id != cuenta_id
                or nuevo_mov.tipo != "expense"):
            continue
        mejor = None
        for i_v, mov in viejos:
            if mov.id in reclamados or mov.id == nuevo_mov.id or i_v is it:
                continue
            p = _puntaje(it, mov)
            if p is not None and (mejor is None or p < mejor[0]):
                mejor = (p, mov, i_v)
        if mejor is None:
            continue
        _, mov, i_v = mejor
        reclamados.add(mov.id)
        confirmados_viejo.add(id(i_v))
        if i_v.get("estado") != QUITAR:
            cambios += 1
        i_v.update({"estado": QUITAR, "movimiento_id": mov.id, "quita_por": "tipo", "nuevo_movimiento_id": nuevo_mov.id,
                    "monto_correcto": float(it["monto"]), "marcar_por_defecto": True,
                    "corrige_lectura": {"descripcion": mov.descripcion, "tipo": "income", "montos": [float(mov.monto)]}})
    return cambios + _limpiar(review, confirmados_nuevo, confirmados_viejo)


def _limpiar(review: list[dict], confirmados_nuevo: set[int], confirmados_viejo: set[int]) -> int:
    """Marcas de una relectura anterior que ya no aplican (el movimiento cambió o desapareció) vuelven a su estado."""
    cambios = 0
    for it in review:
        if it.get("estado") == CORREGIR_TIPO and id(it) not in confirmados_nuevo:
            for k in ("corrige_movimiento_id", "monto_anterior", "tipo_anterior"):
                it.pop(k, None)
            it["estado"] = "faltante"
            cambios += 1
        elif it.get("estado") == QUITAR and it.get("quita_por") == "tipo" and id(it) not in confirmados_viejo:
            for k in ("quita_por", "nuevo_movimiento_id", "monto_correcto", "corrige_lectura"):
                it.pop(k, None)
            it["estado"] = "importado"
            cambios += 1
    return cambios


# ── Aplicar al importar ───────────────────────────────────────────────────────────────────────────
def _mov_a_corregir(db: Session, usuario_id: str, cuenta_id: str, item: dict) -> Movimiento | None:
    mid = item.get("corrige_movimiento_id")
    m = db.get(Movimiento, mid) if mid else None
    if (m is None or m.usuario_id != usuario_id or m.cuenta_id != cuenta_id or (m.fuente or "") not in FUENTES_IMPORTADAS
            or m.tipo not in ("income", "expense") or _es_pago(m, item) or not _igual(m.monto, item.get("monto"))):
        return None
    return m


def corregir(db: Session, usuario_id: str, cuenta, historial_id: str, item: dict, huella: str | None,
             elegida: str | None = None) -> dict | None:
    """Pasa el movimiento de ingreso a gasto. None si ya no se puede (cambió, no es de esta cuenta, es de otro
    canal): quien llama trata entonces la línea como compra normal. Idempotente. Sin commit."""
    if not declara(item):
        return None
    mov = _mov_a_corregir(db, usuario_id, cuenta.id, item)
    if mov is None:
        return None
    if mov.tipo == "expense":  # ya corregido (doble toque o relectura simultánea): nada que mover
        return {"movimiento_id": mov.id, "monto_anterior": float(mov.monto), "sin_cambio": True}
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    antes = delta_saldo(mov)
    anterior = float(mov.monto)
    mov.tipo = "expense"
    mov.monto = round(float(item["monto"]), 2)
    mov.descripcion = item["descripcion"]
    sugerida = item.get("categoria_sugerida")
    if elegida:
        mov.categoria = elegida  # la persona la eligió en la hoja
        mov.cat_origen, mov.cat_confirmada = None, True
    elif (mov.categoria or "").strip().lower() in CATEGORIAS_SIN_ELEGIR or not mov.cat_confirmada:
        if sugerida and sugerida.strip().lower() not in CATEGORIAS_SIN_ELEGIR:
            mov.categoria = sugerida  # solo si la categoría era de ingreso, «Otros» o puesta por la app
        elif (mov.categoria or "").strip().lower() == "ingresos":
            mov.categoria = "Otros"  # una compra no puede quedarse en «Ingresos»
    cuenta.saldo += delta_saldo(mov) - antes
    mov.conciliado_en = ahora_co()
    mov.extracto_id = historial_id
    if huella:
        mov.huella_externa = huella
    corregir_pago._refrescar_canales(db, mov, huella)
    return {"movimiento_id": mov.id, "monto_anterior": anterior, "sin_cambio": False}


def quitar(db: Session, usuario_id: str, cuenta, item: dict) -> bool:
    """Borra el ingreso repetido (motivo «error»: sin fantasma) y revierte su efecto. Solo si la compra buena
    sigue ahí como gasto. Sin commit."""
    regla = corregir_pago.regla_de(item)
    if not regla or item.get("quita_por") != "tipo":
        return False
    mov = db.get(Movimiento, item.get("movimiento_id")) if item.get("movimiento_id") else None
    bueno = db.get(Movimiento, item.get("nuevo_movimiento_id")) if item.get("nuevo_movimiento_id") else None
    if (mov is None or mov.usuario_id != usuario_id or mov.cuenta_id != cuenta.id or not _elegible(mov, item)
            or bueno is None or bueno.usuario_id != usuario_id or bueno.cuenta_id != cuenta.id or bueno.tipo != "expense"
            or bueno.id == mov.id or not _igual(bueno.monto, mov.monto)):
        return False
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    cuenta.saldo -= delta_saldo(mov)
    dup.registrar_borrado(db, mov, dup.MOTIVO_ERROR)
    db.flush()
    db.delete(mov)
    return True


def aplicar_item(db: Session, usuario_id: str, cuenta, historial_id: str, item: dict, review: list[dict],
                 huella: str | None, elegida: str | None = None) -> tuple[str | None, list[dict]]:
    """Aplica UNA línea marcada (`corregir_tipo` o `quitar_repetido` por tipo). Devuelve ("corregido"|"quitado"|None,
    líneas de la revisión que dejan de existir). Si no se pudo, la línea vuelve a su estado normal."""
    if item.get("estado") == CORREGIR_TIPO:
        hecho = corregir(db, usuario_id, cuenta, historial_id, item, huella, elegida)
        if hecho is None:
            for k in ("corrige_movimiento_id", "monto_anterior", "tipo_anterior"):
                item.pop(k, None)
            item["estado"] = "faltante"
            return None, []
        item.update({"estado": "importado", "movimiento_id": hecho["movimiento_id"],
                     "monto_anterior": hecho["monto_anterior"], "corregido": True})
        for k in ("marcar_por_defecto", "aviso_linea"):
            item.pop(k, None)
        fuera = [v for v in review if v is not item and v.get("movimiento_id") == hecho["movimiento_id"]
                 and v.get("estado") in ("importado", QUITAR)]
        return "corregido", fuera
    if item.get("estado") == QUITAR and item.get("quita_por") == "tipo":
        if quitar(db, usuario_id, cuenta, item):
            return "quitado", [item]
        for k in ("quita_por", "nuevo_movimiento_id", "monto_correcto", "corrige_lectura"):
            item.pop(k, None)
        item["estado"] = "importado"
    return None, []


# ── Cuánto cambiaría (vista previa, sin escribir) ─────────────────────────────────────────────────
def candidatos_previa(db: Session, historial, review: list[dict] | None = None) -> list[Movimiento]:
    """Movimientos que ESTE extracto importó como ingreso y no son pagos: en una tarjeta de crédito el lector de
    hoy los lee como compras. Es una estimación para la vista previa (la corrección real la declara el lector al
    releer el PDF y solo ocurre si lo leído suma lo que dice el extracto)."""
    import json
    if review is None:
        try:
            review = json.loads(historial.review_json or "[]")
        except ValueError:
            return []
    return [m for _i, m in _vinculados(db, historial.usuario_id, historial.cuenta_id, review)]


def aplicar_en_historial(db: Session, usuario, h, cuenta=None) -> dict:
    """Aplica TODAS las correcciones de tipo que la revisión de un extracto ya propone (lo usa «Arreglar mis
    extractos de la tarjeta», que no pide un paso más). Una transacción con commit. Devuelve conteos y cambio de saldo."""
    import json
    from app import cuadre_extracto, estado_traer, punto_partida, saldo_inicial_auto
    from app.models import Cuenta
    from app.routers.conciliacion import _huella_linea

    out = {"corregidos": 0, "quitados": 0, "cambio_saldo": 0.0}
    try:
        review = json.loads(h.review_json or "[]")
    except ValueError:
        return out
    if not any(i.get("estado") == CORREGIR_TIPO or (i.get("estado") == QUITAR and i.get("quita_por") == "tipo") for i in review):
        return out
    cuenta = cuenta or db.query(Cuenta).filter(Cuenta.id == h.cuenta_id, Cuenta.usuario_id == usuario.id).first()
    if cuenta is None:
        return out
    cuenta = bloquear_cuenta(db, cuenta.id) or cuenta
    db.refresh(h)  # la revisión vigente, ya con el candado de la cuenta
    review = json.loads(h.review_json or "[]")
    saldo_antes = cuenta.saldo or 0.0
    fuera: list[dict] = []
    for item in sorted(review, key=lambda i: parse_bank_date(i.get("fecha")) or parse_bank_date("2999-01-01")):
        if item.get("estado") not in (CORREGIR_TIPO, QUITAR):
            continue
        tipo, quitar_de_la_revision = aplicar_item(db, usuario.id, cuenta, h.id, item, review,
                                                    _huella_linea(db, usuario.id, item))
        if tipo == "corregido":
            out["corregidos"] += 1
        elif tipo == "quitado":
            out["quitados"] += 1
        fuera += quitar_de_la_revision
    if fuera:
        ids = {id(v) for v in fuera}
        review[:] = [v for v in review if id(v) not in ids]
    h.review_json = json.dumps(review, default=str)
    h.total_movimientos = len([i for i in review if i.get("estado") != "sobrante"])
    estado_traer.sincronizar_contadores(h, review)
    if not any(i.get("estado") in ("faltante", "dudoso", *corregir_pago.ESTADOS_CORRECCION) for i in review):
        cuadre_extracto.registrar_cuadre(db, cuenta, h)
    db.commit()
    out["cambio_saldo"] = (cuenta.saldo or 0.0) - saldo_antes
    try:  # un ingreso que pasa a gasto cambia el saldo: el ajuste inicial se recalcula
        saldo_inicial_auto.registrar(db, cuenta, punto_partida.fecha_inicio(db, usuario.id))
    except Exception:  # noqa: BLE001 - no estorba al arreglo
        db.rollback()
    return out
