"""Nombre propio (titulo) en los informes que arman sus propias filas: se muestra `titulo or descripcion`;
el texto del banco sigue siendo la clave de agrupación (docs/TITULO_PERSONALIZADO.md)."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'titulo_inf.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="tit-inf", email="t@test.com", nombre="T")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_informes_y_detalle_de_cuenta_muestran_el_nombre_propio():
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 0}).json()
    fecha = datetime.now().replace(day=1, hour=12).isoformat()
    for _ in range(2):
        r = client.post("/movimientos", json={"cuenta_id": cuenta["id"], "descripcion": "PAGO PSE 884221 ENEL", "titulo": "Recibo de la luz",
                                              "monto": 90000, "tipo": "expense", "categoria": "Servicios", "fecha": fecha})
        assert r.status_code in (200, 201), r.text
    # Sin nombre propio: sigue el texto del banco.
    client.post("/movimientos", json={"cuenta_id": cuenta["id"], "descripcion": "TIENDA XYZ", "monto": 1000, "tipo": "expense",
                                      "categoria": "Servicios", "fecha": fecha})

    filas = client.get("/informes/gasto/movimientos", params={"categoria": "Servicios", "periodo": "este_mes"}).json()["movimientos"]
    nombres = sorted(f["descripcion"] for f in filas)
    assert nombres == ["Recibo de la luz", "Recibo de la luz", "TIENDA XYZ"]
    assert {f["titulo"] for f in filas} == {"Recibo de la luz", None}

    informe = client.get("/informes/gasto", params={"periodo": "este_mes"}).json()
    top = [c["nombre"] for c in informe["comercios"]]
    assert "Recibo de la luz" in top and not any("PSE" in n for n in top)

    det = client.get(f"/cuentas/{cuenta['id']}/detalle").json()
    assert "Recibo de la luz" in [m["descripcion"] for m in det["movimientos"]]
