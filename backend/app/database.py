from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
_es_sqlite = settings.database_url.startswith("sqlite")
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
