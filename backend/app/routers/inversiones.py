"""
Inversiones (opcional): brokers/plataformas, posiciones, transacciones, precios por
ticker y rentabilidades. Se construye ENCIMA de Patrimonio: cada posición mantiene un
activo "espejo" en activos_patrimonio (fuente_precio="inversiones"), de modo que el
patrimonio ve el valor del portafolio sin doble conteo. Sin posiciones no aparece nada.

Aportes enlazados a una cuenta: se guardan como TRASLADO neutral (tipo transfer,
categoría Transferencia, fuente transferencia_interna): no cuentan como gasto. Los
dividendos/intereses entran como ingreso de la categoría «Rendimientos».
Información educativa, no es asesoría de inversión.
"""
import csv
import io
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app import inversiones_calc as ic
from app import patrimonio_calc as pc
from app import precios_ticker as pt
from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.crons import Corrida, reclamar_marca
from app.database import get_db
from app import fx as _fxmod
from app.contabilidad import moneda_base_de, tasas_manuales_de
from app.models import Cuenta, Movimiento
from app.models_inversiones import Broker, Posicion, PrefInversiones, TransaccionInversion
from app.models_patrimonio import ActivoPatrimonio, SnapshotPatrimonio, ValorActivo
from app.utiles import ahora_co

router = APIRouter(prefix="/inversiones", tags=["inversiones"])

MONEDAS = ("COP", "USD", "EUR", "MXN", "CLP", "BRL", "ARS", "PEN")
TIPOS_BROKER = ("acciones", "etf", "fondos", "cripto", "cdt", "fiducia")
FUENTE_TRANSFERENCIA = "transferencia_interna"
CAT_RENDIMIENTOS = "Rendimientos"


class _FXApp(ic.ProveedorFX):
    """Proveedor por defecto: la conversión que ya usa el resto de la app (app.fx), hacia la MONEDA BASE
    del perfil (fase 2; el nombre pesos_por_unidad es histórico). Primero la tasa manual de la persona.
    Intercambiable: las pruebas y un futuro proveedor de país lo reemplazan."""

    def __init__(self, base="COP", tasas_usuario=None):
        self.base = (base or "COP").upper()
        self.tasas_usuario = {k.upper(): v for k, v in (tasas_usuario or {}).items()}

    def pesos_por_unidad(self, moneda):
        m = (moneda or "").upper()
        if self.tasas_usuario.get(m):
            return self.tasas_usuario[m]
        return _fxmod.tasa(m, self.base)[0]


fx_proveedor: ic.ProveedorFX = _FXApp()


def _contexto_fx(db, uid):
    """(moneda base, proveedor de tasas) de ESTA persona. Si una prueba reemplazó fx_proveedor, se respeta."""
    base = moneda_base_de(db, uid)
    if type(fx_proveedor) is _FXApp:
        return base, _FXApp(base, tasas_manuales_de(db, uid, base))
    return base, fx_proveedor

# Catálogo corto para el autocompletado (sin red). Nemotécnicos de la BVC y más usados.
CATALOGO = [
    ("ECOPETROL", "Ecopetrol", "CL", "accion", "COP"), ("PFBCOLOM", "Bancolombia preferencial", "CL", "accion", "COP"),
    ("BCOLOMBIA", "Bancolombia ordinaria", "CL", "accion", "COP"), ("ISA", "ISA", "CL", "accion", "COP"),
    ("GRUPOSURA", "Grupo Sura", "CL", "accion", "COP"), ("PFGRUPSURA", "Grupo Sura preferencial", "CL", "accion", "COP"),
    ("GEB", "Grupo Energía Bogotá", "CL", "accion", "COP"), ("CELSIA", "Celsia", "CL", "accion", "COP"),
    ("NUTRESA", "Grupo Nutresa", "CL", "accion", "COP"), ("CEMARGOS", "Cementos Argos", "CL", "accion", "COP"),
    ("PFDAVVNDA", "Davivienda preferencial", "CL", "accion", "COP"), ("EXITO", "Grupo Éxito", "CL", "accion", "COP"),
    ("AAPL", "Apple", "US", "accion", "USD"), ("MSFT", "Microsoft", "US", "accion", "USD"),
    ("NVDA", "Nvidia", "US", "accion", "USD"), ("AMZN", "Amazon", "US", "accion", "USD"),
    ("TSLA", "Tesla", "US", "accion", "USD"), ("VOO", "Vanguard S&P 500 ETF", "US", "etf", "USD"),
    ("SPY", "SPDR S&P 500 ETF", "US", "etf", "USD"), ("QQQ", "Invesco QQQ", "US", "etf", "USD"),
    ("VTI", "Vanguard Total Market", "US", "etf", "USD"), ("BTC", "Bitcoin", "", "cripto", "USD"),
    ("ETH", "Ethereum", "", "cripto", "USD"), ("WALMEX", "Walmart de México", "MX", "accion", "MXN"),
    ("PETR4", "Petrobras", "SA", "accion", "BRL"), ("VALE3", "Vale", "SA", "accion", "BRL"),
]


# ---------------------------------------------------------------- esquemas

