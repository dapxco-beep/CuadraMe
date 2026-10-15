"""«Por categorizar» a elección: definición única de pendientes, silencios, acciones y reglas opcionales."""
import os
import tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import pendientes  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def usuario(request):
    uid = f"user-pc-{request.node.name}"
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="p@test.com", nombre="Pau")
    yield uid


@pytest.fixture()
def cuenta(usuario):
    r = client.post("/cuentas", json={"nombre": "Principal", "saldo": 5000000})
    assert r.status_code == 200, r.text
    return r.json()


def _mov(cuenta, descripcion, categoria=None, monto=10000, tipo="expense"):
    body = {"cuenta_id": cuenta["id"], "descripcion": descripcion, "monto": monto, "tipo": tipo}
    if categoria:
        body["categoria"] = categoria
    r = client.post("/movimientos", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _poner(id_, **campos):
    """Fuerza el estado de un movimiento (como lo dejaría una importación o un correo)."""
    from app.database import SessionLocal
    from app.models import Movimiento

    db = SessionLocal()
    try:
        m = db.query(Movimiento).filter(Movimiento.id == id_).first()
        for k, v in campos.items():
            setattr(m, k, v)
        db.commit()
    finally:
        db.close()


def _conteo():
    return client.get("/movimientos/por-revisar/conteo").json()


# --- 1) qué cuenta -------------------------------------------------------------------------

def test_categorizado_con_confianza_alta_no_cuenta(cuenta):
    for origen in ("regla", "comercio", "similar"):
        m = _mov(cuenta, f"Tienda {origen}", "Comida")
        _poner(m["id"], cat_confirmada=False, cat_origen=origen)
    assert _conteo()["total"] == 0


def test_otros_baja_confianza_y_marcados_si_cuentan(cuenta):
    for _ in range(4):  # 4 repeticiones: ya se pregunta
        _mov(cuenta, "Cosa rara uno")  # Otros
        baja = _mov(cuenta, "Cosa sugerida", "Ocio")
        _poner(baja["id"], cat_confirmada=False, cat_origen="sugerida")
    marcada = _mov(cuenta, "Compra marcada", "Comida")  # una sola vez, pero la marcó el cliente
    _poner(marcada["id"], cat_origen="marcada")
    c = _conteo()
    assert (c["total"], c["otros"], c["baja"], c["marcadas"]) == (9, 4, 4, 1)
    assert c["auto"] == 5


def test_regla_mas_de_3_repeticiones(cuenta):
    """1-3 apariciones NO son pendientes (ni en contador, ni en lista, ni en tareas); 4+ sí; marcado sí."""
    for _ in range(3):
        _mov(cuenta, "Zoltan tres veces")
    _mov(cuenta, "Quimbaya una vez")
    assert _conteo()["total"] == 0
    assert client.get("/por-categorizar").json()["conteo"]["total"] == 0
    assert client.get("/movimientos?por_revisar=true").json() == []
    tareas = client.get("/sincronizacion/estado").json()["tareas"]
    assert not [t for t in tareas if t["id"] == "movimientos_por_categorizar"]
    assert len(client.get("/movimientos").json()) == 4  # siguen visibles y editables
    _mov(cuenta, "Zoltan tres veces")  # la 4.a
    m = _mov(cuenta, "Quimbaya una vez", "Comida")
    _poner(m["id"], cat_origen="marcada")
    esperado = 4 + 1
    assert _conteo()["total"] == esperado
    assert client.get("/por-categorizar").json()["conteo"]["total"] == esperado
    assert len(client.get("/movimientos?por_revisar=true").json()) == esperado
    t = next(t for t in client.get("/sincronizacion/estado").json()["tareas"] if t["id"] == "movimientos_por_categorizar")
    assert t["cantidad"] == esperado


def test_lo_confirmado_por_el_usuario_no_cuenta(cuenta):
    _mov(cuenta, "Almuerzo", "Comida")
    assert _conteo()["total"] == 0


def test_traslados_pagos_de_tarjeta_y_ajustes_nunca_cuentan(cuenta):
    _mov(cuenta, "Pago tarjeta Visa")
    b = _mov(cuenta, "Ajuste", tipo="income")
    _poner(b["id"], fuente="ajuste_saldo")
    c = _mov(cuenta, "Rendimientos", "Rendimientos")
    _poner(c["id"], cat_confirmada=False, cat_origen="sugerida")
    d = _mov(cuenta, "Traslado raro")
    _poner(d["id"], fuente="transferencia_interna")
    assert _conteo()["total"] == 0


def test_el_listado_por_revisar_coincide_con_el_contador(cuenta):
    for _ in range(4):
        _mov(cuenta, "Cosa rara uno")
    alta = _mov(cuenta, "Netflix", "Ocio")
    _poner(alta["id"], cat_confirmada=False, cat_origen="regla")
    lista = client.get("/movimientos?por_revisar=true").json()
    assert len(lista) == _conteo()["total"] == 4
    assert lista[0]["por_categorizar"] is True
    todas = client.get("/movimientos").json()
    assert {m["descripcion"]: m["por_categorizar"] for m in todas} == {"Cosa rara uno": True, "Netflix": False}


def test_inicio_y_consejos_usan_la_misma_definicion(cuenta, usuario):
    from datetime import datetime

    from app import consejos
    from app.database import SessionLocal

    for i in range(6):
        m = _mov(cuenta, f"Comercio {i}", "Comida")
        _poner(m["id"], cat_confirmada=False, cat_origen="regla")
    assert not [t for t in client.get("/sincronizacion/estado").json()["tareas"] if t["id"] == "movimientos_por_categorizar"]
    db = SessionLocal()
    try:
        hoy = datetime.now()
        datos = consejos.reunir_datos(db, usuario, hoy)
        assert consejos._regla_sin_categorizar(datos, hoy) == []
    finally:
        db.close()
    for i in range(5):
        _mov(cuenta, "Pendiente repetido")
    t = next(t for t in client.get("/sincronizacion/estado").json()["tareas"] if t["id"] == "movimientos_por_categorizar")
    assert t["cantidad"] == 5 and t["opcional"] is True
    db = SessionLocal()
    try:
        datos = consejos.reunir_datos(db, usuario, datetime.now())
        c = consejos._regla_sin_categorizar(datos, datetime.now())
        assert len(c) == 1
    finally:
        db.close()


# --- 2) selección, silencios y deshacer -------------------------------------------------------

def test_resumen_agrupa_por_comercio_y_ordena_por_impacto(cuenta):
    for _ in range(4):
        _mov(cuenta, "Compra en ZOLTAN PEQUE", monto=5000)
    q = _mov(cuenta, "Compra en QUIMBAYA GRANDE", monto=900000)
    _poner(q["id"], cat_origen="marcada")
    r = client.get("/por-categorizar").json()
    assert r["conteo"]["total"] == 5
    assert [g["conteo"] for g in r["grupos"]] == [1, 4]
    assert r["grupos"][0]["monto_total"] == 900000
    assert r["grupos"][1]["relevante"] is True  # se repite 4 veces
    assert r["relevantes"] >= 1


def test_limite_visible_y_ver_todos(cuenta):
    nombres = "alfa beta gamma delta epsilon zeta eta theta iota kappa lambda sigma".split()
    for i, n in enumerate(nombres):
        m = _mov(cuenta, f"Local {n} Extraño", monto=1000 * (i + 1))
        _poner(m["id"], cat_origen="marcada")
    r = client.get("/por-categorizar?limite=10").json()
    assert len(r["grupos"]) == 10 and r["hay_mas"] is True and r["total_grupos"] == 12
    assert len(client.get("/por-categorizar?todos=true").json()["grupos"]) == 12


def test_no_preguntar_silencia_y_se_deshace(cuenta):
    for _ in range(4):
        _mov(cuenta, "Compra en ZOLTAN PEQUE")
    g = client.get("/por-categorizar").json()["grupos"][0]
    r = client.post("/por-categorizar/accion", json={"accion": "no_preguntar", "huellas": [g["huella"]]}).json()
    assert r["huellas_nuevas"] == [g["huella"]]
    assert _conteo()["total"] == 0
    assert client.get("/por-categorizar/silencios").json()["silencios"][0]["huella"] == g["huella"]
    client.post("/por-categorizar/accion", json={"accion": "no_preguntar", "huellas": [g["huella"]]})  # idempotente
    assert len(client.get("/por-categorizar/silencios").json()["silencios"]) == 1
    client.post("/por-categorizar/deshacer", json={"huellas": [g["huella"]], "tipo_silencio": "no_preguntar"})
    assert _conteo()["total"] == 4


def test_ocultar_y_quitar_silencio(cuenta):
    ids = [_mov(cuenta, "Compra en OTRO LUGAR")["id"] for _ in range(4)]
    client.post("/por-categorizar/accion", json={"accion": "ocultar", "movimiento_ids": ids})
    assert _conteo()["total"] == 0
    h = client.get("/por-categorizar/silencios").json()["silencios"][0]["huella"]
    client.post("/por-categorizar/silencios/quitar", json={"huellas": [h]})
    assert _conteo()["total"] == 4


def test_silencio_es_por_usuario(cuenta):
    for _ in range(4):
        _mov(cuenta, "Compra en LUGAR X")
    h = client.get("/por-categorizar").json()["grupos"][0]["huella"]
    client.post("/por-categorizar/accion", json={"accion": "ocultar", "huellas": [h]})
    assert _conteo()["total"] == 0
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="otro", email="o@t.com", nombre="O")
    assert client.get("/por-categorizar/silencios").json()["silencios"] == []


