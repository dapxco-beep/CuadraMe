"""«Todos los extractos»: de qué mes es cada uno, de qué tipo, por qué no se pudo leer y que NINGÚN extracto
quede invisible (revisados, por revisar, sin procesar, con clave, con error, anteriores, sin PDF).

Parte pura (app/extractos_vista.py) y parte con base de datos (GET /sincronizacion/extractos), con datos
sintéticos que reproducen el caso real: 6 revisados de Nu sin mes en el periodo, 3 con clave, 4 sin procesar,
3 con error de lectura (sin motivo guardado) y 8 correos sin PDF."""
import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'extractos_todos.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import extractos_vista as ev  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto  # noqa: E402

client = TestClient(app)
U = UsuarioActual(id="todos-ext-u", email="todos-ext@test.com", nombre="Persona Uno")
OTRO = UsuarioActual(id="todos-ext-otro", email="todos-ext-otro@test.com", nombre="Persona Dos")
ACTUAL = {"u": U}


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: ACTUAL["u"]
    yield
    ACTUAL["u"] = U
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def limpio():
    """Cada prueba parte sin filas de estos usuarios."""
    def borrar():
        db = SessionLocal()
        try:
            for u in (U, OTRO):
                for m in (ExtractoCorreo, HistorialExtracto, Cuenta):
                    db.query(m).filter(m.usuario_id == u.id).delete()
            db.commit()
        finally:
            db.close()
    borrar()
    yield
    borrar()


# ── Puro: de qué mes es ──────────────────────────────────────────────────────────────────────────
def test_nu_el_nombre_del_archivo_es_la_fecha_de_pago_y_el_periodo_es_el_mes_anterior():
    r = ev.deducir_periodo(archivo="Nu_2026-08-04.pdf", banco="Nu Colombia", recibido_en=datetime(2026, 8, 4, 9))
    assert (r["mes"], r["fuente"]) == ("2026-07", "archivo")
    # En enero, el periodo es diciembre del año anterior.
    assert ev.deducir_periodo(archivo="Nu_2026-01-04.pdf", banco="Nu")["mes"] == "2025-12"
    # Otros bancos: una fecha en el nombre vale su propio mes (no se aplica la regla de Nu).
    assert ev.deducir_periodo(archivo="Bancolombia_2026-08-04.pdf", banco="Bancolombia")["mes"] == "2026-08"
    # Nu se reconoce también por el remitente.
    assert ev.deducir_periodo(archivo="x_2026-08-04.pdf", remitente="Nu <info@nu.com.co>")["mes"] == "2026-07"
    # «Nuevo» o «Nutresa» no son Nu.
    assert not ev.es_nu("Nutresa") and not ev.es_nu("Banco Nuevo") and ev.es_nu("Nu Colombia")


def test_orden_de_deduccion_periodo_asunto_archivo_lineas_recepcion():
    recibido = datetime(2026, 8, 4)
    base = dict(recibido_en=recibido, banco="Davivienda")
    assert ev.deducir_periodo(periodo="junio 2026", asunto="Tu extracto de julio", **base)["fuente"] == "periodo"
    assert ev.deducir_periodo(periodo="01/06/2026 a 30/06/2026", **base)["mes"] == "2026-06"
    r = ev.deducir_periodo(asunto="Tu extracto de julio", archivo="x_2026-03-01.pdf", **base)
    assert (r["mes"], r["fuente"]) == ("2026-07", "asunto")
    r = ev.deducir_periodo(archivo="Extracto_mayo_2026.pdf", mes_lineas="2026-02", **base)
    assert (r["mes"], r["fuente"]) == ("2026-05", "archivo")
    r = ev.deducir_periodo(archivo="extracto.pdf", mes_lineas="2026-06", **base)
    assert (r["mes"], r["fuente"], r["deducido"]) == ("2026-06", "lineas", False)
    r = ev.deducir_periodo(archivo="extracto.pdf", **base)
    assert (r["mes"], r["fuente"], r["deducido"]) == ("2026-07", "recepcion", True)
    assert ev.deducir_periodo(archivo="extracto.pdf") == {"mes": None, "fuente": None, "deducido": True}


