"""«Cambiar la cuenta de este extracto»: el extracto de la tarjeta Nu quedó en la cuenta de ahorros.
Datos sintéticos. Se verifica: se mueven SOLO los movimientos que importó ese extracto, los saldos de
ambas cuentas cuadran (el patrimonio total no cambia), idempotencia, pendiente_revision, aislamiento,
anti-duplicados y la sugerencia automática."""
import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'reasignar.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, HuellaOrigen, Movimiento  # noqa: E402
from app.reasignar_extracto import sugerir_cuenta_credito  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="reasig-u", email="reasig@test.com", nombre="Persona Uno")
OTRO = UsuarioActual(id="reasig-otro", email="reasig-otro@test.com", nombre="Persona Dos")
ACTUAL = {"u": U}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    yield
    ACTUAL["u"] = U
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mundo():
    """Ahorros 880.000 (ya restadas las 3 compras de la tarjeta, 120.000) y tarjeta -300.000 (deuda)."""
    db = SessionLocal()
    for m in (HuellaOrigen, ExtractoCorreo, HistorialExtracto, Movimiento, Cuenta):
        db.query(m).filter(m.usuario_id.in_([U.id, OTRO.id])).delete(synchronize_session=False)
    db.commit()
    ahorro = Cuenta(usuario_id=U.id, nombre="Nu Colombia", tipo="ahorro", saldo=880000)
    tarjeta = Cuenta(usuario_id=U.id, nombre="Nu Colombia Crédito", tipo="credito", saldo=-300000)
    ajena = Cuenta(usuario_id=OTRO.id, nombre="Ajena", tipo="ahorro", saldo=5)
    db.add_all([ahorro, tarjeta, ajena])
    db.flush()
    review, ids = [], []
    for i, (desc, monto) in enumerate([("TIENDA UNO", 50000), ("TIENDA DOS", 30000), ("TIENDA TRES", 40000)]):
        fp = f"fp-reasig-{i}"
        m = Movimiento(usuario_id=U.id, cuenta_id=ahorro.id, descripcion=desc, categoria="Otros", tipo="expense",
                       monto=monto, fecha=datetime(2026, 8, 10 + i), fuente="conciliacion_extracto",
                       origen="extracto", huella_externa=f"ext:{fp}#1")
        db.add(m)
        db.flush()
        db.add(HuellaOrigen(usuario_id=U.id, movimiento_id=m.id, huella=f"ext:{fp}#1", origen="extracto",
                            cuenta_id=ahorro.id, tipo="expense", monto=monto, fecha=m.fecha))
        ids.append(m.id)
        # Dos líneas con vínculo directo; la tercera es «vieja» (sin movimiento_id): se halla por su huella.
        item = {"descripcion": desc, "monto": monto, "tipo": "expense", "fecha": f"2026-08-1{i}",
                "fingerprint": fp, "estado": "importado"}
        if i < 2:
            item["movimiento_id"] = m.id
        review.append(item)
    manual = Movimiento(usuario_id=U.id, cuenta_id=ahorro.id, descripcion="Almuerzo", categoria="Comida", tipo="expense",
                        monto=20000, fecha=datetime(2026, 8, 12), fuente="manual", origen="manual")
    db.add(manual)
    h = HistorialExtracto(usuario_id=U.id, cuenta_id=ahorro.id, banco_detectado="Nu Colombia", estado="conciliado",
                          importados=3, review_json=json.dumps(review))
    db.add(h)
    db.commit()
    datos = dict(ahorro=ahorro.id, tarjeta=tarjeta.id, ajena=ajena.id, historial=h.id, manual=manual.id, movs=ids)
    db.close()
    return datos


def _saldo(cuenta_id):
    db = SessionLocal()
    try:
        return db.get(Cuenta, cuenta_id).saldo
    finally:
        db.close()


def _cambiar(h, cuenta, confirmar=True):
    return client.post(f"/conciliacion/historial/{h}/cambiar-cuenta", json={"cuenta_id": cuenta, "confirmar": confirmar})


def test_previa_no_cambia_nada(mundo):
    r = client.get(f"/conciliacion/historial/{mundo['historial']}/cambiar-cuenta/previa", params={"cuenta_id": mundo["tarjeta"]})
    assert r.status_code == 200
    j = r.json()
    assert j["movera"] == 3 and j["duplicados"] == 0
    assert j["origen"]["saldo_antes"] == 880000 and j["origen"]["saldo_despues"] == 1000000
    assert j["destino"]["saldo_antes"] == -300000 and j["destino"]["saldo_despues"] == -420000
    assert _saldo(mundo["ahorro"]) == 880000 and _saldo(mundo["tarjeta"]) == -300000


