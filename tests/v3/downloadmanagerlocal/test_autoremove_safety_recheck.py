"""Real scanner/criteria/cycle regression; downloader IO is substituted."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def runtime(mp_stubs, monkeypatch):
    prefix = "app.plugins.downloadmanagerlocal."
    previous = {k: v for k, v in sys.modules.items() if k.startswith(prefix)}
    for key in previous:
        sys.modules.pop(key)
    try:
        service = mp_stubs("modules/autoremove/service.py", "modules.autoremove.service")
        monkeypatch.setattr(service, "HrGuard", Mock(return_value=SimpleNamespace(
            should_skip=Mock(return_value=False))))
        yield SimpleNamespace(
            service=service,
            scanner=sys.modules[prefix + "modules.autoremove.scanner"],
            criteria=sys.modules[prefix + "modules.autoremove.criteria"],
            models=sys.modules[prefix + "modules.autoremove.models"],
        )
    finally:
        for key in list(sys.modules):
            if key.startswith(prefix):
                sys.modules.pop(key)
        sys.modules.update(previous)


def torrent(**overrides):
    return dict(hash="abc", name="fixture", size=2 * 1024**3, ratio=3,
                seeding_time=13 * 3600, completion_on=1, added_on=1,
                tags="keep", category="movie", state="stalledUP", uploaded=100,
                save_path="/data", tracker="") | overrides


def cycle(runtime, before, after, **extra):
    client = Mock()
    client.get_torrents.side_effect = [(before, None), (after, None)]
    plugin = Mock()
    plugin.get_data.return_value = None
    plugin.service_info.return_value = SimpleNamespace(type="qbittorrent", instance=client)
    service = runtime.service.AutoRemoveService(plugin)
    service.init_module(dict(enabled=True, remover_enabled=True, remover_observe_only=False,
                             remover_downloaders=["qb"], remover_action="delete",
                             remover_labels="keep", remover_time="12") | extra)
    return service.run_cycle("test"), client


@pytest.mark.parametrize("seed_seconds", [0, 3600, None, -1, "invalid"])
def test_wall_clock_age_never_substitutes_cumulative_time(runtime, seed_seconds):
    raw = torrent(seeding_time=seed_seconds)
    snap = runtime.scanner.build_snapshot(raw, "qb", "qbittorrent", 9999999999)
    assert snap.seeding_seconds == (3600 if seed_seconds == 3600 else 0)
    result, client = cycle(runtime, [raw], [raw])
    assert result["candidates"] == result["deleted"] == 0
    client.delete_torrents.assert_not_called()


@pytest.mark.parametrize("field", ["seconds_seeding", "secondsSeeding"])
def test_transmission_cumulative_time_aliases(runtime, field):
    raw = dict(hashString="abc", name="tr", doneDate=1, addedDate=1, **{field: 7200})
    snap = runtime.scanner.build_snapshot(raw, "tr", "transmission", 9999999999)
    assert snap.seeding_seconds == 7200
    raw.pop(field)
    assert runtime.scanner.build_snapshot(raw, "tr", "transmission", 9999999999).seeding_seconds == 0


@pytest.mark.parametrize("changes,conditions", [
    ({"tags": "other"}, {}),
    ({"category": "tv"}, {"remover_torrentcategorys": "movie"}),
    ({"state": "downloading"}, {"remover_torrentstates": "stalledUP"}),
    ({"seeding_time": 3600}, {}),
    ({"ratio": 1}, {"remover_ratio": "2"}),
])
def test_recheck_rejects_changed_conditions_without_writes(runtime, changes, conditions):
    result, client = cycle(runtime, [torrent()], [torrent(**changes)], **conditions)
    assert result["candidates"] == 1
    assert result["deleted"] == 0
    assert result["skipped"] == 1
    client.delete_torrents.assert_not_called()
    client.stop_torrents.assert_not_called()


def test_unchanged_eligible_task_still_executes(runtime):
    result, client = cycle(runtime, [torrent()], [torrent()])
    assert result["deleted"] == 1
    client.delete_torrents.assert_called_once_with(delete_file=False, ids=["abc"])


@pytest.mark.parametrize("changed", [False, True])
def test_same_data_relation_is_rechecked(runtime, changed):
    primary = torrent()
    extra = torrent(hash="def", seeding_time=0)
    after = [torrent(tags="other") if changed else primary, extra]
    result, client = cycle(runtime, [primary, extra], after, remover_samedata=True)
    assert result["candidates"] == 2
    assert result["deleted"] == (0 if changed else 2)
    assert client.delete_torrents.call_count == (0 if changed else 2)


@pytest.mark.parametrize("raw", ["1,100", "1", "1-2-3", "100-1", "1-1", "-1-100", "nan-100", "1-inf"])
def test_size_range_invalid_is_explicit_config_error(runtime, raw):
    with pytest.raises(runtime.criteria.RemoverConfigError, match="最小值-最大值"):
        runtime.criteria.compile_conditions(runtime.models.RemoverConfig(size=raw))


def test_size_range_open_interval(runtime):
    cond = runtime.criteria.compile_conditions(runtime.models.RemoverConfig(size="1-3"))
    for size, matched in [(1, False), (2, True), (3, False)]:
        snap = runtime.scanner.build_snapshot(torrent(size=size * 1024**3), "qb", "qbittorrent", 0)
        assert (runtime.criteria.match_reason(cond, snap) is not None) is matched


@pytest.mark.parametrize("field,setting,value,matched", [
    ("category", "remover_torrentcategorys", "movie4k", False),
    ("category", "remover_torrentcategorys", "movie,tv", True),
    ("category", "remover_torrentcategorys", " movie ， tv ", True),
    ("category", "remover_torrentcategorys", "", True),
    ("state", "remover_torrentstates", "stalledUP,pausedUP", True),
    ("state", "remover_torrentstates", "stalledUP4k", False),
    ("state", "remover_torrentstates", "", True),
])
def test_exact_lists_preserve_empty_unrestricted(runtime, field, setting, value, matched):
    result, client = cycle(runtime, [torrent()], [torrent()], **{setting: value})
    assert result["deleted"] == int(matched)
    assert client.delete_torrents.call_count == int(matched)


@pytest.mark.parametrize("field,setting", [
    ("category", "remover_torrentcategorys"), ("state", "remover_torrentstates"),
])
@pytest.mark.parametrize("value", ["", None])
def test_required_field_missing_cannot_match(runtime, field, setting, value):
    raw = torrent(**{field: value})
    condition = "movie" if field == "category" else "stalledUP"
    result, client = cycle(runtime, [raw], [raw], **{setting: condition})
    assert result["candidates"] == result["deleted"] == 0
    client.delete_torrents.assert_not_called()
    # With no restriction on this field, other conditions still decide.
    result, client = cycle(runtime, [raw], [raw], **{setting: ""})
    assert result["deleted"] == 1


@pytest.mark.parametrize("field,setting,condition", [
    ("category", "remover_torrentcategorys", "movie4k"),
    ("state", "remover_torrentstates", "stalledUP"),
])
def test_recheck_uses_exact_lists(runtime, field, setting, condition):
    before = torrent(**{field: condition})
    after = torrent(**{field: "movie" if field == "category" else ""})
    result, client = cycle(runtime, [before], [after], **{setting: condition})
    assert result["candidates"] == 1
    assert result["deleted"] == 0
    client.delete_torrents.assert_not_called()


@pytest.mark.parametrize("setting", ["remover_time", "remover_ratio", "remover_upspeed"])
@pytest.mark.parametrize("invalid", ["-1", "nan", "NaN", "inf", "-inf", "1e999"])
def test_invalid_numeric_conditions_stop_entire_cycle(runtime, setting, invalid):
    result, client = cycle(runtime, [torrent()], [torrent()], **{setting: invalid})
    assert result["config_error"]
    assert result["deleted"] == 0
    client.delete_torrents.assert_not_called()
    client.stop_torrents.assert_not_called()


@pytest.mark.parametrize("setting", ["remover_time", "remover_upspeed"])
def test_scaled_threshold_overflow_is_config_error(runtime, setting):
    result, client = cycle(runtime, [torrent()], [torrent()], **{setting: "1e308"})
    assert result["config_error"]
    client.delete_torrents.assert_not_called()


@pytest.mark.parametrize("field", ["seeding_time", "ratio", "uploaded"])
@pytest.mark.parametrize("invalid", ["inf", "nan", "-inf", -1, None])
def test_bad_downloader_numbers_never_enable_delete(runtime, field, invalid):
    raw = torrent(**{field: invalid})
    condition = {"seeding_time": {}, "ratio": {"remover_ratio": "2"},
                 "uploaded": {"remover_time": "", "remover_upspeed": "1"}}[field]
    result, client = cycle(runtime, [raw], [raw], **condition)
    assert result["deleted"] == 0
    client.delete_torrents.assert_not_called()


@pytest.mark.parametrize("seed_seconds", [None, 0, "invalid", "inf", "nan"])
def test_unknown_average_is_not_low_speed(runtime, seed_seconds):
    raw = torrent(seeding_time=seed_seconds)
    snap = runtime.scanner.build_snapshot(raw, "qb", "qbittorrent", 0)
    assert snap.average_upload_bps is None
    candidate = runtime.models.RemoveCandidate(snap, "test")
    assert candidate.to_view()["average_upload_bps"] is None
    result, client = cycle(runtime, [raw], [raw], remover_time="", remover_upspeed="1")
    assert result["candidates"] == result["deleted"] == 0
    client.delete_torrents.assert_not_called()


def test_confirmed_zero_upload_is_real_low_speed(runtime):
    raw = torrent(uploaded=0)
    result, client = cycle(runtime, [raw], [raw], remover_time="", remover_upspeed="1")
    assert result["deleted"] == 1
    client.delete_torrents.assert_called_once()


def test_unknown_average_does_not_block_unrelated_conditions(runtime):
    raw = torrent(uploaded=None)
    result, client = cycle(runtime, [raw], [raw])
    assert result["deleted"] == 1
    client.delete_torrents.assert_called_once()


@pytest.mark.parametrize("uploaded", [None, "inf", "nan", 0, 100])
def test_transmission_average_requires_known_stats(runtime, uploaded):
    raw = dict(hashString="abc", name="tr", secondsSeeding=100,
               uploadedEver=uploaded, uploadRatio=3)
    snap = runtime.scanner.build_snapshot(raw, "tr", "transmission", 0)
    assert snap.average_upload_bps == (uploaded / 100 if isinstance(uploaded, int) else None)