class BrokerIn(BaseModel):
    nombre: str
    pais: str = "CO"
    tipo: str = "acciones"
    moneda: str = "COP"
    cuenta_id: Optional[str] = None

    @field_validator("nombre")
    @classmethod
    def _n(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Ponle un nombre")
        return v

    @field_validator("tipo")
    @classmethod
    def _t(cls, v):
        v = v.strip().lower()
        if v not in TIPOS_BROKER:
            raise ValueError("Tipo inválido")
        return v

    @field_validator("moneda")
    @classmethod
    def _m(cls, v):
        v = v.strip().upper()
        if v not in MONEDAS:
            raise ValueError("Moneda no soportada")
        return v


class PosicionIn(BaseModel):
    nombre: str
    ticker: Optional[str] = None
    mercado: str = ""
    tipo: str = "accion"
    moneda: str = "COP"
    broker_id: Optional[str] = None
    activo_id: Optional[str] = None  # enlazar un activo que ya existe en Patrimonio
    cantidad: float = 0
    costo_promedio: float = 0
    fecha_compra: Optional[datetime] = None
    precio_manual: Optional[float] = None

    @field_validator("nombre")
    @classmethod
    def _n(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Ponle un nombre")
        return v

    @field_validator("tipo")
    @classmethod
    def _t(cls, v):
        v = v.strip().lower()
        if v not in ic.TIPOS_POSICION:
            raise ValueError("Tipo inválido")
        return v

    @field_validator("moneda")
    @classmethod
    def _m(cls, v):
        v = v.strip().upper()
        if v not in MONEDAS:
            raise ValueError("Moneda no soportada")
        return v


class TransaccionIn(BaseModel):
    tipo: str
    fecha: Optional[datetime] = None
    cantidad: float = 0
    precio: float = 0
    comision: float = 0
    monto: float = 0
    tipo_cambio: Optional[float] = None
    cuenta_id: Optional[str] = None  # si viene, se enlaza con un movimiento de esa cuenta
    monto_cuenta: Optional[float] = None
    nota: str = ""

    @field_validator("tipo")
    @classmethod
    def _t(cls, v):
        v = v.strip().lower()
        if v not in ic.TIPOS_TX:
            raise ValueError("Tipo inválido")
        return v


class PrecioIn(BaseModel):
    precio: float
    fecha: Optional[datetime] = None


# ---------------------------------------------------------------- utilidades

def _posicion(db, uid, pid) -> Posicion:
    p = db.query(Posicion).filter(Posicion.id == pid, Posicion.usuario_id == uid, Posicion.activo.is_(True)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Posición no encontrada")
    return p


def _broker(db, uid, bid) -> Broker:
    b = db.query(Broker).filter(Broker.id == bid, Broker.usuario_id == uid, Broker.activo.is_(True)).first()
    if not b:
        raise HTTPException(status_code=404, detail="Broker no encontrado")
    return b


def _txs(db, uid, pid=None) -> list:
    q = db.query(TransaccionInversion).filter(TransaccionInversion.usuario_id == uid)
    if pid:
        q = q.filter(TransaccionInversion.posicion_id == pid)
    return q.order_by(TransaccionInversion.fecha).all()


def precio_efectivo(db, p: Posicion, hoy: datetime) -> dict:
    """Precio a usar: el más reciente entre la cotización por ticker y el precio manual.
    Sin ninguno devuelve precio None (no se inventa): la UI pide un precio manual."""
    cot = pt.leer(db, p.ticker, p.mercado)
    cand = []
    if cot and cot.precio:
        cand.append((cot.fecha or datetime.min, cot.precio, cot.fuente or "proveedor", cot.precio_anterior, cot.moneda))
    if p.precio_manual:
        cand.append((p.precio_manual_fecha or datetime.min, p.precio_manual, "manual", None, p.moneda))
    if not cand:
        est = pt.estado_precio(None, "", hoy)
        if cot and cot.error:
            est["mensaje"] = "Sin datos para este ticker: ponle un precio manual"
        return {"precio": None, "fecha": None, "fuente": "", "anterior": None, **est}
    fecha, precio, fuente, anterior, moneda = max(cand, key=lambda c: c[0])
    est = pt.estado_precio(fecha, "manual" if fuente == "manual" else fuente, hoy)
    return {"precio": precio, "fecha": fecha, "fuente": fuente, "anterior": anterior, **est,
            "moneda_precio": moneda}


def _evaluar(db, p: Posicion, txs: list, hoy: datetime, ctx=None) -> dict:
    mbase, fx = ctx or _contexto_fx(db, p.usuario_id)
    res = ic.resumen_transacciones(txs) if txs else {
        "cantidad": p.cantidad or 0, "costo_total": (p.cantidad or 0) * (p.costo_promedio or 0),
        "costo_promedio": p.costo_promedio or 0, "realizada": 0, "dividendos": 0, "comisiones": 0,
        "aportado": (p.cantidad or 0) * (p.costo_promedio or 0), "retirado": 0}
    pr = precio_efectivo(db, p, hoy)
    vg = ic.valor_y_ganancia(res["cantidad"], pr["precio"], res["costo_total"])
    valor_cop = ic.convertir(vg["valor"], p.moneda, mbase, fx)
    costo_cop = ic.convertir(res["costo_total"], p.moneda, mbase, fx)
    hoy_cop = None
    if pr["precio"] is not None and pr.get("anterior"):
        hoy_cop = ic.convertir((pr["precio"] - pr["anterior"]) * res["cantidad"], p.moneda, mbase, fx)
    total = ic.rentabilidad_total(vg["valor"] or 0, res["costo_total"], res["realizada"], res["dividendos"],
                                  res["aportado"])
    tir_pct = ic.tir(ic.flujos_tir(txs), vg["valor"] or 0, hoy) if txs else None
    return {
        "id": p.id, "broker_id": p.broker_id, "activo_id": p.activo_id, "ticker": p.ticker, "mercado": p.mercado,
        "nombre": p.nombre, "tipo": p.tipo, "moneda": p.moneda,
        "cantidad": res["cantidad"], "costo_promedio": res["costo_promedio"], "costo_total": res["costo_total"],
        "precio": pr["precio"], "precio_fecha": pr["fecha"], "precio_fuente": pr["fuente"],
        "precio_estado": pr["estado"], "precio_mensaje": pr["mensaje"],
        "valor": vg["valor"], "valor_cop": valor_cop, "costo_cop": costo_cop,
        "no_realizada": vg["no_realizada"], "no_realizada_pct": vg["no_realizada_pct"],
        "realizada": res["realizada"], "dividendos": res["dividendos"], "comisiones": res["comisiones"],
        "aportado": res["aportado"], "retirado": res["retirado"],
        "rentabilidad_total": total["total"], "rentabilidad_total_pct": total["total_pct"],
        "tir_pct": tir_pct, "hoy_cop": hoy_cop,
        "sugerir_actualizar": pr["estado"] in ("manual", "sin_datos") and pt_necesita_manual(pr, hoy),
    }


def pt_necesita_manual(pr: dict, hoy: datetime) -> bool:
    return pr["fecha"] is None or (hoy - pr["fecha"]).days >= 30


def _sincronizar_activo(db, p: Posicion, ev: dict, hoy: datetime):
    """Mantiene el activo espejo en Patrimonio (sin duplicar: si la posición se enlazó a un
    activo existente, ese mismo activo se actualiza)."""
    a = db.query(ActivoPatrimonio).filter(ActivoPatrimonio.id == p.activo_id,
                                          ActivoPatrimonio.usuario_id == p.usuario_id).first() if p.activo_id else None
    if a is None:
        a = ActivoPatrimonio(usuario_id=p.usuario_id, clase=ic.CLASE_PATRIMONIO.get(p.tipo, "fondo"),
                             nombre=p.nombre, moneda=p.moneda)
        db.add(a)
        db.flush()
        p.activo_id = a.id
    a.activo = True
    a.nombre, a.ticker, a.moneda = p.nombre, p.ticker, p.moneda
    a.unidades, a.costo_promedio = ev["cantidad"], ev["costo_promedio"]
    a.fuente_precio = "inversiones"
    if p.broker_id:
        b = db.get(Broker, p.broker_id)
        a.broker = b.nombre if b else a.broker
    if ev["precio"] is not None and a.precio_actual != ev["precio"]:
        a.precio_actual, a.precio_fecha = ev["precio"], ev["precio_fecha"] or hoy
        db.add(ValorActivo(usuario_id=p.usuario_id, activo_id=a.id, fecha=a.precio_fecha,
                           valor=ev["precio"], fuente=ev["precio_fuente"] or "manual"))


def _recalcular(db, p: Posicion, hoy: datetime) -> dict:
    txs = [t for t in _txs(db, p.usuario_id, p.id)]
    if txs:
        r = ic.resumen_transacciones(txs)
        p.cantidad, p.costo_promedio = r["cantidad"], r["costo_promedio"]
    ev = _evaluar(db, p, txs, hoy)
    _sincronizar_activo(db, p, ev, hoy)
    return ev


def _serializar_broker(b: Broker) -> dict:
    return {"id": b.id, "nombre": b.nombre, "pais": b.pais, "tipo": b.tipo, "moneda": b.moneda,
            "cuenta_id": b.cuenta_id}


def _cuenta_propia(db, uid, cuenta_id) -> Cuenta:
    c = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == uid).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return c


# ---------------------------------------------------------------- resumen

def calcular_portafolio(db: Session, uid: str, hoy: Optional[datetime] = None) -> dict:
    hoy = hoy or ahora_co()
    pos = db.query(Posicion).filter(Posicion.usuario_id == uid, Posicion.activo.is_(True)) \
        .order_by(Posicion.creado_en).all()
    brokers = db.query(Broker).filter(Broker.usuario_id == uid, Broker.activo.is_(True)).all()
    txs_all = _txs(db, uid)
    por_pos: dict = {}
    for t in txs_all:
        por_pos.setdefault(t.posicion_id, []).append(t)
    mbase, fx = ctx = _contexto_fx(db, uid)
    filas = [_evaluar(db, p, por_pos.get(p.id, []), hoy, ctx) for p in pos]

    def suma(campo):
        return sum(f[campo] or 0 for f in filas)

    valor_total = suma("valor_cop")
    costo_total = suma("costo_cop")
    sin_precio = [f["nombre"] for f in filas if f["precio"] is None]

    # Flujos del portafolio en COP (para TIR y periodos).
    flujos = []
    for t in txs_all:
        p = next((x for x in pos if x.id == t.posicion_id), None)
        if not p:
            continue
        for f, m in ic.flujos_tir([t]):
            cop = ic.convertir(m, p.moneda, mbase, fx, t.tipo_cambio)
            if cop is None:
                continue
            flujos.append((f, cop))
    # Lo que ENTRA al portafolio = lo que salió de tu bolsillo (negativo en `flujos`) -> positivo;
    # ventas, retiros y dividendos recibidos son salidas (negativas) para el método Dietz.
    entradas = [(f, -m) for f, m in flujos if m != 0]
    dividendos_cop = sum((ic.convertir(f["dividendos"], f["moneda"], mbase, fx) or 0) for f in filas)
    realizada_cop = sum((ic.convertir(f["realizada"], f["moneda"], mbase, fx) or 0) for f in filas)
    aportado_cop = sum((ic.convertir(f["aportado"], f["moneda"], mbase, fx) or 0) for f in filas)
    no_real = valor_total - costo_total
    tot = ic.rentabilidad_total(valor_total, costo_total, realizada_cop, dividendos_cop, aportado_cop)
    tir_pct = ic.tir(flujos, valor_total, hoy)

    # Rentabilidad por periodo con las fotos mensuales de Patrimonio (clases de mercado).
    snaps = db.query(SnapshotPatrimonio).filter(SnapshotPatrimonio.usuario_id == uid) \
        .order_by(SnapshotPatrimonio.mes).all()
    serie = []
    for s in snaps:
        try:
            d = json.loads(s.distribucion or "{}")
        except ValueError:
            d = {}
        serie.append({"mes": s.mes, "fecha": s.fecha, "valor": sum(d.get(c, 0) for c in pc.CLASES_MERCADO)})

    def periodo(desde_mes: str):
        previos = [s for s in serie if s["mes"] <= desde_mes]
        if not previos or not valor_total:
            return None
        base = previos[-1]
        if not base["valor"]:
            return None
        return ic.periodo_dietz(base["valor"], valor_total, base["fecha"], hoy, entradas)

    hace12 = (hoy.replace(day=1) - timedelta(days=365)).strftime("%Y-%m")
    primera = min((f for f, _ in flujos), default=None)
    desde_inicio = ic.rentabilidad_periodo(0, valor_total, [(1.0, sum(m for _, m in entradas))]) if entradas else None
    periodos = {
        "ytd_pct": periodo(f"{hoy.year - 1}-12"),
        "doce_meses_pct": periodo(hace12),
        "desde_inicio_pct": desde_inicio,
        "primera_fecha": primera,
    }
    por_broker: dict = {}
    for f in filas:
        k = f["broker_id"] or "_sin"
        por_broker.setdefault(k, []).append(f)
    lista_brokers = []
    for b in brokers:
        fs = por_broker.pop(b.id, [])
        lista_brokers.append({**_serializar_broker(b), "posiciones": fs,
                              "valor_cop": sum(x["valor_cop"] or 0 for x in fs)})
    sueltas = por_broker.pop("_sin", [])
    if sueltas:
        lista_brokers.append({"id": None, "nombre": "Sin plataforma", "pais": "", "tipo": "", "moneda": mbase,
                              "cuenta_id": None, "posiciones": sueltas,
                              "valor_cop": sum(x["valor_cop"] or 0 for x in sueltas)})
    nombres_broker = {b.id: b.nombre for b in brokers}
    for f in filas:
        f["broker"] = nombres_broker.get(f["broker_id"], "Sin plataforma")
    return {
        "tiene": bool(pos or brokers),
        "moneda_base": mbase,
        # posiciones en monedas sin tasa: no entran en los totales (valor_cop = None)
        "monedas_sin_tasa": sorted({f["moneda"] for f in filas if f["valor_cop"] is None and f["moneda"] != mbase}),
        "valor_total": valor_total, "costo_total": costo_total, "aportado": aportado_cop,
        "no_realizada": no_real, "no_realizada_pct": (no_real / costo_total * 100) if costo_total else None,
        "realizada": realizada_cop, "dividendos": dividendos_cop,
        "rentabilidad_total": tot["total"], "rentabilidad_total_pct": tot["total_pct"],
        "tir_pct": tir_pct, "hoy_cop": suma("hoy_cop") if any(f["hoy_cop"] is not None for f in filas) else None,
        "periodos": periodos, "sin_precio": sin_precio,
        "brokers": lista_brokers, "posiciones": filas,
        "distribucion_broker": ic.agrupar(filas, "broker"),
        "distribucion_tipo": ic.agrupar(filas, "tipo"),
        "distribucion_moneda": ic.agrupar(filas, "moneda"),
        "concentracion": ic.mayor_concentracion(filas),
        "evolucion": [{"mes": s["mes"], "valor": s["valor"]} for s in serie if s["valor"]],
        "aviso": ic.AVISO,
    }


# --------------------------------------------------------------- endpoints

@router.get("")
def portafolio(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    return calcular_portafolio(db, usuario.id)


@router.get("/tickers")
def buscar_tickers(q: str = "", usuario: UsuarioActual = Depends(get_current_user)):
    """Autocompletado local (sin gastar peticiones). Si no está, igual se puede escribir
    cualquier ticker con su mercado."""
    t = q.strip().lower()
    if len(t) < 1:
        return []
    return [{"ticker": a, "nombre": n, "mercado": m, "tipo": ti, "moneda": mo}
            for a, n, m, ti, mo in CATALOGO if t in a.lower() or t in n.lower()][:8]


@router.get("/brokers")
def listar_brokers(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    bs = db.query(Broker).filter(Broker.usuario_id == usuario.id, Broker.activo.is_(True)).all()
    return [_serializar_broker(b) for b in bs]


@router.post("/brokers")
def crear_broker(data: BrokerIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    if data.cuenta_id:
        _cuenta_propia(db, usuario.id, data.cuenta_id)
    b = Broker(usuario_id=usuario.id, **data.model_dump())
    db.add(b)
    db.commit()
    return _serializar_broker(b)


@router.put("/brokers/{broker_id}")
def editar_broker(broker_id: str, data: BrokerIn, db: Session = Depends(get_db),
                  usuario: UsuarioActual = Depends(get_current_user)):
    b = _broker(db, usuario.id, broker_id)
    if data.cuenta_id:
        _cuenta_propia(db, usuario.id, data.cuenta_id)
    for k, v in data.model_dump().items():
        setattr(b, k, v)
    db.commit()
    return _serializar_broker(b)


@router.delete("/brokers/{broker_id}")
def eliminar_broker(broker_id: str, db: Session = Depends(get_db),
                    usuario: UsuarioActual = Depends(get_current_user)):
    b = _broker(db, usuario.id, broker_id)
    b.activo = False  # las posiciones quedan «sin plataforma»
    for p in db.query(Posicion).filter(Posicion.usuario_id == usuario.id, Posicion.broker_id == b.id).all():
        p.broker_id = None
    db.commit()
    return {"ok": True}


def _crear_posicion(db, uid, d: PosicionIn, hoy) -> Posicion:
    if d.broker_id:
        _broker(db, uid, d.broker_id)
    if d.activo_id:
        a = db.query(ActivoPatrimonio).filter(ActivoPatrimonio.id == d.activo_id,
                                              ActivoPatrimonio.usuario_id == uid,
                                              ActivoPatrimonio.activo.is_(True)).first()
        if not a or a.clase not in pc.CLASES_MERCADO:
            raise HTTPException(status_code=404, detail="Activo no encontrado")
        ya = db.query(Posicion).filter(Posicion.activo_id == a.id, Posicion.activo.is_(True)).first()
        if ya:
            raise HTTPException(status_code=409, detail="Ese activo ya está enlazado a una posición")
    if d.cantidad < 0 or d.costo_promedio < 0 or (d.precio_manual is not None and d.precio_manual < 0):
        raise HTTPException(status_code=422, detail="Los valores no pueden ser negativos")
    p = Posicion(usuario_id=uid, broker_id=d.broker_id, activo_id=d.activo_id,
                 ticker=(d.ticker or "").strip().upper() or None, mercado=(d.mercado or "").strip().upper(),
                 nombre=d.nombre, tipo=d.tipo, moneda=d.moneda)
    if d.precio_manual:
        p.precio_manual, p.precio_manual_fecha = d.precio_manual, hoy
    db.add(p)
    db.flush()
    if d.cantidad > 0:  # saldo inicial = una compra de apertura, así todo sale de transacciones
        db.add(TransaccionInversion(usuario_id=uid, posicion_id=p.id, tipo="compra",
                                    fecha=d.fecha_compra or hoy, cantidad=d.cantidad, precio=d.costo_promedio,
                                    moneda=d.moneda, nota="Saldo inicial"))
        db.flush()
    _recalcular(db, p, hoy)
    return p


@router.post("/posiciones")
def crear_posicion(data: PosicionIn, db: Session = Depends(get_db),
                   usuario: UsuarioActual = Depends(get_current_user)):
    hoy = ahora_co()
    p = _crear_posicion(db, usuario.id, data, hoy)
    db.commit()
    return _evaluar(db, p, _txs(db, usuario.id, p.id), hoy)


@router.get("/posiciones/{posicion_id}")
def detalle_posicion(posicion_id: str, db: Session = Depends(get_db),
                     usuario: UsuarioActual = Depends(get_current_user)):
    p = _posicion(db, usuario.id, posicion_id)
    hoy = ahora_co()
    txs = _txs(db, usuario.id, p.id)
    hist = []
    if p.activo_id:
        hist = [{"fecha": v.fecha, "valor": v.valor} for v in db.query(ValorActivo).filter(
            ValorActivo.activo_id == p.activo_id, ValorActivo.usuario_id == usuario.id)
            .order_by(ValorActivo.fecha).all()]
    return {**_evaluar(db, p, txs, hoy), "aviso": ic.AVISO, "historial_precio": hist,
            "transacciones": [{"id": t.id, "tipo": t.tipo, "fecha": t.fecha, "cantidad": t.cantidad,
                               "precio": t.precio, "comision": t.comision, "monto": t.monto, "moneda": t.moneda,
                               "movimiento_id": t.movimiento_id, "nota": t.nota} for t in reversed(txs)]}


@router.put("/posiciones/{posicion_id}")
def editar_posicion(posicion_id: str, data: PosicionIn, db: Session = Depends(get_db),
                    usuario: UsuarioActual = Depends(get_current_user)):
    p = _posicion(db, usuario.id, posicion_id)
    if data.broker_id:
        _broker(db, usuario.id, data.broker_id)
    p.nombre, p.tipo, p.moneda, p.broker_id = data.nombre, data.tipo, data.moneda, data.broker_id
    p.ticker, p.mercado = (data.ticker or "").strip().upper() or None, (data.mercado or "").strip().upper()
    hoy = ahora_co()
    ev = _recalcular(db, p, hoy)
    db.commit()
    return ev


@router.delete("/posiciones/{posicion_id}")
def eliminar_posicion(posicion_id: str, db: Session = Depends(get_db),
                      usuario: UsuarioActual = Depends(get_current_user)):
    p = _posicion(db, usuario.id, posicion_id)
    p.activo = False
    if p.activo_id:  # el espejo sale del patrimonio (borrado lógico, igual que Patrimonio)
        a = db.get(ActivoPatrimonio, p.activo_id)
        if a and a.usuario_id == usuario.id:
            a.activo = False
    db.commit()
    return {"ok": True}


@router.post("/posiciones/{posicion_id}/precio-manual")
def precio_manual(posicion_id: str, data: PrecioIn, db: Session = Depends(get_db),
                  usuario: UsuarioActual = Depends(get_current_user)):
    p = _posicion(db, usuario.id, posicion_id)
    if data.precio <= 0:
        raise HTTPException(status_code=422, detail="El precio debe ser mayor a 0")
    hoy = ahora_co()
    p.precio_manual, p.precio_manual_fecha = data.precio, data.fecha or hoy
    ev = _recalcular(db, p, hoy)
    db.commit()
    return ev


@router.post("/posiciones/{posicion_id}/transacciones")
def registrar_transaccion(posicion_id: str, data: TransaccionIn, db: Session = Depends(get_db),
                          usuario: UsuarioActual = Depends(get_current_user)):
    p = _posicion(db, usuario.id, posicion_id)
    hoy = ahora_co()
    fecha = data.fecha or hoy
    if min(data.cantidad, data.precio, data.comision, data.monto) < 0:
        raise HTTPException(status_code=422, detail="Los valores no pueden ser negativos")
    if data.tipo in ("compra", "venta") and (data.cantidad <= 0 or data.precio <= 0):
        raise HTTPException(status_code=422, detail="Indica cantidad y precio")
    if data.tipo in ("dividendo", "comision", "aporte", "retiro") and data.monto <= 0:
        raise HTTPException(status_code=422, detail="Indica el monto")
    if data.tipo == "venta":
        disponible = ic.resumen_transacciones([t for t in _txs(db, usuario.id, p.id) if t.fecha <= fecha])["cantidad"]
        if data.cantidad > disponible + 1e-9:
            raise HTTPException(status_code=422, detail="No puedes vender más de lo que tienes")
    t = TransaccionInversion(usuario_id=usuario.id, posicion_id=p.id, tipo=data.tipo, fecha=fecha,
                             cantidad=data.cantidad, precio=data.precio, comision=data.comision,
                             monto=data.monto, moneda=p.moneda, tipo_cambio=data.tipo_cambio, nota=data.nota or "")
    db.add(t)
    db.flush()
    if data.cuenta_id:
        _enlazar_movimiento(db, usuario.id, p, t, data, fecha)
    ev = _recalcular(db, p, hoy)
    db.commit()
    return ev


def _enlazar_movimiento(db, uid, p: Posicion, t: TransaccionInversion, data: TransaccionIn, fecha):
    """Regla única de contabilidad: aportes y compras son traslados NEUTRALES (no gasto);
    ventas y retiros, traslados que entran; dividendos/intereses, ingreso «Rendimientos»."""
    cuenta = _cuenta_propia(db, uid, data.cuenta_id)
    total = {"compra": data.cantidad * data.precio + data.comision,
             "venta": data.cantidad * data.precio - data.comision}.get(data.tipo, data.monto)
    monto = data.monto_cuenta
    if monto is None:
        if (cuenta.moneda or "COP") == p.moneda:
            monto = total
        else:
            monto = ic.convertir(total, p.moneda, cuenta.moneda or "COP", None, data.tipo_cambio)
            if monto is None:
                raise HTTPException(status_code=422, detail="Indica el monto en la moneda de la cuenta")
    if monto <= 0:
        raise HTTPException(status_code=422, detail="El monto del movimiento debe ser mayor a 0")
    etiqueta = p.ticker or p.nombre
    if data.tipo in ("compra", "aporte", "comision"):
        m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, fecha=fecha, tipo="transfer",
                       descripcion=f"Traslado a Inversiones: {etiqueta}", categoria="Transferencia",
                       monto=monto, fuente=FUENTE_TRANSFERENCIA, notas=f"TRF:inv-{t.id}:out")
        cuenta.saldo = (cuenta.saldo or 0) - monto
    elif data.tipo in ("venta", "retiro"):
        m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, fecha=fecha, tipo="transfer",
                       descripcion=f"Traslado desde Inversiones: {etiqueta}", categoria="Transferencia",
                       monto=monto, fuente=FUENTE_TRANSFERENCIA, notas=f"TRF:inv-{t.id}:in")
        cuenta.saldo = (cuenta.saldo or 0) + monto
    else:  # dividendo
        m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, fecha=fecha, tipo="income",
                       descripcion=f"Dividendo/intereses: {etiqueta}", categoria=CAT_RENDIMIENTOS,
                       monto=monto, fuente="inversiones", notas=f"INV:{t.id}")
        cuenta.saldo = (cuenta.saldo or 0) + monto
    db.add(m)
    db.flush()
    t.movimiento_id = m.id


@router.delete("/transacciones/{tx_id}")
def eliminar_transaccion(tx_id: str, db: Session = Depends(get_db),
                         usuario: UsuarioActual = Depends(get_current_user)):
    t = db.query(TransaccionInversion).filter(TransaccionInversion.id == tx_id,
                                              TransaccionInversion.usuario_id == usuario.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    p = db.get(Posicion, t.posicion_id)
    if t.movimiento_id:  # deshace el movimiento enlazado y su efecto en el saldo
        m = db.query(Movimiento).filter(Movimiento.id == t.movimiento_id, Movimiento.usuario_id == usuario.id).first()
        if m:
            from app.contabilidad import delta_saldo
            c = db.query(Cuenta).filter(Cuenta.id == m.cuenta_id, Cuenta.usuario_id == usuario.id).first()
            if c:
                c.saldo = (c.saldo or 0) - delta_saldo(m)
            db.delete(m)
    db.delete(t)
    db.flush()
    if p:
        _recalcular(db, p, ahora_co())
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- precios

def _tickers_de(db, uid=None) -> list:
    q = db.query(Posicion).filter(Posicion.activo.is_(True), Posicion.ticker.isnot(None))
    if uid:
        q = q.filter(Posicion.usuario_id == uid)
    return q.all()


@router.post("/precios/actualizar")
def actualizar_ahora(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """«Actualizar ahora»: respeta caché (15 min) y el tope diario por usuario y global."""
    hoy = ahora_co()
    pos = _tickers_de(db, usuario.id)
    vistos, resultados = set(), []
    for p in pos:
        k = (p.ticker, p.mercado)
        if k in vistos:
            continue
        vistos.add(k)
        r = pt.actualizar_ticker(db, p.ticker, p.mercado, p.tipo, hoy, usuario_id=usuario.id)
        resultados.append({"ticker": p.ticker, **r})
        if r["resultado"] in ("tope_usuario", "tope_global", "sin_proveedor"):
            break
    for p in pos:
        _recalcular(db, p, hoy)
    db.commit()
    cuenta = {}
    for r in resultados:
        cuenta[r["resultado"]] = cuenta.get(r["resultado"], 0) + 1
    mensajes = {
        "tope_usuario": "Llegaste al máximo de actualizaciones de hoy; los precios se refrescan solos más tarde.",
        "tope_global": "Hoy se agotaron las consultas de precios; verás el último precio conocido.",
        "sin_proveedor": "Las actualizaciones automáticas no están activas; puedes poner el precio a mano.",
    }
    aviso = next((mensajes[k] for k in mensajes if k in cuenta), "")
    return {"ok": True, "resultados": resultados, "resumen": cuenta, "mensaje": aviso}


@router.post("/cron/actualizar-precios")
def cron_actualizar_precios(x_cron_secret: str = Header(default=""), db: Session = Depends(get_db)):
    """Cron idempotente: un ticker distinto se consulta UNA vez para todos los usuarios y la
    caché (TTL) evita repetir la petición si el cron corre dos veces seguidas. Programarlo en
    cron-job.org es decisión de Daniel (cada 30 min en horario de mercado, por ejemplo)."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    hoy = ahora_co()
    pos = _tickers_de(db)
    por_ticker: dict = {}
    for p in pos:
        por_ticker.setdefault((p.ticker, p.mercado, p.tipo), []).append(p)
    corrida = Corrida(db)
    cuenta: dict = {}
    for (ticker, mercado, tipo), ps in por_ticker.items():
        with corrida.aislar(ticker):
            r = pt.actualizar_ticker(db, ticker, mercado, tipo, hoy)
            cuenta[r["resultado"]] = cuenta.get(r["resultado"], 0) + 1
            for p in ps:
                _recalcular(db, p, hoy)
            db.commit()
            if r["resultado"] in ("tope_global", "sin_proveedor"):
                break
    return {"ok": True, "tickers": len(por_ticker), "resultados": cuenta, **corrida.resumen()}


# ---------------------------------------------------------------- CSV

class ImportarIn(BaseModel):
    csv: str
    broker_id: Optional[str] = None
    moneda: str = "COP"
    aplicar: bool = False


def _num(txt) -> Optional[float]:
    t = str(txt or "").strip().replace("$", "").replace(" ", "")
    if not t:
        return None
    if "," in t and "." in t:  # 1.234,56 o 1,234.56: el último separador es el decimal
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


@router.post("/importar")
def importar_csv(data: ImportarIn, db: Session = Depends(get_db),
                 usuario: UsuarioActual = Depends(get_current_user)):
    """CSV genérico con columnas ticker,cantidad,costo (opcional: nombre,mercado,tipo,moneda).
    Con aplicar=false solo devuelve la vista previa."""
    if len(data.csv) > 200_000:
        raise HTTPException(status_code=413, detail="El archivo es muy grande")
    texto = data.csv.strip()
    if not texto:
        raise HTTPException(status_code=422, detail="El archivo está vacío")
    sep = ";" if texto.splitlines()[0].count(";") > texto.splitlines()[0].count(",") else ","
    lector = csv.DictReader(io.StringIO(texto), delimiter=sep)
    if lector.fieldnames is None:
        raise HTTPException(status_code=422, detail="No encontré encabezados")
    claves = {(c or "").strip().lower(): c for c in lector.fieldnames}
    for req in ("ticker", "cantidad", "costo"):
        if req not in claves:
            raise HTTPException(status_code=422, detail=f"Falta la columna «{req}»")
    existentes = {(p.ticker, p.mercado, p.broker_id) for p in
                  db.query(Posicion).filter(Posicion.usuario_id == usuario.id, Posicion.activo.is_(True)).all()}
    if data.broker_id:
        _broker(db, usuario.id, data.broker_id)
    hoy = ahora_co()
    filas, creadas = [], 0
    for i, r in enumerate(lector):
        if i >= 500:
            break
        g = lambda k: (r.get(claves.get(k, ""), "") or "").strip()  # noqa: E731
        ticker, q, c = g("ticker").upper(), _num(g("cantidad")), _num(g("costo"))
        mercado = g("mercado").upper()
        moneda = (g("moneda") or data.moneda).upper()
        tipo = (g("tipo") or "accion").lower()
        error = None
        if not ticker:
            error = "Falta el ticker"
        elif q is None or q <= 0:
            error = "Cantidad inválida"
        elif c is None or c < 0:
            error = "Costo inválido"
        elif moneda not in MONEDAS:
            error = "Moneda no soportada"
        elif tipo not in ic.TIPOS_POSICION:
            error = "Tipo inválido"
        elif (ticker, mercado, data.broker_id) in existentes:
            error = "Ya existe esta posición"
        fila = {"ticker": ticker, "cantidad": q, "costo": c, "nombre": g("nombre") or ticker, "mercado": mercado,
                "tipo": tipo, "moneda": moneda, "ok": error is None, "error": error}
        filas.append(fila)
        if data.aplicar and error is None:
            _crear_posicion(db, usuario.id, PosicionIn(
                nombre=fila["nombre"], ticker=ticker, mercado=mercado, tipo=tipo, moneda=moneda,
                broker_id=data.broker_id, cantidad=q, costo_promedio=c), hoy)
            existentes.add((ticker, mercado, data.broker_id))
            creadas += 1
    if data.aplicar:
        db.commit()
    return {"filas": filas, "validas": sum(1 for f in filas if f["ok"]), "creadas": creadas}


# ---------------------------------------------------------------- opciones

@router.get("/opciones")
def ver_opciones(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    pref = db.get(PrefInversiones, usuario.id)
    return {"resumen_semanal": bool(pref and pref.resumen_semanal)}


class OpcionesIn(BaseModel):
    resumen_semanal: bool


@router.put("/opciones")
def guardar_opciones(data: OpcionesIn, db: Session = Depends(get_db),
                     usuario: UsuarioActual = Depends(get_current_user)):
    pref = db.get(PrefInversiones, usuario.id)
    if not pref:
        pref = PrefInversiones(usuario_id=usuario.id)
        db.add(pref)
    pref.resumen_semanal = data.resumen_semanal
    db.commit()
    return {"resumen_semanal": pref.resumen_semanal}


@router.post("/cron/resumen-semanal")
def cron_resumen_semanal(x_cron_secret: str = Header(default=""), db: Session = Depends(get_db)):
    """Push semanal opcional (solo a quien lo activó). Idempotente por semana ISO."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    from app.push import enviar_push
    hoy = ahora_co()
    semana = hoy.strftime("%G-W%V")
    corrida = Corrida(db)
    enviados = 0
    for pref in db.query(PrefInversiones).filter(PrefInversiones.resumen_semanal.is_(True)).all():
        with corrida.aislar(pref.usuario_id):
            r = calcular_portafolio(db, pref.usuario_id, hoy)
            if not r["posiciones"] or not r["valor_total"]:
                continue
            if not reclamar_marca(db, pref.usuario_id, "inversiones_semanal", semana):
                continue
            pct = r["no_realizada_pct"]
            cuerpo = (f"Tu portafolio vale ${r['valor_total']:,.0f}".replace(",", ".")
                      + (f" ({pct:+.1f} % frente a lo que pagaste)." if pct is not None else ".")
                      + " Información educativa.")
            enviados += 1 if enviar_push(db, pref.usuario_id, "Tu semana en inversiones", cuerpo, "/inversiones") else 0
    return {"ok": True, "enviados": enviados, **corrida.resumen()}
