"""Fecha del movimiento en los correos por aprobar: se lee del texto del banco, se muestra, se puede
corregir y es la que lleva el movimiento al aprobar. Gmail simulado; sin llamadas a Google."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'fecha_mov.db')}")

import pytest  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.gmail_extract import buscar_fecha_en_texto, extraer_fecha_movimiento, fecha_movimiento_info  # noqa: E402
from app.models import CorreoGasto, Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, client, conectar_usuario, mensaje  # noqa: E402

NEQUI = "Nequi <alertas@nequi.com.co>"
NU = "Nu Colombia <notificaciones@nu.com.co>"
# Llegó el 8 oct 2026 a las 21:30 hora Colombia (02:30 UTC del 9).
RECIBIDO = datetime(2026, 10, 9, 2, 30)


# ── Lectura pura ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto,esperado", [
    ("Enviaste de manera exitosa 45.500 a la llave @ana el 8 de octubre de 2026 a las 4:30 pm", datetime(2026, 10, 8, 16, 30)),
    ("Recibiste 30.000 de Ana el 3 de julio de 2026 a las 11:05 am", datetime(2026, 7, 3, 11, 5)),
    ("Pagaste en Rappi con Cuenta Nu el 08/10/2026 a las 16:05", datetime(2026, 10, 8, 16, 5)),
    ("Compra por $12.000 8-oct-2026 11:05 a. m.", datetime(2026, 10, 8, 11, 5)),
    ("Compra aprobada 08 oct 2026 12:10 p.m.", datetime(2026, 10, 8, 12, 10)),
    ("Compra aprobada 08 oct 2026 12:10 a.m.", datetime(2026, 10, 8, 0, 10)),
    ("Compra del 5 de octubre por $9.000", datetime(2026, 10, 5)),   # sin año: el más reciente que no sea futuro
    ("Compra el 2026-10-07 por $9.000", datetime(2026, 10, 7)),      # sin hora: queda a las 00:00
])
def test_lee_la_fecha_escrita_en_el_texto(texto, esperado):
    assert buscar_fecha_en_texto(texto, RECIBIDO) == esperado


@pytest.mark.parametrize("texto", [
    "Recibiste 30.000 de Ana",                                   # aviso sin fecha
    "Compra el 08/10/2026 y vence el 07/10/2026",                # dos fechas distintas: ambiguo
    "Pagaste 5.000 el 15/12/2026",                               # futura
    "Pagaste 5.000 el 15/12/2016",                               # de hace más de 5 años
    "Tu tarjeta vence 31/12/2027",                               # futura
    "Compra el 31/02/2026",                                      # no existe
])
def test_sin_fecha_creible_no_inventa(texto):
    assert buscar_fecha_en_texto(texto, RECIBIDO) is None
    assert extraer_fecha_movimiento(texto, RECIBIDO) == RECIBIDO  # respaldo: la fecha de recepción


def test_extraer_fecha_devuelve_utc_como_recibido_en():
    assert extraer_fecha_movimiento("Pagaste 5.000 el 3 de julio de 2026 a las 11:05 am", RECIBIDO) == datetime(2026, 7, 3, 16, 5)


# ── API ─────────────────────────────────────────────────────────────────────────────────

def _correo(uid, msg_id, remitente, asunto, snippet, recibido=RECIBIDO, fecha_mov=None):
    db = SessionLocal()
    try:
        c = CorreoGasto(usuario_id=uid, gmail_msg_id=msg_id, remitente=remitente, asunto=asunto, snippet=snippet,
                        monto=45500, comercio="Envío a Ana", categoria_sugerida="Otros", tipo_sugerido="expense",
                        estado="pendiente", recibido_en=recibido, fecha_movimiento=fecha_mov)
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


def _preparar(uid, monkeypatch, mensajes=()):
    conectar_usuario(uid, GmailFalso(list(mensajes), {}), monkeypatch)
    return client.post("/cuentas", json={"nombre": "Nequi", "saldo": 100000}).json()


def test_pendientes_trae_fecha_del_texto_y_la_de_llegada_aunque_el_correo_sea_viejo(monkeypatch):
    _preparar("fm-1", monkeypatch)
    _correo("fm-1", "a", NEQUI, "Enviaste 45.500", "Enviaste de manera exitosa 45.500 el 3 de octubre de 2026 a las 11:05 am")
    p = client.get("/correos/pendientes").json()[0]
    assert p["fecha_movimiento"] == "2026-10-03T11:05:00"      # hora Colombia, lista para mostrar
    assert p["fecha_del_texto"] is True and p["fecha_movimiento_con_hora"] is True
    assert p["recibido_en_co"] == "2026-10-08T21:30:00"        # cuándo llegó el correo, en hora Colombia


def test_aviso_sin_fecha_usa_la_de_recepcion(monkeypatch):
    _preparar("fm-2", monkeypatch)
    _correo("fm-2", "a", NU, "Pagaste en Rappi con Cuenta Nu", "Pagaste $45.500 en Rappi con tu Cuenta Nu")
    p = client.get("/correos/pendientes").json()[0]
    assert p["fecha_movimiento"] == p["recibido_en_co"] == "2026-10-08T21:30:00"
    assert p["fecha_del_texto"] is False


def test_orden_por_fecha_del_movimiento_descendente(monkeypatch):
    _preparar("fm-3", monkeypatch)
    _correo("fm-3", "viejo", NEQUI, "Enviaste", "Enviaste 45.500 el 2 de octubre de 2026 a las 8:00 am", recibido=datetime(2026, 10, 9, 3, 0))
    _correo("fm-3", "nuevo", NU, "Pagaste en Rappi", "Pagaste $45.500 en Rappi", recibido=datetime(2026, 10, 7, 15, 0))
    _correo("fm-3", "medio", NEQUI, "Recibiste", "Recibiste 45.500 de Ana el 5 de octubre de 2026 a las 9:00 am", recibido=datetime(2026, 10, 5, 20, 0))
    dias = [c["fecha_movimiento"][:10] for c in client.get("/correos/pendientes").json()]
    assert dias == ["2026-10-07", "2026-10-05", "2026-10-02"]


def test_aprobar_crea_el_movimiento_con_la_fecha_del_correo_no_la_de_lectura(monkeypatch):
    cuenta = _preparar("fm-4", monkeypatch)
    cid = _correo("fm-4", "a", NEQUI, "Enviaste", "Enviaste de manera exitosa 45.500 el 3 de octubre de 2026 a las 4:30 pm")
    r = client.post(f"/correos/{cid}/aprobar", json={"cuenta_id": cuenta["id"]})
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == "fm-4").one().fecha == datetime(2026, 10, 3, 16, 30)
    finally:
        db.close()


def test_aprobar_con_fecha_corregida(monkeypatch):
    cuenta = _preparar("fm-5", monkeypatch)
    cid = _correo("fm-5", "a", NU, "Pagaste en Rappi", "Pagaste $45.500 en Rappi")
    r = client.post(f"/correos/{cid}/aprobar", json={"cuenta_id": cuenta["id"], "fecha": "2026-10-06T21:30:00"})
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == "fm-5").one().fecha == datetime(2026, 10, 6, 21, 30)
    finally:
        db.close()


def test_fecha_corregida_futura_o_muy_antigua_se_rechaza(monkeypatch):
    cuenta = _preparar("fm-6", monkeypatch)
    cid = _correo("fm-6", "a", NU, "Pagaste en Rappi", "Pagaste $45.500 en Rappi")
    futura = (ahora_co() + timedelta(days=5)).isoformat()
    r = client.post(f"/correos/{cid}/aprobar", json={"cuenta_id": cuenta["id"], "fecha": futura})
    assert r.status_code == 400 and "futura" in r.json()["detail"]
    r = client.post(f"/correos/{cid}/aprobar", json={"cuenta_id": cuenta["id"], "fecha": "2015-01-01T00:00:00"})
    assert r.status_code == 400 and "antigua" in r.json()["detail"]
    assert client.get("/cuentas").json()[0]["saldo"] == 100000  # nada se movió
    assert client.get("/correos/pendientes").json()[0]["id"] == cid


def test_punto_de_partida_usa_la_fecha_del_movimiento(monkeypatch):
    _preparar("fm-7", monkeypatch)
    hoy = ahora_co()
    # Llegó ayer, pero el movimiento es de hace 40 días: con punto de partida de hace 10 días no sale.
    hace40 = hoy - timedelta(days=40)
    ayer = datetime.utcnow() - timedelta(days=1)
    _correo("fm-7", "a", NEQUI, "Enviaste", f"Enviaste 45.500 el {hace40:%d/%m/%Y} a las 10:00", recibido=ayer)
    _correo("fm-7", "b", NU, "Pagaste en Rappi", "Pagaste $45.500 en Rappi", recibido=ayer)
    assert len(client.get("/correos/pendientes").json()) == 2
    inicio = (hoy - timedelta(days=10)).date().isoformat()
    assert client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": inicio}).status_code == 200
    assert [c["asunto"] for c in client.get("/correos/pendientes").json()] == ["Pagaste en Rappi"]


def test_columna_guardada_manda_sobre_el_calculo_al_vuelo():
    c = CorreoGasto(asunto="Enviaste", snippet="Enviaste 5.000 el 3 de octubre de 2026 a las 11:05 am",
                    recibido_en=RECIBIDO, fecha_movimiento=datetime(2026, 10, 6, 15, 0))
    assert fecha_movimiento_info(c)["fecha"] == datetime(2026, 10, 6, 10, 0)


def test_al_sincronizar_se_guarda_la_fecha_del_texto(monkeypatch):
    uid = "fm-8"
    msg = mensaje("g1", NEQUI, "Enviaste", "Enviaste de manera exitosa 45.500 el 3 de septiembre de 2026 a las 4:30 pm")
    _preparar(uid, monkeypatch, [msg])
    client.post("/correos/sincronizar")
    db = SessionLocal()
    try:
        c = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid).one()
        assert c.fecha_movimiento == datetime(2026, 9, 3, 21, 30)   # 16:30 Colombia = 21:30 UTC
    finally:
        db.close()
