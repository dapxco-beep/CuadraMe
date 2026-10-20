"""Lector del extracto de la TARJETA DE CRÉDITO de Nu Colombia (texto del PDF).

Es un lector aparte de `_parse_nu` (que está pensado para la cuenta de ahorros: líneas «01 oct … -$1.234,00»).
El extracto de la tarjeta tiene dos zonas:

  · Página 1 (resumen): periodo facturado, fecha de corte y límite de pago, «Deuda a pagar este mes», cupo,
    usado/disponible, cuota de manejo, cargos por conversión, pago mínimo, deuda restante.
  · Páginas siguientes (movimientos), con el encabezado repetido «Fecha Descripción Valor Cuotas …». Cada fila:
        DD MON <descripción> $Valor [N de M] $ValorDelMes pct% $Interés $TotalAPagarEsteMes $RestantePorPagar
    y la línea siguiente trae el AÑO («2026») y/o la continuación de la descripción. Hay filas especiales:
        · «Cobro por cuota $X - $X - - $X» + «de manejo»  -> cuota de manejo.
        · «Pago $A -$B [-$C]» + sub-líneas «↪ A capital / intereses / cargos y comisiones»  -> un PAGO.
          A es el monto del pago (lo que pagaste desde tu cuenta); B y C son cómo se aplicó, y
          capital + intereses + cargos = A.
        · «↪ Comisión por cambio de moneda $300,00» dentro de una compra internacional.

La pieza clave es la VERIFICACIÓN DE LECTURA: el propio extracto trae totales (Deuda a pagar este mes, cuota de
manejo, deuda restante) que deben coincidir con la suma de lo que se leyó. Si no cuadran, falta (o sobra) una línea
y la app lo dice en vez de importar a ciegas. Las relaciones se observaron en un extracto real; son una verificación,
no una garantía: cuando no cuadran se avisa, nunca se corrige a la fuerza.

Todo es texto puro (sin base de datos), para poder probarlo con extractos inventados.
"""
from __future__ import annotations

import copy
import re
import unicodedata
from datetime import date
from functools import lru_cache

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "set": 9,
         "oct": 10, "nov": 11, "dic": 12}
_MES = r"(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)[a-z]*"

TOLERANCIA = 1.0  # pesos: lo que difiere menos que esto cuenta como igual

# Tipos de línea
COMPRA = "compra"
COMPRA_EN_CUOTAS = "compra_en_cuotas"
CUOTA_MANEJO = "cuota_manejo"
PAGO = "pago"
COMISION = "comision"
CUOTA_DE_COMPRA_ANTERIOR = "cuota_de_compra_anterior"

DESCRIPCION_PAGO = "Pago de tu tarjeta"
DESCRIPCION_CUOTA_MANEJO = "Cobro por cuota de manejo"
AVISO_PAGO = "Parece el pago de tu tarjeta. Confirma el monto."
# Descripciones con las que el lector ANTERIOR guardó lo que ya se importó (para no duplicarlo al releer).
_DESC_ANTERIOR_MANEJO = "Cobro por cuota"
_DESC_ANTERIOR_PAGO = "Pago de tu tarjeta (factura anterior)"

_RE_ENCABEZADO = re.compile(r"^\s*Fecha\s+Descripci[oó]n\b", re.IGNORECASE)
_RE_PIE = re.compile(r"^\s*(?:Nu\s+Financiera\b|Bogot[aá]\b|NIT\b|\d+\s*/\s*\d+\s*$|Pago\s+m[ií]nimo\s*$)", re.IGNORECASE)
_RE_FILA = re.compile(rf"^\s*(\d{{1,2}})\s+({_MES})\.?(?:\s+(20\d{{2}}))?\s+(\S.*?)\s*$", re.IGNORECASE)
_RE_ANIO_SUELTO = re.compile(r"^\s*(20\d{2})\b\s*(.*)$")
_RE_MONTO = re.compile(r"(-?)\s*\$\s*(\d[\d.,]*)")
_RE_MONTO_PEGADO = re.compile(r"(-?)\$\s*(\d[\d.,]*)")  # el signo va PEGADO al $: «-$400.000» (un « - $X» suelto es una columna vacía)
_RE_CUOTAS = re.compile(r"\b(\d+)\s+de\s+(\d+)\b", re.IGNORECASE)
_RE_FLECHA = re.compile(r"[↪↳⮡]")
MAX_CONTINUACIONES = 4


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def _num(s: str) -> float | None:
    """'1.234.567,89' -> 1234567.89 ; '$0,00' -> 0.0 (formato colombiano: punto de miles, coma decimal)."""
    s = (s or "").strip().strip(".,")
    if not s:
        return None
    try:
        if "," in s:
            return float(s.replace(".", "").replace(",", "."))
        return float(s.replace(".", ""))
    except ValueError:
        return None


