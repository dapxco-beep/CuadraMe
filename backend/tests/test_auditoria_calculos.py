"""Regresiones de la auditoría: fecha por defecto, xnpv/xirr con desbordes y truncado del asistente."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'audcalc.db')}")

from app import asistente_datos  # noqa: E402
from app import patrimonio_calc as c  # noqa: E402
from app.database import SessionLocal  # noqa: E402
import app.main  # noqa: E402,F401  (crea las tablas al importarse)
from app.models import Cuenta, Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402


def test_movimiento_sin_fecha_cae_en_fecha_colombiana():
    db = SessionLocal()
    cuenta = Cuenta(usuario_id="aud-c1", nombre="Banco", saldo=0)
    db.add(cuenta)
    db.commit()
    antes = ahora_co()
    m = Movimiento(usuario_id="aud-c1", cuenta_id=cuenta.id, descripcion="x", tipo="expense", monto=1)
    db.add(m)
    db.commit()
    despues = ahora_co()
    # UTC va 5 horas por delante: de 19:00 a 23:59 en Colombia ya es "mañana" en UTC.
    assert antes <= m.fecha <= despues
    assert m.fecha.date() in (antes.date(), despues.date())
    db.close()


def test_xnpv_desbordado_devuelve_none_y_xirr_no_revienta():
    hoy = datetime(2026, 1, 1)
    flujos = [(hoy, -1000.0), (hoy + timedelta(days=365 * 80), 1_000_000.0)]
    assert c.xnpv(1e6, flujos) is None          # (1e6)**80 desborda un float
    assert c.xnpv(-1.0, flujos) is None         # 1 + tasa = 0 -> división por cero
    assert c.xnpv(0.10, flujos) is not None     # caso normal intacto
    # XIRR con décadas y rendimiento descomunal: sin excepción
    c.xirr([(hoy, -1.0), (hoy + timedelta(days=365 * 200), 1e300)])  # antes: OverflowError


def test_xirr_normal_sigue_igual():
    ini = datetime(2025, 1, 1)
    r = c.xirr([(ini, -1000.0), (ini + timedelta(days=365), 1100.0)])
    assert abs(r - 0.10) < 1e-6


def test_asistente_trunca_conservando_lo_mas_reciente(monkeypatch):
    monkeypatch.setattr(asistente_datos, "MAX_MOVIMIENTOS", 2)
    hoy = ahora_co()
    db = SessionLocal()
    cuenta = Cuenta(usuario_id="aud-c2", nombre="Banco", saldo=0)
    db.add(cuenta)
    db.commit()
    for dias, monto in ((1, 111), (2, 222), (3, 333)):
        db.add(Movimiento(usuario_id="aud-c2", cuenta_id=cuenta.id, descripcion=f"m{dias}", tipo="expense",
                          monto=monto, categoria="Otros", fecha=hoy - timedelta(days=dias)))
    db.commit()
    datos = asistente_datos.cargar_datos(db, "aud-c2", hoy)
    assert sorted(m["monto"] for m in datos["movs"]) == [111, 222]   # se descarta el más antiguo (333)
    db.close()
