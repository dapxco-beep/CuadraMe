"""
Precios por TICKER para Inversiones: proveedores intercambiables, caché con TTL y
topes de peticiones (cuidan el plan gratuito). Ver docs/INVERSIONES_DISENO.md.

Cadena: proveedor principal -> respaldo -> precio manual (lo pone el usuario).
Las CLAVES se leen SOLO de variables de entorno (nunca van en el código):
  TWELVEDATA_API_KEY, ALPHAVANTAGE_API_KEY, COINGECKO_API_KEY (opcional),
  INVERSIONES_YAHOO_ACTIVO=1 (apagado por defecto: endpoint NO oficial, riesgo de ToS),
  INVERSIONES_TTL_MIN (15), INVERSIONES_TOPE_GLOBAL_DIA (700), INVERSIONES_TOPE_USUARIO_DIA (20).
Sin clave configurada el proveedor no se usa: la app sigue funcionando con precio manual.
"""
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models_inversiones import ConsultaPrecio, Cotizacion
from app.precios import ProveedorPrecios

TTL_MIN_DEFECTO = 15
REINTENTO_SIN_DATOS_HORAS = 6  # un ticker que no existe no se vuelve a pedir en cada pasada
EN_VIVO_MAX_MIN = 20

# Sufijo de mercado -> bolsa para Twelve Data / sufijo de Alpha Vantage / sufijo de Yahoo.
# Cobertura de bolsas latinoamericanas en el plan gratuito: NO CONFIRMADA (ver docs).
BOLSA_TWELVE = {"CL": "BVC", "MX": "BMV", "SA": "BVMF", "SN": "BCS", "BA": "BCBA", "US": ""}
SUFIJO_ALPHA = {"SA": ".SAO", "MX": ".MEX", "US": ""}
SUFIJO_YAHOO = {"CL": ".CL", "MX": ".MX", "SA": ".SA", "SN": ".SN", "BA": ".BA", "US": ""}
IDS_COINGECKO = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "USDT": "tether", "USDC": "usd-coin",
                 "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin"}


def _env(nombre: str, defecto: str = "") -> str:
    return (os.environ.get(nombre) or defecto).strip()


def _num(v) -> Optional[float]:
    try:
        n = float(v)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _fecha(txt) -> datetime:
    try:
        return datetime.fromisoformat(str(txt).replace("Z", "")[:19])
    except ValueError:
        return datetime.utcnow()


class ProveedorCotizacion(ProveedorPrecios):
    """Contrato: cotizar() -> {precio, moneda, fecha, anterior?} o None. La clase
    base `ProveedorPrecios` queda para compatibilidad con el módulo Patrimonio."""
    nombre = ""

    def disponible(self) -> bool:
        return True

    def cotizar(self, ticker: str, mercado: str, tipo: str) -> Optional[dict]:
        raise NotImplementedError

    def precio(self, ticker, clase, moneda):  # contrato heredado
        c = self.cotizar(ticker, "", clase)
        return (c["precio"], c["fecha"]) if c else None


class TwelveData(ProveedorCotizacion):
    nombre = "twelvedata"

    def disponible(self):
        return bool(_env("TWELVEDATA_API_KEY"))

    def cotizar(self, ticker, mercado, tipo):
        params = {"symbol": ticker, "apikey": _env("TWELVEDATA_API_KEY")}
        if BOLSA_TWELVE.get(mercado):
            params["exchange"] = BOLSA_TWELVE[mercado]
        j = httpx.get("https://api.twelvedata.com/quote", params=params, timeout=10).json()
        precio = _num(j.get("close"))
        if j.get("status") == "error" or precio is None:
            return None
        return {"precio": precio, "moneda": j.get("currency") or "", "fecha": _fecha(j.get("datetime")),
                "anterior": _num(j.get("previous_close"))}


