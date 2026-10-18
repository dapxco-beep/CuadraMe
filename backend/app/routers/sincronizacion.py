"""Pantalla única 'Sincronización': qué ya se concilió, qué falta y qué hay que preguntar.

Todo se CALCULA con lo que ya existe (extractos_correo, historial_extractos,
movimientos.conciliado_en / cat_confirmada, correos_gastos): no hay tablas ni
columnas nuevas y ninguna regla se duplica (la bandeja y 'por revisar' se
importan de movimientos.py). Solo se cuentan filas, no se suma dinero; donde
se sume, debe usarse contabilidad.py.
"""
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, not_, or_
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app import carriles_correo
from app import cuadre_encadenado
from app import punto_partida
from app.autocat import patron_de_comercio
from app.compartidos import cuentas_ids_accesibles
from app.database import get_db
from app.duplicados import absorber_correos, grupos_posibles_duplicados
from app import estado_traer
from app import extractos_error
from app import extractos_vista
from app.extractos_conciliados import (  # noqa: F401
    ESTADO_YA_CONCILIADO, FUENTES_CONCILIACION, depurar_conciliados, mes_del_extracto,
)
from app.extractos_gmail import banco_por_remitente, cuentas_del_banco
from app.models import CorreoGasto, Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, SyncGmail
from app import pendientes
from app.schemas import FijarMesIn, MovimientoOut
from app.utiles import ahora_co
from app.wallet import FUENTES_POR_CONFIRMAR

router = APIRouter(prefix="/sincronizacion", tags=["sincronizacion"])

MESES_GRILLA = 6
MESES_GRILLA_MAX = 24
DIAS_BANDEJA = 14  # la misma ventana de GET /movimientos/por-confirmar

_NOMBRES_MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _clave(anio: int, mes: int) -> str:
    return f"{anio:04d}-{mes:02d}"


def ultimos_meses(hoy: datetime, n: int = MESES_GRILLA) -> list[tuple[int, int]]:
    """[(año, mes)] de los últimos n meses, del más viejo al actual."""
    salida = []
    a, m = hoy.year, hoy.month
    for _ in range(n):
        salida.append((a, m))
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return salida[::-1]


def _inicio_mes(a: int, m: int) -> datetime:
    return datetime(a, m, 1)


def _siguiente(a: int, m: int) -> tuple[int, int]:
    return (a + 1, 1) if m == 12 else (a, m + 1)


def estado_celda(*, movimientos: int, conciliados: int, extractos_procesados: int,
                 extractos_nuevos: int, extractos_falta_clave: int, extractos_parciales: int = 0,
                 anterior: bool = False, extractos_error: int = 0) -> str:
    """Estado de una celda cuenta x mes. Prioridad: lo anterior a tu fecha de inicio no cuenta;
    un extracto ya procesado manda (si aún le faltan líneas por registrar es «parcial»);
    si no, lo que espera acción (clave, conciliar); si no, la evidencia de
    movimientos conciliados; si no, hay movimientos sin extracto; si no, vacío."""
    if anterior:
        return "anterior"
    if extractos_parciales:
        return "parcial"
    if extractos_procesados:
        return "conciliado"
    if extractos_falta_clave:
        return "falta_clave"
    if extractos_error:
        return "no_se_pudo_leer"
    if extractos_nuevos:
        return "extracto_pendiente"
    if conciliados:
        return "conciliado"
    if movimientos:
        return "sin_extracto"
    return "vacio"


def _cond_bandeja(ids_accesibles: list[str], desde: datetime):
    """Misma regla que GET /movimientos/por-confirmar."""
    return and_(
        Movimiento.cuenta_id.in_(ids_accesibles),
        Movimiento.cat_confirmada.is_(False),
        Movimiento.fuente.in_(FUENTES_POR_CONFIRMAR),
        Movimiento.fecha >= desde,
    )


def _cola_categorizar(db: Session, usuario_id: str, ids_accesibles: list[str], desde_bandeja: datetime):
    """Lo que espera categoría (definición única: app/pendientes.py), salvo lo que ya está en la
    bandeja '¿son tuyos?' (esos se resuelven allí y no se cuentan dos veces)."""
    return db.query(Movimiento).filter(
        Movimiento.cuenta_id.in_(ids_accesibles),
        Movimiento.id.in_(pendientes.ids_pendientes(db, usuario_id, ids_accesibles) or ["-"]),
        not_(_cond_bandeja(ids_accesibles, desde_bandeja)),
    )


