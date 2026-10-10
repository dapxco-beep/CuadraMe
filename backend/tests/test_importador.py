"""Importar movimientos desde CSV / Excel: parseo de formatos colombianos, detección de
columnas, mapeo editable, vista previa con duplicados y confirmación idempotente."""
import base64
import io
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'importar.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.importador_tabular import (  # noqa: E402
    ErrorArchivo,
    analizar,
    detectar_orden_fecha,
    parse_fecha,
    parse_monto,
)
from app.main import app  # noqa: E402

client = TestClient(app)
USUARIO = {"actual": UsuarioActual(id="imp-0", email="i@test.com", nombre="Imp")}


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["actual"]
    yield


def como(uid):
    USUARIO["actual"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre=uid)


# ── Parsers ──────────────────────────────────────────

@pytest.mark.parametrize("texto,esperado", [
    ("1.234.567,89", 1234567.89),
    ("1,234,567.89", 1234567.89),
    ("$ 45.000", 45000.0),
    ("45000", 45000.0),
    ("1.234", 1234.0),          # 3 dígitos tras el único separador = miles (pesos)
    ("12,5", 12.5),             # 1-2 dígitos = decimal
    ("1,5", 1.5),
    ("(45.000)", -45000.0),     # paréntesis = negativo
    ("45.000-", -45000.0),      # signo al final
    ("-3.500,00", -3500.0),
    ("45.000 DB", -45000.0),
    ("2.000.000 CR", 2000000.0),
])
def test_parse_monto_formatos_colombianos(texto, esperado):
    assert parse_monto(texto) == pytest.approx(esperado)


def test_parse_monto_respeta_el_separador_elegido_por_el_usuario():
    assert parse_monto("1.234", "punto") == pytest.approx(1.234)
    assert parse_monto("1,234", "coma") == pytest.approx(1.234)
    assert parse_monto("abc") is None and parse_monto("") is None and parse_monto(None) is None
    assert parse_monto(1234.5) == 1234.5


def test_parse_fecha_formatos():
    d = datetime(2026, 3, 5)
    assert parse_fecha("05/03/2026") == d
    assert parse_fecha("5-3-26") == d
    assert parse_fecha("2026-03-05") == d
    assert parse_fecha("05/03/2026 14:30") == d
    assert parse_fecha("5 mar 2026") == d
    assert parse_fecha("05-mar-26") == d
    assert parse_fecha(datetime(2026, 3, 5, 18, 0)) == d
    assert parse_fecha("03/05/2026", "mdy") == d
    assert parse_fecha(46086) == datetime(2026, 3, 5)   # número serial de Excel
    assert parse_fecha("31/02/2026") is None and parse_fecha("hola") is None


def test_orden_de_fecha_solo_cambia_con_evidencia():
    assert detectar_orden_fecha(["05/03/2026", "20/03/2026"]) == "dmy"
    assert detectar_orden_fecha(["03/20/2026", "03/05/2026"]) == "mdy"
    assert detectar_orden_fecha(["05/03/2026"]) == "dmy"  # ambiguo: se queda con día primero (Colombia)


# ── Análisis de archivos ──────────────────────────────

CSV_BANCO = (
    "Movimientos de tu cuenta\n"
    "Generado 01/10/2026\n"
    "\n"
    "Fecha;Descripción;Débito;Crédito;Saldo\n"
    "01/10/2026;COMPRA EXITO 123;45.000,50;;1.000.000,00\n"
    "02/10/2026;ABONO NOMINA;;2.500.000,00;3.500.000,00\n"
    "03/10/2026;PAGO TARJETA CREDITO;300.000,00;;3.200.000,00\n"
    "Total;;345.000,50;2.500.000,00;\n"
).encode("utf-8")


