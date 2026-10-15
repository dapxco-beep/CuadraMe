"""Motor de consejos personalizados SIN IA externa: reglas puras sobre los datos del usuario.

Diseño (para poder probarlo con números exactos):
  - `generar(datos, hoy)` es PURA: recibe un dict con los datos ya reunidos (cuentas, movimientos con su
    tipo efectivo, presupuestos, metas, deudas, recurrentes) y devuelve la lista de consejos. Sin base de
    datos, sin red, sin reloj implícito.
  - `reunir_datos(db, usuario_id, hoy)` es la parte que lee la base (solo lectura) y arma ese dict.
  - Cada regla es una función `_regla_x(d, hoy) -> list[consejo]`; agregar una nueva = escribir la función
    y ponerla en REGLAS.

Cada consejo: id estable (incluye el periodo o la situación, así si lo descartas no vuelve hasta que haya
algo nuevo), prioridad (1 = urgente, 3 = educativo), título corto, texto en lenguaje llano (1 a 3 frases),
cifra concreta del usuario, y una acción {texto, ruta} que lleva a la pantalla. `aprende` es la lección
de /aprende donde se explica el concepto.

Orientación educativa, NO asesoría financiera: no se recomienda ningún producto ni inversión, ni se promete
ningún resultado."""
import hashlib
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta

AVISO = "Orientación educativa, no es asesoría financiera."

# Lecciones de la pantalla «Aprende» (pwa/src/lib/aprende.js) a las que puede apuntar un consejo.
# Una prueba de la PWA verifica que todas existan allá.
LECCIONES = {
    "presupuesto-50-30-20", "fondo-de-emergencia", "tarjeta-de-credito", "debito-vs-credito",
    "deudas-avalancha-bola-de-nieve", "gastos-hormiga", "revisar-extractos", "donde-rinde-mi-plata",
}

DIAS_HISTORIAL = 120 # cuánto pasado se lee para detectar patrones (suscripciones necesitan >35 días)
UMBRAL_SUBE_PCT = 30  # una categoría "sube" si crece más de esto frente a los 30 días anteriores
MIN_SUBE_PESOS = 50_000  # y si la diferencia es al menos esto (para no avisar por centavos)
HORMIGA_MAX_PESOS = 30_000  # una compra pequeña
HORMIGA_MIN_VECES = 4
HORMIGA_MIN_TOTAL = 40_000
UTILIZACION_ALERTA = 30  # % del cupo
MESES_FONDO_MIN, MESES_FONDO_IDEAL = 3, 6
MIN_SIN_CATEGORIZAR = 5
DIA_META_SIN_APORTE = 8  # antes de este día del mes no se le reclama el aporte a nadie
MAX_METAS_SIN_APORTE = 2  # para no llenar la pantalla
TASA_CARA_EA = 28.0  # % efectivo anual desde el cual una deuda se considera "cara"
CATEGORIAS_SIN_DEFINIR = {"", "otros", "sin categoria", "sin categoría"}


# ── utilidades ───────────────────────────────────────────────────────────────────────
def _pesos(n: float) -> str:
    return "$" + f"{round(n):,.0f}".replace(",", ".")


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")


def _clave_texto(t: str) -> str:
    """Descripción normalizada para agrupar ('Juan Valdez #123' y 'JUAN VALDEZ 456' son lo mismo)."""
    limpio = "".join(c if c.isalpha() or c == " " else " " for c in _sin_acentos(t).lower())
    return " ".join(limpio.split()[:2])


def _corto(texto: str, n: int = 40) -> str:
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


def _ea_de_mensual(tasa_mensual_pct: float) -> float:
    return ((1 + tasa_mensual_pct / 100) ** 12 - 1) * 100


def _consejo(id_, tipo, prioridad, titulo, texto, cifra, accion_texto, ruta, aprende=None) -> dict:
    return {
        "id": id_, "tipo": tipo, "prioridad": prioridad, "titulo": titulo, "texto": texto, "cifra": cifra,
        "accion": {"texto": accion_texto, "ruta": ruta}, "aprende": aprende,
    }


def _mes(hoy: datetime) -> str:
    return hoy.strftime("%Y-%m")


def _gastos(d: dict, desde: datetime, hasta: datetime | None = None) -> list[dict]:
    return [
        m for m in d.get("movimientos", [])
        if m["tipo"] == "expense" and m["fecha"] >= desde and (hasta is None or m["fecha"] < hasta)
    ]


