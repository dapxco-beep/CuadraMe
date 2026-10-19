"""4x1000 y costos por retiro que el resumen del extracto de una cuenta de ahorros trae pero no lista (con los rendimientos).
Texto y números 100 % inventados.

Agosto:    2.000.000 + entró 1.500.000 - salió 1.000.000 - 4x1000 4.000 - costos 6.500 + rendimientos 9.000 = 2.498.500.
Septiembre: 2.498.500 + entró 300.000 - salió 100.000 - 4x1000 400 + rendimientos 8.000 = 2.706.100 (sin costos por retiro).
"""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'ajustes_extracto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cuadre_encadenado as ce  # noqa: E402
from app import cuadre_extracto as cx  # noqa: E402
from app import limites  # noqa: E402
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
USUARIO = {"u": UsuarioActual(id="ae-0", email="a@test.com", nombre="Persona Prueba")}


def _texto(periodo, ini, entro, salio, gmf, retiro, rendim, final, lineas):
    filas_extra = (f"Impuesto del 4x1000 {gmf}\n" if gmf else "") + (f"Costos por retiro {retiro}\n" if retiro else "")
    return f"""Nu Colombia
Número de Cuenta 1234567890
Período {periodo}
Resumen de tus movimientos
Tu dinero al inicio del mes {ini}
Lo que entró a tu cuenta +{entro}
Lo que salió de tu cuenta -{salio}
{filas_extra}Rendimiento total de tu cuenta +{rendim}
Tu dinero a final del mes {final}
{lineas}
"""


AGO = _texto("01 - 31 AGO 2026", "$2.000.000,00", "$1.500.000,00", "$1.000.000,00", "$4.000,00", "$6.500,00", "$9.000,00", "$2.498.500,00",
             "05 ago Sueldo Empresa Inventada +$1.500.000,00\n10 ago Compra Tienda Uno -$600.000,00\n15 ago Compra Tienda Dos -$400.000,00")
SEP = _texto("01 - 30 SEP 2026", "$2.498.500,00", "$300.000,00", "$100.000,00", "$400,00", None, "$8.000,00", "$2.706.100,00",
             "03 sep Pago Cliente Inventado +$300.000,00\n12 sep Compra Tienda Tres -$100.000,00")
SOLO_RENDIMIENTO = _texto("01 - 30 SEP 2026", "$1.000.000,00", "$500.000,00", "$200.000,00", None, None, "$9.000,00", "$1.309.000,00",
                          "05 sep Sueldo Empresa Inventada +$500.000,00\n10 sep Compra Tienda Uno -$120.000,00\n15 sep Compra Tienda Dos -$80.000,00")
SIN_NADA = _texto("01 - 30 SEP 2026", "$1.000.000,00", "$500.000,00", "$200.000,00", None, None, "$0,00", "$1.300.000,00",
                  "05 sep Sueldo Empresa Inventada +$500.000,00\n10 sep Compra Tienda Uno -$120.000,00\n15 sep Compra Tienda Dos -$80.000,00")
AGO_MAL = AGO.replace("Impuesto del 4x1000 $4.000,00", "Impuesto del 4x1000 $5.000,00")  # el resumen ya no suma


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    limites._eventos.clear()
    yield
    app.dependency_overrides.pop(get_current_user, None)


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre="Persona Prueba")


# ── 1. El lector ──────────────────────────────────────────────────────────────────────────
def test_el_resumen_trae_4x1000_y_costos_por_retiro():
    s = cx.leer_saldos_extracto(AGO)
    assert s["impuesto_4x1000"] == 4000.0 and s["costos_retiro"] == 6500.0 and s["rendimiento"] == 9000.0
    assert s["resumen_cuadra"] is True  # inicio + entró - salió - 4x1000 - costos + rendimiento = final
    assert "impuesto_4x1000" not in cx.leer_saldos_extracto(SOLO_RENDIMIENTO)
    # con signo y coma decimal tambien se lee
    con_signo = AGO.replace("Impuesto del 4x1000 $4.000,00", "Impuesto del 4x1000 -$4.000,00")
    assert cx.leer_saldos_extracto(con_signo)["impuesto_4x1000"] == 4000.0


