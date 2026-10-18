"""Reglas PERSONALES de lectura de correos («enséñale a leer este correo»): esqueleto sin datos personales,
aprender del ICETEX de Nu aunque el lector estándar falle, aplicar a un segundo correo parecido y no pisar
una lectura estándar correcta. Todo sintético."""
import base64
from types import SimpleNamespace

import pytest

from app import reglas_correo as rc
from app.routers import correos as rcor
from tests.test_extractos_gmail import mensaje

REM = "Nu <nu@nu.com.co>"
ASUNTO = "Pagaste con tu Cuenta de ahorros Nu"
CUERPO = ("Hola, Daniel Alfonso: Acá está el detalle de tu pago. Pagaste en: ICETEX. La cantidad de: $1.000.000,00. "
          "Más el impuesto del 4xmil de: $0,00. Si no fuiste tú, contáctanos vía chat")
CUERPO2 = ("Hola, Daniel Alfonso: Acá está el detalle de tu pago. Pagaste en: Colegio San José. La cantidad de: $350.000,00. "
           "Más el impuesto del 4xmil de: $0,00. Si no fuiste tú, contáctanos vía chat")


def _regla(**kw):
    base = dict(id="r1", usuario_id="u1", remitente_dominio="nu.com.co", esqueleto_asunto="", etiqueta_monto=None,
                etiqueta_comercio=None, tipo="expense", corrige=False, usos=0)
    base.update(kw)
    return SimpleNamespace(**base)


def _aprendida(corrige=False, tipo="expense"):
    marcas = rc.derivar_regla(f"{ASUNTO} {CUERPO}", "$1.000.000,00", "ICETEX")
    return _regla(esqueleto_asunto=rc.esqueleto_asunto(ASUNTO), tipo=tipo, corrige=corrige, **marcas)


def _msg(id_, cuerpo, asunto=ASUNTO):
    data = base64.urlsafe_b64encode(cuerpo.encode()).decode()
    return mensaje(id_, REM, asunto, snippet="Hola, Daniel Alfonso: Acá está el detalle de tu pago.",
                   partes=[{"mimeType": "text/plain", "body": {"data": data}}])


class _Modelo:
    def clasificar(self, comercio, texto):
        return None


# ── Esqueleto del asunto ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("asunto,esperado", [
    ("Pagaste en X con Cuenta Nu", "pagaste en * con cuenta nu"),
    ("Pagaste con tu Cuenta de ahorros Nu", "pagaste con tu cuenta de ahorros nu"),
    ("Compra por $45.000 en RAPPI", "compra por * en *"),
    ("Recibiste dinero de Ana Pérez", "recibiste dinero de *"),
    ("Transferencia 123456 aprobada", "transferencia * aprobada"),
])
def test_esqueleto_sin_numeros_ni_nombres(asunto, esperado):
    assert rc.esqueleto_asunto(asunto) == esperado


def test_esqueleto_anonimo_no_trae_digitos_ni_nombres():
    asuntos = ["Pagaste en Colegio San José con Cuenta Nu", "Ana Pérez te envió $50.000", "Compra por $45.000 en RAPPI",
               "Transferencia 123456 aprobada a Juan Valdez", "Daniel Alfonso, pagaste en ICETEX", "Aviso a ana@correo.com"]
    for a in asuntos:
        esq = rc.esqueleto_anonimo(a)
        assert not any(ch.isdigit() for ch in esq), esq
        assert all(p == "*" or p in rc.VOCABULARIO for p in esq.split()), esq
        for nombre in ("ana", "perez", "juan", "valdez", "daniel", "alfonso", "icetex", "rappi", "jose", "colegio"):
            assert nombre not in esq.split(), (a, esq)
    assert rc.esqueleto_anonimo("Hola Pedro") == ""  # nada informativo


def test_dominio_remitente():
    assert rc.dominio_remitente("Nu <aviso@mail.nu.com.co>") == "nu.com.co"
    assert rc.dominio_remitente("x@bancolombia.com.co") == "bancolombia.com.co"
    assert rc.dominio_remitente("Ana <ana@gmail.com>") == "ana@gmail.com"
    assert rc.dominio_anonimo("Ana <ana@gmail.com>") == ""


