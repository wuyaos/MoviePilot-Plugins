from core.auth.cookiecloud import find_cookie_for_url, resolve_invites_cookie


def test_domain_boundary_and_manual_priority():
    cookies = {"evilinvites.fun": "bad", ".invites.fun": "good"}
    assert find_cookie_for_url(cookies, "https://invites.fun/") == "good"
    assert resolve_invites_cookie("manual", fetcher=lambda _: "cloud") == ("manual", False)
    assert resolve_invites_cookie("", fetcher=lambda _: "cloud") == ("cloud", True)
