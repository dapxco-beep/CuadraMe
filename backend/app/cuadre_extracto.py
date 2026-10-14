"""Cuadre con el extracto: que el saldo de la cuenta en CuadraMe coincida con el que dice el banco.

Orientación para la persona: el saldo oficial es el de su banco. Aquí solo se COMPARA y se ayuda a
encontrar la diferencia; nunca se cambia nada sin que la persona lo confirme.

Qué hay en este módulo:
  1) LECTURA (pura) de los saldos que trae un extracto: saldo anterior, saldo final, fecha de corte.
     - PDF: `leer_saldos_extracto(texto, ...)`.   - Excel/CSV: `saldos_de_filas(movs)` (columna «saldo»).
  2) SALDO DE LIBRO: la suma de los movimientos de la cuenta hasta una fecha, con la regla única de
     contabilidad (`delta_saldo`). No incluye el «saldo de partida» que una cuenta pudo traer desde que
     se creó sin ser un movimiento (ese pedazo se llama «sin explicar» y se ofrece como saldo inicial).
  3) EVALUACIÓN: cuadra / diferencia, con causas probables en lenguaje llano y las acciones posibles.
  4) ACCIONES: ajuste de saldo (neutro: NO es gasto ni ingreso), saldo inicial, deshacer.
  5) HISTÓRICO por mes (`cuadre_por_mes`) y memoria de «este mes cuadraba» para avisar si deja de cuadrar.

Convención de signo (la misma de la cuenta): en una tarjeta de crédito la deuda es NEGATIVA
(-800.000 = debes 800.000). Los saldos que se leen de un extracto de tarjeta se guardan así.
"""
from __future__ import annotations

import re
import unicodedata
from bisect import bisect_right
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.contabilidad import CATEGORIA_AJUSTE, FUENTE_AJUSTE, delta_saldo
from app.models import Cuenta, HistorialExtracto, Movimiento
from app.utiles import ahora_co

TOLERANCIA = 1.0  # un peso: los bancos y los redondeos no se pelean por menos
ORIENTACION = "Orientación: el saldo oficial es el de tu banco."

PREFIJO_AJUSTE = "Ajuste para cuadrar con el extracto del"
PREFIJO_INICIAL = "Saldo inicial al"
MARCA_YA_EN_SALDO = "ya estaba en tu saldo"  # el saldo inicial «sin explicar» no mueve el saldo de la cuenta

_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_MES_NUM = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "set": 9,
            "oct": 10, "nov": 11, "dic": 12}
_MESES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                "octubre", "noviembre", "diciembre"]


def fecha_texto(d: date | str | None) -> str:
    """date o 'AAAA-MM-DD' -> '30 sep 2026'."""
    if isinstance(d, str):
        d = a_fecha(d)
    return f"{d.day} {_MESES[d.month - 1]} {d.year}" if d else ""


