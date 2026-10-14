"""Memoria por usuario y señales: casos SINTÉTICOS (nombres y montos inventados)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import classifier, memoria_usuario as mu  # noqa: E402
from app.autocat import decidir_categoria  # noqa: E402

ACTIVAS = {"comida", "transporte", "ocio", "hogar", "salud", "transferencias", "ingresos", "otros", "arriendo"}


def _mov(desc, cat, monto=100000, fecha="2025-03-02", tipo="expense"):
    return {"descripcion": desc, "categoria": cat, "monto": monto, "fecha": fecha, "tipo": tipo}


def _decidir(desc, historial_movs, contexto=None):
    mem = mu.construir_memoria(historial_movs)
    h = {"memoria": mem, "senales": mu.construir_senales(historial_movs, mem)}
    modelo = classifier.build_model(historial_movs)
    return decidir_categoria(desc, [], modelo, ACTIVAS, historial=h, contexto=contexto)


def test_persona_con_dos_confirmaciones_iguales_propone_con_confianza_alta():
    hist = [_mov("Para ZOILA PRUEBA UNO", "Arriendo", fecha="2025-01-03"),
            _mov("Enviaste a ZOILA PRUEBA UNO", "Arriendo", fecha="2025-02-03")]
    r = _decidir("Para ZOILA PRUEBA UNO", hist)
    assert r["categoria"] == "Arriendo" and r["fuente"] == "historial"
    assert r["confianza"] >= mu.UMBRAL_PROPUESTA and not r["tentativa"]
    assert "historial" in r["razon"]


def test_una_sola_confirmacion_es_media_y_queda_marcada():
    r = _decidir("Para ZOILA PRUEBA UNO", [_mov("Para ZOILA PRUEBA UNO", "Arriendo")])
    assert r["categoria"] == "Arriendo" and r["fuente"] == "historial"
    assert mu.CONF_UNA_VEZ <= r["confianza"] < 0.95
    assert r["razon"].startswith("aprendida de tu historial")


def test_dos_categorias_en_pugna_es_ambiguo_y_no_se_propone():
    hist = [_mov("Para ZOILA PRUEBA UNO", "Arriendo"), _mov("Para ZOILA PRUEBA UNO", "Comida")]
    assert _decidir("Para ZOILA PRUEBA UNO", hist) is None
    h = mu.consultar_memoria("Para ZOILA PRUEBA UNO", mu.construir_memoria(hist))
    assert h["estado"] == "ambiguo"
    assert {c for c, _ in h["opciones"]} == {"Arriendo", "Comida"}


def test_la_memoria_es_de_cada_usuario_no_se_comparte():
    suyo = [_mov("Para ZOILA PRUEBA UNO", "Arriendo")] * 3
    otro = []  # otro usuario: sin historial -> nada aprendido del nombre
    assert _decidir("Para ZOILA PRUEBA UNO", suyo)["categoria"] == "Arriendo"
    r = _decidir("Para ZOILA PRUEBA UNO", otro)
    # sin historial propio solo queda la transferencia a ciegas, con confianza baja
    assert r is None or (r["categoria"] == "Transferencias" and r["confianza"] < mu.UMBRAL_PROPUESTA)


def test_persona_nueva_es_transferencias_con_confianza_baja_y_tentativa():
    hist = [_mov("Para OTRA PERSONA DOS", "Comida")]
    r = _decidir("Para NOMBRE NUEVO TRES", hist)
    assert r["categoria"] == "Transferencias" and r["tentativa"] is True and r["confianza"] < 0.8


def test_ruido_de_prefijos_no_separa_al_mismo_beneficiario():
    assert mu.clave_beneficiario("Para ZOILA PRUEBA UNO") == mu.clave_beneficiario("ENVIO CON BRE-B A: zoila prueba uno")


def test_comercio_repetido_tambien_usa_la_memoria():
    hist = [_mov("COMPRA TIENDA INVENTADA XYZ", "Ocio")] * 2
    r = _decidir("COMPRA TIENDA INVENTADA XYZ", hist)
    assert r["categoria"] == "Ocio" and r["fuente"] == "historial"


def test_una_regla_del_usuario_gana_a_la_memoria():
    class R:
        patron, categoria, tipo, activa = "zoila prueba", "Salud", None, True
    hist = [_mov("Para ZOILA PRUEBA UNO", "Arriendo")] * 3
    mem = mu.construir_memoria(hist)
    r = decidir_categoria("Para ZOILA PRUEBA UNO", [R()], classifier.build_model(hist), ACTIVAS,
                          historial={"memoria": mem, "senales": None})
    assert r["categoria"] == "Salud" and r["fuente"] == "regla"


def test_senales_se_abstienen_con_poco_historial():
    hist = [_mov("Para AAA BBB", "Hogar")] * 5
    assert mu.predecir_senales("Para CCC DDD", {"monto": 100000, "fecha": "2025-03-02", "tipo": "expense"},
                               mu.construir_senales(hist)) is None


def test_senales_proponen_con_regularidad_clara_y_se_abstienen_si_no():
    hist = [_mov(f"Para PERSONA NUMERO {i}", "Hogar", monto=1200000, fecha="2025-%02d-02" % (1 + i % 12))
            for i in range(30)]
    hist += [_mov(f"Compra Lugar {i}", "Comida", monto=23500 + i * 137, fecha="2025-%02d-18" % (1 + i % 12))
             for i in range(30)]
    sen = mu.construir_senales(hist)
    p = mu.predecir_senales("Para NUEVA PERSONA", {"monto": 1200000, "fecha": "2025-05-02", "tipo": "expense"},
                            sen, umbral=0.6)
    assert p and p["categoria"] == "Hogar"
    # monto y día que no se parecen a nada claro: puede abstenerse (nunca fuerza una categoría con poca confianza)
    q = mu.predecir_senales("zzz", {}, sen)
    assert q is None


def test_rasgos_de_monto_redondo_y_dia():
    f = mu.rasgos("Para X Y", {"monto": 1500000, "fecha": "2025-05-03", "tipo": "expense", "cuenta_tipo": "ahorro"})
    assert "red:r100k" in f and "dia:d0" in f and "tipo:expense" in f and "cuenta:ahorro" in f and "persona" in f
    assert "red:r0" in mu.rasgos("Compra", {"monto": 12345})
