"""
CuadraMe AI: asistente financiero que conoce los datos del usuario y propone
acciones. Es un router aislado (no modifica /insights).

Flujo de seguridad:
  1. /asistente/mensaje NUNCA escribe en la base: solo responde o PROPONE.
  2. Las acciones (registrar movimiento, crear meta) se ejecutan únicamente en
     /asistente/confirmar/*, que el usuario dispara con un toque explícito.
  3. Límites: por hora (memoria) y por día (tabla `uso_asistente`, solo
     contador) — todo mensaje cuenta por hora; solo los que llaman a la IA
     cuentan por día.
  4. Errores genéricos al cliente; nunca se registra el texto de la conversación.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import asistente as ia
from app import asistente_calc as calc
from app.asistente_datos import cargar_datos, contexto_ia, fuentes_de
from app.auth import UsuarioActual, get_current_user
from app.database import get_db
from app.limites import verificar_limite
from app.models import Movimiento
from app.models_asistente import UsoAsistente
from app.routers import metas as metas_router
from app.routers.movimientos import _clasificar, crear_movimiento
from app.schemas import MetaCreate, MovimientoCreate
from app.utiles import ahora_co

logger = logging.getLogger("cuadrame.asistente")

router = APIRouter(prefix="/asistente", tags=["asistente"])

LIMITE_HORA = 30       # mensajes por hora (cualquier tipo)
LIMITE_DIA_IA = 60     # mensajes que llaman a la IA por día
ERROR_GENERICO = "No pude procesar eso ahora. Intenta de nuevo en un momento."


class MensajeRequest(BaseModel):
    texto: str = Field(min_length=1, max_length=500)


class ConfirmarMovimiento(BaseModel):
    cuenta_id: str
    descripcion: str = Field(min_length=1, max_length=120)
    monto: float = Field(gt=0, le=10_000_000_000)
    tipo: str = Field(pattern="^(income|expense)$")
    categoria: str | None = Field(default=None, max_length=60)
    fecha: datetime | None = None


class ConfirmarPlan(BaseModel):
    """Meta creada a partir de un plan aceptado. El aporte automático solo se
    activa si el usuario eligió una cuenta de origen."""
    nombre: str = Field(min_length=1, max_length=80)
    monto_objetivo: float = Field(gt=0, le=10_000_000_000)
    fecha_objetivo: datetime | None = None
    aporte_mensual: float | None = Field(default=None, gt=0)
    cuenta_origen_id: str | None = None
    descripcion: str = Field(default="", max_length=300)


# ── límites ────────────────────────────────────────────────────────

def _consumir_cupo_ia(db: Session, usuario_id: str, hoy: datetime) -> None:
    dia = hoy.strftime("%Y-%m-%d")
    fila = db.query(UsoAsistente).filter(UsoAsistente.usuario_id == usuario_id, UsoAsistente.dia == dia).first()
    if fila and fila.cantidad >= LIMITE_DIA_IA:
        raise HTTPException(status_code=429, detail="Llegaste al límite diario del asistente. Vuelve mañana.")
    if fila:
        fila.cantidad += 1
    else:
        db.add(UsoAsistente(usuario_id=usuario_id, dia=dia, cantidad=1))
    db.commit()


# ── helpers ────────────────────────────────────────────────────────

def _ctx_calculo(d: dict) -> dict:
    return {k: d[k] for k in ("saldo_liquido", "recurrentes_pendientes", "cuotas_pendientes", "aportes_metas",
                              "ingreso_mensual", "gasto_mensual")}


def _oportunidades(d: dict) -> list[dict]:
    """Anomalías y oportunidades, todas deterministas."""
    from app.insights import detectar_anomalias

    hoy = d["hoy"]
    salida = []
    for a in detectar_anomalias(d["movs"])[:3]:
        salida.append({
            "tipo": "anomalia",
            "titulo": f"{a['categoria']} va {a['variacion_pct']} % por encima de tu promedio",
            "detalle": f"Este mes llevas {ia.cop(a['monto_actual'])} y tu promedio es {ia.cop(a['promedio_historico'])}.",
        })
    for g in calc.gastos_atipicos(d["movs"], hoy.year, hoy.month)[:2]:
        salida.append({
            "tipo": "gasto_atipico",
            "titulo": f"Gasto grande en {g['categoria']}: {ia.cop(g['monto'])}",
            "detalle": f"Es {g['veces']} veces lo habitual en esa categoría ({ia.cop(g['mediana_categoria'])}).",
        })
    subs = calc.suscripciones_anuales(d["recurrentes"])
    if subs["items"]:
        top = subs["items"][0]
        salida.append({
            "tipo": "recurrentes",
            "titulo": f"Tus gastos fijos suman {ia.cop(subs['total_anual'])} al año",
            "detalle": f"El mayor es {top['nombre']} ({ia.cop(top['anual'])} al año). Revisa si todos siguen valiendo la pena.",
        })
    return salida


def _responder_rapida(rid: str, d: dict) -> dict:
    hoy = d["hoy"]
    if rid == "gasto_mes":
        filas = calc.gasto_por_categoria(d["movs"], hoy.year, hoy.month)
        if not filas:
            return {"texto": f"Aún no hay gastos registrados en {ia.etiqueta_mes(hoy)}.", "fuentes": fuentes_de(d, {"mov_mes"})}
        total = sum(f["monto"] for f in filas)
        partes = ", ".join(f"{f['categoria']} {ia.cop(f['monto'])} ({f['pct']} %)" for f in filas[:3])
        return {"texto": f"En {ia.etiqueta_mes(hoy)} llevas {ia.cop(total)} en gastos. Lo que más pesa: {partes}.",
                "fuentes": fuentes_de(d, {"mov_mes"}), "calculo": {"categorias": filas[:5], "total": total}}
    if rid == "anomalias":
        ops = [o for o in _oportunidades(d) if o["tipo"] != "recurrentes"]
        if not ops:
            return {"texto": "No veo gastos fuera de lo normal este mes frente a tus meses anteriores.",
                    "fuentes": fuentes_de(d, {"mov_mes", "mov_historial"})}
        return {"texto": " ".join(f"{o['titulo']}. {o['detalle']}" for o in ops),
                "fuentes": fuentes_de(d, {"mov_mes", "mov_historial"})}
    if rid == "suscripciones":
        s = calc.suscripciones_anuales(d["recurrentes"])
        if not s["items"]:
            return {"texto": "No tienes gastos fijos registrados todavía (Más > Recurrentes).", "fuentes": fuentes_de(d, {"recurrentes"})}
        top = ", ".join(f"{i['nombre']} {ia.cop(i['anual'])}" for i in s["items"][:3])
        return {"texto": f"Tus gastos fijos suman {ia.cop(s['total_mensual'])} al mes, o {ia.cop(s['total_anual'])} al año. Los mayores: {top}.",
                "fuentes": fuentes_de(d, {"recurrentes"}), "calculo": s}
    if rid == "disponible":
        disp = calc.disponible_real(_ctx_calculo(d))
        return {"texto": f"Tu dinero realmente disponible hoy es {ia.cop(disp)}: tus cuentas de ahorro y efectivo ({ia.cop(d['saldo_liquido'])}) "
                         f"menos gastos fijos ({ia.cop(d['recurrentes_pendientes'])}), cuotas ({ia.cop(d['cuotas_pendientes'])}) y aportes a metas ({ia.cop(d['aportes_metas'])}) de este mes.",
                "fuentes": fuentes_de(d, {"saldos", "recurrentes", "deudas", "metas"})}
    # ahorro_mes
    neto = d["ingreso_mes_actual"] - d["gasto_mes_actual"]
    signo = "ahorrado" if neto >= 0 else "gastado de más"
    return {"texto": f"En {ia.etiqueta_mes(hoy)} entraron {ia.cop(d['ingreso_mes_actual'])} y salieron {ia.cop(d['gasto_mes_actual'])}: "
                     f"has {signo} {ia.cop(abs(neto))}.", "fuentes": fuentes_de(d, {"mov_mes"})}


def _numeros_de_contexto(ctx: dict):
    return ctx  # cifras_validas recorre el dict y extrae las hojas numéricas


# ── endpoints ──────────────────────────────────────────────────────

@router.get("/sugerencias")
def sugerencias(db: Session = Depends(get_db), usuario: UsuarioActual = Depends(get_current_user)):
    """Preguntas rápidas + oportunidades detectadas. Sin IA, sin costo."""
    d = cargar_datos(db, usuario.id, ahora_co())
    return {
        "preguntas": ia.PREGUNTAS_RAPIDAS + [
            {"id": "comprar", "texto": "¿Puedo comprar algo de 2 millones?"},
            {"id": "ahorro", "texto": "Quiero ahorrar 12 millones en 12 meses"},
        ],
        "oportunidades": _oportunidades(d),
    }


@router.post("/mensaje")
def mensaje(
    data: MensajeRequest,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    verificar_limite(f"asistente:{usuario.id}", LIMITE_HORA, 3600,
                     "Llegaste al límite de mensajes por hora. Intenta más tarde.")
    hoy = ahora_co()
    try:
        # Texto seguro: sin PINs/claves/tokens y sin delimitadores del prompt
        texto = ia.redactar_secretos(data.texto).replace("<<<", " ").replace(">>>", " ").strip()
        d = cargar_datos(db, usuario.id, hoy)
        intento = ia.detectar_intencion(texto, hoy)
        tipo = intento["intencion"]

        if tipo == "rapida":
            return {"tipo": "respuesta", **_responder_rapida(intento["id"], d)}

        if tipo == "registrar":
            propuesta = ia.proponer_movimiento(
                texto, d["cuentas"], hoy, clasificar=lambda desc: _clasificar(db, usuario.id, desc))
            if not propuesta:
                return {"tipo": "respuesta", "texto": "No logré entender el monto. Prueba con algo como «Gasté 18.000 en almuerzo con Nequi».", "fuentes": []}
            return {
                "tipo": "propuesta_movimiento",
                "texto": "Esto es lo que entendí. Revísalo y confírmalo para guardarlo:",
                "propuesta": propuesta,
                "cuentas": [{"id": c["id"], "nombre": c["nombre"]} for c in d["cuentas"]],
                "fuentes": [],
            }

        if tipo == "comprar":
            calculo = calc.simular_compra(intento["monto"], _ctx_calculo(d))
            _consumir_cupo_ia(db, usuario.id, hoy)
            base = ia.texto_simulacion(calculo)
            return {"tipo": "simulacion", "texto": ia.redactar_explicacion("comprar", calculo, base), "calculo": calculo,
                    "fuentes": fuentes_de(d, {"saldos", "recurrentes", "deudas", "metas", "mov_historial"})}

        if tipo == "ahorro":
            fecha = intento["fecha_objetivo"]
            if not fecha:
                return {"tipo": "respuesta", "texto": "¿Para cuándo quieres lograrlo? Dímelo así: «ahorrar 12 millones para dic 2027» o «en 12 meses».", "fuentes": []}
            if fecha <= hoy:
                return {"tipo": "respuesta", "texto": "Esa fecha ya pasó. Indícame una fecha futura.", "fuentes": []}
            plan = calc.plan_ahorro(intento["monto"], 0, fecha, calc.capacidad_ahorro(_ctx_calculo(d)), hoy)
            _consumir_cupo_ia(db, usuario.id, hoy)
            texto_plan = ia.redactar_explicacion("ahorro", plan, ia.texto_plan_ahorro(plan))
            return {
                "tipo": "plan", "texto": texto_plan, "calculo": plan,
                "accion": {"tipo": "crear_meta", "nombre": f"Ahorrar {ia.cop(plan['objetivo'])}",
                           "monto_objetivo": plan["objetivo"], "fecha_objetivo": fecha.isoformat(),
                           "aporte_mensual": plan["aporte_mensual"]},
                "cuentas": [{"id": c["id"], "nombre": c["nombre"]} for c in d["cuentas"]],
                "fuentes": fuentes_de(d, {"mov_historial"}),
            }

        if tipo == "deudas":
            if not d["deudas"] or sum(x["saldo"] for x in d["deudas"]) <= 0:
                return {"tipo": "respuesta", "texto": "No tienes deudas activas registradas. Agrégalas en Más > Deudas y armamos el plan.", "fuentes": fuentes_de(d, {"deudas"})}
            meses = intento["meses"]
            if not meses or meses < 1:
                return {"tipo": "respuesta", "texto": "¿En cuántos meses quieres salir? Dímelo así: «quiero salir de mis deudas en 12 meses».", "fuentes": []}
            plan = calc.plan_deudas(d["deudas"], meses, calc.capacidad_ahorro(_ctx_calculo(d)))
            _consumir_cupo_ia(db, usuario.id, hoy)
            texto_plan = ia.redactar_explicacion("deudas", plan, ia.texto_plan_deudas(plan))
            return {
                "tipo": "plan", "texto": texto_plan, "calculo": plan,
                "accion": {"tipo": "crear_meta", "nombre": "Salir de mis deudas",
                           "monto_objetivo": plan["deuda_total"],
                           "fecha_objetivo": ia.parsear_fecha_objetivo(f"en {plan['meses_objetivo']} meses", hoy).isoformat(),
                           "aporte_mensual": plan["pago_total_mensual"],
                           "descripcion": f"Plan avalancha: {ia.cop(plan['extra_mensual'])} extra al mes sobre tus cuotas actuales."},
                "cuentas": [{"id": c["id"], "nombre": c["nombre"]} for c in d["cuentas"]],
                "fuentes": fuentes_de(d, {"deudas", "mov_historial"}),
            }

        # Pregunta libre: IA con el resumen agregado
        contexto = contexto_ia(d)
        _consumir_cupo_ia(db, usuario.id, hoy)
        respuesta = ia.responder_libre(texto, contexto, _numeros_de_contexto(contexto))
        if not respuesta:
            return {"tipo": "respuesta", "texto": "No pude responder eso con certeza. Prueba una de las preguntas sugeridas.",
                    "fuentes": [], "sugerir": True}
        return {"tipo": "respuesta", "texto": respuesta,
                "fuentes": fuentes_de(d, {"mov_mes", "mov_historial", "saldos", "recurrentes", "deudas", "metas", "presupuestos"})}

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        # Sin texto del usuario ni del traceback con datos: solo el tipo de error.
        logger.error("asistente: error procesando mensaje (%s)", type(e).__name__)
        raise HTTPException(status_code=500, detail=ERROR_GENERICO)


@router.post("/confirmar/movimiento")
def confirmar_movimiento(
    data: ConfirmarMovimiento,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Guarda el movimiento que el usuario confirmó en la tarjeta. Pasa por el
    mismo camino que el alta manual (permisos de cuenta, saldo, rachas)."""
    verificar_limite(f"asistente-conf:{usuario.id}", 60, 3600)
    mov = crear_movimiento(
        MovimientoCreate(
            cuenta_id=data.cuenta_id,
            descripcion=ia.sanitizar_dato(data.descripcion, 120),
            monto=data.monto,
            tipo=data.tipo,
            categoria=data.categoria,
            fecha=data.fecha,
            notas="Registrado con CuadraMe AI",
        ),
        db,
        usuario,
    )
    fila = db.query(Movimiento).filter(Movimiento.id == mov.id).first()
    if fila:
        fila.fuente = "ai"
        db.commit()
    return {"ok": True, "id": mov.id}


@router.post("/confirmar/plan")
def confirmar_plan(
    data: ConfirmarPlan,
    db: Session = Depends(get_db),
    usuario: UsuarioActual = Depends(get_current_user),
):
    """Crea la meta del plan aceptado. El aporte automático mensual solo se
    programa si el usuario eligió una cuenta de origen."""
    verificar_limite(f"asistente-conf:{usuario.id}", 60, 3600)
    meta = metas_router.crear_meta(
        MetaCreate(
            nombre=ia.sanitizar_dato(data.nombre, 80),
            descripcion=ia.sanitizar_dato(data.descripcion, 300),
            monto_objetivo=data.monto_objetivo,
            fecha_objetivo=data.fecha_objetivo,
            aporte_automatico=data.aporte_mensual if data.cuenta_origen_id else None,
            cuenta_origen_id=data.cuenta_origen_id,
            icono="🎯",
        ),
        db,
        usuario,
    )
    return {"ok": True, "meta": meta}