def test_csv_con_titulos_debito_credito_y_coma_decimal():
    r = analizar("extracto.csv", CSV_BANCO)
    assert r["fila_encabezado"] == 2
    assert r["mapeo"]["fecha"] == 0 and r["mapeo"]["descripcion"] == 1
    assert r["mapeo"]["debito"] == 2 and r["mapeo"]["credito"] == 3 and r["mapeo"]["saldo"] == 4
    assert r["opciones"]["separador_decimal"] == "coma"
    movs = r["movimientos"]
    assert [(m["fecha"], m["tipo"], m["monto"]) for m in movs] == [
        ("2026-10-01", "expense", 45000.5),
        ("2026-10-02", "income", 2_500_000.0),
        ("2026-10-03", "expense", 300_000.0),
    ]
    assert movs[0]["saldo"] == 1_000_000.0
    assert r["errores"] == [] and r["ignoradas"] == 1   # la fila "Total"


def test_csv_en_ingles_con_monto_firmado_y_miles_con_coma():
    csv = ('Date,Description,Amount,Balance\n'
           '2026-10-01,Netflix,"-45,000.00","1,000,000.00"\n'
           '2026-10-02,Salary,"2,500,000.00","3,455,000.00"\n').encode()
    r = analizar("x.csv", csv)
    assert [(m["tipo"], m["monto"]) for m in r["movimientos"]] == [("expense", 45000.0), ("income", 2_500_000.0)]
    assert r["opciones"]["separador_decimal"] == "punto"


def test_columna_tipo_d_c_y_monto_sin_signo():
    csv = "Fecha,Detalle,Valor,Naturaleza\n01/10/2026,Mercado,50.000,D\n02/10/2026,Nómina,1.000.000,C\n".encode()
    r = analizar("x.csv", csv)
    assert [(m["tipo"], m["monto"]) for m in r["movimientos"]] == [("expense", 50000.0), ("income", 1_000_000.0)]


def test_tarjeta_de_credito_con_compras_positivas_se_invierte():
    csv = "Fecha,Descripcion,Valor\n01/10/2026,Restaurante,80.000\n02/10/2026,Pago recibido,-80.000\n".encode()
    normal = analizar("x.csv", csv)["movimientos"]
    assert [m["tipo"] for m in normal] == ["income", "expense"]  # por defecto: positivo = ingreso
    invertido = analizar("x.csv", csv, opciones={"invertir_signo": True})["movimientos"]
    assert [m["tipo"] for m in invertido] == ["expense", "income"]


def test_mapeo_manual_reemplaza_la_deteccion_y_fecha_mdy():
    csv = "a,b,c\n03/20/2026,Cafe,-4.500\n".encode()
    r = analizar("x.csv", csv, mapeo={"fecha": 0, "descripcion": 1, "monto": 2, "debito": None,
                                       "credito": None, "saldo": None, "tipo": None},
                 opciones={"orden_fecha": "mdy"}, fila_encabezado=0)
    assert r["movimientos"][0]["fecha"] == "2026-03-20" and r["movimientos"][0]["monto"] == 4500.0


def test_filas_malas_se_reportan_sin_tumbar_el_archivo():
    csv = "Fecha,Descripcion,Valor\n01/10/2026,Bien,1.000\nxx/yy/zz,Mal fecha,2.000\n03/10/2026,Mal monto,abc\n".encode()
    r = analizar("x.csv", csv)
    assert len(r["movimientos"]) == 1
    assert {e["motivo"] for e in r["errores"]} == {"Fecha no reconocida", "Monto no reconocido"}


def test_excel_xlsx_con_fechas_y_numeros_nativos():
    wb = Workbook()
    ws = wb.active
    ws.append(["Fecha", "Concepto", "Valor"])
    ws.append([datetime(2026, 10, 1), "Arriendo", -1_200_000])
    ws.append([datetime(2026, 10, 2), "Venta", 350_000.5])
    buf = io.BytesIO()
    wb.save(buf)
    r = analizar("mis_gastos.xlsx", buf.getvalue())
    assert [(m["fecha"], m["tipo"], m["monto"]) for m in r["movimientos"]] == [
        ("2026-10-01", "expense", 1_200_000.0), ("2026-10-02", "income", 350_000.5)]
    assert r["hojas"] == ["Sheet"]


