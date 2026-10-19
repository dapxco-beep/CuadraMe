"""Rendimientos que el extracto de una cuenta de ahorros resume pero no lista. Texto y números 100 % inventados.

Septiembre: 1.000.000 + entró 500.000 - salió 200.000 + rendimientos 9.000 = 1.309.000.
Octubre:    1.309.000 + entró 400.000 - salió 100.000 + rendimientos 8.000 = 1.617.000.
"""
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'rend_extracto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cuadre_encadenado as ce  # noqa: E402
from app import cuadre_extracto as cx  # noqa: E402
from app import limites  # noqa: E402
from app import registrar_ajustes_extracto as rr  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app import rendimientos_extracto as rend  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import parse_texto_con_regex  # noqa: E402
from app.contabilidad import tipos_efectivos  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil  # noqa: E402
from app.routers import conciliacion as mod  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="re-0", email="r@test.com", nombre="Persona Prueba")}


def _texto(periodo, mes, ini, entro, salio, rendim, final, lineas):
    return f"""Nu Colombia
Número de Cuenta 1234567890
Período {periodo}
Resumen de tus movimientos
Tu dinero al inicio del mes {ini}
Lo que entró a tu cuenta +{entro}
Lo que salió de tu cuenta -{salio}
Impuesto del 4x1000 $0,00
Rendimiento total de tu cuenta +{rendim}
Tu dinero a final del mes {final}
Dinero en tu Cuenta Nu $9.000,00
Rendimientos 0,10% E.A. +$4.000,00
{lineas}
"""


SEP = _texto("01 - 30 SEP 2026", "sep", "$1.000.000,00", "$500.000,00", "$200.000,00", "$9.000,00", "$1.309.000,00",
             "05 sep Sueldo Empresa Inventada +$500.000,00\n10 sep Compra Tienda Uno -$120.000,00\n15 sep Compra Tienda Dos -$80.000,00")
OCT = _texto("01 - 31 OCT 2026", "oct", "$1.309.000,00", "$400.000,00", "$100.000,00", "$8.000,00", "$1.617.000,00",
             "03 oct Pago Cliente Inventado +$400.000,00\n12 oct Compra Tienda Tres -$100.000,00")
SEP_SIN = _texto("01 - 30 SEP 2026", "sep", "$1.000.000,00", "$500.000,00", "$200.000,00", "$0,00", "$1.300.000,00",
                 "05 sep Sueldo Empresa Inventada +$500.000,00\n10 sep Compra Tienda Uno -$120.000,00\n15 sep Compra Tienda Dos -$80.000,00")
SEP_MAL = SEP.replace("Rendimiento total de tu cuenta +$9.000,00", "Rendimiento total de tu cuenta +$7.000,00")  # el resumen ya no suma


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    limites._eventos.clear()
    yield
    app.dependency_overrides.pop(get_current_user, None)


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre="Persona Prueba")


def _cuenta(nombre="Nu Colombia"):
    return client.post("/cuentas", json={"nombre": nombre, "tipo": "ahorro", "saldo": 0}).json()["id"]


def _procesar(cuenta, texto, monkeypatch):
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: texto)
    r = client.post("/conciliacion/procesar", json={"cuenta_id": cuenta, "pdf_base64": "x"})
    assert r.status_code == 200, r.text
    return r.json()


def _importar_todo(r):
    fps = [i["fingerprint"] for i in r["review"] if i["estado"] == "faltante"]
    ok = client.post(f"/conciliacion/historial/{r['historial_id']}/importar", json={"fingerprints": fps})
    assert ok.status_code == 200, ok.text
    return ok.json()


def _linea_rend(review):
    return next((i for i in review if i.get("rendimiento")), None)


def _movs(uid):
    db = SessionLocal()
    try:
        return sorted((m.cuenta_id, m.descripcion, m.monto, m.tipo, m.categoria) for m in db.query(Movimiento).filter(Movimiento.usuario_id == uid))
    finally:
        db.close()


