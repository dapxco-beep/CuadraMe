"""Fechas de los extractos (app/fechas_extracto.py). Todo sintético: números inventados y el fixture del extracto de tarjeta Nu
(corte 15 OCT, límite de pago 04 NOV, periodo facturado 14 SEP - 14 OCT).

Cubre: la tarjeta guarda el CORTE (no el límite de pago) y el inicio del periodo; el mes del extracto es el del corte; la
relectura rellena fechas vacías o equivocadas sin tocar lo importado; el respaldo por la fecha del correo es solo un
estimado y no pisa una fecha leída; ahorros intactos; hallazgos (a)-(d) con su reparación o decisión; duplicado de
septiembre marcado sin tocar movimientos; cierre/cuadre por el mes del corte; idempotencia y aislamiento."""
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'fechas_extracto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import arreglar_tarjetas as at  # noqa: E402
from app import autoarreglo as aa  # noqa: E402
from app import cuadre_encadenado as ce  # noqa: E402
from app import estado_traer  # noqa: E402
from app import fechas_extracto as fe  # noqa: E402
from app import limites  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.extractos_tarjeta_nu import leer_extracto_tarjeta_nu  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil  # noqa: E402
from app.models_autoarreglo import ArregloAuto  # noqa: E402
from app.routers import conciliacion as router_conc  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402
from app.salud_datos import diagnosticar  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)
FIXTURE = (Path(__file__).parent / "fixtures" / "extracto_tarjeta_nu_sintetico.txt").read_text(encoding="utf-8")
RESUMEN = leer_extracto_tarjeta_nu(FIXTURE)["resumen_tarjeta"]
HOY = date(2026, 10, 19)


@pytest.fixture(autouse=True)
def _limpio():
    app.dependency_overrides.clear()
    limites._eventos.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


_n = [0]


def uid():
    _n[0] += 1
    return f"fx-{_n[0]}"


def cuenta(db, u, nombre="Nu Tarjeta", tipo="credito", saldo=0.0):
    c = Cuenta(usuario_id=u, nombre=nombre, tipo=tipo, saldo=saldo)
    db.add(c)
    db.flush()
    return c


def historial(db, u, c, *, corte=None, inicio=None, resumen=None, estado="conciliado", ini=None, fin=None, lineas=None,
              origen="extracto", importados=0, lectura=None, creado=None):
    lect = dict(lectura or {})
    if resumen is not None:
        lect["resumen_tarjeta"] = resumen
    h = HistorialExtracto(usuario_id=u, cuenta_id=c.id, banco_detectado="nu", estado=estado, fecha_corte=corte, periodo_inicio=inicio,
                          saldo_inicial_extracto=ini, saldo_final_extracto=fin, saldos_origen=origen, importados=importados,
                          review_json=json.dumps(lineas or []), lectura_json=json.dumps(lect) if lect else None,
                          creado_en=creado or datetime(2026, 10, 1))
    db.add(h)
    db.flush()
    return h


def correo(db, u, h, recibido, asunto="Extracto de tu tarjeta de crédito Nu", periodo=""):
    e = ExtractoCorreo(usuario_id=u, gmail_msg_id=f"m-{h.id}", archivo="extracto.pdf", asunto=asunto, estado="procesado",
                       historial_id=h.id, recibido_en=recibido, periodo=periodo)
    db.add(e)
    db.flush()
    return e


def recargar(db, h):
    db.expire_all()
    return db.get(HistorialExtracto, h.id)


# ── 1) Procesar: corte, no límite de pago ─────────────────────────────────────────────────────
def test_el_resumen_del_fixture_distingue_corte_limite_y_periodo():
    assert RESUMEN["corte"] == "2026-10-15" and RESUMEN["limite_pago"] == "2026-11-04"
    f = fe.fechas_del_resumen(RESUMEN)
    assert f == {"periodo_inicio": "2026-09-14", "fecha_corte": "2026-10-15", "periodo_fin": "2026-10-14"}


