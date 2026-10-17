"""
«¿Tengo que declarar renta?»: estimación informativa con los datos que la persona cargó en CuadraMe.

NO es asesoría tributaria ni la declaración. Solo compara, año gravable por año gravable, cinco
topes que la DIAN usa para obligar a declarar (personas naturales residentes) contra lo que la app
alcanza a ver.

Diseño: `calcular_renta` es PURA (recibe un dict con los datos ya reunidos); `reunir_datos` lee la BD
(solo lectura). Todas las constantes que cambian cada año viven aquí arriba, en un solo lugar:
  - UVT por año: se toma de app.impuestos.UVT (una sola fuente de verdad).
  - TOPES_UVT / TOPES_UVT_POR_ANIO: cada criterio en UVT.
  - PLAZOS_RENTA: ventana de presentación de cada año gravable.
Verificar con el contador cada año (ver docs/SALIDA_A_PRODUCCION.md).
"""
import math
from datetime import date, datetime, timedelta

from app.contabilidad import FUENTE_AJUSTE, delta_saldo, tipos_efectivos
from app.impuestos import uvt_del_anio

# Topes en UVT (año gravable 2025, declaración 2026). Si algún año cambian, agrega la entrada en
# TOPES_UVT_POR_ANIO; los años sin entrada propia usan TOPES_UVT.
TOPES_UVT = {
    "patrimonio_bruto": 4500,
    "ingresos_brutos": 1400,
    "consumos_tarjeta": 1400,
    "compras_consumos": 1400,
    "consignaciones": 1400,
}
TOPES_UVT_POR_ANIO: dict[int, dict[str, int]] = {}

# Año gravable -> (primer día, último día) para presentar. Personas naturales: el día exacto depende
# de los dos últimos dígitos del NIT/cédula; el último día es el límite general.
PLAZOS_RENTA = {2025: (date(2026, 8, 12), date(2026, 10, 26))}

UMBRAL_CERCA = 60.0      # % del tope desde el cual se dice «cerca»
UMBRAL_SUPERADO = 100.0
DIAS_TOLERANCIA_INICIO = 7  # empezar a registrar hasta el 7 de enero cuenta como año completo

ORDEN = ["patrimonio_bruto", "ingresos_brutos", "consumos_tarjeta", "compras_consumos", "consignaciones"]
NOMBRES = {
    "patrimonio_bruto": "Patrimonio bruto",
    "ingresos_brutos": "Ingresos",
    "consumos_tarjeta": "Compras con tarjeta de crédito",
    "compras_consumos": "Compras y consumos",
    "consignaciones": "Consignaciones y depósitos",
}
GLOSAS = {
    "patrimonio_bruto": "Todo lo que tenías el 31 de diciembre (cuentas, inversiones, casa, carro), sin restar lo que debías.",
    "ingresos_brutos": "Toda la plata que ganaste en el año antes de descuentos, sin contar pasar plata entre tus cuentas.",
    "consumos_tarjeta": "Lo que compraste con tarjeta de crédito durante el año.",
    "compras_consumos": "Todo lo que compraste y pagaste en el año, con cualquier medio.",
    "consignaciones": "Toda la plata que entró a tus cuentas, incluyendo lo que pasaste entre tus propias cuentas y los préstamos.",
}
AVISO_RENTA = (
    "Es una ayuda informativa con los datos que cargaste en CuadraMe. No es asesoría tributaria ni "
    "es tu declaración. La DIAN decide con toda tu información: confírmalo con ella o con un contador."
)
LIMITES = [
    "Solo ve las cuentas y movimientos que cargaste (no ve cuentas que no agregaste).",
    "No ve ingresos ni compras en efectivo que no registraste.",
    "El patrimonio incluye casa, carro e inversiones solo si los agregaste en Patrimonio.",
    "Los valores de inversiones y bienes son los de hoy, no los del 31 de diciembre.",
]
DIAN_URL = "https://www.dian.gov.co"


def topes_del_anio(anio: int) -> dict[str, int]:
    return {**TOPES_UVT, **TOPES_UVT_POR_ANIO.get(anio, {})}


