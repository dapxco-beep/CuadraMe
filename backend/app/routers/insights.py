from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app import asistente as ia
from app import asistente_consultas as consultas
from app import informe as inf
from app.asistente_datos import cargar_datos
from app.limites import verificar_limite
from app.limites_diarios import consumir_cupo_diario
from app.utiles import ahora_co
from app.alertas_proactivas import detectar_cobros_duplicados, detectar_comisiones
from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import tipos_cuenta_de, tipos_efectivos
from app.database import get_db
from app.edad_dinero import calcular_edad_dinero, mensaje_edad, tendencia_edad
from app.fx import convertir_a_cop
from app.salud_financiera import calcular_salud_financiera
from app.insights import _resumen_fallback, detectar_anomalias, generar_resumen_semanal, responder_pregunta
from app.routers.consentimientos import exigir_consentimiento, tiene_consentimiento
from app.config import settings
from app.models import Cuenta, Deuda, Meta, Movimiento, Presupuesto
from app.schemas import (
    AlertasProactivasResponse,
    EdadDelDinero,
    PreguntarRequest,
    PreguntarResponse,
    ResumenSemanal,
)

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/resumen-semanal", response_model=ResumenSemanal)
def resumen_semanal(
    desde: str | None = None,
    hasta: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Por defecto, los últimos 7 días. Con `desde`/`hasta` (AAAA-MM-DD, ambos
    inclusive) resume cualquier rango personalizado."""
    hoy = ahora_co()
    hace_7_dias = hoy - timedelta(days=7)
    fin_rango = None
    etiqueta = None
    if desde or hasta:
        try:
            rango = inf.rango_periodo("rango", hoy, desde or hasta, hasta or desde)
        except inf.PeriodoInvalido as e:
            raise HTTPException(status_code=422, detail=str(e))
        hace_7_dias, fin_rango, etiqueta = rango["desde"], rango["hasta"], rango["etiqueta"]

    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()}
    todos = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids_accesibles)).all()
    semana = [m for m in todos if m.fecha >= hace_7_dias and (fin_rango is None or m.fecha < fin_rango)]

    def monto_cop(m):
        return convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))

    te = tipos_efectivos(todos, tipos_cuenta_de(db, ids_accesibles))  # sin pagos de tarjeta ni traslados propios
    ingresos = sum(monto_cop(m) for m in semana if te[m.id] == "income")
    gastos = sum(monto_cop(m) for m in semana if te[m.id] == "expense")

    categorias: dict[str, float] = {}
    for m in semana:
        if te[m.id] == "expense":
            categorias[m.categoria] = categorias.get(m.categoria, 0) + monto_cop(m)
    top_categorias = sorted(
        ({"categoria": k, "monto": v} for k, v in categorias.items()),
        key=lambda x: x["monto"],
        reverse=True,
    )[:3]

    anomalias_raw = detectar_anomalias(
        [{"categoria": m.categoria, "tipo": te[m.id], "monto": monto_cop(m), "fecha": m.fecha} for m in todos]
    )

    resumen = {
        "ingresos": ingresos,
        "gastos": gastos,
        "top_categorias": top_categorias,
        "anomalias": anomalias_raw,
        "periodo": etiqueta,
    }
    # Sin consentimiento «ia» vigente, las cifras no salen hacia ningún proveedor: texto determinista.
    if settings.exigir_consentimientos and not tiene_consentimiento(db, usuario.id, "ia"):
        texto = _resumen_fallback(resumen)
    else:
        texto = generar_resumen_semanal(resumen)

    return ResumenSemanal(
        ingresos=ingresos,
        gastos=gastos,
        ahorro=ingresos - gastos,
        top_categorias=top_categorias,
        anomalias=anomalias_raw,
        texto=texto,
        desde=(rango["desde"].date().isoformat() if etiqueta else (hoy - timedelta(days=7)).date().isoformat()),
        hasta=((rango["hasta"] - timedelta(days=1)).date().isoformat() if etiqueta else hoy.date().isoformat()),
        etiqueta=etiqueta or "los últimos 7 días",
    )


@router.get("/alertas-proactivas", response_model=AlertasProactivasResponse)
def alertas_proactivas(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Estilo Fintonic: avisa de comisiones bancarias y posibles cobros
    duplicados que el usuario probablemente no notó por su cuenta."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()}
    hace_90_dias = ahora_co() - timedelta(days=90)
    movimientos = (
        db.query(Movimiento)
        .filter(Movimiento.cuenta_id.in_(ids_accesibles), Movimiento.fecha >= hace_90_dias)
        .all()
    )
    # Convertir a COP como en el resto de insights: si no se convierte, una
    # cuenta en USD mezclada con cuentas en COP suma montos de distinta
    # moneda como si fueran el mismo número en detectar_comisiones, y en
    # detectar_cobros_duplicados dos montos iguales en monedas distintas
    # (o el mismo monto en USD vs. su equivalente en COP) no se comparan
    # de forma consistente con el resto de la app.
    te = tipos_efectivos(movimientos, tipos_cuenta_de(db, ids_accesibles))
    data = [
        {
            "id": m.id,
            "descripcion": m.descripcion,
            "monto": convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP")),
            "fecha": m.fecha,
            "tipo": te[m.id],
        }
        for m in movimientos
    ]

    return AlertasProactivasResponse(
        comisiones=detectar_comisiones(data),
        cobros_duplicados=detectar_cobros_duplicados(data),
    )


@router.get("/edad-del-dinero", response_model=EdadDelDinero)
def edad_del_dinero(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """'Age of Money' (YNAB): cuántos días en promedio dura tu dinero antes
    de gastarse. Un solo número memorable que resume el colchón real."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()}
    hace_90_dias = ahora_co() - timedelta(days=90)
    movimientos = (
        db.query(Movimiento)
        .filter(Movimiento.cuenta_id.in_(ids_accesibles), Movimiento.fecha >= hace_90_dias)
        .all()
    )
    te = tipos_efectivos(movimientos, tipos_cuenta_de(db, ids_accesibles))
    data = [
        {"fecha": m.fecha, "tipo": te[m.id], "monto": convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))}
        for m in movimientos
    ]

    hoy = ahora_co()
    edad_actual = calcular_edad_dinero(data, dias_ventana=30, referencia=hoy)
    edad_anterior = calcular_edad_dinero(data, dias_ventana=30, referencia=hoy - timedelta(days=30))
    tendencia = tendencia_edad(edad_actual, edad_anterior)

    return EdadDelDinero(dias=edad_actual, tendencia=tendencia, mensaje=mensaje_edad(edad_actual, tendencia))


