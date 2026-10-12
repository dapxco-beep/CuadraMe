"""Genera un respaldo ficticio de CuadraMe (cuenta demo) listo para «Importar mi respaldo».

Persona: Camila Rojas, 29 años, analista en Bogotá, salario neto ~$4,8 M, paga arriendo,
mercado, transporte (TransMilenio/Uber), Netflix/Spotify, gimnasio, una tarjeta de crédito y
una meta de ahorro. Todo inventado: ningún dato real.

Uso:  python tools/generar_demo.py [salida.zip]
Luego en la app: Perfil -> Importar mi respaldo -> subir el ZIP (con la cuenta demo ya creada).

Decisiones clave:
  * El importador NO ajusta el saldo de cuentas nuevas: el saldo del respaldo es el final.
    Por eso se calcula aquí: saldo inicial + suma de deltas (misma regla que contabilidad.delta_saldo).
  * Semilla fija -> el mismo ZIP cada vez (reproducible para demos y capturas).
  * Fechas relativas a HOY: siempre hay datos del mes en curso.
"""
import json
import random
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

HOY = date.today()
INICIO = date(HOY.year, HOY.month, 1) - timedelta(days=122)  # ~4 meses atrás
rnd = random.Random(2026)

# id local -> datos. El importador remapea estos ids a UUID nuevos.
CUENTAS = {
    "c_banco": dict(nombre="Bancolombia Ahorros", tipo="ahorro", icono="🏦", inicial=2_300_000),
    "c_nequi": dict(nombre="Nequi", tipo="ahorro", icono="💜", inicial=150_000),
    "c_efectivo": dict(nombre="Efectivo", tipo="efectivo", icono="💵", inicial=120_000),
    "c_tc": dict(nombre="Visa Falabella", tipo="credito", icono="💳", inicial=-600_000,
                 cupo_total=6_000_000, dia_corte=20, dia_pago=5, tasa_ea=28.5,
                 alias_tarjeta="Visa Falabella"),
    "c_cdt": dict(nombre="CDT Davivienda", tipo="inversion", icono="📈", inicial=5_000_000),
}

movs: list[dict] = []


def mov(cuenta, d, tipo, monto, desc, cat, fuente="manual", notas="", hora=None):
    h = hora if hora is not None else rnd.randint(8, 21)
    movs.append(dict(
        cuenta_id=cuenta, fecha=datetime(d.year, d.month, d.day, h, rnd.randint(0, 59)).isoformat(),
        descripcion=desc, categoria=cat, tipo=tipo, monto=float(monto), fuente=fuente, notas=notas,
        cat_confirmada=True,
    ))


def traslado(origen, destino, d, monto, desc):
    mov(origen, d, "transfer", monto, desc, "Transferencias", "transferencia_interna", "T:out", 9)
    mov(destino, d, "transfer", monto, desc, "Transferencias", "transferencia_interna", "T:in", 9)


def redondea(x, paso=100):
    return int(round(x / paso) * paso)


def dias(desde, hasta):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def ultimo_dia(y, m):
    return (date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)).day


# ── Recurrentes mensuales ─────────────────────────────────────────────────────────────
y, m = INICIO.year, INICIO.month
while date(y, m, 1) <= HOY:
    def en(dia):
        return date(y, m, min(dia, ultimo_dia(y, m)))
    fijos = [
        (en(1), "c_banco", "expense", 1_450_000, "Arriendo apartamento", "Hogar"),
        (en(3), "c_banco", "expense", 165_000, "Administración conjunto", "Hogar"),
        (en(6), "c_banco", "expense", 98_000, "Claro internet hogar", "Hogar"),
        (en(8), "c_banco", "expense", 62_000, "Enel energía", "Hogar"),
        (en(9), "c_banco", "expense", 41_000, "Acueducto Bogotá", "Hogar"),
        (en(7), "c_tc", "expense", 44_900, "Netflix", "Suscripciones"),
        (en(12), "c_tc", "expense", 23_900, "Spotify", "Suscripciones"),
        (en(2), "c_banco", "expense", 129_000, "Smart Fit mensualidad", "Salud"),
        (en(10), "c_banco", "expense", 98_000, "Plan Claro celular", "Hogar"),
    ]
    for d, c, t, mt, desc, cat in fijos:
        if d <= HOY:
            mov(c, d, t, mt, desc, cat, hora=7)
    # Salario quincenal (15 y último día)
    for d in (en(15), en(ultimo_dia(y, m))):
        if d <= HOY:
            mov("c_banco", d, "income", 2_400_000, "Nómina Empresa SAS", "Ingresos", hora=6)
    # Freelance ocasional
    if m % 2 == 0 and en(22) <= HOY:
        mov("c_nequi", en(22), "income", redondea(rnd.uniform(350_000, 600_000), 10_000),
            "Pago proyecto freelance", "Ingresos", hora=15)
    # Ahorro a la meta y pago de tarjeta
    if en(16) <= HOY:
        traslado("c_banco", "c_nequi", en(16), 450_000, "Recarga Nequi")
        if en(2) <= HOY:
            traslado("c_banco", "c_nequi", en(2), 300_000, "Recarga Nequi")
        traslado("c_banco", "c_efectivo", en(17), 250_000, "Retiro cajero Bancolombia")
    if en(5) <= HOY and (y, m) != (INICIO.year, INICIO.month):
        traslado("c_banco", "c_tc", en(5), 600_000, "Pago tarjeta Visa Falabella")
    m += 1
    if m == 13:
        y, m = y + 1, 1

