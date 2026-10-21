"""AUTOARREGLO: deja las cuentas de cualquier cliente ordenadas SOLAS, de forma segura, visible y reversible.

Orquesta las reparaciones que antes pedían botones y confirmaciones (docs/AUTOARREGLO.md). `correr` ejecuta, en este
orden seguro e idempotente, 6 pasos y devuelve qué hizo cada uno:

  1. errores     reintenta los extractos que fallaron por la clave del PDF (si ya hay clave guardada)
  2. tarjetas    extractos de TARJETA: pasarlos a la cuenta de crédito del mismo banco (solo si hay UNA candidata), releerlos
                 con el lector de hoy, corregir pagos/tipos y quitar repetidos. Solo con lectura VERIFICADA (`lectura_completa`)
  3. ajustes     rendimientos, 4x1000 y costos por retiro que faltan en extractos de ahorro (lo exacto; lo dudoso no)
  4. importar    líneas `faltante` de extractos con lectura verificada y sin dudas; las dudosas quedan para la persona
  5. inicial     recalcula el ajuste inicial por cuenta (la tarjeta, el saldo fijado a mano y el modo «hoy» no se tocan)
  6. cuadre      lee (no cambia nada) por cuenta: «Cuadra todos los meses» o el primer mes que no cuadra, con su causa

NUNCA: toca movimientos manuales, de correo o de atajo; inventa saldos; mueve dinero entre cuentas sin certeza (varias
candidatas = no hace nada y avisa); toca una tarjeta sin lector verificado; importa una línea dudosa.

Seguridad
  · SNAPSHOT: cada cambio (foto de movimientos, extractos y saldos antes y después de cada fase) queda en `arreglos_auto`
    agrupado en un LOTE. `deshacer_lote` lo revierte completo, en orden inverso, con bloqueo de cuenta; si algo posterior lo
    dejó inconsistente responde 409 y no cambia nada.
  · CANDADO por usuario (`marcas_cron`): un lote a la vez; una segunda llamada simultánea no hace nada.
  · Límites: pocas relecturas de Gmail por llamada (`max_pasos`) y por hora; una cuenta grande converge en varias aperturas.
  · Nunca lanza hacia la persona: un paso que falla queda anotado y los demás siguen."""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from hashlib import sha1
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import cierre_extractos, corregir_pago, deuda_tarjeta, corregir_tipo, extractos_error, punto_partida, reasignar_extracto, saldo_inicial_auto
from app import arreglar_tarjetas as at
from app import cuadre_extracto as cx
from app import fechas_extracto as fe
from app import registrar_ajustes_extracto as rae
from app import releer_extracto as rx
from app.compartidos import bloquear_cuenta
from app.contabilidad import delta_saldo
from app.crons import MarcaCron
from app.cuentas_banco import CREDITO, palabras_marca, producto_de_cuenta
from app.limites import verificar_limite
from app.models import ClavePdf, Cuenta, ExtractoCorreo, HistorialExtracto, HuellaOrigen, Movimiento, Perfil
from app.models_autoarreglo import ArregloAuto

logger = logging.getLogger(__name__)

MAX_PASOS_POR_LLAMADA = 3  # unidades de trabajo con Gmail por llamada (igual que la relectura automática)
LIMITE_RELECTURAS_HORA = 24  # relecturas/lecturas de PDF por persona y hora (se suma a los límites propios de cada botón)
LIMITE_LLAMADAS_HORA = 60
PRESUPUESTO_SEGUNDOS = 25.0  # tiempo máximo de una llamada: lo que falte sigue en la próxima
MAX_HISTORIALES_IMPORTAR = 6
TTL_CANDADO = timedelta(minutes=10)
TTL_LOTE = timedelta(hours=6)
PAUSA_TRAS_DESHACER = timedelta(hours=24)
INTERVALO_APP = timedelta(minutes=5)  # la app no repite una corrida completa antes de esto (salvo que haya algo pedido)

CLAVE_CANDADO = "autoarreglo_candado"
CLAVE_LOTE = "autoarreglo_lote"
CLAVE_PAUSA = "autoarreglo_pausa"
CLAVE_PEDIDO = "autoarreglo_pedido"
CLAVE_ULTIMA = "autoarreglo_ultima"
PREFIJO_NO = "autoarreglo_no:"  # extracto que la persona deshizo: no se vuelve a tocar solo
PREFIJO_SV = "autoarreglo_sv:"  # extracto de tarjeta cuya lectura no se pudo verificar con ESTA versión del lector
# Valor de la marca: «<VERSION_LECTOR>|falso|<iso>» (el lector de hoy ya midió que NO suma: no se vuelve a descargar) o
# «<VERSION_LECTOR>|nulo|<iso>» (no se pudo medir: sin Gmail o falla pasajera; se reintenta tras ESPERA_NULO). Una marca
# «<VERSION_LECTOR>» sola (versiones anteriores de este código) cuenta como falso.
ESPERA_NULO = timedelta(hours=6)
RESERVA_PARA_AJUSTES = 1  # de las lecturas de Gmail de una llamada, las tarjetas dejan esta cantidad a los ajustes de ahorros

PASOS = (("errores", "Reintento extractos con error"), ("tarjetas", "Ordeno las tarjetas"),
         ("ajustes", "Registro rendimientos e impuestos"), ("importar", "Importo lo verificado"),
         ("inicial", "Recalculo el saldo inicial y la deuda de tus tarjetas"), ("cuadre", "Reviso que cuadre"))

# Campos del movimiento que se vigilan (antes/después) y se restauran al deshacer.
TRAZADOS = ("cuenta_id", "tipo", "monto", "fecha", "descripcion", "fuente", "categoria", "notas", "subcategoria", "titulo")
# Campos del extracto (historial) que se guardan en `antes` para poder restaurarlo.
HIST_CAMPOS = ("cuenta_id", "estado", "review_json", "lectura_json", "total_movimientos", "exactos", "aproximados", "faltantes",
               "descartados", "importados", "saldo_inicial_extracto", "saldo_final_extracto", "fecha_corte", "periodo_inicio",
               "saldos_origen", "cuadre_estado", "cuadre_diferencia")
TIPOS_MOV = ("mover_cuenta", "corregir_tipo", "corregir_monto", "quitar_repetido", "crear_linea", "ajuste_inicial")
ESTADOS_LINEA_SUMA = ("importado", "exacto", "aproximado", "completado", "faltante", "borrado_antes", "anterior")


# ── Utilidades ───────────────────────────────────────────────────────────────────────────────────
def _ahora() -> datetime:
    return datetime.utcnow()


def _n(c: int, uno: str, varios: str) -> str:
    return f"{c} {uno if c == 1 else varios}"


def _pesos(v: float) -> str:
    return "$" + f"{abs(round(v or 0)):,}".replace(",", ".")


def _json(d) -> str:
    return json.dumps(d, default=str, ensure_ascii=False, sort_keys=True)


def _cargar(texto) -> dict | None:
    try:
        d = json.loads(texto) if texto else None
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def _review(h: HistorialExtracto) -> list[dict]:
    try:
        r = json.loads(h.review_json or "[]")
    except ValueError:
        return []
    return r if isinstance(r, list) else []


