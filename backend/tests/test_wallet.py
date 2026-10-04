"""Registro con Apple Wallet: montos colombianos, tarjeta -> cuenta, idempotencia,
movimiento 'por confirmar' (y su bandeja) y el recordatorio nocturno."""
import os
import tempfile
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'wallet.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Movimiento, Perfil  # noqa: E402
from app.utiles import ahora_co  # noqa: E402
from app.wallet import fecha_razonable, mapear_cuenta, parse_fecha, parse_monto_co  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="w-0", email="w@test.com", nombre="W")}
CRON = {"X-Cron-Secret": "secreto-de-prueba"}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


def _usuario(uid, cuentas):
    """Crea un usuario con cuentas [(nombre, alias, saldo)] y devuelve (api_key, ids por nombre)."""
    como(uid)
    ids = {}
    for nombre, alias, saldo in cuentas:
        body = {"nombre": nombre, "saldo": saldo}
        if alias:
            body["alias_tarjeta"] = alias
        r = client.post("/cuentas", json=body)
        assert r.status_code == 200, r.text
        ids[nombre] = r.json()["id"]
    return client.get("/perfil/api-key").json()["api_key"], ids


def _saldos():
    return {c["nombre"]: c["saldo"] for c in client.get("/cuentas").json()}


# ---------- montos colombianos ----------

@pytest.mark.parametrize("entrada,esperado", [
    (45000, 45000),
    (45000.5, 45000.5),
    ("45000", 45000),
    ("45.000", 45000),
    ("45.000,00", 45000),
    ("45.000,50", 45000.5),
    ("$ 1.200.000", 1_200_000),
    ("1.200.000,99", 1_200_000.99),
    ("1,234.56", 1234.56),
    ("12,5", 12.5),
    ("12.50", 12.5),
    ("0.500", 0.5),
    ("COP 8000", 8000),
    ("US$ 12.99", 12.99),
    ("-45.000", 45000),
    ("1,500", 1500),
])
def test_parseo_de_montos_colombianos(entrada, esperado):
    assert parse_monto_co(entrada) == pytest.approx(esperado)


@pytest.mark.parametrize("malo", ["", "abc", None, 0, "0", "-0,00", True])
def test_monto_invalido_se_rechaza(malo):
    with pytest.raises(ValueError):
        parse_monto_co(malo)


def test_fechas_del_atajo():
    assert parse_fecha("2026-10-03T20:15:00-05:00").hour == 20
    assert parse_fecha("2026-10-04T01:15:00Z").hour == 20  # UTC -> hora Colombia
    assert parse_fecha("03/10/2026 8:15") is None or parse_fecha("03/10/2026 08:15").day == 3
    assert parse_fecha("cualquier cosa") is None
    ahora = ahora_co()
    assert fecha_razonable(None, ahora) == ahora
    assert fecha_razonable(parse_fecha("2020-01-01"), ahora) == ahora  # absurda: se usa ahora


# ---------- tarjeta -> cuenta ----------

def _c(nombre, alias=None, moneda="COP"):
    return SimpleNamespace(nombre=nombre, alias_tarjeta=alias, moneda=moneda)


def test_mapeo_por_alias_nombre_y_digitos():
    visa = _c("Visa Bancolombia", "Visa 1234, Débito Ahorros")
    nequi = _c("Nequi")
    efectivo = _c("Efectivo")
    cuentas = [efectivo, nequi, visa]
    assert mapear_cuenta(cuentas, "Débito ahorros ••5678")[0] is visa      # alias parcial, sin tildes/mayúsculas
    assert mapear_cuenta(cuentas, "Apple Card ••1234")[0] is visa          # últimos 4 dígitos del alias
    assert mapear_cuenta(cuentas, "NEQUI")[0] is nequi                     # nombre de la cuenta
    assert mapear_cuenta(cuentas, "Mi Visa Bancolombia Gold")[0] is visa   # nombre contenido
    assert mapear_cuenta(cuentas, "Tarjeta rara", "efectivo")[0] is efectivo  # parámetro legado 'cuenta'
    cuenta, como_ = mapear_cuenta(cuentas, "Tarjeta rara")
    assert cuenta is efectivo and como_ == "primera"
    assert mapear_cuenta([], "x") == (None, None)


def test_mapeo_prefiere_la_cuenta_de_la_misma_moneda():
    cop = _c("Banco")
    usd = _c("Wise", moneda="USD")
    assert mapear_cuenta([cop, usd], "tarjeta cualquiera", moneda="USD")[0] is usd


# ---------- /movimientos/rapido ----------

