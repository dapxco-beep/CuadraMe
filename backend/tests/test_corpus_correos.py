"""Corpus de correos bancarios colombianos (SINTÉTICOS: ningún dato real) con la respuesta esperada.

Sirve para «reentrenar» la detección por reglas: cada caso dice qué debe entender el sistema de un
correo (¿es un movimiento, un extracto, un aviso o ruido?, ¿entró o salió plata?, ¿cuánto?, ¿de qué
banco?, ¿es un traslado entre cuentas propias?). Para cubrir un caso nuevo basta con agregar una fila.
"""
import pytest

from app import extractos_gmail as eg
from app import gmail_extract as ge

# (id, remitente, asunto, fragmento, esperado)
# esperado: clase ('mov' | 'extracto' | 'aviso'), y opcionales: tipo, monto, banco, traslado, texto_en_concepto
CORPUS = [
    # ── Movimientos: salidas ──
    ("bancolombia_compra", "alertas@notificacionesbancolombia.com", "Alertas y Notificaciones",
     "Bancolombia le informa Compra por $85.000 en EXITO CHIA con tarjeta *1234 el 12/10/2026 a las 14:32.",
     dict(clase="mov", tipo="expense", monto=85000, banco="Bancolombia", concepto="Exito")),
    ("bancolombia_pago_servicio", "alertas@bancolombia.com.co", "Notificación de pago",
     "Bancolombia le informa que realizó un pago de servicios por $120.500 con cargo a su cuenta de ahorros *4321.",
     dict(clase="mov", tipo="expense", monto=120500, banco="Bancolombia")),
    ("bancolombia_retiro", "alertas@bancolombia.com.co", "Retiro en cajero",
     "Bancolombia le informa Retiro por $200.000 en cajero automático CC Andino.",
     dict(clase="mov", tipo="expense", monto=200000, banco="Bancolombia")),
    ("davivienda_compra", "no-reply@davivienda.com", "Compra con tu tarjeta Davivienda",
     "Davivienda: compra por $120.000 en FALABELLA con tu tarjeta terminada en 4521.",
     dict(clase="mov", tipo="expense", monto=120000, banco="Davivienda", concepto="Falabella")),
    ("nu_compra", "no-reply@nu.com.co", "Compra aprobada",
     "Compra aprobada: $35.000 en UBER *TRIP con tu tarjeta Nu.",
     dict(clase="mov", tipo="expense", monto=35000, banco="Nu Colombia")),
    ("nequi_pago", "notificaciones@nequi.com.co", "Pagaste en un comercio",
     "Pagaste $12.500 en Rappi desde tu Nequi.",
     dict(clase="mov", tipo="expense", monto=12500, banco="Nequi")),
    # ── Bre-B / llaves: de cuál a cuál ──
    ("breb_envio", "notificaciones@nequi.com.co", "Enviaste plata",
     "Enviaste de manera exitosa 45.500 a la llave @juanperez de Juan Pérez.",
     dict(clase="mov", tipo="expense", monto=45500, banco="Nequi", concepto="Juan")),
    ("breb_recibo", "notificaciones@nequi.com.co", "Recibiste plata",
     "Recibiste 30.000 de ANA GOMEZ por Bre-B.",
     dict(clase="mov", tipo="income", monto=30000, banco="Nequi", concepto="Ana")),
    ("breb_recibo_bancolombia", "alertas@bancolombia.com.co", "Recibiste una transferencia Bre-B",
     "Bancolombia le informa que recibió una transferencia por $1.200.000 de CARLOS RUIZ a su llave 3001234567.",
     dict(clase="mov", tipo="income", monto=1200000, banco="Bancolombia")),
    ("daviplata_envio", "notificaciones@daviplata.com", "Transferencia exitosa",
     "Daviplata: transferiste $60.000 a la llave 3109876543 de Laura Mora.",
     dict(clase="mov", tipo="expense", monto=60000, banco="Daviplata")),
    # ── Movimientos: entradas ──
    ("nomina", "alertas@bancolombia.com.co", "Recibiste un abono",
     "Bancolombia le informa abono por $4.800.000 en su cuenta de ahorros por concepto de Nómina.",
     dict(clase="mov", tipo="income", monto=4800000, banco="Bancolombia")),
    ("deposito", "no-reply@davivienda.com", "Consignación recibida",
     "Davivienda: te consignaron $500.000 en tu cuenta de ahorros.",
     dict(clase="mov", tipo="income", monto=500000, banco="Davivienda")),
    # ── Traslados entre cuentas propias ──
    ("traslado_propio", "alertas@bancolombia.com.co", "Transferencia entre tus cuentas",
     "Bancolombia le informa una transferencia entre cuentas propias por $500.000 de Ahorros a Nequi.",
     dict(clase="mov", monto=500000, banco="Bancolombia", traslado=True)),
    ("pago_tarjeta_propia", "alertas@bancolombia.com.co", "Pago de tu tarjeta de crédito",
     "Bancolombia le informa que pagó $300.000 a su tarjeta de crédito terminada en 8890 desde su cuenta de ahorros.",
     dict(clase="mov", tipo="expense", monto=300000, banco="Bancolombia", traslado=True)),
    # ── Extractos ──
    ("extracto_listo", "extractos@bancolombia.com.co", "Tu extracto de octubre ya está disponible",
     "Consulta tu extracto de la tarjeta de crédito terminada en 1234 adjunto a este correo.",
     dict(clase="extracto", banco="Bancolombia")),
    ("estado_cuenta", "no-reply@davivienda.com", "Estado de cuenta septiembre 2026",
     "Adjuntamos el estado de cuenta de tu cuenta de ahorros.",
     dict(clase="extracto", banco="Davivienda")),
    ("extracto_nu", "no-reply@nu.com.co", "Tu resumen mensual de Nu",
     "Aquí tienes el resumen mensual de tu cuenta.",
     dict(clase="extracto", banco="Nu Colombia")),
    # ── Avisos que NO son movimiento ──
    ("aviso_tarjeta_agregada", "no-reply@nequi.com.co", "Agregaste tu tarjeta a Apple Pay",
     "Agregaste tu tarjeta al celular. Ya puedes pagar con él.",
     dict(clase="aviso", banco="Nequi")),
    ("aviso_pago_fallido", "alertas@bancolombia.com.co", "No pudimos procesar tu pago",
     "No pudimos completar tu pago de $85.000 por fondos insuficientes.",
     dict(clase="aviso", banco="Bancolombia")),
    ("aviso_codigo", "seguridad@bancolombia.com.co", "Código de verificación",
     "Tu código de verificación es 482913. No lo compartas.",
     dict(clase="aviso", banco="Bancolombia")),
    ("aviso_inicio_sesion", "seguridad@davivienda.com", "Inicio de sesión en tu cuenta",
     "Detectamos un inicio de sesión desde un nuevo dispositivo.",
     dict(clase="aviso", banco="Davivienda")),
    ("publicidad_credito", "mercadeo@bancolombia.com.co", "Tienes un crédito preaprobado de $20.000.000",
     "Solicita hoy tu crédito de libre inversión con tasa preferencial.",
     dict(clase="aviso", banco="Bancolombia")),
    ("publicidad_promo", "promos@davivienda.com", "Promoción: 20% de descuento en tus compras",
     "Aprovecha esta oferta con tu tarjeta Davivienda este fin de semana.",
     dict(clase="aviso", banco="Davivienda")),
    ("encuesta", "info@bancolombia.com.co", "Cuéntanos cómo te fue",
     "Tu opinión nos ayuda a mejorar. Responde esta breve encuesta.",
     dict(clase="aviso", banco="Bancolombia")),
    # ── No es un banco ──
    ("no_banco_netflix", "info@netflix.com", "Tu pago de Netflix",
     "Cobramos $29.900 a tu tarjeta por tu suscripción.",
     dict(clase="mov", tipo="expense", monto=29900, banco=None)),
    ("no_banco_phishing", "soporte@bancolombia-seguro.xyz", "Verifica tu cuenta Bancolombia",
     "Ingresa aquí para verificar tu cuenta.",
     dict(clase="aviso", banco=None)),
    # ── Casos difíciles ──
    ("nequi_te_enviaron", "notificaciones@nequi.com.co", "Te enviaron plata",
     "Te enviaron $50.000 desde Bre-B.",
     dict(clase="mov", tipo="income", monto=50000, banco="Nequi")),
    ("retiro_nequi", "notificaciones@nequi.com.co", "Retiraste plata",
     "Retiraste $100.000 de tu Nequi en un cajero de Bancolombia.",
     dict(clase="mov", tipo="expense", monto=100000, banco="Nequi")),
    ("devolucion", "alertas@bancolombia.com.co", "Devolución a tu cuenta",
     "Bancolombia le informa una devolución por $50.000 a su cuenta de ahorros por una compra anulada.",
     dict(clase="mov", tipo="income", monto=50000, banco="Bancolombia")),
    ("rendimientos", "notificaciones@nequi.com.co", "Rendimientos del mes",
     "Recibiste $3.450 por rendimientos de tu bolsillo.",
     dict(clase="mov", tipo="income", monto=3450, banco="Nequi")),
    ("cuota_manejo", "alertas@bancolombia.com.co", "Cobro cuota de manejo",
     "Bancolombia le informa cobro de cuota de manejo por $18.900 de su tarjeta.",
     dict(clase="mov", tipo="expense", monto=18900, banco="Bancolombia")),
    ("compra_usd", "alertas@bancolombia.com.co", "Compra internacional",
     "Bancolombia le informa Compra por USD 12.50 en AMAZON con tarjeta *1234.",
     dict(clase="mov", tipo="expense", monto=12.5, banco="Bancolombia", moneda="USD")),
    ("pse", "notificaciones@nequi.com.co", "Pago PSE",
     "Pagaste $89.900 con PSE a Claro.",
     dict(clase="mov", tipo="expense", monto=89900, banco="Nequi")),
    ("decimales", "alertas@bancolombia.com.co", "Pago realizado",
     "Bancolombia le informa pago por $1.250.000,50 a su obligación.",
     dict(clase="mov", tipo="expense", monto=1250000.5, banco="Bancolombia")),
    ("avance", "alertas@davivienda.com", "Avance en efectivo",
     "Davivienda: avance de $300.000 en tu tarjeta de crédito.",
     dict(clase="mov", tipo="expense", monto=300000, banco="Davivienda")),
]


