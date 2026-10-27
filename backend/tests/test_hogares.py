"""Hogares: libro común entre personas con cuenta. Lo que más importa aquí es el AISLAMIENTO: quien no es miembro
activo no ve ni toca nada, y borrar una cuenta no se lleva lo que los demás ya usan."""
import os
import tempfile
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'hogares.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import derechos_titular as dt  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.limites import _eventos  # noqa: E402
from app.main import app  # noqa: E402
from app.models_hogares import GastoHogar, Hogar, MiembroHogar, ParteGastoHogar  # noqa: E402

client = TestClient(app)


@pytest.fixture
def gente():
    """Tres personas con ids únicos por prueba: ana (admin), beto (miembro) y un extraño."""
    s = uuid.uuid4().hex[:8]
    _eventos.clear()
    return {n: UsuarioActual(id=f"{n}-{s}", email=f"{n}-{s}@test.com", nombre=n.capitalize()) for n in ("ana", "beto", "extra")}


def como(u):
    app.dependency_overrides[get_current_user] = lambda: u


def _hogar_de_a_y_b(gente):
    """Ana crea «Casa», invita a Beto por enlace y él acepta. Devuelve (hogar_id, miembro_ana, miembro_beto)."""
    como(gente["ana"])
    hid = client.post("/hogares", json={"nombre": "Casa"}).json()["id"]
    token = client.post(f"/hogares/{hid}/invitar", json={}).json()["token"]
    como(gente["beto"])
    assert client.post(f"/hogares/invitaciones/{token}/aceptar", json={}).status_code == 200
    d = client.get(f"/hogares/{hid}").json()
    ana = next(m for m in d["miembros"] if m["rol"] == "admin")["id"]
    beto = next(m for m in d["miembros"] if m["soy_yo"])["id"]
    return hid, ana, beto


def test_crear_hogar_deja_al_creador_como_admin(gente):
    como(gente["ana"])
    hid = client.post("/hogares", json={"nombre": "Casa", "apodo": "Ani"}).json()["id"]
    d = client.get(f"/hogares/{hid}").json()
    assert d["rol"] == "admin" and [m["apodo"] for m in d["miembros"]] == ["Ani"]
    assert [h["nombre"] for h in client.get("/hogares").json()] == ["Casa"]


def test_invitacion_por_enlace_es_de_un_solo_uso(gente):
    como(gente["ana"])
    hid = client.post("/hogares", json={"nombre": "Casa"}).json()["id"]
    token = client.post(f"/hogares/{hid}/invitar", json={}).json()["token"]
    como(gente["beto"])
    assert client.get(f"/hogares/invitaciones/{token}").json()["hogar"] == "Casa"
    assert client.post(f"/hogares/invitaciones/{token}/aceptar", json={"apodo": "Betico"}).status_code == 200
    como(gente["extra"])
    assert client.post(f"/hogares/invitaciones/{token}/aceptar", json={}).status_code == 404  # ya se usó


def test_invitacion_con_correo_solo_la_acepta_esa_cuenta(gente):
    como(gente["ana"])
    hid = client.post("/hogares", json={"nombre": "Casa"}).json()["id"]
    token = client.post(f"/hogares/{hid}/invitar", json={"email": gente["beto"].email.upper()}).json()["token"]
    como(gente["extra"])
    assert client.post(f"/hogares/invitaciones/{token}/aceptar", json={}).status_code == 404
    como(gente["beto"])
    assert [i["hogar"] for i in client.get("/hogares/invitaciones/mias").json()] == ["Casa"]
    assert client.post(f"/hogares/invitaciones/{token}/aceptar", json={}).status_code == 200


def test_token_invalido_o_corto_da_404(gente):
    como(gente["beto"])
    assert client.get("/hogares/invitaciones/corto").status_code == 404
    assert client.post("/hogares/invitaciones/" + "x" * 30 + "/aceptar", json={}).status_code == 404


def test_solo_admin_invita(gente):
    hid, _, _ = _hogar_de_a_y_b(gente)
    como(gente["beto"])
    assert client.post(f"/hogares/{hid}/invitar", json={}).status_code == 403


