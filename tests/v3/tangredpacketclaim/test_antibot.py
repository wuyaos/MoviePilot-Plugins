"""antibot 模块离线测试：solve_pow 算法与 AntibotClient token 缓存生命周期。"""
import hashlib
import importlib.util
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "tang_antibot_under_test", ROOT / "plugins.v3/tangredpacketclaim/antibot.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AntibotClient = MODULE.AntibotClient
AntibotError = MODULE.AntibotError
solve_pow = MODULE.solve_pow


def test_solve_pow():
    salt, cid = "abc123", "ch-42"
    n = solve_pow(salt, cid, 8)
    digest = hashlib.sha256(f"{salt}:{cid}:{n}".encode()).hexdigest()
    assert digest.startswith("00"), digest
    # difficulty 0 直接返回 0
    assert solve_pow(salt, cid, 0) == 0
    # 难度过高快速失败
    try:
        solve_pow(salt, cid, 40, max_attempts=100)
        raise AssertionError("should raise")
    except AntibotError:
        pass


def test_token_cache():
    store = {}
    client = AntibotClient("https://x.example", "", store.get,
                           lambda k, v: store.__setitem__(k, v))
    assert client.device()
    assert client.device() == store["antibot_device"]
    assert client.cached_token() is None
    assert client.claim_headers() == {}
    store["antibot_token"] = {"token": "t1", "expires_at": 0, "max_uses": 0, "used": 0}
    assert client.cached_token() is None  # expires_at=0 已过期
    import time
    store["antibot_token"] = {"token": "t1", "expires_at": int(time.time()) + 600,
                              "max_uses": 2, "used": 2}
    assert client.cached_token() is None  # 用尽
    store["antibot_token"] = {"token": "t1", "expires_at": int(time.time()) + 600,
                              "max_uses": 2, "used": 1}
    state = client.cached_token()
    assert state and state["token"] == "t1"
    headers = client.claim_headers()
    assert headers["X-RedPacket-Token"] == "t1" and headers["X-RedPacket-Device"]
    client.mark_used()
    assert store["antibot_token"]["used"] == 2
    assert client.cached_token() is None
    client.invalidate()
    assert store["antibot_token"] == ""

import types


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    """按 data 匹配返回 canned 响应的最小 session 桩。"""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def post(self, url, data=None, timeout=None, headers=None):
        self.calls.append({"url": url, "data": dict(data or {})})
        for matcher, payload in self.responses:
            if matcher(data or {}):
                return _FakeResp(payload)
        raise AssertionError("no canned response for %r" % (data,))


def test_turnstile_fallback_pow():
    store = {}
    client = AntibotClient("https://x.example", "", store.get,
                           lambda k, v: store.__setitem__(k, v))
    # 桩掉浏览器求解：模拟 qnap CloakBrowser 拿不到 token 的场景
    client._solve_turnstile = types.MethodType(
        lambda self, challenge: (_ for _ in ()).throw(AntibotError("浏览器不可用")), client)
    ts_challenge = {"mode": "turnstile", "challenge_id": "t-1", "site_key": "sk"}
    fb_challenge = {"mode": "pow", "challenge_id": "p-1", "salt": "abc123",
                    "difficulty_bits": 8}

    # turnstile 失败 → challenge {fallback:1} → pow 求解，verify 用 fallback 的 challenge_id
    session = _FakeSession([(lambda d: d.get("fallback") == 1, fb_challenge)])
    mode, payload, effective = client._solve_challenge(session, ts_challenge)
    assert mode == "pow" and effective["challenge_id"] == "p-1"
    assert payload["confirm"] == 0
    digest = hashlib.sha256(f"abc123:p-1:{payload['nonce']}".encode()).hexdigest()
    assert digest.startswith("00"), digest

    # 主 challenge 直接 pow：不触发 fallback 请求
    mode2, payload2, eff2 = client._solve_challenge(_FakeSession([]), fb_challenge)
    assert mode2 == "pow" and eff2 is fb_challenge and payload2["confirm"] == 0

    # fallback 返回未知模式 → 报错
    session3 = _FakeSession([(lambda d: d.get("fallback") == 1,
                              {"mode": "turnstile", "challenge_id": "x"})])
    try:
        client._solve_challenge(session3, ts_challenge)
        raise AssertionError("should raise")
    except AntibotError:
        pass

    # fallback 返回 disabled → 上层短路（ensure_token 缓存 1h）
    session4 = _FakeSession([(lambda d: d.get("fallback") == 1, {"mode": "disabled"})])
    mode4, payload4, _ = client._solve_challenge(session4, ts_challenge)
    assert mode4 == "disabled" and payload4 == {}


if __name__ == "__main__":
    test_solve_pow()
    test_token_cache()
    test_turnstile_fallback_pow()
    print("tests OK")
