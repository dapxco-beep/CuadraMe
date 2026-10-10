"""Buzón de opinión: validaciones, límites, aislamiento, panel solo-admin, CSV seguro y aviso por correo.
Datos sintéticos; el envío por Resend se reemplaza por una captura."""
import csv
import io
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'comentarios.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import avisos, crecimiento, limites  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.config import settings  # noqa: E402
from app.crons import MarcaCron  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.limites_diarios import UsoDiario  # noqa: E402
from app.main import app  # noqa: E402
from app.models_avisos import EventoActividad  # noqa: E402
from app.models_comentarios import Comentario  # noqa: E402
from app.routers import comentarios as rc  # noqa: E402

client = TestClient(app)
ADMIN = UsuarioActual(id="com-admin", email="Dueno@CuadraMe.test", nombre="Dueño")
U1 = UsuarioActual(id="com-u1", email="uno@test.com", nombre="Uno")
U2 = UsuarioActual(id="com-u2", email="dos@test.com", nombre="Dos")
ACTUAL = {"u": U1}


def como(u):
    ACTUAL["u"] = u


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    monkeypatch.setattr(settings, "admin_email", "dueno@cuadrame.test")
    monkeypatch.setattr(settings, "resend_api_key", "re_clave_de_prueba")
    db = SessionLocal()
    db.query(Comentario).delete()
    db.query(EventoActividad).delete()
    avisos.reiniciar_para_pruebas()
    db.query(MarcaCron).filter(MarcaCron.clave == rc.CLAVE_AVISO).delete()
    db.query(UsoDiario).filter(UsoDiario.accion == "comentario").delete()
    db.commit()
    db.close()
    limites._eventos.clear()
    como(U1)
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def correos(monkeypatch):
    """El aviso va por el mecanismo común (app/avisos.py): se captura el envío a Resend y se corre en línea."""
    enviados = []
    monkeypatch.setattr(avisos, "SINCRONO", True)
    monkeypatch.setattr(avisos, "enviar_push", lambda *a, **k: 0)
    monkeypatch.setattr(crecimiento, "_enviar", lambda destino, asunto, texto: enviados.append((destino, asunto, texto)))
    return enviados


def enviar(**kw):
    cuerpo = {"tipo": "sugerencia", "mensaje": "Me gustaría ver mis gastos por semana", "pantalla": "/movimientos"}
    cuerpo.update(kw)
    return client.post("/comentarios", json=cuerpo)


# ── Enviar ─────────────────────────────────────────────────────────────────────────────
def test_enviar_guarda_con_correo_y_contexto(correos):
    r = enviar(version_app="1.2.3", dispositivo="móvil · Chrome", puede_contactar=False, pantalla="/movimientos?mes=2026-01")
    assert r.status_code == 200 and r.json()["ok"] is True
    db = SessionLocal()
    c = db.query(Comentario).filter(Comentario.id == r.json()["id"]).one()
    assert (c.usuario_id, c.email, c.estado, c.tipo) == (U1.id, U1.email, "nuevo", "sugerencia")
    assert c.pantalla == "/movimientos"  # sin query: podría traer datos
    assert c.puede_contactar is False and c.dispositivo == "móvil · Chrome"
    db.close()


def test_mensaje_se_limpia_de_html_y_se_recorta():
    r = enviar(mensaje="  <script>alert(1)</script>Hola <b>mundo</b>  ")
    assert r.status_code == 200
    db = SessionLocal()
    assert db.query(Comentario).one().mensaje == "alert(1)Hola mundo"
    db.close()


@pytest.mark.parametrize("mensaje", ["", "   ", "<b></b>"])
def test_mensaje_vacio_es_rechazado_con_mensaje_amable(mensaje):
    r = enviar(mensaje=mensaje)
    assert r.status_code == 400 and "Cuéntanos" in r.json()["detail"]


def test_mensaje_demasiado_largo_y_limite_exacto():
    assert enviar(mensaje="a" * 2001).status_code == 400
    assert enviar(mensaje="a" * 2000).status_code == 200


def test_tipo_invalido():
    assert enviar(tipo="queja").status_code == 400


def test_limite_por_hora_10():
    for _ in range(10):
        assert enviar().status_code == 200
    r = enviar()
    assert r.status_code == 429 and "Ya nos escribiste" in r.json()["detail"]


