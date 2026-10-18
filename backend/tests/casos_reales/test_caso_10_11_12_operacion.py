"""CASOS REALES 10, 11 y 12: fallos de operación (no de lectura de correos).

10. Migración desplegada editada. Se agregaron columnas editando la migración 0001, que ya había corrido en
    producción: en la base real no se ejecutaron y la app dio 500 («UndefinedColumn datos_cuerpo»). Regla:
    una migración desplegada NO se edita; lo nuevo es una migración nueva AL FINAL. Aquí se congelan las
    seis migraciones desplegadas (0001-0006) y se exige que lo nuevo vaya después, con número consecutivo.
11. Error 500 sin CORS. Un error inesperado respondía 500 sin cabeceras CORS y el navegador lo mostraba como
    «sin conexión» (el usuario creía que era su internet). Todo 500 debe llevar CORS y un `detail`.
12. Importar dos veces / en paralelo. El reintento de la cola offline de la PWA o un doble toque importaba
    dos veces el mismo extracto y duplicaba movimientos y saldo. Debe crearse UN solo juego.
Datos sintéticos.
"""
import hashlib
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy.exc import ProgrammingError

from app.config import settings
from app.main import app
from app.migraciones import MIGRACIONES
# Reutiliza el armado de un extracto con 3 líneas faltantes y los helpers de saldo / conteo.
from tests.test_importar_idempotente import _auth, _historial_con_faltantes, _movs, _saldo, client  # noqa: F401

# id -> (nº de sentencias, huella sha256 recortada). Desplegadas: NO se tocan. Para una migración nueva se
# AGREGA una fila al final de este diccionario (no se modifica ninguna anterior).
DESPLEGADAS = {
    "0001_columnas_historicas": (77, "83b84688c8f5e091"),
    "0002_nombre_titular_y_datos_cuerpo": (2, "dd8572b8cbfabe74"),
    "0003_subcategorias": (4, "743e43a5c91f4f1f"),
    "0004_titulo_personalizado": (3, "74d08cac942de6f7"),
    "0005_tasas_manuales": (2, "9653fbb12b0168fb"),
    "0006_resumen_lectura_mov": (3, "a290648757cf0b8c"),
}


def _huella(sentencias):
    return (len(sentencias), hashlib.sha256(chr(10).join(sentencias).encode()).hexdigest()[:16])


# ── Caso 10 ────────────────────────────────────────────────────────────────────────────────
def test_caso10_las_migraciones_desplegadas_no_cambian():
    actuales = {mid: _huella(s) for mid, s in MIGRACIONES}
    for mid, esperado in DESPLEGADAS.items():
        assert actuales.get(mid) == esperado, (
            f"La migración {mid} ya corrió en producción y fue editada o borrada. "
            "No se edita: agrega una migración nueva al final de app/migraciones.py."
        )


def test_caso10_lo_nuevo_va_al_final_y_con_numero_consecutivo():
    ids = [mid for mid, _ in MIGRACIONES]
    assert ids[: len(DESPLEGADAS)] == list(DESPLEGADAS), "el orden de las desplegadas no puede cambiar"
    numeros = [int(i.split("_", 1)[0]) for i in ids]
    assert numeros == list(range(1, len(ids) + 1)), "los números deben ser consecutivos y sin repetir"
    assert len(set(ids)) == len(ids)
    for mid, s in MIGRACIONES[len(DESPLEGADAS):]:
        # Una migración nueva (aún sin desplegar) puede existir; al desplegarla se suma a DESPLEGADAS.
        assert s, f"{mid} está vacía"


# ── Caso 11 ────────────────────────────────────────────────────────────────────────────────
@app.get("/_caso11_columna_inexistente")
def _columna_inexistente():
    raise ProgrammingError("SELECT datos_cuerpo FROM correos_gasto", {}, Exception("UndefinedColumn: datos_cuerpo"))


@app.get("/_caso11_error_cualquiera")
def _error_cualquiera():
    raise RuntimeError("fallo inesperado de prueba")


def test_caso11_todo_500_lleva_cors_y_detalle():
    c = TestClient(app, raise_server_exceptions=False)
    for ruta in ("/_caso11_columna_inexistente", "/_caso11_error_cualquiera"):
        r = c.get(ruta, headers={"Origin": settings.pwa_url})
        assert r.status_code == 500, ruta
        assert r.headers.get("access-control-allow-origin") == settings.pwa_url, f"{ruta}: 500 sin CORS = «sin conexión»"
        assert "detail" in r.json()


# ── Caso 12 ────────────────────────────────────────────────────────────────────────────────
def test_caso12_importar_dos_veces_seguidas_no_duplica():
    cuenta, hid, fps = _historial_con_faltantes("caso12-seq")
    a = client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": fps}).json()
    b = client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": fps}).json()
    assert a["importados"] == 3 and b["importados"] == 0 and b["ya_importado"] is True
    assert _movs("caso12-seq") == 3
    assert _saldo(cuenta["id"]) == 400  # 1000 - (100 + 200 + 300): el saldo se movió UNA vez


def test_caso12_importar_en_paralelo_crea_un_solo_juego():
    cuenta, hid, fps = _historial_con_faltantes("caso12-par")

    def _llamar(_):
        return client.post(f"/conciliacion/historial/{hid}/importar", json={"fingerprints": fps}).json()

    with ThreadPoolExecutor(max_workers=4) as pool:
        resultados = list(pool.map(_llamar, range(4)))
    assert sorted(r["importados"] for r in resultados) == [0, 0, 0, 3]
    assert _movs("caso12-par") == 3 and _saldo(cuenta["id"]) == 400
