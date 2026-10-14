"""Punto de partida: desde cuándo cuenta la historia financiera de la persona.

Dos modos (por usuario, editable luego en Perfil):
  - 'hoy' (recomendado): se parte del saldo actual de cada cuenta. Solo se registra lo
    que ocurre desde la fecha de inicio; correos y extractos anteriores se IGNORAN al
    traer movimientos (no aparecen en «Por revisar» ni se importan).
  - 'historico': se elige desde cuándo (3, 6, 12 meses o una fecha); la app pide los
    extractos de ese rango, muestra la cobertura por mes y cuenta, y al final compara el
    saldo reconstruido con el saldo actual declarado.

Reglas:
  - Mover la fecha hacia ATRÁS permite importar más (y reabre la lectura de Gmail).
  - Mover la fecha hacia ADELANTE oculta lo anterior de informes y consejos; NO borra nada.
  - Sin elección (modo NULL) todo funciona como siempre: ninguna función de aquí filtra.
"""
import json
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, not_, or_
from sqlalchemy.orm import Session

from app.contabilidad import delta_saldo
from app.extractos_conciliados import (
    _FECHA_DMY, _FECHA_YMD, _clave, _siguiente, evidencia_conciliado, mes_del_extracto,
)
from app.extractos_gmail import _sin_acentos
from app.models import Cuenta, ExtractoCorreo, Movimiento
from app.models_fiscal import AjusteUsuario
from app.utiles import ahora_co

MODOS = ("hoy", "historico")
NOTA_SALDO_INICIAL = "Saldo inicial (punto de partida)"  # ajuste que FIJA el saldo de partida: no cuenta al reconstruir
NOTA_AJUSTE = "Ajuste de punto de partida"  # ajuste posterior por una diferencia: sí cuenta
MAX_MESES_HISTORICO = 24
_NOMBRES_MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                "septiembre", "octubre", "noviembre", "diciembre"]


def _fila(db: Session, usuario_id: str) -> AjusteUsuario | None:
    return db.query(AjusteUsuario).filter(AjusteUsuario.usuario_id == usuario_id).first()


def _saldos_de(fila: AjusteUsuario | None) -> dict:
    try:
        datos = json.loads(fila.punto_partida_saldos) if fila and fila.punto_partida_saldos else {}
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}


def obtener(db: Session, usuario_id: str) -> dict:
    """{modo, fecha (date|None), saldos, definido}. Nunca falla: sin elección todo es None."""
    f = _fila(db, usuario_id)
    modo = f.punto_partida_modo if f and f.punto_partida_modo in MODOS else None
    return {
        "modo": modo,
        "fecha": f.punto_partida_fecha if f and modo else None,
        "saldos": _saldos_de(f) if modo else {},
        "definido": modo is not None,
    }


def fecha_inicio(db: Session, usuario_id: str) -> datetime | None:
    """Medianoche del primer día que cuenta, o None si la persona aún no eligió."""
    p = obtener(db, usuario_id)
    return datetime(p["fecha"].year, p["fecha"].month, p["fecha"].day) if p["fecha"] else None


def es_anterior(fecha: datetime | date | None, inicio: datetime | None) -> bool:
    """True si `fecha` es estrictamente anterior al inicio. Sin fecha o sin inicio: False."""
    if not fecha or not inicio:
        return False
    if not isinstance(fecha, datetime):
        fecha = datetime(fecha.year, fecha.month, fecha.day)
    return fecha < inicio


def extracto_es_anterior(periodo: str, recibido_en: datetime | None, inicio: datetime | None) -> bool:
    """Un extracto es anterior si TERMINA antes del inicio. Con fechas explícitas en el periodo
    vale la última; con solo mes, el mes completo debe quedar antes del mes de inicio."""
    if not inicio:
        return False
    texto = _sin_acentos(periodo or "")
    fin = None
    for m in _FECHA_DMY.finditer(texto):
        try:
            fin = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    if fin is None:
        for m in _FECHA_YMD.finditer(texto):
            try:
                fin = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
    if fin is not None:
        return fin < inicio
    mes = mes_del_extracto(periodo, recibido_en)
    return bool(mes) and mes < _clave(inicio.year, inicio.month)


