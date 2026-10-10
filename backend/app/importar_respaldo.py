"""Importar mi respaldo: restaura el ZIP que entrega «Descargar mis datos» (/perfil/mis-datos).

Principios (todo pensado para que importar sea SEGURO y se pueda repetir sin miedo):

  * Solo se lee `datos.json` del ZIP. Nada se extrae a disco ni se ejecuta; los CSV y el LEEME
    se ignoran. El archivo tiene tope de tamaño (comprimido y descomprimido: evita «bombas zip»).
  * Lista blanca: solo cuentas, movimientos, presupuestos, metas y reglas. Cualquier otra tabla,
    campo desconocido o campo secreto (claves, tokens) se ignora.
  * Todo lo importado nace con el `usuario_id` de QUIEN importa, con ids NUEVOS (cuentas ->
    movimientos remapeados). Jamás se toca una fila de otro usuario.
  * Idempotente: lo que ya existe se omite. Los movimientos se comparan por una huella
    (cuenta + día + tipo + monto + descripción) contando repetidos (dos cafés iguales el mismo día
    son dos movimientos), así importar dos veces no duplica.
  * Una sola transacción: si algo falla no queda nada a medias.
  * Respeta el punto de partida: lo anterior a esa fecha no se importa.
  * Cada importación guarda un «lote» con los ids creados para poder deshacerla.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy import Date as SaDate
from sqlalchemy.orm import Session

from app import punto_partida
from app.contabilidad import FUENTE_APORTE_META, delta_saldo
from app.database import Base
from app.derechos_titular import COLUMNAS_SECRETAS
from app.duplicados import ORIGENES, ORIGEN_IMPORTACION, huella_archivo
from app.models import Cuenta, Meta, Movimiento, Presupuesto, ReglaCategoria, gen_uuid
from app.utiles import ahora_co

FORMATO = "cuadrame-respaldo"
VERSION_SOPORTADA = 1
MAX_BYTES_ARCHIVO = 15 * 1024 * 1024        # lo que se acepta subir
MAX_BYTES_JSON = 60 * 1024 * 1024           # lo que se acepta descomprimido
MAX_FILAS_POR_TABLA = 100_000
MAX_TEXTO = 1000
TIPOS_MOVIMIENTO = {"income", "expense", "transfer"}
TABLAS = ("cuentas", "movimientos", "presupuestos", "metas", "reglas_categoria")
_COLUMNAS_NO_IMPORTABLES = {"id", "usuario_id"} | COLUMNAS_SECRETAS
# Estados que dependen de procesos externos o de cómo estaba la persona ese día: nacen en blanco.
_COLUMNAS_EN_BLANCO = {
    "cuentas": {"ultima_alerta_pago"},
    "movimientos": {"conciliado_en", "extracto_id"},
    "presupuestos": {"ultima_alerta_mes"},
    "metas": {"ultimo_aporte_automatico"},
    "reglas_categoria": set(),
}
_MODELOS = {"cuentas": Cuenta, "movimientos": Movimiento, "presupuestos": Presupuesto,
            "metas": Meta, "reglas_categoria": ReglaCategoria}


class RespaldoInvalido(ValueError):
    """El archivo no es un respaldo de CuadraMe que podamos leer (mensaje en lenguaje llano)."""


class ImportacionRespaldo(Base):
    """Lote de una importación: ids creados y ajustes de saldo, para poder deshacerla.
    Tabla con usuario_id: la descarga de datos y el borrado de cuenta la cubren solos."""
    __tablename__ = "importaciones_respaldo"

    id = Column(String, primary_key=True, default=gen_uuid)
    usuario_id = Column(String, nullable=False, index=True)
    creado_en = Column(DateTime, default=ahora_co)
    deshecho_en = Column(DateTime, nullable=True)
    resumen = Column(String, default="{}")  # JSON: conteos que se le mostraron a la persona
    lote = Column(String, default="{}")     # JSON: ids creados y ajustes de saldo


# ── Lectura del archivo ────────────────────────────────────────────────────────────────
def leer_datos(contenido: bytes) -> dict:
    """Devuelve {'tablas': {...}, 'correo': str|None} validado. Lanza RespaldoInvalido."""
    if not contenido:
        raise RespaldoInvalido("El archivo está vacío.")
    if len(contenido) > MAX_BYTES_ARCHIVO:
        raise RespaldoInvalido("El archivo es muy pesado para ser un respaldo de CuadraMe (máximo 15 MB).")
    if contenido[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(contenido))
            info = z.getinfo("datos.json")
        except (zipfile.BadZipFile, KeyError):
            raise RespaldoInvalido("Este ZIP no trae el archivo datos.json. Usa el que descargaste en «Descargar mis datos».")
        if info.file_size > MAX_BYTES_JSON:
            raise RespaldoInvalido("El respaldo es demasiado grande para importarlo.")
        with z.open(info) as f:
            crudo = f.read(MAX_BYTES_JSON + 1)  # no se confía en el tamaño declarado
        if len(crudo) > MAX_BYTES_JSON:
            raise RespaldoInvalido("El respaldo es demasiado grande para importarlo.")
    else:
        crudo = contenido  # también se acepta el datos.json suelto
    try:
        cuerpo = json.loads(crudo.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise RespaldoInvalido("No pudimos leer el archivo. ¿Es el respaldo que descargaste de CuadraMe?")
    if not isinstance(cuerpo, dict) or not isinstance(cuerpo.get("tablas"), dict):
        raise RespaldoInvalido("Este archivo no parece un respaldo de CuadraMe.")
    if cuerpo.get("formato") not in (None, FORMATO):
        raise RespaldoInvalido("Este archivo no parece un respaldo de CuadraMe.")
    version = cuerpo.get("version", 1)
    if not isinstance(version, int) or version < 1 or version > VERSION_SOPORTADA:
        raise RespaldoInvalido("Este respaldo viene de una versión más nueva de CuadraMe. Actualiza la app e intenta de nuevo.")
    tablas: dict[str, list[dict]] = {}
    for nombre in TABLAS:
        filas = cuerpo["tablas"].get(nombre) or []
        if not isinstance(filas, list):
            raise RespaldoInvalido("El respaldo tiene un formato inesperado.")
        if len(filas) > MAX_FILAS_POR_TABLA:
            raise RespaldoInvalido("El respaldo trae demasiados registros para importarlo de una vez.")
        tablas[nombre] = [f for f in filas if isinstance(f, dict)]
    correo = cuerpo.get("correo")
    return {"tablas": tablas, "correo": correo if isinstance(correo, str) else None}


# ── Conversión de columnas ─────────────────────────────────────────────────────────────
def _fecha(v: Any, solo_fecha: bool = False):
    if isinstance(v, str) and v.strip():
        try:
            d = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("fecha")
        d = d.replace(tzinfo=None)
        return d.date() if solo_fecha else d
    raise ValueError("fecha")


def _limpiar_fila(nombre: str, fila: dict) -> dict:
    """Solo columnas conocidas del modelo, con el tipo correcto. Lanza ValueError si algo no sirve."""
    modelo = _MODELOS[nombre]
    en_blanco = _COLUMNAS_EN_BLANCO[nombre]
    out: dict[str, Any] = {}
    for col in modelo.__table__.columns:
        k = col.key
        if k in _COLUMNAS_NO_IMPORTABLES or k in en_blanco or k not in fila:
            continue
        v = fila[k]
        if v is None:
            out[k] = None
            continue
        t = col.type
        if isinstance(t, Float):
            if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                raise ValueError(k)
            x = float(v)
            if not math.isfinite(x) or abs(x) > 1e12:
                raise ValueError(k)
            out[k] = x
        elif isinstance(t, Integer):
            if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                raise ValueError(k)
            out[k] = int(float(v))
        elif isinstance(t, Boolean):
            out[k] = bool(v)
        elif isinstance(t, DateTime):
            out[k] = _fecha(v)
        elif isinstance(t, SaDate):
            out[k] = _fecha(v, solo_fecha=True)
        else:
            if not isinstance(v, (str, int, float)):
                raise ValueError(k)
            out[k] = str(v)[:MAX_TEXTO]
    return out


def _norm(texto: Any) -> str:
    return re.sub(r"\s+", " ", str(texto or "")).strip().lower()


def _huella_mov(cuenta_id: str, fecha: datetime, tipo: str, monto: float, descripcion: str) -> str:
    base = f"{cuenta_id}|{fecha:%Y-%m-%d}|{tipo}|{monto:.2f}|{_norm(descripcion)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]


# ── Plan (vista previa) y aplicación ──────────────────────────────────────────────────
def _vacio(): return {"nuevos": 0, "existentes": 0, "invalidos": 0}


def procesar(db: Session, usuario_id: str, datos: dict, *, aplicar: bool) -> dict:
    """Con aplicar=False solo cuenta lo que pasaría (no escribe nada). Con aplicar=True escribe
    dentro de la sesión SIN hacer commit (quien llama decide: así todo es una transacción).
    Devuelve {'resumen': {...}, 'lote': {...}}."""
    t = datos["tablas"]
    inicio_pp = punto_partida.fecha_inicio(db, usuario_id)
    res = {k: _vacio() for k in ("cuentas", "movimientos", "presupuestos", "metas", "reglas")}
    res["movimientos"].update({"sin_cuenta": 0, "anteriores_al_punto_de_partida": 0})
    lote = {"cuentas": [], "movimientos": [], "presupuestos": [], "metas": [], "reglas": [],
            "ajustes_saldo": {}, "metas_monto": {}}

    # 1) Cuentas: si ya tienes una igual (nombre + tipo + moneda) se reutiliza, no se duplica.
    mias = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).all()
    por_clave = {(_norm(c.nombre), c.tipo or "ahorro", c.moneda or "COP"): c for c in mias}
    mapa_cuentas: dict[str, tuple[str, bool]] = {}  # id del respaldo -> (id real, es_nueva)
    for fila in t["cuentas"]:
        try:
            d = _limpiar_fila("cuentas", fila)
            if not _norm(d.get("nombre")):
                raise ValueError("nombre")
        except (ValueError, TypeError):
            res["cuentas"]["invalidos"] += 1
            continue
        id_orig = str(fila.get("id") or "")
        d.setdefault("tipo", "ahorro")
        d.setdefault("moneda", "COP")
        clave = (_norm(d["nombre"]), d["tipo"] or "ahorro", d["moneda"] or "COP")
        if clave in por_clave:
            res["cuentas"]["existentes"] += 1
            if id_orig:
                mapa_cuentas[id_orig] = (por_clave[clave].id, False)
            continue
        res["cuentas"]["nuevos"] += 1
        nueva_id = gen_uuid()
        if id_orig:
            mapa_cuentas[id_orig] = (nueva_id, True)
        if aplicar:
            c = Cuenta(id=nueva_id, usuario_id=usuario_id, **d)
            db.add(c)
            por_clave[clave] = c
            lote["cuentas"].append(nueva_id)
        else:
            por_clave[clave] = Cuenta(id=nueva_id, usuario_id=usuario_id, **d)  # solo en memoria (no se agrega)
    if aplicar:
        db.flush()

    # 2) Presupuestos, metas y reglas (metas antes que movimientos: los aportes citan la meta).
    _simples(db, usuario_id, t["presupuestos"], "presupuestos", Presupuesto, res["presupuestos"], lote,
             clave=lambda d: (_norm(d.get("categoria")), d.get("periodo") or "monthly"),
             existentes=lambda: db.query(Presupuesto).filter(Presupuesto.usuario_id == usuario_id).all(),
             clave_fila=lambda p: (_norm(p.categoria), p.periodo or "monthly"),
             requeridos=("categoria", "limite"), aplicar=aplicar)
    mapa_metas: dict[str, str] = {}
    _simples(db, usuario_id, t["metas"], "metas", Meta, res["metas"], lote,
             clave=lambda d: (_norm(d.get("nombre")), round(float(d.get("monto_objetivo") or 0), 2)),
             existentes=lambda: db.query(Meta).filter(Meta.usuario_id == usuario_id).all(),
             clave_fila=lambda m: (_norm(m.nombre), round(float(m.monto_objetivo or 0), 2)),
             requeridos=("nombre", "monto_objetivo"), aplicar=aplicar, mapa=mapa_metas,
             ajustar=lambda d: d.update(cuenta_origen_id=(mapa_cuentas.get(d.get("cuenta_origen_id") or "", (None, 0))[0])))
    _simples(db, usuario_id, t["reglas_categoria"], "reglas", ReglaCategoria, res["reglas"], lote,
             clave=lambda d: (_norm(d.get("patron")), _norm(d.get("categoria"))),
             existentes=lambda: db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario_id).all(),
             clave_fila=lambda r: (_norm(r.patron), _norm(r.categoria)),
             requeridos=("patron", "categoria"), aplicar=aplicar)

    # 3) Movimientos. Cuentas existentes: se cuentan los movimientos que ya hay por huella.
    ya_hay: Counter = Counter()
    destinos_existentes = [cid for cid, nueva in mapa_cuentas.values() if not nueva]
    if destinos_existentes:
        for m in db.query(Movimiento).filter(Movimiento.cuenta_id.in_(destinos_existentes)).all():
            if m.fecha:
                ya_hay[_huella_mov(m.cuenta_id, m.fecha, m.tipo, m.monto, m.descripcion)] += 1
    vistos: Counter = Counter()
    for fila in t["movimientos"]:
        try:
            d = _limpiar_fila("movimientos", fila)
            if d.get("tipo") not in TIPOS_MOVIMIENTO or d.get("monto") is None or d["monto"] < 0:
                raise ValueError("tipo/monto")
            if not _norm(d.get("descripcion")) or not isinstance(d.get("fecha"), datetime):
                raise ValueError("descripcion/fecha")
        except (ValueError, TypeError):
            res["movimientos"]["invalidos"] += 1
            continue
        destino = mapa_cuentas.get(str(fila.get("cuenta_id") or ""))
        if not destino:
            res["movimientos"]["sin_cuenta"] += 1  # p. ej. un movimiento tuyo en una cuenta compartida de otra persona
            continue
        cuenta_id, cuenta_nueva = destino
        if inicio_pp and d["fecha"] < inicio_pp:
            res["movimientos"]["anteriores_al_punto_de_partida"] += 1
            continue
        fp = _huella_mov(cuenta_id, d["fecha"], d["tipo"], d["monto"], d["descripcion"])
        vistos[fp] += 1
        if vistos[fp] <= ya_hay.get(fp, 0):
            res["movimientos"]["existentes"] += 1
            continue
        res["movimientos"]["nuevos"] += 1
        if not aplicar:
            continue
        notas = d.get("notas") or ""
        if d.get("fuente") == FUENTE_APORTE_META or notas.startswith("META:"):
            m = re.match(r"META:([\w-]+)", notas)
            if m and m.group(1) in mapa_metas:
                notas = "META:" + mapa_metas[m.group(1)] + notas[m.end():]
        d["notas"] = notas
        origen = d.get("origen")
        d["origen"] = origen if origen in ORIGENES else ORIGEN_IMPORTACION
        if not d.get("huella_externa"):
            d["huella_externa"] = huella_archivo("resp-" + fp, vistos[fp])
        d["cuenta_id"] = cuenta_id
        mov = Movimiento(usuario_id=usuario_id, **d)
        db.add(mov)
        db.flush()
        lote["movimientos"].append(mov.id)
        if not cuenta_nueva:
            # En una cuenta que ya tenías, el movimiento recuperado mueve su saldo como cualquier otro.
            delta = delta_saldo(mov)
            if delta:
                cuenta = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == usuario_id).first()
                if cuenta:
                    cuenta.saldo = (cuenta.saldo or 0) + delta
                    lote["ajustes_saldo"][cuenta_id] = lote["ajustes_saldo"].get(cuenta_id, 0) + delta
    correo = datos.get("correo")
    res["correo_distinto"] = False  # lo completa el router (necesita el correo de la sesión)
    res["correo_respaldo"] = correo
    return {"resumen": res, "lote": lote}


def _simples(db, usuario_id, filas, nombre, modelo, cuenta_res, lote, *, clave, existentes, clave_fila,
             requeridos, aplicar, mapa=None, ajustar=None):
    ya = {clave_fila(x): x for x in existentes()}
    nombre_modelo = "reglas_categoria" if nombre == "reglas" else nombre
    for fila in filas:
        try:
            d = _limpiar_fila(nombre_modelo, fila)
            if any(d.get(r) in (None, "") for r in requeridos):
                raise ValueError("requerido")
            if ajustar:
                ajustar(d)
            k = clave(d)
        except (ValueError, TypeError):
            cuenta_res["invalidos"] += 1
            continue
        id_orig = str(fila.get("id") or "")
        if k in ya:
            cuenta_res["existentes"] += 1
            if mapa is not None and id_orig:
                mapa[id_orig] = ya[k].id
            continue
        cuenta_res["nuevos"] += 1
        nueva_id = gen_uuid()
        if mapa is not None and id_orig:
            mapa[id_orig] = nueva_id
        obj = modelo(id=nueva_id, usuario_id=usuario_id, **d)
        ya[k] = obj  # un duplicado dentro del mismo archivo tampoco se crea dos veces
        if aplicar:
            db.add(obj)
            lote[nombre].append(nueva_id)
            if nombre == "metas":
                lote["metas_monto"][nueva_id] = d.get("monto_actual") or 0
    if aplicar:
        db.flush()


# ── Importar y deshacer ────────────────────────────────────────────────────────────────
def importar(db: Session, usuario_id: str, datos: dict) -> dict:
    """Aplica y guarda el lote, TODO en la sesión: quien llama hace commit (o rollback si falla)."""
    r = procesar(db, usuario_id, datos, aplicar=True)
    lote = ImportacionRespaldo(usuario_id=usuario_id, resumen=json.dumps(r["resumen"], ensure_ascii=False),
                               lote=json.dumps(r["lote"]))
    db.add(lote)
    db.flush()
    r["resumen"]["lote_id"] = lote.id
    return r["resumen"]


def ultima_importacion(db: Session, usuario_id: str) -> ImportacionRespaldo | None:
    """La última importación que aún se puede deshacer (de este usuario)."""
    return (db.query(ImportacionRespaldo)
            .filter(ImportacionRespaldo.usuario_id == usuario_id, ImportacionRespaldo.deshecho_en.is_(None))
            .order_by(ImportacionRespaldo.creado_en.desc()).first())


def deshacer(db: Session, usuario_id: str, lote_fila: ImportacionRespaldo) -> dict:
    """Revierte solo lo que esa importación creó (sin commit). Cada borrado filtra por usuario_id."""
    lote = json.loads(lote_fila.lote or "{}")
    uid = usuario_id
    out = {"movimientos": 0, "cuentas": 0, "presupuestos": 0, "metas": 0, "reglas": 0, "conservados": 0}

    ids_mov = lote.get("movimientos") or []
    for i in range(0, len(ids_mov), 500):
        out["movimientos"] += (db.query(Movimiento)
                               .filter(Movimiento.usuario_id == uid, Movimiento.id.in_(ids_mov[i:i + 500]))
                               .delete(synchronize_session=False))
    for cuenta_id, delta in (lote.get("ajustes_saldo") or {}).items():
        c = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == uid).first()
        if c:
            c.saldo = (c.saldo or 0) - delta

    for cuenta_id in lote.get("cuentas") or []:
        c = db.query(Cuenta).filter(Cuenta.id == cuenta_id, Cuenta.usuario_id == uid).first()
        if not c:
            continue
        if db.query(Movimiento.id).filter(Movimiento.cuenta_id == cuenta_id).first():
            out["conservados"] += 1  # ya le registraste cosas después: no se borra
            continue
        db.delete(c)
        out["cuentas"] += 1
    for pid in lote.get("presupuestos") or []:
        out["presupuestos"] += db.query(Presupuesto).filter(Presupuesto.id == pid, Presupuesto.usuario_id == uid).delete()
    for rid in lote.get("reglas") or []:
        out["reglas"] += db.query(ReglaCategoria).filter(ReglaCategoria.id == rid, ReglaCategoria.usuario_id == uid).delete()
    for mid in lote.get("metas") or []:
        m = db.query(Meta).filter(Meta.id == mid, Meta.usuario_id == uid).first()
        if not m:
            continue
        if abs((m.monto_actual or 0) - (lote.get("metas_monto") or {}).get(mid, 0)) > 0.005:
            out["conservados"] += 1  # ya aportaste a esa meta después
            continue
        db.delete(m)
        out["metas"] += 1
    lote_fila.deshecho_en = ahora_co()
    return out