def test_transaccion_de_wallet_crea_movimiento_por_confirmar_y_mueve_saldo():
    key, ids = _usuario("w-basico", [("Efectivo", None, 100_000), ("Visa Bancolombia", "Visa 1234", 500_000)])
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={
        "comercio": "Juan Valdez", "monto": "18.500,00", "tarjeta": "Visa ••1234", "moneda": "COP",
        "fecha": ahora_co().isoformat(),
    })
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["monto"] == 18_500 and m["tipo"] == "expense" and m["descripcion"] == "Juan Valdez"
    assert m["fuente"] == "wallet" and m["cat_origen"] == "wallet" and m["cat_confirmada"] is False
    assert m["por_confirmar"] is True and m["duplicado"] is False
    assert m["cuenta_id"] == ids["Visa Bancolombia"] and m["cuenta_nombre"] == "Visa Bancolombia"
    assert "$18.500" in m["mensaje"] and "Juan Valdez" in m["mensaje"]
    assert _saldos()["Visa Bancolombia"] == 500_000 - 18_500  # el saldo cambia de inmediato

    # aparece en 'Por revisar' y en la bandeja por confirmar
    revisar = client.get("/movimientos?por_revisar=true").json()
    assert m["id"] in [x["id"] for x in revisar]
    assert m["id"] in [x["id"] for x in client.get("/movimientos/por-confirmar").json()]


def test_nombres_en_ingles_de_ios_y_monto_numerico():
    key, _ = _usuario("w-ingles", [("Banco", None, 0)])
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key},
                    json={"merchant": "Spotify", "amount": 16900, "card": "Banco"})
    assert r.status_code == 200, r.text
    assert r.json()["descripcion"] == "Spotify" and r.json()["monto"] == 16900


def test_compatibilidad_con_el_formato_anterior_del_atajo():
    key, ids = _usuario("w-legado", [("Efectivo", None, 50_000)])
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key},
                    json={"monto": 12_000, "tipo": "expense", "descripcion": "Tinto", "cuenta": "Efectivo"})
    assert r.status_code == 200, r.text
    assert r.json()["cuenta_id"] == ids["Efectivo"] and r.json()["fuente"] == "shortcut"
    assert r.json()["cat_origen"] == "atajo" and r.json()["por_confirmar"] is True


def test_sin_comercio_ni_descripcion_o_con_monto_malo_da_422():
    key, _ = _usuario("w-422", [("Banco", None, 0)])
    assert client.post("/movimientos/rapido", headers={"X-Api-Key": key}, json={"monto": "5.000"}).status_code == 422
    assert client.post("/movimientos/rapido", headers={"X-Api-Key": key},
                       json={"comercio": "X", "monto": "mucho"}).status_code == 422
    assert client.post("/movimientos/rapido", headers={"X-Api-Key": "falsa"},
                       json={"comercio": "X", "monto": 1}).status_code == 401


def test_duplicado_dentro_de_dos_minutos_devuelve_el_existente():
    key, _ = _usuario("w-dup", [("Banco", None, 200_000)])
    cuerpo = {"comercio": "Rappi", "monto": "32.000", "tarjeta": "Banco"}
    h = {"X-Api-Key": key}
    a = client.post("/movimientos/rapido", headers=h, json=cuerpo)
    b = client.post("/movimientos/rapido", headers=h, json=cuerpo)
    assert a.status_code == 200 and b.status_code == 200
    assert b.json()["id"] == a.json()["id"] and b.json()["duplicado"] is True
    assert _saldos()["Banco"] == 200_000 - 32_000  # no se descontó dos veces
    assert len(client.get("/movimientos").json()) == 1
    # otro monto o otro comercio sí son movimientos distintos
    client.post("/movimientos/rapido", headers=h, json={**cuerpo, "monto": "33.000"})
    client.post("/movimientos/rapido", headers=h, json={**cuerpo, "comercio": "Uber"})
    assert len(client.get("/movimientos").json()) == 3


def test_mismo_pago_con_dos_horas_de_diferencia_no_es_duplicado():
    key, _ = _usuario("w-dup2", [("Banco", None, 0)])
    h = {"X-Api-Key": key}
    ahora = ahora_co()
    base = {"comercio": "Cine", "monto": 20_000}
    client.post("/movimientos/rapido", headers=h, json={**base, "fecha": (ahora - timedelta_horas(3)).isoformat()})
    r = client.post("/movimientos/rapido", headers=h, json={**base, "fecha": ahora.isoformat()})
    assert r.json()["duplicado"] is False


def timedelta_horas(h):
    from datetime import timedelta
    return timedelta(hours=h)


