"""Aprendizaje de categorías: reglas por huella de comercio, orden de prioridad del
clasificador con su razón, reglas peligrosas, vocabulario y 'por qué se categorizó así'."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'aprende.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.autocat import ClasificadorUsuario  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def usuario(request):
    uid = f"user-apr-{request.node.name}"[:60]
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="a@test.com", nombre="Apr")
    yield uid


@pytest.fixture()
def cuenta(usuario):
    r = client.post("/cuentas", json={"nombre": "Principal", "saldo": 1_000_000})
    assert r.status_code == 200, r.text
    client.get("/categorias")  # crea las 8 base
    return r.json()


def _mov(cuenta, descripcion, categoria=None, monto=10000, tipo="expense"):
    body = {"cuenta_id": cuenta["id"], "descripcion": descripcion, "monto": monto, "tipo": tipo}
    if categoria:
        body["categoria"] = categoria
    r = client.post("/movimientos", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _clasificar(uid, descripcion):
    with SessionLocal() as db:
        return ClasificadorUsuario(db, uid).clasificar(descripcion)


def test_regla_guardada_se_aplica_a_otra_descripcion_del_mismo_comercio(usuario, cuenta):
    r = client.post("/reglas-categoria/aprender", json={"descripcion": "PAGO EN VENTO COLIVING 0105", "categoria": "Hogar"})
    assert r.status_code == 200 and r.json()["guardada"] and r.json()["huella"] == "vento coliving"
    nuevo = _mov(cuenta, "COMPRA VENTO COLIVING BOGOTA")  # descripción distinta, mismo comercio
    assert nuevo["categoria"] == "Hogar" and nuevo["cat_origen"] == "regla"
    res = _clasificar(usuario, "Pago PSE Vento Coliving S.A.S. 2025-11-01")
    assert res["categoria"] == "Hogar" and res["razon"] == "por tu regla «vento coliving»"


def test_orden_de_prioridad_con_razon(usuario, cuenta):
    # 4) nada conocido -> None (se le pregunta)
    assert _clasificar(usuario, "PAGO EN XQZ INVERSIONES 77") is None
    # 3) diccionario
    r = _clasificar(usuario, "COMPRA PANADERIA LA ESPIGA")
    assert r["categoria"] == "Comida" and r["fuente"] == "diccionario" and r["razon"] == "por palabra clave «panaderia»" or r["razon"].startswith("por palabra clave")
    # 2) modelo aprendido de movimientos confirmados: 'Taller Mecanico' va a Hogar por historial propio
    for _ in range(3):
        _mov(cuenta, "Mecanicos del Norte revision", "Hogar")
    r = _clasificar(usuario, "Mecanicos del Norte cambio")
    assert r["categoria"] == "Hogar" and r["fuente"] == "historial" and r["razon"].startswith("aprendida de tu historial")
    # 1) regla del usuario le gana al modelo aprendido y al diccionario
    client.post("/reglas-categoria/aprender", json={"descripcion": "Mecanicos del Norte", "categoria": "Ocio"})
    r = _clasificar(usuario, "Mecanicos del Norte cambio")
    assert r["categoria"] == "Ocio" and r["fuente"] == "regla" and r["razon"] == "por tu regla «mecanicos del norte»"
    client.post("/reglas-categoria/aprender", json={"descripcion": "Panaderia la espiga", "categoria": "Ocio"})
    assert _clasificar(usuario, "COMPRA PANADERIA LA ESPIGA")["fuente"] == "regla"


def test_huella_exacta_gana_a_regla_por_contiene(usuario, cuenta):
    client.post("/reglas-categoria", json={"patron": "juan valdez", "categoria": "Comida", "prioridad": 5})
    client.post("/reglas-categoria/aprender", json={"descripcion": "Compra en JUAN VALDEZ SKANDIA", "categoria": "Ocio"})
    assert _clasificar(usuario, "PAGO JUAN VALDEZ SKANDIA 0001")["categoria"] == "Ocio"      # exacta
    assert _clasificar(usuario, "PAGO JUAN VALDEZ CHAPINERO")["categoria"] == "Comida"       # contiene


def test_regla_existente_se_actualiza_sin_contradicciones(usuario, cuenta):
    client.post("/reglas-categoria/aprender", json={"descripcion": "PAGO EN VENTO COLIVING 0105", "categoria": "Hogar"})
    r = client.post("/reglas-categoria/aprender", json={"descripcion": "COMPRA VENTO COLIVING BOGOTA", "categoria": "Ocio"}).json()
    assert r["actualizada"] is True
    reglas = [x for x in client.get("/reglas-categoria").json() if "vento" in x["patron"]]
    assert len(reglas) == 1 and reglas[0]["categoria"] == "Ocio"


def test_no_guarda_reglas_peligrosas_sin_confirmar(usuario, cuenta):
    for desc in ("PAGO EN D1", "Pago", "COMPRA EN 0105 BOGOTA", "Compra en TIENDA"):
        r = client.post("/reglas-categoria/aprender", json={"descripcion": desc, "categoria": "Comida"}).json()
        assert r["guardada"] is False and r["motivo"], desc
    assert client.get("/reglas-categoria").json() == []
    # con confirmación explícita sí se guarda una huella corta pero real
    r = client.post("/reglas-categoria/aprender", json={"descripcion": "PAGO EN D1", "categoria": "Comida", "confirmar_peligrosa": True}).json()
    assert r["guardada"] is True and r["huella"] == "d1"


def test_categoria_inexistente_se_rechaza(usuario, cuenta):
    r = client.post("/reglas-categoria/aprender", json={"descripcion": "Vento Coliving", "categoria": "Inventada"})
    assert r.status_code == 400


def test_aplicar_a_los_anteriores_recategoriza_solo_ese_comercio(usuario, cuenta):
    a = _mov(cuenta, "PAGO EN VENTO COLIVING 0105")
    b = _mov(cuenta, "COMPRA VENTO COLIVING BOGOTA", "Otros")
    c = _mov(cuenta, "COMPRA EN OTRO LADO XYZ")
    r = client.post("/reglas-categoria/aprender", json={
        "descripcion": "PAGO EN VENTO COLIVING 0105", "categoria": "Hogar", "aplicar_anteriores": True,
    }).json()
    assert r["anteriores_actualizados"] == 2
    por_id = {m["id"]: m for m in client.get("/movimientos").json()}
    assert por_id[a["id"]]["categoria"] == "Hogar" and por_id[a["id"]]["cat_confirmada"] is True
    assert por_id[b["id"]]["categoria"] == "Hogar"
    assert por_id[c["id"]]["categoria"] != "Hogar"


def test_vocabulario_ordena_por_impacto_y_muestra_progreso(usuario, cuenta):
    _mov(cuenta, "COMPRA XQZ INVERSIONES 1", monto=500_000)
    _mov(cuenta, "PAGO XQZ INVERSIONES BOGOTA", monto=300_000)
    _mov(cuenta, "COMPRA LA PERLA DEL SUR", monto=20_000)
    _mov(cuenta, "COMPRA JUMBO CALLE 80", "Comida", monto=50_000)  # ya tiene categoria
    v = client.get("/categorias/vocabulario").json()
    claves = [c["clave"] for c in v["comercios"]]
    assert claves[0] == "xqz inversiones" and "la perla del" not in claves[0]
    top = v["comercios"][0]
    assert top["conteo"] == 2 and top["monto_total"] == 800_000 and top["categoria_actual"] == "Otros" and top["movimiento_id"]
    assert v["progreso"]["movimientos"] >= 4 and 0 <= v["progreso"]["porcentaje"] <= 100
    # al enseñar la regla, el comercio sale de la lista y sube el entrenamiento
    client.post("/reglas-categoria/aprender", json={"descripcion": "XQZ INVERSIONES", "categoria": "Otros", "aplicar_anteriores": False})
    v2 = client.get("/categorias/vocabulario").json()
    assert "xqz inversiones" not in [c["clave"] for c in v2["comercios"]]
    assert v2["progreso"]["comercios_entrenados"] == 1


def test_vocabulario_aislado_por_usuario(usuario, cuenta):
    _mov(cuenta, "COMPRA XQZ INVERSIONES 1", monto=500_000)
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="otro-usuario-vocab", email="o@t.com", nombre="O")
    assert client.get("/categorias/vocabulario").json()["comercios"] == []


def test_explicar_por_que_se_categorizo_asi(usuario, cuenta):
    _mov(cuenta, "COMPRA PANADERIA LA ESPIGA")
    r = client.get("/categorias/explicar", params={"q": "espiga"}).json()["resultados"]
    assert r[0]["categoria_sugerida"] == "Comida" and r[0]["razon"].startswith("por palabra clave") and r[0]["movimiento_id"]
    ej = client.get("/categorias/explicar", params={"q": "zzzz desconocido"}).json()["resultados"]
    assert ej[0]["es_ejemplo"] is True and "enséñame" in ej[0]["razon"]
    assert client.get("/categorias/explicar", params={"q": "a"}).status_code == 400


def test_categoria_del_diccionario_que_el_usuario_no_tiene_cae_en_respaldo_u_otros(usuario, cuenta):
    # 'Suscripciones' no es una categoría base: se respalda en 'Ocio'
    assert _clasificar(usuario, "NETFLIX.COM")["categoria"] == "Ocio"
    # 'Comisiones y costos financieros' no existe para él: no se sugiere nada y se le pregunta
    assert _clasificar(usuario, "RETIRO CAJERO ATM") is None
    # si la crea, se usa
    client.post("/categorias", json={"nombre": "Comisiones y costos financieros", "icono": "🏦"})
    assert _clasificar(usuario, "RETIRO CAJERO ATM")["categoria"] == "Comisiones y costos financieros"
    # las categorías de sistema de costos (cuota de manejo, 4x1000...) no dependen de la lista del usuario
    assert _clasificar(usuario, "CUOTA DE MANEJO TARJETA")["categoria"] == "Cuota de manejo"


def test_importar_confirmar_recuerda_la_categoria_elegida(usuario, cuenta):
    filas = [
        {"fecha": "2025-10-01", "descripcion": "PAGO EN VENTO COLIVING 0105", "monto": 900000, "tipo": "expense",
         "categoria": "Hogar", "recordar": True, "aplicar_anteriores": False},
        {"fecha": "2025-10-02", "descripcion": "PAGO EN D1", "monto": 30000, "tipo": "expense",
         "categoria": "Comida", "recordar": True},
    ]
    r = client.post("/importar/confirmar", json={"cuenta_id": cuenta["id"], "nombre_archivo": "x.csv", "filas": filas}).json()
    assert r["importados"] == 2 and r["reglas_guardadas"] == 1 and len(r["reglas_omitidas"]) == 1
    assert _clasificar(usuario, "COMPRA VENTO COLIVING BOGOTA")["categoria"] == "Hogar"


def test_importar_faltantes_recuerda_y_no_duplica_si_otro_archivo_ya_lo_registro(usuario, cuenta):
    import json
    from datetime import datetime

    from app.conciliacion import compute_fingerprint
    from app.models import HistorialExtracto

    ya = _mov(cuenta, "PAGO EN VENTO COLIVING 0105", "Hogar", monto=900000)
    fp_ya = compute_fingerprint(datetime.fromisoformat(ya["fecha"]), 900000, cuenta["id"], "PAGO EN VENTO COLIVING 0105", "expense")
    review = [
        {"fecha": ya["fecha"][:10], "descripcion": "PAGO EN VENTO COLIVING 0105", "monto": 900000, "tipo": "expense",
         "referencia": "", "fingerprint": fp_ya, "estado": "faltante"},
        {"fecha": "2025-10-03", "descripcion": "COMPRA EN OLIMPICA BOGOTA", "monto": 120000, "tipo": "expense",
         "referencia": "", "fingerprint": "fp-olimpica", "estado": "faltante"},
    ]
    with SessionLocal() as db:
        h = HistorialExtracto(usuario_id=usuario, cuenta_id=cuenta["id"], banco_detectado="nu", total_movimientos=2,
                              exactos=0, aproximados=0, faltantes=2, importados=0, estado="pendiente_revision",
                              review_json=json.dumps(review))
        db.add(h)
        db.commit()
        hid = h.id
    r = client.post(f"/conciliacion/historial/{hid}/importar", json={
        "fingerprints": [fp_ya, "fp-olimpica"], "categorias": {"fp-olimpica": "Comida"},
        "recordar": ["fp-olimpica"], "aplicar_anteriores": [],
    }).json()
    assert r["importados"] == 1 and r["duplicados_omitidos"] == 1 and r["reglas_guardadas"] == 1
    assert _clasificar(usuario, "PAGO OLIMPICA SUPERSTORE")["categoria"] == "Comida"
