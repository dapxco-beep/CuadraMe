"""
Colectas (vacas): una meta con lo que debe poner cada persona, quién ya puso y quién falta.
La lleva el organizador (todo es privado de él); los participantes son sus contactos de gastos compartidos.
Opcional: cada pago se registra como ingreso en una de sus cuentas (con la regla de cuadre de siempre) y
se puede compartir un enlace de SOLO LECTURA con el estado (sin cuentas, montos ajenos ni movimientos).
"""
import secrets
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuenta_accesible
from app.database import get_db
from app.limites import ip_cliente, verificar_limite
from app.models_colectas import AporteColecta, Colecta, PagoColecta
from app.models_gastos import ContactoGasto
from app.routers.gastos_compartidos import decimales_de
from app.routers.movimientos import crear_movimiento, eliminar_movimiento
from app.schemas import MovimientoCreate
from app.utiles import ahora_co

router = APIRouter(prefix="/colectas", tags=["colectas"])

YO = "yo"
MAX_PARTICIPANTES = 60
MAX_COLECTAS = 100


# ---------- Esquemas ----------

class ColectaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str = Field(default="", max_length=300)
    modo: Literal["por_persona", "meta_total"] = "por_persona"
    valor: float = Field(gt=0)  # por persona, o la meta total según `modo`
    participantes: list[str] = Field(default_factory=list, max_length=MAX_PARTICIPANTES)  # ids de contacto
    incluirme: bool = False  # el organizador también pone
    moneda: str = Field(default="COP", max_length=3)
    fecha_limite: Optional[datetime] = None
    cuenta_id: Optional[str] = None  # donde se registran los pagos como ingreso


class ColectaPatch(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=80)
    descripcion: Optional[str] = Field(default=None, max_length=300)
    fecha_limite: Optional[datetime] = None
    estado: Optional[Literal["abierta", "cerrada"]] = None
    cuenta_id: Optional[str] = None


class ParticipanteIn(BaseModel):
    contacto_id: str
    debe: Optional[float] = Field(default=None, ge=0)  # por defecto, lo mismo que los demás


class PagoIn(BaseModel):
    monto: Optional[float] = Field(default=None, gt=0)  # por defecto, lo que le falta
    registrar_ingreso: bool = False
    cuenta_id: Optional[str] = None  # si no, la de la colecta


# ---------- Utilidades ----------

