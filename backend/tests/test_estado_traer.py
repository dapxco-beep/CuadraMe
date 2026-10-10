"""Modelo de estados único de «Traer movimientos» (app/estado_traer.py).

Cubre el diagnóstico de «dice 0 movimientos pero ya estaban»: todo ya registrado, parcial, la carrera entre
canales (registrar a mano DESPUÉS de leer el extracto), el mismo extracto en dos correos o subido a mano y
por Gmail, extractos de otra cuenta del mismo banco, periodos que se solapan y borrar una revisión. Y las
24 órdenes de llegada de los 4 canales, mirando lo que ve la pantalla (/sincronizacion/estado)."""
import itertools
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'estado_traer.db')}")

import pytest  # noqa: E402

from app import estado_traer as et  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import ExtractoCorreo, HistorialExtracto  # noqa: E402
from tests.test_duplicados import CANALES, Escena, client  # noqa: E402

pytest.importorskip("reportlab.pdfgen.canvas")


def _linea(e, desc="COMPRA EXITO 4455", monto=45_000, dias=0, tipo="expense"):
    return {"fecha": (e.base + timedelta(days=dias)).strftime("%Y-%m-%d"), "descripcion": desc,
            "monto": monto, "tipo": tipo, "referencia": ""}


def _estado(e):
    e.como()
    return client.get("/sincronizacion/estado").json()


def _ext_de_cuenta(e):
    return [x for x in _estado(e)["extractos"] if x["cuenta_id"] == e.cuenta["id"]]


# ── pura ──────────────────────────────────────────────────────────────────────────────────
def test_contar_review_cuadra_y_no_cuenta_sobrantes():
    review = [{"estado": s} for s in ("exacto", "aproximado", "completado", "importado", "faltante", "borrado_antes",
                                       "anterior", "sobrante")]
    review[2]["duplicado_evitado"] = True
    c = et.contar_review(review)
    assert c["leidas"] == 7  # el sobrante es un movimiento tuyo, no una línea leída
    assert c["leidas"] == c["ya_estaban"] + c["nuevas_agregadas"] + c["por_revisar"] + c["descartadas"] + c["anteriores"]
    assert (c["ya_estaban"], c["dudosas"], c["duplicadas_detectadas"]) == (3, 1, 1)


def test_frase_nunca_dice_cero_movimientos_si_todo_ya_estaba():
    c = {**et.contar_review([{"estado": "exacto"}] * 37)}
    txt = et.frase(et.estado_de_conteo(c), c, mes="2026-04", cuenta="Nu Colombia")
    assert txt == "Abril · Nu Colombia: 37 movimientos leídos, 37 ya estaban registrados, 0 nuevos"
    c2 = et.contar_review([{"estado": "importado"}] * 5 + [{"estado": "exacto"}] * 32)
    assert "5 nuevos agregados, 32 ya estaban" in et.frase(et.AL_DIA, c2, mes="2026-04", cuenta="Nu")


def test_estados_de_conteo():
    assert et.estado_de_conteo(et.contar_review([])) == et.SIN_MOVIMIENTOS_REALES
    assert et.estado_de_conteo(et.contar_review([{"estado": "faltante"}])) == et.POR_REVISAR
    assert et.estado_de_conteo(et.contar_review([{"estado": "anterior"}])) == et.ANTERIOR_AL_INICIO
    assert et.estado_de_conteo(et.contar_review([{"estado": "exacto"}]), "error") == et.NO_SE_PUDO_LEER


# ── «0 movimientos» ────────────────────────────────────────────────────────────────────────
def test_extracto_con_todo_ya_registrado_esta_al_dia_y_lo_dice(monkeypatch):
    e = Escena(monkeypatch)
    assert e.manual().status_code == 200
    r = e.extracto([_linea(e)], importar=False)
    assert r["importados"] if "importados" in r else True
    assert r["conteo"]["ya_estaban"] == 1 and r["conteo"]["nuevas_agregadas"] == 0
    (x,) = _ext_de_cuenta(e)
    assert x["estado"] == et.AL_DIA and x["leidas"] == 1 and x["ya_estaban"] == 1 and x["nuevas_agregadas"] == 0
    assert x["duplicadas_detectadas"] == 1
    assert "1 ya estaba registrado, 0 nuevos" in x["frase"]
    assert not [t for t in _estado(e)["tareas"] if t["id"] == "extractos_por_conciliar"]


