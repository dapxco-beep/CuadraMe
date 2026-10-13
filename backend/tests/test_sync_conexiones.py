"""
Sincronización de Gmail por lotes (paginación, reanudación, incremental) y
tablero GET /conexiones/estado, con Gmail simulado: ninguna prueba llama a Google.
"""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'sync.db')}")

import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Perfil, SyncGmail  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, mensaje  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    yield


def conectar(uid, gmail, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="P")
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True,
                      gmail_refresh_token_enc="x", gmail_email="x@gmail.com"))
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: gmail)


def notificaciones(n, prefijo="n"):
    return [
        mensaje(f"{prefijo}{i}", "Bancolombia <alertas@alertas.bancolombia.com.co>", "Compra aprobada",
                f"Compra por $1{i:03d}00 en COMERCIO{i} con tu tarjeta")
        for i in range(n)
    ]


def sincronizar_hasta_el_final(**params):
    """Repite la llamada como lo hace la app. Devuelve (respuestas)."""
    respuestas = []
    for _ in range(50):
        r = client.post("/correos/sincronizar", params=params).json()
        respuestas.append(r)
        assert r["ok"], r
        if r["completado"]:
            return respuestas
        params = {k: v for k, v in params.items() if k != "completa"}
    raise AssertionError("no terminó")


def test_120_correos_en_varias_paginas_por_lotes_sin_duplicar(monkeypatch):
    gmail = GmailFalso(notificaciones(120), {})
    conectar("u-sync120", gmail, monkeypatch)
    resp = sincronizar_hasta_el_final()
    # 120 correos, lotes de 40: 3 llamadas de lectura (+1 que cierra las demás fases).
    assert 3 <= len(resp) <= 4
    assert all(not r["completado"] for r in resp[:-1])
    assert [r["leidos"] for r in resp[:3]] == [40, 80, 120]
    assert resp[0]["total_estimado"] == 120 and resp[0]["pendientes"] > 0
    final = resp[-1]
    assert final["completado"] and final["pendientes"] == 0
    assert final["leidos"] == 120 and final["nuevos"] == 120
    assert len(client.get("/correos/pendientes").json()) == 120
    # Primera vez: ventana de 90 días.
    assert any("after:" in q for q in gmail.consultas)

    # Volver a sincronizar (incremental) no duplica nada.
    r = sincronizar_hasta_el_final()[-1]
    assert r["nuevos"] == 0 and r["omitidos"] == 120
    assert len(client.get("/correos/pendientes").json()) == 120


def test_reanuda_a_mitad_despues_de_un_corte(monkeypatch):
    gmail = GmailFalso(notificaciones(120), {})
    conectar("u-reanuda", gmail, monkeypatch)
    r1 = client.post("/correos/sincronizar").json()
    assert r1["leidos"] == 40 and not r1["completado"]
    db = SessionLocal()
    try:
        s = db.query(SyncGmail).filter(SyncGmail.usuario_id == "u-reanuda").first()
        assert s.en_curso and s.leidos == 40  # el cursor quedó guardado
    finally:
        db.close()
    # "Cierra la app" y vuelve más tarde: sigue desde el 41, no desde cero.
    r2 = client.post("/correos/sincronizar").json()
    assert r2["leidos"] == 80
    assert len(client.get("/correos/pendientes").json()) == 80
    final = sincronizar_hasta_el_final()[-1]
    assert final["leidos"] == 120 and final["nuevos"] == 120
    assert len(client.get("/correos/pendientes").json()) == 120


def test_incremental_usa_la_ultima_sync_con_solape_de_un_dia(monkeypatch):
    gmail = GmailFalso(notificaciones(3), {})
    conectar("u-incr", gmail, monkeypatch)
    sincronizar_hasta_el_final()
    db = SessionLocal()
    try:
        s = db.query(SyncGmail).filter(SyncGmail.usuario_id == "u-incr").first()
        assert s.ultima_sync and not s.en_curso
        s.ultima_sync = datetime.utcnow() - timedelta(days=5)
        s.ultima_sync_mov = s.ultima_sync_ext = s.ultima_sync  # la «última vez» vive ahora por carril
        db.commit()
        esperado = (s.ultima_sync - timedelta(days=1)).strftime("%Y/%m/%d")
    finally:
        db.close()
    gmail.consultas.clear()
    gmail.mensajes.update({m["id"]: m for m in notificaciones(2, "nuevo")})
    r = sincronizar_hasta_el_final()[-1]
    assert r["nuevos"] == 2
    assert any(f"after:{esperado}" in q for q in gmail.consultas)
    # `completa=true` vuelve a la ventana larga de 90 días.
    gmail.consultas.clear()
    sincronizar_hasta_el_final(completa="true")
    assert any(f"after:{(datetime.utcnow() - timedelta(days=90)).strftime('%Y/%m/%d')}" in q for q in gmail.consultas)


