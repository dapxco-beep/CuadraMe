"""Resumen semanal por correo y recordatorios del Inicio.

Cada prueba usa su propio usuario (la base de pruebas se comparte entre archivos).
Los números están hechos a mano."""
import os
import tempfile
from datetime import timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'resumen.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import resumen_semanal as rs  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, Movimiento, Presupuesto  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}
USUARIO = {"actual": UsuarioActual(id="rs-0", email="a@test.com", nombre="Rs")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


@pytest.fixture
def correos(monkeypatch):
    """Captura los correos que saldrían por Resend: [(destino, asunto, html)]."""
    enviados = []

    def _enviar(destino, asunto, html, texto):
        enviados.append((destino, asunto, html))
        return True

    monkeypatch.setattr(rs, "enviar_correo", _enviar)
    return enviados


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def sembrar(uid, gastos=(("Comida", 40_000), ("Transporte", 20_000)), tarjeta=False, presupuesto=False):
    """Una cuenta con gastos de esta semana; opcionalmente una tarjeta que se paga en 2 días
    (deuda 500.000) y un presupuesto de Comida al 85 %."""
    db = SessionLocal()
    try:
        c = Cuenta(usuario_id=uid, nombre="Banco", saldo=1_000_000, moneda="COP")
        db.add(c)
        db.flush()
        for cat, monto in gastos:
            db.add(Movimiento(usuario_id=uid, cuenta_id=c.id, fecha=ahora_co() - timedelta(hours=1),
                              descripcion=f"Gasto {cat}", categoria=cat, tipo="expense", monto=monto))
        if tarjeta:
            db.add(Cuenta(usuario_id=uid, nombre="Visa <b>", tipo="credito", saldo=-500_000, moneda="COP",
                          cupo_total=2_000_000, dia_pago=(ahora_co() + timedelta(days=2)).day))
        if presupuesto:
            db.add(Presupuesto(usuario_id=uid, categoria="Comida", limite=47_000, alerta_pct=80))
        db.commit()
    finally:
        db.close()


def activar(uid, valor=True):
    como(uid)
    return client.put("/resumen/preferencias", json={"correo": valor})


def cron():
    return client.post("/resumen/cron/semanal", headers=CABECERA).json()


def test_cron_exige_secreto():
    assert client.post("/resumen/cron/semanal").status_code == 401
    assert client.post("/resumen/cron/semanal", headers={"X-Cron-Secret": "mal"}).status_code == 401


def test_por_defecto_esta_apagado_y_se_puede_activar_y_apagar():
    como("rs-pref")
    assert client.get("/resumen/preferencias").json()["correo"] is False
    assert activar("rs-pref").json()["correo"] is True
    assert client.get("/resumen/preferencias").json() == {"correo": True, "email": "rs-pref@test.com"}
    assert activar("rs-pref", False).json()["correo"] is False


def test_sin_opt_in_no_se_envia_nada(correos):
    sembrar("rs-sin")
    cron()
    assert [c for c in correos if c[0] == "rs-sin@test.com"] == []


def test_envia_con_los_numeros_de_la_semana_y_es_idempotente(correos):
    sembrar("rs-ok", tarjeta=True, presupuesto=True)
    activar("rs-ok")
    r1 = cron()
    mios = [c for c in correos if c[0] == "rs-ok@test.com"]
    assert len(mios) == 1 and r1["enviados"] >= 1
    destino, asunto, html = mios[0]
    assert "$60.000" in asunto and "$60.000" in html
    assert "Comida" in html and "$40.000" in html  # categoría top
    assert "85 %" in html  # presupuesto casi agotado (40.000 de 47.000)
    assert "$500.000" in html and "en 2 días" in html  # vencimiento de tarjeta
    assert "&lt;b&gt;" in html and "<b>" not in html  # lo que escribe el usuario se escapa
    assert "Perfil" in html  # cómo darse de baja
    r2 = cron()
    assert len([c for c in correos if c[0] == "rs-ok@test.com"]) == 1  # misma semana: no repite
    assert r2["ya_enviados"] >= 1


def test_semana_siguiente_vuelve_a_enviar(correos, monkeypatch):
    from app.routers import resumen as router

    sembrar("rs-sem")
    activar("rs-sem")
    cron()
    hoy = ahora_co()
    db = SessionLocal()
    try:  # un gasto de la semana siguiente (la corrida simulada ocurre 7 días después)
        cuenta = db.query(Cuenta).filter(Cuenta.usuario_id == "rs-sem").first()
        db.add(Movimiento(usuario_id="rs-sem", cuenta_id=cuenta.id, fecha=hoy + timedelta(days=5),
                          descripcion="Otro", categoria="Comida", tipo="expense", monto=10_000))
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(router, "ahora_co", lambda: hoy + timedelta(days=7))
    cron()
    assert len([c for c in correos if c[0] == "rs-sem@test.com"]) == 2


def test_usuario_sin_nada_que_contar_no_recibe_correo(correos):
    db = SessionLocal()
    try:
        db.add(Cuenta(usuario_id="rs-vacio", nombre="Banco", saldo=0, moneda="COP"))
        db.commit()
    finally:
        db.close()
    activar("rs-vacio")
    cron()
    assert [c for c in correos if c[0] == "rs-vacio@test.com"] == []


def test_un_fallo_no_frena_a_los_demas_y_la_marca_se_libera(correos, monkeypatch):
    sembrar("rs-falla")
    sembrar("rs-bien")
    activar("rs-falla")
    activar("rs-bien")
    original = rs.enviar_correo

    def _roto(destino, asunto, html, texto):
        if destino == "rs-falla@test.com":
            raise RuntimeError("Resend caído")
        return original(destino, asunto, html, texto)

    monkeypatch.setattr(rs, "enviar_correo", _roto)
    r = cron()
    assert r["fallidos"] >= 1
    assert [c[0] for c in correos if c[0] in ("rs-falla@test.com", "rs-bien@test.com")] == ["rs-bien@test.com"]
    db = SessionLocal()
    try:  # la marca del que falló quedó libre: la próxima corrida puede reintentar
        assert db.query(MarcaCron).filter(MarcaCron.usuario_id == "rs-falla", MarcaCron.clave == "resumen_correo_semanal").count() == 0
    finally:
        db.close()


def test_sin_resend_configurado_no_marca_la_semana(monkeypatch):
    monkeypatch.setattr("app.resumen_semanal.settings.resend_api_key", "")
    sembrar("rs-sinkey")
    activar("rs-sinkey")
    cron()
    db = SessionLocal()
    try:
        assert db.query(MarcaCron).filter(MarcaCron.usuario_id == "rs-sinkey").count() == 0
    finally:
        db.close()


# --------------------------------------------------------------- recordatorios

def test_recordatorios_tarjeta_presupuesto_y_extractos():
    sembrar("rs-rec", tarjeta=True, presupuesto=True)
    db = SessionLocal()
    try:
        db.add(ExtractoCorreo(usuario_id="rs-rec", gmail_msg_id="m1", archivo="a.pdf", estado="nuevo"))
        db.add(ExtractoCorreo(usuario_id="rs-rec", gmail_msg_id="m2", archivo="b.pdf", estado="descartado"))
        db.commit()
    finally:
        db.close()
    como("rs-rec")
    lista = client.get("/recordatorios").json()
    assert [r["tipo"] for r in lista] == ["tarjeta", "presupuesto", "extractos"]
    assert "en 2 días" in lista[0]["titulo"] and "$500.000" in lista[0]["texto"]
    assert "85 %" in lista[1]["titulo"]
    assert lista[2]["titulo"] == "Tienes 1 extracto por revisar"
    assert all(r["clave"] and r["ruta"].startswith("/") for r in lista)


def test_recordatorios_vacio_si_no_hay_nada():
    como("rs-rec-vacio")
    assert client.get("/recordatorios").json() == []
