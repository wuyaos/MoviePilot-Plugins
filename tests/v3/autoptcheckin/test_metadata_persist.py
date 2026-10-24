"""诊断元数据随结果落状态表：4.0.6 起页面/诊断可见 steps 与 page_action。"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
state_store = importlib.import_module("autoptcheckin.core.state_store")
TrackStateStore = state_store.TrackStateStore
_clip_metadata = state_store._clip_metadata


def _store(tmp_path):
    saved = {}

    def save(key, data):
        saved[key] = data

    return TrackStateStore(load=lambda key: saved.get(key), save=save), saved


def test_apply_result_persists_metadata(tmp_path):
    store, saved = _store(tmp_path)
    store.apply_result("yema", "sign", "failed", message="立即签到",
                       metadata={"page_action": {"button": "立即签到"}, "steps": [{"step": "click", "ok": False}]})
    entry = store.entry_of("yema", "sign")
    assert entry["metadata"]["page_action"] == {"button": "立即签到"}
    assert entry["metadata"]["steps"][0]["step"] == "click"


def test_apply_result_without_metadata_clears_stale(tmp_path):
    store, _ = _store(tmp_path)
    store.apply_result("yema", "sign", "failed", metadata={"steps": [{"step": "a"}]})
    store.apply_result("yema", "sign", "success", message="ok")
    assert "metadata" not in store.entry_of("yema", "sign")


def test_clip_metadata_truncates_steps(tmp_path):
    steps = [{"step": f"s{i}"} for i in range(9)]
    clipped = _clip_metadata({"steps": steps})
    assert len(clipped["steps"]) == 6
    assert clipped["steps"][-1]["dropped"] == 4


def test_clip_metadata_oversized_drops_steps(tmp_path):
    big = {"page_action": {"blob": "x" * 4096}, "steps": [{"step": "s"}]}
    clipped = _clip_metadata(big)
    # 丢 steps 后仍超预算：整体降级为 error 摘要，绝不让状态表膨胀
    assert clipped == {"error": "metadata oversized"}


def json_len(obj):
    import json
    return len(json.dumps(obj, ensure_ascii=False))