def test_sin_encabezado_se_infiere_por_contenido():
    csv = "01/10/2026,Cafe Juan Valdez,-8.500\n02/10/2026,Nomina,3.000.000\n".encode()
    r = analizar("x.csv", csv)
    assert r["fila_encabezado"] is None
    assert r["mapeo"]["fecha"] == 0 and r["mapeo"]["monto"] == 2 and r["mapeo"]["descripcion"] == 1
    assert len(r["movimientos"]) == 2


def test_limites_y_formatos_no_soportados():
    with pytest.raises(ErrorArchivo):
        analizar("x.csv", b"")
    with pytest.raises(ErrorArchivo, match="5 MB"):
        analizar("x.csv", b"a" * (5 * 1024 * 1024 + 1))
    with pytest.raises(ErrorArchivo, match="no soportado"):
        analizar("x.pdf", b"%PDF-1.4 hola")
    filas = "Fecha,Descripcion,Valor\n" + "".join(f"01/10/2026,Compra {i},1.000\n" for i in range(3005))
    r = analizar("x.csv", filas.encode())
    assert len(r["movimientos"]) == 3000 and r["truncado"] is True


# ── API: vista previa + confirmar ──────────────────────

def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _preparar(uid):
    como(uid)
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 0}).json()["id"]
    # Ya registrado a mano: coincide EXACTO con la primera fila del archivo
    client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": "expense", "monto": 45000.5,
                                       "descripcion": "COMPRA EXITO 123", "categoria": "Comida",
                                       "fecha": "2026-10-01T00:00:00"})
    # Mismo monto que el pago de tarjeta del archivo, un día antes y otra descripción: APROXIMADO
    client.post("/movimientos", json={"cuenta_id": cuenta, "tipo": "expense", "monto": 300000,
                                       "descripcion": "Mercado grande", "categoria": "Comida",
                                       "fecha": "2026-10-02T00:00:00"})
    return cuenta


def _previa(cuenta, **extra):
    return client.post("/importar/vista-previa", json={
        "cuenta_id": cuenta, "nombre_archivo": "extracto.csv", "archivo_base64": _b64(CSV_BANCO), **extra})


def test_vista_previa_marca_duplicados_y_sugiere_categoria_sin_guardar_nada():
    cuenta = _preparar("imp-prev")
    r = _previa(cuenta)
    assert r.status_code == 200, r.text
    j = r.json()
    estados = {p["descripcion"]: p["estado"] for p in j["propuesta"]}
    assert estados == {"COMPRA EXITO 123": "duplicado", "ABONO NOMINA": "nuevo", "PAGO TARJETA CREDITO": "posible_duplicado"}
    assert j["resumen"] == {"nuevos": 1, "duplicados": 1, "posibles_duplicados": 1, "con_error": 0}
    cat = {p["descripcion"]: p["categoria"] for p in j["propuesta"]}
    assert cat["PAGO TARJETA CREDITO"] == "Pago de tarjeta"   # no se cuenta como gasto
    # nada se guardó: siguen solo los 2 movimientos de antes
    assert len(client.get("/movimientos").json()) == 2


def test_vista_previa_acepta_mapeo_editado():
    cuenta = _preparar("imp-mapeo")
    # El usuario dice que "Débito" (col. 2) es en realidad el monto firmado y no usa crédito
    j = _previa(cuenta, mapeo={"fecha": 0, "descripcion": 1, "monto": 2, "debito": None, "credito": None,
                               "saldo": None, "tipo": None}, fila_encabezado=2).json()
    # solo hay valor en 2 de las 3 filas (la de nómina está en "Crédito", que ahora se ignora)
    assert [p["tipo"] for p in j["propuesta"]] == ["income", "income"]   # positivos, sin invertir
    assert j["resumen"]["con_error"] == 1
    j2 = _previa(cuenta, mapeo={"fecha": 0, "descripcion": 1, "monto": 2, "debito": None, "credito": None,
                                "saldo": None, "tipo": None}, fila_encabezado=2, invertir_signo=True).json()
    assert [p["tipo"] for p in j2["propuesta"]] == ["expense", "expense"]


