"""Nequi desde el atajo de iPhone: textos reales de las notificaciones."""
import pytest

from app.notificaciones import interpretar, pide_monto


def test_recibiste_plata_sin_signo_pesos():
    n = interpretar("Nequi", "Envío", "DANIEL PARRADO te envió 1, ¡lo mejor!")
    assert (n.tipo, n.monto, n.comercio, n.app) == ("income", 1, "De Daniel Parrado", "Nequi")


@pytest.mark.parametrize("texto,monto", [
    ("ANA PEREZ te envió $45.000, ¡lo mejor!", 45000),
    ("ANA PEREZ te envió 1.250.000 ¡lo mejor!", 1250000),
])
def test_recibiste_plata_es_ingreso_aunque_traiga_pesos(texto, monto):
    n = interpretar("Nequi", "Envío", texto)
    assert (n.tipo, n.monto) == ("income", monto)


def test_enviaste_plata_no_trae_monto_hay_que_preguntar():
    t, x = "Tu plata llegó con éxito 💜", "Envío exitoso, la plata ya está en el Nequi destino. Recuerda que no se puede cancelar."
    assert interpretar("Nequi", t, x) is None
    assert pide_monto("Nequi", t, x)


def test_ofertas_no_piden_monto_ni_se_registran():
    assert not pide_monto("Nequi", "Ofertas", "Todos piden OFERTA a solo $14.968")
    assert interpretar("Nequi", "Ofertas", "Todos piden OFERTA a solo $14.968") is None


def test_android_no_cambia():
    assert interpretar("com.nequi.MobileApp", "Envío", "DANIEL PARRADO te envió 1, ¡lo mejor!").tipo == "income"
