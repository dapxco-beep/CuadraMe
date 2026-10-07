"""Extractos subidos a mano cuentan como conciliados en la cuadrícula y la ventana de meses es
configurable (`meses`, `hasta`). Números calculados a mano."""
from datetime import datetime

from app.database import SessionLocal
from app.routers.sincronizacion import ultimos_meses
from app.utiles import ahora_co
from tests.test_sincronizacion import _mov, _usuario, client  # noqa: F401  (fixture autouse viene de aquí)
from tests.test_sincronizacion import _ambiente  # noqa: F401


def test_meses_importados_por_conciliacion_cuentan_como_conciliados():
    uid = "s-manual"
    nu = _usuario(uid, ["Nu"])["Nu"]
    (a0, m0), (a1, m1) = ultimos_meses(ahora_co())[-2:]
    db = SessionLocal()
    try:
        # Mes anterior: 3 movimientos importados de un extracto subido a mano (sin conciliado_en,
        # sin confirmar) + 1 manual. Mes actual: solo uno manual.
        db.add_all([
            _mov(uid, nu, datetime(a0, m0, 3, 12), fuente="conciliacion_extracto", conf=False),
            _mov(uid, nu, datetime(a0, m0, 4, 12), fuente="conciliacion_extracto", conf=False),
            _mov(uid, nu, datetime(a0, m0, 5, 12), fuente="conciliacion_auto", conf=False),
            _mov(uid, nu, datetime(a0, m0, 6, 12)),
            _mov(uid, nu, datetime(a1, m1, 1, 12)),
        ])
        db.commit()
    finally:
        db.close()
    fila = client.get("/sincronizacion/estado").json()["cuentas"][0]["meses"]
    assert fila[-2]["estado"] == "conciliado"
    assert (fila[-2]["movimientos"], fila[-2]["conciliados"], fila[-2]["por_confirmar"]) == (4, 3, 3)
    assert fila[-1]["estado"] == "sin_extracto" and fila[-1]["conciliados"] == 0


def test_ventana_de_la_cuadricula_meses_y_hasta():
    _usuario("s-ventana", ["Efectivo"])
    d = client.get("/sincronizacion/estado").json()
    assert len(d["meses"]) == 6 and len(d["cuentas"][0]["meses"]) == 6
    d = client.get("/sincronizacion/estado?meses=24").json()
    assert len(d["meses"]) == 24 and len(d["cuentas"][0]["meses"]) == 24
    d = client.get("/sincronizacion/estado?meses=4&hasta=2026-02").json()
    assert [m["clave"] for m in d["meses"]] == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert client.get("/sincronizacion/estado?meses=25").status_code == 422
    assert client.get("/sincronizacion/estado?meses=0").status_code == 422
    assert client.get("/sincronizacion/estado?hasta=2026-13").status_code == 422
    assert client.get("/sincronizacion/estado?hasta=hoy").status_code == 422
