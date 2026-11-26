"""
Informes: 'en qué gasto mi plata' con periodo configurable, meses con datos
(para navegar el resumen mensual) y gasto diario (mapa de calor). Todo con la
regla contable: sin pagos de tarjeta ni traslados entre cuentas propias.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import informe as inf
from app import informe_resumen as res
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.compartidos import cuentas_ids_accesibles
from app.contabilidad import delta_saldo
from app.contabilidad import ConvertidorBase
from app.informe_datos import cargar_movs_efectivos
from app.limites import verificar_limite
from app.models import Cuenta, Movimiento, Presupuesto
from app.utiles import ahora_co

router = APIRouter(prefix="/informes", tags=["informes"])

MAX_MOVS_CATEGORIA = 300
MAX_DIAS_DIARIO = 400
LIMITE_RESUMEN_POR_MINUTO = 90  # la pantalla pide 1-2 por cambio de periodo o de agrupación


def _rango(periodo: str, desde: str | None, hasta: str | None, mes: str | None) -> dict:
    try:
        return inf.rango_periodo(periodo, ahora_co(), desde, hasta, mes)
    except inf.PeriodoInvalido as e:
        raise HTTPException(status_code=422, detail=str(e))


def _cargar(db: Session, usuario: UsuarioActual, rango: dict, anterior: dict | None = None) -> list[dict]:
    ini = min(rango["desde"], anterior["desde"]) if anterior else rango["desde"]
    return cargar_movs_efectivos(db, usuario.id, ini, rango["hasta"])


@router.get("/gasto")
def informe_gasto(
    periodo: str = Query("este_mes"),
    desde: str | None = None,
    hasta: str | None = None,
    mes: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Gasto por categoría (con % del total y comparación contra el periodo
    anterior) y comercios principales."""
    rango = _rango(periodo, desde, hasta, mes)
    anterior = inf.periodo_anterior(rango)
    movs = _cargar(db, usuario, rango, anterior)
    informe = inf.informe_gasto(movs, rango, anterior)
    informe["periodo"] = periodo
    informe["moneda_base"] = movs.base
    informe["monedas_sin_tasa"] = list(movs.sin_tasa)
    if not informe["hay_datos"]:
        # Ayuda para que la pantalla ofrezca saltar al último mes con gastos.
        todos = cargar_movs_efectivos(db, usuario.id)
        informe["ultimo_mes_con_datos"] = inf.ultimo_mes_con_datos(todos)
    return informe


