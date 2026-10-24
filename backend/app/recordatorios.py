"""Recordatorios útiles que se calculan con datos que la app ya tiene.

Los usan dos cosas: las tarjetas del Inicio (GET /recordatorios) y el resumen
semanal por correo. Aquí vive la lógica una sola vez para que ambos digan lo mismo.
No envía nada ni guarda estado: solo calcula."""
from datetime import datetime, timedelta
from statistics import median

from sqlalchemy.orm import Session

from app import presupuesto_servicio as srv
from app.extractos_conciliados import depurar_conciliados
from app.models import Cuenta, ExtractoCorreo, Presupuesto
from app.tarjetas import calc_tarjeta, extractos_guardados, movimientos_tras_corte

DIAS_VENCIMIENTO = 5  # una tarjeta aparece en el Inicio cuando falta esto o menos para pagar
UMBRAL_PRESUPUESTO = 80  # % usado desde el cual se avisa
GASTO_GRANDE_MINIMO = 300_000  # un gasto por debajo de esto nunca se avisa como «fuera de lo normal»
GASTO_GRANDE_VECES = 8  # ...ni si no es al menos tantas veces tu gasto típico (la mediana)
GASTO_GRANDE_DIAS = 3  # solo gastos de los últimos días
GASTO_GRANDE_HISTORIAL = 120  # días hacia atrás para saber qué es «típico»
GASTO_GRANDE_MIN_MOVS = 8  # con menos gastos de historia no se adivina qué es normal


def cuentas_en_negativo(db: Session, usuario_id: str) -> list[dict]:
    """Cuentas propias que NO son tarjeta con saldo por debajo de cero (lo normal en una tarjeta de crédito
    es deber, aquí no). Suelen ser un ingreso sin anotar, un saldo inicial que falta o un movimiento en la
    cuenta equivocada."""
    cuentas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id, Cuenta.tipo != "credito", Cuenta.saldo < 0).all()
    return sorted(({"cuenta_id": c.id, "nombre": c.nombre, "saldo": round(c.saldo), "moneda": c.moneda or "COP"} for c in cuentas),
                  key=lambda x: x["saldo"])


def gastos_grandes(db: Session, usuario_id: str, hoy: datetime) -> list[dict]:
    """Gastos reales (no traslados ni pagos de tarjeta) de los últimos días que pasan por mucho lo que
    sueles gastar: al menos $300.000 y GASTO_GRANDE_VECES veces tu gasto típico. Sirve para avisar de un gasto
    grande que quizá era de otra persona, estaba mal anotado o ni siquiera era tuyo."""
    from app.informe_datos import cargar_movs_efectivos

    movs = [m for m in cargar_movs_efectivos(db, usuario_id, hoy - timedelta(days=GASTO_GRANDE_HISTORIAL), hoy + timedelta(days=1))
            if m["tipo"] == "expense" and not m.get("sin_tasa")]
    corte = hoy - timedelta(days=GASTO_GRANDE_DIAS)
    previos = [m["monto"] for m in movs if m["fecha"] < corte]
    if len(previos) < GASTO_GRANDE_MIN_MOVS:
        return []
    tipico = median(previos)
    umbral = max(GASTO_GRANDE_MINIMO, GASTO_GRANDE_VECES * tipico)
    grandes = [m for m in movs if m["fecha"] >= corte and m["monto"] >= umbral]
    return [{"id": m["id"], "descripcion": m["descripcion"], "monto": round(m["monto"]), "tipico": round(tipico)}
            for m in sorted(grandes, key=lambda x: -x["monto"])[:2]]


def tarjetas_por_vencer(db: Session, usuario_id: str, hoy: datetime, dias: int = DIAS_VENCIMIENTO) -> list[dict]:
    """Tarjetas de crédito cuyo pago cae en los próximos `dias` días (hoy incluido).
    El monto es lo que falta para NO pagar intereses cuando se conoce el corte;
    si no, la deuda actual. Las ya pagadas o con plazo vencido no se listan."""
    tarjetas = db.query(Cuenta).filter(Cuenta.usuario_id == usuario_id, Cuenta.tipo == "credito").all()
    tarjetas = [t for t in tarjetas if t.dia_pago]
    if not tarjetas:
        return []
    guardados = extractos_guardados(db, [t.id for t in tarjetas])
    out = []
    for t in tarjetas:
        movs = movimientos_tras_corte(db, t, hoy) if t.dia_corte else None
        info = calc_tarjeta(t, hoy, movs, guardados.get(t.id))
        if info["falta_para_evitar_intereses"] is not None:
            monto, fecha, d = info["falta_para_evitar_intereses"], info["fecha_limite_pago"], info["dias_para_limite"]
        else:
            monto, fecha, d = info["cupo_usado"], info["proximo_pago"], info["dias_para_pago"]
        if monto is None or monto <= 0 or d is None or d < 0 or d > dias:
            continue
        out.append({"cuenta_id": t.id, "nombre": t.nombre, "monto": round(monto), "fecha": fecha, "dias": d})
    return sorted(out, key=lambda x: x["dias"])


