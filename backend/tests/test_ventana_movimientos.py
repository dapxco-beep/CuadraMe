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
    """Como Gmail: `after:AAAA/MM/DD` deja los correos de esa fecha en adelante; `-filename:pdf` los sin partes."""

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
        asunto = re.search(r'subject:"([^"]*)"', q or "")
        solo_pdf = "has:attachment" in (q or "")

        def pasa(x):
            if datetime.utcfromtimestamp(int(x["internalDate"]) / 1000) < corte:
                return False
            if asunto and asunto.group(1).lower() not in x["payload"]["headers"][1]["value"].lower():
                return False
            tiene = bool(x["payload"]["parts"])
            return tiene if solo_pdf else (not tiene if "-filename:pdf" in q else True)

        ids = [i for i, x in self.mensajes.items() if pasa(x)]
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


def test_resumen_de_la_ultima_lectura_con_descartes_y_ceros_seguidos(monkeypatch):
    uid = "u-vent-5"
    ya = correo("r1", 5)
    publicidad = correo("r2", 6, asunto="Tu extracto está listo")
    nuevo = correo("r3", 7, asunto="Compraste con tu tarjeta Nu")
    g = GmailPorFecha([ya, publicidad, nuevo])
    conectar_usuario(uid, g, monkeypatch)
    _sync_mov(uid, datetime.utcnow() - timedelta(hours=1))
    _correr()
    lectura = client.get("/correos/carriles").json()["movimientos"]["ultima_lectura"]
    assert lectura["leidos"] == 3 and lectura["nuevos"] == 2
    assert lectura["avisos_descartados"] == 1 and lectura["ya_registrados"] == 0
    assert lectura["desde"] and lectura["ceros_seguidos"] == 0
    # Sin contenido de correos: solo cifras, fechas y el nombre genérico del motivo.
    assert "Nu" not in str(lectura) and "EXITO" not in str(lectura)
    g.mensajes.clear()
    _correr()
    assert client.get("/correos/carriles").json()["movimientos"]["ultima_lectura"]["ceros_seguidos"] == 1
    _correr()
    ult = client.get("/correos/carriles").json()["movimientos"]["ultima_lectura"]
    assert ult["leidos"] == 0 and ult["ceros_seguidos"] == 2


# ── Búsqueda manual de un MOVIMIENTO por asunto (correo del ICETEX) ──────────────────────────

ICETEX = "Pagaste con tu Cuenta de ahorros Nu"
CUERPO_ICETEX = "Pagaste en: ICETEX. La cantidad de: $1.000.000,00. Más el impuesto del 4xmil de: $0,00."


def _icetex(id_="ix1", hace_horas=24 * 20):
    m = mensaje(id_, REM, ICETEX, CUERPO_ICETEX)
    m["internalDate"] = str(int((datetime.utcnow() - timedelta(hours=hace_horas)).timestamp() * 1000))
    return m


def test_buscar_movimiento_por_asunto_sin_exigir_pdf_y_procesar_a_por_revisar(monkeypatch):
    uid = "u-vent-6"
    g = GmailPorFecha([_icetex(), correo("otro", 5, asunto="Promoción de verano")])
    conectar_usuario(uid, g, monkeypatch)
    r = client.post("/correos/extractos/buscar-asunto", json={"asunto": "Pagaste con tu Cuenta", "modo": "movimiento"})
    assert r.status_code == 200
    hallados = r.json()
    assert [h["gmail_msg_id"] for h in hallados] == ["ix1"] and hallados[0]["archivos"] == [] and not hallados[0]["ya_en_lista"]
    q = g.consultas[-1]
    assert 'subject:"Pagaste con tu Cuenta"' in q and "newer_than:365d" in q and "has:attachment" not in q
    p = client.post("/correos/extractos/buscar-asunto/procesar", json={"ids": ["ix1"], "modo": "movimiento"})
    assert p.status_code == 200 and p.json()["movimientos_nuevos"] == 1
    db = SessionLocal()
    try:
        c = db.query(CorreoGasto).filter_by(usuario_id=uid, gmail_msg_id="ix1").one()
        assert c.estado == "pendiente" and c.monto == 1_000_000 and c.tipo_sugerido == "expense"
        assert "icetex" in (c.comercio or "").lower()
    finally:
        db.close()
    # De nuevo: no duplica.
    p2 = client.post("/correos/extractos/buscar-asunto/procesar", json={"ids": ["ix1"], "modo": "movimiento"}).json()
    assert p2["movimientos_nuevos"] == 0 and p2["ya_en_lista"] == 1
    assert client.post("/correos/extractos/buscar-asunto", json={"asunto": ICETEX, "modo": "movimiento"}).json()[0]["ya_en_lista"]


def test_procesar_movimiento_descarta_avisos_y_respeta_el_interruptor(monkeypatch):
    uid = "u-vent-7"
    aviso = correo("av1", 5, asunto="Tu extracto está listo")
    g = GmailPorFecha([aviso])
    conectar_usuario(uid, g, monkeypatch)
    p = client.post("/correos/extractos/buscar-asunto/procesar", json={"ids": ["av1"], "modo": "movimiento"}).json()
    assert p["movimientos_nuevos"] == 0 and p["descartados"] == 1
    assert client.post("/correos/extractos/buscar-asunto/procesar", json={"ids": ["../x"], "modo": "movimiento"}).status_code == 400
    db = SessionLocal()
    try:
        from app.models import Perfil
        db.query(Perfil).filter_by(usuario_id=uid).update({Perfil.gmail_leer_movimientos: False})
        db.commit()
    finally:
        db.close()
    r = client.post("/correos/extractos/buscar-asunto", json={"asunto": "Pagaste", "modo": "movimiento"})
    assert r.status_code == 400


def test_modo_extracto_sigue_pidiendo_pdf(monkeypatch):
    g = GmailPorFecha([_icetex()])
    conectar_usuario("u-vent-8", g, monkeypatch)
    assert client.post("/correos/extractos/buscar-asunto", json={"asunto": "Pagaste con tu"}).json() == []
    assert "has:attachment" in g.consultas[-1]


def test_releer_60_dias_lee_mas_atras_y_solo_una_vez_por_hora(monkeypatch):
    uid = "u-vent-9"
    g = GmailPorFecha([_icetex("ix9", 24 * 40)])
    conectar_usuario(uid, g, monkeypatch)
    _sync_mov(uid, datetime.utcnow() - timedelta(hours=1))
    r = client.post("/correos/sincronizar?tipo=movimientos&completa=true&dias=60&releer=true").json()
    while r["ok"] and not r["completado"]:
        r = client.post("/correos/sincronizar?tipo=movimientos").json()
    assert r["ok"] and _ids(uid) == {"ix9"}
    again = client.post("/correos/sincronizar?tipo=movimientos&completa=true&dias=60&releer=true")
    assert again.status_code == 429
    assert client.post("/correos/sincronizar?tipo=movimientos").status_code == 200  # la lectura normal no se frena


def test_consulta_de_notificaciones_acepta_correos_con_imagenes_en_linea():
    from app import extractos_gmail as eg
    q = eg.construir_query_notificaciones()
    assert "-filename:pdf" in q and "-has:attachment" not in q