def _gasto_mensual(d: dict, hoy: datetime) -> float:
    """Gasto promedio por mes en los últimos 90 días (o en lo que lleve de historial, mínimo 30 días)."""
    movs = [m for m in d.get("movimientos", []) if m["fecha"] >= hoy - timedelta(days=90)]
    if not movs:
        return 0.0
    dias = max(30, min(90, (hoy - min(m["fecha"] for m in movs)).days))
    return sum(m["monto"] for m in movs if m["tipo"] == "expense") / (dias / 30)


def _liquido(d: dict) -> float:
    """Plata disponible ya: cuentas de ahorro y efectivo con saldo a favor (no tarjetas ni inversiones)."""
    return sum(c["saldo"] for c in d.get("cuentas", []) if c["tipo"] in ("ahorro", "efectivo") and c["saldo"] > 0)


def _tarjetas(d: dict) -> list[dict]:
    return [c for c in d.get("cuentas", []) if c["tipo"] == "credito"]


# ── reglas ───────────────────────────────────────────────────────────────────────────
def _regla_categoria_sube(d, hoy):
    """Gasto de una categoría en los últimos 30 días vs los 30 anteriores."""
    ahora = defaultdict(float)
    antes = defaultdict(float)
    for m in _gastos(d, hoy - timedelta(days=60)):
        (ahora if m["fecha"] >= hoy - timedelta(days=30) else antes)[m["categoria"]] += m["monto"]
    candidatos = []
    for cat, actual in ahora.items():
        previo = antes.get(cat, 0)
        if cat.strip().lower() in CATEGORIAS_SIN_DEFINIR or previo < MIN_SUBE_PESOS:
            continue
        if actual - previo >= MIN_SUBE_PESOS and (actual / previo - 1) * 100 > UMBRAL_SUBE_PCT:
            candidatos.append((actual - previo, cat, actual, previo))
    if not candidatos:
        return []
    dif, cat, actual, previo = max(candidatos)
    pct = round((actual / previo - 1) * 100)
    return [_consejo(
        f"categoria-sube:{cat}:{_mes(hoy)}", "categoria_sube", 2, f"{cat}: gastas {pct} % más",
        f"En los últimos 30 días gastaste {_pesos(actual)} en {cat}, contra {_pesos(previo)} en los 30 días anteriores. "
        "Mirar de dónde viene el aumento es el primer paso para decidir si fue a propósito.",
        f"+{_pesos(dif)}", "Ver en qué gasté", "/informe", "presupuesto-50-30-20")]


def _regla_gastos_hormiga(d, hoy):
    """Compras pequeñas que se repiten (café, domicilios): una a una parecen nada, juntas pesan."""
    grupos = defaultdict(list)
    for m in _gastos(d, hoy - timedelta(days=30)):
        if m["monto"] <= HORMIGA_MAX_PESOS and _clave_texto(m["descripcion"]):
            grupos[_clave_texto(m["descripcion"])].append(m)
    candidatos = [
        (sum(x["monto"] for x in lista), clave, lista) for clave, lista in grupos.items()
        if len(lista) >= HORMIGA_MIN_VECES and sum(x["monto"] for x in lista) >= HORMIGA_MIN_TOTAL
    ]
    if not candidatos:
        return []
    total, clave, lista = max(candidatos, key=lambda t: t[0])
    nombre = _corto(lista[-1]["descripcion"])
    return [_consejo(
        f"hormiga:{clave}:{_mes(hoy)}", "gastos_hormiga", 3, "Un gasto hormiga se repite",
        f"Hiciste {len(lista)} compras pequeñas en «{nombre}» en 30 días y sumaron {_pesos(total)}. "
        f"Si sigue así, al año serían unos {_pesos(total * 12)}. No tienes que dejarlo: solo decidir cuánto vale para ti.",
        _pesos(total), "Ver mis movimientos", "/movimientos", "gastos-hormiga")]


def _regla_tarjeta_solo_minimo(d, hoy):
    out = []
    for t in _tarjetas(d):
        pago = t.get("ultimo_pago")
        minimo, usado = t.get("pago_minimo") or 0, t.get("cupo_usado") or 0
        if not pago or minimo <= 0 or usado <= 0 or (hoy - pago["fecha"]).days > 40:
            continue
        if pago["monto"] > minimo * 1.1:
            continue
        interes = t.get("interes_estimado")
        extra = f" Con tu tasa, ese saldo te cobra unos {_pesos(interes)} de interés cada mes." if interes else ""
        out.append(_consejo(
            f"solo-minimo:{t['id']}:{_mes(hoy)}", "solo_minimo", 1, f"Pagaste el mínimo de {t['nombre']}",
            f"El pago mínimo solo evita que caigas en mora: lo que no pagas sigue generando intereses. "
            f"Te quedan {_pesos(usado)} por pagar.{extra}",
            _pesos(usado), "Ver mi tarjeta", "/cuentas", "tarjeta-de-credito"))
    return out


