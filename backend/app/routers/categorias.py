from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.models import Categoria, Movimiento
from app.schemas import CategoriaCreate, CategoriaOut, CategoriaUpdate

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


@router.get("", response_model=list[CategoriaOut])
def listar_categorias(
    incluir_inactivas: bool = False,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    categorias = _asegurar_categorias_base(db, usuario.id)
    if not incluir_inactivas:
        categorias = [c for c in categorias if c.activa]
    return sorted(categorias, key=lambda c: c.orden)


@router.post("", response_model=CategoriaOut)
def crear_categoria(
    data: CategoriaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    _asegurar_categorias_base(db, usuario.id)
    nombre = data.nombre.strip()

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
        db.commit()
        db.refresh(existente)
        return existente

    max_orden = db.query(Categoria).filter(Categoria.usuario_id == usuario.id).count()
    categoria = Categoria(usuario_id=usuario.id, nombre=nombre, icono=data.icono, orden=max_orden)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.put("/{categoria_id}", response_model=CategoriaOut)
def editar_categoria(
    categoria_id: str,
    data: CategoriaUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    categoria = (
        db.query(Categoria)
        .filter(Categoria.id == categoria_id, Categoria.usuario_id == usuario.id)
        .first()
    )
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

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
                Categoria.activa == True,  # noqa: E712
            )
            .first()
        )
        if duplicada:
            raise HTTPException(status_code=400, detail="Ya tienes una categoría con ese nombre")
        categoria_anterior_nombre = categoria.nombre
        categoria.nombre = nombre
        # Renombrar no debe romper los movimientos ya guardados con el nombre
        # viejo: se actualizan en cascada para que sigan agrupando bien en
        # reportes y presupuestos, en vez de quedar huérfanos con un nombre
        # que ya no existe en la lista de categorías del usuario.
        db.query(Movimiento).filter(
            Movimiento.usuario_id == usuario.id, Movimiento.categoria == categoria_anterior_nombre
        ).update({"categoria": nombre})

    if data.icono is not None:
        categoria.icono = data.icono

    if data.activa is not None:
        if categoria.es_base and not data.activa:
            # Las base se pueden ocultar (no aparecen para elegir en
            # movimientos nuevos) pero no borrar del todo, porque el
            # clasificador y los reportes antiguos siguen refiriéndose a
            # ellas por nombre.
            pass
        categoria.activa = data.activa

    db.commit()
    db.refresh(categoria)
    return categoria


@router.delete("/{categoria_id}")
def eliminar_categoria(
    categoria_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    categoria = (
        db.query(Categoria)
        .filter(Categoria.id == categoria_id, Categoria.usuario_id == usuario.id)
        .first()
    )
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    if categoria.es_base:
        raise HTTPException(
            status_code=400,
            detail="Esta categoría viene por defecto en la app — puedes ocultarla, pero no eliminarla",
        )

    en_uso = (
        db.query(Movimiento.id)
        .filter(Movimiento.usuario_id == usuario.id, Movimiento.categoria == categoria.nombre)
        .first()
    )
    if en_uso:
        raise HTTPException(
            status_code=400,
            detail="Esta categoría tiene movimientos registrados — ocúltala en vez de eliminarla para no perder el historial",
        )

    db.delete(categoria)
    db.commit()
    return {"ok": True}
