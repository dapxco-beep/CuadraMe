"""Registro desde Apple Wallet / Atajos: lectura tolerante de lo que entrega el
disparador personal 'Transacción' de iOS (comercio, monto, tarjeta, fecha).

El Atajo manda los campos tal como los entrega iOS: el monto puede venir como
número, como texto con símbolo ("$45.000,00") o con coma/punto colombianos, y
el nombre de la tarjeta es libre ("Visa Bancolombia", "Apple Card ••1234").
Todo lo de aquí es puro (sin base de datos) para poder probarlo fácil.
"""
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from app.cuentas_banco import filtrar_por_producto, palabras_marca, producto_de_cuenta, producto_de_texto

# Fuentes que nacen de un registro automático y piden "¿es tuyo?" al usuario.
FUENTES_POR_CONFIRMAR = ("wallet", "apple_pay", "google_pay", "shortcut", "sms", "cierre_app")
ORIGEN_WALLET = "wallet"
ORIGEN_ATAJO = "atajo"
ORIGEN_CIERRE_APP = "cierre_app"
# Movimientos que el usuario registró "a mano rápida" y que el extracto debe
# completar: son los únicos candidatos para el cruce con el banco.
ORIGENES_RAPIDOS = ("wallet", "atajo", "cierre_app", "voz")

_ZONA_CO = timezone(timedelta(hours=-5))


