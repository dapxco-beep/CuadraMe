"""
Correos aprobados con el nombre real del comercio (no el del remitente) y sin
aprobar montos <= 0. Gmail simulado: ninguna prueba llama a Google.
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'correos_comercio.db')}")

import pytest  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.gmail_extract import extraer_comercio  # noqa: E402
from app.models import CorreoGasto  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, client, conectar_usuario, mensaje  # noqa: E402

NU = "Nu Colombia <notificaciones@nu.com.co>"


# ── Extracción pura ──────────────────────────────────────────────────

@pytest.mark.parametrize("asunto,cuerpo,esperado", [
    ("Compra aprobada en JUAN VALDEZ por $12.000", "", "Compra en Juan Valdez"),
    ("Tu compra", "Compra en Tienda La Esquina con tu tarjeta terminada en 1234", "Compra en Tienda La Esquina"),
    ("Enviaste $50.000 a Ana Pérez", "", "Envío a Ana Pérez"),
    ("Pago de servicios realizado", "", "Pago de servicios"),
    ("Pago de servicios públicos exitoso", "", "Pago de servicios públicos"),
    ("Recibiste $80.000 de Carlos Gómez", "", "Recibido de Carlos Gómez"),
])
def test_el_concepto_sale_del_asunto_o_del_cuerpo(asunto, cuerpo, esperado):
    assert extraer_comercio(NU, asunto, cuerpo) == esperado


def test_banco_sin_detalle_no_devuelve_el_remitente():
    r = extraer_comercio(NU, "Tienes un nuevo movimiento", "Revisa tu app")
    assert r == "Gasto sin detalle" and "Nu" not in r
    assert extraer_comercio(NU, "Te llegó un abono", "") == "Ingreso sin detalle"


def test_remitente_que_es_comercio_se_conserva():
    assert extraer_comercio("Netflix <info@mailer.netflix.com>", "Tu recibo", "") == "Netflix"


# ── Aprobar desde la API ─────────────────────────────────────────────

def _sincronizar(uid, mensajes, monkeypatch):
    conectar_usuario(uid, GmailFalso(mensajes, {}), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu", "saldo": 100000}).json()
    client.post("/correos/sincronizar")
    return cuenta, client.get("/correos/pendientes").json()


def test_aprobar_correo_deja_el_comercio_como_descripcion(monkeypatch):
    cuenta, pendientes = _sincronizar(
        "cc-comercio", [mensaje("m1", NU, "Compra aprobada en JUAN VALDEZ", "Por $12.000 con tu tarjeta")], monkeypatch
    )
    assert pendientes[0]["comercio"] == "Compra en Juan Valdez"
    assert pendientes[0]["falta_monto"] is False
    r = client.post(f"/correos/{pendientes[0]['id']}/aprobar", json={"cuenta_id": cuenta["id"]})
    assert r.status_code == 200, r.text
    movs = client.get("/movimientos").json()
    movs = movs["items"] if isinstance(movs, dict) else movs
    assert [m["descripcion"] for m in movs] == ["Compra en Juan Valdez"]
    assert movs[0]["fuente"] == "email"
    assert client.get("/cuentas").json()[0]["saldo"] == 88000


def _correo_sin_monto(uid):
    db = SessionLocal()
    try:
        c = CorreoGasto(
            usuario_id=uid, gmail_msg_id="sin-monto", remitente=NU, asunto="Compra en Café Luna", snippet="",
            monto=0, moneda="COP", comercio="Compra en Café Luna", categoria_sugerida="Otros",
            tipo_sugerido="expense", confianza=0, estado="pendiente",
        )
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


def test_no_se_aprueba_un_correo_con_monto_cero(monkeypatch):
    cuenta, _ = _sincronizar("cc-monto0", [], monkeypatch)
    correo_id = _correo_sin_monto("cc-monto0")

    # Un correo sin monto no se ofrece en la lista (ni cuenta como tarea): no es un movimiento...
    assert client.get("/correos/pendientes").json() == []
    # ...y aun llegando a él por el id, no se puede aprobar.
    r = client.post(f"/correos/{correo_id}/aprobar", json={"cuenta_id": cuenta["id"]})
    assert r.status_code == 400 and "monto" in r.json()["detail"].lower()
    r = client.post(f"/correos/{correo_id}/aprobar", json={"cuenta_id": cuenta["id"], "monto": 0})
    assert r.status_code == 400
    r = client.post(f"/correos/{correo_id}/aprobar", json={"cuenta_id": cuenta["id"], "monto": -5})
    assert r.status_code == 400
    assert client.get("/cuentas").json()[0]["saldo"] == 100000  # nada se movió

    r = client.patch(f"/correos/{correo_id}", json={"monto": 0})
    assert r.status_code == 400


def test_con_el_monto_escrito_si_se_aprueba(monkeypatch):
    cuenta, _ = _sincronizar("cc-monto-ok", [], monkeypatch)
    correo_id = _correo_sin_monto("cc-monto-ok")
    r = client.post(f"/correos/{correo_id}/aprobar", json={"cuenta_id": cuenta["id"], "monto": 7500})
    assert r.status_code == 200, r.text
    assert r.json()["monto"] == 7500 and r.json()["estado"] == "aprobado" and r.json()["falta_monto"] is False
    assert client.get("/cuentas").json()[0]["saldo"] == 92500
    tareas = {t["id"] for t in client.get("/sincronizacion/estado").json()["tareas"]}
    assert "correos_por_revisar" not in tareas