def test_periodo_texto_y_etiquetas():
    assert ev.periodo_texto("2026-07") == "julio 2026"
    with pytest.raises(ValueError):
        ev.periodo_texto("2026-13")
    assert ev.etiqueta_mes("2026-07") == "Julio 2026" and ev.etiqueta_mes(None) == "Mes por confirmar"
    assert ev.corte_del_periodo("01/06/2026 a 14/07/2026") == "2026-07-14"
    assert ev.fecha_corta("2026-07-14") == "14 jul 2026"


def test_titulo_banco_tipo_y_mes_en_grande():
    assert ev.titulo_extracto(banco="Nu Colombia", tipo="cuenta", mes="2026-07") == "Nu Colombia · Cuenta · Julio 2026"
    assert ev.titulo_extracto(banco="Nu Colombia", tipo="tarjeta", mes="2026-07", corte="2026-07-14") == "Tarjeta Nu · corte 14 jul 2026"
    assert ev.titulo_extracto(banco="Nu Colombia", tipo="tarjeta", mes="2026-07") == "Nu Colombia · Tarjeta · Julio 2026"
    assert ev.titulo_extracto(banco="", tipo="", mes=None) == "Banco sin identificar · Mes por confirmar"
    assert ev.tipo_de_extracto("credito") == "tarjeta" and ev.tipo_de_extracto("ahorro") == "cuenta"
    assert ev.tipo_de_extracto(None, "Tu extracto de tarjeta") == "tarjeta" and ev.tipo_de_extracto(None, "hola") == ""


# ── Puro: motivos y frases ───────────────────────────────────────────────────────────────────────
def test_motivos_de_error():
    assert ev.clasificar_motivo(pide_clave=True) == "clave_faltante"
    assert ev.clasificar_motivo(pide_clave=True, clave_dada=True) == "clave_incorrecta"
    assert ev.clasificar_motivo(texto="") == "pdf_escaneado"
    assert ev.clasificar_motivo(texto="una carta cualquiera") == "formato_no_reconocido"
    assert ev.clasificar_motivo(pdf_vacio=True, pide_clave=True) == "archivo_vacio"
    for codigo in ev.MOTIVOS:
        f = ev.frase_error(codigo)
        assert f.startswith("No pudimos leer este extracto: ") and len(ev.MOTIVOS[codigo][1]) > 10
    assert ev.frase_error(None).startswith("No se pudo leer (motivo no guardado)")
    assert "Intentar de nuevo" in ev.frase_error("sin_codigo_conocido")


def test_frases_de_resultado_nunca_dicen_cero_coinciden_con_el_banco():
    c37 = {"leidas": 37, "ya_estaban": 37, "nuevas_agregadas": 0, "por_revisar": 0}
    assert ev.frase_resultado("revisado", c37) == "Leímos 37 movimientos: 37 ya estaban registrados, 0 nuevos."
    c5 = {"leidas": 37, "ya_estaban": 32, "nuevas_agregadas": 5, "por_revisar": 0}
    assert "5 nuevos agregados, 32 ya estaban" in ev.frase_resultado("revisado", c5)
    assert ev.frase_resultado("revisado", {"leidas": 0}) == "No encontramos movimientos en este extracto."
    textos = [ev.frase_resultado(v, c37) for v in ev.ESTADOS_VISTA] + [ev.frase_error(m) for m in ev.MOTIVOS]
    assert not any("coinciden con el banco" in t for t in textos)
    assert ev.frase_contadores({"revisado": 6, "necesita_clave": 3, "sin_procesar": 4, "no_se_pudo_leer": 3}) == \
        "6 revisados · 3 con clave pendiente · 4 sin procesar · 3 con error"
    assert ev.frase_contadores({"revisado": 1}) == "1 revisado"


# ── Con base de datos ────────────────────────────────────────────────────────────────────────────
def _cuenta(nombre, tipo="ahorro"):
    return client.post("/cuentas", json={"nombre": nombre, "tipo": tipo, "saldo": 0}).json()["id"]


def _historial(cuenta_id, fechas, estado="conciliado", motivo=None, banco="nu", estados=None, corte=None):
    review = [{"estado": (estados or ["exacto"] * len(fechas))[i], "fecha": f, "descripcion": f"L{i}", "monto": 1,
               "tipo": "expense"} for i, f in enumerate(fechas)]
    db = SessionLocal()
    try:
        h = HistorialExtracto(usuario_id=U.id, cuenta_id=cuenta_id, banco_detectado=banco, estado=estado,
                              total_movimientos=len(fechas), review_json=json.dumps(review),
                              motivo_error=motivo, fecha_corte=corte)
        db.add(h)
        db.commit()
        return h.id
    finally:
        db.close()


