"""Validación del resumen de Informes con datos reales a través de la API (base SQLite temporal, un usuario nuevo por
prueba): tasa de ahorro con ingresos cero / flujo negativo / devoluciones / ajustes / periodos parciales, presupuesto
contra gasto real, hallazgos con datos faltantes y seguridad del endpoint nuevo."""
import calendar
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'validacion.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import informe as inf  # noqa: E402
from app import limites  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import informes as router_informes  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)


def test_las_pruebas_corren_sobre_sqlite_temporal():
    """Garantía de aislamiento: ninguna prueba de esta suite puede tocar una base real."""
    assert settings.database_url.startswith("sqlite")


def _clave(delta):
    hoy = ahora_co()
    a, m = inf.sumar_meses(hoy.year, hoy.month, delta)
    return a, m, f"{a}-{m:02d}"


A = _clave(-3)   # mes de la prueba
B = _clave(-4)   # el mes anterior


def _f(mes, dia, hora=12):
    a, m, _ = mes
    return datetime(a, m, min(dia, calendar.monthrange(a, m)[1]), hora).isoformat()


@pytest.fixture(autouse=True)
def usuario():
    """Un usuario nuevo por prueba: nada de lo que hace una prueba se ve en otra."""
    uid = f"val-{uuid.uuid4().hex[:10]}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@test.com", nombre="V")
    limites._eventos.clear()
    yield uid
    app.dependency_overrides.pop(get_current_user, None)


