import calendar
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app import presupuesto_servicio as srv
from app.auth import UsuarioActual, cron_autorizado, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import gastos_por_categoria, tipos_cuenta_de, tipos_efectivos
from app.config import settings
from app.database import get_db
from app.finanzas import calc_estado_recurrente
from app.fx import convertir_a_cop
from app.models import Cuenta, Meta, Movimiento, Perfil, Presupuesto, PushSubscription, Recurrente
from app.push import enviar_push
from app.rachas import otorgar_vida_si_nueva
from app.tarjetas import tarjetas_por_avisar
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
    notificados = 0
    ahora = ahora_co()

    for usuario_id in usuarios_con_push:
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
                notificados += 1
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
                notificados += 1

    return {"ok": True, "notificados": notificados}


@router.post("/cron/aportes-automaticos")
def cron_aportes_automaticos(
    db: Session = Depends(get_db), x_cron_secret: str = Header(default="")
):
    """Cron diario: para cada meta con aporte_automatico configurado, si hoy
    es el día indicado y no se ha aportado ya este mes, mueve el dinero de la
    cuenta de origen hacia la meta (resta saldo, suma monto_actual) y avisa
    por push. Pensado para llamarse una vez al día desde el mismo cron externo."""
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

    for meta in metas:
        # Si la meta ya alcanzó su objetivo, no debe seguir recibiendo aportes
        # automáticos mes a mes (el usuario no la desactivó, solo la cumplió).
        if (meta.monto_actual or 0) >= (meta.monto_objetivo or 0):
            continue

        # Si el día configurado no existe este mes (ej. 31 en un mes de 30),
        # se dispara el último día del mes en su lugar.
        dia_efectivo = min(meta.dia_aporte, ultimo_dia_mes_actual)
        if dia_efectivo != hoy.day:
            continue
        ya_este_mes = (
            meta.ultimo_aporte_automatico
            and meta.ultimo_aporte_automatico.year == hoy.year
            and meta.ultimo_aporte_automatico.month == hoy.month
        )
        if ya_este_mes:
            continue

        cuenta = None
        if meta.cuenta_origen_id:
            # Defensa en profundidad: aunque la API ya valida al guardar la meta, el cron
            # solo toca cuentas que pertenecen al dueño de la meta.
            cuenta = (
                db.query(Cuenta)
                .filter(Cuenta.id == meta.cuenta_origen_id, Cuenta.usuario_id == meta.usuario_id)
                .first()
            )

        monto = meta.aporte_automatico
        # Si la cuenta de origen no tiene saldo suficiente, no dejar el saldo
        # en negativo silenciosamente: se aparta solo lo disponible (igual que
        # aportar_meta valida en el endpoint manual). Si no hay nada disponible,
        # se salta el aporte este mes.
        if cuenta:
            if cuenta.saldo <= 0:
                continue
            monto = min(monto, cuenta.saldo)
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
        aportados += 1

    return {"ok": True, "aportados": aportados}


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
        return {"ok": True, "premiados": 0, "motivo": "hoy no es el último día del mes"}
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

    for usuario_id in usuarios_con_presupuesto:
        presupuestos = (
            db.query(Presupuesto)
            .filter(Presupuesto.usuario_id == usuario_id, Presupuesto.activo == True)  # noqa: E712
            .all()
        )
        if not presupuestos:
            continue

        ids_accesibles = cuentas_ids_accesibles(db, usuario_id)
        cumplio_todos = True
        gastado_mes = gastos_por_categoria(db, ids_accesibles, inicio_mes)
        for p in presupuestos:
            gastado = gastado_mes.get(p.categoria, 0.0)
            if gastado > p.limite:
                cumplio_todos = False
                break

        if cumplio_todos:
            otorgada = otorgar_vida_si_nueva(db, usuario_id, f"presupuesto_cumplido_{clave_mes}")
            if otorgada:
                premiados += 1
                enviar_push(
                    db,
                    usuario_id,
                    "¡Cumpliste tu presupuesto! 🎉",
                    "Ningún presupuesto se pasó este mes — mira cómo creció tu árbol financiero",
                    "/ahorcado",
                )

    return {"ok": True, "premiados": premiados}


