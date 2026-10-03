"""
Endpoints de gastos compartidos y lectura de facturas. La IA (OpenRouter) SIEMPRE
va simulada: ninguna prueba sale a internet.
"""
import base64
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'gastos.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import factura  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.limites import _eventos  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200


@pytest.fixture(autouse=True)
def _usuario(request):
    # Un usuario distinto por prueba: así los saldos de una no contaminan a las demás.
    uid = f"u-{request.node.name}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="g@test.com", nombre="Gaby")
    _eventos.clear()
    yield


def _cuenta(saldo=1_000_000, moneda="COP"):
    return client.post("/cuentas", json={"nombre": "Cta", "saldo": saldo, "moneda": moneda}).json()


def _contacto(nombre, tel=""):
    r = client.post("/gastos-compartidos/contactos", json={"nombre": nombre, "telefono": tel})
    assert r.status_code == 200
    return r.json()


def _saldo(cuenta_id):
    return next(c["saldo"] for c in client.get("/cuentas").json() if c["id"] == cuenta_id)


def _gasto(cuenta, ids, registro="mi_parte", **extra):
    body = {
        "descripcion": "Cena", "total": 100000, "modo": "iguales",
        "participantes": [{"id": i} for i in ids], "registro": registro, "cuenta_id": cuenta["id"], **extra,
    }
    return client.post("/gastos-compartidos", json=body)


def test_calcular_vista_previa_y_error_claro():
    r = client.post("/gastos-compartidos/calcular", json={
        "total": 100, "modo": "porcentajes", "participantes": [{"id": "yo", "valor": 50}, {"id": "x", "valor": 40}],
    })
    assert r.status_code == 400 and "100" in r.json()["detail"]
    r = client.post("/gastos-compartidos/calcular", json={
        "total": 100000, "modo": "iguales", "participantes": [{"id": "yo"}, {"id": "a"}, {"id": "b"}],
    })
    assert sum(r.json()["partes"].values()) == 100000


def test_registro_mi_parte_y_saldo_del_amigo():
    c, ana = _cuenta(), _contacto("Ana", "3001234567")
    r = _gasto(c, ["yo", ana["id"]])
    assert r.status_code == 200
    assert _saldo(c["id"]) == 950_000  # solo mi mitad sale de la cuenta
    s = client.get("/gastos-compartidos/saldos").json()["monedas"][0]
    persona = next(p for p in s["personas"] if p["contacto_id"] == ana["id"])
    assert persona["saldo"] == 50000 and persona["telefono"] == "3001234567"
    assert s["total_me_deben"] >= 50000


def test_registro_total_y_pago_de_la_deuda():
    c, beto = _cuenta(), _contacto("Beto")
    _gasto(c, ["yo", beto["id"]], registro="total")
    assert _saldo(c["id"]) == 900_000  # pagué todo; Beto me debe 50.000
    pago = client.post("/gastos-compartidos/liquidaciones", json={"de_id": beto["id"], "a_id": "yo", "monto": 50000})
    assert pago.status_code == 200
    s = client.get("/gastos-compartidos/saldos").json()["monedas"][0]
    assert all(p["contacto_id"] != beto["id"] for p in s["personas"])  # quedó en paz


def test_otro_pago_yo_debo_y_se_simplifica():
    c, ana, beto = _cuenta(), _contacto("Ana"), _contacto("Beto")
    r = _gasto(c, ["yo", ana["id"], beto["id"]], registro="total", pagador_id=ana["id"], total=90000)
    assert r.status_code == 200
    assert _saldo(c["id"]) == 970_000  # como pagó Ana, solo mi parte (30.000)
    s = client.get("/gastos-compartidos/saldos").json()["monedas"][0]
    assert next(p for p in s["personas"] if p["contacto_id"] == ana["id"])["saldo"] == -30000
    destinos = {(p["de_nombre"], p["a_nombre"], p["monto"]) for p in s["simplificado"]}
    assert ("Tú", "Ana", 30000) in destinos and ("Beto", "Ana", 30000) in destinos


