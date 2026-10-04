"""Regresión: obtener_email debe usar el perfil de Gmail (alcanza con gmail.readonly)
y no oauth2/v2/userinfo, que da 401 sin el scope userinfo.email."""
from app import gmail_oauth


class _Resp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"emailAddress": "persona@gmail.com"}


def test_obtener_email_usa_perfil_de_gmail(monkeypatch):
    visto = {}

    def falso_get(url, headers=None, timeout=None):
        visto["url"] = url
        visto["auth"] = headers["Authorization"]
        return _Resp()

    monkeypatch.setattr(gmail_oauth.httpx, "get", falso_get)
    assert gmail_oauth.obtener_email("tok") == "persona@gmail.com"
    assert "gmail.googleapis.com" in visto["url"] and "userinfo" not in visto["url"]
    assert visto["auth"] == "Bearer tok"
