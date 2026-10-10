"""
Derechos del titular de los datos (Ley 1581 de 2012, Colombia):

  * Acceso / portabilidad: `armar_zip` entrega TODO lo que CuadraMe guarda del usuario.
  * Supresión: `borrar_todo` elimina cuenta y datos, sin dejar filas huérfanas.

Decisión de diseño: ambas funciones recorren `Base.metadata` en vez de usar una lista
fija de tablas. Así, una tabla nueva con columna `usuario_id` queda incluida en la
descarga y en el borrado sin que nadie tenga que acordarse (el olvido sería una
violación de la ley, no un simple bug). Las únicas tablas sin `usuario_id` son hijas
de otras y se tratan a mano (TABLAS_HIJAS); una prueba falla si aparece una nueva.
"""
import csv
import io
import json
import logging
import zipfile
from datetime import date, datetime
from decimal import Decimal

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base
from app.gmail_oauth import revocar_token
from app.models import CorreoGasto, Cuenta, ExtractoCorreo, HuellaOrigen, Movimiento, Perfil
from app.models_fiscal import MarcaFiscal
from app.models_gastos import GastoCompartido, GrupoGasto
from app.utiles import ahora_co, celda_segura

logger = logging.getLogger(__name__)

# Tablas SIN usuario_id: cuelgan de otra. Si se agrega una nueva, hay que decidir aquí
# cómo se exporta y se borra (test_derechos_titular.py lo exige).
TABLAS_HIJAS = {"invitaciones_cuenta", "miembros_grupo_gasto", "partes_gasto"}
# Tablas internas del sistema (no son datos del titular).
TABLAS_INTERNAS = {"marcas_cron", "importaciones_respaldo"}
# Columnas que NO se entregan: son credenciales del sistema, no datos del titular.
# Entregarlas no le sirve al usuario y, si alguien interceptara el archivo, le daría acceso.
COLUMNAS_SECRETAS = {"api_key", "api_key_hash", "gmail_refresh_token_enc", "clave_enc", "p256dh", "auth", "endpoint"}

LEEME = """CUADRAME - COPIA DE TUS DATOS
Generada el {fecha} (hora de Colombia) para {correo}.

Qué trae este archivo
- datos.json: todo lo que CuadraMe guarda de ti, en un solo archivo.
- csv/: lo mismo, una tabla por archivo, para abrir en Excel o Google Sheets.
  (movimientos.csv = tus gastos e ingresos; cuentas.csv = tus cuentas; etc.)

Qué NO trae (a propósito)
- Tu clave del Atajo, el permiso de Gmail y la clave de tus PDF: son llaves de acceso,
  no datos tuyos. Si quieres cortar esos accesos, hazlo desde Perfil.

Tus derechos (Ley 1581 de 2012): puedes pedir corregir tus datos o borrarlos. Para borrar
todo, entra a Perfil -> Privacidad y datos -> "Borrar mi cuenta y todos mis datos".
"""


