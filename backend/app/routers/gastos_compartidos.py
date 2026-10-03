"""
Gastos compartidos tipo Splitwise: contactos libres, grupos simples (viaje, casa),
división del gasto, saldos netos por persona, simplificación de deudas y pagos.

Todo es privado del usuario: los contactos son solo nombre/teléfono y nunca se
cruzan con otros usuarios de CuadraMe. La matemática vive en app/division.py.
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuenta_accesible
from app.database import get_db
from app.division import YO, DivisionInvalida, calcular_saldos, dividir, saldos_con, simplificar_deudas
from app.models_gastos import (
    ContactoGasto,
    GastoCompartido,
    GrupoGasto,
    LiquidacionGasto,
    MiembroGrupoGasto,
    ParteGasto,
)
from app.routers.movimientos import crear_movimiento
from app.schemas import MovimientoCreate
from app.utiles import ahora_co

router = APIRouter(prefix="/gastos-compartidos", tags=["gastos-compartidos"])

MAX_PARTICIPANTES = 30
MAX_CONTACTOS = 300


def decimales_de(moneda: str) -> int:
    """COP no usa centavos; USD/EUR sí."""
    return 0 if (moneda or "COP").upper() == "COP" else 2


# ---------- Esquemas ----------

class ContactoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    telefono: str = Field(default="", max_length=30)


class GrupoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    miembros: list[str] = Field(default_factory=list, max_length=MAX_PARTICIPANTES)


class ParticipanteIn(BaseModel):
    id: str  # 'yo' o id de contacto
    valor: float = 0  # partes / % / monto según el modo


class DivisionIn(BaseModel):
    total: float = Field(gt=0)
    moneda: str = "COP"
    modo: Literal["iguales", "montos", "porcentajes", "partes"]
    participantes: list[ParticipanteIn] = Field(min_length=1, max_length=MAX_PARTICIPANTES)


class GastoIn(DivisionIn):
    descripcion: str = Field(min_length=1, max_length=120)
    pagador_id: str = YO
    grupo_id: Optional[str] = None
    fecha: Optional[datetime] = None
    # mi_parte: mi movimiento es solo lo que me toca; total: registro lo que pagué
    # y el resto queda como "me deben"; ninguno: solo anota la cuenta con amigos.
    registro: Literal["mi_parte", "total", "ninguno"] = "mi_parte"
    cuenta_id: Optional[str] = None
    categoria: Optional[str] = None


class LiquidacionIn(BaseModel):
    de_id: str
    a_id: str
    monto: float = Field(gt=0)
    moneda: str = "COP"
    grupo_id: Optional[str] = None
    nota: str = Field(default="", max_length=120)


# ---------- Utilidades ----------

def _contacto_o_404(db: Session, usuario_id: str, contacto_id: str) -> ContactoGasto:
    c = db.query(ContactoGasto).filter(ContactoGasto.id == contacto_id, ContactoGasto.usuario_id == usuario_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return c


def _validar_ids(db: Session, usuario_id: str, ids: list[str]) -> dict[str, ContactoGasto]:
    """Verifica que todos los ids (salvo 'yo') sean contactos del usuario."""
    reales = {i for i in ids if i != YO}
    if not reales:
        return {}
    encontrados = {
        c.id: c
        for c in db.query(ContactoGasto).filter(ContactoGasto.usuario_id == usuario_id, ContactoGasto.id.in_(reales)).all()
    }
    if len(encontrados) != len(reales):
        raise HTTPException(status_code=400, detail="Hay participantes que no son tus contactos")
    return encontrados


def _grupo_o_404(db: Session, usuario_id: str, grupo_id: str) -> GrupoGasto:
    g = db.query(GrupoGasto).filter(GrupoGasto.id == grupo_id, GrupoGasto.usuario_id == usuario_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    return g


def _calcular_o_400(d: DivisionIn) -> dict[str, float]:
    try:
        return dividir(
            d.total, d.modo, [{"id": p.id, "valor": p.valor} for p in d.participantes], decimales_de(d.moneda)
        )
    except DivisionInvalida as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- Contactos ----------

@router.get("/contactos")
def listar_contactos(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    filas = db.query(ContactoGasto).filter(ContactoGasto.usuario_id == usuario.id).order_by(ContactoGasto.nombre).all()
    return [{"id": c.id, "nombre": c.nombre, "telefono": c.telefono or ""} for c in filas]


@router.post("/contactos")
def crear_contacto(
    data: ContactoIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    if db.query(ContactoGasto).filter(ContactoGasto.usuario_id == usuario.id).count() >= MAX_CONTACTOS:
        raise HTTPException(status_code=400, detail="Llegaste al máximo de contactos")
    c = ContactoGasto(usuario_id=usuario.id, nombre=data.nombre.strip(), telefono=data.telefono.strip())
    db.add(c)
    db.commit()
    return {"id": c.id, "nombre": c.nombre, "telefono": c.telefono or ""}


@router.delete("/contactos/{contacto_id}")
def eliminar_contacto(
    contacto_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    c = _contacto_o_404(db, usuario.id, contacto_id)
    en_gastos = (
        db.query(ParteGasto).join(GastoCompartido, GastoCompartido.id == ParteGasto.gasto_id)
        .filter(GastoCompartido.usuario_id == usuario.id, ParteGasto.participante_id == c.id).count()
        + db.query(GastoCompartido).filter(GastoCompartido.usuario_id == usuario.id, GastoCompartido.pagador_id == c.id).count()
        + db.query(LiquidacionGasto).filter(
            LiquidacionGasto.usuario_id == usuario.id,
            (LiquidacionGasto.de_id == c.id) | (LiquidacionGasto.a_id == c.id),
        ).count()
    )
    if en_gastos:
        raise HTTPException(status_code=400, detail="Este contacto tiene gastos o pagos registrados; no se puede borrar")
    db.query(MiembroGrupoGasto).filter(MiembroGrupoGasto.contacto_id == c.id).delete()
    db.delete(c)
    db.commit()
    return {"ok": True}


# ---------- Grupos ----------

def _serializar_grupo(db: Session, g: GrupoGasto) -> dict:
    miembros = [m.contacto_id for m in db.query(MiembroGrupoGasto).filter(MiembroGrupoGasto.grupo_id == g.id).all()]
    return {"id": g.id, "nombre": g.nombre, "miembros": miembros}


@router.get("/grupos")
def listar_grupos(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    grupos = db.query(GrupoGasto).filter(GrupoGasto.usuario_id == usuario.id).order_by(GrupoGasto.creado_en).all()
    return [_serializar_grupo(db, g) for g in grupos]


@router.post("/grupos")
def crear_grupo(data: GrupoIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    _validar_ids(db, usuario.id, data.miembros)
    g = GrupoGasto(usuario_id=usuario.id, nombre=data.nombre.strip())
    db.add(g)
    db.flush()
    for cid in dict.fromkeys(m for m in data.miembros if m != YO):
        db.add(MiembroGrupoGasto(grupo_id=g.id, contacto_id=cid))
    db.commit()
    return _serializar_grupo(db, g)


@router.delete("/grupos/{grupo_id}")
def eliminar_grupo(grupo_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    g = _grupo_o_404(db, usuario.id, grupo_id)
    # Los gastos del grupo se conservan (sus saldos siguen contando), solo se desvinculan.
    db.query(GastoCompartido).filter(GastoCompartido.grupo_id == g.id).update({"grupo_id": None})
    db.query(LiquidacionGasto).filter(LiquidacionGasto.grupo_id == g.id).update({"grupo_id": None})
    db.query(MiembroGrupoGasto).filter(MiembroGrupoGasto.grupo_id == g.id).delete()
    db.delete(g)
    db.commit()
    return {"ok": True}


# ---------- Gastos ----------

@router.post("/calcular")
def calcular(data: DivisionIn, usuario: UsuarioActual = Depends(get_current_user)):
    """Vista previa: no guarda nada, solo devuelve cuánto le toca a cada quien."""
    return {"partes": _calcular_o_400(data)}


@router.post("")
def crear_gasto(
    data: GastoIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    ids = [p.id for p in data.participantes] + [data.pagador_id]
    _validar_ids(db, usuario.id, ids)
    if data.grupo_id:
        _grupo_o_404(db, usuario.id, data.grupo_id)

    moneda = (data.moneda or "COP").upper()
    cuenta = None
    if data.registro != "ninguno":
        if not data.cuenta_id:
            raise HTTPException(status_code=400, detail="Elige la cuenta con la que pagaste")
        cuenta = cuenta_accesible(db, usuario.id, data.cuenta_id)
        if not cuenta:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        moneda = (cuenta.moneda or "COP").upper()  # el gasto va en la moneda de la cuenta

    partes = _calcular_o_400(data.model_copy(update={"moneda": moneda}))
    fecha = data.fecha or ahora_co()

    gasto = GastoCompartido(
        usuario_id=usuario.id, grupo_id=data.grupo_id, descripcion=data.descripcion.strip(), total=data.total,
        moneda=moneda, pagador_id=data.pagador_id, modo=data.modo, fecha=fecha,
    )
    db.add(gasto)
    db.flush()
    for pid, monto in partes.items():
        db.add(ParteGasto(gasto_id=gasto.id, participante_id=pid, monto=monto))

    # Mi movimiento: si pagó otra persona solo cuenta mi parte, aunque pidan "total".
    monto_mov = 0.0
    if cuenta is not None:
        if data.registro == "total" and data.pagador_id == YO:
            monto_mov = data.total
        else:
            monto_mov = partes.get(YO, 0.0)
    if monto_mov > 0:
        mov = crear_movimiento(
            MovimientoCreate(
                cuenta_id=cuenta.id, descripcion=data.descripcion.strip(), monto=monto_mov, tipo="expense",
                categoria=data.categoria, fecha=fecha, notas="Gasto compartido",
            ),
            db=db, usuario=usuario,
        )
        gasto.movimiento_id = mov.id
    db.commit()
    return {"id": gasto.id, "partes": partes, "movimiento_id": gasto.movimiento_id}


def _serializar_gasto(g: GastoCompartido, partes: list[ParteGasto], nombres: dict[str, str]) -> dict:
    return {
        "id": g.id, "descripcion": g.descripcion, "total": g.total, "moneda": g.moneda, "modo": g.modo,
        "fecha": g.fecha, "grupo_id": g.grupo_id, "movimiento_id": g.movimiento_id,
        "pagador_id": g.pagador_id, "pagador": nombres.get(g.pagador_id, "?"),
        "partes": [
            {"id": p.participante_id, "nombre": nombres.get(p.participante_id, "?"), "monto": p.monto} for p in partes
        ],
    }


def _nombres(db: Session, usuario_id: str) -> dict[str, str]:
    nombres = {c.id: c.nombre for c in db.query(ContactoGasto).filter(ContactoGasto.usuario_id == usuario_id).all()}
    nombres[YO] = "Tú"
    return nombres


@router.get("")
def listar_gastos(
    grupo_id: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    q = db.query(GastoCompartido).filter(GastoCompartido.usuario_id == usuario.id)
    if grupo_id:
        q = q.filter(GastoCompartido.grupo_id == grupo_id)
    gastos = q.order_by(GastoCompartido.fecha.desc()).limit(200).all()
    partes = db.query(ParteGasto).filter(ParteGasto.gasto_id.in_([g.id for g in gastos])).all() if gastos else []
    por_gasto: dict[str, list[ParteGasto]] = {}
    for p in partes:
        por_gasto.setdefault(p.gasto_id, []).append(p)
    nombres = _nombres(db, usuario.id)
    return [_serializar_gasto(g, por_gasto.get(g.id, []), nombres) for g in gastos]


@router.delete("/{gasto_id}")
def eliminar_gasto(gasto_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Quita el gasto de la cuenta con amigos. El movimiento propio (si se creó) se
    conserva: se borra aparte desde Movimientos para no tocar saldos sin que lo veas."""
    g = db.query(GastoCompartido).filter(GastoCompartido.id == gasto_id, GastoCompartido.usuario_id == usuario.id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    db.query(ParteGasto).filter(ParteGasto.gasto_id == g.id).delete()
    db.delete(g)
    db.commit()
    return {"ok": True}


# ---------- Saldos y pagos ----------

@router.get("/saldos")
def saldos(
    grupo_id: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """
    Por moneda: `personas` = saldo directo de cada contacto contra mí (positivo: me debe);
    `simplificado` = pagos mínimos que dejan a todo el grupo en paz (incluye deudas
    entre terceros cuando alguien más pagó).
    """
    qg = db.query(GastoCompartido).filter(GastoCompartido.usuario_id == usuario.id)
    ql = db.query(LiquidacionGasto).filter(LiquidacionGasto.usuario_id == usuario.id)
    if grupo_id:
        _grupo_o_404(db, usuario.id, grupo_id)
        qg = qg.filter(GastoCompartido.grupo_id == grupo_id)
        ql = ql.filter(LiquidacionGasto.grupo_id == grupo_id)
    gastos = qg.all()
    liquidaciones = ql.all()
    partes = db.query(ParteGasto).filter(ParteGasto.gasto_id.in_([g.id for g in gastos])).all() if gastos else []
    por_gasto: dict[str, dict[str, float]] = {}
    for p in partes:
        por_gasto.setdefault(p.gasto_id, {})[p.participante_id] = p.monto

    contactos = {c.id: c for c in db.query(ContactoGasto).filter(ContactoGasto.usuario_id == usuario.id).all()}
    monedas = sorted({g.moneda or "COP" for g in gastos} | {l.moneda or "COP" for l in liquidaciones})
    resultado = []
    for moneda in monedas:
        dec = decimales_de(moneda)
        gs = [{"pagador": g.pagador_id, "partes": por_gasto.get(g.id, {})} for g in gastos if (g.moneda or "COP") == moneda]
        ls = [{"de": l.de_id, "a": l.a_id, "monto": l.monto} for l in liquidaciones if (l.moneda or "COP") == moneda]
        directo = saldos_con(YO, gs, ls, dec)
        personas = [
            {
                "contacto_id": cid, "nombre": contactos[cid].nombre if cid in contactos else "?",
                "telefono": contactos[cid].telefono if cid in contactos else "", "saldo": s,
            }
            for cid, s in directo.items()
        ]
        personas.sort(key=lambda p: -abs(p["saldo"]))
        simplificado = [
            {
                **pago,
                "de_nombre": "Tú" if pago["de"] == YO else contactos[pago["de"]].nombre if pago["de"] in contactos else "?",
                "a_nombre": "Tú" if pago["a"] == YO else contactos[pago["a"]].nombre if pago["a"] in contactos else "?",
            }
            for pago in simplificar_deudas(calcular_saldos(gs, ls, dec), dec)
        ]
        resultado.append({
            "moneda": moneda,
            "personas": personas,
            "simplificado": simplificado,
            "total_me_deben": sum(p["saldo"] for p in personas if p["saldo"] > 0),
            "total_debo": -sum(p["saldo"] for p in personas if p["saldo"] < 0),
        })
    return {"monedas": resultado}


@router.post("/liquidaciones")
def registrar_pago(
    data: LiquidacionIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Registra que alguien pagó a alguien (yo cobré, yo pagué, o un pago entre terceros)."""
    if data.de_id == data.a_id:
        raise HTTPException(status_code=400, detail="Quien paga y quien recibe deben ser distintos")
    _validar_ids(db, usuario.id, [data.de_id, data.a_id])
    if data.grupo_id:
        _grupo_o_404(db, usuario.id, data.grupo_id)
    liq = LiquidacionGasto(
        usuario_id=usuario.id, grupo_id=data.grupo_id, de_id=data.de_id, a_id=data.a_id,
        monto=data.monto, moneda=(data.moneda or "COP").upper(), nota=data.nota.strip(), fecha=ahora_co(),
    )
    db.add(liq)
    db.commit()
    return {"id": liq.id}


@router.get("/liquidaciones")
def listar_pagos(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    nombres = _nombres(db, usuario.id)
    filas = (
        db.query(LiquidacionGasto).filter(LiquidacionGasto.usuario_id == usuario.id)
        .order_by(LiquidacionGasto.fecha.desc()).limit(200).all()
    )
    return [
        {
            "id": l.id, "de_id": l.de_id, "de": nombres.get(l.de_id, "?"), "a_id": l.a_id, "a": nombres.get(l.a_id, "?"),
            "monto": l.monto, "moneda": l.moneda, "nota": l.nota, "fecha": l.fecha, "grupo_id": l.grupo_id,
        }
        for l in filas
    ]


@router.delete("/liquidaciones/{liquidacion_id}")
def deshacer_pago(
    liquidacion_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    l = db.query(LiquidacionGasto).filter(
        LiquidacionGasto.id == liquidacion_id, LiquidacionGasto.usuario_id == usuario.id
    ).first()
    if not l:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    db.delete(l)
    db.commit()
    return {"ok": True}