def test_agrega_una_linea_por_concepto_con_su_categoria_y_la_verificacion_cuadra():
    movs, _ = parse_texto_con_regex(AGO)
    assert len(movs) == 3
    todas, lectura = rend.con_rendimiento(movs, AGO)
    assert len(todas) == 6
    por = {rend.concepto_de_linea(l): l for l in todas[3:]}
    assert por["rendimientos"]["tipo"] == "income" and por["rendimientos"]["categoria_fija"] == "Rendimientos"
    g = por["impuesto_4x1000"]
    assert (g["fecha"], g["descripcion"], g["monto"], g["tipo"], g["categoria_fija"]) == (
        "2026-08-31", "Impuesto 4x1000 (GMF) · agosto de 2026", 4000.0, "expense", "4x1000 (GMF)")
    r = por["costos_retiro"]
    assert (r["descripcion"], r["monto"], r["tipo"], r["categoria_fija"]) == (
        "Costos por retiro · agosto de 2026", 6500.0, "expense", "Comisiones y seguros")
    assert lectura["lectura_completa"] is True and lectura["lineas_leidas"] == 6
    assert lectura["mensaje_lectura"] == ("Leí 6 líneas, incluidos tus rendimientos de $9.000, el 4x1000 de $4.000 y tus costos por "
                                          "retiro de $6.500, y suman lo que dice tu extracto ✓")
    assert cx.cadena_coincide(cx.leer_saldos_extracto(AGO), todas) is True
    # estable: leer dos veces da las mismas líneas (misma huella) y no toca la lista original
    assert len(movs) == 3 and rend.con_rendimiento(movs, AGO)[0][3:] == todas[3:]


def test_mensaje_con_rendimientos_y_4x1000():
    movs, _ = parse_texto_con_regex(SEP)
    todas, lectura = rend.con_rendimiento(movs, SEP)
    assert len(todas) == 4
    assert lectura["mensaje_lectura"] == "Leí 4 líneas, incluidos tus rendimientos de $8.000 y el 4x1000 de $400, y suman lo que dice tu extracto ✓"


def test_sin_esos_conceptos_no_se_inventa_nada():
    movs, _ = parse_texto_con_regex(SIN_NADA)
    assert rend.con_rendimiento(movs, SIN_NADA) == (movs, None)
    movs, _ = parse_texto_con_regex(SOLO_RENDIMIENTO)
    todas, _ = rend.con_rendimiento(movs, SOLO_RENDIMIENTO)
    assert [rend.concepto_de_linea(l) for l in todas[3:]] == ["rendimientos"]


def test_un_resumen_que_no_cuadra_deja_todo_apagado_con_aviso():
    movs, _ = parse_texto_con_regex(AGO_MAL)
    todas, lectura = rend.con_rendimiento(movs, AGO_MAL)
    assert all(l["marcar_por_defecto"] is False and l["aviso_linea"] for l in todas[3:])
    assert lectura["lectura_completa"] is False and "Revisa antes de importar" in lectura["mensaje_lectura"]


def test_si_el_extracto_ya_lista_el_4x1000_no_se_agrega_otra_linea():
    movs, _ = parse_texto_con_regex(AGO)
    movs = [*movs, {"fecha": "2026-08-20", "descripcion": "Gravamen 4x1000", "monto": 4000.0, "tipo": "expense", "referencia": "", "saldo": None}]
    todas, _ = rend.con_rendimiento(movs, AGO)
    assert [rend.concepto_de_linea(l) for l in todas[4:]] == ["rendimientos", "costos_retiro"]


def test_una_tarjeta_de_credito_no_agrega_nada():
    movs, _ = parse_texto_con_regex(AGO)
    assert rend.con_rendimiento(movs, AGO, es_credito=True) == (movs, None)


# ── 2. Procesar, importar y extractos ya importados ───────────────────────────────────────
_LECTOR_DE_HOY = rend.con_rendimiento  # antes de que algún test lo reemplace


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


def _movs(uid):
    db = SessionLocal()
    try:
        return sorted((m.cuenta_id, m.descripcion, m.monto, m.tipo, m.categoria) for m in db.query(Movimiento).filter(Movimiento.usuario_id == uid))
    finally:
        db.close()


def _lineas_ajuste(review):
    return {rend.concepto_de_linea(i): i for i in review if rend.es_linea_de_ajuste(i)}


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


