import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.config import settings
from app.database import get_db
from app.models import Perfil

router = APIRouter(prefix="/pagos", tags=["pagos"])

stripe.api_key = settings.stripe_secret_key


def _get_or_create_perfil(db: Session, usuario_id: str) -> Perfil:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    if not perfil:
        perfil = Perfil(usuario_id=usuario_id, plan="free")
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
    return perfil


@router.get("/plan")
def obtener_plan(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    perfil = _get_or_create_perfil(db, usuario.id)
    return {"plan": perfil.plan}


@router.post("/checkout")
def crear_checkout(
    success_url: str,
    cancel_url: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    perfil = _get_or_create_perfil(db, usuario.id)
    if perfil.plan == "pro":
        raise HTTPException(status_code=400, detail="Ya tienes CuadraMe Pro")

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "cop",
                    "product_data": {"name": "CuadraMe Pro — acceso de por vida"},
                    "unit_amount": settings.stripe_price_lifetime_cop,
                },
                "quantity": 1,
            }
        ],
        customer_email=usuario.email,
        client_reference_id=usuario.id,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Firma de webhook inválida")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        usuario_id = session.client_reference_id
        if usuario_id:
            perfil = _get_or_create_perfil(db, usuario_id)
            perfil.plan = "pro"
            perfil.stripe_customer_id = session.customer
            db.commit()

    return {"ok": True}
