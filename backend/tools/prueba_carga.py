"""
Prueba de carga ligera de CuadraMe (datos 100 % sintéticos, base SQLite temporal).

NO toca producción ni lee secretos: crea su propia base en un archivo temporal, levanta la
app en un puerto local y la golpea con usuarios virtuales (asyncio + httpx).

Uso (desde backend/):
    python tools/prueba_carga.py                       # 100 usuarios, 30 s
    python tools/prueba_carga.py --usuarios 50 --segundos 15
    python tools/prueba_carga.py --modo consultas      # cuenta consultas SQL por endpoint (detecta N+1)

Dos modos:
  carga      100 usuarios concurrentes con una mezcla realista de lecturas y algunas escrituras.
             Reporta por endpoint: peticiones, errores, p50 / p95 / máximo (ms) y req/s.
  consultas  UN usuario con muchos datos; cuenta cuántas sentencias SQL ejecuta cada endpoint.
             Si ese número crece con la cantidad de datos, hay un N+1.

Decisiones:
  * La autenticación real (JWT de Supabase) se reemplaza por una cabecera X-Usuario-Prueba,
    solo dentro de este script (dependency_overrides). Así no se necesita ninguna credencial.
  * SQLite serializa las escrituras: la latencia de POST aquí es PEOR que en Postgres. Sirve
    para comparar antes/después y encontrar consultas innecesarias, no para dimensionar Railway.
"""
import argparse
import asyncio
import os
import random
import socket
import statistics
import sys
import tempfile
import multiprocessing
import time
from collections import defaultdict
from datetime import timedelta

# --- Entorno aislado: ANTES de importar la app -------------------------------------------
_dir = os.environ.get("CUADRAME_CARGA_DIR") or tempfile.mkdtemp(prefix="cuadrame_carga_")
os.environ["CUADRAME_CARGA_DIR"] = _dir  # el proceso hijo (servidor) reutiliza la misma base
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_dir, 'carga.db').replace(os.sep, '/')}"
os.environ.setdefault("CRON_SECRET", "secreto-de-carga")
os.environ.setdefault("EXIGIR_CONSENTIMIENTOS", "false")
os.environ["ENVIRONMENT"] = "load-test"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import Header  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Deuda, Meta, Movimiento, Presupuesto, Recurrente  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

CATEGORIAS = ["Comida", "Transporte", "Mercado", "Ocio", "Salud", "Servicios", "Otros"]


def _usuario_de_cabecera(x_usuario_prueba: str = Header(default="")):
    return UsuarioActual(id=x_usuario_prueba, email=f"{x_usuario_prueba}@carga.test", nombre="Carga")


app.dependency_overrides[get_current_user] = _usuario_de_cabecera


def sembrar(n_usuarios: int, movs_por_usuario: int, cuentas_por_usuario: int = 4, n_presupuestos: int = 5) -> list[str]:
    """Datos sintéticos por usuario: cuentas, movimientos, presupuestos, metas, recurrentes, deudas."""
    rnd = random.Random(7)
    ids = [f"carga-{i:04d}" for i in range(n_usuarios)]
    ahora = ahora_co()
    db = SessionLocal()
    try:
        for uid in ids:
            cuentas = [Cuenta(usuario_id=uid, nombre=f"Cuenta {k}", saldo=1_000_000, moneda="COP")
                       for k in range(cuentas_por_usuario)]
            db.add_all(cuentas)
            db.flush()
            movs = []
            for j in range(movs_por_usuario):
                tipo = "income" if rnd.random() < 0.15 else "expense"
                movs.append(Movimiento(
                    usuario_id=uid, cuenta_id=rnd.choice(cuentas).id,
                    fecha=ahora - timedelta(days=rnd.randint(0, 120), hours=rnd.randint(0, 23)),
                    descripcion=f"Compra sintética {rnd.randint(1, 60)}", categoria=rnd.choice(CATEGORIAS),
                    tipo=tipo, monto=float(rnd.randint(2, 400) * 1000), fuente="manual"))
            db.bulk_save_objects(movs)
            for c in (CATEGORIAS + [f"Cat {k}" for k in range(40)])[:n_presupuestos]:
                db.add(Presupuesto(usuario_id=uid, categoria=c, limite=500_000))
            db.add_all([Meta(usuario_id=uid, nombre="Meta A", monto_objetivo=5_000_000, monto_actual=100_000),
                        Meta(usuario_id=uid, nombre="Meta B", monto_objetivo=2_000_000)])
            db.add_all([Recurrente(usuario_id=uid, nombre=f"Fijo {k}", monto=50_000, dia_del_mes=1 + k * 7,
                                   cuenta_id=cuentas[0].id) for k in range(3)])
            db.add_all([Deuda(usuario_id=uid, nombre=f"Deuda {k}", saldo_inicial=2_000_000, saldo_actual=1_500_000,
                              cuota_mensual=150_000, tasa_mensual=1.9) for k in range(2)])
            db.commit()
    finally:
        db.close()
    return ids


