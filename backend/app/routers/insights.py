from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.limites import verificar_limite
from app.utiles import ahora_co
from app.alertas_proactivas import detectar_cobros_duplicados, detectar_comisiones
from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.database import get_db
from app.edad_dinero import calcular_edad_dinero, mensaje_edad, tendencia_edad
from app.fx import convertir_a_cop
from app.insights import detectar_anomalias, generar_resumen_semanal, responder_pregunta
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
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    hoy = ahora_co()
    hace_7_dias = hoy - timedelta(days=7)

    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()}
    todos = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids_accesibles)).all()
    semana = [m for m in todos if m.fecha >= hace_7_dias]

    def monto_cop(m):
        return convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))

    ingresos = sum(monto_cop(m) for m in semana if m.tipo == "income")
    gastos = sum(monto_cop(m) for m in semana if m.tipo == "expense")

    categorias: dict[str, float] = {}
    for m in semana:
        if m.tipo == "expense":
            categorias[m.categoria] = categorias.get(m.categoria, 0) + monto_cop(m)
    top_categorias = sorted(
        ({"categoria": k, "monto": v} for k, v in categorias.items()),
        key=lambda x: x["monto"],
        reverse=True,
    )[:3]

    anomalias_raw = detectar_anomalias(
        [{"categoria": m.categoria, "tipo": m.tipo, "monto": monto_cop(m), "fecha": m.fecha} for m in todos]
    )

    texto = generar_resumen_semanal({
        "ingresos": ingresos,
        "gastos": gastos,
        "top_categorias": top_categorias,
        "anomalias": anomalias_raw,
    })

    return ResumenSemanal(
        ingresos=ingresos,
        gastos=gastos,
        ahorro=ingresos - gastos,
        top_categorias=top_categorias,
        anomalias=anomalias_raw,
        texto=texto,
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
    data = [
        {
            "id": m.id,
            "descripcion": m.descripcion,
            "monto": convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP")),
            "fecha": m.fecha,
            "tipo": m.tipo,
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
    data = [
        {"fecha": m.fecha, "tipo": m.tipo, "monto": convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))}
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
                "descripcion": m.descripcion,
                "categoria": m.categoria,
                "tipo": m.tipo,
                "monto": m.monto,
            }
            for m in movimientos
        ],
    }

    respuesta = responder_pregunta(data.pregunta, contexto)
    return PreguntarResponse(respuesta=respuesta)