def test_gasto_iguales_y_saldos_cuadran(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["ana"])
    r = client.post(f"/hogares/{hid}/gastos", json={
        "descripcion": "Mercado", "total": 100_000, "modo": "iguales", "participantes": [{"id": ana}, {"id": beto}],
        "categoria": "Comida"})
    assert r.status_code == 200 and r.json()["partes"] == {ana: 50_000, beto: 50_000}
    d = client.get(f"/hogares/{hid}").json()
    saldos = {m["id"]: m["saldo"] for m in d["miembros"]}
    assert saldos == {ana: 50_000, beto: -50_000}
    assert d["simplificado"] == [{"de": beto, "a": ana, "monto": 50_000, "de_nombre": "Beto", "a_nombre": "Ana"}]
    # el pago de Beto salda la deuda
    como(gente["beto"])
    assert client.post(f"/hogares/{hid}/pagos", json={"de_id": beto, "a_id": ana, "monto": 50_000}).status_code == 200
    assert all(m["saldo"] == 0 for m in client.get(f"/hogares/{hid}").json()["miembros"])


def test_gasto_con_pagador_distinto_y_partes_desiguales(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["beto"])
    r = client.post(f"/hogares/{hid}/gastos", json={
        "descripcion": "Arriendo", "total": 900_000, "modo": "porcentajes", "pagador_id": beto,
        "participantes": [{"id": ana, "valor": 60}, {"id": beto, "valor": 40}]})
    assert r.json()["partes"] == {ana: 540_000, beto: 360_000}
    saldos = {m["id"]: m["saldo"] for m in client.get(f"/hogares/{hid}").json()["miembros"]}
    assert saldos == {ana: -540_000, beto: 540_000}


def test_division_invalida_y_participantes_ajenos_se_rechazan(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["ana"])
    mal = client.post(f"/hogares/{hid}/gastos", json={
        "descripcion": "x", "total": 100, "modo": "porcentajes", "participantes": [{"id": ana, "valor": 50}, {"id": beto, "valor": 40}]})
    assert mal.status_code == 400
    otro = client.post(f"/hogares/{hid}/gastos", json={"descripcion": "x", "total": 100, "participantes": [{"id": "no-es-miembro"}]})
    assert otro.status_code == 400


def test_registrar_en_mi_cuenta_copia_solo_mi_parte(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["beto"])
    cuenta = client.post("/cuentas", json={"nombre": "Mi cuenta", "saldo": 200_000, "moneda": "COP"}).json()
    r = client.post(f"/hogares/{hid}/gastos", json={
        "descripcion": "Internet", "total": 100_000, "participantes": [{"id": ana}, {"id": beto}],
        "registrar_en_mi_cuenta": True, "cuenta_id": cuenta["id"]})
    assert r.status_code == 200
    assert next(c["saldo"] for c in client.get("/cuentas").json() if c["id"] == cuenta["id"]) == 150_000  # solo su parte
    como(gente["ana"])
    assert client.get("/cuentas").json() == []  # Ana no ve la cuenta de Beto ni su movimiento


def test_borrar_gasto_solo_autor_o_admin(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["beto"])
    gid = client.post(f"/hogares/{hid}/gastos", json={"descripcion": "x", "total": 10, "participantes": [{"id": beto}]}).json()["id"]
    como(gente["ana"])  # admin puede
    assert client.delete(f"/hogares/{hid}/gastos/{gid}").status_code == 200
    como(gente["ana"])
    gid2 = client.post(f"/hogares/{hid}/gastos", json={"descripcion": "y", "total": 10, "participantes": [{"id": ana}]}).json()["id"]
    como(gente["beto"])  # otro miembro no
    assert client.delete(f"/hogares/{hid}/gastos/{gid2}").status_code == 403


def test_pago_solo_donde_participas_salvo_admin(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["ana"])
    token = client.post(f"/hogares/{hid}/invitar", json={}).json()["token"]
    como(gente["extra"])
    client.post(f"/hogares/invitaciones/{token}/aceptar", json={})
    extra = next(m for m in client.get(f"/hogares/{hid}").json()["miembros"] if m["soy_yo"])["id"]
    como(gente["beto"])
    assert client.post(f"/hogares/{hid}/pagos", json={"de_id": ana, "a_id": extra, "monto": 10}).status_code == 403
    como(gente["ana"])
    assert client.post(f"/hogares/{hid}/pagos", json={"de_id": beto, "a_id": extra, "monto": 10}).status_code == 200


