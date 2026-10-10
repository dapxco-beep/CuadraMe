"""Crons idempotentes: aportes automáticos a metas (movimiento neutro, recuperación,
sin saldo), resumen semanal, recordatorio de recurrentes, backup y push tolerante.

Los números están hechos a mano en cada prueba. Cada prueba usa su propio usuario
(la base de pruebas se comparte entre archivos)."""
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'crons_idem.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import finanzas  # noqa: E402
from app import push as push_mod  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import FUENTE_APORTE_META, tipos_efectivos  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Meta, Movimiento, PushSubscription, Recurrente  # noqa: E402
from app.routers import backup as backup_router  # noqa: E402
from app.routers import push as push_router  # noqa: E402
from app.utiles import ahora_co  # noqa: E402

client = TestClient(app)
CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}
USUARIO = {"actual": UsuarioActual(id="ci-0", email="a@test.com", nombre="Ci")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


@pytest.fixture
def pushes(monkeypatch):
    """Captura los push enviados por el router: [(usuario_id, titulo, cuerpo)]."""
    enviados = []

    def _enviar(db, usuario_id, titulo, cuerpo, url="/", boton=None):
        enviados.append((usuario_id, titulo, cuerpo))
        return 1

    monkeypatch.setattr(push_router, "enviar_push", _enviar)
    return enviados


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def fijar_hoy(monkeypatch, fecha: datetime):
    monkeypatch.setattr(push_router, "ahora_co", lambda: fecha)
    monkeypatch.setattr(finanzas, "ahora_co", lambda: fecha)


def _cuenta_y_meta(uid, saldo, aporte, dia, objetivo=10_000_000, nombre="Viaje"):
    como(uid)
    db = SessionLocal()
    try:
        cuenta = Cuenta(usuario_id=uid, nombre="Banco", saldo=saldo, moneda="COP")
        db.add(cuenta)
        db.flush()
        meta = Meta(usuario_id=uid, nombre=nombre, monto_objetivo=objetivo, monto_actual=0,
                    aporte_automatico=aporte, dia_aporte=dia, cuenta_origen_id=cuenta.id)
        db.add(meta)
        db.commit()
        return cuenta.id, meta.id
    finally:
        db.close()


def _saldo(cuenta_id):
    return {c["id"]: c["saldo"] for c in client.get("/cuentas").json()}[cuenta_id]


def _meta(meta_id):
    return {m["id"]: m for m in client.get("/metas").json()}[meta_id]


def _movs(cuenta_id):
    return client.get(f"/movimientos?cuenta_id={cuenta_id}&limit=200").json()


def _cron_aportes():
    return client.post("/push/cron/aportes-automaticos", headers=CABECERA).json()


# --------------------------------------------------------------------- aportes

def test_aporte_crea_movimiento_neutro_baja_saldo_y_es_idempotente(monkeypatch, pushes):
    cuenta, meta = _cuenta_y_meta("ci-aporte", saldo=1_000_000, aporte=300_000, dia=1)
    fijar_hoy(monkeypatch, ahora_co())
    r1 = _cron_aportes()
    r2 = _cron_aportes()  # doble ejecución el mismo día
    assert r1["ok"] and r1["aportados"] >= 1 and r1["fallidos"] == 0 and "procesados" in r1
    assert r2["aportados"] == 0
    assert _saldo(cuenta) == 700_000                       # 1.000.000 - 300.000, una sola vez
    assert _meta(meta)["monto_actual"] == 300_000
    movs = [m for m in _movs(cuenta) if m["fuente"] == FUENTE_APORTE_META]
    assert len(movs) == 1
    assert movs[0]["descripcion"] == "Aporte a meta «Viaje»" and movs[0]["monto"] == 300_000
    assert movs[0]["categoria"] == "Aporte a meta"
    assert len([p for p in pushes if p[0] == "ci-aporte"]) == 1


def test_aporte_no_cuenta_como_gasto_en_reportes_presupuestos_wrapped_salud(monkeypatch, pushes):
    cuenta, _ = _cuenta_y_meta("ci-neutro", saldo=2_000_000, aporte=300_000, dia=1)
    client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": "expense", "monto": 100_000,
                                      "descripcion": "Restaurante", "categoria": "Comida"})
    client.post("/presupuestos", json={"categoria": "Aporte a meta", "limite": 50_000})
    client.post("/presupuestos", json={"categoria": "Comida", "limite": 500_000})
    fijar_hoy(monkeypatch, ahora_co())
    _cron_aportes()
    assert _saldo(cuenta) == 1_600_000                      # 2.000.000 - 100.000 - 300.000
    r = client.get("/reportes/mensual").json()
    assert r["gastos"] == 100_000 and r["ingresos"] == 0    # el aporte NO es gasto
    assert {c["categoria"] for c in r["top_categorias"]} == {"Comida"}
    t = client.get("/reportes/tendencias?meses=1").json()["meses"][-1]
    assert t["gastos"] == 100_000
    assert client.get("/insights/resumen-semanal").json()["gastos"] == 100_000
    por_cat = {c["categoria"]: c["gastado"] for c in client.get("/presupuestos/disponible-hoy").json()["categorias"]}
    assert por_cat["Aporte a meta"] == 0 and por_cat["Comida"] == 100_000
    w = client.get(f"/reportes/wrapped?mes={ahora_co().strftime('%Y-%m')}").json()
    assert w["gasto_total"] == 100_000
    assert client.get("/insights/salud-financiera").status_code == 200
    csv = client.get("/exportar/movimientos.csv").text
    assert "No cuenta" in [l for l in csv.splitlines() if "Aporte a meta" in l][0]


