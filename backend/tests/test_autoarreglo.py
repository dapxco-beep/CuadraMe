"""AUTOARREGLO (app/autoarreglo.py): el caso real con datos 100 % inventados.

Mundo de la persona `uid`:
  · "Nu Colombia" (ahorros) con los extractos de agosto y septiembre importados con el lector viejo: faltan los rendimientos, el
    4x1000 y los costos por retiro del resumen (ver tests/test_ajustes_extracto.py para las cifras).
  · "Nu Colombia Crédito" (tarjeta) sin movimientos.
  · Dos extractos de TARJETA (julio y agosto) importados por el lector viejo en la cuenta de AHORROS: compras guardadas como
    ingreso y un pago por $40.000 que en realidad fue de $60.000.
  · Un extracto de tarjeta de septiembre ya en la tarjeta pero con lectura dudosa (no cuadra con el resumen).
  · "Bancolombia Ahorros": un extracto verificado con 2 líneas claras y 1 de lectura dudosa, y otro que no cuadra.
Gmail y el lector de tarjeta están simulados. Nada sale de la base de pruebas."""
import json
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'autoarreglo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import autoarreglo as aa  # noqa: E402
from app import corregir_pago  # noqa: E402
from app import duplicados as dup  # noqa: E402
from app import limites  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app import rendimientos_extracto as rend  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import compute_fingerprint  # noqa: E402
from app.contabilidad import CATEGORIA_PAGO_TARJETA, MARCA_TRASLADO_PROPIO  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Consentimiento, Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil  # noqa: E402
from app.models_autoarreglo import ArregloAuto  # noqa: E402
from app.models_fiscal import AjusteUsuario  # noqa: E402
from app.routers import conciliacion as mod  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402
from tests.test_ajustes_extracto import AGO, SEP  # noqa: E402  (extractos de ahorros inventados)

Base.metadata.create_all(bind=engine)
client = TestClient(app)

# ── Cifras inventadas de la tarjeta ──────────────────────────────────────────────────────────
DESC_PAGO_VIEJA, DESC_PAGO = "Pago de tu tarjeta (factura anterior)", "Pago de tu tarjeta"
PAGO_B, PAGO_A = 40_000.0, 60_000.0
COMPRAS_JUL = [(3, "Tienda Uno SAS", 40_000.0), (5, "Tienda Dos SAS", 23_000.0)]
NUEVA_JUL = (9, "Tienda Tres SAS", 9_800.0)  # la lee el lector de hoy y el viejo no la veía
COMPRAS_AGO = [(4, "Supermercado Uno", 120_000.0)]
TARJETA_FINAL = PAGO_A - 40_000 - 23_000 - 9_800 - 120_000  # = -132.800
AHORRO_FINAL = 2_706_100.0  # lo que dice el extracto de septiembre

TEXTOS: dict[str, str] = {}
LECTURAS: dict[str, list[dict]] = {}  # texto (= id del mensaje) de TARJETA -> líneas que lee el lector de hoy
DUDOSOS: set[str] = set()  # extractos de tarjeta cuya lectura NO cuadra con el resumen
_LECTOR_REAL = rx._leer_lineas
_ES_NU = rx.es_extracto_tarjeta_nu
_LEER_NU = rx.leer_extracto_tarjeta_nu
_DATOS = rx.datos_de_lectura


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


@pytest.fixture(autouse=True)
def _simulado(monkeypatch):
    app.dependency_overrides.clear()
    limites._eventos.clear()
    monkeypatch.setattr(rx, "listar_adjuntos_pdf", lambda msg: [{"archivo": "extracto.pdf", "attachment_id": msg["id"]}])
    monkeypatch.setattr(rx, "descargar_adjunto", lambda g, m, a: m.encode())
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("ok", TEXTOS.get(pdf.decode(), pdf.decode()), None))
    monkeypatch.setattr(rx, "_leer_lineas", lambda t: [dict(m) for m in LECTURAS[t]] if t in LECTURAS else _LECTOR_REAL(t))
    monkeypatch.setattr(rx, "es_extracto_tarjeta_nu", lambda t: t in LECTURAS or _ES_NU(t))
    monkeypatch.setattr(rx, "leer_extracto_tarjeta_nu", lambda t: {"__sim__": t} if t in LECTURAS else _LEER_NU(t))
    monkeypatch.setattr(rx, "datos_de_lectura", lambda r: (
        {"lectura_completa": r["__sim__"] not in DUDOSOS, "lineas_leidas": len(LECTURAS[r["__sim__"]]),
         "mensaje_lectura": f"Leí {len(LECTURAS[r['__sim__']])} líneas" + (" y suman lo que dice tu extracto ✓" if r["__sim__"] not in DUDOSOS
                                                                          else ", pero no suman lo que dice tu extracto")}
        if "__sim__" in r else _DATOS(r)))
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: GmailFalso())
    yield
    app.dependency_overrides.clear()