def _solo_rendimientos(movs, texto, cuenta=None, **k):
    """El lector de la versión anterior: solo agregaba la línea de rendimientos."""
    todas, lectura = _LECTOR_DE_HOY(movs, texto, cuenta, **k)
    return [m for m in todas if not (m.get("impuesto_4x1000") or m.get("costos_retiro"))], None


def _importado_con_lector_viejo(uid, textos, monkeypatch, lector=None, antes=None):
    """Los extractos como quedaron con un lector anterior (sin líneas del resumen, o solo con rendimientos) y con correo."""
    como(uid)
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
        db.commit()
    finally:
        db.close()
    cuenta = _cuenta()
    if antes:
        antes(cuenta)
    ids = []
    viejo = lector or (lambda movs, texto, cuenta=None, **k: (movs, None))
    with monkeypatch.context() as mp:
        mp.setattr(rend, "con_rendimiento", viejo)
        mp.setattr(mod.rendimientos_extracto, "con_rendimiento", viejo)
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


def _saldo(cuenta):
    return {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}[cuenta]


def _cuadre(cuenta):
    db = SessionLocal()
    try:
        return ce.calcular(db, db.get(Cuenta, cuenta))
    finally:
        db.close()


def test_procesar_e_importar_registra_las_tres_lineas_y_el_mes_cuadra_al_peso(monkeypatch):
    como("ae-1")
    cuenta = _cuenta()
    r = _procesar(cuenta, AGO, monkeypatch)
    assert r["lectura_completa"] is True and r["mensaje_lectura"].startswith("Leí 6 líneas, incluidos tus rendimientos de $9.000, el 4x1000 de $4.000")
    lin = _lineas_ajuste(r["review"])
    assert set(lin) == {"rendimientos", "impuesto_4x1000", "costos_retiro"}
    assert all(l["estado"] == "faltante" and l["marcar_por_defecto"] is None for l in lin.values())  # cuadra: encendidas
    assert lin["impuesto_4x1000"]["categoria_sugerida"] == "4x1000 (GMF)" and lin["costos_retiro"]["categoria_sugerida"] == "Comisiones y seguros"
    assert _importar_todo(r)["importados"] == 6
    assert _saldo(cuenta) == 2_498_500.0
    fila = _cuadre(cuenta)["meses"][0]
    assert fila["estado"] == "cuadra" and fila["diferencia"] == 0
    # el 4x1000 y los costos son GASTOS reales (no traslados) y los rendimientos un ingreso real
    db = SessionLocal()
    try:
        ms = db.query(Movimiento).filter(Movimiento.usuario_id == "ae-1").all()
        tipos = tipos_efectivos(ms, {cuenta: "ahorro"})
        por_cat = {m.categoria: tipos[m.id] for m in ms if m.categoria in ("4x1000 (GMF)", "Comisiones y seguros", "Rendimientos")}
    finally:
        db.close()
    assert por_cat == {"4x1000 (GMF)": "expense", "Comisiones y seguros": "expense", "Rendimientos": "income"}
    # volver a subir el mismo extracto: nada por importar, sin duplicados
    movs = _movs("ae-1")
    limites._eventos.clear()
    r2 = _procesar(cuenta, AGO, monkeypatch)
    assert r2["faltantes"] == 0 and all(l["estado"] == "exacto" for l in _lineas_ajuste(r2["review"]).values())
    assert _movs("ae-1") == movs


def test_el_4x1000_del_extracto_figura_como_registrado_en_impuestos(monkeypatch):
    como("ae-2")
    cuenta = _cuenta()
    _importar_todo(_procesar(cuenta, AGO, monkeypatch))
    from app.impuestos import calcular_gmf
    db = SessionLocal()
    try:
        ms = db.query(Movimiento).filter(Movimiento.usuario_id == "ae-2").all()
        movs = [{"fecha": m.fecha, "monto": m.monto, "tipo": m.tipo, "fuente": m.fuente, "notas": m.notas, "descripcion": m.descripcion,
                 "cuenta_id": m.cuenta_id} for m in ms]
        r = calcular_gmf(movs, {cuenta: "ahorro"}, None, 2026)
    finally:
        db.close()
    ago = next(f for f in r["meses"] if f["mes"] == "2026-08")
    assert ago["gmf_registrado"] == 4000 and ago["debitos"] == 1_006_500  # los costos por retiro son un débito; la línea del 4x1000 no se grava a sí misma


