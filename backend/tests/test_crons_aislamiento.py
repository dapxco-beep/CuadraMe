"""Un usuario que falla en un cron no debe impedir que se procesen los demás."""
import logging
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'crons_aisl.db')}")

from fastapi.testclient import TestClient  # noqa: E402

from app.crons import Corrida  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento, PushSubscription  # noqa: E402
from app.routers import push as push_router  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}


def test_corrida_cuenta_fallos_hace_rollback_y_no_loguea_datos(caplog):
    class _Db:
        rollbacks = 0

        def rollback(self):
            self.rollbacks += 1

    db = _Db()
    corrida = Corrida(db)
    with caplog.at_level(logging.ERROR, logger="app.crons"):
        for uid in ("u1", "u2", "u3"):
            with corrida.aislar(uid):
                if uid == "u2":
                    raise ValueError("correo@secreto.com")
    assert corrida.resumen() == {"procesados": 2, "fallidos": 1}
    assert db.rollbacks == 1
    assert "u2" in caplog.text


def test_resumen_semanal_sigue_con_los_demas_si_uno_falla(monkeypatch):
    db = SessionLocal()
    try:
        for uid in ("aisl-malo", "aisl-bueno"):
            cuenta = Cuenta(usuario_id=uid, nombre="Banco", saldo=1000, moneda="COP")
            db.add(cuenta)
            db.flush()
            db.add(PushSubscription(usuario_id=uid, endpoint=f"https://push.test/{uid}", p256dh="x", auth="y"))
            db.add(Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion="Almuerzo", categoria="Comida",
                              tipo="expense", monto=10, fecha=ahora_co()))
        db.commit()
    finally:
        db.close()

    enviados_a = []

    def _enviar(db, usuario_id, *a, **k):
        if usuario_id == "aisl-malo":
            raise RuntimeError("push caído")
        enviados_a.append(usuario_id)
        return 1

    monkeypatch.setattr(push_router, "enviar_push", _enviar)
    r = client.post("/push/cron/resumen-semanal", headers=CABECERA).json()
    assert r["ok"] is True
    assert r["fallidos"] == 1 and r["procesados"] >= 1
    assert r["enviados"] == 1 and "aisl-bueno" in enviados_a