def como(uid):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="Persona Prueba")


def _fecha(mes, dia):
    return f"2026-{mes:02d}-{dia:02d}"


def _mov(db, uid, cuenta, mes, dia, desc, monto, tipo, categoria="Otros", notas="", fp=None):
    m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=desc, categoria=categoria, tipo=tipo, monto=monto,
                   fecha=datetime(2026, mes, dia), fuente="conciliacion_extracto", notas=notas)
    db.add(m)
    db.flush()
    cuenta.saldo += monto if tipo == "income" else -monto
    dup.nuevo_movimiento(db, m, dup.ORIGEN_EXTRACTO, dup.huella_extracto(fp, 1) if fp else None)
    return m


def _compra_nueva(cuenta_id, mes, dia, desc, monto):
    return {"fecha": _fecha(mes, dia), "descripcion": desc, "monto": monto, "tipo": "expense", "linea_tipo": "compra",
            "corrige_tipo": {"de": "income", "a": "expense"}, "cuenta": cuenta_id}


def _tarjeta_en(db, uid, cuenta, destino_id, mes, compras, *, con_pago=False, nueva=None, asunto="Extracto de tu tarjeta de crédito"):
    """Extracto de tarjeta como lo dejó el lector viejo en `cuenta` (compras como ingreso) y lo que lee el de hoy."""
    review, leidas = [], []
    for dia, desc, monto in compras:
        fp = compute_fingerprint(_fecha(mes, dia), monto, cuenta.id, desc, "income")
        m = _mov(db, uid, cuenta, mes, dia, desc, monto, "income", fp=fp)
        review.append({"fecha": _fecha(mes, dia), "descripcion": desc, "monto": monto, "tipo": "income", "fingerprint": fp,
                       "estado": "importado", "movimiento_id": m.id})
        leidas.append(_compra_nueva(destino_id, mes, dia, desc, monto))
    if con_pago:
        fp = compute_fingerprint(_fecha(mes, 20), PAGO_B, cuenta.id, DESC_PAGO_VIEJA, "income")
        m = _mov(db, uid, cuenta, mes, 20, DESC_PAGO_VIEJA, PAGO_B, "income", categoria=CATEGORIA_PAGO_TARJETA,
                 notas=f"Importado desde extracto nu · {MARCA_TRASLADO_PROPIO}", fp=fp)
        review.append({"fecha": _fecha(mes, 20), "descripcion": DESC_PAGO_VIEJA, "monto": PAGO_B, "tipo": "income",
                       "fingerprint": fp, "estado": "importado", "movimiento_id": m.id})
        leidas.append({"fecha": _fecha(mes, 20), "descripcion": DESC_PAGO, "monto": PAGO_A, "tipo": "income", "linea_tipo": "pago",
                       "pago_tarjeta": True, "pista": MARCA_TRASLADO_PROPIO, "cuenta": destino_id,
                       "corrige_lectura": {"descripcion": DESC_PAGO_VIEJA, "tipo": "income", "montos": [PAGO_B]}})
    if nueva:
        leidas.append(_compra_nueva(destino_id, mes, nueva[0], nueva[1], nueva[2]))
    msg = f"m-{uid}-tarjeta-{mes}"
    LECTURAS[msg] = leidas
    h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta.id, banco_detectado="nu", estado="conciliado", total_movimientos=len(review),
                          importados=len(review), review_json=json.dumps(review), fecha_corte=_fecha(mes, 25))
    db.add(h)
    db.flush()
    db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=msg, archivo="extracto.pdf", asunto=asunto, estado="procesado",
                          historial_id=h.id, recibido_en=datetime(2026, mes, 26)))
    return h


def _linea_faltante(fp, mes, dia, desc, monto, tipo, **extra):
    return {"fecha": _fecha(mes, dia), "descripcion": desc, "monto": monto, "tipo": tipo, "fingerprint": fp, "estado": "faltante",
            "categoria_sugerida": "Otros", **extra}


