"""El atajo de iPhone pregunta lo que el aviso no dice y APRENDE la respuesta (reglas personales, sin guardar el texto)."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'reglasnotif.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.reglas_notificacion import esqueleto, tipo_normal  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="rn-0", email="rn@test.com", nombre="RN")}
ENVIO = ("Tu plata llegó con éxito 💜", "Envío exitoso, la plata ya está en el Nequi destino. Recuerda que no se puede cancelar.")
RECIBO = ("Envío", "DANIEL PARRADO te envió 1, ¡lo mejor!")


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch):
    from cryptography.fernet import Fernet

    from app.config import settings

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def _usuario(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)
    assert client.post("/cuentas", json={"nombre": "Nequi", "saldo": 100000}).status_code == 200
    return {"X-Api-Key": client.get("/perfil/api-key").json()["api_key"]}


def _aviso(h, par, **extra):
    r = client.post("/movimientos/rapido-notificacion", headers=h,
                    json={"paquete": "Nequi", "titulo": par[0], "texto": par[1], **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_esqueleto_no_guarda_nombres_ni_montos():
    e = esqueleto(*RECIBO)
    assert "daniel" not in e and "parrado" not in e and "1" not in e and "te" in e.split()


def test_tipo_normal():
    assert tipo_normal("Gasto") == "expense" and tipo_normal("Ingreso") == "income" and tipo_normal("x") is None


def test_enviaste_pregunta_registra_y_aprende():
    h = _usuario("rn-1")
    assert _aviso(h, ENVIO)["motivo"] == "pedir_monto"
    r = _aviso(h, ENVIO, monto=25000, tipo="gasto", nota="parche con Laura")
    assert r["registrado"] and r["aprendido"] and r["por_confirmar"]
    movs = client.get("/movimientos").json()
    mov = movs[0] if isinstance(movs, list) else movs["items"][0]
    assert mov["monto"] == 25000 and mov["tipo"] == "expense" and "parche" in mov["descripcion"].lower()
    reglas = client.get("/movimientos/reglas-notificacion").json()
    assert len(reglas) == 1 and reglas[0]["app"] == "Nequi" and "no trae monto" in reglas[0]["significado"]
    assert "parche" not in str(reglas).lower() and "laura" not in str(reglas).lower()  # nunca el texto ni la nota


def test_recibiste_se_registra_como_ingreso_sin_preguntar():
    h = _usuario("rn-2")
    r = _aviso(h, RECIBO)
    assert r["registrado"] and "motivo" not in r


def test_direccion_dudosa_pregunta_y_luego_ya_no():
    h = _usuario("rn-3")
    dudoso = ("Nequi", "Movimiento por $50.000 en tu cuenta")
    assert _aviso(h, dudoso)["motivo"] == "pedir_tipo"
    r = _aviso(h, dudoso, monto=50000, tipo="ingreso")
    assert r["aprendido"]
    # La próxima vez con la misma forma de aviso ya no pregunta: se registra con lo aprendido.
    otro = ("Nequi", "Movimiento por $70.000 en tu cuenta")
    r2 = _aviso(h, otro)
    assert r2["registrado"] and "motivo" not in r2
    assert client.get("/movimientos/reglas-notificacion").json()[0]["usos"] == 1


def test_aprender_apagado_no_guarda_regla():
    h = _usuario("rn-4")
    _aviso(h, ENVIO, monto=1000, tipo="gasto", nota="x", aprender=False)
    assert client.get("/movimientos/reglas-notificacion").json() == []


def test_reglas_son_personales_y_se_pueden_borrar():
    h = _usuario("rn-5")
    _aviso(h, ENVIO, monto=2000, tipo="gasto", nota="x")
    regla = client.get("/movimientos/reglas-notificacion").json()[0]
    _usuario("rn-6")
    assert client.get("/movimientos/reglas-notificacion").json() == []
    assert client.delete(f"/movimientos/reglas-notificacion/{regla['id']}").status_code == 404  # no es suya
    USUARIO["actual"] = UsuarioActual(id="rn-5", email="rn-5@test.com", nombre="rn-5")
    assert client.delete(f"/movimientos/reglas-notificacion/{regla['id']}").status_code == 200
    assert client.get("/movimientos/reglas-notificacion").json() == []


def test_migracion_crea_la_tabla_sin_errores_de_sintaxis():
    """Los tests usan create_all; esto ejecuta el SQL REAL de la migración (un `DEFAULT ''` mal escapado tumbó un despliegue)."""
    from sqlalchemy import create_engine, text

    from app.migraciones import MIGRACIONES

    sentencias = next(s for nombre, s in MIGRACIONES if nombre == "0013_reglas_notificacion")
    motor = create_engine("sqlite://")
    with motor.begin() as conn:
        for sql in sentencias:
            conn.execute(text(sql))
        conn.execute(text("INSERT INTO reglas_notificacion (id, usuario_id) VALUES ('1', 'u')"))
        fila = conn.execute(text("SELECT app, esqueleto FROM reglas_notificacion")).one()
    assert tuple(fila) == ("", "")


def test_estado_notificaciones_dice_que_bancos_faltan_por_conectar():
    from app.notificaciones import banco_de_cuenta

    assert banco_de_cuenta("Nu Colombia") == "Nu" and banco_de_cuenta("Nequi") == "Nequi"
    assert banco_de_cuenta("Efectivo") is None and banco_de_cuenta("Nueva billetera") is None  # «nu» no es «nueva»
    h = _usuario("rn-7")
    assert client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 0}).status_code == 200
    assert client.post("/cuentas", json={"nombre": "Efectivo", "saldo": 0}).status_code == 200
    antes = {e["app"]: e for e in client.get("/movimientos/estado-notificaciones").json()}
    assert set(antes) == {"Nequi", "Nu"} and antes["Nequi"]["ultimo_aviso"] is None and antes["Nequi"]["avisos_30d"] == 0
    assert _aviso(h, RECIBO)["registrado"]
    despues = {e["app"]: e for e in client.get("/movimientos/estado-notificaciones").json()}
    assert despues["Nequi"]["avisos_30d"] == 1 and despues["Nequi"]["ultimo_aviso"] and despues["Nu"]["avisos_30d"] == 0


def _formas_de_aviso():
    from app.database import SessionLocal
    from app.models import FormaAsuntoFallida

    db = SessionLocal()
    try:
        return [(f.esqueleto, f.dominio, f.conteo) for f in db.query(FormaAsuntoFallida).filter(FormaAsuntoFallida.dominio.like("aviso:%")).all()]
    finally:
        db.close()


def _consentir(si):
    from app.routers import consentimientos as consent

    r = client.post("/consentimientos", json={"version": consent.VERSION_TEXTOS,
                                              "items": [{"finalidad": "estadisticas_anonimas", "aceptado": si}]})
    assert r.status_code == 200, r.text


def test_avisos_que_no_se_entienden_se_cuentan_solo_con_estadisticas_anonimas_y_sin_datos():
    h = _usuario("rn-8")
    raro = ("Nequi", "Tu saldo cambió, revisa tu movimiento reciente con DANIEL PARRADO en tu cuenta")
    antes = len(_formas_de_aviso())
    assert _aviso(h, raro)["motivo"] == "no_parece_un_movimiento"
    assert len(_formas_de_aviso()) == antes  # sin autorización no se anota nada
    _consentir(True)
    assert _aviso(h, raro)["motivo"] == "no_parece_un_movimiento"
    assert _aviso(h, raro)["motivo"] == "no_parece_un_movimiento"
    formas = [f for f in _formas_de_aviso() if f[1] == "aviso:nequi"]
    assert formas and formas[-1][2] == 2
    assert "daniel" not in str(formas).lower() and "parrado" not in str(formas).lower()
    # El ruido (promociones, códigos) no se cuenta como «aviso no entendido».
    n = len(_formas_de_aviso())
    _aviso(h, ("Nequi", "Ofertas", "Todos piden OFERTA a solo $14.968"))
    assert len(_formas_de_aviso()) == n
    _consentir(False)


# ---- Atajo «CuadraMe Registrar» (pantallazo): deduce la cuenta y solo pregunta si no hay forma de saberla ----------

def _pantallazo(h, texto, **extra):
    r = client.post("/movimientos/rapido-notificacion", headers=h,
                    json={"paquete": "auto", "titulo": "", "texto": texto, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _cuentas_nu_nequi(uid):
    h = _usuario(uid)  # crea «Nequi»
    assert client.post("/cuentas", json={"nombre": "Nu Colombia", "saldo": 500000}).status_code == 200
    return h


def _movimiento_mas_reciente():
    movs = client.get("/movimientos").json()
    return movs[0] if isinstance(movs, list) else movs["items"][0]


def test_pantallazo_deduce_la_cuenta_del_propio_texto_y_el_destinatario_sin_preguntar():
    h = _cuentas_nu_nequi("rn-a1")
    r = _pantallazo(h, "11:03 Nu Comprobante Transferencia exitosa $ 45.000 Para LAURA GOMEZ Banco Nequi Compartir")
    assert r["registrado"] and "motivo" not in r
    mov = _movimiento_mas_reciente()
    cuentas = {c["id"]: c["nombre"] for c in client.get("/cuentas").json()}
    assert cuentas[mov["cuenta_id"]] == "Nu Colombia"
    assert mov["monto"] == 45000 and mov["tipo"] == "expense" and mov["descripcion"] == "Envío a Laura Gomez"


def test_pantallazo_sin_banco_en_el_texto_pregunta_una_vez_y_aprende():
    h = _cuentas_nu_nequi("rn-a2")
    texto = "Transferencia exitosa $ 20.000 Para CARLOS RUIZ Compartir Descargar"
    r = _pantallazo(h, texto)
    assert r["motivo"] == "pedir_cuenta" and set(r["cuentas"]) == {"Nequi", "Nu Colombia"}
    r2 = _pantallazo(h, texto, cuenta="Nu Colombia")
    assert r2["registrado"]
    # La próxima vez con la misma forma de pantallazo (otro monto y otra persona) ya no pregunta
    r3 = _pantallazo(h, "Transferencia exitosa $ 35.000 Para ANA TORRES Compartir Descargar")
    assert r3["registrado"] and "motivo" not in r3
    cuentas = {c["id"]: c["nombre"] for c in client.get("/cuentas").json()}
    assert cuentas[_movimiento_mas_reciente()["cuenta_id"]] == "Nu Colombia"
    regla = [x for x in client.get("/movimientos/reglas-notificacion").json() if x["app"].startswith("pantalla:")]
    assert regla and "Nu Colombia" in regla[0]["significado"] and "carlos" not in str(regla).lower()


def test_pantallazo_que_no_es_un_movimiento_no_pregunta_nada():
    h = _cuentas_nu_nequi("rn-a3")
    assert _pantallazo(h, "Mensajes Hoy Mamá: ¿vienes a almorzar? Fotos Cámara")["motivo"] == "no_parece_un_movimiento"


def test_pantallazo_con_dos_bancos_en_el_texto_gana_el_primero_el_de_origen():
    h = _cuentas_nu_nequi("rn-a4")
    r = _pantallazo(h, "Transferencia exitosa $ 9.000 de Nu a Nequi")
    assert r["registrado"] and "motivo" not in r
    cuentas = {c["id"]: c["nombre"] for c in client.get("/cuentas").json()}
    assert cuentas[_movimiento_mas_reciente()["cuenta_id"]] == "Nu Colombia"
