"""
Hogares: libro común de gastos entre personas con cuenta (pareja, familia, compañeros de casa).

Privacidad (lo más importante): TODA ruta pasa por `_miembro_o_404`. Quien no es miembro activo recibe 404 (no se
revela que el hogar existe). Un miembro ve solo el hogar: miembros (apodo), gastos, saldos y pagos; nunca cuentas,
movimientos ni categorías personales de otro. Ver models_hogares.py para el porqué de no usar `usuario_id` en el libro.
"""
import secrets
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuenta_accesible, cuentas_ids_accesibles
from app.database import get_db
from app.division import DivisionInvalida, calcular_saldos, dividir, simplificar_deudas
from app.limites import verificar_limite
from app.models import Cuenta, Movimiento
from app.models_hogares import GastoHogar, Hogar, InvitacionHogar, MiembroHogar, PagoHogar, ParteGastoHogar
from app.push import enviar_push
from app.routers.gastos_compartidos import decimales_de
from app.routers.movimientos import crear_movimiento
from app.schemas import MovimientoCreate
from app.utiles import ahora_co

router = APIRouter(prefix="/hogares", tags=["hogares"])

MAX_HOGARES = 20
MAX_MIEMBROS = 30
DIAS_INVITACION = 7


# ---------- Esquemas ----------

class HogarIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    moneda: str = Field(default="COP", max_length=3)
    apodo: Optional[str] = Field(default=None, max_length=40)


class HogarPatch(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)


class YoPatch(BaseModel):
    apodo: Optional[str] = Field(default=None, min_length=1, max_length=40)
    avisos: Optional[bool] = None


class RolPatch(BaseModel):
    rol: Literal["admin", "miembro"]


class InvitarIn(BaseModel):
    email: Optional[str] = Field(default=None, max_length=120)


class AceptarIn(BaseModel):
    apodo: Optional[str] = Field(default=None, min_length=1, max_length=40)


class ParticipanteIn(BaseModel):
    id: str  # miembros_hogar.id
    valor: float = 0


class GastoIn(BaseModel):
    descripcion: str = Field(min_length=1, max_length=120)
    total: float = Field(gt=0)
    modo: Literal["iguales", "montos", "porcentajes", "partes"] = "iguales"
    participantes: list[ParticipanteIn] = Field(min_length=1, max_length=MAX_MIEMBROS)
    pagador_id: Optional[str] = None  # por defecto, quien lo registra
    categoria: Optional[str] = Field(default=None, max_length=60)
    fecha: Optional[datetime] = None
    registrar_en_mi_cuenta: bool = False  # copia a una cuenta MÍA solo mi parte
    cuenta_id: Optional[str] = None
    # Compartir un gasto que YA tengo como movimiento: el total, la categoría y la fecha salen de él y no se crea otro.
    movimiento_id: Optional[str] = None


class PagoIn(BaseModel):
    de_id: str
    a_id: str
    monto: float = Field(gt=0)
    nota: str = Field(default="", max_length=120)


# ---------- Acceso (la única puerta) ----------

def _miembro_o_404(db: Session, usuario: UsuarioActual, hogar_id: str) -> tuple[Hogar, MiembroHogar]:
    fila = (
        db.query(Hogar, MiembroHogar)
        .join(MiembroHogar, MiembroHogar.hogar_id == Hogar.id)
        .filter(Hogar.id == hogar_id, MiembroHogar.usuario_id == usuario.id, MiembroHogar.activo.is_(True))
        .first()
    )
    if not fila:
        raise HTTPException(status_code=404, detail="Hogar no encontrado")
    return fila[0], fila[1]


def _admin_o_403(yo: MiembroHogar) -> None:
    if yo.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo quien administra el hogar puede hacer esto")


def _miembros(db: Session, hogar_id: str) -> list[MiembroHogar]:
    return db.query(MiembroHogar).filter(MiembroHogar.hogar_id == hogar_id).order_by(MiembroHogar.unido_en).all()


def _nombres(miembros: list[MiembroHogar]) -> dict[str, str]:
    return {m.id: m.apodo for m in miembros}  # quien borró su cuenta ya quedó como «Ex miembro»