# ── 1. El lector ──────────────────────────────────────────────────────────────────────────
def test_la_linea_de_rendimiento_se_lee_con_su_huella_estable():
    movs, _ = parse_texto_con_regex(SEP)
    assert len(movs) == 3
    todas, lectura = rend.con_rendimiento(movs, SEP)
    assert len(todas) == 4
    l = todas[-1]
    assert l == {"fecha": "2026-09-30", "descripcion": "Rendimientos de tu cuenta Nu · septiembre de 2026", "monto": 9000.0,
                 "tipo": "income", "referencia": "", "saldo": None, "rendimiento": True, "categoria_fija": "Rendimientos"}
    assert lectura["lectura_completa"] is True and lectura["lineas_leidas"] == 4
    assert lectura["mensaje_lectura"] == "Leí 4 líneas, incluidos tus rendimientos de $9.000, y suman lo que dice tu extracto ✓"
    # no toca la lista original y leer dos veces da lo mismo (la huella sale de fecha + monto + cuenta + descripción)
    assert len(movs) == 3 and rend.con_rendimiento(movs, SEP)[0][-1] == l
    # ...y lo leído (con el rendimiento) lleva del saldo inicial al final
    assert cx.cadena_coincide(cx.leer_saldos_extracto(SEP), todas) is True


def test_sin_rendimiento_no_se_inventa_nada():
    movs, _ = parse_texto_con_regex(SEP_SIN)
    assert rend.con_rendimiento(movs, SEP_SIN) == (movs, None)
    sin_resumen = "Nequi\nExtracto\n01/03/2026 Pago -$5.000\n"
    assert rend.con_rendimiento([], sin_resumen) == ([], None)


def test_desglose_que_no_cuadra_deja_la_linea_apagada_con_aviso():
    movs, _ = parse_texto_con_regex(SEP_MAL)
    todas, lectura = rend.con_rendimiento(movs, SEP_MAL)
    l = todas[-1]
    assert l["marcar_por_defecto"] is False and l["aviso_linea"] == rend.AVISO_NO_CUADRA
    assert lectura["lectura_completa"] is False and "Revisa antes de importar" in lectura["mensaje_lectura"]


def test_una_tarjeta_de_credito_no_agrega_rendimientos():
    movs, _ = parse_texto_con_regex(SEP)
    assert rend.con_rendimiento(movs, SEP, es_credito=True) == (movs, None)


# ── 2. Al procesar e importar ─────────────────────────────────────────────────────────────
def test_procesar_importar_y_resubir_no_duplica_y_el_mes_cuadra_al_peso(monkeypatch):
    como("re-1")
    cuenta = _cuenta()
    r = _procesar(cuenta, SEP, monkeypatch)
    assert r["lectura_completa"] is True and r["mensaje_lectura"].startswith("Leí 4 líneas, incluidos tus rendimientos de $9.000")
    l = _linea_rend(r["review"])
    assert l["estado"] == "faltante" and l["categoria_sugerida"] == "Rendimientos" and l["rendimiento"] is True
    assert l["marcar_por_defecto"] is None  # cuadra: encendida por defecto
    assert r["saldos_extracto"]["cadena_ok"] is True

    assert _importar_todo(r)["importados"] == 4
    movs = _movs("re-1")
    assert ("Rendimientos de tu cuenta Nu · septiembre de 2026", 9000.0, "income", "Rendimientos") in [(m[1], m[2], m[3], m[4]) for m in movs]
    saldo = {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}[cuenta]
    assert saldo == 1_309_000.0  # lo que dice el extracto (con el ajuste inicial automático)

    # el mes cuadra al peso (cuadre mes a mes) y el Cierre de mes también
    db = SessionLocal()
    try:
        fila = ce.calcular(db, db.get(Cuenta, cuenta))["meses"][0]
    finally:
        db.close()
    assert fila["estado"] == "cuadra" and fila["diferencia"] == 0
    cierre = client.get("/cierre-mes/extractos?mes=2026-09").json()
    c = cierre["bancos"][0]["cuentas"][0]
    assert c["estado"] == "cuadra" and c["diferencia"] == 0
    assert c["ingresos"] == 509_000.0 and c["rendimientos"] == 9000.0 and c["gastos"] == 200_000.0
    assert cierre["total"]["rendimientos"] == 9000.0

    # volver a subir el mismo extracto: la línea ya está («exacta»), no hay nada por importar ni se duplica
    limites._eventos.clear()
    r2 = _procesar(cuenta, SEP, monkeypatch)
    assert _linea_rend(r2["review"])["estado"] == "exacto" and r2["faltantes"] == 0
    assert _movs("re-1") == movs


def test_los_rendimientos_son_ingreso_real_no_traslado(monkeypatch):
    como("re-2")
    cuenta = _cuenta()
    _importar_todo(_procesar(cuenta, SEP, monkeypatch))
    db = SessionLocal()
    try:
        ms = db.query(Movimiento).filter(Movimiento.usuario_id == "re-2").all()
        tipos = tipos_efectivos(ms, {cuenta: "ahorro"})
        m = next(x for x in ms if x.categoria == "Rendimientos")
        assert tipos[m.id] == "income"
    finally:
        db.close()


