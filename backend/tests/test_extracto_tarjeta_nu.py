"""Lector del extracto de la TARJETA de crédito de Nu. Todo sintético: el fixture es un extracto inventado con la
misma estructura que el real (tests/fixtures/extracto_tarjeta_nu_sintetico.txt, 16 filas + 1 comisión = 17 líneas).

Pago $A -$B [-$C]: A es el monto del PAGO; B y C son cómo se aplicó; las sub-líneas capital/intereses/cargos suman A."""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'tarjeta_nu.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import conciliacion as c  # noqa: E402
from app import extractos_tarjeta_nu as nu  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import compute_fingerprint  # noqa: E402
from app.contabilidad import MARCA_TRASLADO_PROPIO  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.extractos_gmail import sugerir_cuenta  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil  # noqa: E402
from app.routers import conciliacion as router_conc  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(app)

FIXTURE = (Path(__file__).parent / "fixtures" / "extracto_tarjeta_nu_sintetico.txt").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _limpio():
    yield
    app.dependency_overrides.clear()


def _lineas(texto=FIXTURE):
    return nu.leer_extracto_tarjeta_nu(texto)


# ── 1) Lectura de todas las filas ─────────────────────────────────────────────────────────────
def test_lee_todas_las_filas_del_fixture():
    r = _lineas()
    tipos = [l["tipo_linea"] for l in r["lineas"]]
    assert r["lineas_leidas"] == len(r["lineas"]) == 17
    assert {t: tipos.count(t) for t in set(tipos)} == {
        nu.COMPRA: 9, nu.COMPRA_EN_CUOTAS: 2, nu.CUOTA_MANEJO: 2, nu.PAGO: 2, nu.COMISION: 1, nu.CUOTA_DE_COMPRA_ANTERIOR: 1}
    # la cuota de una compra vieja se lee pero NO es un movimiento nuevo: 17 - 1 = 16 importables
    assert len(r["movimientos"]) == 16


def test_descripcion_unida_sin_importes_ni_anio():
    r = _lineas()
    descs = {l["descripcion"] for l in r["lineas"]}
    assert {"Tienda Alfa Sa", "Kiosco Beta Centro", "Eds Delta El Norte", "Tienda Eta*Mercado", "Ferreteria Kappa",
            "Cobro por cuota de manejo", "Suscripcion Iota*Servicio Web", "Tienda Mu*Pandora"} <= descs
    assert not any("$" in d or "2026" in d for d in descs)


def test_resumen_de_la_pagina_1():
    s = _lineas()["resumen_tarjeta"]
    assert s["periodo"] == {"inicio": "2026-09-14", "fin": "2026-10-14"}
    assert (s["corte"], s["limite_pago"]) == ("2026-10-15", "2026-11-04")
    assert (s["deuda_a_pagar"], s["cupo"], s["usado"], s["disponible"]) == (408000.0, 1000000.0, 65000.0, 935000.0)
    assert (s["pago_minimo"], s["deuda_restante"], s["cuota_manejo"], s["cargos_conversion"]) == (65000.0, 200000.0, 20000.0, 300.0)
    assert (s["abonaste"], s["intereses"]) == (600000.0, 0.0)
    assert s["tarjetas"] == ["1111", "2222"]


def test_compra_en_cuotas_con_restante_y_fecha_completa():
    r = _lineas()
    eta = next(l for l in r["lineas"] if l["descripcion"] == "Tienda Eta*Mercado")
    assert (eta["tipo_linea"], eta["fecha"], eta["monto"], eta["valor_mes"], eta["restante"]) == (
        nu.COMPRA_EN_CUOTAS, "2026-09-30", 150000.0, 75000.0, 75000.0)
    mov = next(m for m in r["movimientos"] if m["descripcion"] == "Tienda Eta*Mercado")
    assert mov["monto"] == 150000.0 and mov["tipo"] == "expense" and mov["restante"] == 75000.0  # la compra completa
    alfa = next(l for l in r["lineas"] if l["descripcion"] == "Tienda Alfa Sa")
    assert alfa["tipo_linea"] == nu.COMPRA and alfa["cuotas"] == {"n": 1, "m": 1}


