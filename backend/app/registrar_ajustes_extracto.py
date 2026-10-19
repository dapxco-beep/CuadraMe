"""«Completar mis extractos: rendimientos e impuestos (N)»: UN paso para los extractos ya importados cuyo resumen trae
rendimientos, impuesto del 4x1000 o costos por retiro que nunca se registraron.

Problema: el extracto de una cuenta de ahorros (Nu, Lulo...) mueve el saldo con «Rendimiento total», «Impuesto del 4x1000»
y «Costos por retiro», pero nada de eso es una línea de movimientos. Los extractos que ya se importaron con el lector viejo
nunca lo registraron, y esos meses no cuadran al peso (rendimientos_extracto.py explica las líneas nuevas). Aquí se
registra de golpe, con vista previa por concepto y un solo «confirmar».

Qué extractos entran (solo cuentas que NO son tarjeta de crédito):
  A) los que ya tienen líneas del resumen «por importar» (la relectura las agregó) y la lectura cuadra: montos exactos.
  B) los conciliados con correo cuyo mes tiene una diferencia chica (menos del 5 % del saldo) con el banco, A FAVOR O EN
     CONTRA: el monto es una estimación (la diferencia neta) y los reales salen al releer el PDF. OJO: un mes en que el
     4x1000 pesa más que los rendimientos descuadra EN CONTRA (el banco registró menos que la app); antes solo se miraban
     las diferencias a favor del banco y esos meses nunca entraban al lote.
  Los subidos a mano (sin correo) no se pueden releer: se saltan. Los de mes que ya cuadra no entran.

Cómo funciona: del más viejo al más nuevo; los B se releen en modo «solo agregar» (releer_extracto, lo ya importado o
completado no se toca) y las líneas se importan con el mismo código de «Importar» (misma huella, mismo saldo, mismo
recálculo del ajuste inicial). Línea por línea: si la lectura no cuadra queda apagada y NO se registra; si ya hay un «Ajuste
de saldo» por el mismo valor y sentido en ese mes, tampoco (se duplicaría): se avisa; si el movimiento ya existía por otro
canal, la regla central lo reconoce («ya estaba») en vez de duplicarlo. Un mes con líneas `completado` recibe las nuevas
sin tocar las completadas. Idempotente (la marca `releer_extracto:<id>` guarda la versión del lector) y sin columnas
nuevas. Máximo 12 por llamada, como «Arreglar mis extractos de la tarjeta»."""
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
from app.rendimientos_extracto import CLAVES, GMF, RENDIMIENTOS, RETIRO, concepto_de_linea, es_linea_de_ajuste

logger = logging.getLogger(__name__)

MAXIMO_POR_LLAMADA = 12
TOPE_RELATIVO = 0.05  # un mes que difiere más del 5 % del saldo no son estos conceptos: es otra cosa
NOMBRE = {RENDIMIENTOS: "rendimientos", GMF: "4x1000", RETIRO: "costos por retiro"}


def _review(h: HistorialExtracto) -> list[dict]:
    try:
        r = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return r if isinstance(r, list) else []


def _lineas(h: HistorialExtracto) -> list[dict]:
    """Las líneas del resumen del extracto (rendimientos, 4x1000, costos por retiro) en cualquier estado."""
    return [i for i in _review(h) if es_linea_de_ajuste(i)]


def _vacios() -> dict[str, float]:
    return {k: 0.0 for k in CLAVES}


def _estimados_por_historial(db: Session, cuentas: list[Cuenta]) -> dict[str, float]:
    """{historial_id: diferencia del mes en valor absoluto} para meses con una diferencia chica, a favor o en contra del banco."""
    out: dict[str, float] = {}
    for c in cuentas:
        try:
            r = ce.calcular(db, c)
        except Exception:  # noqa: BLE001 - una cuenta rara no frena a las demás
            continue
        for f in r["meses"]:
            hid, dif = f.get("historial_id"), f.get("diferencia") or 0.0
            base = max(abs(f.get("banco_final") or 0.0), abs(f.get("banco_inicial") or 0.0))
            if hid and f.get("estado") == "diferencia" and abs(dif) >= cx.TOLERANCIA and abs(dif) <= TOPE_RELATIVO * base:
                out[hid] = round(abs(dif), 2)
    return out


