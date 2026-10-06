"""asegurar_rls: SQL correcto en Postgres, nada en SQLite y tolerancia a fallos."""
from types import SimpleNamespace

from app.rls import asegurar_rls


class _Conn:
    def __init__(self, tablas, falla=False):
        self.tablas, self.falla, self.sentencias = tablas, falla, []

    def execute(self, stmt):
        self.sentencias.append(str(stmt))
        if self.falla:
            raise RuntimeError("boom")
        return SimpleNamespace(fetchall=lambda: [(t,) for t in self.tablas])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Motor:
    def __init__(self, dialecto, conn):
        self.dialect = SimpleNamespace(name=dialecto)
        self._conn = conn

    def begin(self):
        return self._conn


def test_en_sqlite_no_hace_nada():
    conn = _Conn(["a"])
    assert asegurar_rls(_Motor("sqlite", conn)) == 0
    assert conn.sentencias == []


def test_en_postgres_activa_rls_en_las_tablas_sin_ella():
    conn = _Conn(["cuentas", 'raro"nombre'])
    assert asegurar_rls(_Motor("postgresql", conn)) == 2
    assert conn.sentencias[1] == 'ALTER TABLE public."cuentas" ENABLE ROW LEVEL SECURITY'
    assert conn.sentencias[2] == 'ALTER TABLE public."raro""nombre" ENABLE ROW LEVEL SECURITY'


def test_un_fallo_no_tumba_el_arranque():
    assert asegurar_rls(_Motor("postgresql", _Conn(["x"], falla=True))) == 0
