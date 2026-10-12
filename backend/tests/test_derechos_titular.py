"""Derechos del titular (Ley 1581): descargar mis datos y borrar mi cuenta, sin huérfanos."""
import io
import json
import os
import tempfile
import zipfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'derechos.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import String  # noqa: E402

from app import derechos_titular as dt  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal  # noqa: E402
from app.limites import _eventos  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, Perfil  # noqa: E402
from app.models_fiscal import MarcaFiscal  # noqa: E402

client = TestClient(app)
DUENO = UsuarioActual(id="der-dueno", email="dueno-der@test.com", nombre="Dueño")
EDITOR = UsuarioActual(id="der-editor", email="editor-der@test.com", nombre="Editor")
AJENO = UsuarioActual(id="der-ajeno", email="ajeno-der@test.com", nombre="Ajeno")
ACTUAL = {"u": DUENO}


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    from cryptography.fernet import Fernet

    if not settings.fernet_key:
        monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    yield
    app.dependency_overrides.pop(get_current_user, None)
    for k in [k for k in _eventos if k.startswith("mis-datos:")]:
        _eventos.pop(k, None)


@pytest.fixture(autouse=True, scope="module")
def _limpiar_al_final():
    """Las pruebas comparten base con el resto de la suite: no dejar filas sembradas."""
    yield
    db = SessionLocal()
    try:
        for u in (DUENO, EDITOR, AJENO):
            dt.borrar_todo(db, u.id, u.email)
    finally:
        db.close()


def como(u):
    ACTUAL["u"] = u


def _sembrar(u, marca):
    """Datos de un usuario en varios módulos. Devuelve ids útiles."""
    como(u)
    cta = client.post("/cuentas", json={"nombre": f"{marca} Banco", "saldo": 1000}).json()
    mov = client.post("/movimientos", json={"cuenta_id": cta["id"], "descripcion": f"{marca} compra",
                                            "monto": 10, "tipo": "expense"}).json()
    client.post("/metas", json={"nombre": f"{marca} meta", "monto_objetivo": 100})
    client.post("/presupuestos", json={"categoria": "Comida", "limite": 50})
    contacto = client.post("/gastos-compartidos/contactos", json={"nombre": f"{marca} amigo"}).json()
    grupo = client.post("/gastos-compartidos/grupos", json={"nombre": f"{marca} viaje", "miembros": [contacto["id"]]}).json()
    client.post("/gastos-compartidos", json={
        "descripcion": f"{marca} cena", "total": 100, "modo": "iguales", "registro": "ninguno", "grupo_id": grupo["id"],
        "participantes": [{"id": "yo", "valor": 1}, {"id": contacto["id"], "valor": 1}]})
    client.post("/perfil/api-key/regenerar")
    return {"cuenta": cta["id"], "mov": mov["id"]}


def _zip(r):
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    return zipfile.ZipFile(io.BytesIO(r.content))


# ── Descargar mis datos ────────────────────────────────────────────────────────────

def test_descarga_trae_todo_lo_mio_y_nada_de_otros():
    _sembrar(DUENO, "QQD")
    _sembrar(AJENO, "QQX")
    como(DUENO)
    z = _zip(client.get("/perfil/mis-datos"))
    nombres = set(z.namelist())
    assert {"LEEME.txt", "datos.json", "csv/cuentas.csv", "csv/movimientos.csv", "csv/metas.csv",
            "csv/presupuestos.csv", "csv/perfiles.csv", "csv/contactos_gasto.csv",
            "csv/miembros_grupo_gasto.csv", "csv/partes_gasto.csv"} <= nombres
    datos = json.loads(z.read("datos.json"))["tablas"]
    todo = z.read("datos.json").decode() + "".join(z.read(n).decode("utf-8-sig") for n in nombres if n.startswith("csv/"))
    assert "QQD" in todo
    assert "QQX" not in todo, "la descarga mezcló datos de otro usuario"
    assert len(datos["movimientos"]) == 1 and len(datos["partes_gasto"]) == 2
    assert all(f["usuario_id"] == DUENO.id for f in datos["cuentas"])


