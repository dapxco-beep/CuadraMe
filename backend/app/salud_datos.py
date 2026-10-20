"""Salud de datos: «Revisé tu cuenta y encontré N cosas».

`diagnosticar(db, usuario_id)` mira los datos de UNA persona y devuelve una lista de hallazgos tipados.
Solo LEE (nunca corrige ni mueve dinero): la autocuración vive en `salud_autocuracion.py` y todo lo que
toca movimientos ya importados queda como sugerencia con vista previa.

Cada hallazgo es un dict:
  codigo     identificador estable (ver CODIGOS)
  severidad  'importante' | 'aviso' | 'info'
  titulo     frase corta en español claro (textos según docs/GUIA_DE_TEXTOS.md)
  texto      una o dos frases que explican qué pasó y qué se puede hacer
  accion     {tipo, etiqueta, ...}: lo que hace el botón de un toque (la PWA decide la ruta por `tipo`)
  datos      SOLO ids y conteos: nunca montos, descripciones, nombres de comercios ni contenido de correos.

Los 8 hallazgos nacen de fallas reales que un usuario encontró probando con sus datos."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import fechas_extracto
from app.cuentas_banco import CREDITO, producto_de_cuenta, producto_de_texto
from app.extractos_error import MOTIVOS_CLAVE, correo_de_error
from app.extractos_gmail import cuentas_del_banco
from app.models import (
    ClavePdf, CorreoGasto, Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil, SyncGmail,
)
from app.routers.consentimientos import tiene_consentimiento

CODIGOS = (
    "extracto_producto_distinto",
    "tarjeta_sin_cuenta",
    "extracto_en_error_recuperable",
    "correos_descartados_con_monto",
    "lectura_correo_en_cero",
    "clave_pdf_faltante",
    "movimientos_en_cuenta_incoherente",
    "sin_sincronizar",
    "fechas_extracto_dudosas",
)
ORDEN_SEVERIDAD = {"importante": 0, "aviso": 1, "info": 2}
CEROS_PARA_AVISAR = 3        # corridas completas seguidas sin leer ni un correo
HORAS_SIN_SINCRONIZAR = 48
MAX_IDS = 10                 # ids por hallazgo: lo mínimo para actuar, sin inflar la respuesta
_ESTADOS_EXTRACTO_VIVOS = ("nuevo", "procesado", "falta_clave", "error")


def _h(codigo: str, severidad: str, titulo: str, texto: str, accion: dict, datos: dict) -> dict:
    return {"codigo": codigo, "severidad": severidad, "titulo": titulo, "texto": texto, "accion": accion, "datos": datos}


def _plural(n: int, uno: str, varios: str) -> str:
    return uno if n == 1 else varios


def _texto_extracto(e: ExtractoCorreo) -> str:
    return f"{e.asunto or ''} {e.archivo or ''}"


def _cuenta_de_extracto(e: ExtractoCorreo, hist: dict, cuentas: dict):
    h = hist.get(e.historial_id) if e.historial_id else None
    cid = h.cuenta_id if h is not None else e.cuenta_sugerida_id
    return cuentas.get(cid) if cid else None


def _gmail_activo(db: Session, perfil: Perfil | None, usuario_id: str) -> bool:
    return bool(perfil and perfil.gmail_conectado and perfil.gmail_refresh_token_enc
                and tiene_consentimiento(db, usuario_id, "lectura_correo"))


def diagnosticar(db: Session, usuario_id: str) -> list[dict]:
    """Hallazgos de salud de datos de UN usuario, los más importantes primero. Solo lectura."""
    cuentas_l = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()
    cuentas = {c.id: c for c in cuentas_l}
    extractos = db.query(ExtractoCorreo).filter(
        ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.estado.in_(_ESTADOS_EXTRACTO_VIVOS)).all()
    historiales = db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario_id).all()
    hist = {h.id: h for h in historiales}
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    sync = db.query(SyncGmail).filter(SyncGmail.usuario_id == usuario_id).first()
    tiene_clave = db.query(ClavePdf.usuario_id).filter(ClavePdf.usuario_id == usuario_id).first() is not None
    out: list[dict] = []

    # 1) Extracto de un producto (tarjeta/ahorros) distinto al de la cuenta donde quedó.
    #    Si se importó algo, los movimientos están en la cuenta equivocada.
    mal = []
    for e in extractos:
        cuenta = _cuenta_de_extracto(e, hist, cuentas)
        p_ext, p_cta = producto_de_texto(_texto_extracto(e)), producto_de_cuenta(cuenta) if cuenta else None
        if cuenta is not None and p_ext and p_cta and p_ext != p_cta:
            mal.append(e)
    if mal:
        con_hist = [e for e in mal if e.historial_id]
        n = len(mal)
        out.append(_h(
            "extracto_producto_distinto", "importante",
            f"{n} {_plural(n, 'extracto parece', 'extractos parecen')} de otro producto",
            "Por lo que dice el correo, "
            + ("este extracto es de una tarjeta pero está en una cuenta de ahorros (o al revés). "
               if n == 1 else "estos extractos están en una cuenta que no es la suya. ")
            + "Mira la vista previa y cámbialo de cuenta si es lo correcto.",
            {"tipo": "cambiar_cuenta_extracto", "etiqueta": "Revisar",
             "historial_id": (con_hist[0].historial_id if con_hist else None),
             "cuenta_id": (hist[con_hist[0].historial_id].cuenta_id if con_hist and con_hist[0].historial_id in hist else None)},
            {"cantidad": n, "extracto_ids": [e.id for e in mal][:MAX_IDS],
             "historial_ids": [e.historial_id for e in con_hist][:MAX_IDS]},
        ))

    # 2) Extractos de tarjeta de un banco donde la persona no tiene cuenta de crédito.
    sin_cuenta: Counter = Counter()
    for e in extractos:
        if e.banco and producto_de_texto(_texto_extracto(e)) == CREDITO:
            del_banco = cuentas_del_banco(e.banco, cuentas_l)
            if not any(producto_de_cuenta(c) == CREDITO for c in del_banco):
                sin_cuenta[e.banco] += 1
    for banco, n in sorted(sin_cuenta.items()):
        out.append(_h(
            "tarjeta_sin_cuenta", "importante",
            f"Falta tu cuenta de tarjeta {banco}",
            f"Llegaron {n} {_plural(n, 'extracto', 'extractos')} de tu tarjeta {banco} y todavía no tienes esa tarjeta en CuadraMe. "
            "Créala con un toque y los extractos quedan donde van.",
            {"tipo": "crear_cuenta_tarjeta", "etiqueta": f"Crear tarjeta {banco}", "banco": banco},
            {"banco": banco, "cantidad": n},
        ))

    # 3) Extractos en error que se pueden reintentar (tienen correo y, si era por clave, ya hay clave).
    errores = [h for h in historiales if h.estado == "error"]
    if errores:
        correos = db.query(ExtractoCorreo).filter(ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.archivo != "").all()
        recuperables = [h for h in errores if correo_de_error(db, h, correos=correos) is not None
                        and not (h.motivo_error in MOTIVOS_CLAVE and not tiene_clave)]
        if recuperables:
            n = len(recuperables)
            out.append(_h(
                "extracto_en_error_recuperable", "aviso",
                f"{n} {_plural(n, 'extracto se puede', 'extractos se pueden')} volver a intentar",
                "No se pudieron leer, pero vienen de tu correo y ahora se pueden reintentar. Toca para intentarlo de nuevo.",
                {"tipo": "reintentar_errores", "etiqueta": "Reintentar"},
                {"cantidad": n, "historial_ids": [h.id for h in recuperables][:MAX_IDS]},
            ))

    # 4) Correos de transacciones descartados (con monto): la persona puede recuperarlos.
    n_desc = db.query(func.count(CorreoGasto.id)).filter(
        CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == "descartado", CorreoGasto.monto > 0).scalar() or 0
    if n_desc:
        out.append(_h(
            "correos_descartados_con_monto", "aviso",
            f"{n_desc} {_plural(n_desc, 'correo quedó fuera', 'correos quedaron fuera')} de Por revisar",
            "Coinciden con un movimiento que borraste. Si alguno sí era tuyo, puedes devolverlo a Por revisar.",
            {"tipo": "ver_descartados", "etiqueta": "Ver correos"},
            {"cantidad": int(n_desc)},
        ))

    # 5) La lectura de movimientos del correo da 0 correos varias veces seguidas.
    if (_gmail_activo(db, perfil, usuario_id) and perfil.gmail_leer_movimientos is not False
            and sync is not None and int(sync.ceros_seguidos_mov or 0) >= CEROS_PARA_AVISAR):
        out.append(_h(
            "lectura_correo_en_cero", "importante",
            "Tu correo lleva varias lecturas sin traer nada",
            "Gmail está conectado pero las últimas lecturas no encontraron correos de movimientos. "
            "Puede ser un problema de conexión: vuelve a conectar Gmail o revisa la etiqueta.",
            {"tipo": "revisar_conexion", "etiqueta": "Revisar conexión"},
            {"corridas_en_cero": int(sync.ceros_seguidos_mov or 0)},
        ))

    # 6) Extractos esperando una clave que no existe.
    if not tiene_clave:
        esperan = [e for e in extractos if e.estado == "falta_clave"]
        esperan_h = [h for h in errores if h.motivo_error in MOTIVOS_CLAVE]
        n = len(esperan) + len(esperan_h)
        if n:
            out.append(_h(
                "clave_pdf_faltante", "importante",
                "Falta la clave de tus extractos",
                f"{n} {_plural(n, 'extracto está', 'extractos están')} esperando la clave del PDF (casi siempre es tu cédula). "
                "Guárdala una vez y se leen solos.",
                {"tipo": "guardar_clave", "etiqueta": "Guardar clave"},
                {"cantidad": n},
            ))

    # 7) Movimientos importados de un extracto que viven en una cuenta distinta a la del extracto.
    if historiales:
        ids = [h.id for h in historiales]
        filas = db.query(Movimiento.extracto_id, func.count(Movimiento.id)).filter(
            Movimiento.usuario_id == usuario_id, Movimiento.extracto_id.in_(ids)).group_by(Movimiento.extracto_id).all()
        incoherentes = {}
        for hid, _n in filas:
            h = hist[hid]
            n_fuera = db.query(func.count(Movimiento.id)).filter(
                Movimiento.usuario_id == usuario_id, Movimiento.extracto_id == hid,
                Movimiento.cuenta_id != h.cuenta_id).scalar() or 0
            if n_fuera:
                incoherentes[hid] = int(n_fuera)
        if incoherentes:
            primero = next(iter(incoherentes))
            out.append(_h(
                "movimientos_en_cuenta_incoherente", "importante",
                f"{len(incoherentes)} {_plural(len(incoherentes), 'extracto tiene', 'extractos tienen')} movimientos en otra cuenta",
                "Hay movimientos que salieron de un extracto pero están en una cuenta distinta a la del extracto. "
                "Revisa la vista previa antes de moverlos.",
                {"tipo": "cambiar_cuenta_extracto", "etiqueta": "Revisar", "historial_id": primero, "cuenta_id": hist[primero].cuenta_id},
                {"cantidad": sum(incoherentes.values()), "historial_ids": list(incoherentes)[:MAX_IDS]},
            ))

    # 8) Gmail conectado y sin sincronizar hace más de 48 horas.
    if _gmail_activo(db, perfil, usuario_id) and sync is not None:
        ultima = max([d for d in (sync.ultima_sync, sync.ultima_sync_mov, sync.ultima_sync_ext) if d], default=None)
        if ultima is not None and datetime.utcnow() - ultima > timedelta(hours=HORAS_SIN_SINCRONIZAR):
            out.append(_h(
                "sin_sincronizar", "aviso",
                "Hace días que no traemos tus correos",
                "Tu Gmail sigue conectado pero la última lectura fue hace más de 2 días. Toca para traer lo nuevo.",
                {"tipo": "sincronizar", "etiqueta": "Traer ahora"},
                {"horas": int((datetime.utcnow() - ultima).total_seconds() // 3600)},
            ))

    # 9) Fechas de extractos conciliados que no cuadran: sin fecha, repetidos, con corte futuro o periodos cruzados.
    #    Las dos primeras causas las repara solo el autoarreglo; las otras dos las decide la persona.
    f = fechas_extracto.revisar_fechas(db, usuario_id)
    n_solas, n_decidir = len(f["sin_fechas"]) + len(f["duplicados"]), len(f["futuras"]) + len(f["traslapados"])
    if n_solas or n_decidir:
        n = n_solas + n_decidir
        partes = []
        if f["sin_fechas"]:
            partes.append("falta la fecha de corte en " + str(len(f["sin_fechas"])))
        if f["duplicados"]:
            partes.append(f"{len(f['duplicados'])} {_plural(len(f['duplicados']), 'está repetido', 'están repetidos')}")
        if f["futuras"]:
            partes.append(f"{len(f['futuras'])} {_plural(len(f['futuras']), 'tiene un corte que aún no llega', 'tienen un corte que aún no llega')}")
        if f["traslapados"]:
            partes.append(f"{len(f['traslapados'])} {_plural(len(f['traslapados']), 'se cruza', 'se cruzan')} con otro periodo")
        solas = ("Lo de la fecha faltante y los repetidos se ordena solo al abrir «Traer movimientos». " if n_solas else "")
        decidir = ("Lo demás conviene revisarlo: abre el extracto y confirma las fechas que dice tu banco." if n_decidir else "")
        out.append(_h(
            "fechas_extracto_dudosas", "aviso" if n_decidir else "info",
            f"{n} {_plural(n, 'extracto tiene', 'extractos tienen')} fechas por revisar",
            "Entre tus extractos: " + "; ".join(partes) + ". " + solas + decidir,
            {"tipo": "ver_extractos", "etiqueta": "Ver extractos"},
            {"cantidad": n, "sin_fechas": len(f["sin_fechas"]), "repetidos": len(f["duplicados"]), "cortes_futuros": len(f["futuras"]),
             "periodos_cruzados": len(f["traslapados"]),
             "historial_ids": (f["futuras"] + f["traslapados"] + f["sin_fechas"] + f["duplicados"])[:MAX_IDS]},
        ))

    out.sort(key=lambda x: ORDEN_SEVERIDAD.get(x["severidad"], 9))
    return out