def test_moneda_distinta_a_la_cuenta_se_anota_y_convierte(monkeypatch):
    from app.routers import movimientos as mod
    monkeypatch.setattr(mod, "convertir_a_cop", lambda monto, moneda: monto * 4000)
    key, _ = _usuario("w-usd", [("Banco", None, 1_000_000)])
    r = client.post("/movimientos/rapido", headers={"X-Api-Key": key},
                    json={"comercio": "Amazon", "monto": "10,00", "moneda": "USD", "tarjeta": "Banco"})
    assert r.status_code == 200, r.text
    assert r.json()["monto"] == 40_000 and "Original: 10 USD" in r.json()["notas"]


def test_voz_acepta_tarjeta_y_no_queda_por_confirmar():
    key, ids = _usuario("w-voz", [("Efectivo", None, 0), ("Nequi", "nequi", 0)])
    r = client.post("/movimientos/rapido-voz", headers={"X-Api-Key": key},
                    json={"texto": "gasté 20 mil en el almuerzo", "tarjeta": "Nequi"})
    assert r.status_code == 200 and r.json()["entendido"]
    assert r.json()["movimiento"]["cuenta_id"] == ids["Nequi"]
    assert r.json()["movimiento"]["cat_origen"] != "wallet"


# ---------- bandeja: confirmar / editar / descartar ----------

def test_bandeja_confirmar_editar_y_descartar_revierte_saldo():
    key, _ = _usuario("w-bandeja", [("Banco", None, 100_000)])
    h = {"X-Api-Key": key}
    ids = [client.post("/movimientos/rapido", headers=h, json={"comercio": c, "monto": m, "tarjeta": "Banco"}).json()["id"]
           for c, m in (("Tienda A", 10_000), ("Tienda B", 20_000), ("Tienda C", 5_000))]
    assert _saldos()["Banco"] == 100_000 - 35_000
    assert len(client.get("/movimientos/por-confirmar").json()) == 3

    # confirmar uno
    assert client.post("/movimientos/confirmar-categorias", json={"movimiento_ids": [ids[0]]}).json()["confirmados"] == 1
    # editar monto y confirmar
    assert client.put(f"/movimientos/{ids[1]}", json={"monto": 25_000}).status_code == 200
    client.post("/movimientos/confirmar-categorias", json={"movimiento_ids": [ids[1]]})
    assert _saldos()["Banco"] == 100_000 - 40_000
    # descartar el tercero devuelve el dinero
    assert client.delete(f"/movimientos/{ids[2]}").status_code == 200
    assert _saldos()["Banco"] == 100_000 - 35_000
    assert client.get("/movimientos/por-confirmar").json() == []


def test_bandeja_ignora_movimientos_viejos_y_de_otras_fuentes():
    key, _ = _usuario("w-viejos", [("Banco", None, 0)])
    manual = client.post("/cuentas", json={"nombre": "Otra", "saldo": 0}).json()["id"]
    client.post("/movimientos", json={"cuenta_id": manual, "descripcion": "Uber", "monto": 9000, "tipo": "expense"})
    db = SessionLocal()
    try:
        cuenta_id = client.get("/cuentas").json()[0]["id"]
        from datetime import timedelta
        db.add(Movimiento(usuario_id="w-viejos", cuenta_id=cuenta_id, descripcion="Viejo", categoria="Otros",
                          tipo="expense", monto=1, fecha=ahora_co() - timedelta(days=40), fuente="wallet",
                          cat_origen="wallet", cat_confirmada=False))
        db.commit()
    finally:
        db.close()
    assert client.get("/movimientos/por-confirmar").json() == []


# ---------- alias de tarjeta y recordatorio ----------

def test_alias_de_tarjeta_se_guarda_y_edita():
    _usuario("w-alias", [("Banco", "Visa 1234", 0)])
    cuenta = client.get("/cuentas").json()[0]
    assert cuenta["alias_tarjeta"] == "Visa 1234"
    r = client.put(f"/cuentas/{cuenta['id']}", json={"alias_tarjeta": "Mastercard 9999"})
    assert r.json()["alias_tarjeta"] == "Mastercard 9999"


