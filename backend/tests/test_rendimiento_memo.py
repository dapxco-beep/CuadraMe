"""La clasificación de costos y el quitar tildes se memorizan (los informes los llaman decenas de miles de veces
por petición). Estas pruebas aseguran que la memoria no cambia ningún resultado ni se puede corromper."""
from app import contabilidad as cont
from app import costos_financieros as cf


def test_clasificar_costo_devuelve_copias_que_no_dañan_la_memoria():
    a = cf.clasificar_costo("Cuota de manejo tarjeta")
    assert a is not None
    a["categoria"] = "MODIFICADA"
    a["tipo"] = "income"
    b = cf.clasificar_costo("Cuota de manejo tarjeta")
    assert b["categoria"] != "MODIFICADA" and b["tipo"] == "expense"
    assert a is not b


def test_clasificar_costo_sin_coincidencia_o_vacio_es_none():
    assert cf.clasificar_costo("Almuerzo con amigos") is None
    assert cf.clasificar_costo("") is None
    assert cf.clasificar_costo(None) is None
    assert cf.es_costo_o_rendimiento("Rendimientos financieros") is True
    assert cf.es_costo_o_rendimiento("Jumbo") is False


def test_sin_acentos_memorizado_sigue_igual():
    assert cont._sin_acentos("Envío a Mamá — Canción") == "Envio a Mama — Cancion"
    assert cont._sin_acentos("") == "" and cont._sin_acentos(None) == ""
