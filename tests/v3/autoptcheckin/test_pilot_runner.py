"""S5 离线链测试：合成页面仅回归解析器，不宣称生产结构已核验。"""
import asyncio
import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / 'plugins.v3'))
from autoptcheckin.core.runner import SignRunner
from autoptcheckin.core.credentials import Credential, CredentialResolution
from autoptcheckin.core.pilot import PilotBridge, site_id_for_domain
from autoptcheckin.verifiers.hdsky import HDSkyVerifier
from autoptcheckin.verifiers.haitang import HaitangVerifier

DATE = '2026-10-17'
FIXTURES = Path(__file__).parent / 'fixtures'


def page(site='hdsky', state='success'):
    return (FIXTURES / f'{site}_{state}.html').read_text(encoding='utf8')


def run_chain(pages, *, site='hdsky', uid='42', submit=None, read_only=False, auth=True):
    history, reads, submits = [], [], []
    iterator = iter(pages)
    def fetch():
        reads.append(True)
        value = next(iterator)
        if isinstance(value, Exception):
            raise value
        return value
    def post():
        submits.append(True)
        return submit() if submit else (True, 'old result ignored')
    result = SignRunner(history=history.append).run(site, uid, DATE,
        resolve=lambda: CredentialResolution(Credential('managed_site', 'offline-placeholder', uid), 'valid') if auth else CredentialResolution(None, 'auth_failed'),
        fetch_page=fetch, verifier=HDSkyVerifier() if site == 'hdsky' else HaitangVerifier(),
        submit=post, read_only=read_only, allow_page_identity=True)
    return result, history, reads, submits


@pytest.mark.parametrize('site', ['hdsky', 'haitang'])
def test_success_has_new_page_evidence(site):
    result, history, reads, submits = run_chain([page(site, 'unsigned'), page(site)], site=site)
    assert result.status == 'success'
    assert result.evidence.uid == '42' and result.evidence.date == DATE
    assert result.evidence.button_text == '今日已签到'
    assert len(history) == 1 and len(reads) == 2 and len(submits) == 1


@pytest.mark.parametrize('after', ['', '<html>changed structure</html>', TimeoutError()])
def test_readback_failure_is_unconfirmed(after):
    result, _, reads, submits = run_chain([page(state='unsigned'), after])
    assert result.status == 'unconfirmed' and len(reads) == 2 and len(submits) == 1


@pytest.mark.parametrize('old', [(False, 'failed'), (True, 'success')])
def test_legacy_tuple_cannot_determine_result(old):
    result, _, reads, _ = run_chain([page(state='unsigned'), page()], submit=lambda: old)
    assert result.status == 'success' and len(reads) == 2


def test_submission_exception_still_reads():
    def fail():
        raise TimeoutError()
    result, _, reads, _ = run_chain([page(state='unsigned'), page()], submit=fail)
    assert result.status == 'success' and result.metadata['submit_exception'] and len(reads) == 2


def test_missing_credentials_never_fetch():
    result, history, reads, submits = run_chain([], uid='', auth=False)
    assert result.status == 'auth_failed' and len(history) == 1
    assert not reads and not submits
    assert PilotBridge('hdsky', {}).resolve().status == 'auth_failed'


def test_already_does_not_submit():
    result, _, reads, submits = run_chain([page()])
    assert result.status == 'already' and len(reads) == 1 and not submits


def test_busy_is_independent_history_record():
    history = []
    runner = SignRunner(history=history.append)
    with runner.locks.acquire(('hdsky', '42')):
        result = runner.run('hdsky', '42', DATE, resolve=lambda: pytest.fail(),
                            fetch_page=lambda: pytest.fail(), verifier=HDSkyVerifier(), submit=lambda: pytest.fail())
    assert result.status == 'skipped' and len(history) == 1


def test_readonly_never_submits():
    result, _, reads, submits = run_chain([page(state='unsigned')], read_only=True)
    assert result.status == 'unconfirmed' and len(reads) == 1 and not submits


def test_unknown_preflight_does_not_submit():
    result, _, _, submits = run_chain(['<html>unknown</html>'])
    assert result.status == 'unconfirmed' and not submits


def test_first_page_binds_uid():
    result, _, _, submits = run_chain([page(state='unsigned'), page()], uid='')
    assert result.account == '42' and result.status == 'success' and submits


def test_conflicting_uid_stops():
    result, _, _, submits = run_chain([page(state='unsigned')], uid='99')
    assert result.status == 'unconfirmed' and not submits