def test_mueve_solo_lo_del_extracto_y_el_patrimonio_no_cambia(mundo):
    total_antes = _saldo(mundo["ahorro"]) + _saldo(mundo["tarjeta"])
    r = _cambiar(mundo["historial"], mundo["tarjeta"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["movidos"] == 3 and not j["sin_cambios"]
    assert (j["origen"]["saldo_despues"], j["destino"]["saldo_despues"]) == (1000000, -420000)
    # Los movimientos solo cambian de cuenta: la suma de los saldos (patrimonio) no se altera.
    assert _saldo(mundo["ahorro"]) + _saldo(mundo["tarjeta"]) == total_antes
    db = SessionLocal()
    try:
        for mid in mundo["movs"]:
            assert db.get(Movimiento, mid).cuenta_id == mundo["tarjeta"]
            assert db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == mid).first().cuenta_id == mundo["tarjeta"]
        assert db.get(Movimiento, mundo["manual"]).cuenta_id == mundo["ahorro"]  # el manual no se toca
        h = db.get(HistorialExtracto, mundo["historial"])
        assert h.cuenta_id == mundo["tarjeta"]
        assert all(i.get("movimiento_id") for i in json.loads(h.review_json))
    finally:
        db.close()


def test_idempotente(mundo):
    assert _cambiar(mundo["historial"], mundo["tarjeta"]).json()["movidos"] == 3
    saldos = (_saldo(mundo["ahorro"]), _saldo(mundo["tarjeta"]))
    j = _cambiar(mundo["historial"], mundo["tarjeta"]).json()
    assert j["movidos"] == 0 and j["sin_cambios"] is True
    assert (_saldo(mundo["ahorro"]), _saldo(mundo["tarjeta"])) == saldos


def test_pide_confirmar(mundo):
    assert _cambiar(mundo["historial"], mundo["tarjeta"], confirmar=False).status_code == 400
    assert _saldo(mundo["ahorro"]) == 880000


def test_pendiente_revision_sin_importados_solo_cambia_la_cuenta(mundo):
    db = SessionLocal()
    h = db.get(HistorialExtracto, mundo["historial"])
    h.estado = "pendiente_revision"
    h.review_json = json.dumps([{"descripcion": "X", "monto": 1, "tipo": "expense", "fecha": "2026-08-01",
                                 "fingerprint": "fp-pend", "estado": "faltante"}])
    db.commit()
    db.close()
    j = _cambiar(mundo["historial"], mundo["tarjeta"]).json()
    assert j["movidos"] == 0
    assert _saldo(mundo["ahorro"]) == 880000 and _saldo(mundo["tarjeta"]) == -300000
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, mundo["historial"])
        assert h.cuenta_id == mundo["tarjeta"] and h.estado == "pendiente_revision"
        for mid in mundo["movs"]:
            assert db.get(Movimiento, mid).cuenta_id == mundo["ahorro"]
    finally:
        db.close()


def test_no_duplica_si_el_extracto_ya_estaba_en_la_cuenta_nueva(mundo):
    db = SessionLocal()
    db.add(Movimiento(usuario_id=U.id, cuenta_id=mundo["tarjeta"], descripcion="TIENDA UNO", categoria="Otros", tipo="expense",
                      monto=50000, fecha=datetime(2026, 8, 10), fuente="conciliacion_extracto", origen="extracto"))
    db.commit()
    db.close()
    j = _cambiar(mundo["historial"], mundo["tarjeta"]).json()
    assert j["movidos"] == 2 and j["duplicados"] == 1
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == mundo["tarjeta"], Movimiento.descripcion == "TIENDA UNO").count() == 1
        assert db.get(Movimiento, mundo["movs"][0]) is None  # el repetido de ahorros se quitó
    finally:
        db.close()
    assert _saldo(mundo["ahorro"]) == 880000 + 120000  # se revierte todo lo que había restado en ahorros
    assert _saldo(mundo["tarjeta"]) == -300000 - 70000  # solo suma lo realmente movido


def test_cuenta_o_extracto_ajeno(mundo):
    assert _cambiar(mundo["historial"], mundo["ajena"]).status_code == 404
    ACTUAL["u"] = OTRO
    assert _cambiar(mundo["historial"], mundo["ajena"]).status_code == 404
    assert client.get(f"/conciliacion/historial/{mundo['historial']}/cambiar-cuenta/previa",
                      params={"cuenta_id": mundo["ajena"]}).status_code == 404
    assert _saldo(mundo["ahorro"]) == 880000


# ── Sugerencia ───────────────────────────────────────────────────────────────────────────────────
def _cuentas(*tipos_nombres):
    return [Cuenta(id=f"c{i}", usuario_id=U.id, nombre=n, tipo=t, moneda="COP") for i, (t, n) in enumerate(tipos_nombres)]


def test_sugerencia_solo_cuando_corresponde():
    ahorro, tarjeta = _cuentas(("ahorro", "Nu Colombia"), ("credito", "Nu Colombia Crédito"))
    h = HistorialExtracto(usuario_id=U.id, cuenta_id=ahorro.id)
    texto = "Extracto de tu tarjeta de crédito Nu"
    assert sugerir_cuenta_credito(h, ahorro, [ahorro, tarjeta], texto) == {"cuenta_id": tarjeta.id, "nombre": "Nu Colombia Crédito"}
    assert sugerir_cuenta_credito(h, ahorro, [ahorro, tarjeta], "Extracto de tu cuenta de ahorros") is None
    assert sugerir_cuenta_credito(h, ahorro, [ahorro], texto) is None  # no hay tarjeta
    otro_banco = Cuenta(id="cx", usuario_id=U.id, nombre="Davivienda Visa", tipo="credito")
    assert sugerir_cuenta_credito(h, ahorro, [ahorro, otro_banco], texto) is None  # otro banco
    assert sugerir_cuenta_credito(h, tarjeta, [ahorro, tarjeta], texto) is None  # ya está en la tarjeta


def test_lista_de_extractos_trae_la_sugerencia(mundo):
    db = SessionLocal()
    db.add(ExtractoCorreo(usuario_id=U.id, gmail_msg_id="reasig-m1", archivo="Nu_2026-08-04.pdf",
                          asunto="Extracto de tu tarjeta de crédito", banco="Nu Colombia", estado="procesado",
                          historial_id=mundo["historial"], recibido_en=datetime(2026, 8, 4)))
    db.commit()
    db.close()

    def fila():
        filas = client.get("/sincronizacion/extractos").json()["items"]
        return next(f for f in filas if f["historial_id"] == mundo["historial"])

    f = fila()
    assert f["sugerencia_cuenta"]["cuenta_id"] == mundo["tarjeta"] and f["puede_cambiar_cuenta"] is True
    _cambiar(mundo["historial"], mundo["tarjeta"])
    assert fila()["sugerencia_cuenta"] is None
