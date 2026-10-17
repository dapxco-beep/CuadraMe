"""
Carga de datos del usuario para el asistente: UN resumen agregado y mínimo.

No se envía el historial completo a la IA: solo totales por mes/categoría,
saldos, compromisos y unos pocos comercios principales (sanitizados). Los IDs,
correos, claves y tokens nunca entran aquí.
"""
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.asistente import MESES, sanitizar_dato
from app.asistente_calc import gasto_por_categoria
from app.compartidos import cuentas_ids_accesibles
from app.finanzas import calc_progreso_meta
from app.contabilidad import ConvertidorBase, moneda_base_de
from app.informe_datos import cargar_movs_efectivos
from app.models import Cuenta, Deuda, Meta, Presupuesto, Recurrente
from app.tarjetas import calc_tarjeta

TIPOS_LIQUIDOS = ("ahorro", "efectivo")
MESES_HISTORIAL = 3  # meses completos anteriores para promedios y patrones
MESES_CONSULTA = 12  # meses de movimientos disponibles para preguntas por periodo
MAX_MOVIMIENTOS = 6000


def _inicio_mes_atras(hoy: datetime, atras: int) -> datetime:
    total = hoy.year * 12 + (hoy.month - 1) - atras
    return datetime(total // 12, total % 12 + 1, 1)


def cargar_datos(db: Session, usuario_id: str, hoy: datetime) -> dict:
    """Devuelve el dict con todo lo que necesitan las funciones puras. Las
    claves 'cuentas' / 'recurrentes' / 'movs' son para uso interno (con ids);
    para la IA se usa `contexto_ia`."""
    ids = cuentas_ids_accesibles(db, usuario_id)
    cuentas = db.query(Cuenta).filter(Cuenta.id.in_(ids)).all()
    base = moneda_base_de(db, usuario_id)
    conv = ConvertidorBase.de_usuario(db, usuario_id)

    # Un año de historia para poder responder por cualquier mes reciente
    # ("¿en qué gasté más en julio?"). Los tipos ya son los EFECTIVOS: sin pagos
    # de tarjeta ni traslados entre cuentas propias (misma regla que los reportes).
    desde = _inicio_mes_atras(hoy, MESES_CONSULTA)
    cargados = cargar_movs_efectivos(db, usuario_id, desde, None, MAX_MOVIMIENTOS)
    conv.sin_tasa.update(cargados.sin_tasa)  # monedas sin tasa vistas en los movimientos (su monto vale 0)
    movs = [m for m in cargados if m["tipo"] in ("income", "expense") and m["fecha"] >= desde]

    # Promedios de los últimos meses COMPLETOS anteriores que tienen movimientos
    por_mes: dict[tuple, dict] = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for m in movs:
        por_mes[(m["fecha"].year, m["fecha"].month)][m["tipo"]] += m["monto"]
    actual = (hoy.year, hoy.month)
    ini_hist = _inicio_mes_atras(hoy, MESES_HISTORIAL)
    anteriores = [k for k in por_mes if (ini_hist.year, ini_hist.month) <= k < actual]
    ingreso_mensual = sum(por_mes[k]["income"] for k in anteriores) / len(anteriores) if anteriores else 0.0
    gasto_mensual = sum(por_mes[k]["expense"] for k in anteriores) / len(anteriores) if anteriores else 0.0
    mes_actual = por_mes.get(actual, {"income": 0.0, "expense": 0.0})

    recs = (
        db.query(Recurrente).filter(Recurrente.usuario_id == usuario_id, Recurrente.activo.is_(True)).all()
    )
    recurrentes = [
        {"nombre": sanitizar_dato(r.nombre), "monto": r.monto, "tipo": r.tipo, "activo": True,
         "pagado_mes": bool(r.ultima_vez and (r.ultima_vez.year, r.ultima_vez.month) == actual)}
        for r in recs
    ]
    recurrentes_pendientes = sum(r["monto"] for r in recurrentes if r["tipo"] == "expense" and not r["pagado_mes"])

    deudas = db.query(Deuda).filter(Deuda.usuario_id == usuario_id, Deuda.activa.is_(True)).all()
    # Cuotas de deudas que aún vencen en lo que queda del mes
    cuotas_pendientes = sum((d.cuota_mensual or 0) for d in deudas if (d.dia_pago or 1) >= hoy.day)
    # Tarjetas de crédito: pago mínimo estimado si el pago cae este mes
    for c in cuentas:
        if c.tipo == "credito":
            t = calc_tarjeta(c, hoy)
            if t["proximo_pago"] and t["proximo_pago"][:7] == hoy.strftime("%Y-%m") and t["cupo_usado"] > 0:
                cuotas_pendientes += conv(t["pago_minimo_estimado"], c.moneda)

    metas = db.query(Meta).filter(Meta.usuario_id == usuario_id, Meta.activa.is_(True)).all()
    aportes_metas = 0.0
    for me in metas:
        a = calc_progreso_meta(me).get("aporte_necesario_mes")
        if a:
            aportes_metas += a

    presupuestos = db.query(Presupuesto).filter(Presupuesto.usuario_id == usuario_id, Presupuesto.activo.is_(True)).all()

    saldo_liquido = sum(conv(c.saldo, c.moneda) for c in cuentas if c.tipo in TIPOS_LIQUIDOS)

    return {
        "hoy": hoy,
        "cuentas": [{"id": c.id, "nombre": c.nombre, "tipo": c.tipo, "moneda": c.moneda} for c in cuentas],
        "saldo_liquido": saldo_liquido,
        "moneda_base": base,
        "monedas_sin_tasa": sorted(conv.sin_tasa),
        "movs": movs,
        "ingreso_mensual": ingreso_mensual,
        "gasto_mensual": gasto_mensual,
        "ingreso_mes_actual": mes_actual["income"],
        "gasto_mes_actual": mes_actual["expense"],
        "meses_con_datos": len(anteriores),
        "recurrentes": recurrentes,
        "recurrentes_pendientes": recurrentes_pendientes,
        "cuotas_pendientes": cuotas_pendientes,
        "aportes_metas": aportes_metas,
        "deudas": [
            {"id": d.id, "nombre": sanitizar_dato(d.nombre), "saldo": d.saldo_actual or 0,
             "tasa_mensual": d.tasa_mensual or 0, "cuota": d.cuota_mensual or 0}
            for d in deudas
        ],
        "metas": [
            {"nombre": sanitizar_dato(m.nombre), "objetivo": m.monto_objetivo, "actual": m.monto_actual}
            for m in metas
        ],
        "presupuestos": [{"categoria": sanitizar_dato(p.categoria), "limite": p.limite} for p in presupuestos],
    }


def contexto_ia(datos: dict) -> dict:
    """Resumen mínimo y sin identificadores que SÍ puede ver el modelo."""
    hoy = datos["hoy"]
    top = gasto_por_categoria(datos["movs"], hoy.year, hoy.month)[:6]
    comercios: dict[str, float] = defaultdict(float)
    for m in datos["movs"]:
        # Lo originado en un correo de Gmail no sale hacia la IA con nombre (Uso Limitado de Google).
        if m.get("fuente") == "email":
            continue
        if m["tipo"] == "expense" and (m["fecha"].year, m["fecha"].month) == (hoy.year, hoy.month):
            comercios[sanitizar_dato(m["descripcion"], 40)] += m["monto"]
    principales = sorted(comercios.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "mes_actual": f"{MESES[hoy.month - 1]} de {hoy.year}",
        "ingresos_mes": round(datos["ingreso_mes_actual"]),
        "gastos_mes": round(datos["gasto_mes_actual"]),
        "gastos_por_categoria_mes": top,
        "comercios_principales_mes": [{"nombre": n, "monto": round(v)} for n, v in principales],
        "ingreso_mensual_promedio": round(datos["ingreso_mensual"]),
        "gasto_mensual_promedio": round(datos["gasto_mensual"]),
        "saldo_en_cuentas_liquidas": round(datos["saldo_liquido"]),
        "gastos_fijos_pendientes_mes": round(datos["recurrentes_pendientes"]),
        "cuotas_pendientes_mes": round(datos["cuotas_pendientes"]),
        "deudas": [{"nombre": d["nombre"], "saldo": round(d["saldo"])} for d in datos["deudas"]],
        "metas": [{"nombre": m["nombre"], "objetivo": round(m["objetivo"]), "actual": round(m["actual"])} for m in datos["metas"]],
        "presupuestos": [{"categoria": p["categoria"], "limite": round(p["limite"])} for p in datos["presupuestos"]],
    }


def fuentes_de(datos: dict, usar: set[str]) -> list[str]:
    """Etiquetas legibles de DÓNDE salen las cifras, p. ej.
    'Tus movimientos de octubre de 2026 (47)'."""
    hoy = datos["hoy"]
    etiquetas = {
        "mov_mes": f"Tus movimientos de {MESES[hoy.month - 1]} de {hoy.year} "
                   f"({sum(1 for m in datos['movs'] if (m['fecha'].year, m['fecha'].month) == (hoy.year, hoy.month))})",
        "mov_historial": f"Tus movimientos de los últimos {max(datos['meses_con_datos'], 1)} meses completos (promedios)",
        "saldos": "Saldos de tus cuentas de ahorro y efectivo",
        "recurrentes": f"Tus gastos fijos activos ({len(datos['recurrentes'])})",
        "deudas": f"Tus deudas y tarjetas ({len(datos['deudas'])} deudas)",
        "metas": f"Tus metas activas ({len(datos['metas'])})",
        "presupuestos": f"Tus presupuestos ({len(datos['presupuestos'])})",
    }
    orden = ["mov_mes", "mov_historial", "saldos", "recurrentes", "deudas", "metas", "presupuestos"]
    return [etiquetas[k] for k in orden if k in usar]
