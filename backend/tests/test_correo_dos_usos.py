"""El correo en DOS usos independientes: «Movimientos del día a día» (notificaciones) y «Extractos
para conciliar» (PDF). Carriles, preferencias, minimización, cron y orden de llegada. Gmail simulado."""
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'dos_usos.db')}")

import pytest  # noqa: E402

from app import duplicados as dup  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Consentimiento, CorreoGasto, ExtractoCorreo, Movimiento, Perfil, SyncGmail  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, _gmail_de_prueba, client, conectar_usuario  # noqa: E402

CRON = {"X-Cron-Secret": "secreto-de-prueba"}


class GmailContado(GmailFalso):
    """Cuenta qué se pidió a Gmail: la minimización se prueba mirando lo que NUNCA se descargó."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.adjuntos_pedidos = 0
        self.mensajes_leidos = 0

    def get(self, userId, id=None, messageId=None, format=None):  # noqa: N803
        if messageId:
            self.adjuntos_pedidos += 1
        else:
            self.mensajes_leidos += 1
        return super().get(userId, id=id, messageId=messageId, format=format)


def _gmail():
    g = _gmail_de_prueba()
    c = GmailContado([], {})
    c.mensajes, c.adjuntos = g.mensajes, g.adjuntos
    return c


def _uid():
    return f"u-dosusos-{uuid.uuid4().hex[:8]}"


def _filas(uid):
    db = SessionLocal()
    try:
        return (db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid).count(),
                db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == uid, ExtractoCorreo.estado != "ignorado").count())
    finally:
        db.close()


def _lectura(**kw):
    r = client.put("/correos/gmail/lectura", json=kw)
    assert r.status_code == 200, r.text
    return r.json()


def test_por_defecto_ambos_activos_y_todo_se_comporta_como_siempre(monkeypatch):
    uid = _uid()
    conectar_usuario(uid, _gmail(), monkeypatch)
    e = client.get("/correos/gmail/estado").json()
    assert e["leer_movimientos"] is True and e["leer_extractos"] is True
    r = client.post("/correos/sincronizar").json()  # sin `tipo`
    assert r["ok"] and r["nuevos"] == 1 and r["extractos_nuevos"] == 2 and r["tipo"] == "todo"
    assert r["movimientos_leidos"] >= 1 and r["extractos_leidos"] >= 3


def test_tipo_movimientos_no_toca_extractos_ni_adjuntos(monkeypatch):
    uid = _uid()
    g = _gmail()
    conectar_usuario(uid, g, monkeypatch)
    r = client.post("/correos/sincronizar?tipo=movimientos").json()
    assert r["ok"] and r["nuevos"] == 1 and r["extractos_nuevos"] == 0 and r["tipo"] == "movimientos"
    assert _filas(uid)[1] == 0 and _filas(uid)[0] >= 1
    assert g.adjuntos_pedidos == 0


def test_tipo_extractos_no_guarda_notificaciones(monkeypatch):
    uid = _uid()
    conectar_usuario(uid, _gmail(), monkeypatch)
    r = client.post("/correos/sincronizar?tipo=extractos").json()
    assert r["ok"] and r["extractos_nuevos"] == 2 and r["nuevos"] == 0 and r["tipo"] == "extractos"
    assert _filas(uid)[0] == 0
    assert client.get("/correos/pendientes").json() == []


def test_tipo_invalido_se_rechaza(monkeypatch):
    conectar_usuario(_uid(), _gmail(), monkeypatch)
    assert client.post("/correos/sincronizar?tipo=otra").status_code == 422


def test_extractos_apagado_no_descarga_ni_guarda_adjuntos(monkeypatch):
    uid = _uid()
    g = _gmail()
    conectar_usuario(uid, g, monkeypatch)
    assert _lectura(leer_extractos=False) == {"ok": True, "leer_movimientos": True, "leer_extractos": False}
    r = client.post("/correos/sincronizar").json()  # `todo`, pero solo corre el carril encendido
    assert r["ok"] and r["nuevos"] == 1 and r["extractos_nuevos"] == 0
    assert _filas(uid)[1] == 0 and g.adjuntos_pedidos == 0
    # Pedirlo explícitamente tampoco lee nada.
    r = client.post("/correos/sincronizar?tipo=extractos").json()
    assert r["ok"] and r["aviso"] and g.adjuntos_pedidos == 0 and _filas(uid)[1] == 0
    # Ni conciliar ni probar clave bajan adjuntos con el carril apagado.
    assert client.post("/correos/extractos/x/conciliar", json={}).status_code in (400, 404, 422)


def test_movimientos_apagado_no_guarda_notificaciones(monkeypatch):
    uid = _uid()
    conectar_usuario(uid, _gmail(), monkeypatch)
    _lectura(leer_movimientos=False)
    r = client.post("/correos/sincronizar").json()
    assert r["ok"] and r["nuevos"] == 0 and r["extractos_nuevos"] == 2
    assert _filas(uid)[0] == 0


def test_ambos_apagados_no_se_lee_nada(monkeypatch):
    uid = _uid()
    g = _gmail()
    conectar_usuario(uid, g, monkeypatch)
    llamadas = []
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda t: llamadas.append(t) or g)
    _lectura(leer_movimientos=False, leer_extractos=False)
    for tipo in ("todo", "movimientos", "extractos"):
        r = client.post(f"/correos/sincronizar?tipo={tipo}").json()
        assert r["ok"] and r["aviso"] and r["completado"] and r["nuevos"] == 0
    assert llamadas == [] and g.mensajes_leidos == 0 and _filas(uid) == (0, 0)


def test_la_preferencia_parcial_no_cambia_la_otra(monkeypatch):
    conectar_usuario(_uid(), _gmail(), monkeypatch)
    _lectura(leer_extractos=False)
    assert _lectura(leer_movimientos=False) == {"ok": True, "leer_movimientos": False, "leer_extractos": False}
    assert _lectura(leer_extractos=True)["leer_movimientos"] is False


def test_ultima_vez_y_contadores_por_carril(monkeypatch):
    uid = _uid()
    conectar_usuario(uid, _gmail(), monkeypatch)
    client.post("/correos/sincronizar?tipo=movimientos")
    c = client.get("/correos/carriles").json()
    assert c["movimientos"]["ultima_vez"] and c["extractos"]["ultima_vez"] is None
    assert c["movimientos"]["por_revisar"] == 1 and c["movimientos"]["nuevos"] == 1
    assert c["extractos"]["encontrados"] == 0
    client.post("/correos/sincronizar?tipo=extractos")
    c = client.get("/correos/carriles").json()
    assert c["extractos"]["ultima_vez"] and c["extractos"]["encontrados"] == 2
    assert c["extractos"]["con_clave_pendiente"] == 1 and c["extractos"]["nuevos"] == 2
    # Los contadores de movimientos no se borraron al leer extractos.
    assert c["movimientos"]["nuevos"] == 1 and c["movimientos"]["por_revisar"] == 1
    assert c["movimientos"]["activo"] and c["extractos"]["activo"]


def test_un_carril_nunca_leido_usa_la_ventana_larga(monkeypatch):
    """Leer solo movimientos no marca los extractos como al día: si se activan después, se lee todo lo anterior."""
    uid = _uid()
    conectar_usuario(uid, _gmail(), monkeypatch)
    client.post("/correos/sincronizar?tipo=movimientos")
    db = SessionLocal()
    try:
        s = db.query(SyncGmail).filter(SyncGmail.usuario_id == uid).first()
        assert s.ultima_sync_mov and s.ultima_sync_ext is None and s.tipo == "movimientos"
        s0 = s.ultima_sync_mov
    finally:
        db.close()
    r = client.post("/correos/sincronizar?tipo=extractos").json()
    assert r["extractos_nuevos"] == 2  # se leyó desde atrás, no solo desde la última vez de movimientos
    db = SessionLocal()
    try:
        s = db.query(SyncGmail).filter(SyncGmail.usuario_id == uid).first()
        assert s.ultima_sync_ext and s.ultima_sync_mov == s0
    finally:
        db.close()


def test_datos_de_antes_sin_marcas_por_carril_siguen_incrementales(monkeypatch):
    uid = _uid()
    conectar_usuario(uid, _gmail(), monkeypatch)
    client.post("/correos/sincronizar")
    db = SessionLocal()
    try:
        s = db.query(SyncGmail).filter(SyncGmail.usuario_id == uid).first()
        s.ultima_sync_mov = s.ultima_sync_ext = None  # como una fila anterior a los carriles
        db.commit()
        base = s.ultima_sync
    finally:
        db.close()
    client.post("/correos/sincronizar?tipo=movimientos")
    db = SessionLocal()
    try:
        s = db.query(SyncGmail).filter(SyncGmail.usuario_id == uid).first()
        assert s.ultima_sync_ext == base  # se heredó la marca general, no se perdió
    finally:
        db.close()


def test_orden_de_llegada_correo_primero_luego_el_extracto_lo_confirma(monkeypatch):
    uid = _uid()
    conectar_usuario(uid, _gmail(), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 1000}).json()
    client.post("/correos/sincronizar?tipo=movimientos")
    pend = client.get("/correos/pendientes").json()
    assert client.post(f"/correos/{pend[0]['id']}/aprobar", json={"cuenta_id": cuenta["id"]}).status_code == 200
    c = client.get("/correos/carriles").json()
    assert c["movimientos"]["provisionales"] == 1 and c["movimientos"]["por_revisar"] == 0
    # Llega el extracto y trae la misma compra: se junta con la provisional (no se duplica) y la confirma.
    db = SessionLocal()
    try:
        m = db.query(Movimiento).filter(Movimiento.usuario_id == uid).one()
        dup.confirmar_por_canal(db, m, dup.ORIGEN_EXTRACTO, "ext:prueba")
        m.conciliado_en = datetime.utcnow()
        db.commit()
        assert db.query(Movimiento).filter(Movimiento.usuario_id == uid).count() == 1
    finally:
        db.close()
    assert client.get("/correos/carriles").json()["movimientos"]["provisionales"] == 0


def test_orden_de_llegada_extracto_primero_luego_la_notificacion_no_duplica(monkeypatch):
    uid = _uid()
    conectar_usuario(uid, _gmail(), monkeypatch)
    cuenta = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 1000}).json()
    client.post("/correos/sincronizar?tipo=extractos")
    # Un movimiento ya respaldado por el extracto (misma compra de 45.000).
    db = SessionLocal()
    try:
        m = Movimiento(usuario_id=uid, cuenta_id=cuenta["id"], tipo="expense", monto=45000, descripcion="EXITO",
                       categoria="Otros", fecha=datetime.utcfromtimestamp(1790000000), fuente="conciliacion_extracto")
        db.add(m)
        db.flush()
        dup.nuevo_movimiento(db, m, dup.ORIGEN_EXTRACTO, "ext:1")
        m.conciliado_en = datetime.utcnow()
        db.commit()
    finally:
        db.close()
    r = client.post("/correos/sincronizar?tipo=movimientos").json()
    assert r["ok"]
    # La notificación equivalente no queda «por revisar»: ya la respalda el extracto.
    assert client.get("/correos/pendientes").json() == []
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == uid).count() == 1
    finally:
        db.close()


# ── Cron ──────────────────────────────────────────────────────────────────────
def _cron_usuario(gmails, gmail, **prefs):
    uid = f"cron2-{uuid.uuid4().hex[:8]}"
    token = f"tok-{uid}"
    gmails[token] = gmail
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc=token,
                      gmail_email="x@gmail.com", **prefs))
        ahora = datetime.utcnow()
        db.add(Consentimiento(usuario_id=uid, version="1.1", finalidad="lectura_correo", aceptado=True,
                              creado_en_utc=ahora, creado_en_co=ahora))
        db.commit()
    finally:
        db.close()
    return uid


@pytest.fixture()
def cron(monkeypatch):
    from cryptography.fernet import Fernet

    from app.config import settings

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    db = SessionLocal()
    try:
        db.query(Perfil).update({Perfil.gmail_conectado: False})
        db.commit()
    finally:
        db.close()
    gmails: dict = {}
    llamadas: list = []
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda t: llamadas.append(t) or gmails[t])
    monkeypatch.setattr(router_correos, "enviar_push", lambda *a, **k: 1)
    return gmails, llamadas


def test_cron_respeta_las_preferencias_de_cada_usuario(cron):
    gmails, llamadas = cron
    g_solo_mov, g_solo_ext, g_nada, g_todo = _gmail(), _gmail(), _gmail(), _gmail()
    u1 = _cron_usuario(gmails, g_solo_mov, gmail_leer_extractos=False)
    u2 = _cron_usuario(gmails, g_solo_ext, gmail_leer_movimientos=False)
    u3 = _cron_usuario(gmails, g_nada, gmail_leer_movimientos=False, gmail_leer_extractos=False)
    u4 = _cron_usuario(gmails, g_todo)
    r = client.post("/correos/cron/sincronizar", headers=CRON).json()
    assert r["ok"] and r["apagados"] == 1
    assert _filas(u1)[1] == 0 and _filas(u1)[0] >= 1 and g_solo_mov.adjuntos_pedidos == 0
    assert _filas(u2)[0] == 0 and _filas(u2)[1] == 2
    assert _filas(u3) == (0, 0) and g_nada.mensajes_leidos == 0
    assert _filas(u4)[1] == 2 and _filas(u4)[0] >= 1
    assert f"tok-{u3}" not in llamadas
