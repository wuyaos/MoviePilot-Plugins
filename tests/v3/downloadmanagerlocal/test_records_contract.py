"""记录查询真实 FastAPI 请求路径：宿主/下载器替身，不触发业务写入。"""

import copy
import importlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import ast
from pathlib import Path

from test_manual_run_endpoints import endpoints, PREFIX, _module, FakeHTTPException


@pytest.fixture
def records_api(endpoints, monkeypatch):
    records = importlib.import_module(PREFIX + '.controller.records')
    monkeypatch.setattr(records, 'HTTPException', FakeHTTPException)
    data = {
        'rename_records': {
            f'h{i:03}': {'time': f'2026-01-{i % 3 + 1:02}', 'success': i % 2 == 0}
            for i in reversed(range(45))
        },
        'rename_retry_state': {
            f'a{i:03}': {'archived': True, 'archived_at': '2026-01-01', 'fail_count': 3}
            for i in reversed(range(45))
        },
    }
    phases = ('completed', 'failed', 'target_ready', 'rollback', 'verifying')
    for i in reversed(range(105)):
        data[f'qb-h{i:03}'] = {
            'source_hash': f'h{i:03}', 'transfer_state': phases[i % 5],
            'updated_at': i % 3,
            'delete_source_requested': i % 5 == 2,
            'delete_source': False,
        }
    plugin = Mock()
    plugin.get_data.side_effect = lambda key=None: copy.deepcopy(data if key is None else data.get(key))
    _module(monkeypatch, PREFIX + '.modules.transfer.tasks', load_transfer_tasks=lambda plugin: [])
    _module(monkeypatch, PREFIX + '.modules.transfer.recheck', load_seed_recheck_queue=lambda plugin: {})
    monkeypatch.setattr(sys.modules[PREFIX + '.model.state'], 'load_transfer_stats', lambda plugin: {})
    routes = endpoints.routes.build_api_routes(plugin)
    queries = {route["path"]: route["endpoint"] for route in routes if route["path"] in PATHS}

    class OfflineClient:
        # Only transport conversion; validation/filtering/pagination run in real route handlers.
        def request(self, path, params=None, payload=None):
            try:
                query = {key: str(value) for key, value in (params or {}).items()}
                body = queries[path](**query, payload=payload)
                return SimpleNamespace(status_code=200, json=lambda: body)
            except FakeHTTPException as error:
                detail = {"detail": error.detail}
                return SimpleNamespace(status_code=error.status_code, json=lambda: detail)

        def get(self, path, params=None):
            return self.request(path, params=params)

        def post(self, path, json=None):
            return self.request(path, payload=json)

    yield SimpleNamespace(client=OfflineClient(), data=data, plugin=plugin, queries=queries, records=records)
    plugin.save_data.assert_not_called()


PATHS = ('/rename_history', '/rename_archive', '/transfer_status')


@pytest.mark.parametrize('path', PATHS)
def test_page_boundaries_and_empty_shape(records_api, path):
    client = records_api.client
    first = client.get(path).json()
    total = first['total']
    assert first['page'] == 1 and first['page_size'] == 20
    assert len(first['items']) == 20
    last_page = (total + 19) // 20
    last = client.get(path, params={'page': last_page}).json()
    assert len(last['items']) == total - (last_page - 1) * 20
    beyond = client.get(path, params={'page': last_page + 1}).json()
    assert beyond['items'] == [] and beyond['total'] == total
    records_api.data.clear()
    empty = client.get(path).json()
    assert empty['items'] == [] and empty['total'] == 0
    assert empty['page'] == 1 and empty['page_size'] == 20


@pytest.mark.parametrize('path', PATHS)
@pytest.mark.parametrize('size', (20, 50, 100))
def test_allowed_page_sizes(records_api, path, size):
    response = records_api.client.get(path, params={'page_size': size})
    assert response.status_code == 200
    body = response.json()
    assert body['page_size'] == size
    assert len(body['items']) == min(size, body['total'])