def test_dejar_como_estan_saca_de_pendientes_y_se_deshace(cuenta):
    ids = [_mov(cuenta, "Cosa rara repetida")["id"] for i in range(4)]
    r = client.post("/por-categorizar/accion", json={"accion": "dejar", "movimiento_ids": ids}).json()
    assert r["movimientos"] == 4 and _conteo()["total"] == 0
    assert {m["categoria"] for m in client.get("/movimientos").json()} == {"Otros"}  # decisión, no categoría inventada
    client.post("/por-categorizar/deshacer", json={"previos": r["previos"]})
    assert _conteo()["total"] == 4


def test_marcar_para_revisar_y_deshacer(cuenta):
    m = _mov(cuenta, "Almuerzo", "Comida")
    assert _conteo()["total"] == 0
    r = client.post("/por-categorizar/accion", json={"accion": "marcar", "movimiento_ids": [m["id"]]}).json()
    assert _conteo()["marcadas"] == 1
    client.post("/por-categorizar/deshacer", json={"previos": r["previos"]})
    assert _conteo()["total"] == 0


def test_ponerles_categoria_a_lo_seleccionado_sin_crear_regla(cuenta):
    for i in range(4):
        _mov(cuenta, "Compra en ZOLTAN PEQUE")
    g = client.get("/por-categorizar").json()["grupos"][0]
    r = client.post("/por-categorizar/accion", json={"accion": "categoria", "huellas": [g["huella"]], "categoria": "Comida"}).json()
    assert r["movimientos"] == 4 and r["reglas_creadas"] == []
    assert _conteo()["total"] == 0
    assert client.get("/reglas-categoria").json() == []  # ninguna regla sin pedirla