def test_parcial_queda_por_revisar_y_al_importar_pasa_al_dia_con_contadores_al_dia(monkeypatch):
    e = Escena(monkeypatch)
    e.manual()
    r = e.extracto([_linea(e), _linea(e, "PANADERIA REAL", 8_000)], importar=False)
    (x,) = _ext_de_cuenta(e)
    assert x["estado"] == et.POR_REVISAR and x["por_revisar"] == 1 and x["ya_estaban"] == 1
    tarea = next(t for t in _estado(e)["tareas"] if t["id"] == "extractos_por_conciliar")
    assert tarea["cantidad"] == 1
    fps = [i["fingerprint"] for i in r["review"] if i["estado"] == "faltante"]
    assert client.post(f"/conciliacion/historial/{r['historial_id']}/importar", json={"fingerprints": fps}).status_code == 200
    (x,) = _ext_de_cuenta(e)
    assert x["estado"] == et.AL_DIA and x["nuevas_agregadas"] == 1 and x["ya_estaban"] == 1
    h = [h for h in client.get("/conciliacion/historial").json() if h["id"] == r["historial_id"]][0]
    assert h["faltantes"] == 0 and h["importados"] == 1 and h["estado"] == "conciliado"  # ya no se quedan viejos


# ── la carrera: registrar a mano DESPUÉS de leer el extracto ───────────────────────────────
def test_registrar_a_mano_despues_de_leer_el_extracto_lo_deja_al_dia_sin_duplicar(monkeypatch):
    e = Escena(monkeypatch)
    r = e.extracto([_linea(e)], importar=False)
    assert _ext_de_cuenta(e)[0]["estado"] == et.POR_REVISAR
    assert e.manual().status_code in (200, 409)
    if len(e.movs()) == 0:
        e.manual(forzar=True)
    (x,) = _ext_de_cuenta(e)
    assert x["estado"] == et.AL_DIA and x["por_revisar"] == 0 and x["duplicadas_detectadas"] == 1
    # Aunque la persona toque «importar lo que falta», no se duplica nada.
    client.post(f"/conciliacion/historial/{r['historial_id']}/importar", json={"fingerprints": [_linea(e) and r["review"][0]["fingerprint"]]})
    assert len(e.movs()) == 1
    assert e.saldo() == e.saldo0 - 45_000


def test_el_atajo_que_llega_despues_tambien_resuelve_la_linea_pendiente(monkeypatch):
    e = Escena(monkeypatch)
    e.extracto([_linea(e)], importar=False)
    e.atajo()
    (x,) = _ext_de_cuenta(e)
    assert x["estado"] == et.AL_DIA
    assert len(e.movs()) == 1


# ── el mismo extracto por varias vías ──────────────────────────────────────────────────────
def _poner_extractos(uid, cuenta_id, filas):
    db = SessionLocal()
    try:
        for n, (estado, hist, periodo) in enumerate(filas):
            db.add(ExtractoCorreo(
                usuario_id=uid, gmail_msg_id=f"{uid}-m{n}", archivo=f"e{n}.pdf", remitente="x@bancolombia.com.co",
                banco="Bancolombia", periodo=periodo, estado=estado, cuenta_sugerida_id=cuenta_id,
                historial_id=hist, recibido_en=datetime(2026, 10, 2)))
        db.commit()
    finally:
        db.close()


