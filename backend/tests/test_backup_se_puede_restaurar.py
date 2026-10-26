"""Un respaldo solo sirve si se puede ABRIR. Prueba el viaje completo: exportar la base -> cifrar (como el cron) ->
descifrar con la herramienta INDEPENDIENTE `tools/descifrar_respaldo.py` (la que se usaría el día que el servidor ya no exista)."""
import gzip
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'backup_rt.db')}")

import pytest  # noqa: E402

from app import backup  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Cuenta, Movimiento  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import descifrar_respaldo as herramienta  # noqa: E402

FRASE = "frase-de-prueba-larga-y-unica"


@pytest.fixture
def datos_de_prueba():
    Base.metadata.create_all(bind=engine)  # base de prueba propia (SQLite temporal)
    db = SessionLocal()
    try:
        c = Cuenta(usuario_id="bk-1", nombre="Cuenta de prueba", tipo="ahorro", saldo=1234.5, moneda="COP")
        db.add(c)
        db.flush()
        db.add(Movimiento(usuario_id="bk-1", cuenta_id=c.id, descripcion="Compra de prueba", categoria="Otros",
                          tipo="expense", monto=100.0, fuente="manual"))
        db.commit()
        yield
    finally:
        db.close()


def test_el_respaldo_exportado_se_abre_con_la_herramienta_independiente(datos_de_prueba):
    exportado = backup.exportar_base_de_datos()
    blob = backup.cifrar_respaldo(exportado, FRASE)
    assert blob.startswith(b"CMBK1") and exportado not in blob  # va cifrado, no en claro
    abierto = json.loads(herramienta.descifrar(blob, FRASE))  # la herramienta que se usaría sin el servidor
    assert any(f["nombre"] == "Cuenta de prueba" for f in abierto["tablas"]["cuentas"])
    assert any(f["descripcion"] == "Compra de prueba" for f in abierto["tablas"]["movimientos"])


def test_con_otra_frase_o_alterado_no_abre():
    blob = backup.cifrar_respaldo(b'{"tablas": {}}', FRASE)
    with pytest.raises(ValueError):
        herramienta.descifrar(blob, "otra-frase")
    alterado = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(ValueError):
        herramienta.descifrar(alterado, FRASE)


def test_nunca_se_respaldan_los_secretos_ni_el_contenido_de_gmail(datos_de_prueba):
    tablas = json.loads(gzip.decompress(backup.exportar_base_de_datos()))["tablas"]  # el export ya va comprimido
    for prohibida in ("correos_gastos", "extractos_correo", "claves_pdf", "push_subscriptions"):
        assert prohibida not in tablas
