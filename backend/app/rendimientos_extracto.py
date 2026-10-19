"""Lo que el resumen del extracto de una cuenta de ahorros trae y NO es una línea de movimientos, convertido en líneas importables.

Problema: el extracto de Nu (y de otras billeteras) dice, en su resumen, «Rendimiento total de tu cuenta +$X», «Impuesto del
4x1000 $G» y «Costos por retiro $R». Los tres mueven el saldo (F = A + B - C - G - R + Y) pero no son líneas, así que la app
nunca los registraba y esos meses no cuadraban al peso.

Qué hace (genérico, sin inventar). Por cada concepto > 0 leído con certeza agrega UNA línea, fechada en el corte:
  · «Rendimientos de tu cuenta Nu · septiembre de 2026»  ingreso real (categoría de sistema «Rendimientos»).
  · «Impuesto 4x1000 (GMF) · septiembre de 2026»         GASTO real (categoría de sistema «4x1000 (GMF)»), no traslado.
  · «Costos por retiro · septiembre de 2026»             GASTO real (categoría de sistema «Comisiones y seguros»).
  · La huella es la de cualquier línea (fecha + monto + cuenta + descripción + tipo): estable por extracto y periodo,
    así que releer o volver a subir el mismo extracto NO las duplica (quedan «exactas»).
  · Si el extracto no trae el concepto, o no se puede leer con certeza, no se agrega nada.
  · Si el desglose no cuadra, las líneas se ofrecen APAGADAS con un aviso (la persona decide).
  · Si el extracto YA lista una línea de 4x1000 por ese valor (otros bancos sí la listan), no se agrega otra: se contaría dos veces.
  · La lectura se verifica con todo incluido: lo leído (con las líneas) debe llevar del saldo inicial al final.

Relación con el 4x1000 «estimado» (impuestos.py): el GMF que la app estima (0,4 % de los débitos) y el «registrado» se
comparan por mes; esta línea llega como GMF registrado real (su descripción dice «4x1000»), así que la estimación deja de
ser lo único que hay, sin contradecirla.

Puro: sin base de datos ni red. Lo usan el procesado de extractos y la relectura (releer_extracto.py)."""
from __future__ import annotations

from app import cuadre_extracto as cx
from app.conciliacion import detectar_banco
from app.costos_financieros import CAT_COMISIONES, CAT_GMF, CAT_RENDIMIENTOS
from app.impuestos import es_linea_gmf

PREFIJO_DESCRIPCION = "Rendimientos de tu cuenta"
PREFIJO_GMF = "Impuesto 4x1000 (GMF)"
PREFIJO_RETIRO = "Costos por retiro"
AVISO_NO_CUADRA = "No pude comprobar que este rendimiento sume lo que dice tu extracto. Revísalo antes de agregarlo."
AVISO_NO_CUADRA_GASTO = "No pude comprobar que este cobro sume lo que dice tu extracto. Revísalo antes de agregarlo."

# Conceptos del resumen: (clave, campo en leer_saldos_extracto, marca en la línea, tipo, categoría de sistema).
RENDIMIENTOS, GMF, RETIRO = "rendimientos", "impuesto_4x1000", "costos_retiro"
_CONCEPTOS = [
    (RENDIMIENTOS, "rendimiento", "rendimiento", "income", CAT_RENDIMIENTOS),
    (GMF, "impuesto_4x1000", "impuesto_4x1000", "expense", CAT_GMF),
    (RETIRO, "costos_retiro", "costos_retiro", "expense", CAT_COMISIONES),
]
CLAVES = tuple(c[0] for c in _CONCEPTOS)
RAZON = {RENDIMIENTOS: "rendimiento que trae tu extracto", GMF: "impuesto 4x1000 que trae tu extracto",
         RETIRO: "costos por retiro que trae tu extracto"}

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


def _mes_de(corte) -> str:
    return f"{cx._MESES_LARGO[corte.month - 1]} de {corte.year}"


def descripcion_de(banco: str, corte) -> str:
    return f"{PREFIJO_DESCRIPCION} {banco} · {_mes_de(corte)}"


def descripcion_gmf(corte) -> str:
    return f"{PREFIJO_GMF} · {_mes_de(corte)}"


def descripcion_retiro(corte) -> str:
    return f"{PREFIJO_RETIRO} · {_mes_de(corte)}"


def concepto_de_linea(item: dict) -> str | None:
    """'rendimientos' | 'impuesto_4x1000' | 'costos_retiro' si la línea del review es una de estas, o None."""
    for clave, _campo, marca, tipo, _cat in _CONCEPTOS:
        if item.get(marca) and item.get("tipo") == tipo:
            return clave
    return None


def es_linea_de_rendimiento(item: dict) -> bool:
    return concepto_de_linea(item) == RENDIMIENTOS


def es_linea_de_ajuste(item: dict) -> bool:
    """¿Es una de las líneas que sale del resumen del extracto (rendimientos, 4x1000 o costos por retiro)?"""
    return concepto_de_linea(item) is not None


def razon_de(item: dict) -> str:
    return RAZON.get(concepto_de_linea(item) or "", "dato que trae tu extracto")