def test_limite_diario_30(monkeypatch):
    from app import limites_diarios as ld

    monkeypatch.setitem(ld.LIMITES_DIARIOS, "comentario", (2, "comentarios enviados"))
    assert enviar().status_code == 200
    assert enviar().status_code == 200
    r = enviar()
    assert r.status_code == 429 and "comentarios enviados" in r.json()["detail"]


def test_falla_al_guardar_da_error_amable(monkeypatch):
    from sqlalchemy.orm import Session

    def _falla(self):
        raise RuntimeError("base caída")

    monkeypatch.setattr(Session, "commit", _falla)
    r = enviar()
    assert r.status_code == 503 and "No pudimos guardar" in r.json()["detail"]


# ── Lo mío y aislamiento ───────────────────────────────────────────────────────────────
def test_mios_solo_muestra_los_propios_con_estado_en_palabras_llanas(correos):
    enviar(mensaje="Comentario de uno")
    como(U2)
    enviar(mensaje="Comentario de dos")
    como(U1)
    lista = client.get("/comentarios/mios").json()
    assert [c["mensaje"] for c in lista] == ["Comentario de uno"]
    assert lista[0]["estado"] == "Recibido" and lista[0]["respuesta"] is None
    assert "email" not in lista[0] and "nota_admin" not in lista[0]
    # El admin responde: la persona ve la respuesta y el estado en llano, pero nunca la nota interna.
    como(ADMIN)
    cid = lista[0]["id"]
    r = client.patch(f"/comentarios/{cid}", json={"estado": "resuelto", "nota_admin": "secreto interno",
                                                  "respuesta_publica": "Ya quedó, gracias"})
    assert r.status_code == 200
    como(U1)
    visto = client.get("/comentarios/mios").json()[0]
    assert visto["estado"] == "Ya lo resolvimos" and visto["respuesta"] == "Ya quedó, gracias"
    assert "secreto interno" not in client.get("/comentarios/mios").text


def test_estados_en_palabras_llanas():
    assert rc.ESTADO_PUBLICO["en_curso"] == "Lo estamos revisando"
    assert rc.ESTADO_PUBLICO["descartado"] == "Gracias, lo tendremos en cuenta"


def test_no_admin_recibe_404_en_todas_las_rutas_de_admin():
    cid = enviar().json()["id"]
    for metodo, ruta, kw in (
        ("GET", "/comentarios", {}),
        ("GET", "/comentarios/exportar.csv", {}),
        ("PATCH", f"/comentarios/{cid}", {"json": {"estado": "visto"}}),
        ("POST", "/comentarios/marcar-vistos", {"json": {"ids": [cid]}}),
    ):
        r = client.request(metodo, ruta, **kw)
        assert r.status_code == 404, (metodo, ruta, r.status_code)
    db = SessionLocal()
    assert db.query(Comentario).one().estado == "nuevo"  # nadie lo tocó
    db.close()


def test_sin_admin_email_configurado_nadie_es_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "")
    como(ADMIN)
    assert client.get("/comentarios").status_code == 404


# ── Panel de administración ────────────────────────────────────────────────────────────
def _sembrar_variados():
    como(U1)
    enviar(tipo="elogio", mensaje="Me encanta la app")
    enviar(tipo="problema", mensaje="No carga el extracto 100%_raro")
    como(U2)
    enviar(tipo="pregunta", mensaje="¿Cómo conecto mi Gmail?", pantalla="/ayuda")
    como(ADMIN)


def test_lista_prioriza_nuevos_y_problemas_y_trae_conteos(correos):
    _sembrar_variados()
    d = client.get("/comentarios").json()
    assert d["total"] == 3 and d["items"][0]["tipo"] == "problema"
    assert d["por_estado"]["nuevo"] == 3 and d["por_tipo"]["elogio"] == 1 and d["por_tipo"]["sugerencia"] == 0
    # Al marcar el problema como visto deja de ir primero: lo nuevo manda.
    pid = d["items"][0]["id"]
    client.patch(f"/comentarios/{pid}", json={"estado": "visto"})
    assert client.get("/comentarios").json()["items"][-1]["id"] == pid