def _regla_utilizacion(d, hoy):
    out = []
    for t in _tarjetas(d):
        pct = t.get("utilizacion_pct")
        if pct is None or pct < UTILIZACION_ALERTA:
            continue
        out.append(_consejo(
            f"utilizacion:{t['id']}:{_mes(hoy)}", "utilizacion", 1 if pct >= 70 else 2,
            f"Usas el {round(pct)} % del cupo de {t['nombre']}",
            f"Llevas {_pesos(t['cupo_usado'])} de un cupo de {_pesos(t['cupo_total'])}. Usar más del 30 % del cupo "
            "suele ser señal de estar muy apretado y puede pesar en tu historial crediticio.",
            f"{round(pct)} %", "Ver mi tarjeta", "/cuentas", "tarjeta-de-credito"))
    return out


def _regla_fondo_emergencia(d, hoy):
    gasto = _gasto_mensual(d, hoy)
    if gasto <= 0:
        return []
    liquido = _liquido(d)
    meses = liquido / gasto
    if meses >= MESES_FONDO_MIN:
        return []
    meta = gasto * MESES_FONDO_MIN
    nivel = "sin" if meses < 1 else "poco"
    return [_consejo(
        f"fondo-emergencia:{nivel}", "fondo_emergencia", 2, "Tu colchón para imprevistos es corto",
        f"Gastas unos {_pesos(gasto)} al mes y tienes {_pesos(liquido)} disponibles: te alcanza para {meses:.1f} meses. "
        f"Una guía común es guardar entre {MESES_FONDO_MIN} y {MESES_FONDO_IDEAL} meses de gastos; el primer escalón serían {_pesos(meta)}.",
        f"{meses:.1f} meses", "Crear una meta", "/metas", "fondo-de-emergencia")]


def _regla_ahorro_sin_meta(d, hoy):
    if any(m.get("activa", True) for m in d.get("metas", [])):
        return []
    liquido = _liquido(d)
    if liquido < max(500_000, _gasto_mensual(d, hoy) * 0.5):
        return []
    return [_consejo(
        "ahorro-sin-meta", "ahorro_sin_meta", 3, "Tu ahorro no tiene un propósito",
        f"Tienes {_pesos(liquido)} en tus cuentas y ninguna meta creada. Ponerle nombre y fecha a la plata "
        "(viaje, imprevistos, estudio) hace más fácil no gastarla sin querer.",
        _pesos(liquido), "Crear una meta", "/metas", "fondo-de-emergencia")]


def _regla_meta_sin_aporte(d, hoy):
    """Meta activa y sin completar a la que aún no le llega ningún aporte este mes (ni a mano ni automático)."""
    if hoy.day < DIA_META_SIN_APORTE:
        return []
    candidatas = []
    for m in d.get("metas", []):
        objetivo, actual = m.get("monto_objetivo") or 0, m.get("monto_actual") or 0
        if not m.get("activa", True) or not m.get("id") or objetivo <= 0 or actual >= objetivo:
            continue
        creada = m.get("creada_en")
        if creada and (hoy - creada).days < 7:
            continue  # recién creada: démosle tiempo
        ultimo = m.get("ultimo_aporte")
        if ultimo and (ultimo.year, ultimo.month) == (hoy.year, hoy.month):
            continue
        candidatas.append((objetivo - actual, m))
    candidatas.sort(key=lambda t: -t[0])
    out = []
    for faltante, m in candidatas[:MAX_METAS_SIN_APORTE]:
        c = _consejo(
            f"meta-sin-aporte:{m['id']}:{_mes(hoy)}", "meta_sin_aporte", 2, f"«{_corto(m['nombre'])}» no ha recibido aporte este mes",
            f"A tu meta le faltan {_pesos(faltante)} y este mes aún no has apartado nada. Un aporte pequeño hoy "
            "mantiene el ritmo; lo importante es la constancia, no el monto.",
            _pesos(faltante), "Aportar ahora", "/metas", "fondo-de-emergencia")
        c["meta_id"] = m["id"]
        out.append(c)
    return out


def _regla_sin_presupuesto(d, hoy):
    if d.get("presupuestos"):
        return []
    gasto = sum(m["monto"] for m in _gastos(d, hoy - timedelta(days=30)))
    if gasto < 100_000:
        return []
    return [_consejo(
        "sin-presupuesto", "sin_presupuesto", 2, "Aún no defines un presupuesto",
        f"En 30 días gastaste {_pesos(gasto)}. Un presupuesto es ponerle un tope a las categorías donde más se va la plata; "
        "así te avisamos antes de pasarte, no después.",
        _pesos(gasto), "Crear presupuesto", "/presupuesto", "presupuesto-50-30-20")]


