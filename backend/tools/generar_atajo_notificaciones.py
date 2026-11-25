"""Genera «CuadraMe Notificaciones.shortcut» (sin firmar) para el disparador «Notificación» de iOS 27.

Uso:   python tools/generar_atajo_notificaciones.py [--base URL] [--modo unico|notificacion|pantalla|captura|wallet] [--salida archivo]
(modo «unico» = «CuadraMe Registrar»: notificaciones Y gesto en un solo atajo; es el que se entrega.)
Firma (en el Mac, basta el Apple ID gratis):
       shortcuts sign -m anyone -i "CuadraMe Notificaciones.shortcut" -o "CuadraMe Notificaciones firmado.shortcut"

Qué hace el atajo: manda el texto de la notificación a /movimientos/rapido-notificacion (el mismo
endpoint de Android; el servidor lee cada banco). Según `motivo` de la respuesta (y el servidor APRENDE la respuesta de cada persona; ver reglas_notificacion.py):
  - pedir_monto            -> plata ENVIADA (el banco no dice cuánto): pregunta monto y «¿para qué o para quién?»
                              y lo registra (misma ruta, con la respuesta); ese texto es lo que categoriza el gasto.
  - pedir_tipo             -> hay monto pero no se sabe si entró o salió: pregunta «¿Entró o salió plata?».
  - no_parece_un_movimiento -> no hace nada (ofertas, códigos...).
  - (sin motivo)           -> se registró: muestra el aviso («Ingreso de $X de Laura. Confírmalo en CuadraMe»).
El banco NO se pregunta al instalar (salvo en el modo «captura»): el servidor lo deduce, así que un solo atajo sirve para todos los
bancos y una sola copia basta. Cada banco necesita su propia AUTOMATIZACIÓN (iOS vigila una app por automatización), todas apuntando a este atajo.

Modos (de dónde sale el texto que se le manda al servidor):
  notificacion -> la notificación que dispara la automatización de iOS 27 (Nequi avisa al recibir plata).
  pantalla     -> para bancos que NO avisan al enviar plata (Nu): un gesto que ELIGE cada persona (Toque atrás, Botón de
                  acción, Centro de control, Siri...) toma un pantallazo, el teléfono saca el texto y manda SOLO el texto.
                  El mismo atajo sirve para cualquier banco y NO pregunta nada en el caso normal: el servidor deduce la
                  cuenta del propio texto (o de lo que la persona ya le enseñó), el monto y el destinatario. Solo pregunta
                  si de verdad no puede saberlo (cuenta dudosa la primera vez, monto que el aviso no trae) y APRENDE la
                  respuesta. Solo pide la clave al instalarlo.
  captura      -> igual, pero la imagen es la captura que dispara la automatización «Cuando se guarde una captura».
La imagen nunca sale del teléfono; el servidor recibe texto y lo lee con el mismo lector de avisos.
  wallet       -> «CuadraMe Apple Pay»: lo llama la automatización «Transacción» de iOS (Apple Pay/Wallet). Manda
                  Comercio, Importe y Tarjeta o pase a /movimientos/rapido (fuente wallet) y muestra el resultado. No
                  pregunta nada: el pago llega completo. Mismo diseño que docs/ATAJO_CUADRAME.md (atajo 1).

La clave API NO va dentro del archivo: se pide al instalar el atajo (preguntas de importación), así el
mismo enlace de iCloud sirve para todos los usuarios.

OJO: escrito sin poder probarlo en un iPhone. Los identificadores de acción son los clásicos de Atajos;
la entrada del atajo («Entrada del atajo») es lo que el disparador le pasa. Si iOS 27 cambia algo,
abre el archivo en Atajos y corrige esa acción a mano."""
from __future__ import annotations

import argparse
import plistlib
import uuid

OBJ = "￼"  # marcador de «aquí va una variable» en los textos de Atajos


def _texto(s: str) -> dict:
    return {"Value": {"string": s}, "WFSerializationType": "WFTextTokenString"}