# ── 3. Extractos ya importados: releer y lote ─────────────────────────────────────────────
TEXTOS: dict[str, str] = {}


class _Exec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class GmailFalso:
    def __init__(self): self.llamadas = 0
    def users(self): return self
    def messages(self): return self
    def get(self, **kw):
        self.llamadas += 1
        return _Exec({"id": kw["id"]})


@pytest.fixture
def gmail(monkeypatch):
    g = GmailFalso()
    monkeypatch.setattr(rx, "listar_adjuntos_pdf", lambda msg: [{"archivo": "ahorros.pdf", "attachment_id": msg["id"]}])
    monkeypatch.setattr(rx, "descargar_adjunto", lambda g_, m, a: m.encode())
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("ok", TEXTOS[pdf.decode()], None))
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: g)
    return g


def _importado_con_lector_viejo(uid, textos, monkeypatch):
    """Los extractos como quedaron con el lector de antes: importados SIN la línea de rendimiento y con correo."""
    como(uid)
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
        db.commit()
    finally:
        db.close()
    cuenta = _cuenta()
    ids = []
    with monkeypatch.context() as mp:
        mp.setattr(rend, "con_rendimiento", lambda movs, texto, cuenta=None, **k: (movs, None))
        mp.setattr(mod.rendimientos_extracto, "con_rendimiento", lambda movs, texto, cuenta=None, **k: (movs, None))
        for n, texto in enumerate(textos):
            limites._eventos.clear()
            r = _procesar(cuenta, texto, monkeypatch)
            _importar_todo(r)
            msg = f"m-{uid}-{n}"
            TEXTOS[msg] = texto
            db = SessionLocal()
            try:
                db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=msg, archivo="ahorros.pdf", asunto="Extracto de tu cuenta", estado="procesado",
                                      historial_id=r["historial_id"]))
                db.commit()
            finally:
                db.close()
            ids.append(r["historial_id"])
    return cuenta, ids


def test_releer_un_extracto_conciliado_agrega_solo_la_linea_de_rendimiento(monkeypatch, gmail):
    cuenta, (h1,) = _importado_con_lector_viejo("re-3", [SEP], monkeypatch)
    antes = _movs("re-3")
    saldo_antes = {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}[cuenta]
    assert saldo_antes == 1_300_000.0  # sin los $9.000 de rendimientos: el mes no cuadra
    r = client.post(f"/conciliacion/historial/{h1}/releer")
    assert r.status_code == 200, r.text
    assert r.json()["agregadas"] == 1 and r.json()["por_importar"] == 1
    assert "incluidos tus rendimientos de $9.000" in r.json()["mensaje_lectura"]
    assert _movs("re-3") == antes  # releer no importa ni toca nada
    review = client.get(f"/conciliacion/historial/{h1}").json()["review"]
    assert [i["estado"] for i in review].count("faltante") == 1 and _linea_rend(review)["estado"] == "faltante"
    assert len([i for i in review if i["estado"] == "importado"]) == 3
    # releer otra vez no la duplica
    limites._eventos.clear()
    monkeypatch.setattr(rx, "VERSION_LECTOR", "otra-version")
    assert client.post(f"/conciliacion/historial/{h1}/releer").json()["agregadas"] == 0