def _regla_deudas(d, hoy):
    deudas = [x for x in d.get("deudas", []) if x["saldo"] > 0]
    if not deudas:
        return []
    cara = max(deudas, key=lambda x: x["tasa_mensual"])
    ea = _ea_de_mensual(cara["tasa_mensual"])
    if len(deudas) == 1:
        if ea < TASA_CARA_EA:
            return []
        return [_consejo(
            f"deuda-cara:{cara['id']}", "deudas", 2, f"{_corto(cara['nombre'])} es una deuda cara",
            f"Esta deuda cobra cerca de {ea:.0f} % efectivo anual. Cada peso extra que le abones ahorra más intereses "
            "que dejarlo quieto en una cuenta de ahorros.",
            f"{ea:.0f} % EA", "Ver mis deudas", "/deudas", "deudas-avalancha-bola-de-nieve")]
    chica = min(deudas, key=lambda x: x["saldo"])
    if cara["id"] == chica["id"]:
        detalle = f"Con «{_corto(cara['nombre'])}» tienes la suerte de que es la de mayor tasa ({ea:.0f} % EA) y la más pequeña: empieza por ahí."
    else:
        detalle = (f"Avalancha: abonar extra a «{_corto(cara['nombre'])}» ({ea:.0f} % EA, la más cara) te ahorra más intereses. "
                   f"Bola de nieve: empezar por «{_corto(chica['nombre'])}» ({_pesos(chica['saldo'])}, la más pequeña) la cierras más rápido.")
    return [_consejo(
        f"deudas-orden:{cara['id']}", "deudas", 2, "¿Cuál deuda pagar primero?",
        f"{detalle} Mientras tanto, paga el mínimo de todas.",
        f"{len(deudas)} deudas", "Comparar métodos", "/deudas", "deudas-avalancha-bola-de-nieve")]


def _regla_suscripciones(d, hoy):
    """Cobros que se repiten cada mes y que no están registrados como recurrentes."""
    from app.deteccion import detectar_recurrentes

    movs = [
        {"id": m["id"], "descripcion": m["descripcion"], "categoria": m["categoria"], "tipo": m["tipo"],
         "monto": m["monto"], "fecha": m["fecha"], "cuenta_id": m.get("cuenta_id")}
        for m in d.get("movimientos", []) if m["tipo"] == "expense"
    ]
    registrados = {_clave_texto(r) for r in d.get("recurrentes", [])}
    sugeridas = [
        s for s in detectar_recurrentes(movs)
        if _clave_texto(s["descripcion"]) not in registrados and s["ultima_fecha"] >= hoy - timedelta(days=45)
    ]
    if not sugeridas:
        return []
    total = sum(s["monto_promedio"] for s in sugeridas)
    nombres = ", ".join(_corto(s["descripcion"], 24) for s in sugeridas[:3])
    firma = hashlib.sha1("|".join(sorted(_clave_texto(s["descripcion"]) for s in sugeridas)).encode()).hexdigest()[:8]
    return [_consejo(
        f"suscripciones:{firma}", "suscripciones", 3, "Detectamos cobros que se repiten cada mes",
        f"Parece que pagas {len(sugeridas)} servicio(s) mensual(es) ({nombres}) que sumarían {_pesos(total)} al mes. "
        "Si los registras como recurrentes te avisamos antes de cada cobro, y es buen momento para revisar si aún los usas.",
        f"{_pesos(total)}/mes", "Registrar recurrentes", "/recurrentes", "gastos-hormiga")]


def _regla_ingreso_sin_repartir(d, hoy):
    desde = hoy - timedelta(days=7)
    ingresos = [m for m in d.get("movimientos", []) if m["tipo"] == "income" and m["fecha"] >= desde and m["monto"] >= 100_000]
    if not ingresos:
        return []
    ing = max(ingresos, key=lambda m: m["monto"])
    if any(m.get("fuente") == "aporte_meta" and m["fecha"] >= ing["fecha"] for m in d.get("movimientos_neutros", [])):
        return []
    n = ing["monto"]
    return [_consejo(
        f"ingreso-sin-repartir:{ing['id']}", "ingreso_sin_repartir", 2, "Te entró plata: ¿ya la repartiste?",
        f"Recibiste {_pesos(n)}. Una forma simple de repartirla es 50/30/20: {_pesos(n * .5)} para necesidades, "
        f"{_pesos(n * .3)} para gustos y {_pesos(n * .2)} para ahorro o deudas. Ajusta los porcentajes a tu realidad.",
        _pesos(n), "Repartir mi ingreso", "/presupuesto", "presupuesto-50-30-20")]


