"""CASOS REALES 1, 2 y 3: cifras que NO eran el monto del movimiento (o que lo deformaban).

1. NIT / cuenta / teléfono / cédula leídos como monto: el correo «Nu Colombia ... NIT 901.658.107-2» entró a
   «Por revisar» como un gasto de $901.658.107. El NIT trae dígito de verificación (-2) y aparece en el
   asunto, en el fragmento de Gmail y en el cuerpo.
2. Monto ×100 por el punto final: «La cantidad de: $1.000.000,00.» (el punto cierra la frase) se leía
   como 100.000.000.
3. Montos sin «$»: Nequi / Bre-B escriben «Recibiste 30.000 de ...» y se leían como 0 (el correo se perdía)
   o como 500 / 250.000 (monto falso). Además un año («de 2026») o una hora («14.30», «12:45») no son dinero.

Todo sintético: ninguna cifra ni nombre es de una persona real.
"""
import pytest

from app.gmail_extract import extraer_monto

NIT = "901.658.107-2"


# ── Caso 1: documentos, cuentas y teléfonos no son dinero ──────────────────────────────────
@pytest.mark.parametrize("texto", [
    f"Nu Colombia Compañía de Financiamiento S.A. NIT {NIT}",              # fragmento
    f"Información de tu cuenta. NIT {NIT}",                                 # asunto
    f"Hola. Tu extracto ya está disponible. NIT {NIT}. Escríbenos.",       # cuerpo
    "NIT: 901658107-2 Bogotá",                                              # sin puntos
    "Tu cuenta 12345678901 fue actualizada",
    "Escríbenos al celular 300 123 4567 o al WhatsApp 3001234567",
    "Documento CC 1.020.304.050 verificado",
    "Referencia 884.221.907 de tu solicitud",
])
@pytest.mark.parametrize("estricto", [False, True])
def test_caso1_documentos_no_son_monto(texto, estricto):
    assert extraer_monto(texto, estricto=estricto) == 0


def test_caso1_el_monto_real_sobrevive_junto_al_nit():
    assert extraer_monto(f"Pagaste $ 45.000 en TIENDA UNO. Nu Colombia NIT {NIT}") == 45000
    assert extraer_monto(f"NIT {NIT} Recibiste 30.000 de ANA") == 30000


# ── Caso 2: el punto final no multiplica por 100 ───────────────────────────────────────────
@pytest.mark.parametrize("texto,esperado", [
    ("Pagaste en: TIENDA UNO. La cantidad de: $1.000.000,00.", 1_000_000),
    ("La cantidad de: $45.500.", 45_500),
    ("La cantidad de: $12,50", 12.5),
    ("Compra por $1.250.000, gracias", 1_250_000),
])
def test_caso2_punto_final_no_es_x100(texto, esperado):
    assert extraer_monto(texto) == esperado
    assert extraer_monto(texto, estricto=True) == esperado


# ── Caso 3: sin «$», años y horas ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("texto,esperado", [
    ("¡Recibiste plata por Bre-B! Recibiste 30.000 de LUIS PEREZ el 8 de octubre de 2026 a las 4:30 pm", 30000),
    ("Enviaste de manera exitosa 45.500 a la llave 3001234567 de MARIA GOMEZ el 3 de julio de 2026", 45500),
    ("Recibiste 1.250.000 de LUIS PEREZ el 8 de octubre de 2026", 1_250_000),
])
def test_caso3_monto_sin_signo_peso_se_lee_completo(texto, esperado):
    assert extraer_monto(texto) == esperado


@pytest.mark.parametrize("texto", [
    "Promoción válida hasta 2026",
    "Faltan 2026",
    "Tu cita es el 15.10.2026 a las 9.30",
    "Hora 14.30 cita",
    "Recibimos el pago que hiciste de tu Tarjeta de crédito Nu el 10 de octubre de 2026",
])
def test_caso3_anios_y_horas_no_son_monto(texto):
    assert extraer_monto(texto) == 0
