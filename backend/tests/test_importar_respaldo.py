"""Importar mi respaldo: el ZIP de /perfil/mis-datos se restaura con vista previa, sin duplicar,
en una sola transacción, solo a nombre de quien importa y con «deshacer»."""
import io
import json
import os
import tempfile
import zipfile
from datetime import timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'importar_respaldo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import derechos_titular as dt  # noqa: E402
from app import importar_respaldo as ir  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.limites import _eventos  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Meta, Movimiento, Perfil, Presupuesto, ReglaCategoria  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
ORIGEN = UsuarioActual(id="resp-origen", email="origen-resp@test.com", nombre="Origen")
DESTINO = UsuarioActual(id="resp-destino", email="destino-resp@test.com", nombre="Destino")
OTRO = UsuarioActual(id="resp-otro", email="otro-resp@test.com", nombre="Otro")
ACTUAL = {"u": ORIGEN}
URL = "/perfil/importar-respaldo"


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    yield
    app.dependency_overrides.pop(get_current_user, None)
    for k in [k for k in _eventos if k.startswith(("mis-datos:", "importar-respaldo:"))]:
        _eventos.pop(k, None)


@pytest.fixture(autouse=True, scope="module")
def _limpiar_al_final():
    yield
    db = SessionLocal()
    try:
        for u in (ORIGEN, DESTINO, OTRO):
            dt.borrar_todo(db, u.id, u.email)
    finally:
        db.close()


def como(u):
    ACTUAL["u"] = u


def _borrar(u):
    db = SessionLocal()
    try:
        dt.borrar_todo(db, u.id, u.email)
    finally:
        db.close()


def _sembrar_origen():
    """ORIGEN: 2 cuentas, 3 movimientos (dos cafés idénticos), presupuesto, meta, regla."""
    como(ORIGEN)
    banco = client.post("/cuentas", json={"nombre": "Banco RESP", "saldo": 1000, "tipo": "ahorro"}).json()
    efectivo = client.post("/cuentas", json={"nombre": "Efectivo RESP", "saldo": 50, "tipo": "efectivo"}).json()
    for desc, monto in (("Café RESP", 5), ("Café RESP", 5), ("Almuerzo RESP", 20)):
        assert client.post("/movimientos", json={"cuenta_id": banco["id"], "descripcion": desc, "monto": monto,
                                                 "tipo": "expense", "categoria": "Comida"}).status_code in (200, 201)
    client.post("/presupuestos", json={"categoria": "Comida", "limite": 500})
    meta = client.post("/metas", json={"nombre": "Meta RESP", "monto_objetivo": 1000}).json()
    client.post("/reglas-categoria", json={"patron": "cafe resp", "categoria": "Comida"})
    return banco, efectivo, meta


def _zip_de_origen() -> bytes:
    como(ORIGEN)
    r = client.get("/perfil/mis-datos")
    assert r.status_code == 200
    return r.content


def _subir(url, contenido, nombre="respaldo.zip", **data):
    return client.post(url, files={"archivo": (nombre, contenido, "application/zip")}, data=data)


def _conteo(uid):
    db = SessionLocal()
    try:
        return {
            "cuentas": db.query(Cuenta).filter(Cuenta.usuario_id == uid).count(),
            "movimientos": db.query(Movimiento).filter(Movimiento.usuario_id == uid).count(),
            "presupuestos": db.query(Presupuesto).filter(Presupuesto.usuario_id == uid).count(),
            "metas": db.query(Meta).filter(Meta.usuario_id == uid).count(),
            "reglas": db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == uid).count(),
        }
    finally:
        db.close()


def _zip_con_datos(tablas: dict, **extra) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("datos.json", json.dumps({"formato": "cuadrame-respaldo", "version": 1, "correo": "x@y.z",
                                             "tablas": tablas, **extra}))
    return b.getvalue()


