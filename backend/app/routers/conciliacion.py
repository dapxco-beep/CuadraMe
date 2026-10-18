import json
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.limites import verificar_limite
from app.limites_diarios import consumir_cupo_diario
from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user
from app.autocat import (
    ClasificadorUsuario, aplicar_a_anteriores, ajustar_a_categorias_usuario, datos_auto,
    guardar_regla_aprendida, origen_de,
)
from app import duplicados as dup
from app import cuadre_extracto
from app import arreglar_tarjetas
from app import reasignar_extracto
from app import estado_traer
from app.extractos_vista import clasificar_motivo
from app import punto_partida, saldo_inicial_auto
from app import titulo as tit
from app.conciliacion import _CUENTA_UNICA
from app.wallet import ORIGENES_RAPIDOS
from app import extractos_error
from app import releer_extracto
from app.extractos_tarjeta_nu import datos_de_lectura, es_extracto_tarjeta_nu, leer_extracto_tarjeta_nu
from app.compartidos import cuenta_accesible, puede_editar_cuenta, reclamar_estado
from app.conciliacion import (
    es_transferencia_propia,
    _cand_extracto,
    auditar_movimientos,
    compute_fingerprint,
    detectar_banco,
    MOTIVO_NO_EXTRACTO,
    evaluar_extracto,
    senales_extracto,
    normalize_texto,
    parse_bank_date,
    fijar_nombre_titular,
    parse_texto_con_regex,
)
from app.contabilidad import CATEGORIA_PAGO_TARJETA, con_marca_traslado, delta_saldo, tipo_con_direccion
from app.cuentas_banco import aviso_cuenta_distinta
from app.database import get_db
from app.extractos_conciliados import evidencia_conciliado
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil
from app.extracto_tarjeta import leer_datos_tarjeta, proponer_actualizacion
from app.config import settings
from app.pdf_extract import ORIGEN_GMAIL, ORIGEN_MANUAL, _decodificar_pdf, extraer_via_ia, pdf_a_texto, pdf_pide_clave
from app.routers.consentimientos import tiene_consentimiento
from app.schemas import (
    HistorialExtractoOut,
    ImportarFaltantesRequest,
    ProcesarExtractoRequest,
    ProcesarExtractoResponse,
    ResolverDudososRequest,
)

# Auto-importar es OPCIONAL y viene APAGADO (perfil.autoimportar_extractos): procesar un
# extracto solo lee y propone; importar es al confirmar la revisión. Con el ajuste activo se
# importan solos los movimientos que el clasificador reconoce con confianza >= umbral
# (por defecto este; cada usuario ajusta el suyo en perfil.confianza_autoimport), y se pueden
# deshacer con POST /conciliacion/historial/{id}/deshacer-auto.
# Solo aplica a movimientos detectados por los parsers regex específicos de
# banco (no al fallback de IA, más propenso a error de lectura del PDF).
CONFIANZA_AUTOIMPORT_DEFAULT = 0.75

router = APIRouter(prefix="/conciliacion", tags=["conciliacion"])


def _tipo_y_notas(item: dict, notas: str) -> tuple[str | None, str]:
    """Todo movimiento importado tiene dirección: (tipo income/expense, notas). Un 'transfer'
    heredado de un extracto guardado antes se resuelve por la descripción; si no se puede,
    tipo None y NO se importa (mejor omitir que mover el saldo en la dirección equivocada).
    Si la contraparte parece el propio titular, las notas llevan la marca de traslado propio."""
    tipo = tipo_con_direccion(item.get("tipo"), item.get("descripcion", ""))
    if tipo and (item.get("pista") or es_transferencia_propia(item.get("descripcion", ""))):
        notas = con_marca_traslado(notas)
    return tipo, notas


def _autoimportar_activo(db: Session, usuario_id: str) -> bool:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    return bool(perfil and perfil.autoimportar_extractos)


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
    """Extracto que el usuario sube a mano desde su dispositivo."""
    return _procesar_extracto(data, db, usuario, ORIGEN_MANUAL)


def procesar_extracto_de_gmail(data: ProcesarExtractoRequest, db: Session, usuario: UsuarioActual):
    """Extracto que llegó por Gmail (no es un endpoint): su contenido nunca va a un proveedor
    de IA salvo la excepción documentada en pdf_extract.modelo_ia_permitido."""
    return _procesar_extracto(data, db, usuario, ORIGEN_GMAIL)


