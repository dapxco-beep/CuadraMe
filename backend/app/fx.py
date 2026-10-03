"""
Conversión de monedas para reportes multi-moneda. Usa una API pública sin
key (exchangerate-api.com endpoint abierto) y cachea las tasas en memoria
por 6 horas — los reportes no necesitan tasas al segundo.
"""
import logging
import time

import httpx

logger = logging.getLogger(__name__)

_CACHE: dict = {"tasas": None, "actualizado_en": 0, "ultimo_intento": 0}
CACHE_TTL_SEGUNDOS = 6 * 3600
# Si la API está caída, no reintentar en cada request (cada reporte esperaría
# hasta 10s de timeout): esperar al menos 1 minuto entre intentos fallidos,
# sirviendo la caché vieja (o el fallback fijo) mientras tanto.
REINTENTO_MINIMO_SEGUNDOS = 60


def _obtener_tasas() -> dict[str, float]:
    ahora = time.time()
    if _CACHE["tasas"] and (ahora - _CACHE["actualizado_en"]) < CACHE_TTL_SEGUNDOS:
        return _CACHE["tasas"]

    if (ahora - _CACHE["ultimo_intento"]) < REINTENTO_MINIMO_SEGUNDOS:
        return _CACHE["tasas"] or {"COP": 1, "USD": 0.00023, "EUR": 0.00021}

    _CACHE["ultimo_intento"] = ahora
    try:
        resp = httpx.get("https://open.er-api.com/v6/latest/COP", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        tasas = data.get("rates", {})
        if tasas:
            _CACHE["tasas"] = tasas
            _CACHE["actualizado_en"] = ahora
            return tasas
    except Exception:
        logger.warning("fx: no se pudo obtener tasas de open.er-api.com, usando caché/fallback")

    # Fallback si la API falla y no hay caché previo: tasas aproximadas fijas.
    return _CACHE["tasas"] or {"COP": 1, "USD": 0.00023, "EUR": 0.00021}


def convertir_a_cop(monto: float, moneda_origen: str) -> float:
    if moneda_origen == "COP":
        return monto
    tasas = _obtener_tasas()
    tasa_cop_a_origen = tasas.get(moneda_origen)
    if not tasa_cop_a_origen:
        logger.warning(
            "fx: no hay tasa de cambio para %s, se suma el monto SIN convertir (%s)",
            moneda_origen, monto,
        )
        return monto
    return monto / tasa_cop_a_origen
