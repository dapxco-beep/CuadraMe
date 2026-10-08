"""Topes diarios por usuario (tabla uso_diario) y reparto justo del cron de Gmail entre muchos usuarios."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'limites_diarios.db')}")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app import limites_diarios as ld  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402
from tests.test_cron_correos import CABECERA, URL, GmailFalso, _compra, _pendientes, _usuario, client, entorno  # noqa: E402,F401


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_el_tope_diario_corta_con_mensaje_amable_y_no_afecta_a_otros(db, monkeypatch):
    monkeypatch.setitem(ld.LIMITES_DIARIOS, "factura", (3, "facturas escaneadas"))
    for _ in range(3):
        ld.consumir_cupo_diario(db, "ld-1", "factura")
    with pytest.raises(HTTPException) as e:
        ld.consumir_cupo_diario(db, "ld-1", "factura")
    assert e.value.status_code == 429
    assert "3 facturas escaneadas" in e.value.detail and "mañana" in e.value.detail
    ld.consumir_cupo_diario(db, "ld-2", "factura")  # otro usuario
    ld.consumir_cupo_diario(db, "ld-1", "preguntar")  # otra acción del mismo usuario


def test_el_cupo_se_reinicia_al_dia_siguiente(db, monkeypatch):
    monkeypatch.setitem(ld.LIMITES_DIARIOS, "importar", (1, "archivos importados"))
    ld.consumir_cupo_diario(db, "ld-3", "importar")
    with pytest.raises(HTTPException):
        ld.consumir_cupo_diario(db, "ld-3", "importar")
    from datetime import timedelta
    real = ld.ahora_co
    monkeypatch.setattr(ld, "ahora_co", lambda: real() + timedelta(days=1))
    ld.consumir_cupo_diario(db, "ld-3", "importar")  # día nuevo: no lanza


def test_si_falla_el_contador_se_deja_pasar(db, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("base caída")
    monkeypatch.setattr(db, "execute", roto)
    ld.consumir_cupo_diario(db, "ld-4", "preguntar")  # no lanza


def test_endpoint_devuelve_429_legible_al_agotar_el_cupo(monkeypatch):
    from app.auth import UsuarioActual, get_current_user
    from app.main import app
    monkeypatch.setitem(ld.LIMITES_DIARIOS, "preguntar", (1, "preguntas al asistente"))
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="ld-5", email="a@b.co", nombre="A")
    try:
        client.post("/insights/preguntar", json={"pregunta": "en que gaste mas este mes"})
        r = client.post("/insights/preguntar", json={"pregunta": "en que gaste mas este mes"})
        assert r.status_code == 429 and "1 preguntas al asistente" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_cron_limita_usuarios_por_llamada_y_reanuda_sin_repetir(entorno, monkeypatch):
    monkeypatch.setattr(router_correos, "MAX_USUARIOS_POR_CRON", 2)
    usuarios = [_usuario(entorno, GmailFalso([_compra(f"lt{i}")], {}))[0] for i in range(5)]
    vistos = set()
    for ronda in range(3):
        r = client.post(URL, headers=CABECERA).json()
        assert r["procesados"] <= 2
        vistos |= {u for u in usuarios if _pendientes(u)}
        if ronda == 0:
            assert r["pendientes_por_tiempo"] == 3
    # En 3 llamadas de 2 usuarios, los 5 quedaron atendidos y nadie se repitió primero que otro sin turno.
    assert vistos == set(usuarios)
    assert all(_pendientes(u) == 1 for u in usuarios)


def test_un_usuario_que_siempre_falla_no_acapara_el_turno(entorno, monkeypatch):
    monkeypatch.setattr(router_correos, "MAX_USUARIOS_POR_CRON", 1)
    _malo, _ = _usuario(entorno, RuntimeError("Gmail caído"))
    bueno, _ = _usuario(entorno, GmailFalso([_compra("lt-b")], {}))
    client.post(URL, headers=CABECERA)
    client.post(URL, headers=CABECERA)
    assert _pendientes(bueno) == 1  # en la 2.ª llamada le tocó aunque el otro nunca termina bien
