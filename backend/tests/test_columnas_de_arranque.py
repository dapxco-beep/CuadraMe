"""Toda columna NO diferida que el modelo declare en una tabla ya existente debe tener su ALTER en el
arranque (app/main.py). Si falta, producción falla con «column ... does not exist» en cada consulta."""
import os
import re
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cols.db')}")

from app.database import Base  # noqa: E402
from app import main  # noqa: E402,F401  (registra todos los modelos)

MAIN = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")


def _alter_cols(tabla: str) -> set[str]:
    directos = set(re.findall(rf"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS (\w+)", MAIN))
    # Bucles `for _col, _tipo in ((...)): ... ALTER TABLE <tabla> ADD COLUMN IF NOT EXISTS {_col}`
    for bloque in re.finditer(r"for _col, _tipo in \((.*?)\):\s*conn\.execute\(text\(f\"ALTER TABLE (\w+) ADD", MAIN, re.S):
        if bloque.group(2) == tabla:
            directos |= set(re.findall(r'\("(\w+)",\s*"[A-Z]+"\)', bloque.group(1)))
    return directos


def test_columnas_nuevas_de_patrimonio_y_perfiles_tienen_alter_en_el_arranque():
    esperado = {
        "activos_patrimonio": {"arriendo_mensual", "anio", "depreciacion_pct", "deuda_id", "broker"},
        "perfiles": {"pais", "moneda_base", "zona_horaria", "idioma", "pais_confirmado"},
    }
    for tabla, cols in esperado.items():
        modelo = {c.name for c in Base.metadata.tables[tabla].c}
        assert cols <= modelo, f"{tabla}: el modelo ya no declara {cols - modelo}"
        faltan = cols - _alter_cols(tabla)
        assert not faltan, f"{tabla}: faltan ALTER en el arranque para {faltan}"