def _regla_sin_categorizar(d, hoy):
    # Misma definición que el contador de Inicio y de Movimientos (app/pendientes.py): lo que una
    # regla tuya, el aprendizaje o el diccionario ya categorizó con seguridad NO cuenta.
    from app import pendientes

    sil = set(d.get("silenciadas") or ())
    sin = [
        m for m in d.get("movimientos", [])
        if m["fecha"] >= hoy - timedelta(days=60) and pendientes.motivo(m, sil)
    ]
    if len(sin) < MIN_SIN_CATEGORIZAR:
        return []
    total = sum(m["monto"] for m in sin if m["tipo"] == "expense")
    return [_consejo(
        f"sin-categorizar:{_mes(hoy)}", "sin_categorizar", 3, "Puedes ordenar lo que más pesa",
        f"Hay {len(sin)} movimientos sin categoría clara"
        + (f" (gastos por {_pesos(total)})" if total else "")
        + ". No hace falta categorizarlos todos: con los comercios que más pesan o se repiten ya ves "
        "en qué se va tu plata. El resto puede quedarse como está.",
        f"{len(sin)} movimientos", "Ver lo que más pesa", "/categorizar", "revisar-extractos")]


def _regla_debito_vs_credito(d, hoy):
    ids_tarjeta = {t["id"] for t in _tarjetas(d)}
    if not ids_tarjeta:
        return []
    compras = sum(m["monto"] for m in _gastos(d, hoy - timedelta(days=30)) if m.get("cuenta_id") in ids_tarjeta)
    if compras <= 0:
        return []
    return [_consejo(
        "debito-vs-credito", "debito_vs_credito", 3, "Compras con tarjeta: es plata que aún no pagas",
        f"En 30 días compraste {_pesos(compras)} con tarjeta de crédito. Con débito la plata sale de tu cuenta al instante; "
        "con crédito el banco te la presta y debes devolverla en tu fecha de pago. Tu saldo de ahorros no baja hasta entonces.",
        _pesos(compras), "Aprender la diferencia", "/aprende", "debito-vs-credito")]


def _regla_fechas_tarjeta(d, hoy):
    out = []
    for t in _tarjetas(d):
        dp, dc = t.get("dias_para_pago"), t.get("dias_para_corte")
        if dp is not None and 0 <= dp <= 5 and (t.get("falta_para_evitar_intereses") or t.get("cupo_usado")):
            monto = t.get("falta_para_evitar_intereses") or t["cupo_usado"]
            cuando = "hoy" if dp == 0 else "mañana" if dp == 1 else f"en {dp} días"
            out.append(_consejo(
                f"pago:{t['id']}:{t.get('proximo_pago')}", "fecha_pago", 1 if dp <= 2 else 2, f"Pagas {t['nombre']} {cuando}",
                f"Para no pagar intereses necesitas {_pesos(monto)}. Pagar el total del extracto, y no solo el mínimo, es lo que evita los intereses.",
                _pesos(monto), "Ver mi tarjeta", "/cuentas", "tarjeta-de-credito"))
        if dc is not None and 0 <= dc <= 3:
            cuando = "hoy" if dc == 0 else "mañana" if dc == 1 else f"en {dc} días"
            out.append(_consejo(
                f"corte:{t['id']}:{t.get('proximo_corte')}", "fecha_corte", 3, f"{t['nombre']} corta {cuando}",
                "Lo que compres hasta el corte entra en este extracto; lo que compres después pasa al siguiente y te da más días para pagarlo.",
                f"{dc} día(s)" if dc else "hoy", "Ver mi tarjeta", "/cuentas", "tarjeta-de-credito"))
    return out


def _regla_renta(d, hoy):
    """Entre la apertura del plazo de renta y su vencimiento, solo si el resultado es «sí» o «cerca».
    d["renta"] = {anio, clave, dias_restantes, abierto} lo arma reunir_datos solo dentro de esa ventana."""
    r = d.get("renta")
    if not r or not r.get("abierto") or r.get("clave") not in ("si", "cerca") or r.get("dias_restantes", -1) < 0:
        return []
    n = r["dias_restantes"]
    cuando = "Hoy vence" if n == 0 else f"Falta {n} día" if n == 1 else f"Faltan {n} días"
    titulo = "Hoy vence el plazo para declarar renta" if n == 0 else f"{cuando} para declarar renta"
    probable = "Probablemente te toca declarar" if r["clave"] == "si" else "Estás cerca de los topes para declarar"
    return [_consejo(
        f"renta:{r['anio']}", "renta", 1 if n <= 3 else 2, titulo,
        f"{probable} la renta del {r['anio']}. Revisa tus números y, si tienes dudas, confírmalo con la DIAN o un contador. "
        "Es una ayuda informativa, no asesoría tributaria.",
        f"{n} día(s)", "Ver mi resultado", "/impuestos")]