def test_cuota_de_manejo():
    r = _lineas()
    m = [l for l in r["lineas"] if l["tipo_linea"] == nu.CUOTA_MANEJO]
    assert [(x["fecha"], x["monto"], x["descripcion"]) for x in m] == [
        ("2026-10-14", 10000.0, "Cobro por cuota de manejo"), ("2026-09-15", 10000.0, "Cobro por cuota de manejo")]


def test_cuota_de_compra_anterior_no_se_importa_pero_suma():
    r = _lineas()
    vieja = next(l for l in r["lineas"] if l["descripcion"] == "Tienda Mu*Pandora")
    assert vieja["tipo_linea"] == nu.CUOTA_DE_COMPRA_ANTERIOR and vieja["fecha"] == "2026-06-12"  # JUN en octubre: mismo año
    assert not any("Pandora" in m["descripcion"] for m in r["movimientos"])
    total = next(v for v in r["verificacion"] if v["clave"] == "total_a_pagar")
    assert total["cuadra"] and total["leido"] == 408000.0  # su cuota de $67.500 SÍ cuenta en la suma


def test_comision_por_cambio_de_moneda_es_un_cargo_aparte():
    r = _lineas()
    com = next(l for l in r["lineas"] if l["tipo_linea"] == nu.COMISION)
    assert com["monto"] == 300.0 and com["fecha"] == "2026-09-24" and "Suscripcion Iota*Servicio Web" in com["descripcion"]
    mov = next(m for m in r["movimientos"] if m["linea_tipo"] == nu.COMISION)
    assert mov["tipo"] == "expense" and mov["monto"] == 300.0
    iota = next(m for m in r["movimientos"] if m["descripcion"] == "Suscripcion Iota*Servicio Web")
    assert iota["monto"] == 60000.0  # la compra no incluye la comisión


def test_pago_a_con_sublineas():
    r = _lineas()
    pago = next(m for m in r["movimientos"] if m["linea_tipo"] == nu.PAGO and m["fecha"] == "2026-10-05")
    assert pago["monto"] == 600000.0 and pago["tipo"] == "income" and pago["descripcion"] == "Pago de tu tarjeta"
    assert pago["pago_detalle"] == {"capital": 590000.0, "intereses": 0.0, "cargos": 10000.0, "aplicado": [400000.0, 200000.0]}
    assert pago["pista"] == MARCA_TRASLADO_PROPIO and pago["pago_tarjeta"] is True
    # el 2.º pago no trae C ni A = B + C: sigue siendo un pago de A
    otro = next(m for m in r["movimientos"] if m["linea_tipo"] == nu.PAGO and m["fecha"] == "2026-09-18")
    assert otro["monto"] == 400000.0 and otro["pago_detalle"]["capital"] == 400000.0


def test_el_lector_de_ahorros_no_se_toca():
    assert not nu.es_extracto_tarjeta_nu("Extracto de tu cuenta de ahorros Nu\nPeriodo 01 - 31 OCT 2026\n05 oct Pago Servicio -$80.000,00")
    movs, _ = c.parse_texto_con_regex("Extracto de tu cuenta de ahorros Nu\nPeríodo 01 - 31 OCT 2026\n05 oct Servicio de prueba -$80.000,00\n")
    assert movs and movs[0]["monto"] == 80000.0 and "linea_tipo" not in movs[0]


def test_parse_texto_con_regex_usa_el_lector_de_la_tarjeta():
    movs, descartados = c.parse_texto_con_regex(FIXTURE)
    assert len(movs) == 16 and descartados == 0


