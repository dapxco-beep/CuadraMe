"""Lector de notificaciones para cualquier banco (iPhone y Android): por verbos, no por banco."""
import pytest

from app.notificaciones import interpretar, pide_monto


def test_nequi_recibiste_plata_sin_signo_pesos():
    n = interpretar("Nequi", "Envío", "DANIEL PARRADO te envió 1, ¡lo mejor!")
    assert (n.tipo, n.monto, n.comercio, n.app) == ("income", 1, "De Daniel Parrado", "Nequi")


@pytest.mark.parametrize("paquete,titulo,texto,monto,tipo,comercio", [
    ("Nequi", "Envío", "ANA PEREZ te envió $45.000, ¡lo mejor!", 45000, "income", "De Ana Perez"),
    ("Nequi", "Envío", "ANA PEREZ te envió 1.250.000 ¡lo mejor!", 1250000, "income", "De Ana Perez"),
    ("Bancolombia", "Mi Bancolombia", "Recibiste una transferencia por $230.000 de LUIS GOMEZ", 230000, "income", None),
    ("Davivienda", "Davivienda", "Te llegó $80.000 de MARIA", 80000, "income", None),
    ("Nu", "Nu", "Pagaste $45.900 en Mercado Libre con tu tarjeta ••1234", 45900, "expense", "Mercado Libre"),
    ("Daviplata", "Daviplata", "Enviaste $15.000 a CARLOS", 15000, "expense", None),
])
def test_bancos_distintos_se_leen_por_verbos(paquete, titulo, texto, monto, tipo, comercio):
    n = interpretar(paquete, titulo, texto)
    assert (n.monto, n.tipo) == (monto, tipo) and not n.tipo_incierto
    if comercio:
        assert n.comercio == comercio


@pytest.mark.parametrize("paquete,titulo,texto", [
    ("Nequi", "Tu plata llegó con éxito 💜", "Envío exitoso, la plata ya está en el Nequi destino. Recuerda que no se puede cancelar."),
    ("Bancolombia", "Transferencia exitosa", "Tu transferencia fue exitosa."),
    ("Nu", "Listo", "Pago exitoso"),
])
def test_salio_plata_sin_cifra_hay_que_preguntar_monto(paquete, titulo, texto):
    assert interpretar(paquete, titulo, texto) is None
    assert pide_monto(paquete, titulo, texto)


def test_hay_monto_pero_no_se_sabe_la_direccion():
    n = interpretar("Nu", "Nu", "Movimiento por $50.000 en tu cuenta")
    assert n.monto == 50000 and n.tipo_incierto


@pytest.mark.parametrize("titulo,texto", [
    ("Ofertas", "Todos piden OFERTA a solo $14.968"),
    ("Seguridad", "Tu código es 123456, no lo compartas"),
    ("Hola", "Actualiza tu app para ver novedades"),
])
def test_ruido_no_se_registra_ni_pregunta(titulo, texto):
    assert interpretar("Nequi", titulo, texto) is None
    assert not pide_monto("Nequi", titulo, texto)


def test_android_no_cambia():
    n = interpretar("com.nequi.MobileApp", "Envío", "DANIEL PARRADO te envió 1, ¡lo mejor!")
    assert n.tipo == "income" and n.app == "Nequi"


@pytest.mark.parametrize("nota", ["parche con Laura", "rumba con amigos", "birras del viernes", "trago con el parche"])
def test_la_nota_del_atajo_con_jerga_cae_en_ocio(nota):
    from app.comercios_conocidos import clasificar_por_diccionario

    r = clasificar_por_diccionario(nota)
    assert r and r["categoria"] == "Ocio"


def test_comprobante_leido_de_una_captura_con_ruido_se_registra_como_gasto():
    # Nu no avisa al enviar plata: el atajo saca el texto de un pantallazo del comprobante (texto inventado, con ruido de pantalla).
    texto = ("11:03 Nu < Comprobante Transferencia exitosa $ 45.000 Para LAURA GOMEZ Banco Nequi "
             "Fecha 5 nov. 2026 Compartir Descargar")
    n = interpretar("Nu", "", texto)
    assert n is not None and n.monto == 45000 and n.tipo == "expense" and not n.tipo_incierto


def test_comprobante_largo_no_se_rechaza_por_tamano():
    from app.schemas import NotificacionAndroid

    assert len(NotificacionAndroid(paquete="Nu", titulo="", texto="x " * 2500).texto) == 5000
