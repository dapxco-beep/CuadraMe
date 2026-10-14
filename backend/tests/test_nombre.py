"""Cómo le decimos a la persona: nombre de pila desde Google, validación, endpoints,
aislamiento entre cuentas y uso (resumen semanal y push) con y sin nombre."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'nombre.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import resumen_semanal as rs  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.nombre import NombreInvalido, nombre_de_pila, validar_nombre  # noqa: E402

client = TestClient(app)


def como(nombre_google="", pila="", uid="nom-a"):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
        id=uid, email=f"{uid}@test.com", nombre=nombre_google, nombre_pila=pila)


@pytest.fixture(autouse=True)
def _limpiar():
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("completo,pila,esperado", [
    ("DANIEL ALFONSO PARRADO CARDENAS", "", "Daniel"),
    ("daniel alfonso", "", "Daniel"),
    ("María José Pérez", "", "María"),
    ("María José Pérez", "María José", "María José"),
    ("MARÍA JOSÉ PÉREZ", "MARÍA JOSÉ", "María José"),
    ("Ana María Gómez", "Ana María Isabel", "Ana María"),
    ("O'BRIEN Kevin", "", "O'Brien"),
    ("", "", ""),
    (None, None, ""),
    ("   ", "", ""),
    ("daniel@gmail.com", "", ""),
    ("1234", "", ""),
    ("😀 Pepe", "", "Pepe"),
])
def test_nombre_de_pila(completo, pila, esperado):
    assert nombre_de_pila(completo, pila) == esperado


def test_nombre_de_pila_respeta_mayusculas_mixtas():
    assert nombre_de_pila("McDonald Pérez") == "McDonald"


@pytest.mark.parametrize("texto,esperado", [
    ("  Daniel  ", "Daniel"), ("ana   maría", "Ana María"), ("José-Luis", "José-Luis"),
    ("D'Angelo", "D'Angelo"), ("ÁNGELA", "Ángela"), ("Ñoño", "Ñoño"),
])
def test_validar_nombre_acepta(texto, esperado):
    assert validar_nombre(texto) == esperado


@pytest.mark.parametrize("texto", [
    "", "   ", "<b>Dani</b>", "<script>alert(1)</script>", "http://malo.com", "www.malo.co", "Dani 3001234567",
    "Dani2", "Dani 😀", "😀", "Dani@correo.com", "a" * 41, "---", "'", "Dani; DROP TABLE", "Dani_",
])
def test_validar_nombre_rechaza(texto):
    with pytest.raises(NombreInvalido):
        validar_nombre(texto)


def test_validar_nombre_limite_40():
    assert validar_nombre("a" * 40) == "A" + "a" * 39


def test_get_sin_nada_guardado_sugiere_el_de_google():
    como("DANIEL ALFONSO PARRADO CARDENAS", uid="nom-get")
    r = client.get("/perfil/nombre").json()
    assert r == {"nombre": None, "sugerido": "Daniel", "confirmado": False, "email": "nom-get@test.com"}


def test_get_persona_sin_nombre_en_google():
    como("", uid="nom-vacio")
    r = client.get("/perfil/nombre").json()
    assert r["sugerido"] is None and r["nombre"] is None and r["confirmado"] is False


def test_put_guarda_y_confirma():
    como("DANIEL ALFONSO", uid="nom-put")
    r = client.put("/perfil/nombre", json={"nombre": "  dani  "})
    assert r.status_code == 200 and r.json()["nombre"] == "Dani" and r.json()["confirmado"] is True
    assert client.get("/perfil/nombre").json()["nombre"] == "Dani"


def test_put_cambiar_despues():
    como("X", uid="nom-cambio")
    client.put("/perfil/nombre", json={"nombre": "Dani"})
    r = client.put("/perfil/nombre", json={"nombre": "Daniel"})
    assert r.json()["nombre"] == "Daniel"


@pytest.mark.parametrize("malo", ["<b>x</b>", "Dani 😀", "https://x.co", "123", "", "a" * 41])
def test_put_rechaza_con_mensaje_amable(malo):
    como("X", uid="nom-malo")
    r = client.put("/perfil/nombre", json={"nombre": malo})
    assert r.status_code == 422 and isinstance(r.json()["detail"], str) and r.json()["detail"]


def test_put_nombre_enorme_no_revienta():
    como("X", uid="nom-enorme")
    assert client.put("/perfil/nombre", json={"nombre": "a" * 5000}).status_code == 422


def test_ahora_no_usa_el_automatico_y_no_vuelve_a_preguntar():
    como("MARÍA JOSÉ PÉREZ", pila="MARÍA JOSÉ", uid="nom-omitir")
    r = client.put("/perfil/nombre", json={"omitir": True}).json()
    assert r["nombre"] == "María José" and r["confirmado"] is True


def test_ahora_no_sin_nombre_deja_vacio_pero_confirmado():
    como("", uid="nom-omitir-vacio")
    r = client.put("/perfil/nombre", json={"omitir": True}).json()
    assert r["nombre"] is None and r["confirmado"] is True


def test_ahora_no_no_pisa_un_nombre_ya_elegido():
    como("OTRO NOMBRE", uid="nom-no-pisa")
    client.put("/perfil/nombre", json={"nombre": "Lalo"})
    assert client.put("/perfil/nombre", json={"omitir": True}).json()["nombre"] == "Lalo"


def test_cuenta_compartida_cada_persona_ve_el_suyo():
    como("A", uid="nom-iso-a")
    client.put("/perfil/nombre", json={"nombre": "Ana"})
    como("B", uid="nom-iso-b")
    assert client.get("/perfil/nombre").json()["nombre"] is None
    client.put("/perfil/nombre", json={"nombre": "Beto"})
    como("A", uid="nom-iso-a")
    assert client.get("/perfil/nombre").json()["nombre"] == "Ana"


def test_el_endpoint_exige_sesion():
    app.dependency_overrides.pop(get_current_user, None)
    assert client.get("/perfil/nombre").status_code == 401
    assert client.put("/perfil/nombre", json={"nombre": "x"}).status_code == 401


# ── Uso del nombre: siempre se lee bien sin él ──
DATOS = {"desde": "2026-08-30", "hasta": "2026-09-06", "total_gastos": 50000,
         "top_categorias": [{"categoria": "Mercado", "monto": 50000}], "presupuestos": [], "tarjetas": [], "vacio": False}


def test_push_con_y_sin_nombre():
    c = {"gastos": 120_000, "anterior": 100_000, "top": "Mercado"}
    assert rs.mensaje_push(c, nombre="Daniel")[1].startswith("Daniel, esta semana gastaste $120.000")
    assert rs.mensaje_push(c, ocultar_montos=True, nombre="Daniel")[1].startswith("Daniel, ya está lista")
    assert "$" not in rs.mensaje_push(c, ocultar_montos=True, nombre="Daniel")[1].split("20 %")[0]
    sin = rs.mensaje_push(c)[1]
    assert sin.startswith("Esta semana gastaste") and ", ," not in sin
    assert rs.mensaje_push({"gastos": 0, "anterior": 1, "top": None}, nombre="Daniel")[1].startswith("Daniel, esta semana no registraste")
    assert rs.mensaje_push(c, nombre="   ")[1].startswith("Esta semana")


def test_correo_con_y_sin_nombre():
    assert "Hola, Daniel." in rs.texto_plano(DATOS, "Daniel")
    assert "Hola, Daniel" in rs.html_correo(DATOS, "Daniel")
    assert rs.texto_plano(DATOS).startswith("Hola. ")
    assert "Hola," not in rs.html_correo(DATOS).split("Tu semana, del")[0].split(">")[-1]
    assert rs.asunto(DATOS, "Daniel").startswith("Daniel, tu semana")
    assert rs.asunto(DATOS).startswith("Tu semana en CuadraMe")


def test_correo_escapa_el_nombre():
    assert "<script>" not in rs.html_correo(DATOS, "<script>x</script>")