def _procesar_extracto(data: ProcesarExtractoRequest, db: Session, usuario: UsuarioActual, origen: str):
    cuenta = cuenta_accesible(db, usuario.id, data.cuenta_id)
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    # 60 por hora: la subida múltiple procesa hasta 10 archivos de golpe.
    verificar_limite(f"extracto:{usuario.id}", 60, 3600, "Subiste muchos extractos seguidos. Podrás subir más en {espera}.")
    consumir_cupo_diario(db, usuario.id, "extracto")
    texto_plano = pdf_a_texto(data.pdf_base64, data.password)
    banco = detectar_banco(texto_plano) if texto_plano else "desconocido"

    fijar_nombre_titular(usuario.nombre)
    movimientos, descartados = parse_texto_con_regex(texto_plano) if texto_plano else ([], 0)
    via_ia = False
    sin_senales = banco == "generico" and senales_extracto(texto_plano) < 2
    # Banco desconocido y casi sin señales de extracto: no se manda a la IA (inventaría filas
    # de una carta o factura) ni se importa nada.
    if not movimientos and not sin_senales:
        # IA externa SOLO con consentimiento «ia» vigente y según el origen (ver pdf_extract).
        # Sin permiso no se llama a nadie: queda «necesita tu revisión» / «mi banco no está».
        if (not settings.exigir_consentimientos) or tiene_consentimiento(db, usuario.id, "ia"):
            movimientos = extraer_via_ia(
                texto_plano, cuenta.nombre, banco,
                origen=origen, consentimiento_ia=True, nombre_titular=usuario.nombre or "",
            )
            via_ia = bool(movimientos)

    # Extracto de la tarjeta de Nu: el lector comparó lo leído con los totales del propio extracto.
    lectura = None
    if movimientos and not via_ia and texto_plano and es_extracto_tarjeta_nu(texto_plano):
        lectura = datos_de_lectura(leer_extracto_tarjeta_nu(texto_plano))
    lectura_dudosa_total = bool(lectura) and not lectura["lectura_completa"]  # no cuadra: nada se importa solo

    if movimientos:
        parece, motivo = evaluar_extracto(texto_plano, banco, movimientos)
        if not parece:
            return _no_parece_extracto(banco, motivo)

    if not movimientos:
        pide_clave = (not texto_plano) and pdf_pide_clave(data.pdf_base64, data.password)
        # Por qué no se pudo leer: queda guardado para decírselo a la persona en la lista de extractos.
        motivo_codigo = clasificar_motivo(
            texto=texto_plano, pide_clave=pide_clave, clave_dada=bool(data.password),
            pdf_vacio=_decodificar_pdf(data.pdf_base64 or "") is None,  # vacío, roto o no es un PDF
            sin_movimientos=banco not in ("generico", "desconocido") and not sin_senales)
        if sin_senales and texto_plano:
            motivo_codigo = "formato_no_reconocido"
        motivo_codigo = motivo_codigo or "pdf_ilegible"  # un error nunca queda sin motivo
        historial = HistorialExtracto(
            usuario_id=usuario.id,
            cuenta_id=cuenta.id,
            banco_detectado=banco,
            estado="error",
            motivo_error=motivo_codigo,
        )
        db.add(historial)
        db.commit()
        if pide_clave:
            return ProcesarExtractoResponse(
                ok=False, requiere_clave=True, banco_detectado=banco, motivo_error=motivo_codigo,
                error="El PDF tiene clave: escríbela e inténtalo de nuevo." if not data.password
                else "La clave del PDF no es correcta.",
            )
        detalle = (
            f"Texto extraído del PDF ({len(texto_plano)} chars): {texto_plano[:300]}"
            if texto_plano and len(texto_plano) > 10
            else "No se extrajo texto del PDF (posiblemente protegido con otra clave o escaneado como imagen)."
        )
        if sin_senales and texto_plano:
            r = _no_parece_extracto(banco, MOTIVO_NO_EXTRACTO)
            r.motivo_error = motivo_codigo
            return r
        return ProcesarExtractoResponse(
            ok=False,
            error=f"No se pudieron extraer movimientos del PDF. {detalle}",
            banco_detectado=banco,
            motivo_error=motivo_codigo,
        )

    ledger = _cargar_ledger(db, usuario.id, cuenta.id)
    for mov in movimientos:
        # La huella del ledger (_cargar_ledger) usa el id de la cuenta; con el nombre
        # nunca coincidían y los movimientos ya registrados salían como "aproximados".
        mov["cuenta"] = cuenta.id
    resultado = auditar_movimientos(movimientos, ledger, cruzar_rapidos=True,
                                    descartados=_descartados(db, usuario.id, cuenta.id, movimientos))
    # Punto de partida: lo anterior a la fecha de inicio no se ofrece para importar (no se borra
    # ni se pierde: sale en la revisión como «anterior» y se puede traer cambiando la fecha).
    inicio_pp = punto_partida.fecha_inicio(db, usuario.id)
    anteriores = 0
    if inicio_pp:
        for item in resultado["review"]:
            if item["estado"] == "faltante" and punto_partida.es_anterior(parse_bank_date(item["fecha"]), inicio_pp):
                item["estado"] = "anterior"
                anteriores += 1
        resultado["faltantes"] -= anteriores
    # ¿Ese mes de esa cuenta ya estaba conciliado? Se mira ANTES de auto-importar o completar
    # nada (si no, este mismo archivo contaría). Solo avisa: no bloquea ni duplica (hay huella).
    ya_conciliado = _periodo_ya_conciliado(db, usuario.id, cuenta.id, resultado["review"])

    # Auto-importar los "faltantes" con alta confianza del clasificador aprendido,
    # solo cuando vinieron del parser regex de banco (no del fallback de IA).
    auto_importados = 0
    # Solo lo confirmado por el usuario alimenta el aprendizaje.
    modelo = ClasificadorUsuario(db, usuario.id)
    umbral = _umbral_autoimport(db, usuario.id)
    autoimportar = _autoimportar_activo(db, usuario.id)

    for item in resultado["review"]:
        if item["estado"] != "faltante":
            continue
        clasif = modelo.clasificar(item["descripcion"])

        tipo_dir, notas_auto = _tipo_y_notas(item, f"Auto-importado desde extracto {banco} (confianza {clasif['confianza'] if clasif else 0})")
        if autoimportar and not via_ia and clasif and clasif["confianza"] >= umbral and tipo_dir and not item.get("lectura_dudosa") and not item.get("pago_detalle") and not lectura_dudosa_total:
            fecha_dt = parse_bank_date(item["fecha"])
            movimiento = Movimiento(
                usuario_id=usuario.id,
                cuenta_id=cuenta.id,
                descripcion=item["descripcion"],
                titulo=tit.recordado(db, usuario.id, item["descripcion"]),
                categoria=clasif["categoria"],
                tipo=tipo_dir,
                monto=item["monto"],
                fecha=fecha_dt or ahora_co(),
                fuente="conciliacion_auto",
                notas=notas_auto,
                **datos_auto(origen_de(clasif.get("fuente")) or "similar"),
            )
            db.add(movimiento)
            db.flush()  # id del movimiento, para poder deshacer
            dup.nuevo_movimiento(db, movimiento, dup.ORIGEN_EXTRACTO, _huella_linea(db, usuario.id, item))

            cuenta.saldo += item["monto"] if tipo_dir == "income" else -item["monto"]

            item["estado"] = "importado"
            item["auto"] = True
            item["movimiento_id"] = movimiento.id
            item["categoria_sugerida"] = clasif["categoria"]
            item["razon_categoria"] = clasif.get("razon")
            item["confianza_categoria"] = clasif.get("confianza")
            auto_importados += 1
        else:
            # No se auto-importó (confianza baja, viene de IA, o no hubo match):
            # igual se muestra la categoría sugerida en el review para que el
            # usuario la vea y pueda corregirla ANTES de importar manualmente,
            # en vez de que quede oculta y todo termine en "Otros" en silencio.
            item["categoria_sugerida"] = clasif["categoria"] if clasif else "Otros"
            item["razon_categoria"] = clasif.get("razon") if clasif else None
            item["confianza_categoria"] = clasif.get("confianza") if clasif else None
            if item.get("pago_tarjeta") and (item["categoria_sugerida"] == "Otros" or item.get("pago_detalle")):
                # La línea «Pago ...» de un extracto de tarjeta: se sugiere como pago de la tarjeta (traslado
                # entre tus cuentas), no como un gasto «Sin categoría». La persona puede cambiarla.
                item["categoria_sugerida"] = CATEGORIA_PAGO_TARJETA
                item["razon_categoria"] = "parece el pago de tu tarjeta desde otra cuenta tuya"
                item["confianza_categoria"] = 0.6

    if auto_importados:
        resultado["faltantes"] -= auto_importados

    _confirmar_pagos_de_tarjeta(db, usuario.id, cuenta, banco, resultado["review"])

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
        lectura_json=json.dumps(lectura, default=str) if lectura else None,
    )
    saldos_extracto = _saldos_del_extracto(cuenta, texto_plano, movimientos)
    cuadre_extracto.guardar_saldos(historial, saldos_extracto)
    db.add(historial)
    db.flush()  # para tener historial.id y marcarlo en los movimientos completados

    # Completar con el banco los movimientos rápidos emparejados (1:1).
    ids_completar = {i["match_id"] for i in resultado["review"] if i["estado"] in ("completado", "exacto") and i.get("match_id")}
    registrados = (
        {m.id: m for m in db.query(Movimiento).filter(Movimiento.id.in_(ids_completar), Movimiento.usuario_id == usuario.id).all()}
        if ids_completar else {}
    )
    for item in resultado["review"]:
        if item["estado"] == "exacto" and item.get("match_id"):
            # Línea idéntica a algo que ya estaba: también queda cruzada con el banco (si no lo estaba).
            mov = registrados.get(item["match_id"])
            if mov is not None and dup.origen_de_movimiento(mov) != dup.ORIGEN_EXTRACTO:
                item["duplicado_evitado"] = True  # otro canal ya lo había registrado: se junta, no se repite
            if mov is not None and mov.conciliado_en is None and dup.origen_de_movimiento(mov) != dup.ORIGEN_EXTRACTO:
                mov.conciliado_en, mov.extracto_id = ahora_co(), historial.id
                dup.registrar_canal(db, mov, dup.ORIGEN_EXTRACTO, _huella_linea(db, usuario.id, item))
            continue
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
        _completar_con_extracto(db, mov, item, historial.id, modelo, usuario.id, cuenta=cuenta,
                                huella=_huella_linea(db, usuario.id, item))
        item["duplicado_evitado"] = True

    # Registrados que no aparecen en el extracto: se guardan en la revisión.
    for s in resultado.get("sobrantes", []):
        resultado["review"].append({
            "fecha": s["fecha"], "descripcion": s["descripcion"], "monto": s["monto"], "tipo": s["tipo"],
            "referencia": "", "fingerprint": f"sobrante-{s['id']}", "estado": "sobrante", "match_id": s["id"],
        })

    _enriquecer_dudosas(db, usuario.id, resultado["review"])
    historial.review_json = json.dumps(resultado["review"], default=str)
    estado_traer.sincronizar_contadores(historial, resultado["review"])
    db.commit()
    db.refresh(historial)
    dup.absorber_correos(db, usuario.id)  # correos de lo que acaba de entrar (o conciliarse) ya no salen por revisar
    completados, sobrantes = _contar_review(resultado["review"])

    return ProcesarExtractoResponse(
        **(lectura or {}),
        autoimportar_activo=autoimportar,
        ya_registrados=resultado["exactos"] + resultado["aproximados"] + completados + resultado.get("borrados_antes", 0),
        borrados_antes=resultado.get("borrados_antes", 0),
        propuesta_tarjeta=_propuesta_tarjeta(cuenta, texto_plano),
        saldos_extracto=saldos_extracto,
        aviso_cuenta=aviso_cuenta_distinta(cuenta, texto_plano[:6000], db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()),
        ok=True,
        historial_id=historial.id,
        banco_detectado=banco,
        total_movimientos=resultado["total_movimientos"],
        exactos=resultado["exactos"],
        aproximados=resultado["aproximados"],
        faltantes=resultado["faltantes"],
        descartados=descartados,
        anteriores=anteriores,
        review=resultado["review"],
        auto_importados=auto_importados,
        completados=completados,
        sobrantes=sobrantes,
        ya_conciliado=ya_conciliado,
        conteo=estado_traer.contar_review(resultado["review"]),
        **_periodo(resultado["review"]),
    )