def _json_valor(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _tabla(nombre: str):
    return Base.metadata.tables[nombre]


def recopilar(db: Session, usuario_id: str, email: str = "") -> dict[str, list[dict]]:
    """Todas las filas del titular, por tabla, sin columnas secretas.
    Incluye lo que otras personas escribieron DENTRO de sus cuentas (movimientos en una
    cuenta compartida) y las invitaciones que envió o recibió."""
    mis_cuentas = [r[0] for r in db.query(Cuenta.id).filter(Cuenta.usuario_id == usuario_id).all()]
    mis_grupos = [r[0] for r in db.query(GrupoGasto.id).filter(GrupoGasto.usuario_id == usuario_id).all()]
    mis_gastos = [r[0] for r in db.query(GastoCompartido.id).filter(GastoCompartido.usuario_id == usuario_id).all()]

    datos: dict[str, list[dict]] = {}
    for tabla in Base.metadata.sorted_tables:
        if tabla.name in TABLAS_INTERNAS:
            continue
        c = tabla.c
        if "usuario_id" in c:
            cond = c.usuario_id == usuario_id
            if tabla.name in ("movimientos", "cuentas_compartidas") and mis_cuentas:
                cond = or_(cond, c.cuenta_id.in_(mis_cuentas))
        elif tabla.name == "invitaciones_cuenta":
            cond = or_(c.invitado_por == usuario_id, c.cuenta_id.in_(mis_cuentas or [""]),
                       c.email_invitado == (email or "").lower() if email else False)
        elif tabla.name == "miembros_grupo_gasto":
            cond = c.grupo_id.in_(mis_grupos or [""])
        elif tabla.name == "partes_gasto":
            cond = c.gasto_id.in_(mis_gastos or [""])
        else:
            # Tabla hija nueva sin tratar: mejor no exportarla que exportar de más.
            logger.error("derechos_titular: tabla %s sin regla de exportación", tabla.name)
            continue
        filas = db.execute(tabla.select().where(cond)).mappings().all()
        if filas:
            datos[tabla.name] = [
                {k: _json_valor(v) for k, v in dict(f).items() if k not in COLUMNAS_SECRETAS} for f in filas
            ]
    return datos


def _csv(filas: list[dict]) -> str:
    columnas: list[str] = []
    for f in filas:
        for k in f:
            if k not in columnas:
                columnas.append(k)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columnas)
    for f in filas:
        w.writerow([celda_segura(f.get(k)) if isinstance(f.get(k), str) else f.get(k) for k in columnas])
    return buf.getvalue()


def armar_json(datos: dict, email: str) -> bytes:
    cuerpo = {"formato": "cuadrame-respaldo", "version": 1, "exportado_en_hora_colombia": ahora_co().isoformat(), "correo": email, "tablas": datos}
    return json.dumps(cuerpo, ensure_ascii=False, indent=2).encode("utf-8")


def armar_zip(datos: dict, email: str) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("LEEME.txt", LEEME.format(fecha=ahora_co().strftime("%Y-%m-%d %H:%M"), correo=email or "tu cuenta"))
        z.writestr("datos.json", armar_json(datos, email))
        for nombre, filas in datos.items():
            # BOM para que Excel abra bien las tildes y la ñ.
            z.writestr(f"csv/{nombre}.csv", "﻿" + _csv(filas))
    return salida.getvalue()