@pytest.mark.parametrize('path', PATHS)
@pytest.mark.parametrize('params', (
    {'page': 0}, {'page': -1}, {'page': 'bad'}, {'page': '1.5'},
    {'page_size': 15}, {'page_size': 0}, {'page_size': 200}, {'page_size': 'bad'},
    {'result_filter': 'unknown'},
))
def test_illegal_queries_rejected_for_get_and_post(records_api, path, params):
    for response in (records_api.client.get(path, params=params), records_api.client.post(path, json=params)):
        assert response.status_code in (400, 422)
        assert response.json()['detail']


@pytest.mark.parametrize('path', PATHS)
@pytest.mark.parametrize('params', ({'page': True}, {'page': 1.5}, {'page': None}, {'page_size': False}))
def test_post_does_not_coerce_invalid_json_numbers(records_api, path, params):
    response = records_api.client.post(path, json=params)
    assert response.status_code in (400, 422)


@pytest.mark.parametrize('path', PATHS)
def test_get_post_and_legacy_body_envelopes_are_identical(records_api, path):
    params = {'page': 2, 'page_size': 20, 'result_filter': 'all', 'detail_limit': 1}
    get = records_api.client.get(path, params=params)
    post = records_api.client.post(path, json=params)
    envelope = records_api.client.post(path, json={'data': params})
    assert get.status_code == post.status_code == envelope.status_code == 200
    assert get.json() == post.json() == envelope.json()
    assert len(get.json()['items']) == 20  # detail_limit is not pagination
    if path == '/transfer_status':
        body = get.json()
        assert body['status']['records'] == body['status']['items'] == body['items']
        assert 'pending' in body['status'] and 'tasks' in body['status'] and 'summary' in body['status']
    else:
        assert 'total_pages' in get.json()


@pytest.mark.parametrize('path,filters', (
    ('/rename_history', ('success', 'failed')),
    ('/rename_archive', ('failed',)),
    ('/transfer_status', ('success', 'failed', 'source_pending', 'rollback')),
))
def test_filter_before_paging_and_total(records_api, path, filters):
    all_rows = records_api.client.get(path, params={'page_size': 100}).json()['items']
    if path == '/transfer_status':
        all_rows += records_api.client.get(path, params={'page_size': 100, 'page': 2}).json()['items']
    for value in filters:
        if path == '/rename_archive':
            expected = all_rows
        elif path == '/rename_history':
            expected = [row for row in all_rows if row['success'] == (value == 'success')]
        else:
            phase = {'success': 'completed', 'failed': 'failed', 'source_pending': 'target_ready', 'rollback': 'rollback'}[value]
            expected = [row for row in all_rows if row['phase'] == phase]
        first = records_api.client.get(path, params={'result_filter': value}).json()
        second = records_api.client.post(path, json={'result_filter': value, 'page': 2}).json()
        assert first['total'] == second['total'] == len(expected)
        assert first['items'] == expected[:20]
        assert second['items'] == expected[20:40]
        assert first['result_filter'] == value


@pytest.mark.parametrize('path', PATHS)
def test_stable_timestamp_sort_with_unique_key_tiebreak(records_api, path):
    client = records_api.client
    first = client.get(path, params={'page_size': 100}).json()['items']
    # Change underlying insertion order, not record content.
    if path == '/rename_history':
        source = records_api.data['rename_records']
    elif path == '/rename_archive':
        source = records_api.data['rename_retry_state']
    else:
        source = records_api.data
    pairs = list(source.items())[::-1]
    source.clear()
    source.update(pairs)
    assert client.get(path, params={'page_size': 100}).json()['items'] == first
    assert client.get(path, params={'page_size': 100}).json()['items'] == first
    if path == '/rename_archive':
        assert [row['hash'] for row in first] == sorted(row['hash'] for row in first)
    elif path == '/rename_history':
        assert first == sorted(first, key=lambda row: (-int(row['time'][-2:]), row['hash']))
    else:
        assert first == sorted(first, key=lambda row: (-row['updated_at'], row['source_hash']))


def test_archive_rejects_success_instead_of_reinterpreting_archived_failures(records_api):
    response = records_api.client.get('/rename_archive', params={'result_filter': 'success'})
    assert response.status_code == 400
    assert '不能推导为成功' in response.json()['detail']


