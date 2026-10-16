"""CRUD de subcategorías (un nivel dentro de cada categoría). Todo aislado por usuario.
Ver docs/SUBCATEGORIAS.md."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import subcategorias as sc
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.models import Categoria, Movimiento, ReglaCategoria, Subcategoria
from app.routers.categorias import _asegurar_categorias_base
from app.schemas import SubcategoriaCreate, SubcategoriaOut, SubcategoriaUpdate

router = APIRouter(prefix="/subcategorias", tags=["subcategorias"])


def _salida(db: Session, usuario_id: str, filas: list[Subcategoria]) -> list[dict]:
    uso = {(c, s): n for c, s, n in db.query(Movimiento.categoria, Movimiento.subcategoria, func.count(Movimiento.id))
           .filter(Movimiento.usuario_id == usuario_id, Movimiento.subcategoria.isnot(None))
           .group_by(Movimiento.categoria, Movimiento.subcategoria).all()}
    return [{"id": s.id, "categoria": s.categoria_padre, "nombre": s.nombre, "orden": s.orden or 0,
             "movimientos": uso.get((s.categoria_padre, s.nombre), 0)} for s in filas]


def _buscar(db: Session, usuario_id: str, subcategoria_id: str) -> Subcategoria:
    s = db.query(Subcategoria).filter(Subcategoria.id == subcategoria_id, Subcategoria.usuario_id == usuario_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")
    return s


@router.get("", response_model=list[SubcategoriaOut])
def listar(categoria: str | None = None, db: Session = Depends(get_db),
           usuario: UsuarioActual = Depends(get_current_user)):
    """Todas las subcategorías del usuario (o solo las de una categoría), en el orden en que las creó."""
    q = db.query(Subcategoria).filter(Subcategoria.usuario_id == usuario.id)
    if categoria:
        q = q.filter(Subcategoria.categoria_padre == categoria)
    return _salida(db, usuario.id, q.order_by(Subcategoria.categoria_padre, Subcategoria.orden, Subcategoria.creado_en).all())


@router.post("", response_model=SubcategoriaOut)
def crear(data: SubcategoriaCreate, db: Session = Depends(get_db),
          usuario: UsuarioActual = Depends(get_current_user)):
    _asegurar_categorias_base(db, usuario.id)  # las 8 base se crean la primera vez que se piden
    padre = (db.query(Categoria).filter(Categoria.usuario_id == usuario.id, Categoria.nombre == data.categoria.strip()).first())
    if not padre:
        raise HTTPException(status_code=404, detail="Esa categoría no existe en tu lista")
    if padre.es_sistema or not sc.admite_subcategorias(padre.nombre):
        raise HTTPException(status_code=400, detail="Esta categoría la maneja la app: no admite subcategorías")
    nombre = data.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre no puede quedar vacío")
    if sc.buscar(db, usuario.id, padre.nombre, nombre):
        raise HTTPException(status_code=400, detail=f"Ya tienes «{nombre}» dentro de {padre.nombre}")
    maximo = db.query(func.max(Subcategoria.orden)).filter(
        Subcategoria.usuario_id == usuario.id, Subcategoria.categoria_padre == padre.nombre).scalar()
    s = Subcategoria(usuario_id=usuario.id, categoria_padre=padre.nombre, nombre=nombre,
                     orden=(maximo if maximo is not None else -1) + 1)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _salida(db, usuario.id, [s])[0]


@router.put("/{subcategoria_id}", response_model=SubcategoriaOut)
def renombrar(subcategoria_id: str, data: SubcategoriaUpdate, db: Session = Depends(get_db),
              usuario: UsuarioActual = Depends(get_current_user)):
    s = _buscar(db, usuario.id, subcategoria_id)
    nombre = data.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre no puede quedar vacío")
    otra = sc.buscar(db, usuario.id, s.categoria_padre, nombre)
    if otra and otra.id != s.id:
        raise HTTPException(status_code=400, detail=f"Ya tienes «{nombre}» dentro de {s.categoria_padre}")
    anterior = s.nombre
    if nombre != anterior:
        s.nombre = nombre
        # Los movimientos y reglas que la usaban la siguen con el nombre nuevo.
        db.query(Movimiento).filter(Movimiento.usuario_id == usuario.id, Movimiento.categoria == s.categoria_padre,
                                    Movimiento.subcategoria == anterior).update(
            {"subcategoria": nombre}, synchronize_session=False)
        db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario.id,
                                        ReglaCategoria.categoria == s.categoria_padre,
                                        ReglaCategoria.subcategoria == anterior).update(
            {"subcategoria": nombre}, synchronize_session=False)
    db.commit()
    db.refresh(s)
    return _salida(db, usuario.id, [s])[0]


@router.delete("/{subcategoria_id}")
def eliminar(subcategoria_id: str, db: Session = Depends(get_db),
             usuario: UsuarioActual = Depends(get_current_user)):
    """Borrar una subcategoría NO borra movimientos: quedan solo con su categoría (sin subcategoría)."""
    s = _buscar(db, usuario.id, subcategoria_id)
    quitados = db.query(Movimiento).filter(
        Movimiento.usuario_id == usuario.id, Movimiento.categoria == s.categoria_padre,
        Movimiento.subcategoria == s.nombre).update({"subcategoria": None}, synchronize_session=False)
    db.query(ReglaCategoria).filter(
        ReglaCategoria.usuario_id == usuario.id, ReglaCategoria.categoria == s.categoria_padre,
        ReglaCategoria.subcategoria == s.nombre).update({"subcategoria": None}, synchronize_session=False)
    db.delete(s)
    db.commit()
    return {"ok": True, "movimientos_sin_subcategoria": quitados}