def desde_para_sync(db: Session, usuario_id: str) -> tuple[datetime | None, str | None]:
    """(fecha de inicio, modo) para limitar de dónde lee la sincronización de Gmail."""
    p = obtener(db, usuario_id)
    return fecha_inicio(db, usuario_id), p["modo"]


def _a_numero(v):
    try:
        return None if v is None or v == "" else round(float(v), 2)
    except (TypeError, ValueError):
        return None


def guardar(db: Session, usuario_id: str, modo: str, fecha: date, saldos: dict | None = None) -> dict:
    """Guarda la elección (sin commit). Devuelve {"retrocedio": bool}: la fecha se movió hacia atrás
    (o es la primera elección), así que conviene que la próxima sincronización lea de nuevo."""
    anterior = obtener(db, usuario_id)
    f = _fila(db, usuario_id)
    if not f:
        f = AjusteUsuario(usuario_id=usuario_id)
        db.add(f)
    previos = anterior["saldos"] or {}
    nuevos = dict(previos)
    for cuenta_id, v in (saldos or {}).items():
        v = v or {}
        nuevos[cuenta_id] = {"inicial": _a_numero(v.get("inicial")), "actual": _a_numero(v.get("actual"))}
    f.punto_partida_modo = modo
    f.punto_partida_fecha = fecha
    f.punto_partida_saldos = json.dumps(nuevos) if nuevos else None
    f.punto_partida_en = datetime.utcnow()
    retrocedio = anterior["fecha"] is None or fecha < anterior["fecha"]
    if retrocedio:
        from app.models import SyncGmail

        s = db.query(SyncGmail).filter(SyncGmail.usuario_id == usuario_id).first()
        if s:
            s.ultima_sync = None  # la próxima corrida lee desde la nueva fecha
            s.en_curso = False
    return {"retrocedio": retrocedio}


def correo_desde_inicio(inicio: datetime):
    """Condición SQL: el correo cuenta desde el punto de partida. Vale la fecha del MOVIMIENTO si el
    correo la trae (UTC: el inicio es medianoche de Colombia, +5 h) y, si no, la de recepción."""
    from app.models import CorreoGasto

    con_fecha = CorreoGasto.fecha_movimiento.isnot(None)
    return or_(
        and_(con_fecha, CorreoGasto.fecha_movimiento >= inicio + timedelta(hours=5)),
        and_(not_(con_fecha), or_(CorreoGasto.recibido_en.is_(None), CorreoGasto.recibido_en >= inicio)),
    )


def contar_anteriores(db: Session, usuario_id: str, inicio: datetime | None) -> dict:
    """Cuántos correos y extractos de Gmail quedan fuera por ser anteriores al inicio."""
    if not inicio:
        return {"correos": 0, "extractos": 0}
    from app.models import CorreoGasto

    correos = (
        db.query(func.count(CorreoGasto.id))
        .filter(
            CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "pendiente", CorreoGasto.monto > 0,
            not_(correo_desde_inicio(inicio)),
        )
        .scalar() or 0
    )
    extractos = sum(
        1 for e in db.query(ExtractoCorreo).filter(
            ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.estado.in_(("nuevo", "falta_clave", "error")),
        )
        if extracto_es_anterior(e.periodo, e.recibido_en, inicio)
    )
    return {"correos": int(correos), "extractos": extractos}


def _meses_entre(inicio: datetime, hoy: datetime) -> list[str]:
    """Meses COMPLETOS desde el mes del inicio hasta el mes anterior al actual (máx. 24)."""
    a, m = inicio.year, inicio.month
    tope = _clave(hoy.year, hoy.month)
    out: list[str] = []
    while _clave(a, m) < tope and len(out) < MAX_MESES_HISTORICO:
        out.append(_clave(a, m))
        a, m = _siguiente(a, m)
    return out


def etiqueta_mes(clave: str) -> str:
    return f"{_NOMBRES_MES[int(clave[5:7]) - 1]} {clave[:4]}"


