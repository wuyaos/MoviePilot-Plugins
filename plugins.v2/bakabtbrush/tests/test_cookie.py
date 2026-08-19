from __future__ import annotations

from core.cookie import find_cookie_for_url, resolve_cookie


def test_cookiecloud_matches_root_and_subdomain_without_false_suffix_match():
    cookies = {
        ".bakabt.me": "bbtid=valid",
        "evilbakabt.me": "bbtid=wrong",
    }

    assert find_cookie_for_url(cookies, "https://bakabt.me/browse.php") == "bbtid=valid"
    assert find_cookie_for_url(cookies, "https://www.bakabt.me/browse.php") == "bbtid=valid"
    assert find_cookie_for_url({"evilbakabt.me": "bbtid=wrong"}, "https://bakabt.me/") == ""


def test_configured_cookie_takes_priority_over_cookiecloud():
    cookie, should_save = resolve_cookie(
        "bbtid=manual",
        "https://bakabt.me",
        cookiecloud_fetcher=lambda _: "bbtid=cloud",
    )

    assert cookie == "bbtid=manual"
    assert should_save is False


def test_cookiecloud_cookie_is_marked_for_config_writeback():
    cookie, should_save = resolve_cookie(
        "",
        "https://bakabt.me",
        cookiecloud_fetcher=lambda _: "bbtid=cloud",
    )

    assert cookie == "bbtid=cloud"
    assert should_save is True