def test_source_pending_includes_completed_hr_blocked_without_mutating_history(records_api):
    records_api.data['qb-protected'] = {
        'source_hash': 'protected', 'transfer_state': 'completed', 'updated_at': 100,
        'delete_source_requested': True, 'delete_source': False, 'hr_protected': True,
    }
    body = records_api.client.get('/transfer_status', params={'result_filter': 'source_pending'}).json()
    assert body['items'][0]['source_hash'] == 'protected'
    assert body['items'][0]['phase'] == 'completed'
    assert body['status']['summary']['completed'] == 22  # unfiltered summary stays unfiltered
    success = records_api.client.get('/transfer_status', params={'result_filter': 'success'}).json()
    assert all(row['source_hash'] != 'protected' for row in success['items'])


def test_route_query_and_body_annotations_are_fastapi_bindable():
    root = Path(__file__).resolve().parents[3]
    tree = ast.parse((root / "plugins.v3/downloadmanagerlocal/controller/records.py").read_text(encoding="utf-8"))
    query = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "query")
    annotations = {arg.arg: ast.unparse(arg.annotation) for arg in query.args.args}
    assert annotations == {
        "page": "str | None", "page_size": "str | None", "result_filter": "str | None",
        "detail_limit": "str | None", "payload": "dict | None",
    }
    assert len(query.args.defaults) == 5
    assert all(isinstance(default, ast.Constant) and default.value is None for default in query.args.defaults)


def test_transfer_result_categories_are_disjoint_and_keep_other_inflight_rows(records_api):
    records_api.data["qb-retrying"] = {
        "source_hash": "retrying", "transfer_state": "rolled_back", "updated_at": 1,
    }
    categories = []
    for value in ("success", "failed", "source_pending", "rollback"):
        body = records_api.client.get("/transfer_status", params={"result_filter": value, "page_size": 100}).json()
        assert len(body["items"]) == body["total"] == (22 if value == "rollback" else 21)
        assert body["status"]["summary"]["rollback"] == 22
        assert body["result_filter"] == value
        categories.append({row["source_hash"] for row in body["items"]})
    assert "retrying" in categories[-1]
    assert all("retrying" not in group for group in categories[:-1])
    for index, group in enumerate(categories):
        assert all(group.isdisjoint(other) for other in categories[index + 1:])
    all_body = records_api.client.get("/transfer_status", params={"page_size": 100}).json()
    assert sum(map(len, categories)) <= all_body["total"] == 106
    beyond = records_api.client.get("/transfer_status", params={"page_size": 100, "page": 2}).json()
    assert any(row["source_hash"] == "retrying" for row in all_body["items"] + beyond["items"])


@pytest.mark.parametrize("path", PATHS)
def test_explicit_query_precedence_and_malformed_envelope(records_api, path):
    endpoint = records_api.queries[path]
    body = endpoint(page="1", page_size="50", payload={"page": 2, "page_size": 20})
    assert body["page"] == 1 and body["page_size"] == 50
    with pytest.raises(FakeHTTPException) as error:
        endpoint(payload={"data": []})
    assert error.value.status_code == 400


def test_rename_history_excludes_archived_without_rewriting_records(records_api):
    records_api.data["rename_retry_state"]["h000"] = {"archived": True}
    body = records_api.client.get("/rename_history", params={"result_filter": "success", "page_size": 100}).json()
    assert body["total"] == 22
    assert all(row["hash"] != "h000" for row in body["items"])
    assert "h000" in records_api.data["rename_records"]


@pytest.mark.parametrize("phases", (("rolled_back",), ("rollback",), ("rollback", "rolled_back")))
def test_transfer_rollback_filter_matches_history_and_summary(records_api, phases):
    records_api.data.clear()
    for phase in phases:
        records_api.data[f"qb-{phase}"] = {
            "source_hash": phase, "transfer_state": phase, "updated_at": 1,
            "delete_source_requested": True, "delete_source": False,
        }
    body = records_api.client.get("/transfer_status", params={"result_filter": "rollback"}).json()
    assert body["total"] == len(body["items"]) == len(phases)
    assert {row["phase"] for row in body["items"]} == set(phases)
    assert body["status"]["summary"]["rollback"] == body["total"]
    for value in ("success", "failed", "source_pending"):
        other = records_api.client.get("/transfer_status", params={"result_filter": value}).json()
        assert other["items"] == []
        assert other["total"] == 0
        assert other["status"]["summary"]["rollback"] == body["total"]
