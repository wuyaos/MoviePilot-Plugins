import sys
from pathlib import Path

import pytest
import requests

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

from client import PeerGoAuthError, PeerGoClient  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body
        self.ok = 200 <= status_code < 300

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.cookies = requests.cookies.RequestsCookieJar()
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if method == "POST" and url.endswith("/api/v1/session") and response.ok:
            self.cookies.set(
                PeerGoClient.SESSION_COOKIE_NAME,
                "new-session",
                domain="rousi.pro",
                path="/",
            )
        return response


def session_body():
    return {
        "csrf_token": "csrf",
        "expires_at": "2026-09-20T00:00:00Z",
        "user": {"id": "1", "username": "tester", "display_name": "Tester"},
    }


def test_valid_cookie_skips_login():
    fake = FakeSession([FakeResponse(200, session_body())])
    client = PeerGoClient(cookie="__Host-peergo_session=existing", session=fake)
    info, cookie, refreshed = client.ensure_session("user", "password")
    assert info["user"]["username"] == "tester"
    assert cookie == "__Host-peergo_session=existing"
    assert refreshed is False
    assert [call[0] for call in fake.calls] == ["GET"]


def test_invalid_cookie_uses_password_login_and_returns_new_cookie():
    fake = FakeSession([
        FakeResponse(204),
        FakeResponse(200, session_body()),
    ])
    client = PeerGoClient(cookie="__Host-peergo_session=expired", session=fake)
    info, cookie, refreshed = client.ensure_session("tester", "secret")
    assert info["csrf_token"] == "csrf"
    assert cookie == "__Host-peergo_session=new-session"
    assert refreshed is True
    method, url, kwargs = fake.calls[1]
    assert method == "POST" and url.endswith("/api/v1/session")
    assert kwargs["json"] == {
        "identifier": "tester",
        "password": "secret",
        "remember_me": True,
    }
    assert kwargs["headers"] == {
        "Origin": "https://rousi.pro",
        "Referer": "https://rousi.pro/login",
    }
    assert "Cookie" not in fake.headers


def test_invalid_cookie_without_complete_credentials_fails():
    fake = FakeSession([FakeResponse(204)])
    client = PeerGoClient(cookie="__Host-peergo_session=expired", session=fake)
    with pytest.raises(PeerGoAuthError, match="账号密码"):
        client.ensure_session("tester", "")


def test_login_failure_has_actionable_message():
    fake = FakeSession([
        FakeResponse(204),
        FakeResponse(401, {"detail": "invalid credentials"}),
    ])
    client = PeerGoClient(session=fake)
    with pytest.raises(PeerGoAuthError, match="invalid credentials"):
        client.ensure_session("tester", "wrong")


def test_attendance_post_has_csrf_and_idempotency_key():
    fake = FakeSession([FakeResponse(200, {"claimed_today": True})])
    client = PeerGoClient(session=fake)
    body = client.claim_attendance("csrf-token", mode="fixed")
    assert body["claimed_today"] is True
    method, url, kwargs = fake.calls[0]
    assert method == "POST" and url.endswith("/api/v1/me/attendance")
    assert kwargs["json"] == {"mode": "fixed"}
    assert kwargs["headers"]["Origin"] == "https://rousi.pro"
    assert kwargs["headers"]["Referer"] == "https://rousi.pro/account/economy"
    assert kwargs["headers"]["X-CSRF-Token"] == "csrf-token"
    assert kwargs["headers"]["Idempotency-Key"]


def test_cookie_normalization_keeps_only_session_cookie():
    raw = "theme=dark; __Host-peergo_session=abc123; lang=zh"
    assert PeerGoClient.normalize_cookie(raw) == "__Host-peergo_session=abc123"
    assert PeerGoClient.normalize_cookie("Cookie: __Host-peergo_session=abc") == "__Host-peergo_session=abc"
