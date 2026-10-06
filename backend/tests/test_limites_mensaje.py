"""El mensaje de 'demasiadas solicitudes' dice cuánto falta, y subir un lote entero no lo agota."""
import pytest
from fastapi import HTTPException

from app import limites


@pytest.fixture(autouse=True)
def _limpio():
    limites._eventos.clear()
    yield
    limites._eventos.clear()


def test_el_mensaje_incluye_cuanto_falta():
    for _ in range(3):
        limites.verificar_limite("t:1", 3, 3600, "Muchos intentos. Podrás seguir en {espera}.")
    with pytest.raises(HTTPException) as e:
        limites.verificar_limite("t:1", 3, 3600, "Muchos intentos. Podrás seguir en {espera}.")
    assert e.value.status_code == 429
    assert "{espera}" not in e.value.detail
    assert "minutos" in e.value.detail or "minuto" in e.value.detail
    assert int(e.value.headers["Retry-After"]) > 0


def test_mensaje_por_defecto_y_segundos():
    for _ in range(2):
        limites.verificar_limite("t:2", 2, 30)
    with pytest.raises(HTTPException) as e:
        limites.verificar_limite("t:2", 2, 30)
    assert "segundos" in e.value.detail and "{espera}" not in e.value.detail


def test_textos_de_espera():
    assert limites._texto_espera(5) == "5 segundos"
    assert limites._texto_espera(60) == "1 minuto"
    assert limites._texto_espera(61) == "2 minutos"
    assert limites._texto_espera(3600) == "60 minutos"


def test_un_lote_de_diez_extractos_no_agota_el_tope():
    """Regresión: con el tope anterior (10/hora) un solo lote de 10 archivos lo agotaba."""
    for _ in range(10):
        limites.verificar_limite("extracto:u1", 60, 3600, "x")   # no lanza
    for _ in range(40):
        limites.verificar_limite("extracto:u1", 60, 3600, "x")   # sigue cabiendo un segundo lote
