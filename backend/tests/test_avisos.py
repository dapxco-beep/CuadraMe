"""Avisos de actividad para el administrador: eventos idempotentes, canales (push/correo/panel),
privacidad (correo enmascarado), control de ruido y acceso solo-admin. Datos sintéticos; Resend y el
push real se reemplazan por capturas."""
import json
import os
import tempfile
import threading
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'avisos.db')}")

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import avisos, crecimiento  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.limites_diarios import UsoDiario  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento, Perfil  # noqa: E402
from app.models_avisos import AjustesAvisos, EventoActividad  # noqa: E402
from app.models_comentarios import Comentario  # noqa: E402

client = TestClient(app)
ADMIN = UsuarioActual(id="av-admin", email="Dueno@CuadraMe.test", nombre="Dueño")
U1 = UsuarioActual(id="av-u1", email="daniela@gmail.com", nombre="Daniela Pérez")
U2 = UsuarioActual(id="av-u2", email="otro@test.com", nombre="Otro")
ACTUAL = {"u": U1}
PUSHES: list[tuple[str, str, str]] = []
CORREOS: list[tuple[str, str, str]] = []


def como(u):
    ACTUAL["u"] = u


def _limpiar():
    db = SessionLocal()
    try:
        for modelo in (EventoActividad, AjustesAvisos, Comentario):
            db.query(modelo).delete()
        db.query(MarcaCron).filter(MarcaCron.clave.in_(("avisos:resumen-diario", "comentarios:aviso"))).delete(
            synchronize_session=False)
        db.query(UsoDiario).filter(UsoDiario.usuario_id.in_((ADMIN.id, U1.id, U2.id))).delete(synchronize_session=False)
        for u in (ADMIN, U1, U2):
            db.query(Movimiento).filter(Movimiento.usuario_id == u.id).delete()
            db.query(Cuenta).filter(Cuenta.usuario_id == u.id).delete()
            db.query(Perfil).filter(Perfil.usuario_id == u.id).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    monkeypatch.setattr(settings, "admin_email", "dueno@cuadrame.test")
    monkeypatch.setattr(settings, "resend_api_key", "re_prueba")
    monkeypatch.setattr(avisos, "SINCRONO", True)
    PUSHES.clear()
    CORREOS.clear()
    monkeypatch.setattr(avisos, "enviar_push", lambda db, uid, titulo, cuerpo, url="/": PUSHES.append((uid, titulo, cuerpo)) or 1)
    monkeypatch.setattr(crecimiento, "_enviar", lambda d, a, t: CORREOS.append((d, a, t)))
    avisos.reiniciar_para_pruebas()
    _limpiar()
    como(U1)
    yield
    app.dependency_overrides.pop(get_current_user, None)
    _limpiar()


def eventos(tipo=None):
    db = SessionLocal()
    try:
        q = db.query(EventoActividad)
        if tipo:
            q = q.filter(EventoActividad.tipo == tipo)
        return q.order_by(EventoActividad.creado_en).all()
    finally:
        db.close()


def registrar_admin():
    """El administrador abre la app: queda su fila de ajustes (así el push sabe a qué celular ir)."""
    db = SessionLocal()
    try:
        avisos.asegurar_fila_admin(db, ADMIN.id)
    finally:
        db.close()


def dar_de_alta(u):
    avisos._procesar("nuevo_registro", u.id, u.email, None, f"nuevo_registro:{u.id}", True, True, False)


# ── Utilidades y privacidad ────────────────────────────────────────────────────────────
def test_enmascara_el_correo():
    assert avisos.enmascarar_correo("daniela@gmail.com") == "d***@gmail.com"
    assert avisos.enmascarar_correo("") == "***"
    assert avisos.enmascarar_correo("sin-arroba") == "***"


def test_el_aviso_lleva_correo_enmascarado_y_el_panel_el_completo():
    registrar_admin()
    avisos._procesar("nuevo_registro", U1.id, U1.email, None, f"nuevo_registro:{U1.id}", False, False, False)
    assert len(PUSHES) == 1 and len(CORREOS) == 1
    for texto in (PUSHES[0][1] + PUSHES[0][2], CORREOS[0][1] + CORREOS[0][2]):
        assert "d***@gmail.com" in texto or "Nuevo registro" in texto
        assert "daniela@gmail.com" not in texto and "Daniela" not in texto
    assert "d***@gmail.com se registró" in PUSHES[0][2]
    como(ADMIN)
    r = client.get("/avisos/actividad")
    assert r.status_code == 200
    assert r.json()["items"][0]["email"] == "daniela@gmail.com"