def test_regla_pura_aporte_meta_es_transfer_aun_sin_categoria():
    movs = [
        {"id": "a", "tipo": "expense", "monto": 5, "descripcion": "x", "cuenta_id": "A", "categoria": "Otros", "fuente": FUENTE_APORTE_META},
        {"id": "b", "tipo": "expense", "monto": 5, "descripcion": "x", "cuenta_id": "A", "categoria": "Aporte a meta", "fuente": "manual"},
        {"id": "c", "tipo": "expense", "monto": 5, "descripcion": "x", "cuenta_id": "A", "categoria": "Comida", "fuente": "manual"},
    ]
    assert tipos_efectivos(movs, {"A": "ahorro"}) == {"a": "transfer", "b": "transfer", "c": "expense"}


def test_recuperacion_si_el_cron_fallo_el_dia_del_aporte(monkeypatch, pushes):
    cuenta, meta = _cuenta_y_meta("ci-recupera", saldo=1_000_000, aporte=100_000, dia=10)
    fijar_hoy(monkeypatch, datetime(2026, 3, 9, 8, 0))
    _cron_aportes()
    assert _saldo(cuenta) == 1_000_000                      # el 9 todavía no toca
    fijar_hoy(monkeypatch, datetime(2026, 3, 12, 8, 0))     # el cron falló el 10 y 11
    assert _cron_aportes()["aportados"] >= 1
    assert _saldo(cuenta) == 900_000
    fijar_hoy(monkeypatch, datetime(2026, 3, 13, 8, 0))
    _cron_aportes()
    assert _saldo(cuenta) == 900_000                        # ya aportado este mes
    fijar_hoy(monkeypatch, datetime(2026, 4, 10, 8, 0))     # mes nuevo: vuelve a tocar
    _cron_aportes()
    assert _saldo(cuenta) == 800_000 and _meta(meta)["monto_actual"] == 200_000


def test_dia_31_en_febrero_es_el_ultimo_dia(monkeypatch, pushes):
    cuenta, _ = _cuenta_y_meta("ci-feb", saldo=500_000, aporte=50_000, dia=31)
    fijar_hoy(monkeypatch, datetime(2026, 2, 27, 8, 0))
    _cron_aportes()
    assert _saldo(cuenta) == 500_000                        # febrero 2026 tiene 28 días
    fijar_hoy(monkeypatch, datetime(2026, 2, 28, 8, 0))
    _cron_aportes()
    assert _saldo(cuenta) == 450_000


def test_sin_saldo_no_aporta_parcial_y_avisa_una_sola_vez_al_mes(monkeypatch, pushes):
    cuenta, meta = _cuenta_y_meta("ci-sinsaldo", saldo=100_000, aporte=300_000, dia=5)
    for dia in (5, 5, 6, 20):                               # doble ejecución y reintentos diarios
        fijar_hoy(monkeypatch, datetime(2026, 5, dia, 8, 0))
        _cron_aportes()
    assert _saldo(cuenta) == 100_000 and _meta(meta)["monto_actual"] == 0
    assert not [m for m in _movs(cuenta) if m["fuente"] == FUENTE_APORTE_META]
    avisos = [p for p in pushes if p[0] == "ci-sinsaldo"]
    assert len(avisos) == 1 and "No alcanzó para tu aporte a «Viaje»" in avisos[0][2]
    # Llega plata: el cron aún puede recuperar el aporte del mes.
    db = SessionLocal()
    db.query(Cuenta).filter(Cuenta.id == cuenta).update({"saldo": 400_000})
    db.commit()
    db.close()
    fijar_hoy(monkeypatch, datetime(2026, 5, 21, 8, 0))
    _cron_aportes()
    assert _saldo(cuenta) == 100_000 and _meta(meta)["monto_actual"] == 300_000
    # Mes siguiente sin saldo suficiente: vuelve a avisar (una vez más).
    fijar_hoy(monkeypatch, datetime(2026, 6, 5, 8, 0))
    _cron_aportes()
    _cron_aportes()
    assert len([p for p in pushes if p[0] == "ci-sinsaldo"]) == 3   # aviso mayo + aporte hecho + aviso junio