# ── Gasto del día a día ───────────────────────────────────────────────────────────────
MERCADO = [("Éxito", 85_000, 240_000), ("D1", 25_000, 90_000), ("Jumbo", 120_000, 280_000),
           ("Tienda de barrio", 8_000, 30_000), ("Ara", 20_000, 70_000)]
COMIDA = [("Crepes & Waffles", 45_000, 95_000), ("Rappi domicilio", 28_000, 62_000),
          ("Juan Valdez Café", 9_000, 22_000), ("Corral hamburguesas", 30_000, 58_000),
          ("Almuerzo corrientazo", 14_000, 22_000), ("Panadería Dalú", 6_000, 18_000),
          ("Starbucks", 14_000, 26_000)]
TRANSP = [("Uber", 9_000, 34_000), ("Recarga TuLlave TransMilenio", 20_000, 40_000),
          ("DiDi", 8_000, 26_000), ("Terpel gasolina moto", 25_000, 45_000)]
OCIO = [("Cine Colombia", 28_000, 60_000), ("Bar Zona T", 50_000, 140_000),
        ("Steam videojuego", 25_000, 90_000), ("Entradas concierto", 120_000, 260_000)]
VARIOS = [("Farmacia Cruz Verde", "Salud", 15_000, 80_000), ("Droguería Colsubsidio", "Salud", 10_000, 55_000),
          ("Peluquería", "Otros", 25_000, 60_000), ("Falabella ropa", "Otros", 80_000, 220_000),
          ("Mercado Libre", "Otros", 30_000, 180_000), ("Cita médica EPS copago", "Salud", 4_000, 12_000)]


def elige(lista):
    return lista[rnd.randrange(len(lista))]


for d in dias(INICIO, HOY):
    if d.weekday() in (5, 6) and rnd.random() < 0.55:  # fines de semana: salidas
        n, lo, hi = elige(COMIDA)
        c = rnd.choice(["c_tc", "c_nequi", "c_efectivo"])
        mov(c, d, "expense", redondea(rnd.uniform(lo, hi)), n, "Comida")
        if rnd.random() < 0.35:
            n, lo, hi = elige(OCIO)
            mov(rnd.choice(["c_tc", "c_nequi"]), d, "expense", redondea(rnd.uniform(lo, hi)), n, "Ocio")
    if d.weekday() < 5:
        if rnd.random() < 0.7:
            n, lo, hi = elige(TRANSP)
            mov(rnd.choice(["c_nequi", "c_efectivo", "c_banco"]), d, "expense",
                redondea(rnd.uniform(lo, hi)), n, "Transporte")
        if rnd.random() < 0.6:
            n, lo, hi = elige(COMIDA[2:5])
            mov(rnd.choice(["c_efectivo", "c_nequi"]), d, "expense", redondea(rnd.uniform(lo, hi)), n, "Comida")
    if d.weekday() == 5 or (d.day in (12, 27)):
        n, lo, hi = elige(MERCADO)
        mov(rnd.choice(["c_banco", "c_tc"]), d, "expense", redondea(rnd.uniform(lo, hi)), n, "Comida")
    if rnd.random() < 0.09:
        n, cat, lo, hi = elige(VARIOS)
        mov(rnd.choice(["c_tc", "c_banco", "c_nequi"]), d, "expense", redondea(rnd.uniform(lo, hi)), n, cat)

