"""Pantalla única 'Sincronización': qué ya se concilió, qué falta y qué hay que preguntar.

Todo se CALCULA con lo que ya existe (extractos_correo, historial_extractos,
movimientos.conciliado_en / cat_confirmada, correos_gastos): no hay tablas ni
columnas nuevas y ninguna regla se duplica (la bandeja y 'por revisar' se
importan de movimientos.py). Solo se cuentan filas, no se suma dinero; donde
se sume, debe usarse contabilidad.py.
"""
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, not_
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.autocat import patron_de_comercio
from app.compartidos import cuentas_ids_accesibles
from app.database import get_db
from app.extractos_gmail import _sin_acentos, banco_por_remitente, cuentas_del_banco
from app.models import CorreoGasto, Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, SyncGmail
from app.routers.movimientos import _PENDIENTE_REVISION
from app.schemas import MovimientoOut
from app.utiles import ahora_co
from app.wallet import FUENTES_POR_CONFIRMAR

router = APIRouter(prefix="/sincronizacion", tags=["sincronizacion"])

MESES_GRILLA = 6
DIAS_BANDEJA = 14  # la misma ventana de GET /movimientos/por-confirmar

_NOMBRES_MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_MES_NUM = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_FECHA_DMY = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")
_FECHA_YMD = re.compile(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})")
_MES_ANIO = re.compile(r"\b(" + "|".join(_MES_NUM) + r")\s+(?:de\s+)?(20\d{2})\b")


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


def mes_del_extracto(periodo: str, recibido_en: datetime | None) -> str | None:
    """Mes ('AAAA-MM') al que pertenece un extracto. Con rango de fechas vale el
    mes en que TERMINA (el corte); 'junio 2026' vale junio. Sin periodo se
    supone el mes anterior a la fecha en que llegó el correo (los extractos
    llegan al cerrar el periodo). None si no hay con qué decidir."""
    texto = _sin_acentos(periodo or "")
    fechas = []
    for m in _FECHA_DMY.finditer(texto):
        fechas.append((int(m.group(3)), int(m.group(2))))
    if not fechas:
        for m in _FECHA_YMD.finditer(texto):
            fechas.append((int(m.group(1)), int(m.group(2))))
    if fechas:
        a, mes = fechas[-1]
        if 1 <= mes <= 12:
            return _clave(a, mes)
    m = _MES_ANIO.search(texto)
    if m:
        return _clave(int(m.group(2)), _MES_NUM[m.group(1)])
    if recibido_en:
        a, mes = recibido_en.year, recibido_en.month - 1
        if mes == 0:
            a, mes = a - 1, 12
        return _clave(a, mes)
    return None


def estado_celda(*, movimientos: int, conciliados: int, extractos_procesados: int,
                 extractos_nuevos: int, extractos_falta_clave: int) -> str:
    """Estado de una celda cuenta x mes. Prioridad: un extracto ya procesado manda;
    si no, lo que espera acción (clave, conciliar); si no, la evidencia de
    movimientos conciliados; si no, hay movimientos sin extracto; si no, vacío."""
    if extractos_procesados:
        return "conciliado"
    if extractos_falta_clave:
        return "falta_clave"
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


def _cola_categorizar(db: Session, ids_accesibles: list[str], desde_bandeja: datetime):
    """'Otros' o categorizados solos sin confirmar, salvo los que ya están en la
    bandeja '¿son tuyos?' (esos se resuelven allí y no se cuentan dos veces)."""
    return db.query(Movimiento).filter(
        Movimiento.cuenta_id.in_(ids_accesibles),
        _PENDIENTE_REVISION,
        not_(_cond_bandeja(ids_accesibles, desde_bandeja)),
    )


def _sin_cuenta(db: Session, usuario_id: str, cuentas: list[Cuenta], extractos: list[ExtractoCorreo]) -> list[dict]:
    """Bancos detectados en correos/extractos pendientes para los que no hay cuenta."""
    por_banco: dict[str, dict] = {}

    filas = (
        db.query(CorreoGasto.remitente, func.count(CorreoGasto.id))
        .filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "pendiente", CorreoGasto.monto > 0)
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


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