def _marca_sv_vigente(valor: str | None) -> bool:
    """¿La marca de «no se pudo verificar» vale para el lector de hoy y todavía no toca reintentar?"""
    partes = (valor or "").split("|")
    if partes[0] != rx.VERSION_LECTOR:
        return False
    if len(partes) >= 3 and partes[1] == "nulo":
        desde = _instante(partes[2])
        return bool(desde and _ahora() - desde < ESPERA_NULO)
    return True


def _valor_sv(verificada: bool | None) -> str:
    return f"{rx.VERSION_LECTOR}|{'falso' if verificada is False else 'nulo'}|{_ahora().isoformat()}"


def _usuario_de(db: Session, uid: str):
    """Quien llama desde el cron no trae sesión: se arma lo mínimo que usan las relecturas (id y nombre del titular)."""
    perfil = db.query(Perfil).filter(Perfil.usuario_id == uid).first()
    nombre = (getattr(perfil, "nombre_titular", None) or getattr(perfil, "nombre_preferido", None) or "") if perfil else ""
    return SimpleNamespace(id=uid, email="", nombre=nombre, nombre_pila="")


# ── Marcas: candado, lote abierto, pausa, extractos excluidos ───────────────────────────────────────
def _marca(db: Session, uid: str, clave: str) -> MarcaCron | None:
    return db.query(MarcaCron).filter(MarcaCron.usuario_id == uid, MarcaCron.clave == clave).first()


def _poner(db: Session, uid: str, clave: str, valor: str) -> None:
    fila = _marca(db, uid, clave)
    try:
        if fila is None:
            db.add(MarcaCron(usuario_id=uid, clave=clave, valor=valor))
        else:
            fila.valor = valor
            fila.actualizado_en = _ahora()
        db.commit()
    except IntegrityError:
        db.rollback()


def _quitar(db: Session, uid: str, clave: str) -> None:
    db.query(MarcaCron).filter(MarcaCron.usuario_id == uid, MarcaCron.clave == clave).delete(synchronize_session=False)
    db.commit()


