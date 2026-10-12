"""Lo que cuesta (y lo que rinde) tener tu plata: clasificación de líneas de extracto.

Puro: sin base de datos ni red. Reconoce por PATRÓN DE LÍNEA los cobros que los bancos
colombianos meten en los extractos y que la gente paga sin notarlo:

  - «Intereses de tarjeta»  (intereses corrientes, de mora, de compras/avances...)
  - «Cuota de manejo»
  - «Comisiones y seguros»  (comisiones, seguro de deudores, costo de transacción...)
  - «4x1000 (GMF)»          (gravamen a los movimientos financieros)
  - «Rendimientos»          (ingreso: intereses ganados, cajitas, CDT, cuenta de ahorros)

Por qué «patrón de línea» y no «palabra suelta»: la palabra debe abrir la línea (con a lo sumo
unos conectores antes: «Pago de», «Cargo», «IVA»...). Así «INTERESES DE COMPRAS» sí cuenta, pero
«Cena con intereses comunes» o el comercio «Comisiones Express» no se confunden con un cobro.

Quien clasifica de verdad es `comercios_conocidos.clasificar_por_diccionario` (que llama aquí);
las reglas del usuario (ReglaCategoria) siempre mandan antes que esto."""
import re
import unicodedata

CAT_RENDIMIENTOS = "Rendimientos"
CAT_INTERESES = "Intereses de tarjeta"
CAT_CUOTA = "Cuota de manejo"
CAT_COMISIONES = "Comisiones y seguros"
CAT_GMF = "4x1000 (GMF)"

# (nombre, emoji, tipo): se crean como categorías de sistema (ocultas del presupuesto por defecto,
# visibles en informes). El tipo dice si suele ser gasto o ingreso.
CATEGORIAS_COSTOS = [
    (CAT_INTERESES, "💳", "gasto"),
    (CAT_CUOTA, "🧾", "gasto"),
    (CAT_COMISIONES, "🏦", "gasto"),
    (CAT_GMF, "🧮", "gasto"),
    (CAT_RENDIMIENTOS, "📈", "ingreso"),
]
NOMBRES_COSTOS = [n for n, _, _ in CATEGORIAS_COSTOS if n != CAT_RENDIMIENTOS]
NOMBRES_SISTEMA = {n for n, _, _ in CATEGORIAS_COSTOS}

# Palabras que pueden ir ANTES del concepto sin cambiar de qué se trata la línea.
_PREFIJOS = {
    "pago", "pagos", "cargo", "cargos", "abono", "cobro", "valor", "debito", "credito", "de", "por", "del", "la",
    "el", "los", "las", "mensual", "automatico", "automatica", "tc", "tdc", "tarjeta", "nu", "bancolombia",
    "davivienda", "bbva", "nequi", "daviplata", "iva", "impuesto", "total", "tu", "su", "mi", "aplicado",
    "aplicada", "nuevo", "nueva", "devolucion", "reverso", "reversion", "reintegro",
}
_MAX_PREFIJO = 4

