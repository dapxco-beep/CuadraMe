import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user, get_current_user_by_api_key
from app.classifier import aplicar_reglas, build_model, classify
from app.comercios_conocidos import clasificar_por_diccionario
from app.compartidos import bloquear_cuenta, cuenta_accesible, cuentas_ids_accesibles, puede_editar_cuenta
from app.database import get_db
from app.limites import verificar_limite
from app.models import Cuenta, Movimiento, ReglaCategoria
from app.rachas import registrar_actividad_hoy
from app.schemas import (
    ClasificarRequest,
    ClasificarResponse,
    MovimientoCreate,
    MovimientoOut,
    MovimientoPorVozCreate,
    MovimientoPorVozResponse,
    MovimientoRapidoCreate,
    MovimientoUpdate,
    RecategorizarMasivoRequest,
    RecategorizarMasivoResponse,
    TransferenciaCreate,
)
from app.voz_parser import interpretar_frase

router = APIRouter(prefix="/movimientos", tags=["movimientos"])

# Las transferencias creadas dentro de la app son dos movimientos (salida y
# entrada) que comparten un "grupo" guardado en notas como "TRF:<grupo>:out|in".
# Se distinguen de las transferencias importadas de un extracto (tipo
# "transfer" sin efecto en saldo) por esta fuente.
FUENTE_TRANSFERENCIA = "transferencia_interna"


def _delta_saldo(tipo: str, monto: float) -> float:
    """Cuánto cambia el saldo de la cuenta por un movimiento. 'transfer'
    importado de un extracto no mueve saldo (el banco ya lo reflejó)."""
    if tipo == "income":
        return monto
    if tipo == "expense":
        return -monto
    return 0.0


def _fecha_o_400(valor: str, campo: str) -> datetime:
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"'{campo}' debe ser una fecha ISO (AAAA-MM-DD)")