def topes_en_pesos(anio: int) -> dict[str, int]:
    uvt = uvt_del_anio(anio)
    return {k: v * uvt for k, v in topes_del_anio(anio).items()}


def plazo_del_anio(anio: int, hoy: date) -> dict | None:
    """Ventana de presentación y cuenta atrás; None si no se conoce el calendario de ese año."""
    p = PLAZOS_RENTA.get(anio)
    if not p:
        return None
    desde, hasta = p
    dias = (hasta - hoy).days
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias_restantes": dias,
        "vencido": dias < 0, "abierto": desde <= hoy <= hasta,
        "texto": (f"Vence el {hasta.day} de {_MESES[hasta.month - 1]}"
                  if dias >= 0 else f"El plazo venció el {hasta.day} de {_MESES[hasta.month - 1]}"),
    }


_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def estado_de(pct: float) -> str:
    if pct >= UMBRAL_SUPERADO:
        return "superado"
    if pct >= UMBRAL_CERCA:
        return "cerca"
    return "lejos"


def _pct(valor: float, tope: float) -> float:
    """% del tope, truncado a 1 decimal (así 59,96 % no se ve como 60 % y sigue siendo «lejos»)."""
    return math.floor(valor * 1000 / tope) / 10 if tope else 0.0


def _fecha(m) -> datetime:
    return m["fecha"]