# Mezcla de tráfico: (método, ruta, peso). Refleja lo que hace la PWA al abrir Inicio y navegar.
MEZCLA = [
    ("GET", "/cuentas", 10), ("GET", "/cuentas/resumen", 8), ("GET", "/movimientos?limit=50", 12),
    ("GET", "/presupuestos", 6), ("GET", "/presupuestos/disponible-hoy", 6), ("GET", "/presupuestos/en-mi-bolsillo", 4),
    ("GET", "/reportes/mensual", 6), ("GET", "/reportes/tendencias", 4), ("GET", "/reportes/flujo-caja-futuro", 3),
    ("GET", "/insights/resumen-semanal", 4), ("GET", "/insights/alertas-proactivas", 3),
    ("GET", "/insights/salud-financiera", 3), ("GET", "/metas", 4), ("GET", "/recurrentes", 4), ("GET", "/deudas", 3),
    ("GET", "/informes/gasto", 3), ("GET", "/patrimonio", 3), ("GET", "/sincronizacion/estado", 3),
    ("GET", "/categorias", 4), ("GET", "/movimientos/por-revisar/conteo", 3),
    ("POST", "/movimientos", 6),  # escritura: registra un gasto
]


def _elegir(rnd):
    total = sum(p for _, _, p in MEZCLA)
    x = rnd.uniform(0, total)
    acumulado = 0
    for m, r, p in MEZCLA:
        acumulado += p
        if x <= acumulado:
            return m, r
    return MEZCLA[0][0], MEZCLA[0][1]


async def usuario_virtual(uid, cliente, fin, resultados, cuenta_id, rnd, pausa=(1.0, 3.0)):
    h = {"X-Usuario-Prueba": uid}
    while time.monotonic() < fin:
        metodo, ruta = _elegir(rnd)
        cuerpo = None
        if metodo == "POST":
            cuerpo = {"cuenta_id": cuenta_id, "descripcion": "Gasto de carga", "monto": 1000, "tipo": "expense"}
        t0 = time.perf_counter()
        try:
            r = await cliente.request(metodo, ruta, headers=h, json=cuerpo, timeout=60)
            estado = r.status_code
        except httpx.HTTPError as e:
            estado = type(e).__name__
        ms = (time.perf_counter() - t0) * 1000
        resultados[f"{metodo} {ruta.split('?')[0]}"].append((ms, estado))
        await asyncio.sleep(rnd.uniform(*pausa))  # "tiempo de lectura" de una persona


def _pct(valores, p):
    valores = sorted(valores)
    return valores[min(len(valores) - 1, int(len(valores) * p))]


async def correr_carga(ids, segundos, puerto, pausa=(1.0, 3.0)):
    resultados = defaultdict(list)
    limites = httpx.Limits(max_connections=len(ids) + 10, max_keepalive_connections=len(ids) + 10)
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{puerto}", limits=limites) as cliente:
        db = SessionLocal()
        cuentas = {uid: db.query(Cuenta.id).filter(Cuenta.usuario_id == uid).first()[0] for uid in ids}
        db.close()
        fin = time.monotonic() + segundos
        t0 = time.monotonic()
        await asyncio.gather(*[usuario_virtual(uid, cliente, fin, resultados, cuentas[uid], random.Random(i), pausa)
                               for i, uid in enumerate(ids)])
        duracion = time.monotonic() - t0
    return resultados, duracion


def reporte_carga(resultados, duracion):
    filas, total, errores = [], 0, 0
    for clave, datos in resultados.items():
        ms = [d[0] for d in datos]
        err = sum(1 for d in datos if d[1] != 200)
        total += len(datos)
        errores += err
        filas.append((clave, len(datos), err, statistics.median(ms), _pct(ms, 0.95), max(ms)))
    filas.sort(key=lambda f: -f[4])
    print(f"\n{'Endpoint':<42}{'n':>6}{'err':>5}{'p50 ms':>9}{'p95 ms':>9}{'max ms':>9}")
    for c, n, e, p50, p95, mx in filas:
        print(f"{c:<42}{n:>6}{e:>5}{p50:>9.0f}{p95:>9.0f}{mx:>9.0f}")
    todos = [d[0] for datos in resultados.values() for d in datos]
    print(f"\nTotal: {total} peticiones en {duracion:.1f}s = {total / duracion:.1f} req/s · errores: {errores} "
          f"· p50 global {statistics.median(todos):.0f} ms · p95 global {_pct(todos, 0.95):.0f} ms")


