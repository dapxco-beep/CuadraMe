"""«Arreglar mis extractos de la tarjeta»: mover a la tarjeta + releer en modo «solo agregar», en un paso.
Gmail y lector simulados; datos 100 % inventados."""
import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'arreglar_tarjetas.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import arreglar_tarjetas as at  # noqa: E402
from app import limites  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import compute_fingerprint  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, HuellaOrigen, Movimiento, Perfil  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)


class _Exec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class GmailFalso:
    def __init__(self, caidos=()):
        self.llamadas, self.caidos = 0, set(caidos)

    def users(self): return self
    def messages(self): return self

    def get(self, **kw):
        self.llamadas += 1
        if kw["id"] in self.caidos:
            raise RuntimeError("sin red")
        return _Exec({"id": kw["id"]})


LECTURAS: dict[str, list[dict]] = {}  # texto (= id del mensaje) -> líneas que lee el lector de hoy


@pytest.fixture(autouse=True)
def _simulado(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setattr(rx, "listar_adjuntos_pdf", lambda msg: [{"archivo": "tarjeta.pdf", "attachment_id": msg["id"]}])
    monkeypatch.setattr(rx, "descargar_adjunto", lambda g, m, a: m.encode())
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("ok", pdf.decode(), None))
    monkeypatch.setattr(rx, "_leer_lineas", lambda texto: [dict(m) for m in LECTURAS.get(texto, [])])
    yield
    app.dependency_overrides.clear()


def _linea(dia, desc, monto, mes):
    return {"fecha": f"2026-{mes:02d}-{dia:02d}", "descripcion": desc, "monto": float(monto), "tipo": "expense"}


def _mundo(uid, monkeypatch, banco="Nu", gmail=None, con_credito=True, meses_credito=(5, 6), meses_ahorro=(7, 8, 9, 10),
           lineas_ahorro=(2, 18, 13, 3), asunto="Extracto de tu tarjeta de crédito"):
    """2 extractos en la tarjeta (1 línea cada uno) y 4 en la cuenta de ahorros (con líneas ya importadas).
    Cada uno tiene UNA línea más que el lector de hoy sí lee (la «nueva»)."""
    gmail = gmail or GmailFalso()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="Persona Prueba")
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: gmail)
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
        ahorro = Cuenta(usuario_id=uid, nombre=f"{banco} Colombia", tipo="ahorro", saldo=5_000_000)
        credito = Cuenta(usuario_id=uid, nombre=f"{banco} Colombia Crédito", tipo="credito", saldo=0) if con_credito else None
        db.add(ahorro)
        if credito:
            db.add(credito)
        db.flush()
        ids, saldo_ahorro, saldo_credito = [], 5_000_000.0, 0.0
        for mes, n in [(m, 1) for m in meses_credito] + list(zip(meses_ahorro, lineas_ahorro)):
            en_credito = mes in meses_credito
            cuenta = credito if en_credito else ahorro
            review, leidas = [], []
            for k in range(n):
                dia, desc, monto = 1 + k, f"COMERCIO {mes}-{k} SAS", 10_000 + 1000 * k + mes
                it = _linea(dia, desc, monto, mes)
                fp = compute_fingerprint(it["fecha"], monto, cuenta.id, desc, "expense")
                m = Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=desc, categoria="Otros", tipo="expense",
                               monto=monto, fecha=datetime(2026, mes, dia), fuente="conciliacion_extracto", origen="extracto",
                               huella_externa=f"ext:{fp}#1")
                db.add(m)
                db.flush()
                db.add(HuellaOrigen(usuario_id=uid, movimiento_id=m.id, huella=f"ext:{fp}#1", origen="extracto",
                                    cuenta_id=cuenta.id, tipo="expense", monto=monto, fecha=m.fecha))
                review.append({**it, "fingerprint": fp, "estado": "importado", "movimiento_id": m.id})
                leidas.append(dict(it))
                if en_credito:
                    saldo_credito -= monto
                else:
                    saldo_ahorro -= monto
            leidas.append(_linea(20, f"COMPRA NUEVA {mes} SAS", 7000 + mes, mes))  # la que el lector viejo no leía
            msg = f"m-{uid}-{mes}"
            LECTURAS[msg] = leidas
            h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta.id, banco_detectado=banco.lower(), estado="conciliado",
                                  total_movimientos=n, importados=n, review_json=json.dumps(review),
                                  fecha_corte=f"2026-{mes:02d}-25")
            db.add(h)
            db.flush()
            db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id=msg, archivo="tarjeta.pdf", asunto=asunto, estado="procesado",
                                  historial_id=h.id, recibido_en=datetime(2026, mes, 26)))
            ids.append(h.id)
        ahorro.saldo = saldo_ahorro
        if credito:
            credito.saldo = saldo_credito
        db.commit()
        return dict(historiales=ids, ahorro=ahorro.id, credito=credito.id if credito else None, gmail=gmail)
    finally:
        db.close()


