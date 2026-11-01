"""H&R 预设不能扩大白名单，重复下载事件不能重置已纳管任务。"""
from test_hr_site_scope import hr  # noqa: F401
from test_hr_check_snapshots import hr_check  # noqa: F401


def test_builtin_rules_do_not_expand_explicit_scope(hr):
    config = hr.rules.parse_hr_config({'hr_enable_site_config': True, 'hr_sites': ['OnlyAllowed']})
    assert config.site_rules
    assert config.site_in_scope('OnlyAllowed')
    for name in config.site_rules:
        assert not config.site_in_scope(name)


def test_explicit_yaml_extends_scope_but_presets_do_not(hr):
    config = hr.rules.parse_hr_config({'hr_enable_site_config': True, 'hr_sites': [],
                                      'hr_site_config_str': '- site_name: UserSite\n  hr_duration: 72'})
    assert config.site_in_scope('UserSite')
    assert all(not config.site_in_scope(name) for name in config.site_rules if name != 'UserSite')


def test_duplicate_download_event_keeps_compliant_task(hr_check):
    module, service, downloader = hr_check
    task = module.HrTask(downloader='qb', hash='done', hr_status=module.HrStatus.COMPLIANT,
                         added_on=123, hr_seed_time=9876)
    service._tasks[task.key] = task
    downloader.instance.get_torrents.reset_mock()
    assert service.register_task('qb', 'done', torrent_data={'hit_and_run': True}) is False
    assert service._tasks[task.key] is task
    assert task.hr_status == module.HrStatus.COMPLIANT
    assert task.added_on == 123
    downloader.instance.get_torrents.assert_not_called()