def _montos(texto: str, pegado_solo: bool = False) -> list[float]:
    """Montos con $ en el orden en que aparecen (valor absoluto)."""
    rx = _RE_MONTO_PEGADO if pegado_solo else _RE_MONTO
    return [v for v in (_num(m.group(2)) for m in rx.finditer(texto or "")) if v is not None]


# ── Detección ─────────────────────────────────────────────────────────────────────────────────────
def es_extracto_tarjeta_nu(texto: str) -> bool:
    """¿Es el extracto de la TARJETA de crédito de Nu? (la cuenta de ahorros no trae estas etiquetas)."""
    t = _sin_tildes(texto or "").lower()
    if not t:
        return False
    fuerte = ("deuda a pagar este mes" in t) or ("tus tarjetas" in t and "fecha limite de pago" in t)
    return fuerte and ("periodo facturado" in t or "fecha de corte" in t) and "nu" in t


# ── Fechas ────────────────────────────────────────────────────────────────────────────────────────
def _fecha(dia: int, mes: str, anio: int | None, corte: date | None) -> date | None:
    """Fecha completa. Sin año se usa el del corte; una fecha POSTERIOR al corte es del año anterior
    (una fila de diciembre en un extracto de enero). «JUN» en un extracto de octubre es del mismo año."""
    m = MESES.get(_sin_tildes(mes).lower()[:3])
    if not m:
        return None
    base = corte or date.today()
    y = anio or base.year
    try:
        d = date(y, m, dia)
        if corte and d > corte and (anio is None or anio >= corte.year):
            d = date(y - 1, m, dia)
        return d
    except ValueError:
        return None


# ── Resumen de la página 1 ────────────────────────────────────────────────────────────────────────
def _rx(patron: str, texto: str):
    return re.search(patron, texto, re.IGNORECASE)


def _monto_tras(etiqueta: str, texto: str) -> float | None:
    m = _rx(etiqueta + r"\s*[+\-]?\s*\$\s*(\d[\d.,]*)", texto)
    return _num(m.group(1)) if m else None


def leer_resumen(texto: str) -> dict:
    """Todos los campos del resumen (página 1) que se pudieron leer; los que no aparecen quedan en None."""
    t = re.sub(r"[ \t\r\f\v ]+", " ", texto or "")
    r: dict = {
        "periodo": {"inicio": None, "fin": None}, "corte": None, "limite_pago": None,
        "deuda_a_pagar": _monto_tras(r"Deuda\s+a\s+pagar\s+este\s+mes", t),
        "cupo": _monto_tras(r"Tu\s+cupo\s+definido", t),
        "usado": None, "disponible": None,
        "pago_minimo": _monto_tras(r"PAGO\s+M[ÍI]NIMO", t),
        "deuda_restante": _monto_tras(r"Deuda\s+restante", t),
        "cuota_manejo": _monto_tras(r"Cuota\s+de\s+manejo", t),
        "cargos_conversion": _monto_tras(r"Cargos\s+por\s+conversi[oó]n", t),
        "abonaste": _monto_tras(r"Abonaste", t),
        "intereses": _monto_tras(r"Intereses", t),
        "comisiones_avances": _monto_tras(r"Comisiones\s+de\s+avances", t),
        "comisiones_servicio": _monto_tras(r"Comisiones\s+por\s+servicio", t),
        "deuda_total_hasta": None, "tarjetas": [],
    }
    m = _rx(r"Usado\s+Disponible\s*\$\s*(\d[\d.,]*)\s*\$\s*(\d[\d.,]*)", t)
    if m:
        r["usado"], r["disponible"] = _num(m.group(1)), _num(m.group(2))
    m = _rx(r"DEUDA\s+TOTAL\s+HASTA\s+EL\s+(\d{1,2}\s+[A-ZÁÉÍÓÚa-záéíóú]+)\s*\$\s*(\d[\d.,]*)", t)
    if m:
        r["deuda_total_hasta"] = _num(m.group(2))
    r["tarjetas"] = list(dict.fromkeys(re.findall(r"●\s*●\s*●\s*●\s*(\d{4})", t)))

    d = rf"(\d{{1,2}})\s+({_MES})(?:\s+(20\d{{2}}))?"
    m = _rx(rf"{d}\s+{d}\s+{d}\s*-\s*{d}", t)
    if m:
        g = m.groups()
        limite = (int(g[0]), g[1], int(g[2]) if g[2] else None)
        corte_t = (int(g[3]), g[4], int(g[5]) if g[5] else None)
        corte = _fecha(*corte_t, None)
        r["corte"] = corte.isoformat() if corte else None
        lim = _fecha(*limite, None)
        # el límite de pago es POSTERIOR al corte: si el cálculo lo deja antes (fin de año), es del año siguiente
        if lim and corte and lim < corte and limite[2] is None:
            lim = date(lim.year + 1, lim.month, lim.day)
        r["limite_pago"] = lim.isoformat() if lim else None
        ini = _fecha(int(g[6]), g[7], int(g[8]) if g[8] else None, corte)
        fin = _fecha(int(g[9]), g[10], int(g[11]) if g[11] else None, corte)
        r["periodo"] = {"inicio": ini.isoformat() if ini else None, "fin": fin.isoformat() if fin else None}
    return r


