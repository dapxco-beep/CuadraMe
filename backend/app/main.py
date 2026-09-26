from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import cuentas, movimientos, presupuestos, reportes

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CuadraMe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringir a dominios reales en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cuentas.router)
app.include_router(movimientos.router)
app.include_router(presupuestos.router)
app.include_router(reportes.router)


@app.get("/health")
def health():
    return {"ok": True}
