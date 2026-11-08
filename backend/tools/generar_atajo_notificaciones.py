"""Genera «CuadraMe Notificaciones.shortcut» (sin firmar) para el disparador «Notificación» de iOS 27.

Uso:   python tools/generar_atajo_notificaciones.py [--base URL] [--modo notificacion|pantalla|captura|wallet] [--salida archivo]
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


ENTRADA = {"Type": "ExtensionInput"}  # «Entrada del atajo»: lo que manda la automatización


def _salida(uid: str, nombre: str) -> dict:
    return {"Type": "ActionOutput", "OutputUUID": uid, "OutputName": nombre}


def _dic(pares: list[tuple[str, dict]]) -> dict:
    return {
        "Value": {"WFDictionaryFieldValueItems": [
            {"WFItemType": 0, "WFKey": _texto(k), "WFValue": v} for k, v in pares]},
        "WFSerializationType": "WFDictionaryFieldValue",
    }


def _accion(identificador: str, **parametros) -> dict:
    return {"WFWorkflowActionIdentifier": f"is.workflow.actions.{identificador}",
            "WFWorkflowActionParameters": parametros}


def _post(url: str, clave: dict, cuerpo: list[tuple[str, dict]], uid: str) -> dict:
    return _accion(
        "downloadurl", UUID=uid, WFURL=url, WFHTTPMethod="POST", WFHTTPBodyType="JSON",
        WFHTTPHeaders=_dic([("X-Api-Key", clave)]), WFJSONValues=_dic(cuerpo))


def _valor(clave: str, de: str, uid: str) -> dict:
    return _accion("getvalueforkey", UUID=uid, WFDictionaryKey=clave,
                   WFInput={"Value": _salida(de, "Contenido de la URL"), "WFSerializationType": "WFTextTokenAttachment"})


def _si_igual(grupo: str, variable_uid: str, nombre: str, valor: str, dentro: list[dict], si_no: list[dict] | None = None):
    inicio = _accion(
        "conditional", GroupingIdentifier=grupo, WFControlFlowMode=0, WFCondition="Equals", WFConditionalActionString=valor,
        WFInput={"Type": "Variable", "Variable": {"Value": _salida(variable_uid, nombre), "WFSerializationType": "WFTextTokenAttachment"}})
    medio = _accion("conditional", GroupingIdentifier=grupo, WFControlFlowMode=1)
    fin = _accion("conditional", GroupingIdentifier=grupo, WFControlFlowMode=2, UUID=str(uuid.uuid4()).upper())
    return [inicio, *dentro, medio, *(si_no or []), fin]


def _leer_imagen(modo: str, id_shot: str, id_ocr: str) -> list[dict]:
    """Acciones que sacan el texto de una imagen (OCR del propio iPhone, sin enviarla a ningún lado)."""
    if modo == "notificacion":
        return []
    if modo == "pantalla":
        origen = {"Value": _salida(id_shot, "Captura de pantalla"), "WFSerializationType": "WFTextTokenAttachment"}
        previo = [_accion("takescreenshot", UUID=id_shot)]
    else:  # captura: la imagen es la entrada del atajo
        origen = {"Value": ENTRADA, "WFSerializationType": "WFTextTokenAttachment"}
        previo = []
    return [*previo, _accion("extracttextfromimage", UUID=id_ocr, WFImage=origen)]


def construir(base: str, banco: str = "Nequi", modo: str = "notificacion") -> dict:
    u = lambda: str(uuid.uuid4()).upper()  # noqa: E731
    id_clave, id_banco, id_post, id_motivo, id_msg = u(), u(), u(), u(), u()
    id_monto, id_para, id_rapido, id_resp = u(), u(), u(), u()
    id_monto2, id_com2, id_tipo, id_rapido2, id_resp2 = u(), u(), u(), u(), u()
    id_shot, id_ocr, id_cuentas = u(), u(), u()
    elegir = modo in ("pantalla", "notificacion")  # no se pregunta el banco: el servidor lo deduce del texto o de lo aprendido
    id_rapido3, id_resp3, id_cuentas_resp = u(), u(), u()
    # De dónde sale el texto: la notificación misma o el texto leído de una imagen (pantallazo / captura)
    texto_var = ENTRADA if modo == "notificacion" else _salida(id_ocr, "Texto de la imagen")
    clave = _con_variable("", _salida(id_clave, "Texto"))
    nombre_banco = _texto("auto") if elegir else _con_variable("", _salida(id_banco, "Texto"))
    entrada_texto = lambda uid, n="Entrada proporcionada": _con_variable("", _salida(uid, n))  # noqa: E731
    aviso = lambda uid: _accion("notification", WFNotificationActionTitle="CuadraMe",  # noqa: E731
                                WFNotificationActionBody=_con_variable("", _salida(uid, "Valor del diccionario")))

    acciones = [
        # 0: la clave API (se pregunta al instalar) y, salvo en «pantalla», 1: el banco (también al instalar)
        _accion("gettext", UUID=id_clave, WFTextActionText=""),
        *([] if elegir else [_accion("gettext", UUID=id_banco, WFTextActionText=banco)]),
        *_leer_imagen(modo, id_shot, id_ocr),
        # El texto crudo (de la notificación o del pantallazo): el servidor lo lee, no el atajo
        _post(f"{base}/movimientos/rapido-notificacion", clave,
              [("paquete", nombre_banco), ("titulo", _texto("")), ("texto", _con_variable("", texto_var))], id_post),
        _valor("motivo", id_post, id_motivo),
        _valor("mensaje", id_post, id_msg),
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
        _accion("choosefromlist", UUID=id_tipo, WFChooseFromListActionPrompt="¿Entró o salió plata?",
                WFChooseFromListActionList=["Gasto", "Ingreso"]),
        responder(id_rapido2, entrada_texto(id_monto2, "Valor del diccionario"),
                  entrada_texto(id_tipo, "Elemento elegido"), entrada_texto(id_com2, "Valor del diccionario")),
        _valor("mensaje", id_rapido2, id_resp2),
        aviso(id_resp2),
    ]
    # El servidor no pudo deducir de qué cuenta es el pantallazo: se pregunta UNA vez y lo aprende
    pide_cuenta = [
        _valor("cuentas", id_post, id_cuentas_resp),
        _accion("choosefromlist", UUID=id_banco, WFChooseFromListActionPrompt="¿De qué cuenta es?",
                WFInput={"Value": _salida(id_cuentas_resp, "Valor del diccionario"), "WFSerializationType": "WFTextTokenAttachment"}),
        _post(f"{base}/movimientos/rapido-notificacion", clave,
              [("paquete", _texto("auto")), ("titulo", _texto("")), ("texto", _con_variable("", texto_var)),
               ("cuenta", entrada_texto(id_banco, "Elemento elegido"))], id_rapido3),
        _valor("mensaje", id_rapido3, id_resp3),
        aviso(id_resp3),
    ]
    # En «pantalla» la persona acaba de hacer un gesto: nunca puede quedarse sin respuesta. En notificaciones, lo que no es un
    # pago (ofertas, códigos) se ignora en silencio.
    nada = _si_igual(u(), id_motivo, "Valor del diccionario", "no_parece_un_movimiento",
                     [aviso(id_msg)] if modo == "pantalla" else [], [aviso(id_msg)])
    tipo = _si_igual(u(), id_motivo, "Valor del diccionario", "pedir_tipo", pide_tipo, nada)
    monto = _si_igual(u(), id_motivo, "Valor del diccionario", "pedir_monto", pide_monto, tipo)
    acciones += _si_igual(u(), id_motivo, "Valor del diccionario", "pedir_cuenta", pide_cuenta, monto) if elegir else monto

    return {
        "WFWorkflowClientVersion": "2700",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59511},
        "WFWorkflowTypes": [],
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem", "WFGenericFileContentItem"]
        + (["WFImageContentItem"] if modo == "captura" else []),
        "WFWorkflowActions": acciones,
        "WFWorkflowImportQuestions": [
            {"ActionIndex": 0, "Category": "Parameter", "ParameterKey": "WFTextActionText", "DefaultValue": "",
             "Text": "Pega tu clave de CuadraMe (App > Conectar > Clave del atajo)"},
        ] + ([] if elegir else [
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
        "WFWorkflowImportQuestions": [
            {"ActionIndex": 0, "Category": "Parameter", "ParameterKey": "WFTextActionText", "DefaultValue": "",
             "Text": "Pega tu clave de CuadraMe (App > Conectar > Clave del atajo)"},
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="https://api.cuadrame.dapx.shop")
    p.add_argument("--banco", default="Nequi")
    p.add_argument("--modo", choices=["notificacion", "pantalla", "captura", "wallet"], default="notificacion")
    p.add_argument("--salida", default="CuadraMe Notificaciones.shortcut")
    a = p.parse_args()
    with open(a.salida, "wb") as f:
        datos = construir_wallet(a.base.rstrip("/")) if a.modo == "wallet" else construir(a.base.rstrip("/"), a.banco, a.modo)
        plistlib.dump(datos, f, fmt=plistlib.FMT_BINARY)
    print(f"Listo: {a.salida} (sin firmar). Fírmalo en el Mac con `shortcuts sign -m anyone -i ... -o ...`.")


if __name__ == "__main__":
    main()
