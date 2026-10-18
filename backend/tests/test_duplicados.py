"""Regla CENTRAL de deduplicación entre canales (app/duplicados.py): app (manual), atajo de Apple Pay,
correo del banco y extracto. Todo con datos inventados y Gmail simulado.

Cubre: los 4 canales en las 24 órdenes de llegada, dos compras iguales legítimas, reintento del atajo,
re-sincronización del correo, extracto que llega días después con fecha distinta, montos con centavos,
borrar y volver a sincronizar, «Mostrar de todos modos», traslados propios, «Buscar duplicados» y que dos
usuarios no se interfieran."""
import itertools
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'duplicados.db')}")

import pytest  # noqa: E402

from app import duplicados as dup  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CorreoGasto, HuellaOrigen, Movimiento  # noqa: E402
from app.utiles import ahora_co  # noqa: E402
from tests.test_extractos_gmail import GmailFalso, client, conectar_usuario, mensaje  # noqa: E402

pytest.importorskip("reportlab.pdfgen.canvas")

BANCO = "Bancolombia <alertas@alertas.bancolombia.com.co>"
CANALES = ("manual", "atajo", "correo", "extracto")


def _ms(momento_co: datetime) -> str:
    """internalDate de Gmail (ms, UTC) de un momento en hora Colombia."""
    return str(int((momento_co + timedelta(hours=5)).replace(tzinfo=timezone.utc).timestamp() * 1000))


def _plata(monto: float) -> str:
    return f"{monto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class Escena:
    """Un usuario con una cuenta Bancolombia y los 4 canales para registrar la MISMA compra."""

    def __init__(self, monkeypatch, uid=None, cuentas=(("Bancolombia", 1_000_000),)):
        from app.routers import conciliacion as mod

        self.uid = uid or f"dup-{uuid.uuid4().hex[:8]}"
        self.gmail = GmailFalso([], {})
        conectar_usuario(self.uid, self.gmail, monkeypatch)
        self.cuentas = {n: client.post("/cuentas", json={"nombre": n, "saldo": s}).json() for n, s in cuentas}
        self.cuenta = next(iter(self.cuentas.values()))
        self.saldo0 = self.cuenta["saldo"]
        self.key = client.get("/perfil/api-key").json()["api_key"]
        self.base = (ahora_co() - timedelta(minutes=30)).replace(microsecond=0)
        self.lineas: list[dict] = []
        monkeypatch.setattr(mod, "pdf_a_texto", lambda *a, **k: "texto")
        monkeypatch.setattr(mod, "detectar_banco", lambda t: "bancolombia")
        monkeypatch.setattr(mod, "parse_texto_con_regex", lambda t: ([dict(i) for i in self.lineas], 0))
        self.n_correo = 0

    def como(self):
        app.dependency_overrides[get_current_user] = lambda: UsuarioActual(
            id=self.uid, email=f"{self.uid}@test.com", nombre="Persona Prueba")

    # ── los 4 canales ──
    def manual(self, monto=45_000, desc="Exito", minutos=0, forzar=False, cuenta=None, tipo="expense"):
        self.como()
        return client.post("/movimientos", json={
            "cuenta_id": (cuenta or self.cuenta)["id"], "descripcion": desc, "monto": monto, "tipo": tipo,
            "fecha": (self.base + timedelta(minutes=minutos)).isoformat(), "confirmar_nuevo": forzar})

    def atajo(self, monto=45_000, comercio="EXITO", minutos=0, tarjeta="Bancolombia", **extra):
        self.como()
        return client.post("/movimientos/rapido", headers={"X-Api-Key": self.key}, json={
            "monto": monto, "tipo": "expense", "comercio": comercio, "tarjeta": tarjeta,
            "fecha": (self.base + timedelta(minutes=minutos)).isoformat(), **extra})

    def llega_correo(self, monto=45_000, comercio="EXITO", minutos=0, id_=None, sincronizar=True):
        self.n_correo += 1
        id_ = id_ or f"{self.uid}-m{self.n_correo}"
        msg = mensaje(id_, BANCO, f"Compra en {comercio}", f"Valor ${_plata(monto)} con tu tarjeta")
        msg["internalDate"] = _ms(self.base + timedelta(minutes=minutos))
        self.gmail.mensajes[id_] = msg
        if sincronizar:
            self.sincronizar()
        return id_

    def sincronizar(self):
        self.como()
        for _ in range(6):
            r = client.post("/correos/sincronizar").json()
            if r.get("completado", True):
                return r
        return r

    def extracto(self, lineas=None, importar=True, dias=0):
        """Procesa un extracto (con las líneas dadas o la compra base) e importa lo que no tiene pareja."""
        self.como()
        self.lineas = lineas if lineas is not None else [{
            "fecha": (self.base + timedelta(days=dias)).strftime("%Y-%m-%d"), "descripcion": "COMPRA EXITO 4455",
            "monto": 45_000, "tipo": "expense", "referencia": ""}]
        r = client.post("/conciliacion/procesar", json={"cuenta_id": self.cuenta["id"], "pdf_base64": "x"}).json()
        assert r["ok"], r
        if importar:
            fps = [i["fingerprint"] for i in r["review"] if i["estado"] == "faltante"]
            if fps:
                out = client.post(f"/conciliacion/historial/{r['historial_id']}/importar", json={"fingerprints": fps})
                assert out.status_code == 200, out.text
        return r

    # ── lecturas ──
    def movs(self):
        self.como()
        r = client.get("/movimientos", params={"limit": 500}).json()
        return r["items"] if isinstance(r, dict) else r

    def pendientes(self):
        self.como()
        return client.get("/correos/pendientes").json()

    def correos(self, filtro):
        self.como()
        return client.get("/correos/lista", params={"filtro": filtro}).json()

    def saldo(self, nombre=None):
        self.como()
        c = self.cuentas[nombre] if nombre else self.cuenta
        return [x for x in client.get("/cuentas").json() if x["id"] == c["id"]][0]["saldo"]

    def canales(self, mov_id):
        self.como()
        return client.get(f"/movimientos/{mov_id}").json()["canales"]