def test_el_lote_registra_los_rendimientos_faltantes_y_es_idempotente(monkeypatch, gmail):
    cuenta, ids = _importado_con_lector_viejo("re-4", [SEP, OCT], monkeypatch)
    # ni el cuadre ni el Cierre de septiembre cuadran todavía: faltan los rendimientos
    assert client.get("/cierre-mes/extractos?mes=2026-09").json()["bancos"][0]["cuentas"][0]["estado"] == "no_cuadra"
    previa = client.get("/conciliacion/rendimientos/previa").json()
    assert previa["total"] == 2 and previa["total_pesos"] == 17_000.0 and previa["aproximado"] is True
    assert [e["mes"] for e in previa["extractos"]] == ["2026-09", "2026-10"] and all(e["estimado"] for e in previa["extractos"])
    assert gmail.llamadas == 0  # la previa no toca Gmail
    antes = _movs("re-4")

    assert client.post("/conciliacion/rendimientos/registrar", json={"confirmar": False}).status_code == 400
    r = client.post("/conciliacion/rendimientos/registrar", json={"confirmar": True})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["registrados"] == 2 and j["saltados"] == 0 and j["total_pesos"] == 17_000.0
    assert j["resumen"] == "Completé 2 extractos: $17.000 de rendimientos."
    despues = _movs("re-4")
    assert len(despues) == len(antes) + 2
    assert sorted(m[2] for m in despues if m[4] == "Rendimientos") == [8000.0, 9000.0]
    saldo = {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}[cuenta]
    assert saldo == 1_617_000.0  # el saldo final del último extracto
    assert client.get("/cierre-mes/extractos?mes=2026-09").json()["bancos"][0]["cuentas"][0]["diferencia"] == 0
    assert client.get("/cierre-mes/extractos?mes=2026-10").json()["bancos"][0]["cuentas"][0]["diferencia"] == 0
    db = SessionLocal()
    try:
        assert ce.calcular(db, db.get(Cuenta, cuenta))["cuadra"] is True
        assert {h.estado for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == "re-4")} == {"conciliado"}
    finally:
        db.close()

    # idempotente: no hay nada más que registrar, no se vuelve a leer Gmail ni se duplica
    llamadas = gmail.llamadas
    assert client.get("/conciliacion/rendimientos/previa").json()["total"] == 0
    limites._eventos.clear()
    j2 = client.post("/conciliacion/rendimientos/registrar", json={"confirmar": True}).json()
    assert j2["sin_cambios"] is True and "ya están completos" in j2["resumen"]
    assert _movs("re-4") == despues and gmail.llamadas == llamadas


def test_un_extracto_subido_a_mano_no_entra_al_lote(monkeypatch, gmail):
    como("re-5")
    cuenta = _cuenta()
    _importar_todo(_procesar(cuenta, SEP, monkeypatch))  # ya con la línea
    # ahora uno viejo, sin la línea y sin correo (subido a mano)
    como("re-5b")
    cuenta_b = _cuenta()
    with monkeypatch.context() as mp:
        mp.setattr(mod.rendimientos_extracto, "con_rendimiento", lambda movs, texto, cuenta=None, **k: (movs, None))
        _importar_todo(_procesar(cuenta_b, SEP, monkeypatch))
    assert client.get("/conciliacion/rendimientos/previa").json()["total"] == 0


def test_un_ajuste_de_saldo_por_el_mismo_valor_evita_duplicar(monkeypatch, gmail):
    cuenta, (h1,) = _importado_con_lector_viejo("re-6", [SEP], monkeypatch)
    # aquí la línea ya está «por importar» (la relectura la agregó) y DESPUÉS la persona hizo el ajuste
    assert client.post(f"/conciliacion/historial/{h1}/releer").status_code == 200
    db = SessionLocal()
    try:
        c = db.get(Cuenta, cuenta)
        cx.crear_ajuste(db, c, "re-6", cx.a_fecha("2026-09-30"), 9000.0)
        db.commit()
    finally:
        db.close()
    j = client.post("/conciliacion/rendimientos/registrar", json={"confirmar": True}).json()
    assert j["registrados"] == 0 and j["saltados"] == 1 and "ajuste de saldo" in j["resultados"][0]["motivo"]
    assert not [m for m in _movs("re-6") if m[4] == "Rendimientos"]


def test_el_lote_aislado_por_usuario(monkeypatch, gmail):
    _importado_con_lector_viejo("re-7", [SEP], monkeypatch)
    como("re-8")
    assert client.get("/conciliacion/rendimientos/previa").json()["total"] == 0
    j = client.post("/conciliacion/rendimientos/registrar", json={"confirmar": True}).json()
    assert j["sin_cambios"] is True
    como("re-7")
    assert client.get("/conciliacion/rendimientos/previa").json()["total"] == 1


def test_la_relectura_automatica_incluye_los_de_ahorro_con_rendimientos(monkeypatch, gmail):
    cuenta, (h1,) = _importado_con_lector_viejo("re-9", [SEP], monkeypatch)
    out = client.post("/conciliacion/releer-pendientes").json()
    assert out["releidos"] == 1 and out["cambiados"] == 1
    review = client.get(f"/conciliacion/historial/{h1}").json()["review"]
    assert _linea_rend(review)["estado"] == "faltante"
    assert client.post("/conciliacion/releer-pendientes").json()["releidos"] == 0  # una vez por versión del lector
    assert rx.VERSION_LECTOR.startswith("2026-10-")  # no se fija la versión exacta: sube con cada mejora del lector
