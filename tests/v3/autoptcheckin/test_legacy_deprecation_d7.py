"""D7 offline dispatch contract: deprecated adapters are not native executors."""
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / 'plugins.v3'))
import autoptcheckin as entry
from autoptcheckin.core.models import SignResult, SignStatus
from autoptcheckin.core.registry import get_registry


@pytest.mark.parametrize('action,read_only', [('sign', False), ('sign', True), ('login', False)])
def test_all_native_sites_dispatch_without_legacy_bridge(monkeypatch, action, read_only):
    rows = [row for row in get_registry()['sites'] if row.get('native')]
    assert len(rows) == 128  # 3.38：hares 转正 + FileList/15 排除清单站转仅登录声明
    monkeypatch.setattr(entry, 'managed_site', lambda sid: {})
    run = Mock(return_value=SignResult(SignStatus.UNCONFIRMED, 'offline dispatch'))
    monkeypatch.setattr(entry, 'run_native', run)
    monkeypatch.setattr(entry, 'run_native_login', run)
    obj = entry.AutoPtCheckin()
    ids = [row['id'] for row in rows]
    obj.init_plugin({'enabled_sites': ids, 'sign_sites': ids, 'login_sites': ids, 'unlock_all_sites': True})
    for row in rows:
        run.reset_mock()
        result = obj._execute_site(row['id'], action=action, read_only=read_only)
        if (action == 'sign' and (row['id'] in {'darkland', 'digitalcore'} or not row['signin_capable'])) :
            assert result['status'] == 'skipped'
            run.assert_not_called()
        else:
            assert result['status'] == 'unconfirmed'
            run.assert_called_once()
            assert run.call_args.args[1].id == row['id']
            if action == 'sign':
                assert run.call_args.kwargs['read_only'] is read_only


def test_legacy_copies_and_bridge_removed():
    sites = ROOT / 'plugins.v3/autoptcheckin/sites'
    assert sorted(path.name for path in sites.glob('*.py')) == ['__init__.py']
    assert not (sites.parent / 'core/pilot.py').exists()
