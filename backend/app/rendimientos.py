"""«Tu plata trabajando»: rendimiento ESTIMADO de cuentas y cajitas, y comparación informativa.

Todo lo de aquí es una ESTIMACIÓN con interés compuesto E.A. (efectivo anual): el banco calcula
y paga a su manera (días hábiles, topes, retención). La tasa y su fecha se devuelven siempre
para poder mostrarlas. Orientación educativa, no es asesoría financiera: no se recomienda
ningún banco ni producto.

Piezas puras (probables con números exactos): `ganancia`, `estimar`, `ahorro_extra_anual`,
`mediana`. `resumen(db, usuario_id, hoy)` lee la base (solo lectura) y arma la respuesta.

Cajitas: son una PARTE del saldo de la cuenta (ver models_rendimientos.py). El saldo principal
es `saldo de la cuenta - suma de cajitas`; así nada se cuenta dos veces en Patrimonio."""
import unicodedata
from datetime import date, datetime

DIAS_ANIO = 365.0
MESES_ANIO = 12
DIAS_TASA_VIEJA = 45  # una tasa de referencia sin actualizar más de esto se avisa a la administración
UMBRAL_DIFERENCIA_PP = 3.0  # puntos de E.A. de diferencia desde los que se muestra la comparación
MIN_SALDO_OCIOSO = 200_000  # menos que esto en el saldo principal no vale la pena mencionarlo
AVISO = "Orientación educativa, no es asesoría financiera."
AVISO_ESTIMACION = (
    "Es una estimación con la tasa que tú anotaste. Lo que el banco te pague de verdad puede variar "
    "(las tasas cambian y cada banco las calcula a su manera)."
)
TIPOS_TASA = ("ahorro_vista", "saldo_principal", "cdt")
TIPOS_CON_RENDIMIENTO = ("ahorro",)

# Semilla inicial (solo si la tabla está vacía): cifras de referencia investigadas, NO verdades.
# Después la administración las edita en el panel; el código nunca las usa directamente.
FECHA_SEMILLA = date(2026, 10, 12)
SIN_CIFRA = "Sin cifra verificada todavía. Verifica en la app de tu banco."
SEMILLA = [
    # entidad, producto, tipo, tasa_ea, nota
    ("Nu Colombia", "Saldo principal", "saldo_principal", 0.10, "Referencia, verifica en la app de tu banco."),
    ("Nu Colombia", "Cajitas", "ahorro_vista", 9.0,
     "Referencia (suele estar entre 9 % y 11 % E.A. según la fuente y el mes). Verifica en la app de tu banco."),
    ("Lulo", "Bolsillos", "ahorro_vista", None, SIN_CIFRA),
    ("Nequi", "Bolsillos", "ahorro_vista", None, SIN_CIFRA),
    ("Pibank", "Cuenta de ahorros", "ahorro_vista", None, SIN_CIFRA),
    ("CDT (bancos tradicionales)", "CDT a 90 o 120 días", "cdt", 11.0,
     "Referencia: desde $50.000, a 90 o 120 días. Verifica en la app de tu banco."),
]


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")


# ── cálculo puro ──────────────────────────────────────────────────────────────────────
def ganancia(saldo: float, tasa_ea: float | None, dias: float) -> float:
    """Interés compuesto E.A. durante `dias`: saldo * ((1+EA)^(dias/365) - 1). Tasa en % (9 = 9 % E.A.)."""
    if not saldo or saldo <= 0 or tasa_ea is None or tasa_ea <= -100 or dias <= 0:
        return 0.0
    return saldo * ((1 + tasa_ea / 100.0) ** (dias / DIAS_ANIO) - 1)


def tasa_diaria_pct(tasa_ea: float) -> float:
    """Tasa efectiva diaria equivalente, en %."""
    return ((1 + tasa_ea / 100.0) ** (1 / DIAS_ANIO) - 1) * 100.0


