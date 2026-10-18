"""Regla CENTRAL de deduplicación entre canales de entrada.

Un mismo gasto puede llegar por cinco caminos: lo escribes en la app (manual), lo manda el
atajo de Apple Pay (atajo), lo avisa el correo del banco (correo), aparece en el extracto
(extracto) o viene en un archivo Excel/CSV (importacion). Todos pasan por AQUÍ para decidir
si lo que llega es algo nuevo o algo que ya tenías. Sin esto el mismo café queda 3 o 4 veces.

Las reglas (todas puras salvo el bloque «Base de datos» del final):

1. Mismo canal, mismo aviso  ->  NUNCA duplica. Cada canal deja una HUELLA (id del mensaje de
   Gmail, línea del extracto, id de transacción o huella del disparo del atajo). Si llega otra
   vez (reintento, re-sincronización) se reconoce y se ignora.
2. Canales distintos  ->  es el mismo gasto si coinciden: persona, cuenta (o cuenta del mismo
   banco cuando el canal no sabe cuál), dirección (ingreso/gasto), monto (solo se tolera el
   redondeo), y la fecha cae dentro de la ventana del canal:
       atajo/correo/manual  ->  mismo día o el siguiente (si los dos traen hora real: 6 horas)
       extracto/archivo     ->  ±3 días (la fecha de contabilización del banco cambia)
   El texto del comercio (clave_comercio) solo DESEMPATA, salvo cuando los dos traen hora real
   y no se parecen en nada: ahí tienen que estar a menos de 30 minutos.
3. Emparejamiento 1:1  ->  cada movimiento existente absorbe a UN solo aviso por canal. Dos
   cafés iguales el mismo día son dos movimientos: con 2 existentes y 2 avisos se emparejan
   1 a 1; un tercero es nuevo.
4. Traslados propios y pagos de tarjeta (contabilidad.py) tienen cuentas distintas y
   direcciones opuestas: nunca son duplicados entre sí. Los movimientos que no son de un
   canal (traslados de la app, aportes a metas, ajustes de saldo) no se emparejan jamás.
5. Lo que el usuario borra se recuerda como «descartado»: el correo o extracto equivalente que
   llegue después no lo resucita.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.clave_comercio import clave_comercio
from app.contabilidad import FUENTE_AJUSTE, FUENTE_APORTE_META, FUENTE_TRANSFERENCIA

# ── Canales ───────────────────────────────────────────────────────────────────────────────
ORIGEN_MANUAL = "manual"
ORIGEN_ATAJO = "atajo"
ORIGEN_CORREO = "correo"
ORIGEN_EXTRACTO = "extracto"
ORIGEN_IMPORTACION = "importacion"
ORIGENES = (ORIGEN_MANUAL, ORIGEN_ATAJO, ORIGEN_CORREO, ORIGEN_EXTRACTO, ORIGEN_IMPORTACION)

# Cómo se le dice a cada canal a una persona (insignia «Registrado desde: ...»).
ETIQUETA_CANAL = {
    ORIGEN_MANUAL: "la app",
    ORIGEN_ATAJO: "el atajo",
    ORIGEN_CORREO: "el correo del banco",
    ORIGEN_EXTRACTO: "el extracto",
    ORIGEN_IMPORTACION: "un archivo",
}
ETIQUETA_CORTA = {
    ORIGEN_MANUAL: "app",
    ORIGEN_ATAJO: "atajo",
    ORIGEN_CORREO: "correo",
    ORIGEN_EXTRACTO: "extracto",
    ORIGEN_IMPORTACION: "archivo",
}

ESTADO_VIGENTE = "vigente"
ESTADO_DESCARTADO = "descartado"
ESTADO_NO_DUPLICADO = "no_duplicado"

_FUENTES_ATAJO = {"wallet", "apple_pay", "google_pay", "shortcut", "sms", "cierre_app", "voz", "atajo"}
_FUENTES_IMPORTACION = {"importacion_archivo", "importado_sin_saldo", "csv_import"}
_FUENTES_EXTRACTO = {"conciliacion_auto", "conciliacion_extracto"}
# Movimientos que NO son una compra/ingreso de un canal: nunca se emparejan.
FUENTES_NO_EMPAREJABLES = {FUENTE_TRANSFERENCIA, FUENTE_APORTE_META, FUENTE_AJUSTE}

_GENERICAS = ("movimiento en ", "gasto sin detalle", "ingreso sin detalle")

# Ventanas de fecha y tolerancias (ver el encabezado del módulo).
DIAS_EXTRACTO = 3
DIAS_NORMAL = 1
HORAS_CON_HORA = 6
MINUTOS_SIN_PARECIDO = 30
TOLERANCIA_REDONDEO_COP = 1.0
TOLERANCIA_REDONDEO_OTRA = 0.02


def origen_de_fuente(fuente: str | None, cat_origen: str | None = None) -> str:
    """Canal por el que nació un movimiento VIEJO (sin la columna `origen`), según su fuente."""
    f = (fuente or "").lower()
    if f in _FUENTES_ATAJO or (cat_origen or "") in ("wallet", "atajo", "cierre_app", "voz"):
        return ORIGEN_ATAJO
    if f == "email":
        return ORIGEN_CORREO
    if f in _FUENTES_EXTRACTO:
        return ORIGEN_EXTRACTO
    if f in _FUENTES_IMPORTACION:
        return ORIGEN_IMPORTACION
    return ORIGEN_MANUAL


def filtro_origen(origen: str):
    """Condición SQL «el movimiento nació por este canal» (la columna `origen`, o la deducida de la fuente
    para los movimientos viejos sin ella: igual que `origen_de_movimiento`)."""
    from sqlalchemy import and_, func, not_, or_

    from app.models import Movimiento as M

    fuente, cat = func.coalesce(M.fuente, ""), func.coalesce(M.cat_origen, "")
    atajo = or_(fuente.in_(_FUENTES_ATAJO), cat.in_(("wallet", "atajo", "cierre_app", "voz")))
    viejo = {
        ORIGEN_ATAJO: atajo,
        ORIGEN_CORREO: and_(fuente == "email", not_(atajo)),
        ORIGEN_EXTRACTO: and_(fuente.in_(_FUENTES_EXTRACTO), not_(atajo)),
        ORIGEN_IMPORTACION: and_(fuente.in_(_FUENTES_IMPORTACION), not_(atajo)),
    }
    viejo[ORIGEN_MANUAL] = not_(or_(*viejo.values()))
    return or_(M.origen == origen, and_(or_(M.origen.is_(None), M.origen == ""), viejo[origen]))


def origen_de_movimiento(m) -> str:
    o = getattr(m, "origen", None)
    return o if o in ORIGENES else origen_de_fuente(getattr(m, "fuente", None), getattr(m, "cat_origen", None))


def es_emparejable(m) -> bool:
    return (getattr(m, "fuente", None) or "") not in FUENTES_NO_EMPAREJABLES and getattr(m, "tipo", None) in ("income", "expense")


def es_generica(descripcion: str | None) -> bool:
    d = (descripcion or "").strip().lower()
    return not d or any(d.startswith(g) for g in _GENERICAS)


# ── Huellas de origen ─────────────────────────────────────────────────────────────────────
def huella_correo(gmail_msg_id: str) -> str:
    return f"gmail:{gmail_msg_id}"


def huella_extracto(fingerprint: str, ordinal: int = 1) -> str:
    """Una línea del extracto. El ordinal distingue dos líneas idénticas el mismo día."""
    return f"ext:{fingerprint}#{ordinal}"


def huella_archivo(fingerprint: str, ordinal: int = 1) -> str:
    return f"imp:{fingerprint}#{ordinal}"


def huella_atajo(cuenta_id: str, tipo: str, monto: float, comercio: str | None, momento: datetime,
                 id_transaccion: str | None = None) -> str:
    """Identifica UN disparo del atajo: el mismo comercio, monto y minuto es el mismo disparo (un
    reintento a los pocos segundos). Si el atajo manda el id de la transacción, ese manda."""
    if id_transaccion and str(id_transaccion).strip():
        return f"tx:{str(id_transaccion).strip()[:80]}"
    # El texto completo (no la clave del comercio, que puede quedar vacía: «Tienda A» y «Tienda B» son distintas).
    texto = re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFD", (comercio or "").lower())).strip()
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    base = f"{cuenta_id}|{tipo}|{monto:.2f}|{texto}|{momento.strftime('%Y%m%d%H%M')}"
    return "atajo:" + hashlib.sha1(base.encode()).hexdigest()[:24]


# ── Comparación (pura) ────────────────────────────────────────────────────────────────────
def similitud_comercio(a: str | None, b: str | None) -> float | None:
    """0..1 entre dos textos de comercio; None si alguno no dice nada útil (sin texto no hay
    desempate, pero tampoco se rechaza)."""
    ka, kb = clave_comercio(a or ""), clave_comercio(b or "")
    if not ka or not kb:
        return None
    if ka == kb or ka in kb or kb in ka:
        return 1.0
    ta, tb = set(ka.split()), set(kb.split())
    jaccard = len(ta & tb) / max(len(ta | tb), 1)
    ratio = SequenceMatcher(None, ka, kb).ratio()
    return max(jaccard, ratio if ratio >= 0.75 else 0.0)


@dataclass
class Cand:
    """Un movimiento (existente) o un aviso (entrante) para comparar."""
    id: str
    origen: str
    tipo: str
    monto: float
    fecha: datetime
    cuentas: frozenset
    texto: str = ""
    moneda: str = "COP"
    flexible: bool = False  # el monto pudo cambiar (moneda extranjera, propina): tolerancia amplia
    canales: frozenset = frozenset()  # canales que ya confirmaron este movimiento
    fantasma: bool = False  # un movimiento que el usuario BORRÓ
    con_hora: bool = False  # la fecha trae hora real (no es solo un día)
    ref: object = field(default=None, repr=False, compare=False)

    def hora_real(self) -> bool:
        if not self.con_hora or self.origen in (ORIGEN_MANUAL, ORIGEN_EXTRACTO, ORIGEN_IMPORTACION):
            return False
        return (self.fecha.hour, self.fecha.minute, self.fecha.second) != (0, 0, 0)


def tolerancia_monto(ent: Cand, ex: Cand) -> float:
    """Solo redondeo. La excepción: el extracto contra un registro del atajo (Wallet muestra el
    monto antes de la propina o de la conversión de moneda) y lo marcado como moneda extranjera."""
    if ent.flexible or ex.flexible or {ent.origen, ex.origen} == {ORIGEN_EXTRACTO, ORIGEN_ATAJO}:
        return max(500.0, max(ent.monto, ex.monto) * 0.05)
    moneda = (ex.moneda or ent.moneda or "COP").upper()
    return TOLERANCIA_REDONDEO_COP if moneda == "COP" else TOLERANCIA_REDONDEO_OTRA


def puntaje(ent: Cand, ex: Cand) -> float | None:
    """None si `ent` (lo que llega) NO puede ser el mismo gasto que `ex` (lo que ya hay);
    si puede, un puntaje: menor = más parecido."""
    if ent.tipo != ex.tipo or ent.tipo not in ("income", "expense"):
        return None
    if ent.origen == ex.origen or ent.origen in ex.canales:
        return None  # ese canal ya dijo lo suyo sobre este movimiento: otro igual es otro gasto
    if not (ent.cuentas & ex.cuentas):
        return None
    dif = abs(ent.monto - ex.monto)
    if dif > tolerancia_monto(ent, ex):
        return None
    sim = similitud_comercio(ent.texto, ex.texto)
    largo = {ent.origen, ex.origen} & {ORIGEN_EXTRACTO, ORIGEN_IMPORTACION}
    if largo:
        dias = abs((ent.fecha.date() - ex.fecha.date()).days)
        if dias > DIAS_EXTRACTO:
            return None
        # Si el banco trae la hora, la hora desempata entre compras iguales del mismo día.
        tiempo = abs((ent.fecha - ex.fecha).total_seconds()) / 86400 if (ent.con_hora and ent.origen == ORIGEN_EXTRACTO) \
            else float(dias)
    elif ent.hora_real() and ex.hora_real():
        horas = abs((ent.fecha - ex.fecha).total_seconds()) / 3600
        if horas > HORAS_CON_HORA:
            return None
        if sim == 0.0 and horas * 60 > MINUTOS_SIN_PARECIDO:
            return None  # dos compras distintas con el mismo valor, a horas distintas
        tiempo = horas / 24
    else:
        dias = abs((ent.fecha.date() - ex.fecha.date()).days)
        if dias > DIAS_NORMAL:
            return None
        tiempo = float(dias)
    # Un registro del atajo espera justamente al banco: a igualdad, el extracto prefiere completar ese.
    preferencia = 0.05 if (ent.origen == ORIGEN_EXTRACTO and ex.origen == ORIGEN_ATAJO) else 0.0
    return tiempo + 3 * dif / max(ent.monto, 1.0) - 0.4 * (sim or 0.0) - preferencia


def emparejar(entrantes: list[Cand], existentes: list[Cand]) -> list[tuple[int, int, float]]:
    """Emparejamiento 1:1 entre avisos y movimientos existentes: de todos los pares posibles gana
    el de menor puntaje, y ni el aviso ni el movimiento se usan dos veces. Devuelve
    [(posición del aviso, posición del existente, puntaje)]."""
    pares = []
    for i, ent in enumerate(entrantes):
        for j, ex in enumerate(existentes):
            p = puntaje(ent, ex)
            if p is not None:
                pares.append((p, i, j))
    pares.sort()
    usados_i, usados_j, res = set(), set(), []
    for p, i, j in pares:
        if i in usados_i or j in usados_j:
            continue
        usados_i.add(i)
        usados_j.add(j)
        res.append((i, j, p))
    return res


# ── Enriquecimiento ───────────────────────────────────────────────────────────────────────
def enriquecer(mov, *, descripcion: str | None = None, fecha: datetime | None = None,
               categoria: str | None = None, hora_real: bool = False) -> list[str]:
    """Completa un movimiento con lo que trae mejor el canal que llegó después. Solo agrega: nunca
    pisa lo que la persona escribió. Devuelve qué cambió (para los mensajes)."""
    cambios = []
    if descripcion and not es_generica(descripcion) and es_generica(mov.descripcion):
        mov.descripcion = descripcion
        cambios.append("comercio")
    if hora_real and fecha is not None and mov.fecha is not None:
        imprecisa = (mov.fecha.hour, mov.fecha.minute, mov.fecha.second) == (0, 0, 0) or origen_de_movimiento(mov) == ORIGEN_MANUAL
        if imprecisa and abs((fecha.date() - mov.fecha.date()).days) <= 1 and fecha != mov.fecha:
            mov.fecha = fecha
            cambios.append("hora")
    if categoria and categoria != "Otros" and (mov.categoria or "Otros") == "Otros" and mov.cat_confirmada is False:
        mov.categoria = categoria
        cambios.append("categoría")
    return cambios


# ── Base de datos ─────────────────────────────────────────────────────────────────────────
def _moneda_de_cuentas(db: Session, cuenta_ids) -> dict[str, str]:
    from app.models import Cuenta

    if not cuenta_ids:
        return {}
    return {c.id: (c.moneda or "COP") for c in db.query(Cuenta).filter(Cuenta.id.in_(list(cuenta_ids))).all()}


def canales_de(db: Session, usuario_id: str | None, movimiento_ids) -> dict[str, set[str]]:
    """{movimiento_id: {canales vigentes}} de un lote de movimientos (una consulta por tanda).
    Con `usuario_id=None` no filtra por dueño (los ids ya vienen autorizados: cuentas compartidas)."""
    from app.models import HuellaOrigen

    ids = list(movimiento_ids)
    salida: dict[str, set[str]] = {i: set() for i in ids}
    if not ids:
        return salida
    for i in range(0, len(ids), 500):
        q = db.query(HuellaOrigen.movimiento_id, HuellaOrigen.origen).filter(
            HuellaOrigen.estado == ESTADO_VIGENTE, HuellaOrigen.movimiento_id.in_(ids[i:i + 500]))
        if usuario_id is not None:
            q = q.filter(HuellaOrigen.usuario_id == usuario_id)
        for r in q.all():
            salida.setdefault(r[0], set()).add(r[1])
    return salida


def anotar_canales(db: Session, movs: list) -> list:
    """Agrega a cada movimiento (atributo suelto, no se guarda) `canales`: la lista de canales que
    lo confirmaron, para la insignia «Registrado desde...». Devuelve la misma lista."""
    por_mov = canales_de(db, None, [m.id for m in movs])
    for m in movs:
        m.canales = insignia(origen_de_movimiento(m), por_mov.get(m.id, set()))
    return movs


def _foto(mov) -> dict:
    return dict(cuenta_id=mov.cuenta_id, tipo=mov.tipo, monto=mov.monto, fecha=mov.fecha,
                clave=clave_comercio(mov.descripcion or "") or None)


def buscar_huella(db: Session, usuario_id: str, huella: str, estados=None):
    from app.models import HuellaOrigen

    q = db.query(HuellaOrigen).filter(HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.huella == huella)
    if estados:
        q = q.filter(HuellaOrigen.estado.in_(estados))
    return q.first()


def registrar_canal(db: Session, mov, origen: str, huella: str | None):
    """Anota que `origen` confirmó este movimiento (idempotente por canal+movimiento). Sin commit."""
    from app.models import HuellaOrigen

    huella = huella or f"{origen}:{mov.id}"
    previa = db.query(HuellaOrigen).filter(
        HuellaOrigen.usuario_id == mov.usuario_id, HuellaOrigen.movimiento_id == mov.id,
        HuellaOrigen.origen == origen, HuellaOrigen.estado == ESTADO_VIGENTE,
    ).first()
    if previa:
        return previa
    fila = HuellaOrigen(usuario_id=mov.usuario_id, movimiento_id=mov.id, huella=huella, origen=origen,
                        estado=ESTADO_VIGENTE, **_foto(mov))
    db.add(fila)
    return fila


def nuevo_movimiento(db: Session, mov, origen: str, huella: str | None = None):
    """Marca un movimiento recién creado con su canal de origen y su huella. Sin commit.
    Debe llamarse con `mov` ya agregado a la sesión (se hace flush para tener el id)."""
    mov.origen = origen
    mov.huella_externa = huella
    db.flush()
    registrar_canal(db, mov, origen, huella)


def siguiente_ordinal(db: Session, usuario_id: str, prefijo: str) -> int:
    """Para huellas de líneas idénticas (dos envíos de $20.000 el mismo día): 1, 2, 3..."""
    from app.models import HuellaOrigen

    db.flush()
    n = db.query(HuellaOrigen).filter(HuellaOrigen.usuario_id == usuario_id,
                                      HuellaOrigen.huella.like(f"{prefijo}#%")).count()
    return n + 1


def cand_de_movimiento(m, canales: set[str], moneda: str = "COP", cuentas=None) -> Cand:
    return Cand(
        id=m.id, origen=origen_de_movimiento(m), tipo=m.tipo, monto=float(m.monto or 0), fecha=m.fecha,
        cuentas=frozenset(cuentas or {m.cuenta_id}), texto=m.descripcion or "", moneda=moneda,
        flexible="Original:" in (m.notas or ""), canales=frozenset(canales | {origen_de_movimiento(m)}),
        con_hora=True, ref=m,
    )


def existentes_para(db: Session, usuario_id: str, cuenta_ids, desde: datetime, hasta: datetime,
                    fantasmas: bool = False, excluir_ids=()) -> list[Cand]:
    """Candidatos a 'ya lo tenía': movimientos del usuario en esas cuentas y fechas (y, si se pide,
    los que el usuario borró, como fantasmas)."""
    from app.models import HuellaOrigen, Movimiento

    cuenta_ids = set(cuenta_ids)
    if not cuenta_ids:
        return []
    db.flush()  # sin autoflush: lo que se acaba de agregar en esta misma operación también cuenta
    movs = db.query(Movimiento).filter(
        Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id.in_(list(cuenta_ids)),
        Movimiento.fecha >= desde, Movimiento.fecha <= hasta,
        Movimiento.tipo.in_(("income", "expense")),
        ~Movimiento.fuente.in_(list(FUENTES_NO_EMPAREJABLES)),
    ).all()
    excluidos = set(excluir_ids)
    movs = [m for m in movs if m.id not in excluidos]
    canales = canales_de(db, usuario_id, [m.id for m in movs])
    monedas = _moneda_de_cuentas(db, cuenta_ids)
    res = [cand_de_movimiento(m, canales.get(m.id, set()), monedas.get(m.cuenta_id, "COP")) for m in movs]
    if fantasmas:
        res.extend(fantasmas_de(db, usuario_id, cuenta_ids, desde, hasta, monedas))
    return res


def fantasmas_de(db: Session, usuario_id: str, cuenta_ids, desde: datetime, hasta: datetime,
                 monedas: dict | None = None) -> list[Cand]:
    """Lo que el usuario BORRÓ en esas cuentas y fechas, como candidatos «fantasma»: absorben el
    correo/extracto equivalente que llegue después (para que no resucite)."""
    from app.models import HuellaOrigen

    cuenta_ids = set(cuenta_ids)
    if not cuenta_ids:
        return []
    monedas = monedas if monedas is not None else _moneda_de_cuentas(db, cuenta_ids)
    filas = db.query(HuellaOrigen).filter(
        HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.estado == ESTADO_DESCARTADO,
        HuellaOrigen.cuenta_id.in_(list(cuenta_ids)), HuellaOrigen.fecha >= desde, HuellaOrigen.fecha <= hasta,
        HuellaOrigen.tipo.in_(("income", "expense")),
    ).all()
    por_mov: dict[str, list] = {}
    for f in filas:
        por_mov.setdefault(f.movimiento_id or f.id, []).append(f)
    res = []
    for mid, fs in por_mov.items():
        base = sorted(fs, key=lambda x: x.creado_en or datetime.min)[0]
        res.append(Cand(
            id=mid, origen=base.origen, tipo=base.tipo, monto=float(base.monto or 0), fecha=base.fecha,
            cuentas=frozenset({base.cuenta_id}), texto=base.clave or "", moneda=monedas.get(base.cuenta_id, "COP"),
            canales=frozenset(f.origen for f in fs), fantasma=True, con_hora=True, ref=fs,
        ))
    return res


def huellas_extracto_descartadas(db: Session, usuario_id: str, cuenta_id: str, prefijo: str = "ext:",
                                 origen: str = ORIGEN_EXTRACTO) -> dict[str, int]:
    """{huella de línea (fingerprint): cuántas veces se borró} de los movimientos que vinieron de un
    extracto (o archivo, con prefijo 'imp:') de esa cuenta y el usuario eliminó."""
    from app.models import HuellaOrigen

    cuenta = {}
    for (h,) in db.query(HuellaOrigen.huella).filter(
        HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.estado == ESTADO_DESCARTADO,
        HuellaOrigen.origen == origen, HuellaOrigen.cuenta_id == cuenta_id,
        HuellaOrigen.huella.like(f"{prefijo}%"),
    ).all():
        fp = h[len(prefijo):].rsplit("#", 1)[0]
        cuenta[fp] = cuenta.get(fp, 0) + 1
    return cuenta


def buscar_pareja(db: Session, usuario_id: str, ent: Cand, *, fantasmas: bool = False,
                  excluir_ids=()) -> Cand | None:
    """El movimiento existente (o fantasma) que `ent` ya tiene registrado, o None si es algo nuevo."""
    margen = timedelta(days=DIAS_EXTRACTO + 1 if ent.origen in (ORIGEN_EXTRACTO, ORIGEN_IMPORTACION) else DIAS_NORMAL + 3)
    existentes = existentes_para(db, usuario_id, ent.cuentas, ent.fecha - margen, ent.fecha + margen, fantasmas, excluir_ids)
    for i, j, _ in emparejar([ent], existentes):
        return existentes[j]
    return None


def confirmar_por_canal(db: Session, mov, origen: str, huella: str | None, *, descripcion: str | None = None,
                        fecha: datetime | None = None, categoria: str | None = None,
                        hora_real: bool = False) -> list[str]:
    """Un segundo canal confirma un movimiento que ya existía: se anota el canal, se enriquece con
    lo mejor de cada uno y, si el banco mismo lo corrobora y era un registro rápido por confirmar
    con categoría clara, queda confirmado. Sin commit."""
    registrar_canal(db, mov, origen, huella)
    cambios = enriquecer(mov, descripcion=descripcion, fecha=fecha, categoria=categoria, hora_real=hora_real)
    if origen in (ORIGEN_CORREO, ORIGEN_EXTRACTO) and mov.cat_confirmada is False \
            and mov.cat_origen in ("wallet", "atajo", "cierre_app", "voz") and (mov.categoria or "Otros") != "Otros":
        mov.cat_confirmada = True
        cambios.append("confirmado")
    return cambios


# ── Borrado: lo que se borra no resucita ──────────────────────────────────────────────────
def descartar_movimiento(db: Session, mov) -> None:
    """Se llama ANTES de borrar un movimiento que el usuario eliminó: sus canales pasan a
    'descartado' (con la foto del movimiento) y los correos que lo habían reconocido se ocultan.
    Sin commit."""
    from app.models import CorreoGasto, HuellaOrigen

    filas = db.query(HuellaOrigen).filter(HuellaOrigen.usuario_id == mov.usuario_id,
                                          HuellaOrigen.movimiento_id == mov.id,
                                          HuellaOrigen.estado == ESTADO_VIGENTE).all()
    foto = _foto(mov)
    if not filas:
        # Movimiento viejo: se deduce su canal para que igual quede el fantasma.
        origen = origen_de_movimiento(mov)
        filas = [HuellaOrigen(usuario_id=mov.usuario_id, movimiento_id=mov.id, origen=origen,
                              huella=mov.huella_externa or f"{origen}:{mov.id}")]
        db.add(filas[0])
    tiene = {f.origen for f in filas}
    for c in db.query(CorreoGasto).filter(CorreoGasto.usuario_id == mov.usuario_id,
                                          CorreoGasto.movimiento_id == mov.id).all():
        if c.estado == "ya_registrado":
            c.estado = "descartado"
        if ORIGEN_CORREO not in tiene:
            db.add(HuellaOrigen(usuario_id=mov.usuario_id, movimiento_id=mov.id, origen=ORIGEN_CORREO,
                                huella=huella_correo(c.gmail_msg_id), estado=ESTADO_DESCARTADO, **foto))
    for f in filas:
        f.estado = ESTADO_DESCARTADO
        for k, v in foto.items():
            setattr(f, k, v)


def olvidar_movimiento(db: Session, mov) -> None:
    """Quita las huellas de un movimiento que se borra SIN que cuente como descarte del usuario
    (p. ej. «deshacer lo importado solo»: la línea debe poder volver a aparecer)."""
    from app.models import HuellaOrigen

    db.query(HuellaOrigen).filter(HuellaOrigen.usuario_id == mov.usuario_id,
                                  HuellaOrigen.movimiento_id == mov.id).delete(synchronize_session=False)


def reasignar_canales(db: Session, origen_mov, destino_mov) -> None:
    """Al unir dos movimientos: los canales del que se va pasan al que se queda."""
    from app.models import CorreoGasto, HuellaOrigen

    filas = db.query(HuellaOrigen).filter(HuellaOrigen.usuario_id == origen_mov.usuario_id,
                                          HuellaOrigen.movimiento_id == origen_mov.id).all()
    if not filas:
        registrar_canal(db, origen_mov, origen_de_movimiento(origen_mov), origen_mov.huella_externa)
        db.flush()
        filas = db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == origen_mov.id).all()
    for f in filas:
        f.movimiento_id = destino_mov.id
        for k, v in _foto(destino_mov).items():
            setattr(f, k, v)
    for c in db.query(CorreoGasto).filter(CorreoGasto.usuario_id == origen_mov.usuario_id,
                                          CorreoGasto.movimiento_id == origen_mov.id).all():
        c.movimiento_id = destino_mov.id
    if destino_mov.conciliado_en is None and origen_mov.conciliado_en is not None:
        destino_mov.conciliado_en, destino_mov.extracto_id = origen_mov.conciliado_en, origen_mov.extracto_id
    if not destino_mov.huella_externa and origen_mov.huella_externa:
        destino_mov.huella_externa = origen_mov.huella_externa


# ── Correos: que no aparezcan en «Por revisar» si ya existe el movimiento ─────────────────
def _candidato_de_correo(c, cuentas: list) -> Cand | None:
    from app.extractos_gmail import candidatas_banco, detectar_ultimos4, inferir_cuenta_por_remitente
    from app.gmail_extract import detectar_tipo, fecha_movimiento_info
    from app.utiles import utc_a_co

    if (c.monto or 0) <= 0:
        return None
    texto = f"{c.asunto} {c.snippet}"
    banco, _sug, falta = inferir_cuenta_por_remitente(c.remitente, cuentas, texto)
    if not banco or falta:
        return None  # sin banco reconocido no se adivina la cuenta
    cands, _ = candidatas_banco(banco, detectar_ultimos4(texto), cuentas, texto)
    ids = frozenset(x.id for x in cands if (x.moneda or "COP").upper() == (c.moneda or "COP").upper())
    if not ids:
        return None
    tipo = c.tipo_sugerido if c.tipo_sugerido in ("income", "expense") else detectar_tipo(texto)
    info = fecha_movimiento_info(c)  # la fecha que dice el correo (no la de lectura) para emparejar
    fecha = info["fecha"] or utc_a_co(c.recibido_en or c.creado_en)
    return Cand(
        id=c.id, origen=ORIGEN_CORREO, tipo=tipo, monto=float(c.monto), fecha=fecha, cuentas=ids,
        texto=c.comercio or "", moneda=(c.moneda or "COP"), con_hora=info["con_hora"], ref=c,
    )


def absorber_correos(db: Session, usuario_id: str, *, cuentas: list | None = None) -> dict:
    """Recorre los correos 'pendiente' del usuario y, a los que ya tienen su movimiento (por el
    atajo, a mano, el extracto...), los marca 'ya_registrado' enlazados a él: no salen en «Por
    revisar». Los que coinciden con algo que el usuario BORRÓ pasan a 'descartado'. Emparejamiento
    1:1 global (cada movimiento absorbe un solo correo). Idempotente. Hace commit solo si cambió algo.
    Devuelve {"ya_registrados": n, "descartados": n}."""
    from app.models import CorreoGasto, Cuenta

    db.flush()  # la sesión no hace autoflush: los correos recién leídos tienen que estar en la base
    pend = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "pendiente",
                                        CorreoGasto.monto > 0).all()
    res = {"ya_registrados": 0, "descartados": 0}
    if not pend:
        return res
    from app.models import HuellaOrigen

    excepciones = {h for (h,) in db.query(HuellaOrigen.huella).filter(
        HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.estado == ESTADO_NO_DUPLICADO).all()}
    cuentas = cuentas if cuentas is not None else db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()
    entrantes = []
    for c in pend:
        if huella_correo(c.gmail_msg_id) in excepciones:
            continue
        e = _candidato_de_correo(c, cuentas)
        if e:
            entrantes.append(e)
    if not entrantes:
        return res
    desde = min(e.fecha for e in entrantes) - timedelta(days=DIAS_NORMAL + 1)
    hasta = max(e.fecha for e in entrantes) + timedelta(days=DIAS_NORMAL + 1)
    ids = set().union(*[e.cuentas for e in entrantes])
    existentes = existentes_para(db, usuario_id, ids, desde, hasta, fantasmas=True)
    for i, j, _ in emparejar(entrantes, existentes):
        c, ex = entrantes[i].ref, existentes[j]
        if ex.fantasma:
            c.estado = "descartado"
            c.movimiento_id = ex.id
            db.add(HuellaOrigen(usuario_id=usuario_id, movimiento_id=ex.id, huella=huella_correo(c.gmail_msg_id),
                                origen=ORIGEN_CORREO, estado=ESTADO_DESCARTADO, cuenta_id=next(iter(ex.cuentas)),
                                tipo=ex.tipo, monto=ex.monto, fecha=ex.fecha))
            res["descartados"] += 1
            continue
        mov = ex.ref
        c.estado = "ya_registrado"
        c.movimiento_id = mov.id
        confirmar_por_canal(db, mov, ORIGEN_CORREO, huella_correo(c.gmail_msg_id), descripcion=c.comercio,
                            fecha=entrantes[i].fecha, categoria=c.categoria_sugerida, hora_real=True)
        res["ya_registrados"] += 1
    if res["ya_registrados"] or res["descartados"]:
        db.commit()
    return res


def mostrar_de_todos_modos(db: Session, usuario_id: str, correo) -> None:
    """El usuario dice «No es duplicado» sobre un correo que se había dado por registrado: vuelve a
    'Por revisar' y no se vuelve a absorber. Sin commit."""
    from app.models import HuellaOrigen

    huella = huella_correo(correo.gmail_msg_id)
    if correo.movimiento_id:
        db.query(HuellaOrigen).filter(
            HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.movimiento_id == correo.movimiento_id,
            HuellaOrigen.huella == huella, HuellaOrigen.estado == ESTADO_VIGENTE,
        ).delete(synchronize_session=False)
    correo.estado = "pendiente"
    correo.movimiento_id = None
    if not buscar_huella(db, usuario_id, huella, (ESTADO_NO_DUPLICADO,)):
        db.add(HuellaOrigen(usuario_id=usuario_id, huella=huella, origen=ORIGEN_CORREO, estado=ESTADO_NO_DUPLICADO))


def recuperar_correo(db: Session, usuario_id: str, correo, cuentas: list | None = None) -> str:
    """El usuario quiere de vuelta un correo 'descartado' (o 'ignorado' con monto): vuelve a «Por revisar».
    Se quita la huella fantasma de ESE correo y se anota la excepción «no es duplicado» solo para él, así
    `absorber_correos` no lo vuelve a descartar contra el movimiento que se borró. Los anti-duplicados reales
    siguen: si hoy existe un movimiento vigente equivalente, queda 'ya_registrado'. Devuelve el estado final.
    Sin commit."""
    from app.models import Cuenta, HuellaOrigen

    huella = huella_correo(correo.gmail_msg_id)
    db.query(HuellaOrigen).filter(
        HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.huella == huella,
        HuellaOrigen.estado == ESTADO_DESCARTADO,
    ).delete(synchronize_session=False)
    correo.estado = "pendiente"
    correo.movimiento_id = None
    if not buscar_huella(db, usuario_id, huella, (ESTADO_NO_DUPLICADO,)):
        db.add(HuellaOrigen(usuario_id=usuario_id, huella=huella, origen=ORIGEN_CORREO, estado=ESTADO_NO_DUPLICADO))
    db.flush()
    cuentas = cuentas if cuentas is not None else db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()
    ent = _candidato_de_correo(correo, cuentas)
    pareja = buscar_pareja(db, usuario_id, ent, fantasmas=False) if ent else None
    if pareja:
        correo.estado = "ya_registrado"
        correo.movimiento_id = pareja.ref.id
        confirmar_por_canal(db, pareja.ref, ORIGEN_CORREO, huella, descripcion=correo.comercio, fecha=ent.fecha,
                            categoria=correo.categoria_sugerida, hora_real=True)
    return correo.estado


# ── Datos que ya existen: «Buscar duplicados» ─────────────────────────────────────────────
def _hermanas(cuentas: list) -> dict[str, frozenset]:
    """Para cada cuenta, ella misma y las del MISMO banco (por el nombre): el atajo a veces
    guarda en la tarjeta equivocada del mismo banco."""
    from app.cuentas_banco import palabras_marca

    marcas = {c.id: palabras_marca(c.nombre) for c in cuentas}
    return {
        c.id: frozenset({c.id} | {o.id for o in cuentas if o.id != c.id and marcas[c.id] & marcas[o.id]
                                  and (o.moneda or "COP") == (c.moneda or "COP")})
        for c in cuentas
    }


def grupos_posibles_duplicados(db: Session, usuario_id: str, dias: int = 120, limite: int = 100) -> list[dict]:
    """Grupos de movimientos que PARECEN el mismo gasto llegado por canales distintos. Solo
    sugiere (nada se borra solo). Cada grupo tiene como máximo un movimiento por canal; si hay
    dos cafés iguales y dos registros, salen emparejados 1 a 1 (dos grupos) y un tercero sin
    pareja no sale. Los que el usuario marcó «No es duplicado» no vuelven a salir."""
    from app.models import Cuenta, HuellaOrigen, Movimiento

    from app.utiles import ahora_co

    desde = ahora_co() - timedelta(days=dias + 1)
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()
    hermanas = _hermanas(cuentas)
    monedas = {c.id: (c.moneda or "COP") for c in cuentas}
    movs = db.query(Movimiento).filter(
        Movimiento.usuario_id == usuario_id, Movimiento.fecha >= desde,
        Movimiento.tipo.in_(("income", "expense")), ~Movimiento.fuente.in_(list(FUENTES_NO_EMPAREJABLES)),
    ).all()
    canales = canales_de(db, usuario_id, [m.id for m in movs])
    excepciones = {h for (h,) in db.query(HuellaOrigen.huella).filter(
        HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.estado == ESTADO_NO_DUPLICADO,
        HuellaOrigen.huella.like("par:%")).all()}
    cs = []
    for m in movs:
        c = cand_de_movimiento(m, canales.get(m.id, set()), monedas.get(m.cuenta_id, "COP"), hermanas.get(m.cuenta_id))
        # Aquí cada movimiento compara con los OTROS por su canal de origen (no por todos los que lo confirmaron).
        c.canales = frozenset({c.origen})
        cs.append(c)

    # Aristas entre movimientos de canales distintos, en una sola pasada por (tipo, monto).
    por_tipo: dict[str, list[int]] = {}
    for i, c in enumerate(cs):
        por_tipo.setdefault(c.tipo, []).append(i)
    aristas = []
    for idxs in por_tipo.values():
        idxs.sort(key=lambda i: cs[i].monto)
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                if cs[j].monto - cs[i].monto > max(500.0, cs[j].monto * 0.05):
                    break
                p = puntaje(cs[i], cs[j])
                if p is not None and f"par:{':'.join(sorted((cs[i].id, cs[j].id)))}" not in excepciones:
                    aristas.append((p, i, j))
    aristas.sort()
    # Se une en grupos sin repetir canal (1:1 por canal).
    grupo_de: dict[int, int] = {}
    grupos: dict[int, list[int]] = {}
    for p, i, j in aristas:
        gi, gj = grupo_de.get(i), grupo_de.get(j)
        if gi is None and gj is None:
            g = len(grupos)
            grupos[g] = [i, j]
            grupo_de[i] = grupo_de[j] = g
        elif gi is not None and gj is None:
            if cs[j].origen not in {cs[k].origen for k in grupos[gi]} and all(puntaje(cs[j], cs[k]) is not None for k in grupos[gi]):
                grupos[gi].append(j)
                grupo_de[j] = gi
        elif gj is not None and gi is None:
            if cs[i].origen not in {cs[k].origen for k in grupos[gj]} and all(puntaje(cs[i], cs[k]) is not None for k in grupos[gj]):
                grupos[gj].append(i)
                grupo_de[i] = gj
    nombres = {c.id: c.nombre for c in cuentas}
    salida = []
    for g in grupos.values():
        miembros = [cs[k].ref for k in g]
        miembros.sort(key=lambda m: m.fecha)
        elegido = max(miembros, key=_valor_para_conservar)
        salida.append({
            "id": hashlib.sha1("|".join(sorted(m.id for m in miembros)).encode()).hexdigest()[:16],
            "sugerido_conservar": elegido.id,
            "movimientos": [{
                "id": m.id, "fecha": m.fecha, "descripcion": m.titulo or m.descripcion, "titulo": m.titulo, "categoria": m.categoria, "tipo": m.tipo,
                "monto": m.monto, "cuenta_id": m.cuenta_id, "cuenta_nombre": nombres.get(m.cuenta_id, ""),
                "origen": origen_de_movimiento(m), "canal": ETIQUETA_CANAL[origen_de_movimiento(m)],
                "conciliado": m.conciliado_en is not None, "confirmado": m.cat_confirmada is not False,
            } for m in miembros],
        })
    salida.sort(key=lambda s: max(m["fecha"] for m in s["movimientos"]), reverse=True)
    return salida[:limite]


def _valor_para_conservar(m) -> tuple:
    """Cuál conviene conservar al unir: el conciliado con el banco, el que la persona ya confirmó,
    el que tiene un comercio de verdad y, a igual, el más completo."""
    return (m.conciliado_en is not None, m.cat_confirmada is not False, not es_generica(m.descripcion),
            (m.categoria or "Otros") != "Otros", len(m.descripcion or ""))


def marcar_no_duplicados(db: Session, usuario_id: str, ids: list[str]) -> int:
    """«No es duplicado»: todas las parejas del grupo dejan de sugerirse. Sin commit."""
    from app.models import HuellaOrigen

    n = 0
    ids = sorted(set(ids))
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            huella = f"par:{ids[a]}:{ids[b]}"
            if not buscar_huella(db, usuario_id, huella, (ESTADO_NO_DUPLICADO,)):
                db.add(HuellaOrigen(usuario_id=usuario_id, huella=huella, origen=ORIGEN_MANUAL,
                                    estado=ESTADO_NO_DUPLICADO, movimiento_id=ids[a]))
                n += 1
    return n


def calcular_huellas_viejas(db: Session, aplicar: bool = False, lote: int = 2000) -> dict:
    """Datos de ANTES de esta regla: pone `origen` a cada movimiento según su fuente y crea las
    huellas de canal que ya se pueden deducir (correo aprobado -> su mensaje de Gmail; movimiento
    conciliado -> el extracto). Idempotente: correrlo dos veces no cambia nada la segunda vez.
    Con `aplicar=False` (por defecto) solo cuenta lo que haría. Devuelve los conteos."""
    from app.models import CorreoGasto, HuellaOrigen, Movimiento

    res = {"origen_asignado": 0, "huellas_correo": 0, "huellas_extracto": 0}
    while True:
        movs = db.query(Movimiento).filter(Movimiento.origen.is_(None)).limit(lote).all()
        if not movs:
            break
        for m in movs:
            res["origen_asignado"] += 1
            if aplicar:
                m.origen = origen_de_fuente(m.fuente, m.cat_origen)
        if not aplicar:
            res["origen_asignado"] = db.query(Movimiento).filter(Movimiento.origen.is_(None)).count()
            break
        db.commit()
    tiene = {(r[0], r[1]) for r in db.query(HuellaOrigen.movimiento_id, HuellaOrigen.origen).filter(
        HuellaOrigen.estado == ESTADO_VIGENTE).all()}
    for c in db.query(CorreoGasto).filter(CorreoGasto.estado.in_(("aprobado", "ya_registrado")),
                                          CorreoGasto.movimiento_id.isnot(None)).all():
        m = db.query(Movimiento).filter(Movimiento.id == c.movimiento_id).first()
        if m is None or (m.id, ORIGEN_CORREO) in tiene:
            continue
        res["huellas_correo"] += 1
        tiene.add((m.id, ORIGEN_CORREO))
        if aplicar:
            registrar_canal(db, m, ORIGEN_CORREO, huella_correo(c.gmail_msg_id))
            if not m.huella_externa and origen_de_movimiento(m) == ORIGEN_CORREO:
                m.huella_externa = huella_correo(c.gmail_msg_id)
    for m in db.query(Movimiento).filter(Movimiento.conciliado_en.isnot(None)).all():
        if (m.id, ORIGEN_EXTRACTO) in tiene:
            continue
        res["huellas_extracto"] += 1
        tiene.add((m.id, ORIGEN_EXTRACTO))
        if aplicar:
            registrar_canal(db, m, ORIGEN_EXTRACTO, f"ext:previo:{m.extracto_id or m.id}")
    if aplicar:
        db.commit()
    return res


def insignia(origen: str, canales: set[str]) -> list[str]:
    """Canales que confirmaron un movimiento, en orden de llegada lógico (para la insignia)."""
    todos = set(canales) | {origen}
    return [o for o in ORIGENES if o in todos]