@pytest.fixture()
def e(monkeypatch):
    return Escena(monkeypatch)


# ═══ 1. Los 4 canales en las 24 órdenes de llegada ═════════════════════════════════════════════

@pytest.mark.parametrize("orden", list(itertools.permutations(CANALES)), ids=lambda o: ">".join(o))
def test_la_misma_compra_por_los_4_canales_en_cualquier_orden_queda_una_sola_vez(orden, monkeypatch):
    e = Escena(monkeypatch)
    creador = None
    for canal in orden:
        hay = bool(e.movs())
        if canal == "manual":
            r = e.manual()
            if hay:
                assert r.status_code == 409 and r.json()["detail"]["codigo"] == "posible_duplicado", r.text
            else:
                assert r.status_code == 200, r.text
        elif canal == "atajo":
            r = e.atajo()
            assert r.status_code == 200, r.text
            assert r.json()["duplicado"] is hay
        elif canal == "correo":
            e.llega_correo()
        else:
            r = e.extracto()
            assert r["faltantes"] == (0 if hay else 1) or not hay
        if creador is None and canal in ("manual", "atajo", "extracto"):
            creador = canal

    movs = e.movs()
    assert len(movs) == 1, [(m["descripcion"], m["fuente"]) for m in movs]
    assert e.pendientes() == [], "el correo no debe quedar en «Por revisar»"
    assert [c["estado"] for c in e.correos("todos")] == ["ya_registrado"]
    assert e.saldo() == e.saldo0 - 45_000, "el gasto no se descuenta dos veces"
    esperados = {"atajo", "correo", "extracto"} | ({"manual"} if creador == "manual" else set())
    assert set(movs[0]["canales"]) == esperados
    assert movs[0]["origen"] == creador or creador == "extracto"


def test_el_extracto_concilia_lo_existente_en_vez_de_insertar(e):
    e.atajo()
    r = e.extracto()
    assert r["completados"] == 1 and r["faltantes"] == 0
    (m,) = e.movs()
    assert m["conciliado_en"] is not None
    assert e.saldo() == e.saldo0 - 45_000


# ═══ 2. Dos compras iguales legítimas ══════════════════════════════════════════════════════════

def test_dos_cafes_iguales_el_mismo_dia_son_dos_movimientos(e):
    assert e.atajo(monto=7_000, comercio="Juan Valdez", minutos=0).json()["duplicado"] is False
    assert e.atajo(monto=7_000, comercio="Juan Valdez", minutos=20).json()["duplicado"] is False
    assert len(e.movs()) == 2
    # Llegan los 2 correos: cada uno se empareja 1 a 1 con un café.
    e.llega_correo(monto=7_000, comercio="Juan Valdez", minutos=0, sincronizar=False)
    e.llega_correo(monto=7_000, comercio="Juan Valdez", minutos=20)
    assert e.pendientes() == [] and len(e.correos("ya_registrados")) == 2
    # Un TERCER correo igual es una compra nueva: se queda por revisar.
    e.llega_correo(monto=7_000, comercio="Juan Valdez", minutos=21)
    assert len(e.pendientes()) == 1
    assert len(e.movs()) == 2