# ── Aprender y aplicar ──────────────────────────────────────────────────────────────────────
def test_aprende_icetex_y_lee_aunque_el_estandar_falle():
    regla = _aprendida()
    assert regla.etiqueta_monto.endswith("cantidad de:")
    assert regla.etiqueta_comercio == "pagaste en:"
    # El cuerpo no se guarda: la regla solo trae etiquetas de plantilla.
    assert "icetex" not in (regla.etiqueta_monto + regla.etiqueta_comercio) and "1.000" not in regla.etiqueta_monto
    out = rc.aplicar_regla({"remitente": REM, "asunto": ASUNTO, "texto": f"{ASUNTO} {CUERPO}",
                            "monto": 0, "comercio": "Gasto sin detalle", "tipo": "expense"}, [regla])
    assert out["monto"] == 1_000_000 and out["comercio"] == "Icetex" and out["regla_id"] == "r1"


def test_aplica_a_un_segundo_correo_parecido():
    regla = _aprendida()
    out = rc.aplicar_regla({"remitente": REM, "asunto": ASUNTO, "texto": f"{ASUNTO} {CUERPO2}",
                            "monto": 0, "comercio": "Gasto sin detalle", "tipo": "expense"}, [regla])
    assert out["monto"] == 350_000 and out["comercio"] == "Colegio San José"


def test_no_pisa_una_lectura_estandar_correcta():
    regla = _aprendida()
    out = rc.aplicar_regla({"remitente": REM, "asunto": ASUNTO, "texto": f"{ASUNTO} {CUERPO2}",
                            "monto": 12_345, "comercio": "Pago a Alguien", "tipo": "expense"}, [regla])
    assert out is None


def test_si_la_persona_corrigio_a_proposito_la_regla_si_manda():
    regla = _aprendida(corrige=True)
    out = rc.aplicar_regla({"remitente": REM, "asunto": ASUNTO, "texto": f"{ASUNTO} {CUERPO2}",
                            "monto": 12_345, "comercio": "Pago a Alguien", "tipo": "expense"}, [regla])
    assert out["monto"] == 350_000 and out["comercio"] == "Colegio San José"


def test_otro_remitente_o_asunto_no_coincide():
    regla = _aprendida()
    base = {"texto": f"{ASUNTO} {CUERPO}", "monto": 0, "comercio": "Gasto sin detalle", "tipo": "expense"}
    assert rc.aplicar_regla({**base, "remitente": "Otro <a@otrobanco.com>", "asunto": ASUNTO}, [regla]) is None
    assert rc.aplicar_regla({**base, "remitente": REM, "asunto": "Recibiste dinero en tu cuenta"}, [regla]) is None
    assert rc.aplicar_regla({**base, "remitente": REM, "asunto": ASUNTO}, []) is None


def test_marca_que_no_esta_en_el_texto_da_error_claro():
    with pytest.raises(rc.ErrorRegla):
        rc.derivar_regla(f"{ASUNTO} {CUERPO}", "$999.999", None)
    with pytest.raises(rc.ErrorRegla):
        rc.derivar_regla(f"{ASUNTO} {CUERPO}", None, None)


def test_tipo_ingreso_de_la_regla():
    regla = _aprendida(tipo="income")
    out = rc.aplicar_regla({"remitente": REM, "asunto": ASUNTO, "texto": f"{ASUNTO} {CUERPO}",
                            "monto": 0, "comercio": "Gasto sin detalle", "tipo": "expense"}, [regla])
    assert out["tipo"] == "income"


# ── Dentro del flujo de lectura (_crear_correo) ─────────────────────────────────────────────
def test_crear_correo_usa_la_regla_cuando_el_estandar_no_encuentra_monto(monkeypatch):
    # Se simula que el lector estándar falla: no halla monto ni comercio.
    monkeypatch.setattr(rcor, "extraer_monto", lambda *a, **k: 0.0)
    monkeypatch.setattr(rcor, "extraer_comercio", lambda *a, **k: "Gasto sin detalle")
    regla = _aprendida()
    c = rcor._crear_correo(_msg("m2", CUERPO2), "u1", _Modelo(), [regla])
    assert c.monto == 350_000 and c.comercio == "Colegio San José" and c._por_regla is True
    assert regla.usos == 1
    sin = rcor._crear_correo(_msg("m3", CUERPO2), "u1", _Modelo(), [])
    assert sin.monto == 0 and sin._por_regla is False


def test_crear_correo_no_pisa_lectura_estandar_correcta():
    regla = _aprendida()
    c = rcor._crear_correo(_msg("m4", CUERPO2, asunto=ASUNTO), "u1", _Modelo(), [regla])
    # El lector estándar ya entendía este formato de Nu: se queda con lo suyo y la regla no se usa.
    assert c.monto == 350_000 and c._por_regla is False and regla.usos == 0
