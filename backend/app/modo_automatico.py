"""MODO AUTOMÁTICO: la app resuelve sola lo SEGURO para que la persona no apruebe cosas obvias (ni vea un descuadre de centavos).

Un solo interruptor por persona («Modo automático» en Perfil, ACTIVADO por defecto). Apagado, la app se comporta como antes.
Cada fase corre dentro del lote del autoarreglo (`autoarreglo.correr`), así queda en `arreglos_auto` y se puede «Deshacer»:

  unir     «¿Es el mismo gasto?»: junta la línea del extracto con lo ya registrado solo si el monto es idéntico (|Δ|<1),
           hay ≤3 días de diferencia, el emparejamiento es 1:1 y único y es la misma cuenta. Si no, no hace nada.
  correos  Correos bancarios por revisar: los registra solos si el remitente es de un banco (por DOMINIO, no por nombre),
           la cuenta sugerida es única, el monto es >0, no falta cuenta y no es repetido de otro canal. Máx. 20 por día.
  bandeja  «¿Son tuyos?»: confirma lo de Wallet/atajo que ya tiene categoría por regla/comercio conocido, o que lleva 24 h
           sin tocarse con categoría clara. Los montos atípicos y lo sin categoría clara quedan para la persona.
  ajuste   Diferencia mínima (≤ $2.000 o ≤ 0,05 % del saldo) en una cuenta de ahorro, sin líneas pendientes ni otra causa:
           ajuste neutro «Ajuste automático por redondeo/centavos». Nunca para diferencias mayores.

El ajuste se guarda sin migración: es una marca en `marcas_cron` (`modo_automatico_off`); sin marca = activado.
Todo lo dudoso (ambiguo, repetido, remitente raro) se deja como está."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from statistics import median

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import cuadre_extracto as cx
from app import duplicados as dup
from app import pendientes as pend
from app import punto_partida
from app.compartidos import bloquear_cuenta
from app.crons import MarcaCron
from app.models import CorreoGasto, Cuenta, HistorialExtracto, Movimiento
from app.models_autoarreglo import ArregloAuto
from app.utiles import ahora_co
from app.wallet import FUENTES_POR_CONFIRMAR

logger = logging.getLogger(__name__)

CLAVE_APAGADO = "modo_automatico_off"
PREFIJO_NO = "modo_auto_no:"  # lo que la persona deshizo (correo, movimiento o extracto): no se vuelve a hacer solo

TOPE_CORREOS_DIA = 20
HORAS_BANDEJA = 24
DIAS_BANDEJA = 14
DIAS_UNIR = 3
AJUSTE_MAX_COP = 2000.0
AJUSTE_MAX_PCT = 0.0005  # 0,05 % del saldo
NOTA_AJUSTE = "Ajuste automático por redondeo/centavos"
MIN_ATIPICO = 30_000
MULTIPLO_ATIPICO = 3


# ── Interruptor ─────────────────────────────────────────────────────────────────────────────────────
def _fila(db: Session, uid: str, clave: str) -> MarcaCron | None:
    return db.query(MarcaCron).filter(MarcaCron.usuario_id == uid, MarcaCron.clave == clave).first()


def activo(db: Session, uid: str) -> bool:
    """Activado por defecto: solo se apaga con la marca explícita."""
    return _fila(db, uid, CLAVE_APAGADO) is None


def poner_activo(db: Session, uid: str, valor: bool) -> bool:
    fila = _fila(db, uid, CLAVE_APAGADO)
    if valor and fila is not None:
        db.delete(fila)
    elif not valor and fila is None:
        db.add(MarcaCron(usuario_id=uid, clave=CLAVE_APAGADO, valor="1"))
    db.commit()
    return valor


def marcar_no(db: Session, uid: str, entidad_id: str) -> None:
    """Sin commit: la persona deshizo esto; no se vuelve a hacer solo."""
    if entidad_id and _fila(db, uid, PREFIJO_NO + entidad_id) is None:
        db.add(MarcaCron(usuario_id=uid, clave=PREFIJO_NO + entidad_id, valor="1"))
        db.flush()


def _nos(db: Session, uid: str) -> set[str]:
    return {m.clave[len(PREFIJO_NO):] for m in db.query(MarcaCron).filter(
        MarcaCron.usuario_id == uid, MarcaCron.clave.like(PREFIJO_NO + "%")).all()}


def _n(c: int, uno: str, varios: str) -> str:
    return f"{c} {uno if c == 1 else varios}"


# ── 1. «¿Es el mismo gasto?» ────────────────────────────────────────────────────────────────────────
def _dia(v) -> datetime | None:
    from app.conciliacion import parse_bank_date

    return parse_bank_date(v) if v else None


def mismo_gasto_seguro(item: dict, mov: Movimiento | None, aproximados: list[dict], movs_cuenta: list[Movimiento]) -> bool:
    """¿Esta línea «aproximada» ES el movimiento que ya tengo? Solo con monto idéntico, ≤3 días, 1:1 y único."""
    if mov is None or item.get("lectura_dudosa") or mov.conciliado_en is not None:
        return False
    if item.get("tipo") not in ("income", "expense") or item.get("tipo") != mov.tipo:
        return False
    f_item, f_mov = _dia(item.get("fecha")), mov.fecha
    if f_item is None or f_mov is None:
        return False
    monto = float(item.get("monto") or 0)
    if monto < 1 or abs(monto - float(mov.monto or 0)) >= 1:
        return False
    if abs((f_item.date() - f_mov.date()).days) > DIAS_UNIR:
        return False

    def parecida(m: Movimiento) -> bool:  # otro movimiento que también podría ser esta línea
        return (m.id != mov.id and m.tipo == mov.tipo and abs(float(m.monto or 0) - monto) < 1 and m.fecha is not None
                and abs((f_item.date() - m.fecha.date()).days) <= DIAS_UNIR and m.conciliado_en is None)

    if any(parecida(m) for m in movs_cuenta):
        return False  # hay dos candidatos: ambiguo
    mismos = [a for a in aproximados if a.get("match_id") == mov.id]
    if len(mismos) != 1:
        return False  # el mismo movimiento reclamado por dos líneas
    otras = [a for a in aproximados if a is not item and a.get("tipo") == item.get("tipo")
             and abs(float(a.get("monto") or 0) - monto) < 1 and _dia(a.get("fecha")) is not None
             and abs((_dia(a.get("fecha")).date() - f_mov.date()).days) <= DIAS_UNIR]
    return not otras


def fase_unir(ctx) -> int:
    from app.routers.conciliacion import resolver_dudosos
    from app.schemas import ResolverDudososRequest

    db, uid = ctx.db, ctx.uid
    no = _nos(db, uid)
    hechos = 0
    hist = db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == uid, HistorialExtracto.estado == "pendiente_revision").all()
    for h in hist:
        if h.id in ctx.excluidos or h.id in no:
            continue
        try:
            review = json.loads(h.review_json or "[]")
        except ValueError:
            continue
        aprox = [i for i in review if i.get("estado") == "aproximado" and i.get("match_id") and i.get("fingerprint")]
        if not aprox:
            continue
        movs_cuenta = db.query(Movimiento).filter(Movimiento.usuario_id == uid, Movimiento.cuenta_id == h.cuenta_id).all()
        por_id = {m.id: m for m in movs_cuenta}
        seguras = [i["fingerprint"] for i in aprox if mismo_gasto_seguro(i, por_id.get(i["match_id"]), aprox, movs_cuenta)]
        if not seguras:
            continue
        try:
            resolver_dudosos(h.id, ResolverDudososRequest(mismos=seguras, distintos=[]), db, ctx.usuario)
        except HTTPException:
            db.rollback()
            continue
        hechos += len(seguras)
        ctx.unidades += 1
        ctx.cerrar_fase("unir")
    return hechos


# ── 2. Correos bancarios ────────────────────────────────────────────────────────────────────────────
TOPE_MONTO_CORREO = 2_000_000  # por encima, el correo no se registra solo


def _dominio_de_banco(remitente: str) -> bool:
    """El remitente es de un banco por su DOMINIO (no basta el nombre en pantalla: «Bancolombia <x@gmail.com>» es phishing)."""
    from email.utils import parseaddr

    from app import paises
    from app.extractos_gmail import DOMINIOS_BANCOS

    # Solo la dirección REAL del From (el nombre en pantalla puede traer otro «@dominio» para engañar).
    direccion = parseaddr(remitente or "")[1]
    d = direccion.rsplit("@", 1)[1].lower().strip() if direccion.count("@") == 1 else ""
    if not d:
        return False
    bases = list(DOMINIOS_BANCOS) + list(paises.todos_los_dominios())
    return any(d == b or d.endswith("." + b) for b in bases)


def _registrados_hoy(db: Session, uid: str) -> int:
    desde = datetime.utcnow() - timedelta(hours=24)
    return db.query(ArregloAuto).filter(ArregloAuto.usuario_id == uid, ArregloAuto.tipo == "crear_linea", ArregloAuto.creado_en >= desde,
                                        ArregloAuto.despues.like('%"_paso": "correos"%')).count()


def correo_seguro(c: CorreoGasto, cuentas: list, pendientes: list[CorreoGasto]) -> str | None:
    """La cuenta (id) a la que se puede registrar este correo sin preguntar, o None si hay duda."""
    from app.extractos_gmail import es_notificacion_transaccion, inferir_cuenta_por_remitente
    from app.gmail_extract import detectar_tipo, fecha_movimiento_info

    if c.estado != "pendiente" or (c.monto or 0) <= 0 or not _dominio_de_banco(c.remitente or ""):
        return None
    if (c.monto or 0) > TOPE_MONTO_CORREO:
        return None  # un monto grande lo mira la persona (también frena un correo falso con un monto enorme)
    if not es_notificacion_transaccion(c.asunto or "", c.snippet or ""):
        return None
    banco, sugerida, falta = inferir_cuenta_por_remitente(c.remitente, cuentas, f"{c.asunto} {c.snippet}")
    if not banco or falta or not sugerida:
        return None  # varias cuentas posibles o ninguna: pregunta la app
    tipo = c.tipo_sugerido if c.tipo_sugerido in ("income", "expense") else detectar_tipo(f"{c.asunto} {c.snippet}")
    if tipo not in ("income", "expense"):
        return None
    # Dos correos iguales (misma cuenta, monto, tipo y día) pueden ser un aviso repetido: se deja a la persona.
    dia = (fecha_movimiento_info(c)["fecha"] or c.recibido_en or c.creado_en)
    for o in pendientes:
        if o.id == c.id or abs(float(o.monto or 0) - float(c.monto)) >= 1:
            continue
        d2 = fecha_movimiento_info(o)["fecha"] or o.recibido_en or o.creado_en
        if dia and d2 and abs((dia.date() - d2.date()).days) <= 1:
            return None
    return sugerida


def fase_correos(ctx) -> int:
    from app.gmail_extract import fecha_movimiento_info
    from app.routers.correos import aprobar_correo
    from app.schemas import AprobarCorreoRequest

    db, uid = ctx.db, ctx.uid
    cupo = TOPE_CORREOS_DIA - _registrados_hoy(db, uid)
    if cupo <= 0:
        return 0
    dup.absorber_correos(db, uid)  # lo que ya llegó por otro canal pasa a «ya registrado» y no se aprueba dos veces
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == uid).all()
    inicio = punto_partida.fecha_inicio(db, uid)
    no = _nos(db, uid)
    pendientes = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid, CorreoGasto.estado == "pendiente", CorreoGasto.monto > 0).all()
    pendientes.sort(key=lambda c: c.creado_en or datetime.min, reverse=True)
    hechos = 0
    for c in pendientes:
        if hechos >= cupo or ctx.sin_tiempo():
            break
        if c.id in no or punto_partida.es_anterior(fecha_movimiento_info(c)["fecha"], inicio):
            continue
        if _por_pareja_en_otro_canal(db, uid, c, cuentas):
            continue
        cuenta_id = correo_seguro(c, cuentas, pendientes)
        if not cuenta_id:
            continue
        try:
            aprobar_correo(c.id, AprobarCorreoRequest(cuenta_id=cuenta_id), db, ctx.usuario)
            hechos += 1
        except HTTPException:
            db.rollback()
            continue
        ctx.unidades += 1
        ctx.cerrar_fase("correos")
    return hechos


def _por_pareja_en_otro_canal(db: Session, uid: str, c: CorreoGasto, cuentas: list) -> bool:
    """¿Ya hay (o hubo) un movimiento equivalente por otro canal? Mismo criterio que el anti-duplicados."""
    try:
        cand = dup._candidato_de_correo(c, cuentas)
        return bool(cand and dup.buscar_pareja(db, uid, cand, fantasmas=True))
    except Exception:  # noqa: BLE001 - ante la duda, no se registra solo
        return True


def revertir_correo(db: Session, uid: str, movimiento_id: str) -> None:
    """Al deshacer un lote: el correo que originó ese movimiento vuelve a «por revisar» y no se aprueba solo otra vez."""
    c = db.query(CorreoGasto).filter(CorreoGasto.usuario_id == uid, CorreoGasto.movimiento_id == movimiento_id).first()
    if c is not None:
        c.estado, c.movimiento_id = "pendiente", None
        marcar_no(db, uid, c.id)


# ── 3. Bandeja «¿son tuyos?» ────────────────────────────────────────────────────────────────────────
def _ids_atipicos(db: Session, uid: str, movs: list[Movimiento]) -> set[str]:
    """Montos fuera de lo normal: los que marca `cargos_inusuales` y todo gasto grande frente a la mediana de la persona."""
    from app import cargos_inusuales as ci
    from app.informe_datos import cargar_movs_efectivos

    hoy = ahora_co()
    gastos = [m for m in cargar_movs_efectivos(db, uid, hoy - timedelta(days=200), hoy + timedelta(days=1)) if m["tipo"] == "expense"]
    ids = {a.get("movimiento_id") for a in ci.detectar(gastos, hoy)["alertas"] if a.get("movimiento_id")}
    montos = [float(g["monto"]) for g in gastos if g.get("monto")]
    med = median(montos) if montos else 0.0
    for m in movs:
        if m.monto and m.monto >= MIN_ATIPICO and (not med or m.monto > med * MULTIPLO_ATIPICO):
            ids.add(m.id)
    return ids


def fase_bandeja(ctx) -> int:
    db, uid = ctx.db, ctx.uid
    ahora = ahora_co()
    movs = db.query(Movimiento).filter(Movimiento.usuario_id == uid, Movimiento.cat_confirmada.is_(False),
                                       Movimiento.fuente.in_(FUENTES_POR_CONFIRMAR), Movimiento.fecha >= ahora - timedelta(days=DIAS_BANDEJA)).all()
    no = _nos(db, uid)
    movs = [m for m in movs if m.id not in no and m.cuenta_id]
    if not movs:
        return 0
    try:
        atipicos = _ids_atipicos(db, uid, movs)
    except Exception:  # noqa: BLE001 - sin poder medir lo atípico, no se confirma nada solo
        logger.warning("Modo automático: no pude medir montos atípicos (usuario %s)", uid[:8])
        return 0
    silenciados = pend.silencios(db, uid)
    hechos = 0
    for m in movs:
        if m.id in atipicos or pend.es_neutro(m):
            continue
        categoria = (m.categoria or "").strip().lower()
        if m.cat_origen in (pend.ORIGEN_MARCADA, pend.ORIGEN_DEJADA) or categoria in pend.CATEGORIAS_SIN_DEFINIR:
            continue  # sin categoría clara (o la marcó la persona): le toca a ella
        conocido = m.cat_origen in pend.ORIGENES_CONFIANZA_ALTA
        viejo = m.fecha is not None and ahora - m.fecha >= timedelta(hours=HORAS_BANDEJA)
        if not (conocido or viejo):
            continue
        if pend.motivo(m, silenciados) == "marcada":
            continue
        ctx.anotar("confirmar_auto", m.id, {"cat_confirmada": False}, {"cat_confirmada": True, "cuenta_id": m.cuenta_id, "monto": m.monto})
        m.cat_confirmada = True
        hechos += 1
    if hechos:
        db.commit()
        ctx.unidades += 1
    return hechos


def revertir_confirmacion(db: Session, uid: str, movimiento_id: str) -> None:
    m = db.query(Movimiento).filter(Movimiento.id == movimiento_id, Movimiento.usuario_id == uid).first()
    if m is not None:
        m.cat_confirmada = False
        marcar_no(db, uid, m.id)


# ── 4. Ajuste de saldo pequeño ──────────────────────────────────────────────────────────────────────
def diferencia_pequena(dif: float, saldo_banco: float, moneda: str | None) -> bool:
    d = abs(dif)
    if d < cx.TOLERANCIA:
        return False
    if (moneda or "COP") == "COP" and d <= AJUSTE_MAX_COP:
        return True
    return d <= abs(saldo_banco or 0) * AJUSTE_MAX_PCT


def fase_ajuste(ctx) -> int:
    from app.autoarreglo import _review, _verificada
    from app.cuentas_banco import CREDITO, producto_de_cuenta
    from app.routers.cuadre import _pendientes

    db, uid = ctx.db, ctx.uid
    no = _nos(db, uid)
    inicio = punto_partida.fecha_inicio(db, uid)
    hechos = 0
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == uid, Cuenta.tipo == "ahorro").all()
    for cuenta in cuentas:
        if producto_de_cuenta(cuenta) == CREDITO or cuenta.id in no or ctx.sin_tiempo():
            continue
        # Solo el extracto más reciente de la cuenta: los anteriores dependen de él.
        hs = db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == uid, HistorialExtracto.cuenta_id == cuenta.id,
                                                HistorialExtracto.saldo_final_extracto.isnot(None)).all()
        hs = [h for h in hs if cx.a_fecha(h.fecha_corte)]
        if not hs:
            continue
        h = max(hs, key=lambda x: cx.a_fecha(x.fecha_corte))
        if h.id in no or h.id in ctx.excluidos:
            continue
        review = _review(h)
        if _pendientes(h) > 0 or any(i.get("estado") == "aproximado" for i in review) or not _verificada(h, cuenta, review):
            continue
        corte = cx.a_fecha(h.fecha_corte)
        cuenta = bloquear_cuenta(db, cuenta.id)
        ev = cx.evaluar(db, cuenta, saldo_final=h.saldo_final_extracto, fecha_corte=corte, moneda=h.moneda, pendientes=0, inicio_pp=inicio)
        if ev.get("estado") != "diferencia" or ev.get("advertencias"):
            db.rollback()
            continue
        # Cualquier causa con indicios (saldo inicial, repetido, otra fecha, otra cuenta) = no es redondeo: lo ve la persona.
        if any(c.get("probable") or c.get("codigo") == "saldo_inicial" for c in ev["causas"]):
            db.rollback()
            continue
        dif = ev["diferencia"]
        if not diferencia_pequena(dif, h.saldo_final_extracto, cuenta.moneda) or cx.es_ajuste_grande(dif, h.saldo_final_extracto, cuenta.moneda):
            db.rollback()
            continue
        mov = cx.crear_ajuste(db, cuenta, uid, corte, dif)
        mov.notas = f"{cx.PREFIJO_AJUSTE} {cx.fecha_texto(corte)}. {NOTA_AJUSTE}"[:200]
        cx.registrar_cuadre(db, cuenta, h)
        db.commit()
        hechos += 1
        ctx.unidades += 1
        ctx.cerrar_fase("ajuste_pequeno")
    return hechos


# ── Orquestación ────────────────────────────────────────────────────────────────────────────────────
FASES = (("unir", fase_unir), ("correos", fase_correos), ("bandeja", fase_bandeja), ("ajuste", fase_ajuste))


def correr(ctx) -> dict:
    """Las fases, en orden y tolerantes a fallos (una que falla no frena a las demás). `{}` si el modo está apagado."""
    if not activo(ctx.db, ctx.uid):
        return {}
    ctx.foto = ctx_foto(ctx)
    r = {}
    for nombre, f in FASES:
        try:
            r[nombre] = f(ctx)
        except Exception as e:  # noqa: BLE001
            ctx.db.rollback()
            logger.warning("Modo automático: falló %s (usuario %s): %s", nombre, ctx.uid[:8], type(e).__name__)
            r[nombre] = 0
    return r


def ctx_foto(ctx):
    from app.autoarreglo import _foto

    return _foto(ctx.db, ctx.uid)
