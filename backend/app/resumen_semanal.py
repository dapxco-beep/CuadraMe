"""Resumen semanal por correo: arma los datos de la semana y la plantilla HTML.

Funciones sin efectos secundarios (salvo `enviar_correo`, que habla con Resend).
El cron y el control de idempotencia viven en routers/resumen.py."""
import html
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app import punto_partida
from app.compartidos import cuentas_ids_accesibles
from app.config import settings
from app.contabilidad import gastos_por_categoria, tipos_cuenta_de, tipos_efectivos
from app.fx import convertir_a_cop
from app.models import Cuenta, Movimiento
from app.recordatorios import presupuestos_altos, tarjetas_por_vencer

logger = logging.getLogger(__name__)

DIAS_SEMANA = 7
DIAS_VENCIMIENTO_CORREO = 7  # el correo mira una semana adelante


def _pesos(n: float) -> str:
    return f"${n:,.0f}".replace(",", ".")


def datos_semana(db: Session, usuario_id: str, hoy: datetime) -> dict:
    """Todo lo que lleva el correo de UN usuario. `vacio` = no hay nada que contar
    (sin gastos ni avisos): en ese caso no se manda correo."""
    ids = cuentas_ids_accesibles(db, usuario_id)
    por_cat = gastos_por_categoria(db, ids, hoy - timedelta(days=DIAS_SEMANA)) if ids else {}
    ordenadas = sorted(por_cat.items(), key=lambda kv: -kv[1])
    total = sum(por_cat.values())
    datos = {
        "desde": (hoy - timedelta(days=DIAS_SEMANA)).date().isoformat(),
        "hasta": hoy.date().isoformat(),
        "total_gastos": round(total),
        "top_categorias": [{"categoria": c, "monto": round(m)} for c, m in ordenadas[:3]],
        "presupuestos": presupuestos_altos(db, usuario_id, hoy),
        "tarjetas": tarjetas_por_vencer(db, usuario_id, hoy, DIAS_VENCIMIENTO_CORREO),
    }
    datos["vacio"] = not (datos["total_gastos"] or datos["presupuestos"] or datos["tarjetas"])
    return datos


def _cuando(dias: int) -> str:
    return "hoy" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"


def asunto(datos: dict) -> str:
    return f"Tu semana en CuadraMe: gastaste {_pesos(datos['total_gastos'])}" if datos["total_gastos"] else "Tu semana en CuadraMe"


def texto_plano(datos: dict, nombre: str = "") -> str:
    """Versión sin formato (clientes de correo que no muestran HTML)."""
    l = [f"Hola{', ' + nombre if nombre else ''}. Así te fue esta semana ({datos['desde']} al {datos['hasta']}).", ""]
    l.append(f"Gastaste {_pesos(datos['total_gastos'])}.")
    if datos["top_categorias"]:
        l += ["", "Donde más se fue la plata:"] + [f"- {c['categoria']}: {_pesos(c['monto'])}" for c in datos["top_categorias"]]
    if datos["presupuestos"]:
        l += ["", "Presupuestos casi agotados:"] + [
            f"- {p['categoria']}: {p['pct']} % ({_pesos(p['gastado'])} de {_pesos(p['limite'])})" for p in datos["presupuestos"]
        ]
    if datos["tarjetas"]:
        l += ["", "Próximos pagos de tarjeta:"] + [
            f"- {t['nombre']}: {_pesos(t['monto'])} {_cuando(t['dias'])} ({t['fecha']})" for t in datos["tarjetas"]
        ]
    l += ["", f"Abre CuadraMe: {settings.pwa_url}",
          "Recibes este correo porque lo activaste en Perfil. Puedes apagarlo ahí mismo cuando quieras."]
    return "\n".join(l)


def _fila(izq: str, der: str) -> str:
    return (
        '<tr><td style="padding:8px 0;border-bottom:1px solid #eadfcd;font-size:15px;color:#221f19">' + izq + "</td>"
        '<td align="right" style="padding:8px 0;border-bottom:1px solid #eadfcd;font-size:15px;font-weight:700;color:#221f19;white-space:nowrap">'
        + der + "</td></tr>"
    )


def _bloque(titulo: str, filas: list[str]) -> str:
    if not filas:
        return ""
    return (
        '<h2 style="margin:28px 0 4px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:#7a5a0a">'
        + html.escape(titulo) + '</h2><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        + "".join(filas) + "</table>"
    )


def html_correo(datos: dict, nombre: str = "") -> str:
    """Plantilla sobria de marca: papel crema, naranja CuadraMe, tipografía del sistema
    y estilos en línea (los clientes de correo ignoran las hojas de estilo). Todo texto
    que viene del usuario (categorías, nombres de tarjeta) se escapa."""
    e = html.escape
    saludo = f"Hola, {e(nombre)}" if nombre else "Hola"
    cats = [_fila(e(c["categoria"]), _pesos(c["monto"])) for c in datos["top_categorias"]]
    pres = [_fila(e(p["categoria"]), f"{p['pct']} %") for p in datos["presupuestos"]]
    tarj = [_fila(f"{e(t['nombre'])} <span style='color:#6b6455;font-size:13px'>{_cuando(t['dias'])}</span>", _pesos(t["monto"]))
            for t in datos["tarjetas"]]
    cuerpo = (
        _bloque("Donde más se fue la plata", cats)
        + _bloque("Presupuestos casi agotados", pres)
        + _bloque("Próximos pagos de tarjeta", tarj)
    )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tu semana en CuadraMe</title></head>