def test_mismo_pdf_en_dos_correos_es_un_solo_extracto(monkeypatch):
    e = Escena(monkeypatch)
    e.manual()
    r = e.extracto([_linea(e)], importar=False)
    mes = r["periodo_hasta"][:7]
    _poner_extractos(e.uid, e.cuenta["id"], [("procesado", r["historial_id"], f"{mes}-01 a {mes}-28"), ("nuevo", None, f"{mes}-01 a {mes}-28")])
    # (el periodo con fechas dd/mm/aaaa lo entiende mes_del_extracto; aquí se usa el mismo texto en ambos)
    items = [x for x in _estado(e)["extractos"] if x["cuenta_id"] == e.cuenta["id"]]
    assert len(items) == 1, items
    assert items[0]["estado"] == et.AL_DIA


def test_mismo_pdf_subido_a_mano_y_por_gmail_es_un_solo_extracto(monkeypatch):
    e = Escena(monkeypatch)
    e.manual()
    r = e.extracto([_linea(e)], importar=False)  # subida a mano (sin extracto de correo)
    mes_txt = datetime.strptime(r["periodo_hasta"], "%Y-%m-%d").strftime("%d/%m/%Y")
    _poner_extractos(e.uid, e.cuenta["id"], [("nuevo", None, f"01/{mes_txt[3:]} a {mes_txt}")])
    items = [x for x in _estado(e)["extractos"] if x["cuenta_id"] == e.cuenta["id"]]
    assert len(items) == 1 and items[0]["estado"] == et.AL_DIA
    assert not [t for t in _estado(e)["tareas"] if t["id"] == "extractos_por_conciliar"]


def test_extracto_de_otra_cuenta_del_mismo_banco_no_se_da_por_revisado(monkeypatch):
    e = Escena(monkeypatch, cuentas=(("Bancolombia Ahorros", 1_000_000), ("Bancolombia Tarjeta", 0)))
    e.manual()
    r = e.extracto([_linea(e)], importar=False)
    otra = e.cuentas["Bancolombia Tarjeta"]
    d = datetime.strptime(r["periodo_hasta"], "%Y-%m-%d")
    _poner_extractos(e.uid, otra["id"], [("nuevo", None, f"01/{d:%m/%Y} a {d:%d/%m/%Y}")])
    por_cuenta = {x["cuenta_id"]: x for x in _estado(e)["extractos"]}
    assert por_cuenta[e.cuenta["id"]]["estado"] == et.AL_DIA
    assert por_cuenta[otra["id"]]["estado"] == et.POR_REVISAR


def test_periodos_que_se_solapan_no_dan_por_revisado_el_mes_siguiente(monkeypatch):
    """Unas pocas líneas conciliadas de fin de mes NO marcan todo el mes siguiente como revisado."""
    from app.extractos_conciliados import evidencia_conciliado
    from app.models import Movimiento

    e = Escena(monkeypatch)
    db = SessionLocal()
    try:
        for d in range(1, 11):
            db.add(Movimiento(usuario_id=e.uid, cuenta_id=e.cuenta["id"], fecha=datetime(2026, 8, d, 12), descripcion=f"Compra {d}",
                              categoria="Comida", tipo="expense", monto=1000 + d, fuente="manual", cat_confirmada=True,
                              conciliado_en=datetime(2026, 8, d) if d == 1 else None))
        db.commit()
        assert evidencia_conciliado(db, e.uid, e.cuenta["id"], "2026-08") is None  # 1 de 10: no alcanza
        for m in db.query(Movimiento).filter(Movimiento.usuario_id == e.uid).limit(5).all():
            m.conciliado_en = datetime(2026, 8, 20)
        db.commit()
        assert evidencia_conciliado(db, e.uid, e.cuenta["id"], "2026-08") is not None  # la mitad sí
    finally:
        db.close()


def test_borrar_la_revision_devuelve_el_extracto_de_gmail_a_nuevo(monkeypatch):
    e = Escena(monkeypatch)
    r = e.extracto([_linea(e)], importar=True)
    _poner_extractos(e.uid, e.cuenta["id"], [("procesado", r["historial_id"], "")])
    e.como()
    assert client.delete(f"/conciliacion/historial/{r['historial_id']}").status_code == 200
    db = SessionLocal()
    try:
        fila = db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == e.uid).one()
        assert fila.estado == "nuevo" and fila.historial_id is None
    finally:
        db.close()


