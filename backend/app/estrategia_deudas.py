"""
Estrategia de pago de deudas: avalancha vs bola de nieve.

Todo aquí son funciones PURAS (sin base de datos ni reloj implícito salvo el
parámetro `hoy`), para poder probarlas con números exactos.

- Avalancha: el dinero extra va primero a la deuda de MAYOR tasa de interés.
  Es matemáticamente la que menos intereses paga.
- Bola de nieve: el extra va primero a la deuda de MENOR saldo. Cuesta un poco
  más en intereses, pero cierra deudas rápido y eso motiva.

Supuesto clave: el presupuesto mensual total es constante
(suma de cuotas + extra). Cuando una deuda se salda, su cuota "liberada" se
suma al extra y sigue atacando la siguiente: ese efecto es el que hace que
ambos métodos funcionen.
"""
from datetime import datetime

# 50 años. Si con las cuotas actuales la deuda no baja (cuota <= interés),
# la simulación se corta aquí y el resultado dice "no se termina".
MAX_MESES = 600


def _preparar(deudas: list[dict]) -> list[dict]:
    """Normaliza cada deuda: saldo, tasa mensual (fracción) y cuota mínima.
    Si el usuario no registró cuota, asumimos interés del mes + 1% del saldo
    (una cuota "mínima razonable" que sí hace bajar el saldo)."""
    prep = []
    for d in deudas:
        saldo = float(d.get("saldo") or 0)
        if saldo <= 0:
            continue
        tasa = float(d.get("tasa_mensual") or 0) / 100
        minimo = float(d.get("cuota") or 0)
        if minimo <= 0:
            minimo = saldo * tasa + saldo * 0.01
        prep.append({
            "id": d["id"], "nombre": d.get("nombre", ""),
            "saldo": saldo, "tasa": tasa, "minimo": minimo, "mes_libre": None,
        })
    return prep


def simular(deudas: list[dict], extra: float, metodo: str) -> dict:
    """Simula mes a mes. metodo: 'avalancha' | 'bola_de_nieve' | 'sin_extra'.

    'sin_extra' es la línea base: cada deuda paga solo su cuota, sin extra y
    sin reasignar cuotas liberadas. Devuelve meses (None si no termina),
    intereses totales, saldo total por mes y el orden en que se saldan."""
    est = _preparar(deudas)
    extra = max(0.0, float(extra or 0))
    reasignar = metodo != "sin_extra"
    if metodo == "avalancha":
        prioridad = sorted(est, key=lambda d: (-d["tasa"], d["saldo"]))
    elif metodo == "bola_de_nieve":
        prioridad = sorted(est, key=lambda d: (d["saldo"], -d["tasa"]))
    else:
        prioridad = list(est)

    presupuesto = sum(d["minimo"] for d in est) + (extra if reasignar else 0)
    intereses = 0.0
    saldo_por_mes = [round(sum(d["saldo"] for d in est), 2)]
    mes = 0

    while any(d["saldo"] > 0.005 for d in est) and mes < MAX_MESES:
        mes += 1
        for d in est:
            if d["saldo"] > 0:
                i = d["saldo"] * d["tasa"]
                d["saldo"] += i
                intereses += i
        disponible = presupuesto
        # 1) cuota mínima de cada deuda viva
        for d in est:
            if d["saldo"] > 0:
                pago = min(d["minimo"], d["saldo"])
                d["saldo"] -= pago
                disponible -= pago
        # 2) lo que sobra (extra + cuotas liberadas) a la deuda prioritaria
        if reasignar:
            for d in prioridad:
                if disponible <= 0:
                    break
                if d["saldo"] > 0:
                    pago = min(disponible, d["saldo"])
                    d["saldo"] -= pago
                    disponible -= pago
        for d in est:
            if d["saldo"] <= 0.005 and d["mes_libre"] is None:
                d["saldo"] = 0.0
                d["mes_libre"] = mes
        saldo_por_mes.append(round(sum(d["saldo"] for d in est), 2))

    termino = all(d["mes_libre"] is not None for d in est)
    orden = sorted(
        [{"id": d["id"], "nombre": d["nombre"], "mes_libre": d["mes_libre"]} for d in est],
        key=lambda x: (x["mes_libre"] is None, x["mes_libre"] or 0),
    )
    return {
        "metodo": metodo,
        "meses": mes if termino else None,
        "intereses_totales": round(intereses, 2),
        "orden": orden,
        "saldo_por_mes": saldo_por_mes,
    }


def _fecha_libre(hoy: datetime, meses: int | None) -> str | None:
    if meses is None:
        return None
    total = hoy.year * 12 + (hoy.month - 1) + meses
    return f"{total // 12}-{total % 12 + 1:02d}"


def comparar_estrategias(deudas: list[dict], extra: float, hoy: datetime) -> dict:
    """Corre línea base, avalancha y bola de nieve, y calcula cuánto se ahorra
    cada método (en intereses y en meses) frente a pagar solo las cuotas."""
    base = simular(deudas, 0, "sin_extra")
    resultados = {}
    for metodo in ("avalancha", "bola_de_nieve"):
        r = simular(deudas, extra, metodo)
        resultados[metodo] = r

    def completar(r: dict) -> dict:
        base_ok = base["meses"] is not None
        r["fecha_libre"] = _fecha_libre(hoy, r["meses"])
        r["ahorro_intereses"] = (
            round(base["intereses_totales"] - r["intereses_totales"], 2) if base_ok and r["meses"] is not None else None
        )
        r["meses_ahorrados"] = base["meses"] - r["meses"] if base_ok and r["meses"] is not None else None
        return r

    base["fecha_libre"] = _fecha_libre(hoy, base["meses"])
    base["ahorro_intereses"] = 0.0 if base["meses"] is not None else None
    base["meses_ahorrados"] = 0 if base["meses"] is not None else None
    av = completar(resultados["avalancha"])
    bn = completar(resultados["bola_de_nieve"])

    # "Mejor" = menos intereses (si no terminan, el que lleve menos intereses al horizonte).
    mejor = "avalancha" if av["intereses_totales"] <= bn["intereses_totales"] else "bola_de_nieve"
    return {
        "extra_mensual": round(max(0.0, float(extra or 0)), 2),
        "deuda_total": round(sum(d["saldo"] for d in _preparar(deudas)), 2),
        "sin_extra": base,
        "avalancha": av,
        "bola_de_nieve": bn,
        "mejor": mejor,
    }
