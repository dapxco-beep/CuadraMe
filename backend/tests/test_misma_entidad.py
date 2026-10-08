"""Dos cuentas del MISMO banco (datos sintéticos): 'Nu Colombia' (ahorro) y 'Nu Tarjeta' (crédito).

El tipo de producto (crédito/débito) desempata cuando el nombre del banco no basta; si de
verdad es ambiguo no se adivina: se pregunta (correos/extractos) o se avisa (atajo de Wallet).
El pago de la tarjeta Nu desde la cuenta Nu sigue siendo neutral (no es gasto ni ingreso)."""
import os
import tempfile
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'mismaent.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.contabilidad import tipos_efectivos  # noqa: E402
from app.cuentas_banco import aviso_cuenta_distinta, producto_de_texto  # noqa: E402
from app.extractos_gmail import inferir_cuenta_por_remitente, sugerir_cuenta  # noqa: E402
from app.main import app  # noqa: E402
from app.wallet import mapear_cuenta, mapear_cuenta_ex  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="me-0", email="me@test.com", nombre="ME")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def _c(id, nombre, tipo, alias=None):
    return SimpleNamespace(id=id, nombre=nombre, tipo=tipo, alias_tarjeta=alias, moneda="COP")


AHORRO = _c("a", "Nu Colombia", "ahorro")
TARJETA = _c("t", "Nu Tarjeta", "credito")
CUENTAS = [AHORRO, TARJETA]


# ---------- tipo de producto según el texto ----------

@pytest.mark.parametrize("texto,esperado", [
    ("Tu extracto de tarjeta de crédito Nu: cupo disponible, fecha de pago, pago mínimo", "credito"),
    ("Pago mínimo $50.000 antes de la fecha de pago", "credito"),
    ("Extracto de tu cuenta de ahorros. Saldo disponible $1.000.000", "debito"),
    ("Moviste $20.000 a tu Cajita", "debito"),
    ("Compra con tu tarjeta de crédito terminada en 1234", "credito"),
    ("Compra con tu tarjeta débito terminada en 9876", "debito"),
    ("Hola, te escribimos de Nu", None),
    ("", None),
])
def test_producto_de_texto(texto, esperado):
    assert producto_de_texto(texto) == esperado


# ---------- extractos y correos (Gmail) ----------

def test_extracto_de_tarjeta_va_a_la_cuenta_credito():
    texto = "NU COLOMBIA. Extracto de tarjeta de crédito. Cupo total, fecha de pago 15/10/2026, pago mínimo $80.000"
    assert sugerir_cuenta("Nu Colombia", "", CUENTAS, texto) == "t"


def test_extracto_de_ahorros_va_a_la_cuenta_debito():
    texto = "Extracto de tu cuenta de ahorros. Saldo disponible $2.500.000. Movimientos de la Cajita"
    assert sugerir_cuenta("Nu Colombia", "", CUENTAS, texto) == "a"


def test_sin_pistas_no_se_adivina():
    assert sugerir_cuenta("Nu Colombia", "", CUENTAS, "Extracto del mes de septiembre") is None
    assert sugerir_cuenta("Nu Colombia", "", CUENTAS) is None


def test_ultimos4_en_alias_manda_sobre_el_tipo():
    tarjeta = _c("t", "Nu Tarjeta", "credito", alias="Visa 4321")
    cuentas = [AHORRO, tarjeta]
    assert sugerir_cuenta("Nu Colombia", "4321", cuentas, "cuenta de ahorros") == "t"


def test_correo_de_compra_con_tarjeta_de_credito_o_debito():
    rem = "Nu <notificaciones@nu.com.co>"
    _, sug, falta = inferir_cuenta_por_remitente(rem, CUENTAS, "Compra aprobada con tu tarjeta de crédito por $45.000")
    assert (sug, falta) == ("t", False)
    _, sug, _ = inferir_cuenta_por_remitente(rem, CUENTAS, "Compra aprobada con tu tarjeta débito por $45.000")
    assert sug == "a"
    banco, sug, falta = inferir_cuenta_por_remitente(rem, CUENTAS, "Compra aprobada por $45.000")
    assert banco == "Nu Colombia" and sug is None and falta is False  # ambiguo: hay que preguntar


def test_aviso_si_el_extracto_parece_de_otro_producto():
    aviso = aviso_cuenta_distinta(AHORRO, "tarjeta de crédito, cupo, pago mínimo", CUENTAS)
    assert aviso and "Nu Tarjeta" in aviso
    assert aviso_cuenta_distinta(TARJETA, "tarjeta de crédito, cupo, pago mínimo", CUENTAS) is None
    assert aviso_cuenta_distinta(AHORRO, "texto sin pistas", CUENTAS) is None


# ---------- Wallet / Atajo: mapear_cuenta ----------

