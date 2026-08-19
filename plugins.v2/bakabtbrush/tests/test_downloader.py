from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.downloader import (
    DownloaderError,
    add_and_verify,
    available_slots,
    completed_infohashes,
    downloading_count,
    list_bakabt_torrents,
    transfer_totals_mb,
)


class FakeQBC:
    def __init__(self, torrents):
        self.torrents = torrents

    def torrents_info(self, category=None, torrent_hashes=None):
        if torrent_hashes:
            return [item for item in self.torrents if item.hash == torrent_hashes]
        return [item for item in self.torrents if item.category == category]


def _torrent(name, infohash, *, tags, state, progress=0, uploaded=0, downloaded=0, category="刷流"):
    return SimpleNamespace(
        name=name,
        hash=infohash,
        tags=tags,
        state=state,
        progress=progress,
        uploaded=uploaded,
        downloaded=downloaded,
        category=category,
    )


def test_qb_scope_filters_by_category_and_bakabt_tag_locally():
    instance = SimpleNamespace(qbc=FakeQBC([
        _torrent("a", "a" * 40, tags="bakabt,刷流", state="downloading", uploaded=3 * 1024**2, downloaded=2 * 1024**2),
        _torrent("b", "b" * 40, tags="刷流", state="downloading"),
        _torrent("c", "c" * 40, tags="bakabt", state="uploading", progress=1, uploaded=4 * 1024**2),
        _torrent("d", "d" * 40, tags="bakabt", state="downloading", category="其他"),
    ]))

    torrents = list_bakabt_torrents(instance, "刷流")

    assert [item.infohash for item in torrents] == ["a" * 40, "c" * 40]
    assert downloading_count(torrents) == 1
    assert transfer_totals_mb(torrents) == (7.0, 2.0)
    assert completed_infohashes(torrents) == {"c" * 40}


def test_add_requires_qb_to_confirm_expected_infohash(monkeypatch):
    class InvisibleQBC:
        def torrents_info(self, category=None, torrent_hashes=None):
            return []

    class InvisibleInstance:
        qbc = InvisibleQBC()

        @staticmethod
        def add_torrent(**kwargs):
            return True, ["a" * 40]

    monkeypatch.setattr("core.downloader.time.sleep", lambda _: None)
    with pytest.raises(DownloaderError, match="未确认"):
        add_and_verify(
            InvisibleInstance(), b"d4:infodummy", "a" * 40, "刷流", ("bakabt", "刷流"),
        )


def test_slot_limit_zero_is_unlimited_and_download_states_consume_slots():
    assert available_slots(2, 0) == 2
    assert available_slots(2, 1) == 1
    assert available_slots(2, 2) == 0
    assert available_slots(0, 99) is None