def test_descarga_no_incluye_claves_ni_tokens():
    _sembrar(DUENO, "QQD")
    como(DUENO)
    clave = client.post("/perfil/api-key/regenerar").json()["api_key"]
    db = SessionLocal()
    try:
        p = db.query(Perfil).filter(Perfil.usuario_id == DUENO.id).first()
        p.gmail_refresh_token_enc = "TOKEN-CIFRADO-SECRETO"
        p.gmail_conectado = True
        db.commit()
    finally:
        db.close()
    z = _zip(client.get("/perfil/mis-datos"))
    contenido = "".join(z.read(n).decode("utf-8-sig") for n in z.namelist())
    for secreto in (clave, "TOKEN-CIFRADO-SECRETO", "api_key_hash", "gmail_refresh_token_enc"):
        assert secreto not in contenido
    perfiles = json.loads(z.read("datos.json"))["tablas"]["perfiles"][0]
    assert perfiles["gmail_conectado"] is True  # el dato útil sí viaja; la llave no


def test_descarga_json_y_limite_por_hora():
    como(DUENO)
    r = client.get("/perfil/mis-datos?formato=json")
    assert r.status_code == 200 and "tablas" in r.json()
    for _ in range(4):
        assert client.get("/perfil/mis-datos").status_code == 200
    assert client.get("/perfil/mis-datos").status_code == 429


def test_csv_de_la_descarga_neutraliza_formulas():
    como(DUENO)
    cta = client.post("/cuentas", json={"nombre": "Fórmulas", "saldo": 5}).json()
    client.post("/movimientos", json={"cuenta_id": cta["id"], "descripcion": '=HYPERLINK("http://malo.example","clic")',
                                      "monto": 1, "tipo": "expense"})
    z = _zip(client.get("/perfil/mis-datos"))
    csv_mov = z.read("csv/movimientos.csv").decode("utf-8-sig")
    assert "'=HYPERLINK" in csv_mov and ",=HYPERLINK" not in csv_mov
    # y la exportación normal de movimientos también
    assert "'=HYPERLINK" in client.get("/exportar/movimientos.csv").text


def test_toda_tabla_sin_usuario_id_esta_clasificada():
    """Si alguien agrega una tabla hija (sin usuario_id), esta prueba obliga a decidir cómo
    se exporta y se borra en derechos_titular.py."""
    sin_usuario = {t.name for t in Base.metadata.sorted_tables if "usuario_id" not in t.c}
    assert sin_usuario == dt.TABLAS_HIJAS | dt.TABLAS_PUBLICAS


# ── Borrar mi cuenta ───────────────────────────────────────────────────────────────

def _ids_del_usuario(db, uid):
    """Todas las llaves primarias de texto de las filas del usuario (más sus hijas)."""
    ids = set()
    for tabla in Base.metadata.sorted_tables:
        if "usuario_id" in tabla.c:
            for f in db.execute(tabla.select().where(tabla.c.usuario_id == uid)).mappings():
                ids.update(str(v) for k, v in f.items() if k == "id" and v)
    return ids


def _referencias_a(db, ids, excepto_tabla=()):
    """Filas de CUALQUIER tabla que mencionan alguno de esos ids en una columna de texto."""
    halladas = {}
    for tabla in Base.metadata.sorted_tables:
        if tabla.name in excepto_tabla:
            continue
        for col in tabla.c:
            if isinstance(col.type, String):
                n = db.execute(tabla.select().where(col.in_(list(ids)))).fetchall()
                if n:
                    halladas[f"{tabla.name}.{col.name}"] = len(n)
    return halladas