# ── Años cruzados ─────────────────────────────────────────────────────────────────────────────
ENERO = """Resumen de tu extracto Nu
Fecha límite de pago Fecha de corte Periodo facturado
04 FEB 2027 15 ENE 2027 14 DIC 2026 - 14 ENE
Deuda a pagar este mes $30.000,00
Tu cupo definido $1.000.000,00
Cuota de manejo + $0,00
Deuda restante + $0,00
Fecha Descripción Valor Cuotas Valor Interés del mes Total a pagar Restante
del mes Porcentaje y valor este mes por pagar
10 ENE Tienda Enero $10.000,00 1 de 1 $10.000,00 2.09% $0,00 $10.000,00 $0,00
2027
28 DIC Tienda Diciembre $20.000,00 1 de 1 $20.000,00 2.09% $0,00 $20.000,00 $0,00
"""


def test_diciembre_en_un_extracto_de_enero_es_del_anio_anterior():
    r = _lineas(ENERO)
    f = {l["descripcion"]: l["fecha"] for l in r["lineas"]}
    assert f == {"Tienda Enero": "2027-01-10", "Tienda Diciembre": "2026-12-28"}
    assert r["resumen_tarjeta"]["periodo"]["inicio"] == "2026-12-14" and r["lectura_completa"]
    # con el año impreso igual al del extracto, la fecha posterior al corte sigue siendo del año anterior
    explicito = ENERO.replace("28 DIC Tienda", "28 DIC 2027 Tienda")
    assert {l["descripcion"]: l["fecha"] for l in _lineas(explicito)["lineas"]}["Tienda Diciembre"] == "2026-12-28"


# ── 2) Verificación de lectura ────────────────────────────────────────────────────────────────
def test_la_verificacion_cuadra_con_el_fixture():
    r = _lineas()
    assert r["lectura_completa"] is True
    claves = {v["clave"] for v in r["verificacion"]}
    assert {"total_a_pagar", "cuota_manejo", "deuda_restante", "pago_2026-10-05", "pago_2026-09-18"} <= claves
    assert all(v["cuadra"] for v in r["verificacion"])
    assert r["mensaje_lectura"] == "Leí 17 líneas y suman lo que dice tu extracto ✓"


def test_una_linea_borrada_no_cuadra_y_dice_cuanto_falta():
    texto = FIXTURE.replace("07 OCT Servicio Gamma $5.000,00 1 de 1 $5.000,00 2.09% $0,00 $5.000,00 $0,00\n2026\n", "")
    assert texto != FIXTURE
    r = _lineas(texto)
    assert r["lectura_completa"] is False and r["lineas_leidas"] == 16
    total = next(v for v in r["verificacion"] if v["clave"] == "total_a_pagar")
    assert total["diferencia"] == -5000.0 and not total["cuadra"]
    assert r["mensaje_lectura"] == "Leí 16 líneas pero faltan $5.000 para sumar lo que dice tu extracto. Revisa antes de importar"
    # el lector de extractos avisa con el contador de descartados
    assert c.parse_texto_con_regex(texto)[1] == 1


def test_una_cuota_de_manejo_borrada_tambien_se_nota():
    texto = FIXTURE.replace("15 SEP 2026 Cobro por cuota $10.000,00 - $10.000,00 - - $10.000,00\nde manejo\n", "")
    r = _lineas(texto)
    assert not r["lectura_completa"]
    assert not next(v for v in r["verificacion"] if v["clave"] == "cuota_manejo")["cuadra"]


def test_un_pago_cuyas_partes_no_suman_a_no_cuadra():
    texto = FIXTURE.replace("↪ A cargos y comisiones $10.000,00", "↪ A cargos y comisiones $9.000,00")
    r = _lineas(texto)
    assert not r["lectura_completa"] and "faltan $1.000" in r["mensaje_lectura"]