def _instante(valor: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat((valor or "").split("|")[0])
    except ValueError:
        return None


def tomar_candado(db: Session, uid: str) -> str | None:
    """Un lote por usuario a la vez. Devuelve el token si lo tomó; None si otro proceso ya trabaja (o hay un candado vivo).
    Atómico: la restricción única de `marcas_cron` deja pasar a uno solo; un candado viejo (>10 min, proceso caído) se
    reemplaza con un UPDATE condicionado al valor anterior."""
    token = f"{_ahora().isoformat()}|{uuid.uuid4().hex[:8]}"
    fila = _marca(db, uid, CLAVE_CANDADO)
    try:
        if fila is None:
            db.add(MarcaCron(usuario_id=uid, clave=CLAVE_CANDADO, valor=token))
            db.commit()
            return token
    except IntegrityError:
        db.rollback()
        return None
    desde = _instante(fila.valor)
    if desde is not None and _ahora() - desde < TTL_CANDADO:
        return None
    n = db.query(MarcaCron).filter(MarcaCron.id == fila.id, MarcaCron.valor == fila.valor).update(
        {MarcaCron.valor: token}, synchronize_session=False)
    db.commit()
    return token if n == 1 else None


def soltar_candado(db: Session, uid: str, token: str) -> None:
    try:
        db.rollback()
        db.query(MarcaCron).filter(MarcaCron.usuario_id == uid, MarcaCron.clave == CLAVE_CANDADO,
                                   MarcaCron.valor == token).delete(synchronize_session=False)
        db.commit()
    except Exception:  # noqa: BLE001 - el candado vencido se limpia solo
        db.rollback()


def _lote_abierto(db: Session, uid: str) -> str:
    """El lote en curso (varias llamadas seguidas hasta terminar) o uno nuevo."""
    fila = _marca(db, uid, CLAVE_LOTE)
    if fila is not None:
        desde = _instante(fila.valor)
        if desde is not None and _ahora() - desde < TTL_LOTE:
            return fila.valor.split("|")[1]
    lote = uuid.uuid4().hex
    _poner(db, uid, CLAVE_LOTE, f"{_ahora().isoformat()}|{lote}")
    return lote


def pausado(db: Session, uid: str) -> bool:
    fila = _marca(db, uid, CLAVE_PAUSA)
    hasta = _instante(fila.valor) if fila else None
    return bool(hasta and hasta > _ahora())


def pedir(db: Session, uid: str) -> None:
    """«Algo cambió» (se subió o releyó un extracto): la próxima apertura corre aunque la última corrida sea reciente.
    Barato y nunca lanza."""
    try:
        _poner(db, uid, CLAVE_PEDIDO, _ahora().isoformat())
    except Exception:  # noqa: BLE001
        db.rollback()


def excluidos(db: Session, uid: str) -> set[str]:
    return {m.clave[len(PREFIJO_NO):] for m in db.query(MarcaCron).filter(
        MarcaCron.usuario_id == uid, MarcaCron.clave.like(PREFIJO_NO + "%")).all()}


# ── Foto (snapshot) y diferencias ─────────────────────────────────────────────────────────────────
def _valor(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, float):
        return round(v, 2)
    return v


def _foto(db: Session, uid: str) -> dict:
    """Estado de los movimientos propios, los extractos y los saldos. Lectura directa de columnas (rápida con miles de filas)."""
    tm = Movimiento.__table__
    movs = {r["id"]: {k: _valor(v) for k, v in dict(r).items()}
            for r in db.execute(tm.select().where(tm.c.usuario_id == uid)).mappings()}
    th = HistorialExtracto.__table__
    hist = {r["id"]: {k: _valor(r[k]) for k in HIST_CAMPOS}
            for r in db.execute(th.select().where(th.c.usuario_id == uid)).mappings()}
    cuentas = {c.id: round(float(c.saldo or 0), 2) for c in db.query(Cuenta).filter(Cuenta.usuario_id == uid).all()}
    return {"movs": movs, "hist": hist, "cuentas": cuentas}


def _traz(m: dict) -> dict:
    return {k: m.get(k) for k in TRAZADOS}


def _huella_hist(h: dict, con_saldos: bool = True) -> str:
    """Lo que se vigila de un extracto: cuenta, estado, revisión y (nuevo) sus fechas y la marca de duplicado."""
    dup = (_cargar(h.get("lectura_json")) or {}).get(fe.CLAVE_DUPLICADO)
    # Las anclas de deuda (saldos del extracto de una TARJETA) también se vigilan, para poder deshacerlas. `con_saldos=False`
    # es la fórmula de los lotes anteriores (sus huellas no las llevan).
    saldos = (f"|{h.get('saldo_inicial_extracto')}|{h.get('saldo_final_extracto')}"
              if con_saldos and "resumen_tarjeta" in (h.get("lectura_json") or "") else "")
    return sha1(f"{h.get('cuenta_id')}|{h.get('estado')}|{h.get('review_json')}"
                f"|{h.get('fecha_corte')}|{h.get('periodo_inicio')}|{dup}{saldos}".encode()).hexdigest()


def _diferencias(a: dict, b: dict, paso: str) -> list[dict]:
    """Filas de `arreglos_auto` (sin id ni lote) que llevan la foto `a` a la foto `b`."""
    filas = []

    def fila(tipo, entidad, antes, despues):
        filas.append({"tipo": tipo, "entidad_id": entidad,
                      "antes": None if antes is None else {**antes, "_paso": paso},
                      "despues": None if despues is None else {**despues, "_paso": paso}})

    for mid, nuevo in b["movs"].items():
        if mid not in a["movs"]:
            tipo = "ajuste_inicial" if saldo_inicial_auto.es_automatico(nuevo) else "crear_linea"
            fila(tipo, mid, None, _traz(nuevo))
    for mid, viejo in a["movs"].items():
        nuevo = b["movs"].get(mid)
        if nuevo is None:
            tipo = "ajuste_inicial" if saldo_inicial_auto.es_automatico(viejo) else "quitar_repetido"
            fila(tipo, mid, dict(viejo), None)  # el registro completo: así se puede volver a crear
        elif _traz(viejo) != _traz(nuevo):
            if saldo_inicial_auto.es_automatico(viejo) or saldo_inicial_auto.es_automatico(nuevo):
                tipo = "ajuste_inicial"
            elif viejo["cuenta_id"] != nuevo["cuenta_id"]:
                tipo = "mover_cuenta"
            elif viejo["tipo"] != nuevo["tipo"]:
                tipo = "corregir_tipo"
            elif viejo["monto"] != nuevo["monto"]:
                tipo = "corregir_monto"
            else:
                tipo = "corregir_monto" if viejo["descripcion"] != nuevo["descripcion"] else "ajuste_inicial"
            fila(tipo, mid, _traz(viejo), _traz(nuevo))
    for hid, nuevo in b["hist"].items():
        viejo = a["hist"].get(hid)
        if viejo is not None and _huella_hist(viejo) != _huella_hist(nuevo):
            fila("historial", hid, viejo, {"cuenta_id": nuevo["cuenta_id"], "estado": nuevo["estado"], "huella": _huella_hist(nuevo),
                                           "fecha_corte": nuevo["fecha_corte"], "periodo_inicio": nuevo["periodo_inicio"],
                                           "lectura_json": nuevo["lectura_json"]})
    for cid, saldo in b["cuentas"].items():
        if cid in a["cuentas"] and abs(a["cuentas"][cid] - saldo) >= 0.005:
            fila("saldo", cid, {"saldo": a["cuentas"][cid]}, {"saldo": saldo})
    return filas


# ── Contexto de una corrida ────────────────────────────────────────────────────────────────────────
class _Ctx:
    def __init__(self, db: Session, usuario, lote: str, max_pasos: int):
        self.db, self.usuario, self.uid, self.lote = db, usuario, usuario.id, lote
        self.presupuesto = max(0, int(max_pasos))
        self.inicio = time.monotonic()
        self.unidades = 0  # trabajo hecho en esta llamada (si es 0 no tiene sentido volver a llamar ya)
        self.limite_alcanzado = False
        self.excluidos = excluidos(db, usuario.id)
        # Lo que no se pudo verificar no se vuelve a descargar hasta que el lector mejore (si no, gastaría cada vez la relectura).
        self.sin_verificar = {m.clave[len(PREFIJO_SV):] for m in db.query(MarcaCron).filter(
            MarcaCron.usuario_id == usuario.id, MarcaCron.clave.like(PREFIJO_SV + "%"),
            MarcaCron.valor.like(rx.VERSION_LECTOR + "%")).all() if _marca_sv_vigente(m.valor)}
        self.foto = _foto(db, usuario.id)
        self.reloj = _ahora()
        self.cambios = 0
        self.decisiones: dict[str, int] = {}
        self.notas: list[str] = []

    def sin_tiempo(self) -> bool:
        return time.monotonic() - self.inicio > PRESUPUESTO_SEGUNDOS

    def reservar(self, n: int = 1, *, dejar: int = 0) -> int:
        """Pide `n` relecturas de Gmail: respeta lo que queda de esta llamada y el tope por hora. `dejar`: cuántas dejar a los
        pasos que vienen (así un paso con muchas lecturas no deja sin nada a los demás). Devuelve cuántas dio."""
        dadas = 0
        while dadas < min(n, self.presupuesto - dejar) and not self.sin_tiempo():
            try:
                verificar_limite(f"autoarreglo-relectura:{self.uid}", LIMITE_RELECTURAS_HORA, 3600)
            except HTTPException:
                self.limite_alcanzado = True
                break
            dadas += 1
        self.presupuesto -= dadas
        return dadas

    def decidir(self, clave: str, n: int = 1) -> None:
        self.decisiones[clave] = self.decisiones.get(clave, 0) + n

    def cerrar_fase(self, paso: str) -> int:
        """Compara con la foto anterior, guarda las diferencias en el lote y avanza la foto. Devuelve cuántas filas."""
        db = self.db
        nueva = _foto(db, self.uid)
        filas = _diferencias(self.foto, nueva, paso)
        self.foto = nueva
        if not filas:
            return 0
        for f in filas:
            self.reloj = max(_ahora(), self.reloj + timedelta(microseconds=1))
            db.add(ArregloAuto(usuario_id=self.uid, lote_id=self.lote, tipo=f["tipo"], entidad_id=f["entidad_id"],
                               antes=_json(f["antes"]) if f["antes"] is not None else None,
                               despues=_json(f["despues"]) if f["despues"] is not None else None, creado_en=self.reloj))
        db.commit()
        self.cambios += len([f for f in filas if f["tipo"] != "saldo"])
        return len(filas)


# ── Lectura verificada ─────────────────────────────────────────────────────────────────────────────
def _lectura_del_pdf(db: Session, usuario, h: HistorialExtracto) -> bool | None:
    """Baja el PDF del correo y mide SIN escribir nada si la lectura de la tarjeta suma lo que dice el extracto.
    True / False; None si no se puede saber (no es un lector verificado, no hay Gmail, falló la descarga)."""
    from app.routers import correos as rc

    try:
        fila = rx.correo_de(db, h)
        perfil = rc._get_or_create_perfil(db, usuario.id)
        if fila is None or not perfil.gmail_conectado or not perfil.gmail_refresh_token_enc:
            return None
        gmail = rc.cliente_gmail(perfil.gmail_refresh_token_enc)
        msg = gmail.users().messages().get(userId="me", id=fila.gmail_msg_id, format="full").execute()
        pdfs = rx.listar_adjuntos_pdf(msg)
        adj = next((a for a in pdfs if a["archivo"] == fila.archivo), None) or (pdfs[0] if len(pdfs) == 1 else None)
        if adj is None:
            return None
        pdf = rx.descargar_adjunto(gmail, fila.gmail_msg_id, adj["attachment_id"])
        estado, texto, _ = rx.abrir_pdf(pdf, rx.claves_candidatas(rc._clave_pdf(db, usuario.id)))
        if estado != "ok" or not rx.es_extracto_tarjeta_nu(texto):
            return None
        return bool(rx.datos_de_lectura(rx.leer_extracto_tarjeta_nu(texto))["lectura_completa"])
    except Exception as e:  # noqa: BLE001 - sin red o PDF raro: no se verifica y no se toca
        db.rollback()
        logger.warning("Autoarreglo: no pude verificar la lectura (usuario %s): %s", usuario.id[:8], type(e).__name__)
        return None


def _suma_cuadra(h: HistorialExtracto, review: list[dict]) -> bool:
    """Para extractos que no son de tarjeta: las líneas leídas explican el cambio de saldo que dice el extracto."""
    if h.saldo_inicial_extracto is None or h.saldo_final_extracto is None:
        return False
    neto = 0.0
    for i in review:
        if i.get("estado") == "sobrante":
            continue
        if i.get("estado") not in ESTADOS_LINEA_SUMA or i.get("tipo") not in ("income", "expense"):
            return False  # un estado raro o una línea sin dirección: no se puede dar por verificada
        neto += float(i.get("monto") or 0) * (1 if i.get("tipo") == "income" else -1)
    return abs(float(h.saldo_final_extracto) - float(h.saldo_inicial_extracto) - neto) <= cx.TOLERANCIA


def _verificada(h: HistorialExtracto, cuenta: Cuenta | None, review: list[dict]) -> bool:
    lc = h.lectura_completa
    if lc is True:
        return True
    if lc is False or cuenta is None or producto_de_cuenta(cuenta) == CREDITO:
        return False
    return _suma_cuadra(h, review)


# ── Paso 1: extractos con error por la clave ─────────────────────────────────────────────────────────
def _paso_errores(ctx: _Ctx) -> dict:
    db, uid = ctx.db, ctx.uid
    errores = db.query(HistorialExtracto).filter(
        HistorialExtracto.usuario_id == uid, HistorialExtracto.estado == "error",
        HistorialExtracto.motivo_error.in_(extractos_error.MOTIVOS_CLAVE)).count()
    hay_clave = db.query(ClavePdf.usuario_id).filter(ClavePdf.usuario_id == uid).first() is not None
    sin_clave = db.query(ExtractoCorreo.id).filter(ExtractoCorreo.usuario_id == uid, ExtractoCorreo.estado == "falta_clave").count()
    if not hay_clave:
        if errores or sin_clave:
            ctx.decidir("clave_pdf", max(errores, sin_clave))
        return {"hecho": 0, "quedan": 0}
    if not errores:
        return {"hecho": 0, "quedan": 0}
    dadas = ctx.reservar(MAX_PASOS_POR_LLAMADA)
    if not dadas:
        return {"hecho": 0, "quedan": errores}
    r = extractos_error.reintentar_errores_clave(db, ctx.usuario, maximo=dadas)
    ctx.presupuesto += max(0, dadas - r["reintentados"])  # lo que no usó se devuelve: si no, deja sin lecturas a las tarjetas
    ctx.unidades += r["reintentados"]
    ctx.cerrar_fase("errores")
    return {"hecho": r["leidos"], "reintentados": r["reintentados"], "quedan": r["pendientes"]}


# ── Paso 2: tarjetas ─────────────────────────────────────────────────────────────────────────────────
def _tarjetas_ambiguas(db: Session, uid: str) -> int:
    """Extractos de tarjeta que están en una cuenta de ahorros y tienen VARIAS tarjetas candidatas del mismo banco:
    no se mueven solos."""
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == uid).all()
    n = 0
    for h in db.query(HistorialExtracto).filter(HistorialExtracto.usuario_id == uid, HistorialExtracto.estado != "error").all():
        cuenta = next((c for c in cuentas if c.id == h.cuenta_id), None)
        if cuenta is None or producto_de_cuenta(cuenta) == CREDITO or h.id in excluidos(db, uid):
            continue
        fila = rx.correo_de(db, h)
        if fila is None or not rx.es_de_tarjeta(h, cuenta, fila):
            continue
        if at._destino(h, cuenta, cuentas, fila) is not None:
            continue
        marca = palabras_marca(cuenta.nombre)
        candidatas = [c for c in cuentas if c.id != cuenta.id and producto_de_cuenta(c) == CREDITO and marca & palabras_marca(c.nombre)]
        if len(candidatas) >= 2:
            n += 1
    return n