def _correo(n, estado, archivo="", asunto="", periodo="", banco="Nu Colombia", cuenta=None, historial=None,
            recibido=None, motivo=None, usuario=U):
    db = SessionLocal()
    try:
        e = ExtractoCorreo(usuario_id=usuario.id, gmail_msg_id=f"m{n}", archivo=archivo, asunto=asunto,
                           remitente="Nu <info@nu.com.co>", banco=banco, periodo=periodo, estado=estado,
                           cuenta_sugerida_id=cuenta, historial_id=historial, recibido_en=recibido,
                           motivo_error=motivo)
        db.add(e)
        db.commit()
        return e.id
    finally:
        db.close()


def _escenario_real():
    """6 revisados (Nu, sin mes en el periodo), 3 con clave, 4 sin procesar, 3 con error, 2 por revisar, 8 sin PDF."""
    nu = _cuenta("Nu Colombia")
    tarjeta = _cuenta("Tarjeta Nu", "credito")
    ids = {}
    # 6 revisados: archivos Nu_<fecha de pago>.pdf de enero a junio; el periodo es el mes ANTERIOR a la fecha.
    for i, mes_pago in enumerate(range(2, 8), start=1):
        h = _historial(nu, [f"2026-{mes_pago - 1:02d}-10"] * 2)
        ids[f"rev{i}"] = _correo(i, "procesado", archivo=f"Nu_2026-{mes_pago:02d}-04.pdf", cuenta=nu, historial=h,
                                 recibido=datetime(2026, mes_pago, 4))
    # con clave: 2 de Nu desde el 4-ago (cuenta y tarjeta) y otro del 4-sep
    for i, (fecha, cta) in enumerate([("2026-08-04", nu), ("2026-08-04", tarjeta), ("2026-09-04", tarjeta)]):
        ids[f"clave{i}"] = _correo(10 + i, "falta_clave", archivo=f"Nu_{fecha}.pdf",
                                   recibido=datetime.fromisoformat(fecha), cuenta=cta)
    for i in range(4):  # sin procesar, sin banco
        ids[f"nuevo{i}"] = _correo(20 + i, "nuevo", archivo=f"extracto{i}.pdf", banco="", recibido=datetime(2026, 8 + i, 12))
    for i in range(3):  # error de lectura sin motivo guardado (históricos), mismo banco y cuenta
        _historial(nu, [], estado="error", banco="generico")
    for i in range(8):
        _correo(30 + i, "ignorado", asunto=f"Tu cuenta Nu {i}", archivo="")
    # 2 por revisar con 13 líneas sin resolver
    _historial(nu, ["2026-09-03"] * 8, estado="pendiente_revision", estados=["faltante"] * 8)
    _historial(tarjeta, ["2026-09-05"] * 5, estado="pendiente_revision", estados=["faltante"] * 5)
    return ids, nu, tarjeta


def test_ningun_extracto_queda_invisible_y_cada_fila_dice_su_mes(limpio):
    ids, nu, tarjeta = _escenario_real()
    r = client.get("/sincronizacion/extractos")
    assert r.status_code == 200
    d = r.json()
    c = d["contadores"]
    assert c["revisado"] == 6
    assert c["necesita_clave"] == 3
    assert c["sin_procesar"] == 4
    assert c["no_se_pudo_leer"] == 1  # los 3 intentos fallidos del mismo archivo y cuenta son UNA fila
    assert c["por_revisar"] == 2
    assert len(d["sin_adjunto"]) == 8 and "PDF" in d["razon_sin_adjunto"]
    assert d["resumen"] == "6 revisados · 2 por revisar · 3 con clave pendiente · 4 sin procesar · 1 con error"
    assert d["total"] == sum(c.values())
    revisados = [i for i in d["items"] if i["estado_vista"] == "revisado"]
    assert sorted(i["mes"] for i in revisados) == [f"2026-{m:02d}" for m in range(1, 7)]  # Nu: pago - 1 mes
    for i in revisados:
        assert i["titulo"].startswith("Nu Colombia · Cuenta · ")
        assert i["mes_etiqueta"] in i["titulo"] and "coinciden con el banco" not in i["resultado"]
        assert i["resultado"] == "Leímos 2 movimientos: 2 ya estaban registrados, 0 nuevos."
        assert "ver" in i["acciones"] and "revisar_de_nuevo" in i["acciones"]
    # Del más reciente al más antiguo (los sin mes al final).
    meses = [i["mes"] for i in d["items"] if i["mes"]]
    assert meses == sorted(meses, reverse=True)
    assert d["items"][-1]["mes"] is None or d["items"][-1]["mes"] == meses[-1]