# ── 3) Pagos de la tarjeta ────────────────────────────────────────────────────────────────────
def test_casilla_del_pago_solo_se_enciende_con_salida_de_ahorros_igual_a_a():
    db = SessionLocal()
    try:
        tarjeta = Cuenta(usuario_id="tnu-1", nombre="Nu Tarjeta", tipo="credito", saldo=0)
        ahorro = Cuenta(usuario_id="tnu-1", nombre="Nu Colombia", tipo="ahorro", saldo=0)
        db.add_all([tarjeta, ahorro])
        db.flush()
        db.add(Movimiento(usuario_id="tnu-1", cuenta_id=ahorro.id, descripcion="Pago tarjeta", categoria="Otros",
                          tipo="expense", monto=600000.0, fecha=datetime(2026, 10, 4, 10)))
        db.commit()
        pago = next(m for m in _lineas()["movimientos"] if m["linea_tipo"] == nu.PAGO and m["fecha"] == "2026-10-05")
        con = {**pago, "estado": "faltante"}
        router_conc._confirmar_pagos_de_tarjeta(db, "tnu-1", tarjeta, "nu", [con])
        assert con["marcar_por_defecto"] is True and con["aviso_linea"] is None
        sin = {**pago, "estado": "faltante", "monto": 400000.0}  # una salida de otro monto no basta
        router_conc._confirmar_pagos_de_tarjeta(db, "tnu-1", tarjeta, "nu", [sin])
        assert sin["marcar_por_defecto"] is False and sin["aviso_linea"] == "Parece el pago de tu tarjeta. Confirma el monto."
    finally:
        db.close()


def test_sin_cuenta_de_ahorros_el_pago_queda_apagado():
    db = SessionLocal()
    try:
        tarjeta = Cuenta(usuario_id="tnu-2", nombre="Nu Tarjeta", tipo="credito", saldo=0)
        db.add(tarjeta)
        db.commit()
        pago = {**next(m for m in _lineas()["movimientos"] if m["linea_tipo"] == nu.PAGO), "estado": "faltante"}
        router_conc._confirmar_pagos_de_tarjeta(db, "tnu-2", tarjeta, "nu", [pago])
        assert pago["marcar_por_defecto"] is False and "Confirma el monto" in pago["aviso_linea"]
    finally:
        db.close()


def test_la_logica_de_factura_anterior_ya_no_existe():
    assert not hasattr(c, "resumen_factura_anterior")
    pagos = [m for m in _lineas()["movimientos"] if m["linea_tipo"] == nu.PAGO]
    assert not any("resumen_factura" in m for m in pagos)
    assert not any(m["monto"] == 200000.0 for m in _lineas()["movimientos"])  # C no es un gasto


# ── Procesar un extracto (de punta a punta, PDF simulado) ─────────────────────────────────────
def _como(uid):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email=f"{uid}@t.com", nombre="Ana Pérez Gómez")


def test_procesar_devuelve_resumen_verificacion_y_lo_guarda(monkeypatch):
    _como("tnu-proc")
    monkeypatch.setattr(router_conc, "pdf_a_texto", lambda *a, **k: FIXTURE)
    cuenta = client.post("/cuentas", json={"nombre": "Nu Tarjeta", "tipo": "credito", "saldo": 0}).json()["id"]
    r = client.post("/conciliacion/procesar", json={"cuenta_id": cuenta, "pdf_base64": "x"}).json()
    assert r["ok"] and r["lectura_completa"] is True and r["lineas_leidas"] == 17
    assert r["mensaje_lectura"] == "Leí 17 líneas y suman lo que dice tu extracto ✓"
    assert r["resumen_tarjeta"]["deuda_a_pagar"] == 408000.0 and r["total_movimientos"] == 16
    assert not any("Pandora" in i["descripcion"] for i in r["review"])
    pago = next(i for i in r["review"] if i.get("pago_detalle") and i["fecha"] == "2026-10-05")
    assert pago["categoria_sugerida"] == "Pago de tarjeta" and pago["marcar_por_defecto"] is False and pago["monto"] == 600000.0
    # reabrir la revisión conserva el mismo mensaje; la fila del historial también lo trae
    g = client.get(f"/conciliacion/historial/{r['historial_id']}").json()
    assert g["mensaje_lectura"] == r["mensaje_lectura"] and g["resumen_tarjeta"]["cupo"] == 1000000.0
    fila = next(x for x in client.get("/conciliacion/historial").json() if x["id"] == r["historial_id"])
    assert fila["lectura_completa"] is True and fila["mensaje_lectura"].startswith("Leí 17 líneas")