def _foto(uid):
    db = SessionLocal()
    try:
        cuentas = {c.id: c.saldo for c in db.query(Cuenta).filter(Cuenta.usuario_id == uid).all()}
        movs = db.query(Movimiento).filter(Movimiento.usuario_id == uid).all()
        hist = {h.id: (h.cuenta_id, h.estado, h.faltantes, h.review_json) for h in
                db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == uid).all()}
        return cuentas, sorted((m.cuenta_id, m.descripcion, m.monto) for m in movs), hist
    finally:
        db.close()


def _arreglar():
    limites._eventos.clear()
    return client.post("/conciliacion/tarjetas/arreglar", json={"confirmar": True})


def test_caso_del_usuario_todo_a_la_tarjeta_sin_duplicar(monkeypatch):
    m = _mundo("at-1", monkeypatch)
    cuentas0, movs0, _ = _foto("at-1")

    p = client.get("/conciliacion/tarjetas/arreglar/previa")
    assert p.status_code == 200
    pj = p.json()
    assert pj["total"] == 6 and pj["movimientos_a_mover"] == 2 + 18 + 13 + 3
    assert [e["mes"] for e in pj["extractos"]] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]  # viejo -> nuevo
    ago = pj["extractos"][3]
    assert ago["cuenta_actual"]["nombre"] == "Nu Colombia" and ago["cuenta_destino"]["nombre"] == "Nu Colombia Crédito"
    assert ago["movera"] == 18 and ago["releera"] and ago["puede_releerse"] and not ago["requiere_clave"]
    assert pj["saldos"]["total_antes"] == pj["saldos"]["total_despues"]  # solo se pasan movimientos entre cuentas
    assert _foto("at-1")[0] == cuentas0 and m["gmail"].llamadas == 0  # la previa no cambia ni toca Gmail

    r = _arreglar()
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["arreglados"] == 6 and j["saltados"] == 0 and j["movidos"] == 36 and j["por_importar"] == 6
    assert j["resumen"].startswith("Arreglé 6 extractos: moví 36 movimientos a tu tarjeta, encontré 6 compras por importar")

    cuentas1, movs1, hist1 = _foto("at-1")
    assert all(v[0] == m["credito"] and v[1] == "pendiente_revision" and v[2] == 1 for v in hist1.values())
    assert len(movs1) == len(movs0)  # nada duplicado ni importado solo
    assert sum(cuentas1.values()) == pytest.approx(sum(cuentas0.values()))  # el patrimonio no cambia
    assert cuentas1[m["ahorro"]] == 5_000_000.0 and cuentas1[m["credito"]] == pytest.approx(sum(cuentas0.values()) - 5_000_000)
    db = SessionLocal()
    try:
        assert db.query(Movimiento).filter(Movimiento.usuario_id == "at-1", Movimiento.cuenta_id == m["ahorro"]).count() == 0
        for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == "at-1"):
            review = json.loads(h.review_json)
            assert [i["estado"] for i in review].count("faltante") == 1
            assert any(i["estado"] == "faltante" and i["descripcion"].startswith("COMPRA NUEVA") for i in review)
    finally:
        db.close()


def test_idempotente(monkeypatch):
    m = _mundo("at-2", monkeypatch)
    assert _arreglar().json()["arreglados"] == 6
    antes, llamadas = _foto("at-2"), m["gmail"].llamadas
    j = _arreglar().json()
    assert j["arreglados"] == 0 and j["sin_cambios"] and "ya estaban bien" in j["resumen"]
    assert _foto("at-2") == antes and m["gmail"].llamadas == llamadas
    assert client.get("/conciliacion/tarjetas/arreglar/previa").json()["total"] == 0


def test_la_segunda_relectura_con_otra_version_no_duplica_lo_movido(monkeypatch):
    """Las huellas de lo importado llevan el id de la cuenta vieja: al releer ya en la tarjeta se reconocen por
    comercio/día/monto y NO vuelven a salir como «por importar»."""
    _mundo("at-3", monkeypatch)
    _arreglar()
    antes = _foto("at-3")
    monkeypatch.setattr(rx, "VERSION_LECTOR", "otra-version")
    j = _arreglar().json()
    assert j["por_importar"] == 0 and j["movidos"] == 0
    cuentas, movs, hist = _foto("at-3")
    assert movs == antes[1] and all(v[2] == 1 for v in hist.values())  # sigue 1 faltante por extracto (la nueva)


