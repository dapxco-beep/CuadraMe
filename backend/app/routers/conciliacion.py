import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.limites import verificar_limite
from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user
from app.autocat import (
    ClasificadorUsuario, aplicar_a_anteriores, ajustar_a_categorias_usuario, datos_auto,
    guardar_regla_aprendida, origen_de,
)
from app.wallet import ORIGENES_RAPIDOS
from app.compartidos import cuenta_accesible, puede_editar_cuenta
from app.conciliacion import (
    auditar_movimientos,
    compute_fingerprint,
    detectar_banco,
    normalize_texto,
    parse_bank_date,
    fijar_nombre_titular,
    parse_texto_con_regex,
)
from app.database import get_db
from app.models import Cuenta, HistorialExtracto, Movimiento, Perfil
from app.pdf_extract import extraer_via_ia, pdf_a_texto, pdf_pide_clave
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
        if not texto_plano and pdf_pide_clave(data.pdf_base64, data.password):
            return ProcesarExtractoResponse(
                ok=False, requiere_clave=True, banco_detectado=banco,
                error="El PDF tiene clave: escríbela e inténtalo de nuevo." if not data.password
                else "La clave del PDF no es correcta.",
            )
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
        # La huella del ledger (_cargar_ledger) usa el id de la cuenta; con el nombre
        # nunca coincidían y los movimientos ya registrados salían como "aproximados".
        mov["cuenta"] = cuenta.id
    resultado = auditar_movimientos(movimientos, ledger, cruzar_rapidos=True)

    # Auto-importar los "faltantes" con alta confianza del clasificador aprendido,
    # solo cuando vinieron del parser regex de banco (no del fallback de IA).
    auto_importados = 0
    # Solo lo confirmado por el usuario alimenta el aprendizaje.
    modelo = ClasificadorUsuario(db, usuario.id)
    umbral = _umbral_autoimport(db, usuario.id)

    for item in resultado["review"]:
        if item["estado"] != "faltante":
            continue
        clasif = modelo.clasificar(item["descripcion"])

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
                **datos_auto(origen_de(clasif.get("fuente")) or "similar"),
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
            item["razon_categoria"] = clasif.get("razon") if clasif else None

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
    )
    db.add(historial)
    db.flush()  # para tener historial.id y marcarlo en los movimientos completados

    # Completar con el banco los movimientos rápidos emparejados (1:1).
    ids_completar = {i["match_id"] for i in resultado["review"] if i["estado"] == "completado"}
    registrados = (
        {m.id: m for m in db.query(Movimiento).filter(Movimiento.id.in_(ids_completar), Movimiento.usuario_id == usuario.id).all()}
        if ids_completar else {}
    )
    for item in resultado["review"]:
        if item["estado"] != "completado":
            continue
        mov = registrados.get(item["match_id"])
        if mov is None or mov.conciliado_en is not None:
            item["estado"] = "faltante"  # alguien lo concilió entretanto: se trata como nuevo
            item.pop("match_id", None)
            item["categoria_sugerida"] = "Otros"
            resultado["faltantes"] += 1
            resultado["completados"] -= 1
            continue
        _completar_con_extracto(db, mov, item, historial.id, modelo, usuario.id)

    # Registrados que no aparecen en el extracto: se guardan en la revisión.
    for s in resultado.get("sobrantes", []):
        resultado["review"].append({
            "fecha": s["fecha"], "descripcion": s["descripcion"], "monto": s["monto"], "tipo": s["tipo"],
            "referencia": "", "fingerprint": f"sobrante-{s['id']}", "estado": "sobrante", "match_id": s["id"],
        })

    historial.review_json = json.dumps(resultado["review"], default=str)
    db.commit()
    db.refresh(historial)
    completados, sobrantes = _contar_review(resultado["review"])

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
        auto_importados=auto_importados,
        completados=completados,
        sobrantes=sobrantes,
        **_periodo(resultado["review"]),
    )


def _periodo(review: list[dict]) -> dict:
    """Primer y último día (ISO) de los movimientos del extracto, para mostrar el periodo
    de cada archivo cuando se suben varios."""
    fechas = [d for d in (parse_bank_date(i.get("fecha")) for i in review if i.get("estado") != "sobrante") if d]
    if not fechas:
        return {"periodo_desde": None, "periodo_hasta": None}
    return {"periodo_desde": min(fechas).date().isoformat(), "periodo_hasta": max(fechas).date().isoformat()}


