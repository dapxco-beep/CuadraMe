"""Genera pwa/src/lib/paises.js (espejo de app/paises.py). Uso, desde backend/:
    python tools/generar_paises_js.py
La prueba tests/test_paises.py verifica que el espejo no se desactualice."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import paises  # noqa: E402

DESTINO = os.path.join(os.path.dirname(__file__), "..", "..", "pwa", "src", "lib", "paises.js")

CABECERA = """// GENERADO desde backend/app/paises.py con `python tools/generar_paises_js.py`. NO editar a mano:
// cambia el registro en Python y regenera (tests/test_paises.py verifica la paridad).
// Un solo lugar con lo que cambia de un país a otro: moneda, formato, bancos, funciones fiscales.
"""

COLA = """
export const PAIS_POR_DEFECTO_LEGADO = 'CO'

export function paisValido(codigo) {
  return !!codigo && !!PAISES[codigo] && PAISES[codigo].disponible
}

// Un país desconocido NO cae a Colombia: devuelve null (el que llama decide).
export function configPais(codigo) {
  return PAISES[String(codigo || '').toUpperCase()] || null
}

export function tieneFuncion(codigo, funcion) {
  const c = configPais(codigo)
  return !!c && c.funciones_fiscales.includes(funcion)
}

export function paisesDisponibles() {
  return ORDEN.filter((c) => PAISES[c].disponible).map((c) => PAISES[c])
}

export function bancosDePais(codigo) {
  return (configPais(codigo) || { bancos: [] }).bancos
}

// Sugerencia (nunca decisión): zona horaria o región del idioma. Sin IP ni geolocalización.
export function sugerirPais(idiomaNavegador, zonaHoraria) {
  if (zonaHoraria) {
    const hit = Object.values(PAISES).find((c) => c.disponible && c.zona_horaria === zonaHoraria)
    if (hit) return hit.codigo
  }
  if (idiomaNavegador && idiomaNavegador.includes('-')) {
    const region = idiomaNavegador.split('-').pop().toUpperCase()
    if (paisValido(region)) return region
  }
  return null
}
"""

datos = {c: paises.PAISES[c] for c in paises.ORDEN}
with open(DESTINO, "w", encoding="utf-8", newline="\n") as f:
    f.write(CABECERA)
    f.write("export const PAISES = " + json.dumps(datos, ensure_ascii=False, indent=2) + "\n\n")
    f.write("export const ORDEN = " + json.dumps(paises.ORDEN) + "\n")
    f.write(COLA)
print("ok", DESTINO)