def candidatos_a_completar(db: Session, usuario) -> list[tuple[HistorialExtracto, float, Cuenta]]:
    """Extractos conciliados de cuentas de ahorro, con correo y con una diferencia chica con el banco que no se han vuelto a
    leer con el lector de hoy: [(historial, estimado, cuenta)]. Ya no se exige que falte la línea de rendimiento: un mes con
    rendimientos registrados puede seguir sin su 4x1000."""
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
        if (rx.PREFIJO + h.id) not in hechas]
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
    # A) las líneas ya están «por importar» y la lectura cuadra
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == usuario.id,
                                                HistorialExtracto.estado == "pendiente_revision").all():
        cuenta = cuentas.get(h.cuenta_id)
        if cuenta is None or producto_de_cuenta(cuenta) == CREDITO:
            continue
        listas = [l for l in _lineas(h) if l.get("estado") == "faltante" and l.get("marcar_por_defecto") is not False]
        if not listas:
            continue
        conceptos = _vacios()
        for l in listas:
            conceptos[concepto_de_linea(l)] += round(float(l["monto"]), 2)
        fila = rx.correo_de(db, h)
        filas.append({"historial_id": h.id, "mes": _mes(h, fila), "cuenta": {"id": cuenta.id, "nombre": cuenta.nombre},
                      "monto": round(sum(conceptos.values()), 2), "conceptos": {k: round(v, 2) for k, v in conceptos.items() if v},
                      "estimado": False, "releera": False, "puede_releerse": True, "requiere_clave": False,
                      "_h": h, "_orden": _orden(h, fila)})
    # B) conciliados con una diferencia chica con el banco
    for h, est, cuenta in candidatos_a_completar(db, usuario):
        fila = rx.correo_de(db, h)
        filas.append({"historial_id": h.id, "mes": _mes(h, fila), "cuenta": {"id": cuenta.id, "nombre": cuenta.nombre},
                      "monto": est, "conceptos": None, "estimado": True, "releera": True, "puede_releerse": gmail,
                      "requiere_clave": fila.clave_resultado == "fallo" or (fila.estado == "falta_clave" and not clave_guardada),
                      "_h": h, "_orden": _orden(h, fila)})
    filas.sort(key=lambda f: (f["_orden"], f["_h"].creado_en or datetime.min))
    return filas


def previa(db: Session, usuario) -> dict:
    """Vista previa SIN cambios (no toca Gmail): qué extractos, de cuánto, el total y el total POR CONCEPTO (lo exacto) más
    lo que falta por determinar (estimado hasta releer el PDF)."""
    filas = _plan(db, usuario)
    visibles = [{k: v for k, v in f.items() if not k.startswith("_")} for f in filas]
    por_concepto = _vacios()
    for f in filas:
        for k, v in (f["conceptos"] or {}).items():
            por_concepto[k] += v
    por_determinar = round(sum(f["monto"] for f in filas if f["estimado"]), 2)
    return {"total": len(filas), "total_pesos": round(sum(f["monto"] for f in filas), 2),
            "por_concepto": {k: round(v, 2) for k, v in por_concepto.items()}, "por_determinar": por_determinar,
            "aproximado": any(f["estimado"] for f in filas), "maximo_por_llamada": MAXIMO_POR_LLAMADA,
            "extractos": visibles}


def _ajuste_igual(db: Session, usuario_id: str, h: HistorialExtracto, monto: float, entra: bool) -> bool:
    """¿Ya hay un «Ajuste de saldo» de ese valor y sentido dentro del periodo del extracto? (Registrar la línea lo duplicaría.)"""
    corte = cx.a_fecha(h.fecha_corte)
    if corte is None:
        return False
    ini = cx.a_fecha(h.periodo_inicio) or corte.replace(day=1)
    q = db.query(Movimiento).filter(
        Movimiento.cuenta_id == h.cuenta_id, Movimiento.fuente == FUENTE_AJUSTE,
        Movimiento.fecha >= datetime.combine(ini, time.min), Movimiento.fecha <= datetime.combine(corte, time.max) + timedelta(days=1),
        Movimiento.monto.between(monto - cx.TOLERANCIA, monto + cx.TOLERANCIA))
    return any((m.notas or "").startswith(cx.PREFIJO_AJUSTE) and (delta_saldo(m) > 0) == entra for m in q.all())