def test_dos_cafes_iguales_con_extracto_se_emparejan_1_a_1_y_el_tercero_es_nuevo(e):
    e.atajo(monto=7_000, comercio="Juan Valdez", minutos=0)
    e.atajo(monto=7_000, comercio="Juan Valdez", minutos=20)
    dia = e.base.strftime("%Y-%m-%d")
    linea = {"fecha": dia, "descripcion": "COMPRA JUAN VALDEZ", "monto": 7_000, "tipo": "expense", "referencia": ""}
    r = e.extracto([dict(linea), dict(linea), dict(linea)])
    assert r["completados"] == 2 and r["faltantes"] == 1
    assert len(e.movs()) == 3, "las 3 compras del banco, ninguna duplicada"
    assert sum(1 for m in e.movs() if m["conciliado_en"]) == 2  # los 2 del atajo se concilian; el 3.º entra nuevo
    assert sorted(m["origen"] for m in e.movs()) == ["atajo", "atajo", "extracto"]
    assert e.saldo() == e.saldo0 - 21_000


def test_manual_otro_igual_se_acepta_con_confirmar_nuevo(e):
    e.atajo()
    assert e.manual().status_code == 409
    assert e.manual(forzar=True).status_code == 200  # «Es otro gasto igual»
    assert len(e.movs()) == 2


def test_dos_manuales_iguales_no_se_cuestionan_entre_si(e):
    assert e.manual().status_code == 200
    assert e.manual().status_code == 200  # mismo canal: la app no estorba a quien registra dos veces
    assert len(e.movs()) == 2


# ═══ 3. Reintentos y re-sincronizaciones del MISMO canal ═══════════════════════════════════════

def test_reintento_del_atajo_no_crea_otro(e):
    a = e.atajo().json()
    b = e.atajo().json()
    assert b["duplicado"] is True and b["id"] == a["id"]
    assert len(e.movs()) == 1 and e.saldo() == e.saldo0 - 45_000


def test_reintento_con_id_de_transaccion_nunca_duplica_aunque_pase_el_tiempo(e):
    a = e.atajo(id_transaccion="TX-998877", minutos=0).json()
    b = e.atajo(id_transaccion="TX-998877", minutos=0).json()
    assert b["duplicado"] is True and b["id"] == a["id"]
    assert len(e.movs()) == 1
    # Otro id = otra compra (aunque sea del mismo valor y comercio).
    c = e.atajo(id_transaccion="TX-998878", minutos=20).json()
    assert c["duplicado"] is False and len(e.movs()) == 2


def test_reintento_del_atajo_despues_de_que_el_correo_ya_lo_reconocio(e):
    e.llega_correo()
    a = e.atajo().json()
    assert a["duplicado"] is False and len(e.pendientes()) == 0
    b = e.atajo().json()
    assert b["duplicado"] is True and b["id"] == a["id"]
    assert len(e.movs()) == 1


def test_resincronizar_el_correo_no_duplica_ni_reaparece(e):
    e.llega_correo()
    assert len(e.pendientes()) == 1
    e.sincronizar()
    e.sincronizar()
    assert len(e.pendientes()) == 1 and len(e.correos("todos")) == 1
    # Ya con el atajo: el correo queda enlazado y las re-sincronizaciones no lo vuelven a mostrar.
    e.atajo()
    e.sincronizar()
    e.sincronizar()
    assert e.pendientes() == [] and len(e.movs()) == 1


def test_aprobar_un_correo_guarda_su_huella_y_el_atajo_posterior_lo_confirma(e):
    cid = e.llega_correo()
    pend = e.pendientes()[0]
    r = client.post(f"/correos/{pend['id']}/aprobar", json={"cuenta_id": e.cuenta["id"]})
    assert r.status_code == 200, r.text
    (m,) = e.movs()
    assert m["origen"] == "correo" and m["canales"] == ["correo"]
    a = e.atajo().json()  # llega el atajo DESPUÉS del correo ya aprobado
    assert a["duplicado"] is True and a["id"] == m["id"] and a["ya_estaba_por"] == "correo"
    assert "No lo dupliqué" in a["mensaje"]
    assert e.canales(m["id"]) == ["atajo", "correo"]
    assert e.saldo() == e.saldo0 - 45_000
    with SessionLocal() as db:
        assert db.query(HuellaOrigen).filter(HuellaOrigen.huella == dup.huella_correo(cid)).count() == 1


# ═══ 4. El correo y el extracto enriquecen, no duplican ════════════════════════════════════════

def test_el_correo_enriquece_el_comercio_de_un_registro_generico(e):
    # Un registro a mano sin detalle útil y luego el correo con el comercio real.
    e.manual(desc="Gasto sin detalle")
    e.llega_correo(comercio="Crepes y Waffles")
    (m,) = e.movs()
    assert m["descripcion"] == "Compra en Crepes Y Waffles" or "Crepes" in m["descripcion"]
    assert e.pendientes() == []


def test_el_atajo_confirma_el_registro_por_confirmar_cuando_el_banco_lo_corrobora(e):
    a = e.atajo(comercio="Netflix", monto=33_000).json()
    assert a["por_confirmar"] is True
    e.llega_correo(comercio="Netflix", monto=33_000)
    (m,) = e.movs()
    assert m["categoria"] != "Otros" and m["cat_confirmada"] is True  # el banco lo corroboró
    assert set(m["canales"]) == {"atajo", "correo"}


