"""Lectores de extractos en PDF de bancos colombianos, uno por FORMATO (no por banco).

Cada formato se reconoce por una firma propia de su encabezado, no por el nombre de un banco que aparece suelto en
los movimientos («TRANSFERENCIAS A NEQUI», «enviada a Daviplata»…): eso era lo que hacía confundir a Bancolombia o
Davivienda con Nequi. Cada lector devuelve los movimientos y, cuando el extracto imprime sus totales, comprueba que
lo leído los suma: si no cuadra, `lectura_completa` es False y la app avisa en vez de importar a ciegas.

Formatos: Davivienda «Informe del mes», Bancolombia «Estado de cuenta» y «Sucursal Virtual», Banco Caja Social,
BBVA cuenta corriente y Davibank (Davivienda, resumen con «Depósitos y otros créditos»).

Todo es texto ya extraído del PDF (pdf_extract.pdf_a_texto): nada de red ni de base de datos.
"""
from __future__ import annotations

import calendar
import re
from collections import Counter
from datetime import date

TOLERANCIA = 1.0  # pesos: las sumas de varios montos con decimales pueden diferir en centavos

_MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}
_MESES_LARGOS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _compacto(texto: str) -> str:
    """Minúsculas y sin espacios: algunos extractos (Davivienda) pegan todas las palabras."""
    return re.sub(r"\s+", "", (texto or "").lower())


def _us(s: str) -> float:
    """'1,234.56' o '.34' -> número."""
    return float(s.replace(",", "") or "0")


def _es(s: str) -> float:
    """'1.234,56' -> número."""
    return float(s.replace(".", "").replace(",", "."))


def _iso(anio: int, mes: int, dia: int) -> str | None:
    try:
        return date(anio, mes, dia).isoformat()
    except ValueError:
        return None


def _detalle_util(linea: str) -> str | None:
    """Línea de detalle que algunos bancos imprimen DEBAJO de un movimiento («Recarga Nequi PSE», «Pago factura hogar -
    Multiplay»). Sirve para categorizar. Solo si tiene al menos dos palabras de verdad y no parece un pie de página."""
    t = (linea or "").strip()
    t = re.sub(r"^\d{6,}\s+", "", t)  # referencia numérica delante
    if not t or len(t) > 60 or t.endswith("."):
        return None
    palabras = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]{4,}", t)
    if len(palabras) < 2 or re.search(r"\d{4}-\d{2}|www\.|@", t):
        return None
    return t


def _con_detalle(desc: str, detalle: str | None) -> str:
    return f"{desc.strip()} · {detalle}" if detalle else desc.strip()


def _mov(fecha: str, desc: str, monto: float, tipo: str, saldo: float | None = None) -> dict:
    return {"fecha": fecha, "descripcion": desc.strip(), "monto": abs(monto), "tipo": tipo, "referencia": "", "saldo": saldo}


def _cuadra(leidos: float | None, impreso: float | None) -> bool | None:
    if leidos is None or impreso is None:
        return None
    return abs(leidos - impreso) <= TOLERANCIA


def _lectura(formato: str, banco: str, movs: list[dict], **extra) -> dict:
    abonos = sum(m["monto"] for m in movs if m["tipo"] == "income")
    cargos = sum(m["monto"] for m in movs if m["tipo"] == "expense")
    verificaciones = [v for v in (_cuadra(abonos, extra.get("total_abonos")), _cuadra(cargos, extra.get("total_cargos"))) if v is not None]
    if extra.get("verificada") is not None:  # el lector comprobó la cadena de saldos del banco: vale más que los totales por categoría
        verificaciones = [extra["verificada"]]
    # Meses que faltan en un PDF con varios extractos: el saldo inicial de uno no es el final del anterior
    secciones = extra.get("secciones") or []
    huecos = sum(1 for (_, fin_a), (ini_b, _) in zip(secciones, secciones[1:]) if fin_a is not None and ini_b is not None and abs(fin_a - ini_b) > TOLERANCIA)
    return {
        "huecos": huecos,
        "formato": formato, "banco": banco, "movimientos": movs,
        "saldo_inicial": extra.get("saldo_inicial"), "saldo_final": extra.get("saldo_final"),
        "periodo_inicio": extra.get("periodo_inicio"), "periodo_fin": extra.get("periodo_fin"),
        "total_abonos": extra.get("total_abonos"), "total_cargos": extra.get("total_cargos"),
        "leidos_abonos": abonos, "leidos_cargos": cargos,
        # True = suma lo que dice el extracto; False = no suma (falta o sobra algo); None = el extracto no trae totales
        "lectura_completa": (all(verificaciones) if verificaciones else None),
    }