<body style="margin:0;padding:0;background:#f6efe2;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6efe2"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:16px;overflow:hidden">
<tr><td style="background:#a83f0d;padding:18px 24px;color:#fff7ee;font-size:18px;font-weight:800">CuadraMe</td></tr>
<tr><td style="padding:24px">
<p style="margin:0 0 4px;font-size:15px;color:#6b6455">{saludo}. Tu semana, del {e(datos['desde'])} al {e(datos['hasta'])}:</p>
<p style="margin:0;font-size:34px;font-weight:800;color:#221f19">{_pesos(datos['total_gastos'])}</p>
<p style="margin:2px 0 0;font-size:14px;color:#6b6455">gastados en la semana</p>
{cuerpo}
<p style="margin:28px 0 0"><a href="{e(settings.pwa_url)}" style="display:inline-block;background:#a83f0d;color:#fff7ee;text-decoration:none;font-weight:700;font-size:15px;padding:12px 22px;border-radius:999px">Abrir CuadraMe</a></p>
</td></tr>
<tr><td style="padding:16px 24px;background:#faf5ea;font-size:12px;line-height:1.5;color:#6b6455">
Recibes este correo porque activaste el resumen semanal en tu Perfil. Para dejar de recibirlo, entra a CuadraMe, abre Perfil y apaga &laquo;Resumen semanal por correo&raquo;.
</td></tr></table></td></tr></table></body></html>"""


def enviar_correo(destino: str, asunto_: str, html_: str, texto: str) -> bool:
    """Envía por Resend. False (sin lanzar) si no hay clave configurada; lanza si Resend falla,
    para que el cron libere la marca y reintente en la siguiente corrida."""
    if not settings.resend_api_key:
        logger.warning("resumen: RESEND_API_KEY no configurada, no se envió el correo")
        return False
    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={"from": settings.resend_from, "to": [destino], "subject": asunto_, "html": html_, "text": texto},
        timeout=20,
    )
    r.raise_for_status()
    from app.crecimiento import registrar_correo_enviado  # cuenta el envío para el monitor de Resend
    registrar_correo_enviado()
    return True


# ── Recordatorio semanal por push ─────────────────────────────────────────────────────
def comparativo_push(db: Session, usuario_id: str, ids_cuentas: list[str], ahora: datetime) -> dict | None:
    """Semana (últimos 7 días) contra la anterior, para el push del domingo. None si la persona
    no tuvo movimientos en la semana (entonces no se le escribe). Respeta el punto de partida:
    lo anterior a esa fecha no cuenta, y si la semana anterior queda (en parte) antes de él, no
    se compara (sería una comparación injusta con una semana a medias)."""
    if not ids_cuentas:
        return None
    inicio_sem = ahora - timedelta(days=DIAS_SEMANA)
    inicio_ant = ahora - timedelta(days=2 * DIAS_SEMANA)
    inicio_pp = punto_partida.fecha_inicio(db, usuario_id)
    monedas = {c.id: c.moneda for c in db.query(Cuenta).filter(Cuenta.id.in_(ids_cuentas)).all()}
    # 3 días antes: solo para emparejar traslados del borde (igual que gastos_por_categoria).
    movs = (db.query(Movimiento)
            .filter(Movimiento.cuenta_id.in_(ids_cuentas), Movimiento.fecha >= inicio_ant - timedelta(days=3),
                    Movimiento.fecha <= ahora)
            .all())
    te = tipos_efectivos(movs, tipos_cuenta_de(db, ids_cuentas))

    semana = [m for m in movs if m.fecha >= inicio_sem and not (inicio_pp and m.fecha < inicio_pp)]
    if not semana:
        return None
    por_cat: dict[str, float] = {}
    for m in semana:
        if te[m.id] == "expense":
            cat = m.categoria or "Otros"
            por_cat[cat] = por_cat.get(cat, 0.0) + convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))
    gastos = sum(por_cat.values())
    anterior = None
    if inicio_pp is None or inicio_pp <= inicio_ant:
        anterior = sum(
            convertir_a_cop(m.monto, monedas.get(m.cuenta_id, "COP"))
            for m in movs if inicio_ant <= m.fecha < inicio_sem and te[m.id] == "expense")
    top = max(por_cat.items(), key=lambda kv: kv[1])[0] if por_cat else None
    return {"gastos": gastos, "anterior": anterior, "top": top, "movimientos": len(semana)}


def mensaje_push(c: dict, ocultar_montos: bool = False) -> tuple[str, str]:
    """(título, cuerpo) del push semanal. Tono Cuadri: cercano, sin culpar ni regañar.
    Con «ocultar saldos» activado no lleva ningún monto (los porcentajes sí: no revelan cuánto)."""
    gastos, anterior, top = c["gastos"], c.get("anterior"), c.get("top")
    titulo = "Tu semana con Cuadri"
    if gastos <= 0:
        return titulo, "Esta semana no registraste gastos. ¡Un respiro para tu bolsillo!"
    primera = "Ya está lista la foto de tu semana" if ocultar_montos else f"Esta semana gastaste {_pesos(gastos)}"
    comparacion = ""
    subio = False
    if anterior and anterior > 0:
        pct = round((gastos - anterior) / anterior * 100)
        if abs(pct) < 3:
            comparacion = ", casi igual que la semana anterior"
        elif pct < 0:
            comparacion = f", {abs(pct)} % menos que la anterior"
        else:
            comparacion = f", {pct} % más que la anterior"
            subio = True
    texto = primera + comparacion + "."
    if top:
        texto += f" Lo que más pesó: {top}."
    if subio:
        texto += " Pasa a todos: míralo con calma y ajusta lo que quieras."
    return titulo, texto
