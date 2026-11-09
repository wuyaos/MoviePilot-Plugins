"""antibot 模块离线测试：solve_pow 算法与 AntibotClient token 缓存生命周期。"""
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


if __name__ == "__main__":
    test_solve_pow()
    test_token_cache()
    print("tests OK")