@router.get("/gasto/movimientos")
def movimientos_de_categoria(
    categoria: str | None = None,
    comercio: str | None = None,
    fuente: str | None = None,
    tipo: str = Query("gasto", pattern="^(gasto|ingreso)$"),
    periodo: str = Query("este_mes"),
    desde: str | None = None,
    hasta: str | None = None,
    mes: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Los gastos (reales, según la regla contable) de una categoría o de un
    comercio dentro del periodo, más recientes primero."""
    if not categoria and not comercio and not fuente:
        raise HTTPException(status_code=422, detail="Indica una categoría, un comercio o una fuente")
    rango = _rango(periodo, desde, hasta, mes)
    movs = _cargar(db, usuario, rango)
    clave = inf.clave_comercio(comercio) if comercio else None
    filas = [
        m for m in movs
        if m["tipo"] == ("income" if tipo == "ingreso" else "expense") and inf.en_rango(m, rango)
        and (categoria is None or m["categoria"] == categoria)
        and (clave is None or inf.clave_comercio(m["descripcion"]) == clave)
        and (fuente is None or (inf.clave_comercio(m["descripcion"]) or inf.clave_comercio(m["categoria"] or "Otros")) == fuente)
    ]
    filas.sort(key=lambda m: m["fecha"], reverse=True)
    total = sum(m["monto"] for m in filas)
    return {
        "categoria": categoria,
        "comercio": comercio,
        "etiqueta": rango["etiqueta"],
        "total": round(total),
        "cantidad": len(filas),
        "truncado": len(filas) > MAX_MOVS_CATEGORIA,
        "movimientos": [
            {"id": m["id"], "fecha": m["fecha"].isoformat(), "descripcion": m.get("titulo") or m["descripcion"],
             "titulo": m.get("titulo") or None, "monto": round(m["monto"]), "categoria": m["categoria"],
             "subcategoria": m.get("subcategoria")}
            for m in filas[:MAX_MOVS_CATEGORIA]
        ],
    }


@router.get("/gasto/subcategorias")
def desglose_por_subcategoria(
    categoria: str,
    periodo: str = Query("este_mes"),
    desde: str | None = None,
    hasta: str | None = None,
    mes: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Desglose de UNA categoría por subcategoría (incluye «Sin subcategoría»). La suma es exactamente
    el total de la categoría en el informe: las subcategorías solo detallan, no cambian la cifra."""
    rango = _rango(periodo, desde, hasta, mes)
    movs = _cargar(db, usuario, rango)
    filas = [m for m in movs if m["tipo"] == "expense" and inf.en_rango(m, rango) and m["categoria"] == categoria]
    grupos: dict[str | None, list[float]] = {}
    for m in filas:
        g = grupos.setdefault(m.get("subcategoria") or None, [0.0, 0])
        g[0] += m["monto"]
        g[1] += 1
    total = sum(g[0] for g in grupos.values())
    lista = [{"subcategoria": k, "total": round(g[0]), "cantidad": g[1],
              "porcentaje": round(100 * g[0] / total) if total else 0}
             for k, g in grupos.items()]
    # Las subcategorías de mayor a menor y «Sin subcategoría» siempre al final.
    lista.sort(key=lambda x: (x["subcategoria"] is None, -x["total"]))
    return {"categoria": categoria, "etiqueta": rango["etiqueta"], "total": round(total),
            "tiene_subcategorias": any(x["subcategoria"] for x in lista), "subcategorias": lista}


@router.get("/evolucion-categorias")
def evolucion_categorias(
    meses: int = Query(6, ge=1, le=inf.MAX_MESES_CATEGORIAS),
    categoria: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Gasto mensual por categoría de los últimos `meses` meses (el mes en curso cuenta como parcial). Misma regla
    única que los reportes: sin traslados ni pagos de tarjeta, en moneda base. Con `categoria` agrega la serie por
    subcategoría. Los meses sin gasto valen 0. Liviano: una sola lectura, cacheable en el cliente."""
    hoy = ahora_co()
    a, m = inf.sumar_meses(hoy.year, hoy.month, -(meses - 1))
    ini = inf.inicio_mes(a, m)
    movs = cargar_movs_efectivos(db, usuario.id, ini, inf.inicio_mes(*inf.sumar_meses(hoy.year, hoy.month, 1)))
    out = inf.evolucion_categorias(movs, (hoy.year, hoy.month), meses, categoria, inf.inicio_mes(hoy.year, hoy.month))
    if isinstance(out, dict):
        out["moneda_base"], out["monedas_sin_tasa"] = movs.base, list(movs.sin_tasa)
    return out


@router.get("/meses")
def meses(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Meses que tienen movimientos (para navegar el resumen mensual) y el último."""
    todos = cargar_movs_efectivos(db, usuario.id)
    lista = inf.meses_con_datos(todos)
    return {
        "mes_actual": inf.clave_mes(ahora_co()),
        "meses": lista,
        "ultimo_con_datos": lista[-1]["mes"] if lista else None,
    }


def _disponible_dia_a_dia(db: Session, usuario_id: str, dias: list[str]) -> tuple[int, list[int]]:
    """(disponible hoy, disponible al cierre de cada día). «Disponible» = cuentas que no son tarjeta de crédito,
    igual que el saldo de Inicio; el movimiento de cada día usa la regla única del saldo (contabilidad.delta_saldo)."""
    ids = list(cuentas_ids_accesibles(db, usuario_id))
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids)).all() if ids else []
    propias = {c.id: c for c in cuentas if c.tipo != "credito"}
    conv = ConvertidorBase.de_usuario(db, usuario_id)
    actual = sum(conv.contar(c.saldo or 0, c.moneda or "COP") for c in propias.values())
    if not dias or not propias:
        return round(actual), [round(actual)] * len(dias)
    inicio = datetime.fromisoformat(dias[0])
    delta: dict[str, float] = {}
    for m in db.query(Movimiento).filter(Movimiento.cuenta_id.in_(list(propias)), Movimiento.fecha >= inicio).all():
        k = m.fecha.date().isoformat()
        delta[k] = delta.get(k, 0.0) + conv.contar(delta_saldo(m), propias[m.cuenta_id].moneda or "COP")
    return round(actual), inf.disponible_por_dia(dias, delta, actual)


