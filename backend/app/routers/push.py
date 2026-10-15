import calendar
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import presupuesto_servicio as srv
from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.compartidos import bloquear_cuenta, cuentas_ids_accesibles
from app.contabilidad import (
    CATEGORIA_APORTE_META,
    FUENTE_APORTE_META,
    gastos_por_categoria,
    moneda_base_de,
    tipos_cuenta_de,
    tipos_efectivos,
)
from app.config import settings
from app.crons import Corrida, liberar_marca, reclamar_marca
from app.database import get_db
from app.finanzas import _dia_valido_del_mes, calc_estado_recurrente
from app.fx import convertir_a_cop
from app.models import Cuenta, Meta, Movimiento, Perfil, Presupuesto, PushSubscription, Recurrente
from app.push import enviar_push
from app.rachas import otorgar_vida_si_nueva
from app.tarjetas import extractos_guardados, movimientos_tras_corte, tarjetas_por_avisar
from app.utiles import ahora_co
from app.schemas import PushSubscribeRequest, VapidPublicKeyResponse

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
def vapid_public_key():
    return VapidPublicKeyResponse(public_key=settings.vapid_public_key)


@router.post("/suscribir")
def suscribir(
    data: PushSubscribeRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    # Un mismo endpoint (dispositivo/navegador) reasignándose de usuario es
    # esperado cuando alguien cierra sesión y otra persona entra en el mismo
    # dispositivo — el navegador reusa el endpoint. Se permite la reasignación,
    # pero se actualizan también las claves de cifrado (p256dh/auth) para que
    # quede consistente con el nuevo dueño.
    existente = db.query(PushSubscription).filter(PushSubscription.endpoint == data.endpoint).first()
    if existente:
        existente.usuario_id = usuario.id
        existente.p256dh = data.p256dh
        existente.auth = data.auth
    else:
        db.add(
            PushSubscription(
                usuario_id=usuario.id,
                endpoint=data.endpoint,
                p256dh=data.p256dh,
                auth=data.auth,
            )
        )
    db.commit()
    return {"ok": True}


@router.post("/desuscribir")
def desuscribir(
    endpoint: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == endpoint, PushSubscription.usuario_id == usuario.id
    ).delete()
    db.commit()
    return {"ok": True}


@router.post("/probar")
def probar_push(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    enviados = enviar_push(
        db, usuario.id, "CuadraMe", "Así se ven tus notificaciones 🎉", "/perfil"
    )
    return {"ok": True, "enviados": enviados}


@router.post("/cron/revisar-presupuestos")
def cron_revisar_presupuestos(
    db: Session = Depends(get_db), x_cron_secret: str = Header(default="")
):
    """Pensado para ser llamado periódicamente por un cron externo (Railway
    no tiene cron gratis nativo simple; usar cron-job.org o similar apuntando
    aquí con el header X-Cron-Secret). Revisa, para cada usuario con Gmail o
    push activo, si algún presupuesto superó el 90% y avisa una sola vez."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    usuarios_con_push = {
        s[0] for s in db.query(PushSubscription.usuario_id).distinct().all()
    }
    resultado = {"notificados": 0}
    ahora = ahora_co()

    corrida = Corrida(db)
    for usuario_id in usuarios_con_push:
        with corrida.aislar(usuario_id):
            _revisar_presupuestos_de(db, usuario_id, ahora, resultado)

    return {"ok": True, "notificados": resultado["notificados"], **corrida.resumen()}


def _revisar_presupuestos_de(db: Session, usuario_id: str, ahora, resultado: dict) -> None:
    """Trabajo de UN usuario del cron de presupuestos (aislado por quien lo llama)."""
    presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.usuario_id == usuario_id, Presupuesto.activo == True)  # noqa: E712
        .all()
    )
    cfg = srv.obtener_config(db, usuario_id)
    gastos = srv.GastosPorRango(db, usuario_id)
    for p in presupuestos:
        if p.limite <= 0:
            continue
        # Cada presupuesto se evalúa en SU periodo (mensual, quincenal, semanal).
        proy = srv.proyectar_presupuesto(p, cfg, gastos, ahora)
        clave = proy["clave_periodo"]
        if proy["limite"] <= 0:
            continue

        # 1) Umbral ya usado. Una sola alerta por presupuesto y por periodo:
        #    sin esta marca, el aviso se repetiría cada día sobre el umbral.
        if p.ultima_alerta_mes != clave and proy["pct_usado"] >= p.alerta_pct:
            enviar_push(
                db,
                usuario_id,
                f"Presupuesto de {p.categoria}",
                f"Ya usaste el {round(proy['pct_usado'])}% — quedan "
                f"{max(0, proy['limite'] - proy['gastado']):,.0f} COP",
                "/presupuesto",
            )
            p.ultima_alerta_mes = clave
            db.commit()
            resultado["notificados"] += 1
            continue

        # 2) Alerta PREDICTIVA: aún no llegas al umbral, pero al ritmo actual te
        #    pasarías. Una vez por periodo y sin avisar en los primeros 3 días
        #    (con tan pocos datos el ritmo engaña).
        avisadas = srv.json_dict(cfg.alertas_proyeccion)
        if (
            p.ultima_alerta_mes != clave  # si ya avisó el umbral, no repetir
            and proy["estado"] == "en_riesgo"
            and proy["dias_transcurridos"] >= 3
            and proy["dias_restantes"] > 0
            and avisadas.get(p.id) != clave
        ):
            enviar_push(db, usuario_id, f"Ojo con {p.categoria}", proy["mensaje"], "/presupuesto")
            avisadas[p.id] = clave
            cfg = srv.guardar_config(db, usuario_id, alertas_proyeccion=json.dumps(avisadas))
            resultado["notificados"] += 1


@router.post("/cron/aportes-automaticos")
def cron_aportes_automaticos(
    db: Session = Depends(get_db), x_cron_secret: str = Header(default="")
):
    """Cron diario: para cada meta con aporte_automatico configurado, si ya llegó
    el día del aporte (hoy >= día efectivo) y no se ha aportado este mes, mueve el
    dinero de la cuenta de origen hacia la meta: crea un movimiento neutro
    'Aporte a meta «X»', baja el saldo, suma monto_actual y avisa por push. Si el
    cron falla un día, el siguiente lo recupera; ejecutarlo dos veces no duplica."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    hoy = ahora_co()
    ultimo_dia_mes_actual = calendar.monthrange(hoy.year, hoy.month)[1]
    metas = (
        db.query(Meta)
        .filter(Meta.activa == True, Meta.aporte_automatico.isnot(None))  # noqa: E712
        .all()
    )
    aportados = 0
    corrida = Corrida(db)

    for meta in metas:
        # El id se lee antes: tras un rollback el objeto queda expirado.
        with corrida.aislar(meta.usuario_id):
            if _aportar_meta_automatico(db, meta, hoy, ultimo_dia_mes_actual):
                aportados += 1

    return {"ok": True, "aportados": aportados, **corrida.resumen()}


def _aportar_meta_automatico(db: Session, meta, hoy, ultimo_dia_mes_actual: int) -> bool:
    """Aporte automático de UNA meta. True si se aportó.

    - Recuperación: dispara si el día efectivo (día configurado, o el último del mes
      si no existe, ej. 31 en febrero) ya llegó (<= hoy) y aún no se aportó este mes.
      Si el cron falla un día, el siguiente lo recupera.
    - Idempotente: `ultimo_aporte_automatico` + el bloqueo de la fila impiden doble aporte.
    - Con cuenta de origen crea un Movimiento NEUTRO ('aporte_meta': ni gasto ni
      ingreso, ver contabilidad.FUENTE_APORTE_META) y baja el saldo bajo bloqueo.
      Si no alcanza el saldo NO aporta parcialmente: avisa una sola vez al mes."""
    # Se relee la meta bloqueándola: dos ejecuciones simultáneas no aportan dos veces.
    meta = (
        db.query(Meta).filter(Meta.id == meta.id).with_for_update().populate_existing().first()
    )
    if meta is None or not meta.activa or not meta.aporte_automatico or meta.aporte_automatico <= 0:
        return False

    # Si la meta ya alcanzó su objetivo, no debe seguir recibiendo aportes
    # automáticos mes a mes (el usuario no la desactivó, solo la cumplió).
    if (meta.monto_actual or 0) >= (meta.monto_objetivo or 0):
        return False

    dia_efectivo = min(meta.dia_aporte or 1, ultimo_dia_mes_actual)
    if hoy.day < dia_efectivo:
        return False
    ya_este_mes = (
        meta.ultimo_aporte_automatico
        and meta.ultimo_aporte_automatico.year == hoy.year
        and meta.ultimo_aporte_automatico.month == hoy.month
    )
    if ya_este_mes:
        return False

    monto = meta.aporte_automatico
    cuenta = None
    if meta.cuenta_origen_id:
        # Defensa en profundidad: aunque la API ya valida al guardar la meta, el cron
        # solo toca cuentas que pertenecen al dueño de la meta. Se bloquea la fila
        # (mismo mecanismo que el registro de movimientos) para dejar el saldo consistente.
        cuenta = (
            db.query(Cuenta)
            .filter(Cuenta.id == meta.cuenta_origen_id, Cuenta.usuario_id == meta.usuario_id)
            .first()
        )
        if not cuenta:
            return False  # la cuenta de origen ya no existe/no es suya: no se aporta plata de la nada
        cuenta = bloquear_cuenta(db, cuenta.id)

    if cuenta:
        if (cuenta.saldo or 0) < monto:
            # Sin saldo suficiente: no se aporta parcialmente. Aviso amable, una
            # sola vez al mes por meta (el cron sigue reintentando cada día).
            if reclamar_marca(db, meta.usuario_id, f"aporte_sin_saldo:{meta.id}", hoy.strftime("%Y-%m")):
                enviar_push(
                    db,
                    meta.usuario_id,
                    "Tu aporte automático",
                    f"No alcanzó para tu aporte a «{meta.nombre}». "
                    "Cuando tengas saldo en la cuenta, lo intentamos de nuevo.",
                    "/metas",
                )
            return False
        db.add(
            Movimiento(
                usuario_id=meta.usuario_id,
                cuenta_id=cuenta.id,
                fecha=hoy,
                descripcion=f"Aporte a meta «{meta.nombre}»",
                categoria=CATEGORIA_APORTE_META,
                tipo="expense",  # mueve el saldo como una salida; la regla contable lo trata como neutro
                monto=monto,
                fuente=FUENTE_APORTE_META,
                notas=f"META:{meta.id}",
            )
        )
        cuenta.saldo -= monto
    meta.monto_actual = (meta.monto_actual or 0) + monto
    meta.ultimo_aporte_automatico = hoy
    db.commit()

    enviar_push(
        db,
        meta.usuario_id,
        f"Aporte automático: {meta.nombre}",
        f"Se apartaron {monto:,.0f} COP para tu meta",
        "/metas",
    )
    return True


@router.post("/cron/premiar-presupuestos-mes")
def cron_premiar_presupuestos_mes(
    db: Session = Depends(get_db), x_cron_secret: str = Header(default="")
):
    """Pensado para llamarse una vez, el último día del mes: si un usuario
    tiene presupuestos activos y NINGUNO se pasó del límite, otorga una vida
    del ahorcado. Se identifica por mes para no otorgar dos veces el mismo mes."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    hoy = ahora_co()
    # El cron externo puede estar programado con más frecuencia de la debida
    # (llegó a correr cada 15 minutos). Sin esta guarda, el día 1 —con cero
    # gastos— todos cumplirían "ningún presupuesto se pasó" y ganarían la vida
    # de ese mes sin haber cumplido nada. Solo se premia el último día del mes.
    if hoy.day != calendar.monthrange(hoy.year, hoy.month)[1]:
        return {"ok": True, "premiados": 0, "procesados": 0, "fallidos": 0,
                "motivo": "hoy no es el último día del mes"}
    inicio_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    clave_mes = hoy.strftime("%Y-%m")

    usuarios_con_presupuesto = {
        u[0]
        for u in db.query(Presupuesto.usuario_id)
        .filter(Presupuesto.activo == True)  # noqa: E712
        .distinct()
        .all()
    }
    premiados = 0
    corrida = Corrida(db)

    for usuario_id in usuarios_con_presupuesto:
        with corrida.aislar(usuario_id):
            if _premiar_presupuestos_de(db, usuario_id, inicio_mes, clave_mes):
                premiados += 1

    return {"ok": True, "premiados": premiados, **corrida.resumen()}


def _premiar_presupuestos_de(db: Session, usuario_id: str, inicio_mes, clave_mes: str) -> bool:
    """Premio del mes para UN usuario. True si se otorgó la vida."""
    presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.usuario_id == usuario_id, Presupuesto.activo == True)  # noqa: E712
        .all()
    )
    if not presupuestos:
        return False

    ids_accesibles = cuentas_ids_accesibles(db, usuario_id)
    gastado_mes = gastos_por_categoria(db, ids_accesibles, inicio_mes, base=moneda_base_de(db, usuario_id))
    if any(gastado_mes.get(p.categoria, 0.0) > p.limite for p in presupuestos):
        return False

    if not otorgar_vida_si_nueva(db, usuario_id, f"presupuesto_cumplido_{clave_mes}"):
        return False
    enviar_push(
        db,
        usuario_id,
        "¡Cumpliste tu presupuesto! 🎉",
        "Ningún presupuesto se pasó este mes — mira cómo creció tu árbol financiero",
        "/ahorcado",
    )
    return True


@router.post("/cron/resumen-semanal")
def cron_resumen_semanal(
    db: Session = Depends(get_db), x_cron_secret: str = Header(default="")
):
    """Pensado para llamarse una vez a la semana (domingo en la tarde): manda un push breve con
    lo gastado en los últimos 7 días, la comparación con la semana anterior y la categoría que más
    pesó (+ botón a Informes), a cada usuario con push activo y movimientos en la semana.
    Apagar las notificaciones en Perfil (que quita la suscripción) es el opt-out."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    ahora = ahora_co()
    hace_7_dias = ahora - timedelta(days=7)
    iso = ahora.isocalendar()
    semana_iso = f"{iso[0]}-W{iso[1]:02d}"  # marca de idempotencia: una vez por usuario y semana ISO
    usuarios_con_push = {
        s[0] for s in db.query(PushSubscription.usuario_id).distinct().all()
    }
    enviados = 0
    corrida = Corrida(db)

    for usuario_id in usuarios_con_push:
        with corrida.aislar(usuario_id):
            if _resumen_semanal_de(db, usuario_id, hace_7_dias, semana_iso):
                enviados += 1

    return {"ok": True, "enviados": enviados, **corrida.resumen()}


def _resumen_semanal_de(db: Session, usuario_id: str, hace_7_dias, semana_iso: str) -> bool:
    """Resumen semanal de UN usuario. True si se envió. Idempotente: la marca
    'resumen_semanal' guarda la semana ISO ya avisada (dos ejecuciones = un push).
    Solo escribe a quien tuvo movimientos en la semana; compara con la anterior, nombra la
    categoría que más pesó, respeta el punto de partida y «ocultar saldos» (sin montos)."""
    from app import resumen_semanal as rs
    from app.models_fiscal import AjusteUsuario

    ids_accesibles = cuentas_ids_accesibles(db, usuario_id)
    if not ids_accesibles:
        return False
    ahora = hace_7_dias + timedelta(days=7)
    datos = rs.comparativo_push(db, usuario_id, list(ids_accesibles), ahora)
    if datos is None:
        return False
    aj = db.query(AjusteUsuario).filter(AjusteUsuario.usuario_id == usuario_id).first()
    from app.models import Perfil
    from app.nombre import nombre_para_mostrar

    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    titulo, cuerpo = rs.mensaje_push(datos, ocultar_montos=bool(aj and aj.ocultar_montos),
                                     nombre=nombre_para_mostrar(perfil.nombre_preferido if perfil else ""))

    # Se reclama la marca ANTES de enviar (dos ejecuciones simultáneas: pasa una sola).
    if not reclamar_marca(db, usuario_id, "resumen_semanal", semana_iso):
        return False
    try:
        n = enviar_push(db, usuario_id, titulo, cuerpo, "/informe", boton="Ver mis informes")
    except Exception:
        liberar_marca(db, usuario_id, "resumen_semanal")  # que el siguiente cron lo reintente
        raise
    if not n:
        # Nada llegó (sin VAPID o todas las suscripciones fallaron): se libera la marca.
        liberar_marca(db, usuario_id, "resumen_semanal")
        return False
    return True


HORA_RECORDATORIO_REGISTRO = 20  # 8pm Colombia


@router.post("/cron/recordar-registro")
def cron_recordar_registro(
    forzar: bool = False,
    db: Session = Depends(get_db),
    x_cron_secret: str = Header(default=""),
):
    """Recordatorio nocturno opcional: avisa por push SOLO a quien activó el
    'recordatorio diario' en Perfil y hoy (hora Colombia) no registró nada.
    Programarlo 1 vez al día a las 20:00 hora Colombia. Está blindado contra
    un cron mal programado: antes de las 8pm no hace nada (salvo ?forzar=true)
    y no repite el aviso el mismo día (perfiles.ultimo_recordatorio)."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    ahora = ahora_co()
    if ahora.hour < HORA_RECORDATORIO_REGISTRO and not forzar:
        return {"ok": True, "enviados": 0, "procesados": 0, "fallidos": 0,
                "motivo": "aún no son las 8pm en Colombia"}

    hoy = ahora.strftime("%Y-%m-%d")
    inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    perfiles = (
        db.query(Perfil)
        .filter(Perfil.recordatorio_diario.is_(True))
        .filter((Perfil.ultimo_recordatorio.is_(None)) | (Perfil.ultimo_recordatorio != hoy))
        .all()
    )
    enviados = 0
    corrida = Corrida(db)
    for perfil in perfiles:
        with corrida.aislar(perfil.usuario_id):
            if _recordar_registro_de(db, perfil, hoy, inicio_dia):
                enviados += 1

    return {"ok": True, "enviados": enviados, **corrida.resumen()}


def _recordar_registro_de(db: Session, perfil, hoy: str, inicio_dia) -> bool:
    """Recordatorio nocturno para UN perfil. True si se envió."""
    ids = cuentas_ids_accesibles(db, perfil.usuario_id)
    registro_hoy = (
        db.query(Movimiento.id)
        .filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= inicio_dia)
        .first()
    )
    if registro_hoy:
        return False
    n = enviar_push(
        db,
        perfil.usuario_id,
        "¿Hiciste algún movimiento hoy?",
        "Aún no registras nada hoy. Anótalo en 10 segundos y tus cuentas seguirán cuadrando.",
        "/agregar",
    )
    if not n:
        return False
    perfil.ultimo_recordatorio = hoy
    db.commit()
    return True


@router.post("/cron/recordar-recurrentes")
def cron_recordar_recurrentes(
    db: Session = Depends(get_db), x_cron_secret: str = Header(default="")
):
    """Pensado para llamarse una vez al día: avisa por push cuando un gasto o
    ingreso recurrente está por vencer (según su alerta_dias_antes propia),
    una sola vez por ciclo — se marca con ultima_notificacion_vencimiento
    para no repetir el aviso todos los días mientras sigue "próximo"."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    hoy = ahora_co()
    recurrentes = db.query(Recurrente).filter(Recurrente.activo == True).all()  # noqa: E712
    notificados = 0
    corrida = Corrida(db)

    for rec in recurrentes:
        with corrida.aislar(rec.usuario_id):
            if _avisar_recurrente(db, rec, hoy):
                notificados += 1

    # Mismo cron diario: también avisa de tarjetas de crédito con pago cerca.
    # Así no hace falta un cron nuevo ni cambiar horarios.
    tarjetas_avisadas = 0
    usuarios_con_push = {s[0] for s in db.query(PushSubscription.usuario_id).distinct().all()}
    if usuarios_con_push:
        tarjetas = (
            db.query(Cuenta)
            .filter(Cuenta.usuario_id.in_(usuarios_con_push), Cuenta.tipo == "credito")
            .all()
        )
        movs = {t.id: movimientos_tras_corte(db, t, hoy) for t in tarjetas if t.dia_corte}
        guardados = extractos_guardados(db, [t.id for t in tarjetas])
        for cuenta, info in tarjetas_por_avisar(tarjetas, hoy, movs, guardados):
            with corrida.aislar(cuenta.usuario_id):
                _avisar_pago_tarjeta(db, cuenta, info)
                tarjetas_avisadas += 1

    return {"ok": True, "notificados": notificados, "tarjetas_avisadas": tarjetas_avisadas,
            **corrida.resumen()}


def _avisar_recurrente(db: Session, rec, hoy) -> bool:
    """Aviso de vencimiento de UN recurrente. True si se envió."""
    estado_info = calc_estado_recurrente(rec)
    if estado_info["estado"] != "proximo":
        return False

    # Una vez por OCURRENCIA (no por mes calendario): el aviso de esta ocurrencia
    # solo puede haberse enviado dentro de su ventana [vencimiento - alerta_dias,
    # vencimiento]. Si la última notificación cae antes del inicio de esa ventana,
    # era de una ocurrencia anterior y toca avisar de nuevo.
    fecha_esperada = hoy.replace(day=_dia_valido_del_mes(hoy.year, hoy.month, rec.dia_del_mes or 1))
    inicio_ventana = (fecha_esperada - timedelta(days=rec.alerta_dias_antes or 2)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    ultima = rec.ultima_notificacion_vencimiento
    if ultima is not None and ultima >= inicio_ventana:
        return False

    dias = estado_info["dias_para_vencer"]
    enviar_push(
        db,
        rec.usuario_id,
        f"{rec.nombre} está por vencer",
        f"Faltan {dias} {'día' if dias == 1 else 'días'} — {rec.monto:,.0f} COP",
        "/recurrentes",
    )
    rec.ultima_notificacion_vencimiento = hoy
    db.commit()
    return True


def _avisar_pago_tarjeta(db: Session, cuenta, info: dict) -> None:
    # monto_aviso = lo que FALTA para no pagar intereses (total del extracto menos
    # lo ya abonado); si no se conoce el corte, la deuda actual como antes.
    dias = info["dias_aviso"]
    inicio = f"Te quedan {dias} {'día' if dias == 1 else 'días'} para el pago" if dias > 0 else "Hoy vence el pago"
    minimo = f". Pago mínimo del extracto: {info['pago_minimo']:,.0f}" if info.get("pago_minimo_del_extracto") else ""
    enviar_push(
        db,
        cuenta.usuario_id,
        f"Paga tu {cuenta.nombre}",
        f"{inicio}: paga {info['monto_aviso']:,.0f} antes del {info['fecha_aviso']} para no pagar intereses{minimo}",
        "/cuentas",
    )
    cuenta.ultima_alerta_pago = info["fecha_aviso"]
    db.commit()
