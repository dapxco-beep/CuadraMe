"""Funciones puras de planificación con casos numéricos verificados a mano."""
from datetime import date, datetime

import pytest

from app import planificacion as p


# ---------------------------------------------------------------- periodos

def test_periodo_mensual_octubre():
    r = p.rango_periodo(date(2026, 10, 16), "monthly")
    assert r["inicio"] == date(2026, 10, 1) and r["fin"] == date(2026, 11, 1)
    assert (r["dias_totales"], r["dias_transcurridos"], r["dias_restantes"]) == (31, 16, 15)


def test_periodo_desconocido_cae_en_mensual():
    assert p.normalizar_periodo(None) == "monthly"
    assert p.normalizar_periodo("quincenal") == "biweekly"
    assert p.normalizar_periodo("raro") == "monthly"


def test_quincena_clasica_1_15_y_16_fin():
    a = p.rango_periodo(date(2026, 10, 15), "biweekly")
    assert (a["inicio"], a["fin"], a["dias_totales"]) == (date(2026, 10, 1), date(2026, 10, 16), 15)
    assert a["dias_restantes"] == 0
    b = p.rango_periodo(date(2026, 10, 16), "biweekly")
    assert (b["inicio"], b["fin"], b["dias_totales"]) == (date(2026, 10, 16), date(2026, 11, 1), 16)
    feb = p.rango_periodo(date(2026, 2, 20), "biweekly")  # febrero: 16-28 son 13 días
    assert feb["dias_totales"] == 13


def test_quincena_alineada_al_dia_de_pago():
    # Día de pago 5 => quincenas 5-19 y 20-4.
    r = p.rango_periodo(date(2026, 10, 3), "biweekly", dia_pago=5)
    assert (r["inicio"], r["fin"]) == (date(2026, 9, 20), date(2026, 10, 5))
    r = p.rango_periodo(date(2026, 10, 10), "biweekly", dia_pago=5)
    assert (r["inicio"], r["fin"]) == (date(2026, 10, 5), date(2026, 10, 20))
    r = p.rango_periodo(date(2026, 10, 25), "biweekly", dia_pago=5)
    assert (r["inicio"], r["fin"]) == (date(2026, 10, 20), date(2026, 11, 5))
    # Pago el 30 se pliega a 15 y 30.
    r = p.rango_periodo(date(2026, 10, 20), "biweekly", dia_pago=30)
    assert (r["inicio"], r["fin"]) == (date(2026, 10, 15), date(2026, 10, 30))


def test_semana_inicia_lunes():
    r = p.rango_periodo(datetime(2026, 10, 3, 18, 0), "weekly")  # sábado 3 de octubre de 2026
    assert r["inicio"] == date(2026, 9, 28) and r["fin"] == date(2026, 10, 5)
    assert (r["dias_totales"], r["dias_transcurridos"], r["dias_restantes"]) == (7, 6, 1)


def test_periodo_anterior_y_claves():
    r = p.rango_periodo(date(2026, 1, 10), "monthly")
    ant = p.periodo_anterior(r["inicio"], "monthly")
    assert ant["inicio"] == date(2025, 12, 1) and ant["fin"] == date(2026, 1, 1)
    q = p.rango_periodo(date(2026, 10, 20), "biweekly")
    assert p.periodo_anterior(q["inicio"], "biweekly")["inicio"] == date(2026, 10, 1)
    assert p.clave_periodo(date(2026, 10, 1), "monthly") == "2026-10"  # formato histórico
    assert p.clave_periodo(date(2026, 10, 16), "biweekly") == "2026-10-16"


# -------------------------------------------------------------- proyección

def test_proyeccion_ejemplo_entretenimiento():
    # Mes de 30 días, día 15: 280.000 de 400.000 (70 %). Ritmo 18.666,67/día * 15 restantes
    # = 280.000 más => cierra en 560.000.
    rango = {"dias_totales": 30, "dias_transcurridos": 15, "dias_restantes": 15}
    r = p.proyectar_cierre(280_000, 400_000, rango, categoria="Entretenimiento")
    assert r["proyectado"] == pytest.approx(560_000)
    assert r["pct_usado"] == 70.0 and r["pct_proyectado"] == 140.0
    assert r["estado"] == "en_riesgo"
    assert r["mensaje"] == ("Llevas 70% de Entretenimiento y faltan 15 días; a este ritmo cerrarías en "
                            "$560.000, $160.000 por encima del límite.")
    assert r["dias_hasta_limite"] == pytest.approx(120_000 / (280_000 / 15))  # 6,43 días


def test_proyeccion_mezcla_con_historico():
    # w = 15/30 = 0,5; ritmo actual 18.666,67; histórico 300.000/30 = 10.000/día
    # mezcla = 14.333,33; proyectado = 280.000 + 14.333,33*15 = 495.000.
    rango = {"dias_totales": 30, "dias_transcurridos": 15, "dias_restantes": 15}
    r = p.proyectar_cierre(280_000, 600_000, rango, historico=[300_000, 0, 300_000])
    assert r["promedio_anterior"] == 300_000
    assert r["proyectado"] == pytest.approx(495_000)
    assert r["vs_anterior_pct"] == 65.0  # (495-300)/300
    assert r["estado"] == "bien"


