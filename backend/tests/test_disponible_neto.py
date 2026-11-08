"""GET /cuentas/resumen: «Tienes disponible» = ahorros y efectivo menos lo que se debe en tarjetas; las inversiones
(CDT, fondos) van aparte y no cuentan como plata para gastar. Números inventados."""
import os
import tempfile
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'disponible_neto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta  # noqa: E402

client = TestClient(app)


@pytest.fixture
def usuario():
    u = UsuarioActual(id=f"dn-{uuid.uuid4().hex[:8]}", email="dn@test.com", nombre="Dn")
    app.dependency_overrides[get_current_user] = lambda: u
    yield u
    app.dependency_overrides.pop(get_current_user, None)


def _cuentas(u, filas):
    db = SessionLocal()
    for nombre, tipo, saldo in filas:
        db.add(Cuenta(usuario_id=u.id, nombre=nombre, tipo=tipo, saldo=saldo, moneda="COP"))
    db.commit()
    db.close()


def test_el_disponible_no_cuenta_inversiones_y_resta_la_tarjeta(usuario):
    _cuentas(usuario, [("Banco", "ahorro", 4_000_000), ("Efectivo", "efectivo", 500_000),
                       ("CDT", "inversion", 5_000_000), ("Visa", "credito", -800_000)])
    r = client.get("/cuentas/resumen").json()
    assert r["liquido_cop"] == 4_500_000
    assert r["inversiones_cop"] == 5_000_000
    assert r["deudas_tarjeta_cop"] == 800_000
    assert r["disponible_neto_cop"] == 3_700_000  # 4.500.000 - 800.000
    assert r["disponible_cop"] == 9_500_000       # campo histórico: todo lo que no es tarjeta (no cambia)
    assert r["total_cop"] == 8_700_000            # saldo total = lo que cuadra con Cuentas y Patrimonio


def test_sin_inversiones_ni_tarjetas_el_neto_es_el_liquido(usuario):
    _cuentas(usuario, [("Banco", "ahorro", 1_000_000)])
    r = client.get("/cuentas/resumen").json()
    assert r["disponible_neto_cop"] == r["liquido_cop"] == 1_000_000
    assert r["inversiones_cop"] == 0


def test_gastable_por_dia_no_cuenta_las_inversiones(usuario):
    _cuentas(usuario, [("Banco", "ahorro", 4_000_000), ("CDT", "inversion", 5_000_000), ("Visa", "credito", -800_000)])
    b = client.get("/presupuestos/en-mi-bolsillo").json()
    assert b["saldo_total"] == 8_200_000                    # incluye el CDT y resta la tarjeta (como antes)
    assert b["inversiones"] == 5_000_000
    assert b["disponible_liquido"] == b["disponible_real"] - 5_000_000
    assert b["disponible_liquido_por_dia"] == round(b["disponible_liquido"] / b["dias_restantes_mes"])
    assert b["disponible_liquido_por_dia"] < b["disponible_real_por_dia"]


def test_puntaje_de_salud_no_alarma_con_un_mes_sin_movimientos():
    from app.reportes import calc_health_score
    vacio = calc_health_score(0, 0, 0, 0)
    assert not any("superan" in t or "Burn rate" in t for t in vacio["tips"])
    assert "Necesitas registrar más transacciones" in vacio["tips"]
    solo_gastos = calc_health_score(0, 50_000, -50_000, 3)
    assert "Este mes aún no registras ingresos" in solo_gastos["tips"]
    real = calc_health_score(1_000_000, 1_200_000, -200_000, 30)
    assert "¡Tus gastos superan tus ingresos! Revisa urgente" in real["tips"]  # con datos reales sigue avisando


def test_un_cafe_frecuente_no_es_un_pago_fijo_pero_una_suscripcion_si():
    from datetime import datetime, timedelta
    from app.deteccion import detectar_recurrentes
    base = datetime(2026, 1, 5)
    cafe = [{"id": f"c{i}", "descripcion": "Cafe del barrio", "categoria": "Comida", "tipo": "expense",
             "monto": 15_000 + (i % 3) * 200, "fecha": base + timedelta(days=(0 if i < 2 else 3 * i) + (30 if i == 1 else 0)),
             "cuenta_id": "x"} for i in range(20)]
    # una sola pareja casualmente a 30 días y el resto compras seguidas
    netflix = [{"id": f"n{i}", "descripcion": "Netflix", "categoria": "Suscripciones", "tipo": "expense", "monto": 29_900,
                "fecha": base + timedelta(days=30 * i), "cuenta_id": "x"} for i in range(5)]
    nombres = [s["descripcion"] for s in detectar_recurrentes(cafe + netflix)]
    assert "Netflix" in nombres
    assert "Cafe del barrio" not in nombres


def test_proyeccion_sin_gastos_dice_que_viene_de_meses_anteriores():
    from app.planificacion import mensaje_proyeccion
    base = {"categoria": "Comida", "pct_usado": 0, "dias_restantes": 24, "gastado": 0, "limite": 1_100_000,
            "proyectado": 645_824, "estado": "bien"}
    m = mensaje_proyeccion(base)
    assert "Sin gastos en Comida este mes" in m and "meses anteriores" in m and "Llevas 0%" not in m
    assert "por encima del límite" in mensaje_proyeccion({**base, "proyectado": 1_300_000, "estado": "en_riesgo"})
    con_gasto = mensaje_proyeccion({**base, "gastado": 100_000, "pct_usado": 9})
    assert con_gasto.startswith("Vas bien en Comida")  # con gastos reales, el mensaje de siempre