def test_falla_de_un_extracto_se_salta_y_sigue(monkeypatch):
    uid = "at-4"
    gmail = GmailFalso(caidos={f"m-{uid}-6"})  # el de junio (ya en la tarjeta) no se puede traer
    m = _mundo(uid, monkeypatch, gmail=gmail)
    j = _arreglar().json()
    assert j["arreglados"] == 5 and j["saltados"] == 1
    saltado = next(r for r in j["resultados"] if r["estado"] == "saltado")
    assert saltado["mes"] == "2026-06" and "No pudimos releerlo" in saltado["motivo"]
    assert "quedó para después" in j["resumen"]
    gmail.caidos.clear()
    j2 = _arreglar().json()
    assert j2["arreglados"] == 1 and j2["por_importar"] == 1  # solo queda el que falló
    assert all(v[0] == m["credito"] for v in _foto(uid)[2].values())


def test_pdf_con_clave_que_no_abre_se_salta(monkeypatch):
    uid = "at-5"
    _mundo(uid, monkeypatch)
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("falta_clave", "", None) if b"-8" in pdf else ("ok", pdf.decode(), None))
    j = _arreglar().json()
    r8 = next(r for r in j["resultados"] if r["mes"] == "2026-08")
    # Ya se movió a su tarjeta (eso no necesita el PDF); solo la relectura queda para después.
    assert r8["estado"] == "parcial" and r8["movidos"] == 18 and "clave" in r8["motivo"]
    assert j["saltados"] == 1 and j["arreglados"] == 6


def test_otro_banco_sin_lector_propio(monkeypatch):
    _mundo("at-6", monkeypatch, banco="Davivienda")
    j = _arreglar().json()
    assert j["arreglados"] == 6 and j["movidos"] == 36 and j["por_importar"] == 6


def test_sin_tarjeta_de_credito_del_banco_no_se_toca(monkeypatch):
    m = _mundo("at-7", monkeypatch, con_credito=False, meses_credito=())
    antes = _foto("at-7")
    pj = client.get("/conciliacion/tarjetas/arreglar/previa").json()
    assert pj["total"] == 0 and pj["total_tarjeta"] == 4
    j = _arreglar().json()
    assert j["sin_cambios"] and _foto("at-7") == antes and m["gmail"].llamadas == 0


def test_dos_tarjetas_del_banco_no_adivina(monkeypatch):
    uid = "at-8"
    _mundo(uid, monkeypatch, meses_credito=())
    db = SessionLocal()
    db.add(Cuenta(usuario_id=uid, nombre="Nu Colombia Platino Crédito", tipo="credito", saldo=0))
    db.add(Cuenta(usuario_id=uid, nombre="Nu Colombia Oro Crédito", tipo="credito", saldo=0))
    db.commit()
    db.close()
    assert client.get("/conciliacion/tarjetas/arreglar/previa").json()["total"] == 0


def test_lectura_que_no_cuadra_no_agrega_nada(monkeypatch):
    uid = "at-9"
    m = _mundo(uid, monkeypatch, meses_credito=(5,), meses_ahorro=(), lineas_ahorro=())
    malo = {"resumen_tarjeta": {}, "verificacion": [], "lectura_completa": False, "lineas_leidas": 2,
            "mensaje_lectura": "Leí 2 líneas pero faltan $5.000 para sumar lo que dice tu extracto. Revisa antes de importar"}
    monkeypatch.setattr(rx, "es_extracto_tarjeta_nu", lambda t: True)
    monkeypatch.setattr(rx, "leer_extracto_tarjeta_nu", lambda t: dict(malo))
    antes = _foto(uid)[1]
    j = _arreglar().json()
    r = j["resultados"][0]
    assert j["por_importar"] == 0 and r["lectura_completa"] is False and "faltan $5.000" in r["mensaje_lectura"]
    cuentas, movs, hist = _foto(uid)
    h = next(iter(hist.values()))
    assert h[1] == "conciliado" and h[2] in (0, None) and movs == antes  # sigue conciliado: nada agregado ni importado
    assert json.loads(h[3])[0]["estado"] == "importado"


def test_lectura_que_cuadra_lo_dice(monkeypatch):
    _mundo("at-10", monkeypatch, meses_credito=(5,), meses_ahorro=(), lineas_ahorro=())
    bien = {"resumen_tarjeta": {}, "verificacion": [], "lectura_completa": True, "lineas_leidas": 2,
            "mensaje_lectura": "Leí 2 líneas y suman lo que dice tu extracto ✓"}
    monkeypatch.setattr(rx, "es_extracto_tarjeta_nu", lambda t: True)
    monkeypatch.setattr(rx, "leer_extracto_tarjeta_nu", lambda t: dict(bien))
    r = _arreglar().json()["resultados"][0]
    assert r["lectura_completa"] is True and r["lineas_leidas"] == 2 and "suman lo que dice tu extracto ✓" in r["mensaje_lectura"]
    assert r["nuevas"] == 1