def test_proyeccion_estados():
    rango = {"dias_totales": 30, "dias_transcurridos": 15, "dias_restantes": 15}
    assert p.proyectar_cierre(100_000, 400_000, rango)["estado"] == "bien"        # cierra 200.000
    assert p.proyectar_cierre(180_000, 400_000, rango)["estado"] == "atencion"    # cierra 360.000 = 90 %
    assert p.proyectar_cierre(450_000, 400_000, rango)["estado"] == "excedido"
    assert p.proyectar_cierre(10_000, 0, rango)["estado"] == "sin_limite"
    ultimo_dia = {"dias_totales": 30, "dias_transcurridos": 30, "dias_restantes": 0}
    assert p.proyectar_cierre(300_000, 400_000, ultimo_dia)["proyectado"] == 300_000


def test_proyectar_total():
    rango = {"dias_totales": 30, "dias_transcurridos": 15, "dias_restantes": 15}
    a = p.proyectar_cierre(280_000, 400_000, rango, categoria="A")
    b = p.proyectar_cierre(100_000, 400_000, rango, categoria="B")
    t = p.proyectar_total([a, b])
    assert t["gastado"] == 380_000 and t["limite"] == 800_000
    assert t["proyectado"] == pytest.approx(760_000)
    assert t["categorias_en_riesgo"] == 1


def test_sobrante_arrastrable():
    assert p.sobrante_arrastrable(500_000, 380_000) == 120_000
    assert p.sobrante_arrastrable(500_000, 620_000) == 0  # el exceso no se descuenta


# ------------------------------------------------------- reparto de ingreso

def test_distribucion_con_gastos_fijos_y_metas():
    # 4.000.000; fijos 1.800.000 (45 %). Resto 2.200.000 -> ahorro 40 % = 880.000, libre 1.320.000.
    # Metas necesitan 500.000 y 600.000 (1.100.000 > 880.000): factor 0,8 -> 400.000 y 480.000.
    # Sobres: Comida 600.000 y Ocio 400.000 => 792.000 y 528.000.
    d = p.sugerir_distribucion(
        4_000_000, None, gastos_fijos=1_800_000,
        metas=[{"id": "a", "nombre": "A", "aporte_mensual": 500_000},
               {"id": "b", "nombre": "B", "aporte_mensual": 600_000}],
        sobres=[{"categoria": "Comida", "limite": 600_000}, {"categoria": "Ocio", "limite": 400_000}],
    )
    assert d["necesidades"] == 1_800_000
    assert d["ahorro_total"] == 880_000 and d["gasto_libre"] == 1_320_000
    assert [m["monto"] for m in d["metas"]] == [400_000, 480_000]
    assert d["ahorro_libre"] == 0
    assert {s["categoria"]: s["monto"] for s in d["sobres"]} == {"Comida": 792_000, "Ocio": 528_000}
    assert d["avisos"] == []
    assert d["necesidades"] + d["ahorro_total"] + d["gasto_libre"] == d["monto"]


def test_distribucion_sin_datos_usa_50_30_20_y_metas_con_tope():
    d = p.sugerir_distribucion(2_000_000, metas=[{"id": "a", "nombre": "A", "aporte_mensual": 150_000}])
    assert (d["necesidades"], d["ahorro_total"], d["gasto_libre"]) == (1_000_000, 400_000, 600_000)
    assert d["metas"][0]["monto"] == 150_000      # no se pasa de lo que la meta necesita
    assert d["ahorro_libre"] == 250_000


def test_distribucion_fijos_altos_avisa_y_regla_personalizada():
    d = p.sugerir_distribucion(1_000_000, gastos_fijos=700_000)
    assert d["necesidades"] == 700_000 and d["ahorro_total"] == 120_000 and d["gasto_libre"] == 180_000
    assert len(d["avisos"]) == 1
    d = p.sugerir_distribucion(1_000_000, {"necesidades": 60, "deseos": 20, "ahorro": 20})
    assert (d["necesidades"], d["ahorro_total"], d["gasto_libre"]) == (600_000, 200_000, 200_000)
    # Regla que no suma 100 => vuelve a 50/30/20
    assert p.validar_regla({"necesidades": 70, "deseos": 20, "ahorro": 20}) == p.REGLA_DEFECTO


# -------------------------------------------------------------------- metas

def test_meses_y_aporte_requerido_sin_rendimiento():
    hoy = date(2026, 10, 3)
    assert p.meses_hasta(hoy, date(2027, 10, 3)) == 12   # 365 / 30,4375 = 11,99 -> 12
    assert p.meses_hasta(hoy, date(2026, 10, 3)) == 0
    assert p.aporte_requerido(12_000_000, 2_000_000, 12) == pytest.approx(10_000_000 / 12)


