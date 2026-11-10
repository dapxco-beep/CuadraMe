"""El generador de atajos (backend/tools/generar_atajo_notificaciones.py) produce archivos con estructura válida.
No prueba que iOS los acepte (eso solo se ve en un iPhone), pero evita entregar un archivo roto: condicionales sin cerrar,
la clave dentro del archivo o acciones que apuntan a un resultado que no existe."""
import importlib.util
import os
import plistlib

import pytest

RUTA = os.path.join(os.path.dirname(__file__), "..", "tools", "generar_atajo_notificaciones.py")
_spec = importlib.util.spec_from_file_location("generar_atajo", RUTA)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

BASE = "https://api.cuadrame.dapx.shop"
MODOS = ["notificacion", "pantalla", "captura", "wallet"]


def _atajo(modo):
    datos = gen.construir_wallet(BASE) if modo == "wallet" else gen.construir(BASE, "Nequi", modo)
    return plistlib.loads(plistlib.dumps(datos, fmt=plistlib.FMT_BINARY))  # que se pueda escribir y leer como archivo


def _ids(atajo):
    return [a["WFWorkflowActionIdentifier"].split(".")[-1] for a in atajo["WFWorkflowActions"]]


@pytest.mark.parametrize("modo", MODOS)
def test_condicionales_siempre_cerrados(modo):
    grupos = {}
    for a in _atajo(modo)["WFWorkflowActions"]:
        if a["WFWorkflowActionIdentifier"].endswith(".conditional"):
            p = a["WFWorkflowActionParameters"]
            grupos.setdefault(p["GroupingIdentifier"], []).append(p["WFControlFlowMode"])
    assert all(modos == [0, 1, 2] for modos in grupos.values())


@pytest.mark.parametrize("modo", MODOS)
def test_la_clave_no_viaja_en_el_archivo_y_se_pide_al_instalar(modo):
    atajo = _atajo(modo)
    assert atajo["WFWorkflowImportQuestions"][0]["ActionIndex"] == 0
    primera = atajo["WFWorkflowActions"][0]["WFWorkflowActionParameters"]
    assert primera["WFTextActionText"] == ""  # la clave de cada persona se pega al instalar; nunca va dentro
    assert "cdm_" not in repr(atajo)


@pytest.mark.parametrize("modo", MODOS)
def test_toda_referencia_a_un_resultado_existe_antes_de_usarse(modo):
    vistos, huerfanos = set(), []
    for a in _atajo(modo)["WFWorkflowActions"]:
        p = a["WFWorkflowActionParameters"]
        texto = repr(p)
        for uid in {t.split("'")[0] for t in texto.split("'OutputUUID': '")[1:]}:
            if uid not in vistos:
                huerfanos.append(uid)
        if "UUID" in p:
            vistos.add(p["UUID"])
    assert not huerfanos


def test_wallet_manda_comercio_importe_y_tarjeta_como_fuente_wallet():
    atajo = _atajo("wallet")
    assert _ids(atajo) == ["gettext", "downloadurl", "getvalueforkey", "notification"]
    post = atajo["WFWorkflowActions"][1]["WFWorkflowActionParameters"]
    assert post["WFURL"] == f"{BASE}/movimientos/rapido" and post["WFHTTPMethod"] == "POST"
    campos = {i["WFKey"]["Value"]["string"]: i["WFValue"]["Value"]["string"]
              for i in post["WFJSONValues"]["Value"]["WFDictionaryFieldValueItems"]}
    assert set(campos) == {"comercio", "monto", "tarjeta", "fuente"} and campos["fuente"] == "wallet"
    propiedades = [rango["Aggrandizements"][0]["PropertyName"]
                   for i in post["WFJSONValues"]["Value"]["WFDictionaryFieldValueItems"]
                   for rango in i["WFValue"]["Value"].get("attachmentsByRange", {}).values()]
    assert propiedades == ["Merchant", "Amount", "Card or Pass"]