def _regla_plata_ociosa(d, hoy):
    """Saldo principal de una cuenta de ahorro que rinde mucho menos que la tasa de referencia de los
    productos de ahorro a la vista. Informativo: no recomienda ningún banco; la persona puede silenciarlo
    (los ids empiezan por «plata-ociosa» y la PWA guarda ese silencio en el dispositivo)."""
    out = []
    for o in sorted(d.get("plata_ociosa", []), key=lambda x: -x["extra_anual"])[:2]:
        out.append(_consejo(
            f"plata-ociosa:{o['cuenta_id']}:{_mes(hoy)}", "plata_ociosa", 3,
            f"Tu plata en {o['nombre']} casi no rinde",
            f"Tienes {_pesos(o['saldo'])} en el saldo principal ganando {o['tasa_actual']:.2f} % E.A. Con una tasa de "
            f"referencia de ~{o['tasa_ref']:.1f} % E.A. (la de una cajita o bolsillo) serían ~{_pesos(o['extra_anual'])} "
            "más al año. Es una estimación: las condiciones cambian, verifícalas en tu banco.",
            f"~{_pesos(o['extra_anual'])}/año", "Ver las opciones", "/cuentas", "donde-rinde-mi-plata"))
        out[-1]["silenciable"] = True
    return out


def _plata_ociosa_de(db, usuario_id: str, hoy: datetime) -> list[dict]:
    try:
        from app import rendimientos

        return rendimientos.resumen(db, usuario_id, hoy)["comparacion"]["ociosa"]
    except Exception:  # un consejo opcional nunca debe tumbar los demás
        return []


def _regla_costos_bancarios(d, hoy):
    """Alertas de «lo que te cuesta tu plata» (mora, costo que sube, cuota nueva, solo el mínimo) y cargos
    inusuales/suscripciones. Ya vienen calculadas con ids estables: aquí solo se vuelven consejos."""
    out = []
    for a in d.get("costos_alertas", []):
        c = _consejo(a["id"], a["tipo"], a["prioridad"], a["titulo"], a["texto"], a["cifra"],
                     a["accion"]["texto"], a["accion"]["ruta"], a.get("aprende"))
        out.append(c)
    return out


CONCENTRACION_MAX_PCT = 40.0


def _regla_inversiones(d, hoy):
    """Solo si el usuario tiene inversiones (todo es opcional). Ids estables por mes/situación;
    descartables en el dispositivo. Orientación educativa, no recomienda ningún producto."""
    inv = d.get("inversiones")
    if not inv or not inv.get("valor_total"):
        return []
    out = []
    top = inv.get("concentracion")
    if top and top["pct"] > CONCENTRACION_MAX_PCT and inv.get("n_posiciones", 0) > 1:
        out.append(_consejo(
            f"inv-concentracion:{_corto(top['nombre'] or 'x', 20)}:{_mes(hoy)}", "inversiones", 2,
            f"{_corto(top['nombre'] or 'Una posición', 30)} pesa mucho en tu portafolio",
            f"Una sola inversión es el {top['pct']:.0f} % de tu portafolio. Si le va mal, te afecta mucho. "
            "Diversificar es una idea general para repartir ese riesgo; la decisión es tuya.",
            f"{top['pct']:.0f} %", "Ver mi portafolio", "/inversiones"))
    gasto = _gasto_mensual(d, hoy)
    liquido = _liquido(d)
    if gasto > 0 and liquido >= 0:
        meses = liquido / gasto
        if meses < MESES_FONDO_MIN:
            out.append(_consejo(
                f"inv-fondo-primero:{_mes(hoy)}", "inversiones", 2,
                "Antes de invertir más, mira tu fondo de emergencia",
                f"Tu plata disponible alcanza para ~{meses:.1f} meses de gastos. Muchas guías sugieren tener "
                f"{MESES_FONDO_MIN} a {MESES_FONDO_IDEAL} meses a la mano antes de seguir invirtiendo, porque "
                "una inversión puede bajar justo cuando la necesitas.",
                f"{meses:.1f} meses", "Ver fondo de emergencia", "/aprende", "fondo-de-emergencia"))
        elif meses > MESES_FONDO_IDEAL * 2:
            out.append(_consejo(
                f"inv-plata-ociosa:{_mes(hoy)}", "inversiones", 3,
                "Tienes mucha plata quieta frente a lo que invertiste",
                f"Tienes {_pesos(liquido)} disponibles (~{meses:.0f} meses de gastos) y "
                f"{_pesos(inv['valor_total'])} invertidos. Revisar si esa plata quieta trabaja es solo "
                "una idea; no es una recomendación de compra.",
                _pesos(liquido), "Ver mi patrimonio", "/patrimonio", "donde-rinde-mi-plata"))
    return out