# Intereses de la CDT (ingreso pequeño mensual) y retiro en cajero
for k in range(4):
    d = date(HOY.year, HOY.month, 1) - timedelta(days=30 * k + 1)
    if d >= INICIO:
        mov("c_cdt", d, "income", 52_000, "Rendimientos CDT", "Ingresos", hora=5)
        mov("c_efectivo", d + timedelta(days=3), "income", 150_000, "Retiro cajero Bancolombia", "Transferencias",
            "transferencia_interna", "T:in", 12)
        mov("c_banco", d + timedelta(days=3), "transfer", 150_000, "Retiro cajero Bancolombia", "Transferencias",
            "transferencia_interna", "T:out", 12)

# El retiro de efectivo quedó como income en efectivo: corregirlo a transfer con dirección
for x in movs:
    if x["descripcion"] == "Retiro cajero Bancolombia" and x["tipo"] == "income":
        x["tipo"] = "transfer"

movs = [x for x in movs if datetime.fromisoformat(x["fecha"]).date() <= HOY]
movs.sort(key=lambda x: x["fecha"])


# ── Saldos finales = inicial + deltas (regla de contabilidad.delta_saldo) ─────────────
def delta(x):
    if x["tipo"] == "income":
        return x["monto"]
    if x["tipo"] == "expense":
        return -x["monto"]
    if x["tipo"] == "transfer" and x["fuente"] == "transferencia_interna":
        return x["monto"] if x["notas"].endswith(":in") else -x["monto"]
    return 0.0


saldo = {k: float(v["inicial"]) for k, v in CUENTAS.items()}
for x in movs:
    saldo[x["cuenta_id"]] += delta(x)

cuentas_json = []
for k, v in CUENTAS.items():
    fila = {kk: vv for kk, vv in v.items() if kk != "inicial"}
    fila.update(id=k, saldo=round(saldo[k]), moneda="COP")
    cuentas_json.append(fila)

presupuestos = [dict(categoria=c, periodo="monthly", limite=l, alerta_pct=80, activo=True)
                for c, l in [("Comida", 1_100_000), ("Transporte", 280_000), ("Ocio", 350_000),
                             ("Hogar", 1_900_000), ("Salud", 250_000), ("Suscripciones", 80_000)]]

en6 = datetime.combine(HOY + timedelta(days=180), datetime.min.time())
metas = [
    dict(id="m_viaje", nombre="Viaje a Cartagena", descripcion="Vacaciones de fin de año", monto_objetivo=3_500_000,
         monto_actual=1_450_000, icono="🏖️", fecha_objetivo=datetime(HOY.year, 12, 15).isoformat(),
         fecha_inicio=INICIO.isoformat(), activa=True),
    dict(id="m_fondo", nombre="Fondo de emergencia", descripcion="3 meses de gastos", monto_objetivo=12_000_000,
         monto_actual=5_000_000, icono="🛟", fecha_objetivo=en6.isoformat(),
         fecha_inicio=INICIO.isoformat(), activa=True),
]

reglas = [dict(patron=p, categoria=c, tipo="expense", prioridad=1) for p, c in
          [("rappi", "Comida"), ("uber", "Transporte"), ("netflix", "Suscripciones"), ("spotify", "Suscripciones"),
           ("smart fit", "Salud"), ("terpel", "Transporte"), ("enel", "Hogar")]]

datos = dict(formato="cuadrame-respaldo", version=1, correo="camila.demo@cuadrame.app",
             tablas=dict(cuentas=cuentas_json, movimientos=movs, presupuestos=presupuestos,
                         metas=metas, reglas_categoria=reglas))

salida = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "demo" / "cuadrame-demo.zip")
salida.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("datos.json", json.dumps(datos, ensure_ascii=False, indent=1))
print(f"{salida}: {len(cuentas_json)} cuentas, {len(movs)} movimientos, "
      f"{len(presupuestos)} presupuestos, {len(metas)} metas")
for c in cuentas_json:
    print(f"  {c['nombre']}: {c['saldo']:,}")
