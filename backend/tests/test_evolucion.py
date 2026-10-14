"""
Gráfica evolutiva: GET /reportes/evolucion (ingresos, gastos y ahorro por mes o por semana).
Datos SINTÉTICOS. La agrupación sale de app/informe.py:evolucion y usa SOLO la regla única
(los traslados y pagos de tarjeta llegan como 'transfer' y no suman).
"""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'evolucion.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import informe as inf  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402

HOY = datetime(2026, 10, 14, 10, 0)


def mv(fecha, tipo, monto):
    return {"id": f"{fecha}-{tipo}-{monto}", "fecha": fecha, "tipo": tipo, "monto": monto}


def test_agrupa_por_mes_y_calcula_ahorro_y_acumulado():
    movs = [
        mv(datetime(2026, 8, 5), "income", 3_000_000), mv(datetime(2026, 8, 9), "expense", 1_000_000),
        mv(datetime(2026, 9, 3), "income", 3_000_000), mv(datetime(2026, 9, 20), "expense", 2_500_000),
        mv(datetime(2026, 10, 2), "expense", 400_000),
    ]
    r = inf.evolucion(movs, HOY, "mes", 3)
    assert [p["clave"] for p in r["puntos"]] == ["2026-08", "2026-09", "2026-10"]
    ag, sep, octu = r["puntos"]
    assert (ag["ingresos"], ag["gastos"], ag["ahorro"]) == (3_000_000, 1_000_000, 2_000_000)
    assert sep["ahorro"] == 500_000
    assert octu["ahorro"] == -400_000 and octu["en_curso"] and not sep["en_curso"]
    assert octu["acumulado"] == 2_100_000
    assert ag["etiqueta"] == "ago" and r["hay_datos"] and r["meses_con_datos"] == 3


def test_traslados_no_suman():
    movs = [mv(datetime(2026, 10, 2), "income", 1_000_000), mv(datetime(2026, 10, 3), "transfer", 900_000),
            mv(datetime(2026, 10, 4), "transfer", 50_000)]
    p = inf.evolucion(movs, HOY, "mes", 1)["puntos"][0]
    assert (p["ingresos"], p["gastos"], p["ahorro"]) == (1_000_000, 0, 1_000_000)


def test_mes_sin_datos_es_hueco_no_cero():
    movs = [mv(datetime(2026, 8, 5), "income", 100), mv(datetime(2026, 10, 5), "expense", 40)]
    p = inf.evolucion(movs, HOY, "mes", 3)["puntos"]
    assert p[1]["con_datos"] is False and p[1]["ingresos"] is None and p[1]["ahorro"] is None
    assert p[1]["acumulado"] == 100  # el acumulado sigue donde iba


def test_solo_traslados_cuenta_como_hueco():
    p = inf.evolucion([mv(datetime(2026, 10, 2), "transfer", 500)], HOY, "mes", 1)
    assert p["hay_datos"] is False and p["puntos"][0]["ingresos"] is None


def test_punto_de_partida_no_dibuja_antes():
    movs = [mv(datetime(2026, 9, 20), "income", 100)]
    r = inf.evolucion(movs, HOY, "mes", 12, inicio_pp=datetime(2026, 9, 15))
    assert [p["clave"] for p in r["puntos"]] == ["2026-09", "2026-10"]
    assert r["inicio"] == "2026-09-15"


def test_por_semana_lunes_a_domingo_y_en_curso():
    movs = [mv(datetime(2026, 10, 12), "income", 10), mv(datetime(2026, 10, 11), "expense", 4)]  # lunes y domingo
    p = inf.evolucion(movs, HOY, "semana", 1)["puntos"]
    assert p[-1]["desde"] == "2026-10-12" and p[-1]["hasta"] == "2026-10-18" and p[-1]["en_curso"]
    assert p[-1]["ingresos"] == 10 and p[-2]["gastos"] == 4 and p[-2]["desde"] == "2026-10-05"
    assert all(datetime.fromisoformat(x["desde"]).weekday() == 0 for x in p)


