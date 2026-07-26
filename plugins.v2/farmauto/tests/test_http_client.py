import sys
from pathlib import Path

import pytest
import requests

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.http_client import FarmHttpClient


class RecordingHttpClient(FarmHttpClient):
    def __init__(self, outcomes, **kwargs):
        super().__init__(retry_interval=0, min_interval=0, **kwargs)
        self.outcomes = list(outcomes)
        self.calls = []

    def _send(self, method, url, cookies, proxies, **kwargs):
        self.calls.append((method, url, proxies))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def response(status_code=200):
    value = requests.Response()
    value.status_code = status_code
    value.url = "https://farm.test"
    return value


def test_get_retries_transient_failure():
    client = RecordingHttpClient(
        [requests.Timeout("timeout"), response()], retry_count=2
    )

    result = client.get("https://farm.test/status", {})

    assert result.status_code == 200
    assert len(client.calls) == 2


def test_post_does_not_retry_transient_failure_by_default():
    client = RecordingHttpClient(
        [requests.Timeout("unknown outcome"), response()], retry_count=2
    )

    with pytest.raises(requests.Timeout, match="unknown outcome"):
        client.post("https://farm.test/action", {}, data={"action": "sell"})

    assert len(client.calls) == 1


def test_side_effect_get_can_disable_retry():
    client = RecordingHttpClient(
        [requests.ConnectionError("unknown outcome"), response()], retry_count=2
    )

    with pytest.raises(requests.ConnectionError, match="unknown outcome"):
        client.get("https://farm.test/action=plant", {}, retryable=False)

    assert len(client.calls) == 1