# ── Filas de movimientos ──────────────────────────────────────────────────────────────────────────
def _unir(base: str, fragmento: str) -> str:
    """Une la continuación de la descripción. Una palabra partida a mitad de un comercio con «*»
    («Tienda Eta*Mer» + «cado», «Iota*» + «Servicio Web») se pega sin espacio; lo demás, con espacio."""
    base, fragmento = base.strip(), fragmento.strip()
    if not fragmento:
        return base
    if not base:
        return fragmento
    ultima = base.split()[-1]
    if "*" in ultima and (ultima.endswith("*") or (re.fullmatch(r"[a-záéíóúñ]+", fragmento) and not fragmento[0].isupper())):
        return base + fragmento
    return base + " " + fragmento


def _limpia(desc: str) -> str:
    return re.sub(r"\s+", " ", desc or "").strip(" -")


def _separar_flechas(texto: str) -> tuple[str, list[str]]:
    """«2026 Servicio Web ↪ Comisión … $300,00» -> («2026 Servicio Web», ['Comisión … $300,00'])."""
    partes = _RE_FLECHA.split(texto)
    return partes[0].strip(), [p.strip() for p in partes[1:] if p.strip()]


def _extraer_filas(texto: str) -> list[dict]:
    """Filas crudas: {dia, mes, anio, desc, cola, subs, orden}. Une la continuación (año y descripción)."""
    lineas = (texto or "").splitlines()
    inicio = next((i for i, l in enumerate(lineas) if _RE_ENCABEZADO.match(l)), None)
    if inicio is None:
        return []
    filas: list[dict] = []
    abierta: dict | None = None
    cont = 0
    for linea in lineas[inicio:]:
        if _RE_ENCABEZADO.match(linea) or _RE_PIE.match(linea):
            abierta = None
            continue
        m = _RE_FILA.match(linea)
        if m:
            rest = m.group(4)
            principal, subs = _separar_flechas(rest)
            idx = principal.find("$")
            desc, cola = (principal, "") if idx < 0 else (principal[:idx], principal[idx:])
            abierta = {"dia": int(m.group(1)), "mes": m.group(2), "anio": int(m.group(3)) if m.group(3) else None,
                       "desc": _limpia(desc), "cola": cola, "subs": subs, "orden": len(filas)}
            filas.append(abierta)
            cont = 0
            continue
        if abierta is None or not linea.strip():
            continue
        cont += 1
        if cont > MAX_CONTINUACIONES:
            abierta = None
            continue
        principal, subs = _separar_flechas(linea)
        abierta["subs"].extend(subs)
        ma = _RE_ANIO_SUELTO.match(principal) if principal else None
        if ma:
            if abierta["anio"] is None:
                abierta["anio"] = int(ma.group(1))
            principal = ma.group(2).strip()
        if not principal:
            continue
        if "$" in principal:
            abierta["cola"] = (abierta["cola"] + " " + principal).strip()
        else:
            abierta["desc"] = _limpia(_unir(abierta["desc"], principal))
    return filas