# ── nuevo_registro idempotente ─────────────────────────────────────────────────────────
def test_nuevo_registro_con_dos_peticiones_simultaneas_no_duplica(monkeypatch):
    db = SessionLocal()
    db.add(Perfil(usuario_id=U1.id, plan="free", creado_en=datetime.utcnow()))
    db.commit()
    db.close()
    barrera = threading.Barrier(2)
    errores = []

    def peticion():
        try:
            barrera.wait(timeout=5)
            avisos._revisar_usuario(U1.id, U1.email)
        except Exception as e:  # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=peticion) for _ in range(2)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert not errores
    assert len(eventos("nuevo_registro")) == 1
    avisos._revisar_usuario(U1.id, U1.email)  # una tercera vez: tampoco
    assert len(eventos("nuevo_registro")) == 1


def test_visto_solo_actua_la_primera_vez_por_proceso():
    avisos.visto(U1)
    avisos.visto(U1)
    assert len(eventos("nuevo_registro")) == 1


def test_un_usuario_de_antes_de_los_avisos_no_cuenta_como_nuevo():
    db = SessionLocal()
    db.add(Perfil(usuario_id=U1.id, plan="free", creado_en=datetime.utcnow() - timedelta(days=40)))
    db.add(Perfil(usuario_id=U2.id, plan="free"))
    db.commit()
    db.query(Perfil).filter(Perfil.usuario_id == U2.id).update({Perfil.creado_en: None})  # perfil anterior a creado_en
    db.commit()
    db.close()
    avisos._revisar_usuario(U1.id, U1.email)
    avisos._revisar_usuario(U2.id, U2.email)
    assert eventos("nuevo_registro") == []


def test_sin_perfil_pero_con_cuentas_tampoco_es_nuevo():
    db = SessionLocal()
    db.add(Cuenta(usuario_id=U1.id, nombre="Vieja", saldo=0))
    db.commit()
    db.close()
    avisos._revisar_usuario(U1.id, U1.email)
    assert eventos("nuevo_registro") == []


