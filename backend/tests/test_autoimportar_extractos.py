"""Procesar un extracto solo lee y propone; importar es al confirmar. La auto-importación es un
ajuste opcional (apagado por defecto), con resumen que suma y con 'Deshacer'. Datos inventados."""
import os
import tempfile
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'autoimport.db')}")

import pytest  # noqa: E402

from tests.test_extractos_gmail import GmailFalso, client, conectar_usuario  # noqa: E402

pytest.importorskip("reportlab.pdfgen.canvas")

ITEMS = [
    {"fecha": "2026-09-03", "descripcion": "NETFLIX.COM", "monto": 33000, "tipo": "expense", "referencia": ""},
    {"fecha": "2026-09-05", "descripcion": "SPOTIFY", "monto": 17000, "tipo": "expense", "referencia": ""},
    {"fecha": "2026-09-09", "descripcion": "Compra rara xyz", "monto": 12000, "tipo": "expense", "referencia": ""},
    {"fecha": "2026-09-12", "descripcion": "Abono nomina", "monto": 100000, "tipo": "income", "referencia": ""},
]


@pytest.fixture()
def entorno(monkeypatch):
    from app.routers import conciliacion as mod

    conectar_usuario(f"auto-{uuid.uuid4().hex[:8]}", GmailFalso([], {}), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Nu", "saldo": 1_000_000}).json()
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: "texto")
    monkeypatch.setattr(mod, "detectar_banco", lambda t: "nu")
    monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: ([dict(i) for i in ITEMS], 0))
    return cuenta


def _procesar(cuenta):
    return client.post("/conciliacion/procesar", json={"cuenta_id": cuenta["id"], "pdf_base64": "x"}).json()


def _saldo(cuenta):
    return [c for c in client.get("/cuentas").json() if c["id"] == cuenta["id"]][0]["saldo"]


def _suma(r):
    return r["ya_registrados"] + r["faltantes"] + r["auto_importados"]


def test_por_defecto_procesar_no_importa_nada_y_sugiere_con_razon(entorno):
    cuenta = entorno
    r = _procesar(cuenta)
    assert r["ok"] and r["autoimportar_activo"] is False
    assert r["auto_importados"] == 0 and r["faltantes"] == 4 and r["total_movimientos"] == 4
    assert _suma(r) == r["total_movimientos"]
    assert client.get("/movimientos").json() == []
    assert _saldo(cuenta) == 1_000_000
    netflix = [i for i in r["review"] if i["descripcion"] == "NETFLIX.COM"][0]
    assert netflix["estado"] == "faltante" and netflix["categoria_sugerida"] not in (None, "Otros")
    assert netflix["razon_categoria"]
    # Cancelar = no hacer nada: no queda ningún movimiento ni cambio de saldo.
    assert client.get("/movimientos").json() == []


def test_al_confirmar_si_se_importa(entorno):
    cuenta = entorno
    r = _procesar(cuenta)
    fps = [i["fingerprint"] for i in r["review"]]
    out = client.post(f"/conciliacion/historial/{r['historial_id']}/importar", json={"fingerprints": fps}).json()
    assert out["importados"] == 4
    assert _saldo(cuenta) == 1_000_000 - 33000 - 17000 - 12000 + 100000


def test_ajuste_activo_importa_lo_seguro_el_resumen_suma_y_se_deshace(entorno):
    cuenta = entorno
    assert client.get("/perfil/autoimportar-extractos").json()["activo"] is False
    assert client.put("/perfil/autoimportar-extractos", json={"activo": True}).json() == {"activo": True}

    r = _procesar(cuenta)
    assert r["autoimportar_activo"] is True and r["auto_importados"] >= 1
    assert _suma(r) == r["total_movimientos"] == 4
    autos = [i for i in r["review"] if i.get("auto")]
    assert len(autos) == r["auto_importados"] and all(i["movimiento_id"] for i in autos)
    importado = sum(i["monto"] if i["tipo"] == "expense" else -i["monto"] for i in autos)
    assert _saldo(cuenta) == 1_000_000 - importado
    assert len(client.get("/movimientos").json()) == r["auto_importados"]
    # Reabrir la revisión conserva el conteo.
    assert client.get(f"/conciliacion/historial/{r['historial_id']}").json()["auto_importados"] == r["auto_importados"]

    d = client.post(f"/conciliacion/historial/{r['historial_id']}/deshacer-auto").json()
    assert d["ok"] and d["deshechos"] == len(autos) and d["conservados"] == 0
    assert client.get("/movimientos").json() == []
    assert _saldo(cuenta) == 1_000_000
    despues = client.get(f"/conciliacion/historial/{r['historial_id']}").json()
    assert despues["auto_importados"] == 0
    assert all(i["estado"] == "faltante" for i in despues["review"])
    # Idempotente: otro 'deshacer' no cambia nada.
    assert client.post(f"/conciliacion/historial/{r['historial_id']}/deshacer-auto").json()["deshechos"] == 0
    assert _saldo(cuenta) == 1_000_000


def test_deshacer_respeta_lo_que_el_usuario_ya_confirmo(entorno):
    cuenta = entorno
    client.put("/perfil/autoimportar-extractos", json={"activo": True})
    r = _procesar(cuenta)
    autos = [i for i in r["review"] if i.get("auto")]
    assert autos
    mid = autos[0]["movimiento_id"]
    client.put(f"/movimientos/{mid}", json={"categoria": "Entretenimiento"})
    d = client.post(f"/conciliacion/historial/{r['historial_id']}/deshacer-auto").json()
    assert d["conservados"] + d["deshechos"] == len(autos)
    ids = [m["id"] for m in client.get("/movimientos").json()]
    assert (mid in ids) == (d["conservados"] == 1)
