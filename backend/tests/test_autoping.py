"""El auto-ping mantiene despierto el servidor gratis; apagado si no hay URL, y un fallo de red no lo rompe."""
import os
import threading

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_autoping.db")

from app import autoping  # noqa: E402


def test_sin_url_no_arranca_nada():
    assert autoping.iniciar("") is None
    assert autoping.iniciar("no-es-una-url") is None


def test_con_url_arranca_un_hilo_daemon_que_llama_a_la_direccion():
    llamadas = []
    original = autoping._llamar
    autoping._llamar = lambda u: llamadas.append(u) or True
    try:
        hilo = autoping.iniciar("https://ejemplo.test/health", intervalo=0.05)
        assert isinstance(hilo, threading.Thread) and hilo.daemon
        hilo.join(0.4)
        assert llamadas and all(u == "https://ejemplo.test/health" for u in llamadas)
    finally:
        autoping._llamar = original


def test_un_fallo_de_red_devuelve_false_y_no_lanza():
    assert autoping._llamar("http://127.0.0.1:9/health") is False
