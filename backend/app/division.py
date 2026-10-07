"""
Cálculo puro (sin base de datos) de gastos compartidos tipo Splitwise.

Decisión clave: todo se calcula en enteros de la unidad mínima (pesos para COP,
centavos para USD/EUR) y los porcentajes/partes se manejan como `Fraction`.
Así nunca aparecen errores de flotante (0.1 + 0.2) y la suma de las partes es
SIEMPRE igual al total: el resto que deja el redondeo se reparte con el método
del "mayor residuo" (a cada quien se le da su parte entera y las unidades
sobrantes van a quienes tenían la fracción más grande).
"""
from fractions import Fraction

YO = "yo"  # identificador del propio usuario dentro de un gasto
MODOS = ("iguales", "montos", "porcentajes", "partes")


class DivisionInvalida(ValueError):
    """La división no cuadra (porcentajes que no suman 100, montos distintos al total...)."""


def _a_unidades(monto, decimales: int) -> int:
    x = Fraction(str(monto)) * 10**decimales
    return round(x)  # round() de Fraction redondea al par más cercano, sin flotantes


def _de_unidades(unidades: int, decimales: int) -> float:
    return unidades / 10**decimales if decimales else float(unidades)


def _repartir_proporcional(total_u: int, pesos: list[Fraction]) -> list[int]:
    """Reparte `total_u` enteros según `pesos` sin perder ni crear unidades."""
    suma = sum(pesos)
    if suma <= 0:
        raise DivisionInvalida("Debe haber al menos un participante con parte mayor a cero")
    exactos = [Fraction(total_u) * p / suma for p in pesos]
    base = [int(e // 1) for e in exactos]
    sobrante = total_u - sum(base)
    # Mayor residuo primero; en empate, el orden de la lista (determinista).
    orden = sorted(range(len(pesos)), key=lambda i: (-(exactos[i] - base[i]), i))
    for i in orden[:sobrante]:
        base[i] += 1
    return base


def dividir(total, modo: str, participantes: list[dict], decimales: int = 0) -> dict[str, float]:
    """
    participantes: [{"id": "yo", "valor": <según modo>}, ...]
      - iguales: `valor` se ignora (todos pagan lo mismo).
      - partes: `valor` = nº de partes (ej. 2 para una pareja, 1 para un soltero).
      - porcentajes: `valor` = % (deben sumar 100).
      - montos: `valor` = monto exacto (deben sumar el total).
    Devuelve {id: monto} cuya suma es exactamente `total`.
    """
    if modo not in MODOS:
        raise DivisionInvalida(f"Modo de división desconocido: {modo}")
    if not participantes:
        raise DivisionInvalida("Agrega al menos un participante")
    ids = [p["id"] for p in participantes]
    if len(set(ids)) != len(ids):
        raise DivisionInvalida("Hay participantes repetidos")

    total_u = _a_unidades(total, decimales)
    if total_u <= 0:
        raise DivisionInvalida("El total debe ser mayor a cero")

    def valor(p):
        try:
            v = Fraction(str(p.get("valor", 0) or 0))
        except (ValueError, ZeroDivisionError):
            raise DivisionInvalida("Valor inválido en un participante")
        if v < 0:
            raise DivisionInvalida("Los valores no pueden ser negativos")
        return v

    if modo == "iguales":
        partes_u = _repartir_proporcional(total_u, [Fraction(1)] * len(participantes))
    elif modo == "partes":
        partes_u = _repartir_proporcional(total_u, [valor(p) for p in participantes])
    elif modo == "porcentajes":
        pesos = [valor(p) for p in participantes]
        if sum(pesos) != 100:
            raise DivisionInvalida(f"Los porcentajes deben sumar 100 (suman {float(sum(pesos)):g})")
        partes_u = _repartir_proporcional(total_u, pesos)
    else:  # montos
        partes_u = [_a_unidades(valor(p), decimales) for p in participantes]
        if sum(partes_u) != total_u:
            dif = _de_unidades(total_u - sum(partes_u), decimales)
            raise DivisionInvalida(f"Los montos no suman el total (diferencia de {dif:g})")

    return {pid: _de_unidades(u, decimales) for pid, u in zip(ids, partes_u)}


def calcular_saldos(gastos: list[dict], liquidaciones: list[dict], decimales: int = 0) -> dict[str, float]:
    """
    Saldo neto por persona dentro de UNA moneda. Positivo = le deben; negativo = debe.
      gasto: {"pagador": id, "partes": {id: monto}}
      liquidacion: {"de": id (quien paga), "a": id (quien recibe), "monto": n}
    La suma de todos los saldos es siempre 0.
    """
    neto: dict[str, int] = {}
    for g in gastos:
        partes = {k: _a_unidades(v, decimales) for k, v in g["partes"].items()}
        neto[g["pagador"]] = neto.get(g["pagador"], 0) + sum(partes.values())
        for pid, u in partes.items():
            neto[pid] = neto.get(pid, 0) - u
    for l in liquidaciones:
        u = _a_unidades(l["monto"], decimales)
        neto[l["de"]] = neto.get(l["de"], 0) + u
        neto[l["a"]] = neto.get(l["a"], 0) - u
    return {k: _de_unidades(v, decimales) for k, v in neto.items()}


def saldos_con(yo: str, gastos: list[dict], liquidaciones: list[dict], decimales: int = 0) -> dict[str, float]:
    """
    Saldo directo de cada persona CONTRA MÍ (positivo = esa persona me debe).
    Solo cuenta lo que pasa entre esa persona y yo: si Ana pagó y Beto le debe,
    eso no aparece aquí (ver `simplificar_deudas` para el panorama del grupo).
    """
    res: dict[str, int] = {}
    for g in gastos:
        partes = {k: _a_unidades(v, decimales) for k, v in g["partes"].items()}
        if g["pagador"] == yo:
            for pid, u in partes.items():
                if pid != yo:
                    res[pid] = res.get(pid, 0) + u
        elif yo in partes:
            res[g["pagador"]] = res.get(g["pagador"], 0) - partes[yo]
    for l in liquidaciones:
        u = _a_unidades(l["monto"], decimales)
        if l["de"] == yo:      # yo pagué: esa persona me debe más / yo le debo menos
            res[l["a"]] = res.get(l["a"], 0) + u
        elif l["a"] == yo:     # me pagaron: me debe menos
            res[l["de"]] = res.get(l["de"], 0) - u
    return {k: _de_unidades(v, decimales) for k, v in res.items() if v != 0}


def simplificar_deudas(saldos: dict[str, float], decimales: int = 0) -> list[dict]:
    """
    Reduce las deudas del grupo a pocos pagos: el que más debe le paga al
    que más le deben, y así hasta saldar (voraz; a lo sumo n-1 pagos).
    Devuelve [{"de": deudor, "a": acreedor, "monto": n}].
    """
    u = {k: _a_unidades(v, decimales) for k, v in saldos.items()}
    if sum(u.values()) != 0:
        raise DivisionInvalida("Los saldos del grupo no suman cero")
    deudores = [[k, -v] for k, v in sorted(u.items(), key=lambda x: (x[1], x[0])) if v < 0]
    acreedores = [[k, v] for k, v in sorted(u.items(), key=lambda x: (-x[1], x[0])) if v > 0]
    deudores.sort(key=lambda x: (-x[1], x[0]))
    pagos = []
    i = j = 0
    while i < len(deudores) and j < len(acreedores):
        monto = min(deudores[i][1], acreedores[j][1])
        pagos.append({"de": deudores[i][0], "a": acreedores[j][0], "monto": _de_unidades(monto, decimales)})
        deudores[i][1] -= monto
        acreedores[j][1] -= monto
        if deudores[i][1] == 0:
            i += 1
        if acreedores[j][1] == 0:
            j += 1
    return pagos
