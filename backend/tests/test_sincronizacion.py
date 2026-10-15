"""Pantalla 'Sincronización': cuenta por remitente, estado de la grilla y cola por categorizar.

Los números de la grilla están calculados a mano en el escenario de cada prueba."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'sincro.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.extractos_gmail import banco_por_remitente, inferir_cuenta_por_remitente  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, ExtractoCorreo, HistorialExtracto, Movimiento, ReglaCategoria  # noqa: E402
from app.routers.sincronizacion import estado_celda, mes_del_extracto, ultimos_meses  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="s-0", email="s@test.com", nombre="S")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def _usuario(uid, nombres):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)
    return {n: client.post("/cuentas", json={"nombre": n, "saldo": 0}).json()["id"] for n in nombres}


class C:  # cuenta simulada para las pruebas puras
    def __init__(self, id, nombre):
        self.id, self.nombre = id, nombre


# ── 1) Cuenta por remitente (puro) ──────────────────────────────────

def test_banco_por_remitente_reconoce_subdominios_y_remitentes_reales():
    assert banco_por_remitente("Nequi <no-reply@mail.nequi.com.co>") == "Nequi"
    assert banco_por_remitente("Nu <info@nu.com.co>") == "Nu Colombia"
    assert banco_por_remitente("Bancolombia <alertasynotificaciones@notificacionesbancolombia.com.co>") == "Bancolombia"
    assert banco_por_remitente("Daviplata <x@daviplata.com>") == "Daviplata"
    assert banco_por_remitente("alguien@gmail.com") is None


def test_inferir_cuenta_nequi_sin_cuenta_nequi_no_cae_en_otra():
    # El bug real: un correo de Nequi terminaba en 'Nu Colombia' (la primera cuenta).
    cuentas = [C("nu", "Nu Colombia"), C("ef", "Efectivo")]
    banco, sug, falta = inferir_cuenta_por_remitente("Nequi <no-reply@mail.nequi.com.co>", cuentas)
    assert (banco, sug, falta) == ("Nequi", None, True)


def test_inferir_cuenta_con_cuenta_del_banco():
    cuentas = [C("nu", "Nu Colombia"), C("nq", "Nequi")]
    assert inferir_cuenta_por_remitente("Nequi <a@nequi.com.co>", cuentas) == ("Nequi", "nq", False)
    assert inferir_cuenta_por_remitente("Nu <a@nu.com.co>", cuentas) == ("Nu Colombia", "nu", False)
    # El usuario la llamó solo "Nu": el alias corto la encuentra, sin confundirla con "menú".
    assert inferir_cuenta_por_remitente("Nu <a@nu.com.co>", [C("x", "Menú"), C("n", "Nu")]) == ("Nu Colombia", "n", False)


def test_inferir_cuenta_bancolombia_ambigua_y_desconocido():
    dos = [C("a", "Bancolombia Ahorros"), C("b", "Bancolombia Crédito")]
    # Hay cuentas del banco pero no un ganador claro: no se adivina, tampoco falta cuenta.
    assert inferir_cuenta_por_remitente("B <x@notificacionesbancolombia.com.co>", dos) == ("Bancolombia", None, False)
    una = [C("a", "Bancolombia Ahorros"), C("e", "Efectivo")]
    assert inferir_cuenta_por_remitente("B <x@bancolombia.com.co>", una) == ("Bancolombia", "a", False)
    # Remitente desconocido: no se asume la primera cuenta, se exige elegir.
    assert inferir_cuenta_por_remitente("Tienda <promo@tienda.co>", una) == (None, None, False)


# ── 1b) Pendientes y aprobar por la API ─────────────────────────────

def _correo(uid, remitente, monto=500.0, estado="pendiente", n=[0]):
    n[0] += 1
    db = SessionLocal()
    try:
        c = CorreoGasto(
            usuario_id=uid, gmail_msg_id=f"m{n[0]}", remitente=remitente, asunto="¡Enviaste plata por Bre-B!",
            monto=monto, comercio="Bre-B", categoria_sugerida="Otros", tipo_sugerido="expense", estado=estado,
            recibido_en=ahora_co(),
        )
        db.add(c)
        db.commit()
        return c.id
    finally:
        db.close()


def test_pendientes_traen_cuenta_sugerida_y_falta_cuenta():
    ids = _usuario("s-pend", ["Nu Colombia", "Bancolombia Ahorros"])
    _correo("s-pend", "Nequi <no-reply@mail.nequi.com.co>")
    _correo("s-pend", "Bancolombia <a@notificacionesbancolombia.com.co>")
    _correo("s-pend", "Tienda <promo@tienda.co>")
    por_banco = {p["banco_detectado"]: p for p in client.get("/correos/pendientes").json()}
    assert por_banco["Nequi"]["falta_cuenta"] is True and por_banco["Nequi"]["cuenta_sugerida_id"] is None
    assert por_banco["Bancolombia"]["cuenta_sugerida_id"] == ids["Bancolombia Ahorros"]
    assert por_banco["Bancolombia"]["falta_cuenta"] is False
    assert por_banco[None]["cuenta_sugerida_id"] is None and por_banco[None]["falta_cuenta"] is False


def test_aprobar_sin_cuenta_valida_responde_400_claro():
    ids = _usuario("s-apr", ["Nu Colombia"])
    nequi = _correo("s-apr", "Nequi <no-reply@mail.nequi.com.co>")
    r = client.post(f"/correos/{nequi}/aprobar", json={})
    assert r.status_code == 400 and r.json()["detail"] == "No tienes una cuenta Nequi: créala o elige otra"
    # Una cuenta que no existe tampoco vale.
    assert client.post(f"/correos/{nequi}/aprobar", json={"cuenta_id": "no-existe"}).status_code == 400
    # Remitente desconocido sin cuenta elegida: hay que elegir.
    raro = _correo("s-apr", "Tienda <promo@tienda.co>")
    r = client.post(f"/correos/{raro}/aprobar", json={})
    assert r.status_code == 400 and "Elige la cuenta" in r.json()["detail"]
    # Ningún intento creó movimientos ni tocó el saldo.
    assert client.get("/cuentas").json()[0]["saldo"] == 0
    # Si el usuario elige a conciencia otra cuenta, se respeta.
    ok = client.post(f"/correos/{nequi}/aprobar", json={"cuenta_id": ids["Nu Colombia"]})
    assert ok.status_code == 200 and ok.json()["estado"] == "aprobado"
    assert client.get("/cuentas").json()[0]["saldo"] == -500


# ── 2) Estado de la grilla (números a mano) ─────────────────────────

def test_mes_del_extracto():
    assert mes_del_extracto("01/09/2026 a 30/09/2026", None) == "2026-09"
    assert mes_del_extracto("15/05/2026 a 14/06/2026", None) == "2026-06"  # manda el corte
    assert mes_del_extracto("2026-03-01 a 2026-03-31", None) == "2026-03"
    assert mes_del_extracto("junio 2026", None) == "2026-06"
    assert mes_del_extracto("Septiembre de 2026", None) == "2026-09"
    assert mes_del_extracto("", datetime(2026, 1, 10)) == "2025-12"  # llegó en enero: es de diciembre
    assert mes_del_extracto("", None) is None


def test_ultimos_meses_cruza_el_anio():
    assert ultimos_meses(datetime(2026, 2, 15), 4) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]


def test_estado_celda_prioridades():
    f = dict(movimientos=0, conciliados=0, extractos_procesados=0, extractos_nuevos=0, extractos_falta_clave=0)
    assert estado_celda(**f) == "vacio"
    assert estado_celda(**{**f, "movimientos": 3}) == "sin_extracto"
    assert estado_celda(**{**f, "movimientos": 3, "conciliados": 1}) == "conciliado"
    assert estado_celda(**{**f, "movimientos": 3, "conciliados": 1, "extractos_nuevos": 1}) == "extracto_pendiente"
    assert estado_celda(**{**f, "extractos_nuevos": 1, "extractos_falta_clave": 1}) == "falta_clave"
    assert estado_celda(**{**f, "extractos_procesados": 1, "extractos_nuevos": 1}) == "conciliado"


def _mov(uid, cuenta_id, fecha, categoria="Comida", conf=True, conciliado=False, fuente="manual", desc="Compra"):
    return Movimiento(
        usuario_id=uid, cuenta_id=cuenta_id, fecha=fecha, descripcion=desc, categoria=categoria, tipo="expense",
        monto=1000, fuente=fuente, cat_confirmada=conf, cat_origen=None if conf else "regla",
        conciliado_en=fecha if conciliado else None,
    )


def _ext(uid, n, estado, periodo, cuenta_id=None, banco="", historial_id=None, remitente="x@banco.co"):
    return ExtractoCorreo(
        usuario_id=uid, gmail_msg_id=f"e{n}", archivo=f"e{n}.pdf", remitente=remitente, banco=banco,
        periodo=periodo, estado=estado, cuenta_sugerida_id=cuenta_id, historial_id=historial_id,
        recibido_en=ahora_co(),
    )


NOMBRES_MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def test_estado_grilla_y_tareas_con_numeros_a_mano():
    uid = "s-grilla"
    ids = _usuario(uid, ["Nequi", "Bancolombia Ahorros"])
    banc, nq = ids["Bancolombia Ahorros"], ids["Nequi"]
    ahora = ahora_co()
    (a0, m0), (a1, m1), (a2, m2), (a3, m3), (a4, m4), (a5, m5) = ultimos_meses(ahora)
    dia = lambda a, m, d=2: datetime(a, m, d, 12)  # noqa: E731

    db = SessionLocal()
    try:
        # Bancolombia, mes actual (m5): 3 movs, ninguno conciliado, 1 por confirmar. Dos esperan categoría:
        # 'Otros' y uno puesto por una regla sin confirmar. => sin_extracto
        db.add_all([
            _mov(uid, banc, dia(a5, m5, 1), "Comida"),
            _mov(uid, banc, dia(a5, m5, 1), "Otros", desc="Tienda rara"),
            _mov(uid, banc, dia(a5, m5, 1), "Transporte", conf=False, desc="Uber trip"),
        ])
        # Nequi, mes actual: 1 movimiento de Wallet sin confirmar, reciente => bandeja, NO cola de categorizar.
        db.add(_mov(uid, nq, ahora - timedelta(hours=1), "Comida", conf=False, fuente="wallet", desc="Rappi"))
        # Bancolombia m4: 2 movs, ambos conciliados => conciliado
        db.add_all([_mov(uid, banc, dia(a4, m4), conciliado=True), _mov(uid, banc, dia(a4, m4, 3), conciliado=True)])
        # m3: extracto nuevo por rango de fechas => extracto_pendiente
        db.add(_ext(uid, 1, "nuevo", f"01/{m3:02d}/{a3} a 28/{m3:02d}/{a3}", cuenta_id=banc, banco="Bancolombia"))
        # m2: extracto con clave pendiente, periodo en palabras => falta_clave
        db.add(_ext(uid, 2, "falta_clave", f"{NOMBRES_MES[m2 - 1]} {a2}", cuenta_id=banc, banco="Bancolombia"))
        # m1: extracto procesado: la cuenta sale del historial => conciliado
        h = HistorialExtracto(usuario_id=uid, cuenta_id=banc, estado="conciliado")
        db.add(h)
        db.flush()
        db.add(_ext(uid, 3, "procesado", f"{a1}-{m1:02d}-01 a {a1}-{m1:02d}-28", historial_id=h.id, banco="Bancolombia"))
        # Un extracto de Davivienda sin cuenta Davivienda: no entra a la grilla, pide crear cuenta.
        db.add(_ext(uid, 4, "nuevo", f"{NOMBRES_MES[m5 - 1]} {a5}", banco="Davivienda"))
        # Correos pendientes: 2 de Daviplata (sin cuenta), 1 de Nequi (con cuenta), 1 sin monto (no cuenta).
        db.commit()
    finally:
        db.close()
    _correo(uid, "Daviplata <a@daviplata.com>")
    _correo(uid, "Daviplata <b@daviplata.com>")
    _correo(uid, "Nequi <a@nequi.com.co>")
    _correo(uid, "Nequi <a@nequi.com.co>", monto=0)

    r = client.get("/sincronizacion/estado")
    assert r.status_code == 200, r.text
    d = r.json()
    assert [m["clave"] for m in d["meses"]] == [f"{a:04d}-{m:02d}" for a, m in ultimos_meses(ahora)]
    por_cuenta = {c["nombre"]: [x for x in c["meses"]] for c in d["cuentas"]}
    banco = por_cuenta["Bancolombia Ahorros"]
    assert [c["estado"] for c in banco] == ["vacio", "conciliado", "falta_clave", "extracto_pendiente", "conciliado", "sin_extracto"]
    assert (banco[5]["movimientos"], banco[5]["conciliados"], banco[5]["por_confirmar"]) == (3, 0, 1)
    assert (banco[4]["movimientos"], banco[4]["conciliados"], banco[4]["por_confirmar"]) == (2, 2, 0)
    assert banco[3]["extractos"] == 1 and banco[3]["movimientos"] == 0
    nequi = por_cuenta["Nequi"]
    assert [c["estado"] for c in nequi] == ["vacio"] * 5 + ["sin_extracto"]
    assert (nequi[5]["movimientos"], nequi[5]["por_confirmar"]) == (1, 1)

    # Sin cuenta: Daviplata (2 correos) y Davivienda (1 extracto); Nequi sí tiene cuenta.
    assert d["sin_cuenta"] == [
        {"banco": "Daviplata", "correos": 2, "extractos": 0},
        {"banco": "Davivienda", "correos": 0, "extractos": 1},
    ]
    # Tareas, en orden y solo con cantidad > 0:
    #   falta_clave 1 | por conciliar 2 (m3 + Davivienda) | sin_cuenta 2 bancos |
    #   categorizar 0 (un solo «Otros»: no llega a 4 repeticiones) | confirmar 1 (Wallet) | correos 3 (2 Daviplata + 1 Nequi)
    assert [(t["id"], t["cantidad"]) for t in d["tareas"]] == [
        ("falta_clave", 1),
        ("extractos_por_conciliar", 2),
        ("sin_cuenta", 2),
        ("movimientos_por_confirmar", 1),
        ("correos_por_revisar", 3),
    ]
    assert all(t["titulo"] and t["detalle"] and t["ruta"].startswith("/") for t in d["tareas"])


def test_estado_sin_datos_no_tiene_tareas():
    _usuario("s-vacio", ["Efectivo"])
    d = client.get("/sincronizacion/estado").json()
    assert d["tareas"] == [] and d["sin_cuenta"] == [] and d["ultima_sync"] is None
    assert all(c["estado"] == "vacio" for c in d["cuentas"][0]["meses"])


def test_estado_no_mezcla_datos_de_otros_usuarios():
    _usuario("s-a", ["Nequi"])
    _correo("s-a", "Daviplata <a@daviplata.com>")
    _usuario("s-b", ["Nequi"])
    assert client.get("/sincronizacion/estado").json()["tareas"] == []


# ── 3) Cola por categorizar ─────────────────────────────────────────

def test_por_categorizar_pagina_y_aprende_la_regla_del_comercio():
    uid = "s-cola"
    ids = _usuario(uid, ["Nequi"])
    cuenta = ids["Nequi"]
    ahora = ahora_co()
    db = SessionLocal()
    try:
        for i in range(4):  # 4 repeticiones del comercio: ya se pregunta
            db.add(_mov(uid, cuenta, ahora - timedelta(days=20 + i), "Otros", desc=f"PANADERIA LA 80 {i}"))
        db.add(_mov(uid, cuenta, ahora - timedelta(days=20), "Comida"))  # confirmado: no entra
        db.add(_mov(uid, cuenta, ahora - timedelta(days=21), "Transporte", conf=False, desc="Uber"))  # auto sin confirmar
        db.add(_mov(uid, cuenta, ahora - timedelta(hours=2), "Otros", conf=False, fuente="wallet", desc="Wallet"))  # bandeja
        db.commit()
    finally:
        db.close()

    p1 = client.get("/sincronizacion/por-categorizar?limite=2").json()
    # Solo las 4 de «Otros» (se repiten 4 veces): el Uber (regla) ya está categorizado con confianza alta.
    assert p1["total"] == 4 and len(p1["items"]) == 2 and p1["offset"] == 0
    p2 = client.get("/sincronizacion/por-categorizar?limite=2&offset=2").json()
    assert len(p2["items"]) == 2
    todos = {m["id"]: m for m in p1["items"] + p2["items"]}
    assert len(todos) == 4 and "Wallet" not in {m["descripcion"] for m in todos.values()}
    assert all(m["patron"] for m in todos.values())

    # Responder con 'recordar para este comercio' reutiliza el endpoint existente:
    # crea la regla y recategoriza a los demás del comercio.
    panaderia = next(m for m in todos.values() if m["descripcion"].startswith("PANADERIA"))
    r = client.post(f"/movimientos/{panaderia['id']}/recategorizar-comercio", json={
        "categoria": "Comida", "aplicar_a_todos": True, "patron": "PANADERIA LA 80",
    })
    assert r.status_code == 200 and r.json()["actualizados"] == 4
    db = SessionLocal()
    try:
        regla = db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == uid).one()
        # La regla se guarda con la huella del comercio (minúsculas, sin números ni artículos), no con el texto literal.
        assert (regla.patron, regla.categoria) == ("panaderia", "Comida")
    finally:
        db.close()
    # La cola bajó de 4 a 0.
    despues = client.get("/sincronizacion/por-categorizar").json()
    assert despues["total"] == 0
    assert not [t for t in client.get("/sincronizacion/estado").json()["tareas"] if t["id"] == "movimientos_por_categorizar"]


def test_lista_de_extractos_trae_banco_del_remitente_y_movimientos_cruzados():
    uid = "s-ext"
    _usuario(uid, ["Nequi"])
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=uid, cuenta_id="x", estado="conciliado", exactos=5, aproximados=2)
        db.add(h)
        db.flush()
        # Sin banco guardado: se deduce del remitente (antes salía 'Extracto · junio 2026' sin banco).
        db.add(_ext(uid, 10, "procesado", "junio 2026", historial_id=h.id, banco="", remitente="Nequi <a@mail.nequi.com.co>"))
        db.add(_ext(uid, 11, "descartado", "mayo 2026", banco="Nu Colombia"))
        db.commit()
    finally:
        db.close()
    visibles = client.get("/correos/extractos").json()
    assert [(e["banco"], e["cruzados"]) for e in visibles] == [("Nequi", 7)]
    ignorados = client.get("/correos/extractos?estado=descartado").json()
    assert [(e["banco"], e["cruzados"]) for e in ignorados] == [("Nu Colombia", None)]