def _sub(subs: list[str], clave: str) -> float | None:
    for s in subs:
        if re.search(clave, _sin_tildes(s), re.IGNORECASE):
            v = _montos(s)
            if v:
                return v[0]
    return None


def _linea_de_fila(f: dict, corte: date | None, inicio_periodo: date | None) -> list[dict]:
    """De una fila cruda salen 1 o 2 líneas tipadas (la 2.ª es la comisión por cambio de moneda)."""
    fecha = _fecha(f["dia"], f["mes"], f["anio"], corte)
    desc = f["desc"]
    cola = f["cola"]
    nmontos = _montos(cola)
    base = {"fecha": fecha.isoformat() if fecha else None, "descripcion": desc, "orden": f["orden"]}
    if not fecha or not desc or not nmontos:
        return []
    salida: list[dict] = []

    if re.fullmatch(r"pago", desc, re.IGNORECASE):
        a = nmontos[0]
        b = nmontos[1] if len(nmontos) > 1 else None
        c = nmontos[2] if len(nmontos) > 2 else None
        capital = _sub(f["subs"], r"\bcapital\b")
        intereses = _sub(f["subs"], r"\bintereses\b")
        cargos = _sub(f["subs"], r"\bcargos\b")
        salida.append({**base, "tipo_linea": PAGO, "descripcion": DESCRIPCION_PAGO, "monto": a, "valor": a,
                       "aplicado": [v for v in (b, c) if v is not None],
                       "detalle": {"capital": capital, "intereses": intereses, "cargos": cargos}})
        return salida

    if re.match(r"cobro\s+por\s+cuota\b", desc, re.IGNORECASE):
        total = nmontos[-1]
        salida.append({**base, "tipo_linea": CUOTA_MANEJO, "descripcion": DESCRIPCION_CUOTA_MANEJO, "monto": nmontos[0],
                       "valor": nmontos[0], "total_mes": total, "restante": 0.0})
        return salida

    # compra: Valor [N de M] ValorDelMes pct% Interés TotalAPagar Restante
    valor = nmontos[0]
    if len(nmontos) >= 5:
        valor_mes, interes, total, restante = nmontos[1], nmontos[2], nmontos[3], nmontos[4]
    elif len(nmontos) >= 3:
        valor_mes, interes, total, restante = nmontos[1], 0.0, nmontos[-2], nmontos[-1]
    else:  # no se pudo leer toda la fila: se deja el total en None y la verificación lo notará
        valor_mes, interes, total, restante = valor, 0.0, None, None
    mc = _RE_CUOTAS.search(cola)
    cuotas = {"n": int(mc.group(1)), "m": int(mc.group(2))} if mc else None
    en_cuotas = abs(valor - valor_mes) > TOLERANCIA or (restante or 0) > TOLERANCIA or bool(cuotas and cuotas["m"] > 1)
    vieja = en_cuotas and inicio_periodo is not None and fecha < inicio_periodo
    tipo = CUOTA_DE_COMPRA_ANTERIOR if vieja else (COMPRA_EN_CUOTAS if en_cuotas else COMPRA)
    salida.append({**base, "tipo_linea": tipo, "monto": valor, "valor": valor, "valor_mes": valor_mes,
                   "interes": interes, "total_mes": total, "restante": restante, "cuotas": cuotas})
    com = _sub(f["subs"], r"comision por cambio de moneda")
    if com:
        salida.append({**base, "tipo_linea": COMISION, "monto": com, "valor": com,
                       "descripcion": f"Comisión por cambio de moneda ({desc})"})
    return salida


# ── Verificación ──────────────────────────────────────────────────────────────────────────────────
def _comprobacion(clave: str, nombre: str, leido: float, esperado: float | None, critica: bool = True) -> dict | None:
    if esperado is None:
        return None
    dif = round(leido - esperado, 2)
    return {"clave": clave, "nombre": nombre, "leido": round(leido, 2), "esperado": round(esperado, 2),
            "diferencia": dif, "cuadra": abs(dif) <= TOLERANCIA, "critica": critica}


