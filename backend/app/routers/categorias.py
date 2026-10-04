from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from sqlalchemy import func

from app.models import Categoria, CorreoGasto, Movimiento, Presupuesto, Recurrente, ReglaCategoria
from app.schemas import CategoriaCreate, CategoriaOut, CategoriasOrden, CategoriaUpdate

router = APIRouter(prefix="/categorias", tags=["categorias"])

# Las 8 categorías con las que la app siempre ha trabajado. Se crean en la
# base de datos la primera vez que un usuario pide su lista y no tiene
# ninguna todavía, para que a partir de ahí sean filas editables como
# cualquier categoría que el usuario agregue — nunca vuelven a estar
# hardcodeadas en el frontend.
CATEGORIAS_BASE = [
    ("Comida", "🍔"),
    ("Transporte", "🚗"),
    ("Ocio", "🎬"),
    ("Hogar", "🏠"),
    ("Salud", "💊"),
    ("Transferencias", "↔️"),
    ("Ingresos", "💰"),
    ("Otros", "🏷️"),
]


def _asegurar_categorias_base(db: Session, usuario_id: str) -> list[Categoria]:
    existentes = db.query(Categoria).filter(Categoria.usuario_id == usuario_id).all()
    if existentes:
        return existentes

    nuevas = [
        Categoria(usuario_id=usuario_id, nombre=nombre, icono=icono, orden=i, es_base=True)
        for i, (nombre, icono) in enumerate(CATEGORIAS_BASE)
    ]
    db.add_all(nuevas)
    db.commit()
    for c in nuevas:
        db.refresh(c)
    return nuevas


def _con_conteo(db: Session, usuario_id: str, categorias: list[Categoria]) -> list[dict]:
    """CategoriaOut + cuántos movimientos usa cada una (para avisar antes de
    ocultar/eliminar y para el contador de la pantalla)."""
    filas = (
        db.query(Movimiento.categoria, func.count(Movimiento.id))
        .filter(Movimiento.usuario_id == usuario_id)
        .group_by(Movimiento.categoria)
        .all()
    )
    conteo = {nombre: n for nombre, n in filas}
    salida = []
    for c in sorted(categorias, key=lambda c: c.orden):
        salida.append({
            "id": c.id, "nombre": c.nombre, "icono": c.icono, "orden": c.orden,
            "activa": bool(c.activa), "es_base": bool(c.es_base), "color": c.color,
            "tipo": c.tipo or "ambos", "movimientos": conteo.get(c.nombre, 0),
        })
    return salida


def _buscar(db: Session, usuario_id: str, categoria_id: str) -> Categoria:
    categoria = (
        db.query(Categoria)
        .filter(Categoria.id == categoria_id, Categoria.usuario_id == usuario_id)
        .first()
    )
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return categoria


def _reemplazar_nombre(db: Session, usuario_id: str, anterior: str, nuevo: str) -> int:
    """Cambia el nombre de categoría en TODO lo que la referencia por nombre
    (movimientos, reglas, presupuestos, recurrentes, sugerencias de correo) para
    que nada quede huérfano. Devuelve cuántos movimientos se actualizaron."""
    movidos = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == usuario_id, Movimiento.categoria == anterior)
        .update({"categoria": nuevo}, synchronize_session=False)
    )
    db.query(ReglaCategoria).filter(
        ReglaCategoria.usuario_id == usuario_id, ReglaCategoria.categoria == anterior
    ).update({"categoria": nuevo}, synchronize_session=False)
    db.query(Recurrente).filter(
        Recurrente.usuario_id == usuario_id, Recurrente.categoria == anterior
    ).update({"categoria": nuevo}, synchronize_session=False)
    db.query(CorreoGasto).filter(
        CorreoGasto.usuario_id == usuario_id, CorreoGasto.categoria_sugerida == anterior
    ).update({"categoria_sugerida": nuevo}, synchronize_session=False)
    # Presupuesto: si ya hay uno para el nombre nuevo, el viejo sobra (un solo
    # presupuesto por categoría); si no, simplemente se renombra.
    hay_destino = (
        db.query(Presupuesto.id)
        .filter(Presupuesto.usuario_id == usuario_id, Presupuesto.categoria == nuevo)
        .first()
    )
    if hay_destino and anterior.lower() != nuevo.lower():
        db.query(Presupuesto).filter(
            Presupuesto.usuario_id == usuario_id, Presupuesto.categoria == anterior
        ).delete(synchronize_session=False)
    else:
        db.query(Presupuesto).filter(
            Presupuesto.usuario_id == usuario_id, Presupuesto.categoria == anterior
        ).update({"categoria": nuevo}, synchronize_session=False)
    return movidos


def _referencias(db: Session, usuario_id: str, nombre: str) -> dict:
    return {
        "movimientos": db.query(Movimiento.id).filter(
            Movimiento.usuario_id == usuario_id, Movimiento.categoria == nombre).count(),
        "reglas": db.query(ReglaCategoria.id).filter(
            ReglaCategoria.usuario_id == usuario_id, ReglaCategoria.categoria == nombre).count(),
        "presupuestos": db.query(Presupuesto.id).filter(
            Presupuesto.usuario_id == usuario_id, Presupuesto.categoria == nombre).count(),
        "recurrentes": db.query(Recurrente.id).filter(
            Recurrente.usuario_id == usuario_id, Recurrente.categoria == nombre).count(),
    }


