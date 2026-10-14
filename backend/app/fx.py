"""
Conversión de monedas para reportes y patrimonio multi-moneda.

Tres piezas desacopladas:
  1. PROVEEDOR de tasas (intercambiable): `proveedor_abierto` usa open.er-api.com (sin llave).
     Se cambia con `usar_proveedor(funcion)`; la función recibe la moneda base y devuelve
     {"MONEDA": tasa}, donde 1 base = tasa unidades de MONEDA.
  2. RESPALDO MANUAL: `fijar_tasa_manual("USD", "COP", 4000.0)` por si el proveedor cae
     o la persona prefiere su propio tipo de cambio (tiene prioridad sobre el proveedor).
  3. FECHA del tipo de cambio: `convertir_con_fecha` devuelve (monto, fecha) para mostrarla.

Cache en memoria de 6 horas por moneda base. `convertir_a_cop` se conserva (lo usan
muchos módulos) y delega en `convertir`.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

CACHE_TTL_SEGUNDOS = 6 * 3600
# Si el proveedor está caído no reintentar en cada request (cada reporte esperaría 10 s).
REINTENTO_MINIMO_SEGUNDOS = 60

# Referencia aproximada SOLO cuando no hay proveedor ni caché ni tasa manual (1 USD = ...).
# No es un dato de mercado: evita sumar pesos con dólares sin convertir. Se avisa en el log.
_USD_APROX = {"USD": 1.0, "COP": 4300.0, "MXN": 18.5, "CLP": 950.0, "PEN": 3.7, "ARS": 1000.0,
              "UYU": 40.0, "CRC": 510.0, "BRL": 5.5, "PAB": 1.0, "EUR": 0.92}

_CACHE: dict = {}  # base -> {"tasas", "actualizado_en", "ultimo_intento", "fecha"}
_MANUALES: dict = {}  # (origen, destino) -> (tasa, fecha_iso)


def proveedor_abierto(base: str) -> dict[str, float]:
    resp = httpx.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10)
    resp.raise_for_status()
    return resp.json().get("rates", {}) or {}


_PROVEEDOR: Callable[[str], dict[str, float]] = proveedor_abierto


def usar_proveedor(funcion: Callable[[str], dict[str, float]] | None) -> None:
    """Cambia el proveedor de tasas (None = el de siempre). Limpia la caché."""
    global _PROVEEDOR
    _PROVEEDOR = funcion or proveedor_abierto
    _CACHE.clear()


def fijar_tasa_manual(origen: str, destino: str, tasa: float, fecha: str | None = None) -> None:
    if tasa <= 0:
        raise ValueError("La tasa debe ser mayor que cero.")
    _MANUALES[(origen.upper(), destino.upper())] = (float(tasa), fecha or datetime.now(timezone.utc).date().isoformat())


def borrar_tasas_manuales() -> None:
    _MANUALES.clear()


def _tasas_de(base: str) -> tuple[dict[str, float], str | None]:
    ahora = time.time()
    c = _CACHE.get(base)
    if c and c["tasas"] and (ahora - c["actualizado_en"]) < CACHE_TTL_SEGUNDOS:
        return c["tasas"], c["fecha"]
    if c and (ahora - c["ultimo_intento"]) < REINTENTO_MINIMO_SEGUNDOS:
        return c["tasas"] or {}, c["fecha"]
    entrada = c or {"tasas": None, "actualizado_en": 0, "ultimo_intento": 0, "fecha": None}
    entrada["ultimo_intento"] = ahora
    _CACHE[base] = entrada
    try:
        tasas = _PROVEEDOR(base)
        if tasas:
            entrada.update(tasas=tasas, actualizado_en=ahora, fecha=datetime.now(timezone.utc).date().isoformat())
    except Exception:
        logger.warning("fx: no se pudo obtener tasas para %s, usando caché/respaldo", base)
    return entrada["tasas"] or {}, entrada["fecha"]


def tasa(origen: str, destino: str) -> tuple[float | None, str | None, str]:
    """(tasa, fecha ISO, fuente) para 1 origen -> destino. fuente: igual | manual | proveedor | aproximada | ninguna."""
    o, d = (origen or "").upper(), (destino or "").upper()
    if o == d:
        return 1.0, None, "igual"
    if (o, d) in _MANUALES:
        t, f = _MANUALES[(o, d)]
        return t, f, "manual"
    if (d, o) in _MANUALES:
        t, f = _MANUALES[(d, o)]
        return 1 / t, f, "manual"
    tasas, fecha = _tasas_de(d)  # base = destino: tasas[o] = unidades de origen por 1 destino
    if tasas.get(o):
        return 1 / tasas[o], fecha, "proveedor"
    if o in _USD_APROX and d in _USD_APROX:
        return _USD_APROX[d] / _USD_APROX[o], None, "aproximada"
    return None, None, "ninguna"


def convertir_con_fecha(monto: float, origen: str, destino: str) -> tuple[float, str | None, str]:
    t, fecha, fuente = tasa(origen, destino)
    if t is None:
        logger.warning("fx: sin tasa %s->%s, se deja el monto SIN convertir", origen, destino)
        return monto, None, "ninguna"
    return monto * t, fecha, fuente


def convertir(monto: float, origen: str, destino: str) -> float:
    return convertir_con_fecha(monto, origen, destino)[0]


def convertir_a_cop(monto: float, moneda_origen: str) -> float:
    if moneda_origen == "COP":
        return monto
    return convertir(monto, moneda_origen, "COP")
