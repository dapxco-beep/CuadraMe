"""CASO REAL 13: traslados entre cuentas propias contados como gasto/ingreso.

Qué pasó: al mover plata entre sus propias cuentas el usuario veía «gastos» e «ingresos» inflados, porque
el sistema no reconocía el traslado como propio cuando:
  * el banco TRUNCA el nombre del titular («Enviaste a CARLOS ANDRES PERE» por «Carlos Andres Perez Mora»),
  * la frase no trae nombre pero es mía («Envío a mi Nequi», «Bre-B a mi llave», «Movimiento entre cuentas»).
Y el riesgo contrario: una persona DISTINTA con el mismo nombre de pila («Carlos Pereira Gomez») no es mío.
Los traslados no cuentan en ingresos/gastos (regla única, app/contabilidad.py).
Nombres y cifras inventados.
"""
import pytest

from app import contabilidad as c

TITULAR = ["Carlos Andres Perez Mora"]


@pytest.mark.parametrize("descripcion,minimo", [
    ("Enviaste a CARLOS ANDRES PERE", 3),          # nombre truncado por el banco: prefijo del nombre completo
    ("Enviaste a CARLOS ANDRES PEREZ MORA", 4),    # nombre completo
])
def test_caso13_nombre_truncado_cuenta_como_propio(descripcion, minimo):
    assert c.menciones_propias(descripcion, TITULAR) >= minimo


@pytest.mark.parametrize("descripcion", [
    "Enviaste a CARLOS PEREIRA GOMEZ",   # otra persona con nombre parecido
    "Enviaste a Carlos",                   # solo el nombre de pila: no alcanza
    "Compra en EXITO CHIA",
])
def test_caso13_otra_persona_no_es_propio(descripcion):
    assert c.menciones_propias(descripcion, TITULAR) < 3


@pytest.mark.parametrize("descripcion", [
    "Envío a mi Nequi", "Bre-B a mi llave", "Consignación a cuenta propia",
    "Movimiento entre cuentas", "Traslado a cajita",
])
def test_caso13_frases_de_traslado_propio_sin_nombre(descripcion):
    assert c._es_propio_por_frase(descripcion), descripcion


@pytest.mark.parametrize("descripcion", ["Avance de obra", "Pago a mi proveedor", "Compra en Exito"])
def test_caso13_frases_parecidas_que_no_son_traslado(descripcion):
    assert not c._es_propio_por_frase(descripcion), descripcion
