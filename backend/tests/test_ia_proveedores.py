"""La IA de texto usa Groq primero y OpenRouter de respaldo (ambos gratuitos). Sin red: httpx.post va falso."""
import httpx
import pytest

from app import ia
from app.config import settings


class Resp:
    def __init__(self, estado=200, texto="hola"):
        self.status_code, self._t = estado, texto

    def json(self):
        return {"choices": [{"message": {"content": self._t}}]}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "http://x"), response=self)


class Registro(list):
    pass


@pytest.fixture
def llamadas(monkeypatch):
    registro = Registro()
    monkeypatch.setattr(settings, "groq_api_key", "gsk-falsa")
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-falsa")

    def instalar(*respuestas):
        cola = list(respuestas)

        def falso(url, **kw):
            registro.append((url, kw["json"]))
            return cola.pop(0)
        monkeypatch.setattr(ia.httpx, "post", falso)
    registro.instalar = instalar
    return registro


def test_usa_groq_primero(llamadas):
    llamadas.instalar(Resp(texto=" respuesta "))
    assert ia.completar([{"role": "user", "content": "hola"}], max_tokens=100) == "respuesta"
    assert len(llamadas) == 1 and llamadas[0][0] == ia.GROQ_URL
    assert llamadas[0][1]["model"] == settings.groq_model and llamadas[0][1]["max_tokens"] > 100


def test_si_groq_falla_responde_openrouter(llamadas):
    llamadas.instalar(Resp(429), Resp(texto="del respaldo"))
    assert ia.completar([{"role": "user", "content": "hola"}]) == "del respaldo"
    assert [u for u, _ in llamadas] == [ia.GROQ_URL, ia.OPENROUTER_URL]


def test_respuesta_vacia_cuenta_como_fallo(llamadas):
    llamadas.instalar(Resp(texto=""), Resp(texto="ok"))
    assert ia.completar([{"role": "user", "content": "hola"}]) == "ok"


def test_si_todos_fallan_lanza_el_ultimo_error(llamadas):
    llamadas.instalar(Resp(500), Resp(429))
    with pytest.raises(httpx.HTTPStatusError) as e:
        ia.completar([{"role": "user", "content": "hola"}])
    assert e.value.response.status_code == 429


def test_sin_claves_no_hay_ia(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    assert not ia.hay_ia()
    with pytest.raises(RuntimeError):
        ia.completar([{"role": "user", "content": "hola"}])


def test_solo_openrouter_si_no_hay_clave_de_groq(llamadas, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    llamadas.instalar(Resp(texto="ok"))
    ia.completar([{"role": "user", "content": "hola"}])
    assert llamadas[0][0] == ia.OPENROUTER_URL
