"""Subcategorías (un nivel dentro de cada categoría): CRUD, integridad al renombrar/borrar la categoría,
asignación en movimientos, reglas por comercio, memoria del usuario, desglose en el informe y migración.
Datos sintéticos."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'subcat.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app import memoria_usuario as mu  # noqa: E402
from app import migraciones  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="subcat-u1", email="s1@test.com", nombre="Sub Uno")
V = UsuarioActual(id="subcat-u2", email="s2@test.com", nombre="Sub Dos")
ACTUAL = {"u": U}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    ACTUAL["u"] = U
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _ok(r):
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def cuenta():
    ACTUAL["u"] = U
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    c = _ok(client.post("/cuentas", json={"nombre": "Banco sub", "saldo": 1_000_000}))
    app.dependency_overrides.pop(get_current_user, None)
    return c["id"]


def _mov(cuenta, desc="Tanqueo", monto=50_000, **extra):
    return client.post("/movimientos", json={"cuenta_id": cuenta, "descripcion": desc, "monto": monto,
                                            "tipo": "expense", **extra})


def test_crud_y_reglas_de_nombre():
    g = _ok(client.post("/subcategorias", json={"categoria": "Transporte", "nombre": " Gasolina "}))
    assert g["categoria"] == "Transporte" and g["nombre"] == "Gasolina" and g["movimientos"] == 0
    assert client.post("/subcategorias", json={"categoria": "Transporte", "nombre": "gasolina"}).status_code == 400  # único por padre
    # el mismo nombre en OTRA categoría sí se puede
    assert client.post("/subcategorias", json={"categoria": "Comida", "nombre": "Gasolina"}).status_code == 200
    assert client.post("/subcategorias", json={"categoria": "NoExiste", "nombre": "x"}).status_code == 404
    uber = _ok(client.post("/subcategorias", json={"categoria": "Transporte", "nombre": "Uber"}))
    assert client.put(f"/subcategorias/{uber['id']}", json={"nombre": "Gasolina"}).status_code == 400
    assert _ok(client.put(f"/subcategorias/{uber['id']}", json={"nombre": "Taxi"}))["nombre"] == "Taxi"
    nombres = [s["nombre"] for s in _ok(client.get("/subcategorias?categoria=Transporte"))]
    assert nombres == ["Gasolina", "Taxi"]
    assert client.delete(f"/subcategorias/{uber['id']}").status_code == 200
    assert client.put(f"/subcategorias/{uber['id']}", json={"nombre": "x"}).status_code == 404


def test_categoria_de_sistema_no_admite_subcategorias():
    # «Transferencias» es de sistema: la regla contable única no se puede romper con detalles
    r = client.post("/subcategorias", json={"categoria": "Transferencias", "nombre": "Mamá"})
    assert r.status_code == 400


def test_no_hay_subcategorias_de_subcategorias():
    # la API solo recibe una categoría como padre: un nombre de subcategoría no es un padre válido
    _ok(client.post("/subcategorias", json={"categoria": "Hogar", "nombre": "Aseo"}))
    assert client.post("/subcategorias", json={"categoria": "Aseo", "nombre": "Cloro"}).status_code == 404


def test_movimiento_con_subcategoria_y_validaciones(cuenta):
    _ok(client.post("/subcategorias", json={"categoria": "Salud", "nombre": "Drogería"}))
    m = _ok(_mov(cuenta, "Compra droguería", categoria="Salud", subcategoria="drogería"))
    assert m["categoria"] == "Salud" and m["subcategoria"] == "Drogería"  # nombre oficial
    # subcategoría de otra categoría: rechazada
    assert _mov(cuenta, "x", categoria="Ocio", subcategoria="Drogería").status_code == 400
    # sin subcategoría: todo igual que antes
    assert _ok(_mov(cuenta, "Cine", categoria="Ocio"))["subcategoria"] is None
    # cambiar de categoría limpia la subcategoría; "" también
    cambiado = _ok(client.put(f"/movimientos/{m['id']}", json={"categoria": "Ocio"}))
    assert cambiado["categoria"] == "Ocio" and cambiado["subcategoria"] is None
    otra = _ok(client.put(f"/movimientos/{m['id']}", json={"categoria": "Salud", "subcategoria": "Drogería"}))
    assert otra["subcategoria"] == "Drogería"
    sola = _ok(client.put(f"/movimientos/{m['id']}", json={"notas": "nota"}))
    assert sola["subcategoria"] == "Drogería"  # tocar otra cosa no la pierde
    assert _ok(client.put(f"/movimientos/{m['id']}", json={"subcategoria": ""}))["subcategoria"] is None


def test_renombrar_y_borrar_subcategoria_siguen_a_los_movimientos(cuenta):
    s = _ok(client.post("/subcategorias", json={"categoria": "Ocio", "nombre": "Streaming"}))
    m = _ok(_mov(cuenta, "Plan video", categoria="Ocio", subcategoria="Streaming"))
    assert _ok(client.get("/subcategorias?categoria=Ocio"))[0]["movimientos"] == 1
    _ok(client.put(f"/subcategorias/{s['id']}", json={"nombre": "Series"}))
    movs = _ok(client.get("/movimientos?limit=200"))
    assert next(x for x in movs if x["id"] == m["id"])["subcategoria"] == "Series"
    _ok(client.delete(f"/subcategorias/{s['id']}"))
    movs = _ok(client.get("/movimientos?limit=200"))
    esta = next(x for x in movs if x["id"] == m["id"])
    assert esta["subcategoria"] is None and esta["categoria"] == "Ocio"  # no se borra el movimiento


def test_renombrar_categoria_renombra_sus_subcategorias(cuenta):
    c = _ok(client.post("/categorias", json={"nombre": "Mascotas"}))
    _ok(client.post("/subcategorias", json={"categoria": "Mascotas", "nombre": "Veterinario"}))
    m = _ok(_mov(cuenta, "Consulta", categoria="Mascotas", subcategoria="Veterinario"))
    _ok(client.put(f"/categorias/{c['id']}", json={"nombre": "Animales"}))
    subs = _ok(client.get("/subcategorias?categoria=Animales"))
    assert [s["nombre"] for s in subs] == ["Veterinario"] and subs[0]["movimientos"] == 1
    assert _ok(client.get("/subcategorias?categoria=Mascotas")) == []
    movs = _ok(client.get("/movimientos?limit=200"))
    esta = next(x for x in movs if x["id"] == m["id"])
    assert (esta["categoria"], esta["subcategoria"]) == ("Animales", "Veterinario")


def test_borrar_categoria_mueve_o_borra_sus_subcategorias(cuenta):
    c = _ok(client.post("/categorias", json={"nombre": "Viajes"}))
    _ok(client.post("/subcategorias", json={"categoria": "Viajes", "nombre": "Hotel"}))
    _ok(client.post("/subcategorias", json={"categoria": "Ocio", "nombre": "Hotel"}))  # ya existe en el destino
    _ok(client.post("/subcategorias", json={"categoria": "Viajes", "nombre": "Tiquetes"}))
    _ok(_mov(cuenta, "Hotel Cartagena", categoria="Viajes", subcategoria="Hotel"))
    # en uso: pide destino; con destino, las subcategorías se fusionan por nombre
    assert client.delete(f"/categorias/{c['id']}").status_code == 409
    _ok(client.delete(f"/categorias/{c['id']}?mover_a=Ocio"))
    ocio = sorted(s["nombre"] for s in _ok(client.get("/subcategorias?categoria=Ocio")))
    assert ocio == ["Hotel", "Tiquetes"]
    assert _ok(client.get("/subcategorias?categoria=Viajes")) == []
    # sin uso: se van con la categoría
    c2 = _ok(client.post("/categorias", json={"nombre": "Temporal"}))
    _ok(client.post("/subcategorias", json={"categoria": "Temporal", "nombre": "Algo"}))
    _ok(client.delete(f"/categorias/{c2['id']}"))
    assert _ok(client.get("/subcategorias?categoria=Temporal")) == []


def test_regla_con_subcategoria_la_aplica_a_movimientos_nuevos(cuenta):
    _ok(client.post("/subcategorias", json={"categoria": "Transporte", "nombre": "Peajes"}))
    r = _ok(client.post("/reglas-categoria/aprender", json={
        "descripcion": "AUTOPISTA DEL SOL", "categoria": "Transporte", "subcategoria": "Peajes"}))
    assert r["guardada"]
    reglas = _ok(client.get("/reglas-categoria"))
    assert any(x["categoria"] == "Transporte" and x["subcategoria"] == "Peajes" for x in reglas)
    nuevo = _ok(_mov(cuenta, "AUTOPISTA DEL SOL"))  # sin categoría: la decide la regla
    assert (nuevo["categoria"], nuevo["subcategoria"]) == ("Transporte", "Peajes")
    # una subcategoría que no es de esa categoría no se acepta en la regla
    assert client.post("/reglas-categoria/aprender", json={
        "descripcion": "OTRO LUGAR", "categoria": "Comida", "subcategoria": "Peajes"}).status_code == 400
    # cambiar la regla a otra categoría sin subcategoría limpia la subcategoría
    _ok(client.post("/reglas-categoria/aprender", json={"descripcion": "AUTOPISTA DEL SOL", "categoria": "Otros"}))
    assert all(x["subcategoria"] is None for x in _ok(client.get("/reglas-categoria")) if x["categoria"] == "Otros")


def test_recategorizar_comercio_guarda_categoria_y_subcategoria(cuenta):
    _ok(client.post("/subcategorias", json={"categoria": "Comida", "nombre": "Domicilios"}))
    m = _ok(_mov(cuenta, "Rappi Pedido 123"))
    r = _ok(client.post(f"/movimientos/{m['id']}/recategorizar-comercio", json={
        "categoria": "Comida", "subcategoria": "Domicilios", "aplicar_a_todos": True, "confirmar_peligrosa": True}))
    assert r["ok"]
    movs = _ok(client.get("/movimientos?limit=200"))
    assert next(x for x in movs if x["id"] == m["id"])["subcategoria"] == "Domicilios"


def test_memoria_solo_sugiere_la_subcategoria_que_el_usuario_ya_uso():
    movs = [
        {"descripcion": "Terpel Calle 80", "categoria": "Transporte", "subcategoria": "Gasolina", "tipo": "expense"},
        {"descripcion": "Terpel Calle 80", "categoria": "Transporte", "subcategoria": "Gasolina", "tipo": "expense"},
        {"descripcion": "Terpel Calle 80", "categoria": "Transporte", "subcategoria": None, "tipo": "expense"},
        {"descripcion": "Uber Trip", "categoria": "Transporte", "tipo": "expense"},
        {"descripcion": "Uber Trip", "categoria": "Transporte", "tipo": "expense"},
    ]
    memoria = mu.construir_memoria(movs)
    assert mu.consultar_memoria("Terpel Calle 80", memoria)["subcategoria"] == "Gasolina"
    assert mu.consultar_memoria("Uber Trip", memoria)["subcategoria"] is None  # nunca inventa
    # si no domina (1 de 3), tampoco
    movs2 = [{"descripcion": "Shell", "categoria": "Transporte", "subcategoria": "Gasolina", "tipo": "expense"},
             {"descripcion": "Shell", "categoria": "Transporte", "tipo": "expense"},
             {"descripcion": "Shell", "categoria": "Transporte", "tipo": "expense"}]
    assert mu.consultar_memoria("Shell", mu.construir_memoria(movs2))["subcategoria"] is None


def test_desglose_en_informe_suma_el_total_de_la_categoria(cuenta):
    _ok(client.post("/subcategorias", json={"categoria": "Hogar", "nombre": "Servicios"}))
    _ok(_mov(cuenta, "Luz", 200_000, categoria="Hogar", subcategoria="Servicios"))
    _ok(_mov(cuenta, "Agua", 100_000, categoria="Hogar", subcategoria="Servicios"))
    _ok(_mov(cuenta, "Escoba", 50_000, categoria="Hogar"))
    d = _ok(client.get("/informes/gasto/subcategorias?categoria=Hogar&periodo=anio"))
    por = {x["subcategoria"]: x for x in d["subcategorias"]}
    assert por["Servicios"]["total"] == 300_000 and por[None]["total"] == 50_000
    assert d["subcategorias"][-1]["subcategoria"] is None  # «Sin subcategoría» al final
    assert d["tiene_subcategorias"] and d["total"] == 350_000
    # el informe general sigue agregando por la categoría padre (no cambia con subcategorías)
    inf = _ok(client.get("/informes/gasto?periodo=anio"))
    hogar = next(c for c in inf["categorias"] if c["categoria"] == "Hogar")
    assert hogar["monto"] == d["total"]
    # categoría sin subcategorías usadas
    d2 = _ok(client.get("/informes/gasto/subcategorias?categoria=Comida&periodo=anio"))
    assert d2["tiene_subcategorias"] is False or all(x["subcategoria"] is None or x["total"] >= 0 for x in d2["subcategorias"])


def test_aislamiento_basico_entre_usuarios():
    ACTUAL["u"] = V
    assert _ok(client.get("/subcategorias")) == []
    assert client.post("/subcategorias", json={"categoria": "Transporte", "nombre": "Gasolina"}).status_code == 200  # la suya


def test_migracion_0003_es_idempotente_y_agrega_las_columnas():
    ids = [i for i, _ in migraciones.MIGRACIONES]
    assert ids[-1] == "0003_subcategorias"
    eng = create_engine(f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'mig.db')}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE movimientos (id VARCHAR)"))
        c.execute(text("CREATE TABLE reglas_categoria (id VARCHAR)"))
    # SQLite no soporta ADD COLUMN IF NOT EXISTS: se ejecuta la tabla (idempotente) y se comprueba el texto de las demás
    sentencias = dict(migraciones.MIGRACIONES)["0003_subcategorias"]
    with eng.begin() as c:
        c.execute(text(sentencias[0]))
        c.execute(text(sentencias[0]))  # segunda vez: no falla
        c.execute(text(sentencias[1]))
        c.execute(text(sentencias[1]))
        assert c.execute(text("SELECT COUNT(*) FROM subcategorias")).scalar() == 0
    assert any("movimientos ADD COLUMN IF NOT EXISTS subcategoria" in s for s in sentencias)
    assert any("reglas_categoria ADD COLUMN IF NOT EXISTS subcategoria" in s for s in sentencias)
