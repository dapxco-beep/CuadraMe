"""Servidor LOCAL de auditoría visual: la API real con una base SQLite temporal y los datos de la demo.

No toca producción ni ningún dato real: un usuario fijo (sin Supabase), consentimiento ya aceptado y los datos
de ejemplo de `backend/tools/demo/cuadrame-demo.zip` (o el zip que indique la variable DEMO_ZIP).
Ver docs/AUDITORIA_VISUAL.md para el recorrido completo.

    cd backend
    PYTHONPATH=. venv/Scripts/python.exe tools/auditoria_visual/servidor_auditoria.py
"""
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]  # carpeta backend/
sys.path.insert(0, str(RAIZ))
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'auditoria.db')}"
os.environ["CORS_ORIGINS_EXTRA"] = os.environ.get("CORS_ORIGINS_EXTRA", "http://localhost:5199")

from app.config import settings  # noqa: E402

settings.exigir_consentimientos = False

from app import importar_respaldo as ir  # noqa: E402
from app.auth import UsuarioActual, get_current_user, get_current_user_by_api_key  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Consentimiento, Perfil  # noqa: E402
from app.routers.consentimientos import VERSION_TEXTOS  # noqa: E402

U = UsuarioActual(id="auditoria-1", email="demo@example.com", nombre="Persona Demo")
app.dependency_overrides[get_current_user] = lambda: U
app.dependency_overrides[get_current_user_by_api_key] = lambda: U

zip_demo = os.environ.get("DEMO_ZIP") or str(RAIZ / "tools" / "demo" / "cuadrame-demo.zip")
datos = json.loads(zipfile.ZipFile(zip_demo).read("datos.json"))
db = SessionLocal()
try:
    db.add(Perfil(usuario_id=U.id, plan="free", nombre_preferido="Persona", nombre_confirmado=True))
    ahora = datetime.utcnow()
    db.add(Consentimiento(usuario_id=U.id, version=VERSION_TEXTOS, finalidad="tratamiento_basico", aceptado=True,
                          creado_en_utc=ahora, creado_en_co=ahora - timedelta(hours=5), origen="app"))
    db.commit()
    resumen = ir.importar(db, U.id, datos)
    db.commit()
    print("datos de la demo cargados:", {k: v.get("nuevos") for k, v in resumen.items() if isinstance(v, dict)}, flush=True)
finally:
    db.close()

import uvicorn  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
