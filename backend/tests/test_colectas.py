"""Colectas (vacas): reparto, pagos parciales, ingreso en cuenta, enlace público de solo lectura y aislamiento."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'colectas.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.limites import _eventos  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def _como(uid):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@test.com", nombre="Org")


@pytest.fixture(autouse=True)
def _usuario(request):
    _como(f"col-{request.node.name}")
    _eventos.clear()
    yield


def _contacto(nombre, tel=""):
    return client.post("/gastos-compartidos/contactos", json={"nombre": nombre, "telefono": tel}).json()["id"]


def _cuenta(saldo=100_000):
    return client.post("/cuentas", json={"nombre": "Cta", "saldo": saldo, "moneda": "COP"}).json()


def _saldo(cuenta_id):
    return next(c["saldo"] for c in client.get("/cuentas").json() if c["id"] == cuenta_id)


def _crear(nombre="Inscripción", valor=50_000, modo="por_persona", n=3, **extra):
    ids = [_contacto(f"Persona{i} Apellido") for i in range(n)]
    r = client.post("/colectas", json={"nombre": nombre, "valor": valor, "modo": modo, "participantes": ids, **extra})
    assert r.status_code == 200, r.text
    return r.json()["id"], ids


def test_por_persona_cada_uno_debe_el_valor():
    cid, _ = _crear()
    d = client.get(f"/colectas/{cid}").json()
    assert d["meta"] == 150_000 and d["recogido"] == 0 and d["personas"] == 3
    assert all(p["debe"] == 50_000 and p["estado"] == "falta" for p in d["participantes"])


def test_meta_total_se_reparte_sin_perder_pesos():
    cid, _ = _crear(valor=100_000, modo="meta_total", n=3)
    d = client.get(f"/colectas/{cid}").json()
    assert sorted(p["debe"] for p in d["participantes"]) == [33_333, 33_333, 33_334]
    assert d["meta"] == 100_000


def test_pago_completo_y_parcial_cambian_el_estado_y_los_totales():
    cid, _ = _crear()
    ps = client.get(f"/colectas/{cid}").json()["participantes"]
    assert client.post(f"/colectas/{cid}/aportes/{ps[0]['aporte_id']}/pagos", json={}).status_code == 200
    assert client.post(f"/colectas/{cid}/aportes/{ps[1]['aporte_id']}/pagos", json={"monto": 20_000}).status_code == 200
    d = client.get(f"/colectas/{cid}").json()
    estados = {p["aporte_id"]: p["estado"] for p in d["participantes"]}
    assert estados[ps[0]["aporte_id"]] == "pagado" and estados[ps[1]["aporte_id"]] == "parcial"
    assert d["recogido"] == 70_000 and d["falta"] == 80_000 and d["pagaron"] == 1
    # quien ya pagó todo no puede «pagar» otra vez por defecto
    assert client.post(f"/colectas/{cid}/aportes/{ps[0]['aporte_id']}/pagos", json={}).status_code == 400


def test_registrar_ingreso_suma_a_la_cuenta_y_deshacer_lo_retira():
    cuenta = _cuenta(100_000)
    cid, _ = _crear(cuenta_id=cuenta["id"])
    ap = client.get(f"/colectas/{cid}").json()["participantes"][0]["aporte_id"]
    r = client.post(f"/colectas/{cid}/aportes/{ap}/pagos", json={"registrar_ingreso": True})
    assert r.status_code == 200 and r.json()["movimiento_id"]
    assert _saldo(cuenta["id"]) == 150_000
    pago = next(x for x in client.get(f"/colectas/{cid}").json()["participantes"] if x["aporte_id"] == ap)["pagos"][0]
    assert pago["registrado_en_cuenta"]
    assert client.delete(f"/colectas/{cid}/pagos/{pago['id']}").status_code == 200
    assert _saldo(cuenta["id"]) == 100_000
    assert client.get(f"/colectas/{cid}").json()["recogido"] == 0


def test_registrar_ingreso_sin_cuenta_pide_cuenta():
    cid, _ = _crear()
    ap = client.get(f"/colectas/{cid}").json()["participantes"][0]["aporte_id"]
    assert client.post(f"/colectas/{cid}/aportes/{ap}/pagos", json={"registrar_ingreso": True}).status_code == 400


def test_incluirme_agrega_al_organizador_y_no_acepta_extraños():
    ids = [_contacto("Ana")]
    r = client.post("/colectas", json={"nombre": "X", "valor": 10_000, "participantes": ids, "incluirme": True})
    d = client.get(f"/colectas/{r.json()['id']}").json()
    assert {p["nombre"] for p in d["participantes"]} == {"Tú", "Ana"}
    assert client.post("/colectas", json={"nombre": "X", "valor": 10, "participantes": ["no-es-mio"]}).status_code == 400
    assert client.post("/colectas", json={"nombre": "X", "valor": 10, "participantes": []}).status_code == 400


def test_agregar_y_quitar_participante():
    cid, _ = _crear(n=1)
    nuevo = _contacto("Nuevo")
    assert client.post(f"/colectas/{cid}/participantes", json={"contacto_id": nuevo}).status_code == 200
    assert client.post(f"/colectas/{cid}/participantes", json={"contacto_id": nuevo}).status_code == 400
    ps = client.get(f"/colectas/{cid}").json()["participantes"]
    assert len(ps) == 2 and all(p["debe"] == 50_000 for p in ps)
    ap = next(p for p in ps if p["nombre"] == "Nuevo")["aporte_id"]
    assert client.delete(f"/colectas/{cid}/participantes/{ap}").status_code == 200


def test_enlace_publico_solo_lectura_sin_datos_privados():
    cid, _ = _crear()
    assert client.get("/colectas/publico/token-que-no-existe-0000000000").status_code == 404
    token = client.post(f"/colectas/{cid}/compartir").json()["token"]
    ap = client.get(f"/colectas/{cid}").json()["participantes"][0]["aporte_id"]
    client.post(f"/colectas/{cid}/aportes/{ap}/pagos", json={})
    app.dependency_overrides.pop(get_current_user, None)  # el enlace público NO usa sesión
    r = client.get(f"/colectas/publico/{token}")
    assert r.status_code == 200
    d = r.json()
    assert d["nombre"] == "Inscripción" and d["recogido"] == 50_000
    assert {p["nombre"] for p in d["participantes"]} == {"Persona0", "Persona1", "Persona2"}  # solo nombre de pila
    texto = r.text
    for privado in ("usuario_id", "cuenta_id", "telefono", "Apellido", "movimiento"):
        assert privado not in texto
    _como("col-otro")
    cid_dueno = cid
    assert client.get(f"/colectas/{cid_dueno}").status_code == 404  # otro usuario no la ve por id


def test_dejar_de_compartir_apaga_el_enlace():
    cid, _ = _crear()
    token = client.post(f"/colectas/{cid}/compartir").json()["token"]
    assert client.delete(f"/colectas/{cid}/compartir").status_code == 200
    assert client.get(f"/colectas/publico/{token}").status_code == 404


def test_aislamiento_otro_usuario_no_toca_la_colecta():
    cid, _ = _crear()
    ap = client.get(f"/colectas/{cid}").json()["participantes"][0]["aporte_id"]
    _como("col-intruso")
    assert client.get(f"/colectas/{cid}").status_code == 404
    assert client.patch(f"/colectas/{cid}", json={"nombre": "hackeada"}).status_code == 404
    assert client.delete(f"/colectas/{cid}").status_code == 404
    assert client.post(f"/colectas/{cid}/aportes/{ap}/pagos", json={}).status_code == 404
    assert client.post(f"/colectas/{cid}/compartir").status_code == 404
    assert client.get("/colectas").json() == []


def test_borrar_colecta_limpia_aportes_y_pagos_pero_no_toca_ingresos():
    cuenta = _cuenta(0 + 10_000)
    cid, _ = _crear(cuenta_id=cuenta["id"])
    ap = client.get(f"/colectas/{cid}").json()["participantes"][0]["aporte_id"]
    client.post(f"/colectas/{cid}/aportes/{ap}/pagos", json={"registrar_ingreso": True})
    assert client.delete(f"/colectas/{cid}").status_code == 200
    assert client.get(f"/colectas/{cid}").status_code == 404
    assert _saldo(cuenta["id"]) == 60_000


# ───────────── Nivel A: datos para pagar y «ya pagué» desde el enlace ─────────────

def test_datos_para_pagar_se_guardan_se_muestran_en_el_enlace_y_se_pueden_quitar():
    cid, _ = _crear(datos_pago="  Llave Bre-B: @torneo  ")
    assert client.get(f"/colectas/{cid}").json()["datos_pago"] == "Llave Bre-B: @torneo"
    token = client.post(f"/colectas/{cid}/compartir").json()["token"]
    assert client.get(f"/colectas/publico/{token}").json()["datos_pago"] == "Llave Bre-B: @torneo"
    assert client.patch(f"/colectas/{cid}", json={"datos_pago": ""}).status_code == 200
    assert client.get(f"/colectas/{cid}").json()["datos_pago"] == ""
    assert client.get(f"/colectas/publico/{token}").json()["datos_pago"] == ""


def test_ya_pague_desde_el_enlace_deja_una_marca_y_no_toca_lo_recogido():
    cid, _ = _crear()
    token = client.post(f"/colectas/{cid}/compartir").json()["token"]
    pub = client.get(f"/colectas/publico/{token}").json()
    persona = pub["participantes"][0]
    assert persona["avisado"] is False
    app.dependency_overrides.pop(get_current_user, None)  # quien avisa NO tiene sesión
    assert client.post(f"/colectas/publico/{token}/aportes/{persona['id']}/avisar").status_code == 200
    assert next(p for p in client.get(f"/colectas/publico/{token}").json()["participantes"] if p["id"] == persona["id"])["avisado"]
    _como("col-test_ya_pague_desde_el_enlace_deja_una_marca_y_no_toca_lo_recogido")
    d = client.get(f"/colectas/{cid}").json()
    assert d["recogido"] == 0  # lo recogido NO cambió con el aviso
    assert d["avisaron"] == 1 and sum(1 for p in d["participantes"] if p["avisado"]) == 1


def test_confirmar_el_pago_limpia_el_aviso_y_el_organizador_puede_descartarlo():
    cid, _ = _crear()
    token = client.post(f"/colectas/{cid}/compartir").json()["token"]
    ids = [p["id"] for p in client.get(f"/colectas/publico/{token}").json()["participantes"]]
    for i in ids[:2]:
        client.post(f"/colectas/publico/{token}/aportes/{i}/avisar")
    d = client.get(f"/colectas/{cid}").json()
    avisados = [p for p in d["participantes"] if p["avisado"]]
    assert len(avisados) == 2
    client.post(f"/colectas/{cid}/aportes/{avisados[0]['aporte_id']}/pagos", json={})  # confirma
    assert client.delete(f"/colectas/{cid}/aportes/{avisados[1]['aporte_id']}/aviso").status_code == 200  # descarta
    d = client.get(f"/colectas/{cid}").json()
    assert d["avisaron"] == 0 and d["recogido"] == 50_000


def test_aviso_publico_rechaza_tokens_malos_aportes_ajenos_y_vacas_cerradas():
    cid, _ = _crear()
    otro, _ = _crear(nombre="Otra")
    token = client.post(f"/colectas/{cid}/compartir").json()["token"]
    ap_otro = client.get(f"/colectas/{otro}").json()["participantes"][0]["aporte_id"]
    ap = client.get(f"/colectas/{cid}").json()["participantes"][0]["aporte_id"]
    assert client.post(f"/colectas/publico/corto/aportes/{ap}/avisar").status_code == 404
    assert client.post(f"/colectas/publico/{'x' * 30}/aportes/{ap}/avisar").status_code == 404
    assert client.post(f"/colectas/publico/{token}/aportes/{ap_otro}/avisar").status_code == 404  # aporte de otra vaca
    client.patch(f"/colectas/{cid}", json={"estado": "cerrada"})
    assert client.post(f"/colectas/publico/{token}/aportes/{ap}/avisar").status_code == 404


def test_otro_usuario_no_puede_descartar_el_aviso_de_mi_vaca():
    cid, _ = _crear()
    ap = client.get(f"/colectas/{cid}").json()["participantes"][0]["aporte_id"]
    _como("col-intruso-aviso")
    assert client.delete(f"/colectas/{cid}/aportes/{ap}/aviso").status_code == 404
