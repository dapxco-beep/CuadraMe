"""
Importar movimientos desde un archivo CSV / Excel (de un banco o propio).

Dos pasos, igual que la conciliación de extractos PDF:
1. POST /importar/vista-previa  -> NO guarda nada. Lee el archivo, detecta (o
   respeta) el mapeo de columnas y devuelve una PROPUESTA: cada fila con su
   categoría sugerida y si parece duplicada de algo ya registrado.
2. POST /importar/confirmar     -> guarda solo las filas que el usuario dejó
   marcadas. Vuelve a revisar duplicados exactos (importar dos veces el mismo
   archivo no duplica nada).

Los duplicados se detectan con la MISMA lógica de la conciliación (huella
fecha+monto+cuenta+descripción y coincidencia aproximada ±3 días / ±5 %).
"""
import base64
import binascii
import json
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.autocat import ClasificadorUsuario, aplicar_a_anteriores, clasificar_lote_detalle, datos_auto, guardar_regla_aprendida
from app.comercios_conocidos import clasificar_por_diccionario
from app.compartidos import bloquear_cuenta, cuenta_accesible, puede_editar_cuenta
from app.conciliacion import auditar_movimientos, compute_fingerprint
from app.contabilidad import CATEGORIA_PAGO_TARJETA, FUENTE_IMPORTADO_SIN_SALDO, es_pago_tarjeta
from app.database import get_db
from app.importador_tabular import MAX_BYTES, MAX_FILAS, CAMPOS, ErrorArchivo, analizar
from app.limites import verificar_limite
from app.models import HistorialExtracto, Movimiento, ReglaCategoria
from app.rachas import registrar_actividad_hoy
from app.routers.conciliacion import _cargar_ledger

router = APIRouter(prefix="/importar", tags=["importar"])

FUENTE_IMPORTACION = "importacion_archivo"
# El base64 pesa ~4/3 del archivo; este tope se revisa antes de decodificar.
MAX_BASE64 = MAX_BYTES * 4 // 3 + 1024


class VistaPreviaRequest(BaseModel):
    cuenta_id: str
    nombre_archivo: str = Field(max_length=200)
    archivo_base64: str
    # Mapeo editable por el usuario: {"fecha": 0, "descripcion": 2, "monto": 3, ...}.
    # Si no viene, se detecta solo. null en un campo = "no usar esa columna".
    mapeo: Optional[dict[str, Optional[int]]] = None
    separador_decimal: Optional[Literal["auto", "coma", "punto"]] = None
    orden_fecha: Optional[Literal["dmy", "mdy"]] = None
    invertir_signo: Optional[bool] = None
    fila_encabezado: Optional[int] = Field(default=None, ge=-1, le=500)  # -1 = el archivo no trae encabezado
    hoja: int = Field(default=0, ge=0, le=50)


class FilaImportar(BaseModel):
    fecha: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    descripcion: str = Field(min_length=1, max_length=200)
    monto: float = Field(gt=0, lt=1e13)
    tipo: Literal["income", "expense"]
    categoria: Optional[str] = Field(default=None, max_length=60)
    recordar: bool = False  # guardar la categoría elegida como regla del comercio
    aplicar_anteriores: bool = False  # además, recategorizar movimientos pasados de ese comercio


class ConfirmarRequest(BaseModel):
    cuenta_id: str
    nombre_archivo: str = Field(default="archivo", max_length=200)
    filas: list[FilaImportar] = Field(max_length=MAX_FILAS)
    ajustar_saldo: bool = True


def _decodificar(b64: str) -> bytes:
    if len(b64) > MAX_BASE64:
        raise HTTPException(status_code=413, detail=f"El archivo pesa más de {MAX_BYTES // (1024 * 1024)} MB.")
    try:
        return base64.b64decode(b64.split(",", 1)[-1], validate=False)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="El archivo no llegó completo. Inténtalo de nuevo.")


def _cuenta_editable(db: Session, usuario: UsuarioActual, cuenta_id: str):
    cuenta = cuenta_accesible(db, usuario.id, cuenta_id)
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    return cuenta


def clasificar_lote(db: Session, usuario_id: str, descripciones: list[str]) -> list[str]:
    """Categoría sugerida para cada descripción (el modelo aprendido se arma UNA vez).
    Orden: pago de tarjeta -> reglas del usuario -> aprendido -> diccionario."""
    return [cat for cat, _ in clasificar_lote_detalle(db, usuario_id, descripciones)]


def _ledger_del_rango(db: Session, usuario_id: str, cuenta_id: str, movs: list[dict]) -> list[dict]:
    """Ledger de la cuenta recortado al rango de fechas del archivo (±3 días): el
    emparejamiento aproximado es O(filas × ledger) y no hace falta mirar más lejos."""
    if not movs:
        return []
    fechas = [m["fecha"] for m in movs]
    desde = datetime.fromisoformat(min(fechas)) - timedelta(days=4)
    hasta = datetime.fromisoformat(max(fechas)) + timedelta(days=5)
    return [r for r in _cargar_ledger(db, usuario_id, cuenta_id) if r["fecha"] and desde <= r["fecha"] <= hasta]


