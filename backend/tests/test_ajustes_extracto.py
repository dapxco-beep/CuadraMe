"""4x1000 y costos por retiro que el resumen del extracto de una cuenta de ahorros trae pero no lista (con los rendimientos).
Texto y números 100 % inventados.

Agosto:    2.000.000 + entró 1.500.000 - salió 1.000.000 - 4x1000 4.000 - costos 6.500 + rendimientos 9.000 = 2.498.500.
Septiembre: 2.498.500 + entró 300.000 - salió 100.000 - 4x1000 400 + rendimientos 8.000 = 2.706.100 (sin costos por retiro).
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'ajustes_extracto.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cuadre_encadenado as ce  # noqa: E402
from app import cuadre_extracto as cx  # noqa: E402
from app import limites  # noqa: E402
from app import releer_extracto as rx  # noqa: E402
from app import rendimientos_extracto as rend  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.conciliacion import parse_texto_con_regex  # noqa: E402
from app.contabilidad import tipos_efectivos  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, ExtractoCorreo, HistorialExtracto, Movimiento, Perfil  # noqa: E402
from app.routers import conciliacion as mod  # noqa: E402
from app.routers import correos as router_correos  # noqa: E402

client = TestClient(app)
USUARIO = {"u": UsuarioActual(id="ae-0", email="a@test.com", nombre="Persona Prueba")}


def _texto(periodo, ini, entro, salio, gmf, retiro, rendim, final, lineas):
    filas_extra = (f"Impuesto del 4x1000 {gmf}\n" if gmf else "") + (f"Costos por retiro {retiro}\n" if retiro else "")
    return f"""Nu Colombia
