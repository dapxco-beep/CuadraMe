"""«Traer movimientos» claro: nada sin nombre ni origen, errores iguales agrupados, y un estado honesto.

Datos INVENTADOS con la forma del caso real: una tarjeta de crédito cuyo extracto quedó en la cuenta de ahorros,
errores de varios tipos y correos descartados con monto.
"""
import json
import os
import tempfile
import uuid
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'claridad.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import extractos_vista as ev  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, Cuenta, ExtractoCorreo, HistorialExtracto  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="clar-0", email="c@test.com", nombre="Clar")}
gid = lambda: str(uuid.uuid4())  # noqa: E731


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    yield
    app.dependency_overrides.pop(get_current_user, None)


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


# ── Piezas puras ───────────────────────────────────────────────────────────────────────────
def test_titulo_de_grupo_de_error_dice_cuantos_de_que_banco_y_que_les_pasa():
    assert ev.titulo_grupo_error("clave_faltante", 10, "Nu") == "10 extractos de Nu esperan la clave del PDF"
    assert ev.titulo_grupo_error("clave_faltante", 1, "Nu") == "1 extracto de Nu espera la clave del PDF"
    assert ev.titulo_grupo_error("pdf_ilegible", 5, "Nequi") == "5 extractos de Nequi no se pudieron leer"
    assert ev.titulo_grupo_error(None, 2, "") == "2 extractos no se pudieron leer"
    for banco in ("desconocido", "generico"):
        assert banco not in ev.titulo_grupo_error("formato_no_reconocido", 3, ev.banco_para_titulo(banco, "Mi cuenta"))


def test_origen_dice_de_donde_salio():
    assert ev.origen_texto("correo", asunto="Llegó el extracto", archivo="x.pdf") == "Correo «Llegó el extracto» · archivo x.pdf"
    assert ev.origen_texto("archivo", fecha_iso="2026-10-14T10:00:00") == "Subido a mano el 14 oct 2026"
    assert ev.origen_texto("correo") == "Correo de tu banco"


def test_motivo_corto_nunca_queda_vacio():
    assert ev.motivo_corto("clave_faltante") == "falta la clave"
    assert ev.motivo_corto(None) and ev.motivo_corto("inventado")


# ── Con base de datos ──────────────────────────────────────────────────────────────────────
def _cuenta(uid, nombre, tipo):
    como(uid)
    return client.post("/cuentas", json={"nombre": nombre, "tipo": tipo, "saldo": 0}).json()["id"]


def _historial(uid, cuenta, estado="conciliado", banco="nu", motivo=None, lineas=(), creado=datetime(2026, 10, 14, 10, 0), corte=None):
    db = SessionLocal()
    try:
        h = HistorialExtracto(id=gid(), usuario_id=uid, cuenta_id=cuenta, banco_detectado=banco, estado=estado, motivo_error=motivo,
                              review_json=json.dumps(list(lineas)), total_movimientos=len(lineas), creado_en=creado, fecha_corte=corte)
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


def _correo_extracto(uid, asunto, archivo, cuenta, historial=None, estado="procesado", periodo="Octubre 2026"):
    db = SessionLocal()
    try:
        db.add(ExtractoCorreo(id=gid(), usuario_id=uid, gmail_msg_id=gid(), archivo=archivo, remitente="Nu <noreply@nu.com.co>",
                              asunto=asunto, banco="Nu Colombia", periodo=periodo, estado=estado, historial_id=historial,
                              cuenta_sugerida_id=cuenta, recibido_en=datetime(2026, 10, 15, 9)))
        db.commit()
    finally:
        db.close()


def _estado():
    r = client.get("/sincronizacion/estado?hasta=2026-10")
    assert r.status_code == 200, r.text
    return r.json()


def _linea(estado, desc="Compra", monto=1000.0):
    return {"fecha": "2026-10-03", "descripcion": desc, "monto": monto, "tipo": "expense", "estado": estado,
            "fingerprint": gid(), "referencia": "", "categoria_sugerida": "Otros"}