def _firmar_por_saldo(filas: list[tuple], saldo_previo: float | None) -> tuple[list[tuple], int]:
    """filas: (fecha, descripcion, monto, saldo). Decide entrada o salida con la aritmética del propio banco:
    saldo anterior + monto = saldo -> entrada; saldo anterior - monto = saldo -> salida. Devuelve (fila + tipo, sin_resolver)."""
    salida, sin_resolver, previo = [], 0, saldo_previo
    for fecha, desc, monto, saldo in filas:
        tipo = None
        if previo is not None:
            suma, resta = abs(previo + monto - saldo) <= 0.5, abs(previo - monto - saldo) <= 0.5
            if suma and not resta:
                tipo = "income"
            elif resta and not suma:
                tipo = "expense"
        if tipo is None:
            sin_resolver += 1
        salida.append((fecha, desc, monto, saldo, tipo))
        previo = saldo
    return salida, sin_resolver


# ═══ Davivienda «Informe del mes» ═══════════════════════════════════════════════════════════════════════════
# «01 03 $18,200.00- 8151 CompraBOLD*Avenacubana FRANQUICIAMASTERCARD»: día mes, valor con el signo AL FINAL
# (+ entra, - sale), documento, descripción y oficina, con las palabras pegadas. El año va en «INFORME DEL MES: MARZO/2026».

_RE_DAV_FILA = re.compile(r"^(\d{2})\s(\d{2})\s+\$([\d,]+\.\d{2})([+-])\s+(\d+)\s+(\S.*)$")
_DAV_FRASES = (
    (r"^Transferenciaenviadaa", "Transferencia enviada a "),
    (r"^TransferenciaALlave", "Transferencia a llave "),
    (r"^AbonoPorTransferenciaDeFondos", "Abono por transferencia de fondos "),
    (r"^DescuentoPorTransferenciaDeFondos", "Descuento por transferencia de fondos "),
    (r"^RetiroenCajeroAutomatico\.?", "Retiro en cajero automático "),
    (r"(?i)^transferenciade\s*dineroa\s*bolsillo", "Transferencia de dinero a bolsillo"),
    (r"(?i)^transferenciadesde\s*cuentaa\s*bolsillo", "Transferencia desde cuenta a bolsillo"),
    (r"(?i)^abono\s*de\s*bolsillo\s*acuenta", "Abono de bolsillo a cuenta"),
    (r"(?i)^transferencia\s*de\s*bolsillo\s*acuenta", "Transferencia de bolsillo a cuenta"),
    (r"(?i)^deposito\s*efectivocon\s*volante\s*oficina", "Depósito efectivo con volante oficina"),
    (r"^Compra(?=\S)", "Compra "),
    (r"^Pago(?=[A-Z])", "Pago "),
)


def _despegar_davivienda(desc: str) -> str:
    """Davivienda pega las palabras: se separan las frases típicas y las mayúsculas pegadas a minúsculas."""
    for patron, reemplazo in _DAV_FRASES:
        nuevo = re.sub(patron, reemplazo, desc)
        if nuevo != desc:
            desc = nuevo
            break
    desc = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", desc)
    return re.sub(r"\s+", " ", desc).strip()


def _firma_davivienda_informe(t: str) -> bool:
    c = _compacto(t[:6000])
    return "informedelmes:" in c and "clasedemovimiento" in c


