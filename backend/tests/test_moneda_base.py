"""Totales en la moneda base del perfil: regla única a_base / ConvertidorBase (contabilidad.py).

Los casos de fixtures/moneda_base_casos.json son los MISMOS que prueba la PWA
(pwa/src/test/contabilidad_paridad.test.js). Datos solo sintéticos."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import contabilidad as c  # noqa: E402
from app import fx  # noqa: E402

CASOS = json.loads((Path(__file__).parent / "fixtures" / "moneda_base_casos.json").read_text(encoding="utf-8"))["casos"]


@pytest.mark.parametrize("caso", CASOS, ids=[x["nombre"] for x in CASOS])
def test_a_base_paridad_con_la_pwa(caso):
    valor, ok = c.a_base(caso["monto"], caso["origen"], caso["base"], caso["tasas"])
    assert (round(valor, 6), ok) == (caso["esperado"][0], caso["esperado"][1])


def test_mono_moneda_cop_es_identico_y_sin_tocar_fx(monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("mono-moneda no debe consultar tasas")

    monkeypatch.setattr(fx, "tasa", prohibido)
    conv = c.ConvertidorBase("COP")
    assert conv(123456.78, "COP") == 123456.78
    assert conv(5, None) == 5
    assert conv.sin_tasa == set()


def test_convertidor_usa_tasa_manual_y_marca_sin_tasa():
    fx.borrar_tasas_manuales()
    fx.usar_proveedor(lambda base: {})
    try:
        fx.fijar_tasa_manual("USD", "MXN", 17.0)
        conv = c.ConvertidorBase("MXN")
        assert conv(10, "USD") == pytest.approx(170.0)
        assert conv(100, "MXN") == 100
        assert conv(5, "XYZ") == 5  # sin tasa: no se inventa, queda marcada
        assert conv.sin_tasa == {"XYZ"}
    finally:
        fx.borrar_tasas_manuales()
        fx.usar_proveedor(None)