@router.get("/estado")
def estado(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Todo lo que la pantalla necesita en una sola llamada: grilla cuentas x
    meses, bancos sin cuenta y la lista ordenada de tareas pendientes."""
    hoy = ahora_co()
    meses = ultimos_meses(hoy)
    claves = [_clave(a, m) for a, m in meses]
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).order_by(Cuenta.nombre).all()
    ids_cuentas = [c.id for c in cuentas]
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)

    # ── Movimientos por cuenta y mes: 1 consulta agrupada por mes (índice cuenta+fecha).
    conteo: dict[tuple[str, str], dict] = {}
    if ids_cuentas:
        for (a, m), clave in zip(meses, claves):
            sig = _siguiente(a, m)
            filas = (
                db.query(
                    Movimiento.cuenta_id,
                    func.count(Movimiento.id),
                    func.coalesce(func.sum(case((Movimiento.conciliado_en.isnot(None), 1), else_=0)), 0),
                    func.coalesce(func.sum(case((Movimiento.cat_confirmada.is_(False), 1), else_=0)), 0),
                )
                .filter(
                    Movimiento.cuenta_id.in_(ids_cuentas),
                    Movimiento.fecha >= _inicio_mes(a, m),
                    Movimiento.fecha < _inicio_mes(*sig),
                )
                .group_by(Movimiento.cuenta_id)
                .all()
            )
            for cuenta_id, total, conc, por_conf in filas:
                conteo[(cuenta_id, clave)] = {"movimientos": int(total), "conciliados": int(conc), "por_confirmar": int(por_conf)}

    # ── Extractos de Gmail (solo metadatos, pocos): a qué cuenta y mes pertenecen.
    extractos = (
        db.query(ExtractoCorreo)
        .filter(ExtractoCorreo.usuario_id == usuario.id, ExtractoCorreo.estado.in_(("nuevo", "falta_clave", "procesado")))
        .all()
    )
    historiales = {
        h_id: cuenta_id
        for h_id, cuenta_id in db.query(HistorialExtracto.id, HistorialExtracto.cuenta_id).filter(
            HistorialExtracto.usuario_id == usuario.id,
            HistorialExtracto.id.in_([e.historial_id for e in extractos if e.historial_id] or [""]),
        )
    }
    ext_celda: dict[tuple[str, str], dict] = {}
    for e in extractos:
        cuenta_id = historiales.get(e.historial_id) if e.estado == "procesado" else e.cuenta_sugerida_id
        clave = mes_del_extracto(e.periodo, e.recibido_en)
        if not cuenta_id or not clave:
            continue
        d = ext_celda.setdefault((cuenta_id, clave), {"procesado": 0, "nuevo": 0, "falta_clave": 0})
        d[e.estado] += 1

    filas_cuentas = []
    for c in cuentas:
        celdas = []
        for clave in claves:
            cnt = conteo.get((c.id, clave), {"movimientos": 0, "conciliados": 0, "por_confirmar": 0})
            ex = ext_celda.get((c.id, clave), {"procesado": 0, "nuevo": 0, "falta_clave": 0})
            celdas.append({
                "mes": clave,
                "estado": estado_celda(
                    movimientos=cnt["movimientos"], conciliados=cnt["conciliados"],
                    extractos_procesados=ex["procesado"], extractos_nuevos=ex["nuevo"],
                    extractos_falta_clave=ex["falta_clave"],
                ),
                **cnt,
                "extractos": ex["procesado"] + ex["nuevo"] + ex["falta_clave"],
            })
        filas_cuentas.append({"id": c.id, "nombre": c.nombre, "icono": c.icono, "meses": celdas})

    sin_cuenta = _sin_cuenta(db, usuario.id, cuentas, extractos)

    # ── Tareas, en el orden en que conviene resolverlas.
    n_falta_clave = sum(1 for e in extractos if e.estado == "falta_clave")
    n_por_conciliar = sum(1 for e in extractos if e.estado == "nuevo")
    desde_bandeja = hoy - timedelta(days=DIAS_BANDEJA)
    n_categorizar = _cola_categorizar(db, ids_accesibles, desde_bandeja).count()
    n_confirmar = db.query(func.count(Movimiento.id)).filter(_cond_bandeja(ids_accesibles, desde_bandeja)).scalar() or 0
    n_correos = (
        db.query(func.count(CorreoGasto.id))
        .filter(CorreoGasto.usuario_id == usuario.id, CorreoGasto.estado == "pendiente", CorreoGasto.monto > 0)
        .scalar() or 0
    )
    candidatas = [
        ("falta_clave", "Falta la clave del PDF", "Guárdala y abro estos extractos por ti.", n_falta_clave, "/sincronizacion#clave"),
        ("extractos_por_conciliar", "Extractos por conciliar",
         "Cruza tu extracto con lo que registraste.", n_por_conciliar, "/sincronizacion#extractos"),
        ("sin_cuenta", "Bancos sin cuenta",
         "Crea la cuenta de " + ", ".join(d["banco"] for d in sin_cuenta[:3]) + "." if sin_cuenta else "",
         len(sin_cuenta), "/sincronizacion#cuentas"),
        ("movimientos_por_categorizar", "Movimientos por categorizar",
         "Dime la categoría y la recuerdo para la próxima.", n_categorizar, "/sincronizacion#categorizar"),
        ("movimientos_por_confirmar", "Movimientos por confirmar",
         "Llegaron solos: confirma que son tuyos.", n_confirmar, "/sincronizacion#confirmar"),
        ("correos_por_revisar", "Correos por revisar",
         "Aprueba o descarta lo que leí en tu correo.", n_correos, "/correos"),
    ]
    tareas = [
        {"id": i, "titulo": t, "detalle": d, "cantidad": int(n), "ruta": r}
        for i, t, d, n, r in candidatas if n > 0
    ]

    sync = db.query(SyncGmail).filter(SyncGmail.usuario_id == usuario.id).first()
    return {
        "meses": [{"clave": c, "etiqueta": f"{_NOMBRES_MES[m - 1]} {str(a)[2:]}"} for (a, m), c in zip(meses, claves)],
        "cuentas": filas_cuentas,
        "sin_cuenta": sin_cuenta,
        "tareas": tareas,
        "ultima_sync": sync.ultima_sync.isoformat() if sync and sync.ultima_sync else None,
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
    q = _cola_categorizar(db, ids_accesibles, ahora_co() - timedelta(days=DIAS_BANDEJA))
    total = q.count()
    filas = q.order_by(Movimiento.fecha.desc(), Movimiento.id).offset(offset).limit(limite).all()
    items = []
    for m in filas:
        o = MovimientoOut.model_validate(m).model_dump(mode="json")
        o["patron"] = patron_de_comercio(m.descripcion)
        items.append(o)
    return {"items": items, "total": total, "limite": limite, "offset": offset}