def _leer_davivienda_informe(texto: str) -> dict | None:
    c = _compacto(texto)
    cab = re.search(r"informedelmes:([a-záéíóúñ]+)/(\d{4})", c)
    if not cab or cab.group(1) not in _MESES_LARGOS:
        return None
    mes_inf, anio_inf = _MESES_LARGOS[cab.group(1)], int(cab.group(2))
    movs: list[dict] = []
    for linea in texto.splitlines():
        m = _RE_DAV_FILA.match(linea.strip())
        if not m:
            continue
        dia, mes = int(m.group(1)), int(m.group(2))
        anio = anio_inf - 1 if mes > mes_inf + 6 else anio_inf  # un movimiento de diciembre en el informe de enero
        fecha = _iso(anio, mes, dia)
        if not fecha:
            continue
        resto = m.group(6).strip()
        partes = resto.rsplit(None, 1)
        desc = partes[0] if len(partes) == 2 else resto  # la última palabra es la oficina
        movs.append(_mov(fecha, _despegar_davivienda(desc), _us(m.group(3)), "income" if m.group(4) == "+" else "expense"))

    def valor(clave: str) -> float | None:
        r = re.search(clave + r"\$?([\d,]+\.\d{2})", c)
        return _us(r.group(1)) if r else None

    return _lectura(
        "davivienda_informe", "davivienda", movs,
        saldo_inicial=valor("saldoanterior"), saldo_final=valor("nuevosaldo"),
        total_abonos=valor("máscréditos"), total_cargos=valor("menosdébitos"),
        periodo_inicio=_iso(anio_inf, mes_inf, 1), periodo_fin=_iso(anio_inf, mes_inf, calendar.monthrange(anio_inf, mes_inf)[1]),
    )


# ═══ Bancolombia «Estado de cuenta» ═════════════════════════════════════════════════════════════════════════
# «5/01 PAGO DE PROV BARVAL S A 1,087,488.00 5,576,668.53»: día/mes, descripción, valor (negativo = sale) y saldo.
# El periodo va en «DESDE: 2025/12/31 HASTA: 2026/03/31»; un mismo extracto puede cruzar de un año al siguiente.

_RE_BC_PERIODO = re.compile(r"desde:\s*(\d{4})/(\d{2})/(\d{2})\s+hasta:\s*(\d{4})/(\d{2})/(\d{2})", re.IGNORECASE)
_RE_BC_FILA = re.compile(r"^(\d{1,2})/(\d{2})\s+(.+?)\s+(-?[\d,]*\.\d{2})\s+(-?[\d,]*\.\d{2})$")


def _firma_bancolombia_estado(t: str) -> bool:
    c = _compacto(t[:3000])
    return bool(re.search(r"estadodecuentadesde:\d{4}/\d{2}/\d{2}hasta:\d{4}/\d{2}/\d{2}", c)) and "valorsaldo" in _compacto(t)


def _leer_bancolombia_estado(texto: str) -> dict | None:
    periodos = [tuple(int(x) for x in p.groups()) for p in _RE_BC_PERIODO.finditer(texto)]
    if not periodos:
        return None
    actual = periodos[0]
    filas = []
    for linea in texto.splitlines():
        p = _RE_BC_PERIODO.search(linea)
        if p:  # cada hoja repite el periodo de su extracto: las fechas se leen con el que tienen encima
            actual = tuple(int(x) for x in p.groups())
            continue
        m = _RE_BC_FILA.match(linea.strip())
        if not m:
            continue
        a0, m0, _d0, a1, _m1, _d1 = actual
        dia, mes = int(m.group(1)), int(m.group(2))
        # El año sale del periodo: los meses desde el mes de inicio van en el año de inicio; los anteriores, en el de fin.
        anio = a0 if (a0 == a1 or mes >= m0) else a1
        fecha = _iso(anio, mes, dia)
        if fecha:
            filas.append((fecha, m.group(3), _us(m.group(4)), _us(m.group(5))))
    movs = [_mov(fecha, desc, valor, "expense" if valor < 0 else "income", saldo) for fecha, desc, valor, saldo in filas]

    c = re.sub(r"\s+", " ", texto)

    def todos(etiqueta: str) -> list[float]:
        return [_us(x) for x in re.findall(etiqueta + r"\s*\$?\s*([\d,]*\.\d{2})", c, re.IGNORECASE)]

    anteriores, actuales = todos("saldo anterior"), todos("saldo actual")
    abonos, cargos = todos("total abonos"), todos("total cargos")
    return _lectura(
        "bancolombia_estado", "bancolombia", movs,
        saldo_inicial=anteriores[0] if anteriores else None, saldo_final=actuales[-1] if actuales else None,
        total_abonos=sum(abonos) if abonos else None, total_cargos=sum(cargos) if cargos else None,
        periodo_inicio=_iso(periodos[0][0], periodos[0][1], periodos[0][2]), periodo_fin=_iso(periodos[-1][3], periodos[-1][4], periodos[-1][5]),
    )