def calcular_renta(datos: dict, anio: int, hoy: date) -> dict:
    """datos: {cuentas: [{id, tipo, saldo (COP)}], movimientos: [{id, cuenta_id, fecha, tipo, fuente, notas,
    categoria, descripcion, monto (COP)}] (desde el 1-ene del año, incluye los posteriores),
    activos_cop, tiene_bienes (inmueble/vehículo en Patrimonio), inicio_datos (date|None)}."""
    uvt = uvt_del_anio(anio)
    topes = topes_en_pesos(anio)
    cuentas = datos.get("cuentas", [])
    # `tipos_cuenta` (de reunir_datos) lleva monedas, reglas y nombre del titular: mismas decisiones
    # de traslado que los demás informes. Sin él (pruebas) se usa solo el tipo de cada cuenta.
    tipos = datos.get("tipos_cuenta") or {c["id"]: c["tipo"] for c in cuentas}
    movs = datos.get("movimientos", [])
    fin_anio = datetime(anio + 1, 1, 1)
    ini_anio = datetime(anio, 1, 1)
    efectivos = tipos_efectivos(movs, tipos)
    del_anio = [m for m in movs if ini_anio <= m["fecha"] < fin_anio]

    # Cobertura: ¿tenemos el año completo?
    inicio = datos.get("inicio_datos")
    parcial = False
    if inicio is None:
        parcial = True
    elif inicio > date(anio, 1, 1) + timedelta(days=DIAS_TOLERANCIA_INICIO):
        parcial = True
    if anio >= hoy.year and hoy < date(anio, 12, 31):
        parcial = True  # el año todavía no termina

    ingresos = consign = compras = tarjeta = 0.0
    traslados_in = 0.0
    for m in del_anio:
        tipo_c = tipos.get(m["cuenta_id"])
        if tipo_c is None:
            continue
        te = efectivos.get(m["id"], "transfer")
        if te == "expense":
            compras += m["monto"]
            if tipo_c == "credito":
                tarjeta += m["monto"]
        if tipo_c == "credito" or m.get("fuente") == FUENTE_AJUSTE:
            continue
        if te == "income":
            ingresos += m["monto"]
            consign += m["monto"]
        elif te == "transfer" and _entra_plata(m):
            consign += m["monto"]
            traslados_in += m["monto"]

    # Patrimonio bruto al 31-dic: saldo de hoy menos lo movido desde entonces (solo cuentas que no son tarjeta).
    cierre_pasado = anio < hoy.year
    bruto_cuentas = 0.0
    for c in cuentas:
        if c["tipo"] == "credito":
            continue
        saldo = c["saldo"]
        if cierre_pasado:
            saldo -= sum(delta_saldo(m) for m in movs
                         if m["cuenta_id"] == c["id"] and m["fecha"] >= fin_anio)
        bruto_cuentas += max(0.0, saldo)
    activos = float(datos.get("activos_cop") or 0)
    patrimonio = bruto_cuentas + activos

    hay_movs = bool(del_anio)
    inicio_tardio = inicio is not None and inicio > date(anio, 12, 31)
    valores = {
        "patrimonio_bruto": patrimonio, "ingresos_brutos": ingresos, "consumos_tarjeta": tarjeta,
        "compras_consumos": compras, "consignaciones": consign,
    }
    criterios = []
    for k in ORDEN:
        pct = _pct(valores[k], topes[k])
        estado = estado_de(pct)
        nota = ""
        if k == "patrimonio_bruto":
            sin = (not cuentas and activos <= 0) or inicio_tardio
            if sin:
                estado, nota = "sin_datos", "Empezaste a registrar después de esa fecha o no hay cuentas cargadas."
            elif not datos.get("tiene_bienes"):
                nota = "No incluye casa ni carro: agrégalos en Patrimonio si los tienes."
        else:
            if not hay_movs:
                estado, nota = "sin_datos", "No hay movimientos cargados de ese año."
            elif parcial and estado == "lejos":
                estado, nota = "sin_datos", "Solo tienes una parte del año cargada: puede que falte para llegar al tope."
            elif parcial:
                nota = "Solo una parte del año está cargada; el total real puede ser mayor."
        if k == "consignaciones" and traslados_in:
            nota = (nota + " " if nota else "") + "Incluye plata que pasaste entre tus cuentas, como la cuenta la DIAN."
        criterios.append({
            "id": k, "nombre": NOMBRES[k], "glosa": GLOSAS[k], "valor": round(valores[k]),
            "tope": topes[k], "tope_uvt": topes_del_anio(anio)[k], "pct": pct, "estado": estado,
            "parcial": bool(parcial and k != "patrimonio_bruto"), "nota": nota,
        })
        if k == "consignaciones":
            criterios[-1]["de_los_cuales_traslados"] = round(traslados_in)

    superados = [c for c in criterios if c["estado"] == "superado"]
    cercas = [c for c in criterios if c["estado"] == "cerca"]
    sin = [c["nombre"] for c in criterios if c["estado"] == "sin_datos"]
    if superados:
        clave, titulo = "si", "Probablemente SÍ debes declarar"
        detalle = "Superas el tope de: " + ", ".join(c["nombre"].lower() for c in superados) + "."
    elif cercas:
        clave, titulo = "cerca", "Estás cerca"
        detalle = "Vas cerca del tope de: " + ", ".join(c["nombre"].lower() for c in cercas) + "."
    elif sin:
        clave = "no_se_sabe"
        titulo = "No podemos saberlo"
        detalle = "Faltan datos de: " + ", ".join(n.lower() for n in sin) + "."
    else:
        clave, titulo = "no", "Probablemente no"
        detalle = "Con lo que cargaste, ningún criterio se acerca a su tope."
    if clave in ("si", "cerca") and sin:
        detalle += " Además faltan datos de: " + ", ".join(n.lower() for n in sin) + "."
    if clave == "no_se_sabe":
        titulo = "No podemos saberlo (faltan datos de " + ", ".join(n.lower() for n in sin) + ")"

    return {
        "anio": anio, "uvt": uvt,
        "resultado": {"clave": clave, "titulo": titulo, "detalle": detalle, "faltan": sin},
        "criterios": criterios,
        "cobertura": {"desde": inicio.isoformat() if inicio else None, "parcial": parcial},
        "plazo": plazo_del_anio(anio, hoy),
        "aviso": AVISO_RENTA, "limites": LIMITES, "enlaces": {"dian": DIAN_URL},
        "orientacion": "Orientación educativa, no es asesoría tributaria.",
    }


def _entra_plata(m: dict) -> bool:
    """La pata de entrada de un traslado (creado en la app o detectado entre cuentas propias)."""
    if m["tipo"] == "income":
        return True
    return m["tipo"] == "transfer" and (m.get("notas") or "").endswith(":in")


