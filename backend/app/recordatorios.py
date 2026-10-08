"""Recordatorios útiles que se calculan con datos que la app ya tiene.

Los usan dos cosas: las tarjetas del Inicio (GET /recordatorios) y el resumen
semanal por correo. Aquí vive la lógica una sola vez para que ambos digan lo mismo.
No envía nada ni guarda estado: solo calcula."""
from datetime import datetime

from sqlalchemy.orm import Session

from app import presupuesto_servicio as srv
from app.extractos_conciliados import depurar_conciliados
from app.models import Cuenta, ExtractoCorreo, Presupuesto
from app.tarjetas import calc_tarjeta, extractos_guardados, movimientos_tras_corte

DIAS_VENCIMIENTO = 5  # una tarjeta aparece en el Inicio cuando falta esto o menos para pagar
UMBRAL_PRESUPUESTO = 80  # % usado desde el cual se avisa


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
    """Extractos que llegaron al Gmail del usuario y esperan que los concilie o les ponga la clave."""
    depurar_conciliados(db, usuario_id)  # los ya cruzados a mano dejan de ser pendientes
    return (
        db.query(ExtractoCorreo)
        .filter(ExtractoCorreo.usuario_id == usuario_id, ExtractoCorreo.estado.in_(("nuevo", "falta_clave")))
        .count()
    )


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