def _colecta_o_404(db: Session, usuario_id: str, colecta_id: str) -> Colecta:
    c = db.query(Colecta).filter(Colecta.id == colecta_id, Colecta.usuario_id == usuario_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Colecta no encontrada")
    return c


def _cuenta_o_400(db: Session, usuario_id: str, cuenta_id: str):
    cuenta = cuenta_accesible(db, usuario_id, cuenta_id)
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return cuenta


def _contactos_de(db: Session, usuario_id: str, ids: list[str]) -> dict[str, ContactoGasto]:
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


def _repartir(total: float, n: int, decimales: int) -> list[float]:
    """Reparte `total` entre n sin perder centavos: el sobrante va a los primeros."""
    paso = 10 ** decimales
    base = int(total * paso) // n
    resto = int(round(total * paso)) - base * n
    return [(base + (1 if i < resto else 0)) / paso for i in range(n)]


def _pagado_por_aporte(db: Session, aporte_ids: list[str]) -> dict[str, float]:
    if not aporte_ids:
        return {}
    suma: dict[str, float] = {}
    for p in db.query(PagoColecta).filter(PagoColecta.aporte_id.in_(aporte_ids)).all():
        suma[p.aporte_id] = suma.get(p.aporte_id, 0.0) + p.monto
    return suma


def _estado_aporte(debe: float, pagado: float) -> str:
    if debe > 0 and pagado >= debe - 1e-9:
        return "pagado"
    return "parcial" if pagado > 0 else "falta"


def _resumen(db: Session, c: Colecta) -> dict:
    aportes = db.query(AporteColecta).filter(AporteColecta.colecta_id == c.id).all()
    pagado = _pagado_por_aporte(db, [a.id for a in aportes])
    total_pagado = sum(pagado.values())
    meta = sum(a.debe for a in aportes)
    return {
        "id": c.id, "nombre": c.nombre, "descripcion": c.descripcion or "", "modo": c.modo, "moneda": c.moneda,
        "estado": c.estado, "fecha_limite": c.fecha_limite, "cuenta_id": c.cuenta_id,
        "meta": meta, "recogido": total_pagado, "falta": max(meta - total_pagado, 0.0),
        "personas": len(aportes),
        "pagaron": sum(1 for a in aportes if _estado_aporte(a.debe, pagado.get(a.id, 0.0)) == "pagado"),
        "compartida": bool(c.token_publico),
    }


# ---------- Enlace público (SIN sesión; va antes de /{colecta_id}) ----------

@router.get("/publico/{token}")
def ver_publica(token: str, request: Request, db: Session = Depends(get_db)):
    """Solo lectura: nombre, metas y quién pagó (nombre de pila). Nunca cuentas, movimientos ni montos ajenos."""
    verificar_limite(f"colecta-publica:{ip_cliente(request)}", 60, 600, "Demasiadas consultas. Intenta en {espera}.")
    c = db.query(Colecta).filter(Colecta.token_publico == token).first() if len(token) >= 20 else None
    if not c:
        raise HTTPException(status_code=404, detail="Esta colecta no existe o ya no se comparte")
    aportes = db.query(AporteColecta).filter(AporteColecta.colecta_id == c.id).all()
    pagado = _pagado_por_aporte(db, [a.id for a in aportes])
    nombres = {x.id: x.nombre for x in db.query(ContactoGasto).filter(ContactoGasto.usuario_id == c.usuario_id).all()}
    r = _resumen(db, c)
    return {
        "nombre": c.nombre, "descripcion": r["descripcion"], "moneda": c.moneda, "estado": c.estado,
        "fecha_limite": c.fecha_limite, "meta": r["meta"], "recogido": r["recogido"], "falta": r["falta"],
        "participantes": [
            {
                "nombre": ("Organizador" if a.participante_id == YO else (nombres.get(a.participante_id, "?").split(" ")[0])),
                "estado": _estado_aporte(a.debe, pagado.get(a.id, 0.0)),
            }
            for a in aportes
        ],
    }


# ---------- Colectas ----------

@router.get("")
def listar(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    cs = db.query(Colecta).filter(Colecta.usuario_id == usuario.id).order_by(Colecta.creado_en.desc()).limit(MAX_COLECTAS).all()
    return [_resumen(db, c) for c in cs]


@router.post("")
def crear(data: ColectaIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    if db.query(Colecta).filter(Colecta.usuario_id == usuario.id).count() >= MAX_COLECTAS:
        raise HTTPException(status_code=400, detail="Llegaste al máximo de colectas; cierra o borra alguna")
    ids = list(dict.fromkeys(data.participantes))  # sin repetidos, conserva el orden
    _contactos_de(db, usuario.id, ids)
    if data.incluirme:
        ids = [YO] + ids
    if not ids:
        raise HTTPException(status_code=400, detail="Elige al menos una persona")
    moneda = (data.moneda or "COP").upper()
    if data.cuenta_id:
        moneda = (_cuenta_o_400(db, usuario.id, data.cuenta_id).moneda or "COP").upper()
    dec = decimales_de(moneda)
    debes = [round(data.valor, dec)] * len(ids) if data.modo == "por_persona" else _repartir(data.valor, len(ids), dec)
    c = Colecta(
        usuario_id=usuario.id, nombre=data.nombre.strip(), descripcion=data.descripcion.strip(), modo=data.modo,
        meta_total=sum(debes), moneda=moneda, fecha_limite=data.fecha_limite, cuenta_id=data.cuenta_id,
    )
    db.add(c)
    db.flush()
    for pid, debe in zip(ids, debes):
        db.add(AporteColecta(colecta_id=c.id, usuario_id=usuario.id, participante_id=pid, debe=debe))
    db.commit()
    return {"id": c.id}


@router.get("/{colecta_id}")
def detalle(colecta_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    c = _colecta_o_404(db, usuario.id, colecta_id)
    aportes = db.query(AporteColecta).filter(AporteColecta.colecta_id == c.id).all()
    pagos = db.query(PagoColecta).filter(PagoColecta.aporte_id.in_([a.id for a in aportes])).order_by(PagoColecta.fecha.desc()).all() if aportes else []
    contactos = {x.id: x for x in db.query(ContactoGasto).filter(ContactoGasto.usuario_id == usuario.id).all()}
    pagado: dict[str, float] = {}
    por_aporte: dict[str, list[dict]] = {}
    for p in pagos:
        pagado[p.aporte_id] = pagado.get(p.aporte_id, 0.0) + p.monto
        por_aporte.setdefault(p.aporte_id, []).append(
            {"id": p.id, "monto": p.monto, "fecha": p.fecha, "registrado_en_cuenta": bool(p.movimiento_id)}
        )
    participantes = []
    for a in aportes:
        ct = contactos.get(a.participante_id)
        pg = pagado.get(a.id, 0.0)
        participantes.append({
            "aporte_id": a.id, "participante_id": a.participante_id,
            "nombre": "Tú" if a.participante_id == YO else (ct.nombre if ct else "?"),
            "telefono": ct.telefono if ct else "", "debe": a.debe, "pagado": pg, "falta": max(a.debe - pg, 0.0),
            "estado": _estado_aporte(a.debe, pg), "pagos": por_aporte.get(a.id, []),
        })
    participantes.sort(key=lambda p: ({"falta": 0, "parcial": 1, "pagado": 2}[p["estado"]], p["nombre"].lower()))
    return {**_resumen(db, c), "token_publico": c.token_publico, "participantes": participantes}


@router.patch("/{colecta_id}")
def editar(
    colecta_id: str, data: ColectaPatch, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    c = _colecta_o_404(db, usuario.id, colecta_id)
    cambios = data.model_dump(exclude_unset=True)
    if cambios.get("cuenta_id"):
        _cuenta_o_400(db, usuario.id, cambios["cuenta_id"])
    for campo, valor in cambios.items():
        setattr(c, campo, valor.strip() if isinstance(valor, str) and campo != "cuenta_id" else valor)
    db.commit()
    return {"ok": True}


@router.delete("/{colecta_id}")
def borrar(colecta_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Borra la colecta y sus pagos. Los ingresos ya registrados en tus cuentas NO se tocan."""
    c = _colecta_o_404(db, usuario.id, colecta_id)
    ids = [a.id for a in db.query(AporteColecta).filter(AporteColecta.colecta_id == c.id).all()]
    if ids:
        db.query(PagoColecta).filter(PagoColecta.aporte_id.in_(ids)).delete(synchronize_session=False)
    db.query(AporteColecta).filter(AporteColecta.colecta_id == c.id).delete(synchronize_session=False)
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/{colecta_id}/participantes")
def agregar_participante(
    colecta_id: str, data: ParticipanteIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    c = _colecta_o_404(db, usuario.id, colecta_id)
    _contactos_de(db, usuario.id, [data.contacto_id])
    existentes = db.query(AporteColecta).filter(AporteColecta.colecta_id == c.id).all()
    if any(a.participante_id == data.contacto_id for a in existentes):
        raise HTTPException(status_code=400, detail="Esa persona ya está en la colecta")
    if len(existentes) >= MAX_PARTICIPANTES:
        raise HTTPException(status_code=400, detail="Llegaste al máximo de participantes")
    debe = data.debe
    if debe is None:
        debe = existentes[0].debe if (c.modo == "por_persona" and existentes) else 0.0
    db.add(AporteColecta(colecta_id=c.id, usuario_id=usuario.id, participante_id=data.contacto_id, debe=debe))
    db.commit()
    return {"ok": True}


@router.delete("/{colecta_id}/participantes/{aporte_id}")
def quitar_participante(
    colecta_id: str, aporte_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    c = _colecta_o_404(db, usuario.id, colecta_id)
    a = db.query(AporteColecta).filter(AporteColecta.id == aporte_id, AporteColecta.colecta_id == c.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Participante no encontrado")
    if db.query(PagoColecta).filter(PagoColecta.aporte_id == a.id).count():
        raise HTTPException(status_code=400, detail="Ya tiene pagos: deshazlos primero")
    db.delete(a)
    db.commit()
    return {"ok": True}


# ---------- Pagos ----------

@router.post("/{colecta_id}/aportes/{aporte_id}/pagos")
def registrar_pago(
    colecta_id: str, aporte_id: str, data: PagoIn,
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user),
):
    c = _colecta_o_404(db, usuario.id, colecta_id)
    a = db.query(AporteColecta).filter(AporteColecta.id == aporte_id, AporteColecta.colecta_id == c.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Participante no encontrado")
    ya = _pagado_por_aporte(db, [a.id]).get(a.id, 0.0)
    monto = data.monto if data.monto is not None else round(a.debe - ya, decimales_de(c.moneda))
    if monto <= 0:
        raise HTTPException(status_code=400, detail="Esta persona ya pagó todo")

    movimiento_id = None
    cuenta_id = data.cuenta_id or c.cuenta_id
    if data.registrar_ingreso:
        if not cuenta_id:
            raise HTTPException(status_code=400, detail="Elige la cuenta donde entró la plata")
        cuenta = _cuenta_o_400(db, usuario.id, cuenta_id)
        if (cuenta.moneda or "COP").upper() != (c.moneda or "COP").upper():
            raise HTTPException(status_code=400, detail="La cuenta debe estar en la misma moneda de la colecta")
        nombre = "Tú" if a.participante_id == YO else (
            db.query(ContactoGasto.nombre).filter(ContactoGasto.id == a.participante_id).scalar() or "Participante"
        )
        mov = crear_movimiento(
            MovimientoCreate(
                cuenta_id=cuenta.id, descripcion=f"Colecta {c.nombre}: {nombre}", monto=monto, tipo="income",
                categoria="Ingresos", fecha=ahora_co(), notas="Colecta", confirmar_nuevo=True,
            ),
            db=db, usuario=usuario,
        )
        movimiento_id = mov.id
    pago = PagoColecta(aporte_id=a.id, usuario_id=usuario.id, monto=monto, fecha=ahora_co(), movimiento_id=movimiento_id)
    db.add(pago)
    db.commit()
    return {"id": pago.id, "movimiento_id": movimiento_id}


@router.delete("/{colecta_id}/pagos/{pago_id}")
def deshacer_pago(
    colecta_id: str, pago_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Deshace un pago; si había registrado un ingreso en una cuenta, lo retira también (saldo incluido)."""
    c = _colecta_o_404(db, usuario.id, colecta_id)
    ids = [a.id for a in db.query(AporteColecta).filter(AporteColecta.colecta_id == c.id).all()]
    p = db.query(PagoColecta).filter(PagoColecta.id == pago_id, PagoColecta.aporte_id.in_(ids or ["-"])).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if p.movimiento_id:
        try:
            eliminar_movimiento(p.movimiento_id, motivo="error", db=db, usuario=usuario)
        except HTTPException as e:
            if e.status_code != 404:  # si el movimiento ya no existe, igual se deshace el pago
                raise
    db.delete(p)
    db.commit()
    return {"ok": True}


# ---------- Compartir ----------

@router.post("/{colecta_id}/compartir")
def compartir(colecta_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    c = _colecta_o_404(db, usuario.id, colecta_id)
    if not c.token_publico:
        c.token_publico = secrets.token_urlsafe(24)
        db.commit()
    return {"token": c.token_publico}


@router.delete("/{colecta_id}/compartir")
def dejar_de_compartir(colecta_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    c = _colecta_o_404(db, usuario.id, colecta_id)
    c.token_publico = None
    db.commit()
    return {"ok": True}