def test_resumen_del_mes_por_miembro_y_categoria(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["ana"])
    client.post(f"/hogares/{hid}/gastos", json={"descripcion": "a", "total": 100_000, "categoria": "Comida",
                                               "participantes": [{"id": ana}, {"id": beto}]})
    client.post(f"/hogares/{hid}/gastos", json={"descripcion": "b", "total": 40_000, "categoria": "Hogar", "pagador_id": beto,
                                               "participantes": [{"id": ana}, {"id": beto}]})
    r = client.get(f"/hogares/{hid}/resumen").json()
    assert r["total"] == 140_000
    por = {x["nombre"]: x for x in r["por_miembro"]}
    assert por["Ana"]["puso"] == 100_000 and por["Beto"]["puso"] == 40_000 and por["Ana"]["consumio"] == 70_000
    assert [c["categoria"] for c in r["por_categoria"]] == ["Comida", "Hogar"]
    assert client.get(f"/hogares/{hid}/resumen?mes=basura").status_code == 400


# ───────────── AISLAMIENTO: la parte que no se negocia ─────────────

def test_un_extrano_recibe_404_en_todas_las_rutas_del_hogar(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["ana"])
    gid = client.post(f"/hogares/{hid}/gastos", json={"descripcion": "x", "total": 10, "participantes": [{"id": ana}]}).json()["id"]
    pid = client.post(f"/hogares/{hid}/pagos", json={"de_id": beto, "a_id": ana, "monto": 1}).json()["id"]
    inv = client.post(f"/hogares/{hid}/invitar", json={}).json()["id"]
    como(gente["extra"])
    casos = [
        ("GET", f"/hogares/{hid}", None), ("PATCH", f"/hogares/{hid}", {"nombre": "hack"}), ("DELETE", f"/hogares/{hid}", None),
        ("PATCH", f"/hogares/{hid}/yo", {"apodo": "x"}), ("POST", f"/hogares/{hid}/invitar", {}),
        ("DELETE", f"/hogares/{hid}/invitaciones/{inv}", None), ("PATCH", f"/hogares/{hid}/miembros/{ana}", {"rol": "miembro"}),
        ("DELETE", f"/hogares/{hid}/miembros/{ana}", None), ("GET", f"/hogares/{hid}/gastos", None),
        ("POST", f"/hogares/{hid}/gastos", {"descripcion": "x", "total": 10, "participantes": [{"id": ana}]}),
        ("DELETE", f"/hogares/{hid}/gastos/{gid}", None), ("GET", f"/hogares/{hid}/pagos", None),
        ("POST", f"/hogares/{hid}/pagos", {"de_id": beto, "a_id": ana, "monto": 1}), ("DELETE", f"/hogares/{hid}/pagos/{pid}", None),
        ("GET", f"/hogares/{hid}/resumen", None),
    ]
    for metodo, ruta, cuerpo in casos:
        r = client.request(metodo, ruta, json=cuerpo)
        assert r.status_code == 404, f"{metodo} {ruta} -> {r.status_code}"
    assert client.get("/hogares").json() == []


def test_quien_sale_pierde_el_acceso_pero_sus_aportes_se_conservan(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["beto"])
    client.post(f"/hogares/{hid}/gastos", json={"descripcion": "Mercado", "total": 100_000, "participantes": [{"id": ana}, {"id": beto}]})
    assert client.delete(f"/hogares/{hid}/miembros/{beto}").status_code == 200
    assert client.get(f"/hogares/{hid}").status_code == 404  # ya no ve nada
    como(gente["ana"])
    d = client.get(f"/hogares/{hid}").json()
    assert {m["id"]: m["saldo"] for m in d["miembros"]}[ana] == -50_000  # Ana sigue debiendo lo mismo
    assert [g["descripcion"] for g in client.get(f"/hogares/{hid}/gastos").json()] == ["Mercado"]


def test_admin_saca_a_un_miembro_y_no_puede_irse_sin_relevo(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["ana"])
    assert client.delete(f"/hogares/{hid}/miembros/{ana}").status_code == 400  # única administración
    assert client.patch(f"/hogares/{hid}/miembros/{beto}", json={"rol": "admin"}).status_code == 200
    assert client.delete(f"/hogares/{hid}/miembros/{beto}").status_code == 200
    como(gente["beto"])
    assert client.get(f"/hogares/{hid}").status_code == 404