def _cuenta(nombre="Ahorros", tipo="ahorro"):
    r = client.post("/cuentas", json={"nombre": nombre, "saldo": 0, "tipo": tipo})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _mov(cuenta, desc, monto, tipo, cat, fecha, **extra):
    r = client.post("/movimientos", json={"cuenta_id": cuenta, "descripcion": desc, "monto": monto, "tipo": tipo,
                                          "categoria": cat, "fecha": fecha, "confirmar_nuevo": True, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _resumen(**p):
    r = client.get("/informes/resumen", params=p)
    assert r.status_code == 200, r.text
    return r.json()


def _mes(m):
    return {"periodo": "mes", "mes": m[2]}


def _ids(d):
    return {h["id"] for h in d["hallazgos"]}


# ═══ 1. TASA DE AHORRO ═══════════════════════════════════════════════════════════════════════
def test_ingresos_cero_no_inventa_tasa_ni_concluye_que_ahorras():
    c = _cuenta()
    _mov(c, "Mercado Éxito", 100_000, "expense", "Comida", _f(A, 5))
    d = _resumen(**_mes(A))
    assert (d["ingresos"], d["gastos"], d["balance"]) == (0, 100_000, -100_000)
    assert d["tasa_ahorro"] is None                                   # no 0 %, no −∞: simplemente no hay tasa
    assert d["variacion"]["tasa_ahorro_puntos"] is None
    assert next(m for m in d["meses"] if m["mes"] == A[2])["tasa_ahorro"] is None
    assert d["tasa_serie"] == {"promedio": None, "mejor": None, "peor": None, "meses_con_tasa": 0}
    ids = _ids(d)
    assert "sin_ingresos" in ids and "tasa" not in ids and "flujo" not in ids   # dice «no hay ingresos», no «flujo negativo»
    h = next(h for h in d["hallazgos"] if h["id"] == "sin_ingresos")
    assert "no hay ingresos anotados" in h["texto"] and h["enlace"].startswith("/agregar")


def test_flujo_negativo_tasa_negativa_y_promedio_ponderado():
    c = _cuenta()
    _mov(c, "Sueldo Empresa", 100_000, "income", "Sueldo", _f(A, 1))
    _mov(c, "Arriendo", 300_000, "expense", "Hogar", _f(A, 2))
    d = _resumen(**_mes(A))
    assert (d["balance"], d["tasa_ahorro"]) == (-200_000, -200.0)
    assert d["tasa_serie"]["promedio"] == -200.0 and d["tasa_serie"]["meses_con_tasa"] == 1
    h = next(h for h in d["hallazgos"] if h["id"] == "flujo")
    assert h["tono"] == "atento" and "faltaron" in h["texto"] and "$200.000" in h["texto"]
    assert d["flujo"]["negativos"] == 1 and d["flujo"]["positivos"] == 1       # el día 1 suma, el día 2 resta


def test_devoluciones_se_cuentan_como_ingreso_solo_si_entran_a_una_cuenta_normal():
    """Regla vigente en TODA la app (contabilidad.py): una devolución que entra a ahorros es un ingreso; la que entra a la
    tarjeta de crédito es el abono de una deuda y NO es ingreso. El resumen debe contar igual que el resto."""
    ahorros, tarjeta = _cuenta("Ahorros"), _cuenta("Visa", "credito")
    _mov(ahorros, "Sueldo Empresa", 1_000_000, "income", "Sueldo", _f(A, 1))
    _mov(ahorros, "Devolución Éxito", 50_000, "income", "Devoluciones", _f(A, 6))
    _mov(tarjeta, "Reembolso Rappi", 30_000, "income", "Devoluciones", _f(A, 7))
    _mov(ahorros, "Mercado Éxito", 200_000, "expense", "Comida", _f(A, 3))
    d = _resumen(**_mes(A))
    assert d["ingresos"] == 1_050_000                                # sueldo + devolución a ahorros; sin los 30.000 de la tarjeta
    assert d["gastos"] == 200_000 and d["balance"] == 850_000
    assert d["tasa_ahorro"] == round(850_000 / 1_050_000 * 100, 1)
    nombres = {f["nombre"] for f in d["fuentes"]["fuentes"]}
    assert "Devolución Éxito" in nombres and "Reembolso Rappi" not in nombres
    assert d["fuentes"]["total"] == d["ingresos"]                    # las fuentes SIEMPRE suman el ingreso del periodo


def test_ajustes_pagos_de_tarjeta_aportes_y_traslados_no_mueven_la_tasa():
    a1, a2 = _cuenta("Ahorros"), _cuenta("Nequi")
    _mov(a1, "Sueldo Empresa", 1_000_000, "income", "Sueldo", _f(A, 1))
    _mov(a1, "Mercado Éxito", 100_000, "expense", "Comida", _f(A, 4))
    _mov(a1, "Ajuste de saldo", 777_000, "income", "Ajuste de saldo", _f(A, 8))
    _mov(a1, "Pago tarjeta Visa", 500_000, "expense", "Otros", _f(A, 9))
    _mov(a1, "Aporte a meta Viaje", 200_000, "expense", "Aporte a meta", _f(A, 10))
    r = client.post("/movimientos/transferencia", json={"cuenta_origen_id": a1, "cuenta_destino_id": a2, "monto": 300_000, "fecha": _f(A, 11)})
    assert r.status_code == 200, r.text
    d = _resumen(**_mes(A))
    assert (d["ingresos"], d["gastos"], d["tasa_ahorro"]) == (1_000_000, 100_000, 90.0)
    assert d["fuentes"]["total"] == 1_000_000
    assert {p["con_datos"] for p in d["flujo"]["puntos"] if p["desde"] in (_f(A, 8)[:10], _f(A, 9)[:10], _f(A, 11)[:10])} <= {False}
    fuera = client.get("/informes/no-se-cuenta", params=_mes(A)).json()
    assert fuera["cantidad"] >= 4                                    # lo que se dejó fuera se puede ver y verificar


def test_periodo_parcial_se_compara_con_el_mismo_tramo_del_mes_anterior():
    c = _cuenta()
    _mov(c, "Éxito 1", 50_000, "expense", "Comida", _f(B, 3))
    _mov(c, "Éxito 2", 400_000, "expense", "Comida", _f(B, 20))      # fuera del tramo 1-10
    _mov(c, "Éxito 3", 100_000, "expense", "Comida", _f(A, 3))
    _mov(c, "Éxito 4", 999_000, "expense", "Comida", _f(A, 25))      # fuera del tramo 1-10
    d = _resumen(periodo="rango", desde=_f(A, 1)[:10], hasta=_f(A, 10)[:10])
    assert d["gastos"] == 100_000
    assert d["anterior"]["gastos"] == 50_000                          # no los 450.000 del mes completo
    assert d["variacion"]["gastos_pct"] == 100.0
    assert d["anterior"]["desde"] == _f(B, 1)[:10] and d["anterior"]["hasta"] == _f(B, 10)[:10]
    assert d["en_curso"] is False


def test_rango_que_no_es_un_mes_se_compara_con_el_tramo_inmediatamente_anterior_de_igual_largo():
    c = _cuenta()
    _mov(c, "Cena", 80_000, "expense", "Ocio", _f(A, 20))
    _mov(c, "Cine", 20_000, "expense", "Ocio", _f(A, 12))
    d = _resumen(periodo="rango", desde=_f(A, 15)[:10], hasta=_f(A, 24)[:10])                # 10 días
    assert d["gastos"] == 80_000
    assert d["anterior"]["desde"] == _f(A, 5)[:10] and d["anterior"]["hasta"] == _f(A, 14)[:10]
    assert d["anterior"]["gastos"] == 20_000                                                  # el cine del día 12


def test_el_mes_en_curso_se_marca_y_no_inventa_cifras_de_dias_futuros():
    c = _cuenta()
    hoy = ahora_co()
    _mov(c, "Compra de hoy", 10_000, "expense", "Otros", hoy.replace(hour=9, minute=0).isoformat())
    d = _resumen(periodo="este_mes")
    assert d["en_curso"] is True and d["hasta"] == hoy.date().isoformat()
    assert all(p["hasta"] <= hoy.date().isoformat() for p in d["flujo"]["puntos"])             # ningún tramo en el futuro


# ═══ 2. PRESUPUESTO VS GASTO REAL ════════════════════════════════════════════════════════════
def _presupuesto(categoria, limite, **extra):
    r = client.post("/presupuestos", json={"categoria": categoria, "limite": limite, "periodo": "monthly", "alerta_pct": 80, **extra})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_presupuesto_mes_completo_varios_meses_y_categoria_sin_presupuesto():
    c = _cuenta()
    _presupuesto("Comida", 300_000)
    _mov(c, "Éxito A", 200_000, "expense", "Comida", _f(A, 5))
    _mov(c, "Éxito B", 500_000, "expense", "Comida", _f(B, 5))
    _mov(c, "Cine", 70_000, "expense", "Ocio", _f(A, 6))                                       # sin presupuesto
    uno = _resumen(**_mes(A))["presupuesto"]
    assert uno["meses_equivalentes"] == 1.0
    assert (uno["categorias"][0]["presupuesto"], uno["categorias"][0]["gastado"], uno["categorias"][0]["estado"]) == (300_000, 200_000, "dentro")
    assert uno["gasto_sin_presupuesto"] == 70_000 and uno["disponible_total"] == 100_000
    dos = _resumen(periodo="rango", desde=_f(B, 1)[:10], hasta=_f(A, calendar.monthrange(A[0], A[1])[1])[:10])["presupuesto"]
    assert dos["meses_equivalentes"] == 2.0
    assert (dos["presupuesto_total"], dos["gastado_total"]) == (600_000, 700_000)             # 2 límites; 200k + 500k
    assert dos["categorias"][0]["estado"] == "excedido" and dos["categorias"][0]["pct"] == pytest.approx(116.7, abs=0.1)


def test_presupuestos_duplicados_en_una_categoria_no_cuentan_el_gasto_dos_veces():
    c = _cuenta()
    _presupuesto("Comida", 100_000)
    _presupuesto("Comida", 50_000)                                                             # la base no lo impide
    _mov(c, "Éxito", 120_000, "expense", "Comida", _f(A, 5))
    p = _resumen(**_mes(A))["presupuesto"]
    assert len(p["categorias"]) == 1
    assert (p["presupuesto_total"], p["gastado_total"], p["pct_total"]) == (150_000, 120_000, 80.0)
    assert p["categorias"][0]["estado"] == "cerca"                                             # 80 % = su alerta


def test_presupuesto_creado_o_cambiado_hoy_se_aplica_con_su_limite_actual_a_todo_el_periodo():
    """LIMITACIÓN CONOCIDA y documentada: el presupuesto no guarda historial (ni fecha de creación ni cambios de límite),
    así que un periodo pasado se mide con el límite VIGENTE. Esta prueba fija ese comportamiento para que un cambio
    futuro sea consciente."""
    c = _cuenta()
    pid = _presupuesto("Comida", 100_000)
    _mov(c, "Éxito", 90_000, "expense", "Comida", _f(A, 5))
    assert _resumen(**_mes(A))["presupuesto"]["categorias"][0]["estado"] == "cerca"
    client.delete(f"/presupuestos/{pid}")
    _presupuesto("Comida", 500_000)                                                            # «subí el límite»
    cat = _resumen(**_mes(A))["presupuesto"]["categorias"][0]
    assert (cat["presupuesto"], cat["estado"]) == (500_000, "dentro")                          # el mes pasado se reevalúa con 500.000


def test_sobres_manuales_solo_cuentan_en_el_mes_en_curso():
    _cuenta()
    origen = _presupuesto("Transporte", 100_000)
    destino = _presupuesto("Comida", 300_000)
    r = client.post("/presupuestos/mover-sobre", json={"presupuesto_origen_id": origen, "presupuesto_destino_id": destino, "monto": 30_000})
    assert r.status_code == 200, r.text
    hoy = ahora_co()
    fr = hoy.day / calendar.monthrange(hoy.year, hoy.month)[1]
    actual = {c["categoria"]: c for c in _resumen(periodo="este_mes")["presupuesto"]["categorias"]}
    assert actual["Comida"]["presupuesto"] == round(300_000 * fr + 30_000)
    assert actual["Transporte"]["presupuesto"] == round(100_000 * fr - 30_000)
    pasado = {c["categoria"]: c for c in _resumen(**_mes(A))["presupuesto"]["categorias"]}
    assert (pasado["Comida"]["presupuesto"], pasado["Transporte"]["presupuesto"]) == (300_000, 100_000)   # sin el sobre


def test_sin_presupuestos_no_hay_barras_ni_porcentajes():
    c = _cuenta()
    _mov(c, "Éxito", 10_000, "expense", "Comida", _f(A, 5))
    p = _resumen(**_mes(A))["presupuesto"]
    assert p["hay_presupuestos"] is False and p["categorias"] == [] and p["pct_total"] is None
    assert p["gasto_sin_presupuesto"] == 10_000


# ═══ 4. HALLAZGOS Y GRÁFICOS SIN DATOS ═══════════════════════════════════════════════════════
def test_usuario_nuevo_sin_nada_no_recibe_conclusiones():
    _cuenta()
    d = _resumen(periodo="este_mes")
    assert d["hay_datos"] is False and d["hallazgos"] == []
    assert d["flujo"]["hay_datos"] is False and d["flujo"]["mejor"] is None
    assert d["fuentes"] == {"total": 0, "fuentes": [], "otras": None, "hay_datos": False}
    assert d["tasa_serie"]["promedio"] is None and d["presupuesto"]["hay_presupuestos"] is False
    assert d["tasa_ahorro"] is None and d["variacion"]["gastos_pct"] is None


def test_sin_periodo_anterior_no_se_afirman_cambios():
    c = _cuenta()
    _mov(c, "Sueldo Empresa", 1_000_000, "income", "Sueldo", _f(A, 1))
    _mov(c, "Éxito", 100_000, "expense", "Comida", _f(A, 5))
    d = _resumen(**_mes(A))                                           # el mes anterior no tiene nada
    assert d["variacion"] == {"ingresos_pct": None, "gastos_pct": None, "balance_pct": None, "tasa_ahorro_puntos": None}
    ids = _ids(d)
    assert not ids & {"gastos", "tasa", "sube_categoria"}             # ninguna comparación sin base
    assert "flujo" in ids


def test_un_mes_con_un_solo_movimiento_no_arma_tendencias():
    c = _cuenta()
    _mov(c, "Sueldo Empresa", 1_000_000, "income", "Sueldo", _f(A, 1))
    d = _resumen(**_mes(A))
    assert d["tasa_ahorro"] == 100.0 and d["tasa_serie"]["meses_con_tasa"] == 1
    assert d["tasa_serie"]["mejor"]["mes"] == d["tasa_serie"]["peor"]["mes"] == A[2]


# ═══ 5. ENLACES A MOVIMIENTOS: lo que el resumen cuenta coincide con lo que se lista ═════════
def test_el_detalle_de_una_fuente_suma_lo_mismo_que_el_resumen():
    c = _cuenta()
    _mov(c, "Sueldo Empresa", 600_000, "income", "Sueldo", _f(A, 1))
    _mov(c, "Sueldo Empresa", 400_000, "income", "Sueldo", _f(A, 15))
    _mov(c, "Venta usados", 90_000, "income", "Ventas", _f(A, 9))
    d = _resumen(**_mes(A))
    f = d["fuentes"]["fuentes"][0]
    det = client.get("/informes/gasto/movimientos", params={**_mes(A), "tipo": "ingreso", "fuente": f["clave"]}).json()
    assert det["total"] == f["monto"] == 1_000_000 and det["cantidad"] == f["num"] == 2
    suma = sum(x["monto"] for x in d["fuentes"]["fuentes"]) + (d["fuentes"]["otras"] or {"monto": 0})["monto"]
    assert suma == d["ingresos"] == 1_090_000


def test_el_detalle_de_una_categoria_del_presupuesto_suma_lo_mismo_que_el_resumen():
    c = _cuenta()
    _presupuesto("Comida", 300_000)
    _mov(c, "Éxito 1", 120_000, "expense", "Comida", _f(A, 3))
    _mov(c, "Éxito 2", 80_000, "expense", "Comida", _f(A, 28))
    cat = _resumen(**_mes(A))["presupuesto"]["categorias"][0]
    det = client.get("/informes/gasto/movimientos", params={**_mes(A), "categoria": "Comida"}).json()
    assert det["total"] == cat["gastado"] == 200_000


def test_el_listado_de_movimientos_con_los_mismos_filtros_trae_lo_que_el_resumen_cuenta():
    """Los enlaces del resumen abren /movimientos?desde=&hasta=&tipo=… : esos filtros deben dar las mismas cifras."""
    c = _cuenta()
    _mov(c, "Sueldo Empresa", 1_000_000, "income", "Sueldo", _f(A, 1))
    _mov(c, "Éxito", 150_000, "expense", "Comida", _f(A, 10))
    _mov(c, "Fuera de rango", 999_000, "expense", "Comida", _f(B, 28))
    d = _resumen(periodo="rango", desde=_f(A, 1)[:10], hasta=_f(A, 28)[:10])
    lista = client.get("/movimientos", params={"desde": d["desde"], "hasta": d["hasta"], "limite": 500})
    assert lista.status_code == 200, lista.text
    filas = lista.json()
    gastos = sum(m["monto"] for m in filas if m["tipo"] == "expense")
    ingresos = sum(m["monto"] for m in filas if m["tipo"] == "income")
    assert (ingresos, gastos) == (d["ingresos"], d["gastos"]) == (1_000_000, 150_000)


# ═══ SEGURIDAD ═══════════════════════════════════════════════════════════════════════════════
def test_cada_persona_ve_solo_sus_datos():
    uid_a = f"val-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid_a, email="a@test.com", nombre="A")
    c = _cuenta()
    _mov(c, "Sueldo Secreto SAS", 5_000_000, "income", "Sueldo", _f(A, 1))
    _mov(c, "Compra privada", 123_000, "expense", "Salud", _f(A, 2))
    _presupuesto("Salud", 50_000)
    propio = _resumen(**_mes(A))
    assert propio["ingresos"] == 5_000_000 and propio["presupuesto"]["hay_presupuestos"]
    uid_b = f"val-{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid_b, email="b@test.com", nombre="B")
    ajeno = _resumen(**_mes(A))
    assert (ajeno["ingresos"], ajeno["gastos"]) == (0, 0)
    assert ajeno["fuentes"]["fuentes"] == [] and ajeno["presupuesto"]["hay_presupuestos"] is False and ajeno["hallazgos"] == []
    assert "Secreto" not in str(ajeno) and "privada" not in str(ajeno)
    det = client.get("/informes/gasto/movimientos", params={**_mes(A), "tipo": "ingreso", "fuente": "sueldo secreto sas"}).json()
    assert det["cantidad"] == 0 and det["movimientos"] == []
    app.dependency_overrides.pop(get_current_user, None)


def test_sin_sesion_no_se_responde():
    app.dependency_overrides.pop(get_current_user, None)
    for ruta in ("/informes/resumen", "/informes/gasto/movimientos?categoria=Comida&tipo=ingreso"):
        assert client.get(ruta).status_code in (401, 403)


@pytest.mark.parametrize("params", [
    {"periodo": "'; DROP TABLE movimientos; --"},
    {"periodo": "mes", "mes": "2026-13"},
    {"periodo": "mes", "mes": "../../etc/passwd"},
    {"periodo": "rango", "desde": "ayer", "hasta": "hoy"},
    {"periodo": "rango", "desde": "2026-05-10", "hasta": "2026-05-01"},
    {"periodo": "rango", "desde": "1900-01-01", "hasta": "2026-05-01"},     # más de 5 años
    {"periodo": "rango", "desde": "2026-05-01"},
    {"agrupar": "hora"},
    {"agrupar": "dia; DROP"},
])
def test_parametros_invalidos_dan_422_nunca_500(usuario, params):
    r = client.get("/informes/resumen", params=params)
    assert r.status_code == 422, (params, r.status_code, r.text[:200])
    assert "Traceback" not in r.text and "sqlalchemy" not in r.text.lower()


@pytest.mark.parametrize("valor", ["x" * 5000, "'; DROP TABLE movimientos; --", "%00", "<script>alert(1)</script>", "ñandú 🐍"])
def test_texto_libre_en_fuente_y_categoria_es_inofensivo(usuario, valor):
    _cuenta()
    for extra in ({"fuente": valor, "tipo": "ingreso"}, {"categoria": valor}, {"comercio": valor}):
        r = client.get("/informes/gasto/movimientos", params={"periodo": "este_mes", **extra})
        assert r.status_code == 200, (extra.keys(), r.status_code)
        assert r.json()["cantidad"] == 0
    assert client.get("/informes/gasto/movimientos", params={"periodo": "este_mes", "tipo": "x", "fuente": "a"}).status_code == 422


def test_el_resumen_tiene_limite_de_uso_por_persona(usuario, monkeypatch):
    monkeypatch.setattr(router_informes, "LIMITE_RESUMEN_POR_MINUTO", 3)
    for _ in range(3):
        assert client.get("/informes/resumen", params={"periodo": "este_mes"}).status_code == 200
    r = client.get("/informes/resumen", params={"periodo": "este_mes"})
    assert r.status_code == 429 and "Retry-After" in r.headers
    otro = f"val-{uuid.uuid4().hex[:8]}"                                   # el límite es POR persona
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=otro, email="o@test.com", nombre="O")
    assert client.get("/informes/resumen", params={"periodo": "este_mes"}).status_code == 200


# ═══ COMPATIBILIDAD con el frontend/backend anteriores ═══════════════════════════════════════
def test_los_endpoints_de_antes_responden_igual(usuario):
    c = _cuenta()
    _mov(c, "Éxito", 100_000, "expense", "Comida", _f(A, 5))
    _mov(c, "Sueldo", 900_000, "income", "Sueldo", _f(A, 1))
    gasto = client.get("/informes/gasto", params=_mes(A)).json()
    assert gasto["total"] == 100_000 and gasto["ingresos"] == 900_000
    antiguo = client.get("/informes/gasto/movimientos", params={**_mes(A), "categoria": "Comida"}).json()      # sin tipo ni fuente
    assert antiguo["total"] == 100_000
    assert set(antiguo) >= {"categoria", "comercio", "etiqueta", "total", "cantidad", "truncado", "movimientos"}
    ig = client.get("/reportes/ingresos-gastos", params=_mes(A)).json()
    nuevo = _resumen(**_mes(A))
    for k in ("ingresos", "gastos", "balance", "tasa_ahorro", "variacion", "anterior", "meses"):
        assert nuevo[k] == ig[k], k                                        # el resumen y el informe de siempre cuentan IGUAL
    assert set(nuevo) >= set(ig)                                           # el resumen es un superconjunto: nada se quitó
