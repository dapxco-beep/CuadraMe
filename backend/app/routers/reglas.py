from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.autocat import aplicar_a_anteriores, guardar_regla_aprendida
from app.models import Categoria, ReglaCategoria
from app.schemas import AprenderReglaRequest, ReglaCategoriaCreate, ReglaCategoriaOut

router = APIRouter(prefix="/reglas-categoria", tags=["reglas"])


@router.get("", response_model=list[ReglaCategoriaOut])
def listar_reglas(
    db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)
):
    return (
        db.query(ReglaCategoria)
        .filter(ReglaCategoria.usuario_id == usuario.id)
        .order_by(ReglaCategoria.prioridad.desc())
        .all()
    )


@router.post("", response_model=ReglaCategoriaOut)
def crear_regla(
    data: ReglaCategoriaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    regla = ReglaCategoria(usuario_id=usuario.id, **data.model_dump())
    db.add(regla)
    db.commit()
    db.refresh(regla)
    return regla


@router.post("/aprender")
def aprender_regla(
    data: AprenderReglaRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Guarda la regla del comercio de esta descripción (una por huella: si ya existe se
    actualiza) y, si se pide, recategoriza los movimientos anteriores de ese comercio."""
    categoria = data.categoria.strip()
    hay_lista = db.query(Categoria.id).filter(Categoria.usuario_id == usuario.id).first()
    if hay_lista and not db.query(Categoria.id).filter(
        Categoria.usuario_id == usuario.id, Categoria.nombre == categoria
    ).first():
        raise HTTPException(status_code=400, detail="Esa categoría no existe en tu lista")
    r = guardar_regla_aprendida(
        db, usuario.id, data.descripcion, categoria, tipo=data.tipo, confirmar_peligrosa=data.confirmar_peligrosa
    )
    anteriores = 0
    if r["guardada"] and data.aplicar_anteriores:
        anteriores = aplicar_a_anteriores(db, usuario.id, r["huella"], categoria)
    db.commit()
    return {**r, "anteriores_actualizados": anteriores}


@router.delete("/{regla_id}")
def eliminar_regla(
    regla_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    regla = (
        db.query(ReglaCategoria)
        .filter(ReglaCategoria.id == regla_id, ReglaCategoria.usuario_id == usuario.id)
        .first()
    )
    if not regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    db.delete(regla)
    db.commit()
    return {"ok": True}


# ── Reglas a elección: vista previa, sugerencias y acciones en lote ─────────────────────────────
# Ninguna regla se crea sola: o el usuario activa «Recordar para este comercio» al categorizar,
# o elige cuáles sugerencias crear. Cada sugerencia descartada no vuelve a salir.
from collections import defaultdict  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402

from app import pendientes  # noqa: E402
from app.clave_comercio import clave_comercio, es_huella_peligrosa, huella_en_descripcion  # noqa: E402
from app.compartidos import cuentas_ids_accesibles  # noqa: E402
from app.models import Movimiento  # noqa: E402

# Umbral único: una regla se sugiere (o «recordar» viene activado) solo si el comercio aparece MÁS de 3
# veces (>= 4) en los movimientos del propio usuario. La PWA lo recibe como `recomendada`.
MIN_REPETICIONES_REGLA = pendientes.MIN_REPETICIONES_PENDIENTE  # = 4, una sola constante
MIN_MESES_RECURRENTE = 3
MAX_SUGERENCIAS = 30


@router.get("/vista-previa")
def vista_previa(
    descripcion: str = Query(..., min_length=1, max_length=200),
    excluir_id: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Antes de crear la regla de un comercio: cuántas veces se repite y a cuántos movimientos
    pasados afectaría. `recomendada` = se repite 4 o más veces (compras únicas: no vale la pena)."""
    huella = clave_comercio(descripcion)
    if not huella:
        return {"huella": "", "repeticiones": 1, "afectara_pasados": 0, "recomendada": False, "peligrosa": None,
                "ya_tiene_regla": False}
    ids = cuentas_ids_accesibles(db, usuario.id)
    movs = db.query(Movimiento.id, Movimiento.descripcion).filter(
        Movimiento.cuenta_id.in_(ids), Movimiento.tipo != "transfer").all()
    otros = sum(1 for i, d in movs if i != excluir_id and huella_en_descripcion(huella, d or ""))
    ya = any(clave_comercio(r.patron) == huella for r in db.query(ReglaCategoria)
             .filter(ReglaCategoria.usuario_id == usuario.id).all())
    peligro = es_huella_peligrosa(huella)
    return {"huella": huella, "repeticiones": otros + 1, "afectara_pasados": otros,
            "recomendada": (otros + 1) >= MIN_REPETICIONES_REGLA and not peligro,
            "peligrosa": peligro, "ya_tiene_regla": ya}


@router.get("/sugerencias")
def sugerencias(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Reglas que valdría la pena crear: comercios que YA categorizaste tú mismo igual 4 o más
    veces y que aún no tienen regla. Aparecen sin marcar: tú eliges cuáles crear."""
    ids = cuentas_ids_accesibles(db, usuario.id)
    reglas = db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario.id).all()
    con_regla = {clave_comercio(r.patron) for r in reglas}
    descartadas = pendientes.silencios(db, usuario.id, ("regla_descartada", "no_preguntar"))
    grupos: dict[str, dict] = {}
    for m in db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids), Movimiento.tipo != "transfer").all():
        if m.cat_confirmada is False or pendientes.es_neutro(m):
            continue
        if (m.categoria or "Otros").strip().lower() in pendientes.CATEGORIAS_SIN_DEFINIR:
            continue
        h = clave_comercio(m.descripcion)
        if not h or h in con_regla or h in descartadas or es_huella_peligrosa(h):
            continue
        g = grupos.setdefault(h, {"huella": h, "conteo": 0, "monto_total": 0.0, "ejemplo": m.descripcion,
                                  "categorias": defaultdict(int), "_meses": set()})
        if m.fecha:
            g["_meses"].add((m.fecha.year, m.fecha.month))
        g["conteo"] += 1
        g["monto_total"] += abs(m.monto or 0)
        g["categorias"][m.categoria] += 1
    salida = []
    for g in grupos.values():
        cats = g.pop("categorias")
        meses = len(g.pop("_meses"))
        mejor = max(cats, key=cats.get)
        # Solo si casi siempre lo categorizaste igual (si no, una regla mezclaría lo que haces a veces).
        if g["conteo"] < MIN_REPETICIONES_REGLA or cats[mejor] / g["conteo"] < 0.8:
            continue
        # 'recurrente': misma huella en 3 o más meses distintos (un hábito, no una racha de un día).
        salida.append({**g, "categoria": mejor, "monto_total": round(g["monto_total"], 2),
                       "meses": meses, "recurrente": meses >= MIN_MESES_RECURRENTE})
    salida.sort(key=lambda g: (not g["recurrente"], -g["monto_total"], -g["conteo"], g["huella"]))
    return {"sugerencias": salida[:MAX_SUGERENCIAS], "total": len(salida)}


class SugerenciaElegida(BaseModel):
    huella: str = Field(min_length=1, max_length=100)
    categoria: str = Field(min_length=1, max_length=60)


class CrearSugerenciasRequest(BaseModel):
    elegidas: list[SugerenciaElegida] = Field(min_length=1, max_length=MAX_SUGERENCIAS)
    aplicar_anteriores: bool = False


@router.post("/sugerencias/crear")
def crear_sugerencias(
    data: CrearSugerenciasRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Crea SOLO las reglas que el usuario eligió."""
    nombres = {n for (n,) in db.query(Categoria.nombre).filter(Categoria.usuario_id == usuario.id).all()}
    creadas, omitidas, anteriores = [], [], 0
    for e in data.elegidas:
        if nombres and e.categoria not in nombres:
            omitidas.append({"huella": e.huella, "motivo": "Esa categoría no existe en tu lista"})
            continue
        r = guardar_regla_aprendida(db, usuario.id, e.huella, e.categoria)
        if not r["guardada"]:
            omitidas.append({"huella": e.huella, "motivo": r["motivo"]})
            continue
        creadas.append(r["huella"])
        if data.aplicar_anteriores:
            anteriores += aplicar_a_anteriores(db, usuario.id, r["huella"], e.categoria)
    db.commit()
    return {"ok": True, "creadas": creadas, "omitidas": omitidas, "anteriores_actualizados": anteriores}


class DescartarSugerenciasRequest(BaseModel):
    huellas: list[str] = Field(min_length=1, max_length=MAX_SUGERENCIAS * 4)


@router.post("/sugerencias/descartar")
def descartar_sugerencias(
    data: DescartarSugerenciasRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«No me sugieras esto»: la sugerencia de regla de ese comercio no vuelve a salir."""
    pendientes.silenciar(db, usuario.id, data.huellas, "regla_descartada")
    db.commit()
    return {"ok": True}


@router.post("/sugerencias/restaurar")
def restaurar_sugerencias(
    data: DescartarSugerenciasRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Deshacer un descarte."""
    n = pendientes.quitar_silencios(db, usuario.id, data.huellas, ("regla_descartada",))
    db.commit()
    return {"ok": True, "restauradas": n}


class LoteReglasRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)
    accion: str = Field(pattern="^(pausar|reanudar|borrar)$")


@router.post("/lote")
def lote_reglas(
    data: LoteReglasRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Pausa, reanuda o borra varias reglas a la vez. Una regla en pausa no se aplica a lo nuevo,
    pero no se pierde. Borrar una regla no cambia los movimientos ya categorizados."""
    q = db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario.id, ReglaCategoria.id.in_(data.ids))
    if data.accion == "borrar":
        n = q.delete(synchronize_session=False)
    else:
        n = q.update({"activa": data.accion == "reanudar"}, synchronize_session=False)
    if not n:
        db.rollback()
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    db.commit()
    return {"ok": True, "afectadas": n}