def test_maximo_12_por_llamada_y_limite_por_hora(monkeypatch):
    uid = "at-11"
    _mundo(uid, monkeypatch, meses_credito=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12), meses_ahorro=(), lineas_ahorro=())
    db = SessionLocal()
    extra = HistorialExtracto(usuario_id=uid, cuenta_id=db.query(Cuenta).filter(Cuenta.usuario_id == uid, Cuenta.tipo == "credito").first().id,
                              banco_detectado="nu", estado="conciliado", review_json="[]", fecha_corte="2027-01-25")
    db.add(extra)
    db.flush()
    LECTURAS["m-extra"] = [_linea(3, "OTRA COMPRA SAS", 9000, 12)]
    db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id="m-extra", archivo="tarjeta.pdf", asunto="Extracto tarjeta de crédito",
                          estado="procesado", historial_id=extra.id, recibido_en=datetime(2027, 1, 26)))
    db.commit()
    db.close()
    j = _arreglar().json()
    assert j["arreglados"] == 12 and j["restantes"] == 1 and "Quedan 1 por arreglar" in j["resumen"]
    assert _arreglar().json()["arreglados"] == 1
    # El lote cuenta como UNA llamada frente al límite por hora (6): la séptima seguida se frena.
    limites._eventos.clear()
    for _ in range(6):
        assert client.post("/conciliacion/tarjetas/arreglar", json={"confirmar": True}).status_code == 200
    assert client.post("/conciliacion/tarjetas/arreglar", json={"confirmar": True}).status_code == 429


def test_pide_confirmar(monkeypatch):
    _mundo("at-12", monkeypatch)
    antes = _foto("at-12")
    assert client.post("/conciliacion/tarjetas/arreglar", json={"confirmar": False}).status_code == 400
    assert _foto("at-12") == antes


def test_aislamiento_entre_usuarios(monkeypatch):
    m = _mundo("at-13", monkeypatch)
    antes = _foto("at-13")
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="at-13-otro", email="o@t.com", nombre="Otra Persona")
    assert client.get("/conciliacion/tarjetas/arreglar/previa").json()["total"] == 0
    j = _arreglar().json()
    assert j["sin_cambios"] and j["resultados"] == []
    assert _foto("at-13") == antes and m["gmail"].llamadas == 0


# ── Reconciliación pura (sin base de datos) ───────────────────────────────────────────────────────────────
def test_reconciliar_solo_agregar_no_toca_lo_existente():
    viejo = [{"fecha": "2026-08-02", "descripcion": "TIENDA A", "monto": 10000.0, "tipo": "expense",
              "fingerprint": "fp-vieja-cuenta-ahorros", "estado": "importado", "movimiento_id": "m1"}]
    nuevas = [{"fecha": "2026-08-02", "descripcion": "TIENDA A", "monto": 10000.0, "tipo": "expense", "cuenta": "tarjeta"},
              {"fecha": "2026-08-09", "descripcion": "TIENDA B", "monto": 5000.0, "tipo": "expense", "cuenta": "tarjeta"}]
    review, res = rx.reconciliar(viejo, nuevas, solo_agregar=True)
    assert res["reconocidas"] == 1 and res["por_importar"] == 1 and res["quitadas"] == 0
    assert viejo[0]["estado"] == "importado" and viejo[0]["movimiento_id"] == "m1" and viejo[0]["fingerprint"] == "fp-vieja-cuenta-ahorros"
    assert [i["estado"] for i in review] == ["importado", "faltante"]
    # Segunda vez con la huella alterna anotada: nada cambia.
    review2, res2 = rx.reconciliar(review, nuevas, solo_agregar=True)
    assert (res2["agregadas"], res2["por_importar"], res2["reconocidas"]) == (0, 0, 0) and review2 is review


def test_de_a_uno_con_excluir_para_mostrar_el_avance(monkeypatch):
    """La app arregla de a uno («Arreglando 3 de 6…») y no repite los que ya intentó, aunque se hayan saltado."""
    uid = "at-14"
    gmail = GmailFalso(caidos={f"m-{uid}-5"})
    _mundo(uid, monkeypatch, gmail=gmail)
    limites._eventos.clear()
    intentados, resultados = [], []
    for paso in range(8):
        r = client.post("/conciliacion/tarjetas/arreglar",
                        json={"confirmar": True, "maximo": 1, "excluir": intentados, "continuar": paso > 0}).json()
        if not r["resultados"]:
            break
        resultados += r["resultados"]
        intentados += [x["historial_id"] for x in r["resultados"]]
    assert [x["mes"] for x in resultados] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    assert [x["estado"] for x in resultados].count("saltado") == 1 and sum(x["movidos"] for x in resultados) == 36