@router.post("/preguntar", response_model=PreguntarResponse)
def preguntar(
    data: PreguntarRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Chat de finanzas: responde con base en los movimientos, cuentas,
    presupuestos, metas y deudas reales del usuario (últimos 90 días de
    movimientos, para no exceder el contexto del modelo)."""
    # Cada pregunta cuesta una llamada a la IA: tope por usuario.
    verificar_limite(f"preguntar:{usuario.id}", 20, 3600, "Llegaste al límite de preguntas por hora. Intenta más tarde.")
    consumir_cupo_diario(db, usuario.id, "preguntar")

    # 1) Las preguntas típicas (en qué gasté más, cuánto gasté en X, comparar
    #    meses, presupuesto...) se resuelven con CÁLCULO del backend, el mismo
    #    del asistente nuevo y con la regla contable: cifras reales y periodo explícito.
    from app.routers.asistente import _responder_rapida

    hoy = ahora_co()
    texto_seguro = ia.redactar_secretos(data.pregunta).replace("<<<", " ").replace(">>>", " ").strip()
    intento = ia.detectar_intencion(texto_seguro, hoy)
    if intento["intencion"] in ("consulta", "rapida"):
        d = cargar_datos(db, usuario.id, hoy)
        r = (consultas.responder_consulta(intento, d) if intento["intencion"] == "consulta"
             else _responder_rapida(intento["id"], d, intento.get("periodo")))
        return PreguntarResponse(respuesta=r["texto"], fuentes=r.get("fuentes", []),
                                 sugerencias=r.get("sugerencias", []))
    if intento["intencion"] in ("comprar", "ahorro", "deudas", "registrar"):
        return PreguntarResponse(
            respuesta="Eso lo resuelvo mejor en CuadraMe AI (Inicio > Pregúntale a CuadraMe AI): simula, "
                      "arma el plan y te deja confirmar antes de guardar nada.")

    # 2) Pregunta abierta: IA sobre los últimos 90 días (si no hay IA, se sugieren preguntas útiles).
    exigir_consentimiento(db, usuario.id, "ia")  # Ley 1581: los movimientos van a un proveedor de IA
    hace_90_dias = ahora_co() - timedelta(days=90)
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)

    movimientos = (
        db.query(Movimiento)
        .filter(Movimiento.cuenta_id.in_(ids_accesibles), Movimiento.fecha >= hace_90_dias)
        .order_by(Movimiento.fecha.desc())
        .limit(300)
        .all()
    )
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()
    presupuestos = db.query(Presupuesto).filter(Presupuesto.usuario_id == usuario.id).all()
    metas = db.query(Meta).filter(Meta.usuario_id == usuario.id, Meta.activa == True).all()  # noqa: E712
    deudas = db.query(Deuda).filter(Deuda.usuario_id == usuario.id, Deuda.activa == True).all()  # noqa: E712

    contexto = {
        "cuentas": [{"nombre": c.nombre, "saldo": c.saldo, "moneda": c.moneda} for c in cuentas],
        "presupuestos": [{"categoria": p.categoria, "limite": p.limite} for p in presupuestos],
        "metas": [{"nombre": m.nombre, "objetivo": m.monto_objetivo, "actual": m.monto_actual} for m in metas],
        "deudas": [{"nombre": d.nombre, "saldo_actual": d.saldo_actual} for d in deudas],
        "movimientos_ultimos_90_dias": [
            {
                "fecha": m.fecha.strftime("%Y-%m-%d"),
                # Lo que se originó en un correo de Gmail no se describe a la IA (Uso Limitado de
                # Google): solo viaja categoría, tipo y monto.
                "descripcion": "" if m.fuente == "email" else m.descripcion,
                "categoria": m.categoria,
                "tipo": m.tipo,
                "monto": m.monto,
            }
            for m in movimientos
        ],
    }

    respuesta = responder_pregunta(data.pregunta, contexto)
    if not respuesta:
        return PreguntarResponse(respuesta=consultas.texto_no_entendi(), sugerencias=consultas.SUGERENCIAS_UTILES)
    return PreguntarResponse(respuesta=respuesta)


@router.get("/salud-financiera")
def salud_financiera(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    """Puntaje 0-100 con desglose. Aquí solo se juntan los datos (todo en COP);
    la fórmula vive en app/salud_financiera.py como función pura."""
    ahora = ahora_co()
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()
    monedas = {c.id: c.moneda for c in cuentas}
    # El colchón son los saldos líquidos: una cuenta de crédito no es plata propia.
    saldo_liquido = sum(
        convertir_a_cop(c.saldo, c.moneda) for c in cuentas if c.tipo in ("ahorro", "efectivo")
    )

    movs = (
        db.query(Movimiento)
        .filter(Movimiento.cuenta_id.in_(ids_accesibles), Movimiento.fecha >= ahora - timedelta(days=90))
        .all()
    )

    def cop(m):
        return convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))

    te = tipos_efectivos(movs, tipos_cuenta_de(db, ids_accesibles))
    corte_30 = ahora - timedelta(days=30)
    ult30 = [m for m in movs if m.fecha >= corte_30]
    ingresos_30 = sum(cop(m) for m in ult30 if te[m.id] == "income")
    gastos_30 = sum(cop(m) for m in ult30 if te[m.id] == "expense")

    # Gasto mensual típico: gastos de hasta 90 días prorrateados a 30. Si la
    # persona es nueva se usa solo el tiempo que lleva (mínimo 30 días) para no
    # subestimar su gasto dividiendo entre meses vacíos.
    gastos_90 = sum(cop(m) for m in movs if te[m.id] == "expense")
    if movs:
        dias_obs = min(90, max(30, (ahora - min(m.fecha for m in movs)).days + 1))
    else:
        dias_obs = 30
    gasto_mensual = gastos_90 / dias_obs * 30

    deudas = db.query(Deuda).filter(Deuda.usuario_id == usuario.id, Deuda.activa == True).all()  # noqa: E712
    cuotas = sum(d.cuota_mensual or 0 for d in deudas)

    inicio_mes = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    gastado_cat: dict[str, float] = {}
    for m in movs:
        if te[m.id] == "expense" and m.fecha >= inicio_mes:
            gastado_cat[m.categoria] = gastado_cat.get(m.categoria, 0) + cop(m)
    presupuestos = [
        (p.limite + (p.sobre_ajuste or 0), gastado_cat.get(p.categoria, 0))
        for p in db.query(Presupuesto).filter(Presupuesto.usuario_id == usuario.id, Presupuesto.activo == True).all()  # noqa: E712
    ]

    dias_registro = len({m.fecha.date() for m in ult30})

    return calcular_salud_financiera(
        saldo_liquido=saldo_liquido,
        gasto_mensual_promedio=gasto_mensual,
        ingresos_30d=ingresos_30,
        gastos_30d=gastos_30,
        cuotas_deuda_mensual=cuotas,
        presupuestos=presupuestos,
        dias_con_registro_30d=dias_registro,
    )
