"""
Interfaz para precios AUTOMÁTICOS de activos (hoy todo es manual).

Para conectar una fuente real (Yahoo, CoinGecko, valor de unidad de fondos de
la SFC...) solo hay que:
  1. Crear una clase que herede de `ProveedorPrecios` e implemente `precio()`.
  2. Registrarla en `PROVEEDORES` con un nombre.
  3. Poner ese nombre en `activos_patrimonio.fuente_precio` del activo.
POST /patrimonio/cron/actualizar-precios ya recorre los activos con fuente
distinta de "manual" y llama a `obtener_precio`. Hoy no hay proveedores
registrados, así que no hace nada ni sale a la red.
"""
from datetime import datetime
from typing import Optional


class ProveedorPrecios:
    """Contrato: devolver (precio_por_unidad, fecha_del_precio) o None si no hay dato."""

    def precio(self, ticker: str, clase: str, moneda: str) -> Optional[tuple]:
        raise NotImplementedError


PROVEEDORES: dict = {}


def obtener_precio(fuente: str, ticker: str, clase: str, moneda: str) -> Optional[tuple]:
    proveedor = PROVEEDORES.get(fuente)
    if not proveedor or not ticker:
        return None
    try:
        return proveedor.precio(ticker, clase, moneda)
    except Exception:
        return None
