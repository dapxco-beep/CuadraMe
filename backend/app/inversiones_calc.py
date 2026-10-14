"""
Cálculos PUROS de Inversiones (sin base de datos ni red). Reutiliza xirr de
patrimonio_calc. Información educativa, no es asesoría de inversión.

Método de costo: PROMEDIO PONDERADO (el más usado en Colombia y el más simple de
explicar). Cada compra suma (cantidad*precio + comisión) al costo total; una venta
retira costo en proporción a lo vendido (cantidad vendida * costo promedio), y la
diferencia con lo recibido (neto de comisión) es la ganancia REALIZADA. Una venta
no cambia el costo promedio de lo que queda.
"""
from datetime import datetime
from typing import Optional

from app import patrimonio_calc as pc

AVISO = "Información educativa, no es asesoría de inversión."
MIN_DIAS_TIR = 30  # anualizar menos de un mes da cifras absurdas
TIPOS_TX = ("compra", "venta", "dividendo", "comision", "aporte", "retiro")
TIPOS_POSICION = ("accion", "etf", "fondo", "cripto", "cdt", "fiducia")
CLASE_PATRIMONIO = {"accion": "accion", "etf": "etf", "cripto": "cripto",
                    "fondo": "fondo", "fiducia": "fondo", "cdt": "fondo"}


def _g(t, k, d=0.0):
    v = t.get(k, d) if isinstance(t, dict) else getattr(t, k, d)
    return d if v is None else v


def resumen_transacciones(txs: list) -> dict:
    """Recorre las transacciones en orden de fecha y devuelve cantidad, costo total,
    costo promedio, ganancia realizada, dividendos, comisiones, aportado y retirado
    (todo en la moneda de la posición). Una venta mayor a lo que hay se limita a lo
    disponible (dato inconsistente: no se inventan unidades negativas)."""
    cantidad = costo = realizada = dividendos = comisiones = aportado = retirado = 0.0
    for t in sorted(txs, key=lambda x: _g(x, "fecha", datetime.min)):
        tipo, q, p, com, monto = _g(t, "tipo", ""), _g(t, "cantidad"), _g(t, "precio"), _g(t, "comision"), _g(t, "monto")
        if tipo == "compra":
            gasto = q * p + com
            cantidad += q
            costo += gasto
            aportado += gasto
            comisiones += com
        elif tipo == "venta":
            q = min(q, cantidad)
            prom = costo / cantidad if cantidad else 0.0
            recibido = q * p - com
            realizada += recibido - q * prom
            costo -= q * prom
            cantidad -= q
            retirado += recibido
            comisiones += com
            if cantidad <= 1e-12:
                cantidad, costo = 0.0, 0.0
        elif tipo == "dividendo":
            dividendos += monto
        elif tipo == "comision":
            comisiones += monto
            costo += monto
        elif tipo == "aporte":
            aportado += monto
        elif tipo == "retiro":
            retirado += monto
    return {
        "cantidad": cantidad, "costo_total": costo,
        "costo_promedio": costo / cantidad if cantidad else 0.0,
        "realizada": realizada, "dividendos": dividendos, "comisiones": comisiones,
        "aportado": aportado, "retirado": retirado,
    }


def flujos_tir(txs: list) -> list:
    """[(fecha, monto)] desde el bolsillo del usuario: compras y aportes negativos,
    ventas, retiros y dividendos positivos (es lo que mira la TIR/XIRR)."""
    out = []
    for t in txs:
        tipo, f = _g(t, "tipo", ""), _g(t, "fecha", None)
        q, p, com, m = _g(t, "cantidad"), _g(t, "precio"), _g(t, "comision"), _g(t, "monto")
        if tipo == "compra":
            out.append((f, -(q * p + com)))
        elif tipo == "venta":
            out.append((f, q * p - com))
        elif tipo in ("dividendo", "retiro"):
            out.append((f, m))
        elif tipo in ("aporte", "comision"):
            out.append((f, -m))
    return [x for x in out if x[0] is not None and x[1]]


def tir(flujos: list, valor_actual: float, hoy: datetime, min_dias: int = MIN_DIAS_TIR) -> Optional[float]:
    """TIR efectiva anual (money-weighted) en %. None si no hay datos suficientes:
    sin flujos, todos del mismo signo, o menos de `min_dias` de historia."""
    if not flujos:
        return None
    todos = list(flujos) + ([(hoy, valor_actual)] if valor_actual else [])
    if (hoy - min(f for f, _ in todos)).days < min_dias:
        return None
    r = pc.xirr(todos)
    return None if r is None else r * 100.0


def valor_y_ganancia(cantidad: float, precio: Optional[float], costo_total: float) -> dict:
    """Ganancia NO realizada. Sin precio: valor None y sin ganancia (no se inventa)."""
    if precio is None:
        return {"valor": None, "no_realizada": None, "no_realizada_pct": None}
    valor = cantidad * precio
    g = valor - costo_total
    return {"valor": valor, "no_realizada": g, "no_realizada_pct": (g / costo_total * 100) if costo_total else None}


def rentabilidad_total(valor: float, costo_total: float, realizada: float, dividendos: float,
                       aportado: float) -> dict:
    """Ganancia total = no realizada + realizada + dividendos; % sobre lo aportado."""
    total = (valor - costo_total) + realizada + dividendos
    return {"total": total, "total_pct": (total / aportado * 100) if aportado else None}