@router.get("/historial",response_model=list[HistorialExtractoOut])
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

    review = json.loads(historial.review_json or "[]")
    completados, sobrantes = _contar_review(review)
    return ProcesarExtractoResponse(
        ok=True,
        historial_id=historial.id,
        banco_detectado=historial.banco_detectado,
        total_movimientos=historial.total_movimientos,
        exactos=historial.exactos,
        aproximados=historial.aproximados,
        faltantes=historial.faltantes,
        descartados=historial.descartados or 0,
        review=review,
        completados=completados,
        sobrantes=sobrantes,
        **_periodo(review),
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

    modelo = ClasificadorUsuario(db, usuario.id)

    categorias_elegidas = data.categorias or {}
    sin_categoria_clara = 0
    categorizados_auto = 0
    recordar, anteriores = set(data.recordar), set(data.aplicar_anteriores)
    reglas_guardadas = anteriores_actualizados = 0
    reglas_omitidas: list[dict] = []
    # Varios extractos con periodos que se solapan comparten movimientos: si otro archivo (o
    # el usuario) ya los registró, aquí no se duplican.
    ya_registrados = {r["fingerprint"] for r in _cargar_ledger(db, usuario.id, cuenta.id)}
    duplicados_omitidos = 0

    for item in review:
        fp = item.get("fingerprint")
        if fp not in fingerprints or item.get("estado") != "faltante":
            continue
        if fp in ya_registrados:
            item["estado"] = "exacto"
            duplicados_omitidos += 1
            continue

        if fp in categorias_elegidas and categorias_elegidas[fp]:
            categoria = categorias_elegidas[fp]
            auto = datos_auto(None)  # la eligió el usuario
        else:
            clasif = modelo.clasificar(item["descripcion"])
            categoria = clasif["categoria"] if clasif else "Otros"
            auto = datos_auto(origen_de(clasif.get("fuente")) if clasif else None)
            if categoria == "Otros":
                sin_categoria_clara += 1
            else:
                categorizados_auto += 1

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
            **auto,
        )
        db.add(movimiento)

        if item["tipo"] == "income":
            cuenta.saldo += item["monto"]
        elif item["tipo"] == "expense":
            cuenta.saldo -= item["monto"]

        item["estado"] = "importado"
        importados += 1

        if fp in recordar and categoria and categoria != "Otros":
            r = guardar_regla_aprendida(db, usuario.id, item["descripcion"], categoria)
            if r["guardada"]:
                reglas_guardadas += 1
                if fp in anteriores:
                    anteriores_actualizados += aplicar_a_anteriores(db, usuario.id, r["huella"], categoria)
            else:
                reglas_omitidas.append({"huella": r["huella"], "motivo": r["motivo"], "descripcion": item["descripcion"], "categoria": categoria})

    historial.review_json = json.dumps(review, default=str)
    historial.importados = (historial.importados or 0) + importados
    if all(i["estado"] != "faltante" for i in review):
        historial.estado = "conciliado"

    db.commit()
    return {
        "ok": True, "importados": importados, "sin_categoria_clara": sin_categoria_clara,
        "categorizados_auto": categorizados_auto, "reglas_guardadas": reglas_guardadas,
        "anteriores_actualizados": anteriores_actualizados, "reglas_omitidas": reglas_omitidas,
        "duplicados_omitidos": duplicados_omitidos,
    }


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


FUENTES_RAPIDAS = ("wallet", "apple_pay", "google_pay", "shortcut", "cierre_app", "voz")
DESCRIPCION_POR_DEFECTO = "Movimiento en "  # la pone el registro de cierre de app cuando no hay nota


def es_movimiento_rapido(m: Movimiento) -> bool:
    """Registrado por Wallet / atajo / cierre de app / voz (no por el extracto ni a mano en la app)."""
    return (m.cat_origen in ORIGENES_RAPIDOS) or (m.fuente in FUENTES_RAPIDAS)


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
            "tipo": m.tipo,
            "descripcion": m.descripcion,
            "cuenta_origen": cuenta_id,
            "fingerprint": fp,
            "rapido": es_movimiento_rapido(m),
            "conciliado": m.conciliado_en is not None,
        })
    return ledger


def _completar_con_extracto(db: Session, mov: Movimiento, item: dict, historial_id: str, modelo, usuario_id: str) -> None:
    """Completa un movimiento rápido con los datos reales del banco.

    - La descripción pasa a ser la del banco; si el usuario había escrito una
      propia (nota del Atajo, voz) se conserva en `notas`. La descripción de
      Wallet no cuenta como propia: ya es el comercio.
    - Categoría: si la nota ya la había clasificado, se respeta; si seguía en
      'Otros', se sugiere con el clasificador usando el texto del banco.
    - Queda conciliado (no se vuelve a emparejar) y, si la categoría ya no es
      'Otros', confirmado (sale de la bandeja 'por confirmar').
    El monto y el saldo NO se tocan: si difieren, se informa en la revisión."""
    propia = (mov.descripcion or "").strip()
    es_propia = bool(propia) and not propia.startswith(DESCRIPCION_POR_DEFECTO) and mov.fuente not in ("wallet", "apple_pay", "google_pay")
    if es_propia and normalize_texto(propia) != normalize_texto(item["descripcion"]):
        mov.notas = ((mov.notas + " · ") if mov.notas else "") + f"Nota: {propia}"
    mov.descripcion = item["descripcion"]

    categoria = mov.categoria or "Otros"
    if categoria == "Otros":
        clasif = modelo.clasificar(item["descripcion"])
        if clasif:
            categoria = ajustar_a_categorias_usuario(db, usuario_id, clasif["categoria"])
    mov.categoria = categoria
    if categoria != "Otros":
        mov.cat_confirmada = True
    mov.conciliado_en = ahora_co()
    mov.extracto_id = historial_id
    item["categoria_sugerida"] = categoria
    item["descripcion_registrada"] = propia
    item["monto_registrado"] = mov.monto


def _contar_review(review: list[dict]) -> tuple[int, int]:
    return (
        sum(1 for i in review if i.get("estado") == "completado"),
        sum(1 for i in review if i.get("estado") == "sobrante"),
    )