def _desde_inicio(inicio):
    """Condición SQL: correos recibidos desde el punto de partida (o sin fecha). Sin inicio no filtra."""
    if not inicio:
        return True
    return punto_partida.correo_desde_inicio(inicio)


def _sin_cuenta(db: Session, usuario_id: str, cuentas: list[Cuenta], extractos: list[ExtractoCorreo],
                inicio=None) -> list[dict]:
    """Bancos detectados en correos/extractos pendientes para los que no hay cuenta."""
    por_banco: dict[str, dict] = {}

    filas = (
        db.query(CorreoGasto.remitente, func.count(CorreoGasto.id))
        .filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "pendiente", CorreoGasto.monto > 0,
                _desde_inicio(inicio))
        .group_by(CorreoGasto.remitente)
        .all()
    )
    for remitente, n in filas:
        banco = banco_por_remitente(remitente)
        if banco and not cuentas_del_banco(banco, cuentas):
            d = por_banco.setdefault(banco, {"banco": banco, "correos": 0, "extractos": 0})
            d["correos"] += n
    for e in extractos:
        if e.estado not in ("nuevo", "falta_clave"):
            continue
        banco = e.banco or banco_por_remitente(e.remitente) or ""
        if banco and not cuentas_del_banco(banco, cuentas):
            d = por_banco.setdefault(banco, {"banco": banco, "correos": 0, "extractos": 0})
            d["extractos"] += 1
    return sorted(por_banco.values(), key=lambda d: -(d["correos"] + d["extractos"]))


def _mes_anterior_al_inicio(clave: str, inicio, movimientos: int) -> bool:
    """El mes termina antes de tu fecha de inicio y no tiene movimientos: no se espera nada ahí."""
    if not inicio or movimientos:
        return False
    a, m = int(clave[:4]), int(clave[5:7])
    return _inicio_mes(*_siguiente(a, m)) <= inicio


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


