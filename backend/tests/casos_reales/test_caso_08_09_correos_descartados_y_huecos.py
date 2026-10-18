"""CASOS REALES 8 y 9: correos de bancos que «desaparecen».

8. Correo descartado por movimiento borrado + recuperar. El usuario borró un movimiento que ya estaba
   registrado por el atajo y por el correo; el correo se marca «descartado» (para que no resucite el gasto
   al sincronizar de nuevo). Pero si el usuario SÍ quería ese gasto, no había forma de recuperarlo: ahora
   `POST /correos/{id}/recuperar` lo devuelve a «Por revisar» y no se vuelve a esconder.
9. Ventana de correos con huecos. La sincronización pedía solo lo posterior a la última lectura: un correo
   de hace 2 días que Gmail entregó tarde (o que una lectura fallida se saltó) no entraba nunca. La ventana
   solapa 3 días hacia atrás y no duplica lo ya leído; una corrida fallida no avanza la marca.
Gmail simulado y datos inventados.
"""
from datetime import datetime, timedelta

# La escena `e` (4 canales, Gmail simulado) y la ventana con fecha viven en tests existentes; se reutilizan.
from tests.test_duplicados import e  # noqa: F401
from tests.test_extractos_gmail import client, conectar_usuario  # noqa: F401
from tests.test_ventana_movimientos import (  # noqa: F401
    GmailPorFecha, _clave, _correr, _ids, _sync_mov, correo,
)


def test_caso8_correo_descartado_por_borrado_se_puede_recuperar(e):  # noqa: F811
    e.atajo()
    e.llega_correo()
    (m,) = e.movs()
    assert client.delete(f"/movimientos/{m['id']}").status_code == 200
    e.sincronizar()
    assert e.pendientes() == [], "el borrado no debe resucitar el gasto"
    (c,) = e.correos("todos")
    assert c["estado"] == "descartado"

    r = client.post(f"/correos/{c['id']}/recuperar")
    assert r.status_code == 200 and r.json()["estado"] == "pendiente"
    assert len(e.pendientes()) == 1
    e.sincronizar()
    e.sincronizar()
    assert len(e.pendientes()) == 1, "una vez recuperado no se vuelve a esconder"


def test_caso9_correo_de_hace_dos_dias_que_no_entro_se_lee_sin_duplicar(monkeypatch):
    uid = "u-caso9-hueco"
    # Última lectura hace 2 h; el correo es de hace 60 h (2,5 días) y nunca entró.
    g = GmailPorFecha([correo("h1", 60), correo("h2", 5, asunto="Compraste con tu tarjeta Nu")])
    conectar_usuario(uid, g, monkeypatch)
    _sync_mov(uid, datetime.utcnow() - timedelta(hours=2))
    assert _correr()["ok"]
    assert _ids(uid) == {"h1", "h2"}
    assert _correr()["nuevos"] == 0 and _ids(uid) == {"h1", "h2"}


def test_caso9_la_ventana_es_de_3_dias_y_no_mas(monkeypatch):
    uid = "u-caso9-ventana"
    g = GmailPorFecha([correo("v1", 24 * 6)])  # hace 6 días: fuera de la ventana incremental
    conectar_usuario(uid, g, monkeypatch)
    _sync_mov(uid, datetime.utcnow() - timedelta(hours=1))
    _correr()
    assert _ids(uid) == set()
    esperado = (datetime.utcnow() - timedelta(days=3)).strftime("%Y/%m/%d")
    assert any(f"after:{esperado}" in q for q in g.consultas), g.consultas