def presupuestos_altos(db: Session, usuario_id: str, hoy: datetime, umbral: int = UMBRAL_PRESUPUESTO) -> list[dict]:
    """Presupuestos activos que ya usaron `umbral` % o más de su límite en el periodo actual."""
    presupuestos = (
        db.query(Presupuesto)
        .filter(Presupuesto.usuario_id == usuario_id, Presupuesto.activo == True)  # noqa: E712
        .all()
    )
    if not presupuestos:
        return []
    cfg = srv.obtener_config(db, usuario_id)
    gastos = srv.GastosPorRango(db, usuario_id)
    out = []
    for p in presupuestos:
        if (p.limite or 0) <= 0:
            continue
        proy = srv.proyectar_presupuesto(p, cfg, gastos, hoy, n_historico=1)
        if proy["limite"] <= 0 or proy["pct_usado"] < umbral:
            continue
        out.append({
            "categoria": p.categoria, "pct": round(proy["pct_usado"]), "gastado": round(proy["gastado"]),
            "limite": round(proy["limite"]), "clave_periodo": proy["clave_periodo"],
        })
    return sorted(out, key=lambda x: -x["pct"])


def extractos_pendientes(db: Session, usuario_id: str) -> int:
    """Extractos que piden algo de la persona (revisarlos o poner la clave). Usa el MISMO modelo que la
    pantalla «Traer movimientos» (app/estado_traer.py): un extracto que llegó en dos correos, o que ya
    se subió a mano, cuenta una sola vez; y uno ya revisado con todo registrado no cuenta."""
    from app import estado_traer, punto_partida

    depurar_conciliados(db, usuario_id)  # los ya cruzados a mano dejan de ser pendientes
    estado_traer.reconciliar_pendientes(db, usuario_id)
    lista = estado_traer.lista_extractos(db, usuario_id, punto_partida.fecha_inicio(db, usuario_id))
    return sum(1 for x in lista if x["estado"] in (estado_traer.POR_REVISAR, estado_traer.NECESITA_CLAVE))


def _pesos(n: float) -> str:
    return f"${n:,.0f}".replace(",", ".")


def calcular(db: Session, usuario_id: str, hoy: datetime) -> list[dict]:
    """Lista de recordatorios para el Inicio. Cada uno trae una `clave` estable por
    situación (incluye el periodo o la fecha) para que, al descartarlo, no vuelva a
    salir hasta que haya algo nuevo. Orden: lo más urgente primero."""
    out: list[dict] = []
    for t in tarjetas_por_vencer(db, usuario_id, hoy):
        cuando = "hoy" if t["dias"] == 0 else "mañana" if t["dias"] == 1 else f"en {t['dias']} días"
        out.append({
            "clave": f"tarjeta:{t['cuenta_id']}:{t['fecha']}", "tipo": "tarjeta",
            "titulo": f"Pagas {t['nombre']} {cuando}",
            "texto": f"Para no pagar intereses faltan {_pesos(t['monto'])}.",
            "ruta": "/cuentas",
        })
    for c in cuentas_en_negativo(db, usuario_id):
        out.append({
            "clave": f"negativo:{c['cuenta_id']}:{hoy:%Y-%m}", "tipo": "saldo_negativo",
            "titulo": f"{c['nombre']} está en negativo",
            "texto": f"Su saldo es -{_pesos(abs(c['saldo']))}. Suele ser un ingreso sin anotar, un saldo inicial que falta o un movimiento en la cuenta equivocada.",
            "ruta": "/cuentas",
        })
    for g in gastos_grandes(db, usuario_id, hoy):
        out.append({
            "clave": f"gasto_grande:{g['id']}", "tipo": "gasto_grande",
            "titulo": f"Gasto grande: {_pesos(g['monto'])}",
            "texto": f"«{g['descripcion'][:40]}» está muy por encima de lo que sueles gastar (lo típico es {_pesos(g['tipico'])}). Si no es tuyo o está mal anotado, corrígelo.",
            "ruta": f"/movimientos/{g['id']}",
        })
    for p in presupuestos_altos(db, usuario_id, hoy):
        titulo = f"{p['categoria']}: ya usaste el {p['pct']} %" if p["pct"] < 100 else f"{p['categoria']}: te pasaste del presupuesto"
        out.append({
            "clave": f"presupuesto:{p['categoria']}:{p['clave_periodo']}", "tipo": "presupuesto",
            "titulo": titulo, "texto": f"Llevas {_pesos(p['gastado'])} de {_pesos(p['limite'])}.",
            "ruta": "/presupuesto",
        })
    n = extractos_pendientes(db, usuario_id)
    if n:
        out.append({
            "clave": f"extractos:{n}", "tipo": "extractos",
            "titulo": "Tienes 1 extracto por revisar" if n == 1 else f"Tienes {n} extractos por revisar",
            "texto": "Llegaron a tu correo. Cruzarlos con lo que registraste toma un minuto.",
            "ruta": "/sincronizacion",
        })
    return out
