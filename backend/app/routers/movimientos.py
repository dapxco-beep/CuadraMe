import re
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.utiles import ahora_co
from app.auth import UsuarioActual, get_current_user, get_current_user_by_api_key
from sqlalchemy import and_, or_

from app import duplicados as dup
from app import pendientes
from app import subcategorias as subcat
from app import titulo as tit
from app.clave_comercio import clave_comercio, huella_en_descripcion
from app.autocat import (
    ClasificadorUsuario,
    ajustar_a_categorias_usuario,
    aplicar_a_anteriores,
    guardar_regla_aprendida,
    datos_auto,
    movimientos_confirmados,
    origen_de,
    origen_tras_edicion,
    patron_de_comercio,
)
from app.classifier import aplicar_reglas, build_model, classify
from app.comercios_conocidos import clasificar_por_diccionario
from app.compartidos import bloquear_cuenta, cuenta_accesible, cuentas_ids_accesibles, puede_editar_cuenta
from app.contabilidad import CATEGORIA_PAGO_TARJETA, FUENTE_APORTE_META, FUENTE_IMPORTADO_SIN_SALDO, delta_saldo, es_pago_tarjeta
from app.database import get_db
from app.fx import convertir_a_cop
from app.limites import verificar_limite
from app.wallet import (
    FUENTES_POR_CONFIRMAR,
    ORIGEN_ATAJO,
    ORIGEN_CIERRE_APP,
    ORIGEN_WALLET,
    fecha_razonable,
    formato_cop,
    coincide_cuenta,
    mapear_cuenta_ex,
    parse_fecha,
)
from app.models import Categoria, Cuenta, Meta, Movimiento, ReglaCategoria, ReglaTitulo
from app.rachas import registrar_actividad_hoy
from app.schemas import (
    ClasificarRequest,
    ClasificarResponse,
    ConfirmarCategoriasRequest,
    EliminarMasivoRequest,
    MasivoResponse,
    MoverMasivoRequest,
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

# «Por categorizar» ya NO es «todo lo que la app categorizó sola»: la definición vive en
# app/pendientes.py (Otros, baja confianza o marcado por el usuario) y es la misma para el
# contador de Inicio, el de Movimientos, la lista y los consejos.


def _delta_saldo(tipo: str, monto: float) -> float:
    """Cuánto cambia el saldo por (tipo, monto): income suma, expense resta. Solo un 'transfer'
    heredado sin dirección vale 0; los traslados de la app se resuelven en _delta_de (notas)."""
    if tipo == "income":
        return monto
    if tipo == "expense":
        return -monto
    return 0.0


def _delta_de(mov: Movimiento) -> float:
    """Como _delta_saldo pero respetando los importados 'sin saldo': nunca tocaron
    el saldo al crearse, así que editarlos o borrarlos tampoco debe tocarlo."""
    return delta_saldo(mov)


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
        # Encuentra por el texto del banco Y por el nombre que le puso la persona.
        query = query.filter(or_(
            Movimiento.descripcion.ilike(f"%{q_literal}%", escape="\\"),
            Movimiento.titulo.ilike(f"%{q_literal}%", escape="\\"),
        ))
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
        query = query.filter(pendientes.filtro_ids(db, usuario.id, ids_accesibles))

    filas = query.order_by(Movimiento.fecha.desc()).offset(offset).limit(limit).all()
    pendientes.anotar(db, usuario.id, filas, ids_accesibles)  # por_categorizar: la PWA no repite la regla
    return dup.anotar_canales(db, filas)


@router.get("/por-revisar/conteo")
def conteo_por_revisar(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Cuántos movimientos esperan categoría (definición única en app/pendientes.py): los que
    están en 'Otros', los que la app puso sola con poca confianza y los que marcaste tú. Lo
    categorizado con seguridad por una regla, el aprendizaje o el diccionario NO cuenta; tampoco
    traslados, pagos de tarjeta, ajustes ni comercios que silenciaste. `auto` = baja confianza + marcados."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    c = pendientes.conteo(db, usuario.id, ids_accesibles)
    return {"auto": c["baja"] + c["marcadas"], "otros": c["otros"], "total": c["total"],
            "baja": c["baja"], "marcadas": c["marcadas"], "silenciados": c["silenciados"]}


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
    else:
        # «Confirmar todas» = las N que cuenta el contador (poca confianza o marcadas), no lo que
        # una regla o el diccionario ya categorizó con seguridad.
        q = q.filter(Movimiento.id.in_(
            [m.id for m, _ in pendientes.pendientes(db, usuario.id, ids_accesibles) if m.cat_confirmada is False] or ["-"]))
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

    subcategoria = subcat.normalizar(db, usuario.id, categoria, data.subcategoria)
    mov.cat_origen = origen_tras_edicion(mov.cat_origen, mov.categoria, categoria)
    mov.categoria = categoria
    mov.subcategoria = subcategoria  # otra categoría (o ninguna) = la subcategoría anterior ya no aplica
    mov.cat_confirmada = True
    actualizados = 1
    patron = None
    regla_omitida = None

    if data.aplicar_a_todos:
        origen_regla = (data.patron or "").strip() or mov.descripcion
        r = guardar_regla_aprendida(
            db, usuario.id, origen_regla, categoria, confirmar_peligrosa=data.confirmar_peligrosa,
            subcategoria=subcategoria,
        )
        patron = r["huella"]
        if r["guardada"]:
            actualizados += aplicar_a_anteriores(db, usuario.id, r["huella"], categoria, {mov.id}, subcategoria=subcategoria)
        else:
            regla_omitida = r["motivo"]  # solo este movimiento; la regla pide confirmación

    db.commit()
    return {"ok": True, "actualizados": actualizados, "patron": patron, "regla_omitida": regla_omitida}


# Va antes de "/{movimiento_id}" para que no la confunda con un id.
@router.get("/cuentas-rapido", response_model=list[str])
def cuentas_para_atajo(
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user_by_api_key),
):
    """Nombres de las cuentas del usuario, autenticado por API key, para que un Atajo
    de iPhone las muestre en 'Elegir de la lista' en vez de llevar un nombre fijo.
    Responde una lista simple de textos: Atajos la entiende directo como lista."""
    verificar_limite(f"cuentas-rapido:{usuario.id}", 60, 3600, "Demasiadas consultas seguidas. Intenta en un rato.")
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id).order_by(Cuenta.nombre).all()
    return [c.nombre for c in cuentas]


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
    dup.anotar_canales(db, [mov])
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

    # ¿Ya lo tienes por el atajo, el correo, el extracto...? Se avisa en vez de duplicarlo
    # (otro gasto igual de verdad: se reenvía con confirmar_nuevo=true).
    if data.tipo in ("income", "expense") and not data.confirmar_nuevo:
        pareja = dup.buscar_pareja(db, usuario.id, dup.Cand(
            id="nuevo", origen=dup.ORIGEN_MANUAL, tipo=data.tipo, monto=float(data.monto),
            fecha=data.fecha or ahora_co(), cuentas=frozenset({cuenta.id}), texto=data.descripcion,
            moneda=cuenta.moneda or "COP"))
        if pareja is not None and not pareja.fantasma:
            m = pareja.ref
            raise HTTPException(status_code=409, detail={
                "codigo": "posible_duplicado",
                "mensaje": f"Ya tienes este {'ingreso' if data.tipo == 'income' else 'gasto'} registrado desde "
                           f"{dup.ETIQUETA_CANAL[dup.origen_de_movimiento(m)]}: «{m.descripcion}». "
                           "¿Es otro igual o es el mismo?",
                "movimiento_id": m.id,
                "canal": dup.origen_de_movimiento(m),
            })

    categoria = data.categoria
    auto = datos_auto(None)
    subcategoria = None
    if not categoria:
        resultado = _clasificar(db, usuario.id, data.descripcion)
        categoria = resultado["categoria"] if resultado else "Otros"
        if resultado:
            auto = datos_auto(origen_de(resultado.get("fuente")))
            # Solo si el usuario ya la usó con este comercio (o está en su regla) y todavía existe.
            subcategoria = subcat.existente_o_nada(db, usuario.id, categoria, resultado.get("subcategoria"))
    elif data.subcategoria:
        subcategoria = subcat.normalizar(db, usuario.id, categoria, data.subcategoria)

    movimiento = Movimiento(
        usuario_id=usuario.id,
        cuenta_id=data.cuenta_id,
        descripcion=data.descripcion,
        titulo=tit.titulo_para_nuevo(db, usuario.id, data.descripcion, data.titulo),
        categoria=categoria,
        subcategoria=subcategoria,
        tipo=data.tipo,
        monto=data.monto,
        fecha=data.fecha or ahora_co(),
        notas=data.notas or "",
        fuente="manual",
        **auto,
    )
    db.add(movimiento)
    if data.recordar_titulo and tit.limpiar(data.titulo):
        tit.guardar_regla(db, usuario.id, data.descripcion, data.titulo)
    cuenta.saldo += _delta_saldo(data.tipo, data.monto)
    if data.tipo in ("income", "expense"):
        dup.nuevo_movimiento(db, movimiento, dup.ORIGEN_MANUAL)

    db.commit()
    db.refresh(movimiento)
    registrar_actividad_hoy(db, usuario.id)
    if data.tipo in ("income", "expense"):
        dup.absorber_correos(db, usuario.id)  # los correos de este gasto ya no salen en «Por revisar»
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