def test_error_a_mitad_conserva_el_cursor_y_no_filtra_detalles(monkeypatch):
    class Falla(GmailFalso):
        fallar = False

        def get(self, userId, id=None, messageId=None, format=None):  # noqa: N803
            if self.fallar:
                raise RuntimeError("token=secreto")
            return super().get(userId, id, messageId, format)

    gmail = Falla(notificaciones(60), {})
    conectar("u-falla", gmail, monkeypatch)
    assert client.post("/correos/sincronizar").json()["leidos"] == 40
    gmail.fallar = True
    r = client.post("/correos/sincronizar").json()
    assert r["ok"] is False and "secreto" not in str(r)
    gmail.fallar = False
    final = sincronizar_hasta_el_final()[-1]
    assert final["leidos"] == 60 and len(client.get("/correos/pendientes").json()) == 60


def test_lista_con_filtros_y_paginacion(monkeypatch):
    mensajes = notificaciones(5) + [
        mensaje("pub", "Bancolombia <promo@bancolombia.com.co>", "Gana premios", "Participa y gana"),
    ]
    conectar("u-lista", GmailFalso(mensajes, {}), monkeypatch)
    sincronizar_hasta_el_final()
    p1 = client.get("/correos/lista", params={"filtro": "nuevos", "limite": 3}).json()
    p2 = client.get("/correos/lista", params={"filtro": "nuevos", "limite": 3, "offset": 3}).json()
    assert len(p1) == 3 and len(p2) == 2 and not {c["id"] for c in p1} & {c["id"] for c in p2}
    ign = client.get("/correos/lista", params={"filtro": "ignorados"}).json()
    assert [c["asunto"] for c in ign] == ["Gana premios"]
    assert client.get("/correos/lista", params={"filtro": "raro"}).status_code == 422


def test_conexiones_estado_gmail_atajo_y_semaforos(monkeypatch):
    gmail = GmailFalso(notificaciones(2), {})
    uid = "u-conex"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="c@t.com", nombre="C")
    # Sin nada conectado: ámbar, sin errores.
    e = client.get("/conexiones/estado").json()
    assert e["gmail"]["conectado"] is False and e["gmail"]["semaforo"] == "ambar"
    assert e["atajo"]["semaforo"] == "ambar" and e["atajo"]["ultimo_uso"] is None
    assert "api_key" not in str(e)  # nunca se devuelve la clave

    conectar(uid, gmail, monkeypatch)
    sincronizar_hasta_el_final()
    e = client.get("/conexiones/estado").json()
    assert e["gmail"]["semaforo"] == "verde" and e["gmail"]["notificaciones"] == 2
    assert e["gmail"]["correos_leidos"] == 2 and e["gmail"]["ultima_sync"]

    # Sincronización vieja: ámbar.
    db = SessionLocal()
    try:
        s = db.query(SyncGmail).filter(SyncGmail.usuario_id == uid).first()
        s.ultima_sync = datetime.utcnow() - timedelta(days=4)
        db.commit()
    finally:
        db.close()
    assert client.get("/conexiones/estado").json()["gmail"]["semaforo"] == "ambar"

    # Atajo: usar la API key registra el último uso y cuenta el movimiento.
    cuenta = client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 1000}).json()
    assert cuenta["id"]
    clave = client.get("/perfil/api-key").json()["api_key"]
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": clave},
                    json={"monto": 5000, "tipo": "expense", "descripcion": "Prueba", "fuente": "shortcut"})
    assert r.status_code == 200, r.text
    a = client.get("/conexiones/estado").json()["atajo"]
    assert a["semaforo"] == "verde" and a["ultimo_uso"] and a["movimientos_7d"] == 1

    # Clave nueva: el último uso se reinicia.
    client.post("/perfil/api-key/regenerar")
    a = client.get("/conexiones/estado").json()["atajo"]
    assert a["ultimo_uso"] is None and a["semaforo"] == "ambar"


def test_conexiones_conciliacion_por_cuenta():
    uid = "u-conex-conc"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="c@t.com", nombre="C")
    cuenta = client.post("/cuentas", json={"nombre": "Ahorros", "saldo": 0}).json()
    from app.models import HistorialExtracto
    db = SessionLocal()
    try:
        db.add(HistorialExtracto(usuario_id=uid, cuenta_id=cuenta["id"], banco_detectado="bancolombia",
                                 total_movimientos=10, exactos=6, aproximados=1, faltantes=3,
                                 review_json="[]"))
        db.commit()
    finally:
        db.close()
    c = client.get("/conexiones/estado").json()["conciliacion"]
    fila = c["cuentas"][0]
    assert fila["cruzados"] == 7 and fila["faltantes"] == 3 and fila["ultimo_cruce"]
    assert c["semaforo"] == "ambar"
