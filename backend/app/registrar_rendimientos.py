"""«Registrar los rendimientos de mis extractos (N)»: UN paso para los extractos ya importados que traen rendimientos.

Problema: el extracto de una cuenta de ahorros (Nu, Lulo...) suma «Rendimiento total» al saldo, pero esa plata no es una
línea de movimientos. Los extractos que ya se importaron con el lector viejo nunca la registraron, y esos meses no
cuadran al peso (rendimientos_extracto.py explica la línea nueva). Aquí se registra de golpe, con vista previa.

Qué extractos entran (solo cuentas que NO son tarjeta de crédito):
  A) los que ya tienen la línea de rendimiento «por importar» (la relectura la agregó) y la lectura cuadra: monto exacto.
  B) los conciliados con correo, sin la línea, cuyo mes tiene una diferencia chica a favor del banco (el cuadre mes a
     mes de cuadre_encadenado): monto ESTIMADO con esa diferencia; el real sale al releer el PDF.
  Los subidos a mano (sin correo) no se pueden releer: se saltan. Los de mes que ya cuadra no entran.

Cómo funciona: del más viejo al más nuevo; los B se releen en modo «solo agregar» (releer_extracto, lo importado no se
toca) y la línea se importa con el mismo código de «Importar» (misma huella, mismo saldo, mismo recálculo del ajuste
inicial). Si la lectura no cuadra la línea queda apagada y NO se registra. Si ya hay un «Ajuste de saldo» por el mismo
valor en ese mes, tampoco se registra (se duplicaría): se avisa. Idempotente (la marca `releer_extracto:<id>` guarda la
versión del lector) y sin columnas nuevas. Máximo 12 por llamada, como «Arreglar mis extractos de la tarjeta»."""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import cuadre_encadenado as ce
from app import cuadre_extracto as cx
from app import releer_extracto as rx
from app.arreglar_tarjetas import _mes, _orden
from app.contabilidad import FUENTE_AJUSTE, delta_saldo
from app.crons import MarcaCron
from app.cuentas_banco import CREDITO, producto_de_cuenta
from app.models import ClavePdf, Cuenta, HistorialExtracto, Movimiento, Perfil
from app.rendimientos_extracto import es_linea_de_rendimiento

logger = logging.getLogger(__name__)

MAXIMO_POR_LLAMADA = 12
TOPE_RELATIVO = 0.05  # un mes que "faltan" más del 5 % del saldo no son rendimientos: es otra cosa


def _review(h: HistorialExtracto) -> list[dict]:
    try:
        r = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return r if isinstance(r, list) else []


def _linea(h: HistorialExtracto) -> dict | None:
    """La línea de rendimiento de la revisión del extracto (cualquier estado), o None."""
    return next((i for i in _review(h) if es_linea_de_rendimiento(i)), None)


def _estimados_por_historial(db: Session, cuentas: list[Cuenta]) -> dict[str, float]:
    """{historial_id: lo que el banco sumó de más ese mes} para meses con una diferencia chica a favor del banco."""
    out: dict[str, float] = {}
    for c in cuentas:
        try:
            r = ce.calcular(db, c)
        except Exception:  # noqa: BLE001 - una cuenta rara no frena a las demás
            continue
        for f in r["meses"]:
            hid, dif = f.get("historial_id"), f.get("diferencia") or 0.0
            base = max(abs(f.get("banco_final") or 0.0), abs(f.get("banco_inicial") or 0.0))
            if hid and f.get("estado") == "diferencia" and dif >= cx.TOLERANCIA and dif <= TOPE_RELATIVO * base:
                out[hid] = round(dif, 2)
    return out