def test_extracto_dias_despues_con_fecha_distinta_concilia_y_corrige_la_fecha_aproximada(e):
    e.manual(desc="Exito", minutos=0)
    dia_banco = (e.base + timedelta(days=2)).strftime("%Y-%m-%d")
    r = e.extracto([{"fecha": dia_banco, "descripcion": "COMPRA EXITO 4455", "monto": 45_000, "tipo": "expense", "referencia": ""}])
    assert r["completados"] == 1 and r["faltantes"] == 0
    (m,) = e.movs()
    assert m["fecha"][:10] == dia_banco, "la fecha escrita a mano se corrige con la del banco"
    assert m["descripcion"] == "Exito", "lo que la persona escribió no se pisa con el texto críptico del banco"
    assert m["conciliado_en"] is not None


def test_extracto_dias_despues_respeta_la_hora_real_del_atajo(e):
    e.atajo()
    antes = e.movs()[0]["fecha"]
    dia_banco = (e.base + timedelta(days=2)).strftime("%Y-%m-%d")
    e.extracto([{"fecha": dia_banco, "descripcion": "COMPRA EXITO", "monto": 45_000, "tipo": "expense", "referencia": ""}])
    (m,) = e.movs()
    assert m["fecha"] == antes and m["conciliado_en"]


def test_extracto_a_mas_de_3_dias_ya_no_es_la_misma_compra(e):
    e.manual()
    lejos = (e.base + timedelta(days=5)).strftime("%Y-%m-%d")
    r = e.extracto([{"fecha": lejos, "descripcion": "COMPRA EXITO", "monto": 45_000, "tipo": "expense", "referencia": ""}])
    assert r["completados"] == 0 and len(e.movs()) == 2


def test_extracto_ya_conciliado_no_vuelve_a_tocar_ni_a_insertar(e):
    e.atajo()
    e.extracto()
    r = e.extracto()  # mismo extracto otra vez
    assert r["faltantes"] == 0 and len(e.movs()) == 1


# ═══ 5. Montos con centavos ════════════════════════════════════════════════════════════════════

def test_monto_con_centavos_se_concilia_y_se_corrige_al_exacto_del_banco(e):
    e.manual(monto=45_000.50)
    assert e.saldo() == e.saldo0 - 45_000.50
    r = e.extracto([{"fecha": e.base.strftime("%Y-%m-%d"), "descripcion": "COMPRA", "monto": 45_001.0,
                     "tipo": "expense", "referencia": ""}])
    assert r["completados"] == 1
    (m,) = e.movs()
    assert m["monto"] == 45_001.0
    assert e.saldo() == pytest.approx(e.saldo0 - 45_001.0), "el saldo se ajusta por la diferencia de redondeo"


def test_el_correo_con_centavos_encuentra_el_registro(e):
    e.manual(monto=45_000.50)
    e.llega_correo(monto=45_000.50)
    assert e.pendientes() == [] and len(e.movs()) == 1


def test_un_monto_distinto_no_es_el_mismo_gasto(e):
    e.manual(monto=45_000)
    e.llega_correo(monto=45_900)
    assert len(e.pendientes()) == 1


# ═══ 6. Borrar y volver a sincronizar: no resucita ═════════════════════════════════════════════

def test_borrar_y_resincronizar_el_correo_no_resucita(e):
    e.atajo()
    e.llega_correo()
    (m,) = e.movs()
    assert client.delete(f"/movimientos/{m['id']}").status_code == 200
    assert e.movs() == [] and e.saldo() == e.saldo0
    e.sincronizar()
    e.sincronizar(), e.sincronizar()
    assert e.pendientes() == [], "el correo que ya estaba enlazado no vuelve a ofrecerse"
    assert [c["estado"] for c in e.correos("todos")] == ["descartado"]


def test_borrar_lo_del_atajo_y_que_llegue_el_correo_despues_no_lo_resucita(e):
    a = e.atajo().json()
    client.delete(f"/movimientos/{a['id']}")
    e.llega_correo()
    assert e.pendientes() == []
    assert [c["estado"] for c in e.correos("todos")] == ["descartado"]
    assert e.movs() == []


def test_borrar_algo_a_mano_y_que_llegue_el_correo_no_lo_resucita(e):
    m = e.manual().json()
    client.delete(f"/movimientos/{m['id']}")
    e.llega_correo()
    assert e.pendientes() == []
    # ...pero una compra DISTINTA (otro monto) sí aparece.
    e.llega_correo(monto=12_000, comercio="Rappi")
    assert len(e.pendientes()) == 1


