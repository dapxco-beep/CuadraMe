"""Notificación «Pagaste con tu Cuenta de ahorros Nu»: monto bien leído (no x100), comercio, tipo, consulta de
Gmail por asunto, etiqueta anidada y llegada a «Por revisar» con Gmail simulado. Todo sintético."""
import pytest

from app import extractos_gmail as eg
from app.gmail_extract import detectar_tipo, extraer_comercio, extraer_monto
from app.routers import correos as rc
from tests.test_cron_correos import CABECERA, URL, _pendientes, _usuario, entorno  # noqa: F401
from tests.test_extractos_gmail import GmailFalso, client, mensaje

REM = "Nu <nu@nu.com.co>"
ASUNTO = "Pagaste con tu Cuenta de ahorros Nu"
CUERPO = ("Hola, Daniel Alfonso: Acá está el detalle de tu pago. Pagaste en: ICETEX. La cantidad de: $1.000.000,00. "
          "Más el impuesto del 4xmil de: $0,00. Si no fuiste tú, contáctanos vía chat… No fui yo, deseo contactar a soporte")


def test_monto_con_punto_final_no_es_x100():
    assert extraer_monto(CUERPO, estricto=True) == 1_000_000
    assert extraer_monto(f"{ASUNTO} {CUERPO}") == 1_000_000
    assert extraer_monto("La cantidad de: $45.500.") == 45_500
    assert extraer_monto("La cantidad de: $12,50") == 12.5
    assert extraer_monto("Compra por $1.250.000, gracias") == 1_250_000


def test_saneador_no_borra_cantidad_ni_cuenta_de_ahorros():
    from app.gmail_extract import sin_documentos
    assert "$1.000.000,00" in sin_documentos(CUERPO)
    assert "Cuenta de ahorros Nu" in sin_documentos(ASUNTO)


@pytest.mark.parametrize("cuerpo,comercio,tipo,monto", [
    (CUERPO, "Pago a Icetex", "expense", 1_000_000),
    ("Hola: Pagaste en:\nICETEX\nLa cantidad de: $1.000.000,00.", "Pago a Icetex", "expense", 1_000_000),
    ("Hola. Compraste en: Rappi. La cantidad de: $32.900,00. Si no fuiste tú, contáctanos", "Compra en Rappi", "expense", 32_900),
    ("Hola. Compraste con tu tarjeta en: Juan Valdez. La cantidad de: $18.000,00.", None, "expense", 18_000),
    ("Hola. Recibiste $250.000 de Ana Pérez en tu Cuenta de ahorros Nu.", "Recibido de Ana Pérez", "income", 250_000),
])
def test_variantes_nu(cuerpo, comercio, tipo, monto):
    ASUNTO = "Recibiste dinero en tu Cuenta de ahorros Nu" if tipo == "income" else globals()["ASUNTO"]
    texto = f"{ASUNTO} {cuerpo}"
    assert extraer_monto(texto) == monto
    assert detectar_tipo(texto) == tipo
    if comercio:
        assert extraer_comercio(REM, ASUNTO, cuerpo) == comercio
    assert eg.es_notificacion_transaccion(ASUNTO, cuerpo) and not eg.es_aviso_no_transaccion(ASUNTO, cuerpo)


def test_consulta_incluye_asunto_y_remitente_conocido():
    q = eg.construir_query_notificaciones()
    assert "nu.com.co" in q and 'subject:("pagaste con"' in q and q.endswith("-filename:pdf")
    assert eg.banco_por_remitente("Nu <algo@otro-dominio.example>") == "Nu Colombia"
    assert eg.banco_por_remitente("Spam <a@otro.example>") is None


def test_etiqueta_anidada_o_con_otras_mayusculas():
    labels = [{"id": "A", "name": "Finanzas/Gastos"}, {"id": "B", "name": "Otra"}]
    assert rc._id_etiqueta(labels, "gastos") == "A"
    assert rc._id_etiqueta([{"id": "C", "name": "GASTOS"}], "Gastos") == "C"
    assert rc._id_etiqueta(labels, "inexistente") is None


def test_llega_a_por_revisar_con_etiqueta_anidada_y_monto_correcto(entorno):  # noqa: F811
    msg = mensaje("nu1", REM, ASUNTO, CUERPO[:190], labels=["L1"])
    gmail = GmailFalso([msg], {}, etiquetas=[{"id": "L1", "name": "Finanzas/Gastos"}])
    uid, _ = _usuario(entorno, gmail)
    assert client.post(URL, headers=CABECERA).status_code == 200
    assert _pendientes(uid) == 1
    from app.database import SessionLocal
    from app.models import CorreoGasto
    db = SessionLocal()
    try:
        c = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid).one()
        assert c.monto == 1_000_000 and c.tipo_sugerido == "expense" and c.comercio == "Pago a Icetex"
    finally:
        db.close()
