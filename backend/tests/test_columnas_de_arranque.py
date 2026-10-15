"""Toda columna NO diferida que el modelo declare en una tabla ya existente debe tener su ALTER en
una migración (app/migraciones.py). Si falta, producción falla con «column ... does not exist»."""
import os
import re
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'cols.db')}")

from sqlalchemy import create_engine, text  # noqa: E402

from app.database import Base  # noqa: E402
from app import main  # noqa: E402,F401  (registra todos los modelos)
from app import migraciones  # noqa: E402

SENTENCIAS = [s for _, lista in migraciones.MIGRACIONES for s in lista]


def _alter_cols(tabla: str) -> set[str]:
    cols = set()
    for s in SENTENCIAS:
        m = re.match(rf"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS (\w+)", s)
        if m:
            cols.add(m.group(1))
    return cols


def test_columnas_nuevas_de_patrimonio_y_perfiles_tienen_alter_en_el_arranque():
    esperado = {
        "activos_patrimonio": {"arriendo_mensual", "anio", "depreciacion_pct", "deuda_id", "broker"},
        "perfiles": {"pais", "moneda_base", "zona_horaria", "idioma", "pais_confirmado"},
    }
    for tabla, cols in esperado.items():
        modelo = {c.name for c in Base.metadata.tables[tabla].c}
        assert cols <= modelo, f"{tabla}: el modelo ya no declara {cols - modelo}"
        faltan = cols - _alter_cols(tabla)
        assert not faltan, f"{tabla}: faltan ALTER en las migraciones para {faltan}"


def test_ids_de_migraciones_unicos_ordenados_e_idempotentes():
    ids = [i for i, _ in migraciones.MIGRACIONES]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    for s in SENTENCIAS:
        assert "IF NOT EXISTS" in s, f"sentencia no idempotente: {s}"


def test_aplicar_corre_cada_migracion_una_sola_vez():
    eng = create_engine(f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'm.db')}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE t (a INTEGER)"))
    migs = [("0001_x", ["INSERT INTO t VALUES (1)"]), ("0002_y", ["INSERT INTO t VALUES (2)"])]
    assert migraciones.aplicar(eng, migs) == ["0001_x", "0002_y"]
    assert migraciones.aplicar(eng, migs) == []
    migs.append(("0003_z", ["INSERT INTO t VALUES (3)"]))
    assert migraciones.aplicar(eng, migs) == ["0003_z"]
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM t")).scalar() == 3
        assert c.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar() == 3


def test_migracion_fallida_no_queda_registrada():
    eng = create_engine(f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'f.db')}")
    try:
        migraciones.aplicar(eng, [("0001_mala", ["SELECT * FROM no_existe"])])
    except Exception:
        pass
    with eng.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar() == 0