def _con_variable(prefijo: str, variable: dict, sufijo: str = "") -> dict:
    """Texto con UNA variable incrustada: `prefijo` + variable + `sufijo`."""
    return {
        "Value": {"string": f"{prefijo}{OBJ}{sufijo}", "attachmentsByRange": {f"{{{len(prefijo)}, 1}}": variable}},
        "WFSerializationType": "WFTextTokenString",
    }


# Sube SOLO cuando un cambio del atajo obliga a reinstalarlo (debe coincidir con VERSION_ATAJO_ACTUAL en routers/movimientos.py):
# el servidor avisa a quien mande una versión menor.
VERSION_ATAJO = 7

ENTRADA = {"Type": "ExtensionInput"}  # «Entrada del atajo»: lo que manda la automatización


def _salida(uid: str, nombre: str) -> dict:
    return {"Type": "ActionOutput", "OutputUUID": uid, "OutputName": nombre}


def _dic(pares: list[tuple[str, dict]]) -> dict:
    return {
        "Value": {"WFDictionaryFieldValueItems": [
            {"WFItemType": 0, "WFKey": _texto(k), "WFValue": v} for k, v in pares]},
        "WFSerializationType": "WFDictionaryFieldValue",
    }


# Parámetros que Atajos exige aunque tengan un valor «de siempre»: sin ellos la acción falla con «Elige un valor para cada parámetro
# de la acción» (probado en un Mac con macOS 27.2; los valores son los de Cherri).
PARAMETROS_POR_DEFECTO = {
    "notification": {"WFNotificationActionSound": True},
    "choosefromlist": {"WFChooseFromListActionSelectMultiple": False, "WFChooseFromListActionSelectAll": False},
}


def _accion(identificador: str, **parametros) -> dict:
    return {"WFWorkflowActionIdentifier": f"is.workflow.actions.{identificador}",
            "WFWorkflowActionParameters": {**PARAMETROS_POR_DEFECTO.get(identificador, {}), **parametros}}


def _post(url: str, clave: dict, cuerpo: list[tuple[str, dict]], uid: str) -> dict:
    if url.endswith("/rapido-notificacion"):
        cuerpo = [*cuerpo, ("version", _texto(str(VERSION_ATAJO)))]  # para que el servidor sepa si hay que avisar de uno nuevo
    return _accion(
        "downloadurl", UUID=uid, WFURL=url, WFHTTPMethod="POST", WFHTTPBodyType="JSON",
        WFHTTPHeaders=_dic([("X-Api-Key", clave)]), WFJSONValues=_dic(cuerpo))


def _valor(clave: str, de: str, uid: str) -> dict:
    return _accion("getvalueforkey", UUID=uid, WFDictionaryKey=clave, WFGetDictionaryValueType="Value",
                   WFInput={"Value": _salida(de, "Contenido de la URL"), "WFSerializationType": "WFTextTokenAttachment"})


# Códigos REALES de condición en un archivo de atajo (son números, no el texto que muestra la app). Verificados contra el compilador
# Cherri (iOS 27.2): Es=4, Tiene algún valor=100.
COND_ES = 4
COND_TIENE_VALOR = 100

VAR_TEXTO = "CuadraMe texto"   # el texto que se le manda al servidor (de la notificación o del pantallazo)
VAR_GESTO = "CuadraMe gesto"   # «1» si la persona hizo el gesto (pantallazo); vacío si lo disparó una notificación


def _variable(nombre: str) -> dict:
    return {"Type": "Variable", "VariableName": nombre}


def _si_igual(grupo: str, variable_uid: str | None, nombre: str, valor: str, dentro: list[dict], si_no: list[dict] | None = None,
              variable: str | None = None):
    """Si la salida `variable_uid` (o la variable con nombre `variable`) es igual a `valor`."""
    origen = _variable(variable) if variable else _salida(variable_uid, nombre)
    # El valor que sacó «Obtener valor del diccionario» no tiene tipo conocido: sin convertirlo a texto, Atajos no sabe comparar con
    # «es» y falla con «Elige un valor para cada parámetro de la acción» (probado en macOS 27.2: con esta coerción corre).
    origen = {**origen, "Aggrandizements": [{"Type": "WFCoercionVariableAggrandizement", "CoercionItemClass": "WFStringContentItem"}]}
    inicio = _accion(
        "conditional", GroupingIdentifier=grupo, WFControlFlowMode=0, WFCondition=COND_ES, WFConditionalActionString=valor,
        WFInput={"Type": "Variable", "Variable": {"Value": origen, "WFSerializationType": "WFTextTokenAttachment"}})
    medio = _accion("conditional", GroupingIdentifier=grupo, WFControlFlowMode=1)
    fin = _accion("conditional", GroupingIdentifier=grupo, WFControlFlowMode=2, UUID=str(uuid.uuid4()).upper())
    return [inicio, *dentro, medio, *(si_no or []), fin]


