"""
Patrimonio e inversiones: activos (CDT, fondos/ETF/acciones/cripto, inmuebles,
vehículos), pasivos (las deudas que ya existen), patrimonio neto, rentabilidad y
serie histórica mensual.

Decisiones clave:
- Todo se agrega en COP (moneda base) usando app.fx; cada activo conserva su
  moneda original y su rentabilidad se calcula en ella (el % no depende de la TRM).
- Las fórmulas viven en app/patrimonio_calc.py (puras y probadas).
- Las fotos mensuales (snapshots) se guardan de dos formas: de forma perezosa
  cuando el usuario abre la pantalla (GET /patrimonio) y por el endpoint de cron
  POST /patrimonio/cron/snapshot-mensual (ver docs en ese endpoint).
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import inversiones_calc as inv_calc
from app import patrimonio_calc as calc
from app import precios
from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.crons import Corrida
from app.database import get_db
from app.contabilidad import ConvertidorBase, moneda_base_de, tasas_manuales_de
from app.models import Cuenta, Deuda
from app.models_patrimonio import ActivoPatrimonio, FlujoActivo, SnapshotPatrimonio, ValorActivo
from app import models_inversiones  # noqa: F401  (registra las tablas de Inversiones en create_all)
from app.utiles import ahora_co

router = APIRouter(prefix="/patrimonio", tags=["patrimonio"])

MONEDAS = ("COP", "USD", "EUR")
# Mínimo de días entre el primer flujo y hoy para mostrar XIRR: anualizar un
# rendimiento de pocos días da cifras absurdas (2 % en una semana = 180 % E.A.).
MIN_DIAS_XIRR = 30


# ---------------------------------------------------------------- esquemas

class ActivoIn(BaseModel):
    clase: str
    nombre: str
    moneda: str = "COP"
    capital: Optional[float] = None
    tasa_ea: Optional[float] = None
    fecha_inicio: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None
    ticker: Optional[str] = None
    unidades: Optional[float] = None
    costo_promedio: Optional[float] = None
    precio_actual: Optional[float] = None
    precio_fecha: Optional[datetime] = None
    costo_adquisicion: Optional[float] = None
    fecha_adquisicion: Optional[datetime] = None
    notas: Optional[str] = ""
    arriendo_mensual: Optional[float] = None
    anio: Optional[float] = None
    depreciacion_pct: Optional[float] = None
    deuda_id: Optional[str] = None
    broker: Optional[str] = None

    @field_validator("clase")
    @classmethod
    def _clase(cls, v):
        v = v.strip().lower()
        if v not in calc.CLASES:
            raise ValueError(f"Clase inválida. Usa: {', '.join(calc.CLASES)}")
        return v

    @field_validator("moneda")
    @classmethod
    def _moneda(cls, v):
        v = v.strip().upper()
        if v not in MONEDAS:
            raise ValueError("Moneda no soportada (COP, USD o EUR)")
        return v

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Ponle un nombre al activo")
        return v


class ValorIn(BaseModel):
    valor: float
    fecha: Optional[datetime] = None


class FlujoIn(BaseModel):
    monto: float  # negativo = aporte, positivo = retiro/dividendo
    fecha: Optional[datetime] = None
    nota: Optional[str] = ""


def _validar_por_clase(d: ActivoIn):
    def exige(cond, msg):
        if not cond:
            raise HTTPException(status_code=422, detail=msg)

    if d.clase == "cdt":
        exige(d.capital and d.capital > 0, "El CDT necesita un capital mayor a 0")
        exige(d.tasa_ea is not None and d.tasa_ea >= 0, "El CDT necesita la tasa E.A.")
        exige(d.fecha_inicio and d.fecha_vencimiento, "El CDT necesita fecha de inicio y de vencimiento")
        exige(d.fecha_vencimiento > d.fecha_inicio, "El vencimiento debe ser posterior al inicio")
    elif d.clase in calc.CLASES_MERCADO:
        exige(d.unidades and d.unidades > 0, "Indica las unidades que tienes")
        exige(d.costo_promedio is not None and d.costo_promedio >= 0, "Indica el costo promedio por unidad")
        exige(d.precio_actual is None or d.precio_actual >= 0, "El precio no puede ser negativo")
    else:
        exige(d.precio_actual and d.precio_actual > 0, "Indica el valor estimado actual")
        exige(d.costo_adquisicion is None or d.costo_adquisicion >= 0, "El costo no puede ser negativo")


# ------------------------------------------------------------- evaluación

def evaluar_activo(a: ActivoPatrimonio, flujos: list, hoy: datetime) -> dict:
    """Valor, costo y rentabilidad de un activo, en SU moneda."""
    extra = {}
    xirr_flujos = None
    if a.clase == "cdt":
        valor = calc.valor_cdt(a.capital, a.tasa_ea, a.fecha_inicio, hoy, a.fecha_vencimiento)
        costo = a.capital
        extra["valor_vencimiento"] = calc.valor_cdt(
            a.capital, a.tasa_ea, a.fecha_inicio, a.fecha_vencimiento, a.fecha_vencimiento
        )
        extra["dias_al_vencimiento"] = max(0, (a.fecha_vencimiento - hoy).days)
        extra["vencido"] = hoy > a.fecha_vencimiento
        xirr_flujos = [(a.fecha_inicio, -a.capital), (min(hoy, a.fecha_vencimiento), valor)]
    elif a.clase in calc.CLASES_MERCADO:
        precio = a.precio_actual if a.precio_actual is not None else (a.costo_promedio or 0)
        valor = calc.valor_posicion(a.unidades or 0, precio)
        costo = (a.unidades or 0) * (a.costo_promedio or 0)
        if flujos:
            xirr_flujos = [(f.fecha, f.monto) for f in flujos] + [(hoy, valor)]
    else:
        valor = a.precio_actual or 0
        costo = a.costo_adquisicion or 0
        if costo and a.fecha_adquisicion:
            xirr_flujos = [(a.fecha_adquisicion, -costo), (hoy, valor)]

    rent = calc.rentabilidad(valor, costo)
    tir = None
    if xirr_flujos:
        primera = min(f for f, _ in xirr_flujos)
        if (hoy - primera).days >= MIN_DIAS_XIRR:
            t = calc.xirr(xirr_flujos)
            tir = t * 100 if t is not None else None
    return {"valor": valor, "costo": costo, **rent, "xirr_pct": tir, **extra}


def _serializar_activo(a: ActivoPatrimonio, flujos: list, hoy: datetime, conv=None) -> dict:
    conv = conv or ConvertidorBase("COP")  # `valor_cop` es el nombre histórico: lleva la moneda base
    ev = evaluar_activo(a, flujos, hoy)
    return {
        "id": a.id, "clase": a.clase, "nombre": a.nombre, "moneda": a.moneda,
        "capital": a.capital, "tasa_ea": a.tasa_ea,
        "fecha_inicio": a.fecha_inicio, "fecha_vencimiento": a.fecha_vencimiento,
        "ticker": a.ticker, "unidades": a.unidades, "costo_promedio": a.costo_promedio,
        "precio_actual": a.precio_actual, "precio_fecha": a.precio_fecha,
        "fuente_precio": a.fuente_precio,
        "costo_adquisicion": a.costo_adquisicion, "fecha_adquisicion": a.fecha_adquisicion,
        "notas": a.notas, "arriendo_mensual": a.arriendo_mensual, "anio": a.anio,
        "depreciacion_pct": a.depreciacion_pct, "deuda_id": a.deuda_id, "broker": a.broker,
        **ev,
        **(inv_calc.extras_bien(a.clase, ev["valor"], a.costo_adquisicion, a.precio_fecha,
                                a.arriendo_mensual, hoy) if a.clase in calc.CLASES_BIEN else
           {"actualizado_hace": inv_calc.hace_cuanto(a.precio_fecha, hoy)} if a.clase != "cdt" else {}),
        "valor_cop": conv(ev["valor"], a.moneda),
    }


def _flujos_por_activo(db: Session, uid: str) -> dict:
    por_activo: dict = {}
    for f in db.query(FlujoActivo).filter(FlujoActivo.usuario_id == uid).order_by(FlujoActivo.fecha).all():
        por_activo.setdefault(f.activo_id, []).append(f)
    return por_activo


def calcular_resumen(db: Session, uid: str, hoy: Optional[datetime] = None, base: Optional[str] = None) -> dict:
    """`base` fuerza la moneda de los totales (la renta/DIAN pide COP); por defecto, la del perfil."""
    hoy = hoy or ahora_co()
    flujos = _flujos_por_activo(db, uid)
    activos_db = (
        db.query(ActivoPatrimonio)
        .filter(ActivoPatrimonio.usuario_id == uid, ActivoPatrimonio.activo.is_(True))
        .order_by(ActivoPatrimonio.creado_en)
        .all()
    )
    if base:
        base = base.upper()
        conv = ConvertidorBase(base, tasas_manuales_de(db, uid, base))
    else:
        base = moneda_base_de(db, uid)
        conv = ConvertidorBase.de_usuario(db, uid)
    activos = [_serializar_activo(a, flujos.get(a.id, []), hoy, conv) for a in activos_db]

    por_clase: dict = {}
    for a in activos:
        por_clase[a["clase"]] = por_clase.get(a["clase"], 0) + a["valor_cop"]
    total_activos = sum(por_clase.values())

    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == uid).all()
    total_cuentas = sum(conv(c.saldo or 0, c.moneda or "COP") for c in cuentas)

    # La deuda de una tarjeta de crédito ya está restada dentro de `total_cuentas` (su saldo es
    # negativo). Si además se registró como Deuda de tipo 'tarjeta', se cuenta UNA sola vez:
    # esa Deuda queda fuera de los pasivos (y se avisa en `pasivos_duplicados`).
    tarjetas_con_deuda = [{"nombre": c.nombre} for c in cuentas if c.tipo == "credito" and (c.saldo or 0) < 0]
    deudas_db = db.query(Deuda).filter(Deuda.usuario_id == uid, Deuda.activa.is_(True)).all()
    duplicadas = set(calc.deudas_duplicadas_de_tarjetas(
        [{"id": d.id, "tipo": d.tipo, "nombre": d.nombre, "entidad": d.entidad} for d in deudas_db],
        tarjetas_con_deuda,
    ))
    pasivos = [{"id": d.id, "nombre": d.nombre, "entidad": d.entidad, "saldo": d.saldo_actual or 0}
               for d in deudas_db if d.id not in duplicadas]
    pasivos_duplicados = [{"id": d.id, "nombre": d.nombre} for d in deudas_db if d.id in duplicadas]
    total_deudas = sum(p["saldo"] for p in pasivos)
    deudas_tarjeta = sum(
        max(0.0, -conv(c.saldo or 0, c.moneda or "COP")) for c in cuentas if c.tipo == "credito"
    )

    # La dona incluye las cuentas como una "clase" más: es el efectivo/líquido.
    dist_valores = dict(por_clase)
    if total_cuentas > 0:
        dist_valores["cuentas"] = total_cuentas

    return {
        "moneda_base": base,
        "monedas_sin_tasa": sorted(conv.sin_tasa),
        "patrimonio_neto": calc.patrimonio_neto(total_activos, total_cuentas, total_deudas),
        "total_activos": total_activos,
        "total_cuentas": total_cuentas,
        "total_deudas": total_deudas,
        # Informativo: lo que debes en tarjetas ya viene restado dentro de total_cuentas.
        "deudas_tarjeta": deudas_tarjeta,
        "pasivos_duplicados": pasivos_duplicados,
        "distribucion": calc.distribucion(dist_valores),
        "activos": activos,
        "pasivos": pasivos,
    }


def guardar_snapshot(db: Session, uid: str, resumen: dict, hoy: Optional[datetime] = None) -> SnapshotPatrimonio:
    """Upsert de la foto del mes en curso (hora Colombia)."""
    hoy = hoy or ahora_co()
    mes = hoy.strftime("%Y-%m")
    valores = {f["clase"]: f["valor"] for f in resumen["distribucion"]}
    snap = db.query(SnapshotPatrimonio).filter(
        SnapshotPatrimonio.usuario_id == uid, SnapshotPatrimonio.mes == mes
    ).first()
    if not snap:
        snap = SnapshotPatrimonio(usuario_id=uid, mes=mes)
        db.add(snap)
    snap.fecha = hoy
    snap.total_activos = resumen["total_activos"]
    snap.total_cuentas = resumen["total_cuentas"]
    snap.total_deudas = resumen["total_deudas"]
    snap.patrimonio_neto = resumen["patrimonio_neto"]
    snap.distribucion = json.dumps(valores)
    db.commit()
    return snap


def _guardar_snapshot_seguro(db: Session, uid: str, resumen: dict):
    """Dos pestañas abiertas pueden chocar con el índice único (usuario, mes):
    se descarta el intento, la otra ya guardó la foto de este mes."""
    try:
        guardar_snapshot(db, uid, resumen)
    except IntegrityError:
        db.rollback()


def _snapshot_out(s: SnapshotPatrimonio) -> dict:
    return {
        "mes": s.mes, "fecha": s.fecha, "total_activos": s.total_activos,
        "total_cuentas": s.total_cuentas, "total_deudas": s.total_deudas,
        "patrimonio_neto": s.patrimonio_neto, "distribucion": json.loads(s.distribucion or "{}"),
    }


# --------------------------------------------------------------- endpoints

@router.get("")
def resumen(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Patrimonio neto + activos + pasivos + distribución + serie histórica.
    Efecto secundario deliberado: guarda/actualiza la foto del mes en curso, de modo
    que la serie se llena sola aunque el cron mensual no esté programado."""
    r = calcular_resumen(db, usuario.id)
    if r["activos"] or r["total_cuentas"] or r["pasivos"]:
        _guardar_snapshot_seguro(db, usuario.id, r)
    snaps = (db.query(SnapshotPatrimonio).filter(SnapshotPatrimonio.usuario_id == usuario.id)
             .order_by(SnapshotPatrimonio.mes).all())
    r["historial"] = [_snapshot_out(s) for s in snaps]
    previo = [s for s in snaps if s.mes < ahora_co().strftime("%Y-%m")]
    r["variacion_mes_anterior"] = (r["patrimonio_neto"] - previo[-1].patrimonio_neto) if previo else None
    return r


