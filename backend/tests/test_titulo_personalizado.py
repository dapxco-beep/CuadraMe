"""Nombre propio de un movimiento: se guarda aparte, el texto del banco (descripcion) no se toca."""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'titulo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app import migraciones, titulo as tit  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import HistorialExtracto, HuellaOrigen, Movimiento  # noqa: E402

client = TestClient(app)
ORIGINAL = "Pago PSE CODENSA SA ESP 884221"


@pytest.fixture()
def usuario(request):
    uid = f"user-tit-{request.node.name}"[:60]
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="t@test.com", nombre="Tit")
    yield uid
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def cuenta(usuario):
    r = client.post("/cuentas", json={"nombre": "Banco", "saldo": 1_000_000})
    assert r.status_code == 200, r.text
    return r.json()


def _mov(cuenta, descripcion=ORIGINAL, **extra):
    r = client.post("/movimientos", json={"cuenta_id": cuenta["id"], "descripcion": descripcion, "monto": 50000,
                                          "tipo": "expense", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _lista(**params):
    r = client.get("/movimientos", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_limpiar_recorta_quita_html_y_limita_a_80():
    assert tit.limpiar("  Recibo   de <b>la</b> luz ") == "Recibo de la luz"
    assert tit.limpiar("   ") is None and tit.limpiar(None) is None
    assert len(tit.limpiar("x" * 200)) == 80


def test_guardar_y_limpiar_titulo_conserva_el_original_y_el_saldo(usuario, cuenta):
    m = _mov(cuenta)
    r = client.put(f"/movimientos/{m['id']}", json={"titulo": "  Recibo de la luz "})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["titulo"] == "Recibo de la luz" and j["descripcion"] == ORIGINAL and j["monto"] == 50000
    assert client.get("/cuentas").json()[0]["saldo"] == 950000
    j = client.put(f"/movimientos/{m['id']}", json={"titulo": ""}).json()  # volver al original
    assert j["titulo"] is None and j["descripcion"] == ORIGINAL
    assert client.put(f"/movimientos/{m['id']}", json={"titulo": "x" * 81}).status_code == 422


def test_editar_otro_campo_no_borra_el_titulo(usuario, cuenta):
    m = _mov(cuenta, titulo="Luz")
    j = client.put(f"/movimientos/{m['id']}", json={"notas": "nota"}).json()
    assert j["titulo"] == "Luz"


def test_la_busqueda_encuentra_por_ambos_textos(usuario, cuenta):
    m = _mov(cuenta, titulo="Recibo de la luz")
    _mov(cuenta, "Compra Exito 1")
    assert [x["id"] for x in _lista(q="luz")] == [m["id"]]
    assert [x["id"] for x in _lista(q="codensa")] == [m["id"]]


def test_exportar_usa_el_titulo_y_deja_el_texto_del_banco(usuario, cuenta):
    _mov(cuenta, titulo="Recibo de la luz")
    csv_ = client.get("/exportar/movimientos.csv").text
    assert "Recibo de la luz" in csv_ and ORIGINAL in csv_


def test_importar_linea_con_titulo_conserva_original_y_huella(usuario, cuenta):
    review = [{"fecha": "2025-10-03", "descripcion": ORIGINAL, "monto": 20000, "tipo": "expense",
               "referencia": "", "fingerprint": "fp-t1", "estado": "faltante"}]
    with SessionLocal() as db:
        h = HistorialExtracto(usuario_id=usuario, cuenta_id=cuenta["id"], banco_detectado="nequi", total_movimientos=1,
                              exactos=0, aproximados=0, faltantes=1, importados=0, estado="pendiente_revision",
                              review_json=json.dumps(review))
        db.add(h)
        db.commit()
        hid = h.id
    r = client.post(f"/conciliacion/historial/{hid}/importar", json={
        "fingerprints": ["fp-t1"], "titulos": {"fp-t1": "Recibo de la luz"}}).json()
    assert r["importados"] == 1
    with SessionLocal() as db:
        m = db.query(Movimiento).filter(Movimiento.usuario_id == usuario).one()
        assert m.titulo == "Recibo de la luz" and m.descripcion == ORIGINAL and m.monto == 20000
        # el anti-duplicados sigue colgado de la línea del banco, no del nombre
        assert db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == m.id,
                                              HuellaOrigen.huella.like("ext:fp-t1%")).count() == 1
        assert tit.recordado(db, usuario, ORIGINAL) is None  # no se recuerda nada si no se pidió
        assert json.loads(db.get(HistorialExtracto, hid).review_json)[0]["titulo"] == "Recibo de la luz"


def test_importar_con_recordar_titulo_aplica_a_lo_futuro(usuario, cuenta):
    review = [{"fecha": "2025-10-03", "descripcion": ORIGINAL, "monto": 20000, "tipo": "expense",
               "referencia": "", "fingerprint": "fp-t2", "estado": "faltante"}]
    with SessionLocal() as db:
        h = HistorialExtracto(usuario_id=usuario, cuenta_id=cuenta["id"], banco_detectado="nequi", total_movimientos=1,
                              exactos=0, aproximados=0, faltantes=1, importados=0, estado="pendiente_revision",
                              review_json=json.dumps(review))
        db.add(h)
        db.commit()
        hid = h.id
    client.post(f"/conciliacion/historial/{hid}/importar", json={
        "fingerprints": ["fp-t2"], "titulos": {"fp-t2": "Luz"}, "recordar_titulo": ["fp-t2"]})
    assert _mov(cuenta, "Pago PSE CODENSA SA ESP 123456")["titulo"] == "Luz"


def test_regla_recordada_solo_si_se_eligio(usuario, cuenta):
    _mov(cuenta, "Netflix.com 12345", titulo="Netflix")  # sin recordar
    n2 = _mov(cuenta, "Netflix.com 99999")
    assert n2["titulo"] is None
    m = _mov(cuenta, "Spotify AB 5551", titulo="Música", recordar_titulo=True)
    assert m["titulo"] == "Música"
    futuro = _mov(cuenta, "Spotify AB 7777")
    assert futuro["titulo"] == "Música" and futuro["descripcion"] == "Spotify AB 7777"
    assert client.get(f"/movimientos/{n2['id']}").json()["titulo"] is None  # lo anterior no se renombra solo


def test_recordar_desde_edicion_y_olvidar(usuario, cuenta):
    a = _mov(cuenta, "Claro Movil 3001")
    client.put(f"/movimientos/{a['id']}", json={"titulo": "Plan celular", "recordar_titulo": True})
    assert _mov(cuenta, "Claro Movil 3002")["titulo"] == "Plan celular"
    client.put(f"/movimientos/{a['id']}", json={"titulo": "", "recordar_titulo": True})
    assert _mov(cuenta, "Claro Movil 3003")["titulo"] is None


def test_correo_aprobado_pasa_el_titulo(usuario, cuenta):
    from tests.test_extractos_gmail import GmailFalso, conectar_usuario, mensaje

    mp = pytest.MonkeyPatch()
    try:
        conectar_usuario(usuario, GmailFalso([mensaje("mt1", "Nu Colombia <notificaciones@nu.com.co>",
                                                      "Compra aprobada en JUAN VALDEZ", "Por $12.000 con tu tarjeta")], {}), mp)
        client.post("/correos/sincronizar")
        p = client.get("/correos/pendientes").json()[0]
        r = client.post(f"/correos/{p['id']}/aprobar", json={"cuenta_id": cuenta["id"], "titulo": "Café con Ana"})
        assert r.status_code == 200, r.text
    finally:
        mp.undo()
    m = _lista()[0]
    assert m["titulo"] == "Café con Ana" and m["descripcion"] == "Compra en Juan Valdez"


def test_migracion_0004_va_al_final_y_es_idempotente():
    assert migraciones.MIGRACIONES[-1][0] == "0004_titulo_personalizado"
    sentencias = migraciones.MIGRACIONES[-1][1]
    assert any("movimientos ADD COLUMN IF NOT EXISTS titulo" in s for s in sentencias)
    assert all("IF NOT EXISTS" in s for s in sentencias)
    eng = create_engine(f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'm4.db')}")
    with eng.begin() as c:  # SQLite no entiende ADD COLUMN IF NOT EXISTS: se prueba la tabla nueva dos veces
        for s in sentencias[1:]:
            c.execute(text(s))
            c.execute(text(s))
        assert c.execute(text("SELECT COUNT(*) FROM reglas_titulo")).scalar() == 0
