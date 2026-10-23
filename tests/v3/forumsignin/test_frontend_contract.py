from pathlib import Path

ROOT = Path(__file__).parents[3] / "plugins.v3" / "forumsignin"
FRONTEND = ROOT / "frontend"


def test_remote_contract_and_views():
    vite = (FRONTEND / "vite.config.js").read_text(encoding="utf-8")
    assert "name: 'ForumSignin'" in vite
    assert "'./Config'" in vite and "'./Page'" in vite
    assert (ROOT / "dist" / "assets" / "remoteEntry.js").exists()


def test_forum_config_contract():
    source = (FRONTEND / "src" / "Config.vue").read_text(encoding="utf-8")
    assert "设置" in source and "站点" in source
    assert "展开配置" in source and "remove-icon" in source
    assert "credential?.fields" in source and "model[field.key]" in source
    assert ":type=\"field.type||'text'\"" in source
    assert "失败重试次数" in source and "签到 Cron" in source


def test_forum_page_contract():
    source = (FRONTEND / "src" / "Page.vue").read_text(encoding="utf-8")
    assert "data-grid" in source and "stats" in source
    assert "run_once" in source and "clean_cache" in source
    assert "history-group" in source and "成功 {{group.records" in source
    assert "site-icon site-initial" in source and "🔗" in source
    assert "site-totals" in source and "next_schedule" in source


def test_theme_and_site_registry_contract():
    css = (FRONTEND / "src" / "preview.css").read_text(encoding="utf-8")
    theme = (FRONTEND / "src" / "theme.js").read_text(encoding="utf-8")
    assert "--ptc-surface" in css and "data-ptc-glass" in css
    assert "MutationObserver" in theme
    registry = (ROOT / "core" / "registry.py").read_text(encoding="utf-8")
    assert "iter_modules" in registry and "SITE" in registry and "ADAPTER" in registry
