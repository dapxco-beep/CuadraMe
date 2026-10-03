"""
Recorre los endpoints de cada módulo con un usuario nuevo (sin datos) y luego
con datos, buscando errores 500. Un usuario recién registrado es justo el caso
que más se repite en producción, y el que más se olvida probar.
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'smoke.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="smoke-vacio", email="vacio@test.com", nombre="Vacío")}


@pytest.fixture(autouse=True)
def _usuario_de_esta_suite():
    # Cada módulo de pruebas fija su propia autenticación: si se hiciera al importar,
    # el último módulo cargado pisaría al resto.
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def como(usuario_id, email="x@test.com", nombre="Persona Prueba"):
    USUARIO["actual"] = UsuarioActual(id=usuario_id, email=email, nombre=nombre)


GETS = [
    "/cuentas", "/movimientos", "/presupuestos", "/presupuestos/disponible-hoy",
    "/presupuestos/en-mi-bolsillo", "/reportes/mensual", "/reportes/tendencias",
    "/reportes/flujo-caja-futuro", "/metas", "/recurrentes", "/recurrentes/sugerencias",
    "/deudas", "/categorias", "/reglas-categoria", "/insights/resumen-semanal",
    "/insights/edad-del-dinero", "/insights/alertas-proactivas", "/insights/salud-financiera",
    "/reportes/wrapped", "/ahorcado/vidas",
    "/perfil/api-key", "/perfil/confianza-autoimport", "/correos/gmail/estado",
    "/correos/pendientes", "/conciliacion/historial", "/cuentas/invitaciones/pendientes",
    "/pagos/plan", "/push/vapid-public-key", "/exportar/movimientos.csv",
    "/exportar/movimientos.xlsx",
]


@pytest.mark.parametrize("ruta", GETS)
def test_get_con_usuario_nuevo_sin_datos_no_da_500(ruta):
    como("smoke-vacio")
    r = client.get(ruta)
    assert r.status_code < 500, f"{ruta} -> {r.status_code}: {r.text[:300]}"


def test_flujo_completo_con_datos_no_da_500():
    como("smoke-lleno", "lleno@test.com", "Laura Gómez")
    banco = client.post("/cuentas", json={"nombre": "Bancolombia", "saldo": 2_000_000}).json()
    efectivo = client.post("/cuentas", json={"nombre": "Efectivo", "saldo": 100_000}).json()
    dolares = client.post("/cuentas", json={"nombre": "Wise", "saldo": 500, "moneda": "USD"}).json()

    for desc, monto, tipo in [("Éxito mercado", 150_000, "expense"), ("Uber", 25_000, "expense"),
                              ("Nómina", 3_000_000, "income"), ("Netflix", 33_000, "expense")]:
        r = client.post("/movimientos", json={"cuenta_id": banco["id"], "descripcion": desc, "monto": monto, "tipo": tipo})
        assert r.status_code == 200, r.text
    client.post("/movimientos", json={"cuenta_id": dolares["id"], "descripcion": "Spotify", "monto": 10, "tipo": "expense"})

    # categorías, reglas, presupuestos
    assert client.post("/categorias", json={"nombre": "Mascotas", "icono": "🐶"}).status_code == 200
    assert client.post("/reglas-categoria", json={"patron": "uber", "categoria": "Transporte"}).status_code == 200
    p1 = client.post("/presupuestos", json={"categoria": "Mercado", "limite": 200_000}).json()
    p2 = client.post("/presupuestos", json={"categoria": "Transporte", "limite": 100_000}).json()
    assert client.post("/presupuestos/mover-sobre", json={
        "presupuesto_origen_id": p1["id"], "presupuesto_destino_id": p2["id"], "monto": 10_000}).status_code < 500

    # metas, recurrentes, deudas
    meta = client.post("/metas", json={"nombre": "Viaje", "monto_objetivo": 1_000_000,
                                       "aporte_automatico": 50_000, "dia_aporte": 5,
                                       "cuenta_origen_id": banco["id"]}).json()
    assert client.post(f"/metas/{meta['id']}/aportar?monto=100000&cuenta_id={banco['id']}").status_code == 200
    rec = client.post("/recurrentes", json={"nombre": "Arriendo", "monto": 900_000, "dia_del_mes": 1,
                                            "cuenta_id": banco["id"]}).json()
    assert client.post(f"/recurrentes/{rec['id']}/marcar_pagado", json={"crear_movimiento": True}).status_code < 500
    deuda = client.post("/deudas", json={"nombre": "Tarjeta", "saldo_inicial": 1_000_000, "cuota_mensual": 100_000,
                                         "tasa_mensual": 1.9, "cuenta_pago_id": banco["id"]}).json()
    assert client.post(f"/deudas/{deuda['id']}/pagar", json={"monto_pagado": 100_000, "crear_movimiento": True}).status_code < 500

    # transferencia con saldo suficiente
    assert client.post("/movimientos/transferencia", json={
        "cuenta_origen_id": banco["id"], "cuenta_destino_id": efectivo["id"], "monto": 50_000}).status_code == 200

    # cada lectura, ahora con datos
    for ruta in GETS + ["/reportes/mensual?mes=2026-10", "/movimientos?q=uber&tipo=expense&limit=5&offset=0"]:
        r = client.get(ruta)
        assert r.status_code < 500, f"{ruta} -> {r.status_code}: {r.text[:300]}"

    # clasificación, voz y atajo por API key
    assert client.post("/movimientos/clasificar", json={"descripcion": "Rappi domicilio"}).status_code == 200
    api_key = client.get("/perfil/api-key").json()["api_key"]
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": api_key},
                    json={"monto": 12_000, "tipo": "expense", "descripcion": "Tinto", "cuenta": "Efectivo"})
    assert r.status_code == 200, r.text
    r = client.post("/movimientos/rapido-voz", headers={"X-Api-Key": api_key},
                    json={"texto": "gasté 20 mil en el almuerzo"})
    assert r.status_code == 200 and r.json()["entendido"], r.text
    assert client.post("/movimientos/rapido", headers={"X-Api-Key": "falsa"},
                       json={"monto": 1, "tipo": "expense", "descripcion": "x"}).status_code == 401

    # ahorcado
    partida = client.post("/ahorcado/nueva-partida")
    assert partida.status_code < 500

    # el saldo total es coherente: el exportado no revienta con datos reales
    assert client.get("/exportar/movimientos.csv").status_code == 200


def test_un_usuario_no_ve_ni_toca_los_datos_de_otro():
    como("dueno-a", "a@test.com")
    cuenta = client.post("/cuentas", json={"nombre": "Privada", "saldo": 777}).json()
    mov = client.post("/movimientos", json={"cuenta_id": cuenta["id"], "descripcion": "Secreto",
                                            "monto": 5, "tipo": "expense"}).json()

    como("intruso-b", "b@test.com")
    assert all(c["id"] != cuenta["id"] for c in client.get("/cuentas").json())
    assert client.get(f"/movimientos/{mov['id']}").status_code == 404
    assert client.put(f"/movimientos/{mov['id']}", json={"monto": 1}).status_code == 404
    assert client.delete(f"/movimientos/{mov['id']}").status_code == 404
    assert client.put(f"/cuentas/{cuenta['id']}", json={"nombre": "hackeada"}).status_code == 404
    assert client.delete(f"/cuentas/{cuenta['id']}").status_code == 404
    r = client.post("/movimientos", json={"cuenta_id": cuenta["id"], "descripcion": "x", "monto": 1, "tipo": "expense"})
    assert r.status_code == 404
    r = client.post("/movimientos/transferencia", json={
        "cuenta_origen_id": cuenta["id"], "cuenta_destino_id": cuenta["id"], "monto": 1})
    assert r.status_code in (400, 404)
    assert all(m["id"] != mov["id"] for m in client.get("/movimientos?limit=500").json())

    como("dueno-a", "a@test.com")
    assert next(c for c in client.get("/cuentas").json() if c["id"] == cuenta["id"])["saldo"] == 777 - 5


def test_cuenta_compartida_respeta_los_roles():
    como("due-c", "c@test.com")
    cuenta = client.post("/cuentas", json={"nombre": "Pareja", "saldo": 100}).json()
    assert client.post(f"/cuentas/{cuenta['id']}/invitar", json={"email": "ver@test.com", "rol": "viewer"}).status_code == 200

    como("visor", "ver@test.com")
    inv = client.get("/cuentas/invitaciones/pendientes").json()
    assert len(inv) == 1
    assert client.post(f"/cuentas/invitaciones/{inv[0]['id']}/aceptar").status_code == 200
    assert any(c["id"] == cuenta["id"] for c in client.get("/cuentas").json())
    # solo lectura: no puede crear, editar ni borrar
    r = client.post("/movimientos", json={"cuenta_id": cuenta["id"], "descripcion": "x", "monto": 1, "tipo": "expense"})
    assert r.status_code == 404
    assert client.post(f"/cuentas/{cuenta['id']}/invitar", json={"email": "otro@test.com"}).status_code in (403, 404)


def test_validaciones_de_entrada():
    como("smoke-vacio")
    assert client.post("/cuentas", json={"nombre": ""}).status_code == 422
    assert client.post("/presupuestos", json={"categoria": "X", "limite": -5}).status_code == 422
    assert client.post("/insights/preguntar", json={"pregunta": ""}).status_code == 422
    assert client.post("/insights/preguntar", json={"pregunta": "x" * 501}).status_code == 422


def test_docs_publicas_estan_apagadas_en_produccion():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/health").json() == {"ok": True}


def test_eliminar_cuenta_borra_todo_y_no_toca_a_otros():
    como("borrar-yo", "yo@test.com", "Yo Mismo")
    mia = client.post("/cuentas", json={"nombre": "Mía", "saldo": 1000}).json()
    client.post("/movimientos", json={"cuenta_id": mia["id"], "descripcion": "algo", "monto": 10, "tipo": "expense"})
    client.post("/metas", json={"nombre": "Meta", "monto_objetivo": 100})
    client.post("/presupuestos", json={"categoria": "Comida", "limite": 100})
    client.post(f"/cuentas/{mia['id']}/invitar", json={"email": "amigo@test.com", "rol": "editor"})

    # otra persona con una cuenta propia y una compartida conmigo
    como("borrar-otro", "amigo@test.com", "Amigo")
    suya = client.post("/cuentas", json={"nombre": "De otro", "saldo": 500}).json()
    client.post(f"/cuentas/{suya['id']}/invitar", json={"email": "yo@test.com", "rol": "editor"})

    como("borrar-yo", "yo@test.com", "Yo Mismo")
    inv = client.get("/cuentas/invitaciones/pendientes").json()[0]
    client.post(f"/cuentas/invitaciones/{inv['id']}/aceptar")
    client.post("/movimientos", json={"cuenta_id": suya["id"], "descripcion": "gasto en su cuenta", "monto": 100, "tipo": "expense"})

    como("borrar-otro", "amigo@test.com", "Amigo")
    assert next(c for c in client.get("/cuentas").json() if c["id"] == suya["id"])["saldo"] == 400

    como("borrar-yo", "yo@test.com", "Yo Mismo")
    assert client.post("/perfil/eliminar-cuenta", json={"confirmacion": "no"}).status_code == 400
    assert client.post("/perfil/eliminar-cuenta", json={"confirmacion": "ELIMINAR"}).status_code == 200
    assert client.get("/cuentas").json() == []
    assert client.get("/metas").json() == []

    # al otro usuario no se le rompe nada: su cuenta sigue, con el saldo devuelto
    como("borrar-otro", "amigo@test.com", "Amigo")
    cuentas = client.get("/cuentas").json()
    assert next(c for c in cuentas if c["id"] == suya["id"])["saldo"] == 500
    assert client.get("/cuentas/invitaciones/pendientes").json() == []


def test_meta_no_puede_apuntar_a_la_cuenta_de_otro():
    como("victima", "v@test.com")
    ajena = client.post("/cuentas", json={"nombre": "Ajena", "saldo": 900}).json()
    como("atacante", "at@test.com")
    r = client.post("/metas", json={"nombre": "Robo", "monto_objetivo": 100, "aporte_automatico": 50,
                                    "dia_aporte": 1, "cuenta_origen_id": ajena["id"]})
    assert r.status_code == 404
    propia = client.post("/cuentas", json={"nombre": "Propia", "saldo": 10}).json()
    meta = client.post("/metas", json={"nombre": "Ok", "monto_objetivo": 100, "cuenta_origen_id": propia["id"]}).json()
    # el PATCH no permite cambiar la cuenta de origen: sigue siendo la propia
    r = client.patch(f"/metas/{meta['id']}", json={"cuenta_origen_id": ajena["id"]})
    assert r.status_code in (200, 404)
    assert next(m for m in client.get("/metas").json() if m["id"] == meta["id"])["cuenta_origen_id"] == propia["id"]
