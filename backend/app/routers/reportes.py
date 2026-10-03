import calendar
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user
from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import tipo_efectivo_receta, tipos_cuenta_de, tipos_efectivos
from app.database import get_db
from app.fx import convertir_a_cop
from app.models import Cuenta, Movimiento, Recurrente
from app.reportes import calc_health_score
from app.wrapped import calcular_wrapped
from app.schemas import (
    FlujoCajaFuturo,
    FlujoCajaMes,
    Proyeccion,
    ReporteMensual,
    TendenciaMes,
    TendenciasResponse,
)

router = APIRouter(prefix="/reportes", tags=["reportes"])


def _monedas_por_cuenta(db: Session, ids_accesibles: list[str]) -> dict[str, str]:
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()
    return {c.id: c.moneda for c in cuentas}


def _monto_cop(m: Movimiento, monedas: dict[str, str]) -> float:
    moneda = monedas.get(m.cuenta_id, "COP")
    return convertir_a_cop(m.monto, moneda)


@router.get("/mensual", response_model=ReporteMensual)
def reporte_mensual(
    mes: str | None = None,
    cuenta_id: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Por defecto reporta el mes en curso con todas las cuentas accesibles.
    - cuenta_id: limita el reporte a una sola cuenta.
    - desde/hasta (YYYY-MM-DD): si se pasan, reemplazan el filtro por 'mes'
      con un rango de fechas arbitrario (ej. un trimestre, o año contra año)."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    if cuenta_id:
        if cuenta_id not in ids_accesibles:
            ids_accesibles = []
        else:
            ids_accesibles = [cuenta_id]
    monedas = _monedas_por_cuenta(db, ids_accesibles)

    movimientos = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids_accesibles)).all()

    if desde or hasta:
        desde_dt = datetime.fromisoformat(desde) if desde else datetime.min
        hasta_dt = datetime.fromisoformat(hasta) if hasta else datetime.max
        mes_movs = [m for m in movimientos if desde_dt <= m.fecha <= hasta_dt]
        mes_target = f"{desde or '...'} a {hasta or '...'}"
    else:
        mes_target = mes or ahora_co().strftime("%Y-%m")
        mes_movs = [m for m in movimientos if m.fecha.strftime("%Y-%m") == mes_target]

    # Tipo efectivo: el pago de tarjeta y los traslados entre cuentas propias no son gasto ni ingreso.
    te = tipos_efectivos(movimientos, tipos_cuenta_de(db, ids_accesibles))
    ingresos = sum(_monto_cop(m, monedas) for m in mes_movs if te[m.id] == "income")
    gastos = sum(_monto_cop(m, monedas) for m in mes_movs if te[m.id] == "expense")
    ahorro = ingresos - gastos

    categorias: dict[str, float] = {}
    for m in mes_movs:
        if te[m.id] == "expense":
            categorias[m.categoria] = categorias.get(m.categoria, 0) + _monto_cop(m, monedas)
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


@router.get("/tendencias", response_model=TendenciasResponse)
def tendencias(
    meses: int = 6,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Ingresos/gastos/ahorro de los últimos N meses (para graficar tendencia)
    y una proyección simple del gasto total del mes en curso, extrapolando
    el ritmo diario observado hasta hoy."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    monedas = _monedas_por_cuenta(db, ids_accesibles)
    movimientos = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids_accesibles)).all()

    te = tipos_efectivos(movimientos, tipos_cuenta_de(db, ids_accesibles))
    por_mes: dict[str, dict[str, float]] = {}
    for m in movimientos:
        clave = m.fecha.strftime("%Y-%m")
        por_mes.setdefault(clave, {"ingresos": 0.0, "gastos": 0.0})
        monto_cop = _monto_cop(m, monedas)
        if te[m.id] == "income":
            por_mes[clave]["ingresos"] += monto_cop
        elif te[m.id] == "expense":
            por_mes[clave]["gastos"] += monto_cop

    hoy = ahora_co()
    claves_ordenadas = []
    cursor = hoy
    for _ in range(meses):
        claves_ordenadas.append(cursor.strftime("%Y-%m"))
        mes_anterior = cursor.month - 1 or 12
        anio = cursor.year - 1 if cursor.month == 1 else cursor.year
        cursor = cursor.replace(year=anio, month=mes_anterior, day=1)
    claves_ordenadas.reverse()

    tendencia = [
        TendenciaMes(
            mes=clave,
            ingresos=por_mes.get(clave, {}).get("ingresos", 0.0),
            gastos=por_mes.get(clave, {}).get("gastos", 0.0),
            ahorro=por_mes.get(clave, {}).get("ingresos", 0.0) - por_mes.get(clave, {}).get("gastos", 0.0),
        )
        for clave in claves_ordenadas
    ]

    mes_actual = hoy.strftime("%Y-%m")
    gastos_mes_actual = por_mes.get(mes_actual, {}).get("gastos", 0.0)
    dias_transcurridos = hoy.day
    ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    dias_restantes = ultimo_dia_mes - dias_transcurridos
    ritmo_diario = gastos_mes_actual / dias_transcurridos if dias_transcurridos > 0 else 0
    gasto_proyectado = gastos_mes_actual + ritmo_diario * dias_restantes

    return TendenciasResponse(
        meses=tendencia,
        proyeccion=Proyeccion(
            gasto_proyectado_mes=round(gasto_proyectado),
            dias_transcurridos=dias_transcurridos,
            dias_restantes_mes=dias_restantes,
            ritmo_diario=round(ritmo_diario),
        ),
    )


