"""Reglas PERSONALES de lectura de correos («enséñale a leer este correo»).

Si el lector estándar no entiende un correo, la persona marca una vez dónde está el monto, el comercio
y si fue gasto o ingreso. Se guarda una regla SUYA (tabla `reglas_correo`, siempre filtrada por usuario)
que se aplica a los correos parecidos de esa misma persona.

Decisiones de privacidad (Ley 1581 y política de datos de usuario de Google):
  * Nada se entrena ni se comparte: la regla vale solo para quien la creó.
  * El cuerpo del correo NO se guarda. La regla guarda solo el dominio del remitente, el «esqueleto»
    del asunto (sin números, montos ni nombres propios) y las etiquetas que PRECEDEN a lo marcado
    (p. ej. «la cantidad de:»), es decir texto fijo de la plantilla del banco, no datos de la persona.
  * `esqueleto_anonimo` (para el contador global opcional) es aún más estricto: solo deja palabras de un
    vocabulario fijo de notificaciones; todo lo demás queda como «*».

Todo aquí es función pura (sin base de datos ni red) para poder probarlo con correos sintéticos.
"""
import re
import unicodedata

from app.gmail_extract import _bonito, extraer_monto

COMERCIO_GENERICO = ("gasto sin detalle", "ingreso sin detalle")
_DOMINIOS_LIBRES = {"gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "yahoo.com", "live.com", "icloud.com"}
_SEGUNDO_NIVEL = {"com", "co", "org", "net", "edu", "gov", "mil"}

# Vocabulario cerrado de notificaciones financieras (sin tildes, en minúscula). Una palabra con mayúscula
# que NO esté aquí se toma por nombre propio y se vuelve «*». Nunca debe contener nombres de personas.
VOCABULARIO = frozenset("""
a al con de del desde en el la las los lo un una unos unas por para hacia y o u e se te tu tus su sus mi
ha has fue ya mas menos que como cuando donde tiene nuevo nueva hola gracias importante
pagaste pago pagos pagado pagada compra compraste compras comprado recibiste recibido recibida recibimos
transferencia transferiste transferido transferencias enviaste envio enviado envia retiro retiraste retiros
deposito depositaron consignacion consignaste abono abonaste abonado cargo cargos debito credito cobro cobraron
notificacion notificaciones aviso alerta alertas transaccion transacciones movimiento movimientos operacion
exitosa exitoso aprobada aprobado rechazada rechazado realizada realizado procesada procesado confirmada
confirmacion comprobante recibo factura facturas cuenta cuentas ahorros corriente tarjeta tarjetas virtual
digital nu nequi daviplata bancolombia davivienda bbva itau scotiabank colpatria occidente popular bogota
avvillas falabella banco bancos pse qr dinero plata saldo disponible detalle resumen extracto extractos
mensaje realizaste hiciste hicimos aprobamos procesamos recarga recargaste recargas giro nomina salario
pension intereses rendimientos cuota cuotas avance sobregiro impuesto gmf comision comisiones billetera
suscripcion renovacion servicio servicios publico publicos pagar pagaron pendiente vencimiento
""".split())

_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_PUNTUACION = ".,;:!?¡¿()[]{}\"'*#«»“”"


def plano(texto: str) -> str:
    """Minúsculas y sin tildes, conservando el LARGO (cada carácter se cambia por uno), para que las posiciones
    de la versión simple valgan en el texto original."""
    salida = []
    for ch in texto or "":
        base = unicodedata.normalize("NFD", ch)[0].lower()
        salida.append(base if len(base) == 1 else ch)
    return "".join(salida)


def colapsar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def dominio_remitente(remitente: str) -> str:
    """'Nu <aviso@mail.nu.com.co>' -> 'nu.com.co'. Si el remitente es de un correo gratuito (gmail, hotmail...)
    se conserva la dirección completa: el dominio solo no diría quién envía."""
    m = _RE_CORREO.search((remitente or "").lower())
    if not m:
        return ""
    direccion = m.group(0)
    dominio = direccion.split("@", 1)[1]
    if dominio in _DOMINIOS_LIBRES:
        return direccion
    partes = dominio.split(".")
    n = 3 if len(partes) >= 3 and partes[-2] in _SEGUNDO_NIVEL else 2
    return ".".join(partes[-n:])


def _palabras_del_asunto(asunto: str) -> list[str]:
    """Palabras del asunto en versión simple; las que llevan dígitos o parecen nombre propio pasan a «*»."""
    limpio = _RE_URL.sub(" * ", _RE_CORREO.sub(" * ", asunto or ""))
    res: list[str] = []
    for i, tok in enumerate(limpio.split()):
        nucleo = tok.strip(_PUNTUACION + "$")
        if not nucleo:
            if "$" in tok or "*" in tok:
                res.append("*")
            continue
        if any(ch.isdigit() for ch in nucleo) or "$" in tok:
            res.append("*")
            continue
        norm = plano(nucleo)
        capital = nucleo[0].isupper()
        if capital and norm not in VOCABULARIO and (i > 0 or (nucleo.isupper() and len(nucleo) > 1) or len(nucleo) == 1):
            res.append("*")
        else:
            res.append(norm)
    return res


def _unir(palabras: list[str]) -> str:
    salida: list[str] = []
    for p in palabras:
        if p == "*" and salida and salida[-1] == "*":
            continue
        salida.append(p)
    return " ".join(salida)


def esqueleto_asunto(asunto: str) -> str:
    """Forma del asunto sin lo variable: 'Pagaste en X con Cuenta Nu' -> 'pagaste en * con cuenta nu'.
    Los números, montos y nombres propios (palabras con mayúscula fuera del vocabulario) pasan a «*»."""
    return _unir(_palabras_del_asunto(asunto))[:200]


def esqueleto_anonimo(asunto: str) -> str:
    """Versión para el contador global: SOLO palabras del vocabulario fijo; lo demás «*». Sin dígitos ni nombres.
    '' si no queda nada informativo (menos de dos palabras reales)."""
    palabras = [p if p in VOCABULARIO else "*" for p in _palabras_del_asunto(asunto)]
    esq = _unir(palabras)
    if sum(1 for p in esq.split() if p != "*") < 2:
        return ""
    return esq[:120]


def dominio_anonimo(remitente: str) -> str:
    d = dominio_remitente(remitente)
    return "" if "@" in d else d


def es_comercio_generico(comercio: str) -> bool:
    c = plano((comercio or "").strip())
    return not c or c in COMERCIO_GENERICO


# ── Aprender: del texto marcado a una regla ─────────────────────────────────────────────────
def _palabras_antes(texto: str, pos: int) -> list[str]:
    """Palabras que preceden a `pos` dentro de la misma oración, cortando en la última palabra con dígitos."""
    previo = texto[:pos]
    corte = max(previo.rfind(". "), previo.rfind("! "), previo.rfind("? "))
    if corte >= 0:
        previo = previo[corte + 2:]
    palabras = previo.split()
    for i in range(len(palabras) - 1, -1, -1):
        if any(ch.isdigit() for ch in palabras[i]):
            palabras = palabras[i + 1:]
            break
    return palabras[-6:]


def _buscar(tp: str, etiqueta: str) -> int:
    """Primera aparición de la etiqueta como palabras completas (no a mitad de otra palabra)."""
    m = re.search(r"(?<!\S)" + re.escape(etiqueta), tp)
    return m.start() if m else -1


def _etiqueta_unica(texto: str, pos: int) -> str:
    """La etiqueta MÁS CORTA (1 a 6 palabras antes de `pos`) cuya primera aparición en el texto es la que
    termina justo antes de `pos`. Así «de» solo no sirve, pero «pagaste en:» sí."""
    tp = plano(texto)
    palabras = _palabras_antes(texto, pos)
    for n in range(min(2, len(palabras)), len(palabras) + 1):
        et = plano(" ".join(palabras[-n:]))
        i = _buscar(tp, et)
        if i >= 0 and tp[i + len(et):pos].strip() == "":
            return et
    return plano(" ".join(palabras))


_RE_FIN_COMERCIO = re.compile(r"\s*(.{1,60}?)(?=\.(?:\s|$)|[\n;|]|\s-\s|$)")


def _despues_de(tp: str, texto: str, etiqueta: str) -> str | None:
    """Texto original que sigue a la etiqueta (None si la etiqueta no está)."""
    if etiqueta == "":
        return texto
    i = _buscar(tp, etiqueta)
    if i < 0:
        return None
    return texto[i + len(etiqueta):]


def leer_monto(texto: str, etiqueta: str) -> float:
    resto = _despues_de(plano(texto), texto, etiqueta)
    return 0.0 if resto is None else extraer_monto(resto[:40], sanear=False)


def leer_comercio(texto: str, etiqueta: str) -> str:
    resto = _despues_de(plano(texto), texto, etiqueta)
    if resto is None:
        return ""
    m = _RE_FIN_COMERCIO.match(resto)
    return _bonito(m.group(1)) if m else ""


class ErrorRegla(ValueError):
    """La marca de la persona no se puede convertir en una regla (el mensaje se le muestra tal cual)."""


def derivar_regla(texto: str, monto_texto: str | None, comercio_texto: str | None) -> dict:
    """De lo que la persona tocó en el texto saca las etiquetas fijas que lo preceden.
    Devuelve {'etiqueta_monto', 'etiqueta_comercio'} (None = no marcó ese dato). Comprueba que la regla,
    puesta sobre el mismo texto, devuelva lo marcado; si no, ErrorRegla."""
    texto = colapsar(texto)
    tp = plano(texto)
    sal: dict = {"etiqueta_monto": None, "etiqueta_comercio": None}
    if monto_texto and monto_texto.strip():
        mt = plano(colapsar(monto_texto)).strip(" .,;:")
        pos = tp.find(mt) if mt else -1
        valor = extraer_monto(monto_texto, sanear=False)
        if pos < 0 or valor <= 0:
            raise ErrorRegla("No encontramos ese monto en el correo. Toca de nuevo el número.")
        sal["etiqueta_monto"] = _etiqueta_unica(texto, pos)
        if leer_monto(texto, sal["etiqueta_monto"]) != valor:
            raise ErrorRegla("No pudimos aprender dónde está el monto. Prueba tocando solo el número.")
    if comercio_texto and comercio_texto.strip():
        limpio = colapsar(comercio_texto).strip(" .,;:")
        ct = plano(limpio)
        pos = tp.find(ct) if ct else -1
        if pos < 0:
            raise ErrorRegla("No encontramos ese texto en el correo. Toca de nuevo el nombre.")
        sal["etiqueta_comercio"] = _etiqueta_unica(texto, pos)
        if plano(leer_comercio(texto, sal["etiqueta_comercio"])) != plano(_bonito(limpio)):
            raise ErrorRegla("No pudimos aprender dónde está el nombre. Prueba marcando menos texto.")
    if sal["etiqueta_monto"] is None and sal["etiqueta_comercio"] is None:
        raise ErrorRegla("Marca el monto o el nombre para que podamos aprender.")
    return sal


# ── Aplicar ─────────────────────────────────────────────────────────────────────────────────
def coincide(regla, remitente: str, asunto: str) -> bool:
    esq = esqueleto_asunto(asunto)
    return bool(esq) and regla.remitente_dominio == dominio_remitente(remitente) and regla.esqueleto_asunto == esq


def hay_regla_para(reglas, remitente: str, asunto: str) -> bool:
    return any(coincide(r, remitente, asunto) for r in reglas or [])


def aplicar_regla(correo: dict, reglas) -> dict | None:
    """Lo que enseñó la persona para un correo parecido.

    `correo`: {remitente, asunto, texto (asunto+fragmento+cuerpo), y la lectura estándar: monto, comercio, tipo}.
    `reglas`: filas de `reglas_correo` SOLO de esa persona (el llamador las filtra por usuario).
    Devuelve {'regla_id', y de 'monto' | 'comercio' | 'tipo' lo que cambia} o None si no hay regla o no hay nada
    que cambiar. La lectura estándar correcta NUNCA se pisa, salvo que la regla sea `corrige` (la persona
    corrigió a propósito algo que el lector había leído)."""
    texto = colapsar(correo.get("texto") or "")
    monto_std = float(correo.get("monto") or 0)
    comercio_std = correo.get("comercio") or ""
    for r in reglas or []:
        if not coincide(r, correo.get("remitente", ""), correo.get("asunto", "")):
            continue
        corrige = bool(getattr(r, "corrige", False))
        sal: dict = {}
        if r.etiqueta_monto is not None and (monto_std <= 0 or corrige):
            m = leer_monto(texto, r.etiqueta_monto)
            if m > 0 and m != monto_std:
                sal["monto"] = m
        if r.etiqueta_comercio is not None and (es_comercio_generico(comercio_std) or corrige):
            c = leer_comercio(texto, r.etiqueta_comercio)
            if c and c != comercio_std:
                sal["comercio"] = c
        if r.tipo in ("income", "expense") and (sal or corrige) and r.tipo != correo.get("tipo"):
            sal["tipo"] = r.tipo
        if sal:
            sal["regla_id"] = r.id
            return sal
    return None


def texto_del_mensaje(asunto: str, snippet: str, cuerpo: str) -> str:
    """El texto sobre el que se aprende y se aplica una regla: asunto + cuerpo (o el fragmento si no hay cuerpo).
    Siempre el mismo armado, para que lo que la persona ve al marcar sea lo que luego se lee."""
    return colapsar(f"{asunto or ''} {cuerpo or snippet or ''}")