def test_recordatorio_diario_preferencia_y_cron(monkeypatch):
    from app.routers import push as mod
    enviados = []
    monkeypatch.setattr(mod, "enviar_push", lambda db, uid, t, c, u="/": enviados.append(uid) or 1)

    _usuario("w-rec-si", [("Banco", None, 0)])
    assert client.get("/perfil/recordatorio-diario").json() == {"activo": False}
    assert client.put("/perfil/recordatorio-diario", json={"activo": True}).json() == {"activo": True}
    _usuario("w-rec-hoy", [("Banco", None, 0)])
    client.put("/perfil/recordatorio-diario", json={"activo": True})
    cid = client.get("/cuentas").json()[0]["id"]
    client.post("/movimientos", json={"cuenta_id": cid, "descripcion": "Café", "monto": 3000, "tipo": "expense"})
    _usuario("w-rec-no", [("Banco", None, 0)])  # no activó el recordatorio

    assert client.post("/push/cron/recordar-registro").status_code == 401
    r = client.post("/push/cron/recordar-registro?forzar=true", headers=CRON).json()
    assert "w-rec-si" in enviados            # activó y no registró nada hoy
    assert "w-rec-hoy" not in enviados       # ya registró hoy
    assert "w-rec-no" not in enviados        # no lo activó
    assert r["enviados"] >= 1

    # idempotente el mismo día
    antes = len(enviados)
    client.post("/push/cron/recordar-registro?forzar=true", headers=CRON)
    assert len(enviados) == antes
    db = SessionLocal()
    try:
        assert db.query(Perfil).filter(Perfil.usuario_id == "w-rec-si").first().ultimo_recordatorio == ahora_co().strftime("%Y-%m-%d")
    finally:
        db.close()


def test_recordatorio_no_envia_antes_de_las_8pm(monkeypatch):
    from app.routers import push as mod
    enviados = []
    monkeypatch.setattr(mod, "enviar_push", lambda *a, **k: enviados.append(1) or 1)
    monkeypatch.setattr(mod, "ahora_co", lambda: ahora_co().replace(hour=15))
    r = client.post("/push/cron/recordar-registro", headers=CRON).json()
    assert r["enviados"] == 0 and not enviados


def test_rapido_acepta_claves_con_mayusculas_y_en_espanol():
    """El Atajo puede enviar 'Comercio', 'Importe' o 'Tarjeta o pase' tal cual."""
    from app.schemas import MovimientoRapidoCreate

    m = MovimientoRapidoCreate.model_validate(
        {"Comercio": "Juan Valdez", "Importe": "45.000,00", "Tarjeta o pase": "Nu Débito"}
    )
    assert m.comercio == "Juan Valdez" and m.monto == 45000 and m.tarjeta == "Nu Débito"


def test_errores_del_atajo_traen_mensaje_legible():
    """El Atajo muestra 'mensaje' como notificación: aun con error debe decir qué pasó."""
    clave, _ = _usuario("w-err", [("Nequi", None, 0)])
    url = "/movimientos/rapido"

    # Sin clave: antes salía un 422 mudo.
    r = client.post(url, json={"monto": 1000, "descripcion": "x"})
    assert r.status_code == 422
    assert "clave" in r.json()["mensaje"].lower() and r.json()["ok"] is False

    # Clave inválida.
    r = client.post(url, json={"monto": 1000, "descripcion": "x"}, headers={"X-Api-Key": "cm_mala"})
    assert r.status_code == 401
    assert "clave" in r.json()["mensaje"].lower()

    # Monto ausente o cero, con clave buena: dice que no entendió el monto.
    for cuerpo in ({"descripcion": "x"}, {"monto": 0, "descripcion": "x"}, {"monto": "abc", "descripcion": "x"}):
        r = client.post(url, json=cuerpo, headers={"X-Api-Key": clave})
        assert r.status_code == 422, cuerpo
        assert "monto" in r.json()["mensaje"].lower(), r.json()

    # El mensaje nunca repite el valor enviado.
    r = client.post(url, json={"monto": "dato-sensible-123", "descripcion": "x"}, headers={"X-Api-Key": clave})
    assert "dato-sensible-123" not in r.json()["mensaje"]

    # Otras rutas conservan la respuesta estándar de FastAPI (sin 'mensaje').
    r = client.post("/movimientos", json={})
    assert r.status_code == 422 and "mensaje" not in r.json()


def test_cierre_avisa_si_la_cuenta_pedida_no_existe_y_no_si_existe():
    """Si el Atajo pide 'Nequi' y no hay tal cuenta, el mensaje lo dice (no cae en silencio)."""
    clave, _ = _usuario("w-nq", [("Bancolombia", None, 0)])
    cuerpo = {"Tipo": "Gasto", "monto": 5000, "descripcion": "prueba", "cuenta": "Nequi", "fuente": "cierre_app"}
    r = client.post("/movimientos/rapido", json=cuerpo, headers={"X-Api-Key": clave})
    assert r.status_code == 200, r.text
    m = r.json()["mensaje"]
    assert "no encontré una cuenta" in m and "Nequi" in m and "Bancolombia" in m

    # Con la cuenta creada, ya no hay aviso y cae donde debe.
    client.post("/cuentas", json={"nombre": "Nequi", "saldo": 0})
    cuerpo["monto"] = 6000
    r = client.post("/movimientos/rapido", json=cuerpo, headers={"X-Api-Key": clave})
    assert r.status_code == 200, r.text
    assert r.json()["cuenta_nombre"] == "Nequi"
    assert "no encontré" not in r.json()["mensaje"]