def verificar(lineas: list[dict], resumen: dict) -> list[dict]:
    """Comprobaciones entre lo leído y lo que dice el resumen del propio extracto."""
    out: list[dict | None] = []
    filas_total = [l for l in lineas if l["tipo_linea"] in (COMPRA, COMPRA_EN_CUOTAS, CUOTA_DE_COMPRA_ANTERIOR)]
    sin_total = [l for l in filas_total if l.get("total_mes") is None]
    suma_total = sum(l["total_mes"] for l in filas_total if l.get("total_mes") is not None)
    c = _comprobacion("total_a_pagar", "Total a pagar este mes", suma_total, resumen.get("deuda_a_pagar"))
    if c and sin_total:  # una fila no se pudo leer completa: no se puede dar por buena la suma
        c["cuadra"] = False
    out.append(c)
    manejo = [l for l in lineas if l["tipo_linea"] == CUOTA_MANEJO]
    out.append(_comprobacion("cuota_manejo", "Cuota de manejo", sum(l["monto"] for l in manejo), resumen.get("cuota_manejo")))
    out.append(_comprobacion("deuda_restante", "Restante por pagar", sum(l.get("restante") or 0 for l in filas_total),
                             resumen.get("deuda_restante")))
    for p in (l for l in lineas if l["tipo_linea"] == PAGO):
        partes = [v for v in p["detalle"].values() if v is not None]
        if partes:  # sin sub-líneas no hay nada contra qué comparar
            out.append(_comprobacion(f"pago_{p['fecha']}", f"Pago del {p['fecha']}", sum(partes), p["monto"]))
    # Informativas (no frenan la lectura): se observaron en un extracto real pero no son una garantía.
    pagos = [l for l in lineas if l["tipo_linea"] == PAGO]
    if pagos and resumen.get("usado") is not None:
        ultimo = max(p["fecha"] for p in pagos)
        despues = sum((l.get("total_mes") or 0) for l in lineas
                      if l["tipo_linea"] in (COMPRA, COMPRA_EN_CUOTAS, CUOTA_MANEJO) and l["fecha"] > ultimo)
        out.append(_comprobacion("usado", "Usado (lo posterior al último pago)", despues, resumen["usado"], critica=False))
    com = sum(l["monto"] for l in lineas if l["tipo_linea"] == COMISION)
    out.append(_comprobacion("cargos_conversion", "Cargos por conversión", com, resumen.get("cargos_conversion"), critica=False))
    return [c for c in out if c]


def lectura_completa(verificacion: list[dict]) -> bool:
    """True si todas las comprobaciones críticas cuadran (y hubo al menos una)."""
    criticas = [c for c in verificacion if c["critica"]]
    return bool(criticas) and all(c["cuadra"] for c in criticas)


def _pesos(v: float) -> str:
    return "$" + f"{abs(round(v)):,}".replace(",", ".")


def mensaje_lectura(n_lineas: int, verificacion: list[dict]) -> str:
    """Frase para la persona: siempre dice cuántas líneas leyó."""
    uno = "línea" if n_lineas == 1 else "líneas"
    if lectura_completa(verificacion):
        return f"Leí {n_lineas} {uno} y suman lo que dice tu extracto ✓"
    malas = [c for c in verificacion if c["critica"] and not c["cuadra"]]
    if not malas:
        return f"Leí {n_lineas} {uno}, pero no pude compararlas con el resumen de tu extracto. Revisa antes de importar"
    peor = max(malas, key=lambda c: abs(c["diferencia"]))
    if abs(peor["diferencia"]) <= TOLERANCIA:  # la fila no se leyó completa
        return f"Leí {n_lineas} {uno} pero alguna no se leyó completa. Revisa antes de importar"
    if peor["diferencia"] < 0:
        return f"Leí {n_lineas} {uno} pero faltan {_pesos(peor['diferencia'])} para sumar lo que dice tu extracto. Revisa antes de importar"
    return f"Leí {n_lineas} {uno} pero sobran {_pesos(peor['diferencia'])} respecto a lo que dice tu extracto. Revisa antes de importar"