def _aplicar_correcciones_de_pago(db: Session, usuario, h: HistorialExtracto) -> None:
    """`corregir_monto` y `quitar_repetido` (pago que el lector viejo leyó con otro monto): se aplican con el mismo código
    de «Importar»; no crean nada nuevo."""
    from app.routers.conciliacion import importar_faltantes
    from app.schemas import ImportarFaltantesRequest

    fps = [i["fingerprint"] for i in _review(h) if i.get("fingerprint") and (
        i.get("estado") == corregir_pago.CORREGIR or (i.get("estado") == corregir_pago.QUITAR and i.get("quita_por") != "tipo"))]
    if fps:
        importar_faltantes(h.id, ImportarFaltantesRequest(fingerprints=fps), db, usuario)
        db.refresh(h)


def _tarjeta_uno(ctx: _Ctx, f: dict, verificada: bool | None) -> dict:
    db, usuario, h = ctx.db, ctx.usuario, f["_h"]
    out = {"historial_id": h.id, "mes": f["mes"], "movido": False, "nuevas": 0, "corregidos": 0, "pagos": 0, "quitados": 0, "estado": "ok"}
    try:
        if f["_destino_obj"] is not None:
            reasignar_extracto.cambiar(db, usuario.id, h.id, f["_destino_obj"].id)
            db.refresh(h)
            out["movido"] = ctx.cerrar_fase("tarjetas") > 0
        if f["releera"]:
            r = rx.releer_historial(db, usuario, h, solo_agregar=True)
            out["nuevas"] = r.get("por_importar", 0)
            db.refresh(h)
            ctx.cerrar_fase("tarjetas")
        t = corregir_tipo.aplicar_en_historial(db, usuario, h)
        out["corregidos"], out["quitados"] = t["corregidos"], t["quitados"]
        if t["corregidos"] or t["quitados"]:
            db.refresh(h)
            ctx.cerrar_fase("tarjetas")
        _aplicar_correcciones_de_pago(db, usuario, h)
        out["pagos"] = ctx.cerrar_fase("tarjetas")
    except rx.ReleerError as e:
        db.rollback()
        out.update(estado="saltado", motivo=e.mensaje)
        ctx.cerrar_fase("tarjetas")
    except Exception as e:  # noqa: BLE001 - un extracto roto no frena a los demás; lo ya hecho queda en el lote
        db.rollback()
        logger.warning("Autoarreglo tarjetas falló (usuario %s): %s", usuario.id[:8], type(e).__name__)
        out.update(estado="saltado", motivo=rx.MSG_FALLA)
        try:
            ctx.cerrar_fase("tarjetas")
        except Exception:  # noqa: BLE001
            db.rollback()
    return out


def _reparar_fechas(ctx: _Ctx) -> dict:
    """Fechas de los extractos (docs/FECHAS_DE_EXTRACTOS.md): completa/corrige corte y periodo de las tarjetas con lo que ya
    se leyó (o, si no hay lectura, con la fecha del correo marcada como estimada) y aparta los extractos subidos dos veces.
    No descarga nada, no toca movimientos ni saldos. Lo dudoso de verdad (corte en el futuro, periodos cruzados) no se toca:
    queda como decisión de la persona."""
    db = ctx.db
    r = fe.reparar(db, ctx.uid, excluir=ctx.excluidos)  # un extracto que la persona deshizo no se vuelve a tocar solo
    if r["fechas"] or r["duplicados"]:
        db.commit()
        ctx.cerrar_fase("tarjetas")
    dudosas = fe.revisar_fechas(db, ctx.uid)
    ctx.decidir("fechas_dudosas", len(set(dudosas["futuras"]) | set(dudosas["traslapados"]) | set(dudosas["sin_fechas"])))
    return {"fechas": len(r["fechas"]), "duplicados": len(r["duplicados"])}


