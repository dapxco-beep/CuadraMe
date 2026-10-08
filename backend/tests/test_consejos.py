"""Motor de consejos: reglas puras con casos sintéticos (números hechos a mano) y el endpoint."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'consejos.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import consejos as c  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

HOY = datetime(2026, 10, 15, 12, 0)
_n = [0]


def mov(dias_atras, monto, desc="Compra", cat="Comida", tipo="expense", cuenta="c1", **extra):
    _n[0] += 1
    return {"id": f"m{_n[0]}", "cuenta_id": cuenta, "fecha": HOY - timedelta(days=dias_atras), "descripcion": desc,
            "categoria": cat, "tipo": tipo, "monto": monto, "fuente": "manual", "cat_confirmada": True, **extra}


def datos(**kw):
    base = {"cuentas": [], "movimientos": [], "movimientos_neutros": [], "presupuestos": [], "metas": [],
            "deudas": [], "recurrentes": []}
    base.update(kw)
    return base


def tipos(d):
    return {x["tipo"]: x for x in c.generar(d, HOY)}


def tarjeta(**kw):
    t = {"id": "t1", "nombre": "Visa", "tipo": "credito", "saldo": -1_000_000, "cupo_total": 2_000_000, "cupo_usado": 1_000_000,
         "utilizacion_pct": 50.0, "pago_minimo": 100_000, "interes_estimado": 25_000, "dias_para_pago": 20,
         "dias_para_corte": 10, "proximo_pago": "2026-11-04", "proximo_corte": "2026-10-25",
         "falta_para_evitar_intereses": None}
    t.update(kw)
    return t


# ── estructura ────────────────────────────────────────────────────────────────────────
def test_sin_datos_no_hay_consejos():
    assert c.generar(datos(), HOY) == []


def test_cada_consejo_tiene_la_forma_completa_e_ids_unicos():
    d = datos(cuentas=[tarjeta(), {"id": "c1", "nombre": "Banco", "tipo": "ahorro", "saldo": 100_000}],
              movimientos=[mov(d, 300_000, cat="Mercado") for d in (5, 20)] + [mov(40, 100_000, cat="Mercado")])
    lista = c.generar(d, HOY)
    assert lista
    for x in lista:
        assert {"id", "tipo", "prioridad", "titulo", "texto", "cifra", "accion", "aprende"} <= set(x)
        assert x["accion"]["ruta"].startswith("/") and x["accion"]["texto"]
        assert x["prioridad"] in (1, 2, 3)
    assert len({x["id"] for x in lista}) == len(lista)
    assert all(x["aprende"] in c.LECCIONES for x in lista if x["aprende"])
    assert [x["prioridad"] for x in lista] == sorted(x["prioridad"] for x in lista)


def test_los_ids_son_estables_entre_llamadas():
    d = datos(cuentas=[tarjeta()])
    assert [x["id"] for x in c.generar(d, HOY)] == [x["id"] for x in c.generar(d, HOY)]


def test_ningun_texto_promete_ni_recomienda_inversion():
    d = datos(cuentas=[tarjeta(), {"id": "c1", "nombre": "B", "tipo": "ahorro", "saldo": 5_000_000}],
              movimientos=[mov(3, 200_000, tipo="income", cat="Salario")],
              deudas=[{"id": "d1", "nombre": "Libre", "saldo": 5e6, "tasa_mensual": 2.2}, {"id": "d2", "nombre": "Moto", "saldo": 1e6, "tasa_mensual": 1.0}])
    for x in c.generar(d, HOY):
        t = (x["titulo"] + x["texto"]).lower()
        assert not any(p in t for p in ("garantiz", "rentabilidad", "invierte en", "compra acciones", "cdt"))


# ── categoría que sube ────────────────────────────────────────────────────────────────
def test_categoria_sube_mas_de_30_pct():
    d = datos(movimientos=[mov(10, 300_000, cat="Restaurantes"), mov(45, 200_000, cat="Restaurantes")])
    x = tipos(d)["categoria_sube"]
    assert x["titulo"] == "Restaurantes: gastas 50 % más"
    assert x["cifra"] == "+$100.000" and "$300.000" in x["texto"] and "$200.000" in x["texto"]
    assert x["id"] == "categoria-sube:Restaurantes:2026-10"


def test_categoria_sube_no_avisa_con_aumento_pequeno_o_poca_plata():
    # +20 % (por debajo del umbral) y otra categoría con diferencia de solo $30.000
    d = datos(movimientos=[mov(10, 240_000, cat="A"), mov(45, 200_000, cat="A"), mov(10, 40_000, cat="B"), mov(45, 10_000, cat="B")])
    assert "categoria_sube" not in tipos(d)


# ── gastos hormiga ────────────────────────────────────────────────────────────────────
def test_gastos_hormiga_repetidos():
    d = datos(movimientos=[mov(i, 8_000, desc=f"Juan Valdez #{i}", cat="Café") for i in (1, 3, 5, 8, 12)])
    x = tipos(d)["gastos_hormiga"]
    assert x["cifra"] == "$40.000" and "5 compras" in x["texto"] and "$480.000" in x["texto"]


def test_hormiga_ignora_pocas_veces_o_compras_grandes():
    pocas = datos(movimientos=[mov(i, 9_000, desc="Rappi") for i in (1, 2, 3)])
    grandes = datos(movimientos=[mov(i, 90_000, desc="Rappi") for i in (1, 2, 3, 4, 5)])
    assert "gastos_hormiga" not in tipos(pocas) and "gastos_hormiga" not in tipos(grandes)


# ── tarjeta de crédito ────────────────────────────────────────────────────────────────
def test_pago_solo_el_minimo():
    t = tarjeta(ultimo_pago={"monto": 100_000, "fecha": HOY - timedelta(days=5)})
    x = tipos(datos(cuentas=[t]))["solo_minimo"]
    assert x["prioridad"] == 1 and "$1.000.000" in x["texto"] and "$25.000" in x["texto"]
    t2 = tarjeta(ultimo_pago={"monto": 900_000, "fecha": HOY - timedelta(days=5)})
    assert "solo_minimo" not in tipos(datos(cuentas=[t2]))
    t3 = tarjeta(ultimo_pago={"monto": 100_000, "fecha": HOY - timedelta(days=60)})  # pago muy viejo
    assert "solo_minimo" not in tipos(datos(cuentas=[t3]))


def test_utilizacion_de_cupo_sobre_30():
    x = tipos(datos(cuentas=[tarjeta(utilizacion_pct=45.0)]))["utilizacion"]
    assert x["cifra"] == "45 %" and x["prioridad"] == 2 and "$1.000.000" in x["texto"] and "$2.000.000" in x["texto"]
    assert tipos(datos(cuentas=[tarjeta(utilizacion_pct=75.0)]))["utilizacion"]["prioridad"] == 1
    assert "utilizacion" not in tipos(datos(cuentas=[tarjeta(utilizacion_pct=20.0)]))
    assert "utilizacion" not in tipos(datos(cuentas=[tarjeta(utilizacion_pct=None)]))


def test_fechas_de_pago_y_corte_proximas():
    t = tarjeta(dias_para_pago=2, dias_para_corte=1, falta_para_evitar_intereses=750_000, proximo_pago="2026-10-17", proximo_corte="2026-10-16")
    r = tipos(datos(cuentas=[t]))
    assert r["fecha_pago"]["titulo"] == "Pagas Visa en 2 días" and r["fecha_pago"]["cifra"] == "$750.000"
    assert r["fecha_pago"]["prioridad"] == 1
    assert r["fecha_corte"]["titulo"] == "Visa corta mañana"
    lejos = tipos(datos(cuentas=[tarjeta(dias_para_pago=12, dias_para_corte=9)]))
    assert "fecha_pago" not in lejos and "fecha_corte" not in lejos


def test_debito_vs_credito_cuando_hay_compras_en_tarjeta():
    d = datos(cuentas=[tarjeta()], movimientos=[mov(4, 120_000, cuenta="t1"), mov(9, 80_000, cuenta="t1"), mov(3, 50_000, cuenta="c1")])
    x = tipos(d)["debito_vs_credito"]
    assert x["cifra"] == "$200.000" and x["accion"]["ruta"] == "/aprende"
    assert "debito_vs_credito" not in tipos(datos(movimientos=[mov(4, 120_000)]))  # sin tarjeta


# ── fondo de emergencia, ahorro, presupuesto ──────────────────────────────────────────
def test_fondo_de_emergencia_calculado_de_sus_datos():
    # 3 meses de historial, $600.000 de gasto cada mes => $1.800.000 en 90 días => $600.000/mes
    movs = [mov(5, 600_000), mov(35, 600_000), mov(90, 600_000)]
    cuentas = [{"id": "c1", "nombre": "B", "tipo": "ahorro", "saldo": 300_000}]
    x = tipos(datos(cuentas=cuentas, movimientos=movs))["fondo_emergencia"]
    assert x["cifra"] == "0.5 meses" and "$600.000" in x["texto"] and "$1.800.000" in x["texto"]
    rico = [{"id": "c1", "nombre": "B", "tipo": "ahorro", "saldo": 2_000_000}]
    assert "fondo_emergencia" not in tipos(datos(cuentas=rico, movimientos=movs))
    assert "fondo_emergencia" not in tipos(datos(cuentas=cuentas))  # sin gastos no hay base de cálculo


def test_la_tarjeta_y_la_inversion_no_cuentan_como_fondo():
    movs = [mov(5, 600_000), mov(35, 600_000), mov(90, 600_000)]
    cuentas = [{"id": "c1", "nombre": "Fondo", "tipo": "inversion", "saldo": 9_000_000}]
    assert "fondo_emergencia" in tipos(datos(cuentas=cuentas, movimientos=movs))


def test_ahorro_sin_meta():
    cuentas = [{"id": "c1", "nombre": "B", "tipo": "ahorro", "saldo": 2_000_000}]
    assert tipos(datos(cuentas=cuentas))["ahorro_sin_meta"]["cifra"] == "$2.000.000"
    assert "ahorro_sin_meta" not in tipos(datos(cuentas=cuentas, metas=[{"nombre": "Viaje", "activa": True}]))
    assert "ahorro_sin_meta" not in tipos(datos(cuentas=[{"id": "c1", "nombre": "B", "tipo": "ahorro", "saldo": 100_000}]))


def test_presupuesto_sin_definir():
    movs = [mov(5, 150_000)]
    assert tipos(datos(movimientos=movs))["sin_presupuesto"]["cifra"] == "$150.000"
    assert "sin_presupuesto" not in tipos(datos(movimientos=movs, presupuestos=[{"categoria": "Comida", "limite": 1}]))
    assert "sin_presupuesto" not in tipos(datos(movimientos=[mov(5, 20_000)]))


# ── deudas ────────────────────────────────────────────────────────────────────────────
def test_deudas_avalancha_vs_bola_de_nieve():
    ds = [{"id": "d1", "nombre": "Libre inversión", "saldo": 8_000_000, "tasa_mensual": 2.0},
          {"id": "d2", "nombre": "Celular", "saldo": 1_000_000, "tasa_mensual": 1.0}]
    x = tipos(datos(deudas=ds))["deudas"]
    assert "Avalancha" in x["texto"] and "Libre inversión" in x["texto"] and "Bola de nieve" in x["texto"] and "Celular" in x["texto"]
    assert x["id"] == "deudas-orden:d1"
    assert "deudas" not in tipos(datos(deudas=[ds[0]]))  # 2 % mensual = 26,8 % EA (<28): no es "cara"
    cara = tipos(datos(deudas=[{"id": "d9", "nombre": "Tarjeta tienda", "saldo": 1e6, "tasa_mensual": 2.3}]))["deudas"]
    assert cara["id"] == "deuda-cara:d9" and "31 %" in cara["cifra"]
    assert "deudas" not in tipos(datos(deudas=[{"id": "d9", "nombre": "Hipoteca", "saldo": 1e6, "tasa_mensual": 1.0}]))
    assert "deudas" not in tipos(datos(deudas=[{"id": "d9", "nombre": "Pagada", "saldo": 0, "tasa_mensual": 3.0}]))


# ── suscripciones, ingreso, categorías ────────────────────────────────────────────────
def test_suscripcion_detectada_y_no_si_ya_esta_registrada():
    movs = [mov(5, 29_900, desc="Netflix", cat="Entretenimiento"), mov(35, 29_900, desc="Netflix", cat="Entretenimiento")]
    x = tipos(datos(movimientos=movs))["suscripciones"]
    assert x["cifra"] == "$29.900/mes" and "Netflix" in x["texto"]
    assert "suscripciones" not in tipos(datos(movimientos=movs, recurrentes=["Netflix"]))


def test_ingreso_sin_repartir_y_si_ya_aporto_a_una_meta():
    ing = mov(2, 2_000_000, desc="Nómina", cat="Salario", tipo="income")
    x = tipos(datos(movimientos=[ing]))["ingreso_sin_repartir"]
    assert "$1.000.000" in x["texto"] and "$600.000" in x["texto"] and "$400.000" in x["texto"]
    aporte = mov(1, 300_000, tipo="transfer", fuente="aporte_meta")
    assert "ingreso_sin_repartir" not in tipos(datos(movimientos=[ing], movimientos_neutros=[aporte]))
    assert "ingreso_sin_repartir" not in tipos(datos(movimientos=[mov(20, 2_000_000, tipo="income")]))  # ya pasó una semana


def test_movimientos_sin_categoria():
    movs = [mov(i, 10_000, cat="Otros") for i in range(1, 6)]
    assert tipos(datos(movimientos=movs))["sin_categorizar"]["cifra"] == "5 movimientos"
    assert "sin_categorizar" not in tipos(datos(movimientos=movs[:4]))
    sin_confirmar = [mov(i, 10_000, cat="Comida", cat_confirmada=False) for i in range(1, 6)]
    assert "sin_categorizar" in tipos(datos(movimientos=sin_confirmar))


# ── endpoint ──────────────────────────────────────────────────────────────────────────
@pytest.fixture
def cliente():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="cons-1", email="cons@test.com", nombre="Cons")
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_endpoint_sin_datos_devuelve_aviso_y_lista_vacia(cliente):
    r = cliente.get("/consejos")
    assert r.status_code == 200
    assert r.json() == {"aviso": "Orientación educativa, no es asesoría financiera.", "consejos": []}


def test_endpoint_con_datos_reales_de_base(cliente):
    from app.database import SessionLocal
    from app.derechos_titular import borrar_todo

    cuenta = cliente.post("/cuentas", json={"nombre": "Banco", "saldo": 2_000_000}).json()
    cliente.post("/cuentas", json={"nombre": "Mi Visa", "tipo": "credito", "saldo": -1_500_000, "cupo_total": 2_000_000})
    cliente.post("/movimientos", json={"cuenta_id": cuenta["id"], "descripcion": "Mercado", "monto": 150_000, "tipo": "expense", "categoria": "Mercado"})
    try:
        r = cliente.get("/consejos")
        assert r.status_code == 200
        tp = {x["tipo"] for x in r.json()["consejos"]}
        assert {"utilizacion", "sin_presupuesto", "ahorro_sin_meta"} <= tp
        assert all(x["id"] and x["accion"]["ruta"].startswith("/") for x in r.json()["consejos"])
    finally:
        db = SessionLocal()
        try:
            borrar_todo(db, "cons-1", "cons@test.com")
        finally:
            db.close()


def test_endpoint_exige_sesion():
    app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(app).get("/consejos").status_code == 401