def test_el_lote_completa_rendimientos_4x1000_y_costos_incluido_el_mes_donde_el_4x1000_pesa_mas(monkeypatch, gmail):
    """El caso de agosto: rendimientos 9.000 - 4x1000 4.000 - costos 6.500 = -1.500, así que el banco registró MENOS que la app
    (diferencia en contra). El lote anterior solo miraba diferencias a favor del banco y ese mes nunca entraba."""
    cuenta, ids = _importado_con_lector_viejo("ae-3", [AGO, SEP], monkeypatch)
    dif = {f["mes"]: f["diferencia"] for f in _cuadre(cuenta)["meses"]}
    assert dif == {"2026-08": -1500.0, "2026-09": 7600.0}
    previa = client.get("/conciliacion/ajustes-extracto/previa").json()
    assert previa["total"] == 2 and previa["aproximado"] is True and previa["por_determinar"] == 9100.0
    assert [e["mes"] for e in previa["extractos"]] == ["2026-08", "2026-09"]
    assert gmail.llamadas == 0  # la previa no toca Gmail
    assert client.get("/conciliacion/rendimientos/previa").json()["total"] == 2  # la ruta anterior del botón sigue igual
    antes = _movs("ae-3")

    assert client.post("/conciliacion/ajustes-extracto/registrar", json={"confirmar": False}).status_code == 400
    j = client.post("/conciliacion/ajustes-extracto/registrar", json={"confirmar": True}).json()
    assert j["registrados"] == 2 and j["saltados"] == 0
    assert j["por_concepto"] == {"rendimientos": 17000.0, "impuesto_4x1000": 4400.0, "costos_retiro": 6500.0}
    assert j["resumen"] == "Completé 2 extractos: $17.000 de rendimientos, $4.400 de 4x1000 y $6.500 de costos por retiro."
    despues = _movs("ae-3")
    assert len(despues) == len(antes) + 5
    assert sorted(m[2] for m in despues if m[4] == "4x1000 (GMF)") == [400.0, 4000.0]
    assert _saldo(cuenta) == 2_706_100.0
    assert _cuadre(cuenta)["cuadra"] is True
    db = SessionLocal()
    try:
        assert {h.estado for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == "ae-3")} == {"conciliado"}
    finally:
        db.close()

    # idempotente: no hay nada más que completar, no se vuelve a leer Gmail ni se duplica
    llamadas = gmail.llamadas
    assert client.get("/conciliacion/ajustes-extracto/previa").json()["total"] == 0
    limites._eventos.clear()
    j2 = client.post("/conciliacion/ajustes-extracto/registrar", json={"confirmar": True}).json()
    assert j2["sin_cambios"] is True and "ya están completos" in j2["resumen"]
    assert _movs("ae-3") == despues and gmail.llamadas == llamadas


def test_un_mes_con_lineas_completadas_recibe_sus_lineas_sin_tocar_lo_completado(monkeypatch, gmail):
    def del_atajo(cuenta):  # el gasto ya lo había registrado el atajo del celular: el extracto lo «completa»
        db = SessionLocal()
        try:
            db.add(Movimiento(usuario_id="ae-4", cuenta_id=cuenta, descripcion="Pago atajo tienda", categoria="Otros", tipo="expense",
                              monto=600000, fecha=datetime(2026, 8, 10, 12, 0), fuente="shortcut"))
            db.get(Cuenta, cuenta).saldo -= 600000  # como lo hace el atajo al registrar el gasto
            db.commit()
        finally:
            db.close()

    cuenta, (h1,) = _importado_con_lector_viejo("ae-4", [AGO], monkeypatch, antes=del_atajo)
    review = client.get(f"/conciliacion/historial/{h1}").json()["review"]
    completadas = [i["fingerprint"] for i in review if i["estado"] == "completado"]
    assert len(completadas) == 1
    antes = _movs("ae-4")
    j = client.post("/conciliacion/ajustes-extracto/registrar", json={"confirmar": True}).json()
    assert j["registrados"] == 1 and j["por_concepto"] == {"rendimientos": 9000.0, "impuesto_4x1000": 4000.0, "costos_retiro": 6500.0}
    review = client.get(f"/conciliacion/historial/{h1}").json()["review"]
    assert [i["fingerprint"] for i in review if i["estado"] == "completado"] == completadas  # lo completado sigue igual
    assert len(_movs("ae-4")) == len(antes) + 3
    assert _cuadre(cuenta)["meses"][0]["estado"] == "cuadra"