@router.get("/estado")
def estado(
    meses: int = Query(MESES_GRILLA, ge=1, le=MESES_GRILLA_MAX, description="Cuántos meses mostrar (hasta 24)"),
    hasta: str | None = Query(None, description="Mes final de la cuadrícula, AAAA-MM (por defecto el actual)"),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Todo lo que la pantalla necesita en una sola llamada: grilla cuentas x
    meses, bancos sin cuenta y la lista ordenada de tareas pendientes. La cuadrícula
    muestra `meses` (6 por defecto, máx. 24) terminando en `hasta`."""
    hoy = ahora_co()
    fin_grilla = hoy
    if hasta:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", hasta):
            raise HTTPException(status_code=422, detail="'hasta' debe ser un mes AAAA-MM")
        fin_grilla = datetime(int(hasta[:4]), int(hasta[5:7]), 1)
    meses = ultimos_meses(fin_grilla, meses)
    claves = [_clave(a, m) for a, m in meses]
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).order_by(Cuenta.nombre).all()
    ids_cuentas = [c.id for c in cuentas]
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)

    # ── Movimientos por cuenta y mes: 1 consulta agrupada por mes (índice cuenta+fecha).
    conteo: dict[tuple[str, str], dict] = {}
    if ids_cuentas:
        # UNA consulta agrupada por cuenta y mes (antes, una por mes: hasta 24 consultas).
        anio_mes = func.extract("year", Movimiento.fecha), func.extract("month", Movimiento.fecha)
        filas = (
            db.query(
                Movimiento.cuenta_id,
                *anio_mes,
                func.count(Movimiento.id),
                # Conciliado = cruzado con un extracto o importado desde uno (mismo criterio que
                # extractos_conciliados.evidencia_conciliado, pero en una sola consulta agrupada).
                func.coalesce(func.sum(case((or_(Movimiento.conciliado_en.isnot(None), Movimiento.fuente.in_(FUENTES_CONCILIACION)), 1), else_=0)), 0),
                func.coalesce(func.sum(case((Movimiento.cat_confirmada.is_(False), 1), else_=0)), 0),
            )
            .filter(
                Movimiento.cuenta_id.in_(ids_cuentas),
                Movimiento.fecha >= _inicio_mes(*meses[0]),
                Movimiento.fecha < _inicio_mes(*_siguiente(*meses[-1])),
            )
            .group_by(Movimiento.cuenta_id, *anio_mes)
            .all()
        )
        for cuenta_id, a, m, total, conc, por_conf in filas:
            conteo[(cuenta_id, _clave(int(a), int(m)))] = {
                "movimientos": int(total), "conciliados": int(conc), "por_confirmar": int(por_conf)}

    # ── Extractos de Gmail (solo metadatos, pocos): a qué cuenta y mes pertenecen.
    # Si el periodo ya se concilió (p. ej. subiste el archivo a mano), el extracto de
    # Gmail deja de ser pendiente antes de contar nada.
    estado_traer.persistir_periodos(db, usuario.id)  # el mes deducido (asunto, archivo, líneas) queda guardado
    depurar_conciliados(db, usuario.id)
    # Carrera entre canales: si mientras tanto la app, el atajo o el correo registraron líneas que
    # este extracto traía como «faltantes», se juntan aquí (nunca se duplican) y el extracto queda al día.
    estado_traer.reconciliar_pendientes(db, usuario.id)
    extractos = (
        db.query(ExtractoCorreo)
        .filter(
            ExtractoCorreo.usuario_id == usuario.id,
            ExtractoCorreo.estado.in_(("nuevo", "falta_clave", "procesado", ESTADO_YA_CONCILIADO)),
        )
        .all()
    )
    # Punto de partida: los extractos anteriores a la fecha de inicio no son pendientes (se ignoran).
    inicio_pp = punto_partida.fecha_inicio(db, usuario.id)
    extractos = [
        e for e in extractos
        if not (e.estado in ("nuevo", "falta_clave") and punto_partida.extracto_es_anterior(e.periodo, e.recibido_en, inicio_pp))
    ]
    historiales = {
        h_id: cuenta_id
        for h_id, cuenta_id in db.query(HistorialExtracto.id, HistorialExtracto.cuenta_id).filter(
            HistorialExtracto.usuario_id == usuario.id,
            HistorialExtracto.id.in_([e.historial_id for e in extractos if e.historial_id] or [""]),
        )
    }
    lista_ext = estado_traer.lista_extractos(db, usuario.id, inicio_pp)
    resumen_celdas = estado_traer.resumen_por_celda(lista_ext)
    cuadre_cuentas = cuadre_encadenado.anotar_lista(db, usuario.id, lista_ext, inicio_pp)  # insignia «Cuadra / No cuadra»
    parciales_celda: dict[tuple[str, str], int] = {}
    for x in lista_ext:
        if x["historial_id"] and x["estado"] == estado_traer.POR_REVISAR and x["cuenta_id"] and x["mes"]:
            parciales_celda[(x["cuenta_id"], x["mes"])] = parciales_celda.get((x["cuenta_id"], x["mes"]), 0) + 1
    ext_celda: dict[tuple[str, str], dict] = {}
    hist_obj = {h.id: h for h in db.query(HistorialExtracto).filter(
        HistorialExtracto.usuario_id == usuario.id,
        HistorialExtracto.id.in_([e.historial_id for e in extractos if e.historial_id] or [""]))}
    for e in extractos:
        cuenta_id = historiales.get(e.historial_id) if e.estado == "procesado" else e.cuenta_sugerida_id
        clave = estado_traer.mes_de_correo(e, hist_obj.get(e.historial_id))["mes"]  # el mismo mes que dice la lista
        if not cuenta_id or not clave:
            continue
        d = ext_celda.setdefault((cuenta_id, clave), {"procesado": 0, "nuevo": 0, "falta_clave": 0})
        # Un extracto 'ya conciliado' cuenta como procesado en la grilla, nunca como pendiente.
        d["procesado" if e.estado == ESTADO_YA_CONCILIADO else e.estado] += 1

    # Extractos que no se pudieron leer, por celda (la lista los muestra; la cobertura también).
    errores_celda: dict[tuple[str, str], int] = {}
    motivo_celda: dict[tuple[str, str], str] = {}  # por qué no se pudo leer (frase corta) en esa celda
    for x in lista_ext:
        if x["estado"] == estado_traer.NO_SE_PUDO_LEER and x["cuenta_id"] and x["mes"]:
            errores_celda[(x["cuenta_id"], x["mes"])] = errores_celda.get((x["cuenta_id"], x["mes"]), 0) + 1
            motivo_celda[(x["cuenta_id"], x["mes"])] = x.get("motivo_corto") or extractos_vista.motivo_corto(None)
        elif x["estado"] == estado_traer.NECESITA_CLAVE and x["cuenta_id"] and x["mes"]:
            motivo_celda.setdefault((x["cuenta_id"], x["mes"]), extractos_vista.motivo_corto("clave_faltante"))
    # Extractos de una tarjeta que quedaron en OTRA cuenta (p. ej. la de ahorros): la tarjeta debe decirlo.
    en_otra_cuenta: dict[tuple[str, str], list[dict]] = {}
    for x in lista_ext:
        sug = x.get("sugerencia_cuenta")
        if sug and x.get("mes") and x.get("historial_id"):
            en_otra_cuenta.setdefault((sug["cuenta_id"], x["mes"]), []).append(
                {"historial_id": x["historial_id"], "desde": x["cuenta"], "titulo": x["titulo"]})
    filas_cuentas = []
    for c in cuentas:
        celdas = []
        for clave in claves:
            cnt = conteo.get((c.id, clave), {"movimientos": 0, "conciliados": 0, "por_confirmar": 0})
            ex = ext_celda.get((c.id, clave), {"procesado": 0, "nuevo": 0, "falta_clave": 0})
            res = resumen_celdas.get((c.id, clave))
            celdas.append({
                "mes": clave,
                "estado": estado_celda(
                    movimientos=cnt["movimientos"], conciliados=cnt["conciliados"],
                    extractos_procesados=ex["procesado"], extractos_nuevos=ex["nuevo"],
                    extractos_falta_clave=ex["falta_clave"],
                    extractos_parciales=parciales_celda.get((c.id, clave), 0),
                    extractos_error=errores_celda.get((c.id, clave), 0),
                    anterior=_mes_anterior_al_inicio(clave, inicio_pp, cnt["movimientos"]),
                ),
                **cnt,
                "extractos": ex["procesado"] + ex["nuevo"] + ex["falta_clave"],
                # Qué pasó con el extracto de esta celda (para el detalle al tocarla).
                "leidas": res["leidas"] if res else 0,
                "ya_estaban": res["ya_estaban"] if res else 0,
                "nuevas_agregadas": res["nuevas_agregadas"] if res else 0,
                "por_revisar": res["por_revisar"] if res else 0,
                "lectura_dudosa": res["lectura_dudosa"] if res else 0,
                "motivo_corto": motivo_celda.get((c.id, clave)),
                "en_otra_cuenta": en_otra_cuenta.get((c.id, clave), []),
                # Los extractos de esta celda, con el mismo título y estado que en «Todos los extractos».
                "lista": res["lista"] if res else [],
            })
        filas_cuentas.append({"id": c.id, "nombre": c.nombre, "icono": c.icono, "tipo": c.tipo or "ahorro", "meses": celdas})

    sin_cuenta = _sin_cuenta(db, usuario.id, cuentas, extractos, inicio_pp)

    # ── Tareas, en el orden en que conviene resolverlas.
    # Un extracto real es UNO aunque haya llegado en dos correos o se haya subido a mano también.
    # Un error por clave se arregla poniendo la clave: cuenta como «falta la clave», no como «no se pudo leer».
    es_error_clave = lambda x: x["estado"] == estado_traer.NO_SE_PUDO_LEER and x.get("motivo_codigo") in extractos_error.MOTIVOS_CLAVE  # noqa: E731
    n_falta_clave = sum(1 for x in lista_ext if x["estado"] == estado_traer.NECESITA_CLAVE or es_error_clave(x))
    n_por_conciliar = sum(1 for x in lista_ext if x["estado"] == estado_traer.POR_REVISAR)
    n_no_leyo = sum(1 for x in lista_ext if x["estado"] == estado_traer.NO_SE_PUDO_LEER and not es_error_clave(x))
    n_cuenta_dudosa = sum(1 for x in lista_ext if x.get("sugerencia_cuenta") and x.get("historial_id"))
    n_duplicados = len(grupos_posibles_duplicados(db, usuario.id))
    desde_bandeja = hoy - timedelta(days=DIAS_BANDEJA)
    n_categorizar = _cola_categorizar(db, usuario.id, ids_accesibles, desde_bandeja).count()
    n_confirmar = db.query(func.count(Movimiento.id)).filter(_cond_bandeja(ids_accesibles, desde_bandeja)).scalar() or 0
    absorber_correos(db, usuario.id)  # lo que ya tiene su movimiento no cuenta como «por revisar»
    n_ya_registrados = (
        db.query(func.count(CorreoGasto.id))
        .filter(CorreoGasto.usuario_id == usuario.id, CorreoGasto.estado == "ya_registrado")
        .scalar() or 0
    )
    n_descartados = (
        db.query(func.count(CorreoGasto.id))
        .filter(CorreoGasto.usuario_id == usuario.id, CorreoGasto.estado == "descartado", CorreoGasto.monto > 0)
        .scalar() or 0
    )
    n_correos = (
        db.query(func.count(CorreoGasto.id))
        .filter(CorreoGasto.usuario_id == usuario.id, CorreoGasto.estado == "pendiente", CorreoGasto.monto > 0,
                _desde_inicio(inicio_pp))
        .scalar() or 0
    )
    candidatas = [
        ("falta_clave", "Falta la clave del PDF", "Guárdala y abro estos extractos por ti.", n_falta_clave, "/sincronizacion#clave"),
        ("extractos_por_conciliar", "Extractos por conciliar",
         "Mira qué trae tu extracto y qué falta registrar.", n_por_conciliar, "/sincronizacion#extractos"),
        ("sin_cuenta", "Bancos sin cuenta",
         "Crea la cuenta de " + ", ".join(d["banco"] for d in sin_cuenta[:3]) + "." if sin_cuenta else "",
         len(sin_cuenta), "/sincronizacion#cuentas"),
        ("movimientos_por_categorizar", "Movimientos por categorizar",
         "Dime la categoría y la recuerdo para la próxima.", n_categorizar, "/sincronizacion#categorizar"),
        ("movimientos_por_confirmar", "Movimientos por confirmar",
         "Llegaron solos: confirma que son tuyos.", n_confirmar, "/movimientos?revisar=1"),
        ("correos_por_revisar", "Movimientos del correo por revisar",
         "Mira la fecha, el monto y la cuenta de cada uno, y apruébalos o descártalos.", n_correos, "/movimientos?filtro=por-revisar"),
        ("cuadre_no_cuadra", "Un mes no cuadra con tu banco",
         next((r["resumen"] for r in cuadre_cuentas.values() if r.get("resumen")), ""),
         sum(1 for r in cuadre_cuentas.values() if r.get("resumen")), "/sincronizacion#cuadre"),
        ("extractos_sin_leer", "Extractos que no pudimos leer",
         "Sube el archivo de nuevo o agrega esos movimientos a mano.", n_no_leyo, "/sincronizacion#extractos"),
        ("posibles_duplicados", "Posibles movimientos repetidos",
         "Parecen el mismo gasto: dime si es el mismo o es otro.", n_duplicados, "/buscar-duplicados"),
        ("extracto_cuenta_dudosa", "Un extracto está en otra cuenta",
         "Parece de tu tarjeta de crédito pero quedó en una cuenta de ahorros. Pásalo a la cuenta correcta.",
         n_cuenta_dudosa, "/sincronizacion#extractos"),
        # Opcional: no es una obligación, pero «Todo al día» no puede esconder que hay correos por recuperar.
        ("correos_descartados", "Correos descartados que puedes recuperar",
         "Los descartaste al borrar un movimiento parecido. Mira si alguno sí era tuyo.", n_descartados, "/sincronizacion#descartados"),
    ]
    # Cada tarea dice a qué «carril» del correo pertenece (o ninguno): así la pantalla no mezcla
    # los movimientos del día a día con los extractos para conciliar.
    carril_de = {
        "falta_clave": "extractos", "extractos_por_conciliar": "extractos", "extractos_sin_leer": "extractos",
        "extracto_cuenta_dudosa": "extractos",
        "correos_por_revisar": "movimientos", "cuadre_no_cuadra": "extractos",
    }
    tareas = [
        {"id": i, "titulo": t, "detalle": d, "cantidad": int(n), "ruta": r,
         "carril": carril_de.get(i), "carril_nombre": carriles_correo.NOMBRE_CARRIL.get(carril_de.get(i), ""),
         # Categorizar es una invitación, no una obligación: no cuenta como «cosa por resolver».
         "opcional": i in ("movimientos_por_categorizar", "correos_descartados")}
        for i, t, d, n, r in candidatas if n > 0
    ]

    sync = db.query(SyncGmail).filter(SyncGmail.usuario_id == usuario.id).first()
    return {
        "meses": [{"clave": c, "etiqueta": f"{_NOMBRES_MES[m - 1]} {str(a)[2:]}"} for (a, m), c in zip(meses, claves)],
        "cuentas": filas_cuentas,
        "sin_cuenta": sin_cuenta,
        "tareas": tareas,
        "correos_ya_registrados": n_ya_registrados,
        "correos_descartados": n_descartados,
        # Un renglón por extracto real, con lo que pasó con cada línea (ver app/estado_traer.py).
        "extractos": lista_ext,
        # «Todos los extractos»: la misma lista, completa y ordenada por mes, con contadores y correos sin PDF.
        "todos_extractos": estado_traer.vista_completa(db, usuario.id, inicio_pp, lista=lista_ext),
        "estados_extracto": list(estado_traer.ESTADOS),
        # Cuadre mes a mes por cuenta (calculado al consultar; ver app/cuadre_encadenado.py).
        "cuadre_mensual": list(cuadre_cuentas.values()),
        # Punto de partida: elección actual, cuántos correos/extractos anteriores se ignoran y, en modo
        # histórico, qué meses faltan por cuenta.
        "punto_partida": {
            **punto_partida.resumen(db, usuario.id),
            "cobertura": punto_partida.cobertura(db, usuario.id) if inicio_pp and punto_partida.obtener(db, usuario.id)["modo"] == "historico" else None,
        },
        "ultima_sync": sync.ultima_sync.isoformat() if sync and sync.ultima_sync else None,
        # Los dos usos del correo, contados por separado (interruptor, última vez, contadores).
        "carriles": carriles_correo.resumen(db, usuario.id, lista_ext),
    }


@router.get("/por-categorizar")
def por_categorizar(
    limite: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Cola de movimientos cuya categoría hay que preguntar (están en 'Otros' o
    la puso la app sola sin confirmar). Cada uno trae `patron`, el comercio que
    se recordaría. Para responder se usa POST /movimientos/{id}/recategorizar-comercio
    con `aplicar_a_todos`: crea la regla y recategoriza los demás del comercio."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    q = _cola_categorizar(db, usuario.id, ids_accesibles, ahora_co() - timedelta(days=DIAS_BANDEJA))
    total = q.count()
    filas = q.order_by(Movimiento.fecha.desc(), Movimiento.id).offset(offset).limit(limite).all()
    items = []
    for m in filas:
        o = MovimientoOut.model_validate(m).model_dump(mode="json")
        o["patron"] = patron_de_comercio(m.descripcion)
        items.append(o)
    return {"items": items, "total": total, "limite": limite, "offset": offset}


@router.get("/extractos")
def todos_los_extractos(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Todos los extractos» del usuario: revisados, por revisar, sin procesar, con clave pendiente, con error
    (con su motivo) y anteriores al punto de partida, del más reciente al más antiguo, más los correos de
    extracto sin PDF adjunto. Solo ve lo suyo."""
    estado_traer.persistir_periodos(db, usuario.id)
    depurar_conciliados(db, usuario.id)
    estado_traer.reconciliar_pendientes(db, usuario.id)
    inicio = punto_partida.fecha_inicio(db, usuario.id)
    lista = estado_traer.lista_extractos(db, usuario.id, inicio)
    cuadre_encadenado.anotar_lista(db, usuario.id, lista, inicio)
    return estado_traer.vista_completa(db, usuario.id, inicio, lista=lista)


@router.put("/extractos/{extracto_id}/mes")
def fijar_mes_extracto(
    extracto_id: str,
    data: FijarMesIn,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """La persona fija de qué mes es un extracto cuando no se pudo deducir (o se deducó mal). Se guarda en
    ExtractoCorreo.periodo («julio 2026»)."""
    fila = db.query(ExtractoCorreo).filter(ExtractoCorreo.id == extracto_id, ExtractoCorreo.usuario_id == usuario.id).first()
    if not fila:
        raise HTTPException(status_code=404, detail="Extracto no encontrado")
    try:
        fila.periodo = extractos_vista.periodo_texto(data.mes)
    except ValueError:
        raise HTTPException(status_code=422, detail="Elige un mes válido, por ejemplo 2026-07.")
    db.commit()
    return {"ok": True, "periodo": fila.periodo, "mes": data.mes}