def test_procesar_con_una_linea_menos_avisa_y_no_importa_solo(monkeypatch):
    _como("tnu-proc2")
    texto = FIXTURE.replace("07 OCT Servicio Gamma $5.000,00 1 de 1 $5.000,00 2.09% $0,00 $5.000,00 $0,00\n2026\n", "")
    monkeypatch.setattr(router_conc, "pdf_a_texto", lambda *a, **k: texto)
    cuenta = client.post("/cuentas", json={"nombre": "Nu Tarjeta", "tipo": "credito", "saldo": 0}).json()["id"]
    r = client.post("/conciliacion/procesar", json={"cuenta_id": cuenta, "pdf_base64": "x"}).json()
    assert r["lectura_completa"] is False and r["auto_importados"] == 0
    assert r["mensaje_lectura"] == "Leí 16 líneas pero faltan $5.000 para sumar lo que dice tu extracto. Revisa antes de importar"
    assert r["descartados"] == 1


# ── 4) Relectura ──────────────────────────────────────────────────────────────────────────────
class _Exec:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class _Gmail:
    def users(self): return self
    def messages(self): return self
    def get(self, **kw): return _Exec({"id": kw["id"]})


def test_releer_un_extracto_guardado_con_la_lectura_vieja_lo_corrige_sin_duplicar(monkeypatch):
    uid = "tnu-rel"
    _como(uid)
    monkeypatch.setattr(router_correos, "cliente_gmail", lambda _t: _Gmail())
    monkeypatch.setattr(rx, "listar_adjuntos_pdf", lambda msg: [{"archivo": "nu.pdf", "attachment_id": "a1"}])
    monkeypatch.setattr(rx, "descargar_adjunto", lambda g, m, a: b"%PDF-falso")
    monkeypatch.setattr(rx, "abrir_pdf", lambda pdf, claves: ("ok", FIXTURE, None))
    db = SessionLocal()
    try:
        db.add(Perfil(usuario_id=uid, plan="free", gmail_conectado=True, gmail_refresh_token_enc="t", gmail_email="x@g.com"))
        cuenta = Cuenta(usuario_id=uid, nombre="Nu Tarjeta", tipo="credito", saldo=0)
        db.add(cuenta)
        db.flush()

        def fp(f, m, d, t="expense"):
            return compute_fingerprint(f, m, cuenta.id, d, t)

        # Las 3 líneas que leía el lector viejo (con su descripción vieja): una ya importada, dos sin importar.
        viejo = [
            {"fecha": "2026-10-14", "descripcion": "Cobro por cuota", "monto": 10000.0, "tipo": "expense",
             "fingerprint": fp("2026-10-14", 10000.0, "Cobro por cuota"), "estado": "importado", "movimiento_id": "mov-1"},
            {"fecha": "2026-10-05", "descripcion": "Pago de tu tarjeta (factura anterior)", "monto": 400000.0, "tipo": "income",
             "fingerprint": fp("2026-10-05", 400000.0, "Pago de tu tarjeta (factura anterior)", "income"), "estado": "faltante",
             "pago_tarjeta": True},
            {"fecha": "2026-09-15", "descripcion": "Cobro por cuota", "monto": 10000.0, "tipo": "expense",
             "fingerprint": fp("2026-09-15", 10000.0, "Cobro por cuota"), "estado": "faltante"},
        ]
        h = HistorialExtracto(usuario_id=uid, cuenta_id=cuenta.id, banco_detectado="nu", estado="pendiente_revision",
                              total_movimientos=3, importados=1, faltantes=2, review_json=json.dumps(viejo))
        db.add(h)
        db.flush()
        db.add(ExtractoCorreo(usuario_id=uid, gmail_msg_id="m-rel", archivo="nu.pdf", estado="procesado", historial_id=h.id))
        db.commit()
        hid = h.id
    finally:
        db.close()

    r = client.post(f"/conciliacion/historial/{hid}/releer")
    assert r.status_code == 200, r.text
    assert r.json()["mensaje_lectura"] == "Leí 17 líneas y suman lo que dice tu extracto ✓"
    db = SessionLocal()
    try:
        h = db.get(HistorialExtracto, hid)
        review = json.loads(h.review_json)
        assert h.lectura_completa is True and h.total_movimientos == 16
    finally:
        db.close()
    manejo = [i for i in review if i["descripcion"] in ("Cobro por cuota", "Cobro por cuota de manejo")]
    # lo ya importado con la descripción vieja se sigue reconociendo (no se duplica) y la otra cuota quedó con su nombre nuevo
    assert len(manejo) == 2
    importada = next(i for i in manejo if i["fecha"] == "2026-10-14")
    assert importada["estado"] == "importado" and importada["movimiento_id"] == "mov-1"
    assert next(i for i in manejo if i["fecha"] == "2026-09-15")["estado"] == "faltante"
    assert len(review) == 16 and sum(1 for i in review if i["estado"] == "faltante") == 15
    # la lectura vieja del pago (por B) se reemplazó por el pago de A
    pagos = [i for i in review if i["descripcion"].startswith("Pago de tu tarjeta")]
    assert sorted(i["monto"] for i in pagos) == [400000.0, 600000.0] and all("factura anterior" not in i["descripcion"] for i in pagos)