def test_registrar_un_evento_nunca_rompe_la_operacion(monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("base caída")

    monkeypatch.setattr(avisos, "SessionLocal", roto)
    avisos.registrar_evento("nuevo_registro", U1.id, U1.email, clave_unica="x")  # no lanza
    avisos.visto(U1)  # no lanza
    avisos.registrar_evento("tipo_que_no_existe")  # no lanza


# ── Activación ─────────────────────────────────────────────────────────────────────────
def test_primera_cuenta_y_primer_movimiento_una_sola_vez():
    dar_de_alta(U1)
    como(U1)
    r = client.post("/cuentas", json={"nombre": "Banco", "saldo": 100})
    assert r.status_code == 200
    cuenta_id = r.json()["id"]
    client.post("/cuentas", json={"nombre": "Otra", "saldo": 5})
    assert len(eventos("primera_cuenta")) == 1
    for _ in range(2):
        client.post("/movimientos", json={"cuenta_id": cuenta_id, "descripcion": "Secreto 99999", "monto": 12345,
                                          "tipo": "expense"})
    assert len(eventos("primer_movimiento")) == 1
    # sin montos ni descripciones en ningún evento
    for e in eventos():
        assert "12345" not in (e.resumen + (e.meta or "")) and "Secreto" not in (e.resumen + (e.meta or ""))


def test_quien_no_es_nuevo_no_genera_eventos_de_activacion():
    como(U2)  # sin evento nuevo_registro: llegó antes de los avisos
    client.post("/cuentas", json={"nombre": "Banco", "saldo": 1})
    assert eventos("primera_cuenta") == []


def test_atajo_activado_y_gmail_conectado():
    dar_de_alta(U1)
    db = SessionLocal()
    cuenta = Cuenta(usuario_id=U1.id, nombre="Tarjeta", saldo=0)
    db.add(cuenta)
    db.commit()
    db.add(Movimiento(usuario_id=U1.id, cuenta_id=cuenta.id, descripcion="x", monto=1, tipo="expense",
                      fecha=datetime.utcnow(), origen="atajo"))
    db.commit()
    perfil = Perfil(usuario_id=U1.id, plan="free", creado_en=datetime.utcnow())
    db.add(perfil)
    db.commit()
    perfil.gmail_conectado = True
    db.commit()
    perfil.gmail_conectado = True
    perfil.gmail_email = "x@y.com"
    db.commit()
    db.close()
    assert len(eventos("atajo_activado")) == 1
    assert len(eventos("gmail_conectado")) == 1
    assert eventos("gmail_conectado")[0].resumen == "d***@gmail.com conectó su Gmail"


def test_cuenta_eliminada_se_anota_sin_datos_de_la_persona():
    dar_de_alta(U1)
    como(U1)
    r = client.post("/perfil/eliminar-cuenta", json={"confirmacion": "ELIMINAR"})
    assert r.status_code == 200
    ev = eventos("cuenta_eliminada")
    assert len(ev) == 1
    assert ev[0].usuario_id is None and ev[0].email is None
    assert U1.id not in (ev[0].resumen + (ev[0].meta or ""))
    assert eventos("nuevo_registro") == []  # sus eventos se borraron con la cuenta
    avisos.visto(U1)  # el token viejo no la «registra» de nuevo
    assert eventos("nuevo_registro") == []


def test_limite_alcanzado_se_anota_una_vez_por_dia_y_accion(monkeypatch):
    from app import limites_diarios as ld
    from fastapi import HTTPException

    monkeypatch.setitem(ld.LIMITES_DIARIOS, "comentario", (1, "comentarios enviados"))
    db = SessionLocal()
    ld.consumir_cupo_diario(db, U1.id, "comentario")
    for _ in range(3):
        with pytest.raises(HTTPException) as e:
            ld.consumir_cupo_diario(db, U1.id, "comentario")
        assert e.value.status_code == 429
    db.close()
    assert len(eventos("limite_alcanzado")) == 1


# ── Comentarios unificados ─────────────────────────────────────────────────────────────
def test_comentario_problema_es_un_evento_y_un_solo_correo():
    registrar_admin()
    como(U1)
    r = client.post("/comentarios", json={"tipo": "problema", "mensaje": "No me carga mi saldo 4.000.000",
                                          "pantalla": "/movimientos"})
    assert r.status_code == 200
    assert len(eventos("comentario_problema")) == 1
    assert len(CORREOS) == 1 and len(PUSHES) == 1
    assert "4.000.000" not in CORREOS[0][2] + PUSHES[0][2]  # el texto del comentario no viaja en el aviso
    client.post("/comentarios", json={"tipo": "sugerencia", "mensaje": "Una idea"})
    assert len(eventos("comentario_problema")) == 1 and len(CORREOS) == 1


# ── Capacidad ──────────────────────────────────────────────────────────────────────────
def test_umbral_capacidad_se_registra_sin_duplicar_el_correo_del_monitor():
    registrar_admin()
    m = {"dia": "2026-10-10", "mes": "2026-10", "semana": "2026-W41"}
    cap = {"id": "gmail", "nombre": "usuarios con Gmail conectado"}
    señal = {"id": "errores_5xx", "actual": 31}
    crecimiento._registrar_eventos(m, [(cap, 80, [])], [señal])
    crecimiento._registrar_eventos(m, [(cap, 80, [])], [señal])  # reintento: no duplica
    assert len(eventos("umbral_capacidad")) == 1 and len(eventos("errores_5xx_picos")) == 1
    assert CORREOS == []  # el correo ya lo manda el monitor
    assert len(PUSHES) == 2


# ── Ruido ──────────────────────────────────────────────────────────────────────────────
def test_tope_por_hora_agrupa_en_un_solo_aviso(monkeypatch):
    registrar_admin()
    monkeypatch.setattr(avisos, "MAX_AVISOS_POR_HORA", 3)
    for i in range(7):
        avisos._procesar("gmail_conectado", f"u{i}", f"p{i}@test.com", None, f"gmail_conectado:u{i}", True, False, False)
    assert len(PUSHES) == 3  # los 3 primeros por separado
    assert len([e for e in eventos() if e.aviso_estado == "agrupado"]) == 4
    assert len(eventos()) == 7  # el panel los tiene todos
    avisos._envios.clear()  # pasó la hora
    avisos._procesar("gmail_conectado", "u9", "p9@test.com", None, "gmail_conectado:u9", True, False, False)
    assert PUSHES[3][1] == "4 eventos nuevos"
    assert len(PUSHES) == 5
    assert not [e for e in eventos() if e.aviso_estado == "agrupado"]


# ── Correo rechazado ───────────────────────────────────────────────────────────────────
def test_correo_rechazado_por_remitente_de_pruebas_no_se_reintenta(monkeypatch, caplog):
    registrar_admin()
    llamadas = []

    def rechazado(destino, asunto, texto):
        llamadas.append(asunto)
        resp = httpx.Response(403, request=httpx.Request("POST", "https://api.resend.com/emails"))
        raise httpx.HTTPStatusError("403", request=resp.request, response=resp)

    monkeypatch.setattr(crecimiento, "_enviar", rechazado)
    with caplog.at_level("WARNING", logger="app.avisos"):
        avisos._procesar("nuevo_registro", "x1", "a@test.com", None, "nuevo_registro:x1", False, False, False)
        avisos._procesar("nuevo_registro", "x2", "b@test.com", None, "nuevo_registro:x2", False, False, False)
    assert len(llamadas) == 1  # el segundo no vuelve a intentarlo
    assert any("RESEND_FROM" in r.message for r in caplog.records)
    assert len(PUSHES) == 2  # el push sigue llegando
    como(ADMIN)
    prefs = client.get("/avisos/preferencias").json()
    assert "RESEND_FROM" in prefs["canales"]["correo_error"]


# ── Acceso, panel y preferencias ───────────────────────────────────────────────────────
@pytest.mark.parametrize("metodo,ruta", [("GET", "/avisos/actividad"), ("GET", "/avisos/preferencias"),
                                         ("PUT", "/avisos/preferencias"), ("POST", "/avisos/probar")])
def test_quien_no_es_admin_recibe_404(metodo, ruta):
    como(U1)
    r = client.request(metodo, ruta, json={})
    assert r.status_code == 404


def test_cron_exige_secreto():
    assert client.post("/avisos/cron/resumen-diario").status_code == 401


def test_panel_con_contadores_filtro_y_registros_por_dia():
    registrar_admin()
    dar_de_alta(U1)
    dar_de_alta(U2)
    avisos._procesar("gmail_conectado", U1.id, None, None, f"gmail_conectado:{U1.id}", True, True, False)
    como(ADMIN)
    d = client.get("/avisos/actividad").json()
    assert d["total"] == 3
    assert d["contadores"]["por_tipo"]["nuevo_registro"]["hoy"] == 2
    assert d["contadores"]["total_7d"] == 3
    assert len(d["registros_por_dia"]) == 30
    assert sum(p["registros"] for p in d["registros_por_dia"]) == 2
    solo = client.get("/avisos/actividad?tipo=gmail_conectado").json()
    assert solo["total"] == 1 and solo["items"][0]["tipo"] == "gmail_conectado"
    assert {t["id"] for t in d["tipos"]} == set(avisos.TIPOS)


def test_preferencias_por_tipo_silencio_y_resumen_diario():
    como(ADMIN)
    base = client.get("/avisos/preferencias").json()
    assert base["max_por_hora"] == 20 and base["resumen_diario"] is False
    # Apagar el push de «Gmail conectado»
    r = client.put("/avisos/preferencias", json={"tipos": {"gmail_conectado": {"push": False, "correo": False}}})
    assert r.status_code == 200
    avisos._procesar("gmail_conectado", "g1", "g@test.com", None, "gmail_conectado:g1", True, False, False)
    assert PUSHES == [] and eventos("gmail_conectado")[0].aviso_estado == "sin_canal"
    # Silenciar 2 horas: se registra pero no avisa
    r = client.put("/avisos/preferencias", json={"silenciar_horas": 2})
    assert r.json()["silenciado_hasta"]
    avisos._procesar("nuevo_registro", "s1", "s@test.com", None, "nuevo_registro:s1", False, False, False)
    assert PUSHES == [] and CORREOS == []
    assert eventos("nuevo_registro")[0].aviso_estado == "silenciado"
    assert client.put("/avisos/preferencias", json={"silenciar_horas": 0}).json()["silenciado_hasta"] is None
    # Resumen diario: nada inmediato; el cron manda UN aviso
    client.put("/avisos/preferencias", json={"resumen_diario": True})
    for i in range(3):
        avisos._procesar("nuevo_registro", f"r{i}", f"r{i}@test.com", None, f"nuevo_registro:r{i}", False, False, False)
    assert PUSHES == [] and CORREOS == []
    r = client.post("/avisos/cron/resumen-diario", headers={"X-Cron-Secret": settings.cron_secret})
    assert r.status_code == 200 and r.json()["eventos"] == 3 and r.json()["enviado"] is True
    assert len(PUSHES) == 1 and "3 eventos" in PUSHES[0][1]
    assert len(CORREOS) == 1
    assert "@" not in PUSHES[0][2].replace("***@", "")  # solo correos enmascarados
    r2 = client.post("/avisos/cron/resumen-diario", headers={"X-Cron-Secret": settings.cron_secret})
    assert r2.json()["eventos"] == 0 and len(PUSHES) == 1  # idempotente


def test_probar_envia_aviso_de_prueba():
    como(ADMIN)
    r = client.post("/avisos/probar")
    assert r.status_code == 200 and r.json()["push"] == 1 and r.json()["correo"] is True
    assert PUSHES[0][0] == ADMIN.id
    assert json.dumps(r.json()).count("@") == 0