def _registrar_uno(db: Session, usuario, f: dict) -> dict:
    from app.routers.conciliacion import importar_faltantes
    from app.schemas import ImportarFaltantesRequest

    h = f["_h"]
    out = {"historial_id": h.id, "mes": f["mes"], "estado": "sin_cambios", "monto": 0.0, "conceptos": {}, "motivo": None,
           "mensaje_lectura": None}
    if f["releera"]:
        try:
            rx.releer_historial(db, usuario, h, solo_agregar=True)
        except rx.ReleerError as e:
            out.update(estado="saltado", motivo=e.mensaje)
            return out
        db.refresh(h)
    lineas = _lineas(h)
    out["mensaje_lectura"] = h.mensaje_lectura
    if not lineas:
        out["motivo"] = "Este extracto no trae rendimientos, 4x1000 ni costos por retiro."
        return out
    pendientes = [l for l in lineas if l.get("estado") == "faltante"]
    if not pendientes:
        return out  # ya estaban registradas
    elegidas, avisos = [], []
    for l in pendientes:
        monto = float(l["monto"])
        nombre = NOMBRE[concepto_de_linea(l)]
        if l.get("marcar_por_defecto") is False:
            avisos.append(l.get("aviso_linea") or f"La lectura de {nombre} no cuadra; la dejé para que la revises.")
        elif _ajuste_igual(db, usuario.id, h, monto, entra=l.get("tipo") == "income"):
            avisos.append(f"Ya tienes un ajuste de saldo por el valor de {nombre} en ese mes; bórralo y vuelve a intentarlo.")
        else:
            elegidas.append(l)
    if elegidas:
        fps = [l["fingerprint"] for l in elegidas]
        importar_faltantes(h.id, ImportarFaltantesRequest(
            fingerprints=fps, categorias={l["fingerprint"]: l.get("categoria_fija") or "Otros" for l in elegidas}), db, usuario)
        db.refresh(h)
        estados = {i.get("fingerprint"): i.get("estado") for i in _review(h) if es_linea_de_ajuste(i)}
        for l in elegidas:
            if estados.get(l["fingerprint"]) == "importado":
                k = concepto_de_linea(l)
                out["conceptos"][k] = round(out["conceptos"].get(k, 0.0) + float(l["monto"]), 2)
            elif estados.get(l["fingerprint"]) == "completado":
                avisos.append(f"Ya tenías un movimiento por el valor de {NOMBRE[concepto_de_linea(l)]}: lo reconocí como el del extracto, sin duplicar.")
    out["monto"] = round(sum(out["conceptos"].values()), 2)
    if out["conceptos"]:
        out["estado"] = "registrado"
    elif avisos:
        out["estado"] = "saltado"
    out["motivo"] = " ".join(avisos) or None
    return out


def registrar(db: Session, usuario, maximo: int = MAXIMO_POR_LLAMADA, excluir=()) -> dict:
    """Completa hasta `maximo` extractos (del más viejo al más nuevo). Un fallo no detiene al resto."""
    filas = [f for f in _plan(db, usuario) if f["historial_id"] not in set(excluir)]
    maximo = max(1, min(int(maximo or MAXIMO_POR_LLAMADA), MAXIMO_POR_LLAMADA))
    lote, restantes = filas[:maximo], max(0, len(filas) - maximo)
    resultados = []
    for f in lote:
        try:
            r = _registrar_uno(db, usuario, f)
        except HTTPException as e:
            db.rollback()
            r = {"historial_id": f["historial_id"], "mes": f["mes"], "estado": "saltado", "monto": 0.0, "conceptos": {},
                 "motivo": str(e.detail), "mensaje_lectura": None}
        except Exception as e:  # noqa: BLE001 - un extracto roto no frena a los demás
            db.rollback()
            logger.warning("Completar extractos falló (usuario %s): %s", usuario.id[:8], type(e).__name__)
            r = {"historial_id": f["historial_id"], "mes": f["mes"], "estado": "saltado", "monto": 0.0, "conceptos": {},
                 "motivo": rx.MSG_FALLA, "mensaje_lectura": None}
        r["cuenta"] = f["cuenta"]
        resultados.append(r)
    hechos = [r for r in resultados if r["estado"] == "registrado"]
    saltados = [r for r in resultados if r["estado"] == "saltado"]
    por_concepto = _vacios()
    for r in hechos:
        for k, v in r["conceptos"].items():
            por_concepto[k] += v
    por_concepto = {k: round(v, 2) for k, v in por_concepto.items()}
    total = round(sum(por_concepto.values()), 2)
    return {"ok": True, "registrados": len(hechos), "saltados": len(saltados), "total_pesos": total, "por_concepto": por_concepto,
            "restantes": restantes, "resultados": resultados,
            "resumen": resumen(len(hechos), por_concepto, len(saltados), restantes),
            "sin_cambios": not hechos and not saltados}


def resumen(registrados: int, por_concepto: dict, saltados: int, restantes: int) -> str:
    """«Completé 8 extractos: $123.456 de rendimientos y $34.000 de 4x1000.»"""
    if not registrados and not saltados:
        return "Tus extractos ya están completos. No cambié nada."

    def n(c, uno, varios):
        return f"{c} {uno if c == 1 else varios}"
    partes = [f"{cx.pesos(por_concepto[k])} de {NOMBRE[k]}" for k in CLAVES if por_concepto.get(k)]
    detalle = (partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]) if partes else cx.pesos(0)
    frase = (f"Completé {n(registrados, 'extracto', 'extractos')}: {detalle}" if registrados
             else "No pude completar ningún extracto ahora")
    if saltados:
        frase += f". {n(saltados, 'extracto quedó', 'extractos quedaron')} para después (te digo por qué abajo)"
    if restantes:
        frase += f". Quedan {restantes} por completar: vuelve a tocar el botón"
    return frase + "."
