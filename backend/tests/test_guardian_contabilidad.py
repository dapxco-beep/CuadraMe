"""
PRUEBA GUARDIÁN de la regla única de ingresos/gastos.

Falla si aparece, fuera de app/contabilidad.py, una comparación directa del tipo GUARDADO de un
movimiento (`Movimiento.tipo == "expense"`, `m.tipo == "income"`, `.tipo.in_(("income", ...))`).
Sumar ingresos o gastos con el tipo guardado cuenta dos veces los traslados entre cuentas propias,
los pagos de tarjeta y los ajustes de saldo. Quien necesite ingresos/gastos debe usar
`contabilidad.tipos_efectivos / clasificar` (o `informe_datos.cargar_movs_efectivos`).

No se miran los diccionarios ya «efectivos» (`m["tipo"] == "expense"`): esos vienen de clasificar().
La lista blanca es POR ARCHIVO con la razón; agregar una entrada exige justificarla aquí.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

# archivo -> por qué puede mirar el tipo guardado (dirección del movimiento, no «es gasto real»)
LISTA_BLANCA = {
    "contabilidad.py": "es la regla única",
    "duplicados.py": "deduplicación entre canales: compara la dirección guardada de dos filas, no suma",
    "cuadre_extracto.py": "saldo del libro contable de una cuenta (todo movimiento mueve saldo, también los traslados)",
    "tarjetas.py": "saldo y estado de la tarjeta: cada movimiento mueve la deuda según su dirección",
    "routers/importar.py": "neto de un extracto para cuadrar saldo (dirección de cada línea)",
    "importador_tabular.py": "lectura de archivos: asigna la dirección de cada línea",
    "gmail_extract.py": "lectura de correos: asigna la dirección",
    "routers/conciliacion.py": "ajusta el saldo de la cuenta según la dirección del movimiento",
    "routers/movimientos.py": "CRUD de movimientos: saldo, avisos de duplicado y filtro de listado por dirección",
    "routers/correos.py": "aprobación de correos: dirección del movimiento que se crea",
    "routers/recurrentes.py": "pagos fijos (recurrentes), no son movimientos reales",
    "routers/presupuestos.py": "pagos fijos (recurrentes)",
    "routers/planificacion.py": "pagos fijos (recurrentes)",
    "costos_bancarios.py": "pagos que ENTRAN a la tarjeta de crédito: son el pago de la tarjeta, no un ingreso",
    "rendimientos.py": "rendimientos: se identifican por su categoría de sistema, no por traslado",
    "ingresos_sueltos.py": "empareja la DIRECCION guardada de un ingreso falso con su compra buena (dedupe y saldo), no suma gastos ni ingresos",
    "corregir_tipo.py": "corrige la DIRECCION guardada de una compra que se importó como ingreso (saldo), no suma gastos ni ingresos",
    "consejos.py": "abono a tarjeta ya clasificado como neutral por tipos_efectivos; solo recuerda el último pago",
    "metas_plan.py": "recurrentes/metas (usa cargar_movs_efectivos para los movimientos)",
}

PATRON = re.compile(
    r"""(?:Movimiento\.tipo\s*(?:==|!=)\s*["'](?:expense|income)["']"""
    r"""|Movimiento\.tipo\.in_\(\s*[\(\[]?\s*["'](?:expense|income)["']"""
    r"""|\b(?:m|mov|movimiento|x|f|p)\.tipo\s*(?:==|!=)\s*["'](?:expense|income)["'])"""
)


def _archivos():
    for p in sorted(APP.rglob("*.py")):
        yield p.relative_to(APP).as_posix(), p


def test_nadie_suma_gastos_o_ingresos_con_el_tipo_guardado():
    infractores = []
    for rel, p in _archivos():
        if rel in LISTA_BLANCA:
            continue
        for n, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if linea.lstrip().startswith("#"):
                continue
            if PATRON.search(linea):
                infractores.append(f"{rel}:{n}: {linea.strip()}")
    assert not infractores, (
        "Comparación directa del tipo guardado fuera de contabilidad.py. Usa contabilidad.tipos_efectivos/clasificar "
        "(o cargar_movs_efectivos). Si de verdad es la dirección del movimiento (saldo, dedupe), agrégalo a "
        "LISTA_BLANCA con su razón:\n" + "\n".join(infractores)
    )


def test_la_lista_blanca_no_tiene_archivos_inexistentes():
    existentes = {rel for rel, _ in _archivos()}
    assert not [k for k in LISTA_BLANCA if k not in existentes]


def test_el_guardian_detecta_la_infraccion():
    assert PATRON.search('total = db.query(func.sum(Movimiento.monto)).filter(Movimiento.tipo == "expense")')
    assert PATRON.search("if m.tipo == 'income':")
    assert not PATRON.search('if m["tipo"] == "income":')  # dict efectivo: permitido