def test_borrar_cuenta_sin_huerfanos_con_cuenta_compartida_y_revoca_gmail(monkeypatch):
    from app.gmail_oauth import cifrar

    d = _sembrar(DUENO, "QQB")
    _sembrar(AJENO, "QQY")
    como(DUENO)
    inv = client.post(f"/cuentas/{d['cuenta']}/invitar", json={"email": EDITOR.email, "rol": "editor"}).json()
    como(EDITOR)
    client.post(f"/cuentas/invitaciones/{inv['id']}/aceptar")
    mov_editor = client.post("/movimientos", json={"cuenta_id": d["cuenta"], "descripcion": "del editor",
                                                   "monto": 3, "tipo": "expense"}).json()
    db = SessionLocal()
    try:
        # rastros del EDITOR que apuntan a movimientos que desaparecerán con la cuenta del dueño
        db.add(MarcaFiscal(usuario_id=EDITOR.id, movimiento_id=d["mov"], categoria_fiscal="salud"))
        db.add(CorreoGasto(usuario_id=EDITOR.id, gmail_msg_id="der-m1", movimiento_id=mov_editor["id"], estado="aprobado"))
        db.add(MarcaFiscal(usuario_id=DUENO.id, movimiento_id=d["mov"], categoria_fiscal="salud"))
        p = db.query(Perfil).filter(Perfil.usuario_id == DUENO.id).first()
        p.gmail_refresh_token_enc = cifrar("refresh-del-dueno")
        db.commit()
        ids = _ids_del_usuario(db, DUENO.id) | {mov_editor["id"]}
        assert len(ids) > 8
    finally:
        db.close()

    llamadas = []

    class _R:
        status_code = 200

    monkeypatch.setattr(dt, "revocar_token", lambda enc: (llamadas.append(enc), True)[1])
    como(DUENO)
    r = client.post("/perfil/eliminar-cuenta", json={"confirmacion": "eliminar"})
    assert r.status_code == 200 and r.json()["gmail_revocado"] is True
    assert len(llamadas) == 1 and llamadas[0]  # se pidió revocar el token guardado

    db = SessionLocal()
    try:
        assert _referencias_a(db, ids) == {}, "quedaron filas huérfanas que apuntan a datos borrados"
        for tabla in Base.metadata.sorted_tables:
            if "usuario_id" in tabla.c:
                assert db.execute(tabla.select().where(tabla.c.usuario_id == DUENO.id)).fetchall() == [], tabla.name
        # los demás conservan lo suyo
        assert db.query(Perfil).filter(Perfil.usuario_id == AJENO.id).count() == 1
        from app.models import Cuenta
        assert db.query(Cuenta).filter(Cuenta.usuario_id == AJENO.id).count() >= 1
    finally:
        db.close()
    como(EDITOR)
    assert client.get("/cuentas").json() == []  # ya no ve la cuenta compartida


def test_borrar_exige_confirmacion_escrita_y_solo_borra_al_que_llama():
    _sembrar(DUENO, "QQC")
    _sembrar(AJENO, "QQZ")
    como(DUENO)
    for mala in ("", "no", "borrar", "ELIMINA"):
        assert client.post("/perfil/eliminar-cuenta", json={"confirmacion": mala}).status_code == 400
    assert client.post("/perfil/eliminar-cuenta", json={}).status_code == 422
    assert client.get("/cuentas").json() != []  # nada se borró
    como(AJENO)
    assert client.post("/perfil/eliminar-cuenta", json={"confirmacion": "ELIMINAR"}).status_code == 200
    como(DUENO)
    assert client.get("/cuentas").json() != []  # borrar la cuenta de AJENO no tocó la de DUENO


def test_revocar_token_nunca_lanza_y_llama_a_google(monkeypatch):
    import httpx

    from app import gmail_oauth

    assert gmail_oauth.revocar_token(None) is False
    enc = gmail_oauth.cifrar("rt-123")
    vistos = {}

    def _post(url, params=None, timeout=None):
        vistos["url"], vistos["token"] = url, params["token"]

        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(httpx, "post", _post)
    assert gmail_oauth.revocar_token(enc) is True
    assert vistos == {"url": gmail_oauth.GOOGLE_REVOKE_URL, "token": "rt-123"}

    def _cae(*a, **k):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(httpx, "post", _cae)
    assert gmail_oauth.revocar_token(enc) is False  # Google caído: no impide desconectar ni borrar
    assert gmail_oauth.revocar_token("basura-no-cifrada") is False
