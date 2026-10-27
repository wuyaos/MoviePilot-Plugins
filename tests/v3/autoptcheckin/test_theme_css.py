from pathlib import Path

ROOT = Path(__file__).parents[3]
SRC = ROOT / "frontend.v3" / "autoptcheckin" / "src"


def test_theme_css_defines_status_and_surface_tokens():
    css = (SRC / "preview.css").read_text()
    for token in (
        "--ptc-surface", "--ptc-line", "--ptc-text", "--ptc-text-muted",
        "--ptc-success-bg", "--ptc-success-text", "--ptc-signed-bg",
        "--ptc-failure-bg", "--ptc-unknown-bg", "--ptc-off-bg",
        "--ptc-danger", "--ptc-confirm", "--ptc-control-radius", "--ptc-control-height",
    ):
        assert token in css
    assert ":global(html.v-theme--dark)" in css
    assert "--ptc-danger:var(--ptc-failure-text)" in css
    assert "--ptc-control-radius:6px" in css
    assert "prefers-color-scheme:dark" in css
    assert "background:#" not in css and "color:#" not in css


def test_theme_observer_tracks_host_class():
    source = (SRC / "theme.js").read_text()
    assert "MutationObserver" in source
    assert "v-theme--dark" in source and "v-theme--light" in source
    assert "ptcTheme" in source
