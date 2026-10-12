"""
Ayudas fiscales para Colombia. TODO es informativo y estimado: no es asesoría
tributaria ni garantiza que algo sea deducible. Funciones puras (sin BD ni red).

1. GMF / 4x1000: 0,4 % sobre los débitos de cuentas bancarias. Se ESTIMA a partir
   de los movimientos registrados; el valor real es el que cobra el banco.
2. Posibles deducibles: gastos que por su naturaleza (salud, educación, intereses
   de vivienda...) podrían servir en la declaración de renta, para que el usuario
   los organice con su soporte y los revise con un contador.
"""
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime

TARIFA_GMF = 0.004          # 4 x 1000
TOPE_EXENTO_UVT = 350       # débitos mensuales exentos de la ÚNICA cuenta marcada como exenta

# Valor de la UVT por año (DIAN). Verificar cada diciembre cuando se publica el del año siguiente.
UVT = {2024: 47065, 2025: 49799, 2026: 52374}

AVISO = (
    "Información de apoyo, no asesoría tributaria. Los valores son estimaciones a partir de los "
    "movimientos que registraste; CuadraMe no garantiza que un gasto sea deducible ni calcula tu "
    "impuesto. Confirma siempre con tu contador y con la normativa vigente de la DIAN."
)

# id -> (etiqueta, por qué podría aplicar). Sin topes numéricos a propósito: cambian cada año.
CATEGORIAS_FISCALES = {
    "salud": ("Salud", "Medicina prepagada, seguros de salud o planes complementarios podrían tener tratamiento especial."),
    "educacion": ("Educación", "Intereses de créditos educativos (p. ej. ICETEX) podrían ser deducibles; la matrícula en general no."),
    "vivienda_intereses": ("Intereses de vivienda", "Los intereses (no el capital) de un crédito de vivienda podrían ser deducibles. Pide el certificado de intereses al banco."),
    "ahorro_voluntario": ("AFC / pensión voluntaria", "Aportes voluntarios a pensión o cuentas AFC podrían ser rentas exentas dentro de un tope."),
    "donaciones": ("Donaciones", "Donaciones a entidades calificadas podrían dar descuento; exigen certificado de la entidad."),
    "gmf": ("4x1000 pagado", "Una parte del GMF efectivamente pagado podría ser deducible según la norma vigente."),
    "otro": ("Otro", "Marcado por ti para revisarlo con tu contador."),
}

# (categoria_fiscal, regex sobre descripción, confianza)
_REGLAS_DESCRIPCION = [
    ("vivienda_intereses", r"inter[eé]s(es)?.{0,30}(vivienda|hipotec|leasing hab)|(hipotec|vivienda|leasing hab).{0,30}inter[eé]s", "alta"),
    ("vivienda_intereses", r"\bhipotec|cr[eé]dito (de )?vivienda|leasing habitacional|fondo nacional del ahorro|\bfna\b", "media"),
    ("salud", r"medicina prepagada|prepagada|colsanitas|medplus|coomeva (medicina|salud)|plan complementario|p[oó]liza (de )?salud|seguro (de )?salud|sura (eps|salud)", "alta"),
    ("educacion", r"icetex|inter[eé]s(es)?.{0,25}(educativ|estudi)", "alta"),
    ("educacion", r"matr[ií]cula|universidad|colegio|semestre|pensi[oó]n escolar|jard[ií]n infantil", "media"),
    ("ahorro_voluntario", r"\bafc\b|pensi[oó]n voluntaria|aporte voluntario|fondo de pensi[oó]n|cuenta afc", "alta"),
    ("donaciones", r"donaci[oó]n|fundaci[oó]n|telet[oó]n|cruz roja|\bong\b", "media"),
]
_CATEGORIA_APP = {  # categoría de CuadraMe -> categoría fiscal sugerida (solo si ninguna regla de texto aplicó)
    "salud": "salud",
    "educacion": "educacion",
    "educación": "educacion",
}

PATRON_GMF = re.compile(r"gravamen|\bgmf\b|4\s?x\s?1000|4\s?x\s?mil|cuatro por mil", re.IGNORECASE)


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")


def uvt_del_anio(anio: int) -> int:
    if anio in UVT:
        return UVT[anio]
    return UVT[max(UVT)] if anio > max(UVT) else UVT[min(UVT)]


# ------------------------------------------------------------------ GMF

def es_linea_gmf(descripcion: str) -> bool:
    return bool(PATRON_GMF.search(descripcion or ""))


def _es_debito_gravable(m: dict) -> bool:
    """Un débito de una cuenta bancaria: gasto, pago de tarjeta (sale de la cuenta) o
    la pata de salida de un traslado. No incluye la propia línea del GMF (no se grava sobre sí mismo)."""
    if es_linea_gmf(m.get("descripcion", "")):
        return False
    if m.get("tipo") == "expense":
        return True
    return m.get("fuente") == "transferencia_interna" and (m.get("notas") or "").endswith(":out")