@router.get("", response_model=list[MovimientoOut])
def listar_movimientos(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str | None = None,
    categoria: str | None = None,
    tipo: str | None = None,
    cuenta_id: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    monto_min: float | None = None,
    monto_max: float | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    query = db.query(Movimiento).filter(Movimiento.cuenta_id.in_(ids_accesibles))

    if q:
        # Se escapan % y _ para que el texto buscado se trate como literal.
        q_literal = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(Movimiento.descripcion.ilike(f"%{q_literal}%", escape="\\"))
    if categoria:
        query = query.filter(Movimiento.categoria == categoria)
    if tipo:
        query = query.filter(Movimiento.tipo == tipo)
    if cuenta_id:
        query = query.filter(Movimiento.cuenta_id == cuenta_id)
    if desde:
        query = query.filter(Movimiento.fecha >= _fecha_o_400(desde, "desde"))
    if hasta:
        query = query.filter(Movimiento.fecha <= _fecha_o_400(hasta, "hasta"))
    if monto_min is not None:
        query = query.filter(Movimiento.monto >= monto_min)
    if monto_max is not None:
        query = query.filter(Movimiento.monto <= monto_max)

    return query.order_by(Movimiento.fecha.desc()).offset(offset).limit(limit).all()


@router.get("/{movimiento_id}", response_model=MovimientoOut)
def obtener_movimiento(
    movimiento_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    mov = (
        db.query(Movimiento)
        .filter(Movimiento.id == movimiento_id, Movimiento.cuenta_id.in_(ids_accesibles))
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return mov


@router.post("", response_model=MovimientoOut)
def crear_movimiento(
    data: MovimientoCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    cuenta = cuenta_accesible(db, usuario.id, data.cuenta_id)
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    cuenta = bloquear_cuenta(db, cuenta.id)  # saldo consistente si llegan dos registros a la vez

    categoria = data.categoria
    if not categoria:
        resultado = _clasificar(db, usuario.id, data.descripcion)
        categoria = resultado["categoria"] if resultado else "Otros"

    movimiento = Movimiento(
        usuario_id=usuario.id,
        cuenta_id=data.cuenta_id,
        descripcion=data.descripcion,
        categoria=categoria,
        tipo=data.tipo,
        monto=data.monto,
        fecha=data.fecha or ahora_co(),
        notas=data.notas or "",
        fuente="manual",
    )
    db.add(movimiento)
    cuenta.saldo += _delta_saldo(data.tipo, data.monto)

    db.commit()
    db.refresh(movimiento)
    registrar_actividad_hoy(db, usuario.id)
    return movimiento


@router.post("/transferencia")
def crear_transferencia(
    data: TransferenciaCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Mueve plata entre dos cuentas del usuario: resta de una, suma en la
    otra y deja dos movimientos enlazados (que no cuentan como gasto ni
    ingreso en los reportes, porque el dinero solo cambia de bolsillo)."""
    if data.cuenta_origen_id == data.cuenta_destino_id:
        raise HTTPException(status_code=400, detail="La cuenta de origen y la de destino deben ser distintas")

    for cid in (data.cuenta_origen_id, data.cuenta_destino_id):
        c = cuenta_accesible(db, usuario.id, cid)
        if not c or not puede_editar_cuenta(db, usuario.id, c):
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    # Se bloquean siempre en el mismo orden (por id) para que dos transferencias
    # cruzadas (A→B y B→A) no se queden esperándose mutuamente.
    bloqueadas = {cid: bloquear_cuenta(db, cid) for cid in sorted([data.cuenta_origen_id, data.cuenta_destino_id])}
    origen = bloqueadas[data.cuenta_origen_id]
    destino = bloqueadas[data.cuenta_destino_id]
    if (origen.moneda or "COP") != (destino.moneda or "COP"):
        raise HTTPException(
            status_code=400,
            detail="Aún no se pueden hacer transferencias entre cuentas de monedas distintas",
        )

    grupo = uuid.uuid4().hex
    fecha = data.fecha or ahora_co()
    db.add(Movimiento(
        usuario_id=usuario.id, cuenta_id=origen.id, fecha=fecha, tipo="transfer",
        descripcion=f"Transferencia a {destino.nombre}", categoria="Transferencia",
        monto=data.monto, fuente=FUENTE_TRANSFERENCIA, notas=f"TRF:{grupo}:out",
    ))
    db.add(Movimiento(
        usuario_id=usuario.id, cuenta_id=destino.id, fecha=fecha, tipo="transfer",
        descripcion=f"Transferencia desde {origen.nombre}", categoria="Transferencia",
        monto=data.monto, fuente=FUENTE_TRANSFERENCIA, notas=f"TRF:{grupo}:in",
    ))
    origen.saldo -= data.monto
    destino.saldo += data.monto
    db.commit()
    registrar_actividad_hoy(db, usuario.id)
    return {"ok": True, "grupo": grupo}


@router.put("/{movimiento_id}", response_model=MovimientoOut)
def editar_movimiento(
    movimiento_id: str,
    data: MovimientoUpdate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Edita un movimiento y corrige los saldos: primero se deshace el efecto
    del movimiento viejo en su cuenta y luego se aplica el del nuevo (que
    puede ser en otra cuenta, con otro monto o de otro tipo)."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    mov = (
        db.query(Movimiento)
        .filter(Movimiento.id == movimiento_id, Movimiento.cuenta_id.in_(ids_accesibles))
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if mov.fuente == FUENTE_TRANSFERENCIA:
        raise HTTPException(
            status_code=400,
            detail="Las transferencias entre cuentas no se editan: elimínala y créala de nuevo",
        )

    cambios = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}

    cuenta_actual = bloquear_cuenta(db, mov.cuenta_id)
    if not cuenta_actual or not puede_editar_cuenta(db, usuario.id, cuenta_actual):
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta cuenta")

    cuenta_nueva = cuenta_actual
    if cambios.get("cuenta_id") and cambios["cuenta_id"] != mov.cuenta_id:
        destino = cuenta_accesible(db, usuario.id, cambios["cuenta_id"])
        if not destino or not puede_editar_cuenta(db, usuario.id, destino):
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        cuenta_nueva = bloquear_cuenta(db, destino.id)

    cuenta_actual.saldo -= _delta_saldo(mov.tipo, mov.monto)
    for campo in ("descripcion", "monto", "tipo", "categoria", "fecha", "notas"):
        if campo in cambios:
            setattr(mov, campo, cambios[campo])
    mov.cuenta_id = cuenta_nueva.id
    cuenta_nueva.saldo += _delta_saldo(mov.tipo, mov.monto)

    db.commit()
    db.refresh(mov)
    return mov


@router.post("/recategorizar-masivo", response_model=RecategorizarMasivoResponse)
def recategorizar_masivo(
    data: RecategorizarMasivoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Cambia la categoría de varios movimientos a la vez (ej. seleccionar 8
    movimientos mal categorizados como 'Otros' y pasarlos todos a 'Transporte'
    en un solo toque, en vez de editar uno por uno)."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    movs = (
        db.query(Movimiento)
        .filter(Movimiento.id.in_(data.movimiento_ids), Movimiento.cuenta_id.in_(ids_accesibles))
        .all()
    )
    if not movs:
        return RecategorizarMasivoResponse(ok=True, actualizados=0)

    cuentas_de_movs = {m.cuenta_id for m in movs}
    cuentas_editables = {
        c.id for c in db.query(Cuenta).filter(Cuenta.id.in_(cuentas_de_movs)).all()
        if puede_editar_cuenta(db, usuario.id, c)
    }
    actualizados = 0
    for mov in movs:
        if mov.cuenta_id not in cuentas_editables:
            continue
        mov.categoria = data.categoria
        actualizados += 1

    db.commit()
    return RecategorizarMasivoResponse(ok=True, actualizados=actualizados)


@router.delete("/{movimiento_id}")
def eliminar_movimiento(
    movimiento_id: str,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    mov = (
        db.query(Movimiento)
        .filter(Movimiento.id == movimiento_id, Movimiento.cuenta_id.in_(ids_accesibles))
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    if mov.fuente == FUENTE_TRANSFERENCIA:
        _eliminar_transferencia(db, usuario, mov)
        return {"ok": True}

    cuenta = bloquear_cuenta(db, mov.cuenta_id)
    if cuenta and not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta cuenta")

    if cuenta:
        cuenta.saldo -= _delta_saldo(mov.tipo, mov.monto)

    db.delete(mov)
    db.commit()
    return {"ok": True}


def _eliminar_transferencia(db: Session, usuario: UsuarioActual, mov: Movimiento) -> None:
    """Borra las dos patas de una transferencia interna y devuelve el dinero
    a su lugar. Exige permiso de edición sobre ambas cuentas."""
    grupo = (mov.notas or "").split(":")[1] if (mov.notas or "").startswith("TRF:") else None
    patas = [mov]
    if grupo:
        patas = (
            db.query(Movimiento)
            .filter(Movimiento.fuente == FUENTE_TRANSFERENCIA, Movimiento.notas.like(f"TRF:{grupo}:%"))
            .all()
        )
    for cid in sorted({p.cuenta_id for p in patas}):
        c = bloquear_cuenta(db, cid)
        if not c or not puede_editar_cuenta(db, usuario.id, c):
            raise HTTPException(status_code=403, detail="No tienes permiso para editar las cuentas de esta transferencia")
    for p in patas:
        c = db.query(Cuenta).filter(Cuenta.id == p.cuenta_id).first()
        sale = (p.notas or "").endswith(":out")
        c.saldo += p.monto if sale else -p.monto
        db.delete(p)
    db.commit()


def _registrar_movimiento_rapido(
    db: Session,
    usuario_id: str,
    monto: float,
    tipo: str,
    descripcion: str,
    cuenta_nombre: str | None,
    fuente: str,
) -> Movimiento:
    # Estos endpoints se autentican solo con API key: se limita para frenar
    # tanto abusos como un atajo mal configurado que se quede en bucle.
    verificar_limite(f"rapido:{usuario_id}", 120, 3600, "Demasiados registros rápidos seguidos. Intenta en un rato.")
    cuenta = None
    if cuenta_nombre:
        cuenta = (
            db.query(Cuenta)
            .filter(Cuenta.usuario_id == usuario_id, Cuenta.nombre.ilike(f"%{cuenta_nombre}%"))
            .first()
        )
    if not cuenta:
        cuenta = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="El usuario no tiene ninguna cuenta creada")

    resultado = _clasificar(db, usuario_id, descripcion)
    categoria = resultado["categoria"] if resultado else "Otros"

    movimiento = Movimiento(
        usuario_id=usuario_id,
        cuenta_id=cuenta.id,
        descripcion=descripcion,
        categoria=categoria,
        tipo=tipo,
        monto=monto,
        fecha=ahora_co(),
        fuente=fuente,
    )
    db.add(movimiento)
    cuenta = bloquear_cuenta(db, cuenta.id)
    cuenta.saldo += _delta_saldo(tipo, monto)

    db.commit()
    db.refresh(movimiento)
    registrar_actividad_hoy(db, usuario_id)
    return movimiento


@router.post("/rapido", response_model=MovimientoOut)
def crear_movimiento_rapido(
    data: MovimientoRapidoCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user_by_api_key),
):
    """Registro sin login, autenticado por API key (header X-Api-Key).
    Pensado para Atajos de iOS / Scriptable / Tasker / reglas de correo."""
    return _registrar_movimiento_rapido(
        db, usuario.id, data.monto, data.tipo, data.descripcion, data.cuenta, data.fuente
    )


@router.post("/rapido-voz", response_model=MovimientoPorVozResponse)
def crear_movimiento_por_voz(
    data: MovimientoPorVozCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user_by_api_key),
):
    """Registro por voz/Siri: recibe la frase dicha tal cual (ej. 'gasté 20 mil
    en el almuerzo') y la interpreta sin IA, con patrones de español colombiano.
    Si no logra extraer un monto, devuelve entendido=false para que el Atajo
    le pida al usuario repetir o abrir la app."""
    interpretado = interpretar_frase(data.texto)
    if not interpretado:
        return MovimientoPorVozResponse(
            ok=True,
            entendido=False,
            movimiento=None,
            mensaje="No logré entender el monto. Intenta decir algo como 'gasté 20 mil en el almuerzo'.",
        )

    movimiento = _registrar_movimiento_rapido(
        db,
        usuario.id,
        interpretado["monto"],
        interpretado["tipo"],
        interpretado["descripcion"],
        data.cuenta,
        "voz",
    )
    return MovimientoPorVozResponse(
        ok=True,
        entendido=True,
        movimiento=movimiento,
        mensaje=f"Registrado: {interpretado['descripcion']}",
    )


@router.post("/clasificar", response_model=ClasificarResponse)
def clasificar_movimiento(
    data: ClasificarRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    resultado = _clasificar(db, usuario.id, data.descripcion)

    if resultado:
        return ClasificarResponse(
            categoria=resultado["categoria"],
            tipo=resultado["tipo"],
            confianza=resultado["confianza"],
            fuente=resultado["fuente"],
        )

    return ClasificarResponse(categoria="Otros", tipo="expense", confianza=0, fuente="default")


def _movimientos_categorizados(db: Session, usuario_id: str) -> list[dict]:
    movs = (
        db.query(Movimiento)
        .filter(Movimiento.usuario_id == usuario_id, Movimiento.categoria != "Otros")
        .all()
    )
    return [{"descripcion": m.descripcion, "categoria": m.categoria, "tipo": m.tipo} for m in movs]


def _clasificar(db: Session, usuario_id: str, descripcion: str) -> dict | None:
    """Reglas del usuario primero (control explícito), modelo aprendido después."""
    reglas = (
        db.query(ReglaCategoria)
        .filter(ReglaCategoria.usuario_id == usuario_id)
        .order_by(ReglaCategoria.prioridad.desc())
        .all()
    )
    resultado = aplicar_reglas(descripcion, reglas)
    if resultado:
        return resultado

    historial = _movimientos_categorizados(db, usuario_id)
    modelo = build_model(historial)
    resultado = classify(descripcion, modelo)
    if resultado:
        return resultado

    return clasificar_por_diccionario(descripcion)
