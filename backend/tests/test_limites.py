import pytest
from fastapi import HTTPException

from app.limites import verificar_limite


def test_limite_bloquea_al_superar_el_maximo():
    for _ in range(3):
        verificar_limite("t:a", 3, 60)
    with pytest.raises(HTTPException) as e:
        verificar_limite("t:a", 3, 60)
    assert e.value.status_code == 429
    verificar_limite("t:b", 3, 60)  # otra clave no se ve afectada