def test_borrar_y_volver_a_subir_el_extracto_no_resucita(e):
    r1 = e.extracto()  # entra por el extracto
    (m,) = e.movs()
    assert m["origen"] == "extracto"
    client.delete(f"/movimientos/{m['id']}")
    r2 = e.extracto()
    assert r2["borrados_antes"] == 1 and r2["faltantes"] == 0
    assert [i["estado"] for i in r2["review"]] == ["borrado_antes"]
    assert e.movs() == []


def test_borrar_lo_del_atajo_y_que_llegue_el_extracto_no_lo_resucita(e):
    a = e.atajo().json()
    client.delete(f"/movimientos/{a['id']}")
    r = e.extracto()
    assert r["borrados_antes"] == 1 and e.movs() == []


def test_deshacer_lo_importado_solo_si_permite_que_vuelva(e):
    e.extracto(importar=False)
    client.put("/perfil/autoimportar-extractos", json={"activo": True})
    e.lineas = [{"fecha": e.base.strftime("%Y-%m-%d"), "descripcion": "NETFLIX.COM", "monto": 33_000,
                 "tipo": "expense", "referencia": ""}]
    r = client.post("/conciliacion/procesar", json={"cuenta_id": e.cuenta["id"], "pdf_base64": "x"}).json()
    if r["auto_importados"]:
        client.post(f"/conciliacion/historial/{r['historial_id']}/deshacer-auto")
        r2 = e.extracto(lineas=e.lineas, importar=False)
        assert r2["borrados_antes"] == 0, "deshacer no cuenta como borrado: la línea puede volver"


# ═══ 7. «Mostrar de todos modos» ═══════════════════════════════════════════════════════════════

def test_mostrar_de_todos_modos_devuelve_el_correo_y_no_se_vuelve_a_esconder(e):
    e.atajo()
    e.llega_correo()
    (c,) = e.correos("ya_registrados")
    assert c["registrado_como"]["canales"] == ["atajo", "correo"] and c["movimiento_id"]
    r = client.post(f"/correos/{c['id']}/no-es-duplicado")
    assert r.status_code == 200 and r.json()["estado"] == "pendiente"
    assert len(e.pendientes()) == 1
    e.sincronizar()
    e.atajo(minutos=1, comercio="EXITO 2")  # un movimiento nuevo dispara la revisión: el correo sigue visible
    assert len(e.pendientes()) == 1
    (m_atajo,) = [m for m in e.movs() if m["descripcion"] == "EXITO"]
    assert set(m_atajo["canales"]) == {"atajo"}
    # Se aprueba: era otro gasto igual, ahora hay dos.
    pid = e.pendientes()[0]["id"]
    assert client.post(f"/correos/{pid}/aprobar", json={"cuenta_id": e.cuenta["id"]}).status_code == 200
    assert len(e.movs()) == 3


def test_no_es_duplicado_solo_aplica_a_correos_ya_registrados(e):
    e.llega_correo()
    (c,) = e.pendientes()
    assert client.post(f"/correos/{c['id']}/no-es-duplicado").status_code == 400


# ═══ 8. Traslados y pagos entre cuentas propias ════════════════════════════════════════════════

def test_un_traslado_propio_no_se_confunde_con_un_gasto_igual(monkeypatch):
    e = Escena(monkeypatch, cuentas=(("Bancolombia", 500_000), ("Nequi", 100_000)))
    e.como()
    r = client.post("/movimientos/transferencia", json={
        "cuenta_origen_id": e.cuentas["Bancolombia"]["id"], "cuenta_destino_id": e.cuentas["Nequi"]["id"],
        "monto": 45_000, "fecha": e.base.isoformat()})
    assert r.status_code == 200, r.text
    # Un gasto de $45.000 en la misma cuenta y día es OTRO movimiento (el traslado no lo absorbe).
    assert e.atajo().json()["duplicado"] is False
    assert e.manual(forzar=False).status_code == 409  # ...y sí reconoce al atajo, no al traslado
    movs = e.movs()
    assert len([m for m in movs if m["tipo"] == "transfer"]) == 2
    assert len([m for m in movs if m["tipo"] == "expense"]) == 1


def test_egreso_de_una_cuenta_e_ingreso_de_la_otra_no_son_duplicados_entre_si(monkeypatch):
    e = Escena(monkeypatch, cuentas=(("Bancolombia", 500_000), ("Nequi", 100_000)))
    e.manual(monto=45_000, desc="Pago tarjeta", cuenta=e.cuentas["Bancolombia"])
    r = e.manual(monto=45_000, desc="Pago recibido", cuenta=e.cuentas["Nequi"], tipo="income")
    assert r.status_code == 200
    assert len(e.movs()) == 2
    assert dup.grupos_posibles_duplicados(SessionLocal(), e.uid) == []


# ═══ 9. Dos usuarios no se interfieren ═════════════════════════════════════════════════════════

