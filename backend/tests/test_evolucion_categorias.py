"""Evolución del gasto por categoría (GET /informes/evolucion-categorias): suma exacta contra los reportes, sin
traslados ni pagos de tarjeta, aislamiento entre usuarios, meses vacíos en 0, subcategorías y mes parcial. Sintético."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'evocat.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import informe as inf  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="evocat-u", email="ec@test.com", nombre="Evo Uno")
V = UsuarioActual(id="evocat-v", email="ev@test.com", nombre="Evo Dos")
ACTUAL = {"u": U}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    ACTUAL["u"] = U
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _mes_atras(n):
    return inf.sumar_meses(ahora_co().year, ahora_co().month, -n)


@pytest.fixture
def datos():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    cu = Cuenta(usuario_id=U.id, nombre="Banco evo", tipo="ahorro", saldo=0, moneda="COP")
    cu2 = Cuenta(usuario_id=U.id, nombre="Otra evo", tipo="ahorro", saldo=0, moneda="COP")
    ajena = Cuenta(usuario_id=V.id, nombre="Ajena evo", tipo="ahorro", saldo=0, moneda="COP")
    db.add_all([cu, cu2, ajena])
    db.flush()

    def mv(cuenta, usuario, tipo, monto, desc, n, cat, sub=None, dia=10):
        a, m = _mes_atras(n)
        db.add(Movimiento(usuario_id=usuario.id, cuenta_id=cuenta.id, fecha=datetime(a, m, dia, 12), descripcion=desc,
                          categoria=cat, subcategoria=sub, tipo=tipo, monto=monto, fuente="manual", notas=""))

    # Transporte: hace 3 meses 100k, hace 2 meses nada (mes vacío), hace 1 mes 300k (200k gasolina + 100k sin sub), mes actual 50k
    mv(cu, U, "expense", 100_000, "Tanqueo A", 3, "Transporte", "Gasolina")
    mv(cu, U, "expense", 200_000, "Tanqueo B", 1, "Transporte", "Gasolina")
    mv(cu, U, "expense", 100_000, "Taxi", 1, "Transporte")
    mv(cu, U, "expense", 50_000, "Bus", 0, "Transporte", "Bus")
    mv(cu, U, "expense", 80_000, "Mercado C", 1, "Mercado")
    mv(cu, U, "income", 2_000_000, "Nomina Demo", 1, "Ingresos")
    # No deben contar: pago de tarjeta y traslado propio (par exacto entre cuentas propias)
    mv(cu, U, "expense", 900_000, "Pago tarjeta de crédito", 1, "Otros")
    mv(cu, U, "expense", 400_000, "Enviaste a Ana Demo", 1, "Otros", dia=15)
    mv(cu2, U, "income", 400_000, "Recibiste de Ana Demo", 1, "Otros", dia=15)
    # De otra persona
    mv(ajena, V, "expense", 777_000, "Gasto ajeno", 1, "Transporte")
    db.commit()
    db.close()
    yield
    from app.derechos_titular import borrar_todo
    for u in (U, V):
        db = SessionLocal()
        try:
            borrar_todo(db, u.id, u.email)
        finally:
            db.close()


def _get(url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()


def test_serie_por_categoria_con_meses_vacios_en_cero(datos):
    d = _get("/informes/evolucion-categorias?meses=6")
    assert len(d["meses"]) == 6 and d["meses"][-1]["parcial"] is True and not d["meses"][-2]["parcial"]
    t = next(c for c in d["categorias"] if c["categoria"] == "Transporte")
    assert t["valores"] == [0, 0, 100_000, 0, 300_000, 50_000]
    # el promedio usa solo meses completos (el actual es parcial): (100k + 300k) / 5
    assert t["promedio"] == 80_000
    assert t["vs_anterior_pct"][4] is None and t["vs_anterior_pct"][3] == -100.0  # base 0 -> sin comparación
    assert t["resumen"]["mes"] == d["meses"][4]["mes"] and t["resumen"]["vs_promedio_pct"] == 275.0
    assert d["categorias"][0]["categoria"] == "Transporte"  # ordenadas por gasto total


def test_no_cuenta_traslados_ni_pagos_de_tarjeta_ni_ingresos(datos):
    d = _get("/informes/evolucion-categorias?meses=6")
    assert "Otros" not in [c["categoria"] for c in d["categorias"]]
    assert "Ingresos" not in [c["categoria"] for c in d["categorias"]]
    assert d["total_mensual"][4] == 300_000 + 80_000
    assert d["serie_total"]["valores"] == d["total_mensual"] and d["serie_total"]["promedio"] == (100_000 + 380_000) // 5


def test_suma_exacta_contra_el_informe_de_gasto(datos):
    d = _get("/informes/evolucion-categorias?meses=6")
    mes = d["meses"][4]["mes"]
    g = _get(f"/informes/gasto?periodo=mes&mes={mes}")
    por_cat = {c["categoria"]: c["monto"] for c in g["categorias"]}
    for c in d["categorias"]:
        if c["valores"][4]:
            assert c["valores"][4] == por_cat[c["categoria"]]
    assert d["total_mensual"][4] == g["total"]


def test_subcategorias_suman_la_categoria_y_sin_subcategoria_al_final(datos):
    d = _get("/informes/evolucion-categorias?meses=6&categoria=Transporte")
    assert d["tiene_subcategorias"] is True
    subs = d["subcategorias"]
    assert [s["subcategoria"] for s in subs] == ["Gasolina", "Bus", None]
    t = next(c for c in d["categorias"] if c["categoria"] == "Transporte")
    for i in range(6):
        assert sum(s["valores"][i] for s in subs) == t["valores"][i]
    # sin el parámetro no hay subcategorías
    assert "subcategorias" not in _get("/informes/evolucion-categorias?meses=6")


def test_aislamiento_entre_usuarios(datos):
    ACTUAL["u"] = V
    d = _get("/informes/evolucion-categorias?meses=6")
    t = next(c for c in d["categorias"] if c["categoria"] == "Transporte")
    assert t["total"] == 777_000 and [c["categoria"] for c in d["categorias"]] == ["Transporte"]
    ACTUAL["u"] = U
    assert next(c for c in _get("/informes/evolucion-categorias")["categorias"] if c["categoria"] == "Transporte")["total"] == 450_000


def test_sin_datos_y_limites(datos):
    ACTUAL["u"] = UsuarioActual(id="evocat-vacio", email="x@test.com", nombre="Vacio")
    d = _get("/informes/evolucion-categorias?meses=12")
    assert d["hay_datos"] is False and d["categorias"] == [] and len(d["meses"]) == 12 and set(d["total_mensual"]) == {0}
    assert client.get("/informes/evolucion-categorias?meses=0").status_code == 422
    assert client.get("/informes/evolucion-categorias?meses=99").status_code == 422


def test_serie_mensual_trae_tasa_y_variacion(datos):
    d = _get("/reportes/ingresos-gastos?periodo=este_mes&meses=6")
    m = d["meses"]
    assert m[4]["tasa_ahorro"] == 100.0 * (2_000_000 - 380_000) / 2_000_000
    assert m[4]["variacion"]["gastos_pct"] is None  # el mes anterior no tenía gasto
    assert m[5]["variacion"]["gastos_pct"] == round((50_000 - 380_000) / 380_000 * 100, 1)