def cobertura(db: Session, usuario_id: str, hoy: datetime | None = None) -> dict:
    """Para el modo histórico: por cuenta, qué meses ya tienen su extracto conciliado, cuáles tienen
    uno por procesar y cuáles faltan. Las cuentas de efectivo no tienen extracto y no se piden."""
    hoy = hoy or ahora_co()
    inicio = fecha_inicio(db, usuario_id)
    if not inicio:
        return {"meses": [], "cuentas": []}
    meses = _meses_entre(inicio, hoy)
    cuentas = [c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all()
               if (c.tipo or "") != "efectivo"]
    pendientes: dict[tuple[str, str], int] = {}
    for e in db.query(ExtractoCorreo).filter(
        ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.estado.in_(("nuevo", "falta_clave")),
        ExtractoCorreo.cuenta_sugerida_id.isnot(None),
    ):
        mes = mes_del_extracto(e.periodo, e.recibido_en)
        if mes:
            pendientes[(e.cuenta_sugerida_id, mes)] = pendientes.get((e.cuenta_sugerida_id, mes), 0) + 1
    filas = []
    for c in cuentas:
        estados = {}
        for mes in meses:
            if evidencia_conciliado(db, usuario_id, c.id, mes):
                estados[mes] = "conciliado"
            elif pendientes.get((c.id, mes)):
                estados[mes] = "por_procesar"
            else:
                estados[mes] = "falta"
        faltan = [m for m in meses if estados[m] == "falta"]
        filas.append({
            "cuenta_id": c.id, "nombre": c.nombre, "icono": c.icono,
            "meses": [{"mes": m, "estado": estados[m]} for m in meses],
            "faltan": faltan, "faltan_texto": ", ".join(_NOMBRES_MES[int(m[5:7]) - 1] for m in faltan),
        })
    return {"meses": [{"mes": m, "etiqueta": etiqueta_mes(m)} for m in meses], "cuentas": filas}


def conciliacion(db: Session, usuario_id: str) -> list[dict]:
    """Saldo reconstruido (saldo inicial + movimientos desde la fecha de inicio) frente al saldo actual
    que la persona declaró (o, si no declaró, el que lleva la app). `coincide` con 1 peso de tolerancia."""
    inicio = fecha_inicio(db, usuario_id)
    if not inicio:
        return []
    saldos = obtener(db, usuario_id)["saldos"]
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all()
    movs: dict[str, float] = {}
    if cuentas:
        for m in db.query(Movimiento).filter(
            Movimiento.cuenta_id.in_([c.id for c in cuentas]), Movimiento.fecha >= inicio
        ):
            if (m.notas or "") == NOTA_SALDO_INICIAL:
                continue
            movs[m.cuenta_id] = movs.get(m.cuenta_id, 0.0) + delta_saldo(m)
    salida = []
    for c in cuentas:
        d = saldos.get(c.id) or {}
        inicial, declarado = _a_numero(d.get("inicial")), _a_numero(d.get("actual"))
        if inicial is None:
            salida.append({"cuenta_id": c.id, "nombre": c.nombre, "icono": c.icono, "saldo_inicial": None,
                           "saldo_actual_app": c.saldo, "saldo_declarado": declarado, "reconstruido": None,
                           "diferencia": None, "coincide": None})
            continue
        reconstruido = round(inicial + movs.get(c.id, 0.0), 2)
        objetivo = declarado if declarado is not None else (c.saldo or 0.0)
        diferencia = round(objetivo - reconstruido, 2)
        salida.append({
            "cuenta_id": c.id, "nombre": c.nombre, "icono": c.icono, "saldo_inicial": inicial,
            "saldo_actual_app": c.saldo, "saldo_declarado": declarado, "reconstruido": reconstruido,
            "diferencia": diferencia, "coincide": abs(diferencia) < 1.0,
        })
    return salida


def resumen(db: Session, usuario_id: str) -> dict:
    """Estado completo para la pantalla (una sola llamada)."""
    p = obtener(db, usuario_id)
    inicio = fecha_inicio(db, usuario_id)
    return {
        "definido": p["definido"],
        "modo": p["modo"],
        "fecha": p["fecha"].isoformat() if p["fecha"] else None,
        "saldos": p["saldos"],
        "anteriores": contar_anteriores(db, usuario_id, inicio),
    }


def sugerencia_fecha(meses: int, hoy: datetime | None = None) -> date:
    """Fecha de inicio para «los últimos N meses» (primer día de ese mes)."""
    hoy = hoy or ahora_co()
    a, m = hoy.year, hoy.month - meses
    while m <= 0:
        a, m = a - 1, m + 12
    return date(a, m, 1)


def hoy_co() -> date:
    return ahora_co().date()
