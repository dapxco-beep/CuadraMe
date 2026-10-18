"""Fila «resumen de la factura anterior» del extracto de tarjeta de Nu. Datos inventados.

«Pago $A -$B» con tercer importe C = A − B no es un gasto de C: A = total de la factura anterior, B = lo pagado,
C = saldo pendiente. Lo real es UN pago de B (abona a la tarjeta; es traslado, no gasto ni ingreso).
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'resumen.db')}")

from datetime import datetime  # noqa: E402

from app import conciliacion as c  # noqa: E402
from app.contabilidad import MARCA_TRASLADO_PROPIO  # noqa: E402
from app.routers.conciliacion import _confirmar_pagos_de_factura  # noqa: E402

TARJETA = """Extracto de tu tarjeta de crédito Nu
Período 01 - 31 OCT 2026
Pago mínimo $98.000
05 oct Pago $500.000,00 -$300.000,00 -$200.000,00
06 oct Tienda de prueba -$45.000,00
14 oct Cobro por cuota $9.000,00 - $9.000,00 -$9.000,00
"""


def test_resumen_se_convierte_en_un_pago_de_lo_abonado():
    movs, _ = c._parse_nu(TARJETA, "2026")
    assert not [m for m in movs if m["monto"] == 200000.0]  # no hay gasto de A-B
    pago = next(m for m in movs if m.get("resumen_factura"))
    assert pago["monto"] == 300000.0 and pago["tipo"] == "income" and pago["fecha"] == "2026-10-05"
    assert pago["descripcion"] == "Pago de tu tarjeta (factura anterior)"
    assert pago["resumen_factura"] == {"factura_anterior": 500000.0, "pagado": 300000.0, "saldo_pendiente": 200000.0}
    assert pago["pista"] == MARCA_TRASLADO_PROPIO and pago["pago_tarjeta"] is True
    assert "lectura_dudosa" not in pago and pago["aviso_linea"] == "Parece el pago de tu tarjeta. Confirma el monto."


def test_dos_montos_que_no_cumplen_la_resta_siguen_siendo_dudosos():
    texto = TARJETA.replace("-$200.000,00", "-$150.000,00")
    movs, _ = c._parse_nu(texto, "2026")
    d = next(m for m in movs if m["descripcion"].startswith("Pago"))
    assert d["lectura_dudosa"] is True and d["montos_alternativos"] == [500000.0, 300000.0]
    assert "resumen_factura" not in d


def test_cobro_por_cuota_se_limpia_y_conserva_el_monto_una_vez():
    movs, _ = c._parse_nu(TARJETA, "2026")
    cobro = next(m for m in movs if m["descripcion"] == "Cobro por cuota")
    assert cobro["monto"] == 9000.0 and cobro["tipo"] == "expense" and "lectura_dudosa" not in cobro
    anio = c.limpiar_descripcion_cobro("2026 Cobro por cuota $9.000,00 - $9.000,00 -", 9000.0)
    assert anio == "Cobro por cuota"
    assert c.limpiar_descripcion_cobro("Compra $9.000,00 y $5.000,00", 9000.0) is None


def test_la_huella_anterior_se_sigue_reconociendo():
    movs, _ = c._parse_nu(TARJETA, "2026")
    cobro = next(m for m in movs if m["descripcion"] == "Cobro por cuota")
    cobro["cuenta"] = "cta"
    previa = cobro["huella_anterior"]
    vieja = c.compute_fingerprint(previa["fecha"], previa["monto"], "cta", previa["descripcion"], previa["tipo"])
    nueva = c.compute_fingerprint(cobro["fecha"], cobro["monto"], "cta", cobro["descripcion"], cobro["tipo"])
    assert vieja != nueva
    ledger = [{"id": "m1", "fecha": datetime(2026, 10, 14), "monto": 9000.0, "tipo": "expense",
               "descripcion": previa["descripcion"], "fingerprint": vieja}]
    for cruzar in (False, True):
        r = c.auditar_movimientos([dict(cobro)], ledger, cruzar_rapidos=cruzar)
        assert r["review"][0]["estado"] == "exacto" and r["review"][0]["fingerprint"] == vieja
    # sin nada registrado, la línea usa la huella nueva
    r = c.auditar_movimientos([dict(cobro)], [], cruzar_rapidos=True)
    assert r["review"][0]["fingerprint"] == nueva and r["review"][0]["estado"] == "faltante"


def test_casilla_del_pago_solo_se_enciende_con_salida_igual_en_ahorros_del_mismo_banco():
    from app.database import SessionLocal
    from app.models import Cuenta, Movimiento
    db = SessionLocal()
    try:
        tarjeta = Cuenta(usuario_id="res-1", nombre="Nu Tarjeta", tipo="credito", saldo=0)
        ahorro = Cuenta(usuario_id="res-1", nombre="Nu Colombia", tipo="ahorro", saldo=0)
        db.add_all([tarjeta, ahorro])
        db.flush()
        db.add(Movimiento(usuario_id="res-1", cuenta_id=ahorro.id, descripcion="Pago tarjeta", categoria="Otros",
                          tipo="expense", monto=300000.0, fecha=datetime(2026, 10, 4, 10)))
        db.commit()
        movs, _ = c._parse_nu(TARJETA, "2026")
        pago = next(m for m in movs if m.get("resumen_factura"))
        con = {**pago, "estado": "faltante"}
        _confirmar_pagos_de_factura(db, "res-1", tarjeta, "nu", [con])
        assert con["marcar_por_defecto"] is True and con["aviso_linea"] is None
        sin = {**pago, "estado": "faltante", "monto": 310000.0}
        _confirmar_pagos_de_factura(db, "res-1", tarjeta, "nu", [sin])
        assert sin["marcar_por_defecto"] is False and "Confirma el monto" in sin["aviso_linea"]
    finally:
        db.close()
