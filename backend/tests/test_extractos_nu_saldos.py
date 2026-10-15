"""Extractos de Nu: saldos de la cuenta (resumen de movimientos) y producto cuenta vs tarjeta.
TODO el texto y los números son inventados."""
import os
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'nu.db')}")

from app import cuadre_extracto as cx  # noqa: E402
from app import extractos_gmail as eg  # noqa: E402
from app.routers import correos  # noqa: E402

TEXTO_CUENTA_NU = """Nu Colombia
Número de Cuenta 1234567890
Período 01 - 30 SEP 2026
Resumen de tus movimientos
Tu dinero al inicio del mes $1.248.276,89
Lo que entró a tu cuenta +$7.030.400,00
Lo que salió de tu cuenta -$5.239.500,00
Impuesto del 4x1000 $0,00
Costos por retiro $0,00
Rendimiento total de tu cuenta +$9.079,91
Tu dinero a final del mes $3.048.256,80
Dinero en tu Cuenta Nu $20.000,00
Dinero en tus cajitas $3.028.256,80
"""


def test_cuenta_nu_lee_saldos_y_corte():
    s = cx.leer_saldos_extracto(TEXTO_CUENTA_NU)
    assert s["saldo_inicial"] == 1248276.89
    assert s["saldo_final"] == 3048256.80
    assert s["fecha_corte"] == "2026-09-30"
    assert s["periodo_inicio"] == "2026-09-01"
    # El saldo que se compara con el libro es el TOTAL (cuenta + cajitas): las cajitas son parte de la cuenta.
    assert s["saldo_cuenta_principal"] == 20000.0 and s["saldo_cajitas"] == 3028256.80
    assert s["desglose_cuadra"] is True
    assert s["resumen_cuadra"] is True
    assert s["entradas"] == 7030400.0 and s["salidas"] == 5239500.0 and s["rendimiento"] == 9079.91


def test_cuenta_nu_resumen_que_no_cuadra_se_marca():
    t = TEXTO_CUENTA_NU.replace("$7.030.400,00", "$7.000.000,00")
    assert cx.leer_saldos_extracto(t)["resumen_cuadra"] is False


def test_tarjeta_nu_no_inventa_saldos_de_cuenta():
    texto = "Nu Colombia\nTarjeta de crédito\nFecha de corte 14 oct 2026\nTotal a pagar $850.000,00\nPago mínimo $85.000,00\nCupo total $5.000.000,00\n"
    s = cx.leer_saldos_extracto(texto, es_credito=True)
    assert s["saldo_final"] == -850000.0
    assert "saldo_cuenta_principal" not in s and "resumen_cuadra" not in s
    assert s["fecha_corte"] == "2026-10-14"


def _c(id, nombre, tipo):
    return SimpleNamespace(id=id, nombre=nombre, tipo=tipo, alias_tarjeta=None)


def test_tarjeta_nu_no_se_asigna_a_la_unica_cuenta_de_ahorros():
    cuentas = [_c("ah", "Nu Colombia", "ahorro")]
    tarjeta = "Extracto de tu tarjeta de crédito Nu. Cupo total, pago mínimo, fecha límite de pago"
    assert eg.sugerir_cuenta("Nu Colombia", "", cuentas, tarjeta) is None
    cuenta = "Extracto de tu cuenta de ahorros Nu. Cajita, saldo disponible"
    assert eg.sugerir_cuenta("Nu Colombia", "", cuentas, cuenta) == "ah"
    # Con las dos cuentas, cada producto va a la suya.
    ambas = cuentas + [_c("tc", "Nu Tarjeta", "credito")]
    assert eg.sugerir_cuenta("Nu Colombia", "", ambas, tarjeta) == "tc"


def test_extractos_miran_un_ano_pero_respetan_el_punto_de_partida():
    ref = datetime(2026, 10, 14)
    desde_90 = ref - timedelta(days=90)
    assert correos.desde_de_fase("notificaciones", desde_90, ref=ref) == desde_90
    assert correos.desde_de_fase("extractos", desde_90, ref=ref) == ref - timedelta(days=365)
    # «hoy» con inicio reciente: nunca antes del inicio.
    inicio = datetime(2026, 8, 1)
    assert correos.desde_de_fase("extractos", desde_90, inicio, "hoy", ref) == inicio
    # histórico: llega hasta la fecha elegida.
    ini_h = datetime(2025, 6, 1)
    assert correos.desde_de_fase("extractos", desde_90, ini_h, "historico", ref) == ini_h
    # incremental (desde reciente): no pierde meses viejos
    assert correos.desde_de_fase("extractos", ref - timedelta(days=1), ref=ref) == ref - timedelta(days=365)