def candidatos_sin_linea(db: Session, usuario) -> list[tuple[HistorialExtracto, float, Cuenta]]:
    """Extractos conciliados de cuentas de ahorro, con correo, sin la línea de rendimiento y con una diferencia chica a favor
    del banco que no se ha vuelto a leer con el lector de hoy: [(historial, estimado, cuenta)]."""
    cuentas = [c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all() if producto_de_cuenta(c) != CREDITO]
    if not cuentas:
        return []
    por_id = {c.id: c for c in cuentas}
    hechas = {m.clave for m in db.query(MarcaCron).filter(
        MarcaCron.usuario_id == usuario.id, MarcaCron.valor == rx.VERSION_LECTOR,
        MarcaCron.clave.like(rx.PREFIJO + "%")).all()}
    hist = [h for h in db.query(HistorialExtracto).filter(
        HistorialExtracto.usuario_id == usuario.id, HistorialExtracto.estado == "conciliado",
        HistorialExtracto.cuenta_id.in_(list(por_id))).all()
        if (rx.PREFIJO + h.id) not in hechas and _linea(h) is None]
    if not hist:
        return []
    est = _estimados_por_historial(db, [c for c in cuentas if any(h.cuenta_id == c.id for h in hist)])
    return [(h, est[h.id], por_id[h.cuenta_id]) for h in hist if h.id in est and rx.correo_de(db, h) is not None]


def _plan(db: Session, usuario) -> list[dict]:
    perfil = db.query(Perfil).filter(Perfil.usuario_id == usuario.id).first()
    gmail = bool(perfil and perfil.gmail_conectado and perfil.gmail_refresh_token_enc)
    clave_guardada = db.query(ClavePdf).filter(ClavePdf.usuario_id == usuario.id).first() is not None
    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).all()}
    filas = []
    # A) la línea ya está «por importar» y la lectura cuadra
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario.id,
                                                HistorialExtracto.estado == "pendiente_revision").all():
        cuenta, lin = cuentas.get(h.cuenta_id), _linea(h)
        if cuenta is None or producto_de_cuenta(cuenta) == CREDITO or lin is None:
            continue
        if lin.get("estado") != "faltante" or lin.get("marcar_por_defecto") is False:
            continue
        fila = rx.correo_de(db, h)
        filas.append({"historial_id": h.id, "mes": _mes(h, fila), "cuenta": {"id": cuenta.id, "nombre": cuenta.nombre},
                      "monto": round(float(lin["monto"]), 2), "estimado": False, "releera": False,
                      "puede_releerse": True, "requiere_clave": False, "_h": h, "_orden": _orden(h, fila)})
    # B) conciliados sin la línea, con diferencia chica a favor del banco
    for h, est, cuenta in candidatos_sin_linea(db, usuario):
        fila = rx.correo_de(db, h)
        filas.append({"historial_id": h.id, "mes": _mes(h, fila), "cuenta": {"id": cuenta.id, "nombre": cuenta.nombre},
                      "monto": est, "estimado": True, "releera": True, "puede_releerse": gmail,
                      "requiere_clave": fila.clave_resultado == "fallo" or (fila.estado == "falta_clave" and not clave_guardada),
                      "_h": h, "_orden": _orden(h, fila)})
    filas.sort(key=lambda f: (f["_orden"], f["_h"].creado_en or datetime.min))
    return filas


def previa(db: Session, usuario) -> dict:
    """Vista previa SIN cambios (no toca Gmail): qué extractos, de cuánto y el total."""
    filas = _plan(db, usuario)
    visibles = [{k: v for k, v in f.items() if not k.startswith("_")} for f in filas]
    return {"total": len(filas), "total_pesos": round(sum(f["monto"] for f in filas), 2),
            "aproximado": any(f["estimado"] for f in filas), "maximo_por_llamada": MAXIMO_POR_LLAMADA,
            "extractos": visibles}


def _ajuste_igual(db: Session, usuario_id: str, h: HistorialExtracto, monto: float) -> bool:
    """¿Ya hay un «Ajuste de saldo» de ese valor dentro del periodo del extracto? (Registrar el rendimiento lo duplicaría.)"""
    corte = cx.a_fecha(h.fecha_corte)
    if corte is None:
        return False
    ini = cx.a_fecha(h.periodo_inicio) or corte.replace(day=1)
    q = db.query(Movimiento).filter(
        Movimiento.cuenta_id == h.cuenta_id, Movimiento.fuente == FUENTE_AJUSTE,
        Movimiento.fecha >= datetime.combine(ini, time.min), Movimiento.fecha <= datetime.combine(corte, time.max) + timedelta(days=1),
        Movimiento.monto.between(monto - cx.TOLERANCIA, monto + cx.TOLERANCIA))
    return any((m.notas or "").startswith(cx.PREFIJO_AJUSTE) and delta_saldo(m) > 0 for m in q.all())


