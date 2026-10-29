"""可选真实 FastAPI 参数绑定验收；未安装时保留为明确 skipped。"""

import pytest

fastapi = pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from test_records_contract import records_api, PATHS
from test_manual_run_endpoints import endpoints


def test_record_routes_real_http(records_api, monkeypatch):
    monkeypatch.setattr(records_api.records, 'HTTPException', fastapi.HTTPException)
    app = fastapi.FastAPI()
    for path, endpoint in records_api.queries.items():
        app.add_api_route(path, endpoint, methods=['GET', 'POST'], response_model=None)
    with TestClient(app) as client:
        for path in PATHS:
            params = {'page': 2, 'page_size': 20, 'result_filter': 'all', 'detail_limit': 1}
            get = client.get(path, params=params)
            post = client.post(path, json=params)
            envelope = client.post(path, json={'data': params})
            assert get.status_code == post.status_code == envelope.status_code == 200
            assert get.json() == post.json() == envelope.json()
            assert len(get.json()['items']) == 20
            for invalid in ({'page': 0}, {'page_size': 15}, {'result_filter': 'unknown'}):
                assert client.get(path, params=invalid).status_code in (400, 422)
                assert client.post(path, json=invalid).status_code in (400, 422)