def test_confirmar_importa_ajusta_saldo_y_es_idempotente():
    cuenta = _preparar("imp-conf")
    filas = [{"fecha": p["fecha"], "descripcion": p["descripcion"], "monto": p["monto"], "tipo": p["tipo"],
              "categoria": p["categoria"]} for p in _previa(cuenta).json()["propuesta"]]
    r = client.post("/importar/confirmar", json={"cuenta_id": cuenta, "nombre_archivo": "extracto.csv", "filas": filas})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["importados"] == 2 and j["duplicados_omitidos"] == 1     # el exacto no se vuelve a crear
    # saldo: -45.000,5 (manual) -300.000 (manual) +2.500.000 -300.000 (importados) = 1.854.999,5
    assert j["saldo"] == pytest.approx(-45000.5 - 300000 + 2_500_000 - 300_000)
    # importar el MISMO archivo otra vez no duplica nada
    again = client.post("/importar/confirmar", json={"cuenta_id": cuenta, "nombre_archivo": "extracto.csv", "filas": filas}).json()
    assert again["importados"] == 0 and again["duplicados_omitidos"] == 3
    assert again["saldo"] == pytest.approx(j["saldo"])
    movs = client.get("/movimientos").json()
    assert len(movs) == 4
    pago = [m for m in movs if m["descripcion"] == "PAGO TARJETA CREDITO"][0]
    assert pago["categoria"] == "Pago de tarjeta" and pago["fuente"] == "importacion_archivo"


def test_confirmar_sin_ajustar_saldo_y_validaciones():
    como("imp-val")
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 100}).json()["id"]
    fila = {"fecha": "2026-10-01", "descripcion": "Cafe", "monto": 5000, "tipo": "expense"}
    j = client.post("/importar/confirmar", json={"cuenta_id": cuenta, "filas": [fila], "ajustar_saldo": False}).json()
    assert j["importados"] == 1 and j["saldo"] == 100 and j["saldo_ajustado"] is False
    malas = [{**fila, "monto": -5}, {**fila, "tipo": "transfer"}, {**fila, "fecha": "01/10/2026"}]
    for mala in malas:
        assert client.post("/importar/confirmar", json={"cuenta_id": cuenta, "filas": [mala]}).status_code == 422
    assert client.post("/importar/confirmar", json={"cuenta_id": cuenta, "filas": []}).status_code == 422


def test_importado_sin_ajustar_saldo_no_mueve_saldo_al_editar_ni_borrar():
    """Regresión: saldo 100.000; se importan 2 filas (5.000 y 7.000) sin ajustar; borrar una
    o editar el monto de la otra no cambia el saldo (antes lo desfasaba)."""
    como("imp-sinsaldo")
    cuenta = client.post("/cuentas", json={"nombre": "Banco", "saldo": 100_000}).json()["id"]
    filas = [{"fecha": "2026-10-01", "descripcion": "Cafe", "monto": 5_000, "tipo": "expense"},
             {"fecha": "2026-10-02", "descripcion": "Libro", "monto": 7_000, "tipo": "expense"}]
    j = client.post("/importar/confirmar", json={"cuenta_id": cuenta, "filas": filas, "ajustar_saldo": False}).json()
    assert j["importados"] == 2 and j["saldo"] == 100_000

    def saldo():
        return [c for c in client.get("/cuentas").json() if c["id"] == cuenta][0]["saldo"]

    movs = {m["descripcion"]: m for m in client.get("/movimientos").json() if m["cuenta_id"] == cuenta}
    assert movs["Cafe"]["fuente"] == "importado_sin_saldo"
    assert client.delete(f"/movimientos/{movs['Cafe']['id']}").status_code == 200
    assert saldo() == 100_000
    assert client.put(f"/movimientos/{movs['Libro']['id']}", json={"monto": 9_000}).status_code == 200
    assert saldo() == 100_000
    # Con ajuste (caso normal) borrar SÍ devuelve el dinero: 100.000 -> importa 5.000 -> 95.000 -> borra -> 100.000
    j2 = client.post("/importar/confirmar", json={"cuenta_id": cuenta, "ajustar_saldo": True, "filas": [
        {"fecha": "2026-10-03", "descripcion": "Taxi", "monto": 5_000, "tipo": "expense"}]}).json()
    assert j2["saldo"] == 95_000
    taxi = [m for m in client.get("/movimientos").json() if m["descripcion"] == "Taxi"][0]
    client.delete(f"/movimientos/{taxi['id']}")
    assert saldo() == 100_000


