"""Salud de datos: un caso sintético por hallazgo + los datos mínimos (sin montos ni descripciones)."""
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'salud.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    ClavePdf, Consentimiento, CorreoGasto, Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil, SyncGmail,
)
from app.salud_datos import CODIGOS, diagnosticar  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


def uid():
    return f"salud-{uuid.uuid4().hex[:8]}"


def cuenta(db, u, nombre, tipo="ahorro"):
    c = Cuenta(usuario_id=u, nombre=nombre, tipo=tipo, saldo=0)
    db.add(c)
    db.commit()
    return c


def extracto(db, u, banco, asunto, archivo="extracto.pdf", estado="nuevo", cuenta_id=None, historial_id=None):
    e = ExtractoCorreo(usuario_id=u, gmail_msg_id=uuid.uuid4().hex, archivo=archivo, banco=banco, asunto=asunto,
                       estado=estado, cuenta_sugerida_id=cuenta_id, historial_id=historial_id, recibido_en=datetime.utcnow())
    db.add(e)
    db.commit()
    return e


def gmail_activo(db, u, ceros=0, ultima=None):
    db.add(Perfil(usuario_id=u, gmail_conectado=True, gmail_refresh_token_enc="tok"))
    ahora = datetime.utcnow()
    db.add(Consentimiento(usuario_id=u, version="1.1", finalidad="lectura_correo", aceptado=True,
                          creado_en_utc=ahora, creado_en_co=ahora))
    db.add(SyncGmail(usuario_id=u, ceros_seguidos_mov=ceros, ultima_sync=ultima))
    db.commit()


def codigos(db, u):
    return {h["codigo"]: h for h in diagnosticar(db, u)}


def test_usuario_sano_sin_hallazgos(db):
    u = uid()
    cuenta(db, u, "Nu Tarjeta", "credito")
    assert diagnosticar(db, u) == []


def test_extracto_de_tarjeta_en_cuenta_de_ahorros(db):
    u = uid()
    ahorros = cuenta(db, u, "Nu Colombia", "ahorro")
    cuenta(db, u, "Nu Tarjeta", "credito")
    extracto(db, u, "Nu", "Extracto de tu tarjeta de crédito Nu", cuenta_id=ahorros.id)
    h = codigos(db, u)["extracto_producto_distinto"]
    assert h["severidad"] == "importante" and h["accion"]["tipo"] == "cambiar_cuenta_extracto"
    assert h["datos"]["cantidad"] == 1


def test_extracto_en_su_cuenta_no_se_marca(db):
    u = uid()
    tarjeta = cuenta(db, u, "Nu Tarjeta", "credito")
    extracto(db, u, "Nu", "Extracto de tu tarjeta de crédito Nu", cuenta_id=tarjeta.id)
    assert "extracto_producto_distinto" not in codigos(db, u)


def test_tarjeta_sin_cuenta_de_credito_del_banco(db):
    u = uid()
    cuenta(db, u, "Nu Colombia", "ahorro")
    extracto(db, u, "Nu", "Extracto de tu tarjeta de crédito Nu")
    extracto(db, u, "Nu", "Extracto de tu tarjeta de crédito Nu", archivo="otro.pdf")
    h = codigos(db, u)["tarjeta_sin_cuenta"]
    assert h["accion"] == {"tipo": "crear_cuenta_tarjeta", "etiqueta": "Crear tarjeta Nu", "banco": "Nu"}
    assert h["datos"] == {"banco": "Nu", "cantidad": 2}
    cuenta(db, u, "Nu Tarjeta", "credito")
    assert "tarjeta_sin_cuenta" not in codigos(db, u)


def test_error_recuperable_solo_si_hay_correo_y_clave(db):
    u = uid()
    c = cuenta(db, u, "Bancolombia Tarjeta", "credito")
    h = HistorialExtracto(usuario_id=u, cuenta_id=c.id, banco_detectado="bancolombia", estado="error", motivo_error="clave_faltante")
    db.add(h)
    db.commit()
    extracto(db, u, "Bancolombia", "Extracto", estado="falta_clave", cuenta_id=c.id)
    # Sin clave guardada no es «recuperable»: es «falta la clave».
    r = codigos(db, u)
    assert "extracto_en_error_recuperable" not in r and "clave_pdf_faltante" in r
    db.add(ClavePdf(usuario_id=u, clave_enc="x"))
    db.commit()
    r = codigos(db, u)
    assert r["extracto_en_error_recuperable"]["datos"]["cantidad"] == 1 and "clave_pdf_faltante" not in r


