"""Duplicados al importar extractos (datos sintéticos): dos movimientos idénticos el mismo
día son DOS; el mismo archivo subido dos veces no duplica nada."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'dup_ext.db')}")

import pytest  # noqa: E402

from tests.test_extractos_gmail import GmailFalso, client, conectar_usuario  # noqa: E402

pytest.importorskip("reportlab.pdfgen.canvas")


def _item(desc, monto, fecha="2026-09-18", tipo="expense"):
    return {"fecha": fecha, "descripcion": desc, "monto": monto, "tipo": tipo, "referencia": ""}


@pytest.fixture()
def preparado(monkeypatch):
    from app.routers import conciliacion as mod

    def _preparar(uid, items):
        conectar_usuario(uid, GmailFalso([], {}), monkeypatch)
        cuenta = client.post("/cuentas", json={"nombre": "Nu", "saldo": 0}).json()
        monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: "texto")
        monkeypatch.setattr(mod, "detectar_banco", lambda t: "nu")
        monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: ([dict(i) for i in items], 0))
        return cuenta

    return _preparar


def _procesar(cuenta):
    return client.post("/conciliacion/procesar", json={"cuenta_id": cuenta["id"], "pdf_base64": "x"}).json()


def _importar(r):
    fps = [i["fingerprint"] for i in r["review"] if i["estado"] == "faltante"]
    return client.post(f"/conciliacion/historial/{r['historial_id']}/importar", json={"fingerprints": fps}).json()


def test_dos_movimientos_identicos_se_importan_los_dos(preparado):
    cuenta = preparado("dup-ident", [_item("Envio a Persona", 20000), _item("Envio a Persona", 20000)])
    r = _procesar(cuenta)
    assert r["total_movimientos"] == 2 and r["faltantes"] == 2
    out = _importar(r)
    assert out["importados"] == 2 and out["duplicados_omitidos"] == 0
    # Mismo archivo otra vez: los dos ya están, nada nuevo.
    r2 = _procesar(cuenta)
    assert r2["exactos"] == 2 and r2["faltantes"] == 0


def test_extracto_subido_dos_veces_antes_de_importar_no_duplica(preparado):
    cuenta = preparado("dup-doble", [_item("Envio a Persona", 20000), _item("Envio a Persona", 20000)])
    a, b = _procesar(cuenta), _procesar(cuenta)  # las dos revisiones quedan pendientes
    assert _importar(a)["importados"] == 2
    seg = _importar(b)
    assert seg["importados"] == 0 and seg["duplicados_omitidos"] == 2


def test_si_ya_estaba_uno_de_los_dos_se_importa_solo_el_otro(preparado):
    cuenta = preparado("dup-mitad", [_item("Envio a Persona", 20000), _item("Envio a Persona", 20000)])
    client.post("/movimientos", json={
        "cuenta_id": cuenta["id"], "descripcion": "Envio a Persona", "monto": 20000, "tipo": "expense",
        "categoria": "Otros", "fecha": "2026-09-18T00:00:00",
    })
    r = _procesar(cuenta)
    assert r["exactos"] == 1 and r["faltantes"] == 1
    out = _importar(r)
    assert out["importados"] == 1 and out["duplicados_omitidos"] == 0