# ── Movimientos importables ───────────────────────────────────────────────────────────────────────
def _movimiento(l: dict) -> dict | None:
    """La línea tipada como movimiento del lector de extractos (None si no se importa)."""
    from app.contabilidad import MARCA_TRASLADO_PROPIO

    t = l["tipo_linea"]
    if t == CUOTA_DE_COMPRA_ANTERIOR or not l.get("monto") or l["monto"] < 1:
        return None
    mov = {"fecha": l["fecha"], "descripcion": l["descripcion"], "monto": l["monto"], "referencia": "", "saldo": None,
           "tipo": "income" if t == PAGO else "expense", "linea_tipo": t}
    if t != PAGO:
        # El lector anterior no veía el signo y guardó estas líneas como ingreso. Regla EXPLÍCITA (corregir_tipo):
        # si ya se importaron así, no se ofrecen como compra nueva: se corrige el tipo del movimiento que ya existe.
        mov["corrige_tipo"] = {"de": "income", "a": "expense"}
    if t == COMPRA_EN_CUOTAS:
        mov["restante"] = l.get("restante")
        mov["valor_mes"] = l.get("valor_mes")
        if l.get("cuotas"):
            mov["cuotas"] = f"{l['cuotas']['n']} de {l['cuotas']['m']}"
    if t == CUOTA_MANEJO:
        # El lector anterior la guardó como «Cobro por cuota»: si ya se importó así, se sigue reconociendo.
        mov["huella_anterior"] = {"fecha": l["fecha"], "monto": l["monto"], "descripcion": _DESC_ANTERIOR_MANEJO, "tipo": "expense"}
    if t == PAGO:
        d = l["detalle"]
        mov.update({"pista": MARCA_TRASLADO_PROPIO, "pago_tarjeta": True, "aviso_linea": AVISO_PAGO,
                    "pago_detalle": {"capital": d["capital"], "intereses": d["intereses"], "cargos": d["cargos"],
                                     "aplicado": l["aplicado"]}})
        ap = l["aplicado"]
        if len(ap) == 2 and abs(abs(l["monto"] - ap[0]) - ap[1]) <= TOLERANCIA:
            # El lector anterior leyó «Pago $A -$B -$C» (C = A−B) como un pago de B. Regla EXPLÍCITA (corregir_pago):
            # si ya se importó así, no se ofrece un segundo pago: se corrige el monto del que ya existe.
            mov["corrige_lectura"] = {"descripcion": _DESC_ANTERIOR_PAGO, "tipo": "income", "montos": list(ap)}
    return mov


# ── Entrada principal ─────────────────────────────────────────────────────────────────────────────
def _leer(texto: str) -> dict:
    resumen = leer_resumen(texto)
    corte = date.fromisoformat(resumen["corte"]) if resumen["corte"] else None
    inicio = date.fromisoformat(resumen["periodo"]["inicio"]) if resumen["periodo"]["inicio"] else None
    lineas: list[dict] = []
    for f in _extraer_filas(texto):
        lineas.extend(_linea_de_fila(f, corte, inicio))
    movimientos = [m for m in (_movimiento(l) for l in lineas) if m]
    verificacion = verificar(lineas, resumen)
    completa = lectura_completa(verificacion)
    return {
        "resumen_tarjeta": resumen, "lineas": lineas, "movimientos": movimientos, "verificacion": verificacion,
        "lectura_completa": completa, "lineas_leidas": len(lineas),
        "mensaje_lectura": mensaje_lectura(len(lineas), verificacion),
    }


@lru_cache(maxsize=8)
def _leer_cacheado(texto: str) -> dict:
    return _leer(texto)


def leer_extracto_tarjeta_nu(texto: str) -> dict:
    """{resumen_tarjeta, lineas (todas, tipadas), movimientos (las importables), verificacion, lectura_completa,
    lineas_leidas, mensaje_lectura}. Siempre devuelve una copia: quien llama puede modificarla."""
    return copy.deepcopy(_leer_cacheado(texto or ""))


def datos_de_lectura(lectura: dict) -> dict:
    """Lo que se guarda con el extracto para reabrir la revisión sin el PDF."""
    return {k: lectura[k] for k in ("resumen_tarjeta", "verificacion", "lectura_completa", "lineas_leidas", "mensaje_lectura")}