def _leer_imagen(modo: str, id_shot: str, id_ocr: str) -> list[dict]:
    """Acciones que sacan el texto de una imagen (OCR del propio iPhone, sin enviarla a ningún lado)."""
    if modo == "notificacion":
        return []
    if modo == "pantalla":
        origen = {"Value": _salida(id_shot, "Captura de pantalla"), "WFSerializationType": "WFTextTokenAttachment"}
        previo = [_accion("takescreenshot", UUID=id_shot, WFTakeScreenshotScreenshotType="Full Screen")]
    else:  # captura: la imagen es la entrada del atajo
        origen = {"Value": ENTRADA, "WFSerializationType": "WFTextTokenAttachment"}
        previo = []
    return [*previo, _accion("extracttextfromimage", UUID=id_ocr, WFImage=origen)]


def _texto_de_entrada_o_pantallazo(id_entrada: str, id_shot: str, id_ocr: str, id_v1: str, id_v2: str) -> list[dict]:
    """Modo «unico»: UN atajo para todo. Si lo dispara una notificación (trae entrada) usa su texto; si lo dispara el gesto (sin
    entrada) toma el pantallazo y le saca el texto en el iPhone. Deja el resultado en la variable `VAR_TEXTO` y marca `VAR_GESTO`."""
    grupo = str(uuid.uuid4()).upper()
    ent = {"Type": "Variable", "Variable": {"Value": ENTRADA, "WFSerializationType": "WFTextTokenAttachment"}}
    como_entrada = lambda uid, n: {"Value": _salida(uid, n), "WFSerializationType": "WFTextTokenAttachment"}  # noqa: E731
    return [
        _accion("conditional", GroupingIdentifier=grupo, WFControlFlowMode=0, WFCondition=COND_TIENE_VALOR, WFInput=ent),
        _accion("gettext", UUID=id_entrada, WFTextActionText=_con_variable("", ENTRADA)),
        _accion("setvariable", WFVariableName=VAR_TEXTO, WFInput=como_entrada(id_entrada, "Texto")),
        _accion("gettext", UUID=id_v1, WFTextActionText=""),
        _accion("setvariable", WFVariableName=VAR_GESTO, WFInput=como_entrada(id_v1, "Texto")),
        _accion("conditional", GroupingIdentifier=grupo, WFControlFlowMode=1),
        _accion("takescreenshot", UUID=id_shot, WFTakeScreenshotScreenshotType="Full Screen"),
        _accion("extracttextfromimage", UUID=id_ocr, WFImage=como_entrada(id_shot, "Captura de pantalla")),
        _accion("setvariable", WFVariableName=VAR_TEXTO, WFInput=como_entrada(id_ocr, "Texto de la imagen")),
        _accion("gettext", UUID=id_v2, WFTextActionText="1"),
        _accion("setvariable", WFVariableName=VAR_GESTO, WFInput=como_entrada(id_v2, "Texto")),
        _accion("conditional", GroupingIdentifier=grupo, WFControlFlowMode=2, UUID=str(uuid.uuid4()).upper()),
    ]