def test_extracto_de_tarjeta_en_cuenta_de_ahorros_se_nombra_tarjeta_y_dice_origen():
    uid = "clar-1"
    ahorros = _cuenta(uid, "Nu Colombia", "ahorro")
    _cuenta(uid, "Nu Colombia Crédito", "credito")
    h = _historial(uid, ahorros, estado="pendiente_revision", lineas=[_linea("importado"), _linea("faltante", "Pago $1.000,00 -$500,00", 500.0)],
                   corte="2026-10-15")
    _correo_extracto(uid, "Llegó el extracto de tu tarjeta de crédito Nu", "tarjeta_oct.pdf", ahorros, h)
    e = _estado()
    fila = next(i for i in e["todos_extractos"]["items"] if i["historial_id"] == h)
    assert fila["titulo"] == "Tarjeta Nu · corte 15 oct 2026"  # no «Cuenta»: el correo dice tarjeta
    assert fila["cuenta_asignada"] == "Nu Colombia"
    assert "Llegó el extracto de tu tarjeta de crédito Nu" in fila["origen_texto"] and "tarjeta_oct.pdf" in fila["origen_texto"]
    # La tarjeta dice que su extracto está en otra cuenta, y el estado lo cuenta como pendiente real.
    credito = next(c for c in e["cuentas"] if c["tipo"] == "credito")
    celda = next(m for m in credito["meses"] if m["mes"] == "2026-10")
    assert celda["en_otra_cuenta"] and celda["en_otra_cuenta"][0]["desde"] == "Nu Colombia"
    assert any(t["id"] == "extracto_cuenta_dudosa" and not t["opcional"] for t in e["tareas"])


def test_errores_iguales_se_agrupan_con_un_solo_boton_de_clave():
    uid = "clar-2"
    nu = _cuenta(uid, "Nu Colombia", "ahorro")
    for k in range(10):
        _historial(uid, nu, estado="error", banco="archivo: nu", motivo="clave_faltante", creado=datetime(2026, 9, 1 + k, 8))
    for k in range(3):
        _historial(uid, nu, estado="error", banco="generico", motivo=None, creado=datetime(2026, 9, 20 + k, 8))
    e = _estado()
    err = [i for i in e["todos_extractos"]["items"] if i["estado_vista"] == "no_se_pudo_leer"]
    assert len(err) == 2  # no 13 filas
    clave = next(i for i in err if i["motivo_codigo"] == "clave_faltante")
    assert clave["titulo"] == "10 extractos de Nu Colombia esperan la clave del PDF"
    assert clave["acciones"][0] == "poner_clave" and "quitar_de_la_lista" in clave["acciones"]
    resto = next(i for i in err if i["motivo_codigo"] != "clave_faltante")
    assert resto["titulo"] == "3 extractos de Nu Colombia no se pudieron leer"
    assert resto["banco_sin_identificar"] is True and resto["origen_texto"].startswith("Subido a mano")
    for i in err:
        assert "desconocido" not in i["titulo"].lower() and "generico" not in i["titulo"].lower()
    # Los de clave cuentan como «falta la clave» (un solo paso), no como «no se pudo leer».
    ids = {t["id"]: t["cantidad"] for t in e["tareas"]}
    assert ids["falta_clave"] == 1 and ids["extractos_sin_leer"] == 1


def test_descartados_con_monto_son_un_pendiente_opcional_y_se_nombran():
    uid = "clar-3"
    _cuenta(uid, "Nequi", "ahorro")
    db = SessionLocal()
    try:
        for k in range(4):
            db.add(CorreoGasto(id=gid(), usuario_id=uid, gmail_msg_id=gid(), remitente="Nequi <n@nequi.com.co>", asunto="Pagaste",
                               monto=10000 + k, comercio="Comercio", estado="descartado", recibido_en=datetime(2026, 10, 2)))
        db.add(CorreoGasto(id=gid(), usuario_id=uid, gmail_msg_id=gid(), remitente="x", asunto="Aviso", monto=0, estado="descartado"))
        db.commit()
    finally:
        db.close()
    t = next(t for t in _estado()["tareas"] if t["id"] == "correos_descartados")
    assert t["cantidad"] == 4 and t["opcional"] is True  # el aviso sin monto no cuenta


def test_la_celda_dice_por_que_no_se_pudo_leer():
    uid = "clar-4"
    nu = _cuenta(uid, "Nu Colombia", "ahorro")
    h = _historial(uid, nu, estado="error", banco="nu", motivo="formato_no_reconocido", creado=datetime(2026, 10, 3, 8))
    _correo_extracto(uid, "Tu extracto de octubre", "oct.pdf", nu, h, estado="error", periodo="Octubre 2026")
    c = next(m for m in _estado()["cuentas"][0]["meses"] if m["mes"] == "2026-10")
    assert c["estado"] == "no_se_pudo_leer" and c["motivo_corto"] == "formato no reconocido"
