"""Prueba extractos PDF contra el lector de la app y resume qué entiende de cada uno.

Sirve para «alimentar» la app con formatos nuevos: se pasa una carpeta (o archivos) y sale una tabla con el banco que
detecta, el formato, cuántos movimientos lee y si lo leído cuadra con los totales que imprime el propio extracto.
NO imprime nombres, cuentas ni cifras: solo conteos y estados. Nada se guarda en la base de datos ni sale de este equipo.

    cd backend
    venv/Scripts/python.exe tools/probar_extractos.py "C:/Users/yo/Downloads" --desde-hoy
    venv/Scripts/python.exe tools/probar_extractos.py extracto.pdf --clave 12345 --texto salida_textos

  --desde-hoy   solo PDFs modificados en las últimas 24 horas
  --clave X     clave del PDF (si la tienen)
  --texto DIR   además guarda el texto extraído de cada PDF en DIR (útil para escribir el lector del formato nuevo;
                ese texto trae datos personales: no se sube al repositorio, usa textos sintéticos en las pruebas)
"""
from __future__ import annotations

import argparse
import base64
import glob
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app import conciliacion as c  # noqa: E402
from app import extractos_co  # noqa: E402
from app.pdf_extract import pdf_a_texto, pdf_pide_clave  # noqa: E402


def _archivos(entradas: list[str], desde_hoy: bool) -> list[str]:
    salida: list[str] = []
    for e in entradas:
        salida += glob.glob(os.path.join(e, "*.pdf")) if os.path.isdir(e) else [e]
    if desde_hoy:
        limite = time.time() - 86400
        salida = [a for a in salida if os.path.getmtime(a) >= limite]
    return sorted(salida, key=os.path.getmtime)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entradas", nargs="+", help="PDFs o carpetas con PDFs")
    ap.add_argument("--desde-hoy", action="store_true")
    ap.add_argument("--clave", default="")
    ap.add_argument("--texto", default="", help="carpeta donde guardar el texto extraído de cada PDF")
    args = ap.parse_args()
    if args.texto:
        os.makedirs(args.texto, exist_ok=True)

    archivos = _archivos(args.entradas, args.desde_hoy)
    if not archivos:
        print("No hay PDFs que probar.")
        return 1
    print(f"{'#':>2} {'KB':>6} {'banco':<12} {'formato':<22} {'movs':>5} {'cuadra':<7} {'huecos':>6}  nota")
    sin_leer = 0
    for i, ruta in enumerate(archivos, 1):
        b64 = base64.b64encode(open(ruta, "rb").read()).decode()
        kb = round(os.path.getsize(ruta) / 1024)
        try:
            texto = pdf_a_texto(b64, args.clave)
        except Exception as e:  # noqa: BLE001 - un PDF roto no detiene la revisión de los demás
            print(f"{i:>2} {kb:>6} {'-':<12} {'-':<22} {'-':>5} {'-':<7} {'-':>6}  error al abrir ({type(e).__name__})")
            sin_leer += 1
            continue
        if not texto:
            nota = "pide clave (usa --clave)" if pdf_pide_clave(b64, args.clave) else "sin texto (¿escaneado como imagen?)"
            print(f"{i:>2} {kb:>6} {'-':<12} {'-':<22} {'-':>5} {'-':<7} {'-':>6}  {nota}")
            sin_leer += 1
            continue
        if args.texto:
            open(os.path.join(args.texto, f"{i:02d}.txt"), "w", encoding="utf-8").write(texto)
        banco = c.detectar_banco(texto)
        lectura = extractos_co.leer(texto)
        movs, descartados = c.parse_texto_con_regex(texto)
        formato = lectura["formato"] if lectura else ("(parser por banco)" if movs else "-")
        cuadra = "-" if not lectura or lectura["lectura_completa"] is None else ("sí" if lectura["lectura_completa"] else "NO")
        huecos = lectura.get("huecos", 0) if lectura else 0
        nota = ""
        if not movs:
            nota = "NO LO LEE: falta un lector para este formato"
            sin_leer += 1
        elif descartados:
            nota = "puede faltar algo (no cuadra con el resumen)"
        elif huecos:
            nota = f"faltan {huecos} mes(es) en el PDF"
        print(f"{i:>2} {kb:>6} {banco:<12} {formato:<22} {len(movs):>5} {cuadra:<7} {huecos:>6}  {nota}")
    print(f"\n{len(archivos) - sin_leer} de {len(archivos)} se leen.")
    return 0 if not sin_leer else 2


if __name__ == "__main__":
    raise SystemExit(main())