def test_flujo_completo_vista_previa_importar_y_repetir_no_duplica():
    _borrar(ORIGEN), _borrar(DESTINO)
    _sembrar_origen()
    zipb = _zip_de_origen()

    como(DESTINO)
    antes = _conteo(DESTINO.id)
    vp = _subir(f"{URL}/vista-previa", zipb)
    assert vp.status_code == 200, vp.text
    v = vp.json()
    assert v["cuentas"]["nuevos"] == 2 and v["movimientos"]["nuevos"] == 3
    assert v["presupuestos"]["nuevos"] == 1 and v["metas"]["nuevos"] == 1 and v["reglas"]["nuevos"] == 1
    assert v["correo_distinto"] is True and "correo_respaldo" not in v
    assert _conteo(DESTINO.id) == antes, "la vista previa no debe escribir nada"

    # Sin confirmar no importa.
    assert _subir(URL, zipb).status_code == 400
    assert _conteo(DESTINO.id) == antes

    r = _subir(URL, zipb, confirmar="true")
    assert r.status_code == 200, r.text
    assert r.json()["movimientos"]["nuevos"] == 3
    c = _conteo(DESTINO.id)
    assert c == {"cuentas": 2, "movimientos": 3, "presupuestos": 1, "metas": 1, "reglas": 1}

    # Todo quedó a nombre de DESTINO, con ids NUEVOS, remapeados cuenta -> movimiento.
    db = SessionLocal()
    try:
        cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == DESTINO.id).all()
        ids_origen = {x.id for x in db.query(Cuenta).filter(Cuenta.usuario_id == ORIGEN.id).all()}
        assert not ({x.id for x in cuentas} & ids_origen)
        movs = db.query(Movimiento).filter(Movimiento.usuario_id == DESTINO.id).all()
        assert all(m.cuenta_id in {x.id for x in cuentas} for m in movs)
        banco = next(x for x in cuentas if x.nombre == "Banco RESP")
        assert banco.saldo == pytest.approx(1000 - 30)  # el saldo del respaldo, sin sumar movimientos otra vez
    finally:
        db.close()

    # Repetir: nada se duplica.
    v2 = _subir(f"{URL}/vista-previa", zipb).json()
    assert v2["cuentas"] == {"nuevos": 0, "existentes": 2, "invalidos": 0}
    assert v2["movimientos"]["nuevos"] == 0 and v2["movimientos"]["existentes"] == 3
    assert _subir(URL, zipb, confirmar="true").status_code == 200
    assert _conteo(DESTINO.id) == c


def test_importar_en_cuenta_existente_suma_solo_lo_que_falta_y_ajusta_saldo():
    _borrar(ORIGEN), _borrar(DESTINO)
    _sembrar_origen()
    zipb = _zip_de_origen()
    como(DESTINO)
    cta = client.post("/cuentas", json={"nombre": "Banco RESP", "saldo": 500, "tipo": "ahorro"}).json()
    # Ya tiene UNO de los dos cafés: el segundo sí falta.
    client.post("/movimientos", json={"cuenta_id": cta["id"], "descripcion": "Café RESP", "monto": 5,
                                      "tipo": "expense", "fecha": ahora_co().isoformat()})
    v = _subir(f"{URL}/vista-previa", zipb).json()
    assert v["cuentas"]["existentes"] == 1 and v["cuentas"]["nuevos"] == 1
    assert v["movimientos"]["existentes"] == 1 and v["movimientos"]["nuevos"] == 2
    assert _subir(URL, zipb, confirmar="true").json()["movimientos"]["nuevos"] == 2
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == cta["id"]).count() == 3
        # 495 (500 - el café que ya tenía) - el otro café (5) - el almuerzo (20)
        assert db.query(Cuenta).filter(Cuenta.id == cta["id"]).first().saldo == pytest.approx(470)
    finally:
        db.close()
    # Deshacer deja la cuenta como estaba (saldo y movimientos).
    d = client.post(f"{URL}/deshacer")
    assert d.status_code == 200, d.text
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == cta["id"]).count() == 1
        assert db.query(Cuenta).filter(Cuenta.id == cta["id"]).first().saldo == pytest.approx(495)
    finally:
        db.close()


def test_deshacer_quita_solo_lo_importado():
    _borrar(ORIGEN), _borrar(DESTINO)
    _sembrar_origen()
    zipb = _zip_de_origen()
    como(DESTINO)
    propia = client.post("/cuentas", json={"nombre": "Mi cuenta propia", "saldo": 10}).json()
    client.post("/movimientos", json={"cuenta_id": propia["id"], "descripcion": "Mio", "monto": 1, "tipo": "expense"})
    client.post("/metas", json={"nombre": "Meta mía", "monto_objetivo": 5})
    base = _conteo(DESTINO.id)
    assert client.get(f"{URL}/ultima").json()["hay"] is False
    assert client.post(f"{URL}/deshacer").status_code == 404

    assert _subir(URL, zipb, confirmar="true").status_code == 200
    assert client.get(f"{URL}/ultima").json()["hay"] is True
    assert _conteo(DESTINO.id) != base
    out = client.post(f"{URL}/deshacer").json()
    assert out["ok"] and out["revertido"]["movimientos"] == 3
    assert _conteo(DESTINO.id) == base
    assert client.get(f"{URL}/ultima").json()["hay"] is False
    assert client.post(f"{URL}/deshacer").status_code == 404