def test_categoria_con_recordar_crea_la_regla_y_se_deshace_todo(cuenta):
    for _ in range(4):
        _mov(cuenta, "Compra en ZOLTAN PEQUE")
    otro = _mov(cuenta, "Compra en ZOLTAN PEQUE", "Ocio")  # ya categorizado por el usuario
    g = client.get("/por-categorizar").json()["grupos"][0]
    r = client.post("/por-categorizar/accion", json={
        "accion": "categoria", "huellas": [g["huella"]], "categoria": "Comida", "recordar": True, "aplicar_anteriores": True,
    }).json()
    assert len(r["reglas_creadas"]) == 1
    assert len(client.get("/reglas-categoria").json()) == 1
    assert {m["categoria"] for m in client.get("/movimientos").json()} == {"Comida"}
    d = client.post("/por-categorizar/deshacer", json={"previos": r["previos"], "reglas_creadas": r["reglas_creadas"]}).json()
    assert d["reglas_borradas"] == 1
    assert client.get("/reglas-categoria").json() == []
    por_id = {m["id"]: m["categoria"] for m in client.get("/movimientos").json()}
    assert por_id[otro["id"]] == "Ocio"  # lo que la regla cambió en los anteriores, también vuelve
    assert _conteo()["otros"] == 4


def test_categoria_inexistente_y_sin_seleccion(cuenta):
    m = _mov(cuenta, "Cosa rara")
    client.get("/categorias")  # crea la lista base del usuario
    assert client.post("/por-categorizar/accion", json={"accion": "categoria", "movimiento_ids": [m["id"]], "categoria": "Inventada"}).status_code == 400
    assert client.post("/por-categorizar/accion", json={"accion": "dejar"}).status_code == 400


def test_no_se_toca_lo_de_otro_usuario(cuenta):
    m = _mov(cuenta, "Cosa rara")
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="intruso", email="i@t.com", nombre="I")
    r = client.post("/por-categorizar/accion", json={"accion": "dejar", "movimiento_ids": [m["id"]]})
    assert r.status_code == 400  # para él no existe


# --- 3) reglas a elección ---------------------------------------------------------------------

