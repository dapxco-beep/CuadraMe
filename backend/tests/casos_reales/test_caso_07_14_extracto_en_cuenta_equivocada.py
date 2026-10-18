"""CASOS REALES 7 y 14: extracto de la tarjeta de crédito Nu cayó en la cuenta de AHORROS.

7. El usuario tenía una sola cuenta «Nu Colombia» (ahorros). Subió/recibió el extracto de su tarjeta de
   crédito y el sistema lo asignó a esa cuenta: las compras de la tarjeta restaron saldo de ahorros y la
   deuda de la tarjeta no aparecía. Reglas que lo evitan: (a) un extracto de tarjeta NO se asigna solo a la
   única cuenta de ahorros; (b) si existe UNA tarjeta del mismo banco, se sugiere «cambiar la cuenta»;
   (c) la tarjeta nueva se puede crear con la deuda declarada.
14. «Cambiar la cuenta de este extracto» mueve SOLO los movimientos que ese extracto importó; los saldos de
   ambas cuentas se ajustan en sentido contrario (el patrimonio total no cambia); repetirlo no mueve nada.
Datos sintéticos.
"""
from datetime import timedelta
from types import SimpleNamespace

from app import extractos_gmail as eg
from app.models import HistorialExtracto
from app.reasignar_extracto import sugerir_cuenta_credito
from app.utiles import ahora_co
# `mundo` arma ahorros 880.000 + tarjeta -300.000 con 3 compras (120.000) importadas por un extracto;
# `_auth` (autouse) pone al usuario de prueba.
from tests.test_reasignar_extracto import _auth, _cambiar, _saldo, client, mundo  # noqa: F401

TEXTO_TARJETA = "Extracto de tu tarjeta de crédito Nu. Cupo total, pago mínimo, fecha límite de pago"
TEXTO_CUENTA = "Extracto de tu cuenta de ahorros Nu. Cajita, saldo disponible"


def _c(id_, nombre, tipo):
    return SimpleNamespace(id=id_, nombre=nombre, tipo=tipo, alias_tarjeta=None, moneda="COP")


def test_caso7_extracto_de_tarjeta_no_se_asigna_a_la_unica_cuenta_de_ahorros():
    ahorro = _c("ah", "Nu Colombia", "ahorro")
    assert eg.sugerir_cuenta("Nu Colombia", "", [ahorro], TEXTO_TARJETA) is None
    assert eg.sugerir_cuenta("Nu Colombia", "", [ahorro], TEXTO_CUENTA) == "ah"
    tarjeta = _c("tc", "Nu Tarjeta", "credito")
    assert eg.sugerir_cuenta("Nu Colombia", "", [ahorro, tarjeta], TEXTO_TARJETA) == "tc"


def test_caso7_si_ya_cayo_en_ahorros_se_sugiere_la_tarjeta_solo_cuando_corresponde():
    ahorro, tarjeta = _c("ah", "Nu Colombia", "ahorro"), _c("tc", "Nu Colombia Crédito", "credito")
    h = HistorialExtracto(usuario_id="x", cuenta_id="ah")
    assert sugerir_cuenta_credito(h, ahorro, [ahorro, tarjeta], TEXTO_TARJETA) == {"cuenta_id": "tc", "nombre": "Nu Colombia Crédito"}
    assert sugerir_cuenta_credito(h, ahorro, [ahorro, tarjeta], TEXTO_CUENTA) is None      # es de la cuenta
    assert sugerir_cuenta_credito(h, ahorro, [ahorro], TEXTO_TARJETA) is None               # no hay tarjeta
    otra = _c("dv", "Davivienda Visa", "credito")
    assert sugerir_cuenta_credito(h, ahorro, [ahorro, otra], TEXTO_TARJETA) is None         # otro banco
    assert sugerir_cuenta_credito(h, tarjeta, [ahorro, tarjeta], TEXTO_TARJETA) is None     # ya está en la tarjeta


def test_caso7_se_crea_la_cuenta_de_tarjeta_con_deuda_declarada():
    hoy = ahora_co()
    r = client.post("/cuentas", json={
        "nombre": "Nu Tarjeta Caso7", "tipo": "credito", "saldo": -450_000, "cupo_total": 3_000_000,
        "dia_corte": (hoy - timedelta(days=10)).day, "dia_pago": (hoy - timedelta(days=5)).day,
    })
    assert r.status_code == 200, r.text
    cuenta = r.json()
    assert cuenta["tipo"] == "credito" and cuenta["saldo"] == -450_000
    assert cuenta["tarjeta"]["saldo_declarado"] is True


def test_caso14_cambiar_la_cuenta_mueve_saldos_sin_cambiar_el_patrimonio(mundo):  # noqa: F811
    antes = _saldo(mundo["ahorro"]) + _saldo(mundo["tarjeta"])
    r = _cambiar(mundo["historial"], mundo["tarjeta"])
    assert r.status_code == 200, r.text
    assert r.json()["movidos"] == 3
    # Las 3 compras (120.000) se devuelven a ahorros y pasan a la deuda de la tarjeta: la suma no cambia.
    assert _saldo(mundo["ahorro"]) == 1_000_000 and _saldo(mundo["tarjeta"]) == -420_000
    assert _saldo(mundo["ahorro"]) + _saldo(mundo["tarjeta"]) == antes == 580_000
    segunda = _cambiar(mundo["historial"], mundo["tarjeta"]).json()
    assert segunda["movidos"] == 0 and segunda["sin_cambios"] is True
    assert _saldo(mundo["ahorro"]) == 1_000_000 and _saldo(mundo["tarjeta"]) == -420_000