def test_la_fila_de_error_muestra_el_motivo_o_dice_que_no_se_guardo(limpio):
    ids, nu, _ = _escenario_real()
    err = [i for i in client.get("/sincronizacion/extractos").json()["items"] if i["estado_vista"] == "no_se_pudo_leer"]
    assert len(err) == 1 and err[0]["copias"] == 3 and err[0]["copias_texto"] == "x3 intentos"
    assert err[0]["resultado"].startswith("No se pudo leer (motivo no guardado)")
    assert err[0]["acciones"] == ["subir_de_nuevo", "mi_banco_no_esta"]
    assert err[0]["mes_por_confirmar"] and "Mes por confirmar" in err[0]["titulo"]
    # Con motivo guardado en un correo: frase concreta y siguiente paso.
    _correo(90, "error", archivo="Nu_2026-11-04.pdf", cuenta=nu, motivo="pdf_escaneado", recibido=datetime(2026, 11, 4))
    d = client.get("/sincronizacion/extractos").json()
    f = next(i for i in d["items"] if i["motivo_error"] == "pdf_escaneado")
    assert f["resultado"].startswith("No pudimos leer este extracto: el PDF es una imagen")
    assert "Excel o CSV" in f["resultado"] and f["mes"] == "2026-10"
    assert f["acciones"] == ["intentar_de_nuevo", "mi_banco_no_esta"]


def test_un_correo_nuevo_que_ya_se_intento_leer_aparece_como_no_se_pudo_leer(limpio):
    nu = _cuenta("Nu Colombia")
    _correo(1, "nuevo", archivo="Nu_2026-08-04.pdf", cuenta=nu, motivo="error_temporal")
    i = client.get("/sincronizacion/extractos").json()["items"][0]
    assert i["estado_vista"] == "no_se_pudo_leer" and "problema momentáneo" in i["resultado"]


def test_duplicados_del_mismo_extracto_son_una_fila_con_x2_correos(limpio):
    nu = _cuenta("Nu Colombia")
    for n in (1, 2):
        _correo(n, "nuevo", archivo="Nu_2026-08-04.pdf", cuenta=nu, recibido=datetime(2026, 8, 4, n))
    # Sin cuenta conocida: se junta por banco + tipo + mes.
    for n in (3, 4):
        _correo(n, "nuevo", archivo="Nu_2026-05-04.pdf", cuenta=None, asunto="Tu extracto de tarjeta")
    items = client.get("/sincronizacion/extractos").json()["items"]
    assert len(items) == 2 and {i["copias_texto"] for i in items} == {"x2 correos"}
    assert all(i["estado_vista"] == "sin_procesar" and "aún no lo hemos leído" in i["resultado"] for i in items)


def test_tarjeta_con_corte_se_titula_con_la_fecha_de_corte(limpio):
    t = _cuenta("Tarjeta Nu", "credito")
    h = _historial(t, ["2026-07-10"], corte="2026-07-14")
    _correo(1, "procesado", archivo="Nu_2026-08-04.pdf", cuenta=t, historial=h)
    i = client.get("/sincronizacion/extractos").json()["items"][0]
    assert i["tipo"] == "tarjeta" and i["titulo"] == "Tarjeta Nu · corte 14 jul 2026"
    assert i["mes"] == "2026-07"


def test_periodo_deducido_se_guarda_y_la_recepcion_no(limpio):
    nu = _cuenta("Nu Colombia")
    a = _correo(1, "nuevo", archivo="Nu_2026-08-04.pdf", cuenta=nu)
    b = _correo(2, "nuevo", archivo="extracto.pdf", banco="", recibido=datetime(2026, 8, 4))
    client.get("/sincronizacion/extractos")
    db = SessionLocal()
    try:
        assert db.get(ExtractoCorreo, a).periodo == "julio 2026"
        assert db.get(ExtractoCorreo, b).periodo in ("", None)  # solo se supone por la fecha del correo
    finally:
        db.close()
    item_b = next(i for i in client.get("/sincronizacion/extractos").json()["items"] if i["extracto_id"] == b)
    assert item_b["mes"] == "2026-07" and item_b["mes_deducido"] is True and item_b["mes_fuente"] == "recepcion"