Número de Cuenta 1234567890
Período {periodo}
Resumen de tus movimientos
Tu dinero al inicio del mes {ini}
Lo que entró a tu cuenta +{entro}
Lo que salió de tu cuenta -{salio}
{filas_extra}Rendimiento total de tu cuenta +{rendim}
Tu dinero a final del mes {final}
{lineas}
"""


AGO = _texto("01 - 31 AGO 2026", "$2.000.000,00", "$1.500.000,00", "$1.000.000,00", "$4.000,00", "$6.500,00", "$9.000,00", "$2.498.500,00",
             "05 ago Sueldo Empresa Inventada +$1.500.000,00\n10 ago Compra Tienda Uno -$600.000,00\n15 ago Compra Tienda Dos -$400.000,00")
SEP = _texto("01 - 30 SEP 2026", "$2.498.500,00", "$300.000,00", "$100.000,00", "$400,00", None, "$8.000,00", "$2.706.100,00",
             "03 sep Pago Cliente Inventado +$300.000,00\n12 sep Compra Tienda Tres -$100.000,00")
SOLO_RENDIMIENTO = _texto("01 - 30 SEP 2026", "$1.000.000,00", "$500.000,00", "$200.000,00", None, None, "$9.000,00", "$1.309.000,00",
                          "05 sep Sueldo Empresa Inventada +$500.000,00\n10 sep Compra Tienda Uno -$120.000,00\n15 sep Compra Tienda Dos -$80.000,00")
SIN_NADA = _texto("01 - 30 SEP 2026", "$1.000.000,00", "$500.000,00", "$200.000,00", None, None, "$0,00", "$1.300.000,00",
                  "05 sep Sueldo Empresa Inventada +$500.000,00\n10 sep Compra Tienda Uno -$120.000,00\n15 sep Compra Tienda Dos -$80.000,00")
AGO_MAL = AGO.replace("Impuesto del 4x1000 $4.000,00", "Impuesto del 4x1000 $5.000,00")  # el resumen ya no suma


@pytest.fixture(autouse=True)
def _ambiente():
    app.dependency_overrides[get_current_user] = lambda: USUARIO["u"]
    limites._eventos.clear()
    yield
    app.dependency_overrides.pop(get_current_user, None)


def como(uid):
    USUARIO["u"] = UsuarioActual(id=uid, email=f"{uid}@test.com", nombre="Persona Prueba")


# ── 1. El lector ──────────────────────────────────────────────────────────────────────────
def test_el_resumen_trae_4x1000_y_costos_por_retiro():
    s = cx.leer_saldos_extracto(AGO)
    assert s["impuesto_4x1000"] == 4000.0 and s["costos_retiro"] == 6500.0 and s["rendimiento"] == 9000.0
    assert s["resumen_cuadra"] is True  # inicio + entró - salió - 4x1000 - costos + rendimiento = final
    assert "impuesto_4x1000" not in cx.leer_saldos_extracto(SOLO_RENDIMIENTO)
    # con signo y coma decimal tambien se lee
    con_signo = AGO.replace("Impuesto del 4x1000 $4.000,00", "Impuesto del 4x1000 -$4.000,00")
    assert cx.leer_saldos_extracto(con_signo)["impuesto_4x1000"] == 4000.0


def test_agrega_una_linea_por_concepto_con_su_categoria_y_la_verificacion_cuadra():
    movs, _ = parse_texto_con_regex(AGO)
    assert len(movs) == 3
    todas, lectura = rend.con_rendimiento(movs, AGO)
    assert len(todas) == 6
    por = {rend.concepto_de_linea(l): l for l in todas[3:]}
    assert por["rendimientos"]["tipo"] == "income" and por["rendimientos"]["categoria_fija"] == "Rendimientos"
    g = por["impuesto_4x1000"]
    assert (g["fecha"], g["descripcion"], g["monto"], g["tipo"], g["categoria_fija"]) == (
        "2026-08-31", "Impuesto 4x1000 (GMF) · agosto de 2026", 4000.0, "expense", "4x1000 (GMF)")
    r = por["costos_retiro"]
    assert (r["descripcion"], r["monto"], r["tipo"], r["categoria_fija"]) == (
        "Costos por retiro · agosto de 2026", 6500.0, "expense", "Comisiones y seguros")
    assert lectura["lectura_completa"] is True and lectura["lineas_leidas"] == 6
    assert lectura["mensaje_lectura"] == ("Leí 6 líneas, incluidos tus rendimientos de $9.000, el 4x1000 de $4.000 y tus costos por "
                                          "retiro de $6.500, y suman lo que dice tu extracto ✓")
    assert cx.cadena_coincide(cx.leer_saldos_extracto(AGO), todas) is True
    # estable: leer dos veces da las mismas líneas (misma huella) y no toca la lista original
    assert len(movs) == 3 and rend.con_rendimiento(movs, AGO)[0][3:] == todas[3:]


def test_mensaje_con_rendimientos_y_4x1000():
    movs, _ = parse_texto_con_regex(SEP)
    todas, lectura = rend.con_rendimiento(movs, SEP)
    assert len(todas) == 4
    assert lectura["mensaje_lectura"] == "Leí 4 líneas, incluidos tus rendimientos de $8.000 y el 4x1000 de $400, y suman lo que dice tu extracto ✓"


def test_sin_esos_conceptos_no_se_inventa_nada():
    movs, _ = parse_texto_con_regex(SIN_NADA)
    assert rend.con_rendimiento(movs, SIN_NADA) == (movs, None)
    movs, _ = parse_texto_con_regex(SOLO_RENDIMIENTO)
    todas, _ = rend.con_rendimiento(movs, SOLO_RENDIMIENTO)
    assert [rend.concepto_de_linea(l) for l in todas[3:]] == ["rendimientos"]


def test_un_resumen_que_no_cuadra_deja_todo_apagado_con_aviso():
    movs, _ = parse_texto_con_regex(AGO_MAL)
    todas, lectura = rend.con_rendimiento(movs, AGO_MAL)
    assert all(l["marcar_por_defecto"] is False and l["aviso_linea"] for l in todas[3:])
    assert lectura["lectura_completa"] is False and "Revisa antes de importar" in lectura["mensaje_lectura"]


def test_si_el_extracto_ya_lista_el_4x1000_no_se_agrega_otra_linea():
    movs, _ = parse_texto_con_regex(AGO)
    movs = [*movs, {"fecha": "2026-08-20", "descripcion": "Gravamen 4x1000", "monto": 4000.0, "tipo": "expense", "referencia": "", "saldo": None}]
    todas, _ = rend.con_rendimiento(movs, AGO)
    assert [rend.concepto_de_linea(l) for l in todas[4:]] == ["rendimientos", "costos_retiro"]


def test_una_tarjeta_de_credito_no_agrega_nada():
    movs, _ = parse_texto_con_regex(AGO)
    assert rend.con_rendimiento(movs, AGO, es_credito=True) == (movs, None)