def _procesar(cuenta, texto, monkeypatch):
    monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: texto)
    r = client.post("/conciliacion/procesar", json={"cuenta_id": cuenta, "pdf_base64": "x"})
    assert r.status_code == 200, r.text
    fps = [i["fingerprint"] for i in r.json()["review"] if i["estado"] == "faltante"]
    ok = client.post(f"/conciliacion/historial/{r.json()['historial_id']}/importar", json={"fingerprints": fps})
    assert ok.status_code == 200, ok.text
    return r.json()["historial_id"]


def mundo(uid, monkeypatch, *, tarjetas=1, con_credito=True, tarjeta_extra=True, bancolombia=True):
    """Arma el caso real. `tarjetas` = cuántas cuentas de crédito del mismo banco (2 = ambiguo)."""
    como(uid)
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
        ahorro = Cuenta(usuario_id=uid, nombre="Nu Colombia", tipo="ahorro", saldo=0)
        db.add(ahorro)
        creditos = []
        for k in range(tarjetas if con_credito else 0):
            c = Cuenta(usuario_id=uid, nombre="Nu Colombia Crédito" + (f" {k + 1}" if tarjetas > 1 else ""), tipo="credito", saldo=0)
            db.add(c)
            creditos.append(c)
        db.flush()
        destino = creditos[0].id if creditos else ahorro.id
        _tarjeta_en(db, uid, ahorro, destino, 7, COMPRAS_JUL, con_pago=True, nueva=NUEVA_JUL)
        _tarjeta_en(db, uid, ahorro, destino, 8, COMPRAS_AGO)
        ids = {"ahorro": ahorro.id, "credito": creditos[0].id if creditos else None}
        if creditos and tarjeta_extra:
            dud = _tarjeta_en(db, uid, creditos[0], creditos[0].id, 9, [(2, "Tienda Cuatro SAS", 15_000.0)])
            # este extracto ya está en la tarjeta (compras como gasto) pero su lectura de hoy NO cuadra con el resumen
            for m in db.query(Movimiento).filter(Movimiento.cuenta_id == creditos[0].id):
                m.tipo = "expense"
                creditos[0].saldo -= 2 * m.monto
            DUDOSOS.add(f"m-{uid}-tarjeta-9")
            ids["tarjeta_dudosa"] = dud.id
        if bancolombia:
            b = Cuenta(usuario_id=uid, nombre="Bancolombia Ahorros", tipo="ahorro", saldo=1_000_000.0)
            db.add(b)
            db.flush()
            claras = [_linea_faltante("fp-b1", 8, 5, "Abono Cliente Inventado", 200_000.0, "income"),
                      _linea_faltante("fp-b2", 8, 9, "Compra Tienda Inventada", 50_000.0, "expense"),
                      _linea_faltante("fp-b3", 8, 12, "Compra Dudosa $30.000 $45.000", 30_000.0, "expense", lectura_dudosa=True)]
            ok = HistorialExtracto(usuario_id=uid, cuenta_id=b.id, banco_detectado="bancolombia", estado="pendiente_revision",
                                   total_movimientos=3, faltantes=3, review_json=json.dumps(claras), fecha_corte="2026-08-31",
                                   periodo_inicio="2026-08-01", saldo_inicial_extracto=1_000_000.0, saldo_final_extracto=1_120_000.0,
                                   saldos_origen="extracto")
            no = HistorialExtracto(usuario_id=uid, cuenta_id=b.id, banco_detectado="bancolombia", estado="pendiente_revision",
                                   total_movimientos=1, faltantes=1, fecha_corte="2026-09-30", periodo_inicio="2026-09-01",
                                   review_json=json.dumps([_linea_faltante("fp-b4", 9, 3, "Compra Que No Cuadra", 10_000.0, "expense")]),
                                   saldo_inicial_extracto=1_120_000.0, saldo_final_extracto=1_000_000.0, saldos_origen="extracto")
            db.add_all([ok, no])
            db.flush()
            ids.update(bancolombia=b.id, h_ok=ok.id, h_no=no.id)
        db.commit()
    finally:
        db.close()
    # Ahorros de Nu: se importan con el lector VIEJO (sin las líneas del resumen) y con correo
    ahorro_id = ids["ahorro"]
    viejo = lambda movs, texto, cuenta=None, **k: (movs, None)  # noqa: E731
    with monkeypatch.context() as mp:
        mp.setattr(rend, "con_rendimiento", viejo)
        mp.setattr(mod.rendimientos_extracto, "con_rendimiento", viejo)
        for n, texto in enumerate((AGO, SEP)):
            limites._eventos.clear()
            hid = _procesar(ahorro_id, texto, monkeypatch)
            msg = f"m-{uid}-ahorro-{n}"
            TEXTOS[msg] = texto
            db = SessionLocal()
            try:
                db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=msg, archivo="extracto.pdf", asunto="Extracto de tu cuenta de ahorros",
                                      estado="procesado", historial_id=hid))
                db.commit()
            finally:
                db.close()
    limites._eventos.clear()
    return ids