def borrar_hogar(db: Session, hogar_id: str) -> None:
    """Borra el hogar y todo su libro (SQLite no aplica las cascadas, por eso a mano)."""
    gastos = [g.id for g in db.query(GastoHogar.id).filter(GastoHogar.hogar_id == hogar_id).all()]
    if gastos:
        db.query(ParteGastoHogar).filter(ParteGastoHogar.gasto_id.in_(gastos)).delete(synchronize_session=False)
    for modelo in (GastoHogar, PagoHogar, InvitacionHogar, MiembroHogar):
        db.query(modelo).filter(modelo.hogar_id == hogar_id).delete(synchronize_session=False)
    db.query(Hogar).filter(Hogar.id == hogar_id).delete(synchronize_session=False)


def _saldos(db: Session, h: Hogar, miembros: list[MiembroHogar]) -> dict:
    dec = decimales_de(h.moneda)
    gastos = db.query(GastoHogar).filter(GastoHogar.hogar_id == h.id).all()
    partes: dict[str, dict[str, float]] = {}
    if gastos:
        for p in db.query(ParteGastoHogar).filter(ParteGastoHogar.gasto_id.in_([g.id for g in gastos])).all():
            partes.setdefault(p.gasto_id, {})[p.miembro_id] = p.monto
    pagos = db.query(PagoHogar).filter(PagoHogar.hogar_id == h.id).all()
    neto = calcular_saldos(
        [{"pagador": g.pagador_id, "partes": partes.get(g.id, {})} for g in gastos],
        [{"de": p.de_id, "a": p.a_id, "monto": p.monto} for p in pagos],
        dec,
    )
    nombres = _nombres(miembros)
    simplificado = [
        {**p, "de_nombre": nombres.get(p["de"], "?"), "a_nombre": nombres.get(p["a"], "?")}
        for p in simplificar_deudas(neto, dec)
    ]
    return {"neto": neto, "simplificado": simplificado}


# ---------- Hogares ----------