def _paso_tarjetas(ctx: _Ctx) -> dict:
    db = ctx.db
    reparadas = _reparar_fechas(ctx)
    ambiguas = _tarjetas_ambiguas(db, ctx.uid)
    if ambiguas:
        ctx.decidir("varias_tarjetas", ambiguas)
    plan = at._plan(db, ctx.usuario)
    filas = [f for f in plan["filas"] if f["historial_id"] not in ctx.excluidos]
    hechos, quedan, saltados = [], 0, 0
    dejar = RESERVA_PARA_AJUSTES if ctx.presupuesto > RESERVA_PARA_AJUSTES else 0  # fijo para todo el paso
    for k, f in enumerate(filas):
        h = f["_h"]
        sin_trabajo = f["_destino_obj"] is None and not f["releera"] and not f.get("propuestas_tipo")
        if sin_trabajo:
            continue
        if h.id in ctx.sin_verificar and h.lectura_completa is not True:
            ctx.decidir("tarjeta_sin_verificar")
            continue
        if f["requiere_clave"]:
            ctx.decidir("clave_pdf")
            continue
        if ctx.sin_tiempo():
            quedan = len(filas) - k
            break
        verificada = h.lectura_completa
        if verificada is False and f["releera"]:
            verificada = None  # lo midió un lector anterior: se vuelve a medir UNA vez con el de hoy (luego queda en caché)
        necesita_gmail = f["releera"] or verificada is None
        gasto = False
        if necesita_gmail:
            if not f["puede_releerse"]:
                continue
            if not ctx.reservar(1, dejar=dejar):
                quedan += 1  # sin lecturas por ahora (se guardan para los ajustes): sigue con los que no las necesitan
                continue
            gasto = True
            if verificada is None:
                verificada = _lectura_del_pdf(db, ctx.usuario, h)
        if verificada is not True:
            ctx.decidir("tarjeta_sin_verificar")  # nunca se toca una tarjeta sin lector verificado; NO frena a las demás
            _poner(db, ctx.uid, PREFIJO_SV + h.id, _valor_sv(verificada))
            if gasto:
                ctx.unidades += 1  # gastó una lectura: la llamada sí avanzó
            saltados += 1
            continue
        ctx.unidades += 1
        hechos.append(_tarjeta_uno(ctx, f, verificada))
    return {"hecho": len(hechos), "quedan": quedan, "saltados": saltados, "extractos": hechos, "fechas": reparadas}


# ── Paso 3: rendimientos, 4x1000 y costos por retiro ───────────────────────────────────────────────────
def _paso_ajustes(ctx: _Ctx) -> dict:
    db = ctx.db
    filas = [f for f in rae._plan(db, ctx.usuario) if f["historial_id"] not in ctx.excluidos]
    hechos, quedan = [], 0
    for k, f in enumerate(filas):
        if f["requiere_clave"]:
            ctx.decidir("clave_pdf")
            continue
        if ctx.sin_tiempo():
            quedan = len(filas) - k
            break
        if f["releera"]:
            if not f["puede_releerse"]:
                continue
            if not ctx.reservar(1):
                quedan = len(filas) - k
                break
        ctx.unidades += 1
        try:
            r = rae._registrar_uno(db, ctx.usuario, f)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.warning("Autoarreglo ajustes falló (usuario %s): %s", ctx.uid[:8], type(e).__name__)
            r = {"historial_id": f["historial_id"], "estado": "saltado", "conceptos": {}, "motivo": rx.MSG_FALLA}
        ctx.cerrar_fase("ajustes")
        hechos.append({"historial_id": f["historial_id"], "estado": r["estado"], "conceptos": r.get("conceptos") or {}})
    return {"hecho": len([h for h in hechos if h["estado"] == "registrado"]), "quedan": quedan, "extractos": hechos}


# ── Paso 4: líneas verificadas ───────────────────────────────────────────────────────────────────────────
def _elegible(item: dict, inicio) -> bool:
    """Una línea `faltante` que se puede importar sin preguntar: lectura sin dudas y con dirección clara."""
    from app.conciliacion import parse_bank_date

    if item.get("estado") != "faltante" or item.get("lectura_dudosa") or item.get("marcar_por_defecto") is False:
        return False
    # El pago a una tarjeta con su desglose (capital/intereses/cargos) sí entra: la lectura de la tarjeta ya está verificada
    # (_verificada) y el pago es el que sale de otra cuenta tuya; sin él la deuda del corte no cuadra.
    if (item.get("pago_detalle") and not item.get("pago_tarjeta")) or item.get("aviso_linea") or item.get("tipo") not in ("income", "expense"):
        return False
    if not (float(item.get("monto") or 0) >= 1) or not item.get("fingerprint"):
        return False
    return not punto_partida.es_anterior(parse_bank_date(item.get("fecha")), inicio)  # modo «hoy»: lo anterior no entra


def _paso_importar(ctx: _Ctx) -> dict:
    from app.routers.conciliacion import importar_faltantes
    from app.schemas import ImportarFaltantesRequest

    db = ctx.db
    inicio = punto_partida.fecha_inicio(db, ctx.uid)
    cuentas = {c.id: c for c in db.query(Cuenta).filter(Cuenta.usuario_id == ctx.uid).all()}
    hist = db.query(HistorialExtracto).filter(
        HistorialExtracto.usuario_id == ctx.uid, HistorialExtracto.estado == "pendiente_revision").order_by(HistorialExtracto.creado_en).all()
    trabajo, por_decidir = [], 0
    for h in hist:
        review = _review(h)
        faltantes = [i for i in review if i.get("estado") == "faltante"]
        if not faltantes:
            continue
        if h.id in ctx.excluidos or any(i.get("estado") in corregir_pago.ESTADOS_CORRECCION for i in review):
            por_decidir += len(faltantes)  # una corrección sin aplicar es decisión de la persona
            continue
        if not _verificada(h, cuentas.get(h.cuenta_id), review):
            por_decidir += len(faltantes)
            continue
        elegibles = [i for i in faltantes if _elegible(i, inicio)]
        por_decidir += len(faltantes) - len(elegibles)
        if elegibles:
            trabajo.append((h, elegibles))
    importadas, hechos = 0, 0
    for k, (h, elegibles) in enumerate(trabajo):
        if k >= MAX_HISTORIALES_IMPORTAR or ctx.sin_tiempo():
            return _cerrar_importar(ctx, hechos, importadas, len(trabajo) - k, por_decidir)
        try:
            r = importar_faltantes(h.id, ImportarFaltantesRequest(
                fingerprints=[i["fingerprint"] for i in elegibles],
                categorias={i["fingerprint"]: i["categoria_fija"] for i in elegibles if i.get("categoria_fija")}), db, ctx.usuario)
            importadas += r.get("importados", 0)
            hechos += 1
            ctx.unidades += 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.warning("Autoarreglo importar falló (usuario %s): %s", ctx.uid[:8], type(e).__name__)
        ctx.cerrar_fase("importar")
    return _cerrar_importar(ctx, hechos, importadas, 0, por_decidir)


def _cerrar_importar(ctx: _Ctx, hechos: int, importadas: int, quedan: int, por_decidir: int) -> dict:
    if por_decidir:
        ctx.decidir("dudosas", por_decidir)
    return {"hecho": hechos, "importadas": importadas, "quedan": quedan}


