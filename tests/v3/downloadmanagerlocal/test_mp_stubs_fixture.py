"""conftest.mp_stubs 夹具的自检：确保宿主替身 + 真实源码加载路径可用。

夹具本身是死代码时不会报错，只有真正加载一次插件模块才能发现路径写错
（历史上 parents[2] 曾指向 tests/，导致 PLUGIN 不存在）。
"""


def test_mp_stubs_loads_real_plugin_module(mp_stubs):
    module = mp_stubs("utils/torrent_adapter.py", "torrent_adapter")

    assert callable(module.get_torrent_state)
    assert callable(module.supports_recheck)