def test_grupo_filtra_saldos_y_ajenos_se_rechazan():
    c, ana = _cuenta(), _contacto("Ana")
    g = client.post("/gastos-compartidos/grupos", json={"nombre": "Viaje", "miembros": [ana["id"]]}).json()
    _gasto(c, ["yo", ana["id"]], grupo_id=g["id"])
    assert client.get(f"/gastos-compartidos/saldos?grupo_id={g['id']}").json()["monedas"]
    assert client.get("/gastos-compartidos/saldos?grupo_id=nope").status_code == 404
    assert _gasto(c, ["yo", "contacto-ajeno"]).status_code == 400
    # un contacto con gastos no se puede borrar
    assert client.delete(f"/gastos-compartidos/contactos/{ana['id']}").status_code == 400


def test_otro_usuario_no_ve_nada():
    c, ana = _cuenta(), _contacto("Ana")
    _gasto(c, ["yo", ana["id"]])
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="otro", email="o@test.com", nombre="O")
    assert client.get("/gastos-compartidos/contactos").json() == []
    assert client.get("/gastos-compartidos").json() == []
    assert client.get("/gastos-compartidos/saldos").json()["monedas"] == []


# ---------- Facturas ----------

def _ia(monkeypatch, contenido, status=200):
    llamadas = []

    class Resp:
        status_code = status

        def raise_for_status(self):
            if status >= 400:
                import httpx
                raise httpx.HTTPError("fallo simulado")

        def json(self):
            return {"choices": [{"message": {"content": contenido}}]}

    def falso_post(url, **kw):
        llamadas.append(kw)
        return Resp()

    monkeypatch.setattr(factura.httpx, "post", falso_post)
    monkeypatch.setattr(settings, "openrouter_api_key", "clave-falsa")
    return llamadas


def _escanear(datos=JPEG, mime="image/jpeg"):
    return client.post("/facturas/escanear", json={"imagen_base64": base64.b64encode(datos).decode(), "mime": mime})


def test_factura_lee_campos(monkeypatch):
    llamadas = _ia(monkeypatch, '```json\n{"legible": true, "comercio": "Restaurante El Cielo", "fecha": "2026-09-20",'
                                 ' "total": "145.900", "impuestos": 13264, "propina": null, "moneda": "COP", "categoria": "Comida"}\n```')
    r = _escanear()
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total"] == 145900 and d["comercio"] == "Restaurante El Cielo" and d["fecha"] == "2026-09-20"
    assert d["impuestos"] == 13264 and d["propina"] is None and d["categoria"] == "Comida"
    assert len(llamadas) == 1


def test_factura_categoria_de_respaldo_con_clasificador(monkeypatch):
    _ia(monkeypatch, '{"legible": true, "comercio": "Uber", "total": 18500, "categoria": "Inventada"}')
    d = _escanear().json()
    assert d["categoria"] == "Transporte"  # la IA dijo algo que no existe; manda el clasificador


def test_factura_borrosa_o_sin_total(monkeypatch):
    _ia(monkeypatch, '{"legible": false}')
    r = _escanear()
    assert r.status_code == 422 and "clara" in r.json()["detail"]
    _ia(monkeypatch, '{"legible": true, "comercio": "X", "total": null}')
    r = _escanear()
    assert r.status_code == 422 and "total" in r.json()["detail"]
    _ia(monkeypatch, "lo siento, no puedo ayudar")
    assert _escanear().status_code == 422


def test_factura_validaciones_de_imagen(monkeypatch):
    llamadas = _ia(monkeypatch, "{}")
    assert _escanear(b"no soy una imagen").status_code == 400
    assert _escanear(JPEG, "application/pdf").status_code == 400
    assert _escanear(b"\xff\xd8\xff" + b"0" * 2_000_000).status_code == 413
    assert client.post("/facturas/escanear", json={"imagen_base64": "###", "mime": "image/jpeg"}).status_code == 400
    assert llamadas == []  # nada de eso llegó a la IA


def test_factura_falla_de_la_ia_y_sin_clave(monkeypatch):
    _ia(monkeypatch, "", status=500)
    assert _escanear().status_code == 502
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    assert _escanear().status_code == 503


def test_factura_limite_por_usuario(monkeypatch):
    _ia(monkeypatch, '{"legible": true, "comercio": "Éxito", "total": 1000}')
    assert all(_escanear().status_code == 200 for _ in range(10))
    r = _escanear()
    assert r.status_code == 429 and "límite" in r.json()["detail"]