def calcular_gmf(movs: list[dict], tipos_cuenta: dict[str, str], cuenta_exenta_id: str | None, anio: int) -> dict:
    """movs: [{fecha, monto (COP), tipo, fuente, notas, descripcion, cuenta_id}] SIN filtrar por tipo efectivo
    (un pago de tarjeta sí es un débito gravable aunque no sea un gasto).

    Devuelve por mes: base gravable, GMF estimado, GMF registrado (líneas 'gravamen' que el
    usuario/extracto ya tiene) y cuánto del tope exento se usó."""
    uvt = uvt_del_anio(anio)
    tope_exento = TOPE_EXENTO_UVT * uvt
    deb: dict[tuple[str, str], float] = defaultdict(float)   # (mes, cuenta) -> débitos
    registrado: dict[str, float] = defaultdict(float)
    for m in movs:
        f: datetime = m["fecha"]
        if f.year != anio:
            continue
        mes = f.strftime("%Y-%m")
        if tipos_cuenta.get(m["cuenta_id"]) != "ahorro":
            continue
        if m.get("tipo") == "expense" and es_linea_gmf(m.get("descripcion", "")):
            registrado[mes] += m["monto"]
            continue
        if _es_debito_gravable(m):
            deb[(mes, m["cuenta_id"])] += m["monto"]

    meses = sorted({k[0] for k in deb} | set(registrado))
    filas = []
    for mes in meses:
        base = 0.0
        exento_usado = 0.0
        total_debitos = 0.0
        for (mes_k, cuenta), valor in deb.items():
            if mes_k != mes:
                continue
            total_debitos += valor
            if cuenta == cuenta_exenta_id:
                exento_usado = min(valor, tope_exento)
                base += max(0.0, valor - tope_exento)
            else:
                base += valor
        filas.append({
            "mes": mes,
            "debitos": round(total_debitos),
            "base_gravable": round(base),
            "exento_usado": round(exento_usado),
            "gmf_estimado": round(base * TARIFA_GMF),
            "gmf_registrado": round(registrado.get(mes, 0.0)),
        })
    total_est = sum(f["gmf_estimado"] for f in filas)
    total_reg = sum(f["gmf_registrado"] for f in filas)
    return {
        "anio": anio,
        "uvt": uvt,
        "tope_exento_mensual": tope_exento,
        "tarifa": TARIFA_GMF,
        "meses": filas,
        "total_estimado": total_est,
        "total_registrado": total_reg,
        "promedio_mensual": round(total_est / len(filas)) if filas else 0,
        "nota": "Estimado sobre los débitos registrados en cuentas de ahorro. El traslado entre cuentas "
                "del mismo banco y titular normalmente está exento; el valor real lo cobra tu banco.",
    }


# ------------------------------------------------------------ posibles deducibles

def sugerir_categoria_fiscal(m: dict) -> tuple[str, str] | None:
    """(categoria_fiscal, confianza) o None. Solo para gastos reales (el que llama filtra por tipo efectivo)."""
    desc = _sin_acentos(m.get("descripcion", "")).lower()
    if es_linea_gmf(m.get("descripcion", "")):
        return ("gmf", "alta")
    for cat, patron, conf in _REGLAS_DESCRIPCION:
        if re.search(_sin_acentos(patron), desc):
            return (cat, conf)
    cat_app = _sin_acentos(m.get("categoria", "")).lower().strip()
    if cat_app in _CATEGORIA_APP:
        return (_CATEGORIA_APP[cat_app], "baja")
    return None