def test_filtros_y_busqueda(correos):
    _sembrar_variados()
    assert client.get("/comentarios?tipo=pregunta").json()["total"] == 1
    assert client.get("/comentarios?estado=resuelto").json()["total"] == 0
    assert client.get("/comentarios?q=gmail").json()["total"] == 1
    assert client.get("/comentarios?q=dos@test").json()["total"] == 1
    assert client.get("/comentarios?q=100%25_raro").json()["total"] == 1  # % y _ son literales
    assert client.get("/comentarios?q=%25").json()["total"] == 1  # no es comodín


def test_paginacion(correos):
    _sembrar_variados()
    p = client.get("/comentarios?por_pagina=2&pagina=2").json()
    assert p["total"] == 3 and len(p["items"]) == 1


def test_patch_valida_estado_y_actualiza(correos):
    cid = enviar().json()["id"]
    como(ADMIN)
    assert client.patch(f"/comentarios/{cid}", json={"estado": "inventado"}).status_code == 400
    assert client.patch("/comentarios/no-existe", json={"estado": "visto"}).status_code == 404
    r = client.patch(f"/comentarios/{cid}", json={"estado": "en_curso", "nota_admin": "<i>revisar</i>"}).json()
    assert r["estado"] == "en_curso" and r["nota_admin"] == "revisar"


def test_marcar_varios_como_vistos(correos):
    _sembrar_variados()
    ids = [c["id"] for c in client.get("/comentarios").json()["items"]]
    r = client.post("/comentarios/marcar-vistos", json={"ids": ids[:2] + ["no-existe"]}).json()
    assert r["actualizados"] == 2
    assert client.get("/comentarios").json()["por_estado"] == {
        "nuevo": 1, "visto": 2, "en_curso": 0, "resuelto": 0, "descartado": 0}


def test_csv_seguro_contra_formulas(correos):
    enviar(mensaje='=HYPERLINK("http://malo","clic")')
    enviar(mensaje="+cmd|' /C calc'!A0")
    enviar(mensaje="normal, con coma y\nsalto")
    como(ADMIN)
    r = client.get("/comentarios/exportar.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    filas = list(csv.reader(io.StringIO(r.text)))
    mensajes = [f[8] for f in filas[1:]]
    assert all(not m.startswith(("=", "+", "-", "@")) for m in mensajes)
    assert any(m.startswith("'=HYPERLINK") for m in mensajes)
    assert "normal, con coma y\nsalto" in mensajes


# ── Aviso al administrador ─────────────────────────────────────────────────────────────
def test_problema_avisa_por_correo_sin_texto_ni_correo_de_la_persona(correos):
    assert enviar(tipo="problema", mensaje="Se cae al subir").status_code == 200
    assert len(correos) == 1  # un solo correo (el mecanismo común; ya no hay uno propio del buzón)
    destino, asunto, texto = correos[0]
    assert destino == "dueno@cuadrame.test" and "Problema reportado" in asunto
    assert "Se cae al subir" not in texto  # el texto libre del comentario no viaja en el aviso
    assert U1.email not in texto  # ni el correo de la persona
    db = SessionLocal()
    assert db.query(EventoActividad).filter(EventoActividad.tipo == "comentario_problema").count() == 1
    db.close()


def test_un_comentario_normal_no_avisa_pero_5_nuevos_si(correos):
    for _ in range(4):
        enviar()
    assert correos == []
    enviar()
    assert len(correos) == 1 and "Comentarios sin revisar" in correos[0][1]
    enviar()
    assert len(correos) == 1  # máximo 1 por hora


def test_sin_admin_email_no_envia_y_no_falla(correos, monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "")
    assert enviar(tipo="problema").status_code == 200
    assert correos == []


def test_si_el_correo_falla_el_comentario_igual_se_guarda(monkeypatch):
    def _roto(*a):
        raise RuntimeError("Resend caído")

    monkeypatch.setattr(avisos, "SINCRONO", True)
    monkeypatch.setattr(avisos, "enviar_push", lambda *a, **k: 0)
    monkeypatch.setattr(crecimiento, "_enviar", _roto)
    assert enviar(tipo="problema").status_code == 200
    db = SessionLocal()
    assert db.query(Comentario).count() == 1
    assert db.query(EventoActividad).filter(EventoActividad.tipo == "comentario_problema").count() == 1  # queda en el panel
    db.close()