def _registrar_uno(db: Session, usuario, f: dict) -> dict:
    from app.routers.conciliacion import importar_faltantes
    from app.schemas import ImportarFaltantesRequest

    h = f["_h"]
    out = {"historial_id": h.id, "mes": f["mes"], "estado": "sin_cambios", "monto": 0.0, "motivo": None, "mensaje_lectura": None}
    if f["releera"]:
        try:
            rx.releer_historial(db, usuario, h, solo_agregar=True)
        except rx.ReleerError as e:
            out.update(estado="saltado", motivo=e.mensaje)
            return out
        db.refresh(h)
    lin = _linea(h)
    out["mensaje_lectura"] = h.mensaje_lectura
    if lin is None:
        out["motivo"] = "Este extracto no trae rendimientos."
        return out
    if lin.get("estado") != "faltante":
        return out  # ya estaba registrada
    if lin.get("marcar_por_defecto") is False:
        out.update(estado="saltado", motivo=lin.get("aviso_linea") or "La lectura no cuadra; la dejé para que la revises.")
        return out
    if _ajuste_igual(db, usuario.id, h, float(lin["monto"])):
        out.update(estado="saltado", motivo="Ya tienes un ajuste de saldo por ese valor en ese mes; bórralo y vuelve a intentarlo.")
        return out
    fp = lin["fingerprint"]
    r = importar_faltantes(h.id, ImportarFaltantesRequest(fingerprints=[fp], categorias={fp: lin.get("categoria_fija") or "Rendimientos"}),
                           db, usuario)
    if r.get("importados"):
        out.update(estado="registrado", monto=round(float(lin["monto"]), 2))
    return out


def registrar(db: Session, usuario, maximo: int = MAXIMO_POR_LLAMADA, excluir=()) -> dict:
    """Registra los rendimientos de hasta `maximo` extractos (del más viejo al más nuevo). Un fallo no detiene al resto."""
    filas = [f for f in _plan(db, usuario) if f["historial_id"] not in set(excluir)]
    maximo = max(1, min(int(maximo or MAXIMO_POR_LLAMADA), MAXIMO_POR_LLAMADA))
    lote, restantes = filas[:maximo], max(0, len(filas) - maximo)
    resultados = []
    for f in lote:
        try:
            r = _registrar_uno(db, usuario, f)
        except HTTPException as e:
            db.rollback()
            r = {"historial_id": f["historial_id"], "mes": f["mes"], "estado": "saltado", "monto": 0.0,
                 "motivo": str(e.detail), "mensaje_lectura": None}
        except Exception as e:  # noqa: BLE001 - un extracto roto no frena a los demás
            db.rollback()
            logger.warning("Registrar rendimientos falló (usuario %s): %s", usuario.id[:8], type(e).__name__)
            r = {"historial_id": f["historial_id"], "mes": f["mes"], "estado": "saltado", "monto": 0.0,
                 "motivo": rx.MSG_FALLA, "mensaje_lectura": None}
        r["cuenta"] = f["cuenta"]
        resultados.append(r)
    hechos = [r for r in resultados if r["estado"] == "registrado"]
    saltados = [r for r in resultados if r["estado"] == "saltado"]
    total = round(sum(r["monto"] for r in hechos), 2)
    return {"ok": True, "registrados": len(hechos), "saltados": len(saltados), "total_pesos": total, "restantes": restantes,
            "resultados": resultados, "resumen": resumen(len(hechos), total, len(saltados), restantes),
            "sin_cambios": not hechos and not saltados}


def resumen(registrados: int, total: float, saltados: int, restantes: int) -> str:
    """«Registré los rendimientos de 8 extractos: $123.456 en total.»"""
    if not registrados and not saltados:
        return "Tus extractos ya tienen sus rendimientos. No cambié nada."
    def n(c, uno, varios):
        return f"{c} {uno if c == 1 else varios}"
    frase = (f"Registré los rendimientos de {n(registrados, 'extracto', 'extractos')}: {cx.pesos(total)} en total"
             if registrados else "No pude registrar ningún rendimiento ahora")
    if saltados:
        frase += f". {n(saltados, 'extracto quedó', 'extractos quedaron')} para después (te digo por qué abajo)"
    if restantes:
        frase += f". Quedan {restantes} por registrar: vuelve a tocar el botón"
    return frase + "."