def foto(uid):
    db = SessionLocal()
    try:
        cuentas = {c.nombre: round(c.saldo, 2) for c in db.query(Cuenta).filter(Cuenta.usuario_id == uid)}
        nombre = {c.id: c.nombre for c in db.query(Cuenta).filter(Cuenta.usuario_id == uid)}
        movs = sorted((nombre.get(m.cuenta_id, "?"), m.descripcion, round(m.monto, 2), m.tipo, m.fecha.isoformat())
                      for m in db.query(Movimiento).filter(Movimiento.usuario_id == uid))
        hist = sorted((nombre.get(h.cuenta_id, "?"), h.estado, h.review_json) for h in
                      db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == uid))
        return {"cuentas": cuentas, "movs": movs, "hist": hist}
    finally:
        db.close()


def correr_todo(uid, max_pasos=1, rondas=15):
    """Llama varias veces, como lo hace la app, hasta que termina. Devuelve la última respuesta y cuántas llamadas hizo."""
    r, n = None, 0
    while n < rondas:
        db = SessionLocal()
        try:
            r = aa.correr(db, uid, max_pasos)
        finally:
            db.close()
        n += 1
        if r["estado"] == "listo":
            break
    return r, n


def n_filas(uid, **filtro):
    db = SessionLocal()
    try:
        return db.query(ArregloAuto).filter_by(usuario_id=uid, **filtro).count()
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════════════════
def test_el_caso_real_queda_ordenado_en_varias_llamadas_y_todo_queda_registrado(monkeypatch):
    uid = "aa-1"
    ids = mundo(uid, monkeypatch)
    antes = foto(uid)
    assert antes["cuentas"]["Nu Colombia Crédito"] == pytest.approx(-15_000.0 * 1)  # solo la compra de la tarjeta dudosa
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == ids["ahorro"], Movimiento.tipo == "income",
                                           Movimiento.descripcion.like("Tienda%")).count() == 2  # compras como ingreso
    finally:
        db.close()

    r, llamadas = correr_todo(uid, max_pasos=1)
    assert llamadas > 1, "con 1 relectura por llamada debe converger en varias aperturas"
    assert r["estado"] == "listo" and r["progreso"] == {"hecho": 6, "total": 6, "paso": None}
    despues = foto(uid)

    # (b) la tarjeta: extractos movidos, compras como gasto, pago corregido a $60.000, compra nueva importada
    assert despues["cuentas"]["Nu Colombia Crédito"] == pytest.approx(TARJETA_FINAL - 15_000.0)
    db = SessionLocal()
    try:
        tarjeta = db.query(Movimiento).filter(Movimiento.cuenta_id == ids["credito"], Movimiento.usuario_id == uid).all()
        por_desc = {m.descripcion: m for m in tarjeta}
        assert all(por_desc[d].tipo == "expense" for _, d, _ in COMPRAS_JUL + COMPRAS_AGO)
        assert por_desc[NUEVA_JUL[1]].tipo == "expense" and por_desc[NUEVA_JUL[1]].monto == NUEVA_JUL[2]
        assert por_desc[DESC_PAGO].monto == PAGO_A and por_desc[DESC_PAGO].tipo == "income"
        assert DESC_PAGO_VIEJA not in por_desc
        assert db.query(Movimiento).filter(Movimiento.cuenta_id == ids["ahorro"], Movimiento.descripcion.like("Tienda%")).count() == 0
        # (c) rendimientos / 4x1000 / costos: el ahorro queda como dice el banco
        cats = {m.categoria for m in db.query(Movimiento).filter(Movimiento.cuenta_id == ids["ahorro"])}
        assert {"Rendimientos", "4x1000 (GMF)", "Comisiones y seguros"} <= cats
        # (d) lo verificado se importó; lo dudoso NO
        b = {m.descripcion: m for m in db.query(Movimiento).filter(Movimiento.cuenta_id == ids["bancolombia"])}
        assert "Abono Cliente Inventado" in b and "Compra Tienda Inventada" in b
        assert not any("Dudosa" in d or "Que No Cuadra" in d for d in b)
        h_ok, h_no = db.get(HistorialExtracto, ids["h_ok"]), db.get(HistorialExtracto, ids["h_no"])
        assert [i["estado"] for i in json.loads(h_ok.review_json)] == ["importado", "importado", "faltante"]
        assert json.loads(h_no.review_json)[0]["estado"] == "faltante"
        # la tarjeta de lectura dudosa quedó intacta (ni relectura ni correcciones)
        dud = db.get(HistorialExtracto, ids["tarjeta_dudosa"])
        assert [i["estado"] for i in json.loads(dud.review_json)] == ["importado"] and dud.lectura_json is None
    finally:
        db.close()
    assert despues["cuentas"]["Nu Colombia"] == pytest.approx(AHORRO_FINAL)  # ahorros = lo que dice el banco, al peso

    # (e) y el cuadre por cuenta
    cuadre = {c["cuenta"]: c for c in r["cuadre"]}
    assert cuadre["Nu Colombia"]["estado"] == "cuadra" and cuadre["Nu Colombia"]["texto"] == "Cuadra todos los meses"
    # lo que quedó para la persona
    tipos = {d["tipo"]: d["cantidad"] for d in r["decisiones"]}
    assert tipos["dudosas"] >= 2 and tipos["tarjeta_sin_verificar"] == 1
    # el lote lo cuenta
    resumen = r["resumen"]
    c = resumen["contadores"]
    assert c["extractos_movidos"] == 2 and c["compras_corregidas"] == 3 and c["pagos_corregidos"] == 1
    assert c["rendimientos_registrados"] == 5 and c["lineas_importadas"] >= 3
    assert resumen["texto"].startswith("Listo, ordené tus cuentas: moví 2 extractos a tu tarjeta, corregí 3 compras")
    nombres = {x["cuenta"]: x for x in resumen["cuentas"]}
    assert nombres["Nu Colombia Crédito"]["saldo_antes"] == pytest.approx(-15_000.0)
    assert nombres["Nu Colombia"]["saldo_despues"] == pytest.approx(AHORRO_FINAL)
    # arreglos_auto trae el detalle por tipo, con antes y después
    db = SessionLocal()
    try:
        filas = db.query(ArregloAuto).filter(ArregloAuto.usuario_id == uid).all()
        tipos_fila = {f.tipo for f in filas}
        assert {"mover_cuenta", "corregir_tipo", "corregir_monto", "crear_linea", "historial", "saldo"} <= tipos_fila
        assert len({f.lote_id for f in filas}) == 1
        pago = next(f for f in filas if f.tipo == "corregir_monto")
        assert json.loads(pago.antes)["monto"] == PAGO_B and json.loads(pago.despues)["monto"] == PAGO_A
        # no se guarda nada de correos: solo montos, ids y descripciones del movimiento
        assert all("asunto" not in (f.antes or "") for f in filas)
    finally:
        db.close()
    # el patrimonio total es el que dicen los extractos
    assert sum(despues["cuentas"].values()) == pytest.approx(AHORRO_FINAL + TARJETA_FINAL - 15_000.0 + 1_000_000.0 + 200_000.0 - 50_000.0)
    assert antes["movs"] != despues["movs"]