def construir(base: str, banco: str = "Nequi", modo: str = "notificacion", clave_prueba: str = "") -> dict:
    u = lambda: str(uuid.uuid4()).upper()  # noqa: E731
    id_clave, id_banco, id_post, id_motivo, id_msg = u(), u(), u(), u(), u()
    id_monto, id_para, id_rapido, id_resp = u(), u(), u(), u()
    id_monto2, id_com2, id_tipo, id_rapido2, id_resp2 = u(), u(), u(), u(), u()
    id_shot, id_ocr, id_cuentas = u(), u(), u()
    elegir = modo in ("pantalla", "notificacion", "unico")  # no se pregunta el banco: el servidor lo deduce del texto o de lo aprendido
    id_rapido3, id_resp3, id_movid = u(), u(), u()
    # De dónde sale el texto: la notificación misma o el texto leído de una imagen (pantallazo / captura)
    id_ent, id_v1, id_v2 = u(), u(), u()
    if modo == "unico":
        texto_var = _variable(VAR_TEXTO)
    else:
        texto_var = ENTRADA if modo == "notificacion" else _salida(id_ocr, "Texto de la imagen")
    clave = _con_variable("", _salida(id_clave, "Texto"))
    nombre_banco = _texto("auto") if elegir else _con_variable("", _salida(id_banco, "Texto"))
    entrada_texto = lambda uid, n="Entrada proporcionada": _con_variable("", _salida(uid, n))  # noqa: E731
    aviso = lambda uid: _accion("notification", WFNotificationActionTitle="CuadraMe",  # noqa: E731
                                WFNotificationActionBody=_con_variable("", _salida(uid, "Valor del diccionario")))

    acciones = [
        # 0: la clave API (se pregunta al instalar) y, salvo en «pantalla», 1: el banco (también al instalar)
        _accion("gettext", UUID=id_clave, WFTextActionText=clave_prueba),  # clave_prueba: SOLO para pruebas locales
        *([] if elegir else [_accion("gettext", UUID=id_banco, WFTextActionText=banco)]),
        *(_texto_de_entrada_o_pantallazo(id_ent, id_shot, id_ocr, id_v1, id_v2) if modo == "unico" else _leer_imagen(modo, id_shot, id_ocr)),
        # El texto crudo (de la notificación o del pantallazo): el servidor lo lee, no el atajo
        _post(f"{base}/movimientos/rapido-notificacion", clave,
              [("paquete", nombre_banco), ("titulo", _texto("")), ("texto", _con_variable("", texto_var))], id_post),
        _valor("mensaje", id_post, id_msg),
        # Va de ÚLTIMO: la entrada de un «Si» es, por defecto, la salida de la acción inmediatamente anterior; así es «motivo» incluso si
        # iOS ignora la entrada explícita que también se le pone.
        _valor("motivo", id_post, id_motivo),
    ]
    # Segunda llamada con el MISMO texto + la respuesta de la persona: el servidor registra y aprende la forma del
    # aviso, así la próxima vez de este banco ya no pregunta.
    def responder(uid, monto_v, tipo_v, nota_v=None):
        campos = [("paquete", nombre_banco), ("titulo", _texto("")), ("texto", _con_variable("", texto_var)),
                  ("monto", monto_v), ("tipo", tipo_v)]
        if nota_v is not None:
            campos.append(("nota", nota_v))
        return _post(f"{base}/movimientos/rapido-notificacion", clave, campos, uid)

    # Salió plata y el aviso no dice cuánto (único dato que no se puede deducir): se pregunta SOLO el monto
    pide_monto = [
        _accion("ask", UUID=id_monto, WFAskActionPrompt="¿Cuánto enviaste?", WFInputType="Number"),
        responder(id_rapido, entrada_texto(id_monto), _texto("gasto")),
        _valor("mensaje", id_rapido, id_resp),
        aviso(id_resp),
    ]
    # Hay monto pero el texto no dice si entró o salió: se pregunta (el servidor entiende «Gasto»/«Ingreso»)
    pide_tipo = [
        _valor("monto", id_post, id_monto2),
        _valor("comercio", id_post, id_com2),
        # Una lista fija se arma con la acción «Lista» y «Elegir de la lista» la toma como entrada (no es un parámetro de ésta)
        _accion("list", WFItems=["Gasto", "Ingreso"]),
        _accion("choosefromlist", UUID=id_tipo, WFChooseFromListActionPrompt="¿Entró o salió plata?"),
        responder(id_rapido2, entrada_texto(id_monto2, "Valor del diccionario"),
                  entrada_texto(id_tipo, "Elemento elegido"), entrada_texto(id_com2, "Valor del diccionario")),
        _valor("mensaje", id_rapido2, id_resp2),
        aviso(id_resp2),
    ]
    # El servidor no supo de qué cuenta era: YA lo registró en la más probable y lo dice (primero el aviso, para que nunca se quede
    # mudo). Después pregunta «¿De qué cuenta es?» entre las cuentas registradas (las pide al servidor y elige de esa lista, igual que
    # el atajo de cierre que ya funciona) y, si la persona elige otra, el servidor mueve el movimiento y aprende esa pantalla.
    confirma_cuenta = [
        aviso(id_msg),
        _valor("movimiento_id", id_post, id_movid),
        _accion("downloadurl", UUID=id_cuentas, WFURL=f"{base}/movimientos/cuentas-rapido", WFHTTPMethod="GET",
                WFHTTPHeaders=_dic([("X-Api-Key", clave)])),
        _accion("choosefromlist", UUID=id_banco, WFChooseFromListActionPrompt="¿De qué cuenta es?",
                WFInput={"Value": _salida(id_cuentas, "Contenido de la URL"), "WFSerializationType": "WFTextTokenAttachment"}),
        _post(f"{base}/movimientos/rapido-notificacion", clave,
              [("paquete", _texto("auto")), ("titulo", _texto("")), ("texto", _con_variable("", texto_var)),
               ("movimiento_id", entrada_texto(id_movid, "Valor del diccionario")),
               ("cuenta", entrada_texto(id_banco, "Elemento elegido"))], id_rapido3),
        _valor("mensaje", id_rapido3, id_resp3),
        aviso(id_resp3),
    ]
    # En «pantalla» la persona acaba de hacer un gesto: nunca puede quedarse sin respuesta. En notificaciones, lo que no es un
    # pago (ofertas, códigos) se ignora en silencio.
    # «No parece un pago»: con el gesto la persona espera respuesta; con una notificación (ofertas, códigos) se calla.
    sin_pago = (_si_igual(u(), None, "", "1", [aviso(id_msg)], variable=VAR_GESTO) if modo == "unico"
                else [aviso(id_msg)] if modo == "pantalla" else [])
    nada = _si_igual(u(), id_motivo, "Valor del diccionario", "no_parece_un_movimiento", sin_pago, [aviso(id_msg)])
    tipo = _si_igual(u(), id_motivo, "Valor del diccionario", "pedir_tipo", pide_tipo, nada)
    monto = _si_igual(u(), id_motivo, "Valor del diccionario", "pedir_monto", pide_monto, tipo)
    acciones += _si_igual(u(), id_motivo, "Valor del diccionario", "confirmar_cuenta", confirma_cuenta, monto) if elegir else monto

    return {
        "WFWorkflowClientVersion": "2700",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59511},
        "WFWorkflowTypes": [],
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem", "WFGenericFileContentItem"]
        + (["WFImageContentItem"] if modo == "captura" else []),
        "WFWorkflowActions": acciones,
        "WFWorkflowImportQuestions": ([] if clave_prueba else [
            {"ActionIndex": 0, "Category": "Parameter", "ParameterKey": "WFTextActionText", "DefaultValue": "",
             "Text": "Pega tu clave de CuadraMe (App > Conectar > Clave del atajo)"},
        ]) + ([] if elegir else [
            {"ActionIndex": 1, "Category": "Parameter", "ParameterKey": "WFTextActionText", "DefaultValue": banco,
             "Text": "¿De qué banco o app es? (Nequi, Nu, Bancolombia, Davivienda, Daviplata...)"},
        ]),
    }