def test_vista_previa_recomienda_solo_si_se_repite_4_o_mas(cuenta):
    _mov(cuenta, "Compra en UNICA VEZ SAS")
    r = client.get("/reglas-categoria/vista-previa", params={"descripcion": "Compra en UNICA VEZ SAS"}).json()
    assert r["repeticiones"] == 2 and r["recomendada"] is False  # este mismo movimiento ya está guardado
    r = client.get("/reglas-categoria/vista-previa", params={"descripcion": "Compra en NUNCA VISTO SAS"}).json()
    assert r["repeticiones"] == 1 and r["afectara_pasados"] == 0 and r["recomendada"] is False
    for _ in range(2):
        _mov(cuenta, "Compra en KOPI ZEBRA")
    r = client.get("/reglas-categoria/vista-previa", params={"descripcion": "Compra en KOPI ZEBRA"}).json()
    assert r["repeticiones"] == 3 and r["recomendada"] is False  # 3 apariciones: no se sugiere
    _mov(cuenta, "Compra en KOPI ZEBRA")
    r = client.get("/reglas-categoria/vista-previa", params={"descripcion": "Compra en KOPI ZEBRA"}).json()
    assert r["repeticiones"] == 4 and r["recomendada"] is True  # 4 apariciones: sí


def test_sugerencias_umbral_3_no_4_si(cuenta):
    for _ in range(3):
        _mov(cuenta, "Compra en TRES VECES", "Comida")
    assert client.get("/reglas-categoria/sugerencias").json()["sugerencias"] == []
    _mov(cuenta, "Compra en TRES VECES", "Comida")
    sug = client.get("/reglas-categoria/sugerencias").json()["sugerencias"]
    assert [s["huella"] for s in sug] == ["tres veces"]


def test_sugerencias_crear_solo_las_elegidas_y_descartar(cuenta):
    for _ in range(4):
        _mov(cuenta, "Compra en KOPI ZEBRA", "Comida")
        _mov(cuenta, "Compra en QUIRIGUA AZUL", "Transporte")
        _mov(cuenta, "Compra en XANADU ROYAL", "Ocio")
    _mov(cuenta, "Compra en SOLO UNA", "Ocio")
    sug = client.get("/reglas-categoria/sugerencias").json()["sugerencias"]
    assert {s["huella"] for s in sug} == {"kopi zebra", "quirigua azul", "xanadu royal"}
    assert client.get("/reglas-categoria").json() == []  # sugerir no crea
    r = client.post("/reglas-categoria/sugerencias/crear", json={"elegidas": [{"huella": "kopi zebra", "categoria": "Comida"}]}).json()
    assert r["creadas"] == ["kopi zebra"]
    assert len(client.get("/reglas-categoria").json()) == 1
    client.post("/reglas-categoria/sugerencias/descartar", json={"huellas": ["xanadu royal"]})
    assert {s["huella"] for s in client.get("/reglas-categoria/sugerencias").json()["sugerencias"]} == {"quirigua azul"}
    client.post("/reglas-categoria/sugerencias/restaurar", json={"huellas": ["xanadu royal"]})
    assert "xanadu royal" in {s["huella"] for s in client.get("/reglas-categoria/sugerencias").json()["sugerencias"]}


def test_reglas_en_lote_pausar_reanudar_borrar(cuenta):
    ids = []
    for nombre, cat in (("kopi zebra", "Comida"), ("quirigua azul", "Transporte")):
        ids.append(client.post("/reglas-categoria", json={"patron": nombre, "categoria": cat}).json()["id"])
    client.post("/reglas-categoria/lote", json={"ids": ids, "accion": "pausar"})
    assert all(r["activa"] is False for r in client.get("/reglas-categoria").json())
    m = _mov(cuenta, "Compra en KOPI ZEBRA", monto=3000)
    cat_pausada = next(x for x in client.get("/movimientos").json() if x["id"] == m["id"])["categoria"]
    client.post("/reglas-categoria/lote", json={"ids": ids, "accion": "reanudar"})
    m2 = client.post("/movimientos/clasificar", json={"descripcion": "Compra en KOPI ZEBRA"})
    assert cat_pausada == "Otros"
    assert m2.status_code == 200 and m2.json()["categoria"] == "Comida"
    r = client.post("/reglas-categoria/lote", json={"ids": ids, "accion": "borrar"}).json()
    assert r["afectadas"] == 2 and client.get("/reglas-categoria").json() == []


def test_motivo_funciona_con_dicts_y_silencios():
    d = {"categoria": "Otros", "cat_confirmada": True, "cat_origen": None, "fuente": "manual", "tipo": "expense",
         "descripcion": "Compra en LUGAR"}
    assert pendientes.motivo(d) == "otros"
    assert pendientes.motivo(d, {"lugar"}) is None
    assert pendientes.motivo({**d, "cat_origen": "marcada"}, {"lugar"}) == "marcada"  # lo marcó él: gana
    assert pendientes.motivo({**d, "cat_origen": "dejada"}) is None
