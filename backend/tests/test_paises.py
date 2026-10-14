"""Registro de países: paridad Python<->JS, sugerencia, remitentes por país, gating, conversión y endpoints."""
import json
import os
import re
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'paises.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import extractos_gmail as eg  # noqa: E402
from app import fx, paises  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
client = TestClient(app)


def _js():
    texto = open(os.path.join(RAIZ, "pwa", "src", "lib", "paises.js"), encoding="utf-8").read()
    m = re.search(r"export const PAISES = (\{.*?\n\})\n\nexport const ORDEN = (\[.*?\])\n", texto, re.S)
    return json.loads(m.group(1)), json.loads(m.group(2))


def test_paridad_python_js():
    datos, orden = _js()
    assert orden == paises.ORDEN
    assert datos == json.loads(json.dumps({c: paises.PAISES[c] for c in paises.ORDEN}))


def test_cada_pais_tiene_lo_minimo():
    for cod, c in paises.PAISES.items():
        assert c["codigo"] == cod
        for k in ("moneda", "simbolo", "locale", "zona_horaria", "ley_datos", "banco_central", "bancos"):
            assert c[k], (cod, k)
        nombres = [b["nombre"] for b in c["bancos"]]
        assert len(nombres) == len(set(nombres)), cod


def test_funciones_solo_colombia():
    assert paises.tiene_funcion("CO", "renta_dian") and paises.tiene_funcion("CO", "gmf")
    for cod in ("MX", "CL", "PE", "AR", "UY"):
        assert not paises.tiene_funcion(cod, "renta_dian")
        assert not paises.tiene_funcion(cod, "gmf")
    assert paises.tiene_funcion("MX", "declaracion_anual_informativa")
    assert not paises.tiene_funcion("ZZ", "renta_dian")  # desconocido: nada, nunca cae a CO


def test_sugerencia_sin_ip():
    assert paises.sugerir_pais("es-MX", None) == "MX"
    assert paises.sugerir_pais("es", "America/Santiago") == "CL"
    assert paises.sugerir_pais("es-ES", None) is None
    assert paises.sugerir_pais("pt-BR", None) is None  # Brasil aún no disponible
    assert paises.sugerir_pais(None, None) is None


def test_remitentes_por_pais():
    assert eg.banco_por_remitente("Alertas <alertas@bancolombia.com.co>") == "Bancolombia"
    assert eg.banco_por_remitente("x <no-reply@bbva.mx>") == "BBVA México"
    assert eg.banco_por_remitente("x <a@correo.bancoestado.cl>") == "BancoEstado"
    assert eg.banco_por_remitente("x <a@yape.com.pe>") == "Yape"
    assert eg.banco_por_remitente("x <a@desconocido.example>") is None
    q_co = eg.construir_query_notificaciones()
    q_mx = eg.construir_query_notificaciones(pais="MX")
    assert "bancolombia.com.co" in q_co and "banorte.com" not in q_co
    assert "banorte.com" in q_mx and "bancolombia.com.co" not in q_mx


def test_bancos_por_pais_sin_mezclar():
    mx = {b["nombre"] for b in paises.PAISES["MX"]["bancos"]}
    assert {"BBVA México", "Banorte", "Nu México", "Mercado Pago", "Spin by OXXO", "Hey Banco"} <= mx
    assert "Bancolombia" not in mx and "Nequi" not in mx
    assert "Nequi" in {b["nombre"] for b in paises.PAISES["CO"]["bancos"]}


def test_fx_proveedor_intercambiable_y_manual():
    try:
        fx.usar_proveedor(lambda base: {"MXN": 18.0, "USD": 1.0} if base == "USD" else {"USD": 0.05, "MXN": 1.0})
        m, fecha, fuente = fx.convertir_con_fecha(100, "USD", "MXN")
        assert fuente == "proveedor" and abs(m - 2000) < 1e-6 and fecha
        fx.fijar_tasa_manual("USD", "MXN", 20.0, "2026-10-01")
        m, fecha, fuente = fx.convertir_con_fecha(100, "USD", "MXN")
        assert (m, fecha, fuente) == (2000.0, "2026-10-01", "manual")
        assert fx.convertir(50, "MXN", "MXN") == 50
    finally:
        fx.borrar_tasas_manuales()
        fx.usar_proveedor(None)


def test_fx_sin_proveedor_cae_a_aproximada(monkeypatch):
    def caido(base):
        raise RuntimeError("sin red")

    try:
        fx.usar_proveedor(caido)
        m, _f, fuente = fx.convertir_con_fecha(1, "USD", "COP")
        assert fuente == "aproximada" and m > 1000
    finally:
        fx.usar_proveedor(None)


@pytest.fixture
def usuario():
    u = UsuarioActual(id="pais-u1", email="pais1@test.com", nombre="Pais Uno")
    app.dependency_overrides[get_current_user] = lambda: u
    yield u
    app.dependency_overrides.pop(get_current_user, None)


def test_endpoint_pais_defecto_y_guardado(usuario):
    r = client.get("/perfil/pais").json()
    assert r["pais"] == "CO" and r["confirmado"] is False  # perfil sin país: legado Colombia, sin confirmar
    r = client.put("/perfil/pais", json={"pais": "mx"}).json()
    assert r["pais"] == "MX" and r["moneda_base"] == "MXN" and r["confirmado"] is True
    assert "declaracion_anual_informativa" in r["config"]["funciones_fiscales"]
    db = SessionLocal()
    try:
        assert paises.pais_de_usuario(db, usuario.id) == "MX"
    finally:
        db.close()
    assert client.put("/perfil/pais", json={"pais": "BR"}).status_code == 422  # pt-BR aún no
    assert client.put("/perfil/pais", json={"pais": "XX"}).status_code == 422
    assert [p["codigo"] for p in client.get("/perfil/paises").json()["paises"]][:4] == ["CO", "MX", "CL", "PE"]


def test_usuario_no_ve_pais_de_otro(usuario):
    client.put("/perfil/pais", json={"pais": "CL"})
    otro = UsuarioActual(id="pais-u2", email="pais2@test.com", nombre="Dos")
    app.dependency_overrides[get_current_user] = lambda: otro
    assert client.get("/perfil/pais").json()["pais"] == "CO"
