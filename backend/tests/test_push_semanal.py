"""Recordatorio semanal por push: texto (comparación, categoría top, sin montos), reglas
(punto de partida, solo con movimientos, opt-out) e idempotencia por usuario y semana."""
import os
import tempfile
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'push_semanal.db')}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import resumen_semanal as rs  # noqa: E402
from app.auth import UsuarioActual, get_current_user  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Cuenta, Movimiento, PushSubscription  # noqa: E402
from app.models_fiscal import AjusteUsuario  # noqa: E402
from app.routers import push as push_router  # noqa: E402

client = TestClient(app)
CABECERA = {"X-Cron-Secret": "secreto-de-prueba"}
DOMINGO = datetime(2026, 9, 6, 17, 0)  # semana ISO 36


@pytest.fixture
def pushes(monkeypatch):
    enviados = []

    def _enviar(db, usuario_id, titulo, cuerpo, url="/", boton=None):
        enviados.append({"uid": usuario_id, "titulo": titulo, "cuerpo": cuerpo, "url": url, "boton": boton})
        return 1

    monkeypatch.setattr(push_router, "enviar_push", _enviar)
    monkeypatch.setattr(push_router, "ahora_co", lambda: DOMINGO)
    return enviados


def _sembrar(uid, gastos: list[tuple[str, float, int]], con_push=True, ajustes: dict | None = None):
    """gastos: (categoría, monto, días atrás)."""
    db = SessionLocal()
    try:
        cuenta = Cuenta(usuario_id=uid, nombre="Banco", saldo=1000, moneda="COP")
        db.add(cuenta)
        db.flush()
        if con_push:
            db.add(PushSubscription(usuario_id=uid, endpoint=f"https://push.test/{uid}", p256dh="x", auth="y"))
        for cat, monto, dias in gastos:
            db.add(Movimiento(usuario_id=uid, cuenta_id=cuenta.id, descripcion=f"{cat} compra", categoria=cat,
                              tipo="expense", monto=monto, fecha=DOMINGO - timedelta(days=dias)))
        if ajustes:
            db.add(AjusteUsuario(usuario_id=uid, **ajustes))
        db.commit()
    finally:
        db.close()


def _correr():
    return client.post("/push/cron/resumen-semanal", headers=CABECERA).json()


def _de(pushes, uid):
    return [p for p in pushes if p["uid"] == uid]


def test_texto_compara_con_la_semana_anterior_y_nombra_la_categoria(pushes):
    # Esta semana: 88.000 (Comida 60.000, Transporte 28.000). La anterior: 100.000 -> 12 % menos.
    _sembrar("ps-texto", [("Comida", 60_000, 1), ("Transporte", 28_000, 2), ("Comida", 100_000, 9)])
    r = _correr()
    assert r["ok"] and r["enviados"] >= 1
    p = _de(pushes, "ps-texto")[0]
    assert p["cuerpo"] == "Esta semana gastaste $88.000, 12 % menos que la anterior. Lo que más pesó: Comida."
    assert p["url"] == "/informe" and p["boton"] == "Ver mis informes"


def test_mensaje_sube_sin_culpar_y_sin_montos_si_oculta():
    t, c = rs.mensaje_push({"gastos": 120_000, "anterior": 100_000, "top": "Mercado"})
    assert "$120.000" in c and "20 % más que la anterior" in c and "Mercado" in c
    assert "mal" not in c.lower() and "culpa" not in c.lower() and "demasiado" not in c.lower()
    t, c = rs.mensaje_push({"gastos": 120_000, "anterior": 100_000, "top": "Mercado"}, ocultar_montos=True)
    assert "$" not in c and "120" not in c.replace("20 %", "") and "Mercado" in c
    assert rs.mensaje_push({"gastos": 100_000, "anterior": 99_000, "top": "X"})[1].count("casi igual") == 1
    assert "Esta semana gastaste $5.000." in rs.mensaje_push({"gastos": 5_000, "anterior": None, "top": None})[1]
    assert "no registraste gastos" in rs.mensaje_push({"gastos": 0, "anterior": 10, "top": None})[1]


def test_ocultar_saldos_manda_el_push_sin_montos(pushes):
    _sembrar("ps-oculta", [("Comida", 77_000, 1)], ajustes={"ocultar_montos": True})
    _correr()
    cuerpo = _de(pushes, "ps-oculta")[0]["cuerpo"]
    assert "$" not in cuerpo and "77" not in cuerpo and "Comida" in cuerpo


def test_la_preferencia_ocultar_montos_se_guarda_por_api(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id="ps-pref", email="p@t.com", nombre="P")
    try:
        assert client.get("/resumen/preferencias").json()["ocultar_montos"] is False
        assert client.put("/resumen/preferencias", json={"ocultar_montos": True}).json()["ocultar_montos"] is True
        r = client.get("/resumen/preferencias").json()
        assert r["ocultar_montos"] is True and r["correo"] is False  # no pisa la preferencia de correo
        assert client.put("/resumen/preferencias", json={"correo": True}).json()["ocultar_montos"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_sin_semana_anterior_no_compara(pushes):
    _sembrar("ps-sin-ant", [("Comida", 40_000, 1)])
    _correr()
    c = _de(pushes, "ps-sin-ant")[0]["cuerpo"]
    assert c == "Esta semana gastaste $40.000. Lo que más pesó: Comida."


def test_respeta_el_punto_de_partida(pushes):
    # El punto de partida es hace 3 días: lo anterior no cuenta, y la semana anterior no se compara.
    inicio = (DOMINGO - timedelta(days=3)).date()
    _sembrar("ps-pp", [("Comida", 10_000, 1), ("Otros", 500_000, 5), ("Comida", 50_000, 10)],
             ajustes={"punto_partida_modo": "hoy", "punto_partida_fecha": inicio})
    _correr()
    c = _de(pushes, "ps-pp")[0]["cuerpo"]
    assert "$10.000" in c and "menos" not in c and "más que" not in c and "Otros" not in c


def test_solo_con_movimientos_y_solo_con_push(pushes):
    _sembrar("ps-vieja", [("Comida", 9_000, 12)])               # nada en los últimos 7 días
    _sembrar("ps-sinpush", [("Comida", 9_000, 1)], con_push=False)  # opt-out: sin suscripción
    r = _correr()
    assert r["ok"]
    assert _de(pushes, "ps-vieja") == [] and _de(pushes, "ps-sinpush") == []


def test_una_vez_por_semana_y_tolerante_a_fallos(pushes, monkeypatch):
    _sembrar("ps-idem", [("Comida", 9_000, 1)])
    _sembrar("ps-falla", [("Comida", 9_000, 1)])
    original = push_router.enviar_push

    def _con_fallo(db, usuario_id, *a, **k):
        if usuario_id == "ps-falla":
            raise RuntimeError("push caído")
        return original(db, usuario_id, *a, **k)

    monkeypatch.setattr(push_router, "enviar_push", _con_fallo)
    r1 = _correr()
    r2 = _correr()
    assert r1["fallidos"] >= 1 and len(_de(pushes, "ps-idem")) == 1  # el fallo de uno no frena a los demás
    assert len(_de(pushes, "ps-idem")) == 1 and r2["enviados"] == 0   # segunda corrida de la semana: nada
    # El que falló libera su marca y se reintenta en la siguiente corrida.
    monkeypatch.setattr(push_router, "enviar_push", original)
    _correr()
    assert len(_de(pushes, "ps-falla")) == 1