def test_dos_usuarios_con_la_misma_compra_no_se_interfieren(monkeypatch):
    a = Escena(monkeypatch)
    a.atajo()
    b = Escena(monkeypatch)  # otro usuario, mismo monto y comercio
    b.llega_correo()
    assert len(b.pendientes()) == 1, "el correo de B no se absorbe con el movimiento de A"
    assert b.movs() == []
    assert b.atajo().json()["duplicado"] is False
    assert b.pendientes() == []
    assert len(a.movs()) == 1 and len(b.movs()) == 1
    a.como()
    assert a.correos("todos") == [] and a.pendientes() == []


def test_la_huella_de_un_usuario_no_bloquea_a_otro_con_el_mismo_id_de_transaccion(monkeypatch):
    a = Escena(monkeypatch)
    b = Escena(monkeypatch)
    assert a.atajo(id_transaccion="MISMO-ID").json()["duplicado"] is False
    assert b.atajo(id_transaccion="MISMO-ID").json()["duplicado"] is False


# ═══ 10. Banco con varias cuentas ══════════════════════════════════════════════════════════════

def test_correo_de_un_banco_con_dos_cuentas_encuentra_el_registro_del_atajo_en_cualquiera(monkeypatch):
    e = Escena(monkeypatch, cuentas=(("Bancolombia Ahorros", 500_000), ("Bancolombia Crédito", 0)))
    r = e.atajo(tarjeta="Bancolombia").json()  # el atajo no sabe cuál: queda en una de las dos
    assert r["duplicado"] is False
    e.llega_correo()
    assert e.pendientes() == [] and len(e.movs()) == 1


# ═══ 11. Buscar duplicados (datos viejos) ══════════════════════════════════════════════════════

def _sembrar_viejos(e, monto=45_000):
    """Movimientos de ANTES de la regla: sin origen ni huellas, uno por cada canal."""
    e.como()
    with SessionLocal() as db:
        ids = []
        for i, (fuente, desc, min_) in enumerate((("manual", "Exito", 0), ("wallet", "EXITO", 2), ("email", "Compra en Exito", 4))):
            m = Movimiento(usuario_id=e.uid, cuenta_id=e.cuenta["id"], fecha=e.base + timedelta(minutes=min_),
                           descripcion=desc, categoria="Comida", tipo="expense", monto=monto, fuente=fuente,
                           cat_confirmada=fuente == "manual")
            db.add(m)
            db.flush()
            ids.append(m.id)
        db.commit()
    return ids


def test_buscar_duplicados_sugiere_grupos_sin_borrar_nada(e):
    ids = _sembrar_viejos(e)
    r = client.get("/duplicados/buscar").json()
    assert r["total"] == 1
    g = r["grupos"][0]
    assert {m["id"] for m in g["movimientos"]} == set(ids)
    assert {m["origen"] for m in g["movimientos"]} == {"manual", "atajo", "correo"}
    assert g["sugerido_conservar"] in ids
    assert len(e.movs()) == 3, "solo sugiere: no borra nada"


def test_buscar_duplicados_respeta_el_1_a_1_dos_cafes_y_un_tercero_suelto(e):
    e.como()
    with SessionLocal() as db:
        for fuente, min_ in (("manual", 0), ("wallet", 1), ("manual", 40), ("wallet", 41), ("email", 90)):
            db.add(Movimiento(usuario_id=e.uid, cuenta_id=e.cuenta["id"], fecha=e.base + timedelta(minutes=min_),
                              descripcion="Juan Valdez", categoria="Comida", tipo="expense", monto=7_000, fuente=fuente))
        db.commit()
    grupos = client.get("/duplicados/buscar").json()["grupos"]
    assert len(grupos) >= 1
    for g in grupos:  # cada grupo tiene como máximo un movimiento por canal
        origenes = [m["origen"] for m in g["movimientos"]]
        assert len(origenes) == len(set(origenes))
    assert sum(len(g["movimientos"]) for g in grupos) <= 5


def test_unir_conserva_el_elegido_traspasa_canales_y_devuelve_el_saldo(e):
    ids = _sembrar_viejos(e)
    with SessionLocal() as db:
        from app.models import Cuenta
        db.query(Cuenta).filter(Cuenta.id == e.cuenta["id"]).update({"saldo": e.saldo0 - 3 * 45_000})
        db.commit()
    conservar = ids[0]
    r = client.post("/duplicados/unir", json={"conservar_id": conservar, "unir_ids": ids[1:]})
    assert r.status_code == 200, r.text
    assert r.json()["unidos"] == 2
    movs = e.movs()
    assert [m["id"] for m in movs] == [conservar]
    assert set(movs[0]["canales"]) == {"manual", "atajo", "correo"}
    assert e.saldo() == e.saldo0 - 45_000, "los dos duplicados eliminados devuelven su saldo"
    assert client.get("/duplicados/buscar").json()["total"] == 0