def test_no_toca_datos_de_otros_ni_importa_secretos():
    _borrar(ORIGEN), _borrar(DESTINO), _borrar(OTRO)
    _sembrar_origen()
    como(OTRO)
    client.post("/cuentas", json={"nombre": "Cuenta de OTRO", "saldo": 7})
    antes_otro = _conteo(OTRO.id)
    # Respaldo malicioso: pretende escribir con el usuario_id y los ids de OTRO y trae un secreto.
    db = SessionLocal()
    try:
        cuenta_otro = db.query(Cuenta).filter(Cuenta.usuario_id == OTRO.id).first()
        cid = cuenta_otro.id
    finally:
        db.close()
    zipb = _zip_con_datos({
        "cuentas": [{"id": cid, "usuario_id": OTRO.id, "nombre": "Cuenta de OTRO", "saldo": 999, "tipo": "ahorro",
                     "moneda": "COP", "campo_raro": "x", "clave_enc": "SECRETO"}],
        "movimientos": [{"id": "m-malo", "usuario_id": OTRO.id, "cuenta_id": cid, "fecha": "2026-01-02T10:00:00",
                         "descripcion": "Inyectado", "tipo": "expense", "monto": 3, "api_key": "SECRETO"}],
        "perfiles": [{"usuario_id": DESTINO.id, "plan": "pro", "api_key": "SECRETO"}],
    })
    como(DESTINO)
    r = _subir(URL, zipb, confirmar="true")
    assert r.status_code == 200, r.text
    # La cuenta es «igual» a una de OTRO, pero DESTINO no la tiene: se crea la suya, a su nombre.
    db = SessionLocal()
    try:
        assert db.query(Cuenta).filter(Cuenta.id == cid).first().usuario_id == OTRO.id
        assert db.query(Cuenta).filter(Cuenta.id == cid).first().saldo == 7
        mias = db.query(Cuenta).filter(Cuenta.usuario_id == DESTINO.id).all()
        assert len(mias) == 1 and mias[0].id != cid
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == cid).count() == 0
        assert db.query(Movimiento).filter(Movimiento.usuario_id == DESTINO.id).count() == 1
        p = db.query(Perfil).filter(Perfil.usuario_id == DESTINO.id).first()
        assert p is None or (p.plan != "pro" and not p.api_key)
    finally:
        db.close()
    assert _conteo(OTRO.id) == antes_otro


def test_archivos_invalidos_se_rechazan_con_mensaje_llano():
    como(DESTINO)
    assert _subir(f"{URL}/vista-previa", b"no soy un zip").status_code == 400
    sin_datos = io.BytesIO()
    with zipfile.ZipFile(sin_datos, "w") as z:
        z.writestr("otra_cosa.txt", "hola")
    assert _subir(f"{URL}/vista-previa", sin_datos.getvalue()).status_code == 400
    version_futura = _zip_con_datos({}, version=99)
    r = _subir(f"{URL}/vista-previa", version_futura)
    assert r.status_code == 400 and "versión" in r.json()["detail"]
    assert _subir(f"{URL}/vista-previa", _zip_con_datos({"cuentas": "no es lista"})).status_code == 400
    grande = b"PK" + b"0" * (ir.MAX_BYTES_ARCHIVO + 10)
    assert _subir(f"{URL}/vista-previa", grande).status_code in (400, 413)  # 413 si lo corta antes el límite global del cuerpo
    assert _subir(f"{URL}/vista-previa", b"").status_code == 400


