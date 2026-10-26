"""RetroToon notification message: timezone chrome stripped, judgment unchanged.

Real-page structure taken from the 2026-10 calibration sample
(D:/tmp/calibration/retrotoon.html): the rt-form-card "Daily Reward" card embeds
timezone chrome ("Your day resets at midnight in UTC ... Change timezone" and
the hidden "Your device reports ... Use this timezone" block) that leaked into
the whole notification message. Offline only; no real URLs are requested.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "plugins.v3"))
from autoptcheckin.core.credentials import Credential
from autoptcheckin.core.models import LoginPage
from autoptcheckin.core.sitemodel import SignContext
from autoptcheckin.sites.native.retrotoon import RetroToon, _strip_timezone_noise

NOISE_DIVS = (
    '<div style="margin-top:12px; font-size:10px; opacity:.5;">'
    '&#128336; Your day resets at midnight in <b>UTC</b>'
    ' (it is Oct 22, 07:10 there now).'
    ' <a href="my.php">Change timezone</a></div>'
    '<div id="tz-mismatch" style="display:none;">'
    ' Your device reports <b id="tz-mismatch-name"></b>.'
    ' <a href="#" id="tz-mismatch-use">Use this timezone</a></div>'
)

CLAIM_FORM = ('<form method="post" style="display:inline;">'
              '<input type="hidden" name="csrf_token" value="fixture-csrf">'
              '<input type="submit" name="claim" value="Claim Daily Reward" class="rt-btn">'
              '</form>')

CLAIMED_MESSAGE = ('<div class="rt-claim-result">'
                   "&#10004; You've already claimed today's reward. Come back tomorrow!"
                   '</div>')

UNCLAIMED_PAGE = ('<main><div class="rt-form-card">'
                  '<div class="rt-section-head">&#127873; Daily Reward</div>'
                  f'<div style="padding:18px 16px; text-align:center;">{CLAIM_FORM}{NOISE_DIVS}</div>'
                  '</div></main>')

CLAIMED_PAGE = ('<main><div class="rt-form-card">'
                '<div class="rt-section-head">&#127873; Daily Reward</div>'
                f'<div style="padding:18px 16px; text-align:center;">{CLAIMED_MESSAGE}{NOISE_DIVS}</div>'
                '</div></main>')

# Fresh readback after a successful claim: reward granted, same chrome.
SUCCESS_PAGE = ('<main><div class="rt-form-card">'
                '<div class="rt-section-head">&#127873; Daily Reward</div>'
                '<div style="padding:18px 16px; text-align:center;">'
                '<div class="rt-claim-result">Daily reward claimed! +409 pts</div>'
                f'{NOISE_DIVS}</div></div></main>')


class Http:
    def retain_cookies(self, names):
        pass

    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url))
        return LoginPage(next(self.pages), url)

    def post(self, url, *, data):
        self.calls.append(("post", url, data))
        return LoginPage("untrusted reply", url)


def context(site, http):
    return SignContext(site.id, Credential("managed_site", "fixture"), http)


def test_noise_stripped_from_message_text():
    trimmed = _strip_timezone_noise(
        "Daily Reward\n    \n✅ You've already claimed today's reward. Come back tomorrow!\n"
        "🕐 Your day resets at midnight in UTC\n(it is Oct 22, 07:20 there now).\n"
        "Change timezone\n\nYour device reports .\nUse this timezone")
    assert "already claimed" in trimmed
    for noise in ("Your day resets", "(it is Oct", "Change timezone",
                  "Your device reports", "Use this timezone"):
        assert noise not in trimmed


def test_signed_preread_message_trimmed():
    site = RetroToon()
    http = Http([CLAIMED_PAGE])
    result = site.signin(context(site, http))
    assert result.status == "already"
    assert "already claimed" in result.message
    assert "Use this timezone" not in result.message
    assert "Your day resets" not in result.message
    assert "Change timezone" not in result.message
    assert "Your device reports" not in result.message
    assert len(http.calls) == 1


def test_success_readback_message_trimmed():
    site = RetroToon()
    http = Http([UNCLAIMED_PAGE, SUCCESS_PAGE])
    result = site.signin(context(site, http))
    assert result.status == "success"
    assert "reward claimed" in result.message
    for noise in ("Your day resets", "midnight", "Change timezone",
                  "Your device reports", "Use this timezone"):
        assert noise not in result.message
    assert [x[0] for x in http.calls] == ["get", "post", "get"]
    assert dict(http.calls[1][2]) == {"csrf_token": "fixture-csrf", "claim": "Claim Daily Reward"}


def test_noise_never_fabricates_signed_or_failed():
    site = RetroToon()
    # No signed keyword anywhere: unclaimed form + chrome only on both reads.
    http = Http([UNCLAIMED_PAGE, UNCLAIMED_PAGE])
    result = site.signin(context(site, http))
    assert result.status == "unconfirmed"
    assert result.status not in ("success", "already", "failed")
    assert [x[0] for x in http.calls] == ["get", "post", "get"]


def test_judgment_uses_untrimmed_text():
    site = RetroToon()
    ctx = context(site, Http([]))
    # The only signed keyword sits on a line that trimming removes; the
    # judgment must still be made on the untrimmed card text.
    page = ('<main><div class="rt-form-card">'
            '<div class="rt-section-head">&#127873; Daily Reward</div>'
            '<div>You\'ve already claimed today\'s reward. Use this timezone</div>'
            '</div></main>')
    evidence = ctx.read_record(LoginPage(page, site.url), site.record_spec)
    assert evidence.status == "signed"
    result = site.read_after(ctx, LoginPage(page, site.url))
    assert result.status == "success"
    assert "already claimed" not in result.message