def parse_monto_co(valor) -> float:
    """Convierte un monto en cualquier formato razonable a un float positivo.

    '45.000' -> 45000 (en Colombia el punto separa miles), '45.000,50' -> 45000.5,
    '1,234.56' -> 1234.56, '12,5' -> 12.5, '$ 1.200.000' -> 1200000, 'COP 8000' -> 8000.
    Un único separador seguido de exactamente 3 dígitos es de miles; en otro
    caso es decimal. Lanza ValueError si no hay un monto positivo."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError("Monto inválido")
    if isinstance(valor, (int, float)):
        numero = abs(float(valor))
    else:
        s = re.sub(r"[^\d.,]", "", str(valor))
        if not re.search(r"\d", s):
            raise ValueError("Monto inválido")
        if "." in s and "," in s:
            # El último separador es el decimal; el otro es de miles.
            dec = "," if s.rfind(",") > s.rfind(".") else "."
            miles = "." if dec == "," else ","
            s = s.replace(miles, "").replace(dec, ".")
        elif "." in s or "," in s:
            sep = "." if "." in s else ","
            partes = s.split(sep)
            if len(partes) > 2:
                s = "".join(partes)  # 1.234.567 -> miles
            else:
                antes, despues = partes
                if len(despues) == 3 and antes not in ("", "0"):
                    s = antes + despues  # 45.000 -> miles
                else:
                    s = antes + "." + despues  # 12,5 / 0.500 -> decimal
        try:
            numero = float(s)
        except ValueError:
            raise ValueError("Monto inválido")
    if not numero > 0 or numero != numero or numero == float("inf"):
        raise ValueError("El monto debe ser mayor que cero")
    return round(numero, 2)


_FORMATOS_FECHA = (
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%d-%m-%Y %H:%M", "%d-%m-%Y",
)


def parse_fecha(valor) -> datetime | None:
    """Fecha del Atajo -> datetime 'naive' en hora de Colombia, o None si no se
    entiende (el llamador usa entonces la hora actual)."""
    if not valor:
        return None
    s = str(valor).strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is not None:
            d = d.astimezone(_ZONA_CO).replace(tzinfo=None)
        return d
    except ValueError:
        pass
    for fmt in _FORMATOS_FECHA:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def fecha_razonable(fecha: datetime | None, ahora: datetime) -> datetime:
    """Una compra con Wallet es de 'ahora': si la fecha no viene, o viene
    absurda (futuro lejano o más de 7 días atrás), se usa la hora actual."""
    if fecha is None or fecha > ahora + timedelta(days=1) or fecha < ahora - timedelta(days=7):
        return ahora
    return fecha


def _norm(texto: str | None) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()


def alias_de(cuenta) -> list[str]:
    """Alias de tarjeta de una cuenta: varios separados por coma, punto y coma o |."""
    bruto = getattr(cuenta, "alias_tarjeta", None) or ""
    return [a for a in (_norm(x) for x in re.split(r"[,;|\n]", bruto)) if a]


def coincide_cuenta(cuenta, nombre: str | None) -> bool:
    """¿El nombre pedido ('Nequi') corresponde a esta cuenta, por nombre o alias?
    Sirve para avisar cuando el registro cayó en otra cuenta por no encontrar la pedida."""
    cn = _norm(nombre)
    if not cn:
        return True
    return cn in _norm(cuenta.nombre) or any(cn in a for a in alias_de(cuenta))


def _decidir_empate(grupo: list, producto: str | None, ultimo_uso: dict | None):
    """De varias cuentas que encajan igual: 1) el TIPO (crédito/débito) según el texto de la
    tarjeta; 2) si sigue el empate, la de uso más reciente. Devuelve (cuenta, empate) donde
    `empate` lista las cuentas que quedaron empatadas (vacío si se resolvió bien)."""
    grupo = filtrar_por_producto(grupo, producto)
    if len(grupo) == 1:
        return grupo[0], []
    uso = ultimo_uso or {}
    elegida = max(grupo, key=lambda c: (uso.get(c.id) is not None, uso.get(c.id) or 0))
    return elegida, grupo


def mapear_cuenta_ex(cuentas: list, tarjeta: str | None, cuenta_nombre: str | None = None,
                     moneda: str | None = None, ultimo_uso: dict | None = None):
    """Como `mapear_cuenta` pero devuelve (cuenta, como, empate).

    `como` agrega: tipo (el texto decía crédito/débito y eso desempató) y empate (de verdad
    había dos cuentas posibles del mismo banco y no hay dígitos, alias ni pista de tipo:
    se toma la de uso más reciente según `ultimo_uso` {cuenta_id: fecha} y `empate` trae
    las candidatas para avisarle a la persona)."""
    if not cuentas:
        return None, None, []
    if moneda:
        misma = [c for c in cuentas if (c.moneda or "COP").upper() == moneda.upper()]
        if misma:
            cuentas = misma
    t = _norm(tarjeta)
    producto = producto_de_texto(f"{tarjeta or ''} {cuenta_nombre or ''}")

    if t:
        mejor, puntaje = None, 0
        for c in cuentas:
            for a in alias_de(c):
                if len(a) >= 3 and (a in t or t in a) and len(a) > puntaje:
                    mejor, puntaje = c, len(a)
        if mejor:
            return mejor, "alias", []

        ultimos = re.findall(r"\d{4}", t)
        if ultimos:
            d = ultimos[-1]
            for c in cuentas:
                if any(d in a for a in alias_de(c)) or d in _norm(c.nombre):
                    return c, "digitos", []

        palabras_t = {w for w in t.split() if len(w) >= 4}
        marca_t = palabras_marca(t)
        puntajes = []
        for c in cuentas:
            n = _norm(c.nombre)
            if len(n) >= 3 and n in t:
                p = 100 + len(n)
            elif len(n) >= 3 and t in n:
                # La tarjeta es solo una parte del nombre ('Nu' dentro de 'Nu Colombia' y 'Nu Tarjeta'):
                # vale lo que coincide, no el largo del nombre; así un nombre más largo no gana por serlo.
                p = 100 + len(t)
            else:
                p = sum(len(w) for w in set(n.split()) & palabras_t)
                if not p:  # marca corta ('nu', 'rappi'): vale menos que un nombre completo
                    p = sum(len(w) for w in palabras_marca(n) & marca_t)
            if p:
                puntajes.append((p, c))
        if puntajes:
            tope = max(p for p, _ in puntajes)
            grupo = [c for p, c in puntajes if p == tope]
            # El texto dice crédito/débito pero la ganadora es del otro tipo: si otra cuenta
            # del mismo banco sí es del tipo pedido, esa manda.
            if producto and not any(producto_de_cuenta(c) == producto for c in grupo):
                otras = [c for _, c in puntajes if producto_de_cuenta(c) == producto]
                if len(otras) == 1:
                    return otras[0], "tipo", []
            cuenta, empate = _decidir_empate(grupo, producto, ultimo_uso)
            if empate:
                return cuenta, "empate", empate
            return cuenta, ("tipo" if len(grupo) > 1 else "nombre"), []

    cn = _norm(cuenta_nombre)
    if cn:
        grupo = [c for c in cuentas if cn in _norm(c.nombre) or any(cn in a for a in alias_de(c))]
        if grupo:
            cuenta, empate = _decidir_empate(grupo, producto, ultimo_uso)
            if empate:
                return cuenta, "empate", empate
            return cuenta, ("tipo" if len(grupo) > 1 else "cuenta"), []

    return cuentas[0], "primera", []


def mapear_cuenta(cuentas: list, tarjeta: str | None, cuenta_nombre: str | None = None, moneda: str | None = None):
    """Elige la cuenta del usuario a la que corresponde el pago.

    Devuelve (cuenta, como) con como en: alias | digitos | nombre | tipo | cuenta | empate | primera.
    Orden: alias de tarjeta (parcial) -> últimos 4 dígitos -> nombre de la cuenta
    contra el de la tarjeta (con el TIPO crédito/débito como desempate cuando el banco tiene
    varias cuentas) -> parámetro 'cuenta' -> la primera cuenta."""
    cuenta, como, _ = mapear_cuenta_ex(cuentas, tarjeta, cuenta_nombre, moneda)
    return cuenta, como


def formato_cop(monto: float) -> str:
    """45000 -> '$45.000' (punto de miles colombiano)."""
    if abs(monto - round(monto)) < 0.005:
        return "$" + f"{int(round(monto)):,}".replace(",", ".")
    return "$" + f"{monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