# ── Paso 5 y 6: ajuste inicial y cuadre ──────────────────────────────────────────────────────────────────────
def _paso_inicial(ctx: _Ctx) -> dict:
    """Ajuste inicial de cada cuenta. En las TARJETAS (deuda, no saldo): 1) las anclas de deuda de cada extracto (lo que se
    debía al corte, leído del resumen) y 2) la «Deuda inicial» derivada del extracto más antiguo, solo con lectura verificada."""
    db = ctx.db
    tarjetas = db.query(Cuenta).filter(Cuenta.usuario_id == ctx.uid, Cuenta.tipo == "credito").all()
    ancladas = 0
    for c in tarjetas:
        ancladas += len(deuda_tarjeta.anclar_cuenta(db, c))
    if ancladas:
        db.commit()
        ctx.cerrar_fase("inicial")
    r = saldo_inicial_auto.registrar_todas(db, ctx.uid, punto_partida.fecha_inicio(db, ctx.uid))
    ctx.cerrar_fase("inicial")
    inicio_pp = punto_partida.fecha_inicio(db, ctx.uid)
    for c in tarjetas:  # sin el primer extracto leído completo no se inventa: se dice qué falta
        db.refresh(c)
        _, _, filas = cx._serie(db, c.id)
        o = deuda_tarjeta.objetivo_deuda_inicial(db, c, filas, saldo_inicial_auto.es_automatico)
        if o["estado"] == "incompleto" and not any(saldo_inicial_auto.es_automatico(f) for f in filas) \
                and not punto_partida.es_anterior(o["inicio"], inicio_pp):
            ctx.decidir("deuda_inicial_sin_lectura")
    return {"hecho": len(r) + ancladas, "anclas": ancladas, "quedan": 0}


def _paso_cuadre(ctx: _Ctx) -> dict:
    ctx.cuadre = cierre_extractos.cuadre_por_cuenta(ctx.db, ctx.uid)
    return {"hecho": 0, "quedan": 0}


_EJECUTORES = {"errores": _paso_errores, "tarjetas": _paso_tarjetas, "ajustes": _paso_ajustes,
               "importar": _paso_importar, "inicial": _paso_inicial, "cuadre": _paso_cuadre}

DECISIONES = {
    "dudosas": ("Hay movimientos de tus extractos que no importé porque no estoy seguro.", "Revisarlos", "/sincronizacion"),
    "varias_tarjetas": ("Tienes varias tarjetas del mismo banco y no sé a cuál va cada extracto.", "Elegir la tarjeta", "/sincronizacion"),
    "clave_pdf": ("Me falta la clave de tus extractos en PDF para leerlos.", "Poner la clave", "/correos"),
    "fechas_dudosas": ("Hay extractos con fechas que no cuadran (un corte que aún no llega, periodos que se cruzan o sin fecha); no las cambié.",
                       "Revisarlos", "/sincronizacion"),
    "deuda_inicial_sin_lectura": ("Aún no puedo calcular con cuánto empezó tu tarjeta: faltan líneas de tu primer extracto.",
                                  "Verlos", "/sincronizacion"),
    "tarjeta_sin_verificar": ("Hay extractos de tarjeta que no pude comprobar contra el resumen del banco; no los toqué.",
                              "Verlos", "/sincronizacion"),
}


def _decisiones(ctx_dec: dict[str, int]) -> list[dict]:
    salida = []
    for clave, (texto, accion, ruta) in DECISIONES.items():
        n = ctx_dec.get(clave, 0)
        if n:
            salida.append({"tipo": clave, "cantidad": n, "texto": texto, "accion": accion, "ruta": ruta})
    return salida


# ── Resumen del lote ───────────────────────────────────────────────────────────────────────────────────────
def _filas_del_lote(db: Session, uid: str, lote: str) -> list[ArregloAuto]:
    return (db.query(ArregloAuto).filter(ArregloAuto.usuario_id == uid, ArregloAuto.lote_id == lote)
            .order_by(ArregloAuto.creado_en, ArregloAuto.id).all())


def resumen_lote(db: Session, uid: str, lote: str) -> dict:
    filas = _filas_del_lote(db, uid, lote)
    c = {"extractos_movidos": 0, "compras_corregidas": 0, "pagos_corregidos": 0, "repetidos_quitados": 0,
         "rendimientos_registrados": 0, "monto_rendimientos": 0.0, "lineas_importadas": 0, "ajustes_iniciales": 0,
         "extractos_releidos": 0, "fechas_arregladas": 0, "duplicados_marcados": 0}
    saldos: dict[str, dict] = {}
    detalle = []
    for f in filas:
        antes, despues = _cargar(f.antes) or {}, _cargar(f.despues) or {}
        if f.tipo == "historial":
            marca_antes = (_cargar(antes.get("lectura_json")) or {}).get(fe.CLAVE_DUPLICADO)
            marca_despues = (_cargar(despues.get("lectura_json")) or {}).get(fe.CLAVE_DUPLICADO)
            if antes.get("cuenta_id") != despues.get("cuenta_id"):
                c["extractos_movidos"] += 1
            elif marca_despues and not marca_antes:
                c["duplicados_marcados"] += 1
            elif (antes.get("fecha_corte"), antes.get("periodo_inicio")) != (despues.get("fecha_corte"), despues.get("periodo_inicio")):
                c["fechas_arregladas"] += 1
            else:
                c["extractos_releidos"] += 1
        elif f.tipo == "corregir_tipo":
            c["compras_corregidas"] += 1
        elif f.tipo == "corregir_monto":
            c["pagos_corregidos"] += 1
        elif f.tipo == "quitar_repetido":
            c["repetidos_quitados"] += 1
        elif f.tipo == "crear_linea":
            if despues.get("_paso") == "ajustes":
                c["rendimientos_registrados"] += 1
                c["monto_rendimientos"] += float(despues.get("monto") or 0)
            else:
                c["lineas_importadas"] += 1
        elif f.tipo == "ajuste_inicial":
            c["ajustes_iniciales"] += 1
        elif f.tipo == "saldo":
            s = saldos.setdefault(f.entidad_id, {"antes": antes.get("saldo"), "despues": None})
            s["despues"] = despues.get("saldo")
        if f.tipo in TIPOS_MOV:
            base = despues or antes
            detalle.append({"tipo": f.tipo, "cuenta_id": base.get("cuenta_id"), "descripcion": (base.get("descripcion") or "")[:60],
                            "monto": base.get("monto"), "fecha": (base.get("fecha") or "")[:10],
                            "monto_antes": antes.get("monto") if antes and despues else None,
                            "tipo_antes": antes.get("tipo") if antes and despues else None})
    nombres = {x.id: x.nombre for x in db.query(Cuenta).filter(Cuenta.usuario_id == uid).all()}
    cuentas = [{"cuenta_id": cid, "cuenta": nombres.get(cid, "Cuenta"), "saldo_antes": s["antes"], "saldo_despues": s["despues"]}
               for cid, s in saldos.items() if s["antes"] is not None and s["despues"] is not None
               and abs(s["antes"] - s["despues"]) >= 0.005]
    revertido = bool(filas) and all(f.revertido_en is not None for f in filas)
    return {"lote_id": lote, "creado_en": filas[0].creado_en.isoformat() if filas else None,
            "cambios": len([f for f in filas if f.tipo != "saldo"]), "contadores": {**c, "monto_rendimientos": round(c["monto_rendimientos"], 2)},
            "texto": texto_resumen(c), "cuentas": cuentas, "detalle": detalle[:200], "revertido": revertido,
            "deshacible": bool(filas) and not revertido,
            "total_saldo_antes": round(sum(x["saldo_antes"] for x in cuentas), 2),
            "total_saldo_despues": round(sum(x["saldo_despues"] for x in cuentas), 2)}