@router.get("", response_model=list[CategoriaOut])
def listar_categorias(
    incluir_inactivas: bool = False,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Por defecto solo las activas (para los selectores). Con
    incluir_inactivas=true devuelve también las ocultas: la pantalla de
    Categorías siempre lo pide así, para que nada quede inaccesible."""
    categorias = _asegurar_categorias_base(db, usuario.id)
    if not incluir_inactivas:
        categorias = [c for c in categorias if c.activa]
    return _con_conteo(db, usuario.id, categorias)


@router.post("", response_model=CategoriaOut)
def crear_categoria(
    data: CategoriaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    _asegurar_categorias_base(db, usuario.id)
    nombre = data.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre no puede quedar vacío")

    existente = (
        db.query(Categoria)
        .filter(Categoria.usuario_id == usuario.id, Categoria.nombre.ilike(nombre))
        .first()
    )
    if existente:
        if existente.activa:
            raise HTTPException(status_code=400, detail="Ya tienes una categoría con ese nombre")
        # reactivar en vez de duplicar, si el usuario la había ocultado antes
        existente.activa = True
        existente.icono = data.icono
        existente.color = data.color
        existente.tipo = data.tipo
        db.commit()
        db.refresh(existente)
        return _con_conteo(db, usuario.id, [existente])[0]

    max_orden = db.query(func.max(Categoria.orden)).filter(Categoria.usuario_id == usuario.id).scalar()
    categoria = Categoria(
        usuario_id=usuario.id, nombre=nombre, icono=data.icono, color=data.color,
        tipo=data.tipo, orden=(max_orden if max_orden is not None else -1) + 1,
    )
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return _con_conteo(db, usuario.id, [categoria])[0]


# Debe ir antes de "/{categoria_id}" para que "orden" no se tome como un id.
@router.put("/orden")
def reordenar_categorias(
    data: CategoriasOrden,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Guarda el orden elegido: recibe los ids en el orden deseado. Las que no
    vengan en la lista (por ejemplo ocultas) se quedan al final."""
    todas = _asegurar_categorias_base(db, usuario.id)
    por_id = {c.id: c for c in todas}
    for i, cid in enumerate(data.ids):
        if cid not in por_id:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
        por_id[cid].orden = i
    resto = sorted((c for c in todas if c.id not in set(data.ids)), key=lambda c: c.orden)
    for j, c in enumerate(resto):
        c.orden = len(data.ids) + j
    db.commit()
    return {"ok": True}


@router.put("/{categoria_id}", response_model=CategoriaOut)
def editar_categoria(
    categoria_id: str,
    data: CategoriaUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    categoria = _buscar(db, usuario.id, categoria_id)

    if data.nombre is not None:
        nombre = data.nombre.strip()
        if not nombre:
            raise HTTPException(status_code=400, detail="El nombre no puede quedar vacío")
        duplicada = (
            db.query(Categoria)
            .filter(
                Categoria.usuario_id == usuario.id,
                Categoria.nombre.ilike(nombre),
                Categoria.id != categoria_id,
            )
            .first()
        )
        if duplicada:
            raise HTTPException(
                status_code=400,
                detail="Ya tienes una categoría con ese nombre"
                + ("" if duplicada.activa else " (está oculta: reactívala)"),
            )
        anterior = categoria.nombre
        if nombre != anterior:
            categoria.nombre = nombre
            # Renombrar no debe dejar nada huérfano con el nombre viejo.
            _reemplazar_nombre(db, usuario.id, anterior, nombre)

    if data.icono is not None:
        categoria.icono = data.icono
    if data.color is not None:
        categoria.color = data.color or None
    if data.tipo is not None:
        categoria.tipo = data.tipo
    if data.activa is not None:
        # Ocultar nunca borra nada: los movimientos conservan su categoría y la
        # categoría sigue visible (y reactivable) en la pantalla de Categorías.
        categoria.activa = data.activa

    db.commit()
    db.refresh(categoria)
    return _con_conteo(db, usuario.id, [categoria])[0]


@router.delete("/{categoria_id}")
def eliminar_categoria(
    categoria_id: str,
    mover_a: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Elimina una categoría propia. Si tiene movimientos (o reglas,
    presupuestos o recurrentes) hay que decir a qué categoría pasarlos con
    `mover_a`; sin eso responde 409 con el detalle de lo que la usa."""
    categoria = _buscar(db, usuario.id, categoria_id)
    if categoria.es_base:
        raise HTTPException(
            status_code=400,
            detail="Esta categoría viene por defecto en la app — puedes ocultarla, pero no eliminarla",
        )

    refs = _referencias(db, usuario.id, categoria.nombre)
    movidos = 0
    if any(refs.values()):
        if not mover_a:
            raise HTTPException(
                status_code=409,
                detail={
                    "mensaje": "Esta categoría está en uso: elige a qué categoría pasar sus movimientos",
                    **refs,
                },
            )
        destino = (
            db.query(Categoria)
            .filter(Categoria.usuario_id == usuario.id, Categoria.nombre == mover_a)
            .first()
        )
        if not destino or destino.id == categoria.id:
            raise HTTPException(status_code=400, detail="La categoría de destino no es válida")
        if not destino.activa:
            raise HTTPException(status_code=400, detail="La categoría de destino está oculta")
        movidos = _reemplazar_nombre(db, usuario.id, categoria.nombre, destino.nombre)

    db.delete(categoria)
    db.commit()
    return {"ok": True, "movidos": movidos}