# Conceptos: (palabras, categoría). Los más largos se prueban primero.
_CONCEPTOS: list[tuple[tuple[str, ...], str]] = [
    # intereses que se PAGAN
    (("intereses", "de", "corriente"), CAT_INTERESES), (("intereses", "de", "corrientes"), CAT_INTERESES),
    (("intereses", "corrientes"), CAT_INTERESES), (("intereses", "corriente"), CAT_INTERESES),
    (("interes", "corriente"), CAT_INTERESES), (("interes", "corrientes"), CAT_INTERESES),
    (("intereses", "de", "mora"), CAT_INTERESES), (("interes", "de", "mora"), CAT_INTERESES),
    (("intereses", "mora"), CAT_INTERESES), (("interes", "mora"), CAT_INTERESES),
    (("intereses", "moratorios"), CAT_INTERESES),
    (("intereses", "de", "compras"), CAT_INTERESES), (("intereses", "compras"), CAT_INTERESES),
    (("intereses", "de", "avances"), CAT_INTERESES), (("intereses", "avances"), CAT_INTERESES),
    (("intereses", "de", "financiacion"), CAT_INTERESES), (("intereses", "por", "financiacion"), CAT_INTERESES),
    (("intereses", "financiacion"), CAT_INTERESES), (("intereses", "sobregiro"), CAT_INTERESES),
    (("intereses", "de", "sobregiro"), CAT_INTERESES),
    # cuota de manejo
    (("cuota", "de", "manejo"), CAT_CUOTA), (("cuota", "manejo"), CAT_CUOTA),
    # 4x1000
    (("gmf",), CAT_GMF), (("gravamen",), CAT_GMF), (("gravamen", "movimientos", "financieros"), CAT_GMF),
    (("gravamen", "a", "los", "movimientos", "financieros"), CAT_GMF),
    (("gravamen", "al", "movimiento"), CAT_GMF), (("gravamen", "al", "movimiento", "financiero"), CAT_GMF),
    (("gravamen", "movimiento", "financiero"), CAT_GMF),
    (("4x1000",), CAT_GMF), (("4", "x", "1000"), CAT_GMF), (("4", "por", "mil"), CAT_GMF),
    (("4", "por", "1000"), CAT_GMF), (("cuatro", "por", "mil"), CAT_GMF),
    # comisiones y seguros
    (("comision",), CAT_COMISIONES), (("comisiones",), CAT_COMISIONES),
    (("seguro", "deudores"), CAT_COMISIONES), (("seguro", "de", "deudores"), CAT_COMISIONES),
    (("seguro", "deudor"), CAT_COMISIONES), (("seguro", "de", "deudor"), CAT_COMISIONES),
    (("seguro", "desempleo"), CAT_COMISIONES), (("seguro", "de", "desempleo"), CAT_COMISIONES),
    (("seguro", "tarjeta"), CAT_COMISIONES), (("cobro", "seguro"), CAT_COMISIONES),
    (("costo", "transaccion"), CAT_COMISIONES), (("costo", "de", "transaccion"), CAT_COMISIONES),
    (("costo", "transferencia"), CAT_COMISIONES), (("cobro", "por", "transferencia"), CAT_COMISIONES),
    (("retiro", "cajero", "ajeno"), CAT_COMISIONES), (("retiro", "en", "cajero", "ajeno"), CAT_COMISIONES),
    (("retiro", "cajero", "otra", "red"), CAT_COMISIONES), (("retiro", "otra", "red"), CAT_COMISIONES),
    (("cobro",), CAT_COMISIONES),
    # rendimientos (INGRESO)
    (("intereses", "ganados"), CAT_RENDIMIENTOS), (("interes", "ganado"), CAT_RENDIMIENTOS),
    (("intereses", "ganado"), CAT_RENDIMIENTOS),
    (("abono", "intereses"), CAT_RENDIMIENTOS), (("abono", "de", "intereses"), CAT_RENDIMIENTOS),
    (("intereses", "abonados"), CAT_RENDIMIENTOS), (("pago", "de", "intereses"), CAT_RENDIMIENTOS),
    (("intereses", "cajita"), CAT_RENDIMIENTOS), (("intereses", "cajitas"), CAT_RENDIMIENTOS),
    (("intereses", "bolsillo"), CAT_RENDIMIENTOS), (("intereses", "bolsillos"), CAT_RENDIMIENTOS),
    (("intereses", "de", "ahorro"), CAT_RENDIMIENTOS), (("intereses", "de", "ahorros"), CAT_RENDIMIENTOS),
    (("interes", "cuenta", "de", "ahorros"), CAT_RENDIMIENTOS), (("interes", "cuenta", "de", "ahorro"), CAT_RENDIMIENTOS),
    (("intereses", "cuenta", "de", "ahorros"), CAT_RENDIMIENTOS), (("intereses", "cuenta", "ahorros"), CAT_RENDIMIENTOS),
    (("interes", "cuenta", "ahorros"), CAT_RENDIMIENTOS), (("interes", "cdt"), CAT_RENDIMIENTOS),
    (("intereses", "cdt"), CAT_RENDIMIENTOS),
    (("rendimientos",), CAT_RENDIMIENTOS), (("rendimiento",), CAT_RENDIMIENTOS),
]
_CONCEPTOS.sort(key=lambda c: -len(c[0]))

# Tras «comisión(es)» estas palabras indican un COMERCIO («Comisiones Express»), no un cobro bancario.
_NO_ES_COBRO_TRAS_COMISION = {"express", "ventas", "inmobiliaria", "corredores", "y", "ganadas", "ganada", "recibidas", "recibida"}
# «Cuota de administración» solo es un cobro financiero si habla de tarjeta/cuenta/crédito; si no, es la
# administración del conjunto (Hogar) y se deja al diccionario normal.
_CONTEXTO_BANCARIO = {"tarjeta", "cuenta", "credito", "tc", "tdc", "banco", "plan", "debito", "ahorros", "nomina"}
# «Seguro de vida» a secas es una póliza propia (categoría Seguros); como cobro del banco trae este contexto.
_CONTEXTO_SEGURO_BANCO = {"tarjeta", "credito", "deudor", "deudores", "cuota", "saldo", "cobro", "cargo", "tc", "tdc",
                          "prestamo", "libranza", "hipoteca"}