REGLAS = [
    _regla_inversiones,
    _regla_costos_bancarios, _regla_renta, _regla_fechas_tarjeta, _regla_tarjeta_solo_minimo, _regla_utilizacion, _regla_deudas, _regla_fondo_emergencia,
    _regla_categoria_sube, _regla_ingreso_sin_repartir, _regla_sin_presupuesto, _regla_gastos_hormiga,
    _regla_suscripciones, _regla_meta_sin_aporte, _regla_ahorro_sin_meta, _regla_sin_categorizar, _regla_debito_vs_credito,
    _regla_plata_ociosa,
]


def generar(datos: dict, hoy: datetime) -> list[dict]:
    """Todos los consejos que aplican hoy, urgentes primero (el orden entre iguales sigue el de REGLAS).
    Pura: sin base de datos ni red."""
    out: list[dict] = []
    for regla in REGLAS:
        out.extend(regla(datos, hoy))
    vistos, unicos = set(), []
    for c in out:  # ids repetidos nunca deberían pasar, pero un id debe identificar UN consejo
        if c["id"] not in vistos:
            vistos.add(c["id"])
            unicos.append(c)
    return sorted(unicos, key=lambda c: c["prioridad"])  # sorted es estable


# ── lectura de la base (solo lectura) ────────────────────────────────────────────────
def _inversiones_de(db, usuario_id: str, hoy: datetime) -> dict:
    try:
        from app.routers.inversiones import calcular_portafolio

        r = calcular_portafolio(db, usuario_id, hoy)
        if not r["posiciones"]:
            return {}
        return {"valor_total": r["valor_total"], "concentracion": r["concentracion"],
                "n_posiciones": len(r["posiciones"])}
    except Exception:  # un consejo opcional nunca debe tumbar los demás
        return {}


