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


def test_pantallazo_sin_pista_del_banco_va_a_la_cuenta_que_mas_usa_sin_preguntar_y_se_corrige_una_vez():
    h = _cuentas_nu_nequi("rn-a2")
    # La persona ya usa Nu: un comprobante sin el nombre del banco cae ahí, SIN preguntar nada, y se lo dice
    assert _pantallazo(h, _nu_comprobante(_ayer()))["registrado"]
    sin_banco = "Transferencia exitosa $ 20.000 Para CARLOS RUIZ Compartir Descargar"
    r = _pantallazo(h, sin_banco)
    assert r["registrado"] and "motivo" not in r, r
    assert r["cuenta_adivinada"] == "Nu Colombia" and "no pude saber de qué banco" in r["mensaje"]
    # Si era de Nequi, lo corrige UNA vez (la app manda la cuenta) y esa forma de pantallazo queda aprendida
    r2 = _pantallazo(h, "Transferencia exitosa $ 35.000 Para ANA TORRES Compartir Descargar", cuenta="Nequi")
    assert r2["registrado"]
    r3 = _pantallazo(h, "Transferencia exitosa $ 41.000 Para LUIS GOMEZ Compartir Descargar")
    assert r3["registrado"] and r3["cuenta_adivinada"] is None and "Ojo" not in r3["mensaje"]
    assert _cuenta_nombre(_movimiento_mas_reciente()) == "Nequi"
    regla = [x for x in client.get("/movimientos/reglas-notificacion").json() if x["app"].startswith("pantalla:")]
    assert regla and "Nequi" in regla[0]["significado"] and "carlos" not in str(regla).lower()


def test_pantallazo_que_no_es_un_movimiento_no_pregunta_nada():
    h = _cuentas_nu_nequi("rn-a3")
    r = _pantallazo(h, "Mensajes Hoy Mamá: ¿vienes a almorzar? Fotos Cámara")
    assert r["motivo"] == "no_parece_un_movimiento"
    assert "No encontré un pago en esta pantalla" in r["mensaje"]  # el atajo de pantallazo no puede quedarse mudo


def test_pantallazo_con_dos_bancos_en_el_texto_gana_el_primero_el_de_origen():
    h = _cuentas_nu_nequi("rn-a4")
    r = _pantallazo(h, "Transferencia exitosa $ 9.000 de Nu a Nequi")
    assert r["registrado"] and "motivo" not in r
    cuentas = {c["id"]: c["nombre"] for c in client.get("/cuentas").json()}
    assert cuentas[_movimiento_mas_reciente()["cuenta_id"]] == "Nu Colombia"


# ---- Pantallas reales de Nu y Nequi (misma estructura que las capturas; nombres, llaves y referencias INVENTADOS) -------------
# Las fechas son las de AYER: el servidor solo acepta la fecha de un comprobante si es de los últimos 7 días (si no, usa «ahora»).
from datetime import timedelta  # noqa: E402

from app.utiles import ahora_co  # noqa: E402

_ABR = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _ayer():
    return ahora_co() - timedelta(days=1)


def _nu_comprobante(d):
    return (f"8:10 48 Comprobante de transferencia {d.day:02d} {_ABR[d.month - 1].upper()} {d.year} - 20:08:29 "
            "Monto total $24.000,00 Monto $24.000,00 Impuesto 4x1.000 $0,00 Vía Bre-B "
            "Número de comprobante (ID MOL) 20269999999999999ENT111111111111111 "
            "Para Nombre ANA PEREZ Entidad Nequi S.A. CF Llave 3001112233")


def _nu_detalle(d):
    return (f"8:10 47 CARLOS RUIZ $23.000,00 {d.day:02d} de {_MES[d.month - 1]} de {d.year}, 12:52 "
            "Transferencia inmediata Bre-B Reportar un problema Abrir comprobante Monto total $23.000,00 "
            "Impuesto 4x1.000 $0,00 Enviaste a su cuenta de Bancolombia Llave 12345678")


