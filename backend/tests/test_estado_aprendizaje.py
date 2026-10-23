"""«Estamos aprendiendo el formato de tu banco»: estado estructurado y no accionable. Datos 100 % inventados."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'aprendizaje.db')}")

from app import autoarreglo as aa  # noqa: E402
from app import estado_aprendizaje as ea  # noqa: E402
from app import salud_datos  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Cuenta, HistorialExtracto, Perfil  # noqa: E402

Base.metadata.create_all(bind=engine)


def test_campos_solo_cuando_hay_formato_sin_lector_verificado():
    assert ea.campos("formato_no_reconocido")["estado_aprendizaje"] == "aprendiendo"
    assert ea.campos(lectura_completa=False)["texto_aprendizaje"] == "Estamos aprendiendo el formato de tu banco; no tienes que hacer nada."
    for motivo in ("clave_faltante", "clave_incorrecta", "pdf_escaneado", "error_temporal", None):  # ahí SÍ hay algo que hacer
        assert ea.campos(motivo, True) == {"estado_aprendizaje": None, "texto_aprendizaje": None}
    assert ea.campos(None, None)["estado_aprendizaje"] is None


def _extracto_de_banco_desconocido(uid, **kw):
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free")) if not db.query(Perfil).filter_by(usuario_id=uid).first() else None
        c = Cuenta(usuario_id=uid, nombre="Banco Ejemplo B Ahorros", tipo="ahorro", saldo=0)
        db.add(c)
        db.flush()
        h = HistorialExtracto(usuario_id=uid, cuenta_id=c.id, banco_detectado="desconocido", review_json="[]", **kw)
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


def test_correr_informa_aprendiendo_sin_tocar_nada_y_sin_pedir_accion():
    uid = "ap-1"
    hid = _extracto_de_banco_desconocido(uid, estado="error", motivo_error="formato_no_reconocido")
    db = SessionLocal()
    try:
        r = aa.correr(db, uid)
        assert r["aprendizaje"]["estado_aprendizaje"] == "aprendiendo" and r["aprendizaje"]["historial_ids"] == [hid]
        assert r["aprendizaje"]["texto_aprendizaje"].endswith("no tienes que hacer nada.")
        assert r["cambios"] == 0 and not any("formato" in d["texto"].lower() for d in r["decisiones"])  # ninguna decisión pide nada
        h = db.get(HistorialExtracto, hid)
        assert h.estado == "error" and h.review_json == "[]"  # no se tocó
    finally:
        db.close()


def test_sin_extractos_que_aprender_no_hay_campo():
    uid = "ap-2"
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free"))
        db.commit()
        assert aa.correr(db, uid)["aprendizaje"] is None
    finally:
        db.close()


def test_salud_de_datos_trae_el_estado_estructurado_sin_cambiar_su_texto():
    uid = "ap-3"
    _extracto_de_banco_desconocido(uid, estado="conciliado", lectura_json=json.dumps(
        {"lectura_completa": False, "resumen_tarjeta": {"x": 1}, "lineas_leidas": 3}))
    db = SessionLocal()
    try:
        hall = next(h for h in salud_datos.diagnosticar(db, uid) if h["codigo"] == "tarjeta_formato_no_reconocido")
        assert hall["datos"]["estado_aprendizaje"] == "aprendiendo" and hall["datos"]["cantidad"] == 1
        assert hall["accion"]["tipo"] == "pedir_muestra_extracto"  # contrato anterior intacto
    finally:
        db.close()
