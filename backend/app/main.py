from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import (
    conciliacion,
    cuentas,
    deudas,
    metas,
    movimientos,
    pagos,
    presupuestos,
    recurrentes,
    reportes,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CuadraMe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://pwa-livid-nu.vercel.app",
    ],
    allow_origin_regex=r"https://pwa-.*-investia2\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cuentas.router)
app.include_router(movimientos.router)
app.include_router(pagos.router)
app.include_router(presupuestos.router)
app.include_router(reportes.router)
app.include_router(metas.router)
app.include_router(recurrentes.router)
app.include_router(deudas.router)
app.include_router(conciliacion.router)


@app.get("/health")
def health():
    return {"ok": True}