def _nequi_detalle(d):
    return ("8:11 47 Detalle del movimiento Envío Realizado ¡Escanea este QR con Nequi para verificar tu envío al "
            "instante! Para Maria De La Torre ¿Cuánto? $ 1,00 Número Nequi 300 111 2233 "
            f"Fecha {d.day:02d} de {_MES[d.month - 1]} de {d.year} a las 10:52 p. m. Referencia M99999999 "
            "¿De dónde salió la plata? Disponible ¿Algún problema con este movimiento?")


def _cuenta_nombre(mov):
    return {c["id"]: c["nombre"] for c in client.get("/cuentas").json()}[mov["cuenta_id"]]


@pytest.mark.parametrize("construir,cuenta,monto,descripcion,hora", [
    (_nu_comprobante, "Nu Colombia", 24000, "Envío a Ana Perez", "T20:08:29"),
    (_nu_detalle, "Nu Colombia", 23000, "Envío a Carlos Ruiz", "T12:52:00"),
    (_nequi_detalle, "Nequi", 1, "Envío a Maria De La Torre", "T22:52:00"),
])
def test_pantallas_reales_se_registran_completas_sin_preguntar(construir, cuenta, monto, descripcion, hora):
    h = _cuentas_nu_nequi(f"rn-r{monto}")
    d = _ayer()
    r = _pantallazo(h, construir(d))
    assert r["registrado"] and "motivo" not in r, r
    mov = _movimiento_mas_reciente()
    assert _cuenta_nombre(mov) == cuenta  # el «Entidad Nequi» del comprobante de Nu es el DESTINO, no la cuenta de origen
    assert (mov["monto"], mov["tipo"], mov["descripcion"]) == (monto, "expense", descripcion)
    assert mov["fecha"].startswith(f"{d:%Y-%m-%d}{hora}")


def test_leer_dos_veces_el_mismo_comprobante_no_duplica():
    h = _cuentas_nu_nequi("rn-dup")
    texto = _nu_comprobante(_ayer())
    assert _pantallazo(h, texto)["registrado"]
    antes = len(client.get("/movimientos").json())
    r2 = _pantallazo(h, texto)
    assert r2["duplicado"] is True and not r2["registrado"]
    assert len(client.get("/movimientos").json()) == antes


def test_fecha_destinatario_e_id_de_los_comprobantes():
    from app.notificaciones import _destinatario, _fecha_en_texto, _id_comprobante

    assert _fecha_en_texto("05 NOV 2026 - 20:08:29") == "2026-11-05T20:08:29"
    assert _fecha_en_texto("06 de noviembre de 2026, 12:52") == "2026-11-06T12:52:00"
    assert _fecha_en_texto("05 de noviembre de 2026 a las 12:05 a. m.") == "2026-11-05T00:05:00"
    assert _fecha_en_texto("05 de noviembre de 2026 a las 1:05 p. m.") == "2026-11-05T13:05:00"
    assert _fecha_en_texto("Tu pago de $5.000 fue exitoso") is None
    assert _destinatario("Para Nombre ANA PEREZ Entidad Nequi S.A. CF Llave 1") == "Ana Perez"
    assert _destinatario("Para Maria De La Torre ¿Cuánto? $ 1,00") == "Maria De La Torre"
    assert _destinatario("LUIS GOMEZ $5.000,00 06 de noviembre") == "Luis Gomez"
    assert _destinatario("Pagaste en JUMBO para toda la familia") == ""
    assert _id_comprobante("(ID MOL) 20269999ENT1234567890") == "20269999ENT1234567890"
    assert _id_comprobante("Referencia M99999999 ¿De dónde") == "M99999999"


# ---- Comprobante de transferencia de Bancolombia (misma estructura que la captura; datos INVENTADOS) -------------------------
def _bancolombia(d):
    return (f"¡Transferencia exitosa! Comprobante No. 7J9WA127VQ {d.day:02d} {_ABR[d.month - 1].capitalize()} {d.year} - 11:50 a. m. "
            "Datos de la transferencia Valor de la transferencia $ 25.000 Producto destino Nequi 3001112233 "
            "Producto origen Cuenta de Ahorros Ahorros *4321")