@router.get("")
def listar(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    filas = (
        db.query(Hogar, MiembroHogar)
        .join(MiembroHogar, MiembroHogar.hogar_id == Hogar.id)
        .filter(MiembroHogar.usuario_id == usuario.id, MiembroHogar.activo.is_(True))
        .order_by(Hogar.creado_en.desc())
        .all()
    )
    salida = []
    for h, yo in filas:
        miembros = _miembros(db, h.id)
        s = _saldos(db, h, miembros)
        salida.append({
            "id": h.id, "nombre": h.nombre, "moneda": h.moneda, "rol": yo.rol, "mi_miembro_id": yo.id,
            "miembros": sum(1 for m in miembros if m.activo), "mi_saldo": s["neto"].get(yo.id, 0.0),
        })
    return salida


@router.post("")
def crear(data: HogarIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    ya = db.query(MiembroHogar).filter(MiembroHogar.usuario_id == usuario.id, MiembroHogar.activo.is_(True)).count()
    if ya >= MAX_HOGARES:
        raise HTTPException(status_code=400, detail="Llegaste al máximo de hogares")
    h = Hogar(nombre=data.nombre.strip(), moneda=(data.moneda or "COP").upper(), creado_por=usuario.id)
    db.add(h)
    db.flush()
    apodo = (data.apodo or usuario.nombre or "Yo").strip()[:40] or "Yo"
    db.add(MiembroHogar(hogar_id=h.id, usuario_id=usuario.id, apodo=apodo, rol="admin"))
    db.commit()
    return {"id": h.id}


# ---------- Invitaciones (antes de /{hogar_id}) ----------

@router.get("/invitaciones/mias")
def mis_invitaciones(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Invitaciones hechas a mi correo que siguen vigentes."""
    if not usuario.email:
        return []
    invs = (
        db.query(InvitacionHogar)
        .filter(InvitacionHogar.email == usuario.email.lower(), InvitacionHogar.estado == "pendiente",
                InvitacionHogar.vence_en > datetime.utcnow())
        .all()
    )
    salida = []
    for i in invs:
        h = db.query(Hogar).filter(Hogar.id == i.hogar_id).first()
        if h:
            salida.append({"token": i.token, "hogar": h.nombre, "vence_en": i.vence_en})
    return salida


@router.get("/de-movimiento/{movimiento_id}")
def parches_de_un_movimiento(movimiento_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """En qué parches ya compartí este movimiento mío (solo lo mío; si el movimiento no es mío, 404)."""
    _movimiento_mio_o_404(db, usuario, movimiento_id)
    filas = (
        db.query(ParteGastoHogar, GastoHogar, Hogar)
        .join(GastoHogar, GastoHogar.id == ParteGastoHogar.gasto_id)
        .join(Hogar, Hogar.id == GastoHogar.hogar_id)
        .join(MiembroHogar, MiembroHogar.id == ParteGastoHogar.miembro_id)
        .filter(ParteGastoHogar.movimiento_id == movimiento_id, MiembroHogar.usuario_id == usuario.id, MiembroHogar.activo.is_(True))
        .all()
    )
    return [{"hogar_id": h.id, "nombre": h.nombre, "gasto_id": g.id, "mi_parte": pt.monto} for pt, g, h in filas]


def _movimiento_mio_o_404(db: Session, usuario: UsuarioActual, movimiento_id: str) -> Movimiento:
    mov = (
        db.query(Movimiento)
        .filter(Movimiento.id == movimiento_id, Movimiento.cuenta_id.in_(cuentas_ids_accesibles(db, usuario.id)))
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return mov


def _invitacion_vigente(db: Session, usuario: UsuarioActual, token: str) -> InvitacionHogar:
    verificar_limite(f"hogar-token:{usuario.id}", 30, 3600, "Demasiados intentos. Intenta de nuevo en {espera}.")
    inv = db.query(InvitacionHogar).filter(InvitacionHogar.token == token).first() if len(token) >= 20 else None
    if (
        not inv or inv.estado != "pendiente" or inv.vence_en <= datetime.utcnow()
        or (inv.email and inv.email != (usuario.email or "").lower())
    ):
        raise HTTPException(status_code=404, detail="Esta invitación no existe, ya se usó o venció")
    return inv


@router.get("/invitaciones/{token}")
def ver_invitacion(token: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    inv = _invitacion_vigente(db, usuario, token)
    h = db.query(Hogar).filter(Hogar.id == inv.hogar_id).first()
    return {"hogar": h.nombre, "moneda": h.moneda, "vence_en": inv.vence_en}


@router.post("/invitaciones/{token}/aceptar")
def aceptar(
    token: str, data: AceptarIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    inv = _invitacion_vigente(db, usuario, token)
    h = db.query(Hogar).filter(Hogar.id == inv.hogar_id).first()
    miembros = _miembros(db, h.id)
    if sum(1 for m in miembros if m.activo) >= MAX_MIEMBROS:
        raise HTTPException(status_code=400, detail="El hogar llegó al máximo de miembros")
    apodo = (data.apodo or usuario.nombre or "Miembro").strip()[:40] or "Miembro"
    previo = next((m for m in miembros if m.usuario_id == usuario.id), None)
    if previo:
        previo.activo, previo.apodo = True, apodo  # volvió: conserva su historial
    else:
        db.add(MiembroHogar(hogar_id=h.id, usuario_id=usuario.id, apodo=apodo, rol="miembro"))
    inv.estado = "aceptada"  # un solo uso
    db.commit()
    return {"id": h.id}


# ---------- Detalle ----------

@router.get("/{hogar_id}")
def detalle(hogar_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    miembros = _miembros(db, h.id)
    s = _saldos(db, h, miembros)
    invitaciones = []
    if yo.rol == "admin":
        invitaciones = [
            {"id": i.id, "token": i.token, "email": i.email, "vence_en": i.vence_en}
            for i in db.query(InvitacionHogar)
            .filter(InvitacionHogar.hogar_id == h.id, InvitacionHogar.estado == "pendiente",
                    InvitacionHogar.vence_en > datetime.utcnow()).all()
        ]
    nombres = _nombres(miembros)
    return {
        "id": h.id, "nombre": h.nombre, "moneda": h.moneda, "rol": yo.rol, "mi_miembro_id": yo.id, "mis_avisos": yo.avisos,
        "miembros": [
            {"id": m.id, "apodo": nombres[m.id], "rol": m.rol, "activo": bool(m.activo), "soy_yo": m.id == yo.id,
             "saldo": s["neto"].get(m.id, 0.0)}
            for m in miembros if m.activo or m.id in s["neto"]
        ],
        "simplificado": s["simplificado"], "invitaciones": invitaciones,
    }


@router.patch("/{hogar_id}")
def renombrar(hogar_id: str, data: HogarPatch, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    _admin_o_403(yo)
    h.nombre = data.nombre.strip()
    db.commit()
    return {"ok": True}


@router.patch("/{hogar_id}/yo")
def mis_ajustes(hogar_id: str, data: YoPatch, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    _, yo = _miembro_o_404(db, usuario, hogar_id)
    if data.apodo is not None:
        yo.apodo = data.apodo.strip()
    if data.avisos is not None:
        yo.avisos = data.avisos
    db.commit()
    return {"ok": True}


@router.delete("/{hogar_id}")
def borrar(hogar_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Borra el hogar para TODOS (solo administración)."""
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    _admin_o_403(yo)
    borrar_hogar(db, h.id)
    db.commit()
    return {"ok": True}


# ---------- Miembros e invitar ----------

@router.post("/{hogar_id}/invitar")
def invitar(hogar_id: str, data: InvitarIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    _admin_o_403(yo)
    email = (data.email or "").strip().lower() or None
    if email and usuario.email and email == usuario.email.lower():
        raise HTTPException(status_code=400, detail="No puedes invitarte a ti mismo")
    if email:  # una sola invitación vigente por correo
        db.query(InvitacionHogar).filter(
            InvitacionHogar.hogar_id == h.id, InvitacionHogar.email == email, InvitacionHogar.estado == "pendiente"
        ).update({"estado": "cancelada"})
    inv = InvitacionHogar(
        hogar_id=h.id, token=secrets.token_urlsafe(24), email=email, invitado_por=usuario.id,
        vence_en=datetime.utcnow() + timedelta(days=DIAS_INVITACION),
    )
    db.add(inv)
    db.commit()
    return {"id": inv.id, "token": inv.token, "vence_en": inv.vence_en}


@router.delete("/{hogar_id}/invitaciones/{invitacion_id}")
def cancelar_invitacion(
    hogar_id: str, invitacion_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    _admin_o_403(yo)
    inv = db.query(InvitacionHogar).filter(InvitacionHogar.id == invitacion_id, InvitacionHogar.hogar_id == h.id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    inv.estado = "cancelada"
    db.commit()
    return {"ok": True}


@router.patch("/{hogar_id}/miembros/{miembro_id}")
def cambiar_rol(
    hogar_id: str, miembro_id: str, data: RolPatch,
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user),
):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    _admin_o_403(yo)
    m = db.query(MiembroHogar).filter(MiembroHogar.id == miembro_id, MiembroHogar.hogar_id == h.id, MiembroHogar.activo.is_(True)).first()
    if not m:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    if m.id == yo.id and data.rol != "admin":
        otros = db.query(MiembroHogar).filter(MiembroHogar.hogar_id == h.id, MiembroHogar.activo.is_(True),
                                              MiembroHogar.rol == "admin", MiembroHogar.id != yo.id).count()
        if not otros:
            raise HTTPException(status_code=400, detail="Nombra a otra persona administradora primero")
    m.rol = data.rol
    db.commit()
    return {"ok": True}


@router.delete("/{hogar_id}/miembros/{miembro_id}")
def quitar_o_salir(
    hogar_id: str, miembro_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Salir uno mismo, o que administración saque a otra persona. Lo que aportó se conserva en el libro."""
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    m = db.query(MiembroHogar).filter(MiembroHogar.id == miembro_id, MiembroHogar.hogar_id == h.id, MiembroHogar.activo.is_(True)).first()
    if not m:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    if m.id != yo.id:
        _admin_o_403(yo)
    activos = [x for x in _miembros(db, h.id) if x.activo]
    if len(activos) == 1:  # el último que sale apaga la luz: el hogar ya no tiene a nadie
        borrar_hogar(db, h.id)
        db.commit()
        return {"ok": True, "hogar_borrado": True}
    if m.rol == "admin" and not any(x.rol == "admin" and x.id != m.id for x in activos):
        raise HTTPException(status_code=400, detail="Nombra a otra persona administradora antes de salir")
    m.activo = False
    db.commit()
    return {"ok": True}


# ---------- Gastos ----------

def _serializar_gasto(g: GastoHogar, partes: dict[str, float], nombres: dict[str, str]) -> dict:
    return {
        "id": g.id, "descripcion": g.descripcion, "categoria": g.categoria, "total": g.total, "moneda": g.moneda,
        "modo": g.modo, "fecha": g.fecha, "pagador_id": g.pagador_id, "pagador": nombres.get(g.pagador_id, "?"),
        "creado_por_id": g.creado_por_id,
        "partes": [{"miembro_id": k, "nombre": nombres.get(k, "?"), "monto": v} for k, v in partes.items()],
    }


@router.get("/{hogar_id}/gastos")
def listar_gastos(hogar_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    nombres = _nombres(_miembros(db, h.id))
    gastos = db.query(GastoHogar).filter(GastoHogar.hogar_id == h.id).order_by(GastoHogar.fecha.desc()).limit(300).all()
    partes: dict[str, dict[str, float]] = {}
    mios: dict[str, str] = {}  # gasto_id -> movimiento personal que nació de MI parte (solo lo mío, nunca el de otros)
    if gastos:
        for p in db.query(ParteGastoHogar).filter(ParteGastoHogar.gasto_id.in_([g.id for g in gastos])).all():
            partes.setdefault(p.gasto_id, {})[p.miembro_id] = p.monto
            if p.miembro_id == yo.id and p.movimiento_id:
                mios[p.gasto_id] = p.movimiento_id
    # Si borré ese movimiento, el gasto vuelve a poder pasarse a mis gastos.
    vivos = set()
    if mios:
        vivos = {i for (i,) in db.query(Movimiento.id).filter(Movimiento.id.in_(list(mios.values()))).all()}
    salida = []
    for g in gastos:
        d = _serializar_gasto(g, partes.get(g.id, {}), nombres)
        d["mi_parte"] = partes.get(g.id, {}).get(yo.id)
        d["en_mis_gastos"] = mios.get(g.id) in vivos
        salida.append(d)
    return salida


class PasarAMisGastosIn(BaseModel):
    cuenta_id: str


@router.post("/{hogar_id}/gastos/{gasto_id}/a-mis-gastos")
def pasar_a_mis_gastos(hogar_id: str, gasto_id: str, data: PasarAMisGastosIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Copia MI parte de un gasto del hogar a una cuenta mía. Una sola vez por gasto: si ya está, avisa y no duplica."""
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    g = db.query(GastoHogar).filter(GastoHogar.id == gasto_id, GastoHogar.hogar_id == h.id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    parte = db.query(ParteGastoHogar).filter(ParteGastoHogar.gasto_id == g.id, ParteGastoHogar.miembro_id == yo.id).first()
    if not parte or parte.monto <= 0:
        raise HTTPException(status_code=400, detail="Este gasto no tiene una parte tuya")
    if parte.movimiento_id and db.query(Movimiento.id).filter(Movimiento.id == parte.movimiento_id).first():
        raise HTTPException(status_code=409, detail="Este gasto ya está en tus gastos")
    cuenta = cuenta_accesible(db, usuario.id, data.cuenta_id)
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    if (cuenta.moneda or "COP").upper() != (h.moneda or "COP").upper():
        raise HTTPException(status_code=400, detail="La cuenta debe estar en la misma moneda del hogar")
    mov = crear_movimiento(
        MovimientoCreate(
            cuenta_id=cuenta.id, descripcion=f"{g.descripcion} ({h.nombre})", monto=parte.monto, tipo="expense",
            categoria=g.categoria, fecha=g.fecha, notas="Gasto del hogar", confirmar_nuevo=True,
        ),
        db=db, usuario=usuario,
    )
    parte.movimiento_id = mov.id
    db.commit()
    return {"ok": True, "movimiento_id": mov.id, "monto": parte.monto}


@router.post("/{hogar_id}/gastos")
def crear_gasto(hogar_id: str, data: GastoIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    miembros = _miembros(db, h.id)
    activos = {m.id: m for m in miembros if m.activo}
    pagador = data.pagador_id or yo.id
    if pagador not in activos or any(p.id not in activos for p in data.participantes):
        raise HTTPException(status_code=400, detail="Solo pueden participar miembros del hogar")
    if len({p.id for p in data.participantes}) != len(data.participantes):
        raise HTTPException(status_code=400, detail="Hay personas repetidas")
    mov_origen = None
    total = data.total
    if data.movimiento_id:
        if data.registrar_en_mi_cuenta:
            raise HTTPException(status_code=400, detail="Este gasto ya está en tus movimientos: no se copia otra vez")
        mov_origen = _movimiento_mio_o_404(db, usuario, data.movimiento_id)
        if mov_origen.tipo != "expense":
            raise HTTPException(status_code=400, detail="Solo se pueden compartir gastos")
        cta = db.query(Cuenta).filter(Cuenta.id == mov_origen.cuenta_id).first()
        if (getattr(cta, "moneda", None) or "COP").upper() != (h.moneda or "COP").upper():
            raise HTTPException(status_code=400, detail="La cuenta de ese gasto debe estar en la misma moneda del parche")
        ya = (
            db.query(ParteGastoHogar.id)
            .join(MiembroHogar, MiembroHogar.id == ParteGastoHogar.miembro_id)
            .join(GastoHogar, GastoHogar.id == ParteGastoHogar.gasto_id)
            .filter(ParteGastoHogar.movimiento_id == mov_origen.id, MiembroHogar.usuario_id == usuario.id)
            .first()
        )
        if ya:
            raise HTTPException(status_code=409, detail="Este gasto ya está compartido en un parche")
        total = mov_origen.monto  # lo que de verdad pagué
    try:
        partes = dividir(total, data.modo, [{"id": p.id, "valor": p.valor} for p in data.participantes], decimales_de(h.moneda))
    except DivisionInvalida as e:
        raise HTTPException(status_code=400, detail=str(e))

    cuenta = None
    if data.registrar_en_mi_cuenta:
        if not data.cuenta_id:
            raise HTTPException(status_code=400, detail="Elige la cuenta donde quieres registrarlo")
        cuenta = cuenta_accesible(db, usuario.id, data.cuenta_id)
        if not cuenta:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        if (cuenta.moneda or "COP").upper() != (h.moneda or "COP").upper():
            raise HTTPException(status_code=400, detail="La cuenta debe estar en la misma moneda del hogar")

    fecha = data.fecha or (mov_origen.fecha if mov_origen is not None and mov_origen.fecha else None) or ahora_co()
    g = GastoHogar(
        hogar_id=h.id, descripcion=data.descripcion.strip(), categoria=data.categoria or (mov_origen.categoria if mov_origen is not None else None), total=total, moneda=h.moneda,
        modo=data.modo, pagador_id=pagador, creado_por_id=yo.id, fecha=fecha,
    )
    db.add(g)
    db.flush()
    filas_partes = {mid: ParteGastoHogar(gasto_id=g.id, miembro_id=mid, monto=monto) for mid, monto in partes.items()}
    db.add_all(filas_partes.values())
    mi_parte = partes.get(yo.id, 0.0)
    if mov_origen is not None and yo.id in filas_partes:
        filas_partes[yo.id].movimiento_id = mov_origen.id  # vínculo: este gasto es el movimiento que ya tenía
    if cuenta is not None and mi_parte > 0:  # solo MI parte, en MI cuenta (nada de otros miembros)
        mov = crear_movimiento(
            MovimientoCreate(
                cuenta_id=cuenta.id, descripcion=f"{data.descripcion.strip()} ({h.nombre})", monto=mi_parte, tipo="expense",
                categoria=data.categoria, fecha=fecha, notas="Gasto del hogar", confirmar_nuevo=True,
            ),
            db=db, usuario=usuario,
        )
        filas_partes[yo.id].movimiento_id = mov.id  # queda el vínculo: este gasto ya está en mis gastos
    db.commit()

    for m in activos.values():  # avisos a los demás (los que no los apagaron); nunca debe romper el registro
        if m.id != yo.id and m.avisos and m.usuario_id:
            try:
                enviar_push(db, m.usuario_id, h.nombre, f"{yo.apodo} registró «{g.descripcion}»", url=f"#/hogares/{h.id}")
            except Exception:  # noqa: BLE001
                pass
    return {"id": g.id, "partes": partes}


@router.delete("/{hogar_id}/gastos/{gasto_id}")
def borrar_gasto(
    hogar_id: str, gasto_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Lo borra quien lo registró o administración. Tu movimiento personal, si lo copiaste, no se toca."""
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    g = db.query(GastoHogar).filter(GastoHogar.id == gasto_id, GastoHogar.hogar_id == h.id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    if g.creado_por_id != yo.id:
        _admin_o_403(yo)
    db.query(ParteGastoHogar).filter(ParteGastoHogar.gasto_id == g.id).delete(synchronize_session=False)
    db.delete(g)
    db.commit()
    return {"ok": True}


# ---------- Pagos (liquidaciones) ----------

@router.get("/{hogar_id}/pagos")
def listar_pagos(hogar_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    h, _ = _miembro_o_404(db, usuario, hogar_id)
    nombres = _nombres(_miembros(db, h.id))
    pagos = db.query(PagoHogar).filter(PagoHogar.hogar_id == h.id).order_by(PagoHogar.fecha.desc()).limit(200).all()
    return [
        {"id": p.id, "de_id": p.de_id, "de": nombres.get(p.de_id, "?"), "a_id": p.a_id, "a": nombres.get(p.a_id, "?"),
         "monto": p.monto, "nota": p.nota, "fecha": p.fecha, "creado_por_id": p.creado_por_id}
        for p in pagos
    ]


@router.post("/{hogar_id}/pagos")
def registrar_pago(hogar_id: str, data: PagoIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    activos = {m.id for m in _miembros(db, h.id) if m.activo}
    if data.de_id == data.a_id or data.de_id not in activos or data.a_id not in activos:
        raise HTTPException(status_code=400, detail="El pago debe ser entre dos miembros distintos del hogar")
    if yo.id not in (data.de_id, data.a_id) and yo.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo puedes registrar pagos donde participas")
    p = PagoHogar(hogar_id=h.id, de_id=data.de_id, a_id=data.a_id, monto=data.monto, moneda=h.moneda,
                  nota=data.nota.strip(), creado_por_id=yo.id, fecha=ahora_co())
    db.add(p)
    db.commit()
    return {"id": p.id}


@router.delete("/{hogar_id}/pagos/{pago_id}")
def deshacer_pago(hogar_id: str, pago_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    h, yo = _miembro_o_404(db, usuario, hogar_id)
    p = db.query(PagoHogar).filter(PagoHogar.id == pago_id, PagoHogar.hogar_id == h.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if p.creado_por_id != yo.id:
        _admin_o_403(yo)
    db.delete(p)
    db.commit()
    return {"ok": True}


# ---------- Resumen del mes ----------

@router.get("/{hogar_id}/resumen")
def resumen(hogar_id: str, mes: Optional[str] = None, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Del mes (YYYY-MM, por defecto el actual): cuánto puso (pagó) y cuánto consumió (su parte) cada quien, y por categoría."""
    h, _ = _miembro_o_404(db, usuario, hogar_id)
    hoy = ahora_co()
    try:
        anio, m = (int(x) for x in (mes or f"{hoy.year}-{hoy.month:02d}").split("-"))
        inicio = datetime(anio, m, 1)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="El mes debe ser AAAA-MM")
    fin = datetime(anio + (m == 12), (m % 12) + 1, 1)
    nombres = _nombres(_miembros(db, h.id))
    gastos = db.query(GastoHogar).filter(GastoHogar.hogar_id == h.id, GastoHogar.fecha >= inicio, GastoHogar.fecha < fin).all()
    puso: dict[str, float] = {}
    consumio: dict[str, float] = {}
    categorias: dict[str, float] = {}
    if gastos:
        for g in gastos:
            puso[g.pagador_id] = puso.get(g.pagador_id, 0.0) + g.total
            categorias[g.categoria or "Otros"] = categorias.get(g.categoria or "Otros", 0.0) + g.total
        for p in db.query(ParteGastoHogar).filter(ParteGastoHogar.gasto_id.in_([g.id for g in gastos])).all():
            consumio[p.miembro_id] = consumio.get(p.miembro_id, 0.0) + p.monto
    ids = list(dict.fromkeys([*puso, *consumio]))
    return {
        "mes": f"{anio}-{m:02d}", "moneda": h.moneda, "total": sum(g.total for g in gastos),
        "por_miembro": [
            {"miembro_id": i, "nombre": nombres.get(i, "?"), "puso": puso.get(i, 0.0), "consumio": consumio.get(i, 0.0)}
            for i in ids
        ],
        "por_categoria": sorted(({"categoria": k, "monto": v} for k, v in categorias.items()), key=lambda x: -x["monto"]),
    }
