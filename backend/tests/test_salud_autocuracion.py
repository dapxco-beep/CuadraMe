"""Autocuración segura: asignación automática de extractos de tarjeta (cualquier banco), crear la cuenta de
tarjeta en un toque, reintento diario de errores de clave. Datos sintéticos."""
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'autocuracion.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import salud_autocuracion  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.extractos_gmail import sugerir_cuenta  # noqa: E402
from app.main import app  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, Movimiento  # noqa: E402

client = TestClient(app)
TEXTO_TARJETA = "Extracto de tu tarjeta de crédito: cupo, pago mínimo y fecha límite de pago"
TEXTO_AHORROS = "Extracto de tu cuenta de ahorros: saldo disponible"


def uid():
    return f"cura-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


def cuenta(db, u, nombre, tipo):
    c = Cuenta(usuario_id=u, nombre=nombre, tipo=tipo, saldo=0)
    db.add(c)
    db.commit()
    return c


def extracto(db, u, banco, asunto, estado="nuevo", archivo="e.pdf", sugerida=None):
    e = ExtractoCorreo(usuario_id=u, gmail_msg_id=uuid.uuid4().hex, archivo=archivo, banco=banco, asunto=asunto,
                       estado=estado, cuenta_sugerida_id=sugerida, recibido_en=datetime.utcnow())
    db.add(e)
    db.commit()
    return e


# ── 2a. La asignación automática es general, no solo de Nu ─────────────────────────────────────
@pytest.mark.parametrize("banco,ahorro,tarjeta", [
    ("Nu Colombia", "Nu Colombia", "Nu Tarjeta"),
    ("Bancolombia", "Bancolombia Ahorros", "Bancolombia Tarjeta"),
    ("Davivienda", "Davivienda Ahorros", "Davivienda Tarjeta"),
    ("Banco Falabella", "Falabella Ahorros", "Falabella CMR"),
    ("Banco de Bogotá", "Bogotá Ahorros", "Bogotá Tarjeta"),
])
def test_extracto_de_tarjeta_va_a_la_unica_tarjeta_del_banco(db, banco, ahorro, tarjeta):
    u = uid()
    a, t = cuenta(db, u, ahorro, "ahorro"), cuenta(db, u, tarjeta, "credito")
    cuentas = [a, t]
    assert sugerir_cuenta(banco, "", cuentas, TEXTO_TARJETA) == t.id
    assert sugerir_cuenta(banco, "", cuentas, TEXTO_AHORROS) == a.id


@pytest.mark.parametrize("banco,ahorro", [("Bancolombia", "Bancolombia Ahorros"), ("Davivienda", "Davivienda"),
                                          ("Banco Falabella", "Falabella Ahorros")])
def test_tarjeta_sin_cuenta_de_credito_no_se_asigna_a_los_ahorros(db, banco, ahorro):
    u = uid()
    a = cuenta(db, u, ahorro, "ahorro")
    assert sugerir_cuenta(banco, "", [a], TEXTO_TARJETA) is None  # nunca tapar el extracto de los ahorros


def test_con_dos_tarjetas_del_banco_no_adivina(db):
    u = uid()
    t1, t2 = cuenta(db, u, "Bancolombia Visa", "credito"), cuenta(db, u, "Bancolombia Mastercard", "credito")
    assert sugerir_cuenta("Bancolombia", "", [t1, t2], TEXTO_TARJETA) is None


# ── 2b. «Crear tu cuenta de tarjeta <Banco>» ───────────────────────────────────────────────────
def como(u):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=u, email=f"{u}@t.com", nombre="P")