def test_segunda_corrida_no_cambia_nada(monkeypatch):
    uid = "aa-2"
    mundo(uid, monkeypatch)
    correr_todo(uid, max_pasos=3)
    f1, filas1 = foto(uid), n_filas(uid)
    r, _ = correr_todo(uid, max_pasos=3)
    assert foto(uid) == f1 and n_filas(uid) == filas1
    assert r["estado"] == "listo" and r["cambios"] == 0 and r["lote_id"] is None


def test_deshacer_el_lote_restaura_saldos_tipos_y_extractos(monkeypatch):
    uid = "aa-3"
    mundo(uid, monkeypatch)
    inicial = foto(uid)
    r, _ = correr_todo(uid, max_pasos=3)
    lote = r["resumen"]["lote_id"]
    assert foto(uid) != inicial

    como(uid)
    ls = client.get("/autoarreglo/lotes").json()["lotes"]
    assert [x["lote_id"] for x in ls] == [lote] and ls[0]["deshacible"] and ls[0]["cuentas"]
    d = client.post(f"/autoarreglo/lotes/{lote}/deshacer")
    assert d.status_code == 200, d.text
    assert d.json()["ya_deshecho"] is False
    assert foto(uid) == inicial  # saldos, tipos, cuentas y extractos exactamente como estaban
    # idempotente
    d2 = client.post(f"/autoarreglo/lotes/{lote}/deshacer")
    assert d2.status_code == 200 and d2.json()["ya_deshecho"] is True and foto(uid) == inicial
    assert client.get("/autoarreglo/lotes").json()["lotes"][0]["revertido"] is True
    # tras deshacer, el orden automático descansa (no vuelve a hacer lo mismo en cuanto abres la app)
    db = SessionLocal()
    try:
        assert aa.correr(db, uid, 3)["pausado"] is True
    finally:
        db.close()
    assert foto(uid) == inicial