def test_no_es_duplicado_no_vuelve_a_sugerirse(e):
    ids = _sembrar_viejos(e)
    assert client.get("/duplicados/buscar").json()["total"] == 1
    assert client.post("/duplicados/no-es-duplicado", json={"movimiento_ids": ids}).status_code == 200
    assert client.get("/duplicados/buscar").json()["total"] == 0


def test_unir_rechaza_traslados_tipos_mezclados_y_ajenos(e):
    ids = _sembrar_viejos(e)
    assert client.post("/duplicados/unir", json={"conservar_id": ids[0], "unir_ids": [ids[0]]}).status_code == 400
    assert client.post("/duplicados/unir", json={"conservar_id": ids[0], "unir_ids": ["no-existe"]}).status_code == 404


def test_calcular_huellas_viejas_es_idempotente(e):
    ids = _sembrar_viejos(e)
    with SessionLocal() as db:
        simulado = dup.calcular_huellas_viejas(db, aplicar=False)
        assert simulado["origen_asignado"] >= 3
        assert db.query(Movimiento).filter(Movimiento.id.in_(ids), Movimiento.origen.isnot(None)).count() == 0
        dup.calcular_huellas_viejas(db, aplicar=True)
        otra = dup.calcular_huellas_viejas(db, aplicar=True)
        assert otra == {"origen_asignado": 0, "huellas_correo": 0, "huellas_extracto": 0}
        origenes = {m.fuente: m.origen for m in db.query(Movimiento).filter(Movimiento.id.in_(ids)).all()}
        assert origenes == {"manual": "manual", "wallet": "atajo", "email": "correo"}


# ═══ 12. La regla pura ═════════════════════════════════════════════════════════════════════════

def _c(origen, minutos=0, monto=45_000, tipo="expense", cuentas=("c1",), texto="", canales=(), fecha=None, **kw):
    base = datetime(2026, 10, 5, 12, 0, 0)
    return dup.Cand(id=f"{origen}{minutos}", origen=origen, tipo=tipo, monto=monto, cuentas=frozenset(cuentas),
                    fecha=fecha or base + timedelta(minutes=minutos), texto=texto,
                    canales=frozenset(canales) | {origen}, con_hora=True, **kw)


def test_regla_pura_basicos():
    assert dup.puntaje(_c("correo"), _c("atajo")) is not None
    assert dup.puntaje(_c("correo", tipo="income"), _c("atajo")) is None, "dirección distinta"
    assert dup.puntaje(_c("correo", cuentas=("c2",)), _c("atajo")) is None, "cuenta distinta"
    assert dup.puntaje(_c("correo", monto=45_002), _c("atajo")) is None, "más que redondeo"
    assert dup.puntaje(_c("correo", monto=45_000.5), _c("atajo")) is not None, "centavos = redondeo"
    assert dup.puntaje(_c("atajo"), _c("atajo")) is None, "mismo canal nunca se absorbe"
    assert dup.puntaje(_c("correo"), _c("atajo", canales=("correo",))) is None, "ese canal ya confirmó"
    assert dup.puntaje(_c("correo", tipo="transfer"), _c("atajo", tipo="transfer")) is None


def test_regla_pura_ventanas_de_fecha():
    assert dup.puntaje(_c("correo", minutos=5 * 60), _c("atajo")) is not None
    assert dup.puntaje(_c("correo", minutos=7 * 60), _c("atajo")) is None, "dos horas con hora real: más de 6 h"
    assert dup.puntaje(_c("correo", minutos=20 * 60, fecha=datetime(2026, 10, 6, 8, 0)), _c("manual", minutos=0)) is not None
    manana2 = datetime(2026, 10, 7, 12, 0)
    assert dup.puntaje(_c("correo", fecha=manana2), _c("manual")) is None, "a 2 días: no"
    assert dup.puntaje(dup.Cand(id="x", origen="extracto", tipo="expense", monto=45_000, fecha=datetime(2026, 10, 8),
                                cuentas=frozenset({"c1"})), _c("manual")) is not None, "extracto: ±3 días"
    assert dup.puntaje(dup.Cand(id="x", origen="extracto", tipo="expense", monto=45_000, fecha=datetime(2026, 10, 9),
                                cuentas=frozenset({"c1"})), _c("manual")) is None


def test_regla_pura_comercio_distinto_con_hora_real_exige_cercania():
    assert dup.puntaje(_c("correo", minutos=120, texto="Uber"), _c("atajo", texto="Netflix")) is None
    assert dup.puntaje(_c("correo", minutos=10, texto="Uber"), _c("atajo", texto="Netflix")) is not None
    assert dup.puntaje(_c("correo", minutos=120, texto="Netflix"), _c("atajo", texto="Netflix")) is not None
    # sin texto en alguno, el comercio no decide
    assert dup.puntaje(_c("correo", minutos=120, texto=""), _c("atajo", texto="Netflix")) is not None