def estimar(saldo: float, tasa_ea: float | None, hoy: datetime) -> dict | None:
    """{dia, mes_corrido, mes, anio}: ganancia estimada por día, en lo que va del mes, en un mes tipo
    (365/12 días) y en 12 meses, manteniendo el saldo de hoy. None si no hay tasa."""
    if tasa_ea is None:
        return None
    return {
        "dia": ganancia(saldo, tasa_ea, 1),
        "mes_corrido": ganancia(saldo, tasa_ea, max(1, hoy.day)),
        "mes": ganancia(saldo, tasa_ea, DIAS_ANIO / MESES_ANIO),
        "anio": ganancia(saldo, tasa_ea, DIAS_ANIO),
    }


def ahorro_extra_anual(saldo: float, tasa_actual: float, tasa_ref: float) -> float:
    """Cuánto más ganaría en un año con `tasa_ref` que con `tasa_actual` (ambas E.A. en %)."""
    return max(0.0, saldo * (tasa_ref - tasa_actual) / 100.0)


def mediana(valores: list[float]) -> float | None:
    v = sorted(valores)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def dias_sin_actualizar(vigente_desde: date, hoy: date) -> int:
    return max(0, (hoy - vigente_desde).days)


# ── tasas de referencia ───────────────────────────────────────────────────────────────
def serializar_tasa(t, hoy: date) -> dict:
    dias = dias_sin_actualizar(t.vigente_desde, hoy) if t.vigente_desde else None
    return {
        "id": t.id, "entidad": t.entidad, "producto": t.producto, "tipo": t.tipo, "tasa_ea": t.tasa_ea,
        "vigente_desde": t.vigente_desde.isoformat() if t.vigente_desde else None,
        "fuente_url": t.fuente_url, "nota": t.nota, "activa": t.activa is not False,
        "dias_sin_actualizar": dias, "desactualizada": dias is not None and dias > DIAS_TASA_VIEJA,
    }


def tasas(db, solo_activas: bool = True) -> list:
    """Filas de tasas_referencia, en orden neutral (alfabético por entidad). Siembra la tabla si está vacía."""
    from app.models_rendimientos import TasaReferencia

    if db.query(TasaReferencia.id).first() is None:
        for entidad, producto, tipo, tasa, nota in SEMILLA:
            db.add(TasaReferencia(entidad=entidad, producto=producto, tipo=tipo, tasa_ea=tasa,
                                  vigente_desde=FECHA_SEMILLA, nota=nota))
        db.commit()
    q = db.query(TasaReferencia)
    if solo_activas:
        q = q.filter(TasaReferencia.activa == True)  # noqa: E712
    return sorted(q.all(), key=lambda t: (_sin_acentos(t.entidad).lower(), _sin_acentos(t.producto).lower()))


def tasas_desactualizadas(db, hoy: date) -> list[dict]:
    """Tasas activas CON cifra y sin actualizar hace más de 45 días (aviso en el panel de administración)."""
    return [serializar_tasa(t, hoy) for t in tasas(db) if t.tasa_ea is not None and t.vigente_desde
            and dias_sin_actualizar(t.vigente_desde, hoy) > DIAS_TASA_VIEJA]


# ── resumen del usuario ───────────────────────────────────────────────────────────────
def _rendimientos_recibidos(db, ids: list[str], monedas: dict, hoy: datetime, conv=None) -> float | None:
    """Plata de «Rendimientos» que realmente entró este mes (categoría que clasifican los extractos).
    None si la persona no tiene ningún movimiento en esa categoría."""
    from app.models import Movimiento

    if not ids:
        return None
    inicio = datetime(hoy.year, hoy.month, 1)
    movs = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids), Movimiento.fecha >= inicio,
                                       Movimiento.tipo == "income").all()
    hay = [m for m in movs if _sin_acentos(m.categoria or "").strip().lower().startswith("rendimiento")]
    if not hay:
        return None
    return sum(conv.contar(m.monto, monedas.get(m.cuenta_id, "COP")) for m in hay)