@router.post("/{movimiento_id}/pasar-a-efectivo")
def pasar_a_efectivo(
    movimiento_id: str,
    crear_cuenta: bool = Query(False, description="Crear la cuenta Efectivo si la persona no tiene"),
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """«¿Lo pasamos a tu efectivo?»: convierte un retiro de cajero (gasto) en traslado banco ->
    Efectivo, o una consignación en efectivo (ingreso) en traslado Efectivo -> banco. El saldo
    del banco no cambia (ya lo había movido); el Efectivo recibe/entrega la otra pata y el
    movimiento deja de contar como gasto/ingreso (regla única)."""
    from app.efectivo import ICONO_EFECTIVO, NOMBRE_CUENTA_EFECTIVO, sugerencia_efectivo

    ids = cuentas_ids_accesibles(db, usuario.id)
    mov = db.query(Movimiento).filter(Movimiento.id == movimiento_id, Movimiento.cuenta_id.in_(ids)).first()
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    banco = bloquear_cuenta(db, mov.cuenta_id)
    if not banco or not puede_editar_cuenta(db, usuario.id, banco):
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta cuenta")
    if mov.fuente == FUENTE_TRANSFERENCIA or mov.tipo not in ("income", "expense") or banco.tipo == "efectivo":
        raise HTTPException(status_code=400, detail="Este movimiento no se puede pasar a efectivo.")
    if not sugerencia_efectivo(mov.tipo, mov.descripcion):
        raise HTTPException(status_code=400, detail="Este movimiento no parece un retiro ni una consignación.")

    efectivo = (db.query(Cuenta).filter(Cuenta.usuario_id == usuario.id, Cuenta.tipo == "efectivo",
                                        Cuenta.moneda == (banco.moneda or "COP")).order_by(Cuenta.nombre).first())
    if not efectivo:
        if not crear_cuenta:
            raise HTTPException(status_code=409, detail="Aún no tienes una cuenta de efectivo. ¿La creamos?")
        efectivo = Cuenta(usuario_id=usuario.id, nombre=NOMBRE_CUENTA_EFECTIVO, tipo="efectivo", saldo=0,
                          moneda=banco.moneda or "COP", icono=ICONO_EFECTIVO)
        db.add(efectivo)
        db.flush()
    efectivo = bloquear_cuenta(db, efectivo.id)

    sale_del_banco = mov.tipo == "expense"
    grupo = uuid.uuid4().hex
    monto = float(mov.monto or 0)
    # La pata del banco conserva su efecto en saldo: expense -monto == :out, income +monto == :in.
    mov.tipo = "transfer"
    mov.fuente = FUENTE_TRANSFERENCIA
    mov.categoria = "Transferencia"
    mov.notas = f"TRF:{grupo}:{'out' if sale_del_banco else 'in'}"
    mov.descripcion = f"Retiro a {efectivo.nombre}" if sale_del_banco else f"Depósito desde {efectivo.nombre}"
    db.add(Movimiento(
        usuario_id=usuario.id, cuenta_id=efectivo.id, fecha=mov.fecha, tipo="transfer",
        descripcion=f"Retiro desde {banco.nombre}" if sale_del_banco else f"Depósito a {banco.nombre}",
        categoria="Transferencia", monto=monto, fuente=FUENTE_TRANSFERENCIA,
        notas=f"TRF:{grupo}:{'in' if sale_del_banco else 'out'}",
    ))
    efectivo.saldo += monto if sale_del_banco else -monto
    db.commit()
    return {"ok": True, "cuenta_efectivo_id": efectivo.id, "sentido": "retiro" if sale_del_banco else "deposito"}


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

    if mov.fuente == FUENTE_APORTE_META:
        # Decisión simple y segura: editarlo desalinearía la meta (su monto_actual
        # ya sumó este aporte). Para deshacerlo se elimina (eso sí revierte la meta).
        raise HTTPException(
            status_code=400,
            detail="Este movimiento es un aporte a una meta y no se edita: "
                   "elimínalo para devolver el dinero a la cuenta y descontarlo de la meta",
        )

    cambios = {k: v for k, v in data.model_dump(exclude_unset=True).items()
               if v is not None and k not in ("titulo", "recordar_titulo")}

    cuenta_actual = bloquear_cuenta(db, mov.cuenta_id)
    if not cuenta_actual or not puede_editar_cuenta(db, usuario.id, cuenta_actual):
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta cuenta")

    cuenta_nueva = cuenta_actual
    if cambios.get("cuenta_id") and cambios["cuenta_id"] != mov.cuenta_id:
        destino = cuenta_accesible(db, usuario.id, cambios["cuenta_id"])
        if not destino or not puede_editar_cuenta(db, usuario.id, destino):
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        cuenta_nueva = bloquear_cuenta(db, destino.id)

    # Subcategoría: "" la quita; con otra categoría y sin subcategoría nueva, la anterior se limpia.
    sub_pedida = data.subcategoria if "subcategoria" in data.model_fields_set else None
    categoria_final = cambios.get("categoria", mov.categoria)
    if sub_pedida:
        sub_final = subcat.normalizar(db, usuario.id, categoria_final, sub_pedida)
    elif sub_pedida == "" or ("categoria" in cambios and cambios["categoria"] != mov.categoria):
        sub_final = None
    else:
        sub_final = mov.subcategoria
    cuenta_actual.saldo -= _delta_de(mov)
    categoria_previa, origen_previo = mov.categoria, mov.cat_origen
    for campo in ("descripcion", "monto", "tipo", "categoria", "fecha", "notas"):
        if campo in cambios:
            setattr(mov, campo, cambios[campo])
    if "titulo" in data.model_fields_set and data.titulo is not None:
        # Solo cambia el nombre que ve la persona; la descripción del banco no se toca. "" = volver al original.
        mov.titulo = tit.limpiar(data.titulo)
        if data.recordar_titulo:
            if mov.titulo:
                tit.guardar_regla(db, usuario.id, mov.descripcion, mov.titulo)
            else:  # quitó el nombre y pidió olvidarlo para este comercio
                db.query(ReglaTitulo).filter(
                    ReglaTitulo.usuario_id == usuario.id, ReglaTitulo.huella == pendientes.huella_de(mov.descripcion),
                ).delete()
    mov.subcategoria = sub_final
    mov.cuenta_id = cuenta_nueva.id
    cuenta_nueva.saldo += _delta_de(mov)
    if "categoria" in cambios:
        # El usuario eligió la categoría: deja de ser una suposición de la app.
        mov.cat_confirmada = True
        mov.cat_origen = origen_tras_edicion(origen_previo, categoria_previa, mov.categoria)

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
    subcategoria = subcat.normalizar(db, usuario.id, data.categoria, data.subcategoria)
    actualizados = 0
    for mov in movs:
        if mov.cuenta_id not in cuentas_editables:
            continue
        mov.cat_origen = origen_tras_edicion(mov.cat_origen, mov.categoria, data.categoria)
        if mov.categoria != data.categoria or subcategoria:
            mov.subcategoria = subcategoria
        mov.categoria = data.categoria
        mov.cat_confirmada = True
        actualizados += 1

    db.commit()
    return RecategorizarMasivoResponse(ok=True, actualizados=actualizados)


@router.post("/mover-masivo", response_model=MasivoResponse)
def mover_masivo(
    data: MoverMasivoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Pasa varios movimientos a otra cuenta y corrige los saldos de ambas (como editar uno
    por uno, pero en una sola transacción). Se omiten las transferencias internas, los aportes
    a metas y los de una cuenta en otra moneda que la de destino."""
    destino = cuenta_accesible(db, usuario.id, data.cuenta_id)
    if not destino or not puede_editar_cuenta(db, usuario.id, destino):
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    pedidos = set(data.movimiento_ids)
    movs = (
        db.query(Movimiento)
        .filter(Movimiento.id.in_(pedidos), Movimiento.cuenta_id.in_(ids_accesibles))
        .all()
    )
    # Se bloquean todas las cuentas implicadas siempre en el mismo orden (por id).
    cuentas = {cid: bloquear_cuenta(db, cid) for cid in sorted({m.cuenta_id for m in movs} | {destino.id})}
    destino = cuentas[destino.id]
    actualizados = 0
    for mov in movs:
        origen = cuentas.get(mov.cuenta_id)
        if (
            mov.fuente in (FUENTE_TRANSFERENCIA, FUENTE_APORTE_META)
            or mov.cuenta_id == destino.id
            or not origen
            or not puede_editar_cuenta(db, usuario.id, origen)
            or (origen.moneda or "COP") != (destino.moneda or "COP")
        ):
            continue
        origen.saldo -= _delta_de(mov)
        destino.saldo += _delta_de(mov)
        mov.cuenta_id = destino.id
        actualizados += 1
    db.commit()
    return MasivoResponse(ok=True, actualizados=actualizados, omitidos=len(pedidos) - actualizados)


@router.post("/eliminar-masivo", response_model=MasivoResponse)
def eliminar_masivo(
    data: EliminarMasivoRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Elimina varios movimientos y revierte sus saldos (y los aportes a metas) en una sola
    transacción. Las transferencias internas se omiten: se borran de a una porque afectan
    dos cuentas. Si falta permiso sobre alguna cuenta, no se borra nada."""
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    pedidos = set(data.movimiento_ids)
    movs = (
        db.query(Movimiento)
        .filter(Movimiento.id.in_(pedidos), Movimiento.cuenta_id.in_(ids_accesibles))
        .all()
    )
    borrables = sorted((m for m in movs if m.fuente != FUENTE_TRANSFERENCIA), key=lambda m: m.cuenta_id)
    try:
        for mov in borrables:
            dup.descartar_movimiento(db, mov)
            _borrar_normal(db, usuario, mov)
    except HTTPException:
        db.rollback()
        raise
    db.commit()
    return MasivoResponse(ok=True, actualizados=len(borrables), omitidos=len(pedidos) - len(borrables))


@router.get("/similares/conteo")
def conteo_similares(
    descripcion: str = Query(..., min_length=1, max_length=200),
    excluir_id: str | None = None,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Cuántos OTROS movimientos tuyos son del mismo comercio (misma huella): sirve para
    mostrar 'Aplicar a los 12 anteriores' antes de decidir."""
    huella = clave_comercio(descripcion)
    if not huella:
        return {"huella": "", "conteo": 0}
    ids_accesibles = cuentas_ids_accesibles(db, usuario.id)
    movs = (
        db.query(Movimiento.id, Movimiento.descripcion)
        .filter(
            Movimiento.cuenta_id.in_(ids_accesibles),
            Movimiento.tipo != "transfer",
            Movimiento.fuente != FUENTE_TRANSFERENCIA,
        )
        .all()
    )
    n = sum(1 for i, d in movs if i != excluir_id and huella_en_descripcion(huella, d or ""))
    return {"huella": huella, "conteo": n}


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

    dup.descartar_movimiento(db, mov)  # el correo/extracto equivalente no lo resucita
    _borrar_normal(db, usuario, mov)
    db.commit()
    return {"ok": True}


def _borrar_normal(db: Session, usuario: UsuarioActual, mov: Movimiento) -> None:
    """Borra un movimiento común y revierte su efecto en la cuenta (y en la meta si era un
    aporte). Sin commit: quien llama decide cuándo confirmar."""
    # bloquear_cuenta relee la fila (populate_existing): sin este flush, al borrar varios de la
    # misma cuenta seguidos se perdería el ajuste de saldo pendiente del anterior.
    db.flush()
    cuenta = bloquear_cuenta(db, mov.cuenta_id)
    if cuenta and not puede_editar_cuenta(db, usuario.id, cuenta):
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta cuenta")

    if cuenta:
        cuenta.saldo -= _delta_de(mov)

    if mov.fuente == FUENTE_APORTE_META and (mov.notas or "").startswith("META:"):
        # Revierte el aporte: el dinero vuelve a la cuenta (línea de arriba) y se
        # descuenta de la meta (sin bajar de 0). El cron no re-aporta este mes porque
        # la meta conserva su marca de "ya aportado" (borrarlo es decisión del usuario).
        meta = (
            db.query(Meta)
            .filter(Meta.id == mov.notas[5:], Meta.usuario_id == mov.usuario_id)
            .with_for_update()
            .populate_existing()
            .first()
        )
        if meta:
            meta.monto_actual = max(0.0, (meta.monto_actual or 0) - mov.monto)

    db.delete(mov)


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
        notas = p.notas or ""
        if notas.endswith(":out"):
            sale = True
        elif notas.endswith(":in"):
            sale = False
        elif p.tipo in ("income", "expense"):
            # Transferencia antigua sin notas 'TRF:': el tipo dice hacia dónde movió el saldo
            # (expense = salió de esta cuenta; income = entró). Solo se borra esta pata.
            sale = p.tipo == "expense"
        else:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Esta transferencia antigua no se puede borrar automáticamente: "
                       "ajusta el saldo de la cuenta a mano y deja el movimiento como está.",
            )
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
    empate_out: list | None = None,
    id_transaccion: str | None = None,
    absorbido_out: list | None = None,
) -> tuple[Movimiento, Cuenta, bool]:
    """Crea el movimiento de un registro automático y devuelve (movimiento,
    cuenta, duplicado).

    - La cuenta sale del alias/nombre de la tarjeta (ver wallet.mapear_cuenta_ex). Si el banco
      tiene varias cuentas (débito y crédito) el tipo que insinúa la tarjeta desempata; si de
      verdad no hay forma, se registra en la de uso más reciente (el movimiento queda "por
      confirmar", así que no se pierde) y `empate_out` recibe las candidatas para avisar.
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
    # Uso reciente por cuenta: solo sirve para desempatar entre cuentas del mismo banco
    # (p. ej. 'Nu Colombia' ahorros y 'Nu Tarjeta' crédito) cuando el Wallet no dio pistas.
    ultimo_uso = dict(
        db.query(Movimiento.cuenta_id, func.max(Movimiento.fecha))
        .filter(Movimiento.usuario_id == usuario_id)
        .group_by(Movimiento.cuenta_id)
        .all()
    ) if len(cuentas) > 1 else None
    cuenta, _como, empate = mapear_cuenta_ex(cuentas, tarjeta, cuenta_nombre, moneda, ultimo_uso)
    if empate and empate_out is not None:
        empate_out.extend(empate)
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

    es_cierre = origen_auto == ORIGEN_CIERRE_APP
    nota_usuario = (descripcion or "").strip()
    if es_cierre and not nota_usuario:
        descripcion = f"Movimiento en {cuenta.nombre}"
    # Huella de ESTE disparo del atajo: un reintento (o el mismo aviso llegando otra vez) nunca crea otro.
    huella = dup.huella_atajo(cuenta.id, tipo, monto, descripcion, momento, id_transaccion)
    if detectar_duplicado:
        previa = dup.buscar_huella(db, usuario_id, huella, (dup.ESTADO_VIGENTE,))
        if previa is not None and previa.movimiento_id:
            ya = db.query(Movimiento).filter(Movimiento.id == previa.movimiento_id).first()
            # Con id de transacción explícito, el mismo id SIEMPRE es el mismo pago. Con la huella por
            # minuto, solo si el movimiento sigue siendo de ese momento (como el reintento de ±2 min).
            if ya is not None and (huella.startswith("tx:") or dup.origen_de_movimiento(ya) != dup.ORIGEN_ATAJO
                                   or abs(ya.fecha - momento) <= timedelta(minutes=2)):
                cuenta_ya = db.query(Cuenta).filter(Cuenta.id == ya.cuenta_id).first() or cuenta
                return ya, cuenta_ya, True
        # Cierre de app: el Atajo no trae comercio, así que un reintento se
        # reconoce por monto+cuenta+tipo en ±1 min. Wallet/atajo: ±2 min y mismo comercio.
        ventana = timedelta(minutes=1 if es_cierre else 2)
        filtros = [
            Movimiento.cuenta_id == cuenta.id,
            Movimiento.tipo == tipo,
            Movimiento.monto == monto,
            Movimiento.fecha >= momento - ventana,
            Movimiento.fecha <= momento + ventana,
        ]
        if es_cierre:
            filtros.append(Movimiento.fuente == "cierre_app")
        else:
            filtros.append(func.lower(Movimiento.descripcion) == descripcion.lower())
        existente = db.query(Movimiento).filter(*filtros).first()
        if existente:
            if dup.origen_de_movimiento(existente) != dup.ORIGEN_ATAJO and not es_cierre:
                # No es un reintento del atajo: es el mismo gasto que ya llegó por otro canal. Se confirma.
                dup.confirmar_por_canal(db, existente, dup.ORIGEN_ATAJO, huella, descripcion=descripcion,
                                        fecha=momento, hora_real=True)
                db.commit()
                db.refresh(existente)
                if absorbido_out is not None:
                    absorbido_out.append(dup.origen_de_movimiento(existente))
            return existente, cuenta, True

        # ¿Ya lo tienes por otro canal (escrito a mano, el correo del banco, el extracto)? Entonces el
        # atajo lo CONFIRMA y lo completa en vez de crear otro. El cierre de app no trae comercio:
        # solo se deduplica contra sí mismo (arriba) y lo cruza luego el extracto.
        if not es_cierre:
            ent = dup.Cand(
                id="atajo", origen=dup.ORIGEN_ATAJO, tipo=tipo, monto=float(monto), fecha=momento,
                cuentas=frozenset({cuenta.id} | {c.id for c in empate}), texto=descripcion or "",
                moneda=moneda_cuenta, con_hora=True)
            pareja = dup.buscar_pareja(db, usuario_id, ent)
            if pareja is not None and not pareja.fantasma:
                ya = pareja.ref
                dup.confirmar_por_canal(db, ya, dup.ORIGEN_ATAJO, huella, descripcion=descripcion,
                                        fecha=momento, hora_real=True)
                db.commit()
                db.refresh(ya)
                if absorbido_out is not None:
                    absorbido_out.append(dup.origen_de_movimiento(ya))
                cuenta_ya = db.query(Cuenta).filter(Cuenta.id == ya.cuenta_id).first() or cuenta
                return ya, cuenta_ya, True

    # Sin nota no hay nada que clasificar: el cierre de app queda en 'Otros'.
    resultado = None if (es_cierre and not nota_usuario) else _clasificar(db, usuario_id, descripcion)
    categoria = resultado["categoria"] if resultado else "Otros"
    if origen_auto:
        auto = {"cat_origen": origen_auto, "cat_confirmada": False}
    else:
        auto = datos_auto(origen_de(resultado.get("fuente")) if resultado else None)
    subcategoria = subcat.existente_o_nada(db, usuario_id, categoria, resultado.get("subcategoria")) if resultado else None

    movimiento = Movimiento(
        usuario_id=usuario_id,
        cuenta_id=cuenta.id,
        descripcion=descripcion,
        titulo=tit.recordado(db, usuario_id, descripcion),
        categoria=categoria,
        subcategoria=subcategoria,
        tipo=tipo,
        monto=monto,
        fecha=momento,
        notas=notas,
        fuente=fuente,
        **auto,
    )
    db.add(movimiento)
    cuenta.saldo += _delta_saldo(tipo, monto)
    dup.nuevo_movimiento(db, movimiento, dup.ORIGEN_ATAJO, huella)

    db.commit()
    db.refresh(movimiento)
    registrar_actividad_hoy(db, usuario_id)
    dup.absorber_correos(db, usuario_id)  # los correos de esta compra ya no salen en «Por revisar»
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
    es_cierre = data.fuente == "cierre_app" and not data.comercio and not data.tarjeta
    es_wallet = not es_cierre and (bool(data.comercio or data.tarjeta) or data.fuente in ("wallet", "apple_pay", "google_pay"))
    descripcion = data.comercio or data.descripcion  # en cierre_app puede ser None: la nota es opcional
    fuente = data.fuente if data.fuente in ("apple_pay", "google_pay") else ("wallet" if es_wallet else data.fuente)
    origen = ORIGEN_CIERRE_APP if es_cierre else (ORIGEN_WALLET if es_wallet else ORIGEN_ATAJO)
    empate: list = []
    absorbido: list = []
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
        origen_auto=origen,
        detectar_duplicado=True,
        empate_out=empate,
        id_transaccion=data.id_transaccion,
        absorbido_out=absorbido,
    )
    signo = "Ingreso" if mov.tipo == "income" else "Gasto"
    if duplicado and absorbido:
        # Ya estaba por otro canal: el atajo lo confirmó, no se creó otro.
        mensaje = (f"Ya lo tenías registrado desde {dup.ETIQUETA_CANAL[absorbido[0]]}: {signo.lower()} de "
                   f"{formato_cop(mov.monto)} en {mov.descripcion}. No lo dupliqué.")
    elif duplicado:
        mensaje = f"Ya lo tenías: {signo.lower()} de {formato_cop(mov.monto)} en {mov.descripcion}."
    else:
        mensaje = f"{signo} de {formato_cop(mov.monto)} en {mov.descripcion} ({cuenta.nombre}). Confírmalo en CuadraMe."
    if empate and not duplicado:
        otras = [c for c in empate if c.id != cuenta.id]
        mensaje += (
            f" Ojo: tu banco tiene varias cuentas ({', '.join(c.nombre for c in empate)}) y no supe cuál es "
            f"esta tarjeta, así que lo guardé en {cuenta.nombre}"
            + (f" (la que más usas). Si era {' o '.join(c.nombre for c in otras)}, corrígelo al confirmar. " if otras else ". ")
            + "Para que no se confunda: en CuadraMe, Cuentas > editar cuenta > «Alias de la tarjeta», pon los últimos 4 dígitos "
            "o el nombre que muestra Wallet."
        )
    # Si el Atajo pidió una cuenta que no existe, el movimiento cayó en otra: se dice,
    # para que no se registre en silencio en la cuenta equivocada.
    if data.cuenta and not data.tarjeta and not coincide_cuenta(cuenta, data.cuenta):
        mensaje += (
            f" Ojo: no encontré una cuenta que se llame «{data.cuenta}», así que lo guardé en {cuenta.nombre}. "
            "Crea esa cuenta en CuadraMe o corrige el texto de la automatización."
        )
    base = MovimientoOut.model_validate(mov, from_attributes=True).model_dump()
    return MovimientoRapidoOut(
        **base,
        mensaje=mensaje,
        duplicado=duplicado,
        por_confirmar=mov.cat_confirmada is False,
        cuenta_nombre=cuenta.nombre,
        ya_estaba_por=absorbido[0] if absorbido else None,
    )


@router.post("/rapido-prueba", response_model=MovimientoRapidoOut)
def crear_movimiento_rapido_prueba(
    data: MovimientoRapidoCreate,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Gemelo de /rapido autenticado con la SESIÓN (no con la clave API): permite probar la
    conexión desde la app aunque la clave guardada ya no se pueda leer (solo se guarda su hash)."""
    return crear_movimiento_rapido(data, db, usuario)


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
            tipo=resultado["tipo"] or "expense",  # una regla sin tipo no fuerza ninguno
            confianza=resultado["confianza"],
            fuente=resultado["fuente"],
        )

    return ClasificarResponse(categoria="Otros", tipo="expense", confianza=0, fuente="default")


def _movimientos_categorizados(db: Session, usuario_id: str) -> list[dict]:
    # Solo lo confirmado por el usuario alimenta el aprendizaje (ver autocat).
    return movimientos_confirmados(db, usuario_id)


def _clasificar(db: Session, usuario_id: str, descripcion: str) -> dict | None:
    """Reglas del usuario > modelo aprendido > palabras clave (ver autocat.ClasificadorUsuario).
    El resultado incluye la 'razon' que se le muestra al usuario."""
    return ClasificadorUsuario(db, usuario_id).clasificar(descripcion)