def test_el_ultimo_que_sale_borra_el_hogar(gente):
    como(gente["ana"])
    hid = client.post("/hogares", json={"nombre": "Solo"}).json()["id"]
    me = client.get(f"/hogares/{hid}").json()["mi_miembro_id"]
    assert client.delete(f"/hogares/{hid}/miembros/{me}").json()["hogar_borrado"] is True
    db = SessionLocal()
    try:
        assert db.query(Hogar).filter(Hogar.id == hid).count() == 0
    finally:
        db.close()


def test_borrar_hogar_es_solo_de_admin_y_limpia_todo(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["ana"])
    client.post(f"/hogares/{hid}/gastos", json={"descripcion": "x", "total": 10, "participantes": [{"id": ana}, {"id": beto}]})
    como(gente["beto"])
    assert client.delete(f"/hogares/{hid}").status_code == 403
    como(gente["ana"])
    assert client.delete(f"/hogares/{hid}").status_code == 200
    db = SessionLocal()
    try:
        assert db.query(GastoHogar).filter(GastoHogar.hogar_id == hid).count() == 0
        assert db.query(MiembroHogar).filter(MiembroHogar.hogar_id == hid).count() == 0
    finally:
        db.close()


def test_el_detalle_no_filtra_cuentas_ni_correos(gente):
    hid, _, _ = _hogar_de_a_y_b(gente)
    como(gente["beto"])
    cuenta = client.post("/cuentas", json={"nombre": "SecretaDeBeto", "saldo": 777, "moneda": "COP"}).json()
    como(gente["ana"])
    texto = client.get(f"/hogares/{hid}").text + client.get(f"/hogares/{hid}/gastos").text
    for privado in ("SecretaDeBeto", cuenta["id"], gente["beto"].email, gente["beto"].id, gente["ana"].id):
        assert privado not in texto


# ───────────── Borrar mi cuenta (Ley 1581) ─────────────

def test_borrar_cuenta_deja_ex_miembro_y_no_cambia_los_saldos_de_los_demas(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["beto"])
    client.post(f"/hogares/{hid}/gastos", json={"descripcion": "Mercado", "total": 100_000, "participantes": [{"id": ana}, {"id": beto}]})
    db = SessionLocal()
    try:
        dt.borrar_todo(db, gente["beto"].id, gente["beto"].email)
        fila = db.query(MiembroHogar).filter(MiembroHogar.id == beto).first()
        assert fila.usuario_id is None and fila.apodo == "Ex miembro" and not fila.activo
        assert db.query(ParteGastoHogar).filter(ParteGastoHogar.miembro_id == beto).count() == 1  # el libro se conserva
    finally:
        db.close()
    como(gente["ana"])
    d = client.get(f"/hogares/{hid}").json()
    assert {m["id"]: m["saldo"] for m in d["miembros"]}[ana] == -50_000
    assert "Ex miembro" in [m["apodo"] for m in d["miembros"]]
    assert gente["beto"].email not in client.get(f"/hogares/{hid}").text


def test_borrar_cuenta_del_unico_miembro_borra_el_hogar_y_del_admin_pasa_la_administracion(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    db = SessionLocal()
    try:
        dt.borrar_todo(db, gente["ana"].id, gente["ana"].email)  # Ana era la admin: Beto hereda
        assert db.query(MiembroHogar).filter(MiembroHogar.id == beto).first().rol == "admin"
        dt.borrar_todo(db, gente["beto"].id, gente["beto"].email)  # el último: el hogar desaparece
        assert db.query(Hogar).filter(Hogar.id == hid).count() == 0
    finally:
        db.close()


def test_la_descarga_de_datos_incluye_el_hogar_activo_y_no_el_ajeno(gente):
    hid, ana, beto = _hogar_de_a_y_b(gente)
    como(gente["ana"])
    client.post(f"/hogares/{hid}/gastos", json={"descripcion": "Mercado", "total": 10, "participantes": [{"id": ana}]})
    como(gente["extra"])
    ajeno = client.post("/hogares", json={"nombre": "OtroHogar"}).json()["id"]
    db = SessionLocal()
    try:
        datos_ana = dt.recopilar(db, gente["ana"].id, gente["ana"].email)
        assert [h["nombre"] for h in datos_ana["hogares"]] == ["Casa"]
        assert [g["descripcion"] for g in datos_ana["gastos_hogar"]] == ["Mercado"]
        assert ajeno not in {h["id"] for h in datos_ana["hogares"]}
    finally:
        db.close()