def resumen(db, usuario_id: str, hoy: datetime) -> dict:
    from app.contabilidad import ConvertidorBase
    from app.models import Cuenta
    from app.models_rendimientos import Cajita

    cuentas = (db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id, Cuenta.tipo.in_(TIPOS_CON_RENDIMIENTO))
               .order_by(Cuenta.nombre).all())
    ids = [c.id for c in cuentas]
    conv = ConvertidorBase.de_usuario(db, usuario_id)  # montos en moneda base (fase 2)
    cajitas = (db.query(Cajita).filter(Cajita.usuario_id == usuario_id, Cajita.activa == True).all()  # noqa: E712
               if ids else [])
    por_cuenta: dict[str, list] = {}
    for k in cajitas:
        por_cuenta.setdefault(k.cuenta_id, []).append(k)

    refs = tasas(db)
    vista = [t for t in refs if t.tipo == "ahorro_vista" and t.tasa_ea is not None]
    ref_mediana = mediana([t.tasa_ea for t in vista])
    ref_fecha = max((t.vigente_desde for t in vista), default=None)

    filas, ociosa = [], []
    tot_mes = tot_anio = 0.0
    hay_estimacion = False
    for c in cuentas:
        mon = c.moneda or "COP"

        def cop(v, m=mon):
            return conv.contar(float(v or 0), m)

        saldo = float(c.saldo or 0)
        ks = por_cuenta.get(c.id, [])
        suma_k = sum(float(k.saldo or 0) for k in ks)
        principal = max(0.0, saldo - suma_k)
        lineas = [{"tipo": "principal", "nombre": "Saldo principal", "saldo": principal, "tasa_ea": c.tasa_ea,
                   "tasa_fecha": None, "est": estimar(principal, c.tasa_ea, hoy)}]
        for k in ks:
            lineas.append({"tipo": "cajita", "id": k.id, "nombre": k.nombre, "saldo": float(k.saldo or 0),
                           "tasa_ea": k.tasa_ea, "tasa_fecha": k.tasa_fecha.isoformat() if k.tasa_fecha else None,
                           "est": estimar(float(k.saldo or 0), k.tasa_ea, hoy)})
        ests = [l["est"] for l in lineas if l["est"]]
        est = {k: sum(e[k] for e in ests) for k in ("dia", "mes_corrido", "mes", "anio")} if ests else None
        if est:
            hay_estimacion = True
            tot_mes += cop(est["mes_corrido"])
            tot_anio += cop(est["anio"])
        filas.append({
            "cuenta_id": c.id, "nombre": c.nombre, "moneda": mon, "saldo": saldo, "principal": principal,
            "cajitas": [l for l in lineas if l["tipo"] == "cajita"], "tasa_principal": c.tasa_ea,
            "descuadre": suma_k > saldo + 1, "estimado": est,
            "sin_tasa": c.tasa_ea is None and not any(k.tasa_ea is not None for k in ks),
        })
        # Comparación informativa: saldo principal que rinde mucho menos que las cajitas de referencia.
        if (ref_mediana is not None and c.tasa_ea is not None and cop(principal) >= MIN_SALDO_OCIOSO
                and ref_mediana - c.tasa_ea >= UMBRAL_DIFERENCIA_PP):
            ociosa.append({"cuenta_id": c.id, "nombre": c.nombre, "saldo": cop(principal), "tasa_actual": c.tasa_ea,
                           "tasa_ref": ref_mediana,
                           "extra_anual": ahorro_extra_anual(cop(principal), c.tasa_ea, ref_mediana)})

    monedas = {c.id: c.moneda or "COP" for c in cuentas}
    recibido = _rendimientos_recibidos(db, ids, monedas, hoy, conv)
    return {
        "aviso": AVISO, "aviso_estimacion": AVISO_ESTIMACION, "hay_cuentas": bool(cuentas),
        "hay_cajitas": bool(cajitas), "cuentas": filas,
        "total": {"mes_corrido": tot_mes, "anio": tot_anio, "hay_estimacion": hay_estimacion, "recibido_mes": recibido},
        "comparacion": {
            "ociosa": ociosa, "tasa_ref": ref_mediana,
            "ref_fecha": ref_fecha.isoformat() if ref_fecha else None,
            "opciones": [serializar_tasa(t, hoy.date()) for t in refs if t.tipo != "saldo_principal"],
            "nota": "Las condiciones cambian y cada banco tiene topes y requisitos: verifica en la app o la página de tu banco.",
            "aviso": AVISO,
        },
        "hoy": hoy.date().isoformat(),
        "moneda_base": conv.base, "monedas_sin_tasa": sorted(conv.sin_tasa),
    }
