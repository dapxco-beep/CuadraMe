"""«Tu plata trabajando»: cajitas/bolsillos, rendimiento estimado y tasas de referencia.

Personas: GET /rendimientos (resumen), cajitas (crear, editar, borrar, mover plata) y
GET /rendimientos/tasas (lectura). Administración (ADMIN_EMAIL; 404 para el resto, como una ruta
que no existe): crear / editar / desactivar tasas de referencia.

Mover plata entre el saldo principal y una cajita NO crea movimientos ni cambia el saldo de la
cuenta (la cajita es una parte de ese saldo): es neutral por construcción."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import rendimientos as calc
from app.auth import UsuarioActual, get_current_user
from app.crecimiento import es_admin
from app.database import get_db
from app.models import Cuenta
from app.models_rendimientos import Cajita, TasaReferencia
from app.utiles import ahora_co

router = APIRouter(prefix="/rendimientos", tags=["rendimientos"])

MAX_NOMBRE = 40
TASA_MAX = 100.0


class CajitaIn(BaseModel):
    cuenta_id: str
    nombre: str = Field(min_length=1, max_length=MAX_NOMBRE)
    saldo: float = Field(default=0, ge=0)
    tasa_ea: float | None = Field(default=None, ge=0, le=TASA_MAX)
    tasa_fecha: date | None = None


class CajitaEdit(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=MAX_NOMBRE)
    saldo: float | None = Field(default=None, ge=0)
    tasa_ea: float | None = Field(default=None, ge=0, le=TASA_MAX)
    quitar_tasa: bool = False
    tasa_fecha: date | None = None


class MoverIn(BaseModel):
    monto: float = Field(gt=0)
    sentido: str = Field(pattern="^(entrar|salir)$")  # entrar: saldo principal -> cajita; salir: cajita -> principal


class TasaIn(BaseModel):
    entidad: str = Field(min_length=1, max_length=80)
    producto: str = Field(min_length=1, max_length=80)
    tipo: str = Field(default="ahorro_vista")
    tasa_ea: float | None = Field(default=None, ge=0, le=TASA_MAX)
    vigente_desde: date | None = None
    fuente_url: str | None = Field(default=None, max_length=300)
    nota: str | None = Field(default=None, max_length=300)
    activa: bool = True


def _solo_admin(usuario: UsuarioActual):
    if not es_admin(usuario.email):
        raise HTTPException(status_code=404, detail="No encontrado")


def _cuenta_propia(db: Session, usuario_id: str, cuenta_id: str) -> Cuenta:
    c = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    if c.tipo != "ahorro":
        raise HTTPException(status_code=400, detail="Las cajitas son para cuentas de ahorro.")
    return c


def _cajita_propia(db: Session, usuario_id: str, cajita_id: str) -> Cajita:
    k = db.query(Cajita).filter(Cajita.id == cajita_id, Cajita.usuario_id == usuario_id,
                                Cajita.activa == True).first()  # noqa: E712
    if not k:
        raise HTTPException(status_code=404, detail="Cajita no encontrada")
    return k


def _principal(db: Session, cuenta: Cuenta, excepto: str | None = None) -> float:
    """Lo que queda en el saldo principal: saldo de la cuenta menos lo apartado en las demás cajitas."""
    q = db.query(Cajita).filter(Cajita.cuenta_id == cuenta.id, Cajita.activa == True)  # noqa: E712
    apartado = sum(float(k.saldo or 0) for k in q.all() if k.id != excepto)
    return float(cuenta.saldo or 0) - apartado


def _salida(k: Cajita) -> dict:
    return {"id": k.id, "cuenta_id": k.cuenta_id, "nombre": k.nombre, "saldo": k.saldo, "tasa_ea": k.tasa_ea,
            "tasa_fecha": k.tasa_fecha.isoformat() if k.tasa_fecha else None}


def _sin_plata(disponible: float) -> HTTPException:
    return HTTPException(status_code=400, detail=(
        f"En el saldo principal solo hay ${max(0, round(disponible)):,.0f}".replace(",", ".") + " para apartar."))


# ── resumen ───────────────────────────────────────────────────────────────────────────
@router.get("")
def resumen(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    return calc.resumen(db, usuario.id, ahora_co())


# ── cajitas ───────────────────────────────────────────────────────────────────────────
@router.post("/cajitas")
def crear_cajita(data: CajitaIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    cuenta = _cuenta_propia(db, usuario.id, data.cuenta_id)
    if data.saldo > _principal(db, cuenta) + 0.5:
        raise _sin_plata(_principal(db, cuenta))
    k = Cajita(usuario_id=usuario.id, cuenta_id=cuenta.id, nombre=data.nombre.strip(), saldo=data.saldo,
               tasa_ea=data.tasa_ea, tasa_fecha=(data.tasa_fecha or ahora_co().date()) if data.tasa_ea is not None else None)
    db.add(k)
    db.commit()
    db.refresh(k)
    return _salida(k)


@router.put("/cajitas/{cajita_id}")
def editar_cajita(cajita_id: str, data: CajitaEdit, db: Session = Depends(get_db),
                  usuario: UsuarioActual = Depends(get_current_user)):
    k = _cajita_propia(db, usuario.id, cajita_id)
    cuenta = _cuenta_propia(db, usuario.id, k.cuenta_id)
    if data.nombre is not None:
        k.nombre = data.nombre.strip()
    if data.saldo is not None:
        if data.saldo > _principal(db, cuenta, excepto=k.id) + 0.5:
            raise _sin_plata(_principal(db, cuenta, excepto=k.id))
        k.saldo = data.saldo
    if data.quitar_tasa:
        k.tasa_ea, k.tasa_fecha = None, None
    elif data.tasa_ea is not None:
        k.tasa_ea = data.tasa_ea
        k.tasa_fecha = data.tasa_fecha or ahora_co().date()
    db.commit()
    return _salida(k)


@router.post("/cajitas/{cajita_id}/mover")
def mover_plata(cajita_id: str, data: MoverIn, db: Session = Depends(get_db),
                usuario: UsuarioActual = Depends(get_current_user)):
    k = _cajita_propia(db, usuario.id, cajita_id)
    cuenta = _cuenta_propia(db, usuario.id, k.cuenta_id)
    if data.sentido == "entrar":
        disponible = _principal(db, cuenta)
        if data.monto > disponible + 0.5:
            raise _sin_plata(disponible)
        k.saldo = float(k.saldo or 0) + data.monto
    else:
        if data.monto > float(k.saldo or 0) + 0.5:
            raise HTTPException(status_code=400, detail="La cajita no tiene tanta plata.")
        k.saldo = max(0.0, float(k.saldo or 0) - data.monto)
    db.commit()
    return _salida(k)


@router.delete("/cajitas/{cajita_id}")
def borrar_cajita(cajita_id: str, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Borrar una cajita devuelve su plata al saldo principal (el saldo de la cuenta no cambia)."""
    k = _cajita_propia(db, usuario.id, cajita_id)
    k.activa = False
    k.saldo = 0
    db.commit()
    return {"ok": True}


