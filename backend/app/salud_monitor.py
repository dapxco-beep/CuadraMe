"""Monitor de salud de datos PARA EL DUEÑO: contadores agregados y anónimos (cuántas personas, nunca cuáles).

`contadores(db)` cuenta, sin ids ni datos personales:
  lectura_en_cero      personas con Gmail conectado y lectura activa cuyas últimas corridas dieron 0 correos
  extractos_en_error   personas con algún extracto en error
  descartados_altos    personas con muchos correos descartados con monto
  sin_sync_48h         personas con Gmail conectado sin sincronizar hace más de 48 h
`revisar(db)` los compara con UMBRALES y, si alguno se supera, deja UN aviso por día en «Actividad reciente»
(app/avisos.py: push y correo al administrador, el mismo mecanismo de los picos de errores 5xx)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CorreoGasto, HistorialExtracto, Perfil, SyncGmail
from app.routers.consentimientos import tiene_consentimiento
from app.salud_datos import CEROS_PARA_AVISAR, HORAS_SIN_SINCRONIZAR
from app.utiles import ahora_co

logger = logging.getLogger("app.salud_monitor")

DESCARTADOS_ALTOS = 5   # correos descartados con monto para contar a una persona
# Cuántas personas hacen falta para avisar al dueño. Una sola con la lectura en 0 ya puede ser una falla del
# sistema (pasó durante días sin que nadie lo notara), por eso ese umbral es 1.
UMBRALES = {"lectura_en_cero": 1, "extractos_en_error": 3, "descartados_altos": 3, "sin_sync_48h": 2}
ETIQUETAS = {
    "lectura_en_cero": "con la lectura de correo en 0",
    "extractos_en_error": "con extractos en error",
    "descartados_altos": "con muchos correos descartados",
    "sin_sync_48h": "sin sincronizar hace más de 48 h",
}


def _gmail_activos(db: Session) -> dict[str, tuple]:
    """usuario_id -> (perfil, sync) de quienes tienen Gmail conectado, token y consentimiento de lectura."""
    filas = (db.query(Perfil, SyncGmail).join(SyncGmail, SyncGmail.usuario_id == Perfil.usuario_id)
             .filter(Perfil.gmail_conectado.is_(True), Perfil.gmail_refresh_token_enc.isnot(None)).all())
    return {p.usuario_id: (p, s) for p, s in filas if tiene_consentimiento(db, p.usuario_id, "lectura_correo")}


def contadores(db: Session) -> dict[str, int]:
    activos = _gmail_activos(db)
    limite = datetime.utcnow() - timedelta(hours=HORAS_SIN_SINCRONIZAR)
    en_cero = sin_sync = 0
    for p, s in activos.values():
        if p.gmail_leer_movimientos is not False and int(s.ceros_seguidos_mov or 0) >= CEROS_PARA_AVISAR:
            en_cero += 1
        ultima = max([d for d in (s.ultima_sync, s.ultima_sync_mov, s.ultima_sync_ext) if d], default=None)
        if ultima is not None and ultima < limite:
            sin_sync += 1
    con_error = db.query(func.count(func.distinct(HistorialExtracto.usuario_id))).filter(
        HistorialExtracto.estado == "error").scalar() or 0
    altos = db.query(CorreoGasto.usuario_id).filter(CorreoGasto.estado == "descartado", CorreoGasto.monto > 0) \
        .group_by(CorreoGasto.usuario_id).having(func.count(CorreoGasto.id) >= DESCARTADOS_ALTOS).count()
    return {"lectura_en_cero": en_cero, "extractos_en_error": int(con_error), "descartados_altos": int(altos),
            "sin_sync_48h": sin_sync, "con_gmail_activo": len(activos)}


def superados(cont: dict[str, int]) -> list[str]:
    return [k for k, umbral in UMBRALES.items() if cont.get(k, 0) >= umbral]


def revisar(db: Session) -> dict:
    """Calcula los contadores y, si alguno supera su umbral, deja UN aviso al dueño por día."""
    cont = contadores(db)
    pasados = superados(cont)
    alertado = False
    if pasados:
        try:
            from app import avisos

            texto = "Salud de datos: " + "; ".join(f"{cont[k]} {ETIQUETAS[k]}" for k in pasados)
            avisos.registrar_evento("salud_datos_alerta", meta={k: cont[k] for k in pasados},
                                    clave_unica=f"salud_datos:{ahora_co().date().isoformat()}", texto=texto)
            alertado = True
        except Exception:  # noqa: BLE001 - un aviso nunca debe romper el cron
            logger.warning("Monitor de salud: no se pudo registrar el aviso", exc_info=True)
    return {"ok": True, "contadores": cont, "umbrales": UMBRALES, "superados": pasados, "alertado": alertado}
