from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.models import Movimiento
from app.reportes import calc_health_score
from app.schemas import ReporteMensual

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/mensual", response_model=ReporteMensual)
def reporte_mensual(
    mes: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    mes_target = mes or datetime.utcnow().strftime("%Y-%m")

    movimientos = db.query(Movimiento).filter(Movimiento.usuario_id == usuario.id).all()
    mes_movs = [m for m in movimientos if m.fecha.strftime("%Y-%m") == mes_target]

    ingresos = sum(m.monto for m in mes_movs if m.tipo == "income")
    gastos = sum(m.monto for m in mes_movs if m.tipo == "expense")
    ahorro = ingresos - gastos

    categorias: dict[str, float] = {}
    for m in mes_movs:
        if m.tipo == "expense":
            categorias[m.categoria] = categorias.get(m.categoria, 0) + m.monto
    top_categorias = sorted(
        ({"categoria": k, "monto": v} for k, v in categorias.items()),
        key=lambda x: x["monto"],
        reverse=True,
    )[:5]

    salud = calc_health_score(ingresos, gastos, ahorro, len(mes_movs))

    return ReporteMensual(
        mes=mes_target,
        ingresos=ingresos,
        gastos=gastos,
        ahorro=ahorro,
        tasa_ahorro=salud["tasa_ahorro"],
        top_categorias=top_categorias,
        salud=salud,
    )
