"""El atajo de iPhone pregunta lo que el aviso no dice y APRENDE la respuesta (reglas personales, sin guardar el texto)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'reglasnotif.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.reglas_notificacion import esqueleto, tipo_normal  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="rn-0", email="rn@test.com", nombre="RN")}
ENVIO = ("Tu plata llegó con éxito 💜", "Envío exitoso, la plata ya está en el Nequi destino. Recuerda que no se puede cancelar.")
RECIBO = ("Envío", "DANIEL PARRADO te envió 1, ¡lo mejor!")


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def _usuario(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)
    assert client.post("/cuentas", json={"nombre": "Nequi", "saldo": 100000}).status_code == 200
    return {"X-Api-Key": client.get("/perfil/api-key").json()["api_key"]}


def _aviso(h, par, **extra):
    r = client.post("/movimientos/rapido-notificacion", headers=h,
                    json={"paquete": "Nequi", "titulo": par[0], "texto": par[1], **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_esqueleto_no_guarda_nombres_ni_montos():
    e = esqueleto(*RECIBO)
    assert "daniel" not in e and "parrado" not in e and "1" not in e and "te" in e.split()


def test_tipo_normal():
    assert tipo_normal("Gasto") == "expense" and tipo_normal("Ingreso") == "income" and tipo_normal("x") is None


def test_enviaste_pregunta_registra_y_aprende():
    h = _usuario("rn-1")
    assert _aviso(h, ENVIO)["motivo"] == "pedir_monto"
    r = _aviso(h, ENVIO, monto=25000, tipo="gasto", nota="parche con Laura")
    assert r["registrado"] and r["aprendido"] and r["por_confirmar"]
    movs = client.get("/movimientos").json()
    mov = movs[0] if isinstance(movs, list) else movs["items"][0]
    assert mov["monto"] == 25000 and mov["tipo"] == "expense" and "parche" in mov["descripcion"].lower()
    reglas = client.get("/movimientos/reglas-notificacion").json()
    assert len(reglas) == 1 and reglas[0]["app"] == "Nequi" and "no trae monto" in reglas[0]["significado"]
    assert "parche" not in str(reglas).lower() and "laura" not in str(reglas).lower()  # nunca el texto ni la nota


def test_recibiste_se_registra_como_ingreso_sin_preguntar():
    h = _usuario("rn-2")
    r = _aviso(h, RECIBO)
    assert r["registrado"] and "motivo" not in r


def test_direccion_dudosa_pregunta_y_luego_ya_no():
    h = _usuario("rn-3")
    dudoso = ("Nequi", "Movimiento por $50.000 en tu cuenta")
    assert _aviso(h, dudoso)["motivo"] == "pedir_tipo"
    r = _aviso(h, dudoso, monto=50000, tipo="ingreso")
    assert r["aprendido"]
    # La próxima vez con la misma forma de aviso ya no pregunta: se registra con lo aprendido.
    otro = ("Nequi", "Movimiento por $70.000 en tu cuenta")
    r2 = _aviso(h, otro)
    assert r2["registrado"] and "motivo" not in r2
    assert client.get("/movimientos/reglas-notificacion").json()[0]["usos"] == 1


def test_aprender_apagado_no_guarda_regla():
    h = _usuario("rn-4")
    _aviso(h, ENVIO, monto=1000, tipo="gasto", nota="x", aprender=False)
    assert client.get("/movimientos/reglas-notificacion").json() == []


def test_reglas_son_personales_y_se_pueden_borrar():
    h = _usuario("rn-5")
    _aviso(h, ENVIO, monto=2000, tipo="gasto", nota="x")
    regla = client.get("/movimientos/reglas-notificacion").json()[0]
    _usuario("rn-6")
    assert client.get("/movimientos/reglas-notificacion").json() == []
    assert client.delete(f"/movimientos/reglas-notificacion/{regla['id']}").status_code == 404  # no es suya
    USUARIO["actual"] = UsuarioActual(id="rn-5", email="rn-5@test.com", nombre="rn-5")
    assert client.delete(f"/movimientos/reglas-notificacion/{regla['id']}").status_code == 200
    assert client.get("/movimientos/reglas-notificacion").json() == []


def test_migracion_crea_la_tabla_sin_errores_de_sintaxis():
    """Los tests usan create_all; esto ejecuta el SQL REAL de la migración (un `DEFAULT ''` mal escapado tumbó un despliegue)."""
    from sqlalchemy import create_engine, text

    from app.migraciones import MIGRACIONES

    sentencias = next(s for nombre, s in MIGRACIONES if nombre == "0013_reglas_notificacion")
    motor = create_engine("sqlite://")
    with motor.begin() as conn:
        for sql in sentencias:
            conn.execute(text(sql))
        conn.execute(text("INSERT INTO reglas_notificacion (id, usuario_id) VALUES ('1', 'u')"))
        fila = conn.execute(text("SELECT app, esqueleto FROM reglas_notificacion")).one()
    assert tuple(fila) == ("", "")
