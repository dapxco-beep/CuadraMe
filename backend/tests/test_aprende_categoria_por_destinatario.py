"""Lo que el atajo registra («Envío a Ana Perez») aprende la categoría que la persona corrige: el siguiente envío a la
misma persona llega ya categorizado (sigue «por confirmar»). Por eso el atajo no pregunta «¿para qué?»."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'aprendecat.db')}")

from cryptography.fernet import Fernet  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_la_categoria_corregida_se_aprende_por_destinatario(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="cat-1", email="c@t.com", nombre="C")
    assert client.post("/cuentas", json={"nombre": "Nequi", "saldo": 100000}).status_code == 200
    h = {"X-Api-Key": client.get("/perfil/api-key").json()["api_key"]}

    def enviar(monto, ref):
        texto = (f"Detalle del movimiento Envío Realizado Para Ana Perez ¿Cuánto? $ {monto},00 Número Nequi 300 111 2233 "
                 f"Referencia {ref} ¿De dónde salió la plata? Disponible Escanea este QR con Nequi")
        r = client.post("/movimientos/rapido-notificacion", headers=h, json={"paquete": "auto", "titulo": "", "texto": texto})
        assert r.status_code == 200 and r.json().get("registrado"), r.text
        return client.get(f"/movimientos/{r.json()['movimiento_id']}").json()

    primero = enviar("20.000", "M11111111")
    assert primero["descripcion"] == "Envío a Ana Perez" and primero["categoria"] == "Transferencias"
    assert client.put(f"/movimientos/{primero['id']}", json={"categoria": "Ocio"}).json()["categoria"] == "Ocio"
    segundo = enviar("15.000", "M22222222")
    assert segundo["categoria"] == "Ocio" and segundo["cat_confirmada"] is False  # aprendido, pero se sigue pudiendo revisar