# ═══ Bancolombia «Sucursal Virtual» (movimientos copiados o impresos de la web) ═════════════════════════════
# «16 ago 2026 TRANSFERENCIAS A NEQUI -$ 15.000,00»: fecha con el mes en letras, valor con signo y números en español.
# Líneas sueltas debajo (referencias, «Dirección IP») no son movimientos. No trae saldos: no se puede comprobar la suma.

_RE_SV_FILA = re.compile(r"^(\d{1,2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)\.?\s+(\d{4})\s+(.+?)\s+(-?)\$\s*([\d.]+,\d{2})$", re.IGNORECASE)


def _firma_bancolombia_sucursal(t: str) -> bool:
    c = _compacto(t[:1200])
    return "sucursalvirtualpersonas" in c and "movimientos:" in c


def _leer_bancolombia_sucursal(texto: str) -> dict | None:
    movs: list[dict] = []
    for linea in texto.splitlines():
        m = _RE_SV_FILA.match(linea.strip())
        if not m:
            continue
        fecha = _iso(int(m.group(3)), _MESES[m.group(2).lower()], int(m.group(1)))
        if fecha:
            movs.append(_mov(fecha, m.group(4), _es(m.group(6)), "expense" if m.group(5) else "income"))
    if not movs:
        return None
    return _lectura("bancolombia_sucursal", "bancolombia", movs)


# ═══ Banco Caja Social «Extracto individual» ════════════════════════════════════════════════════════════════
# «MAR 06 DEBITO POR RECAUDO INTERNET 46,280.00 232,671.36»: mes en letras y día, UN valor y el saldo. Cada hoja de mes
# trae su resumen (saldo anterior · más créditos · menos débitos · intereses · nuevo saldo) y un PDF puede traer varios meses.

_RE_CS_FILA = re.compile(r"^(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$")
_RE_CS_PERIODO = re.compile(r"(\d{1,2})\s+de\s+([A-Za-záéíóú]+)\s+a\s+(\d{1,2})\s+de\s+([A-Za-záéíóú]+)\s+de\s+(\d{4})")
_RE_CS_RESUMEN = re.compile(r"^(-?[\d,]*\.\d{2})\s+(-?[\d,]*\.\d{2})\s+(-?[\d,]*\.\d{2})\s+(-?[\d,]*\.\d{2})\s+(-?[\d,]*\.\d{2})$")


def _limpiar_documento_cs(desc: str) -> str:
    """«COMPRA INTERNET 6332430 INTERNET» -> «COMPRA INTERNET»; conserva el detalle que va tras « · »."""
    base, sep, detalle = desc.partition(" · ")
    base = re.sub(r"\s+\d{5,}(?:\s+[A-ZÁÉÍÓÚÑ]+){0,2}$", "", base)
    return base + (sep + detalle if sep else "")


def _firma_cajasocial(t: str) -> bool:
    c = _compacto(t[:4000])
    return "periododelinforme" in c and "bancocajasocial" in _compacto(t)