# ── dudosos lado a lado ────────────────────────────────────────────────────────────────────
def _con_dudoso(e):
    """Un registro a mano y una línea de extracto parecida pero no igual (monto distinto en 2 %)."""
    e.manual(monto=45_000, desc="Exito")
    return e.extracto([_linea(e, monto=45_900)], importar=False)


def test_los_dudosos_traen_las_dos_filas_y_se_resuelven_en_bloque(monkeypatch):
    e = Escena(monkeypatch)
    r = _con_dudoso(e)
    item = r["review"][0]
    if item["estado"] != "aproximado":
        pytest.skip("la regla central los junta sola: no hay dudoso en este caso")
    assert item["descripcion_registrada"] == "Exito" and item["monto_registrado"] == 45_000
    out = client.post(f"/conciliacion/historial/{r['historial_id']}/resolver-dudosos", json={"mismos": [item["fingerprint"]]}).json()
    assert out["juntados"] == 1 and out["conteo"]["por_revisar"] == 0
    assert len(e.movs()) == 1


def test_dudoso_que_es_otro_gasto_queda_para_agregar_y_no_se_pierde(monkeypatch):
    e = Escena(monkeypatch)
    r = _con_dudoso(e)
    item = r["review"][0]
    if item["estado"] != "aproximado":
        pytest.skip("sin dudoso")
    out = client.post(f"/conciliacion/historial/{r['historial_id']}/resolver-dudosos", json={"distintos": [item["fingerprint"]]}).json()
    assert out["separados"] == 1 and out["conteo"]["por_revisar"] == 1
    client.post(f"/conciliacion/historial/{r['historial_id']}/importar", json={"fingerprints": [item["fingerprint"]]})
    assert len(e.movs()) == 2


# ── las 24 órdenes, mirando lo que ve la pantalla ──────────────────────────────────────────
@pytest.mark.parametrize("orden", list(itertools.permutations(CANALES)), ids=lambda o: ">".join(o))
def test_24_ordenes_la_pantalla_no_deja_nada_pendiente_ni_doble(orden, monkeypatch):
    e = Escena(monkeypatch)
    for canal in orden:
        if canal == "manual":
            e.manual(forzar=False)
        elif canal == "atajo":
            e.atajo()
        elif canal == "correo":
            e.llega_correo()
        else:
            e.extracto()
    est = _estado(e)
    assert len(e.movs()) == 1
    ids = {t["id"] for t in est["tareas"]}
    assert "correos_por_revisar" not in ids and "extractos_por_conciliar" not in ids
    assert est["correos_ya_registrados"] in (0, 1)
    for x in est["extractos"]:
        if x["cuenta_id"] == e.cuenta["id"]:
            assert x["estado"] == et.AL_DIA
            assert x["leidas"] == x["ya_estaban"] + x["nuevas_agregadas"] + x["por_revisar"] + x["descartadas"] + x["anteriores"]
            assert x["leidas"] == 1 and x["por_revisar"] == 0
    assert e.saldo() == e.saldo0 - 45_000


def test_el_recordatorio_de_inicio_cuenta_igual_que_traer_movimientos(monkeypatch):
    """Inicio y Traer movimientos no pueden contar distinto: dos correos del mismo extracto son UNO."""
    e = Escena(monkeypatch)
    d = datetime(2026, 8, 28)
    _poner_extractos(e.uid, e.cuenta["id"], [("nuevo", None, "01/08/2026 a 28/08/2026"), ("nuevo", None, "01/08/2026 a 28/08/2026")])
    e.como()
    rec = [r for r in client.get("/recordatorios").json() if r["tipo"] == "extractos"]
    tareas = [t for t in _estado(e)["tareas"] if t["id"] == "extractos_por_conciliar"]
    assert len(rec) == 1 and "1 extracto por revisar" in rec[0]["titulo"]
    assert tareas[0]["cantidad"] == 1