@pytest.fixture(autouse=True)
def _limpiar_auth():
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_crear_tarjeta_crea_la_cuenta_estandar_y_reasigna_sin_importar(db):
    u = uid()
    ahorros = cuenta(db, u, "Bancolombia Ahorros", "ahorro")
    e1 = extracto(db, u, "Bancolombia", "Extracto de tu tarjeta de crédito", sugerida=ahorros.id)  # mal asignado
    e2 = extracto(db, u, "Bancolombia", "Extracto de tu tarjeta de crédito", estado="falta_clave", archivo="b.pdf")
    e3 = extracto(db, u, "Bancolombia", "Extracto de tu cuenta de ahorros", archivo="c.pdf", sugerida=ahorros.id)
    como(u)
    antes = db.query(Movimiento).filter(Movimiento.usuario_id == u).count()
    r = client.post("/salud/crear-tarjeta", json={"banco": "bancolombia"}).json()
    assert r["ok"] and r["creada"] and r["nombre"] == "Bancolombia Tarjeta" and r["reasignados"] == 2
    db.expire_all()
    tarjeta = db.query(Cuenta).filter(Cuenta.id == r["cuenta_id"]).one()
    assert tarjeta.tipo == "credito" and tarjeta.saldo == 0 and tarjeta.usuario_id == u
    assert db.get(ExtractoCorreo, e1.id).cuenta_sugerida_id == tarjeta.id
    assert db.get(ExtractoCorreo, e2.id).cuenta_sugerida_id == tarjeta.id
    assert db.get(ExtractoCorreo, e3.id).cuenta_sugerida_id == ahorros.id  # el de ahorros no se toca
    assert db.query(Movimiento).filter(Movimiento.usuario_id == u).count() == antes  # sin importar nada
    assert db.get(Cuenta, ahorros.id).saldo == 0
    # El hallazgo desaparece e insistir no duplica la cuenta.
    assert client.get("/salud").json()["total"] == 0 or "tarjeta_sin_cuenta" not in client.get("/salud").text
    otra = client.post("/salud/crear-tarjeta", json={"banco": "Bancolombia"}).json()
    assert otra["cuenta_id"] == tarjeta.id and otra["creada"] is False  # idempotente: no duplica la cuenta
    assert db.query(Cuenta).filter(Cuenta.usuario_id == u, Cuenta.tipo == "credito").count() == 1


def test_crear_tarjeta_de_un_banco_sin_extractos_de_tarjeta_es_404(db):
    u = uid()
    como(u)
    assert client.post("/salud/crear-tarjeta", json={"banco": "Davivienda"}).status_code == 404
    assert db.query(Cuenta).filter(Cuenta.usuario_id == u).count() == 0


def test_crear_tarjeta_no_toca_a_otra_persona(db):
    a, b = uid(), uid()
    ea = extracto(db, a, "Davivienda", "Extracto de tu tarjeta de crédito")
    como(b)
    assert client.post("/salud/crear-tarjeta", json={"banco": "Davivienda"}).status_code == 404
    db.expire_all()
    assert db.get(ExtractoCorreo, ea.id).cuenta_sugerida_id is None
    assert db.query(Cuenta).filter(Cuenta.usuario_id == b).count() == 0


# ── 2d. Reintento diario de errores de clave ────────────────────────────────────────────────────
def test_reintento_diario_corre_una_vez_al_dia(db, monkeypatch):
    llamadas = []
    monkeypatch.setattr("app.extractos_error.reintentar_errores_clave",
                        lambda d, usuario: llamadas.append(usuario.id) or {"reintentados": 1, "leidos": 1, "pendientes": 0})
    u = uid()
    assert salud_autocuracion.reintento_diario(db, u)["reintentados"] == 1
    assert salud_autocuracion.reintento_diario(db, u) is None  # ya se hizo hoy
    assert llamadas == [u]
    db.query(MarcaCron).filter(MarcaCron.usuario_id == u).update({"valor": "2000-01-01"})
    db.commit()
    assert salud_autocuracion.reintento_diario(db, u) is not None  # al día siguiente vuelve


def test_reintento_diario_no_lanza_si_falla(db, monkeypatch):
    def falla(d, usuario):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.extractos_error.reintentar_errores_clave", falla)
    assert salud_autocuracion.reintento_diario(db, uid()) is None