def _leer_cajasocial(texto: str) -> dict | None:
    lineas = [l.strip() for l in texto.splitlines()]
    secciones: list[dict] = []
    for i, l in enumerate(lineas):
        per = _RE_CS_PERIODO.search(l)
        if per and (i == 0 or "periodo" in " ".join(lineas[max(0, i - 2):i + 1]).lower()):
            secciones.append({"i": i, "anio": int(per.group(5)), "mes_ini": _MESES_LARGOS.get(per.group(2).lower()), "mes_fin": _MESES_LARGOS.get(per.group(4).lower()),
                              "dia_ini": int(per.group(1)), "dia_fin": int(per.group(3)), "resumen": None})
    if not secciones:
        return None
    for s in secciones:  # la línea con los 5 valores del resumen queda justo después del encabezado del periodo
        for l in lineas[s["i"]:s["i"] + 8]:
            r = _RE_CS_RESUMEN.match(l)
            if r:
                s["resumen"] = [_us(x) for x in r.groups()]
                break
    movs: list[dict] = []
    sin_resolver = 0
    for k, s in enumerate(secciones):
        fin = secciones[k + 1]["i"] if k + 1 < len(secciones) else len(lineas)
        filas = []
        bloque = lineas[s["i"]:fin]
        for j, l in enumerate(bloque):
            m = _RE_CS_FILA.match(l)
            if not m:
                continue
            mes = _MESES[m.group(1).lower()]
            anio = s["anio"] - 1 if s["mes_ini"] and mes > s["mes_ini"] + 6 else s["anio"]
            fecha = _iso(anio, mes, int(m.group(2)))
            if fecha:
                sig = bloque[j + 1] if j + 1 < len(bloque) else ""
                detalle = None if _RE_CS_FILA.match(sig) else _detalle_util(sig) if re.match(r"^\d{6,}\s+\S", sig) else None
                filas.append((fecha, _con_detalle(m.group(3), detalle), _us(m.group(4)), _us(m.group(5))))
        previo = s["resumen"][0] if s["resumen"] else None
        # (fecha, descripción limpia, monto, saldo): el documento y el «lugar» (INTERNET, ACH…) no dicen en qué se gastó
        filas = [(f, _limpiar_documento_cs(d), mo, sa) for f, d, mo, sa in filas]
        firmadas, nr = _firmar_por_saldo(filas, previo)
        sin_resolver += nr
        for fecha, desc, monto, saldo, tipo in firmadas:
            if tipo:
                movs.append(_mov(fecha, desc, monto, tipo, saldo))
    if not movs:
        return None
    res = [s["resumen"] for s in secciones if s["resumen"]]
    out = _lectura(
        "cajasocial", "cajasocial", movs,
        saldo_inicial=res[0][0] if res else None, saldo_final=res[-1][4] if res else None,
        total_abonos=sum(r[1] for r in res) if res else None, total_cargos=sum(abs(r[2]) for r in res) if res else None,
        periodo_inicio=_iso(secciones[0]["anio"], secciones[0]["mes_ini"], secciones[0]["dia_ini"]) if secciones[0]["mes_ini"] else None,
        periodo_fin=_iso(secciones[-1]["anio"], secciones[-1]["mes_fin"], secciones[-1]["dia_fin"]) if secciones[-1]["mes_fin"] else None,
    )
    if sin_resolver:
        out["lectura_completa"] = False
    return out


# ═══ BBVA cuenta corriente ══════════════════════════════════════════════════════════════════════════════════
# «13686 01-11-2025 04-11-2025 CARGO POR IMPUESTO 4X1.000 229.00 21,380,835.51»: número, fecha de operación, fecha valor,
# descripción, UN valor y el saldo. Cada mes trae «SALDO CIERRE MES ANTERIOR … + ABONOS n total … - CARGOS n total … SALDO FINAL».

_RE_BBVA_FILA = re.compile(r"^(\d{3,7})\s+(\d{2})-(\d{2})-(\d{4})\s+\d{2}-\d{2}-\d{4}\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$")


def _firma_bbva(t: str) -> bool:
    c = _compacto(t[:6000])
    return "saldocierremesanterior" in c and "períododesde" in c.replace("periodo", "período")