def test_deshacer_da_409_si_algo_posterior_lo_hizo_inconsistente(monkeypatch):
    uid = "aa-4"
    mundo(uid, monkeypatch)
    r, _ = correr_todo(uid, max_pasos=3)
    lote = r["resumen"]["lote_id"]
    db = SessionLocal()
    try:  # la persona editó a mano una compra que el autoarreglo había corregido
        m = db.query(Movimiento).filter(Movimiento.usuario_id == uid, Movimiento.descripcion == "Tienda Uno SAS").first()
        m.monto = 41_000.0
        db.commit()
    finally:
        db.close()
    despues = foto(uid)
    como(uid)
    d = client.post(f"/autoarreglo/lotes/{lote}/deshacer")
    assert d.status_code == 409 and "no cambié nada" in d.json()["detail"]
    assert foto(uid) == despues  # nada a medias


def test_varias_tarjetas_candidatas_no_mueve_nada_y_avisa(monkeypatch):
    uid = "aa-5"
    mundo(uid, monkeypatch, tarjetas=2, tarjeta_extra=False, bancolombia=False)
    antes = foto(uid)
    r, _ = correr_todo(uid, max_pasos=3)
    assert {d["tipo"] for d in r["decisiones"]} >= {"varias_tarjetas"}
    despues = foto(uid)
    # los extractos de tarjeta siguen en ahorros, sus compras siguen como ingreso y la tarjeta sigue en cero
    assert [m for m in despues["movs"] if m[1].startswith("Tienda") or m[1].startswith("Supermercado")] == \
        [m for m in antes["movs"] if m[1].startswith("Tienda") or m[1].startswith("Supermercado")]
    assert despues["cuentas"]["Nu Colombia Crédito 1"] == 0 == despues["cuentas"]["Nu Colombia Crédito 2"]
    assert n_filas(uid, tipo="mover_cuenta") == 0


def test_tarjeta_sin_cuenta_de_credito_no_se_toca(monkeypatch):
    uid = "aa-6"
    mundo(uid, monkeypatch, con_credito=False, tarjeta_extra=False, bancolombia=False)
    antes = [m for m in foto(uid)["movs"] if m[1].startswith("Tienda") or m[1].startswith("Supermercado")]
    r, _ = correr_todo(uid, max_pasos=3)
    assert [m for m in foto(uid)["movs"] if m[1].startswith("Tienda") or m[1].startswith("Supermercado")] == antes
    assert n_filas(uid, tipo="mover_cuenta") == 0 and n_filas(uid, tipo="corregir_tipo") == 0


def test_modo_hoy_lo_anterior_al_inicio_no_se_importa(monkeypatch):
    uid = "aa-7"
    mundo(uid, monkeypatch, tarjeta_extra=False)
    db = SessionLocal()
    try:  # «solo desde hoy»: el extracto de agosto de Bancolombia quedó antes del inicio
        db.add(AjusteUsuario(usuario_id=uid, punto_partida_modo="hoy", punto_partida_fecha=datetime(2026, 9, 1).date()))
        db.commit()
    finally:
        db.close()
    correr_todo(uid, max_pasos=3)
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == uid, Movimiento.descripcion == "Abono Cliente Inventado").count() == 0
    finally:
        db.close()


