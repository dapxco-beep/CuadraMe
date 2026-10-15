"""
Traslados propios, casos sintéticos para CUALQUIER cliente (nada de datos reales):
nombre completo del titular (guardado por /perfil/nombre), truncamientos de los bancos, una sola
punta registrada y consistencia entre superficies (detalle de cuenta, informes, asistente IA).

Los casos de texto puro están en fixtures/contabilidad_casos.json (los comparte la PWA).
"""
import os
import tempfile
from datetime import timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'trasprop.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import contabilidad as c  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402

U = UsuarioActual(id="u-prop-1", email="titular.demo@example.com",
                  nombre="MARIA FERNANDA RODRIGUEZ LOPEZ", nombre_pila="Maria Fernanda")
client = TestClient(app)
TIT = ["Maria Fernanda Rodriguez Lopez"]


def test_menciones_nombre_truncado_y_orden():
    assert c.menciones_propias("Enviaste a MARIA FERNANDA RODRIG", TIT) == 3  # truncado: prefijo
    assert c.menciones_propias("RODRIGUEZ LOPEZ MARIA", TIT) == 3  # apellidos primero
    assert c.menciones_propias("Enviaste a Maria", TIT) == 1  # una sola palabra: no basta
    assert c.menciones_propias("Enviaste a Maria Rod", TIT) == 1  # prefijo < 4 letras no cuenta


def test_pistas_sin_nombre_y_sin_tildes():
    for d in ("Envío a mi Nequi", "Bre-B a mi llave", "Consignación a cuenta propia", "Movimiento entre cuentas",
              "Traslado a cajita", "Avance en efectivo"):
        assert c._es_propio_por_frase(d), d
    for d in ("Avance de obra", "Pago a mi proveedor", "Compra en Exito"):
        assert not c._es_propio_por_frase(d), d


@pytest.fixture
def escenario():
    from app.utiles import ahora_co
    from app.models import Perfil

    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_current_user] = lambda: U
    db = SessionLocal()
    ahora = ahora_co().replace(hour=12, minute=0, second=0, microsecond=0)
    base = ahora.replace(day=2) if ahora.day >= 2 else ahora
    a = Cuenta(usuario_id=U.id, nombre="Banco A demo", tipo="ahorro", saldo=0, moneda="COP")
    b = Cuenta(usuario_id=U.id, nombre="Banco B demo", tipo="ahorro", saldo=0, moneda="COP")
    db.add_all([a, b])
    db.flush()

    def mv(cuenta, tipo, monto, desc, dias=0):
        m = Movimiento(usuario_id=U.id, cuenta_id=cuenta.id, fecha=base + timedelta(days=dias), descripcion=desc,
                       categoria="Otros", tipo=tipo, monto=monto, fuente="importacion_archivo", notas="")
        db.add(m)
        return m

    out = {
        # par con una pista débil (Nequi) y SIN nombre: solo el detalle de cuenta lo veía mal
        "par_sale": mv(a, "expense", 300_000, "Nequi envio", 0),
        "par_entra": mv(b, "income", 300_000, "Recibido Nequi", 0),
        # una sola punta con el nombre completo truncado por el banco
        "sola_nombre": mv(a, "expense", 120_000, "ENVIASTE A MARIA FERNANDA RODRIG", 1),
        # un homónimo parcial: una sola palabra del nombre -> gasto real
        "homonimo": mv(a, "expense", 45_000, "Enviaste a Maria Gomez", 1),
        "sueldo": mv(b, "income", 2_000_000, "Nomina Empresa Demo", 1),
    }
    db.add(Perfil(usuario_id=U.id, plan="free"))
    db.commit()
    ids = {k: v.id for k, v in out.items()}
    ids["cuenta_a"], ids["cuenta_b"] = a.id, b.id
    db.close()
    yield ids
    from app.derechos_titular import borrar_todo
    db = SessionLocal()
    try:
        borrar_todo(db, U.id, U.email)
    finally:
        db.close()
    app.dependency_overrides.pop(get_current_user, None)


def test_el_nombre_completo_se_guarda_y_reconoce_la_unica_punta(escenario):
    # Sin nombre_titular guardado, «ENVIASTE A MARIA FERNANDA RODRIG» ya trae 2 palabras del nombre
    # preferido? No hay preferido: sigue siendo gasto hasta que la app guarde el nombre completo.
    antes = client.get("/reportes/ingresos-gastos?periodo=este_mes").json()
    assert antes["gastos"] == 120_000 + 45_000
    assert client.get("/perfil/nombre").status_code == 200  # la app lo llama al abrir: guarda el titular
    despues = client.get("/reportes/ingresos-gastos?periodo=este_mes").json()
    assert despues["gastos"] == 45_000  # el homónimo (1 palabra) sigue siendo gasto real
    assert despues["ingresos"] == 2_000_000


def test_detalle_de_cuenta_no_cuenta_el_traslado_de_la_otra_cuenta(escenario):
    d = client.get(f"/cuentas/{escenario['cuenta_a']}/detalle").json()
    assert d["gastos_mes"] == 120_000 + 45_000  # antes de conocer el nombre; el par Nequi es neutral
    client.get("/perfil/nombre")
    d = client.get(f"/cuentas/{escenario['cuenta_a']}/detalle").json()
    assert d["gastos_mes"] == 45_000
    b = client.get(f"/cuentas/{escenario['cuenta_b']}/detalle").json()
    assert b["ingresos_mes"] == 2_000_000


def test_posible_traslado_es_neutral_y_se_pregunta(escenario):
    client.get("/perfil/nombre")
    sug = client.get("/traslados/sugerencias").json()["sugerencias"]
    posibles = [s for s in sug if s["tipo"] == "posible"]
    assert any(escenario["sola_nombre"] in s["ids"] for s in posibles)
    assert not any(escenario["homonimo"] in s["ids"] for s in posibles)