# ── tasas de referencia ───────────────────────────────────────────────────────────────
@router.get("/tasas")
def listar_tasas(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    hoy = ahora_co().date()
    return {"aviso": calc.AVISO,
            "nota": "Son tasas de referencia, no ofertas: cambian con frecuencia. Verifica en la app de tu banco.",
            "tasas": [calc.serializar_tasa(t, hoy) for t in calc.tasas(db)]}


def _aplicar(t: TasaReferencia, data: TasaIn):
    if data.tipo not in calc.TIPOS_TASA:
        raise HTTPException(status_code=422, detail="Tipo de tasa no válido.")
    t.entidad, t.producto, t.tipo = data.entidad.strip(), data.producto.strip(), data.tipo
    t.tasa_ea, t.fuente_url, t.nota, t.activa = data.tasa_ea, data.fuente_url, data.nota, data.activa
    t.vigente_desde = data.vigente_desde or ahora_co().date()


@router.get("/tasas/admin")
def listar_tasas_admin(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    _solo_admin(usuario)
    hoy = ahora_co().date()
    return {"tasas": [calc.serializar_tasa(t, hoy) for t in calc.tasas(db, solo_activas=False)]}


@router.post("/tasas")
def crear_tasa(data: TasaIn, db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    _solo_admin(usuario)
    t = TasaReferencia()
    _aplicar(t, data)
    db.add(t)
    db.commit()
    return calc.serializar_tasa(t, ahora_co().date())


@router.put("/tasas/{tasa_id}")
def editar_tasa(tasa_id: str, data: TasaIn, db: Session = Depends(get_db),
                usuario: UsuarioActual = Depends(get_current_user)):
    _solo_admin(usuario)
    t = db.query(TasaReferencia).filter(TasaReferencia.id == tasa_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="No encontrado")
    _aplicar(t, data)
    db.commit()
    return calc.serializar_tasa(t, ahora_co().date())