def test_borrar_aporte_revierte_cuenta_y_meta_y_editar_se_rechaza(monkeypatch, pushes):
    cuenta, meta = _cuenta_y_meta("ci-borrar", saldo=1_000_000, aporte=250_000, dia=1)
    fijar_hoy(monkeypatch, ahora_co())
    _cron_aportes()
    mov = [m for m in _movs(cuenta) if m["fuente"] == FUENTE_APORTE_META][0]
    assert _saldo(cuenta) == 750_000 and _meta(meta)["monto_actual"] == 250_000
    r = client.put(f"/movimientos/{mov['id']}", json={"monto": 1})
    assert r.status_code == 400 and "aporte a una meta" in r.json()["detail"]
    assert _saldo(cuenta) == 750_000
    assert client.delete(f"/movimientos/{mov['id']}").status_code == 200
    assert _saldo(cuenta) == 1_000_000 and _meta(meta)["monto_actual"] == 0
    _cron_aportes()  # el usuario deshizo el aporte: este mes no se repite solo
    assert _saldo(cuenta) == 1_000_000


# ------------------------------------------------------------- resumen semanal

def _usuario_con_push_y_gasto(uid, fecha):
    db = SessionLocal()
    try:
        cuenta = Cuenta(usuario_id=uid, nombre="Banco", saldo=1000, moneda="COP")
        db.add(cuenta)
        db.flush()
        db.add(PushSubscription(usuario_id=uid, endpoint=f"https://push.test/{uid}", p256dh="x", auth="y"))
        db.add(Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion="Almuerzo", categoria="Comida",
                          tipo="expense", monto=10, fecha=fecha))
        db.commit()
    finally:
        db.close()


def test_resumen_semanal_una_vez_por_semana_iso(monkeypatch, pushes):
    lunes = datetime(2026, 7, 6, 20, 0)   # semana ISO 28
    _usuario_con_push_y_gasto("ci-semana", lunes)
    fijar_hoy(monkeypatch, lunes)
    r1 = client.post("/push/cron/resumen-semanal", headers=CABECERA).json()
    r2 = client.post("/push/cron/resumen-semanal", headers=CABECERA).json()
    assert r1["ok"] and r1["enviados"] >= 1 and "fallidos" in r1 and "procesados" in r1
    assert r2["enviados"] == 0
    assert len([p for p in pushes if p[0] == "ci-semana"]) == 1
    fijar_hoy(monkeypatch, datetime(2026, 7, 13, 20, 0))   # semana ISO 29: vuelve a avisar
    db = SessionLocal()
    db.query(Movimiento).filter(Movimiento.usuario_id == "ci-semana").update({"fecha": datetime(2026, 7, 12)})
    db.commit()
    db.close()
    client.post("/push/cron/resumen-semanal", headers=CABECERA)
    assert len([p for p in pushes if p[0] == "ci-semana"]) == 2


def test_resumen_semanal_libera_la_marca_si_el_envio_falla(monkeypatch):
    lunes = datetime(2026, 8, 3, 20, 0)
    _usuario_con_push_y_gasto("ci-semana-falla", lunes)
    fijar_hoy(monkeypatch, lunes)
    monkeypatch.setattr(push_router, "enviar_push", lambda *a, **k: 0)   # nada llegó
    client.post("/push/cron/resumen-semanal", headers=CABECERA)
    db = SessionLocal()
    try:
        assert db.query(MarcaCron).filter_by(usuario_id="ci-semana-falla", clave="resumen_semanal").first() is None
    finally:
        db.close()


# -------------------------------------------------------- recordar recurrentes

def _recurrente(uid, dia, alerta=2):
    db = SessionLocal()
    try:
        db.add(Recurrente(usuario_id=uid, nombre="Arriendo", monto=900_000, dia_del_mes=dia,
                          alerta_dias_antes=alerta))
        db.commit()
    finally:
        db.close()