def rentabilidad_periodo(valor_ini: float, valor_fin: float, flujos: list) -> Optional[float]:
    """Rentabilidad de un periodo en % por Dietz modificado. `flujos`: [(peso, monto)]
    con peso = fracción del periodo que el flujo estuvo invertido (0..1) y monto
    positivo si ENTRA al portafolio (aporte) o negativo si sale (retiro)."""
    neto = sum(m for _, m in flujos)
    base = valor_ini + sum(w * m for w, m in flujos)
    if base <= 0:
        return None
    return (valor_fin - valor_ini - neto) / base * 100.0


def periodo_dietz(valor_ini: float, valor_fin: float, desde: datetime, hasta: datetime, flujos_fechados: list):
    """Dietz modificado con flujos [(fecha, monto_que_entra)] dentro de (desde, hasta]."""
    total = (hasta - desde).total_seconds()
    if total <= 0:
        return None
    pesos = [((hasta - f).total_seconds() / total, m) for f, m in flujos_fechados if desde < f <= hasta]
    return rentabilidad_periodo(valor_ini, valor_fin, pesos)


# --- moneda ---------------------------------------------------------------------

class ProveedorFX:
    """Contrato intercambiable: pesos_por_unidad(moneda) -> float | None."""

    def pesos_por_unidad(self, moneda: str) -> Optional[float]:
        raise NotImplementedError


class FXManual(ProveedorFX):
    """Respaldo manual / pruebas: {"USD": 4000}."""

    def __init__(self, tasas: dict):
        self.tasas = tasas

    def pesos_por_unidad(self, moneda: str) -> Optional[float]:
        return 1.0 if moneda == "COP" else self.tasas.get(moneda)


def convertir(monto: Optional[float], moneda: str, base: str = "COP", fx: Optional[ProveedorFX] = None,
              tipo_cambio: Optional[float] = None) -> Optional[float]:
    """Convierte a la moneda base del usuario (hoy COP). `tipo_cambio` explícito
    (base por unidad) manda sobre el proveedor. None si no hay tasa: nunca se suma
    un monto en otra moneda como si fuera COP."""
    if monto is None:
        return None
    if moneda == base:
        return monto
    tasa = tipo_cambio if tipo_cambio else (fx.pesos_por_unidad(moneda) if fx else None)
    return monto * tasa if tasa else None


# --- agrupación y alertas -------------------------------------------------------

def agrupar(filas: list, clave: str, valor: str = "valor_cop") -> list:
    """[{clase, valor, pct}] de mayor a menor por `clave` (ignora vacíos o <= 0)."""
    acc: dict = {}
    for f in filas:
        v = f.get(valor)
        if v:
            k = f.get(clave) or "sin dato"
            acc[k] = acc.get(k, 0) + v
    return pc.distribucion(acc)


def mayor_concentracion(filas: list, valor: str = "valor_cop") -> Optional[dict]:
    """La posición con más peso: {nombre, pct, valor} o None si no hay valores."""
    con = [f for f in filas if (f.get(valor) or 0) > 0]
    total = sum(f[valor] for f in con)
    if not con or not total:
        return None
    top = max(con, key=lambda f: f[valor])
    return {"nombre": top.get("nombre"), "pct": top[valor] / total * 100, "valor": top[valor]}


# --- bienes (inmueble, vehículo, otros) ------------------------------------------

def valor_vehiculo_estimado(compra: float, fecha_compra: datetime, hoy: datetime, depreciacion_pct: float) -> float:
    """Estimación simple: pierde `depreciacion_pct` % de su valor cada año (saldo
    decreciente). Es una estimación, no un avalúo."""
    anios = max(0.0, (hoy - fecha_compra).days / 365.0)
    return compra * (1 - depreciacion_pct / 100.0) ** anios


def hace_cuanto(fecha: Optional[datetime], hoy: datetime) -> Optional[str]:
    """«hoy», «hace 3 días», «hace 2 meses»: texto llano para «actualizado hace X»."""
    if not fecha:
        return None
    d = (hoy - fecha).days
    if d <= 0:
        return "hoy"
    if d == 1:
        return "hace 1 día"
    if d < 30:
        return f"hace {d} días"
    m = d // 30
    return "hace 1 mes" if m == 1 else f"hace {m} meses" if m < 12 else "hace más de un año"


def extras_bien(clase: str, valor: float, costo: Optional[float], precio_fecha: Optional[datetime],
                arriendo_mensual: Optional[float], hoy: datetime) -> dict:
    """Datos propios de inmueble/vehículo/otro: valorización o depreciación (NO es
    'rentabilidad de mercado'), rentabilidad por arriendo y recordatorio de actualizar."""
    out: dict = {"actualizado_hace": hace_cuanto(precio_fecha, hoy)}
    if costo:
        out["variacion_valor"] = valor - costo
        out["variacion_pct"] = (valor - costo) / costo * 100
        out["variacion_tipo"] = "valorizacion" if valor >= costo else "depreciacion"
    umbral = 180 if clase == "inmueble" else 365
    out["sugerir_actualizar"] = bool(precio_fecha) and (hoy - precio_fecha).days >= umbral
    if clase == "inmueble" and arriendo_mensual and valor:
        out["arriendo_anual_pct"] = arriendo_mensual * 12 / valor * 100
    return out
