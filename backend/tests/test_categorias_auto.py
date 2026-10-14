"""
Categorías libres (emoji, color, orden, renombrar/eliminar sin huérfanos) y
categorización automática transparente (insignia 'Auto', 'Por revisar',
confirmar y 'aplicar a todos los de este comercio').
"""
import os
import tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.autocat import es_emoji, patron_de_comercio  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def usuario(request):
    uid = f"user-cat-{request.node.name}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="c@test.com", nombre="Cata")
    yield uid


@pytest.fixture()
def cuenta(usuario):
    r = client.post("/cuentas", json={"nombre": "Principal", "saldo": 1000000})
    assert r.status_code == 200, r.text
    return r.json()


def _mov(cuenta, descripcion, categoria=None, tipo="expense", monto=10000):
    body = {"cuenta_id": cuenta["id"], "descripcion": descripcion, "monto": monto, "tipo": tipo}
    if categoria:
        body["categoria"] = categoria
    r = client.post("/movimientos", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _cat(nombre, icono="🦄", **extra):
    r = client.post("/categorias", json={"nombre": nombre, "icono": icono, **extra})
    assert r.status_code == 200, r.text
    return r.json()


# --- categorías -------------------------------------------------------------

def test_las_ocultas_siguen_accesibles_y_se_pueden_reactivar(usuario):
    base = client.get("/categorias").json()
    assert len(base) == 8
    comida = next(c for c in base if c["nombre"] == "Comida")
    assert client.put(f"/categorias/{comida['id']}", json={"activa": False}).json()["activa"] is False

    assert "Comida" not in [c["nombre"] for c in client.get("/categorias").json()]
    todas = client.get("/categorias?incluir_inactivas=true").json()
    assert len(todas) == 8 and next(c for c in todas if c["nombre"] == "Comida")["activa"] is False

    client.put(f"/categorias/{comida['id']}", json={"activa": True})
    assert "Comida" in [c["nombre"] for c in client.get("/categorias").json()]


def test_cualquier_emoji_vale_y_el_texto_no(usuario):
    for emoji in ["🦄", "👨‍👩‍👧", "🇨🇴", "❤️", "👍🏽"]:
        assert es_emoji(emoji)
    for malo in ["", "abc", "a🦄", "🦄 ", "1", "x" * 20, "🦄" * 20]:
        assert not es_emoji(malo)

    assert _cat("Unicornios", "🦄")["icono"] == "🦄"
    assert client.post("/categorias", json={"nombre": "Texto", "icono": "hola"}).status_code == 422
    assert client.post("/categorias", json={"nombre": "Largo", "icono": "🦄" * 20}).status_code == 422


def test_color_tipo_y_nombre_libre(usuario):
    c = _cat("Salario extra", "💵", color="#AABBCC", tipo="ingreso")
    assert c["color"] == "#aabbcc" and c["tipo"] == "ingreso"
    assert client.post("/categorias", json={"nombre": "Mal color", "color": "rojo"}).status_code == 422
    quitado = client.put(f"/categorias/{c['id']}", json={"color": ""}).json()
    assert quitado["color"] is None


def test_reordenar(usuario):
    a = _cat("Zeta")
    b = _cat("Alfa")
    todas = client.get("/categorias").json()
    ids = [c["id"] for c in todas]
    nuevo = [b["id"], a["id"]] + [i for i in ids if i not in (a["id"], b["id"])]
    assert client.put("/categorias/orden", json={"ids": nuevo}).status_code == 200
    assert [c["id"] for c in client.get("/categorias").json()] == nuevo


def test_renombrar_arrastra_movimientos_reglas_y_presupuestos(usuario, cuenta):
    mascotas = _cat("Mascotas", "🐶")
    _mov(cuenta, "Veterinaria", "Mascotas")
    client.post("/reglas-categoria", json={"patron": "purina", "categoria": "Mascotas"})
    client.post("/presupuestos", json={"categoria": "Mascotas", "limite": 200000})

    r = client.put(f"/categorias/{mascotas['id']}", json={"nombre": "Peluditos"})
    assert r.status_code == 200 and r.json()["movimientos"] == 1

    movs = client.get("/movimientos").json()
    assert {m["categoria"] for m in movs} == {"Peluditos"}
    assert client.get("/reglas-categoria").json()[0]["categoria"] == "Peluditos"
    assert [p["categoria"] for p in client.get("/presupuestos").json()] == ["Peluditos"]


def test_no_se_puede_renombrar_a_un_nombre_ya_usado(usuario):
    _cat("Uno")
    dos = _cat("Dos")
    assert client.put(f"/categorias/{dos['id']}", json={"nombre": "uno"}).status_code == 400


def test_eliminar_con_movimientos_pide_destino_y_no_deja_huerfanos(usuario, cuenta):
    viajes = _cat("Viajes", "✈️")
    _mov(cuenta, "Tiquete", "Viajes")
    _mov(cuenta, "Hotel", "Viajes")
    client.post("/presupuestos", json={"categoria": "Viajes", "limite": 500000})

    r = client.delete(f"/categorias/{viajes['id']}")
    assert r.status_code == 409 and r.json()["detail"]["movimientos"] == 2

    assert client.delete(f"/categorias/{viajes['id']}?mover_a=NoExiste").status_code == 400
    ok = client.delete(f"/categorias/{viajes['id']}?mover_a=Ocio")
    assert ok.status_code == 200 and ok.json()["movidos"] == 2

    assert {m["categoria"] for m in client.get("/movimientos").json()} == {"Ocio"}
    assert [p["categoria"] for p in client.get("/presupuestos").json()] == ["Ocio"]
    assert "Viajes" not in [c["nombre"] for c in client.get("/categorias?incluir_inactivas=true").json()]


def test_eliminar_sin_uso_funciona_y_las_base_no_se_eliminan(usuario):
    libre = _cat("Pasajera")
    assert client.delete(f"/categorias/{libre['id']}").status_code == 200
    comida = next(c for c in client.get("/categorias").json() if c["nombre"] == "Comida")
    assert client.delete(f"/categorias/{comida['id']}").status_code == 400


def test_ocultar_no_deja_movimientos_huerfanos(usuario, cuenta):
    c = _cat("Hobby")
    _mov(cuenta, "Pinceles", "Hobby")
    client.put(f"/categorias/{c['id']}", json={"activa": False})
    oculta = next(x for x in client.get("/categorias?incluir_inactivas=true").json() if x["id"] == c["id"])
    assert oculta["movimientos"] == 1


def test_categoria_propia_se_usa_en_movimientos_igual_que_las_base(usuario, cuenta):
    _cat("Gimnasio", "🏋️")
    m = _mov(cuenta, "Mensualidad", "Gimnasio")
    assert m["categoria"] == "Gimnasio" and m["cat_confirmada"] is True
    assert len(client.get("/movimientos?categoria=Gimnasio").json()) == 1


# --- auto-categorización ----------------------------------------------------

def test_patron_de_comercio():
    assert patron_de_comercio("Compra en JUAN VALDEZ SKANDIA con tarjeta débito") == "JUAN VALDEZ SKANDIA"
    assert patron_de_comercio("COMPRA EN D1 ref 123456") == "D1"
    assert patron_de_comercio("Rappi") == "Rappi"


def test_movimiento_categorizado_por_la_app_queda_auto_y_por_revisar(usuario, cuenta):
    m = _mov(cuenta, "Compra en JUAN VALDEZ SKANDIA con tarjeta débito")
    assert m["categoria"] == "Comida"
    assert m["cat_confirmada"] is False and m["cat_origen"] == "comercio"

    # Sigue «Auto» (se puede corregir), pero un comercio conocido es confianza alta: NO es pendiente.
    conteo = client.get("/movimientos/por-revisar/conteo").json()
    assert (conteo["auto"], conteo["otros"], conteo["total"]) == (0, 0, 0)
    assert client.get("/movimientos?por_revisar=true").json() == []


def test_por_tu_regla_y_los_de_otros_tambien_se_revisan(usuario, cuenta):
    client.post("/reglas-categoria", json={"patron": "gimnasio", "categoria": "Salud"})
    a = _mov(cuenta, "Mensualidad gimnasio")
    assert a["cat_origen"] == "regla" and a["cat_confirmada"] is False
    b = _mov(cuenta, "xyzzy qwerty")
    assert b["categoria"] == "Otros"
    conteo = client.get("/movimientos/por-revisar/conteo").json()  # lo de la regla ya está categorizado: solo cuenta «Otros»
    assert (conteo["auto"], conteo["otros"], conteo["total"]) == (0, 1, 1)


def test_lo_que_el_usuario_elige_nace_confirmado(usuario, cuenta):
    m = _mov(cuenta, "Compra en JUAN VALDEZ", "Ocio")
    assert m["cat_confirmada"] is True
    assert client.get("/movimientos/por-revisar/conteo").json()["total"] == 0


def test_confirmar_con_un_toque(usuario, cuenta):
    m = _mov(cuenta, "Rappi pedido")
    n = client.post("/movimientos/confirmar-categorias", json={"movimiento_ids": [m["id"]]}).json()
    assert n["confirmados"] == 1
    assert client.get("/movimientos/por-revisar/conteo").json()["total"] == 0
    assert client.get(f"/movimientos/{m['id']}").json()["categoria"] == "Comida"


def test_cambiar_categoria_manual_confirma(usuario, cuenta):
    m = _mov(cuenta, "Rappi pedido")
    r = client.put(f"/movimientos/{m['id']}", json={"categoria": "Ocio"}).json()
    assert r["categoria"] == "Ocio" and r["cat_confirmada"] is True and r["cat_origen"] == "corregida:Comida"  # la app sugirió Comida y la persona la cambió


def test_aplicar_a_todos_los_de_este_comercio_crea_regla(usuario, cuenta):
    a = _mov(cuenta, "Compra en JUAN VALDEZ SKANDIA con tarjeta débito")
    b = _mov(cuenta, "Compra en JUAN VALDEZ CHAPINERO con tarjeta débito")
    c = _mov(cuenta, "Compra en JUAN VALDEZ SKANDIA con tarjeta débito", monto=5000)
    d = _mov(cuenta, "Netflix mensual", "Ocio")

    r = client.post(f"/movimientos/{a['id']}/recategorizar-comercio", json={"categoria": "Ocio"})
    assert r.status_code == 200, r.text
    assert r.json()["patron"] == "juan valdez skandia" and r.json()["actualizados"] == 2

    por_id = {m["id"]: m for m in client.get("/movimientos").json()}
    assert por_id[a["id"]]["categoria"] == "Ocio" and por_id[a["id"]]["cat_confirmada"] is True
    assert por_id[c["id"]]["categoria"] == "Ocio"
    assert por_id[b["id"]]["categoria"] == "Comida"  # otra sucursal: no coincide con el patrón
    assert por_id[d["id"]]["categoria"] == "Ocio"

    reglas = client.get("/reglas-categoria").json()
    assert any(x["patron"] == "juan valdez skandia" and x["categoria"] == "Ocio" for x in reglas)

    # a futuro, el mismo comercio queda "por tu regla"
    nuevo = _mov(cuenta, "Compra en JUAN VALDEZ SKANDIA con tarjeta débito")
    assert nuevo["categoria"] == "Ocio" and nuevo["cat_origen"] == "regla"


def test_aplicar_solo_a_este_no_crea_regla(usuario, cuenta):
    a = _mov(cuenta, "Compra en D1 ref 99")
    client.post(f"/movimientos/{a['id']}/recategorizar-comercio", json={"categoria": "Hogar", "aplicar_a_todos": False})
    assert client.get("/reglas-categoria").json() == []


def test_categoria_inexistente_en_recategorizar_se_rechaza(usuario, cuenta):
    client.get("/categorias")  # crea las base
    a = _mov(cuenta, "Compra en D1")
    r = client.post(f"/movimientos/{a['id']}/recategorizar-comercio", json={"categoria": "Inventada"})
    assert r.status_code == 400


def test_renombrar_base_no_deja_sugerencias_huerfanas(usuario, cuenta):
    comida = next(c for c in client.get("/categorias").json() if c["nombre"] == "Comida")
    client.put(f"/categorias/{comida['id']}", json={"nombre": "Restaurantes"})
    m = _mov(cuenta, "Compra en JUAN VALDEZ")  # el diccionario sugiere 'Comida', que ya no existe
    assert m["categoria"] == "Otros"


def test_lo_auto_no_entrena_al_clasificador(usuario, cuenta):
    from app.autocat import movimientos_confirmados
    from app.database import SessionLocal
    _mov(cuenta, "Compra en JUAN VALDEZ SKANDIA")  # auto, sin confirmar
    with SessionLocal() as db:
        assert movimientos_confirmados(db, usuario) == []