def test_todo_arranca_en_el_primer_movimiento_con_tope():
    movs = [mv(datetime(2026, 7, 9), "income", 10)]
    r = inf.evolucion(movs, HOY, "mes", 0)
    assert r["puntos"][0]["clave"] == "2026-07" and len(r["puntos"]) == 4
    viejo = inf.evolucion([mv(datetime(2020, 1, 9), "income", 10)], HOY, "mes", 0)
    assert len(viejo["puntos"]) == inf.MAX_MESES_EVOLUCION


def test_sin_movimientos():
    r = inf.evolucion([], HOY, "mes", 0)
    assert r["hay_datos"] is False and len(r["puntos"]) == 1


# ── Endpoint ─────────────────────────────────────────────────────────────────────────
client = TestClient(app)
U = UsuarioActual(id="evol-u", email="evol@test.com", nombre="Evol")
V = UsuarioActual(id="evol-v", email="evol-v@test.com", nombre="Otro")
ACTUAL = {"u": U}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    ACTUAL["u"] = U
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def datos():
    from app.derechos_titular import borrar_todo
    from app.utiles import ahora_co

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    hoy = ahora_co().replace(hour=12, minute=0, second=0, microsecond=0)
    cu = Cuenta(usuario_id=U.id, nombre="Nequi demo", tipo="ahorro", saldo=0, moneda="COP")
    cu2 = Cuenta(usuario_id=U.id, nombre="Nu demo", tipo="ahorro", saldo=0, moneda="COP")
    db.add_all([cu, cu2])
    db.flush()
    mes_ant = (hoy.replace(day=1) - timedelta(days=1)).replace(day=5)

    def add(cuenta, fecha, tipo, monto, desc):
        db.add(Movimiento(usuario_id=U.id, cuenta_id=cuenta.id, fecha=fecha, descripcion=desc, categoria="Otros",
                          tipo=tipo, monto=monto, fuente="manual", notas=""))

    add(cu, mes_ant, "income", 2_000_000, "Nomina Empresa Demo")
    add(cu, mes_ant, "expense", 300_000, "Supermercado Demo")
    add(cu, mes_ant + timedelta(days=1), "expense", 400_000, "Enviaste a Ana Demo")
    add(cu2, mes_ant + timedelta(days=1), "income", 400_000, "Recibiste de Ana Demo")
    add(cu, hoy.replace(day=1), "expense", 100_000, "Pan Demo")
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    try:
        borrar_todo(db, U.id, U.email)
    finally:
        db.close()


def test_endpoint_excluye_traslado_y_marca_en_curso(datos):
    r = client.get("/reportes/evolucion?agrupar=mes&meses=2")
    assert r.status_code == 200
    pts = r.json()["puntos"]
    assert len(pts) == 2
    assert (pts[0]["ingresos"], pts[0]["gastos"], pts[0]["ahorro"]) == (2_000_000, 300_000, 1_700_000)
    assert pts[1]["en_curso"] and pts[1]["gastos"] == 100_000
    assert pts[1]["acumulado"] == 1_600_000


def test_endpoint_por_semana_y_todo(datos):
    s = client.get("/reportes/evolucion?agrupar=semana&meses=0").json()
    assert s["agrupar"] == "semana" and sum(p["ingresos"] or 0 for p in s["puntos"]) == 2_000_000
    assert client.get("/reportes/evolucion?agrupar=dia").status_code == 422
    assert client.get("/reportes/evolucion?meses=99").status_code == 422


def test_endpoint_respeta_punto_de_partida(datos):
    from app.utiles import ahora_co

    hoy = ahora_co()
    r = client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": hoy.date().isoformat()})
    assert r.status_code == 200, r.text
    pts = client.get("/reportes/evolucion?meses=6").json()["puntos"]
    assert len(pts) == 1 and pts[0]["en_curso"]
    if hoy.day > 1:  # el gasto del día 1 queda antes del punto de partida
        assert pts[0]["con_datos"] is False


def test_otro_usuario_no_ve_datos_ajenos(datos):
    ACTUAL["u"] = V
    r = client.get("/reportes/evolucion?meses=6").json()
    assert r["hay_datos"] is False
    assert all(p["ingresos"] is None for p in r["puntos"])