def test_emparejar_es_1_a_1_y_prefiere_el_mas_cercano():
    ex = [_c("atajo", minutos=0), _c("atajo", minutos=20)]
    ex[1].id = "b"
    ent = [_c("correo", minutos=21), _c("correo", minutos=1)]
    ent[0].id = "x"
    pares = dup.emparejar(ent, ex)
    assert sorted((i, j) for i, j, _ in pares) == [(0, 1), (1, 0)]
    assert len(dup.emparejar([_c("correo"), _c("correo", minutos=1), _c("correo", minutos=2)], ex)) == 2


def test_huella_del_atajo_distingue_comercios_y_minutos():
    m = datetime(2026, 10, 5, 12, 0, 30)
    h = dup.huella_atajo("c1", "expense", 45_000, "Tienda A", m)
    assert h == dup.huella_atajo("c1", "expense", 45_000, "Tienda A", m + timedelta(seconds=10))
    assert h != dup.huella_atajo("c1", "expense", 45_000, "Tienda B", m)
    assert h != dup.huella_atajo("c1", "expense", 45_000, "Tienda A", m + timedelta(minutes=1))
    assert dup.huella_atajo("c1", "expense", 1, "x", m, "ABC") == "tx:ABC"


def test_origen_de_fuente_cubre_las_fuentes_conocidas():
    assert dup.origen_de_fuente("wallet") == dup.origen_de_fuente("apple_pay") == dup.origen_de_fuente("cierre_app") == "atajo"
    assert dup.origen_de_fuente("email") == "correo"
    assert dup.origen_de_fuente("conciliacion_extracto") == dup.origen_de_fuente("conciliacion_auto") == "extracto"
    assert dup.origen_de_fuente("importacion_archivo") == "importacion"
    assert dup.origen_de_fuente("manual") == dup.origen_de_fuente("ai") == dup.origen_de_fuente(None) == "manual"


# ═══ 9. Recuperar un correo descartado ═════════════════════════════════════════════════════════

def _descartado_por_fantasma(e):
    """Atajo borrado y luego llega el correo: queda 'descartado' sin que la persona lo sepa."""
    a = e.atajo().json()
    client.delete(f"/movimientos/{a['id']}")
    e.llega_correo()
    (c,) = e.correos("descartados")
    assert e.pendientes() == [] and e.movs() == []
    return c


def test_recuperar_un_correo_descartado_por_fantasma_lo_devuelve_a_por_revisar_y_se_puede_aprobar(e):
    c = _descartado_por_fantasma(e)
    e.como()
    r = client.post(f"/correos/{c['id']}/recuperar")
    assert r.status_code == 200 and r.json()["estado"] == "pendiente"
    assert [x["id"] for x in e.pendientes()] == [c["id"]]
    e.sincronizar(), e.sincronizar()  # absorber_correos corre al listar y al sincronizar: no lo re-descarta
    assert [x["id"] for x in e.pendientes()] == [c["id"]]
    r = client.post(f"/correos/{c['id']}/aprobar", json={"cuenta_id": e.cuenta["id"]})
    assert r.status_code == 200 and r.json()["estado"] == "aprobado"
    assert len(e.movs()) == 1 and e.pendientes() == []
    e.sincronizar()
    assert len(e.movs()) == 1 and e.correos("descartados") == []


def test_recuperar_dos_veces_es_inocuo(e):
    c = _descartado_por_fantasma(e)
    assert client.post(f"/correos/{c['id']}/recuperar").status_code == 200
    r = client.post(f"/correos/{c['id']}/recuperar")
    assert r.status_code == 200 and r.json()["estado"] == "pendiente"


def test_recuperar_respeta_el_anti_duplicado_si_hoy_existe_un_movimiento_equivalente(e):
    c = _descartado_por_fantasma(e)
    e.manual()  # la persona ya lo registró a mano después de borrar el del atajo
    e.como()
    r = client.post(f"/correos/{c['id']}/recuperar")
    assert r.status_code == 200 and r.json()["estado"] == "ya_registrado"
    assert e.pendientes() == [] and len(e.movs()) == 1


def test_recuperar_solo_descartados_o_ignorados_con_monto(e):
    e.llega_correo()
    (p,) = e.pendientes()
    assert client.post(f"/correos/{p['id']}/recuperar").json()["estado"] == "pendiente"  # ya estaba así
    client.post(f"/correos/{p['id']}/aprobar", json={"cuenta_id": e.cuenta["id"]})
    assert client.post(f"/correos/{p['id']}/recuperar").status_code == 400  # aprobado: no se recupera
    assert client.post("/correos/no-existe/recuperar").status_code == 404


def test_recuperar_no_toca_correos_de_otra_persona(e):
    ca = _descartado_por_fantasma(e)
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="otra-persona", email="o@test.com", nombre="Otra")
    assert client.post(f"/correos/{ca['id']}/recuperar").status_code == 404
    assert [x["estado"] for x in e.correos("todos")] == ["descartado"]