def _confirmar_pagos_de_tarjeta(db: Session, usuario_id: str, cuenta, banco: str, review: list[dict]) -> None:
    """El pago de la tarjeta (la fila «Pago $A …» del extracto) solo viene marcado si hay certeza: hay una salida de
    ≈A (±$1) en otra cuenta del mismo banco (ahorros, no crédito) con fecha a ±3 días. Si no, queda apagado con el
    aviso «Parece el pago de tu tarjeta. Confirma el monto.»."""
    pagos = [i for i in review if i.get("pago_detalle") and i.get("estado") == "faltante"]
    if not pagos:
        return
    propias = [c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id, Cuenta.id != cuenta.id).all()
               if c.tipo != "credito" and (banco or "") in normalize_texto(c.nombre).split()]
    for item in pagos:
        item["marcar_por_defecto"] = False
        fecha = parse_bank_date(item["fecha"])
        if not propias or not fecha:
            continue
        salida = (
            db.query(Movimiento.id)
            .filter(Movimiento.usuario_id == usuario_id, Movimiento.cuenta_id.in_([c.id for c in propias]),
                    Movimiento.tipo == "expense", Movimiento.monto.between(item["monto"] - 1, item["monto"] + 1),
                    Movimiento.fecha >= fecha - timedelta(days=3), Movimiento.fecha < fecha + timedelta(days=4))
            .first()
        )
        if salida:
            item["marcar_por_defecto"] = True
            item["aviso_linea"] = None


