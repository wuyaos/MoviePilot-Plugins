"""client.py 协议解析离线测试（全部 mock，不触真实站点）。"""
import json

import pytest

from jying_under_test.client import (ApiResult, JyingClient, LoginResult,
                                     _extract_message, _extract_token,
                                     _extract_user_id)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text_body=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text_body

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.mark.parametrize("payload,expected", [
    ({"status": "success", "data": {"token": "abc"}}, "abc"),
    ({"token": "abc"}, "abc"),
    ({"data": {"token": {"value": "abc"}}}, "abc"),
    ({"data": {"access_token": "abc"}}, "abc"),
    ({}, ""),
    ("not-dict", ""),
])
def test_extract_token(payload, expected):
    assert _extract_token(payload) == expected


@pytest.mark.parametrize("payload,expected", [
    ({"data": {"user_id": 42}}, 42),
    ({"user": {"id": "u9"}}, "u9"),
    ({"data": {"user": {"uid": 7}}}, 7),
    ({"checked_today": True}, None),  # 数值字段不被误取：checked_today 是 bool，跳过
])
def test_extract_user_id(payload, expected):
    assert _extract_user_id(payload) == expected


def test_parse_success_envelope():
    result = JyingClient()._parse(FakeResponse(200, {"status": "success", "checked_today": False, "message": "ok"}))
    assert result.ok and result.status == "success" and result.data["checked_today"] is False


def test_parse_401_marks_auth_expired():
    result = JyingClient()._parse(FakeResponse(401, {"message": "token 已过期"}))
    assert not result.ok and result.auth_expired and result.message == "token 已过期"
    assert result.http_status == 401


def test_parse_non_json_is_error_not_auth():
    result = JyingClient()._parse(FakeResponse(502, None, text_body="bad gateway"))
    assert not result.ok and not result.auth_expired and "non-json" in result.error


def test_parse_non_object_envelope():
    result = JyingClient()._parse(FakeResponse(200, [1, 2]))
    assert not result.ok and result.error == "non-object envelope"


def test_login_ok():
    client = JyingClient()

    class FakeSession:
        def post(self, url, json=None, timeout=None):
            assert json == {"username": "u", "password": "p"}
            return FakeResponse(200, {"status": "success", "data": {"token": "T123", "user_id": 5}})

    client._session = FakeSession()
    result = client.login("u", "p")
    assert result.ok and result.token == "T123" and result.user_id == 5
    assert result.expires_at > 0


def test_login_missing_credentials():
    assert not JyingClient().login("", "").ok
    assert JyingClient().login("", "").message == "缺少账号或密码"


def test_login_bad_password_keeps_site_message():
    client = JyingClient()

    class FakeSession:
        def post(self, url, json=None, timeout=None):
            return FakeResponse(400, {"status": "error", "message": "用户名或密码错误"})

    client._session = FakeSession()
    result = client.login("u", "wrong")
    assert not result.ok and result.message == "用户名或密码错误"
    assert not result.error.startswith("network:")


def test_login_network_error_prefix():
    import requests

    client = JyingClient()

    class FakeSession:
        def post(self, url, json=None, timeout=None):
            raise requests.ConnectionError("boom")

    client._session = FakeSession()
    result = client.login("u", "p")
    assert not result.ok and result.error.startswith("network:")


def test_do_checkin_sends_empty_json_body():
    client = JyingClient()
    captured = {}

    class FakeSession:
        def post(self, url, json=None, timeout=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse(200, {"status": "success"})

    client._session = FakeSession()
    result = client.do_checkin("T")
    assert result.ok
    assert captured["url"].endswith("/api/app/checkin/do/")
    assert captured["json"] == {}
    assert captured["headers"]["Authorization"] == "Bearer T"


def test_luck_draw_guard_headers_only_with_user_id():
    client = JyingClient()
    captured = {}

    class FakeSession:
        def post(self, url, json=None, timeout=None, headers=None):
            captured["headers"] = headers
            return FakeResponse(200, {"status": "success"})

    client._session = FakeSession()
    client.luck_draw("T")  # 无 user_id：不带守卫头
    assert "X-Expected-App-User-Id" not in captured["headers"]
    client.luck_draw("T", user_id=9)  # 有 user_id：带守卫头
    assert captured["headers"]["X-Expected-App-User-Id"] == "9"
    assert captured["headers"]["X-App-User-Token"] == "T"
