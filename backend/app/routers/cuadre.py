"""Cuadre con el extracto: comparar el saldo que dice el banco con el de la cuenta, y ayudar a cerrar la diferencia.

Nada de aquí cambia datos salvo los POST de acción (ajuste, saldo inicial, deshacer, saldos a mano), y todos
exigen `confirmar: true`. Ver app/cuadre_extracto.py para las reglas.
"""
import json
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import cuadre_extracto as cx
from app import punto_partida
from app.auth import UsuarioActual, get_current_user
from app.compartidos import bloquear_cuenta, cuenta_accesible, puede_editar_cuenta
from app.database import get_db
from app.models import HistorialExtracto, Movimiento
from app.utiles import ahora_co

router = APIRouter(prefix="/conciliacion/cuadre", tags=["cuadre"])


class LineaPorImportar(BaseModel):
    fecha: str
    monto: float
    tipo: str


class EvaluarRequest(BaseModel):
    cuenta_id: str
    historial_id: str | None = None
    saldo_final: float | None = None
    saldo_inicial: float | None = None
    fecha_corte: str | None = None
    periodo_inicio: str | None = None
    moneda: str | None = None
    por_importar: list[LineaPorImportar] = Field(default_factory=list, max_length=5000)
    aviso_cuenta: str | None = Field(default=None, max_length=400)
    registrar: bool = False  # recordar en el historial si cuadra (solo después de traer los movimientos)


class SaldosManualesRequest(BaseModel):
    historial_id: str
    saldo_final: float
    fecha_corte: str
    saldo_inicial: float | None = None
    confirmar: bool = False


class AjusteRequest(BaseModel):
    cuenta_id: str
    historial_id: str | None = None
    saldo_final: float | None = None
    fecha_corte: str | None = None
    moneda: str | None = None
    confirmar: bool = False
    confirmar_reforzado: bool = False


class SaldoInicialRequest(BaseModel):
    cuenta_id: str
    modo: str  # extracto | sin_explicar
    historial_id: str | None = None
    saldo_inicial: float | None = None
    periodo_inicio: str | None = None
    confirmar: bool = False


class DeshacerRequest(BaseModel):
    movimiento_id: str
    confirmar: bool = False


def _cuenta(db: Session, usuario: UsuarioActual, cuenta_id: str, editar: bool = False):
    cuenta = cuenta_accesible(db, usuario.id, cuenta_id)
    if not cuenta or (editar and not puede_editar_cuenta(db, usuario.id, cuenta)):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return cuenta