def test_fijar_el_mes_con_el_selector(limpio):
    nu = _cuenta("Nu Colombia")
    e = _correo(1, "nuevo", archivo="extracto.pdf", cuenta=nu)  # sin periodo, sin fecha: Mes por confirmar
    i = client.get("/sincronizacion/extractos").json()["items"][0]
    assert i["mes_por_confirmar"] and i["puede_fijar_mes"]
    assert client.put(f"/sincronizacion/extractos/{e}/mes", json={"mes": "2026-13"}).status_code == 422
    assert client.put(f"/sincronizacion/extractos/{e}/mes", json={"mes": "2026-04"}).json()["periodo"] == "abril 2026"
    i = client.get("/sincronizacion/extractos").json()["items"][0]
    assert i["mes"] == "2026-04" and not i["mes_por_confirmar"] and "Abril 2026" in i["titulo"]
    ACTUAL["u"] = OTRO
    assert client.put(f"/sincronizacion/extractos/{e}/mes", json={"mes": "2026-05"}).status_code == 404


def test_aislamiento_la_lista_es_solo_del_usuario(limpio):
    nu = _cuenta("Nu Colombia")
    _correo(1, "nuevo", archivo="Nu_2026-08-04.pdf", cuenta=nu)
    ACTUAL["u"] = OTRO
    d = client.get("/sincronizacion/extractos").json()
    assert d["items"] == [] and d["sin_adjunto"] == [] and d["total"] == 0 and d["resumen"] == ""


def test_la_cobertura_dice_lo_mismo_que_la_lista(limpio):
    """Cada celda trae el mismo título y estado que la lista, y un extracto con error ya no es «Sin datos»."""
    nu = _cuenta("Nu Colombia")
    hoy = datetime.utcnow()
    mes_actual = f"{hoy.year:04d}-{hoy.month:02d}"
    # Un extracto de Nu cuyo archivo es de este mes: el periodo es el mes anterior.
    ant = f"{hoy.year - 1:04d}-12" if hoy.month == 1 else f"{hoy.year:04d}-{hoy.month - 1:02d}"
    _correo(1, "error", archivo=f"Nu_{mes_actual}-04.pdf", cuenta=nu, motivo="archivo_vacio")
    est = client.get("/sincronizacion/estado").json()
    celda = next(m for c in est["cuentas"] if c["id"] == nu for m in c["meses"] if m["mes"] == ant)
    assert celda["estado"] == "no_se_pudo_leer"
    assert celda["lista"][0]["estado_vista"] == "no_se_pudo_leer"
    todos = est["todos_extractos"]["items"]
    assert celda["lista"][0]["titulo"] == todos[0]["titulo"]
    assert est["todos_extractos"]["contadores"]["no_se_pudo_leer"] == 1


def test_banco_del_titulo_usa_la_cuenta_cuando_lo_detectado_viene_en_minuscula_o_generico():
    assert ev.banco_para_titulo("nu", "Nu Colombia") == "Nu Colombia"
    assert ev.banco_para_titulo("generico", "Nu Colombia") == "Nu Colombia"
    assert ev.banco_para_titulo("generico", "") == ""
    assert ev.banco_para_titulo("Bancolombia", "Mi ahorro") == "Bancolombia"
    assert ev.banco_para_titulo("nu", "") == "Nu"


def test_estado_corto_dice_en_una_linea_que_pasa_con_cada_extracto():
    c = {"leidas": 52, "ya_estaban": 0, "nuevas_agregadas": 0, "por_revisar": 52}
    assert ev.estado_corto("por_revisar", c) == "Falta importar 52"
    assert ev.estado_corto("revisado", {"leidas": 37, "por_revisar": 0}) == "Conciliado ✓ · 37 movimientos"
    assert ev.estado_corto("revisado", {"leidas": 1, "por_revisar": 0}) == "Conciliado ✓ · 1 movimiento"
    assert ev.estado_corto("necesita_clave", {}) == "No se pudo leer: falta la clave del PDF"
    assert ev.estado_corto("necesita_clave", {}, clave_estado="no_abrio") == "No se pudo leer: la clave del PDF no abrió"
