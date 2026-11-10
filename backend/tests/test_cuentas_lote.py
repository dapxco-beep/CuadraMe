"""listar_cuentas precalcula las tarjetas en lote: mismo resultado que el cálculo por tarjeta."""
import os
import tempfile
from datetime import timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'lote.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import FUENTE_AJUSTE  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402
from app.routers.cuentas import _serializar  # noqa: E402
from app.tarjetas import precalcular_tarjetas  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _usuario():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="u-lote", email="l@t.com", nombre="L")
    yield


def _mov(db, cuenta_id, dias_atras, fuente="manual", monto=-10_000):
    db.add(Movimiento(usuario_id="u-lote", cuenta_id=cuenta_id, monto=monto, tipo="expense",
                      fecha=ahora_co() - timedelta(days=dias_atras), descripcion="x", fuente=fuente))


def test_lote_igual_al_calculo_por_tarjeta():
    # Tarjetas: con historial previo, sin historial (solo ajuste), sin día de corte; más una cuenta normal.
    for nombre, corte in [("A", 5), ("B", 20), ("C", None)]:
        client.post("/cuentas", json={"nombre": f"Lote {nombre}", "tipo": "credito", "saldo": -500_000,
                                      "cupo_total": 2_000_000, "dia_corte": corte, "dia_pago": 25})
    client.post("/cuentas", json={"nombre": "Lote ahorros", "saldo": 1000})
    db = SessionLocal()
    try:
        cuentas = {c.nombre: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == "u-lote").all()}
        for nombre in ("Lote A", "Lote B", "Lote C"):
            cid = cuentas[nombre].id
            if nombre != "Lote B":
                _mov(db, cid, 90)   # historial real anterior al corte
            else:
                _mov(db, cid, 90, fuente=FUENTE_AJUSTE)  # solo ajuste: saldo declarado
            _mov(db, cid, 2)        # reciente
            _mov(db, cid, 40)
        db.commit()
        lista = list(cuentas.values())
        pre = precalcular_tarjetas(db, lista)
        assert "Lote ahorros" not in [cuentas[n].nombre for n in cuentas if cuentas[n].id in pre]
        for c in lista:
            assert _serializar(c, db, pre) == _serializar(c, db), c.nombre
    finally:
        db.close()
    # Y el endpoint devuelve lo mismo que el cálculo individual
    api = {x["nombre"]: x for x in client.get("/cuentas").json()}
    assert api["Lote B"]["tarjeta"] is not None and api["Lote ahorros"]["tarjeta"] is None