def test_errores_de_archivo_y_cuenta_ajena():
    cuenta = _preparar("imp-err")
    base = {"cuenta_id": cuenta, "nombre_archivo": "x.pdf", "archivo_base64": _b64(b"%PDF-1.4")}
    r = client.post("/importar/vista-previa", json=base)
    assert r.status_code == 422 and "Formato no soportado" in r.json()["detail"]
    enorme = {**base, "nombre_archivo": "x.csv", "archivo_base64": "A" * (8 * 1024 * 1024)}
    assert client.post("/importar/vista-previa", json=enorme).status_code == 413
    como("imp-otro")
    assert _previa(cuenta).status_code == 404
    assert client.post("/importar/confirmar", json={"cuenta_id": cuenta, "filas": [
        {"fecha": "2026-10-01", "descripcion": "x", "monto": 1, "tipo": "expense"}]}).status_code == 404


def test_vista_previa_avisa_si_el_mes_de_la_cuenta_ya_esta_conciliado_sin_bloquear():
    from app.database import SessionLocal
    from app.models import Movimiento

    cuenta = _preparar("imp-ya-conc")
    assert _previa(cuenta).json()["ya_conciliado"] is None
    # El mes (octubre 2026) se concilió antes: un movimiento de esa cuenta quedó cruzado con el extracto.
    db = SessionLocal()
    try:
        m = db.query(Movimiento).filter(Movimiento.cuenta_id == cuenta).first()
        m.conciliado_en = datetime(2026, 10, 5)
        db.commit()
    finally:
        db.close()
    j = _previa(cuenta).json()
    assert j["ya_conciliado"] == {"mes": "2026-10", "cruzados": 1}
    # Solo avisa: la vista previa sigue completa y los duplicados se siguen detectando por huella.
    assert j["resumen"]["duplicados"] == 1 and len(j["propuesta"]) == 3


def test_posible_duplicado_trae_la_fila_registrada_y_confirmar_la_junta_sin_crear_otra():
    """«¿Es el mismo gasto?»: la vista previa muestra las dos filas y «Sí, es el mismo» confirma el que ya
    tenías (canal archivo) en vez de crear otro."""
    cuenta = _preparar("imp-mismo")
    j = _previa(cuenta).json()
    dudosa = next(p for p in j["propuesta"] if p["estado"] == "posible_duplicado")
    assert dudosa["registrado"]["descripcion"] == "Mercado grande" and dudosa["match_id"]
    antes = len(client.get("/movimientos").json())
    r = client.post("/importar/confirmar", json={"cuenta_id": cuenta, "nombre_archivo": "extracto.csv", "filas": [{
        "fecha": dudosa["fecha"], "descripcion": dudosa["descripcion"], "monto": dudosa["monto"], "tipo": dudosa["tipo"],
        "conciliar_con": dudosa["match_id"]}]}).json()
    assert r["importados"] == 0 and r["juntados"] == 1
    assert len(client.get("/movimientos").json()) == antes
    mov = client.get(f"/movimientos/{dudosa['match_id']}").json()
    assert "importacion" in mov["canales"]
