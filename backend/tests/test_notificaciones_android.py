"""Notificaciones de Android -> movimiento «por confirmar». TODO el texto es inventado (ningún dato real).

Para «reentrenar» una notificación que falle: agregar una fila a CORPUS con el texto tal cual y lo esperado."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'notif.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import notificaciones as nt  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento, Perfil  # noqa: E402

# (id, paquete, titulo, texto, esperado) — esperado None = no es un movimiento
CORPUS = [
    ("nequi_pago", "com.nequi.MobileApp", "Nequi", "Pagaste $20.000 en JUMBO.",
     dict(tipo="expense", monto=20000, comercio="Jumbo", clase="banco")),
    ("nequi_envio", "com.nequi.MobileApp", "Nequi", "Enviaste $50.000 a Juan Perez",
     dict(tipo="expense", monto=50000, comercio_en="Juan Perez")),
    ("nequi_recibo", "com.nequi.MobileApp", "Nequi", "Recibiste $100.000 de Maria Lopez",
     dict(tipo="income", monto=100000, comercio_en="Maria Lopez")),
    ("nu_compra", "com.nu.production", "Compra aprobada", "Compra por $45.900 en Mercado Libre con tu tarjeta terminada en 1234",
     dict(tipo="expense", monto=45900, comercio_en="Mercado Libre", tarjeta="1234")),
    ("bancolombia_compra", "com.todo1.mobile", "Bancolombia", "Bancolombia le informa Compra por $85.000 en EXITO CHIA con tarjeta *1234",
     dict(tipo="expense", monto=85000, comercio_en="Exito")),
    ("wallet_titulo", "com.google.android.apps.walletnfcrel", "$20.000 COP a JUMBO", "Visa ••••1234",
     dict(tipo="expense", monto=20000, comercio="Jumbo", clase="wallet", fuente="google_pay", tarjeta="Visa 1234")),
    ("wallet_texto", "com.google.android.apps.walletnfcrel", "Pagaste $20.000", "Tarjeta Visa ••1234 en Jumbo Calle 80",
     dict(tipo="expense", monto=20000, comercio_en="Jumbo", clase="wallet")),
    ("monto_con_decimales", "com.nu.production", "Nu", "Pagaste $1.234.567,89 en Falabella",
     dict(tipo="expense", monto=1234567.89, comercio_en="Falabella")),
    # ── ruido: nunca es un movimiento ──
    ("otp", "com.nu.production", "Tu código", "Tu código es 123456, no lo compartas con nadie", None),
    ("promo", "com.nu.production", "Gana un 10% de descuento", "en tus compras de esta semana", None),
    ("sin_monto", "com.nequi.MobileApp", "Nequi", "Tu transferencia está en proceso", None),
    ("vacia", "com.nequi.MobileApp", "", "", None),
    ("inicio_sesion", "com.nequi.MobileApp", "Seguridad", "Detectamos un inicio de sesión en un nuevo dispositivo. Monto límite $500.000", None),
]


@pytest.mark.parametrize("id_,paquete,titulo,texto,esperado", CORPUS, ids=[c[0] for c in CORPUS])
def test_corpus(id_, paquete, titulo, texto, esperado):
    r = nt.interpretar(paquete, titulo, texto)
    if esperado is None:
        assert r is None
        return
    assert r is not None
    assert r.tipo == esperado["tipo"]
    assert r.monto == pytest.approx(esperado["monto"])
    if "comercio" in esperado:
        assert r.comercio == esperado["comercio"]
    if "comercio_en" in esperado:
        assert esperado["comercio_en"].lower() in r.comercio.lower()
    for campo in ("clase", "fuente", "tarjeta"):
        if campo in esperado:
            assert getattr(r, campo) == esperado[campo]


# ── endpoint ──
client = TestClient(app)


def _usuario(uid, clave, cuentas=("Nequi",)):
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", api_key=clave))
        for n in cuentas:
            db.add(Cuenta(usuario_id=uid, nombre=n, tipo="ahorro", saldo=0, moneda="COP"))
        db.commit()
    finally:
        db.close()


def _post(clave, **cuerpo):
    return client.post("/movimientos/rapido-notificacion", json=cuerpo, headers={"X-Api-Key": clave})


def test_una_notificacion_de_nequi_crea_un_movimiento_por_confirmar_en_la_cuenta_nequi():
    _usuario("na-1", "clave-na-1", cuentas=("Efectivo", "Nequi"))
    r = _post("clave-na-1", paquete="com.nequi.MobileApp", titulo="Nequi", texto="Pagaste $20.000 en JUMBO.", publicado_ms=1_790_000_000_000)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["registrado"] is True and j["por_confirmar"] is True and j["duplicado"] is False
    db = SessionLocal()
    try:
        m = db.query(Movimiento).filter(Movimiento.id == j["movimiento_id"]).one()
        cuenta = db.query(Cuenta).filter(Cuenta.id == m.cuenta_id).one()
        assert (m.tipo, m.monto, m.descripcion, cuenta.nombre) == ("expense", 20000, "Jumbo", "Nequi")
        assert cuenta.saldo == -20000  # el saldo se mueve de inmediato
    finally:
        db.close()


def test_el_mismo_aviso_dos_veces_no_crea_dos_movimientos():
    _usuario("na-2", "clave-na-2")
    cuerpo = dict(paquete="com.nequi.MobileApp", titulo="Nequi", texto="Pagaste $35.000 en Rappi", publicado_ms=1_790_000_100_000)
    a = _post("clave-na-2", **cuerpo).json()
    b = _post("clave-na-2", **cuerpo).json()
    assert a["registrado"] is True and b["duplicado"] is True and a["movimiento_id"] == b["movimiento_id"]
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == "na-2").count() == 1
    finally:
        db.close()


def test_un_codigo_de_seguridad_o_una_promo_se_ignoran_sin_error():
    _usuario("na-3", "clave-na-3")
    r = _post("clave-na-3", paquete="com.nu.production", titulo="Tu código", texto="Tu código es 482913, no lo compartas")
    assert r.status_code == 200 and r.json() == {"ok": True, "registrado": False, "motivo": "no_parece_un_movimiento"}
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == "na-3").count() == 0
    finally:
        db.close()


def test_recibir_plata_entra_como_ingreso():
    _usuario("na-4", "clave-na-4")
    j = _post("clave-na-4", paquete="com.nequi.MobileApp", titulo="Nequi", texto="Recibiste $100.000 de Maria Lopez").json()
    db = SessionLocal()
    try:
        m = db.query(Movimiento).filter(Movimiento.id == j["movimiento_id"]).one()
        assert m.tipo == "income" and m.monto == 100000
    finally:
        db.close()


def test_sin_clave_valida_no_entra():
    r = _post("clave-que-no-existe", paquete="x", titulo="Nequi", texto="Pagaste $1.000 en algo")
    assert r.status_code == 401


def test_la_lista_de_apps_viene_del_servidor():
    _usuario("na-5", "clave-na-5")
    r = client.get("/movimientos/notificaciones-apps", headers={"X-Api-Key": "clave-na-5"})
    assert r.status_code == 200
    paquetes = {p["paquete"] for p in r.json()["paquetes"]}
    assert "com.nequi.MobileApp" in paquetes and "com.google.android.apps.walletnfcrel" in paquetes