def modo_consultas(movs, cuentas=4, presupuestos=5):
    """Cuenta sentencias SQL por endpoint con UN usuario con muchos datos."""
    from fastapi.testclient import TestClient

    ids = sembrar(1, movs, cuentas, presupuestos)
    cliente = TestClient(app)
    h = {"X-Usuario-Prueba": ids[0]}
    contador = {"n": 0}

    @event.listens_for(engine, "before_cursor_execute")
    def _cuenta(conn, cursor, statement, parameters, context, executemany):
        contador["n"] += 1

    filas = []
    for metodo, ruta, _ in MEZCLA:
        if metodo != "GET":
            continue
        cliente.get(ruta, headers=h)  # calentamiento: la 1.ª vez algunos endpoints crean datos base
        contador["n"] = 0
        t0 = time.perf_counter()
        r = cliente.get(ruta, headers=h)
        filas.append((ruta, r.status_code, contador["n"], (time.perf_counter() - t0) * 1000))
    filas.sort(key=lambda f: -f[2])
    print(f"\nUsuario con {movs} movimientos, {cuentas} cuentas, {presupuestos} presupuestos, 2 metas, 3 recurrentes, 2 deudas")
    print(f"{'Endpoint':<42}{'HTTP':>6}{'SQL':>6}{'ms':>8}")
    for ruta, est, n, ms in filas:
        print(f"{ruta:<42}{est:>6}{n:>6}{ms:>8.0f}")
    return filas


def _servir(puerto: int):
    """Punto de entrada del proceso hijo: la app (con la autenticación de prueba) en uvicorn."""
    if os.environ.get("CARGA_VOLCADO"):  # diagnóstico: a los N segundos vuelca la pila de todos los hilos
        import faulthandler

        faulthandler.dump_traceback_later(int(os.environ["CARGA_VOLCADO"]), file=open(os.path.join(_dir, "hilos.txt"), "w"))
    if os.environ.get("CARGA_VOLCADO"):
        import threading

        def _estado():
            while True:
                time.sleep(2)
                with open(os.path.join(_dir, "pool.txt"), "a") as f:
                    f.write(f"{time.strftime('%X')} {engine.pool.status()}\n")

        threading.Thread(target=_estado, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["carga", "consultas"], default="carga")
    ap.add_argument("--usuarios", type=int, default=100)
    ap.add_argument("--segundos", type=int, default=30)
    ap.add_argument("--pausa", type=float, nargs=2, default=(1.0, 3.0), metavar=("MIN", "MAX"),
                    help="segundos entre peticiones de cada usuario (0.05 0.25 = saturación extrema)")
    ap.add_argument("--movimientos", type=int, default=300, help="movimientos sintéticos por usuario")
    ap.add_argument("--cuentas", type=int, default=4, help="cuentas por usuario")
    ap.add_argument("--presupuestos", type=int, default=5, help="presupuestos por usuario")
    ap.add_argument("--puerto", type=int, default=0, help="0 = elegir uno libre")
    a = ap.parse_args()

    if a.modo == "consultas":
        modo_consultas(a.movimientos, a.cuentas, a.presupuestos)
        return

    print(f"Sembrando {a.usuarios} usuarios x {a.movimientos} movimientos (SQLite temporal en {_dir})...")
    ids = sembrar(a.usuarios, a.movimientos, a.cuentas, a.presupuestos)
    if not a.puerto:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            a.puerto = s.getsockname()[1]
    # El servidor corre en OTRO proceso: si compartiera proceso con el generador de carga,
    # ambos pelearían por el mismo GIL de Python y las latencias saldrían infladas.
    proceso = multiprocessing.get_context("spawn").Process(target=_servir, args=(a.puerto,), daemon=True)
    proceso.start()
    limite_arranque = time.monotonic() + 60
    while True:
        try:
            if httpx.get(f"http://127.0.0.1:{a.puerto}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if not proceso.is_alive() or time.monotonic() > limite_arranque:
            sys.exit("El servidor local no arrancó (¿puerto ocupado?). Prueba con --puerto 0.")
        time.sleep(0.3)
    print(f"Servidor local listo. {a.usuarios} usuarios virtuales durante {a.segundos}s...")
    try:
        resultados, duracion = asyncio.run(correr_carga(ids, a.segundos, a.puerto, tuple(a.pausa)))
        reporte_carga(resultados, duracion)
    finally:
        proceso.terminate()
        proceso.join(timeout=5)


if __name__ == "__main__":
    main()