@router.post("/vista-previa")
def vista_previa(
    data: VistaPreviaRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = _cuenta_editable(db, usuario, data.cuenta_id)
    verificar_limite(f"importar:{usuario.id}", 60, 3600, "Subiste muchos archivos seguidos. Podrás subir más en {espera}.")
    contenido = _decodificar(data.archivo_base64)

    mapeo = None
    if data.mapeo is not None:
        mapeo = {c: data.mapeo.get(c) for c in CAMPOS}
    opciones = {
        "separador_decimal": data.separador_decimal,
        "orden_fecha": data.orden_fecha,
        "invertir_signo": data.invertir_signo,
    }
    opciones = {k: v for k, v in opciones.items() if v is not None}
    try:
        analisis = analizar(
            data.nombre_archivo, contenido, mapeo=mapeo, opciones=opciones,
            fila_encabezado=data.fila_encabezado, hoja=data.hoja,
        )
    except ErrorArchivo as e:
        raise HTTPException(status_code=422, detail=str(e))

    movs = analisis.pop("movimientos")
    for m in movs:
        m["cuenta"] = cuenta.id  # la huella del ledger usa el id de la cuenta (ver _cargar_ledger)
    auditoria = auditar_movimientos(movs, _ledger_del_rango(db, usuario.id, cuenta.id, movs))
    clf = ClasificadorUsuario(db, usuario.id)
    clasifs = [clf.clasificar(m["descripcion"]) for m in movs]

    ESTADO = {"faltante": "nuevo", "exacto": "duplicado", "aproximado": "posible_duplicado"}
    propuesta = []
    for item, r in zip(auditoria["review"], clasifs):
        cat = r["categoria"] if r else "Otros"
        propuesta.append({
            "razon_categoria": r.get("razon") if r else None,
            "fila": item["fila"],
            "fecha": item["fecha"],
            "descripcion": item["descripcion"],
            "monto": item["monto"],
            "tipo": item["tipo"],
            "categoria": cat,
            "estado": ESTADO[item["estado"]],
        })

    return {
        "cuenta": {"id": cuenta.id, "nombre": cuenta.nombre, "moneda": cuenta.moneda, "saldo": cuenta.saldo},
        **analisis,
        "propuesta": propuesta,
        "resumen": {
            "nuevos": auditoria["faltantes"],
            "duplicados": auditoria["exactos"],
            "posibles_duplicados": auditoria["aproximados"],
            "con_error": len(analisis["errores"]),
        },
        "errores": analisis["errores"][:50],
    }


@router.post("/confirmar")
def confirmar(
    data: ConfirmarRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = _cuenta_editable(db, usuario, data.cuenta_id)
    if not data.filas:
        raise HTTPException(status_code=422, detail="No hay movimientos para importar.")
    cuenta = bloquear_cuenta(db, cuenta.id)

    movs = [{"fecha": f.fecha, "descripcion": f.descripcion, "monto": f.monto, "tipo": f.tipo,
             "cuenta": cuenta.id} for f in data.filas]
    ledger = _ledger_del_rango(db, usuario.id, cuenta.id, movs)
    huellas_existentes = {r["fingerprint"] for r in ledger if r.get("fingerprint")}
    categorias_auto = None

    importados = omitidos = auto_categorizados = 0
    reglas_guardadas = anteriores_actualizados = 0
    reglas_omitidas: list[dict] = []
    neto = 0.0
    for i, f in enumerate(data.filas):
        fp = compute_fingerprint(f.fecha, f.monto, cuenta.id, f.descripcion, f.tipo)
        if fp in huellas_existentes:
            omitidos += 1  # ya está: importar el mismo archivo dos veces no duplica
            continue
        categoria = (f.categoria or "").strip()
        if categorias_auto is None:
            categorias_auto = clasificar_lote_detalle(db, usuario.id, [x.descripcion for x in data.filas])
        sugerida, origen = categorias_auto[i]
        if not categoria:
            categoria = sugerida
        # Si la categoría que llega es la misma que sugirió la app (la vista previa
        # la muestra), sigue siendo "automática"; si el usuario la cambió, es suya.
        auto = datos_auto(origen if categoria == sugerida else None)
        if not auto["cat_confirmada"]:
            auto_categorizados += 1
        db.add(Movimiento(
            usuario_id=usuario.id, cuenta_id=cuenta.id, fecha=datetime.fromisoformat(f.fecha),
            descripcion=f.descripcion.strip(), categoria=categoria, tipo=f.tipo, monto=f.monto,
            # Sin ajustar saldo, la marca evita que editar/borrar luego mueva el saldo.
            fuente=FUENTE_IMPORTACION if data.ajustar_saldo else FUENTE_IMPORTADO_SIN_SALDO,
            notas=f"Importado de {data.nombre_archivo[:80]}", **auto,
        ))
        neto += f.monto if f.tipo == "income" else -f.monto
        importados += 1
        if f.recordar and categoria and categoria != "Otros":
            r = guardar_regla_aprendida(db, usuario.id, f.descripcion, categoria)
            if r["guardada"]:
                reglas_guardadas += 1
                if f.aplicar_anteriores:
                    anteriores_actualizados += aplicar_a_anteriores(db, usuario.id, r["huella"], categoria)
            else:
                reglas_omitidas.append({"huella": r["huella"], "motivo": r["motivo"], "descripcion": f.descripcion, "categoria": categoria})

    if data.ajustar_saldo and importados:
        cuenta.saldo = (cuenta.saldo or 0) + neto

    db.add(HistorialExtracto(
        usuario_id=usuario.id, cuenta_id=cuenta.id, banco_detectado=f"archivo: {data.nombre_archivo[:60]}",
        total_movimientos=len(data.filas), exactos=omitidos, aproximados=0, faltantes=0,
        importados=importados, estado="conciliado", review_json=json.dumps([]),
    ))
    db.commit()
    if importados:
        registrar_actividad_hoy(db, usuario.id)
    return {"ok": True, "importados": importados, "duplicados_omitidos": omitidos,
            "categorizados_auto": auto_categorizados, "reglas_guardadas": reglas_guardadas,
            "anteriores_actualizados": anteriores_actualizados, "reglas_omitidas": reglas_omitidas,
            "saldo": cuenta.saldo, "saldo_ajustado": bool(data.ajustar_saldo and importados)}
