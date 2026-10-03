import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.database import get_db
from app.models import Movimiento

router = APIRouter(prefix="/exportar", tags=["exportar"])


def _movimientos_rango(
    db: Session, usuario_id: str, desde: str | None, hasta: str | None
) -> list[Movimiento]:
    ids_accesibles = cuentas_ids_accesibles(db, usuario_id)
    query = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids_accesibles))
    if desde:
        query = query.filter(Movimiento.fecha >= datetime.fromisoformat(desde))
    if hasta:
        query = query.filter(Movimiento.fecha <= datetime.fromisoformat(hasta))
    return query.order_by(Movimiento.fecha.asc()).all()


@router.get("/movimientos.csv")
def exportar_csv(
    desde: str | None = None,
    hasta: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    movimientos = _movimientos_rango(db, usuario.id, desde, hasta)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Fecha", "Descripción", "Categoría", "Tipo", "Monto", "Fuente", "Notas"])
    for m in movimientos:
        writer.writerow([
            m.fecha.strftime("%Y-%m-%d"), m.descripcion, m.categoria,
            m.tipo, m.monto, m.fuente, m.notas,
        ])

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=movimientos_cuadrame.csv"},
    )


@router.get("/movimientos.xlsx")
def exportar_excel(
    desde: str | None = None,
    hasta: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    movimientos = _movimientos_rango(db, usuario.id, desde, hasta)

    wb = Workbook()
    ws = wb.active
    ws.title = "Movimientos"

    encabezados = ["Fecha", "Descripción", "Categoría", "Tipo", "Monto", "Fuente", "Notas"]
    ws.append(encabezados)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for m in movimientos:
        ws.append([
            m.fecha.strftime("%Y-%m-%d"), m.descripcion, m.categoria,
            m.tipo, m.monto, m.fuente, m.notas,
        ])

    for col in ws.columns:
        largo = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(40, largo + 2)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=movimientos_cuadrame.xlsx"},
    )