class AlphaVantage(ProveedorCotizacion):
    nombre = "alphavantage"

    def disponible(self):
        return bool(_env("ALPHAVANTAGE_API_KEY"))

    def cotizar(self, ticker, mercado, tipo):
        simbolo = ticker + SUFIJO_ALPHA.get(mercado, "")
        j = httpx.get("https://www.alphavantage.co/query", timeout=10, params={
            "function": "GLOBAL_QUOTE", "symbol": simbolo, "apikey": _env("ALPHAVANTAGE_API_KEY")}).json()
        q = j.get("Global Quote") or {}
        precio = _num(q.get("05. price"))
        if precio is None:
            return None
        return {"precio": precio, "moneda": "", "fecha": _fecha(q.get("07. latest trading day")),
                "anterior": _num(q.get("08. previous close"))}


class CoinGecko(ProveedorCotizacion):
    nombre = "coingecko"

    def cotizar(self, ticker, mercado, tipo):
        ident = IDS_COINGECKO.get(ticker.upper(), ticker.lower())
        cab = {"x-cg-demo-api-key": _env("COINGECKO_API_KEY")} if _env("COINGECKO_API_KEY") else {}
        j = httpx.get("https://api.coingecko.com/api/v3/simple/price", headers=cab, timeout=10, params={
            "ids": ident, "vs_currencies": "usd", "include_last_updated_at": "true"}).json()
        d = j.get(ident) or {}
        precio = _num(d.get("usd"))
        if precio is None:
            return None
        ts = d.get("last_updated_at")
        return {"precio": precio, "moneda": "USD",
                "fecha": datetime.utcfromtimestamp(ts) if ts else datetime.utcnow(), "anterior": None}


class YahooNoOficial(ProveedorCotizacion):
    """Endpoint NO oficial. Apagado por defecto: sus términos no autorizan este uso
    comercial y puede cambiar o bloquear sin aviso. Solo con INVERSIONES_YAHOO_ACTIVO=1."""
    nombre = "yahoo"

    def disponible(self):
        return _env("INVERSIONES_YAHOO_ACTIVO") == "1"

    def cotizar(self, ticker, mercado, tipo):
        simbolo = ticker + SUFIJO_YAHOO.get(mercado, "")
        r = httpx.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}", timeout=10,
                      headers={"User-Agent": "Mozilla/5.0"}, params={"interval": "1d", "range": "5d"})
        meta = (((r.json().get("chart") or {}).get("result") or [{}])[0]).get("meta") or {}
        precio = _num(meta.get("regularMarketPrice"))
        if precio is None:
            return None
        ts = meta.get("regularMarketTime")
        return {"precio": precio, "moneda": meta.get("currency") or "",
                "fecha": datetime.utcfromtimestamp(ts) if ts else datetime.utcnow(),
                "anterior": _num(meta.get("chartPreviousClose"))}


PROVEEDORES_COTIZACION: dict = {p.nombre: p for p in (TwelveData(), AlphaVantage(), CoinGecko(), YahooNoOficial())}
# Orden de intento por tipo: principal y respaldo (el manual es el último recurso, lo pone el usuario).
CADENA = {"cripto": ["coingecko", "twelvedata", "yahoo"], "defecto": ["twelvedata", "alphavantage", "yahoo"]}


# ---------------------------------------------------------------- límites

def _clave(prefijo: str, dia: str) -> str:
    return f"{prefijo}:{dia}"


def _usado(db: Session, clave: str) -> int:
    f = db.get(ConsultaPrecio, clave)
    return int(f.cantidad) if f else 0


def _contar(db: Session, clave: str):
    f = db.get(ConsultaPrecio, clave)
    if not f:
        f = ConsultaPrecio(clave=clave, cantidad=0)
        db.add(f)
    f.cantidad = (f.cantidad or 0) + 1


def tope_global() -> int:
    return int(_env("INVERSIONES_TOPE_GLOBAL_DIA", "700") or 700)


def tope_usuario() -> int:
    return int(_env("INVERSIONES_TOPE_USUARIO_DIA", "20") or 20)