def reunir_datos(db, usuario_id: str, hoy: datetime) -> dict:
    from app import contabilidad as cont
    from app.compartidos import cuentas_ids_accesibles
    from app.contabilidad import ConvertidorBase, moneda_base_de
    from app.models import Cuenta, Deuda, Meta, Movimiento, Presupuesto, Recurrente
    from app.tarjetas import calc_tarjeta, extractos_guardados, movimientos_tras_corte

    ids = cuentas_ids_accesibles(db, usuario_id)
    cuentas_db = db.query(Cuenta).filter(Cuenta.id.in_(ids)).all() if ids else []
    monedas = {c.id: c.moneda or "COP" for c in cuentas_db}
    conv = ConvertidorBase(moneda_base_de(db, usuario_id))

    def cop(monto, cuenta_id):
        mon = monedas.get(cuenta_id, "COP")
        return conv(float(monto or 0), mon)

    guardados = extractos_guardados(db, [c.id for c in cuentas_db if c.tipo == "credito"])
    cuentas = []
    for c in cuentas_db:
        item = {"id": c.id, "nombre": c.nombre, "tipo": c.tipo, "saldo": cop(c.saldo, c.id)}
        if c.tipo == "credito":
            movs_t = movimientos_tras_corte(db, c, hoy) if c.dia_corte else None
            info = calc_tarjeta(c, hoy, movs_t, guardados.get(c.id))
            item.update({k: info.get(k) for k in (
                "cupo_usado", "utilizacion_pct", "pago_minimo", "interes_estimado", "dias_para_pago", "dias_para_corte",
                "proximo_pago", "proximo_corte", "falta_para_evitar_intereses")})
            item["cupo_total"] = c.cupo_total
        cuentas.append(item)

    desde = hoy - timedelta(days=DIAS_HISTORIAL)
    from app import punto_partida

    inicio_pp = punto_partida.fecha_inicio(db, usuario_id)  # los consejos arrancan en el punto de partida
    if inicio_pp and desde < inicio_pp:
        desde = inicio_pp
    movs_db = (
        db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= desde).all() if ids else []
    )
    tipos_cuenta = cont.tipos_cuenta_de(db, ids) if ids else {}
    efectivos = cont.tipos_efectivos(movs_db, tipos_cuenta)
    movimientos, neutros, pagos = [], [], {}
    for m in movs_db:
        base = {
            "id": m.id, "cuenta_id": m.cuenta_id, "fecha": m.fecha, "descripcion": m.descripcion or "",
            "categoria": m.categoria or "", "monto": cop(m.monto, m.cuenta_id), "fuente": m.fuente,
            "cat_confirmada": m.cat_confirmada is not False,
            "cat_origen": m.cat_origen,
        }
        tipo = efectivos.get(m.id, "transfer")
        if tipo in ("income", "expense"):
            movimientos.append({**base, "tipo": tipo})
        else:
            neutros.append({**base, "tipo": "transfer"})
            # El abono que "entra" a una tarjeta es el pago que hizo el usuario.
            if m.tipo == "income" and tipos_cuenta.get(m.cuenta_id) == "credito" and m.fuente not in (cont.FUENTE_AJUSTE,):
                previo = pagos.get(m.cuenta_id)
                if not previo or m.fecha > previo["fecha"]:
                    pagos[m.cuenta_id] = {"monto": base["monto"], "fecha": m.fecha}
    for c in cuentas:
        if c["id"] in pagos:
            c["ultimo_pago"] = pagos[c["id"]]

    renta = None
    try:  # recordatorio de renta: solo dentro de la ventana del plazo (así Inicio no paga el cálculo el resto del año)
        from app import paises, renta_alerta

        if not paises.tiene_funcion(paises.pais_de_usuario(db, usuario_id), "renta_dian"):
            raise LookupError("la renta DIAN solo aplica a Colombia")
        anio_g = renta_alerta.anio_gravable_vigente(hoy.date())
        if renta_alerta.en_ventana_aviso(anio_g, hoy.date()):
            r = renta_alerta.renta_de_usuario(db, usuario_id, anio_g, hoy)
            renta = {"anio": anio_g, "clave": r["resultado"]["clave"], "abierto": True,
                     "dias_restantes": r["plazo"]["dias_restantes"]}
    except Exception:
        renta = None  # un fallo del cálculo nunca debe tumbar los demás consejos
    costos_alertas = []
    try:  # el análisis de costos nunca debe tumbar los consejos
        from app import cargos_inusuales, costos_bancarios

        ahora_d = hoy.date()
        costos_alertas = costos_bancarios.analizar_usuario(
            db, usuario_id, ahora_d.replace(day=1), ahora_d, hoy)["alertas"]
        costos_alertas += cargos_inusuales.detectar_usuario(db, usuario_id, hoy)["alertas"]
    except Exception:  # noqa: BLE001
        costos_alertas = []

    activas = lambda q, M: q.filter(M.usuario_id == usuario_id, M.activo == True).all()  # noqa: E731, E712
    return {
        "costos_alertas": costos_alertas,
        "cuentas": cuentas,
        "movimientos": movimientos,
        "movimientos_neutros": neutros,
        "presupuestos": [{"categoria": p.categoria, "limite": p.limite} for p in activas(db.query(Presupuesto), Presupuesto)],
        "metas": [{"id": m.id, "nombre": m.nombre, "monto_actual": m.monto_actual or 0,
                   "monto_objetivo": m.monto_objetivo or 0, "activa": m.activa is not False,
                   "creada_en": m.creado_en or m.fecha_inicio,
                   "ultimo_aporte": max((f for f in (m.ultimo_aporte, m.ultimo_aporte_automatico) if f), default=None)}
                  for m in db.query(Meta).filter(Meta.usuario_id == usuario_id).all()],
        "deudas": [{"id": x.id, "nombre": x.nombre, "saldo": x.saldo_actual or 0, "tasa_mensual": x.tasa_mensual or 0}
                   for x in db.query(Deuda).filter(Deuda.usuario_id == usuario_id, Deuda.activa == True).all()],  # noqa: E712
        "recurrentes": [r.nombre for r in activas(db.query(Recurrente), Recurrente)],
        "renta": renta,
        "plata_ociosa": _plata_ociosa_de(db, usuario_id, hoy),
        "inversiones": _inversiones_de(db, usuario_id, hoy),
        "silenciadas": sorted(__import__("app.pendientes", fromlist=["x"]).silencios(db, usuario_id)),
    }


def consejos_de_usuario(db, usuario_id: str, hoy: datetime) -> dict:
    return {"aviso": AVISO, "consejos": generar(reunir_datos(db, usuario_id, hoy), hoy)}