def test_pantalla_y_notificacion_no_preguntan_el_banco_al_instalar():
    for modo in ("pantalla", "notificacion"):
        assert len(_atajo(modo)["WFWorkflowImportQuestions"]) == 1  # solo la clave
    assert len(_atajo("captura")["WFWorkflowImportQuestions"]) == 2  # captura sí conserva la pregunta del banco


def test_en_pantallazo_el_atajo_nunca_se_queda_mudo_y_en_notificaciones_ignora_en_silencio():
    def avisos_en_rama_sin_pago(modo):
        acciones = _atajo(modo)["WFWorkflowActions"]
        # Rama «no_parece_un_movimiento»: las acciones entre su Si y su Otherwise
        for i, a in enumerate(acciones):
            p = a["WFWorkflowActionParameters"]
            if a["WFWorkflowActionIdentifier"].endswith(".conditional") and p.get("WFConditionalActionString") == "no_parece_un_movimiento":
                grupo = p["GroupingIdentifier"]
                dentro = []
                for b in acciones[i + 1:]:
                    q = b["WFWorkflowActionParameters"]
                    if b["WFWorkflowActionIdentifier"].endswith(".conditional") and q.get("GroupingIdentifier") == grupo:
                        break
                    dentro.append(b["WFWorkflowActionIdentifier"].split(".")[-1])
                return dentro.count("notification")
        raise AssertionError("no hay rama no_parece_un_movimiento")

    assert avisos_en_rama_sin_pago("pantalla") == 1
    assert avisos_en_rama_sin_pago("notificacion") == 0


def _acciones_de_la_rama(modo, valor):
    acciones = _atajo(modo)["WFWorkflowActions"]
    for i, a in enumerate(acciones):
        p = a["WFWorkflowActionParameters"]
        if a["WFWorkflowActionIdentifier"].endswith(".conditional") and p.get("WFConditionalActionString") == valor:
            grupo, dentro = p["GroupingIdentifier"], []
            for b in acciones[i + 1:]:
                q = b["WFWorkflowActionParameters"]
                if b["WFWorkflowActionIdentifier"].endswith(".conditional") and q.get("GroupingIdentifier") == grupo:
                    break
                dentro.append(b)
            return dentro
    raise AssertionError(f"no hay rama {valor}")


@pytest.mark.parametrize("modo", ["pantalla", "notificacion"])
def test_si_no_sabe_la_cuenta_el_atajo_la_pregunta_entre_las_registradas(modo):
    rama = _acciones_de_la_rama(modo, "confirmar_cuenta")
    ids = [a["WFWorkflowActionIdentifier"].split(".")[-1] for a in rama]
    assert ids == ["notification", "getvalueforkey", "downloadurl", "choosefromlist", "downloadurl", "getvalueforkey", "notification"]
    # 1.º avisa dónde quedó; luego pide LAS CUENTAS de la persona al servidor y elige de esa lista (la entrada de «Elegir de la lista»)
    assert rama[2]["WFWorkflowActionParameters"]["WFURL"].endswith("/movimientos/cuentas-rapido")
    assert rama[2]["WFWorkflowActionParameters"]["WFHTTPMethod"] == "GET"
    campos = {i["WFKey"]["Value"]["string"] for i in rama[4]["WFWorkflowActionParameters"]["WFJSONValues"]["Value"]["WFDictionaryFieldValueItems"]}
    assert {"movimiento_id", "cuenta", "texto"} <= campos  # le dice al servidor QUÉ movimiento y a QUÉ cuenta


def test_la_pregunta_entro_o_salio_usa_una_lista_fija_como_entrada():
    ids = [a["WFWorkflowActionIdentifier"].split(".")[-1] for a in _acciones_de_la_rama("pantalla", "pedir_tipo")]
    i = ids.index("choosefromlist")
    assert ids[i - 1] == "list"  # la lista fija se arma con la acción «Lista», justo antes
    assert "WFChooseFromListActionList" not in _acciones_de_la_rama("pantalla", "pedir_tipo")[i]["WFWorkflowActionParameters"]
