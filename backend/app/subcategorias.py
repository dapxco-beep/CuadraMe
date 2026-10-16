"""Subcategorías: un nivel de detalle OPCIONAL dentro de una categoría (ver docs/SUBCATEGORIAS.md).

Regla de oro: la CATEGORÍA padre es la que agrega (informes, presupuestos, gráficas, asistente, regla
contable). La subcategoría solo desglosa, así que ninguna cifra existente cambia por tenerlas.
Se guardan por NOMBRE de la categoría padre, igual que el resto de la app referencia las categorías."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.autocat import CATEGORIAS_DE_SISTEMA
from app.models import Movimiento, ReglaCategoria, Subcategoria


def admite_subcategorias(categoria: str) -> bool:
    """Las categorías que la app maneja por su cuenta (traslados, pago de tarjeta, cobros del banco...)
    no admiten subcategorías: podrían romper la regla contable única."""
    return bool(categoria) and categoria not in CATEGORIAS_DE_SISTEMA


def buscar(db: Session, usuario_id: str, categoria: str, nombre: str) -> Subcategoria | None:
    """Sin distinguir mayúsculas: «gasolina» y «Gasolina» son la misma."""
    n = (nombre or "").strip().lower()
    if not n:
        return None
    for s in db.query(Subcategoria).filter(Subcategoria.usuario_id == usuario_id,
                                          Subcategoria.categoria_padre == categoria).all():
        if s.nombre.strip().lower() == n:
            return s
    return None


def normalizar(db: Session, usuario_id: str, categoria: str, nombre: str | None) -> str | None:
    """Nombre oficial de la subcategoría de esa categoría, o None si viene vacía. 400 si no existe."""
    if nombre is None or not nombre.strip():
        return None
    s = buscar(db, usuario_id, categoria, nombre)
    if not s:
        raise HTTPException(status_code=400, detail=f"«{nombre.strip()}» no es una subcategoría de {categoria}")
    return s.nombre


def existente_o_nada(db: Session, usuario_id: str, categoria: str, nombre: str | None) -> str | None:
    """Como normalizar pero sin error: para sugerencias automáticas (si ya no existe, se descarta)."""
    s = buscar(db, usuario_id, categoria, nombre) if nombre else None
    return s.nombre if s else None


def renombrar_categoria_padre(db: Session, usuario_id: str, anterior: str, nuevo: str) -> None:
    """La categoría cambió de nombre: sus subcategorías la siguen. Si el nuevo nombre ya tenía una
    subcategoría igual, la vieja se descarta (los movimientos conservan el nombre, que es el mismo)."""
    for s in db.query(Subcategoria).filter(Subcategoria.usuario_id == usuario_id,
                                          Subcategoria.categoria_padre == anterior).all():
        if buscar(db, usuario_id, nuevo, s.nombre):
            db.delete(s)
        else:
            s.categoria_padre = nuevo
    db.flush()


def mover_a_otra_categoria(db: Session, usuario_id: str, anterior: str, destino: str) -> None:
    """Se elimina `anterior` pasando sus movimientos a `destino`: sus subcategorías se van con ellos
    (las que ya existan en destino se fusionan por nombre). Si destino no admite subcategorías
    (categoría de sistema) los movimientos y reglas pierden la subcategoría."""
    if not admite_subcategorias(destino):
        db.query(Movimiento).filter(Movimiento.usuario_id == usuario_id, Movimiento.categoria == destino,
                                    Movimiento.subcategoria.isnot(None)).update(
            {"subcategoria": None}, synchronize_session=False)
        db.query(ReglaCategoria).filter(ReglaCategoria.usuario_id == usuario_id,
                                        ReglaCategoria.categoria == destino).update(
            {"subcategoria": None}, synchronize_session=False)
        borrar_de_categoria(db, usuario_id, anterior)
        return
    renombrar_categoria_padre(db, usuario_id, anterior, destino)


def borrar_de_categoria(db: Session, usuario_id: str, categoria: str) -> None:
    """Se elimina la categoría: sus subcategorías se van con ella."""
    db.query(Subcategoria).filter(Subcategoria.usuario_id == usuario_id,
                                  Subcategoria.categoria_padre == categoria).delete(synchronize_session=False)
