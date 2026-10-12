"""Lo que te cuesta tener tu plata: GET /costos-bancarios (análisis por mes y cuenta, alertas, suscripciones)
y un cron diario que avisa por push de un cobro inusual y relevante (máximo 1 aviso por día por persona)."""
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import cargos_inusuales, costos_bancarios as cb
from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.crons import Corrida
from app.database import get_db
from app.limites_diarios import consumir_cupo_diario
from app.models import PushSubscription
from app.push import enviar_push
from app.utiles import ahora_co

router = APIRouter(prefix="/costos-bancarios", tags=["costos-bancarios"])

MAX_DIAS = 366 * 3


def _fecha(valor: str | None, nombre: str) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"«{nombre}» debe ser una fecha AAAA-MM-DD")


def _rango(desde: str | None, hasta: str | None, hoy: date) -> tuple[date, date]:
    h = _fecha(hasta, "hasta") or hoy
    d = _fecha(desde, "desde")
    if d is None:  # por defecto, los últimos 6 meses (mes actual incluido)
        a, m = h.year, h.month - 5
        while m < 1:
            a, m = a - 1, m + 12
        d = date(a, m, 1)
    if d > h:
        raise HTTPException(status_code=422, detail="«desde» no puede ser posterior a «hasta»")
    if (h - d).days > MAX_DIAS:
        raise HTTPException(status_code=422, detail="El rango es demasiado largo (máximo 3 años)")
    return d, h


@router.get("")
def costos_bancarios(
    desde: str | None = None,
    hasta: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    ahora = ahora_co()
    d, h = _rango(desde, hasta, ahora.date())
    out = cb.analizar_usuario(db, usuario.id, d, h, ahora)
    cargos = cargos_inusuales.detectar_usuario(db, usuario.id, ahora)
    out["suscripciones"] = {"lista": cargos["suscripciones"], "total_mensual": cargos["total_mensual_suscripciones"]}
    out["alertas"] = sorted(out["alertas"] + cargos["alertas"], key=lambda a: a["prioridad"])
    return out


@router.post("/cron/avisar-cargos")
def cron_avisar_cargos(db: Session = Depends(get_db), x_cron_secret: str = Header(default="")):
    """Una vez al día: si a alguien con push le llegó en las últimas 24 h un cobro nuevo o inusual y de monto
    relevante, se le avisa. Tope de 1 aviso por persona y por día; los montos pequeños nunca generan push."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")
    ahora = ahora_co()
    usuarios = {s[0] for s in db.query(PushSubscription.usuario_id).distinct().all()}
    corrida = Corrida(db)
    avisados = 0
    for uid in sorted(usuarios):
        with corrida.aislar(uid):
            cargos = cargos_inusuales.detectar_usuario(db, uid, ahora)
            candidatas = [
                a for a in cargos["alertas"]
                if a["tipo"] in ("cargo_inusual", "cargo_cambio") and a.get("monto", 0) >= cargos_inusuales.MONTO_RELEVANTE_PUSH
                and a.get("movimiento_id")
            ]
            if not candidatas:
                continue
            a = max(candidatas, key=lambda x: x["monto"])
            try:
                consumir_cupo_diario(db, uid, "aviso-cargo-inusual")
            except HTTPException:
                continue  # ya se le avisó hoy
            enviar_push(db, uid, "Un cobro que no esperábamos", a["texto"][:140], "/costos", boton="Revisarlo")
            avisados += 1
    return {"ok": True, "avisados": avisados, **corrida.resumen()}