# Propiedades de la «Entrada del atajo» que entrega la automatización «Transacción» (Wallet). Los nombres son los que
# muestra iOS: si en tu idioma o versión no resuelven, en Atajos toca la burbuja y elige la propiedad (ver docs/ATAJO_CUADRAME.md).
PROPIEDADES_WALLET = {"comercio": "Merchant", "monto": "Amount", "tarjeta": "Card or Pass"}


def _propiedad_de_entrada(nombre: str) -> dict:
    """«Entrada del atajo › <propiedad>»: la entrada con la propiedad pedida."""
    return {**ENTRADA, "Aggrandizements": [{"Type": "WFPropertyVariableAggrandizement", "PropertyName": nombre}]}


def construir_wallet(base: str) -> dict:
    """«CuadraMe Apple Pay»: automatización Transacción -> /movimientos/rapido, sin preguntar nada."""
    u = lambda: str(uuid.uuid4()).upper()  # noqa: E731
    id_clave, id_post, id_msg = u(), u(), u()
    clave = _con_variable("", _salida(id_clave, "Texto"))
    cuerpo = [(campo, _con_variable("", _propiedad_de_entrada(prop))) for campo, prop in PROPIEDADES_WALLET.items()]
    cuerpo.append(("fuente", _texto("wallet")))
    acciones = [
        _accion("gettext", UUID=id_clave, WFTextActionText=""),
        _post(f"{base}/movimientos/rapido", clave, cuerpo, id_post),
        _valor("mensaje", id_post, id_msg),
        _accion("notification", WFNotificationActionTitle="CuadraMe",
                WFNotificationActionBody=_con_variable("", _salida(id_msg, "Valor del diccionario"))),
    ]
    return {
        "WFWorkflowClientVersion": "2700",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59511},
        "WFWorkflowTypes": [],
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem", "WFGenericFileContentItem"],
        "WFWorkflowActions": acciones,
        # En iOS 27 la automatización viaja DENTRO del atajo: «Transacción» de Wallet (identificador verificado: Atajos lo guarda tal
        # cual en macOS 27.2). Sin parámetros = cualquier tarjeta de Wallet; solo se activa con pagos de Apple Pay.
        "WFWorkflowTriggers": [{"WFTriggerIdentifier": "WFWalletTransactionTrigger", "WFTriggerSerializedParameters": {},
                                "WFTriggerUUID": str(uuid.uuid4()).upper()}],
        "WFWorkflowImportQuestions": [
            {"ActionIndex": 0, "Category": "Parameter", "ParameterKey": "WFTextActionText", "DefaultValue": "",
             "Text": "Pega tu clave de CuadraMe (App > Conectar > Clave del atajo)"},
        ],
    }


