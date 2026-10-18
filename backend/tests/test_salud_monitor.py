"""Monitor de salud para el dueño: contadores agregados y anónimos, umbrales, un solo aviso por día."""
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'monitor.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import avisos, salud_monitor  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Consentimiento, CorreoGasto, HistorialExtracto, Perfil, SyncGmail  # noqa: E402

client = TestClient(app)
CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}


@pytest.fixture()
def mundo():
    db = SessionLocal()
    yield db
    db.close()


def gmail(db, ceros=0, horas=1):
    u = f"mon-{uuid.uuid4().hex[:8]}"
    ahora = datetime.utcnow()
    db.add(Perfil(usuario_id=u, gmail_conectado=True, gmail_refresh_token_enc="t"))
    db.add(Consentimiento(usuario_id=u, version="1.1", finalidad="lectura_correo", aceptado=True, creado_en_utc=ahora, creado_en_co=ahora))
    db.add(SyncGmail(usuario_id=u, ceros_seguidos_mov=ceros, ultima_sync=ahora - timedelta(hours=horas)))
    db.commit()
    return u


def test_exige_secreto():
    assert client.post("/salud/cron/resumen").status_code == 401
    assert client.post("/salud/cron/resumen", headers={"X-Cron-Secret": "otro"}).status_code == 401


def test_contadores_agregados(mundo):
    db = mundo
    antes = salud_monitor.contadores(db)  # la base se comparte con otras pruebas: se mide la diferencia
    gmail(db)  # sano
    gmail(db, ceros=4)
    gmail(db, horas=70)
    db.add_all([HistorialExtracto(usuario_id="mon-x", cuenta_id="c", estado="error"),
                HistorialExtracto(usuario_id="mon-x", cuenta_id="c", estado="error")])
    db.add_all([CorreoGasto(usuario_id="mon-y", gmail_msg_id=f"m{i}", estado="descartado", monto=10) for i in range(5)])
    db.commit()
    despues = salud_monitor.contadores(db)
    assert {k: despues[k] - antes[k] for k in despues} == {
        "lectura_en_cero": 1, "extractos_en_error": 1, "descartados_altos": 1, "sin_sync_48h": 1, "con_gmail_activo": 3}


def _con_contadores(monkeypatch, **valores):
    base = {"lectura_en_cero": 0, "extractos_en_error": 0, "descartados_altos": 0, "sin_sync_48h": 0, "con_gmail_activo": 7}
    monkeypatch.setattr(salud_monitor, "contadores", lambda db: {**base, **valores})


def test_sin_umbral_superado_no_avisa(mundo, monkeypatch):
    llamadas = []
    monkeypatch.setattr(avisos, "registrar_evento", lambda *a, **k: llamadas.append(k))
    _con_contadores(monkeypatch, extractos_en_error=2, sin_sync_48h=1)  # por debajo de sus umbrales (3 y 2)
    r = client.post("/salud/cron/resumen", headers=CABECERA).json()
    assert r["superados"] == [] and r["alertado"] is False and llamadas == []


def test_umbral_superado_manda_un_aviso_sin_datos_personales(mundo, monkeypatch):
    llamadas = []
    monkeypatch.setattr(avisos, "registrar_evento", lambda tipo, **k: llamadas.append((tipo, k)))
    _con_contadores(monkeypatch, lectura_en_cero=1)
    r = client.post("/salud/cron/resumen", headers=CABECERA).json()
    assert r["superados"] == ["lectura_en_cero"] and r["alertado"] is True
    assert len(llamadas) == 1
    tipo, k = llamadas[0]
    assert tipo == "salud_datos_alerta" and k["clave_unica"].startswith("salud_datos:")  # una vez por día
    assert "1 con la lectura de correo en 0" in k["texto"]
    assert "usuario_id" not in json.dumps(k, default=str) and set(r["contadores"]) == set(salud_monitor.UMBRALES) | {"con_gmail_activo"}


def test_el_tipo_de_aviso_existe_para_el_dueno():
    assert "salud_datos_alerta" in avisos.TIPOS