def resumen_csv(r: dict) -> str:
    """Resumen simple con totales por criterio; sin movimientos individuales."""
    def f(x):
        return str(int(x))
    lineas = [f"CuadraMe - resumen para tu declaración de renta (año gravable {r['anio']})",
              r["aviso"].replace(";", ","), f"UVT usada;{r['uvt']}", f"Resultado;{r['resultado']['titulo']}", "",
              "Criterio;Tu total;Tope;Tope en UVT;% del tope;Estado;Nota"]
    for c in r["criterios"]:
        lineas.append(";".join([c["nombre"], f(c["valor"]), f(c["tope"]), str(c["tope_uvt"]), str(c["pct"]),
                                c["estado"], c["nota"].replace(";", ",")]))
    lineas.append("")
    lineas.append("Lo que CuadraMe no ve;" + " ".join(r["limites"]).replace(";", ","))
    return "\r\n".join(lineas) + "\r\n"


# ------------------------------------------------------------------ lectura de la BD

def reunir_datos(db, usuario_id: str, anio: int, hoy: datetime) -> dict:
    from app import punto_partida
    # IMPUESTOS (DIAN / renta) van SIEMPRE en COP, a propósito: la declaración colombiana se hace en pesos y
    # no depende de la moneda base del perfil (moneda base fase 2, ver docs/MONEDA_BASE.md).
    from app.fx import convertir_a_cop
    from app.models import Cuenta, Movimiento
    from app.models_patrimonio import ActivoPatrimonio
    from app.routers.patrimonio import calcular_resumen

    cuentas_db = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()  # solo cuentas PROPIAS
    monedas = {c.id: c.moneda or "COP" for c in cuentas_db}

    def cop(v, cid):
        return convertir_a_cop(float(v or 0), monedas.get(cid, "COP"))

    ids = list(monedas)
    movs = []
    if ids:
        for m in db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids),
                                             Movimiento.fecha >= datetime(anio, 1, 1) - timedelta(days=3)).all():
            movs.append({"id": m.id, "cuenta_id": m.cuenta_id, "fecha": m.fecha, "tipo": m.tipo,
                         "fuente": m.fuente, "notas": m.notas or "", "categoria": m.categoria or "",
                         "descripcion": m.descripcion or "", "monto": cop(m.monto, m.cuenta_id)})
    inicio = punto_partida.fecha_inicio(db, usuario_id)
    inicio_d = inicio.date() if inicio else None
    if inicio_d is None and ids:
        from sqlalchemy import func
        primero = db.query(func.min(Movimiento.fecha)).filter(Movimiento.cuenta_id.in_(ids)).scalar()
        inicio_d = primero.date() if primero else None
    bienes = db.query(ActivoPatrimonio).filter(
        ActivoPatrimonio.usuario_id == usuario_id, ActivoPatrimonio.activo.is_(True),
        ActivoPatrimonio.clase.in_(["inmueble", "vehiculo"])).count()
    from app.contabilidad import tipos_de_cuentas

    return {
        "tipos_cuenta": tipos_de_cuentas(cuentas_db, db),
        "cuentas": [{"id": c.id, "tipo": c.tipo, "saldo": cop(c.saldo, c.id)} for c in cuentas_db],
        "movimientos": movs,
        "activos_cop": calcular_resumen(db, usuario_id, hoy, base="COP")["total_activos"],
        "tiene_bienes": bienes > 0,
        "inicio_datos": inicio_d,
    }


def renta_de_usuario(db, usuario_id: str, anio: int, hoy: datetime) -> dict:
    return calcular_renta(reunir_datos(db, usuario_id, anio, hoy), anio, hoy.date())


def anio_gravable_vigente(hoy: date) -> int:
    return hoy.year - 1


def en_ventana_aviso(anio: int, hoy: date) -> bool:
    """Entre la apertura del plazo y su último día (inclusive)."""
    p = PLAZOS_RENTA.get(anio)
    return bool(p and p[0] <= hoy <= p[1])