def a_fecha(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def pesos(v: float) -> str:
    return "$" + f"{abs(round(v)):,}".replace(",", ".")


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


# ── 1. LECTURA DE SALDOS (pura) ─────────────────────────────────────────────────────────
_NUM = r"(\(?\s*[-–−]?\s*\$?\s*[-–−]?\s*\d[\d.,]*\s*\)?)"
_FECHA_DMY = re.compile(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](20\d{2})")
_FECHA_TEXTO = re.compile(r"(\d{1,2})\s*(?:de\s+)?(ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)[a-z]*\.?\s*(?:de\s+)?(20\d{2})")


def _numero(token: str) -> float | None:
    from app.conciliacion import _num_flexible

    negativo = bool(re.search(r"[-–−]", token)) or bool(re.match(r"^\(.*\)$", token.strip()))
    n = _num_flexible(re.sub(r"[^\d.,]", "", token))
    if n is None:
        return None
    return -n if negativo else n


def _valor_tras(texto: str, etiquetas: list[str], largo: int = 40) -> float | None:
    """Primer número que aparece justo después de la primera etiqueta que exista en el texto."""
    for et in etiquetas:
        m = re.search(r"(?<![a-z])" + et + r"(?![a-z])", texto)
        if not m:
            continue
        resto = texto[m.end(): m.end() + largo]
        n = re.match(r"[\s:.\-]*" + _NUM, resto)
        if n:
            v = _numero(n.group(1))
            if v is not None:
                return v
    return None


def _fecha_ymd(d: int, m: int, a: int) -> date | None:
    try:
        return date(a, m, d)
    except ValueError:
        return None


def _fechas_del_periodo(t: str) -> tuple[date | None, date | None]:
    """Primer y último día que dice el encabezado del extracto: «periodo 01/09/2026 - 30/09/2026»,
    «del 1 al 30 de septiembre de 2026», «01 - 31 OCT 2025»."""
    m = re.search(r"(20\d{2})[/\-](\d{1,2})[/\-](\d{1,2})\s*(?:-|a|al|hasta)\s*(20\d{2})[/\-](\d{1,2})[/\-](\d{1,2})", t)
    if m:
        g = [int(x) for x in m.groups()]
        return _fecha_ymd(g[2], g[1], g[0]), _fecha_ymd(g[5], g[4], g[3])
    m = re.search(r"(?:periodo|per[ií]odo|extracto|desde)[^\n]{0,40}?" + _FECHA_DMY.pattern + r"\s*(?:-|a|al|hasta)\s*" + _FECHA_DMY.pattern, t)
    if m:
        g = [int(x) for x in m.groups()]
        return _fecha_ymd(g[0], g[1], g[2]), _fecha_ymd(g[3], g[4], g[5])
    m = re.search(r"\b(\d{1,2})\s*(?:-|al|a)\s*(\d{1,2})\s+(?:de\s+)?(" + "|".join(_MES_NUM) + r")[a-z]*\.?\s*(?:de\s+)?(20\d{2})\b", t)
    if m:
        d1, d2, mes, a = int(m.group(1)), int(m.group(2)), _MES_NUM[m.group(3)], int(m.group(4))
        return _fecha_ymd(d1, mes, a), _fecha_ymd(d2, mes, a)
    return None, None


def _fecha_tras(t: str, etiquetas: list[str]) -> date | None:
    for et in etiquetas:
        m = re.search(r"(?<![a-z])" + et + r"(?![a-z])", t)
        if not m:
            continue
        resto = t[m.end(): m.end() + 40]
        f = _FECHA_DMY.search(resto)
        if f:
            return _fecha_ymd(int(f.group(1)), int(f.group(2)), int(f.group(3)))
        f = _FECHA_TEXTO.search(resto)
        if f:
            return _fecha_ymd(int(f.group(1)), _MES_NUM[f.group(2)], int(f.group(3)))
    return None


def detectar_moneda(texto: str) -> str | None:
    """'USD' si el extracto está en dólares, 'COP' si dice pesos o COP, None si no se sabe."""
    t = _sin_acentos(texto)
    dolares = bool(re.search(r"\busd\b|us\$|\bdolares\b", t))
    pesos_ = bool(re.search(r"\bcop\b|\bpesos\b", t))
    if dolares and not pesos_:
        return "USD"
    if pesos_ and not dolares:
        return "COP"
    return None


_ETQ_INICIAL = [r"saldo\s+anterior", r"saldo\s+inicial(?:\s+del\s+periodo)?", r"saldo\s+al\s+inicio", r"saldo\s+del\s+extracto\s+anterior"]
_ETQ_FINAL = [r"saldo\s+final(?:\s+del\s+periodo)?", r"saldo\s+actual", r"nuevo\s+saldo", r"saldo\s+a\s+la\s+fecha\s+de\s+corte",
              r"saldo\s+al\s+corte", r"saldo\s+al\s+cierre", r"saldo\s+al\s+final"]
_ETQ_DEUDA = [r"saldo\s+total", r"deuda\s+total", r"total\s+deuda", r"saldo\s+a\s+la\s+fecha\s+de\s+corte", r"saldo\s+al\s+corte",
              r"saldo\s+final", r"nuevo\s+saldo", r"valor\s+total\s+a\s+pagar", r"total\s+a\s+pagar", r"pago\s+total"]
_ETQ_DEUDA_INICIAL = [r"saldo\s+anterior", r"saldo\s+inicial", r"saldo\s+extracto\s+anterior"]
_ETQ_CORTE = [r"fecha\s+de\s+corte", r"fecha\s+corte", r"fecha\s+de\s+cierre", r"corte\s+del\s+extracto", r"saldo\s+al\s+corte",
              r"hasta\s+el"]


def leer_saldos_extracto(texto: str, es_credito: bool = False, datos_tarjeta: dict | None = None) -> dict | None:
    """Saldos que imprime el extracto (PDF ya convertido en texto), en la convención de la cuenta.
    Devuelve None si no se pudo leer NINGÚN saldo (se pedirá a mano). Nunca inventa: cada dato es
    opcional y solo está si se halló con una etiqueta clara.

    Cuentas de ahorro/débito: «saldo anterior» y «saldo actual/final/nuevo saldo». Tarjeta de crédito:
    la deuda va en NEGATIVO; «saldo total / deuda total / pago total» es lo que se debía al corte."""
    t = _sin_acentos(texto)
    out: dict = {}
    if es_credito:
        deuda = _valor_tras(t, _ETQ_DEUDA)
        previa = _valor_tras(t, _ETQ_DEUDA_INICIAL)
        if deuda is not None:
            out["saldo_final"] = -abs(deuda) if not re.search(r"saldo\s+a\s+favor", t) else abs(deuda)
        if previa is not None:
            out["saldo_inicial"] = -abs(previa)
        pm = (datos_tarjeta or {}).get("pago_minimo")
        if pm is not None:
            out["pago_minimo"] = pm
        if "saldo_final" not in out and (datos_tarjeta or {}).get("pago_total") is not None:
            out["saldo_final"] = -abs(datos_tarjeta["pago_total"])
            out["aproximado"] = True  # el pago total puede no incluir lo comprado después del corte
    else:
        ini, fin = _valor_tras(t, _ETQ_INICIAL), _valor_tras(t, _ETQ_FINAL)
        if ini is not None:
            out["saldo_inicial"] = ini
        if fin is not None:
            out["saldo_final"] = fin
    if "saldo_final" not in out and "saldo_inicial" not in out:
        return None
    desde, hasta = _fechas_del_periodo(t)
    corte = (a_fecha((datos_tarjeta or {}).get("fecha_corte")) if datos_tarjeta else None) or _fecha_tras(t, _ETQ_CORTE) or hasta
    if corte:
        out["fecha_corte"] = corte.isoformat()
    if desde:
        out["periodo_inicio"] = desde.isoformat()
    moneda = detectar_moneda(texto)
    if moneda:
        out["moneda"] = moneda
    out["origen"] = "extracto"
    return out


def saldos_de_filas(movs: list[dict]) -> dict | None:
    """Saldos de un Excel/CSV con columna «saldo» (saldo corrido después de cada fila). Solo se confía si la
    cadena es coherente: saldo[i] = saldo[i-1] + monto firmado (de arriba abajo o de abajo arriba).
    `movs`: dicts con fecha, monto, tipo ('income'|'expense'), saldo. None si no hay columna o no cuadra."""
    filas = [m for m in movs if m.get("saldo") is not None and m.get("fecha")]
    if len(filas) < 2 or len(filas) < 0.8 * len(movs):
        return None

    def firmado(m):
        return m["monto"] if m["tipo"] == "income" else -m["monto"]

    def coherencia(lista):
        buenos = sum(1 for a, b in zip(lista, lista[1:]) if abs(a["saldo"] + firmado(b) - b["saldo"]) < TOLERANCIA)
        return buenos / (len(lista) - 1)

    asc, desc = coherencia(filas), coherencia(filas[::-1])
    if max(asc, desc) < 0.9:
        return None
    orden = filas if asc >= desc else filas[::-1]
    primero, ultimo = orden[0], orden[-1]
    return {
        "saldo_inicial": round(primero["saldo"] - firmado(primero), 2),
        "saldo_final": round(ultimo["saldo"], 2),
        "fecha_corte": str(ultimo["fecha"])[:10],
        "periodo_inicio": str(primero["fecha"])[:10],
        "origen": "tabla",
    }


def cadena_coincide(saldos: dict | None, movs: list[dict]) -> bool | None:
    """¿saldo anterior + movimientos leídos = saldo final? False delata una línea que no se pudo leer (o leída
    de más). None si el extracto no trae las dos puntas. Los movimientos: dicts con monto y tipo."""
    if not saldos or saldos.get("saldo_inicial") is None or saldos.get("saldo_final") is None or not movs:
        return None
    firmados = sum(m["monto"] if m.get("tipo") == "income" else -m["monto"] for m in movs if m.get("tipo") in ("income", "expense"))
    return abs(saldos["saldo_inicial"] + firmados - saldos["saldo_final"]) < TOLERANCIA


# ── 2. SALDO DE LIBRO ──────────────────────────────────────────────────────────────────
def _serie(db: Session, cuenta_id: str) -> tuple[list[datetime], list[float], list[dict]]:
    """Movimientos de la cuenta en orden de fecha: (fechas, saldo corrido, filas)."""
    filas = (db.query(Movimiento.id, Movimiento.fecha, Movimiento.tipo, Movimiento.monto, Movimiento.fuente,
                      Movimiento.notas, Movimiento.descripcion, Movimiento.conciliado_en, Movimiento.categoria)
             .filter(Movimiento.cuenta_id == cuenta_id).order_by(Movimiento.fecha).all())
    fechas, acumulado, filas_d, total = [], [], [], 0.0
    for f in filas:
        d = {"id": f.id, "fecha": f.fecha, "tipo": f.tipo, "monto": f.monto, "fuente": f.fuente, "notas": f.notas or "",
             "descripcion": f.descripcion, "conciliado_en": f.conciliado_en, "categoria": f.categoria}
        total += delta_saldo(d)
        fechas.append(f.fecha or datetime.min)
        acumulado.append(total)
        filas_d.append(d)
    return fechas, acumulado, filas_d


def _libro_en(fechas: list[datetime], acumulado: list[float], corte: date) -> float:
    i = bisect_right(fechas, datetime.combine(corte, time.max))
    return round(acumulado[i - 1], 2) if i else 0.0


def saldo_libro(db: Session, cuenta_id: str, corte: date) -> float:
    """Suma de los movimientos de la cuenta hasta el final del día `corte` (regla única `delta_saldo`)."""
    fechas, acumulado, _ = _serie(db, cuenta_id)
    return _libro_en(fechas, acumulado, corte)


def saldo_sin_explicar(db: Session, cuenta: Cuenta) -> float:
    """Parte del saldo de la cuenta que NO viene de ningún movimiento (p. ej. el saldo con el que se creó
    la cuenta o el que trajo un respaldo). Es lo que explica por qué «saldo ≠ suma de movimientos»."""
    _, acumulado, _ = _serie(db, cuenta.id)
    return round((cuenta.saldo or 0.0) - (acumulado[-1] if acumulado else 0.0), 2)


# ── 3. EVALUACIÓN ──────────────────────────────────────────────────────────────────────
def umbral_ajuste_grande(saldo_banco: float, moneda: str | None) -> float:
    """Un ajuste mayor que esto pide confirmación reforzada: pasa el 5 % del saldo del banco o el monto fijo
    (en pesos). Se usa el que se alcance primero. Ambos se configuran en settings."""
    topes = []
    if saldo_banco:
        topes.append(abs(saldo_banco) * settings.cuadre_ajuste_grande_pct)
    if (moneda or "COP") == "COP":
        topes.append(settings.cuadre_ajuste_grande_monto)
    return min(topes) if topes else float("inf")


def es_ajuste_grande(diferencia: float, saldo_banco: float, moneda: str | None) -> bool:
    return abs(diferencia) > umbral_ajuste_grande(saldo_banco, moneda) + 1e-9


def _delta(monto: float, tipo: str) -> float:
    return monto if tipo == "income" else -monto if tipo == "expense" else 0.0


def evaluar(
    db: Session, cuenta: Cuenta, *, saldo_final: float | None, fecha_corte: date | None, saldo_inicial: float | None = None,
    periodo_inicio: date | None = None, moneda: str | None = None, por_importar: list[dict] | None = None,
    pendientes: int = 0, aviso_cuenta: str | None = None, inicio_pp: datetime | None = None, series=None,
) -> dict:
    """Compara el saldo del banco (al corte) con el saldo de libro de la cuenta. `por_importar`: líneas que se van a
    traer (fecha, monto, tipo) y que cuentan como si ya estuvieran. `pendientes`: líneas por revisar sin resolver
    (bloquean el ajuste). Pura salvo por las lecturas."""
    base = {"cuenta_id": cuenta.id, "orientacion": ORIENTACION, "fecha_corte": fecha_corte.isoformat() if fecha_corte else None,
            "moneda_cuenta": cuenta.moneda or "COP", "causas": [], "advertencias": [], "acciones": {}}
    if aviso_cuenta:
        base["advertencias"].append({"codigo": "otra_cuenta", "texto": aviso_cuenta})
    if moneda and (cuenta.moneda or "COP") != moneda:
        base.update(estado="moneda_distinta", texto=(
            f"Este extracto está en {moneda} y tu cuenta «{cuenta.nombre}» está en {cuenta.moneda or 'COP'}. "
            "No lo comparo para no mezclar monedas: revisa que sea la cuenta correcta."))
        return base
    if saldo_final is None or fecha_corte is None:
        base.update(estado="sin_saldo", texto=(
            "Este extracto no trae un saldo que pueda leer. "
            f"Escribe el saldo que dice tu extracto al {fecha_texto(fecha_corte) if fecha_corte else '[fecha de corte]'} y lo comparo con tus movimientos."))
        base["acciones"]["pedir_saldo"] = True
        return base
    if inicio_pp and datetime.combine(fecha_corte, time.max) < inicio_pp:
        base.update(estado="antes_de_inicio", saldo_extracto=saldo_final, texto=(
            f"Este corte es anterior a tu fecha de inicio ({fecha_texto(inicio_pp.date())}): lo anterior no se trae, "
            "así que no lo comparo."))
        return base

    fechas, acumulado, filas = series or _serie(db, cuenta.id)
    libro = _libro_en(fechas, acumulado, fecha_corte)
    extra = sum(_delta(float(x.get("monto") or 0), x.get("tipo")) for x in (por_importar or [])
                if (a_fecha(x.get("fecha")) or fecha_corte) <= fecha_corte)
    libro = round(libro + extra, 2)
    dif = round(saldo_final - libro, 2)
    base.update(saldo_extracto=round(saldo_final, 2), saldo_libro=libro, diferencia=dif,
                texto_saldo_extracto=pesos(saldo_final), texto_saldo_libro=pesos(libro))
    credito = cuenta.tipo == "credito"
    if abs(dif) < TOLERANCIA:
        base.update(estado="cuadra", texto=f"Cuadra ✓ con tu banco al {fecha_texto(fecha_corte)}.")
        return base

    # Cómo se lee el saldo en el texto: una tarjeta muestra la deuda en positivo.
    def v(x):
        return pesos(x)

    base["estado"] = "diferencia"
    base["texto"] = (
        f"Diferencia de {v(dif)}: el banco dice {'que debes ' if credito else ''}{v(saldo_final)} "
        f"y tus movimientos {'suman una deuda de ' if credito else 'suman '}{v(libro)}."
    )
    sin_explicar = round((cuenta.saldo or 0.0) - (acumulado[-1] if acumulado else 0.0), 2)
    causas = base["causas"]
    if abs(sin_explicar) >= TOLERANCIA:
        justo = abs(dif - sin_explicar) < TOLERANCIA
        causas.append({"codigo": "saldo_inicial", "probable": justo, "texto": (
            f"Tu cuenta tiene {v(sin_explicar)} de saldo que no viene de ningún movimiento (el saldo con el que la creaste o la trajiste)."
            + (" Es justo la diferencia: lo más probable es un saldo inicial sin registrar." if justo else ""))})
    if pendientes:
        causas.append({"codigo": "falta_movimiento", "probable": True, "texto": (
            f"Hay {pendientes} {'línea' if pendientes == 1 else 'líneas'} del extracto sin traer o sin resolver."
            " Mira si quedan por revisar.")})
    else:
        causas.append({"codigo": "falta_movimiento", "probable": False, "texto": (
            "Puede faltar un ingreso o abono que el banco registró y no está en tu lista, o haber un gasto de más."
            if dif > 0 else
            "Puede faltar un gasto o cobro que el banco registró y no está en tu lista, o haber un ingreso de más.")})
    # Movimiento que coincide justo con la diferencia: duplicado o de otra fecha.
    ini = datetime.combine(periodo_inicio, time.min) if periodo_inicio else datetime.combine(fecha_corte, time.min) - timedelta(days=45)
    for f in filas:
        d = delta_saldo(f)
        if not d or f["fecha"] is None:
            continue
        if f["fecha"] <= datetime.combine(fecha_corte, time.max) and f["fecha"] >= ini and abs(d + dif) < TOLERANCIA:
            causas.append({"codigo": "duplicado", "probable": True, "texto": (
                f"Hay un movimiento de {v(d)} («{(f['descripcion'] or '')[:40]}», {fecha_texto(f['fecha'])}) que coincide justo con la diferencia: ¿está repetido o no es de esta cuenta?")})
            break
    for f in filas:
        d = delta_saldo(f)
        if not d or f["fecha"] is None:
            continue
        fuera = datetime.combine(fecha_corte, time.max) < f["fecha"] <= datetime.combine(fecha_corte + timedelta(days=5), time.max)
        if fuera and abs(d - dif) < TOLERANCIA:
            causas.append({"codigo": "otra_fecha", "probable": True, "texto": (
                f"Un movimiento de {v(d)} está fechado el {fecha_texto(f['fecha'])}, justo después del corte: puede ser de este periodo.")})
            break
    if aviso_cuenta:
        causas.append({"codigo": "otra_cuenta", "probable": True, "texto": aviso_cuenta})
    elif credito:
        causas.append({"codigo": "otra_cuenta", "probable": False, "texto": "Revisa que sea la tarjeta correcta: un pago o una compra pudo quedar en otra cuenta."})

    grande = es_ajuste_grande(dif, saldo_final, cuenta.moneda)
    bloqueo = None
    if pendientes:
        bloqueo = "Primero trae o resuelve las líneas del extracto que faltan; después podrás crear el ajuste."
    base["acciones"] = {
        "ver_que_falta": True,
        "ajuste": {"permitido": bloqueo is None, "motivo_bloqueo": bloqueo, "monto": dif, "grande": grande,
                   "umbral": round(umbral_ajuste_grande(saldo_final, cuenta.moneda)),
                   "nota": f"{PREFIJO_AJUSTE} {fecha_texto(fecha_corte)}"},
        "dejar_asi": True,
    }
    if grande:
        base["advertencias"].append({"codigo": "ajuste_grande", "texto": (
            f"Es una diferencia grande ({v(dif)}). Un ajuste así puede ocultar un movimiento que falta: "
            "búscalo antes. Si de todas formas lo creas, podrás deshacerlo.")})
    # Saldo inicial: sin movimientos antes del primer día del extracto y con el saldo anterior leído.
    desde = periodo_inicio
    if saldo_inicial is not None and desde is not None:
        antes = [f for f in filas if f["fecha"] is not None and f["fecha"] < datetime.combine(desde, time.min)]
        if not antes:
            monto = round(saldo_inicial, 2)
            if abs(monto) >= TOLERANCIA:
                base["acciones"]["saldo_inicial"] = {
                    "modo": "extracto", "fecha": desde.isoformat(), "monto": monto,
                    "texto": f"Saldo inicial al {fecha_texto(desde)}: {v(monto)}, tomado de tu extracto.",
                    "saldo_cuenta_despues": round((acumulado[-1] if acumulado else 0.0) + monto, 2),
                    "saldo_cuenta_antes": round(cuenta.saldo or 0.0, 2)}
    if abs(sin_explicar) >= TOLERANCIA and "saldo_inicial" not in base["acciones"]:
        primera = next((f["fecha"] for f in filas if f["fecha"]), None)
        base["acciones"]["saldo_inicial"] = {
            "modo": "sin_explicar", "fecha": (primera or ahora_co()).date().isoformat(), "monto": sin_explicar,
            "texto": f"Registrar los {v(sin_explicar)} que ya están en tu saldo como «Saldo inicial». Tu saldo no cambia.",
            "saldo_cuenta_antes": round(cuenta.saldo or 0.0, 2), "saldo_cuenta_despues": round(cuenta.saldo or 0.0, 2)}
    return base


def diagnostico_cuenta(db: Session, cuenta: Cuenta) -> dict:
    """«Saldo de la cuenta ≠ suma de sus movimientos»: lo que explica el saldo de partida sin movimiento."""
    _, acumulado, filas = _serie(db, cuenta.id)
    suma = round(acumulado[-1] if acumulado else 0.0, 2)
    dif = round((cuenta.saldo or 0.0) - suma, 2)
    primera = next((f["fecha"] for f in filas if f["fecha"]), None)
    return {"saldo_cuenta": round(cuenta.saldo or 0.0, 2), "suma_movimientos": suma, "diferencia": dif,
            "descuadre": abs(dif) >= TOLERANCIA, "primer_movimiento": primera.date().isoformat() if primera else None,
            "texto": (None if abs(dif) < TOLERANCIA else
                      f"El saldo de esta cuenta ({pesos(cuenta.saldo or 0)}) no coincide con la suma de sus movimientos ({pesos(suma)}): "
                      f"hay {pesos(dif)} que no vienen de ningún movimiento, casi seguro el saldo inicial.")}


# ── 4. ACCIONES ───────────────────────────────────────────────────────────────────────
def _nuevo_mov(cuenta: Cuenta, usuario_id: str, fecha: datetime, desc: str, valor: float, nota: str) -> Movimiento:
    return Movimiento(
        usuario_id=usuario_id, cuenta_id=cuenta.id, fecha=fecha, descripcion=desc, categoria=CATEGORIA_AJUSTE,
        tipo="income" if valor > 0 else "expense", monto=round(abs(valor), 2), fuente=FUENTE_AJUSTE, notas=nota[:200],
    )


def crear_ajuste(db: Session, cuenta: Cuenta, usuario_id: str, fecha_corte: date, diferencia: float) -> Movimiento:
    """Movimiento neutro (fuente ajuste_saldo: no es gasto ni ingreso) fechado al corte. Mueve el saldo de la cuenta
    igual que cualquier movimiento. Sin commit."""
    mov = _nuevo_mov(cuenta, usuario_id, datetime.combine(fecha_corte, time(23, 59)), "Ajuste de saldo", diferencia,
                     f"{PREFIJO_AJUSTE} {fecha_texto(fecha_corte)}")
    cuenta.saldo = round((cuenta.saldo or 0.0) + diferencia, 2)
    db.add(mov)
    db.flush()
    return mov


def crear_saldo_inicial(db: Session, cuenta: Cuenta, usuario_id: str, modo: str, fecha: date, monto: float) -> Movimiento:
    """Saldo inicial como movimiento neutro dated al inicio del periodo.
    modo 'extracto': el saldo de la cuenta pasa a ser SOLO lo que explican los movimientos (el viejo saldo de
    partida se reemplaza por el del extracto). modo 'sin_explicar': el monto ya estaba en el saldo; solo se vuelve
    visible como movimiento y el saldo de la cuenta no cambia."""
    sin_mover = modo == "sin_explicar"
    nota = f"{PREFIJO_INICIAL} {fecha_texto(fecha)}" + (f" · {MARCA_YA_EN_SALDO}" if sin_mover else " (según tu extracto)")
    mov = _nuevo_mov(cuenta, usuario_id, datetime.combine(fecha, time.min), "Saldo inicial", monto, nota)
    if not sin_mover:
        _, acumulado, _ = _serie(db, cuenta.id)
        cuenta.saldo = round((acumulado[-1] if acumulado else 0.0) + monto, 2)
    db.add(mov)
    db.flush()
    return mov


def es_de_cuadre(mov: Movimiento) -> bool:
    n = mov.notas or ""
    return mov.fuente == FUENTE_AJUSTE and (n.startswith(PREFIJO_AJUSTE) or n.startswith(PREFIJO_INICIAL))


def deshacer(db: Session, cuenta: Cuenta, mov: Movimiento) -> float:
    """Borra un ajuste/saldo inicial de cuadre y deja el saldo de la cuenta como estaba. Sin commit."""
    d = delta_saldo(mov)
    # El saldo inicial «sin explicar» nunca movió el saldo de la cuenta; el resto sí (y se revierte).
    # Un saldo inicial «según el extracto» REEMPLAZÓ el saldo de partida: ese valor viejo no se reconstruye ni se inventa.
    if MARCA_YA_EN_SALDO not in (mov.notas or ""):
        cuenta.saldo = round((cuenta.saldo or 0.0) - d, 2)
    db.delete(mov)
    db.flush()
    return d


# ── 5. HISTÓRICO POR MES ──────────────────────────────────────────────────────────────
def guardar_saldos(historial: HistorialExtracto, saldos: dict | None, origen: str | None = None) -> None:
    if not saldos:
        return
    historial.saldo_inicial_extracto = saldos.get("saldo_inicial")
    historial.saldo_final_extracto = saldos.get("saldo_final")
    historial.fecha_corte = saldos.get("fecha_corte")
    historial.periodo_inicio = saldos.get("periodo_inicio")
    historial.moneda = saldos.get("moneda")
    historial.saldos_origen = origen or saldos.get("origen") or "extracto"


def saldos_de_historial(h: HistorialExtracto) -> dict | None:
    if h.saldo_final_extracto is None and h.saldo_inicial_extracto is None:
        return None
    return {"saldo_inicial": h.saldo_inicial_extracto, "saldo_final": h.saldo_final_extracto, "fecha_corte": h.fecha_corte,
            "periodo_inicio": h.periodo_inicio, "moneda": h.moneda, "origen": h.saldos_origen}


def registrar_cuadre(db: Session, cuenta: Cuenta, historial: HistorialExtracto, series=None) -> dict | None:
    """Mide ahora el cuadre de ese extracto (sin lo que falta por importar) y lo recuerda en el historial: así se
    puede avisar si un mes que cuadraba deja de cuadrar. Sin commit. None si el extracto no tiene saldo final."""
    if historial.saldo_final_extracto is None or not a_fecha(historial.fecha_corte):
        return None
    ev = evaluar(db, cuenta, saldo_final=historial.saldo_final_extracto, fecha_corte=a_fecha(historial.fecha_corte),
                 moneda=historial.moneda, series=series)
    if ev.get("estado") in ("cuadra", "diferencia"):
        historial.cuadre_estado = ev["estado"]
        historial.cuadre_diferencia = ev.get("diferencia")
        historial.cuadre_en = ahora_co()
    return ev


def _fin_de_mes(a: int, m: int) -> date:
    return (date(a + (m == 12), (m % 12) + 1, 1)) - timedelta(days=1)


def cuadre_por_mes(db: Session, cuenta: Cuenta, hoy: date | None = None, inicio_pp: datetime | None = None) -> dict:
    """Por mes: cuadra / diferencia / sin_extracto (solo desde el primer extracto con saldo) + alerta si un mes que
    cuadraba ya no cuadra. Usa el extracto más reciente de cada mes."""
    hoy = hoy or ahora_co().date()
    hist = [h for h in db.query(HistorialExtracto).filter(HistorialExtracto.cuenta_id == cuenta.id).order_by(HistorialExtracto.creado_en).all()
            if h.estado != "error"]
    con_saldo = [h for h in hist if h.saldo_final_extracto is not None and a_fecha(h.fecha_corte)]
    series = _serie(db, cuenta.id)
    por_mes: dict[str, HistorialExtracto] = {}
    for h in con_saldo:
        f = a_fecha(h.fecha_corte)
        por_mes[f"{f.year}-{f.month:02d}"] = h
    meses, alertas = [], []
    if por_mes:
        a, m = (int(x) for x in min(por_mes).split("-"))
        n = 0
        while (a, m) <= (hoy.year, hoy.month) and n < 36:
            clave = f"{a}-{m:02d}"
            h = por_mes.get(clave)
            fila = {"mes": clave, "etiqueta": f"{_MESES_LARGO[m - 1].capitalize()} {a}", "estado": "sin_extracto"}
            if h:
                ev = evaluar(db, cuenta, saldo_final=h.saldo_final_extracto, fecha_corte=a_fecha(h.fecha_corte),
                             moneda=h.moneda, inicio_pp=inicio_pp, series=series)
                fila.update(estado=ev["estado"], diferencia=ev.get("diferencia"), saldo_extracto=ev.get("saldo_extracto"),
                            saldo_libro=ev.get("saldo_libro"), historial_id=h.id, fecha_corte=h.fecha_corte)
                if ev["estado"] == "diferencia" and h.cuadre_estado == "cuadra":
                    fila["dejo_de_cuadrar"] = True
                    alertas.append({"mes": clave, "historial_id": h.id, "diferencia": ev["diferencia"], "texto": (
                        f"{fila['etiqueta']} cuadraba y ahora tiene una diferencia de {pesos(ev['diferencia'])}. "
                        "Puede ser que se editó o se borró un movimiento de ese mes.")})
            meses.append(fila)
            a, m, n = (a + (m == 12), (m % 12) + 1, n + 1)
    ultimo = None
    for fila in meses:
        if fila["estado"] == "cuadra":
            ultimo = fila
    actual = next((f for f in reversed(meses) if f["estado"] in ("cuadra", "diferencia")), None)
    return {"cuenta_id": cuenta.id, "moneda": cuenta.moneda or "COP", "meses": meses, "alertas": alertas,
            "ultimo_cuadre": ({"mes": ultimo["mes"], "fecha_corte": ultimo.get("fecha_corte")} if ultimo else None),
            "estado_actual": actual, "diagnostico": diagnostico_cuenta(db, cuenta), "orientacion": ORIENTACION}