def _clase(asunto: str, snippet: str) -> str:
    """Misma lógica que usa el sincronizador: primero extracto, luego aviso, luego movimiento."""
    if eg.es_aviso_no_transaccion(asunto, snippet):
        return "extracto" if eg.contiene_palabra_extracto(asunto) else "aviso"
    if eg.es_notificacion_transaccion(asunto, snippet):
        return "mov"
    return "aviso"


@pytest.mark.parametrize("caso", CORPUS, ids=[c[0] for c in CORPUS])
def test_corpus_correos(caso):
    _id, remitente, asunto, snippet, esp = caso
    assert _clase(asunto, snippet) == esp["clase"], "clase"
    assert eg.banco_por_remitente(remitente) == esp.get("banco"), "banco"
    if esp["clase"] != "mov":
        return
    texto = f"{asunto} {snippet}"
    assert ge.extraer_monto(texto, estricto=True) == esp["monto"], "monto"
    if "tipo" in esp:
        assert ge.detectar_tipo(texto) == esp["tipo"], "tipo"
    if "moneda" in esp:
        assert ge.extraer_moneda(texto) == esp["moneda"], "moneda"
    if esp.get("traslado"):
        assert ge.es_posible_traslado_propio(texto), "traslado propio"
    if esp.get("concepto"):
        assert esp["concepto"].lower() in ge.extraer_comercio(remitente, asunto, snippet).lower(), "concepto"
