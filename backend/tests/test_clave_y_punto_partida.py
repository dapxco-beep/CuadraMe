"""
1) Estado confiable de la clave del PDF: «Clave guardada», cuántos extractos abrió, cuáles no,
   y «Probar la clave ahora» (nunca devuelve ni registra la clave).
2) Punto de partida («empezar desde hoy» / «recrear mi histórico»): lo anterior a la fecha de
   inicio se ignora al traer movimientos y se oculta de informes y consejos, sin borrar nada.
Todo con Gmail y PDFs simulados: ninguna prueba llama a Google.
"""
import base64
import os
import tempfile
from datetime import date, datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'clave_pp.db')}")

import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, ExtractoCorreo  # noqa: E402
from app.utiles import ahora_co  # noqa: E402
from test_extractos_gmail import (  # noqa: E402
    CLAVE, TEXTO_EXTRACTO, GmailFalso, adjunto, conectar_usuario, hacer_pdf, mensaje,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    yield


def como(uid: str):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


# ── 1. Clave del PDF ────────────────────────────────────────────────

def _gmail_dos_protegidos():
    mensajes = [
        mensaje("e1", "Bancolombia <extractos@bancolombia.com.co>", "Tu extracto de septiembre",
                partes=[adjunto("Extracto_092026.pdf", "A1")]),
        mensaje("e2", "Davivienda <extractos@davivienda.com>", "Extracto de agosto",
                partes=[adjunto("Extracto_082026.pdf", "A2")]),
    ]
    return GmailFalso(mensajes, {
        "A1": hacer_pdf(TEXTO_EXTRACTO, CLAVE),                       # abre con la clave guardada
        "A2": hacer_pdf(["DAVIVIENDA - Extracto", "Periodo: 01/08/2026 al 31/08/2026"], "OTRA-CLAVE"),
    })


def test_estado_de_la_clave_probar_ahora_y_resultado_explicito(monkeypatch):
    conectar_usuario("u-clave-estado", _gmail_dos_protegidos(), monkeypatch)
    client.post("/cuentas", json={"nombre": "Bancolombia Ahorros", "saldo": 0})
    client.post("/correos/sincronizar")

    # Sin clave: dice que faltan, nada «probado».
    e = client.get("/correos/clave-pdf").json()
    assert e["configurada"] is False and e["protegidos"] == 2 and e["por_probar"] == 2
    assert {b["banco"] for b in e["por_banco"]} == {"Bancolombia", "Davivienda"}
    sin = client.post("/correos/clave-pdf/probar", json={})
    assert sin.json()["ok"] is False and "clave" in sin.json()["mensaje"].lower()

    client.put("/correos/clave-pdf", json={"clave": CLAVE})
    e = client.get("/correos/clave-pdf").json()
    assert e["configurada"] is True and e["cantidad_claves"] == 1 and e["por_probar"] == 2
    assert CLAVE not in client.get("/correos/clave-pdf").text  # nunca se devuelve

    # Probar en todos: uno abre, el otro no (clave distinta).
    r = client.post("/correos/clave-pdf/probar", json={})
    j = r.json()
    assert CLAVE not in r.text
    assert j["ok"] is True and j["abrieron"] == 1 and j["no_abrieron"] == 1 and j["restantes"] == 0
    assert "La clave funcionó en 1 extracto." in j["mensaje"]
    assert "no abrió el extracto" in j["mensaje"] and "revísala" in j["mensaje"]
    por_resultado = {x["resultado"] for x in j["resultados"]}
    assert por_resultado == {"abrio", "no_abrio"}

    e = client.get("/correos/clave-pdf").json()
    assert e["abrieron"] == 1 and e["no_abrieron"] == 1 and e["por_probar"] == 0
    # El extracto abierto quedó listo para conciliar; el otro sigue pidiendo clave, ya marcado como probado.
    ext = {x["archivo"]: x for x in client.get("/correos/extractos").json()}
    assert ext["Extracto_092026.pdf"]["estado"] == "nuevo" and ext["Extracto_092026.pdf"]["clave_estado"] == "abrio"
    assert ext["Extracto_082026.pdf"]["estado"] == "falta_clave" and ext["Extracto_082026.pdf"]["clave_estado"] == "no_abrio"

    # Cambiar la clave vuelve a dejar el fallido «por probar» (el resultado anterior ya no vale).
    client.put("/correos/clave-pdf", json={"clave": "OTRA-CLAVE"})
    ext = {x["archivo"]: x for x in client.get("/correos/extractos").json()}
    assert ext["Extracto_082026.pdf"]["clave_estado"] == "por_probar"
    uno = client.post("/correos/clave-pdf/probar", json={"extracto_id": ext["Extracto_082026.pdf"]["id"]}).json()
    assert uno["abrieron"] == 1 and uno["no_abrieron"] == 0
    assert client.get("/correos/clave-pdf").json()["por_probar"] == 0


def test_probar_clave_exige_gmail_y_extracto_propio(monkeypatch):
    como("u-sin-gmail")
    assert client.post("/correos/clave-pdf/probar", json={}).status_code == 400
    assert client.post("/correos/clave-pdf/probar", json={"extracto_id": "no-existe"}).status_code == 404


# ── 2. Punto de partida ─────────────────────────────────────────────

def _hoy() -> date:
    return ahora_co().date()


def _cuenta(nombre="Banco", saldo=1000, tipo="ahorro"):
    return client.post("/cuentas", json={"nombre": nombre, "saldo": saldo, "tipo": tipo}).json()["id"]


def test_sin_eleccion_todo_sigue_igual():
    como("pp-nada")
    r = client.get("/perfil/punto-de-partida").json()
    assert r["definido"] is False and r["modo"] is None and r["fecha"] is None
    assert r["anteriores"] == {"correos": 0, "extractos": 0}
    assert client.get("/perfil/punto-de-partida/conciliacion").json()["cuentas"] == []


def test_empezar_desde_hoy_guarda_saldos_y_ajusta_con_movimiento_neutral():
    como("pp-hoy")
    c = _cuenta(saldo=1000)
    r = client.put("/perfil/punto-de-partida", json={
        "modo": "hoy", "saldos": {c: {"actual": 2500}}, "ajustar_saldos": True}).json()
    assert r["modo"] == "hoy" and r["fecha"] == _hoy().isoformat()
    assert r["ajustados"] == 1 and r["saldos"][c] == {"inicial": 2500.0, "actual": 2500.0}
    cuentas = {x["id"]: x for x in client.get("/cuentas").json()}
    assert cuentas[c]["saldo"] == 2500
    # El ajuste no es gasto ni ingreso (mismo «Ajuste de saldo» de siempre).
    movs = client.get("/movimientos").json()
    movs = movs["items"] if isinstance(movs, dict) else movs
    assert any(m["categoria"] == "Ajuste de saldo" for m in movs)
    conc = client.get("/perfil/punto-de-partida/conciliacion").json()
    assert conc["cuentas"][0]["coincide"] is True


def test_validaciones_de_fecha_y_cuentas_ajenas():
    como("pp-valida")
    c = _cuenta()
    manana = (_hoy() + timedelta(days=2)).isoformat()
    assert client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": manana}).status_code == 400
    lejos = (_hoy() - timedelta(days=900)).isoformat()
    assert client.put("/perfil/punto-de-partida", json={"modo": "historico", "fecha": lejos}).status_code == 400
    assert client.put("/perfil/punto-de-partida", json={"modo": "historico"}).status_code == 400
    assert client.put("/perfil/punto-de-partida", json={"modo": "hoy", "saldos": {"ajena": {"actual": 1}}}).status_code == 404
    ok = client.put("/perfil/punto-de-partida", json={"modo": "historico", "meses": 6, "saldos": {c: {"inicial": 10}}})
    assert ok.status_code == 200 and ok.json()["modo"] == "historico"


def test_correos_y_extractos_anteriores_no_se_muestran_ni_se_borran():
    como("pp-correos")
    c = _cuenta("Bancolombia Ahorros")
    ahora = ahora_co()
    db = SessionLocal()
    try:
        for i, dias in enumerate((120, 40, 3)):
            db.add(CorreoGasto(
                usuario_id="pp-correos", gmail_msg_id=f"m{i}", remitente="alertas@bancolombia.com.co",
                asunto="Compra", snippet="", monto=1000 + i, comercio=f"Comercio {i}",
                recibido_en=ahora - timedelta(days=dias), estado="pendiente",
            ))
        db.add(ExtractoCorreo(
            usuario_id="pp-correos", gmail_msg_id="x1", archivo="viejo.pdf", remitente="x@bancolombia.com.co",
            banco="Bancolombia", periodo="01/01/2026 a 31/01/2026", estado="nuevo", cuenta_sugerida_id=c,
            recibido_en=ahora - timedelta(days=250),
        ))
        db.add(ExtractoCorreo(
            usuario_id="pp-correos", gmail_msg_id="x2", archivo="nuevo.pdf", remitente="x@bancolombia.com.co",
            banco="Bancolombia", periodo=f"01/{ahora:%m}/{ahora:%Y} a 28/{ahora:%m}/{ahora:%Y}", estado="nuevo",
            cuenta_sugerida_id=c, recibido_en=ahora - timedelta(days=2),
        ))
        db.commit()
    finally:
        db.close()
    assert len(client.get("/correos/pendientes").json()) == 3
    assert len(client.get("/correos/extractos").json()) == 2

    client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": (_hoy() - timedelta(days=10)).isoformat()})
    assert [p["comercio"] for p in client.get("/correos/pendientes").json()] == ["Comercio 2"]
    assert [e["archivo"] for e in client.get("/correos/extractos").json()] == ["nuevo.pdf"]
    pp = client.get("/perfil/punto-de-partida").json()
    assert pp["anteriores"] == {"correos": 2, "extractos": 1}
    est = client.get("/sincronizacion/estado").json()
    assert est["punto_partida"]["anteriores"]["correos"] == 2
    ids = {t["id"]: t["cantidad"] for t in est["tareas"]}
    assert ids.get("correos_por_revisar") == 1

    # Mover el inicio hacia atrás permite ver todo otra vez: no se había borrado nada.
    client.put("/perfil/punto-de-partida", json={"modo": "historico", "meses": 12})
    assert len(client.get("/correos/pendientes").json()) == 3
    assert len(client.get("/correos/extractos").json()) == 2


def test_archivo_ignora_filas_anteriores_a_la_fecha_de_inicio():
    como("pp-archivo")
    c = _cuenta()
    csv = "fecha,descripcion,monto\n2026-01-05,COMPRA VIEJA,-5000\n2026-10-05,COMPRA RECIENTE,-7000\n"
    b64 = base64.b64encode(csv.encode()).decode()
    client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": "2026-09-01"})
    r = client.post("/importar/vista-previa", json={"cuenta_id": c, "nombre_archivo": "e.csv", "archivo_base64": b64})
    assert r.status_code == 200, r.text
    estados = {p["descripcion"]: p["estado"] for p in r.json()["propuesta"]}
    assert estados == {"COMPRA VIEJA": "anterior", "COMPRA RECIENTE": "nuevo"}
    assert r.json()["anteriores"] == 1 and r.json()["resumen"]["nuevos"] == 1

    # Aunque alguien mande la fila vieja al confirmar, no entra.
    filas = [
        {"fecha": "2026-01-05", "descripcion": "COMPRA VIEJA", "monto": 5000, "tipo": "expense"},
        {"fecha": "2026-10-05", "descripcion": "COMPRA RECIENTE", "monto": 7000, "tipo": "expense"},
    ]
    r = client.post("/importar/confirmar", json={"cuenta_id": c, "nombre_archivo": "e.csv", "filas": filas}).json()
    assert r["importados"] == 1 and r["anteriores_omitidas"] == 1


def test_informes_y_consejos_arrancan_en_el_punto_de_partida_sin_borrar():
    como("pp-informes")
    c = _cuenta(saldo=0)
    hoy = ahora_co()
    viejo, reciente = hoy - timedelta(days=100), hoy - timedelta(days=2)
    for fecha, monto in ((viejo, 90000), (reciente, 30000)):
        r = client.post("/movimientos", json={"cuenta_id": c, "tipo": "expense", "monto": monto, "descripcion": "Mercado",
                                              "categoria": "Comida", "fecha": fecha.isoformat()})
        assert r.status_code in (200, 201), r.text
    meses_antes = [m["mes"] for m in client.get("/informes/meses").json()["meses"]]
    assert len(meses_antes) >= 2
    client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": (hoy - timedelta(days=10)).date().isoformat()})
    meses_despues = [m["mes"] for m in client.get("/informes/meses").json()["meses"]]
    assert meses_despues == [f"{reciente:%Y-%m}"]
    # Nada se borró: la lista de movimientos sigue mostrando los dos.
    movs = client.get("/movimientos").json()
    movs = movs["items"] if isinstance(movs, dict) else movs
    assert len(movs) == 2
    assert client.get("/consejos").status_code == 200


def test_modo_historico_muestra_cobertura_y_saldo_reconstruido():
    como("pp-historico")
    c = _cuenta("Banco Ahorros", saldo=1000)
    ef = _cuenta("Efectivo", saldo=0, tipo="efectivo")
    hoy = ahora_co()
    r = client.put("/perfil/punto-de-partida", json={
        "modo": "historico", "meses": 3, "saldos": {c: {"inicial": 1000, "actual": 800}, ef: {"inicial": 0}}}).json()
    assert r["modo"] == "historico"
    cob = client.get("/perfil/punto-de-partida/cobertura").json()
    assert len(cob["meses"]) == 3 and cob["modo"] == "historico"
    nombres = [x["nombre"] for x in cob["cuentas"]]
    assert nombres == ["Banco Ahorros"]  # el efectivo no tiene extractos que pedir
    assert cob["cuentas"][0]["faltan"] == [m["mes"] for m in cob["meses"]]
    assert cob["cuentas"][0]["faltan_texto"]
    est = client.get("/sincronizacion/estado").json()
    assert est["punto_partida"]["cobertura"]["cuentas"][0]["faltan"]

    # Un gasto de 100 desde el inicio: reconstruido 900 contra 800 declarado => diferencia -100.
    client.post("/movimientos", json={"cuenta_id": c, "tipo": "expense", "monto": 100, "descripcion": "Café",
                                      "fecha": (hoy - timedelta(days=1)).isoformat()})
    conc = {x["cuenta_id"]: x for x in client.get("/perfil/punto-de-partida/conciliacion").json()["cuentas"]}
    assert conc[c]["reconstruido"] == 900 and conc[c]["diferencia"] == -100 and conc[c]["coincide"] is False
    # El ajuste neutral deja la cuenta en lo declarado y la conciliación coincide.
    a = client.post("/perfil/punto-de-partida/ajustar-saldos", json={}).json()
    assert a["ajustados"] >= 1
    saldo = {x["id"]: x["saldo"] for x in client.get("/cuentas").json()}[c]
    assert saldo == 800
    assert client.get("/perfil/punto-de-partida/conciliacion").json()["cuentas"][0]["coincide"] is True


def test_extracto_pdf_marca_lineas_anteriores_y_no_las_importa(monkeypatch):
    """La revisión del PDF deja las líneas previas al inicio como 'anterior' (no 'faltante')."""
    from app.routers import conciliacion as rc

    como("pp-pdf")
    c = _cuenta("Bancolombia Ahorros")
    client.put("/perfil/punto-de-partida", json={"modo": "hoy", "fecha": "2026-09-01"})
    monkeypatch.setattr(rc, "pdf_a_texto", lambda *_a, **_k: "BANCOLOMBIA extracto de cuenta de ahorros")
    movs = [
        {"fecha": "2026-08-10", "descripcion": "COMPRA ANTIGUA", "monto": 5000.0, "tipo": "expense", "referencia": "",
         "fingerprint": "fp-viejo"},
        {"fecha": "2026-09-10", "descripcion": "COMPRA NUEVA", "monto": 7000.0, "tipo": "expense", "referencia": "",
         "fingerprint": "fp-nuevo"},
    ]
    monkeypatch.setattr(rc, "parse_texto_con_regex", lambda _t: (movs, 0))
    monkeypatch.setattr(rc, "evaluar_extracto", lambda *_a, **_k: (True, ""))
    r = client.post("/conciliacion/procesar", json={"pdf_base64": base64.b64encode(b"x").decode(), "cuenta_id": c})
    assert r.status_code == 200, r.text
    j = r.json()
    estados = {i["descripcion"]: i["estado"] for i in j["review"]}
    assert estados["COMPRA ANTIGUA"] == "anterior" and estados["COMPRA NUEVA"] == "faltante"
    assert j["anteriores"] == 1 and j["faltantes"] == 1
    # La confianza de la sugerencia viaja para que la revisión distinga «automática» de «por revisar».
    assert "confianza_categoria" in j["review"][0]
    # Importar «a la fuerza» la línea anterior tampoco la crea.
    fps = [i["fingerprint"] for i in j["review"]]
    imp = client.post(f"/conciliacion/historial/{j['historial_id']}/importar", json={"fingerprints": fps})
    assert imp.status_code == 200, imp.text
    assert imp.json()["importados"] == 1 and imp.json()["anteriores_omitidas"] == 0