@router.get("/historial")
def historial(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    snaps = (db.query(SnapshotPatrimonio).filter(SnapshotPatrimonio.usuario_id == usuario.id)
             .order_by(SnapshotPatrimonio.mes).all())
    return [_snapshot_out(s) for s in snaps]


@router.post("/snapshot")
def tomar_snapshot(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Guarda ya la foto del mes en curso (sobrescribe la anterior del mismo mes)."""
    r = calcular_resumen(db, usuario.id)
    return _snapshot_out(guardar_snapshot(db, usuario.id, r))


@router.post("/cron/snapshot-mensual")
def cron_snapshot_mensual(x_cron_secret: str = Header(default=""), db: Session = Depends(get_db)):
    """Foto de TODOS los usuarios con cuentas o activos. Recomendado: programarlo en
    cron-job.org una vez al día (cierra con el valor del último día del mes porque
    cada pasada sobrescribe la foto del mes) con el header X-Cron-Secret. Este
    endpoint NO crea ni cambia ningún cron; programarlo es una decisión de Daniel."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    ids = {r[0] for r in db.query(Cuenta.usuario_id).distinct().all()}
    ids |= {r[0] for r in db.query(ActivoPatrimonio.usuario_id).distinct().all()}
    guardados = 0
    corrida = Corrida(db)
    for uid in ids:
        with corrida.aislar(uid):
            guardar_snapshot(db, uid, calcular_resumen(db, uid))
            guardados += 1
    return {"ok": True, "usuarios": len(ids), "guardados": guardados, **corrida.resumen()}


@router.post("/cron/actualizar-precios")
def cron_actualizar_precios(x_cron_secret: str = Header(default=""), db: Session = Depends(get_db)):
    """Gancho para precios automáticos (ver app/precios.py). Solo toca activos cuya
    `fuente_precio` no sea "manual" y tenga un proveedor registrado; hoy no hay ninguno."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    candidatos = db.query(ActivoPatrimonio).filter(
        ActivoPatrimonio.activo.is_(True), ActivoPatrimonio.fuente_precio != "manual",
        ActivoPatrimonio.fuente_precio.isnot(None),
    ).all()
    actualizados = 0
    corrida = Corrida(db)
    for a in candidatos:
        with corrida.aislar(a.usuario_id):
            res = precios.obtener_precio(a.fuente_precio, a.ticker, a.clase, a.moneda)
            if res:
                _registrar_valor(db, a, res[0], res[1], a.fuente_precio)
                db.commit()
                actualizados += 1
    return {"ok": True, "actualizados": actualizados, **corrida.resumen()}


def _registrar_valor(db: Session, a: ActivoPatrimonio, valor: float, fecha: datetime, fuente="manual"):
    a.precio_actual = valor
    a.precio_fecha = fecha
    db.add(ValorActivo(usuario_id=a.usuario_id, activo_id=a.id, fecha=fecha, valor=valor, fuente=fuente))


def _activo_de(db: Session, uid: str, activo_id: str) -> ActivoPatrimonio:
    a = db.query(ActivoPatrimonio).filter(
        ActivoPatrimonio.id == activo_id, ActivoPatrimonio.usuario_id == uid,
        ActivoPatrimonio.activo.is_(True),
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    return a


@router.get("/activos")
def listar_activos(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    return calcular_resumen(db, usuario.id)["activos"]


@router.post("/activos")
def crear_activo(data: ActivoIn, db: Session = Depends(get_db),
                 usuario: UsuarioActual = Depends(get_current_user)):
    _validar_por_clase(data)
    campos = data.model_dump()
    a = ActivoPatrimonio(usuario_id=usuario.id, **campos)
    db.add(a)
    db.flush()
    if a.precio_actual is not None and a.clase not in ("cdt",):
        _registrar_valor(db, a, a.precio_actual, a.precio_fecha or ahora_co())
    db.commit()
    db.refresh(a)
    return _serializar_activo(a, [], ahora_co())


@router.put("/activos/{activo_id}")
def editar_activo(activo_id: str, data: ActivoIn, db: Session = Depends(get_db),
                  usuario: UsuarioActual = Depends(get_current_user)):
    a = _activo_de(db, usuario.id, activo_id)
    _validar_por_clase(data)
    precio_anterior = a.precio_actual
    for k, v in data.model_dump().items():
        setattr(a, k, v)
    if a.clase != "cdt" and a.precio_actual is not None and a.precio_actual != precio_anterior:
        _registrar_valor(db, a, a.precio_actual, data.precio_fecha or ahora_co())
    db.commit()
    db.refresh(a)
    flujos = _flujos_por_activo(db, usuario.id).get(a.id, [])
    return _serializar_activo(a, flujos, ahora_co())


@router.delete("/activos/{activo_id}")
def eliminar_activo(activo_id: str, db: Session = Depends(get_db),
                    usuario: UsuarioActual = Depends(get_current_user)):
    a = _activo_de(db, usuario.id, activo_id)
    a.activo = False  # borrado lógico, igual que las deudas: conserva el histórico
    db.commit()
    return {"ok": True}


@router.post("/activos/{activo_id}/valor")
def registrar_valor(activo_id: str, data: ValorIn, db: Session = Depends(get_db),
                    usuario: UsuarioActual = Depends(get_current_user)):
    """Registra un precio por unidad (fondos/ETF/acciones/cripto) o una valoración
    total (inmueble/vehículo) con su fecha, y lo deja como valor actual."""
    a = _activo_de(db, usuario.id, activo_id)
    if a.clase == "cdt":
        raise HTTPException(status_code=422, detail="El valor de un CDT se calcula solo con su tasa")
    if data.valor < 0:
        raise HTTPException(status_code=422, detail="El valor no puede ser negativo")
    _registrar_valor(db, a, data.valor, data.fecha or ahora_co())
    db.commit()
    db.refresh(a)
    return _serializar_activo(a, _flujos_por_activo(db, usuario.id).get(a.id, []), ahora_co())


@router.get("/activos/{activo_id}/valores")
def historial_valores(activo_id: str, db: Session = Depends(get_db),
                      usuario: UsuarioActual = Depends(get_current_user)):
    _activo_de(db, usuario.id, activo_id)
    filas = (db.query(ValorActivo).filter(ValorActivo.activo_id == activo_id,
                                          ValorActivo.usuario_id == usuario.id)
             .order_by(ValorActivo.fecha).all())
    return [{"id": v.id, "fecha": v.fecha, "valor": v.valor, "fuente": v.fuente} for v in filas]


@router.post("/activos/{activo_id}/flujos")
def registrar_flujo(activo_id: str, data: FlujoIn, db: Session = Depends(get_db),
                    usuario: UsuarioActual = Depends(get_current_user)):
    """Aporte (monto negativo) o retiro/dividendo (positivo). Alimenta el XIRR."""
    a = _activo_de(db, usuario.id, activo_id)
    if a.clase == "cdt":
        raise HTTPException(status_code=422, detail="El CDT usa su capital y fechas; no necesita flujos")
    if data.monto == 0:
        raise HTTPException(status_code=422, detail="El monto no puede ser 0")
    db.add(FlujoActivo(usuario_id=usuario.id, activo_id=a.id, fecha=data.fecha or ahora_co(),
                       monto=data.monto, nota=data.nota or ""))
    db.commit()
    return {"ok": True}


@router.get("/activos/{activo_id}/flujos")
def listar_flujos(activo_id: str, db: Session = Depends(get_db),
                  usuario: UsuarioActual = Depends(get_current_user)):
    _activo_de(db, usuario.id, activo_id)
    filas = (db.query(FlujoActivo).filter(FlujoActivo.activo_id == activo_id,
                                          FlujoActivo.usuario_id == usuario.id)
             .order_by(FlujoActivo.fecha).all())
    return [{"id": f.id, "fecha": f.fecha, "monto": f.monto, "nota": f.nota} for f in filas]


@router.delete("/flujos/{flujo_id}")
def eliminar_flujo(flujo_id: str, db: Session = Depends(get_db),
                   usuario: UsuarioActual = Depends(get_current_user)):
    f = db.query(FlujoActivo).filter(FlujoActivo.id == flujo_id, FlujoActivo.usuario_id == usuario.id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Flujo no encontrado")
    db.delete(f)
    db.commit()
    return {"ok": True}