def test_la_version_del_lector_cambio_para_que_se_relean_los_pendientes():
    assert rx.VERSION_LECTOR == "2026-10-v4-4x1000-costos"


def test_huella_anterior_del_pago_leido_por_b():
    """Si el lector viejo ya importó «Pago de tu tarjeta (factura anterior)» por B (cuando C = A − B), el pago nuevo
    por A se reconoce con esa huella y no se duplica."""
    pago = next(m for m in _lineas()["movimientos"] if m["linea_tipo"] == nu.PAGO and m["fecha"] == "2026-10-05")
    assert pago["huella_anterior"] == {"fecha": "2026-10-05", "monto": 400000.0,
                                       "descripcion": "Pago de tu tarjeta (factura anterior)", "tipo": "income"}
    otro = next(m for m in _lineas()["movimientos"] if m["linea_tipo"] == nu.PAGO and m["fecha"] == "2026-09-18")
    assert "huella_anterior" not in otro  # 400.000 ≠ 27.000 + 0: el lector viejo nunca lo leyó como pago


# ── 5) Producto y cuenta ──────────────────────────────────────────────────────────────────────
def _c(i, nombre, tipo):
    return SimpleNamespace(id=i, nombre=nombre, tipo=tipo, alias_tarjeta="")


AHORRO = _c("a", "Nu Colombia", "ahorro")
TARJETA = _c("t", "Nu Tarjeta", "credito")


@pytest.mark.parametrize("texto", [
    "Llegó el extracto de tu tarjeta de crédito Nu",
    "Tus tarjetas Fecha límite de pago Fecha de corte Periodo facturado",
    FIXTURE[:6000],
])
def test_el_extracto_de_la_tarjeta_va_a_la_cuenta_de_credito(texto):
    assert sugerir_cuenta("Nu Colombia", "", [AHORRO, TARJETA], texto) == "t"


@pytest.mark.parametrize("texto", [
    "Llegó el extracto de tu tarjeta de crédito Nu",
    "Tus tarjetas Fecha límite de pago Fecha de corte Periodo facturado",
    FIXTURE[:6000],
])
def test_si_solo_tiene_la_de_ahorros_queda_sin_asignar(texto):
    """No se asigna a la cuenta de ahorros: la pantalla avisa «crea tu cuenta de tarjeta para conciliarlo»."""
    assert sugerir_cuenta("Nu Colombia", "", [AHORRO], texto) is None
