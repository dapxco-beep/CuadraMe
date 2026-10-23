"""Alerta de mes que deja de cuadrar: si una cuenta que cuadraba pasa a no cuadrar, queda UN aviso interno (evento de actividad,
sin push ni correo, sin montos) y no se repite para el mismo mes. Datos 100 % inventados."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cuadre_roto.db')}")

import pytest  # noqa: E402

from app import autoarreglo as aa  # noqa: E402
from app import avisos, cierre_extractos  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Cuenta, Perfil  # noqa: E402
from app.models_avisos import EventoActividad  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(avisos, "SINCRONO", True)
    avisos.reiniciar_para_pruebas()
    pushes, correos = [], []
    monkeypatch.setattr(avisos, "enviar_push", lambda *a, **k: pushes.append(a) or 1)
    monkeypatch.setattr(avisos, "_enviar_correo", lambda *a, **k: correos.append(a) or True)
    yield {"pushes": pushes, "correos": correos}


def _cuenta(uid, nombre="Banco Ejemplo A Ahorros"):
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free")) if not db.query(Perfil).filter_by(usuario_id=uid).first() else None
        c = Cuenta(usuario_id=uid, nombre=nombre, tipo="ahorro", saldo=0)
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


def _c(cid, estado, mes=None):
    return {"cuenta_id": cid, "cuenta": "Banco Ejemplo A Ahorros", "estado": estado, "primer_mes_malo": mes, "meses": 2}


def _avisar(uid, *lecturas):
    db = SessionLocal()
    try:
        return aa.avisar_cuadre_roto(db, uid, list(lecturas))
    finally:
        db.close()


def _eventos(uid):
    db = SessionLocal()
    try:
        return db.query(EventoActividad).filter_by(usuario_id=uid, tipo="cuadre_dejo_de_cuadrar").all()
    finally:
        db.close()


def _marca(uid, cid):
    db = SessionLocal()
    try:
        m = db.query(MarcaCron).filter_by(usuario_id=uid, clave=aa.PREFIJO_CUADRE + cid).first()
        return m.valor if m else None
    finally:
        db.close()


def test_pasar_de_cuadra_a_no_cuadra_avisa_una_sola_vez_por_mes(_ambiente):
    uid, cid = "c-1", _cuenta("c-1")
    assert _avisar(uid, _c(cid, "cuadra")) == 0 and _marca(uid, cid) == "cuadra"  # la primera lectura solo se anota
    assert _avisar(uid, _c(cid, "cuadra")) == 0
    assert _avisar(uid, _c(cid, "no_cuadra", "2026-08")) == 1
    ev = _eventos(uid)
    assert len(ev) == 1 and ev[0].clave_unica == f"cuadre_roto:{uid}:{cid}:2026-08"
    assert json.loads(ev[0].meta) == {"cuenta_id": cid, "mes": "2026-08"}
    assert "$" not in ev[0].resumen  # sin montos
    assert _marca(uid, cid) == "no_cuadra|2026-08"
    assert _avisar(uid, _c(cid, "no_cuadra", "2026-08")) == 0  # sigue sin cuadrar: no repite
    # vuelve a cuadrar y se rompe OTRA VEZ en el mismo mes: el aviso de ese mes no se repite
    assert _avisar(uid, _c(cid, "cuadra")) == 0
    _avisar(uid, _c(cid, "no_cuadra", "2026-08"))
    assert len(_eventos(uid)) == 1
    # pero otro mes sí avisa
    _avisar(uid, _c(cid, "cuadra"))
    _avisar(uid, _c(cid, "no_cuadra", "2026-09"))
    assert len(_eventos(uid)) == 2
    assert not _ambiente["pushes"] and not _ambiente["correos"]  # no se envía nada nuevo: solo el aviso interno


def test_una_cuenta_que_nunca_cuadro_no_avisa():
    uid, cid = "c-2", _cuenta("c-2")
    assert _avisar(uid, _c(cid, "no_cuadra", "2026-07")) == 0
    assert _avisar(uid, _c(cid, "no_cuadra", "2026-08")) == 0
    assert _eventos(uid) == [] and _marca(uid, cid) == "no_cuadra|2026-08"


def test_cada_cuenta_y_cada_usuario_van_por_separado():
    a, b, otro = _cuenta("c-3"), _cuenta("c-3", "Banco Ejemplo B Ahorros"), _cuenta("c-4")
    _avisar("c-3", _c(a, "cuadra"), _c(b, "cuadra"))
    _avisar("c-4", _c(otro, "cuadra"))
    assert _avisar("c-3", _c(a, "no_cuadra", "2026-08"), _c(b, "cuadra")) == 1
    assert len(_eventos("c-3")) == 1 and _eventos("c-4") == []


def test_el_paso_cuadre_del_autoarreglo_lo_dispara(monkeypatch):
    uid, cid = "c-5", _cuenta("c-5")
    lecturas = iter([[_c(cid, "cuadra")], [_c(cid, "no_cuadra", "2026-08")]])
    monkeypatch.setattr(cierre_extractos, "cuadre_por_cuenta", lambda db, u: next(lecturas))
    for _ in range(2):
        db = SessionLocal()
        try:
            r = aa.correr(db, uid)
        finally:
            db.close()
    paso = next(p for p in r["pasos"] if p["paso"] == "cuadre")
    assert paso["estado"] == "ok" and paso["alertas"] == 1
    assert len(_eventos(uid)) == 1