def _historial(db: Session, usuario: UsuarioActual, historial_id: str | None, cuenta_id: str) -> HistorialExtracto | None:
    if not historial_id:
        return None
    h = db.query(HistorialExtracto).filter(HistorialExtracto.id == historial_id, HistorialExtracto.usuario_id == usuario.id,
                                           HistorialExtracto.cuenta_id == cuenta_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    return h


def _fecha(v: str | None, nombre: str):
    f = cx.a_fecha(v) if v else None
    if v and not f:
        raise HTTPException(status_code=400, detail=f"La fecha {nombre} no parece válida. Escríbela como día, mes y año.")
    if f and f > ahora_co().date() + timedelta(days=1):
        raise HTTPException(status_code=400, detail="La fecha de corte no puede ser futura.")
    return f


def _pendientes(h: HistorialExtracto | None, ya_seleccionadas: int = 0) -> int:
    """Líneas del extracto que siguen sin resolver (nuevas sin traer o dudosas)."""
    if not h:
        return 0
    try:
        review = json.loads(h.review_json or "[]")
    except ValueError:
        return 0
    return sum(1 for i in review if i.get("estado") in ("faltante", "dudoso")) - ya_seleccionadas


def _inicio_pp(db: Session, usuario: UsuarioActual):
    return punto_partida.fecha_inicio(db, usuario.id)


def _datos(h: HistorialExtracto | None, d: EvaluarRequest | AjusteRequest) -> dict:
    """Lo que manda la persona manda; si no manda nada, se usa lo guardado en el historial."""
    guardados = cx.saldos_de_historial(h) if h else None
    g = guardados or {}
    return {
        "saldo_final": d.saldo_final if d.saldo_final is not None else g.get("saldo_final"),
        "fecha_corte": cx.a_fecha(d.fecha_corte) or cx.a_fecha(g.get("fecha_corte")),
        "saldo_inicial": getattr(d, "saldo_inicial", None) if getattr(d, "saldo_inicial", None) is not None else g.get("saldo_inicial"),
        "periodo_inicio": cx.a_fecha(getattr(d, "periodo_inicio", None)) or cx.a_fecha(g.get("periodo_inicio")),
        "moneda": d.moneda or g.get("moneda"),
    }


@router.get("")
def cuadre_de_la_cuenta(
    cuenta_id: str = Query(...),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Histórico de cuadres de una cuenta por mes (cuadra / diferencia / sin extracto), el diagnóstico «saldo de la
    cuenta frente a la suma de sus movimientos» y las alertas de meses que dejaron de cuadrar. Solo lee."""
    cuenta = _cuenta(db, usuario, cuenta_id)
    return cx.cuadre_por_mes(db, cuenta, inicio_pp=_inicio_pp(db, usuario))


@router.post("/evaluar")
def evaluar(
    data: EvaluarRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Compara el saldo del extracto con tus movimientos (más lo que se va a traer). No cambia nada, salvo recordar
    en el historial que ese mes cuadró cuando `registrar` viene activo."""
    cuenta = _cuenta(db, usuario, data.cuenta_id)
    h = _historial(db, usuario, data.historial_id, cuenta.id)
    d = _datos(h, data)
    por_importar = [x.model_dump() for x in data.por_importar]
    pendientes = max(0, _pendientes(h, len(por_importar)))
    ev = cx.evaluar(
        db, cuenta, saldo_final=d["saldo_final"], fecha_corte=d["fecha_corte"], saldo_inicial=d["saldo_inicial"],
        periodo_inicio=d["periodo_inicio"], moneda=d["moneda"], por_importar=por_importar, pendientes=pendientes,
        aviso_cuenta=data.aviso_cuenta, inicio_pp=_inicio_pp(db, usuario),
    )
    ev["historial_id"] = h.id if h else None
    ev["saldos"] = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in d.items()}
    if data.registrar and h and not por_importar and not pendientes:
        cx.registrar_cuadre(db, cuenta, h)
        db.commit()
    return ev


@router.get("/que-falta")
def que_puede_faltar(
    cuenta_id: str = Query(...),
    historial_id: str | None = Query(None),
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Ver qué puede faltar»: líneas del extracto sin pareja en tus movimientos y movimientos del periodo que el
    extracto no respalda. Solo lee."""
    cuenta = _cuenta(db, usuario, cuenta_id)
    h = _historial(db, usuario, historial_id, cuenta.id)
    sin_pareja, sin_respaldo = [], []
    if h:
        try:
            review = json.loads(h.review_json or "[]")
        except ValueError:
            review = []
        sin_pareja = [{"fecha": i.get("fecha"), "descripcion": i.get("descripcion"), "monto": i.get("monto"), "tipo": i.get("tipo"),
                       "estado": i.get("estado")} for i in review if i.get("estado") in ("faltante", "dudoso", "anterior")]
        sin_respaldo = [{"fecha": i.get("fecha"), "descripcion": i.get("descripcion"), "monto": i.get("monto"), "tipo": i.get("tipo"),
                         "movimiento_id": i.get("match_id")} for i in review if i.get("estado") == "sobrante"]
    else:
        f1, f2 = _fecha(desde, "de inicio"), _fecha(hasta, "de corte")
        if f1 and f2:
            q = (db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta.id, Movimiento.fecha >= datetime.combine(f1, time.min),
                                             Movimiento.fecha <= datetime.combine(f2, time.max), Movimiento.conciliado_en.is_(None),
                                             Movimiento.fuente != "ajuste_saldo").order_by(Movimiento.fecha).limit(100))
            sin_respaldo = [{"fecha": m.fecha.isoformat(), "descripcion": m.descripcion, "monto": m.monto, "tipo": m.tipo,
                             "movimiento_id": m.id} for m in q]
    return {"cuenta_id": cuenta.id, "sin_pareja_en_tus_movimientos": sin_pareja[:100], "sin_respaldo_en_el_extracto": sin_respaldo[:100],
            "texto": ("Estas líneas del extracto no tienen pareja en tus movimientos, y estos movimientos tuyos no aparecen en el extracto. "
                      "Revisa si falta alguno o está repetido."), "orientacion": cx.ORIENTACION}


@router.post("/saldos")
def guardar_saldos_a_mano(
    data: SaldosManualesRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Escribe el saldo que dice tu extracto al [fecha]»: para extractos que no traen saldos legibles."""
    h = db.query(HistorialExtracto).filter(HistorialExtracto.id == data.historial_id, HistorialExtracto.usuario_id == usuario.id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    _cuenta(db, usuario, h.cuenta_id, editar=True)
    if not data.confirmar:
        raise HTTPException(status_code=400, detail="Confirma el saldo que escribiste para guardarlo.")
    if abs(data.saldo_final) > 1e12 or (data.saldo_inicial is not None and abs(data.saldo_inicial) > 1e12):
        raise HTTPException(status_code=400, detail="Ese saldo no parece válido.")
    corte = _fecha(data.fecha_corte, "de corte")
    if not corte:
        raise HTTPException(status_code=400, detail="Escribe la fecha de corte del extracto.")
    h.saldo_final_extracto, h.fecha_corte, h.saldos_origen = data.saldo_final, corte.isoformat(), "manual"
    if data.saldo_inicial is not None:
        h.saldo_inicial_extracto = data.saldo_inicial
    h.cuadre_estado = h.cuadre_diferencia = h.cuadre_en = None  # saldo nuevo: la medición anterior ya no vale
    db.commit()
    return {"ok": True, "historial_id": h.id, "saldos": cx.saldos_de_historial(h)}


@router.post("/ajuste")
def crear_ajuste(
    data: AjusteRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Crea el «Ajuste de saldo» al corte del extracto. Solo con confirmación explícita. Es un movimiento neutro (no es
    gasto ni ingreso) y se puede deshacer. Un ajuste grande pide confirmación reforzada; con líneas del extracto sin
    resolver no se crea (primero resolverlas)."""
    cuenta = _cuenta(db, usuario, data.cuenta_id, editar=True)
    if not data.confirmar:
        raise HTTPException(status_code=400, detail="Confirma que quieres crear el ajuste: no se crea sin tu permiso.")
    h = _historial(db, usuario, data.historial_id, cuenta.id)
    d = _datos(h, data)
    if d["saldo_final"] is None or d["fecha_corte"] is None:
        raise HTTPException(status_code=400, detail="Falta el saldo del extracto y su fecha de corte.")
    cuenta = bloquear_cuenta(db, cuenta.id)
    pendientes = max(0, _pendientes(h))
    ev = cx.evaluar(db, cuenta, saldo_final=d["saldo_final"], fecha_corte=d["fecha_corte"], moneda=d["moneda"],
                    pendientes=pendientes, inicio_pp=_inicio_pp(db, usuario))
    if ev["estado"] == "cuadra":
        return {"ok": True, "ajustado": False, "estado": "cuadra", "texto": ev["texto"]}
    if ev["estado"] != "diferencia":
        raise HTTPException(status_code=409, detail={"codigo": ev["estado"], "mensaje": ev["texto"]})
    if pendientes:
        raise HTTPException(status_code=409, detail={"codigo": "lineas_por_revisar", "mensaje": (
            f"Hay {pendientes} {'línea' if pendientes == 1 else 'líneas'} del extracto sin resolver. "
            "Primero tráelas o resuélvelas; así el ajuste no tapa un movimiento que falta.")})
    if ev["acciones"]["ajuste"]["grande"] and not data.confirmar_reforzado:
        raise HTTPException(status_code=409, detail={"codigo": "requiere_confirmacion_reforzada", "mensaje": (
            f"Es un ajuste grande ({cx.pesos(ev['diferencia'])}). Puede ocultar un movimiento que falta. "
            "Confirma de nuevo si estás seguro; podrás deshacerlo."), "diferencia": ev["diferencia"]})
    mov = cx.crear_ajuste(db, cuenta, usuario.id, d["fecha_corte"], ev["diferencia"])
    nuevo = cx.evaluar(db, cuenta, saldo_final=d["saldo_final"], fecha_corte=d["fecha_corte"], moneda=d["moneda"],
                       inicio_pp=_inicio_pp(db, usuario))
    if h:
        cx.registrar_cuadre(db, cuenta, h)
    db.commit()
    return {"ok": True, "ajustado": True, "movimiento_id": mov.id, "diferencia": ev["diferencia"], "estado": nuevo["estado"],
            "saldo_cuenta": cuenta.saldo, "texto": f"Listo: ajuste de {cx.pesos(ev['diferencia'])} creado al {cx.fecha_texto(d['fecha_corte'])}. No cuenta como gasto ni ingreso."}


@router.post("/saldo-inicial")
def crear_saldo_inicial(
    data: SaldoInicialRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Registra el saldo inicial como movimiento neutro. modo «extracto»: lo toma del extracto (solo si la cuenta no tiene
    movimientos anteriores a su primer día). modo «sin_explicar»: el saldo que la cuenta ya traía sin movimiento."""
    cuenta = _cuenta(db, usuario, data.cuenta_id, editar=True)
    if not data.confirmar:
        raise HTTPException(status_code=400, detail="Confirma que quieres registrar el saldo inicial.")
    if data.modo not in ("extracto", "sin_explicar"):
        raise HTTPException(status_code=400, detail="No entendí qué saldo inicial registrar.")
    h = _historial(db, usuario, data.historial_id, cuenta.id)
    cuenta = bloquear_cuenta(db, cuenta.id)
    series = cx._serie(db, cuenta.id)
    _, acumulado, filas = series
    if data.modo == "sin_explicar":
        monto = round((cuenta.saldo or 0.0) - (acumulado[-1] if acumulado else 0.0), 2)
        if abs(monto) < cx.TOLERANCIA:
            raise HTTPException(status_code=409, detail={"codigo": "nada_que_explicar", "mensaje": "El saldo de esta cuenta ya coincide con sus movimientos."})
        primera = next((f["fecha"] for f in filas if f["fecha"]), None)
        fecha = (primera or ahora_co()).date()
    else:
        g = (cx.saldos_de_historial(h) if h else None) or {}
        saldo_ini = data.saldo_inicial if data.saldo_inicial is not None else g.get("saldo_inicial")
        fecha = cx.a_fecha(data.periodo_inicio) or cx.a_fecha(g.get("periodo_inicio"))
        if saldo_ini is None or fecha is None:
            raise HTTPException(status_code=400, detail="Falta el saldo anterior del extracto y el primer día del periodo.")
        if abs(saldo_ini) > 1e12:
            raise HTTPException(status_code=400, detail="Ese saldo no parece válido.")
        if any(f["fecha"] is not None and f["fecha"] < datetime.combine(fecha, time.min) for f in filas):
            raise HTTPException(status_code=409, detail={"codigo": "ya_hay_historia", "mensaje": (
                "Esta cuenta ya tiene movimientos anteriores a ese extracto. El saldo inicial solo se toma del extracto más antiguo.")})
        monto = round(saldo_ini, 2)
        if abs(monto) < cx.TOLERANCIA:
            return {"ok": True, "creado": False, "texto": "El saldo inicial del extracto es cero: no hay nada que registrar."}
    antes = cuenta.saldo or 0.0
    mov = cx.crear_saldo_inicial(db, cuenta, usuario.id, data.modo, fecha, monto)
    if h:
        cx.registrar_cuadre(db, cuenta, h)
    db.commit()
    return {"ok": True, "creado": True, "movimiento_id": mov.id, "monto": monto, "saldo_antes": antes, "saldo_cuenta": cuenta.saldo,
            "texto": f"Listo: saldo inicial de {cx.pesos(monto)} al {cx.fecha_texto(fecha)}. No cuenta como gasto ni ingreso."}


@router.post("/deshacer")
def deshacer(
    data: DeshacerRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Deshace un ajuste o saldo inicial creado por el cuadre (y deja el saldo de la cuenta como estaba)."""
    mov = db.query(Movimiento).filter(Movimiento.id == data.movimiento_id).first()
    cuenta = cuenta_accesible(db, usuario.id, mov.cuenta_id) if mov else None
    if not mov or not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if not cx.es_de_cuadre(mov):
        raise HTTPException(status_code=400, detail="Solo se pueden deshacer los ajustes y saldos iniciales del cuadre.")
    if not data.confirmar:
        raise HTTPException(status_code=400, detail="Confirma que quieres deshacerlo.")
    cuenta = bloquear_cuenta(db, cuenta.id)
    cx.deshacer(db, cuenta, mov)
    db.commit()
    return {"ok": True, "saldo_cuenta": cuenta.saldo, "texto": "Listo: lo deshice. El saldo de tu cuenta quedó como antes."}
