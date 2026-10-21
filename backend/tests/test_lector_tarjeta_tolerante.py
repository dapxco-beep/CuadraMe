"""Lector de la tarjeta Nu más tolerante con los formatos viejos (may-ago). Extractos INVENTADOS, sin cifras reales.

Reglas: una línea de «Pago»/«Abono» nunca se tipa como compra; la cuota de manejo se reconoce en todas sus variantes;
los intereses del resumen entran como gasto «Intereses de tu tarjeta»; si aun así no suma, la lectura NO queda completa."""
from app import extractos_tarjeta_nu as nu

CABECERA = """===== PAGINA 1 =====
Hola, Ana
Llegó tu extracto de Julio
Ana Pérez Gómez Tus tarjetas
Fecha límite de pago Fecha de corte Periodo facturado
04 AGO 2026 15 JUL 2026 15 JUN 2026 - 14 JUL
Resumen de tu extracto
Deuda a pagar este mes {a_pagar}
Tu cupo definido $1.000.000,00
Intereses + {intereses}
Usado Disponible
{usado} {disp}
Cuota de manejo + {manejo}
Deuda restante + {restante}
Nu Financiera
===== PAGINA 2 =====
Fecha Descripción Valor Cuotas Valor Interés del mes Total a pagar Restante
del mes Porcentaje y valor este mes por pagar
"""


def _extracto(filas, a_pagar="$30.000,00", manejo="$12.000,00", restante="$0,00", intereses="$0,00", usado="$42.000,00", disp="$958.000,00"):
    return CABECERA.format(a_pagar=a_pagar, manejo=manejo, restante=restante, intereses=intereses, usado=usado, disp=disp) + "\n".join(filas) + "\n"


COMPRA = ["08 JUL Tienda Alfa Sa $30.000,00 1 de 1 $30.000,00 2.09% $0,00 $30.000,00 $0,00", "2026"]


def _tipos(texto):
    return [l["tipo_linea"] for l in nu.leer_extracto_tarjeta_nu(texto)["lineas"]]


def test_cuota_de_manejo_sin_de_manejo_en_la_linea_siguiente():
    t = _extracto(["14 JUL Cobro por cuota $12.000,00 - $12.000,00 - - $12.000,00", "2026", *COMPRA])
    r = nu.leer_extracto_tarjeta_nu(t)
    assert nu.CUOTA_MANEJO in _tipos(t)
    assert r["lectura_completa"] is True


def test_cuota_de_manejo_con_otras_formas_de_escribirla():
    for desc in ("Cuota de manejo", "Cobro por cuota", "Cargo por cuota de manejo", "Cobro cuota de manejo"):
        t = _extracto([f"14 JUL {desc} $12.000,00 - $12.000,00 - - $12.000,00", "2026", *COMPRA])
        assert _tipos(t).count(nu.CUOTA_MANEJO) == 1, desc
        assert nu.leer_extracto_tarjeta_nu(t)["lectura_completa"] is True, desc


def test_cuota_de_manejo_con_un_solo_importe():
    t = _extracto(["14 JUL Cobro por cuota de manejo $12.000,00", "2026", *COMPRA])
    assert nu.CUOTA_MANEJO in _tipos(t)


def test_un_abono_o_pago_nunca_es_compra():
    t = _extracto(["10 JUL Abono a tarjeta $470.000,00", "2026", "11 JUL Pago PSE $50.000,00 -$50.000,00", "2026",
                   "14 JUL Cobro por cuota de manejo $12.000,00 - $12.000,00 - - $12.000,00", "2026", *COMPRA])
    r = nu.leer_extracto_tarjeta_nu(t)
    tipos = _tipos(t)
    assert tipos.count(nu.PAGO) == 2
    assert not any(t_ in (nu.COMPRA, nu.COMPRA_EN_CUOTAS) and "abono" in l["descripcion"].lower() for t_, l in zip(tipos, r["lineas"]))
    pagos = [m for m in r["movimientos"] if m["linea_tipo"] == nu.PAGO]
    assert {p["monto"] for p in pagos} == {470000.0, 50000.0} and all(p["tipo"] == "income" for p in pagos)
    assert r["lectura_completa"] is True  # los pagos no cuentan en el total a pagar


def test_lo_que_aparece_bajo_una_seccion_de_abonos_es_pago():
    t = _extracto(["14 JUL Cobro por cuota de manejo $12.000,00 - $12.000,00 - - $12.000,00", "2026", *COMPRA,
                   "Abonos", "09 JUL Transferencia recibida $90.000,00", "2026"])
    assert _tipos(t).count(nu.PAGO) == 1


def test_los_intereses_del_resumen_entran_como_gasto():
    t = _extracto(["14 JUL Cobro por cuota de manejo $12.000,00 - $12.000,00 - - $12.000,00", "2026", *COMPRA], intereses="$7.500,00")
    r = nu.leer_extracto_tarjeta_nu(t)
    intereses = [l for l in r["lineas"] if l["tipo_linea"] == nu.INTERESES]
    assert len(intereses) == 1 and intereses[0]["monto"] == 7500.0 and intereses[0]["fecha"] == "2026-07-15"
    mov = [m for m in r["movimientos"] if m["linea_tipo"] == nu.INTERESES][0]
    assert mov["tipo"] == "expense" and mov["descripcion"] == "Intereses de tu tarjeta"
    assert r["lectura_completa"] is True


def test_sin_intereses_en_el_resumen_no_se_inventa_ninguno():
    t = _extracto(["14 JUL Cobro por cuota de manejo $12.000,00 - $12.000,00 - - $12.000,00", "2026", *COMPRA])
    assert nu.INTERESES not in _tipos(t)


def test_si_no_suma_la_lectura_no_queda_completa_y_lo_dice():
    t = _extracto(["14 JUL Cobro por cuota de manejo $12.000,00 - $12.000,00 - - $12.000,00", "2026"])  # falta la compra
    r = nu.leer_extracto_tarjeta_nu(t)
    assert r["lectura_completa"] is False
    assert "faltan $30.000 para sumar lo que dice tu extracto" in r["mensaje_lectura"]
    assert "Revisa antes de importar" in r["mensaje_lectura"]