def organizar_deducibles(gastos: list[dict], marcas: dict[str, dict]) -> dict:
    """gastos: gastos REALES del año [{id, fecha, descripcion, categoria, monto (COP), ...}].
    marcas: {movimiento_id: {categoria_fiscal, soporte, estado}} (lo que el usuario confirmó/descartó).

    Cada gasto queda 'confirmado' (lo marcó el usuario), 'sugerido' (lo detectó el sistema, sin revisar)
    o se omite (descartado o sin relación fiscal). Los totales por categoría suman SOLO los
    confirmados, para que ningún número prometa más de lo que el usuario revisó."""
    items = []
    for g in gastos:
        marca = marcas.get(g["id"])
        if marca and marca["estado"] == "descartada":
            continue
        if marca:
            cat, conf, estado, origen = marca["categoria_fiscal"], "usuario", "confirmado", "manual"
        else:
            s = sugerir_categoria_fiscal(g)
            if not s:
                continue
            (cat, conf), estado, origen = s, "sugerido", "auto"
        items.append({
            "movimiento_id": g["id"], "fecha": g["fecha"], "descripcion": g["descripcion"],
            "monto": round(g["monto"]), "categoria_fiscal": cat, "confianza": conf,
            "estado": estado, "origen": origen, "soporte": (marca or {}).get("soporte", ""),
        })
    items.sort(key=lambda i: i["fecha"])

    por_cat: dict[str, dict] = {}
    for i in items:
        c = por_cat.setdefault(i["categoria_fiscal"], {
            "categoria_fiscal": i["categoria_fiscal"],
            "etiqueta": CATEGORIAS_FISCALES.get(i["categoria_fiscal"], ("Otro", ""))[0],
            "ayuda": CATEGORIAS_FISCALES.get(i["categoria_fiscal"], ("", ""))[1],
            "confirmado": 0, "sugerido": 0, "con_soporte": 0, "cantidad": 0,
        })
        c[i["estado"]] += i["monto"]
        c["cantidad"] += 1
        if i["estado"] == "confirmado" and i["soporte"]:
            c["con_soporte"] += 1
    return {
        "items": items,
        "por_categoria": sorted(por_cat.values(), key=lambda c: -(c["confirmado"] + c["sugerido"])),
        "total_confirmado": sum(c["confirmado"] for c in por_cat.values()),
        "total_sugerido": sum(c["sugerido"] for c in por_cat.values()),
    }


# ------------------------------------------------------------ 4x1000 del mes

CATEGORIA_GMF = "4x1000 (GMF)"  # la crea el frente de costos bancarios; aquí solo se LEE por nombre
ALERTA_GMF_PCT = 80.0
RECORDATORIO_GMF = [
    "Puedes pedir en tu banco que marquen UNA cuenta de ahorros como exenta del 4x1000: en esa no pagas hasta cierto monto al mes.",
    "Solo una cuenta por persona puede estar marcada como exenta, aunque tengas varios bancos o billeteras.",
    "Mover plata entre tus cuentas del mismo banco no cobra 4x1000.",
]


def es_movimiento_gmf(m: dict) -> bool:
    cat = _sin_acentos(m.get("categoria", "")).lower().replace(" ", "")
    return cat == _sin_acentos(CATEGORIA_GMF).lower().replace(" ", "") or es_linea_gmf(m.get("descripcion", ""))


def gmf_mes(movs: list[dict], tipos_cuenta: dict[str, str], cuenta_exenta_id: str | None, mes: str) -> dict:
    """4x1000 de un mes ('YYYY-MM'). movs: [{fecha, monto (COP), tipo, fuente, notas, descripcion, categoria, cuenta_id}].
    - gmf_pagado: lo que ya te cobraron (categoría «4x1000 (GMF)» o líneas que lo dicen).
    - debitos_total: lo que salió de tus cuentas de ahorro ese mes (sin contar el propio 4x1000).
    - Frente al tope exento (350 UVT del año): si marcaste cuál es tu cuenta exenta se mide esa cuenta;
      si no, se mide el total como referencia."""
    anio = int(mes[:4])
    uvt = uvt_del_anio(anio)
    tope = TOPE_EXENTO_UVT * uvt
    pagado = 0.0
    deb_total = 0.0
    deb_exenta = 0.0
    for m in movs:
        if m["fecha"].strftime("%Y-%m") != mes:
            continue
        if es_movimiento_gmf(m):
            if m.get("tipo") == "expense":
                pagado += m["monto"]
            continue
        if tipos_cuenta.get(m["cuenta_id"]) != "ahorro" or not _es_debito_gravable(m):
            continue
        deb_total += m["monto"]
        if cuenta_exenta_id and m["cuenta_id"] == cuenta_exenta_id:
            deb_exenta += m["monto"]
    medido = deb_exenta if cuenta_exenta_id else deb_total
    pct = math.floor(medido / tope * 1000) / 10 if tope else 0.0
    alerta = pct >= ALERTA_GMF_PCT
    return {
        "mes": mes, "uvt": uvt, "tope_exento_mensual": tope, "tope_uvt": TOPE_EXENTO_UVT,
        "gmf_pagado": round(pagado), "debitos_total": round(deb_total),
        "debitos_cuenta_exenta": round(deb_exenta) if cuenta_exenta_id else None,
        "tiene_cuenta_exenta": bool(cuenta_exenta_id), "cuenta_exenta_id": cuenta_exenta_id,
        "uso_pct": pct, "alerta": alerta,
        "mensaje": ("Te acercas al tope de tu cuenta exenta" if alerta else
                    "Vas bien frente al tope de tu cuenta exenta"),
        "recordatorio": RECORDATORIO_GMF,
        "nota": "Estimado con los movimientos que cargaste; el valor real lo cobra tu banco.",
    }
