import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.limites import verificar_limite
from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user
from app.classifier import build_model, classify
from app.comercios_conocidos import clasificar_por_diccionario
from app.compartidos import cuenta_accesible, puede_editar_cuenta
from app.conciliacion import (
    auditar_movimientos,
    compute_fingerprint,
    detectar_banco,
    parse_bank_date,
    fijar_nombre_titular,
    parse_texto_con_regex,
)
from app.database import get_db
from app.models import Cuenta, HistorialExtracto, Movimiento, Perfil
from app.pdf_extract import extraer_via_ia, pdf_a_texto
from app.schemas import (
    HistorialExtractoOut,
    ImportarFaltantesRequest,
    ProcesarExtractoRequest,
    ProcesarExtractoResponse,
)

# Umbral de confianza por defecto del clasificador aprendido para auto-importar
# sin pasar por revisión manual. Cada usuario puede ajustar el suyo desde
# Perfil (perfil.confianza_autoimport) si quiere ser más o menos estricto.
# Solo aplica a movimientos detectados por los parsers regex específicos de
# banco (no al fallback de IA, más propenso a error de lectura del PDF).
CONFIANZA_AUTOIMPORT_DEFAULT = 0.75

router = APIRouter(prefix="/conciliacion", tags=["conciliacion"])


def _umbral_autoimport(db: Session, usuario_id: str) -> float:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    if perfil and perfil.confianza_autoimport:
        return perfil.confianza_autoimport
    return CONFIANZA_AUTOIMPORT_DEFAULT


@router.post("/procesar", response_model=ProcesarExtractoResponse)
def procesar_extracto(
    data: ProcesarExtractoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = cuenta_accesible(db, usuario.id, data.cuenta_id)
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    verificar_limite(f"extracto:{usuario.id}", 10, 3600, "Subiste muchos extractos seguidos. Intenta en un rato.")
    texto_plano = pdf_a_texto(data.pdf_base64, data.password)
    banco = detectar_banco(texto_plano) if texto_plano else "desconocido"

    fijar_nombre_titular(usuario.nombre)
    movimientos, descartados = parse_texto_con_regex(texto_plano) if texto_plano else ([], 0)
    via_ia = False
    if not movimientos:
        movimientos = extraer_via_ia(texto_plano, cuenta.nombre, banco)
        via_ia = True

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

    # Auto-importar los "faltantes" con alta confianza del clasificador aprendido,
    # solo cuando vinieron del parser regex de banco (no del fallback de IA).
    auto_importados = 0
    historial_mov = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == usuario.id, Movimiento.categoria != "Otros")
        .all()
    )
    modelo = build_model(
        [{"descripcion": m.descripcion, "categoria": m.categoria, "tipo": m.tipo} for m in historial_mov]
    )
    umbral = _umbral_autoimport(db, usuario.id)

    for item in resultado["review"]:
        if item["estado"] != "faltante":
            continue
        clasif = classify(item["descripcion"], modelo) or clasificar_por_diccionario(item["descripcion"])

        if not via_ia and clasif and clasif["confianza"] >= umbral:
            fecha_dt = parse_bank_date(item["fecha"])
            movimiento = Movimiento(
                usuario_id=usuario.id,
                cuenta_id=cuenta.id,
                descripcion=item["descripcion"],
                categoria=clasif["categoria"],
                tipo=item["tipo"],
                monto=item["monto"],
                fecha=fecha_dt or ahora_co(),
                fuente="conciliacion_auto",
                notas=f"Auto-importado desde extracto {banco} (confianza {clasif['confianza']})",
            )
            db.add(movimiento)

            if item["tipo"] == "income":
                cuenta.saldo += item["monto"]
            elif item["tipo"] == "expense":
                cuenta.saldo -= item["monto"]

            item["estado"] = "importado"
            auto_importados += 1
        else:
            # No se auto-importó (confianza baja, viene de IA, o no hubo match):
            # igual se muestra la categoría sugerida en el review para que el
            # usuario la vea y pueda corregirla ANTES de importar manualmente,
            # en vez de que quede oculta y todo termine en "Otros" en silencio.
            item["categoria_sugerida"] = clasif["categoria"] if clasif else "Otros"

    if auto_importados:
        resultado["faltantes"] -= auto_importados

    historial = HistorialExtracto(
        usuario_id=usuario.id,
        cuenta_id=cuenta.id,
        banco_detectado=banco,
        total_movimientos=resultado["total_movimientos"],
        exactos=resultado["exactos"],
        aproximados=resultado["aproximados"],
        faltantes=resultado["faltantes"],
        descartados=descartados,
        importados=auto_importados,
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
        descartados=descartados,
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
        descartados=historial.descartados or 0,
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

    cuenta = cuenta_accesible(db, usuario.id, historial.cuenta_id)
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    review = json.loads(historial.review_json or "[]")
    fingerprints = set(data.fingerprints)
    importados = 0

    historial_mov = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == usuario.id, Movimiento.categoria != "Otros")
        .all()
    )
    modelo = build_model(
        [{"descripcion": m.descripcion, "categoria": m.categoria, "tipo": m.tipo} for m in historial_mov]
    )

    categorias_elegidas = data.categorias or {}
    sin_categoria_clara = 0

    for item in review:
        fp = item.get("fingerprint")
        if fp not in fingerprints or item.get("estado") != "faltante":
            continue

        if fp in categorias_elegidas and categorias_elegidas[fp]:
            categoria = categorias_elegidas[fp]
        else:
            clasif = classify(item["descripcion"], modelo) or clasificar_por_diccionario(item["descripcion"])
            categoria = clasif["categoria"] if clasif else "Otros"
            if categoria == "Otros":
                sin_categoria_clara += 1

        movimiento = Movimiento(
            usuario_id=usuario.id,
            cuenta_id=cuenta.id,
            descripcion=item["descripcion"],
            categoria=categoria,
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
    return {"ok": True, "importados": importados, "sin_categoria_clara": sin_categoria_clara}


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
