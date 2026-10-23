"""GUARDIA DE COHERENCIA: lo importado de un extracto debe tener respaldo en ese extracto. SOLO LECTURA.

Un mismo problema salió de seis formas en una cuenta real (ingresos falsos con su compra buena, pagos repetidos, parejas en
otra cuenta, compras emparejadas con otro comercio, residuos de fecha leídos como compra, líneas «completadas» sin pareja).
Cada una tenía su regla suelta (ingresos_sueltos.py). Esta guardia mira lo que QUEDA con una sola pregunta, por cuenta:

  · Del lado del movimiento: un movimiento importado de extracto cuya fecha cae en el periodo de un extracto leído COMPLETO
    (el más reciente de ese corte) debe tener una línea que lo respalde (mismo tipo, mismo valor ±$1, fecha cercana, 1:1).
  · Del lado de la línea: una línea «completada» o «aproximada» de ese extracto debe apuntar a un movimiento que exista, que
    sea de esta cuenta y (si nació de otro extracto) del mismo comercio.

Nunca escribe ni borra nada: devuelve hallazgos `{movimiento_id, motivo, texto, severidad}` para mostrarlos o actuar después.
`motivo` es un código estable (ver MOTIVOS); el texto va en español claro, sin jerga ni cifras de otras personas."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import cuadre_extracto as cx
from app.models import Cuenta, HistorialExtracto, Movimiento
from app.reasignar_extracto import FUENTES_IMPORTADAS

TOL = 1.0
VENTANA_FECHA = timedelta(days=4)  # el banco corre la fecha unos días entre compra y aplicación

# código estable -> severidad
MOTIVOS = {
    "sin_respaldo_en_extracto": "alta",
    "tipo_distinto_al_extracto": "alta",
    "repetido_frente_al_extracto": "alta",
    "pareja_inexistente": "media",
    "pareja_en_otra_cuenta": "media",
    "pareja_de_otro_comercio": "media",
}
ESTADOS_CON_PAREJA = ("completado", "aproximado")
TIPOS_DIRECCION = ("income", "expense")


def _review(h: HistorialExtracto) -> list[dict]:
    try:
        r = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return r if isinstance(r, list) else []


def _fecha_linea(i: dict) -> datetime | None:
    from app.conciliacion import parse_bank_date

    try:
        return parse_bank_date(i.get("fecha"))
    except Exception:  # noqa: BLE001 - una fecha rara no tumba la guardia
        return None


def _hallazgo(movimiento_id: str | None, motivo: str, texto: str, **extra) -> dict:
    return {"movimiento_id": movimiento_id, "motivo": motivo, "texto": texto, "severidad": MOTIVOS[motivo], **extra}


def _extractos_completos(db: Session, usuario_id: str, cuenta: Cuenta) -> list[tuple]:
    """(historial, inicio, fin_exclusivo, líneas) del extracto MÁS RECIENTE de cada corte, solo si se leyó completo."""
    from app import autoarreglo as aa  # import tardío: autoarreglo usa este módulo

    recientes: dict = {}
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario_id, HistorialExtracto.cuenta_id == cuenta.id).all():
        if h.estado == "error" or not h.fecha_corte:
            continue
        k = str(h.fecha_corte)[:10]
        if k not in recientes or (h.creado_en or datetime.min) > (recientes[k].creado_en or datetime.min):
            recientes[k] = h
    salida = []
    for h in recientes.values():
        ini, fin = cx.a_fecha(h.periodo_inicio), cx.a_fecha(h.fecha_corte)
        if ini is None or fin is None:
            continue
        review = _review(h)
        if not aa._verificada(h, cuenta, review):
            continue
        salida.append((h, datetime.combine(ini, datetime.min.time()), datetime.combine(fin, datetime.min.time()) + timedelta(days=1), review))
    return salida


def _respalda(i: dict, m: Movimiento, tipo: bool) -> bool:
    if i.get("tipo") not in TIPOS_DIRECCION or i.get("estado") == "sobrante":
        return False
    if tipo and i.get("tipo") != m.tipo:
        return False
    if abs(float(i.get("monto") or 0) - float(m.monto)) > TOL:
        return False
    f = _fecha_linea(i)
    return f is None or abs(f - m.fecha) <= VENTANA_FECHA + timedelta(days=1)


def _dia(d: datetime) -> str:
    return cx.fecha_texto(d.date())


def _del_movimiento(movs: list[Movimiento], completos: list[tuple]) -> list[dict]:
    out = []
    for h, ini, fin, review in completos:
        lineas = [i for i in review if i.get("tipo") in TIPOS_DIRECCION and i.get("estado") != "sobrante"]
        usadas: set[int] = set()
        propios = sorted((m for m in movs if ini <= m.fecha < fin), key=lambda m: m.fecha)
        pendientes = []
        for m in propios:  # primero la línea que ya apunta a este movimiento
            k = next((n for n, i in enumerate(lineas) if n not in usadas and m.id in (i.get("movimiento_id"), i.get("match_id")) and _respalda(i, m, True)), None)
            if k is None:
                pendientes.append(m)
            else:
                usadas.add(k)
        for m in pendientes:
            k = next((n for n, i in enumerate(lineas) if n not in usadas and _respalda(i, m, True)), None)
            if k is not None:
                usadas.add(k)
                continue
            donde = f"el extracto que cierra el {cx.fecha_texto(h.fecha_corte)}"
            cuando = f"del {_dia(m.fecha)}"
            if any(_respalda(i, m, False) for i in lineas):
                if any(i.get("tipo") == m.tipo and _respalda(i, m, True) for i in lineas):
                    out.append(_hallazgo(m.id, "repetido_frente_al_extracto",
                                         f"El movimiento {cuando} está repetido: {donde} trae solo uno igual.", historial_id=h.id))
                else:
                    sentido = "un gasto" if m.tipo == "income" else "un ingreso"
                    out.append(_hallazgo(m.id, "tipo_distinto_al_extracto",
                                         f"El movimiento {cuando} está como {'ingreso' if m.tipo == 'income' else 'gasto'}, "
                                         f"pero {donde} lo trae como {sentido}.", historial_id=h.id))
            else:
                out.append(_hallazgo(m.id, "sin_respaldo_en_extracto",
                                     f"El movimiento {cuando} no aparece en {donde}, que ya leí completo.", historial_id=h.id))
    return out


def _de_la_linea(db: Session, cuenta: Cuenta, completos: list[tuple]) -> list[dict]:
    from app.conciliacion import _comparten_comercio

    out = []
    for h, _ini, _fin, review in completos:
        for i in review:
            if i.get("estado") not in ESTADOS_CON_PAREJA:
                continue
            mid = i.get("movimiento_id") or i.get("match_id")
            if not mid:
                out.append(_hallazgo(None, "pareja_inexistente",
                                     "Una línea de tu extracto figura como registrada, pero no tiene ningún movimiento asociado.", historial_id=h.id))
                continue
            m = db.get(Movimiento, mid)
            if m is None:
                out.append(_hallazgo(mid, "pareja_inexistente",
                                     "Una línea de tu extracto figura como registrada, pero ese movimiento ya no existe.", historial_id=h.id))
            elif m.cuenta_id != cuenta.id:
                out.append(_hallazgo(mid, "pareja_en_otra_cuenta",
                                     "Una línea de tu extracto figura como registrada, pero su movimiento está en otra de tus cuentas.", historial_id=h.id))
            elif (i.get("estado") == "aproximado" and (m.extracto_id or m.fuente in FUENTES_IMPORTADAS) and m.extracto_id != h.id
                  and not _comparten_comercio(m.descripcion, i.get("descripcion"))):
                out.append(_hallazgo(mid, "pareja_de_otro_comercio",
                                     f"Una línea de tu extracto quedó emparejada con un movimiento del {_dia(m.fecha)} de otro comercio que tiene el mismo valor.",
                                     historial_id=h.id))
    return out


def revisar(db: Session, usuario_id: str, cuenta: Cuenta) -> list[dict]:
    """Hallazgos de coherencia de una cuenta. SOLO LECTURA (no escribe, no hace commit). Aislado por usuario."""
    if cuenta is None or cuenta.usuario_id != usuario_id:
        return []
    completos = _extractos_completos(db, usuario_id, cuenta)
    if not completos:
        return []
    movs = db.query(Movimiento).filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == cuenta.id,
                                       Movimiento.fuente.in_(FUENTES_IMPORTADAS), Movimiento.tipo.in_(TIPOS_DIRECCION)).all()
    return _del_movimiento(movs, completos) + _de_la_linea(db, cuenta, completos)


def revisar_usuario(db: Session, usuario_id: str) -> list[dict]:
    """Todas las cuentas con extractos, cada hallazgo con `cuenta_id` y `cuenta`. Una cuenta que falla no frena a las demás."""
    salida = []
    for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id, Cuenta.tipo.in_(("ahorro", "credito"))).order_by(Cuenta.nombre).all():
        try:
            for h in revisar(db, usuario_id, c):
                salida.append({**h, "cuenta_id": c.id, "cuenta": c.nombre})
        except Exception:  # noqa: BLE001
            continue
    return salida