def borrar_todo(db: Session, usuario_id: str, email: str = "") -> dict:
    """Borra TODO lo del usuario, de forma irreversible. Devuelve un resumen:
    {"auth_eliminado": bool, "gmail_revocado": bool, "aviso": str | None}.

    Orden (importa):
      0. Revocar el permiso de Gmail en Google (antes de perder el token).
      1. Deshacer el efecto de lo que registró en cuentas AJENAS (saldo del dueño).
      2. Quitar todo lo que cuelga de SUS cuentas, sin importar quién lo escribió, y las
         marcas fiscales de otros sobre esos movimientos (si no, quedarían huérfanas).
      3. Invitaciones.
      4. Tablas hijas sin usuario_id (miembros/partes de gastos compartidos).
      5. Toda tabla con usuario_id.
      6. Un solo commit; recién entonces se borra el login en Supabase Auth.
    """
    uid = usuario_id
    perfil = db.query(Perfil).filter(Perfil.usuario_id == uid).first()
    gmail_revocado = revocar_token(perfil.gmail_refresh_token_enc) if perfil and perfil.gmail_refresh_token_enc else False

    mis_cuentas = [c.id for c in db.query(Cuenta.id).filter(Cuenta.usuario_id == uid).all()]

    from app.routers.movimientos import _delta_saldo  # import tardío: evita un ciclo de módulos

    ajenos = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == uid, Movimiento.cuenta_id.notin_(mis_cuentas or [""]))
        .all()
    )
    for m in ajenos:
        cuenta = db.query(Cuenta).filter(Cuenta.id == m.cuenta_id).first()
        if cuenta:
            cuenta.saldo -= _delta_saldo(m.tipo, m.monto)

    if mis_cuentas:
        movs_en_mis_cuentas = db.query(Movimiento.id).filter(Movimiento.cuenta_id.in_(mis_cuentas))
        db.query(MarcaFiscal).filter(MarcaFiscal.movimiento_id.in_(movs_en_mis_cuentas)).delete(synchronize_session=False)
        # Rastros de OTROS usuarios (editores de una cuenta compartida) que apuntan a estos movimientos.
        db.query(CorreoGasto).filter(CorreoGasto.movimiento_id.in_(movs_en_mis_cuentas)).update(
            {CorreoGasto.movimiento_id: None}, synchronize_session=False)
        # Huellas de canal (dedup) de cualquier usuario que apunten a estas cuentas o movimientos.
        db.query(HuellaOrigen).filter(or_(HuellaOrigen.cuenta_id.in_(mis_cuentas),
                                          HuellaOrigen.movimiento_id.in_(movs_en_mis_cuentas))).delete(synchronize_session=False)
        db.query(ExtractoCorreo).filter(ExtractoCorreo.cuenta_sugerida_id.in_(mis_cuentas)).update(
            {ExtractoCorreo.cuenta_sugerida_id: None}, synchronize_session=False)
        db.query(Movimiento).filter(Movimiento.cuenta_id.in_(mis_cuentas)).delete(synchronize_session=False)
        for nombre in ("historial_extractos", "cuentas_compartidas", "invitaciones_cuenta"):
            t = _tabla(nombre)
            db.execute(t.delete().where(t.c.cuenta_id.in_(mis_cuentas)))

    inv = _tabla("invitaciones_cuenta")
    db.execute(inv.delete().where(inv.c.invitado_por == uid))
    if email:
        db.execute(inv.delete().where(inv.c.email_invitado == email.lower()))

    mis_grupos = db.query(GrupoGasto.id).filter(GrupoGasto.usuario_id == uid)
    mis_gastos = db.query(GastoCompartido.id).filter(GastoCompartido.usuario_id == uid)
    for nombre, col, sub in (("miembros_grupo_gasto", "grupo_id", mis_grupos), ("partes_gasto", "gasto_id", mis_gastos)):
        t = _tabla(nombre)
        db.execute(t.delete().where(t.c[col].in_(sub)))

    # Archivos de muestra («Mi banco no aparece») en almacenamiento privado: salen antes que las filas que
    # guardan su ruta. Si falla un borrado, se registra y se sigue (no debe impedir el derecho a borrar).
    from app import almacen_muestras
    from app.models_comentarios import Comentario

    for (ruta,) in db.query(Comentario.adjunto_ruta).filter(
        Comentario.usuario_id == uid, Comentario.adjunto_ruta.isnot(None)
    ).all():
        almacen_muestras.borrar(ruta)

    for tabla in Base.metadata.sorted_tables:
        if "usuario_id" in tabla.c:
            db.execute(tabla.delete().where(tabla.c.usuario_id == uid))
    db.commit()

    auth_eliminado = False
    aviso = None
    if settings.supabase_service_role_key:
        try:
            resp = httpx.delete(
                f"{settings.supabase_url}/auth/v1/admin/users/{uid}",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                },
                timeout=15,
            )
            auth_eliminado = resp.status_code in (200, 204)
            if not auth_eliminado:
                logger.error("Supabase Auth respondió %s al borrar el usuario %s", resp.status_code, uid)
        except httpx.HTTPError:
            logger.exception("No se pudo borrar el usuario %s de Supabase Auth", uid)
        if not auth_eliminado:
            # Los datos ya se borraron (commit arriba): no se pierde ese avance.
            aviso = "Tus datos se borraron, pero no pudimos cerrar tu acceso; escríbenos a soporte"
    return {"auth_eliminado": auth_eliminado, "gmail_revocado": gmail_revocado, "aviso": aviso}