def test_wallet_nombre_exacto_de_la_tarjeta_manda():
    assert mapear_cuenta(CUENTAS, "Nu Tarjeta")[0] is TARJETA
    assert mapear_cuenta(CUENTAS, "Nu Colombia")[0] is AHORRO


def test_wallet_el_tipo_desempata_cuando_el_nombre_es_solo_el_banco():
    cuenta, como, empate = mapear_cuenta_ex(CUENTAS, "Nu Visa Crédito")
    assert cuenta is TARJETA and como == "tipo" and empate == []
    cuenta, como, _ = mapear_cuenta_ex(CUENTAS, "Nu Débito")
    assert cuenta is AHORRO and como == "tipo"


def test_wallet_alias_y_digitos_mandan_sobre_el_tipo():
    tarjeta = _c("t", "Nu Tarjeta", "credito", alias="Mastercard 5555")
    cuentas = [AHORRO, tarjeta]
    assert mapear_cuenta(cuentas, "Nu Débito ••5555")[0] is tarjeta  # los 4 dígitos son de la tarjeta
    assert mapear_cuenta(cuentas, "Mastercard")[0] is tarjeta


def test_wallet_ambiguo_devuelve_el_empate_y_prefiere_la_de_uso_reciente():
    cuenta, como, empate = mapear_cuenta_ex(CUENTAS, "Nu")
    assert como == "empate" and {c.id for c in empate} == {"a", "t"}
    uso = {"a": datetime(2026, 10, 1), "t": datetime(2026, 10, 5)}
    cuenta, como, empate = mapear_cuenta_ex(CUENTAS, "Nu", ultimo_uso=uso)
    assert cuenta is TARJETA and como == "empate" and len(empate) == 2


# ---------- Atajo por API ----------

def _usuario_nu(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)
    ids = {}
    for body in (
        {"nombre": "Nu Colombia", "tipo": "ahorro", "saldo": 1_000_000},
        {"nombre": "Nu Tarjeta", "tipo": "credito", "saldo": -200_000, "cupo_total": 3_000_000},
    ):
        r = client.post("/cuentas", json=body)
        assert r.status_code == 200, r.text
        ids[body["nombre"]] = r.json()["id"]
    return client.get("/perfil/api-key").json()["api_key"], ids


def _rapido(key, **extra):
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={"monto": "12.000", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_atajo_resuelve_por_tipo_y_avisa_solo_si_es_ambiguo():
    key, ids = _usuario_nu("me-atajo")
    m = _rapido(key, comercio="Tienda A", tarjeta="Nu Visa Crédito")
    assert m["cuenta_id"] == ids["Nu Tarjeta"] and "Ojo" not in m["mensaje"]
    m = _rapido(key, comercio="Tienda B", tarjeta="Nu Débito")
    assert m["cuenta_id"] == ids["Nu Colombia"] and "Ojo" not in m["mensaje"]
    # Ni dígitos, ni alias, ni tipo: se registra en la de uso más reciente (la de la tienda B) y se avisa.
    m = _rapido(key, comercio="Tienda C", tarjeta="Nu")
    assert m["cuenta_id"] == ids["Nu Colombia"] and m["por_confirmar"] is True
    assert "Nu Tarjeta" in m["mensaje"] and "Alias de la tarjeta" in m["mensaje"]


# ---------- Contabilidad: el pago de la tarjeta Nu desde Nu es neutral ----------

TIPOS = {"a": "ahorro", "t": "credito"}


def _m(id, tipo, monto, desc, cuenta, categoria="Otros"):
    return {"id": id, "tipo": tipo, "monto": monto, "descripcion": desc, "cuenta_id": cuenta,
            "categoria": categoria, "fecha": datetime(2026, 10, 5, 12), "fuente": "importacion_archivo", "notas": ""}


@pytest.mark.parametrize("descripcion", [
    "Pago tarjeta de crédito Nu", "Pago Nu Tarjeta", "Abono a tarjeta Nu", "PAGO NU TC",
])
def test_pago_de_tarjeta_nu_desde_cuenta_nu_es_neutral(descripcion):
    te = tipos_efectivos([
        _m("sale", "expense", 300_000, descripcion, "a"),
        _m("entra", "income", 300_000, "Pago recibido", "t"),
    ], TIPOS)
    assert te == {"sale": "transfer", "entra": "transfer"}


def test_la_compra_con_tarjeta_nu_sigue_siendo_gasto():
    te = tipos_efectivos([_m("c", "expense", 45_000, "Compra con tarjeta Nu en Éxito", "t")], TIPOS)
    assert te == {"c": "expense"}
    te = tipos_efectivos([_m("c2", "expense", 45_000, "Pago con tarjeta Nu en Éxito", "a")], TIPOS)
    assert te == {"c2": "expense"}