def ttl_min() -> int:
    return int(_env("INVERSIONES_TTL_MIN", str(TTL_MIN_DEFECTO)) or TTL_MIN_DEFECTO)


def estado_precio(fecha: Optional[datetime], fuente: str, hoy: datetime) -> dict:
    """{estado, mensaje}: en_vivo | retrasado | manual | sin_datos, con texto honesto."""
    if fecha is None:
        return {"estado": "sin_datos", "mensaje": "Sin datos para este ticker: usa un precio manual"}
    dias = (hoy - fecha).days
    edad = "" if dias <= 0 else f"Precio de hace {dias} día" + ("s" if dias != 1 else "")
    if fuente == "manual":
        return {"estado": "manual", "mensaje": edad or "Precio manual de hoy"}
    if (hoy - fecha) <= timedelta(minutes=EN_VIVO_MAX_MIN):
        return {"estado": "en_vivo", "mensaje": ""}
    return {"estado": "retrasado", "mensaje": edad or "Precio con algunas horas de retraso"}


# ---------------------------------------------------------------- servicio

def _cotizacion(db: Session, ticker: str, mercado: str) -> Optional[Cotizacion]:
    return db.query(Cotizacion).filter(Cotizacion.ticker == ticker, Cotizacion.mercado == mercado).first()


def leer(db: Session, ticker: Optional[str], mercado: str) -> Optional[Cotizacion]:
    return _cotizacion(db, ticker.upper(), mercado or "") if ticker else None


def actualizar_ticker(db: Session, ticker: str, mercado: str, tipo: str, hoy: datetime,
                      usuario_id: Optional[str] = None, forzar: bool = False) -> dict:
    """Actualiza UN ticker respetando caché y topes. Devuelve {resultado, ...}:
    'cache' (vigente, sin petición), 'ok', 'sin_datos', 'tope_usuario', 'tope_global',
    'sin_proveedor' (no hay clave configurada). Nunca lanza por fallos de red."""
    ticker, mercado = ticker.upper().strip(), (mercado or "").upper().strip()
    c = _cotizacion(db, ticker, mercado)
    if c and c.consultada_en and not forzar:
        espera = timedelta(hours=REINTENTO_SIN_DATOS_HORAS) if c.error else timedelta(minutes=ttl_min())
        if hoy - c.consultada_en < espera:
            return {"resultado": "cache"}
    dia = hoy.strftime("%Y-%m-%d")
    if usuario_id and _usado(db, _clave(f"u:{usuario_id}", dia)) >= tope_usuario():
        return {"resultado": "tope_usuario"}
    if _usado(db, _clave("g", dia)) >= tope_global():
        return {"resultado": "tope_global"}

    nombres = [n for n in CADENA.get(tipo, CADENA["defecto"]) if PROVEEDORES_COTIZACION[n].disponible()]
    if not nombres:
        return {"resultado": "sin_proveedor"}
    dato, fuente = None, ""
    for n in nombres:
        if _usado(db, _clave("g", dia)) >= tope_global():
            return {"resultado": "tope_global"}
        _contar(db, _clave("g", dia))
        if usuario_id:
            _contar(db, _clave(f"u:{usuario_id}", dia))
        try:
            dato = PROVEEDORES_COTIZACION[n].cotizar(ticker, mercado, tipo)
        except Exception:
            dato = None
        if dato:
            fuente = n
            break
    if not c:
        c = Cotizacion(ticker=ticker, mercado=mercado)
        db.add(c)
    c.consultada_en = hoy
    if dato:
        if c.fecha and c.precio and c.fecha.date() < dato["fecha"].date():
            c.precio_anterior = c.precio
        elif dato.get("anterior"):
            c.precio_anterior = dato["anterior"]
        c.precio, c.fecha, c.moneda, c.fuente, c.error = dato["precio"], dato["fecha"], dato["moneda"] or c.moneda, fuente, ""
    else:
        c.error = "sin_datos"
    db.commit()
    return {"resultado": "ok" if dato else "sin_datos"}