def test_procesar_guarda_el_corte_y_el_inicio_del_periodo_no_el_limite_de_pago(monkeypatch):
    u = uid()
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=u, email=f"{u}@t.com", nombre="Ana Pérez Gómez")
    monkeypatch.setattr(router_conc, "pdf_a_texto", lambda *a, **k: FIXTURE)
    c = client.post("/cuentas", json={"nombre": "Nu Tarjeta", "tipo": "credito", "saldo": 0}).json()["id"]
    r = client.post("/conciliacion/procesar", json={"cuenta_id": c, "pdf_base64": "x"}).json()
    s = SessionLocal()
    try:
        h = s.get(HistorialExtracto, r["historial_id"])
        assert h.fecha_corte == "2026-10-15" and h.fecha_corte != RESUMEN["limite_pago"]
        assert h.periodo_inicio == "2026-09-14"
        assert fe.mes_de_extracto(h, s.get(Cuenta, c)) == "2026-10"
    finally:
        s.close()


def test_el_mes_de_una_tarjeta_es_el_del_corte_y_ahorros_no_cambia(db):
    u = uid()
    t, a = cuenta(db, u), cuenta(db, u, "Nu Ahorros", "ahorro")
    jun = historial(db, u, t, corte="2026-06-14", inicio="2026-05-15")
    oct_ = historial(db, u, t, corte="2026-10-15", inicio="2026-09-14")
    aho = historial(db, u, a, corte="2026-10-31", inicio="2026-10-01")
    assert fe.mes_de_extracto(jun, t) == "2026-06" and fe.mes_de_extracto(oct_, t) == "2026-10"
    assert fe.mes_de_extracto(aho, a) is None  # ahorros: sigue por su regla de siempre (mes calendario)


# ── 2) Rellenar lo ya guardado ───────────────────────────────────────────────────────────────
def test_rellena_fechas_vacias_y_corrige_el_limite_de_pago_sin_tocar_lo_importado(db):
    u = uid()
    t = cuenta(db, u, saldo=-50_000.0)
    mov = Movimiento(usuario_id=u, cuenta_id=t.id, descripcion="Tienda Alfa", categoria="Otros", tipo="expense", monto=50_000.0,
                     fecha=datetime(2026, 10, 8), fuente="conciliacion_extracto")
    db.add(mov)
    lineas = [{"fecha": "2026-10-08", "descripcion": "Tienda Alfa", "monto": 50000.0, "tipo": "expense", "estado": "importado"}]
    vacio = historial(db, u, t, resumen=RESUMEN, lineas=lineas, importados=1)
    mal = historial(db, u, t, corte="2026-11-04", inicio="2026-09-15", resumen=RESUMEN)
    db.commit()
    antes = (db.get(Cuenta, t.id).saldo, db.query(Movimiento).filter_by(usuario_id=u).count(), vacio.review_json)
    assert set(fe.completar_fechas(db, u)) == {vacio.id, mal.id}
    db.commit()
    for h in (recargar(db, vacio), recargar(db, mal)):
        assert (h.fecha_corte, h.periodo_inicio) == ("2026-10-15", "2026-09-14")
        assert h.lectura["periodo_fin"] == "2026-10-14" and "fechas_estimadas" not in h.lectura
    assert (db.get(Cuenta, t.id).saldo, db.query(Movimiento).filter_by(usuario_id=u).count(), recargar(db, vacio).review_json) == antes
    assert fe.completar_fechas(db, u) == []  # idempotente


