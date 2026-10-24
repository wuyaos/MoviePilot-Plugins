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
    assert "分论坛设置" in source
    assert "每个论坛独立启用与配置" in source
    assert "pting.club" in source and "invites.fun" in source and "ssdforum.org" in source
    assert source.index("yaowan_username") < source.index("yaowan_password") < source.index("yaowan_cookie")
    assert "timed_update_enabled" in source and "展开配置" not in source and "remove-icon" not in source
    assert "model.onlyonce" not in source and "执行调度" not in source
    assert "失败重试次数" in source and "签到 Cron" in source


def test_forum_page_contract():
    source = (FRONTEND / "src" / "Page.vue").read_text(encoding="utf-8")
    assert "data-grid" in source and "stats" in source
    assert "run_once" in source and "clean_cache" not in source
    assert "history-group" not in source and "<details" not in source
    assert "site-icon site-initial" in source and "can_sync" in source
    assert "site-totals" not in source and "next_schedule" in source
    assert "连续签到" in source and "currentStreak" in source and "points" not in source and "maxStreak" not in source and "lastCheckInDate" not in source and "checkedInToday" not in source
    assert 'v-if="site.message" class="meta"' in source and 'v-else class="meta">连续签到' in source
    assert "data?.attributes" not in source and "totalContinuousCheckIn" not in source


def test_theme_and_site_registry_contract():
    css = (FRONTEND / "src" / "preview.css").read_text(encoding="utf-8")
    theme = (FRONTEND / "src" / "theme.js").read_text(encoding="utf-8")
    assert "--ptc-surface" in css and "data-ptc-glass" in css
    assert "MutationObserver" in theme
    registry = (ROOT / "core" / "registry.py").read_text(encoding="utf-8")
    assert "iter_modules" in registry and "SITE" in registry and "ADAPTER" in registry


def test_stats_exposes_sync_capability():
    source = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert '"can_sync": site["id"] == "fengchao"' in source


def test_page_renders_fengchao_sync_badge():
    source = (FRONTEND / "src" / "Page.vue").read_text(encoding="utf-8")
    assert "stats.value?.fengchao_user_info" in source
    assert "stats.value?.fengchao_sync" in source
    assert "function syncChip" in source and "未同步" in source and "同步失败 · " in source
    assert "totalContinuousCheckIn" not in source and "lastCheckinMoney" not in source
    assert "syncInfo" not in source and "上次同步：" not in source