@router.get("/diario")
def diario(
    desde: str | None = None,
    hasta: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Gasto de cada día del rango (con ceros). Por defecto, las últimas 5 semanas."""
    hoy = ahora_co()
    if not desde and not hasta:
        fin = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
        desde, hasta = (fin - timedelta(days=34)).date().isoformat(), fin.date().isoformat()
    rango = _rango("rango", desde or hasta, hasta or desde, None)
    if (rango["hasta"] - rango["desde"]).days > MAX_DIAS_DIARIO:
        raise HTTPException(status_code=422, detail="Elige un rango de máximo 400 días")
    movs = cargar_movs_efectivos(db, usuario.id, rango["desde"], rango["hasta"])
    dias = inf.gasto_diario(movs, rango)
    disponible_hoy, disp = _disponible_dia_a_dia(db, usuario.id, [d["dia"] for d in dias])
    for d, v in zip(dias, disp):
        d["disponible"] = v
    return {
        "desde": dias[0]["dia"] if dias else desde,
        "hasta": dias[-1]["dia"] if dias else hasta,
        "total": sum(d["gasto"] for d in dias),
        "disponible_hoy": disponible_hoy,
        "dias": dias,
        "moneda_base": movs.base,
        "monedas_sin_tasa": list(movs.sin_tasa),
    }


@router.get("/no-se-cuenta")
def no_se_cuenta(
    periodo: str = Query("este_mes"),
    desde: str | None = None,
    hasta: str | None = None,
    mes: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Lo que NO se cuenta como ingreso ni gasto en el periodo (traslados entre tus cuentas, pagos de
    tarjeta, ajustes de saldo, aportes a metas y posibles traslados) para que la persona lo verifique."""
    rango = _rango(periodo, desde, hasta, mes)
    movs = _cargar(db, usuario, rango)
    return inf.no_se_cuenta(movs, rango)


@router.get("/resumen")
def resumen(
    periodo: str = Query("este_mes"),
    desde: str | None = None,
    hasta: str | None = None,
    mes: str | None = None,
    agrupar: str | None = Query(None, pattern="^(dia|semana|mes)$"),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Resumen del periodo en una sola lectura: totales y comparación contra el periodo anterior equivalente,
    flujo neto por día/semana/mes, tasa de ahorro mes a mes, ingresos por fuente, presupuesto contra gasto real y
    hallazgos. Todo con la regla única de contabilidad (sin traslados ni pagos de tarjeta)."""
    verificar_limite(f"informes-resumen:{usuario.id}", LIMITE_RESUMEN_POR_MINUTO, 60,
                     "Estás consultando el resumen muy seguido. Intenta de nuevo en {espera}.")
    hoy = ahora_co()
    rango = _rango(periodo, desde, hasta, mes)
    anterior = inf.periodo_anterior(rango)
    n_meses = res.meses_de_la_serie(rango)
    ultimo = rango["hasta"] - timedelta(days=1)
    a, m = inf.sumar_meses(ultimo.year, ultimo.month, -(n_meses - 1))
    ini = min(rango["desde"], anterior["desde"], inf.inicio_mes(a, m))
    movs = cargar_movs_efectivos(db, usuario.id, ini, rango["hasta"])

    base = inf.ingresos_gastos(movs, rango, anterior, n_meses)
    informe = inf.informe_gasto(movs, rango, anterior)
    presupuestos = [
        {"categoria": p.categoria, "limite": p.limite, "periodo": p.periodo, "alerta_pct": p.alerta_pct,
         "sobre_ajuste": p.sobre_ajuste, "activo": p.activo}
        for p in db.query(Presupuesto).filter(Presupuesto.usuario_id == usuario.id).all()
    ]
    fuentes = res.ingresos_por_fuente(movs, rango, anterior)
    presupuesto = res.presupuesto_vs_real(movs, presupuestos, rango, hoy)
    base["periodo"] = periodo
    base["flujo"] = res.flujo_neto(movs, rango, agrupar)
    base["fuentes"] = fuentes
    base["tasa_serie"] = res.resumen_tasa(base["meses"])
    base["presupuesto"] = presupuesto
    base["hallazgos"] = res.hallazgos(base, informe, presupuesto, rango["etiqueta"])
    base["moneda_base"], base["monedas_sin_tasa"] = movs.base, list(movs.sin_tasa)
    base["en_curso"] = (rango["hasta"] - timedelta(days=1)).date() >= hoy.date()
    return base