def test_un_mes_con_rendimientos_ya_registrados_recibe_solo_el_4x1000_que_faltaba(monkeypatch, gmail):
    cuenta, _ = _importado_con_lector_viejo("ae-5", [SEP], monkeypatch, lector=_solo_rendimientos)
    assert _cuadre(cuenta)["meses"][0]["diferencia"] == -400.0  # el banco cobró 400 de 4x1000 que la app no tiene
    assert client.get("/conciliacion/ajustes-extracto/previa").json()["total"] == 1
    j = client.post("/conciliacion/ajustes-extracto/registrar", json={"confirmar": True}).json()
    assert j["por_concepto"] == {"rendimientos": 0.0, "impuesto_4x1000": 400.0, "costos_retiro": 0.0}
    assert j["resumen"] == "Completé 1 extracto: $400 de 4x1000."
    assert _cuadre(cuenta)["cuadra"] is True


def test_si_el_resumen_no_cuadra_las_lineas_quedan_apagadas_y_el_lote_no_las_registra(monkeypatch, gmail):
    cuenta, (h1,) = _importado_con_lector_viejo("ae-6", [AGO_MAL], monkeypatch)
    antes = _movs("ae-6")
    j = client.post("/conciliacion/ajustes-extracto/registrar", json={"confirmar": True}).json()
    assert j["registrados"] == 0 and j["saltados"] == 1 and "Revísalo" in j["resultados"][0]["motivo"]
    assert _movs("ae-6") == antes


def test_un_ajuste_de_saldo_por_el_mismo_valor_y_sentido_evita_duplicar_solo_esa_linea(monkeypatch, gmail):
    cuenta, (h1,) = _importado_con_lector_viejo("ae-7", [AGO], monkeypatch)
    assert client.post(f"/conciliacion/historial/{h1}/releer").status_code == 200
    db = SessionLocal()
    try:
        cx.crear_ajuste(db, db.get(Cuenta, cuenta), "ae-7", cx.a_fecha("2026-08-31"), -4000.0)  # ajuste que sale por el valor del 4x1000
        db.commit()
    finally:
        db.close()
    j = client.post("/conciliacion/ajustes-extracto/registrar", json={"confirmar": True}).json()
    assert j["por_concepto"] == {"rendimientos": 9000.0, "impuesto_4x1000": 0.0, "costos_retiro": 6500.0}
    assert "4x1000" in j["resultados"][0]["motivo"] and "ajuste de saldo" in j["resultados"][0]["motivo"]


def test_releer_y_la_relectura_automatica_agregan_las_lineas_por_importar_y_es_idempotente(monkeypatch, gmail):
    cuenta, (h1,) = _importado_con_lector_viejo("ae-8", [AGO], monkeypatch)
    antes = _movs("ae-8")
    out = client.post("/conciliacion/releer-pendientes").json()
    assert out["releidos"] == 1 and out["cambiados"] == 1
    review = client.get(f"/conciliacion/historial/{h1}").json()["review"]
    assert {k: l["estado"] for k, l in _lineas_ajuste(review).items()} == {
        "rendimientos": "faltante", "impuesto_4x1000": "faltante", "costos_retiro": "faltante"}
    assert _movs("ae-8") == antes  # releer no importa nada
    assert client.post("/conciliacion/releer-pendientes").json()["releidos"] == 0  # una vez por versión del lector
    limites._eventos.clear()
    monkeypatch.setattr(rx, "VERSION_LECTOR", "otra-version")
    assert client.post(f"/conciliacion/historial/{h1}/releer").json()["agregadas"] == 0  # la huella es estable: no se duplican


def test_el_lote_esta_aislado_por_usuario(monkeypatch, gmail):
    _importado_con_lector_viejo("ae-9", [AGO], monkeypatch)
    como("ae-10")
    assert client.get("/conciliacion/ajustes-extracto/previa").json()["total"] == 0
    assert client.post("/conciliacion/ajustes-extracto/registrar", json={"confirmar": True}).json()["sin_cambios"] is True
    como("ae-9")
    assert client.get("/conciliacion/ajustes-extracto/previa").json()["total"] == 1