def _huella_linea(db: Session, usuario_id: str, item: dict) -> str:
    """Huella de una línea del extracto: su fingerprint + un ordinal (dos líneas idénticas el mismo día
    son dos movimientos distintos). Cuenta también las que el usuario ya borró."""
    fp = item.get("fingerprint") or ""
    return dup.huella_extracto(fp, dup.siguiente_ordinal(db, usuario_id, f"ext:{fp}"))


def _absorbidas_por_otro_canal(db: Session, usuario_id: str, cuenta, items: list[dict]) -> dict:
    """{id(item): Movimiento existente | None (None = lo borraste antes)} de las líneas que otro canal
    ya registró. Emparejamiento 1:1 con la regla central, solo contra lo que aún no está conciliado."""
    if not items:
        return {}
    entrantes = []
    for n, it in enumerate(items):
        c = _cand_extracto(n, it)
        c.cuentas = frozenset({cuenta.id})
        entrantes.append(c)
    fechas = [c.fecha for c in entrantes]
    desde, hasta = min(fechas) - timedelta(days=4), max(fechas) + timedelta(days=5)
    existentes = [e for e in dup.existentes_para(db, usuario_id, {cuenta.id}, desde, hasta, fantasmas=True)
                  if e.fantasma or e.ref.conciliado_en is None]
    existentes.sort(key=lambda e: e.fecha)
    salida = {}
    for i, j, _p in dup.emparejar(entrantes, existentes):
        salida[id(items[i])] = None if existentes[j].fantasma else existentes[j].ref
    return salida


def _descartados(db: Session, usuario_id: str, cuenta_id: str, movimientos: list[dict]) -> dict:
    """Lo que el usuario borró de esta cuenta (por huella de línea y por la foto del movimiento):
    una línea del extracto que coincide con eso NO resucita el movimiento."""
    fechas = [d for d in (parse_bank_date(m.get("fecha")) for m in movimientos) if d]
    fantasmas = []
    if fechas:
        fantasmas = [f for f in dup.fantasmas_de(db, usuario_id, {cuenta_id}, min(fechas) - timedelta(days=4),
                                                 max(fechas) + timedelta(days=5))
                     if dup.ORIGEN_EXTRACTO not in f.canales]
        for f in fantasmas:
            f.cuentas = _CUENTA_UNICA
    return {"fingerprints": dup.huellas_extracto_descartadas(db, usuario_id, cuenta_id), "fantasmas": fantasmas}


def _no_parece_extracto(banco: str, motivo: str) -> ProcesarExtractoResponse:
    """Rechazo claro (sin importar nada): el cliente lo muestra como error de ESE archivo."""
    return ProcesarExtractoResponse(
        ok=False, parece_extracto=False, motivo_rechazo=motivo, banco_detectado=banco,
        error=f"{motivo} Sube el PDF que descargas de tu banco con los movimientos del mes.",
    )


def _periodo_ya_conciliado(db: Session, usuario_id: str, cuenta_id: str, review: list[dict]) -> dict | None:
    fechas = [d for d in (parse_bank_date(i.get("fecha")) for i in review if i.get("estado") != "sobrante") if d]
    if not fechas:
        return None
    ultimo = max(fechas)  # el mes del corte, igual que en los extractos de Gmail
    mes = f"{ultimo.year:04d}-{ultimo.month:02d}"
    ev = evidencia_conciliado(db, usuario_id, cuenta_id, mes)
    return {"mes": mes, "cruzados": ev["cruzados"]} if ev else None


def _saldos_del_extracto(cuenta, texto: str, movimientos: list[dict]) -> dict | None:
    """Saldos que imprime el extracto (para cuadrar), o None si no trae ninguno legible. Nunca rompe el proceso."""
    try:
        credito = cuenta.tipo == "credito"
        saldos = cuadre_extracto.leer_saldos_extracto(texto or "", es_credito=credito,
                                                      datos_tarjeta=leer_datos_tarjeta(texto) if credito else None)
        if saldos:
            saldos["cadena_ok"] = cuadre_extracto.cadena_coincide(saldos, movimientos)
            if not saldos.get("periodo_inicio") or not saldos.get("fecha_corte"):
                fechas = [d for d in (parse_bank_date(m.get("fecha")) for m in movimientos) if d]
                if fechas:
                    saldos.setdefault("periodo_inicio", min(fechas).date().isoformat())
                    saldos.setdefault("fecha_corte", max(fechas).date().isoformat())
        return saldos
    except Exception:  # noqa: BLE001 - leer saldos es un extra: si falla, el extracto se procesa como siempre
        return None


def _propuesta_tarjeta(cuenta, texto: str) -> dict | None:
    """Si la cuenta es una tarjeta de crédito, lee cupo, pago, fechas y tasa del extracto y
    PROPONE actualizar la tarjeta (nunca la modifica). Cualquier fallo se ignora: leer el
    extracto de más no puede romper la conciliación."""
    if cuenta.tipo != "credito" or not texto:
        return None
    try:
        return proponer_actualizacion(cuenta, leer_datos_tarjeta(texto))
    except Exception:
        return None


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
    _enriquecer_dudosas(db, usuario.id, review)
    completados, sobrantes = _contar_review(review)
    return ProcesarExtractoResponse(
        **(historial.lectura or {}),
        ok=True,
        conteo=estado_traer.conteo_de_historial(historial),
        historial_id=historial.id,
        cuenta_id=historial.cuenta_id,
        banco_detectado=historial.banco_detectado,
        total_movimientos=historial.total_movimientos,
        exactos=historial.exactos,
        aproximados=historial.aproximados,
        faltantes=historial.faltantes,
        descartados=historial.descartados or 0,
        saldos_extracto=cuadre_extracto.saldos_de_historial(historial),
        origen=estado_traer.origen_de_historial(db, usuario.id, historial),
        review=review,
        completados=completados,
        sobrantes=sobrantes,
        auto_importados=sum(1 for i in review if i.get("auto") and i.get("estado") == "importado"),
        ya_registrados=historial.exactos + historial.aproximados + completados
        + sum(1 for i in review if i.get("estado") == "borrado_antes"),
        borrados_antes=sum(1 for i in review if i.get("estado") == "borrado_antes"),
        **_periodo(review),
    )