def test_saldo_fijado_a_mano_no_se_recalcula(monkeypatch):
    uid = "aa-8"
    como(uid)
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free"))
        c = Cuenta(usuario_id=uid, nombre="Cuenta Fijada", tipo="ahorro", saldo=777_000.0)  # sin movimientos que lo expliquen
        db.add(c)
        db.flush()
        db.add(HistorialExtracto(usuario_id=uid, cuenta_id=c.id, banco_detectado="x", estado="conciliado", review_json="[]",
                                 fecha_corte="2026-08-31", periodo_inicio="2026-08-01", saldo_inicial_extracto=100_000.0,
                                 saldo_final_extracto=150_000.0, saldos_origen="extracto"))
        db.commit()
    finally:
        db.close()
    r, _ = correr_todo(uid)
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == uid).count() == 0
        assert db.query(Cuenta).filter(Cuenta.usuario_id == uid).first().saldo == 777_000.0
    finally:
        db.close()
    assert r["cambios"] == 0


def test_no_toca_movimientos_manuales_ni_de_correo(monkeypatch):
    uid = "aa-9"
    ids = mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)
    db = SessionLocal()
    try:
        for fuente, desc in (("manual", "Tienda Uno SAS"), ("correo", "Tienda Dos SAS")):
            db.add(Movimiento(usuario_id=uid, cuenta_id=ids["ahorro"], descripcion=desc, categoria="Otros", tipo="income", monto=777.0,
                              fecha=datetime(2026, 7, 3), fuente=fuente))
        db.commit()
    finally:
        db.close()
    correr_todo(uid, max_pasos=3)
    db = SessionLocal()
    try:
        raros = db.query(Movimiento).filter(Movimiento.usuario_id == uid, Movimiento.monto == 777.0).all()
        assert len(raros) == 2 and all(m.cuenta_id == ids["ahorro"] and m.tipo == "income" for m in raros)
    finally:
        db.close()


def test_limite_por_hora_de_relecturas_se_respeta(monkeypatch):
    uid = "aa-10"
    mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)
    monkeypatch.setattr(aa, "LIMITE_RELECTURAS_HORA", 1)
    db = SessionLocal()
    try:
        r1 = aa.correr(db, uid, 3)
        gmail_tarjetas = n_filas(uid, tipo="mover_cuenta")
        r2 = aa.correr(db, uid, 3)  # el tope por hora ya se gastó: no relee nada más
    finally:
        db.close()
    assert r1["limite_alcanzado"] is True and r2["limite_alcanzado"] is True
    assert r2["estado"] == "listo" and r2["quedan_por_hacer"] is True
    assert n_filas(uid, tipo="mover_cuenta") == gmail_tarjetas  # no avanzó
    limites._eventos.clear()  # pasó la hora: sigue donde se quedó
    db = SessionLocal()
    try:
        monkeypatch.setattr(aa, "LIMITE_RELECTURAS_HORA", 24)
        aa.correr(db, uid, 3)
    finally:
        db.close()
    assert n_filas(uid, tipo="mover_cuenta") > gmail_tarjetas


def test_candado_un_lote_por_usuario_y_vence(monkeypatch):
    uid = "aa-11"
    mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)
    antes = foto(uid)
    db = SessionLocal()
    try:
        token = aa.tomar_candado(db, uid)
        assert token and aa.tomar_candado(db, uid) is None  # la segunda llamada simultánea no entra
        r = aa.correr(db, uid, 3)
        assert r["estado"] == "trabajando" and r["ocupado"] is True and foto(uid) == antes  # y no duplica ni cambia nada
        aa.soltar_candado(db, uid, token)
        # un candado viejo (proceso caído) se reemplaza
        db.add(MarcaCron(usuario_id=uid, clave=aa.CLAVE_CANDADO, valor=(datetime.utcnow() - timedelta(hours=1)).isoformat() + "|x"))
        db.commit()
        nuevo = aa.tomar_candado(db, uid)
        assert nuevo is not None
        aa.soltar_candado(db, uid, nuevo)
        assert db.query(MarcaCron).filter(MarcaCron.usuario_id == uid, MarcaCron.clave == aa.CLAVE_CANDADO).count() == 0
    finally:
        db.close()


