import pytest

from core.config import PluginConfig
from core.source_instances import build_source_instances

SOURCE_ID = "pter_digest"
DEFAULT_URL = "https://pterclub.net/forums.php?action=viewtopic&topicid=2327&page=last#last"
EXTRA_URL = "https://pterclub.net/forums.php?action=viewtopic&topicid=9999&page=last#last"


def config_with_urls(*urls, enabled=True):
    return PluginConfig.from_dict({
        f"source_{SOURCE_ID}_enabled": enabled,
        f"source_{SOURCE_ID}_urls": "\n".join(urls),
    })


def pter_instances(config):
    return [source for source in build_source_instances(config) if source.base_id == SOURCE_ID]


def test_sources_are_disabled_by_default():
    config = PluginConfig.from_dict({})
    assert config.source_enabled(SOURCE_ID) is False
    assert build_source_instances(config) == []


def test_multiple_urls_are_normalized_and_deduplicated():
    equivalent = "HTTPS://PTERCLUB.NET:443/forums.php?topicid=2327&page=last&action=viewtopic#other"
    instances = pter_instances(config_with_urls(DEFAULT_URL, equivalent))
    assert len(instances) == 1
    assert instances[0].source_id == SOURCE_ID


def test_default_url_keeps_legacy_source_id():
    assert pter_instances(config_with_urls(DEFAULT_URL))[0].source_id == SOURCE_ID


def test_extra_url_has_stable_id_independent_of_input_order():
    first = pter_instances(config_with_urls(DEFAULT_URL, EXTRA_URL))
    second = pter_instances(config_with_urls(EXTRA_URL, DEFAULT_URL))
    first_extra = next(source for source in first if source.source_id != SOURCE_ID)
    second_extra = next(source for source in second if source.source_id != SOURCE_ID)
    assert first_extra.source_id == second_extra.source_id
    assert first_extra.source_id.startswith(f"{SOURCE_ID}#")


@pytest.mark.parametrize("invalid_url", [
    "http://pterclub.net/forums.php?topicid=9999",
    "https://pterclub.net.evil.example/forums.php?topicid=9999",
    "https://127.0.0.1/forums.php?topicid=9999",
])
def test_url_requires_https_known_domain_and_public_host(invalid_url):
    with pytest.raises(ValueError):
        build_source_instances(config_with_urls(invalid_url))
