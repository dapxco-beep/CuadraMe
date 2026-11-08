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
