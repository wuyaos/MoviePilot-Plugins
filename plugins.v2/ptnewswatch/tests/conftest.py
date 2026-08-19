from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1]
PLUGINS_ROOT = ROOT.parent
for path in (ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# 测试 UI/core 子模块时跳过插件入口的 MoviePilot/apscheduler 运行时依赖。
package = types.ModuleType("ptnewswatch")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("ptnewswatch", package)
