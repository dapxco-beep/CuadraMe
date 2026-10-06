"""Periodos de extracto que YA están conciliados.

Si el periodo de una cuenta ya se concilió (por Gmail o subiendo el archivo a
mano), ese extracto no se vuelve a buscar, no se muestra como pendiente y no
cuenta en las tareas. Todo se deduce de lo que ya existe (sin tablas nuevas):
  - extractos de Gmail ya procesados de la misma cuenta y mes,
  - historiales de conciliación terminados cuyo rango de fechas cae en ese mes,
  - movimientos de la cuenta en ese mes con `conciliado_en` (o importados por
    conciliación).
"""
import json
import re
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.conciliacion import parse_bank_date
from app.extractos_gmail import _sin_acentos
from app.models import ExtractoCorreo, HistorialExtracto, Movimiento

ESTADO_YA_CONCILIADO = "ya_conciliado"
FUENTES_CONCILIACION = ("conciliacion_extracto", "conciliacion_auto")

_MES_NUM = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_NOMBRE_MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]
_FECHA_DMY = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")
_FECHA_YMD = re.compile(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})")
_MES_ANIO = re.compile(r"\b(" + "|".join(_MES_NUM) + r")\s+(?:de\s+)?(20\d{2})\b")
_SOLO_MES = re.compile(r"\b(" + "|".join(_MES_NUM) + r")\b")


def _clave(anio: int, mes: int) -> str:
    return f"{anio:04d}-{mes:02d}"


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


def periodo_en_asunto(asunto: str, recibido_en: datetime | None) -> str:
    """Periodo que dice el asunto del correo, ANTES de descargar el PDF
    ('Tu extracto de septiembre' -> 'septiembre 2026'). El año, si falta, es el
    de la fecha del correo (o el anterior si el mes aún no había llegado).
    Cadena vacía si el asunto no lo dice."""
    texto = _sin_acentos(asunto or "")
    m = _MES_ANIO.search(texto)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    if _FECHA_DMY.search(texto) or _FECHA_YMD.search(texto):
        return asunto or ""
    m = _SOLO_MES.search(texto)
    if not m or not recibido_en:
        return ""
    mes = _MES_NUM[m.group(1)]
    anio = recibido_en.year if mes <= recibido_en.month else recibido_en.year - 1
    return f"{_NOMBRE_MES[mes - 1]} {anio}"


def _rango_mes(mes: str) -> tuple[datetime, datetime]:
    a, m = int(mes[:4]), int(mes[5:7])
    return datetime(a, m, 1), datetime(*_siguiente(a, m), 1)


def evidencia_conciliado(db: Session, usuario_id: str, cuenta_id: str | None, mes: str | None) -> dict | None:
    """None si ese mes de esa cuenta NO está conciliado. Si lo está:
    {"cruzados": n, "historial_id": id o None}."""
    if not cuenta_id or not mes:
        return None
    try:
        ini, fin = _rango_mes(mes)
    except ValueError:
        return None

    cruzados, historial_id, hay = 0, None, False

    # 1) Extractos de Gmail ya procesados (o marcados) de la misma cuenta y mes.
    por_historial = {
        e.historial_id: (e.periodo, e.recibido_en)
        for e in db.query(ExtractoCorreo).filter(
            ExtractoCorreo.usuario_id == usuario_id,
            ExtractoCorreo.estado.in_(("procesado", ESTADO_YA_CONCILIADO)),
            ExtractoCorreo.historial_id.isnot(None),
        )
    }
    if por_historial:
        for h in db.query(HistorialExtracto).filter(
            HistorialExtracto.usuario_id == usuario_id,
            HistorialExtracto.cuenta_id == cuenta_id,
            HistorialExtracto.id.in_(list(por_historial)),
        ):
            periodo, recibido = por_historial[h.id]
            if mes_del_extracto(periodo, recibido) == mes:
                hay, historial_id = True, h.id
                cruzados = max(cruzados, (h.exactos or 0) + (h.aproximados or 0))

    # 2) Historiales terminados (subida manual): el rango de fechas del extracto cae en el mes.
    for h in (
        db.query(HistorialExtracto)
        .filter(
            HistorialExtracto.usuario_id == usuario_id, HistorialExtracto.cuenta_id == cuenta_id,
            HistorialExtracto.estado == "conciliado",
        )
        .order_by(HistorialExtracto.creado_en.desc()).limit(24).all()
    ):
        try:
            review = json.loads(h.review_json or "[]")
        except ValueError:
            continue
        fechas = [d for d in (parse_bank_date(i.get("fecha")) for i in review if i.get("estado") != "sobrante") if d]
        if fechas and _clave(max(fechas).year, max(fechas).month) == mes:
            hay = True
            historial_id = historial_id or h.id
            cruzados = max(cruzados, (h.exactos or 0) + (h.aproximados or 0))

    # 3) Movimientos conciliados dentro del mes y la cuenta.
    n_mov = db.query(func.count(Movimiento.id)).filter(
        Movimiento.cuenta_id == cuenta_id, Movimiento.fecha >= ini, Movimiento.fecha < fin,
        or_(Movimiento.conciliado_en.isnot(None), Movimiento.fuente.in_(FUENTES_CONCILIACION)),
    ).scalar() or 0
    if n_mov:
        hay = True
        cruzados = max(cruzados, int(n_mov))

    return {"cruzados": cruzados, "historial_id": historial_id} if hay else None


def depurar_conciliados(db: Session, usuario_id: str) -> int:
    """Extractos de Gmail que seguían 'nuevo' pero cuyo periodo ya se concilió
    (p. ej. el usuario subió el archivo a mano después) pasan a 'ya_conciliado'.
    Idempotente. Hace commit solo si cambió algo."""
    filas = db.query(ExtractoCorreo).filter(
        ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.estado == "nuevo",
        ExtractoCorreo.cuenta_sugerida_id.isnot(None), ExtractoCorreo.periodo != "",
    ).all()
    n = 0
    for f in filas:
        ev = evidencia_conciliado(db, usuario_id, f.cuenta_sugerida_id, mes_del_extracto(f.periodo, None))
        if ev:
            f.estado = ESTADO_YA_CONCILIADO
            f.historial_id = f.historial_id or ev["historial_id"]
            n += 1
    if n:
        db.commit()
    return n
