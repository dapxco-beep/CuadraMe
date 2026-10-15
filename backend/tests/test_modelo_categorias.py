"""Modelo de categorías: huellas estables, nada de aprender de nombres propios, costos de sistema
intocables, Bre-B, confianza con evidencia, «reentrenar» al vuelo, script de evaluación y panel de
calidad del dueño. TODO con datos SINTÉTICOS (marcas públicas y nombres inventados)."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'modelo.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import classifier  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.autocat import ClasificadorUsuario, decidir_categoria, movimientos_confirmados  # noqa: E402
from app.calidad_categorias import PERSONALIZADAS, origen_tras_edicion, panel_calidad  # noqa: E402
from app.clave_comercio import clave_comercio, es_transferencia_entre_personas  # noqa: E402
from app.comercios_conocidos import clasificar_por_diccionario  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Movimiento  # noqa: E402

client = TestClient(app)
ACTIVAS = {"comida", "transporte", "ocio", "hogar", "salud", "transferencias", "ingresos", "otros", "suscripciones"}


# ── (c) huella estable ante prefijos de pasarela, ciudades, NIT y códigos ───────────────────
@pytest.mark.parametrize("descripcion,esperada", [
    ("Pagaste en Netflix con Cuenta Nu", "netflix"),
    ("PAGO PSE NETFLIX COLOMBIA", "netflix"),
    ("COMPRA EN NETFLIX BOGOTA", "netflix"),
    ("DLO*Spotify", "spotify"),
    ("BOLD*Cafe Luna", "cafe luna"),
    ("Mercpago*Rappi", "rappi"),
    ("PAYU*Netflix", "netflix"),
    ("Compra en EXITO CHAPINERO NIT 890900608", "exito chapinero"),
    ("ENVIO CON BRE-B A: LAURA", "laura"),
])
def test_huella_estable(descripcion, esperada):
    assert clave_comercio(descripcion) == esperada


# ── (d) transferencias entre personas ───────────────────────────────────────────────────────
@pytest.mark.parametrize("descripcion,es_persona", [
    ("Para MARIA FERNANDA LOPEZ", True),
    ("De CARLOS ANDRES RUIZ", True),
    ("Enviaste a Juan Perez", True),
    ("Recibiste de Ana Gomez", True),
    ("ENVIO CON BRE-B A: LAURA", True),
    ("RECIBI POR BRE-B DE:", True),
    ("PAGO EN QR BRE-B: Bokado", False),       # negocio, no persona
    ("Compra en DECATHLON", False),           # 'de' dentro de otra palabra
    ("Para", False),
    ("Compra en UBER RIDES", False),
])
def test_detecta_transferencias_entre_personas(descripcion, es_persona):
    assert es_transferencia_entre_personas(descripcion) is es_persona


def test_no_se_aprende_de_nombres_propios():
    historial = [{"descripcion": "Para MARIA FERNANDA LOPEZ", "categoria": "Comida", "tipo": "expense"}] * 6
    modelo = classifier.build_model(historial)
    assert classifier.classify("Para MARIA FERNANDA LOPEZ", modelo) is None
    assert classifier.classify("Para MARIA PEREZ", modelo) is None  # ni siquiera por compartir un nombre
    r = decidir_categoria("Para MARIA FERNANDA LOPEZ", [], modelo, ACTIVAS)
    assert r["categoria"] == "Transferencias" and r["confianza"] <= 0.5 and r["fuente"] == "diccionario"


@pytest.mark.parametrize("descripcion,categoria,tipo", [
    ("ENVIO CON BRE-B A: LAURA", "Transferencias", "expense"),
    ("RECIBI POR BRE-B DE: MARIA", "Transferencias", "income"),
    ("PAGO EN QR BRE-B: Bokado", "Transferencias", "expense"),     # negocio desconocido: se pregunta
    ("PAGO EN QR BRE-B: Pizzeria Roma", "Comida", "expense"),       # negocio reconocido: su categoría
])
def test_bre_b(descripcion, categoria, tipo):
    r = clasificar_por_diccionario(descripcion)
    assert r["categoria"] == categoria and r["tipo"] == tipo
    if categoria == "Transferencias":
        assert r["confianza"] <= 0.5  # nunca se confirma sola


# ── (a) marcas públicas y pasarelas ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("descripcion,categoria", [
    ("Compra en OXXO EDS AVENIDA 68 con tarjeta débito", "Transporte"),
    ("Bold Sa*Smart Fit", "Salud"),
    ("DLO*Spotify", "Suscripciones"),
    ("Compra en DUNKIN CALLE 80", "Comida"),
    ("Compra en MERCALDAS", "Comida"),
    ("Compra en YANGO", "Transporte"),
    ("Compra en TICKETMASTER", "Ocio"),
    ("Compra en MEDPLUS", "Salud"),
    ("Compra en DOMESTIKA", "Educación"),
    ("Pago Camara de Comercio de Bogota", "Impuestos"),
])
def test_marcas_publicas(descripcion, categoria):
    assert clasificar_por_diccionario(descripcion)["categoria"] == categoria


# ── (f) categorías de sistema: el historial no las pisa ─────────────────────────────────────
@pytest.mark.parametrize("descripcion,categoria", [
    ("CUOTA DE MANEJO TARJETA", "Cuota de manejo"),
    ("IMPUESTO 4X1000 GMF", "4x1000 (GMF)"),
    ("ABONO INTERESES AHORROS", "Rendimientos"),
])
def test_costos_de_sistema_no_se_pisan(descripcion, categoria):
    # el historial dice (mal) que esas líneas son 'Ocio': el modelo no debe usarlo
    historial = [{"descripcion": descripcion, "categoria": "Ocio", "tipo": "expense"}] * 5
    modelo = classifier.build_model(historial)
    r = decidir_categoria(descripcion, [], modelo, ACTIVAS | {categoria.lower()})
    assert r["categoria"] == categoria


def test_el_modelo_no_aprende_categorias_de_sistema():
    modelo = classifier.build_model([{"descripcion": "CUOTA MANEJO VISA", "categoria": "Cuota de manejo", "tipo": "expense"}])
    assert modelo["total"] == 0


# ── (b) confianza según evidencia ───────────────────────────────────────────────────────────
def test_la_confianza_crece_con_la_evidencia():
    uno = classifier.build_model([{"descripcion": "Compra en KOPI ZEBRA", "categoria": "Comida", "tipo": "expense"}])
    diez = classifier.build_model([{"descripcion": "Compra en KOPI ZEBRA", "categoria": "Comida", "tipo": "expense"}] * 10)
    c1 = classifier.classify("KOPI ZEBRA norte", uno)["confianza"]
    c10 = classifier.classify("KOPI ZEBRA norte", diez)["confianza"]
    assert 0.55 <= c1 < c10 <= 0.97


def test_parecido_debil_cede_ante_una_marca_conocida():
    # 'Uber Rides' solo se parece a 'Uber Eats' por una palabra: el diccionario (Uber -> Transporte) gana
    modelo = classifier.build_model([{"descripcion": "Compra en UBER EATS", "categoria": "Comida", "tipo": "expense"}])
    r = decidir_categoria("Compra en UBER RIDES", [], modelo, ACTIVAS)
    assert r["categoria"] == "Transporte"


# ── «reentrenar»: el aprendido se calcula al vuelo desde lo confirmado ──────────────────────
@pytest.fixture()
def usuario(request):
    uid = f"user-mod-{request.node.name}"[:60]
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id=uid, email="m@test.com", nombre="Mod")
    yield uid


@pytest.fixture()
def cuenta(usuario):
    r = client.post("/cuentas", json={"nombre": "Principal", "saldo": 1_000_000})
    assert r.status_code == 200, r.text
    client.get("/categorias")
    return r.json()


def _mov(cuenta, descripcion, categoria=None, monto=10000):
    body = {"cuenta_id": cuenta["id"], "descripcion": descripcion, "monto": monto, "tipo": "expense"}
    if categoria:
        body["categoria"] = categoria
    r = client.post("/movimientos", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _clasificar(uid, descripcion):
    with SessionLocal() as db:
        return ClasificadorUsuario(db, uid).clasificar(descripcion)


def test_reentrenar_es_automatico_al_confirmar_y_al_corregir(usuario, cuenta):
    assert _clasificar(usuario, "Zorbex Qantu cambio") is None
    m = _mov(cuenta, "Zorbex Qantu revision", "Hogar")           # lo escribió la persona
    assert _clasificar(usuario, "Zorbex Qantu cambio")["categoria"] == "Hogar"
    client.put(f"/movimientos/{m['id']}", json={"categoria": "Ocio"})  # lo corrige
    r = _clasificar(usuario, "Zorbex Qantu cambio")
    assert r["categoria"] == "Ocio" and r["fuente"] == "learned"


def test_lo_automatico_sin_confirmar_no_entrena(usuario, cuenta):
    m = _mov(cuenta, "Rappi pedido 123")  # la app lo puso en Comida (auto, sin confirmar)
    assert m["cat_confirmada"] is False
    with SessionLocal() as db:
        assert movimientos_confirmados(db, usuario) == []
    client.post("/movimientos/confirmar-categorias", json={"movimiento_ids": [m["id"]]})
    with SessionLocal() as db:
        assert len(movimientos_confirmados(db, usuario)) == 1  # confirmado: ahora sí entrena


def test_el_aprendido_no_mezcla_usuarios(usuario, cuenta):
    _mov(cuenta, "Zorbex Qantu revision", "Hogar")
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="otro-mod", email="o@test.com", nombre="O")
    assert _clasificar("otro-mod", "Zorbex Qantu cambio") is None


# ── (e) sugerencias recurrentes ─────────────────────────────────────────────────────────────
def test_sugerencia_marca_recurrente_si_hay_3_meses(usuario, cuenta):
    from datetime import datetime
    with SessionLocal() as db:
        for dia, mes in ((5, 1), (6, 2), (7, 3), (8, 3)):
            db.add(Movimiento(usuario_id=usuario, cuenta_id=cuenta["id"], descripcion="Compra en KOPI ZEBRA", monto=9000,
                              tipo="expense", categoria="Comida", cat_confirmada=True, fecha=datetime(2026, mes, dia)))
        for dia in (1, 2, 3, 4):
            db.add(Movimiento(usuario_id=usuario, cuenta_id=cuenta["id"], descripcion="Compra en QUIRIGUA AZUL", monto=9000,
                              tipo="expense", categoria="Ocio", cat_confirmada=True, fecha=datetime(2026, 4, dia)))
        db.commit()
    sug = {s["huella"]: s for s in client.get("/reglas-categoria/sugerencias").json()["sugerencias"]}
    assert sug["kopi zebra"]["recurrente"] is True and sug["kopi zebra"]["meses"] == 3
    assert sug["quirigua azul"]["recurrente"] is False and sug["quirigua azul"]["meses"] == 1


# ── calidad: acertada vs corregida ──────────────────────────────────────────────────────────
def test_origen_tras_edicion():
    assert origen_tras_edicion("comercio", "Comida", "Ocio") == "corregida:Comida"
    assert origen_tras_edicion("comercio", "Comida", "Comida") == "comercio"      # la aceptó
    assert origen_tras_edicion("corregida:Comida", "Ocio", "Hogar") == "corregida:Comida"
    assert origen_tras_edicion(None, "Comida", "Ocio") is None                      # la escribió ella
    assert origen_tras_edicion("marcada", "Otros", "Ocio") is None


def test_corregir_una_sugerencia_deja_rastro(usuario, cuenta):
    m = _mov(cuenta, "Rappi pedido 999")
    assert m["cat_origen"] == "comercio" and m["categoria"] == "Comida"
    r = client.put(f"/movimientos/{m['id']}", json={"categoria": "Ocio"}).json()
    assert r["cat_origen"] == "corregida:Comida" and r["cat_confirmada"] is True


def test_panel_calidad_solo_conteos_y_agrupa_personalizadas(usuario, cuenta):
    from datetime import datetime
    base = dict(usuario_id=usuario, cuenta_id=cuenta["id"], tipo="expense", monto=1000, fecha=datetime(2026, 5, 1))
    with SessionLocal() as db:
        antes = panel_calidad(db)
        db.add_all([
            Movimiento(descripcion="SECRETO UNO", categoria="Comida", cat_origen="comercio", cat_confirmada=True, **base),
            Movimiento(descripcion="SECRETO DOS", categoria="Comida", cat_origen="regla", cat_confirmada=True, **base),
            Movimiento(descripcion="SECRETO TRES", categoria="Ocio", cat_origen="corregida:Comida", cat_confirmada=True, **base),
            Movimiento(descripcion="SECRETO CUATRO", categoria="Comida", cat_origen="similar", cat_confirmada=False, **base),
            Movimiento(descripcion="SECRETO CINCO", categoria="Juliana", cat_origen="corregida:Lote", cat_confirmada=True, **base),
        ])
        db.commit()
        p = panel_calidad(db)
    assert p["acertadas"] - antes["acertadas"] == 2 and p["corregidas"] - antes["corregidas"] == 2
    assert p["pendientes"] - antes["pendientes"] == 1
    assert PERSONALIZADAS in {c["categoria"] for c in p["por_categoria"]}
    texto = json.dumps(p, ensure_ascii=False)
    assert "SECRETO" not in texto and "Juliana" not in texto and "Lote" not in texto


def test_panel_calidad_en_salud_del_negocio_solo_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "dueno@cuadrame.test")
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="mod-admin", email="DUENO@cuadrame.test", nombre="D")
    r = client.get("/metricas/panel")
    assert r.status_code == 200 and "exactitud" in r.json()["calidad_categorias"]
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="mod-normal", email="x@test.com", nombre="X")
    assert client.get("/metricas/panel").status_code == 404


# ── script de evaluación ────────────────────────────────────────────────────────────────────
def _export_sintetico(ruta: Path):
    filas = []
    for i in range(4):
        filas.append({"descripcion": "Compra en KOPI ZEBRA", "categoria": "Comida", "tipo": "expense", "cat_confirmada": True})
        filas.append({"descripcion": f"Para PERSONA INVENTADA {i}", "categoria": "Transferencias", "tipo": "expense", "cat_confirmada": True})
    filas += [
        {"descripcion": "Compra en UBER RIDES", "categoria": "Transporte", "tipo": "expense", "cat_confirmada": True},
        {"descripcion": "Compra en NETFLIX", "categoria": "Suscripciones", "tipo": "expense", "cat_confirmada": True},
        {"descripcion": "Cosa desconocida XYZ", "categoria": "Otros", "tipo": "expense", "cat_confirmada": True},
        {"descripcion": "Esto lo puso la app", "categoria": "Comida", "tipo": "expense", "cat_confirmada": False},
    ]
    ruta.write_text(json.dumps(filas), encoding="utf-8")


def test_script_evaluacion_agregados_y_privacidad(tmp_path, capsys):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import evaluar_clasificador as ev

    ruta = tmp_path / "export.json"
    _export_sintetico(ruta)
    assert ev.main([str(ruta), "--salida-json", str(tmp_path / "agg.json")]) == 0
    salida = capsys.readouterr().out
    agg = json.loads((tmp_path / "agg.json").read_text(encoding="utf-8"))
    assert agg["n"] == 11  # los de la app (cat_confirmada False) no son verdad de referencia
    assert agg["segmentos"]["n_personas"] == 4
    assert agg["segmentos"]["personas_propuestas_como_transferencias"] == 1.0
    assert 0 <= agg["exactitud_global"] <= 1 and 0 <= agg["cobertura_otros"] <= 1
    # sin --mostrar-errores no se imprime ninguna descripción cruda
    for crudo in ("PERSONA INVENTADA", "Cosa desconocida", "KOPI ZEBRA"):
        assert crudo not in salida
    # con la bandera local sí (solo errores)
    ev.main([str(ruta), "--mostrar-errores"])
    assert "[LOCAL]" in capsys.readouterr().out


def test_script_evaluacion_uno_fuera_por_comercio_no_hace_trampa():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import evaluar_clasificador as ev

    movs = [{"descripcion": "Zorbex Qantu revision", "categoria": "Hogar", "tipo": "expense"}] * 4
    # 'dejar un comercio fuera' quita los 4: no hay de dónde copiar la categoría
    assert ev.evaluar(movs, modo="comercio")["exactitud_global"] == 0
    # 'dejar un movimiento fuera' sí encuentra a sus hermanos (comercio repetido)
    assert ev.evaluar(movs, modo="movimiento")["exactitud_global"] == 1