def _leer_bbva(texto: str) -> dict | None:
    bloques = re.split(r"(?=SALDO CIERRE MES ANTERIOR)", texto)[1:]  # un bloque por mes del PDF
    if not bloques:
        return None
    movs: list[dict] = []
    secciones: list[tuple[float | None, float | None]] = []
    cadena_completa = True
    for b in bloques:
        cab = re.sub(r"\s+", " ", b[:900])
        previo_m = re.search(r"SALDO CIERRE MES ANTERIOR\s+([\d,]+\.\d{2})", cab)
        final_m = re.search(r"SALDO FINAL\s+([\d,]+\.\d{2})", cab)
        previo = _us(previo_m.group(1)) if previo_m else None
        final = _us(final_m.group(1)) if final_m else None
        filas = []
        for l in b.splitlines():
            m = _RE_BBVA_FILA.match(l.strip())
            if m:
                fecha = _iso(int(m.group(4)), int(m.group(3)), int(m.group(2)))
                if fecha:
                    filas.append((fecha, m.group(5), _us(m.group(6)), _us(m.group(7))))
        firmadas, sin_resolver = _firmar_por_saldo(filas, previo)
        movs.extend(_mov(fe, d, mo, t, sa) for fe, d, mo, sa, t in firmadas if t)
        # El mes está completo si lo leído termina exactamente en el SALDO FINAL que imprime el banco
        if sin_resolver or (final is not None and firmadas and abs(firmadas[-1][3] - final) > 0.5):
            cadena_completa = False
        secciones.append((previo, final))
    if not movs:
        return None
    return _lectura(
        "bbva_cuenta", "bbva", movs,
        saldo_inicial=secciones[0][0], saldo_final=secciones[-1][1],
        periodo_inicio=min(m["fecha"] for m in movs), periodo_fin=max(m["fecha"] for m in movs),
        verificada=cadena_completa, secciones=secciones,
    )


# ═══ Davibank (Davivienda) ═════════════════════════════════════════════════════════════════════════════════
# «1/12/2025 CENTRAL DE C Pago por PSE -20.000,00 35.276,68»: fecha, oficina, descripción, monto con signo y saldo,
# con números en español. El resumen trae saldo anterior, depósitos y créditos, retiros y débitos, nuevo saldo.

_RE_DB_SIN_FECHA = re.compile(r"^(?!\d)([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9/ .\-]{5,50}?)\s+(-?[\d.]+,\d{2})\s+([\d.]+,\d{2})$")
_RE_DB_FILA = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+(.+?)\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})$")


def _firma_davibank(t: str) -> bool:
    c = _compacto(t[:4000])
    return "fechaoficinanodocumdescripcionmontosaldo" in c or ("depositosyotroscreditos" in c and "retirosyotrosdebitos" in c)


def _quitar_oficina(descs: list[str]) -> list[str]:
    """La columna «oficina» ocupa 12 letras fijas ('CENTRAL DE C', 'BOGOTA CENTR', 'BOGOTA LOS H') y queda pegada a la
    descripción. Un prefijo de 12 letras que se repite en varias filas y termina en espacio es la oficina: se quita."""
    cuenta = Counter(d[:12] for d in descs if len(d) > 13 and d[12] == " " and re.fullmatch(r"[A-ZÁÉÍÓÚÑ ]{12}", d[:12]))
    oficinas = {o for o, n in cuenta.items() if n >= 3}
    return [d[13:].strip() if d[:12] in oficinas and len(d) > 13 and d[12] == " " else d for d in descs]


def _quitar_prefijo_comun(descs: list[str]) -> list[str]:
    """La columna «oficina» ('CENTRAL DE C') se pega a la descripción: si casi todas empiezan igual, se quita."""
    if len(descs) < 5:
        return descs
    cuenta = Counter(" ".join(d.split()[:3]) for d in descs if len(d.split()) > 3)
    if not cuenta:
        return descs
    pref, n = cuenta.most_common(1)[0]
    if n < 0.6 * len(descs):
        return descs
    return [d[len(pref):].strip() if d.startswith(pref) else d for d in descs]


