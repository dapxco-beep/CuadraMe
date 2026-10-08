import asyncio
import weakref
from concurrent.futures import ThreadPoolExecutor

import anyio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
_es_sqlite = settings.database_url.startswith("sqlite")
# Conexiones máximas que el pool puede abrir (SQLite local usa el pool por defecto 5 + 10).
CONEXIONES_MAX = 15 if _es_sqlite else 20
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    # pre_ping descarta conexiones muertas antes de usarlas (Supabase cierra las
    # inactivas); recycle las renueva cada 30 min. Sin esto, tras un rato sin
    # tráfico la primera petición falla con "connection closed".
    **({} if _es_sqlite else {"pool_pre_ping": True, "pool_recycle": 1800, "pool_size": 10, "max_overflow": 10}),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Peticiones que pueden tener una sesión abierta AL MISMO TIEMPO: dos menos que las conexiones
# del pool, así ninguna petición espera nunca por una conexión (ver get_db).
CUPO_SESIONES = CONEXIONES_MAX - 2
# Hilos exclusivos para cerrar sesiones (devolver la conexión al pool).
_cierres = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cierre-sesion")
# Un semáforo por bucle de eventos (el de asyncio se amarra al bucle donde se usa).
_cupos: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _cupo_del_bucle() -> asyncio.Semaphore:
    bucle = asyncio.get_running_loop()
    if bucle not in _cupos:
        _cupos[bucle] = asyncio.Semaphore(CUPO_SESIONES)
    return _cupos[bucle]


async def get_db():
    """Una sesión por petición. Es `async` y limita las sesiones abiertas a propósito.

    El problema que resuelve (reproducido con tools/prueba_carga.py, 100 usuarios simultáneos:
    1,7 peticiones/s y 100 % de errores 500 tras 30 s): FastAPI ejecuta los endpoints síncronos
    en un pool de hilos y, DESPUÉS de cada endpoint, necesita OTRO hilo para serializar la
    respuesta. Si hay más peticiones que conexiones, los hilos se llenan de endpoints esperando
    una conexión libre, y las conexiones están retenidas por peticiones ya terminadas que
    esperan un hilo para serializar y cerrar la sesión. Todos esperan a todos hasta el
    timeout del pool.

    Solución: una petición no empieza hasta que haya una conexión garantizada para ella (el
    semáforo espera en el bucle de eventos, sin gastar hilos) y la sesión se cierra en hilos
    propios. Así nadie bloquea un hilo esperando una conexión y el sistema solo se pone en
    cola (más lento), nunca se bloquea."""
    async with _cupo_del_bucle():
        db = SessionLocal()
        try:
            yield db
        finally:
            # shield: si el cliente se desconecta (cancelación), igual hay que devolver la conexión.
            with anyio.CancelScope(shield=True):
                await asyncio.get_running_loop().run_in_executor(_cierres, db.close)
