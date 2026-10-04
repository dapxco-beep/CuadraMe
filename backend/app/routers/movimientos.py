import re
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user, get_current_user_by_api_key
from sqlalchemy import and_, or_

from app.autocat import (
    ajustar_a_categorias_usuario,
    datos_auto,
    movimientos_confirmados,
    origen_de,
    patron_de_comercio,
)
from app.classifier import aplicar_reglas, build_model, classify
from app.comercios_conocidos import clasificar_por_diccionario
from app.compartidos import bloquear_cuenta, cuenta_accesible, cuentas_ids_accesibles, puede_editar_cuenta
from app.contabilidad import CATEGORIA_PAGO_TARJETA, es_pago_tarjeta
from app.database import get_db
from app.fx import convertir_a_cop
from app.limites import verificar_limite
from app.wallet import (
    FUENTES_POR_CONFIRMAR,
    ORIGEN_ATAJO,
    ORIGEN_WALLET,
    fecha_razonable,
    formato_cop,
    mapear_cuenta,
    parse_fecha,
)
from app.models import Categoria, Cuenta, Movimiento, ReglaCategoria
from app.rachas import registrar_actividad_hoy
from app.schemas import (
    ClasificarRequest,
    ClasificarResponse,
    ConfirmarCategoriasRequest,
    MovimientoCreate,
    MovimientoOut,
    MovimientoPorVozCreate,
    MovimientoPorVozResponse,
    MovimientoRapidoCreate,
    MovimientoRapidoOut,
    MovimientoUpdate,
    RecategorizarComercioRequest,
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

# "Por revisar": categorizados automáticamente sin confirmar, o en 'Otros'.
_PENDIENTE_REVISION = or_(
    Movimiento.cat_confirmada.is_(False),
    and_(Movimiento.categoria == "Otros", Movimiento.fuente != FUENTE_TRANSFERENCIA),
)


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
    por_revisar: bool = False,
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
    if por_revisar:
        query = query.filter(_PENDIENTE_REVISION)

    return query.order_by(Movimiento.fecha.desc()).offset(offset).limit(limit).all()


@router.get("/por-revisar/conteo")
def conteo_por_revisar(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Cuántos movimientos esperan revisión: los que la app categorizó sola y
    nadie confirmó, más los que quedaron en 'Otros'. Los traslados propios no cuentan."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    base = db.query(Movimiento).filter(
        Movimiento.cuenta_id.in_(ids_accesibles), Movimiento.fuente != FUENTE_TRANSFERENCIA
    )
    auto = base.filter(Movimiento.cat_confirmada.is_(False)).count()
    otros = base.filter(Movimiento.categoria == "Otros", Movimiento.cat_confirmada.isnot(False)).count()
    return {"auto": auto, "otros": otros, "total": auto + otros}


@router.get("/por-confirmar", response_model=list[MovimientoOut])
def listar_por_confirmar(
    dias: int = Query(14, ge=1, le=60),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Bandeja '¿son tuyos?': movimientos que llegaron solos (Wallet, atajos,
    SMS) y el usuario aún no confirmó. Ya cuentan en los saldos; confirmar los
    deja como están y descartar (DELETE) revierte el saldo."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    desde = ahora_co() - timedelta(days=dias)
    return (
        db.query(Movimiento)
        .filter(
            Movimiento.cuenta_id.in_(ids_accesibles),
            Movimiento.cat_confirmada.is_(False),
            Movimiento.fuente.in_(FUENTES_POR_CONFIRMAR),
            Movimiento.fecha >= desde,
        )
        .order_by(Movimiento.fecha.desc())
        .limit(100)
        .all()
    )


@router.post("/confirmar-categorias")
def confirmar_categorias(
    data: ConfirmarCategoriasRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Confirma con un toque la categoría que puso la app (uno, varios o todos
    los pendientes). No cambia la categoría: solo deja de ser 'Auto'."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    q = db.query(Movimiento).filter(
        Movimiento.cuenta_id.in_(ids_accesibles), Movimiento.cat_confirmada.is_(False)
    )
    if data.movimiento_ids is not None:
        q = q.filter(Movimiento.id.in_(data.movimiento_ids))
    n = q.update({"cat_confirmada": True}, synchronize_session=False)
    db.commit()
    return {"ok": True, "confirmados": n}


@router.post("/{movimiento_id}/recategorizar-comercio")
def recategorizar_comercio(
    movimiento_id: str,
    data: RecategorizarComercioRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Cambia la categoría de este movimiento y, si `aplicar_a_todos`, crea una
    regla de categoría para el comercio y la aplica a todos los movimientos tuyos
    que lo contengan (los confirma). Las compras futuras de ese comercio quedan
    categorizadas 'por tu regla'."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    mov = (
        db.query(Movimiento)
        .filter(Movimiento.id == movimiento_id, Movimiento.cuenta_id.in_(ids_accesibles))
        .first()
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    cuenta = cuenta_accesible(db, usuario.id, mov.cuenta_id)
    if not cuenta or not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta cuenta")

    categoria = data.categoria.strip()
    existe = db.query(Categoria.id).filter(Categoria.usuario_id == usuario.id).first()
    if existe and not db.query(Categoria.id).filter(
        Categoria.usuario_id == usuario.id, Categoria.nombre == categoria
    ).first():
        raise HTTPException(status_code=400, detail="Esa categoría no existe en tu lista")

    mov.categoria = categoria
    mov.cat_confirmada = True
    mov.cat_origen = None
    actualizados = 1
    patron = None

    if data.aplicar_a_todos:
        patron = (data.patron or "").strip() or patron_de_comercio(mov.descripcion)
        if patron.lower() not in mov.descripcion.lower():
            raise HTTPException(status_code=400, detail="El comercio debe aparecer en la descripción del movimiento")
        regla = (
            db.query(ReglaCategoria)
            .filter(ReglaCategoria.usuario_id == usuario.id, ReglaCategoria.patron.ilike(patron))
            .first()
        )
        if regla:
            regla.categoria = categoria
        else:
            db.add(ReglaCategoria(usuario_id=usuario.id, patron=patron, categoria=categoria, tipo=None, prioridad=0))
        # Escapa % y _ para que el patrón se trate como texto literal.
        literal = patron.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        otros = (
            db.query(Movimiento)
            .filter(
                Movimiento.cuenta_id.in_(ids_accesibles),
                Movimiento.id != mov.id,
                Movimiento.fuente != FUENTE_TRANSFERENCIA,
                Movimiento.tipo != "transfer",
                Movimiento.descripcion.ilike(f"%{literal}%", escape="\\"),
            )
            .all()
        )
        for o in otros:
            c = cuenta_accesible(db, usuario.id, o.cuenta_id)
            if c and puede_editar_cuenta(db, usuario.id, c):
                o.categoria = categoria
                o.cat_confirmada = True
                o.cat_origen = None
                actualizados += 1

    db.commit()
    return {"ok": True, "actualizados": actualizados, "patron": patron}


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
    auto = datos_auto(None)
    if not categoria:
        resultado = _clasificar(db, usuario.id, data.descripcion)
        categoria = resultado["categoria"] if resultado else "Otros"
        if resultado:
            auto = datos_auto(origen_de(resultado.get("fuente")))

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
        **auto,
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
    if "categoria" in cambios:
        # El usuario eligió la categoría: deja de ser una suposición de la app.
        mov.cat_confirmada = True
        mov.cat_origen = None

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
        mov.cat_confirmada = True
        mov.cat_origen = None
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
    *,
    tarjeta: str | None = None,
    fecha: str | None = None,
    moneda: str | None = None,
    origen_auto: str | None = None,
    detectar_duplicado: bool = False,
) -> tuple[Movimiento, Cuenta, bool]:
    """Crea el movimiento de un registro automático y devuelve (movimiento,
    cuenta, duplicado).

    - La cuenta sale del alias/nombre de la tarjeta (ver wallet.mapear_cuenta).
    - Con `origen_auto` ('wallet' | 'atajo') el movimiento se crea de inmediato
      (los saldos quedan bien) pero marcado "por confirmar", con el mismo
      mecanismo de la categorización automática (cat_confirmada=False).
    - Con `detectar_duplicado`, el mismo comercio+monto+cuenta dentro de ±2
      minutos devuelve el movimiento ya existente en vez de crear otro: así
      un reintento del Atajo no cuenta el pago dos veces."""
    # Estos endpoints se autentican solo con API key: se limita para frenar
    # tanto abusos como un atajo mal configurado que se quede en bucle.
    verificar_limite(f"rapido:{usuario_id}", 120, 3600, "Demasiados registros rápidos seguidos. Intenta en un rato.")
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre).all()
    cuenta, _como = mapear_cuenta(cuentas, tarjeta, cuenta_nombre, moneda)
    if not cuenta:
        raise HTTPException(status_code=404, detail="El usuario no tiene ninguna cuenta creada")

    cuenta = bloquear_cuenta(db, cuenta.id)  # serializa reintentos simultáneos del mismo pago
    ahora = ahora_co()
    momento = fecha_razonable(parse_fecha(fecha), ahora)

    notas = ""
    if tarjeta:
        notas = f"Tarjeta: {tarjeta[:60]}"
    moneda_orig = re.sub(r"[^A-Z]", "", (moneda or "").upper())[:3]
    moneda_cuenta = (cuenta.moneda or "COP").upper()
    if moneda_orig and moneda_orig != moneda_cuenta:
        notas = (notas + " · " if notas else "") + f"Original: {monto:g} {moneda_orig}"
        if moneda_cuenta == "COP":
            monto = round(convertir_a_cop(monto, moneda_orig), 2)

    if detectar_duplicado:
        ventana = timedelta(minutes=2)
        existente = (
            db.query(Movimiento)
            .filter(
                Movimiento.cuenta_id == cuenta.id,
                Movimiento.tipo == tipo,
                Movimiento.monto == monto,
                func.lower(Movimiento.descripcion) == descripcion.lower(),
                Movimiento.fecha >= momento - ventana,
                Movimiento.fecha <= momento + ventana,
            )
            .first()
        )
        if existente:
            return existente, cuenta, True

    resultado = _clasificar(db, usuario_id, descripcion)
    categoria = resultado["categoria"] if resultado else "Otros"
    if origen_auto:
        auto = {"cat_origen": origen_auto, "cat_confirmada": False}
    else:
        auto = datos_auto(origen_de(resultado.get("fuente")) if resultado else None)

    movimiento = Movimiento(
        usuario_id=usuario_id,
        cuenta_id=cuenta.id,
        descripcion=descripcion,
        categoria=categoria,
        tipo=tipo,
        monto=monto,
        fecha=momento,
        notas=notas,
        fuente=fuente,
        **auto,
    )
    db.add(movimiento)
    cuenta.saldo += _delta_saldo(tipo, monto)

    db.commit()
    db.refresh(movimiento)
    registrar_actividad_hoy(db, usuario_id)
    return movimiento, cuenta, False


@router.post("/rapido", response_model=MovimientoRapidoOut)
def crear_movimiento_rapido(
    data: MovimientoRapidoCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user_by_api_key),
):
    """Registro sin login, autenticado por API key (header X-Api-Key).
    Pensado para el disparador 'Transacción' de Atajos de iOS (Apple Wallet),
    Tasker y reglas de correo. El movimiento se crea al instante pero queda
    'por confirmar': la app le pregunta al usuario si es suyo. Un reintento del
    mismo pago (±2 min) responde 200 con el movimiento que ya existía."""
    es_wallet = bool(data.comercio or data.tarjeta) or data.fuente in ("wallet", "apple_pay", "google_pay")
    descripcion = data.comercio or data.descripcion
    fuente = data.fuente if data.fuente in ("apple_pay", "google_pay") else ("wallet" if es_wallet else data.fuente)
    mov, cuenta, duplicado = _registrar_movimiento_rapido(
        db,
        usuario.id,
        data.monto,
        data.tipo,
        descripcion,
        data.cuenta,
        fuente,
        tarjeta=data.tarjeta,
        fecha=data.fecha,
        moneda=data.moneda,
        origen_auto=ORIGEN_WALLET if es_wallet else ORIGEN_ATAJO,
        detectar_duplicado=True,
    )
    signo = "Ingreso" if mov.tipo == "income" else "Gasto"
    if duplicado:
        mensaje = f"Ya lo tenías: {signo.lower()} de {formato_cop(mov.monto)} en {mov.descripcion}."
    else:
        mensaje = f"{signo} de {formato_cop(mov.monto)} en {mov.descripcion} ({cuenta.nombre}). Confírmalo en CuadraMe."
    base = MovimientoOut.model_validate(mov, from_attributes=True).model_dump()
    return MovimientoRapidoOut(
        **base,
        mensaje=mensaje,
        duplicado=duplicado,
        por_confirmar=mov.cat_confirmada is False,
        cuenta_nombre=cuenta.nombre,
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

    movimiento, _cuenta, _dup = _registrar_movimiento_rapido(
        db,
        usuario.id,
        interpretado["monto"],
        interpretado["tipo"],
        interpretado["descripcion"],
        data.cuenta,
        "voz",
        tarjeta=data.tarjeta,
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
    # Solo lo confirmado por el usuario alimenta el aprendizaje (ver autocat).
    return movimientos_confirmados(db, usuario_id)


def _clasificar(db: Session, usuario_id: str, descripcion: str) -> dict | None:
    """Reglas del usuario primero (control explícito), modelo aprendido después."""
    if es_pago_tarjeta(descripcion):
        # El pago de una tarjeta no es un gasto (las compras ya se contaron).
        return {"categoria": CATEGORIA_PAGO_TARJETA, "tipo": "expense", "confianza": 1.0, "fuente": "regla_tarjeta"}
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

    resultado = clasificar_por_diccionario(descripcion)
    if resultado:
        # Si el usuario renombró/ocultó la categoría base que sugiere el
        # diccionario, no se crea un movimiento huérfano.
        resultado = {**resultado, "categoria": ajustar_a_categorias_usuario(db, usuario_id, resultado["categoria"])}
    return resultado