def test_unparsed_uid_allows_clear_form_but_not_success():
    unsigned = page(state='unsigned').replace('<div id="info_block"><a href="userdetails.php?id=42">本人</a></div>', '')
    result, _, _, submits = run_chain([unsigned, '<html>unknown</html>'], uid='')
    assert result.status == 'unconfirmed' and submits


@pytest.mark.parametrize('site,verifier', [('hdsky', HDSkyVerifier()), ('haitang', HaitangVerifier())])
def test_parser_only_reads_matching_current_row(site, verifier):
    evidence = verifier.parse(page(site), '99', DATE)
    assert not evidence.date
    evidence = verifier.parse(page(site), '42', '2020-01-01')
    assert not evidence.date
    evidence = verifier.parse(page(site), '42', DATE)
    assert evidence.status == '签到成功' and evidence.uid == '42'


@pytest.mark.parametrize('domain,expected', [('https://hdsky.me/index.php','hdsky'), ('htpt.cc','haitang'), ('hdsky.me.evil.invalid',None), ('unknown',None)])
def test_domain_boundary(domain, expected):
    assert site_id_for_domain(domain) == expected


def test_api_auth_failure_history_and_readonly(monkeypatch):
    module = importlib.import_module('autoptcheckin')
    monkeypatch.setattr(module, 'managed_site', lambda sid: {})
    plugin = module.AutoPtCheckin()
    plugin.init_plugin({'enabled_sites': ['hdsky', 'rousi'], 'sign_sites': ['hdsky']})
    response = asyncio.run(plugin.api_signin_by_domain('hdsky.me'))
    assert response['data']['status'] == 'auth_failed'
    assert asyncio.run(plugin.api_verify_site('hdsky'))['data']['status'] == 'auth_failed'
    results = plugin._execute_all()
    assert [r['status'] for r in results] == ['auth_failed']
    history = asyncio.run(plugin.api_history())['data']
    assert history['total'] == 6
    stats = asyncio.run(plugin.api_stats())['data']
    assert stats['latest']['sign']['failed'] == 1
    assert next(s for s in stats['sites'] if s['id'] == 'hdsky')['can_signin']


def test_disabled_site_rejected_before_host_io(monkeypatch):
    module = importlib.import_module('autoptcheckin')
    monkeypatch.setattr(module, 'managed_site', lambda sid: pytest.fail('host must not be accessed'))
    result = asyncio.run(module.AutoPtCheckin().api_signin_by_domain('hdsky'))
    assert result['data']['status'] == 'skipped'


def test_signed_text_in_other_page_content_does_not_block_submit():
    unsigned = page(state='unsigned').replace('</body>', '<p>其他用户已签到</p></body>')
    result, _, _, submits = run_chain([unsigned, page()])
    assert submits and result.status == 'success'

def test_bound_identity_record_confirms_without_navigation():
    unsigned = page(state='unsigned').replace('<div id="info_block"><a href="userdetails.php?id=42">本人</a></div>', '')
    result, _, _, submits = run_chain([unsigned, page().replace('<div id="info_block"><a href="userdetails.php?id=42">本人</a></div>', '')], uid='42')
    assert submits and result.status == 'success' and result.evidence.uid == '42'


def test_signed_text_in_other_page_content_does_not_block_submit():
    unsigned = page(state='unsigned').replace('</body>', '<p>其他用户已签到</p></body>')
    result, _, _, submits = run_chain([unsigned, page()])
    assert submits and result.status == 'success'

def test_bound_identity_record_confirms_without_navigation():
    unsigned = page(state='unsigned').replace('<div id="info_block"><a href="userdetails.php?id=42">本人</a></div>', '')
    result, _, _, submits = run_chain([unsigned, page().replace('<div id="info_block"><a href="userdetails.php?id=42">本人</a></div>', '')], uid='42')
    assert submits and result.status == 'success' and result.evidence.uid == '42'


def test_failed_record_without_submittable_control_does_not_submit():
    before = page().replace('今日已签到', '签到入口未知').replace('<button id="showup">', '<button id="showup" disabled>').replace('签到成功', '未签到')
    result, _, reads, submits = run_chain([before])
    assert not submits and len(reads) == 1 and result.status == 'unconfirmed'

@pytest.mark.parametrize('outcome,expected', [('no_result', 2), ('failed', 1), ('success', 1), ('already', 1)])
def test_hdsky_only_retries_unrecognized_captcha(outcome, expected):
    calls = []
    class Adapter:
        def _try_engine(self, engine, *args):
            calls.append(engine)
            return outcome
    bridge = PilotBridge('hdsky', {'cookie': 'offline-placeholder'})
    bridge.adapter = Adapter()
    bridge.submit()
    assert len(calls) == expected