@router.post("/cron/resumen-semanal")
def cron_resumen_semanal(
    db: Session = Depends(get_db), x_cron_secret: str = Header(default="")
):
    """Pensado para llamarse una vez a la semana (ej. domingo en la noche):
    manda un push con ingresos/gastos de los últimos 7 días a cada usuario
    con push activo, para que no tenga que abrir la app a revisarlo."""
    if not cron_autorizado(x_cron_secret):
        raise HTTPException(status_code=401, detail="No autorizado")

    hace_7_dias = ahora_co() - timedelta(days=7)
    usuarios_con_push = {
        s[0] for s in db.query(PushSubscription.usuario_id).distinct().all()
    }
    enviados = 0

    for usuario_id in usuarios_con_push:
        ids_accesibles = cuentas_ids_accesibles(db, usuario_id)
        if not ids_accesibles:
            continue
        monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()}
        semana = (
            db.query(Movimiento)
            .filter(Movimiento.cuenta_id.in_(ids_accesibles), Movimiento.fecha >= hace_7_dias)
            .all()
        )
        if not semana:
            continue

        def monto_cop(m):
            return convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))

        te = tipos_efectivos(semana, tipos_cuenta_de(db, ids_accesibles))
        gastos = sum(monto_cop(m) for m in semana if te[m.id] == "expense")
        ingresos = sum(monto_cop(m) for m in semana if te[m.id] == "income")

        enviar_push(
            db,
            usuario_id,
            "Tu semana en números",
            f"Gastaste {gastos:,.0f} COP e ingresaste {ingresos:,.0f} COP — mira el detalle",
            "/insights",
        )
        enviados += 1

    return {"ok": True, "enviados": enviados}


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
        return {"ok": True, "enviados": 0, "motivo": "aún no son las 8pm en Colombia"}

    hoy = ahora.strftime("%Y-%m-%d")
    inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    perfiles = (
        db.query(Perfil)
        .filter(Perfil.recordatorio_diario.is_(True))
        .filter((Perfil.ultimo_recordatorio.is_(None)) | (Perfil.ultimo_recordatorio != hoy))
        .all()
    )
    enviados = 0
    for perfil in perfiles:
        ids = cuentas_ids_accesibles(db, perfil.usuario_id)
        registro_hoy = (
            db.query(Movimiento.id)
            .filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= inicio_dia)
            .first()
        )
        if registro_hoy:
            continue
        n = enviar_push(
            db,
            perfil.usuario_id,
            "¿Hiciste algún movimiento hoy?",
            "Aún no registras nada hoy. Anótalo en 10 segundos y tus cuentas seguirán cuadrando.",
            "/agregar",
        )
        if n:
            perfil.ultimo_recordatorio = hoy
            db.commit()
            enviados += 1

    return {"ok": True, "enviados": enviados}


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

    for rec in recurrentes:
        estado_info = calc_estado_recurrente(rec)
        if estado_info["estado"] != "proximo":
            continue

        ya_notificado_este_ciclo = (
            rec.ultima_notificacion_vencimiento is not None
            and rec.ultima_notificacion_vencimiento.year == hoy.year
            and rec.ultima_notificacion_vencimiento.month == hoy.month
        )
        if ya_notificado_este_ciclo:
            continue

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
        for cuenta, info in tarjetas_por_avisar(tarjetas, hoy):
            dias = info["dias_para_pago"]
            cuando = "hoy" if dias == 0 else f"en {dias} {'día' if dias == 1 else 'días'}"
            enviar_push(
                db,
                cuenta.usuario_id,
                f"Paga tu {cuenta.nombre}",
                f"Paga antes del {info['proximo_pago']} ({cuando}) para no pagar intereses — "
                f"debes {info['cupo_usado']:,.0f}",
                "/cuentas",
            )
            cuenta.ultima_alerta_pago = info["proximo_pago"]
            db.commit()
            tarjetas_avisadas += 1

    return {"ok": True, "notificados": notificados, "tarjetas_avisadas": tarjetas_avisadas}