def _cuentas_con_bancolombia(uid, alias=None):
    h = _cuentas_nu_nequi(uid)
    cuerpo = {"nombre": "Bancolombia Ahorros", "saldo": 800000}
    if alias:
        cuerpo["alias_tarjeta"] = alias
    assert client.post("/cuentas", json=cuerpo).status_code == 200
    return h


def test_comprobante_de_bancolombia_sin_nombre_usa_el_producto_destino_y_la_cuenta_por_su_huella():
    h = _cuentas_con_bancolombia("rn-bc1")
    d = _ayer()
    r = _pantallazo(h, _bancolombia(d))
    assert r["registrado"] and "motivo" not in r, r
    mov = _movimiento_mas_reciente()
    assert _cuenta_nombre(mov) == "Bancolombia Ahorros"  # «Producto origen/destino» es de Bancolombia; Nequi es solo el destino
    assert (mov["monto"], mov["tipo"], mov["descripcion"]) == (25000, "expense", "Envío a Nequi ·2233")
    assert mov["fecha"].startswith(f"{d:%Y-%m-%d}T11:50")


def test_los_ultimos_digitos_de_la_cuenta_de_origen_la_identifican_por_su_alias():
    h = _cuentas_con_bancolombia("rn-bc2", alias="4321")
    assert client.post("/cuentas", json={"nombre": "Bancolombia Corriente", "saldo": 1, "alias_tarjeta": "9999"}).status_code == 200
    r = _pantallazo(h, _bancolombia(_ayer()))  # dos cuentas Bancolombia: solo el *4321 del comprobante decide cuál es
    assert r["registrado"] and "motivo" not in r, r
    assert _cuenta_nombre(_movimiento_mas_reciente()) == "Bancolombia Ahorros"


def test_pantalla_de_compra_con_tarjeta_es_un_gasto_sin_preguntar():
    from app.notificaciones import interpretar

    n = interpretar("auto", "", "Jumbo Calle 80 $45.900,00 COP Hoy 8:15 a. m. Visa ••1234 Apple Pay")
    assert n is not None and (n.monto, n.tipo) == (45900, "expense") and not n.tipo_incierto


@pytest.mark.parametrize("crudo,esperado", [
    ("$45,900.00", 45900), ("$45.900,00", 45900), ("45900", 45900), ("COP 45.900,00", 45900), ("$ 1,00", 1),
])
def test_wallet_acepta_el_importe_en_cualquier_formato_que_entregue_ios(crudo, esperado):
    h = _usuario(f"rn-w{abs(hash(crudo)) % 9999}")
    r = client.post("/movimientos/rapido", headers=h, json={"comercio": "JUMBO", "monto": crudo, "tarjeta": "Visa 1234", "fuente": "wallet"})
    assert r.status_code == 200, r.text
    assert r.json()["monto"] == esperado


# ---- Ingresos: «Recibiste de…» (Nu) y «Envío Recibido» (Nequi). Misma estructura que las capturas; datos INVENTADOS ----------

def _nu_recibido(d):
    return (f"8:25 45 Recibiste de Ana Perez $6.400,00 {d.day:02d} {_ABR[d.month - 1]} {d.year}, 16:31 Aceptada "
            "Transferencia Bre-B Reportar problema Llave @ABC123 Institución de origen Nu")


def _nequi_recibido(d):
    return ("8:26 44 Detalle del movimiento Envío Recibido ¡Escanea este QR con Nequi para verificar tu envío al instante! "
            f"De Maria De La Torre ¿Cuánto? $ 1,00 Fecha {d.day:02d} de {_MES[d.month - 1]} de {d.year} a las 10:51 p. m. "
            "Referencia M88888888")