_PALABRAS_DEVOLUCION = {"devolucion", "reverso", "reversion", "reintegro"}


def _normalizar(texto: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _palabras(descripcion: str) -> list[str]:
    return _normalizar(descripcion).split()


def _posicion(palabras: list[str], frase: tuple[str, ...]) -> int | None:
    """Índice donde empieza `frase`, si solo hay conectores antes de ella."""
    n = len(frase)
    for i in range(0, min(_MAX_PREFIJO, len(palabras) - n) + 1):
        if tuple(palabras[i:i + n]) == frase and all(p in _PREFIJOS for p in palabras[:i]):
            return i
    return None


def clasificar_costo(descripcion: str) -> dict | None:
    """{categoria, tipo, confianza, fuente, palabra, razon} si la LÍNEA es un cobro/rendimiento bancario;
    None si no. `tipo` es el esperado ('income' para rendimientos y devoluciones de cobros, 'expense' lo
    demás): quien lee el extracto puede preferir el signo impreso."""
    palabras = _palabras(descripcion)
    if not palabras:
        return None
    for frase, categoria in _CONCEPTOS:
        i = _posicion(palabras, frase)
        if i is None:
            continue
        resto = palabras[i + len(frase):]
        if frase in (("comision",), ("comisiones",)) and resto and resto[0] in _NO_ES_COBRO_TRAS_COMISION:
            continue
        if frase == ("cobro",) and any(p in {"en", "tienda", "pedido"} for p in resto[:1]):
            continue
        devolucion = any(p in _PALABRAS_DEVOLUCION for p in palabras[:i])
        tipo = "income" if (categoria == CAT_RENDIMIENTOS or devolucion) else "expense"
        if categoria == CAT_RENDIMIENTOS and devolucion:
            continue
        texto = " ".join(frase)
        return {
            "categoria": categoria, "tipo": tipo, "confianza": 0.85, "fuente": "diccionario",
            "palabra": texto, "razon": f"por palabra clave «{texto}»",
        }
    # Casos con contexto
    for frase, categoria in ((("cuota", "de", "administracion"), CAT_COMISIONES), (("cuota", "administracion"), CAT_COMISIONES)):
        i = _posicion(palabras, frase)
        if i is not None and _CONTEXTO_BANCARIO & set(palabras):
            return {"categoria": categoria, "tipo": "expense", "confianza": 0.8, "fuente": "diccionario",
                    "palabra": " ".join(frase), "razon": f"por palabra clave «{' '.join(frase)}»"}
    for frase in (("seguro", "de", "vida"), ("seguro", "vida")):
        i = _posicion(palabras, frase)
        if i is not None and _CONTEXTO_SEGURO_BANCO & set(palabras):
            return {"categoria": CAT_COMISIONES, "tipo": "expense", "confianza": 0.8, "fuente": "diccionario",
                    "palabra": " ".join(frase), "razon": f"por palabra clave «{' '.join(frase)}»"}
    return None


def es_costo_o_rendimiento(descripcion: str) -> bool:
    """True si la línea es un cobro o rendimiento bancario (nunca un traslado entre cuentas)."""
    return clasificar_costo(descripcion) is not None


def bucket_de(categoria: str | None, descripcion: str = "") -> str | None:
    """Cubo de costo de un movimiento para el análisis: 'intereses' | 'cuota' | 'comisiones' | 'gmf' |
    'rendimientos' | None. Manda la categoría guardada (así respeta lo que el usuario corrigió); si es la
    categoría antigua «Comisiones y costos financieros», se mira la línea para repartirla."""
    c = _normalizar(categoria or "")
    por_nombre = {
        _normalizar(CAT_INTERESES): "intereses", _normalizar(CAT_CUOTA): "cuota",
        _normalizar(CAT_COMISIONES): "comisiones", _normalizar(CAT_GMF): "gmf",
        _normalizar(CAT_RENDIMIENTOS): "rendimientos",
    }
    if c in por_nombre:
        return por_nombre[c]
    if c == _normalizar("Comisiones y costos financieros"):
        r = clasificar_costo(descripcion)
        return por_nombre.get(_normalizar(r["categoria"]), "comisiones") if r else "comisiones"
    return None