def test_un_paso_que_falla_no_rompe_los_demas(monkeypatch):
    uid = "aa-12"
    mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)

    def roto(ctx):
        raise RuntimeError("boom")

    monkeypatch.setitem(aa._EJECUTORES, "ajustes", roto)
    r, _ = correr_todo(uid, max_pasos=3)
    est = {p["paso"]: p["estado"] for p in r["pasos"]}
    assert est["ajustes"] == "fallo" and est["tarjetas"] == "ok" and est["inicial"] == "ok"
    assert n_filas(uid, tipo="mover_cuenta") > 0  # lo demás sí se hizo


def test_endpoint_correr_responde_rapido_y_nunca_lanza(monkeypatch):
    uid = "aa-13"
    mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)
    como(uid)
    r = client.post("/autoarreglo/correr")
    assert r.status_code == 200
    j = r.json()
    assert j["estado"] in ("trabajando", "listo") and set(j["progreso"]) == {"hecho", "total", "paso"} and j["progreso"]["total"] == 6
    # una falla interna se responde como «listo» con error, nunca como 500
    monkeypatch.setattr(aa, "_foto", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    limites._eventos.clear()
    r2 = client.post("/autoarreglo/correr")
    assert r2.status_code == 200 and r2.json()["estado"] == "listo" and r2.json().get("error") is True


def test_aislamiento_otro_usuario_no_ve_ni_deshace_mis_lotes(monkeypatch):
    uid = "aa-14"
    mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)
    r, _ = correr_todo(uid, max_pasos=3)
    lote = r["resumen"]["lote_id"]
    despues = foto(uid)
    como("aa-14-otro")
    assert client.get("/autoarreglo/lotes").json() == {"lotes": []}
    assert client.post(f"/autoarreglo/lotes/{lote}/deshacer").status_code == 404
    assert foto(uid) == despues and n_filas(uid) > 0
    db = SessionLocal()
    try:
        assert db.query(ArregloAuto).filter(ArregloAuto.usuario_id == "aa-14-otro").count() == 0
    finally:
        db.close()


def test_derechos_del_titular_exportan_y_borran_arreglos_auto(monkeypatch):
    from app import derechos_titular as dt

    uid = "aa-15"
    mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)
    correr_todo(uid, max_pasos=3)
    db = SessionLocal()
    try:
        assert len(dt.recopilar(db, uid).get("arreglos_auto", [])) > 0
        dt.borrar_todo(db, uid)
    finally:
        db.close()
    assert n_filas(uid) == 0


def test_la_tabla_no_viaja_en_los_respaldos():
    from app import backup

    assert "arreglos_auto" in backup.TABLAS_NO_RESPALDADAS


def test_el_cron_diario_ordena_las_cuentas_de_quien_tiene_gmail(monkeypatch):
    uid = "aa-16"
    mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)
    llamados = []
    monkeypatch.setattr(router_correos, "_lote_de_sincronizacion", lambda db, u, p, tipo="todo", **k: (None, 0, 0))
    monkeypatch.setattr(router_correos.autoarreglo, "correr_seguro", lambda db, u, *a, **k: llamados.append((u, k.get("origen"))))
    db = SessionLocal()
    try:
        db.query(Perfil).filter(Perfil.usuario_id != uid).update({Perfil.gmail_conectado: False})
        ahora = datetime.utcnow()
        db.add(Consentimiento(usuario_id=uid, version="1.1", finalidad="lectura_correo", aceptado=True,
                              creado_en_utc=ahora, creado_en_co=ahora))
        db.commit()
    finally:
        db.close()
    r = client.post("/correos/cron/sincronizar", headers={"X-Cron-Secret": "secreto-de-prueba"})
    assert r.status_code == 200, r.text
    assert (uid, "cron") in llamados and r.json()["ordenados"] == len(llamados)


def test_pedir_marca_que_algo_cambio_y_correr_la_limpia(monkeypatch):
    uid = "aa-17"
    mundo(uid, monkeypatch, tarjeta_extra=False, bancolombia=False)
    db = SessionLocal()
    try:
        aa.pedir(db, uid)
        assert db.query(MarcaCron).filter(MarcaCron.usuario_id == uid, MarcaCron.clave == aa.CLAVE_PEDIDO).count() == 1
        aa.correr(db, uid, 1)
        assert db.query(MarcaCron).filter(MarcaCron.usuario_id == uid, MarcaCron.clave == aa.CLAVE_PEDIDO).count() == 0
    finally:
        db.close()