@router.get("/flujo-caja-futuro", response_model=FlujoCajaFuturo)
def flujo_caja_futuro(
    meses: int = 3,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Proyecta el saldo total mes a mes hacia adelante, combinando: saldo
    actual + recurrentes conocidos (ingresos y gastos con fecha fija) +
    promedio histórico de gastos NO recurrentes de los últimos 3 meses
    (para capturar el 'ruido' de gasto variable que no es una suscripción)."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids_accesibles)).all()
    monedas = {c.id: c.moneda for c in cuentas}
    saldo_actual = sum(convertir_a_cop(c.saldo, c.moneda) for c in cuentas)

    recurrentes = db.query(Recurrente).filter(Recurrente.usuario_id == usuario.id, Recurrente.activo == True).all()  # noqa: E712

    def _monto_recurrente_cop(r: Recurrente) -> float:
        return convertir_a_cop(r.monto, monedas.get(r.cuenta_id, "COP"))

    # Un recurrente "Pago tarjeta" no es gasto: las compras con la tarjeta ya cuentan en el promedio variable.
    def _efectivo_rec(r):
        return tipo_efectivo_receta(r.tipo, r.categoria, r.nombre)

    ingresos_recurrentes = sum(_monto_recurrente_cop(r) for r in recurrentes if _efectivo_rec(r) == "income")
    gastos_recurrentes = sum(_monto_recurrente_cop(r) for r in recurrentes if _efectivo_rec(r) == "expense")

    hoy = ahora_co()
    hace_3_meses = hoy - timedelta(days=90)
    movimientos = (
        db.query(Movimiento)
        .filter(
            Movimiento.cuenta_id.in_(ids_accesibles),
            Movimiento.fecha >= hace_3_meses,
            Movimiento.fuente != "recurrente",
        )
        .all()
    )
    te = tipos_efectivos(movimientos, tipos_cuenta_de(db, ids_accesibles))
    gasto_variable_total = sum(_monto_cop(m, monedas) for m in movimientos if te[m.id] == "expense")
    gasto_variable_promedio_mes = gasto_variable_total / 3

    meses_proyeccion: list[FlujoCajaMes] = []
    saldo_corrido = saldo_actual
    cursor = hoy

    for _ in range(meses):
        mes_siguiente = cursor.month + 1
        anio = cursor.year + (1 if mes_siguiente > 12 else 0)
        mes_siguiente = mes_siguiente if mes_siguiente <= 12 else 1
        cursor = cursor.replace(year=anio, month=mes_siguiente, day=1)

        gastos_esperados = gastos_recurrentes + gasto_variable_promedio_mes
        saldo_corrido = saldo_corrido + ingresos_recurrentes - gastos_esperados

        meses_proyeccion.append(
            FlujoCajaMes(
                mes=cursor.strftime("%Y-%m"),
                saldo_proyectado=round(saldo_corrido),
                ingresos_esperados=round(ingresos_recurrentes),
                gastos_esperados=round(gastos_esperados),
            )
        )

    return FlujoCajaFuturo(saldo_actual=round(saldo_actual), meses=meses_proyeccion)


@router.get("/wrapped")
def resumen_wrapped(
    mes: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Datos para las diapositivas del resumen mensual (por defecto, el mes
    en curso). Solo movimientos de las cuentas del propio usuario."""
    mes = mes or ahora_co().strftime("%Y-%m")
    try:
        anio, num = (int(x) for x in mes.split("-"))
        if not 1 <= num <= 12:
            raise ValueError
        anterior = f"{anio - 1}-12" if num == 1 else f"{anio}-{num - 1:02d}"
    except ValueError:
        raise HTTPException(status_code=422, detail="El mes debe tener formato YYYY-MM")

    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    monedas = _monedas_por_cuenta(db, ids_accesibles)
    movimientos = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids_accesibles)).all()

    te = tipos_efectivos(movimientos, tipos_cuenta_de(db, ids_accesibles))

    def filas(clave):
        return [
            {"tipo": te[m.id], "monto": _monto_cop(m, monedas), "categoria": m.categoria, "fecha": m.fecha}
            for m in movimientos
            if m.fecha.strftime("%Y-%m") == clave
        ]

    return calcular_wrapped(mes, filas(mes), filas(anterior))
