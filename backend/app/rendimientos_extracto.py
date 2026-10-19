"""Rendimientos que trae el extracto de una cuenta de ahorros, convertidos en UNA línea importable.

Problema: el extracto de Nu (y de otras billeteras) dice «Rendimiento total de tu cuenta +$X». Ese dinero SÍ suma al
saldo, pero no es una línea de movimientos, así que la app nunca lo registraba y esos meses no cuadraban al peso.

Qué hace (genérico, sin inventar):
  · Si un extracto de CUENTA (no tarjeta) trae un rendimiento del periodo > 0 leído con certeza (el resumen
    inicio + entró - salió + rendimiento = final suma), agrega UNA línea «Rendimientos de tu cuenta Nu · septiembre
    de 2026»: ingreso real (categoría de sistema «Rendimientos»), fechado en el corte, por el rendimiento total.
  · La huella es la de cualquier línea (fecha + monto + cuenta + descripción + tipo): estable por extracto y periodo,
    así que releer o volver a subir el mismo extracto NO la duplica (queda «exacta»).
  · Si el extracto no trae rendimiento, o no se puede leer con certeza, no se agrega nada.
  · Si el desglose no cuadra, la línea se ofrece APAGADA con un aviso (la persona decide).
  · La lectura se verifica con el rendimiento incluido: lo leído (con la línea) debe llevar del saldo inicial al final.

Puro: sin base de datos ni red. Lo usan el procesado de extractos y la relectura (releer_extracto.py)."""
from __future__ import annotations

from app import cuadre_extracto as cx
from app.costos_financieros import CAT_RENDIMIENTOS
from app.conciliacion import detectar_banco

PREFIJO_DESCRIPCION = "Rendimientos de tu cuenta"
AVISO_NO_CUADRA = "No pude comprobar que este rendimiento sume lo que dice tu extracto. Revísalo antes de agregarlo."

_BANCOS = {"nu": "Nu", "nequi": "Nequi", "bancolombia": "Bancolombia", "davivienda": "Davivienda", "lulo": "Lulo",
           "daviplata": "Daviplata", "bbva": "BBVA", "movii": "Movii"}


def _banco_visible(texto: str, cuenta=None) -> str:
    b = detectar_banco(texto or "")
    if b in _BANCOS:
        return _BANCOS[b]
    if b not in ("generico", "desconocido", "") and b:
        return b.title()
    nombre = (getattr(cuenta, "nombre", "") or "").strip()
    return nombre or "tu banco"


def descripcion_de(banco: str, corte) -> str:
    return f"{PREFIJO_DESCRIPCION} {banco} · {cx._MESES_LARGO[corte.month - 1]} de {corte.year}"


def es_linea_de_rendimiento(item: dict) -> bool:
    return bool(item.get("rendimiento")) and item.get("tipo") == "income"


def _mensaje(n: int, rend: float, cuadra: bool, diferencia: float) -> str:
    uno = "línea" if n == 1 else "líneas"
    if cuadra:
        return f"Leí {n} {uno}, incluidos tus rendimientos de {cx.pesos(rend)}, y suman lo que dice tu extracto ✓"
    if abs(diferencia) < cx.TOLERANCIA:
        return (f"Leí {n} {uno}, incluidos tus rendimientos de {cx.pesos(rend)}, pero el resumen del extracto no cuadra. "
                "Revisa antes de importar")
    verbo = "faltan" if diferencia > 0 else "sobran"
    return (f"Leí {n} {uno}, incluidos tus rendimientos de {cx.pesos(rend)}, pero {verbo} {cx.pesos(diferencia)} "
            "para sumar lo que dice tu extracto. Revisa antes de importar")


def con_rendimiento(movimientos: list[dict], texto: str, cuenta=None, *, es_credito: bool = False) -> tuple[list[dict], dict | None]:
    """(movimientos, lectura). Agrega la línea de rendimiento si el extracto de cuenta la trae con certeza.
    `lectura` (None si no hay rendimiento) lleva lectura_completa, lineas_leidas y mensaje_lectura, y se guarda en
    el historial. No modifica la lista recibida."""
    if es_credito or (getattr(cuenta, "tipo", "") or "").lower() == "credito" or not texto:
        return movimientos, None
    try:
        s = cx.leer_saldos_extracto(texto)
    except Exception:  # noqa: BLE001 - leer saldos es un extra
        return movimientos, None
    if not s or not s.get("rendimiento") or s["rendimiento"] <= 0 or s.get("saldo_inicial") is None:
        return movimientos, None
    corte = cx.a_fecha(s.get("fecha_corte"))
    if corte is None:
        return movimientos, None  # sin fecha de corte no se inventa el día
    rend = round(float(s["rendimiento"]), 2)
    banco = _banco_visible(texto, cuenta)
    firmados = sum(m["monto"] if m.get("tipo") == "income" else -m["monto"]
                   for m in movimientos if m.get("tipo") in ("income", "expense"))
    # Lo leído (con el rendimiento) debe llevar del saldo inicial al final, y el resumen del propio extracto debe sumar.
    diferencia = round(s["saldo_final"] - (s["saldo_inicial"] + firmados + rend), 2) if s.get("saldo_final") is not None else 0.0
    cuadra = bool(s.get("resumen_cuadra")) and s.get("saldo_final") is not None and abs(diferencia) < cx.TOLERANCIA
    linea = {
        "fecha": corte.isoformat(), "descripcion": descripcion_de(banco, corte), "monto": rend, "tipo": "income",
        "referencia": "", "saldo": None, "rendimiento": True, "categoria_fija": CAT_RENDIMIENTOS,
    }
    if not cuadra:
        linea["marcar_por_defecto"] = False
        linea["aviso_linea"] = AVISO_NO_CUADRA
    todas = [*movimientos, linea]
    lectura = {
        "lectura_completa": cuadra, "lineas_leidas": len(todas),
        "mensaje_lectura": _mensaje(len(todas), rend, cuadra, diferencia),
        "rendimiento_extracto": {"monto": rend, "cuadra": cuadra, "fecha": corte.isoformat()},
    }
    return todas, lectura