def texto_resumen(c: dict) -> str:
    """«Listo, ordené tus cuentas: moví 4 extractos a tu tarjeta, corregí 31 compras, registré 12 rendimientos e impuestos.»"""
    partes = []
    if c["extractos_movidos"]:
        partes.append(f"moví {_n(c['extractos_movidos'], 'extracto', 'extractos')} a tu tarjeta")
    if c["compras_corregidas"]:
        partes.append(f"corregí {_n(c['compras_corregidas'], 'compra', 'compras')}")
    if c["pagos_corregidos"]:
        partes.append(f"corregí {_n(c['pagos_corregidos'], 'pago', 'pagos')} de tarjeta")
    if c["repetidos_quitados"]:
        partes.append(f"quité {_n(c['repetidos_quitados'], 'movimiento repetido', 'movimientos repetidos')}")
    if c["rendimientos_registrados"]:
        partes.append(f"registré {_n(c['rendimientos_registrados'], 'rendimiento o impuesto', 'rendimientos e impuestos')}")
    if c["lineas_importadas"]:
        partes.append(f"importé {_n(c['lineas_importadas'], 'movimiento verificado', 'movimientos verificados')}")
    if c["fechas_arregladas"]:
        partes.append(f"corregí las fechas de {_n(c['fechas_arregladas'], 'extracto', 'extractos')}")
    if c["duplicados_marcados"]:
        partes.append(f"aparté {_n(c['duplicados_marcados'], 'extracto repetido', 'extractos repetidos')} (no toqué tus movimientos)")
    if c["ajustes_iniciales"] and not partes:
        partes.append("actualicé el saldo con el que empezaron tus cuentas")
    return ("Listo, ordené tus cuentas: " + ", ".join(partes) + ".") if partes else "Tus cuentas ya estaban ordenadas."


# ── Orquestador ──────────────────────────────────────────────────────────────────────────────────────────
def correr(db: Session, usuario_id: str, max_pasos: int = MAX_PASOS_POR_LLAMADA, *, usuario=None,
           respetar_intervalo: bool = False, origen: str = "app") -> dict:
    """Una llamada acotada. Devuelve `{estado: 'trabajando'|'listo', progreso: {hecho, total, paso}, lote_id, cambios, resumen,
    pasos, decisiones, cuadre, ...}`. 'trabajando' = queda trabajo y esta llamada avanzó: vuelve a llamar. Nunca lanza."""
    uid = usuario_id
    base = {"estado": "listo", "progreso": {"hecho": len(PASOS), "total": len(PASOS), "paso": None}, "lote_id": None, "cambios": 0,
            "resumen": None, "pasos": [], "decisiones": [], "cuadre": [], "origen": origen}
    token = None
    try:
        if pausado(db, uid):
            return {**base, "pausado": True, "texto": "Pausé el orden automático porque deshiciste el último arreglo."}
        if respetar_intervalo and _marca(db, uid, CLAVE_PEDIDO) is None:
            ultima = _instante(_marca(db, uid, CLAVE_ULTIMA).valor) if _marca(db, uid, CLAVE_ULTIMA) else None
            if ultima and _ahora() - ultima < INTERVALO_APP and _marca(db, uid, CLAVE_LOTE) is None:
                return {**base, "omitido": True}
        token = tomar_candado(db, uid)
        if token is None:  # otra llamada ya está ordenando: esta no duplica nada
            return {**base, "estado": "trabajando", "ocupado": True, "progreso": {"hecho": 0, "total": len(PASOS), "paso": PASOS[0][1]}}
        usuario = usuario or _usuario_de(db, uid)
        lote = _lote_abierto(db, uid)
        ctx = _Ctx(db, usuario, lote, max_pasos)
        ctx.cuadre = []
        pasos, hecho, pendiente = [], 0, False
        for clave, etiqueta in PASOS:
            try:
                r = _EJECUTORES[clave](ctx)
                r.update(paso=clave, etiqueta=etiqueta, estado="ok")
            except Exception as e:  # noqa: BLE001 - un paso que falla no rompe los demás
                db.rollback()
                logger.exception("Autoarreglo: falló el paso %s (usuario %s)", clave, uid[:8])
                r = {"paso": clave, "etiqueta": etiqueta, "estado": "fallo", "error": type(e).__name__, "hecho": 0, "quedan": 0}
                ctx.notas.append(f"{etiqueta}: no pude terminarlo ahora")
            pasos.append(r)
            if r.get("quedan"):
                pendiente = True
            elif r["estado"] == "ok" and not pendiente:
                hecho += 1
        _poner(db, uid, CLAVE_ULTIMA, _ahora().isoformat())
        _quitar(db, uid, CLAVE_PEDIDO)
        sigue = pendiente and ctx.unidades > 0 and not ctx.limite_alcanzado
        if not sigue:
            _quitar(db, uid, CLAVE_LOTE)  # el lote se cierra: lo siguiente será otro
        resumen = resumen_lote(db, uid, lote) if ctx.cambios or _filas_del_lote(db, uid, lote) else None
        actual = next((p["etiqueta"] for p in pasos if p.get("quedan")), None) if sigue else None
        return {
            **base, "estado": "trabajando" if sigue else "listo", "lote_id": lote if resumen else None, "cambios": resumen["cambios"] if resumen else 0,
            "progreso": {"hecho": hecho if sigue else len(PASOS), "total": len(PASOS), "paso": actual},
            "resumen": resumen, "pasos": pasos, "decisiones": _decisiones(ctx.decisiones), "cuadre": ctx.cuadre,
            "limite_alcanzado": ctx.limite_alcanzado, "quedan_por_hacer": pendiente and not sigue, "notas": ctx.notas}
    except Exception:  # noqa: BLE001 - jamás hacia la persona
        db.rollback()
        logger.exception("Autoarreglo falló (usuario %s)", uid[:8])
        return {**base, "error": True}
    finally:
        if token is not None:
            soltar_candado(db, uid, token)


def correr_seguro(db: Session, usuario_id: str, max_pasos: int = MAX_PASOS_POR_LLAMADA, **kw) -> dict:
    """Igual que `correr` (que ya no lanza), por si quien llama quiere dejarlo explícito (cron)."""
    return correr(db, usuario_id, max_pasos, **kw)


# ── Deshacer ─────────────────────────────────────────────────────────────────────────────────────────────────
class Inconsistente(Exception):
    pass


def _fecha(v):
    return datetime.fromisoformat(v) if isinstance(v, str) and v else None


def _igual_traz(mov: Movimiento, esperado: dict) -> bool:
    actual = _traz({k: _valor(getattr(mov, k, None)) for k in TRAZADOS})
    return {k: actual.get(k) for k in TRAZADOS} == {k: _valor(esperado.get(k)) for k in TRAZADOS}


def _restaurar_campos(mov: Movimiento, antes: dict) -> None:
    for k in TRAZADOS:
        v = antes.get(k)
        setattr(mov, k, _fecha(v) if k == "fecha" else v)