def _leer_davibank(texto: str) -> dict | None:
    lineas = [l.strip() for l in texto.splitlines()]
    resumenes = []  # un resumen por cada mes del PDF
    for i, l in enumerate(lineas):
        if re.search(r"SALDO ANTERIOR.*NUEVO SALDO", l, re.IGNORECASE) and i + 1 < len(lineas):
            nums = re.findall(r"-?[\d.]+,\d{2}", lineas[i + 1])
            if len(nums) >= 4:
                resumenes.append([_es(x) for x in nums[:4]])
    filas = []
    for k, l in enumerate(lineas):
        m = _RE_DB_FILA.match(l)
        if m:
            fecha = _iso(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if fecha:
                sig = lineas[k + 1] if k + 1 < len(lineas) else ""
                detalle = None if (_RE_DB_FILA.match(sig) or _RE_DB_SIN_FECHA.match(sig)) else _detalle_util(sig)
                filas.append((fecha, _con_detalle(m.group(4), detalle), _es(m.group(5)), _es(m.group(6))))
            continue
        # Fila de cierre de mes sin fecha propia («IMP/TRANS FINANC/ACUM MES -49.136,80 560.202,86»): lleva la fecha de la
        # fila anterior y solo se acepta si la cadena de saldos del banco la confirma (saldo previo + monto = saldo).
        sd = _RE_DB_SIN_FECHA.match(l)
        if sd and filas:
            monto, saldo = _es(sd.group(2)), _es(sd.group(3))
            if abs(filas[-1][3] + monto - saldo) <= 0.5:
                filas.append((filas[-1][0], sd.group(1), monto, saldo))
    if not filas:
        return None
    descs = _quitar_oficina([f[1] for f in filas])
    descs = _quitar_prefijo_comun(descs)
    movs = [_mov(f[0], d, f[2], "expense" if f[2] < 0 else "income", f[3]) for f, d in zip(filas, descs)]
    return _lectura(
        "davibank", "davivienda", movs,
        saldo_inicial=resumenes[0][0] if resumenes else None, saldo_final=resumenes[-1][3] if resumenes else None,
        total_abonos=sum(r[1] for r in resumenes) if resumenes else None, total_cargos=sum(abs(r[2]) for r in resumenes) if resumenes else None,
        periodo_inicio=min(m["fecha"] for m in movs), periodo_fin=max(m["fecha"] for m in movs),
    )


# ═══ Entrada pública ════════════════════════════════════════════════════════════════════════════════════════
# El orden importa poco (las firmas no se pisan), pero va de la más específica a la más general.
_FORMATOS = (
    ("davivienda_informe", _firma_davivienda_informe, _leer_davivienda_informe),
    ("bancolombia_estado", _firma_bancolombia_estado, _leer_bancolombia_estado),
    ("bancolombia_sucursal", _firma_bancolombia_sucursal, _leer_bancolombia_sucursal),
    ("cajasocial", _firma_cajasocial, _leer_cajasocial),
    ("bbva_cuenta", _firma_bbva, _leer_bbva),
    ("davibank", _firma_davibank, _leer_davibank),
)

_BANCO_DE_FORMATO = {
    "davivienda_informe": "davivienda", "bancolombia_estado": "bancolombia", "bancolombia_sucursal": "bancolombia",
    "cajasocial": "cajasocial", "bbva_cuenta": "bbva", "davibank": "davivienda",
}


def detectar_formato(texto: str) -> str | None:
    """Nombre del formato si el texto trae la firma de uno de estos extractos; None si no."""
    if not texto:
        return None
    for nombre, firma, _ in _FORMATOS:
        try:
            if firma(texto):
                return nombre
        except (ValueError, KeyError):
            continue
    return None


def banco_de_formato(formato: str | None) -> str | None:
    return _BANCO_DE_FORMATO.get(formato or "")


def leer(texto: str) -> dict | None:
    """Lee el extracto si es de un formato conocido. None = no lo es (o no se pudo leer ningún movimiento)."""
    formato = detectar_formato(texto)
    if not formato:
        return None
    lector = next(l for n, _, l in _FORMATOS if n == formato)
    try:
        lectura = lector(texto)
    except (ValueError, KeyError, IndexError):
        return None
    return lectura if lectura and lectura["movimientos"] else None
