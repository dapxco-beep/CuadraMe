import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.conciliacion import (
    auditar_movimientos,
    compute_fingerprint,
    detectar_banco,
    parse_bank_date,
    parse_texto_con_regex,
)
from app.database import get_db
from app.models import Cuenta, HistorialExtracto, Movimiento
from app.pdf_extract import extraer_via_ia, pdf_a_texto
from app.schemas import (
    HistorialExtractoOut,
    ImportarFaltantesRequest,
    ProcesarExtractoRequest,
    ProcesarExtractoResponse,
)

router = APIRouter(prefix="/conciliacion", tags=["conciliacion"])


@router.post("/procesar", response_model=ProcesarExtractoResponse)
def procesar_extracto(
    data: ProcesarExtractoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.id == data.cuenta_id, Cuenta.usuario_id == usuario.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    texto_plano = pdf_a_texto(data.pdf_base64, data.password)
    banco = detectar_banco(texto_plano) if texto_plano else "desconocido"

    movimientos = parse_texto_con_regex(texto_plano) if texto_plano else []
    if not movimientos:
        movimientos = extraer_via_ia(texto_plano, cuenta.nombre, banco)

    if not movimientos:
        historial = HistorialExtracto(
            usuario_id=usuario.id,
            cuenta_id=cuenta.id,
            banco_detectado=banco,
            estado="error",
        )
        db.add(historial)
        db.commit()
        detalle = (
            f"Texto extraído del PDF ({len(texto_plano)} chars): {texto_plano[:300]}"
            if texto_plano and len(texto_plano) > 10
            else "No se extrajo texto del PDF (posiblemente protegido con otra clave o escaneado como imagen)."
        )
        return ProcesarExtractoResponse(
            ok=False,
            error=f"No se pudieron extraer movimientos del PDF. {detalle}",
            banco_detectado=banco,
        )

    ledger = _cargar_ledger(db, usuario.id, cuenta.id)
    for mov in movimientos:
        mov["cuenta"] = cuenta.nombre
    resultado = auditar_movimientos(movimientos, ledger)

    historial = HistorialExtracto(
        usuario_id=usuario.id,
        cuenta_id=cuenta.id,
        banco_detectado=banco,
        total_movimientos=resultado["total_movimientos"],
        exactos=resultado["exactos"],
        aproximados=resultado["aproximados"],
        faltantes=resultado["faltantes"],
        estado="pendiente_revision",
        review_json=json.dumps(resultado["review"], default=str),
    )
    db.add(historial)
    db.commit()
    db.refresh(historial)

    return ProcesarExtractoResponse(
        ok=True,
        historial_id=historial.id,
        banco_detectado=banco,
        total_movimientos=resultado["total_movimientos"],
        exactos=resultado["exactos"],
        aproximados=resultado["aproximados"],
        faltantes=resultado["faltantes"],
        review=resultado["review"],
    )


@router.get("/historial", response_model=list[HistorialExtractoOut])
def listar_historial(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    return (
        db.query(HistorialExtracto)
        .filter(HistorialExtracto.usuario_id == usuario.id)
        .order_by(HistorialExtracto.creado_en.desc())
        .all()
    )


@router.get("/historial/{historial_id}", response_model=ProcesarExtractoResponse)
def obtener_review(
    historial_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    historial = (
        db.query(HistorialExtracto)
        .filter(HistorialExtracto.id == historial_id, HistorialExtracto.usuario_id == usuario.id)
        .first()
    )
    if not historial:
        raise HTTPException(status_code=404, detail="Historial no encontrado")

    return ProcesarExtractoResponse(
        ok=True,
        historial_id=historial.id,
        banco_detectado=historial.banco_detectado,
        total_movimientos=historial.total_movimientos,
        exactos=historial.exactos,
        aproximados=historial.aproximados,
        faltantes=historial.faltantes,
        review=json.loads(historial.review_json or "[]"),
    )


@router.post("/historial/{historial_id}/importar")
def importar_faltantes(
    historial_id: str,
    data: ImportarFaltantesRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    historial = (
        db.query(HistorialExtracto)
        .filter(HistorialExtracto.id == historial_id, HistorialExtracto.usuario_id == usuario.id)
        .first()
    )
    if not historial:
        raise HTTPException(status_code=404, detail="Historial no encontrado")

    cuenta = (
        db.query(Cuenta)
        .filter(Cuenta.id == historial.cuenta_id, Cuenta.usuario_id == usuario.id)
        .first()
    )
    if not cuenta:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    review = json.loads(historial.review_json or "[]")
    fingerprints = set(data.fingerprints)
    importados = 0

    for item in review:
        if item.get("fingerprint") not in fingerprints or item.get("estado") != "faltante":
            continue

        movimiento = Movimiento(
            usuario_id=usuario.id,
            cuenta_id=cuenta.id,
            descripcion=item["descripcion"],
            categoria="Otros",
            tipo=item["tipo"],
            monto=item["monto"],
            fecha=parse_bank_date(item["fecha"]) or historial.creado_en,
            fuente="conciliacion_extracto",
            notas=f"Importado desde extracto {historial.banco_detectado}",
        )
        db.add(movimiento)

        if item["tipo"] == "income":
            cuenta.saldo += item["monto"]
        elif item["tipo"] == "expense":
            cuenta.saldo -= item["monto"]

        item["estado"] = "importado"
        importados += 1

    historial.review_json = json.dumps(review, default=str)
    historial.importados = (historial.importados or 0) + importados
    if all(i["estado"] != "faltante" for i in review):
        historial.estado = "conciliado"

    db.commit()
    return {"ok": True, "importados": importados}


@router.delete("/historial/{historial_id}")
def eliminar_historial(
    historial_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    historial = (
        db.query(HistorialExtracto)
        .filter(HistorialExtracto.id == historial_id, HistorialExtracto.usuario_id == usuario.id)
        .first()
    )
    if not historial:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    db.delete(historial)
    db.commit()
    return {"ok": True}


def _cargar_ledger(db: Session, usuario_id: str, cuenta_id: str) -> list[dict]:
    movimientos = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id == cuenta_id)
        .all()
    )
    ledger = []
    for m in movimientos:
        fp = compute_fingerprint(m.fecha, m.monto, cuenta_id, m.descripcion, m.tipo)
        ledger.append({
            "id": m.id,
            "fecha": m.fecha,
            "monto": m.monto,
            "descripcion": m.descripcion,
            "cuenta_origen": cuenta_id,
            "fingerprint": fp,
        })
    return ledger
