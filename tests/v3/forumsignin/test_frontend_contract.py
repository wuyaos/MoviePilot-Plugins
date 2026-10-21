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
    assert "展开配置" in source
    assert "蜂巢同步状态" in source
    assert 'type="password"' in source
    assert "来源：" in source and "凭证：" in source and "能力：" in source


def test_forum_page_contract():
    source = (FRONTEND / "src" / "Page.vue").read_text(encoding="utf-8")
    assert "data-grid" in source and "stats" in source
    assert "蜂巢个人信息" in source
    assert "history-day" in source and "evidence-grid" in source
    assert "site-icon site-initial" in source
    assert "展开其余" in source