def construir_cascaron(interno: str = "CuadraMe Registrar") -> dict:
    """«CuadraMe»: un atajo FIJO que solo llama al atajo real por su nombre. El gesto (Tocar atrás, Botón de acción) se asigna a
    este y no se pierde cuando se cambia el atajo interno. Prueba: no se sabe si iOS 27 deja la referencia por nombre."""
    return {
        "WFWorkflowClientVersion": "2700",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59511},
        "WFWorkflowTypes": [],
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem", "WFGenericFileContentItem"],
        "WFWorkflowActions": [_accion("runworkflow", WFWorkflowName=interno,
                                      WFInput={"Value": ENTRADA, "WFSerializationType": "WFTextTokenAttachment"})],
        "WFWorkflowImportQuestions": [],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://api.cuadrame.dapx.shop")
    p.add_argument("--banco", default="Nequi")
    p.add_argument("--modo", choices=["unico", "notificacion", "pantalla", "captura", "wallet", "cascaron"], default="notificacion")
    p.add_argument("--salida", default="CuadraMe Notificaciones.shortcut")
    p.add_argument("--clave-prueba", default="", help="SOLO pruebas locales: pone una clave falsa dentro del archivo y no la pide al instalar")
    p.add_argument("--interno", default="CuadraMe Registrar", help="solo para --modo cascaron: nombre del atajo que llama")
    a = p.parse_args()
    with open(a.salida, "wb") as f:
        if a.modo == "wallet":
            datos = construir_wallet(a.base.rstrip("/"))
        elif a.modo == "cascaron":
            datos = construir_cascaron(a.interno)
        else:
            datos = construir(a.base.rstrip("/"), a.banco, a.modo, a.clave_prueba)
        plistlib.dump(datos, f, fmt=plistlib.FMT_BINARY)
    print(f"Listo: {a.salida} (sin firmar). Fírmalo en el Mac con `shortcuts sign -m anyone -i ... -o ...`.")


if __name__ == "__main__":
    main()
