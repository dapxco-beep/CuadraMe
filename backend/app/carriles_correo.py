"""Los dos usos del correo, contados POR SEPARADO.

  movimientos  Notificaciones del banco (compra, transferencia, retiro, pago): el dato real del día a día.
               Cada una queda «por revisar» hasta que la apruebas; al aprobarla pasa a Movimientos
               como provisional («correo») y se confirma sola cuando llega el extracto.
  extractos    PDF del estado de cuenta: sirve para CONCILIAR y cuadrar el mes.

Cada carril tiene su interruptor (perfiles.gmail_leer_movimientos / gmail_leer_extractos, activos por
defecto), su «última vez» y sus contadores. Esta función solo LEE; no toca Gmail.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import estado_traer, punto_partida
from app.models import CorreoGasto, Movimiento, Perfil, SyncGmail

NOMBRE_CARRIL = {
    "movimientos": "Movimientos del día a día",
    "extractos": "Extractos para conciliar",
}


def _iso(d):
    return d.isoformat() if d else None


def movimientos_sin_extracto(db: Session, usuario_id: str) -> int:
    """Movimientos que entraron por correo y aún no respalda un extracto («falta confirmar con el
    extracto»): tienen el canal «correo» vigente y ninguno de «extracto». Usa las etiquetas de origen
    que ya existen (HuellaOrigen); no hay un modelo nuevo."""
    from app.duplicados import ESTADO_VIGENTE, ORIGEN_CORREO, ORIGEN_EXTRACTO
    from app.models import HuellaOrigen

    def ids(origen):
        return db.query(HuellaOrigen.movimiento_id).filter(
            HuellaOrigen.usuario_id == usuario_id, HuellaOrigen.estado == ESTADO_VIGENTE, HuellaOrigen.origen == origen)

    n = (
        db.query(func.count(Movimiento.id))
        .filter(Movimiento.usuario_id == usuario_id, Movimiento.conciliado_en.is_(None),
                Movimiento.id.in_(ids(ORIGEN_CORREO)), ~Movimiento.id.in_(ids(ORIGEN_EXTRACTO)))
        .scalar()
    )
    return int(n or 0)


def resumen(db: Session, usuario_id: str, lista_ext: list[dict] | None = None) -> dict:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario_id).first()
    sync = db.query(SyncGmail).filter(SyncGmail.usuario_id == usuario_id).first()
    inicio_pp = punto_partida.fecha_inicio(db, usuario_id)
    if lista_ext is None:
        lista_ext = estado_traer.lista_extractos(db, usuario_id, inicio_pp)

    def cuenta_correos(estado: str) -> int:
        q = db.query(func.count(CorreoGasto.id)).filter(CorreoGasto.usuario_id == usuario_id, CorreoGasto.estado == estado)
        if estado == "pendiente":
            q = q.filter(CorreoGasto.monto > 0)
        return int(q.scalar() or 0)

    por_revisar = cuenta_correos("pendiente")
    ya_registrados = cuenta_correos("ya_registrado")
    de_correo = [x for x in lista_ext if "correo" in (x.get("origenes") or [])]
    por_estado = {e: sum(1 for x in de_correo if x["estado"] == e) for e in estado_traer.ESTADOS}
    # Datos de antes de los carriles (sin marcas por carril): la marca general vale para ambos.
    legado = bool(sync) and not sync.ultima_sync_mov and not sync.ultima_sync_ext
    marca_mov = (sync.ultima_sync or None) if legado else (sync.ultima_sync_mov if sync else None)
    marca_ext = (sync.ultima_sync or None) if legado else (sync.ultima_sync_ext if sync else None)
    en_curso = bool(sync and sync.en_curso)
    ultimo = lambda col: (getattr(sync, col, None) or 0) if sync else 0  # noqa: E731

    return {
        "movimientos": {
            "nombre": NOMBRE_CARRIL["movimientos"],
            "activo": not perfil or perfil.gmail_leer_movimientos is not False,
            "ultima_vez": _iso(marca_mov),
            "leidos": ultimo("ultimo_leidos_mov"),
            "nuevos": ultimo("ultimo_nuevos"),
            "por_revisar": por_revisar,
            "ya_registrados": ya_registrados,
            "provisionales": movimientos_sin_extracto(db, usuario_id),
            "ultimo_error": sync.ultimo_error if sync else None,
        },
        "extractos": {
            "nombre": NOMBRE_CARRIL["extractos"],
            "activo": not perfil or perfil.gmail_leer_extractos is not False,
            "ultima_vez": _iso(marca_ext),
            "encontrados": len(de_correo),
            "leidos": len(de_correo) - por_estado[estado_traer.NECESITA_CLAVE] - por_estado[estado_traer.NO_SE_PUDO_LEER],
            "por_conciliar": por_estado[estado_traer.POR_REVISAR],
            "con_clave_pendiente": por_estado[estado_traer.NECESITA_CLAVE],
            "no_se_pudo_leer": por_estado[estado_traer.NO_SE_PUDO_LEER],
            "al_dia": por_estado[estado_traer.AL_DIA],
            "nuevos": ultimo("ultimo_extractos"),
        },
        "en_curso": en_curso,
        "tipo_en_curso": (sync.tipo or "todo") if en_curso else None,
    }