def _revertir_mov(db: Session, f: ArregloAuto, cuentas: dict[str, Cuenta]) -> None:
    antes, despues = _cargar(f.antes), _cargar(f.despues)
    actual = db.get(Movimiento, f.entidad_id)
    if antes is None:  # se creó: se borra
        if actual is None:
            return  # ya no está (la persona lo borró): el estado que se quería ya es el actual
        if not _igual_traz(actual, despues):
            raise Inconsistente("Un movimiento que creé después cambió")
        cuenta = cuentas.get(actual.cuenta_id) or bloquear_cuenta(db, actual.cuenta_id)
        cuenta.saldo = round((cuenta.saldo or 0) - delta_saldo(actual), 2)
        db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == actual.id).delete(synchronize_session=False)
        db.delete(actual)
    elif despues is None:  # se borró: se vuelve a crear con todos sus datos
        if actual is not None:
            raise Inconsistente("El movimiento que quité volvió a existir")
        fila = {k: v for k, v in antes.items() if not k.startswith("_")}
        for k in ("fecha", "conciliado_en"):
            fila[k] = _fecha(fila.get(k))
        mov = Movimiento(**{k: v for k, v in fila.items() if k in Movimiento.__table__.c})
        db.add(mov)
        cuenta = cuentas.get(mov.cuenta_id) or bloquear_cuenta(db, mov.cuenta_id)
        if cuenta is None or cuenta.usuario_id != f.usuario_id:
            raise Inconsistente("La cuenta de un movimiento ya no existe")
        cuenta.saldo = round((cuenta.saldo or 0) + delta_saldo(mov), 2)
    else:  # se modificó: vuelve a como estaba
        if actual is None or not _igual_traz(actual, despues):
            raise Inconsistente("Un movimiento que corregí cambió después")
        c_ahora = cuentas.get(actual.cuenta_id) or bloquear_cuenta(db, actual.cuenta_id)
        c_ahora.saldo = round((c_ahora.saldo or 0) - delta_saldo(actual), 2)
        _restaurar_campos(actual, antes)
        c_antes = cuentas.get(actual.cuenta_id) or bloquear_cuenta(db, actual.cuenta_id)
        c_antes.saldo = round((c_antes.saldo or 0) + delta_saldo(actual), 2)
        if antes.get("cuenta_id") != despues.get("cuenta_id"):
            db.query(HuellaOrigen).filter(HuellaOrigen.movimiento_id == actual.id).update(
                {HuellaOrigen.cuenta_id: antes["cuenta_id"]}, synchronize_session=False)


def _revertir_historial(db: Session, f: ArregloAuto) -> None:
    antes, despues = _cargar(f.antes), _cargar(f.despues)
    h = db.query(HistorialExtracto).filter(HistorialExtracto.id == f.entidad_id, HistorialExtracto.usuario_id == f.usuario_id).first()
    if h is None:
        return
    actual = {"cuenta_id": h.cuenta_id, "estado": h.estado, "review_json": h.review_json, "fecha_corte": h.fecha_corte,
              "periodo_inicio": h.periodo_inicio, "lectura_json": h.lectura_json,
              "saldo_inicial_extracto": h.saldo_inicial_extracto, "saldo_final_extracto": h.saldo_final_extracto}
    if despues.get("huella") not in (_huella_hist(actual), _huella_hist(actual, False)):
        raise Inconsistente("Un extracto que ordené cambió después")
    for k in HIST_CAMPOS:
        if k in antes:
            setattr(h, k, antes[k])


def _ids_de_cuentas(filas: list[ArregloAuto]) -> set[str]:
    ids: set[str] = set()
    for f in filas:
        for blob in (f.antes, f.despues):
            d = _cargar(blob)
            if d and d.get("cuenta_id"):
                ids.add(d["cuenta_id"])
        if f.tipo == "saldo" and f.entidad_id:
            ids.add(f.entidad_id)
    return ids


def deshacer_lote(db: Session, usuario_id: str, lote_id: str) -> dict:
    """Revierte el lote COMPLETO en orden inverso (con bloqueo de las cuentas). Idempotente. Si algo posterior dejó un
    cambio inconsistente → 409 y no se toca nada. Tras deshacer, esos extractos no se vuelven a ordenar solos y el orden
    automático se pausa 24 horas."""
    filas = _filas_del_lote(db, usuario_id, lote_id)
    if not filas:
        raise HTTPException(status_code=404, detail="No encontramos ese arreglo.")
    pendientes = [f for f in filas if f.revertido_en is None]
    if not pendientes:
        return {"ok": True, "ya_deshecho": True, "revertidos": 0, "texto": "Ese arreglo ya estaba deshecho."}
    token = tomar_candado(db, usuario_id)
    if token is None:
        raise HTTPException(status_code=409, detail="Estoy ordenando tus cuentas ahora mismo. Intenta de nuevo en un momento.")
    try:
        ids = sorted(_ids_de_cuentas(pendientes))
        cuentas = {}
        for cid in ids:  # siempre en el mismo orden (por id), como el resto de operaciones de saldo
            c = bloquear_cuenta(db, cid)
            if c is not None and c.usuario_id == usuario_id:
                cuentas[cid] = c
        try:
            for f in sorted(pendientes, key=lambda x: (x.creado_en, x.id), reverse=True):
                if f.tipo == "historial":
                    _revertir_historial(db, f)
                elif f.tipo in TIPOS_MOV:
                    _revertir_mov(db, f, cuentas)
                f.revertido_en = _ahora()
            db.flush()
        except Inconsistente as e:
            db.rollback()
            raise HTTPException(status_code=409, detail=f"No pude deshacerlo: {e}. Lo que hiciste después lo hace inconsistente; no cambié nada.") from e
        for f in pendientes:
            if f.tipo == "historial":
                _poner_sin_commit(db, usuario_id, PREFIJO_NO + f.entidad_id)
        _poner_sin_commit(db, usuario_id, CLAVE_PAUSA, (_ahora() + PAUSA_TRAS_DESHACER).isoformat())
        db.commit()
    finally:
        soltar_candado(db, usuario_id, token)
    return {"ok": True, "ya_deshecho": False, "revertidos": len([f for f in pendientes if f.tipo != "saldo"]),
            "texto": "Listo, deshice el arreglo: tus cuentas quedaron como estaban antes."}


def _poner_sin_commit(db: Session, uid: str, clave: str, valor: str = "1") -> None:
    fila = _marca(db, uid, clave)
    if fila is None:
        db.add(MarcaCron(usuario_id=uid, clave=clave, valor=valor))
    else:
        fila.valor = valor
    db.flush()


def lotes(db: Session, usuario_id: str, limite: int = 20) -> list[dict]:
    """Lo hecho por lote (más reciente primero): cuántos cambios, texto, saldos antes/después por cuenta y si se puede deshacer."""
    ids = [r[0] for r in db.query(ArregloAuto.lote_id).filter(ArregloAuto.usuario_id == usuario_id)
           .group_by(ArregloAuto.lote_id).all()]
    resumenes = [resumen_lote(db, usuario_id, lote) for lote in ids]
    resumenes = [r for r in resumenes if r["cambios"]]
    resumenes.sort(key=lambda r: r["creado_en"] or "", reverse=True)
    return resumenes[:limite]