def _lista(frases: list[str]) -> str:
    return frases[0] if len(frases) == 1 else ", ".join(frases[:-1]) + " y " + frases[-1]


def _frases(montos: dict[str, float]) -> str:
    f = []
    if RENDIMIENTOS in montos:
        f.append(f"tus rendimientos de {cx.pesos(montos[RENDIMIENTOS])}")
    if GMF in montos:
        f.append(f"el 4x1000 de {cx.pesos(montos[GMF])}")
    if RETIRO in montos:
        f.append(f"tus costos por retiro de {cx.pesos(montos[RETIRO])}")
    return _lista(f)


def _mensaje(n: int, montos: dict[str, float], cuadra: bool, diferencia: float) -> str:
    uno = "línea" if n == 1 else "líneas"
    que = _frases(montos)
    if cuadra:
        return f"Leí {n} {uno}, incluidos {que}, y suman lo que dice tu extracto ✓"
    if abs(diferencia) < cx.TOLERANCIA:
        return f"Leí {n} {uno}, incluidos {que}, pero el resumen del extracto no cuadra. Revisa antes de importar"
    verbo = "faltan" if diferencia > 0 else "sobran"
    return f"Leí {n} {uno}, incluidos {que}, pero {verbo} {cx.pesos(diferencia)} para sumar lo que dice tu extracto. Revisa antes de importar"


def _gmf_ya_listado(movimientos: list[dict], monto: float) -> bool:
    """¿El extracto ya trae el 4x1000 como línea (otros bancos sí lo listan)? Entonces no se agrega otra."""
    return any(m.get("tipo") == "expense" and es_linea_gmf(m.get("descripcion", "")) and abs(float(m.get("monto") or 0) - monto) < cx.TOLERANCIA
               for m in movimientos)


def con_rendimiento(movimientos: list[dict], texto: str, cuenta=None, *, es_credito: bool = False) -> tuple[list[dict], dict | None]:
    """(movimientos, lectura). Agrega las líneas del resumen del extracto de cuenta (rendimientos, 4x1000, costos por
    retiro) que se lean con certeza. `lectura` (None si no hay ninguna) lleva lectura_completa, lineas_leidas y
    mensaje_lectura, y se guarda en el historial. No modifica la lista recibida. (El nombre se conserva por compatibilidad.)"""
    if es_credito or (getattr(cuenta, "tipo", "") or "").lower() == "credito" or not texto:
        return movimientos, None
    try:
        s = cx.leer_saldos_extracto(texto)
    except Exception:  # noqa: BLE001 - leer saldos es un extra
        return movimientos, None
    if not s or s.get("saldo_inicial") is None:
        return movimientos, None
    montos = {clave: round(float(s[campo]), 2) for clave, campo, *_ in _CONCEPTOS if s.get(campo) and s[campo] > 0}
    if GMF in montos and _gmf_ya_listado(movimientos, montos[GMF]):
        del montos[GMF]
    if not montos:
        return movimientos, None
    corte = cx.a_fecha(s.get("fecha_corte"))
    if corte is None:
        return movimientos, None  # sin fecha de corte no se inventa el día
    banco = _banco_visible(texto, cuenta)
    nuevas = []
    for clave, _campo, marca, tipo, categoria in _CONCEPTOS:
        if clave not in montos:
            continue
        desc = {RENDIMIENTOS: descripcion_de(banco, corte), GMF: descripcion_gmf(corte), RETIRO: descripcion_retiro(corte)}[clave]
        nuevas.append({"fecha": corte.isoformat(), "descripcion": desc, "monto": montos[clave], "tipo": tipo, "referencia": "",
                       "saldo": None, marca: True, "categoria_fija": categoria})
    todas = [*movimientos, *nuevas]
    # Lo leído (con todo lo agregado) debe llevar del saldo inicial al final, y el resumen del propio extracto debe sumar.
    firmados = sum(m["monto"] if m.get("tipo") == "income" else -m["monto"] for m in todas if m.get("tipo") in ("income", "expense"))
    diferencia = round(s["saldo_final"] - (s["saldo_inicial"] + firmados), 2) if s.get("saldo_final") is not None else 0.0
    cuadra = bool(s.get("resumen_cuadra")) and s.get("saldo_final") is not None and abs(diferencia) < cx.TOLERANCIA
    if not cuadra:
        for l in nuevas:
            l["marcar_por_defecto"] = False
            l["aviso_linea"] = AVISO_NO_CUADRA if l["tipo"] == "income" else AVISO_NO_CUADRA_GASTO
    lectura = {
        "lectura_completa": cuadra, "lineas_leidas": len(todas),
        "mensaje_lectura": _mensaje(len(todas), montos, cuadra, diferencia),
        "ajustes_extracto": {k: {"monto": v, "cuadra": cuadra, "fecha": corte.isoformat()} for k, v in montos.items()},
    }
    if RENDIMIENTOS in montos:
        lectura["rendimiento_extracto"] = lectura["ajustes_extracto"][RENDIMIENTOS]
    return todas, lectura