def test_filas_malas_se_cuentan_y_se_omiten_sin_romper():
    _borrar(DESTINO)
    como(DESTINO)
    zipb = _zip_con_datos({
        "cuentas": [{"id": "c1", "nombre": "Buena", "saldo": 5}, {"id": "c2", "nombre": "", "saldo": 1},
                    {"id": "c3", "nombre": "Saldo absurdo", "saldo": 1e30}],
        "movimientos": [
            {"cuenta_id": "c1", "fecha": "2026-02-01T08:00:00", "descripcion": "Ok", "tipo": "expense", "monto": 4},
            {"cuenta_id": "c1", "fecha": "no-es-fecha", "descripcion": "Mala fecha", "tipo": "expense", "monto": 4},
            {"cuenta_id": "c1", "fecha": "2026-02-01T08:00:00", "descripcion": "Tipo raro", "tipo": "regalo", "monto": 4},
            {"cuenta_id": "c-no-existe", "fecha": "2026-02-01T08:00:00", "descripcion": "Huérfano", "tipo": "expense", "monto": 4},
        ],
    })
    v = _subir(URL, zipb, confirmar="true").json()
    assert v["cuentas"]["nuevos"] == 1 and v["cuentas"]["invalidos"] == 2
    assert v["movimientos"] == {"nuevos": 1, "existentes": 0, "invalidos": 2, "sin_cuenta": 1,
                                "anteriores_al_punto_de_partida": 0}


def test_respeta_el_punto_de_partida():
    _borrar(DESTINO)
    como(DESTINO)
    hoy = ahora_co()
    viejo = (hoy - timedelta(days=60)).isoformat()
    reciente = (hoy - timedelta(days=2)).isoformat()
    zipb = _zip_con_datos({
        "cuentas": [{"id": "c1", "nombre": "PP", "saldo": 0}],
        "movimientos": [
            {"cuenta_id": "c1", "fecha": viejo, "descripcion": "Viejo", "tipo": "expense", "monto": 1},
            {"cuenta_id": "c1", "fecha": reciente, "descripcion": "Reciente", "tipo": "expense", "monto": 1},
        ],
    })
    assert client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": (hoy - timedelta(days=10)).date().isoformat()}).status_code == 200
    v = _subir(URL, zipb, confirmar="true").json()
    assert v["movimientos"]["nuevos"] == 1 and v["movimientos"]["anteriores_al_punto_de_partida"] == 1


def test_si_falla_a_mitad_no_queda_nada(monkeypatch):
    _borrar(DESTINO)
    _sembrar_origen()
    zipb = _zip_de_origen()
    como(DESTINO)
    original = ir.Movimiento

    class Roto:
        n = 0

        def __new__(cls, *a, **k):
            Roto.n += 1
            if Roto.n == 2:
                raise RuntimeError("falla a mitad")
            return original(*a, **k)

    monkeypatch.setattr(ir, "Movimiento", Roto)
    antes = _conteo(DESTINO.id)
    r = _subir(URL, zipb, confirmar="true")
    assert r.status_code == 500
    monkeypatch.setattr(ir, "Movimiento", original)
    assert _conteo(DESTINO.id) == antes
    assert client.get(f"{URL}/ultima").json()["hay"] is False


def test_aporte_a_meta_conserva_su_referencia_remapeada():
    _borrar(ORIGEN), _borrar(DESTINO)
    como(ORIGEN)
    cta = client.post("/cuentas", json={"nombre": "Con meta RESP", "saldo": 1000}).json()
    meta = client.post("/metas", json={"nombre": "Meta con aporte", "monto_objetivo": 500}).json()
    db = SessionLocal()
    try:  # el aporte automático deja un movimiento neutro que cita la meta en `notas`
        db.add(Movimiento(usuario_id=ORIGEN.id, cuenta_id=cta["id"], fecha=ahora_co(), descripcion="Aporte a meta",
                          categoria="Aporte a meta", tipo="expense", monto=100, fuente="aporte_meta",
                          notas=f"META:{meta['id']}"))
        db.commit()
    finally:
        db.close()
    zipb = _zip_de_origen()
    como(DESTINO)
    assert _subir(URL, zipb, confirmar="true").status_code == 200
    db = SessionLocal()
    try:
        m = db.query(Meta).filter(Meta.usuario_id == DESTINO.id).first()
        aportes = [x for x in db.query(Movimiento).filter(Movimiento.usuario_id == DESTINO.id).all()
                   if (x.notas or "").startswith("META:")]
        assert len(aportes) == 1
        assert aportes[0].notas == f"META:{m.id}" and m.id != meta["id"]
    finally:
        db.close()