def test_recurrente_avisa_una_vez_por_ocurrencia_no_por_mes(monkeypatch, pushes):
    _recurrente("ci-rec", dia=10, alerta=2)
    for dia in (8, 8, 9, 10):                       # ventana 8-10 de octubre: un solo aviso
        fijar_hoy(monkeypatch, datetime(2026, 10, dia, 9, 0))
        client.post("/push/cron/recordar-recurrentes", headers=CABECERA)
    assert len([p for p in pushes if p[0] == "ci-rec"]) == 1
    fijar_hoy(monkeypatch, datetime(2026, 11, 8, 9, 0))   # siguiente ocurrencia
    client.post("/push/cron/recordar-recurrentes", headers=CABECERA)
    assert len([p for p in pushes if p[0] == "ci-rec"]) == 2


def test_recurrente_con_aviso_de_la_ocurrencia_anterior_dentro_del_mismo_mes(monkeypatch, pushes):
    """Antes se comparaba año+mes: un aviso viejo del mismo mes bloqueaba la ocurrencia nueva."""
    _recurrente("ci-rec2", dia=25, alerta=2)
    db = SessionLocal()
    db.query(Recurrente).filter(Recurrente.usuario_id == "ci-rec2").update(
        {"ultima_notificacion_vencimiento": datetime(2026, 12, 3, 9, 0)})   # de una ocurrencia previa (día 5)
    db.commit()
    db.close()
    fijar_hoy(monkeypatch, datetime(2026, 12, 24, 9, 0))
    client.post("/push/cron/recordar-recurrentes", headers=CABECERA)
    assert len([p for p in pushes if p[0] == "ci-rec2"]) == 1


# ----------------------------------------------------------------------- backup

def test_backup_una_vez_al_dia(monkeypatch):
    llamadas = []
    monkeypatch.setattr(backup_router, "enviar_backup_por_correo", lambda: llamadas.append(1) or {"ok": True, "bytes": 5})
    dias = iter([datetime(2026, 9, 1, 3, 0)] * 2 + [datetime(2026, 9, 2, 3, 0)])
    monkeypatch.setattr(backup_router, "ahora_co", lambda: next(dias))
    r1 = client.post("/backup/cron/enviar", headers=CABECERA).json()
    r2 = client.post("/backup/cron/enviar", headers=CABECERA).json()
    r3 = client.post("/backup/cron/enviar", headers=CABECERA).json()
    assert r1["ok"] and r1["enviado"] is True and r1["procesados"] == 1 and r1["fallidos"] == 0
    assert r2["ok"] and r2["enviado"] is False
    assert r3["enviado"] is True and len(llamadas) == 2   # día nuevo: se envía


def test_backup_fallido_libera_la_marca_para_reintentar(monkeypatch):
    monkeypatch.setattr(backup_router, "ahora_co", lambda: datetime(2026, 9, 10, 3, 0))
    monkeypatch.setattr(backup_router, "enviar_backup_por_correo", lambda: {"ok": False, "error": "Resend no configurado"})
    assert client.post("/backup/cron/enviar", headers=CABECERA).status_code == 500
    monkeypatch.setattr(backup_router, "enviar_backup_por_correo", lambda: {"ok": True, "bytes": 1})
    assert client.post("/backup/cron/enviar", headers=CABECERA).json()["enviado"] is True


# ------------------------------------------------------------------ push seguro

def test_enviar_push_no_se_cae_con_errores_distintos_de_webpush(monkeypatch, caplog):
    from app.config import settings

    def _boom(**kw):
        raise ConnectionError("red caída https://secreto")

    monkeypatch.setattr(push_mod, "webpush", _boom)
    monkeypatch.setattr(settings, "vapid_private_key_pem", "pem-falso")
    _usuario_con_push_y_gasto("ci-push-red", ahora_co())
    db = SessionLocal()
    try:
        assert push_mod.enviar_push(db, "ci-push-red", "t", "c") == 0   # no lanza
    finally:
        db.close()
    assert "ConnectionError" in caplog.text and "secreto" not in caplog.text and "push.test" not in caplog.text


def test_todos_los_crons_devuelven_ok_procesados_fallidos(monkeypatch, pushes):
    monkeypatch.setattr(backup_router, "enviar_backup_por_correo", lambda: {"ok": True, "bytes": 1})
    monkeypatch.setattr(backup_router, "ahora_co", lambda: datetime(2027, 1, 5, 3, 0))
    rutas = [
        "/push/cron/revisar-presupuestos", "/push/cron/aportes-automaticos",
        "/push/cron/premiar-presupuestos-mes", "/push/cron/resumen-semanal",
        "/push/cron/recordar-recurrentes", "/push/cron/recordar-registro",
        "/backup/cron/enviar", "/patrimonio/cron/snapshot-mensual", "/patrimonio/cron/actualizar-precios",
    ]
    for ruta in rutas:
        r = client.post(ruta, headers=CABECERA).json()
        assert r["ok"] is True and "procesados" in r and "fallidos" in r, ruta