def test_error_sin_correo_no_es_recuperable(db):
    u = uid()
    c = cuenta(db, u, "Davivienda", "ahorro")
    db.add(HistorialExtracto(usuario_id=u, cuenta_id=c.id, estado="error", motivo_error="pdf_ilegible"))
    db.commit()
    assert "extracto_en_error_recuperable" not in codigos(db, u)


def test_correos_descartados_con_monto(db):
    u = uid()
    db.add_all([CorreoGasto(usuario_id=u, gmail_msg_id=uuid.uuid4().hex, estado="descartado", monto=1000),
                CorreoGasto(usuario_id=u, gmail_msg_id=uuid.uuid4().hex, estado="descartado", monto=0),
                CorreoGasto(usuario_id=u, gmail_msg_id=uuid.uuid4().hex, estado="pendiente", monto=500)])
    db.commit()
    h = codigos(db, u)["correos_descartados_con_monto"]
    assert h["datos"] == {"cantidad": 1}


def test_lectura_en_cero_exige_3_corridas_gmail_y_lectura_activa(db):
    u = uid()
    gmail_activo(db, u, ceros=2)
    assert "lectura_correo_en_cero" not in codigos(db, u)
    db.query(SyncGmail).filter(SyncGmail.usuario_id == u).update({"ceros_seguidos_mov": 3})
    db.commit()
    assert codigos(db, u)["lectura_correo_en_cero"]["datos"] == {"corridas_en_cero": 3}
    db.query(Perfil).filter(Perfil.usuario_id == u).update({"gmail_leer_movimientos": False})
    db.commit()
    assert "lectura_correo_en_cero" not in codigos(db, u)  # la apagó ella: no es una falla


def test_lectura_en_cero_sin_gmail_conectado_no_avisa(db):
    u = uid()
    db.add(Perfil(usuario_id=u, gmail_conectado=False))
    db.add(SyncGmail(usuario_id=u, ceros_seguidos_mov=9))
    db.commit()
    assert diagnosticar(db, u) == []


def test_clave_faltante_con_extractos_esperando(db):
    u = uid()
    extracto(db, u, "Davivienda", "Extracto", estado="falta_clave")
    h = codigos(db, u)["clave_pdf_faltante"]
    assert h["accion"]["tipo"] == "guardar_clave" and h["datos"]["cantidad"] == 1


def test_movimientos_de_extracto_en_cuenta_incoherente(db):
    u = uid()
    a, b = cuenta(db, u, "Nu Colombia"), cuenta(db, u, "Nu Tarjeta", "credito")
    h = HistorialExtracto(usuario_id=u, cuenta_id=b.id, estado="conciliado", importados=2)
    db.add(h)
    db.commit()
    db.add_all([Movimiento(usuario_id=u, cuenta_id=a.id, tipo="expense", monto=10, descripcion="x", extracto_id=h.id),
                Movimiento(usuario_id=u, cuenta_id=b.id, tipo="expense", monto=10, descripcion="y", extracto_id=h.id)])
    db.commit()
    r = codigos(db, u)["movimientos_en_cuenta_incoherente"]
    assert r["datos"] == {"cantidad": 1, "historial_ids": [h.id]} and r["accion"]["historial_id"] == h.id


def test_sin_sincronizar_mas_de_48_horas(db):
    u = uid()
    gmail_activo(db, u, ultima=datetime.utcnow() - timedelta(hours=47))
    assert "sin_sincronizar" not in codigos(db, u)
    db.query(SyncGmail).filter(SyncGmail.usuario_id == u).update({"ultima_sync": datetime.utcnow() - timedelta(hours=60)})
    db.commit()
    assert codigos(db, u)["sin_sincronizar"]["datos"]["horas"] >= 59


def test_los_hallazgos_no_llevan_montos_ni_descripciones(db):
    assert len(CODIGOS) == 8
    u = uid()
    a = cuenta(db, u, "Nu Colombia")
    extracto(db, u, "Nu", "Extracto de tu tarjeta de crédito Nu", cuenta_id=a.id, estado="falta_clave")
    db.add(CorreoGasto(usuario_id=u, gmail_msg_id="m1", estado="descartado", monto=98765, comercio="SECRETO"))
    db.commit()
    txt = json.dumps(diagnosticar(db, u))
    assert "98765" not in txt and "SECRETO" not in txt


def test_endpoint_salud_es_del_usuario():
    s = SessionLocal()
    a, b = uid(), uid()
    extracto(s, a, "Davivienda", "Extracto", estado="falta_clave")
    s.close()
    try:
        app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=a, email="a@t.com", nombre="A")
        ra = client.get("/salud").json()
        app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=b, email="b@t.com", nombre="B")
        rb = client.get("/salud").json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert ra["total"] == 1 and ra["hallazgos"][0]["codigo"] == "clave_pdf_faltante"
    assert rb == {"total": 0, "hallazgos": []}