def test_aporte_requerido_con_rendimiento_ea():
    # 12 % EA, 12 meses, sin saldo: r = 1,12^(1/12)-1 = 0,0094888; (1+r)^12 = 1,12
    # PMT = 12.000.000 * r / 0,12 = 948.879
    assert p.aporte_requerido(12_000_000, 0, 12, 12) == pytest.approx(948_879, abs=1)
    # El saldo también rinde: 5.000.000 * 1,12 = 5.600.000; faltan 6.400.000 -> 6.400.000*r/0,12
    assert p.aporte_requerido(12_000_000, 5_000_000, 12, 12) == pytest.approx(6_400_000 * p.tasa_mensual(12) / 0.12, abs=1)


def test_meses_para_meta():
    assert p.meses_para_meta(12_000_000, 2_000_000, 500_000) == 20
    assert p.meses_para_meta(12_000_000, 2_000_000, 600_000) == 17      # 16,67
    assert p.meses_para_meta(12_000_000, 2_000_000, 0) is None
    assert p.meses_para_meta(10, 20, 0) == 0
    # Con 12 % EA y 948.879 al mes se llega justo en 12 meses
    assert p.meses_para_meta(12_000_000, 0, 948_880, 12) == 12
    # Con rendimiento y sin aportes también puede llegar: 1.000.000 -> 2.000.000 a 12 % EA = ln2/ln1,12 = 6,12 años
    assert p.meses_para_meta(2_000_000, 1_000_000, 0, 12) == 74


def test_plan_meta_incompatible():
    # Quiere 12M en 12 meses, sin saldo; ingresa 3M y gasta 2,5M (le sobran 500.000).
    plan = p.plan_meta(12_000_000, 0, date(2027, 10, 3), date(2026, 10, 3),
                       ahorro_real_mensual=300_000, ingreso_mensual=3_000_000, gasto_mensual=2_500_000)
    assert plan["aporte_requerido"] == 1_000_000
    assert plan["capacidad_ahorro"] == 500_000
    assert plan["viabilidad"] == "incompatible" and "1.000.000" in plan["advertencia"]
    assert plan["meses_a_ritmo_actual"] == 40
    assert plan["meses_con_extra"] == 30   # 12M / 400.000
    assert "la logras en 40 meses" in plan["mensaje"] and "en 30" in plan["mensaje"]


def test_plan_meta_viable_ajustada_y_lograda():
    hoy, fecha = date(2026, 10, 3), date(2027, 10, 3)
    viable = p.plan_meta(6_000_000, 0, fecha, hoy, 500_000, 3_000_000, 2_000_000)   # 500.000 <= 80 % de 1M
    assert viable["viabilidad"] == "viable"
    ajustada = p.plan_meta(10_800_000, 0, fecha, hoy, 500_000, 3_000_000, 2_000_000)  # 900.000 entre 80 y 100 %
    assert ajustada["viabilidad"] == "ajustada"
    assert p.plan_meta(1_000, 5_000, fecha, hoy)["viabilidad"] == "lograda"
    assert p.plan_meta(5_000_000, 0, fecha, hoy)["viabilidad"] == "sin_datos"
    assert p.plan_meta(5_000_000, 0, date(2026, 9, 1), hoy)["viabilidad"] == "fecha_vencida"


# --------------------------------------------------- patrimonio: descomposición

PREV = {"mes": "2026-08", "total_activos": 10_000_000, "total_cuentas": 2_000_000, "total_deudas": 5_000_000}
CUR = {"mes": "2026-09", "total_activos": 11_000_000, "total_cuentas": 2_500_000, "total_deudas": 4_500_000}


def test_descomposicion_suma_el_cambio_del_neto():
    # Neto 7M -> 9M (+2M). Aportes a activos 400.000.
    # valorización = 1.000.000 - 400.000 = 600.000; deuda baja 500.000;
    # ahorro = 500.000 (cuentas) + 400.000 = 900.000.   600+500+900 = 2.000.000
    d = p.descomponer_crecimiento(PREV, CUR, 400_000)
    assert d["valorizacion"] == 600_000 and d["reduccion_deuda"] == 500_000 and d["ahorro"] == 900_000
    assert d["neto_delta"] == 2_000_000
    assert d["valorizacion"] + d["reduccion_deuda"] + d["ahorro"] == d["neto_delta"]


def test_descomposicion_mes_malo_y_deuda_que_crece():
    malo = {"mes": "2026-10", "total_activos": 10_500_000, "total_cuentas": 2_500_000, "total_deudas": 4_800_000}
    d = p.descomponer_crecimiento(CUR, malo, 0)   # activos -500.000 (pérdida), deuda +300.000
    assert d["valorizacion"] == -500_000 and d["reduccion_deuda"] == -300_000 and d["ahorro"] == 0
    assert d["neto_delta"] == -800_000


def test_serie_descomposicion_pares_consecutivos():
    snaps = [CUR, PREV, {**CUR, "mes": "2026-10", "total_cuentas": 3_000_000}]  # desordenados
    serie = p.serie_descomposicion(snaps, {"2026-09": 400_000})
    assert [s["mes"] for s in serie] == ["2026-09", "2026-10"]
    assert serie[0]["ahorro"] == 900_000
    assert serie[1]["ahorro"] == 500_000 and serie[1]["valorizacion"] == 0
    assert p.serie_descomposicion([PREV]) == []
