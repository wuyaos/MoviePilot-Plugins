"""将来源模板与多行 URL 配置展开为稳定的运行实例。"""
from __future__ import annotations

import hashlib
from dataclasses import replace

from .models import SourceSpec
from .source_registry import SOURCES
from .url_utils import normalize_url, validate_source_url

MAX_URLS_PER_SOURCE = 10


def configured_urls(config, source: SourceSpec) -> list[str]:
    raw = config.source_urls_text(source.source_id)
    lines = [line.strip() for line in str(raw or "").splitlines() if line.strip()]
    if len(lines) > MAX_URLS_PER_SOURCE:
        raise ValueError(f"{source.title} 每个来源最多配置 {MAX_URLS_PER_SOURCE} 个地址")
    urls: list[str] = []
    seen: set[str] = set()
    for line_number, line in enumerate(lines, 1):
        try:
            normalized = validate_source_url(line, source.site_domain)
        except ValueError as error:
            raise ValueError(f"{source.title} 第 {line_number} 行：{error}") from error
        if normalized not in seen:
            seen.add(normalized)
            urls.append(normalized)
    return urls


def build_source_instances(config, source_filter: str = "", *, include_disabled: bool = False) -> list[SourceSpec]:
    instances: list[SourceSpec] = []
    for source in SOURCES:
        if source_filter and source.source_id != source_filter:
            continue
        if not include_disabled and not config.source_enabled(source.source_id):
            continue
        urls = configured_urls(config, source)
        default_url = normalize_url(source.url)
        for url in urls:
            instance_id = source.source_id if url == default_url else _instance_id(source.source_id, url)
            instances.append(replace(
                source,
                source_id=instance_id,
                base_source_id=source.source_id,
                url=url,
                title=source.title,
            ))
    return instances


def validate_source_config(config) -> None:
    build_source_instances(config, include_disabled=True)


def _instance_id(base_source_id: str, normalized_url: str) -> str:
    digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:12]
    return f"{base_source_id}#{digest}"
