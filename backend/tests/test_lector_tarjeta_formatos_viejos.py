"""Formatos viejos (may-ago) de la tarjeta Nu. Cuatro extractos SINTÉTICOS con cifras inventadas que cumplen las relaciones:

  cadena:  usado(k) = usado(k-1) + cargos del periodo (compras completas, avances, comisiones, intereses, manejo) - pagos
  fórmula: usado = a pagar + restante + manejo + conversión + intereses + comisiones - abonaste
  a pagar = suma del «total a pagar» de las líneas que NO son manejo, intereses ni comisiones.
"""
from pathlib import Path

import pytest

from app import extractos_tarjeta_nu as nu
from app.conciliacion import compute_fingerprint, huella_de_linea, parse_bank_date
from app.contabilidad import MARCA_TRASLADO_PROPIO
from app import corregir_tipo

FIX = Path(__file__).parent / "fixtures"
MESES = ("mayo", "junio", "julio", "agosto")
USADO = {"mayo": 276_000, "junio": 204_000, "julio": 361_000, "agosto": 203_000}


def _leer(mes, quitar=None):
    t = (FIX / f"extracto_tarjeta_nu_viejo_{mes}.txt").read_text(encoding="utf-8")
    if quitar:
        assert quitar in t
        t = t.replace(quitar, "")
    return nu.leer_extracto_tarjeta_nu(t)


def _tipos(r):
    return [l["tipo_linea"] for l in r["lineas"]]


@pytest.mark.parametrize("mes", MESES)
def test_los_cuatro_extractos_se_leen_completos(mes):
    r = _leer(mes)
    assert r["lectura_completa"] is True, r["mensaje_lectura"]
    assert r["resumen_tarjeta"]["usado"] == USADO[mes]
    assert all(v["cuadra"] for v in r["verificacion"] if v["critica"])


def test_mayo_periodo_desde_abril_y_el_mes_es_el_del_corte():
    r = _leer("mayo")["resumen_tarjeta"]
    assert r["periodo"] == {"inicio": "2026-04-10", "fin": "2026-05-14"} and r["corte"] == "2026-05-14"


def test_gracias_por_tu_pago_es_un_pago_con_el_primer_importe():
    r = _leer("mayo")
    pagos = [l for l in r["lineas"] if l["tipo_linea"] == nu.PAGO]
    assert [p["monto"] for p in pagos] == [90_000.0, 30_000.0]  # «$A -$A $0,00» y «$A $0,00 $0,00»
    assert sum(1 for l in r["lineas"] if l["tipo_linea"] in (nu.COMPRA, nu.COMPRA_EN_CUOTAS) and "gracias" in l["descripcion"].lower()) == 0
    mov = [m for m in r["movimientos"] if m["linea_tipo"] == nu.PAGO]
    assert all(m["tipo"] == "income" and m["pago_tarjeta"] for m in mov)
    # el lector anterior los guardó como «Gracias por tu pago»: esa huella se reconoce para no duplicar lo ya importado
    viejo = compute_fingerprint(parse_bank_date("2026-05-05"), 90_000.0, "", "Gracias por tu pago", "income")
    assert huella_de_linea({**mov[0], "cuenta": ""}, {viejo}) == viejo


def test_el_avance_trae_comision_por_servicio_e_intereses_y_es_traslado_propio():
    r = _leer("mayo")
    av = next(l for l in r["lineas"] if l["tipo_linea"] == nu.AVANCE)
    assert av["monto"] == 200_000.0 and av["total_mes"] == 210_000.0  # T = V + C + I
    assert [l["monto"] for l in r["lineas"] if l["tipo_linea"] == nu.COMISION_SERVICIO] == [7_000.0]
    assert sorted(l["monto"] for l in r["lineas"] if l["tipo_linea"] == nu.INTERESES) == [3_000.0, 4_000.0]
    mov = {m["linea_tipo"]: m for m in r["movimientos"]}
    assert mov[nu.AVANCE]["tipo"] == "expense" and mov[nu.AVANCE]["pista"] == MARCA_TRASLADO_PROPIO
    assert mov[nu.COMISION_SERVICIO]["descripcion"] == "Comisión por servicio de avance"
    assert corregir_tipo.declara({**mov[nu.AVANCE]})  # si el lector viejo lo guardó como ingreso, se corrige el tipo


def test_fila_sin_descripcion_con_solo_columnas_de_interes_es_el_cobro_de_intereses():
    r = _leer("junio")
    it = [l for l in r["lineas"] if l["tipo_linea"] == nu.INTERESES]
    assert len(it) == 1 and it[0]["monto"] == 6_000.0 and it[0]["descripcion"] == "Intereses de tu tarjeta"


def test_la_cuota_de_manejo_que_solo_trae_el_resumen_se_agrega_marcada():
    r = _leer("julio")
    extra = [l for l in r["lineas"] if l.get("desde_resumen")]
    assert len(extra) == 1 and extra[0]["tipo_linea"] == nu.CUOTA_MANEJO and extra[0]["monto"] == 12_000.0
    assert extra[0]["fecha"] == "2026-07-15"  # el día del corte


def test_las_cuotas_siguientes_de_una_compra_en_cuotas_no_son_movimientos_nuevos():
    r = _leer("agosto")
    anteriores = [l for l in r["lineas"] if l["tipo_linea"] == nu.CUOTA_DE_COMPRA_ANTERIOR]
    assert len(anteriores) == 2  # «4 de 6» y el saldo financiado: cuentan en la verificación, no se importan
    assert not any(m["descripcion"] == "Mercpago*Pandora" for m in r["movimientos"])
    primera = _leer("mayo")
    pandora = next(l for l in primera["lineas"] if l["descripcion"] == "Mercpago*Pandora")
    assert pandora["tipo_linea"] == nu.COMPRA_EN_CUOTAS and pandora["monto"] == 120_000.0  # el valor COMPLETO el día de la compra


def test_la_cadena_de_deuda_cuadra_exacto_entre_los_cuatro_extractos():
    usado = 0.0  # mayo: la tarjeta empezó en ese periodo
    for mes in MESES:
        r = _leer(mes)
        cargos = sum(m["monto"] for m in r["movimientos"] if m["tipo"] == "expense")
        pagos = sum(m["monto"] for m in r["movimientos"] if m["tipo"] == "income")
        usado = usado + cargos - pagos
        assert usado == r["resumen_tarjeta"]["usado"] == USADO[mes], mes


def test_la_formula_del_resumen_se_comprueba_y_una_linea_perdida_la_rompe():
    r = _leer("julio")
    assert next(v for v in r["verificacion"] if v["clave"] == "formula_usado")["cuadra"]
    perdida = _leer("julio", quitar="01 JUL Cuota por avance a cuenta $100.000,00 1 de 1 $100.000,00 2.07% $2.000,00 $105.000,00 $0,00\n2026\n"
                                    "↪ Comisión por servicio $3.000,00\n")
    assert perdida["lectura_completa"] is False
    assert "faltan $100.000" in perdida["mensaje_lectura"] or "Revisa antes de importar" in perdida["mensaje_lectura"]


def test_si_el_resumen_no_cumple_la_formula_no_se_le_exige():
    # el extracto sintético de octubre tiene otras cifras: la fórmula no aplica y no frena la lectura
    t = (FIX / "extracto_tarjeta_nu_sintetico.txt").read_text(encoding="utf-8")
    r = nu.leer_extracto_tarjeta_nu(t)
    assert r["lectura_completa"] is True and not any(v["clave"] == "formula_usado" for v in r["verificacion"])