@router.post("/historial/{historial_id}/deshacer-auto")
def deshacer_auto_importados(
    historial_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Deshace lo que se importó solo al procesar este extracto (ajuste 'importar lo que
    reconozco'): borra esos movimientos y revierte el saldo. Los que el usuario ya confirmó o
    editó se respetan y quedan registrados. Lo borrado vuelve a la revisión como 'faltante'."""
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
    deshechos = conservados = 0
    for item in review:
        if not (item.get("auto") and item.get("estado") == "importado" and item.get("movimiento_id")):
            continue
        mov = (
            db.query(Movimiento)
            .filter(Movimiento.id == item["movimiento_id"], Movimiento.usuario_id == usuario.id,
                    Movimiento.cuenta_id == cuenta.id, Movimiento.fuente == "conciliacion_auto")
            .first()
        )
        if mov is None:
            item["estado"] = "faltante"  # ya no existe (lo borró el usuario)
        elif mov.cat_confirmada:
            conservados += 1  # el usuario ya lo revisó: se queda
            item["auto"] = False
            continue
        else:
            if mov.tipo == "income":
                cuenta.saldo -= mov.monto
            elif mov.tipo == "expense":
                cuenta.saldo += mov.monto
            dup.olvidar_movimiento(db, mov)  # deshacer NO cuenta como borrado del usuario: la línea puede volver
            db.delete(mov)
            item["estado"] = "faltante"
            deshechos += 1
        item["auto"] = False
        item.pop("movimiento_id", None)

    historial.review_json = json.dumps(review, default=str)
    historial.importados = max(0, (historial.importados or 0) - deshechos)
    historial.faltantes = (historial.faltantes or 0) + deshechos
    if deshechos:
        historial.estado = "pendiente_revision"
    db.commit()
    return {"ok": True, "deshechos": deshechos, "conservados": conservados}


def _resultado_ya_importado(historial: HistorialExtracto) -> dict:
    """Respuesta de una importación que ya se hizo: mismo formato, sin crear nada (`ya_importado`)."""
    return {
        "ok": True, "importados": 0, "sin_categoria_clara": 0, "categorizados_auto": 0, "reglas_guardadas": 0,
        "anteriores_actualizados": 0, "reglas_omitidas": [], "duplicados_omitidos": 0, "sin_direccion": 0,
        "anteriores_omitidas": 0, "ya_importado": True, "importados_total": historial.importados or 0,
    }


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

    # Idempotencia: pendiente_revision -> importando es atómico (reclamar_estado). Si otra petición
    # igual (reintento de la cola offline, doble toque) ya lo tomó o lo terminó, esta NO crea nada:
    # espera su commit, relee la revisión ya calculada y responde con ese resultado.
    estado_previo = historial.estado
    if estado_previo == "importando" or not reclamar_estado(db, HistorialExtracto, historial.id, estado_previo, "importando"):
        db.rollback()
        db.refresh(historial)
        return _resultado_ya_importado(historial)
    db.refresh(historial)  # la revisión que dejó la petición anterior (si la hubo), no la que se leyó antes del candado
    review = json.loads(historial.review_json or "[]")
    fingerprints = set(data.fingerprints)
    if not any(i.get("fingerprint") in fingerprints and i.get("estado") == "faltante" for i in review):
        historial.estado = estado_previo  # nada por importar (ya se hizo): se suelta el candado sin tocar nada
        db.commit()
        return _resultado_ya_importado(historial)
    importados = 0

    modelo = ClasificadorUsuario(db, usuario.id)

    categorias_elegidas = data.categorias or {}
    sin_categoria_clara = 0
    categorizados_auto = 0
    recordar, anteriores = set(data.recordar), set(data.aplicar_anteriores)
    titulos_elegidos = data.titulos or {}
    montos_elegidos = data.montos or {}
    dudosas_omitidas = 0
    recordar_titulo = set(data.recordar_titulo)
    reglas_guardadas = anteriores_actualizados = 0
    reglas_omitidas: list[dict] = []
    # Varios extractos con periodos que se solapan comparten movimientos: si otro archivo (o
    # el usuario) ya los registró, aquí no se duplican.
    # Se CUENTAN las huellas (no basta con saber si existen): dos movimientos idénticos el
    # mismo día (dos envíos de $20.000 a la misma persona) son DOS, no un duplicado. De lo
    # registrado con una huella solo sobra para "duplicado" lo que este mismo extracto aún
    # no explica (sus líneas ya exactas o importadas).
    # Lo que ESTE extracto ya cruzó (movimientos completados con su texto del banco) tampoco cuenta como
    # «ya registrado» de otra línea idéntica: dos cafés iguales del banco con uno solo registrado son dos.
    completados_aqui = {i.get("match_id") for i in review if i.get("estado") == "completado"}
    en_libro = Counter(r["fingerprint"] for r in _cargar_ledger(db, usuario.id, cuenta.id)
                       if r["id"] not in completados_aqui)
    explicados = Counter(i.get("fingerprint") for i in review if i.get("estado") in ("exacto", "importado"))
    ya_registrados = {fp: n - explicados[fp] for fp, n in en_libro.items() if n > explicados[fp]}
    duplicados_omitidos = 0
    sin_direccion = 0
    anteriores_omitidas = 0
    inicio_pp_imp = punto_partida.fecha_inicio(db, usuario.id)

    # Regla central: entre calcular la revisión y confirmarla, el atajo, el correo o la app pudieron
    # registrar alguna de estas líneas. Esas se CONCILIAN con lo que ya existe; solo se insertan las
    # líneas sin pareja (y las que borraste antes no resucitan).
    absorbidas = _absorbidas_por_otro_canal(
        db, usuario.id, cuenta, [i for i in review if i.get("fingerprint") in fingerprints and i.get("estado") == "faltante"])

    for item in review:
        fp = item.get("fingerprint")
        if fp not in fingerprints or item.get("estado") != "faltante":
            continue
        # Línea con varios montos: sin el monto que la persona eligió NO se importa (no se adivina).
        if item.get("lectura_dudosa"):
            elegido = montos_elegidos.get(fp)
            if elegido is None or not (elegido >= 1):
                dudosas_omitidas += 1
                continue
            item["monto_leido"] = item["monto"]
            item["monto"] = round(float(elegido), 2)
            item["lectura_dudosa"] = False
        # Nombre propio elegido en la revisión (el texto del banco, `descripcion`, no se toca).
        if fp in titulos_elegidos:
            nombre = tit.limpiar(titulos_elegidos[fp])
            if nombre:
                item["titulo"] = nombre
            else:
                item.pop("titulo", None)
        if punto_partida.es_anterior(parse_bank_date(item.get("fecha")), inicio_pp_imp):
            anteriores_omitidas += 1  # el inicio se movió después de procesar el extracto
            continue
        tipo_dir, notas_mov = _tipo_y_notas(item, f"Importado desde extracto {historial.banco_detectado}")
        if not tipo_dir:
            sin_direccion += 1  # 'transfer' viejo sin dirección deducible: se omite, no se adivina
            continue
        if id(item) in absorbidas:
            existente = absorbidas[id(item)]
            if existente is None:
                item["estado"] = "borrado_antes"
            else:
                _completar_con_extracto(db, existente, item, historial.id, modelo, usuario.id, cuenta=cuenta,
                                        huella=_huella_linea(db, usuario.id, item))
                item["estado"] = "completado"
            item["duplicado_evitado"] = True
            duplicados_omitidos += 1
            continue
        if ya_registrados.get(fp, 0) > 0:
            ya_registrados[fp] -= 1
            item["estado"] = "exacto"
            item["duplicado_evitado"] = True
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
            titulo=tit.limpiar(item.get("titulo")) or tit.recordado(db, usuario.id, item["descripcion"]),
            categoria=categoria,
            tipo=tipo_dir,
            monto=item["monto"],
            fecha=parse_bank_date(item["fecha"]) or historial.creado_en,
            fuente="conciliacion_extracto",
            notas=notas_mov,
            **auto,
        )
        db.add(movimiento)
        dup.nuevo_movimiento(db, movimiento, dup.ORIGEN_EXTRACTO, _huella_linea(db, usuario.id, item))

        cuenta.saldo += item["monto"] if tipo_dir == "income" else -item["monto"]

        item["estado"] = "importado"
        item["movimiento_id"] = movimiento.id  # vínculo directo extracto->movimiento (reasignar_extracto lo usa)
        importados += 1

        if fp in recordar_titulo and item.get("titulo"):
            tit.guardar_regla(db, usuario.id, item["descripcion"], item["titulo"])
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
    historial.estado = "conciliado" if all(i["estado"] != "faltante" for i in review) else estado_previo
    estado_traer.sincronizar_contadores(historial, review)  # los contadores del historial ya no se quedan viejos
    if not any(i.get("estado") in ("faltante", "dudoso") for i in review):
        cuadre_extracto.registrar_cuadre(db, cuenta, historial)  # recuerda si este mes cuadra (para avisar si deja de cuadrar)

    db.commit()
    dup.absorber_correos(db, usuario.id)
    saldo_inicial = None
    try:  # con el primer extracto conciliado se sabe con cuánto empezó la cuenta; si algo falla, no estorba la importación
        if cuenta.usuario_id == usuario.id:
            saldo_inicial = saldo_inicial_auto.registrar(db, cuenta, punto_partida.fecha_inicio(db, usuario.id))
    except Exception:  # noqa: BLE001
        db.rollback()
    return {
        "saldo_inicial_auto": saldo_inicial,
        "ok": True, "importados": importados, "sin_categoria_clara": sin_categoria_clara,
        "categorizados_auto": categorizados_auto, "reglas_guardadas": reglas_guardadas,
        "anteriores_actualizados": anteriores_actualizados, "reglas_omitidas": reglas_omitidas,
        "duplicados_omitidos": duplicados_omitidos, "sin_direccion": sin_direccion,
        "anteriores_omitidas": anteriores_omitidas, "dudosas_omitidas": dudosas_omitidas,
    }


def _enriquecer_dudosas(db: Session, usuario_id: str, review: list[dict]) -> None:
    """A cada línea «aproximada» (parece algo que ya tienes, pero no es idéntica) le pega lo que hay
    registrado, para poder mostrar las dos filas lado a lado: «¿es el mismo gasto?»."""
    ids = {i["match_id"] for i in review if i.get("estado") == "aproximado" and i.get("match_id")}
    if not ids:
        return
    movs = {m.id: m for m in db.query(Movimiento).filter(Movimiento.id.in_(ids), Movimiento.usuario_id == usuario_id).all()}
    for i in review:
        m = movs.get(i.get("match_id")) if i.get("estado") == "aproximado" else None
        if m is not None:
            i["descripcion_registrada"] = m.descripcion
            i["monto_registrado"] = m.monto
            i["fecha_registrada"] = m.fecha.strftime("%Y-%m-%d") if m.fecha else None


@router.post("/historial/{historial_id}/resolver-dudosos")
def resolver_dudosos(
    historial_id: str,
    data: ResolverDudososRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """La persona decide lo que la app no pudo: «Sí, es el mismo» junta la línea con el movimiento que ya
    tenías (queda revisado con el banco, no se duplica); «No, es otro» la deja como faltante para agregarla.
    Se puede confirmar en bloque (varias huellas a la vez). Idempotente."""
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
    mismos, distintos = set(data.mismos), set(data.distintos)
    modelo = ClasificadorUsuario(db, usuario.id)
    juntados = separados = 0
    for item in review:
        if item.get("estado") != "aproximado":
            continue
        fp = item.get("fingerprint")
        if fp in mismos:
            mov = db.query(Movimiento).filter(Movimiento.id == item.get("match_id"), Movimiento.usuario_id == usuario.id).first()
            if mov is None:
                item["estado"] = "faltante"  # ya no existe: pasa a ser una línea por agregar
                item.pop("match_id", None)
                separados += 1
                continue
            if mov.conciliado_en is None:
                _completar_con_extracto(db, mov, item, historial.id, modelo, usuario.id, cuenta=cuenta,
                                        huella=_huella_linea(db, usuario.id, item))
            item["estado"] = "completado"
            item["duplicado_evitado"] = True
            juntados += 1
        elif fp in distintos:
            item["estado"] = "faltante"
            item["categoria_sugerida"] = item.get("categoria_sugerida") or "Otros"
            item.pop("match_id", None)
            separados += 1
    historial.review_json = json.dumps(review, default=str)
    if separados:
        historial.estado = "pendiente_revision"
    estado_traer.sincronizar_contadores(historial, review)
    db.commit()
    dup.absorber_correos(db, usuario.id)
    return {"ok": True, "juntados": juntados, "separados": separados, "conteo": estado_traer.contar_review(review)}


class CambiarCuentaIn(BaseModel):
    cuenta_id: str
    confirmar: bool = False


@router.get("/historial/{historial_id}/cambiar-cuenta/previa")
def cambiar_cuenta_previa(
    historial_id: str, cuenta_id: str,
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user),
):
    """Vista previa SIN cambios: cuántos movimientos pasarían y cómo quedarían los saldos de ambas cuentas."""
    return reasignar_extracto.previa(db, usuario.id, historial_id, cuenta_id)


@router.post("/historial/{historial_id}/cambiar-cuenta")
def cambiar_cuenta(
    historial_id: str, data: CambiarCuentaIn,
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user),
):
    """Pasa el extracto (y lo que importó) a otra cuenta y recalcula los saldos de las dos. Pide confirmar."""
    if not data.confirmar:
        raise HTTPException(status_code=400, detail="Confirma el cambio para continuar.")
    return reasignar_extracto.cambiar(db, usuario.id, historial_id, data.cuenta_id)


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
    # El extracto de Gmail que apuntaba a esta revisión vuelve a «nuevo»: sin esto quedaba «procesado»
    # para siempre sin revisión que lo respalde.
    for ec in db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario.id,
                                              ExtractoCorreo.historial_id == historial.id).all():
        ec.estado, ec.historial_id = "nuevo", None
    db.delete(historial)
    db.commit()
    return {"ok": True}


def _historial_en_error(db: Session, usuario: UsuarioActual, historial_id: str) -> HistorialExtracto:
    h = (
        db.query(HistorialExtracto)
        .filter(HistorialExtracto.id == historial_id, HistorialExtracto.usuario_id == usuario.id)
        .first()
    )
    if not h:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    if h.estado != "error":
        raise HTTPException(status_code=409, detail="Este extracto no está en error")
    return h


@router.delete("/historial/{historial_id}/error")
def quitar_extracto_en_error(
    historial_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Quitar de la lista»: borra SOLO un extracto en error del propio usuario (nunca uno conciliado ni
    pendiente de revisión: esos tienen movimientos detrás). Si venía de un correo, ese correo vuelve a
    «nuevo» para poder revisarlo otra vez."""
    h = _historial_en_error(db, usuario, historial_id)
    for ec in db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario.id,
                                              ExtractoCorreo.historial_id == h.id).all():
        ec.estado, ec.historial_id = "nuevo", None
    db.delete(h)
    db.commit()
    return {"ok": True}


@router.post("/historial/{historial_id}/reintentar")
def reintentar_extracto_en_error(
    historial_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Reintentar» un extracto en error que vino de un correo: se vuelve a traer el adjunto y, si ahora se
    lee, el extracto procesado REEMPLAZA a la fila de error. Los subidos a mano no se pueden reintentar."""
    h = _historial_en_error(db, usuario, historial_id)
    verificar_limite(f"reintentar-error:{usuario.id}", 30, 3600, "Reintentaste muchos extractos seguidos. Podrás seguir en {espera}.")
    return extractos_error.reintentar_historial(db, usuario, h)


@router.post("/historial/{historial_id}/releer")
def releer_extracto_guardado(
    historial_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«Releer este extracto»: vuelve a traer el adjunto del correo y lo lee con el lector de hoy, sin duplicar
    ni deshacer lo importado (ver app/releer_extracto.py). Los subidos a mano no se pueden releer (409)."""
    h = (
        db.query(HistorialExtracto)
        .filter(HistorialExtracto.id == historial_id, HistorialExtracto.usuario_id == usuario.id)
        .first()
    )
    if not h:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    if h.estado != "error" and releer_extracto.correo_de(db, h) is None:
        raise HTTPException(status_code=409, detail=releer_extracto.MSG_MANUAL)
    verificar_limite(f"releer-extracto:{historial_id}", 1, 60, "Acabas de releer este extracto. Podrás hacerlo otra vez en {espera}.")
    verificar_limite(f"releer-extracto-usuario:{usuario.id}", 6, 3600, "Releíste muchos extractos seguidos. Podrás seguir en {espera}.")
    try:
        return releer_extracto.releer_historial(db, usuario, h)
    except releer_extracto.ReleerError as e:
        raise HTTPException(status_code=e.estado, detail=e.mensaje)


class ArreglarTarjetasIn(BaseModel):
    confirmar: bool = False
    maximo: int = 12  # la app arregla de a uno para mostrar el avance («3 de 6»)
    excluir: list[str] = []  # historiales que esta tanda ya intentó
    continuar: bool = False  # sigue una tanda ya iniciada: no cuenta como llamada nueva frente al límite por hora


@router.get("/tarjetas/arreglar/previa")
def arreglar_tarjetas_previa(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user),
):
    """«Arreglar mis extractos de la tarjeta», vista previa SIN cambios ni Gmail: qué extractos, a qué cuenta pasan,
    cuántos movimientos se mueven y cómo quedan los saldos."""
    return arreglar_tarjetas.previa(db, usuario)


@router.post("/tarjetas/arreglar")
def arreglar_tarjetas_ahora(
    data: ArreglarTarjetasIn,
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user),
):
    """Mueve los extractos de tarjeta a su tarjeta y los relee con el lector de hoy, en un solo paso (máx. 12 por
    llamada, del más viejo al más nuevo). Pide confirmar. La llamada cuenta como UNA relectura por hora."""
    if not data.confirmar:
        raise HTTPException(status_code=400, detail="Confirma el arreglo para continuar.")
    if data.continuar:  # los pasos de una tanda ya iniciada tienen su propio tope (cada uno relee como mucho 1 PDF)
        verificar_limite(f"arreglar-tarjetas-sigue:{usuario.id}", 40, 3600, "Arreglaste tus extractos muchas veces seguidas. Podrás seguir en {espera}.")
    else:
        verificar_limite(f"arreglar-tarjetas:{usuario.id}", 6, 3600, "Arreglaste tus extractos muchas veces seguidas. Podrás seguir en {espera}.")
    return arreglar_tarjetas.arreglar(db, usuario, maximo=data.maximo, excluir=data.excluir[:50])


