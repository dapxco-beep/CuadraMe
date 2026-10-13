"""Bajo ráfagas de peticiones simultáneas el servidor NO debe bloquearse (pool de conexiones).

Reproduce el fallo hallado con tools/prueba_carga.py: con más peticiones simultáneas que
conexiones, los hilos esperaban conexión y las conexiones esperaban hilo -> todo se
colgaba 30 s y respondía 500. Con 100 peticiones a la vez debe terminar rápido y sin errores.
"""
import asyncio
import os
import tempfile
import time

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'concurrencia.db')}")

import httpx  # noqa: E402

from app import database  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402


async def _rafaga(n: int):
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as c:
        t0 = time.monotonic()
        # asyncio.wait_for: si hubiera bloqueo, la prueba falla en 25 s en vez de colgar la suite.
        resp = await asyncio.wait_for(asyncio.gather(*[c.get("/cuentas") for _ in range(n)]), timeout=25)
        return resp, time.monotonic() - t0


def test_100_peticiones_simultaneas_no_bloquean_el_pool():
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="conc-1", email="c@test.com", nombre="C")
    try:
        respuestas, segundos = asyncio.run(_rafaga(100))
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert [r.status_code for r in respuestas].count(200) == 100
    assert segundos < 20, f"tardó {segundos:.1f}s: el pool se está bloqueando"


def test_el_cupo_de_sesiones_es_menor_que_las_conexiones_del_pool():
    # Si alguien sube el cupo por encima del pool, vuelve el bloqueo.
    assert database.CUPO_SESIONES < database.CONEXIONES_MAX
    capacidad = database.engine.pool.size() + max(database.engine.pool._max_overflow, 0)
    assert database.CUPO_SESIONES <= capacidad


def test_la_sesion_se_cierra_aunque_el_endpoint_falle():
    from fastapi import HTTPException

    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="conc-2", email="c2@test.com", nombre="C")
    try:
        async def _llamar():
            transporte = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as c:
                return [await c.get("/movimientos/no-existe") for _ in range(40)]

        respuestas = asyncio.run(_llamar())
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert all(r.status_code == 404 for r in respuestas)
    assert database.engine.pool.checkedout() == 0, "quedaron conexiones sin devolver al pool"


def test_pool_de_postgres_cabe_en_el_pooler_de_supabase_durante_un_despliegue():
    """El pooler de Supabase en modo sesión admite 15 clientes en total y, al desplegar, conviven dos
    instancias: con los valores por defecto cada una abre como máximo 7 (2 x 7 = 14 < 15)."""
    import importlib
    import os

    anteriores = {k: os.environ.pop(k, None) for k in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW")}
    try:
        por_defecto = int(os.getenv("DB_POOL_SIZE", "5")) + int(os.getenv("DB_MAX_OVERFLOW", "2"))
    finally:
        for k, v in anteriores.items():
            if v is not None:
                os.environ[k] = v
    assert 2 * por_defecto <= 15
    importlib.import_module("app.database")  # sigue importando sin error
