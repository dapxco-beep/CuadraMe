"""Ventana solapada del carril de movimientos, con Gmail simulado que SÍ filtra por la fecha de `after:`.
Todo sintético."""
import os
import re
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'ventana.db')}")

import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402

from app import punto_partida  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import CorreoGasto, SyncGmail  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, _Llamada, client, conectar_usuario, mensaje  # noqa: E402

REM = "Nu <nu@nu.com.co>"


def correo(id_, hace_horas, asunto="Pagaste con tu Cuenta de ahorros Nu", monto="45.000"):
    m = mensaje(id_, REM, asunto, f"Pagaste en: EXITO. La cantidad de: ${monto},00")
    m["internalDate"] = str(int((datetime.utcnow() - timedelta(hours=hace_horas)).timestamp() * 1000))
    return m


class GmailPorFecha(GmailFalso):
    """Como Gmail: `after:AAAA/MM/DD` deja los correos de esa fecha en adelante; `-has:attachment` los sin partes."""

    def __init__(self, mensajes, falla=False):
        super().__init__(mensajes, {})
        self.falla = falla

    def get(self, userId, id=None, messageId=None, format=None):  # noqa: N803
        if self.falla:
            raise RuntimeError("Gmail caído")
        return super().get(userId, id, messageId, format)

    def list(self, userId, q=None, labelIds=None, maxResults=25, pageToken=None):  # noqa: N803
        if q is None and labelIds is None:
            return super().list(userId, q, labelIds, maxResults, pageToken)
        self.consultas.append(q)
        m = re.search(r"after:(\d{4})/(\d{2})/(\d{2})", q or "")
        corte = datetime(*map(int, m.groups())) if m else datetime.min
        ids = [i for i, x in self.mensajes.items()
               if datetime.utcfromtimestamp(int(x["internalDate"]) / 1000) >= corte and not x["payload"]["parts"]]
        if labelIds:
            ids = [i for i in ids if labelIds[0] in self.mensajes[i]["labelIds"]]
        ini = int(pageToken or 0)
        resp = {"messages": [{"id": i} for i in ids[ini:ini + maxResults]], "resultSizeEstimate": len(ids)}
        if ini + maxResults < len(ids):
            resp["nextPageToken"] = str(ini + maxResults)
        return _Llamada(resp)


@pytest.fixture(autouse=True)
def _clave(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())


def _sync_mov(uid, ultima):
    db = SessionLocal()
    try:
        db.add(SyncGmail(usuario_id=uid, ultima_sync=ultima, ultima_sync_mov=ultima, ultima_sync_ext=ultima))
        db.commit()
    finally:
        db.close()


def _correr(tipo="movimientos"):
    for _ in range(10):
        r = client.post(f"/correos/sincronizar?tipo={tipo}").json()
        if r.get("completado") or not r.get("ok"):
            return r
    raise AssertionError("no terminó")


def _ids(uid):
    db = SessionLocal()
    try:
        return {c.gmail_msg_id for c in db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid).all()}
    finally:
        db.close()


def test_correo_de_antes_de_la_ultima_sync_entra_y_no_se_duplica(monkeypatch):
    uid = "u-vent-1"
    # Llegó hace 2,5 días y la última sincronización fue hace 2 horas: con solo 1 día de solape se perdía.
    g = GmailPorFecha([correo("a1", 60), correo("a2", 5, asunto="Compraste con tu tarjeta Nu")])
    conectar_usuario(uid, g, monkeypatch)
    _sync_mov(uid, datetime.utcnow() - timedelta(hours=2))
    r = _correr()
    assert r["ok"] and _ids(uid) == {"a1", "a2"}
    assert any("after:" in q for q in g.consultas)
    r2 = _correr()  # segunda corrida: mismos correos, ninguno nuevo
    assert r2["nuevos"] == 0 and _ids(uid) == {"a1", "a2"}


def test_la_ventana_minima_son_3_dias_pero_no_mas_atras(monkeypatch):
    uid = "u-vent-2"
    g = GmailPorFecha([correo("v1", 24 * 6)])  # de hace 6 días: fuera de la ventana incremental
    conectar_usuario(uid, g, monkeypatch)
    _sync_mov(uid, datetime.utcnow() - timedelta(hours=1))
    _correr()
    assert _ids(uid) == set()
    hoy = datetime.utcnow().date()
    esperado = (datetime.utcnow() - timedelta(days=3)).strftime("%Y/%m/%d")
    assert any(f"after:{esperado}" in q for q in g.consultas), g.consultas
    assert hoy  # silencia linter


def test_corrida_fallida_no_avanza_ultima_sync(monkeypatch):
    uid = "u-vent-3"
    antes = datetime.utcnow() - timedelta(days=1)
    g = GmailPorFecha([correo("f1", 10)], falla=True)
    conectar_usuario(uid, g, monkeypatch)
    _sync_mov(uid, antes)
    r = _correr()
    assert r["ok"] is False
    db = SessionLocal()
    try:
        s = db.query(SyncGmail).filter_by(usuario_id=uid).one()
        assert s.ultima_sync_mov == antes and s.ultima_sync == antes and s.ultimo_error
    finally:
        db.close()
    g.falla = False  # Gmail vuelve: reanuda y entra
    assert _correr()["ok"] and _ids(uid) == {"f1"}


def test_punto_de_partida_hoy_no_lee_antes_de_su_fecha(monkeypatch):
    uid = "u-vent-4"
    g = GmailPorFecha([correo("p1", 24 * 2)])
    conectar_usuario(uid, g, monkeypatch)
    db = SessionLocal()
    try:
        punto_partida.guardar(db, uid, "hoy", datetime.utcnow().date())
        db.commit()
    finally:
        db.close()
    _sync_mov(uid, datetime.utcnow() - timedelta(hours=1))
    _correr()
    assert _ids(uid) == set()
    assert all(f"after:{datetime.utcnow():%Y/%m/%d}" in q for q in g.consultas if "after:" in q)