@router.post("/releer-pendientes")
def releer_pendientes_al_abrir(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Al abrir «Traer movimientos»: relee una vez (por versión del lector) los extractos por revisar que
    vinieron de un correo y los conciliados de tarjeta ya en su cuenta de crédito, en modo «solo agregar»
    (máx. 3 en total). Nunca falla."""
    return releer_extracto.releer_pendientes(db, usuario)


@router.post("/reintentar-errores")
def reintentar_errores(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Al abrir «Traer movimientos»: completa los motivos que faltan y reintenta (en lote pequeño) los errores
    por clave que tienen correo. Nunca falla: si Gmail no responde, todo queda como estaba."""
    return extractos_error.reintentar_errores_clave(db, usuario)


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
    canales = dup.canales_de(db, usuario_id, [m.id for m in movimientos])
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
            "extracto_id": m.extracto_id,
            # Canal de origen y canales que ya lo confirmaron (regla central, app/duplicados.py).
            # Lo que no es una compra de un canal (traslados, aportes a metas) no se empareja.
            "origen": dup.origen_de_movimiento(m),
            "canales": canales.get(m.id, set()),
            "flexible": "Original:" in (m.notas or ""),
            "emparejable": dup.es_emparejable(m),
        })
    return ledger


def _completar_con_extracto(db: Session, mov: Movimiento, item: dict, historial_id: str, modelo, usuario_id: str,
                            cuenta: Cuenta | None = None, huella: str | None = None) -> None:
    """Concilia con el banco un movimiento que YA existía (atajo, correo, a mano...). No inserta nada.

    - Movimiento rápido (atajo/voz/cierre de app): la descripción pasa a ser la del banco; si el
      usuario había escrito una propia se conserva en `notas`. La descripción de Wallet no cuenta
      como propia: ya es el comercio. Si seguía en 'Otros' se sugiere categoría con el texto del
      banco y, si ya no es 'Otros', queda confirmado (sale de «por confirmar»).
    - Correo o a mano: la descripción y la categoría que ya tenía NO se tocan (el banco suele escribir
      un texto críptico); solo se concilia.
    - Fecha: si la que había era aproximada (a mano, sin hora) se corrige con la del banco. Una hora
      real (atajo/correo) se respeta.
    - Monto: si difiere solo por redondeo (≤ $1) se corrige al exacto del banco y el saldo de la
      cuenta se ajusta por esa diferencia. Una diferencia mayor (propina, conversión de moneda) NO
      se toca: se informa en la revisión.
    - Queda conciliado (no se vuelve a emparejar) y anota 'extracto' como canal que lo confirmó."""
    propia = (mov.descripcion or "").strip()
    monto_antes = mov.monto
    if es_movimiento_rapido(mov):
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
    else:
        categoria = mov.categoria or "Otros"

    nombre = tit.limpiar(item.get("titulo"))
    if nombre:  # la persona le puso nombre a esta línea en la revisión: pasa al movimiento que ya existía
        mov.titulo = nombre

    fecha_banco = parse_bank_date(item.get("fecha"))
    if fecha_banco and mov.fecha and fecha_banco.date() != mov.fecha.date():
        sin_hora = (mov.fecha.hour, mov.fecha.minute, mov.fecha.second) == (0, 0, 0)
        if sin_hora or dup.origen_de_movimiento(mov) in (dup.ORIGEN_MANUAL, dup.ORIGEN_IMPORTACION):
            mov.fecha = fecha_banco.replace(hour=mov.fecha.hour, minute=mov.fecha.minute, second=mov.fecha.second)
    dif = float(item.get("monto") or 0) - float(mov.monto or 0)
    moneda = ((cuenta.moneda if cuenta is not None else None) or "COP").upper()
    if dif and abs(dif) <= (dup.TOLERANCIA_REDONDEO_COP if moneda == "COP" else dup.TOLERANCIA_REDONDEO_OTRA):
        antes = delta_saldo(mov)
        mov.monto = float(item["monto"])
        if cuenta is not None:
            cuenta.saldo += delta_saldo(mov) - antes

    mov.conciliado_en = ahora_co()
    mov.extracto_id = historial_id
    dup.registrar_canal(db, mov, dup.ORIGEN_EXTRACTO, huella)
    item["categoria_sugerida"] = categoria
    item["descripcion_registrada"] = propia
    item["monto_registrado"] = monto_antes


def _contar_review(review: list[dict]) -> tuple[int, int]:
    return (
        sum(1 for i in review if i.get("estado") == "completado"),
        sum(1 for i in review if i.get("estado") == "sobrante"),
    )