@pytest.mark.parametrize("construir,cuenta,monto,descripcion,hora", [
    (_nu_recibido, "Nu Colombia", 6400, "De Ana Perez", "T16:31:00"),
    (_nequi_recibido, "Nequi", 1, "De Maria De La Torre", "T22:51:00"),
])
def test_ingresos_se_registran_completos_sin_preguntar(construir, cuenta, monto, descripcion, hora):
    h = _cuentas_nu_nequi(f"rn-i{monto}")
    d = _ayer()
    r = _pantallazo(h, construir(d))
    assert r["registrado"] and "motivo" not in r, r
    mov = _movimiento_mas_reciente()
    assert _cuenta_nombre(mov) == cuenta
    assert (mov["monto"], mov["tipo"], mov["descripcion"]) == (monto, "income", descripcion)
    assert mov["fecha"].startswith(f"{d:%Y-%m-%d}{hora}")


def test_la_institucion_de_origen_es_la_de_quien_te_envio_no_tu_cuenta():
    # «Institución de origen Nu» = el banco del que ENVIÓ. No es pista de tu cuenta: se usa la apuesta por uso (aquí «Nequi», la
    # primera por nombre), no Nu, y se avisa para que la corrijas si era otra.
    h = _cuentas_nu_nequi("rn-io")
    r = _pantallazo(h, "Recibiste de Ana Perez $5.000,00 Aceptada Llave @ABC Institución de origen Nu")
    assert r["registrado"] and r["cuenta_adivinada"] == "Nequi" and "Ojo" in r["mensaje"]


def test_cada_uso_deja_una_linea_de_diagnostico_sin_datos_personales(caplog):
    import logging

    h = _cuentas_nu_nequi("rn-log")
    texto = "Transferencia exitosa $ 20.000 Para CARLOS RUIZ Compartir Descargar"  # sin banco: se adivina la cuenta
    with caplog.at_level(logging.INFO, logger="cuadrame.atajo"):
        assert _pantallazo(h, texto)["registrado"]
        client.post("/movimientos/rapido", headers=h, json={"comercio": "JUMBO", "monto": "5.000", "tarjeta": "Visa 1", "fuente": "wallet"})
    lineas = [r.getMessage() for r in caplog.records if r.getMessage().startswith("atajo")]
    assert any("paquete=auto" in l and "cuenta_adivinada=True" in l and f"texto_len={len(texto)}" in l and "forma=" in l for l in lineas)
    assert any("atajo rapido fuente=wallet con_comercio=True con_tarjeta=True" in l for l in lineas)
    todo = " ".join(lineas).lower()
    assert "carlos" not in todo and "20.000" not in todo and "ruiz" not in todo and "cdm_" not in todo  # la forma es anónima

# ---- Atajos de versiones anteriores: iOS no los actualiza, así que el propio atajo les explica cómo cambiarlo -----------------

def test_el_atajo_anterior_recibe_una_vez_al_dia_como_actualizarse_y_el_nuevo_nunca():
    h = _usuario("rn-viejo")
    # Atajo anterior: manda el nombre del banco («Nequi»), no «auto»
    r = _aviso(h, RECIBO)
    assert r["registrado"] and "Hay una versión nueva de este atajo" in r["mensaje"]
    assert "Perfil › Registro automático" in r["mensaje"] and "Instalar" in r["mensaje"] and "Agregar atajo" in r["mensaje"]
    # Solo una vez al día: no se repite en cada uso
    r2 = _aviso(h, ("Envío", "ANA PEREZ te envió 2, ¡lo mejor!"))
    assert r2["registrado"] and "versión nueva" not in r2["mensaje"]
    # El atajo nuevo (paquete «auto») no recibe el aviso nunca
    h2 = _cuentas_nu_nequi("rn-nuevo")
    r3 = _pantallazo(h2, _nu_comprobante(_ayer()))
    assert r3["registrado"] and "versión nueva" not in r3["mensaje"]


def test_android_no_recibe_el_aviso_de_atajo_viejo():
    h = _usuario("rn-android")
    r = client.post("/movimientos/rapido-notificacion", headers=h,
                    json={"paquete": "com.nequi.MobileApp", "titulo": "Envío", "texto": "ANA PEREZ te envió 3, ¡lo mejor!"})
    assert r.status_code == 200 and r.json()["registrado"] and "versión nueva" not in r.json()["mensaje"]