def test_releer_un_extracto_conciliado_de_tarjeta_arregla_sus_fechas(monkeypatch, db):
    u = uid()
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: SimpleNamespace(
        users=lambda: SimpleNamespace(messages=lambda: SimpleNamespace(get=lambda **kw: SimpleNamespace(execute=lambda: {"id": kw["id"]})))))
    monkeypatch.setattr(rx, "listar_adjuntos_pdf", lambda msg: [{"archivo": "extracto.pdf", "attachment_id": "a1"}])
    monkeypatch.setattr(rx, "descargar_adjunto", lambda g, m, a: b"%PDF-falso")
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("ok", FIXTURE, None))
    db.add(Perfil(usuario_id=u, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
    t = cuenta(db, u)
    h = historial(db, u, t, corte="2026-11-04", inicio="2026-09-15", fin=-408000.0, ini=-200000.0)
    correo(db, u, h, datetime(2026, 10, 15, 14, 0))
    db.commit()
    rx.releer_historial(db, SimpleNamespace(id=u, nombre="Ana Pérez Gómez"), h, solo_agregar=True)  # modo de los ya conciliados
    h = recargar(db, h)
    assert (h.fecha_corte, h.periodo_inicio) == ("2026-10-15", "2026-09-14")
    assert h.saldo_final_extracto == -408000.0  # los saldos ya conciliados no se tocan en ese modo


def test_el_respaldo_por_la_fecha_del_correo_se_marca_estimado(db):
    u = uid()
    t = cuenta(db, u)
    h = historial(db, u, t)
    correo(db, u, h, datetime(2026, 10, 15, 14, 0))
    db.commit()
    assert fe.completar_fechas(db, u) == [h.id]
    db.commit()
    h = recargar(db, h)
    assert h.fecha_corte == "2026-10-15" and fe.es_estimada(h)
    e = db.query(ExtractoCorreo).filter_by(historial_id=h.id).first()
    ded = estado_traer.mes_de_correo(e, h)
    assert ded["mes"] == "2026-10" and ded["deducido"] is True  # es una suposición y la vista lo sabe


def test_una_fecha_leida_del_pdf_nunca_se_pisa_con_una_estimada(db):
    u = uid()
    t = cuenta(db, u)
    leida = historial(db, u, t, corte="2026-09-15", inicio="2026-08-14", ini=-1.0, fin=-2.0)
    correo(db, u, leida, datetime(2026, 10, 20, 14, 0))
    sin_resumen_con_corte = fe.aplicar_estimada(leida, datetime(2026, 10, 20, 14, 0))
    assert sin_resumen_con_corte is False and leida.fecha_corte == "2026-09-15" and not fe.es_estimada(leida)
    # y cuando luego sí se lee el PDF, la lectura reemplaza al estimado y quita la marca
    est = historial(db, u, t)
    fe.aplicar_estimada(est, datetime(2026, 10, 14, 14, 0))
    assert est.fecha_corte == "2026-10-14" and fe.es_estimada(est)
    assert fe.aplicar_resumen(est, RESUMEN) is True
    assert est.fecha_corte == "2026-10-15" and not fe.es_estimada(est)


def test_los_extractos_de_ahorros_con_fechas_no_se_tocan_y_los_vacios_se_completan_con_sus_lineas(db):
    u = uid()
    a = cuenta(db, u, "Nu Ahorros", "ahorro")
    bien = historial(db, u, a, corte="2026-09-30", inicio="2026-09-01", ini=1.0, fin=2.0)
    lineas = [{"fecha": "2026-08-03", "monto": 1, "tipo": "income", "estado": "importado"},
              {"fecha": "2026-08-27", "monto": 1, "tipo": "income", "estado": "importado"}]
    vacio = historial(db, u, a, lineas=lineas)
    assert fe.completar_fechas(db, u) == [vacio.id]
    assert (bien.fecha_corte, bien.periodo_inicio) == ("2026-09-30", "2026-09-01")
    assert (vacio.periodo_inicio, vacio.fecha_corte) == ("2026-08-03", "2026-08-27") and fe.es_estimada(vacio)


# ── 3) Hallazgos ─────────────────────────────────────────────────────────────────────────────
def test_hallazgos_a_b_c_d(db):
    u = uid()
    t = cuenta(db, u)
    sin = historial(db, u, t)                                                        # (a)
    fut = historial(db, u, t, corte="2026-12-20", inicio="2026-11-20", ini=1.0, fin=2.0)  # (b) corte que aún no llega
    inv = historial(db, u, t, corte="2026-05-10", inicio="2026-06-10", ini=1.0, fin=2.0)  # (b) corte antes del inicio
    p1 = historial(db, u, t, corte="2026-07-15", inicio="2026-06-14", ini=1.0, fin=2.0)
    p2 = historial(db, u, t, corte="2026-08-20", inicio="2026-07-10", ini=3.0, fin=4.0)  # (c) cruza con p1
    d1 = historial(db, u, t, corte="2026-09-15", inicio="2026-08-21", ini=5.0, fin=6.0, importados=3, creado=datetime(2026, 9, 16))
    d2 = historial(db, u, t, corte="2026-09-15", inicio="2026-08-21", ini=5.0, fin=6.0, importados=0, creado=datetime(2026, 9, 17))  # (d)
    r = fe.revisar_fechas(db, u, hoy=HOY)
    assert r["sin_fechas"] == [sin.id] and set(r["futuras"]) == {fut.id, inv.id}
    assert set(r["traslapados"]) == {p1.id, p2.id} and r["duplicados"] == [d2.id]
    db.commit()
    h = next(x for x in diagnosticar(db, u) if x["codigo"] == "fechas_extracto_dudosas")
    assert h["datos"]["sin_fechas"] == 1 and h["datos"]["repetidos"] == 1 and h["datos"]["periodos_cruzados"] == 2
    assert d1.id not in r["duplicados"]  # se queda el que más importó


def test_extractos_sin_problema_no_generan_hallazgo(db):
    u = uid()
    t = cuenta(db, u)
    historial(db, u, t, corte="2026-09-15", inicio="2026-08-16", ini=1.0, fin=2.0)
    historial(db, u, t, corte="2026-10-15", inicio="2026-09-16", ini=2.0, fin=3.0)
    db.commit()
    assert all(x["codigo"] != "fechas_extracto_dudosas" for x in diagnosticar(db, u))


# ── 4) Autoarreglo: repara (a) y (d) con registro y reversible; deja (b) y (c) a la persona ───
def test_el_autoarreglo_repara_a_y_d_con_registro_y_no_toca_b_ni_c(db):
    u = uid()
    t = cuenta(db, u, saldo=-100_000.0)
    mov = Movimiento(usuario_id=u, cuenta_id=t.id, descripcion="Tienda Alfa", categoria="Otros", tipo="expense", monto=100_000.0,
                     fecha=datetime(2026, 9, 3), fuente="conciliacion_extracto")
    db.add(mov)
    mal = historial(db, u, t, corte="2026-11-04", inicio="2026-09-15", resumen=RESUMEN, ini=-1.0, fin=-408000.0)
    sep1 = historial(db, u, t, corte="2026-09-15", inicio="2026-08-16", ini=5.0, fin=6.0, importados=1, creado=datetime(2026, 9, 16))
    sep2 = historial(db, u, t, corte="2026-09-15", inicio="2026-08-16", ini=5.0, fin=6.0, creado=datetime(2026, 9, 17))
    fut = historial(db, u, t, corte="2099-01-01", inicio="2098-12-01", ini=7.0, fin=8.0)
    db.commit()
    movs_antes = [(m.id, m.monto, m.tipo, m.fecha) for m in db.query(Movimiento).filter_by(usuario_id=u)]
    saldo_antes = db.get(Cuenta, t.id).saldo

    r = aa.correr(db, u, usuario=SimpleNamespace(id=u, email="", nombre="", nombre_pila=""))
    assert not r.get("error")
    mal, sep2, fut = recargar(db, mal), recargar(db, sep2), recargar(db, fut)
    assert (mal.fecha_corte, mal.periodo_inicio) == ("2026-10-15", "2026-09-14")
    assert fe.duplicado_de(sep2) == sep1.id and not fe.es_duplicado(recargar(db, sep1))
    assert fut.fecha_corte == "2099-01-01" and not fe.es_duplicado(fut)          # (b) decisión humana
    assert any(d["tipo"] == "fechas_dudosas" for d in r["decisiones"])
    assert [(m.id, m.monto, m.tipo, m.fecha) for m in db.query(Movimiento).filter_by(usuario_id=u)] == movs_antes
    assert db.get(Cuenta, t.id).saldo == saldo_antes
    lote = r["lote_id"]
    filas = db.query(ArregloAuto).filter_by(usuario_id=u, lote_id=lote, tipo="historial").all()
    assert {f.entidad_id for f in filas} == {mal.id, sep2.id}
    c = r["resumen"]["contadores"]
    assert c["fechas_arregladas"] == 1 and c["duplicados_marcados"] == 1

    # idempotente: otra corrida no cambia nada ni registra más
    n_filas = db.query(ArregloAuto).filter_by(usuario_id=u).count()
    aa.correr(db, u, usuario=SimpleNamespace(id=u, email="", nombre="", nombre_pila=""))
    assert db.query(ArregloAuto).filter_by(usuario_id=u).count() == n_filas

    # reversible
    aa.deshacer_lote(db, u, lote)
    mal, sep2 = recargar(db, mal), recargar(db, sep2)
    assert (mal.fecha_corte, mal.periodo_inicio) == ("2026-11-04", "2026-09-15") and not fe.es_duplicado(sep2)


def test_el_autoarreglo_completa_una_fecha_faltante_con_el_correo_marcada_como_estimada(db):
    u = uid()
    t = cuenta(db, u)
    h = historial(db, u, t)
    correo(db, u, h, datetime(2026, 10, 15, 14, 0))
    db.commit()
    aa.correr(db, u, usuario=SimpleNamespace(id=u, email="", nombre="", nombre_pila=""))
    h = recargar(db, h)
    assert h.fecha_corte == "2026-10-15" and fe.es_estimada(h)


# ── 5) Cierre, cuadre, arreglar tarjetas ─────────────────────────────────────────────────────
def test_cuadre_cierre_y_arreglar_tarjetas_usan_el_mes_del_corte(db):
    u = uid()
    t = cuenta(db, u)
    h = historial(db, u, t, corte="2026-10-15", inicio="2026-09-14", resumen=RESUMEN, ini=-200000.0, fin=-408000.0)
    e = correo(db, u, h, datetime(2026, 10, 15, 14, 0), periodo="noviembre 2026")  # el periodo viejo decía el mes del límite
    db.commit()
    r = ce.calcular(db, t)
    fila = next(m for m in r["meses"] if m.get("historial_id") == h.id)
    assert fila["mes"] == "2026-10" and fila["periodo_inicio"] == "2026-09-14" and fila["fecha_corte"] == "2026-10-15"
    assert fila["tarjeta_fechas"] == {"corte": "2026-10-15", "limite_pago": "2026-11-04", "periodo_fin": "2026-10-14", "estimado": False}
    assert at._mes(h, e) == "2026-10"
    assert estado_traer.mes_de_correo(e, h)["mes"] == "2026-10"


def test_la_lista_de_extractos_pone_el_de_octubre_en_octubre_y_oculta_el_repetido(db):
    u = uid()
    t = cuenta(db, u)
    h = historial(db, u, t, corte="2026-10-15", inicio="2026-09-14", resumen=RESUMEN, ini=-200000.0, fin=-408000.0)
    correo(db, u, h, datetime(2026, 10, 15, 14, 0), periodo="noviembre 2026")
    dup = historial(db, u, t, corte="2026-09-15", inicio="2026-08-16", ini=5.0, fin=6.0, importados=1)
    rep = historial(db, u, t, corte="2026-09-15", inicio="2026-08-16", ini=5.0, fin=6.0)
    db.commit()
    fe.marcar_duplicados(db, u)
    db.commit()
    filas = estado_traer.lista_extractos(db, u)
    meses = sorted(f["mes"] for f in filas if f["cuenta_id"] == t.id)
    assert meses == ["2026-09", "2026-10"]  # el repetido de septiembre no es otro renglón
    assert fe.es_duplicado(recargar(db, rep)) and not fe.es_duplicado(recargar(db, dup))


# ── 6) Aislamiento ───────────────────────────────────────────────────────────────────────────
def test_reparar_fechas_de_una_persona_no_toca_a_otra(db):
    a, b = uid(), uid()
    ta, tb = cuenta(db, a), cuenta(db, b)
    ha = historial(db, a, ta, corte="2026-11-04", inicio="2026-09-15", resumen=RESUMEN)
    hb = historial(db, b, tb, corte="2026-11-04", inicio="2026-09-15", resumen=RESUMEN)
    db.commit()
    fe.reparar(db, a)
    db.commit()
    assert recargar(db, ha).fecha_corte == "2026-10-15" and recargar(db, hb).fecha_corte == "2026-11-04"
    assert fe.revisar_fechas(db, b, hoy=HOY)["sin_fechas"] == []


def test_la_lista_trae_el_corte_y_el_limite_de_pago_de_la_tarjeta(db):
    u = uid()
    t = cuenta(db, u)
    h = historial(db, u, t, corte="2026-10-15", inicio="2026-09-14", resumen=RESUMEN, ini=-200000.0, fin=-408000.0)
    correo(db, u, h, datetime(2026, 10, 15, 14, 0))
    db.commit()
    fila = next(f for f in estado_traer.lista_extractos(db, u) if f["historial_id"] == h.id)
    assert fila["mes"] == "2026-10"
    assert fila["tarjeta_fechas"] == {"corte": "2026-10-15", "limite_pago": "2026-11-04", "periodo_fin": "2026-10-14", "estimado": False}
