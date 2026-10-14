"""
Informes: 'en qué gasto mi plata' con periodo configurable, meses con datos
(para navegar el resumen mensual) y gasto diario (mapa de calor). Todo con la
regla contable: sin pagos de tarjeta ni traslados entre cuentas propias.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import informe as inf
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.informe_datos import cargar_movs_efectivos
from app.utiles import ahora_co

router = APIRouter(prefix="/informes", tags=["informes"])

MAX_MOVS_CATEGORIA = 300
MAX_DIAS_DIARIO = 400


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
    if not informe["hay_datos"]:
        # Ayuda para que la pantalla ofrezca saltar al último mes con gastos.
        todos = cargar_movs_efectivos(db, usuario.id)
        informe["ultimo_mes_con_datos"] = inf.ultimo_mes_con_datos(todos)
    return informe


@router.get("/gasto/movimientos")
def movimientos_de_categoria(
    categoria: str | None = None,
    comercio: str | None = None,
    periodo: str = Query("este_mes"),
    desde: str | None = None,
    hasta: str | None = None,
    mes: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Los gastos (reales, según la regla contable) de una categoría o de un
    comercio dentro del periodo, más recientes primero."""
    if not categoria and not comercio:
        raise HTTPException(status_code=422, detail="Indica una categoría o un comercio")
    rango = _rango(periodo, desde, hasta, mes)
    movs = _cargar(db, usuario, rango)
    clave = inf.clave_comercio(comercio) if comercio else None
    filas = [
        m for m in movs
        if m["tipo"] == "expense" and inf.en_rango(m, rango)
        and (categoria is None or m["categoria"] == categoria)
        and (clave is None or inf.clave_comercio(m["descripcion"]) == clave)
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
            {"id": m["id"], "fecha": m["fecha"].isoformat(), "descripcion": m["descripcion"],
             "monto": round(m["monto"]), "categoria": m["categoria"]}
            for m in filas[:MAX_MOVS_CATEGORIA]
        ],
    }


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
    return {
        "desde": dias[0]["dia"] if dias else desde,
        "hasta": dias[-1]["dia"] if dias else hasta,
        "total": sum(d["gasto"] for d in dias),
        "dias": dias,
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
