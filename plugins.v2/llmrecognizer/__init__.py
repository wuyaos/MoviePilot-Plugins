# input: ChainEventType.NameRecognize 事件 + MoviePilot LLM 配置
# output: 结构化识别兜底结果（注回事件链）+ 失败样本 JSONL + CustomIdentifiers 建议
# pos: 识别链路扩展层，原生识别失败后 LLM 结构化兜底，沉淀失败样本并生成识别词规则

import hmac
import asyncio
import inspect
import json
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.chain.media import MediaChain
from app.core.config import settings
from app.core.event import eventmanager
from app.core.meta.words import WordsMatcher
from app.core.metainfo import MetaInfo
from app.db.systemconfig_oper import SystemConfigOper
try:
    from app.helper.llm import LLMHelper
except ImportError:
    from app.agent.llm import LLMHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import ChainEventType, MediaType, SystemConfigKey


class AIRecognitionGuess(BaseModel):
    name: str = Field(default="", description="标准化后的影视标题；无法判断时返回空字符串")
    year: str = Field(default="", description="四位年份；无法判断时返回空字符串")
    media_type: str = Field(default="unknown", description="movie、tv 或 unknown")
    season: int = Field(default=0, description="剧集季号，电影填 0")
    episode: int = Field(default=0, description="剧集集号，电影或未知填 0")
    confidence: float = Field(default=0.0, description="0 到 1 之间的置信度")
    reason: str = Field(default="", description="简短说明为什么这样判断")


class IdentifierSuggestion(BaseModel):
    comment: str = Field(default="", description="可选注释，不带 #")
    rule: str = Field(default="", description="一条 MoviePilot 自定义识别词规则")
    confidence: float = Field(default=0.0, description="0 到 1 之间的置信度")
    reason: str = Field(default="", description="为什么建议这条规则")


class IdentifierSuggestionBundle(BaseModel):
    summary: str = Field(default="", description="整体建议摘要")
    suggestions: List[IdentifierSuggestion] = Field(default_factory=list, description="建议规则列表")


class LLMRecognizer(_PluginBase):
    plugin_name = "AI识别增强"
    plugin_desc = "直接复用 MoviePilot 当前 LLM 配置，在原生识别失败后做本地结构化识别兜底，并交回原生链路继续二次识别。"
    plugin_icon = "https://raw.githubusercontent.com/wuyaos/MoviePilot-Plugins/main/icons/llmrecognizer.png"
    plugin_version = "1.1.0"
    plugin_author = "wuyaos"
    plugin_level = 1
    author_url = "https://github.com/wuyaos"
    # plugin_config_prefix 简化为 llmrecognizer_
    plugin_config_prefix = "llmrecognizer_"
    plugin_order = 41
    auth_level = 1

    _enabled = False
    _debug = False
    _confidence_threshold = 0.65
    _request_timeout = 25
    _max_retries = 2
    _save_failed_samples = True
    _max_failed_samples = 200
    _auto_remove_applied_sample = True
    # 新增：是否调用 TMDB 二次校验
    _verify_tmdb: bool = False
    # 新增：是否要求 TMDB 校验通过才注入
    _require_tmdb_verify: bool = False
    _systemconfig: Optional[SystemConfigOper] = None

    # ---- 线程安全 ----
    _sample_lock: Optional[threading.Lock] = None       # 保护 JSONL 文件读写
    _chain_lock: Optional[threading.Lock] = None        # 保护 LLM chain 懒初始化
    _identifiers_lock: Optional[threading.Lock] = None  # 保护 CustomIdentifiers 读写
    _llm_chain = None                                   # 识别 chain 缓存
    _identifier_chain = None                            # 识别词建议 chain 缓存

    def init_plugin(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._debug = bool(config.get("debug", False))
        self._confidence_threshold = self._safe_float(config.get("confidence_threshold"), 0.65)
        self._request_timeout = self._safe_int(config.get("request_timeout"), 25)
        self._max_retries = max(1, min(5, self._safe_int(config.get("max_retries"), 2)))
        self._save_failed_samples = bool(config.get("save_failed_samples", True))
        self._max_failed_samples = max(20, min(1000, self._safe_int(config.get("max_failed_samples"), 200)))
        self._auto_remove_applied_sample = bool(config.get("auto_remove_applied_sample", True))
        self._verify_tmdb = bool(config.get("verify_tmdb", False))
        self._require_tmdb_verify = bool(config.get("require_tmdb_verify", False))
        self._systemconfig = SystemConfigOper()
        # 配置变更时重置 chain 缓存，须在旧锁内置 None 再换锁，避免竞态
        if self._chain_lock:
            with self._chain_lock:
                self._llm_chain = None
                self._identifier_chain = None
        else:
            self._llm_chain = None
            self._identifier_chain = None
        self._sample_lock = threading.Lock()
        self._chain_lock = threading.Lock()
        self._identifiers_lock = threading.Lock()
        self._ensure_plugin_log_file()
        self._register_events()

    def _ensure_plugin_log_file(self) -> None:
        """确保插件日志文件存在，避免前端日志页 404。"""
        try:
            path = settings.LOG_PATH / "plugins" / "llmrecognizer.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except Exception:
            pass

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def stop_service(self):
        try:
            eventmanager.disable_event_handler(self.on_chain_name_recognize)
        except Exception:
            pass

    # ---- 工具方法 ----

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _extract_apikey(request: Request, body: Optional[Dict[str, Any]] = None) -> str:
        header = str(request.headers.get("Authorization") or "").strip()
        if header.lower().startswith("bearer "):
            return header.split(" ", 1)[1].strip()
        if body:
            for key in ("apikey", "api_key"):
                token = str(body.get(key) or "").strip()
                if token:
                    return token
        return str(request.query_params.get("apikey") or "").strip()

    def _check_api_access(self, request: Request, body: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        expected = str(getattr(settings, "API_TOKEN", "") or "").strip()
        if not expected:
            return False, "服务端未配置 API Token"
        actual = self._extract_apikey(request, body)
        if not hmac.compare_digest(actual, expected):
            return False, "API Token 无效"
        return True, ""

    def _register_events(self) -> None:
        try:
            eventmanager.register(ChainEventType.NameRecognize)(self.on_chain_name_recognize)
            if self._enabled:
                eventmanager.enable_event_handler(self.on_chain_name_recognize)
            else:
                eventmanager.disable_event_handler(self.on_chain_name_recognize)
        except Exception as exc:
            logger.warning(f"[AI识别增强] 注册链式识别事件失败: {exc}")

    @staticmethod
    def _extract_title_path(event_data: Any) -> Tuple[str, str]:
        title = ""
        path = ""
        if isinstance(event_data, dict):
            title = (event_data.get("title") or event_data.get("name")
                     or event_data.get("org_string") or "")
            path = (event_data.get("path") or event_data.get("file_path")
                    or event_data.get("org_string") or "")
        else:
            title = (getattr(event_data, "title", "") or getattr(event_data, "name", "")
                     or getattr(event_data, "org_string", "") or "")
            path = (getattr(event_data, "path", "") or getattr(event_data, "file_path", "")
                    or getattr(event_data, "org_string", "") or "")
        return str(title or "").strip(), str(path or "").strip()

    def _build_meta_hint(self, raw_text: str) -> Dict[str, Any]:
        try:
            meta = MetaInfo(raw_text)
        except Exception as exc:
            logger.debug(f"[AI识别增强] MetaInfo 解析失败: {exc}")
            return {}
        return {
            "name": getattr(meta, "name", "") or "",
            "year": getattr(meta, "year", "") or "",
            "type": getattr(getattr(meta, "type", None), "to_agent", lambda: None)() or "",
            "season": getattr(meta, "begin_season", None) or 0,
            "episode": getattr(meta, "begin_episode", None) or 0,
        }

    # ---- LLM chain 缓存 ----

    @staticmethod
    def _run_async_compatible(value: Any, timeout: Optional[float] = None) -> Any:
        if not inspect.isawaitable(value):
            return value
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(value)
        result: Dict[str, Any] = {}
        error: Dict[str, Exception] = {}

        def _worker() -> None:
            try:
                result["value"] = asyncio.run(value)
            except Exception as exc:
                error["exc"] = exc

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if t.is_alive():
            raise TimeoutError("async LLM bridge timed out")
        if "exc" in error:
            raise error["exc"]
        return result.get("value")

    def _get_llm(self):
        llm = LLMHelper.get_llm(streaming=False)
        return self._run_async_compatible(llm, timeout=self._request_timeout + 2)

    def _get_recognize_chain(self):
        """懒初始化并缓存识别 chain，线程安全。"""
        with self._chain_lock:
            if self._llm_chain is None:
                llm = self._get_llm()
                self._llm_chain = (
                    self._build_prompt()
                    | llm.with_structured_output(AIRecognitionGuess)
                    .with_retry(stop_after_attempt=self._max_retries)
                )
            return self._llm_chain

    def _get_identifier_chain(self):
        """懒初始化并缓存识别词建议 chain，线程安全。"""
        with self._chain_lock:
            if self._identifier_chain is None:
                llm = self._get_llm()
                self._identifier_chain = (
                    self._build_identifier_prompt()
                    | llm.with_structured_output(IdentifierSuggestionBundle)
                    .with_retry(stop_after_attempt=self._max_retries)
                )
            return self._identifier_chain

    def _build_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """你是 MoviePilot 的影视文件名识别增强助手。

你的任务不是搜索 TMDB，也不是编造结果，而是根据文件名、路径和已有解析提示，尽量提炼出更适合 MoviePilot 二次识别的结构化信息。

规则：
1. 只依据输入内容推断，不要臆造不存在的信息。
2. 如果不确定，请返回空标题，并把 media_type 设为 unknown，confidence 降低。
3. title/name 只保留作品名，不要包含分辨率、制作组、音频编码、网盘标记等噪音。
4. year 只有在比较确定时才给四位年份。
5. 电影 season/episode 必须为 0。
6. 剧集如果能确定季集就填写，否则保持 0。
7. media_type 只能是 movie、tv、unknown。
8. confidence 范围为 0 到 1。
"""),
            ("human", """原始标题：
{title}

原始路径：
{path}

MoviePilot 当前基础解析提示：
{meta_hint}
"""),
        ])

    def _build_identifier_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", """你是 MoviePilot 自定义识别词规则助手。

你的任务是根据错误标题、当前解析结果和目标结果，生成尽量窄作用域、可直接用于 MoviePilot CustomIdentifiers 的规则。

支持格式只有四种：
1. 屏蔽词
2. 替换词：被替换词 => 替换词
3. 集偏移：前定位词 <> 后定位词 >> EP±N
4. 组合规则：被替换词 => 替换词 && 前定位词 <> 后定位词 >> EP±N

硬性要求：
1. 运算符两侧必须保留空格： => 、 <> 、 >> 、 &&
2. 优先生成窄作用域规则，尽量带发布组、年份、季集、分辨率等锚点
3. 不要生成过宽的裸屏蔽词，比如 1080p、WEB-DL、字幕
4. 如果需要强制绑 TMDB，可使用 {[tmdbid=xxx;type=tv/movies;s=1;e=14]} 这种替换词
5. comment 不带 #，rule 里不要再包 markdown 或代码块
6. 如果没有把握，请返回空 suggestions
"""),
            ("human", """原始标题：
{title}

原始路径：
{path}

MoviePilot 当前基础解析：
{meta_hint}

AI 识别增强结果：
{guess}

二次校验到的媒体信息摘要：
{verified_summary}

希望修正成的目标结果：
{target}
"""),
        ])

    def _invoke_llm(self, title: str, path: str) -> AIRecognitionGuess:
        raw_text = path or title
        meta_hint = self._build_meta_hint(raw_text)
        chain = self._get_recognize_chain()
        result: AIRecognitionGuess = chain.invoke(
            {"title": title, "path": path, "meta_hint": meta_hint},
        )
        return self._normalize_guess(result)

    def _invoke_identifier_llm(self, title: str, path: str,
                                result: Dict[str, Any], target: Dict[str, Any]) -> IdentifierSuggestionBundle:
        chain = self._get_identifier_chain()
        bundle: IdentifierSuggestionBundle = chain.invoke(
            {
                "title": title,
                "path": path,
                "meta_hint": self._build_meta_hint(path or title),
                "guess": result.get("guess") or {},
                "verified_summary": self._compact_verified_summary(result.get("verified_media_info")),
                "target": target,
            },
        )
        return bundle

    def _normalize_guess(self, guess: AIRecognitionGuess) -> AIRecognitionGuess:
        name = str(guess.name or "").strip()
        year = str(guess.year or "").strip()
        if len(year) != 4 or not year.isdigit():
            year = ""
        media_type = str(guess.media_type or "unknown").strip().lower()
        if media_type not in ("movie", "tv"):
            media_type = "unknown"
        season = max(0, self._safe_int(guess.season, 0))
        episode = max(0, self._safe_int(guess.episode, 0))
        confidence = min(1.0, max(0.0, self._safe_float(guess.confidence, 0.0)))
        return AIRecognitionGuess(name=name, year=year, media_type=media_type,
                                  season=season, episode=episode, confidence=confidence,
                                  reason=str(guess.reason or "").strip())

    # ---- 样本文件（线程安全） ----

    def _sample_path(self) -> Path:
        return self.get_data_path() / "failed_samples.jsonl"

    @staticmethod
    def _sample_identity(payload: Dict[str, Any]) -> str:
        return json.dumps(
            {"title": str(payload.get("title") or "").strip(),
             "path": str(payload.get("path") or "").strip(),
             "reason": str(payload.get("reason") or "").strip()},
            ensure_ascii=False, sort_keys=True,
        )

    def _write_failed_samples(self, rows: List[Dict[str, Any]]) -> None:
        sample_path = self._sample_path()
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        trimmed = rows[-self._max_failed_samples:]
        with sample_path.open("w", encoding="utf-8") as f:
            for row in trimmed:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _record_failed_sample(self, payload: Dict[str, Any]) -> None:
        if not self._save_failed_samples:
            return
        try:
            with self._sample_lock:
                rows = self._read_failed_samples_unsafe(limit=1000)
                rows.reverse()
                identity = self._sample_identity(payload)
                filtered = [r for r in rows if self._sample_identity(r) != identity]
                filtered.append(payload)
                self._write_failed_samples(filtered)
        except Exception as exc:
            logger.warning(f"[AI识别增强] 写入失败样本失败: {exc}")

    def _read_failed_samples_unsafe(self, limit: int = 20) -> List[Dict[str, Any]]:
        """不加锁，调用方需自己持有 _sample_lock。
        返回 newest-first 顺序；写回文件前必须先 rows.reverse() 恢复 oldest-first。
        """
        sample_path = self._sample_path()
        if not sample_path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        try:
            with sample_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning(f"[AI识别增强] 读取失败样本失败: {exc}")
            return []
        if limit > 0:
            rows = rows[-limit:]
        rows.reverse()
        return rows

    def _read_failed_samples(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._sample_lock:
            return self._read_failed_samples_unsafe(limit=limit)

    def _clear_failed_samples(self) -> int:
        with self._sample_lock:
            rows = self._read_failed_samples_unsafe(limit=1000)
            sample_path = self._sample_path()
            if sample_path.exists():
                sample_path.unlink()
            return len(rows)

    def _remove_failed_sample(self, sample_index: Optional[Any], limit: int = 1000) -> Dict[str, Any]:
        with self._sample_lock:
            rows = self._read_failed_samples_unsafe(limit=max(1, min(limit, 1000)))
            if not rows:
                return {"removed": False, "message": "暂无失败样本", "removed_count": 0}
            index = self._safe_int(sample_index, 0)
            if index < 0:
                index = 0
            if index >= len(rows):
                return {"removed": False, "message": f"索引超出范围，当前共 {len(rows)} 条", "removed_count": 0}
            removed_sample = dict(rows[index])
            del rows[index]
            if rows:
                rows.reverse()
                self._write_failed_samples(rows)
            else:
                sp = self._sample_path()
                if sp.exists():
                    sp.unlink()
            return {"removed": True, "message": "success", "removed_count": 1,
                    "remaining_count": len(rows), "removed_sample": removed_sample,
                    "removed_sample_index": index}

    def _remove_failed_samples(self, sample_indexes: List[Any], limit: int = 1000) -> Dict[str, Any]:
        with self._sample_lock:
            rows = self._read_failed_samples_unsafe(limit=max(1, min(limit, 1000)))
            if not rows:
                return {"removed": False, "message": "暂无失败样本", "removed_count": 0, "remaining_count": 0}
            normalized = sorted(
                {self._safe_int(i, -1) for i in (sample_indexes or []) if self._safe_int(i, -1) >= 0},
                reverse=True,
            )
            valid = [i for i in normalized if i < len(rows)]
            if not valid:
                return {"removed": False, "message": "没有可移除的有效索引",
                        "removed_count": 0, "remaining_count": len(rows)}
            removed: List[Dict[str, Any]] = []
            for i in valid:
                removed.append(dict(rows[i]))
                del rows[i]
            if rows:
                rows.reverse()
                self._write_failed_samples(rows)
            else:
                sp = self._sample_path()
                if sp.exists():
                    sp.unlink()
            removed.reverse()
            return {"removed": True, "message": "success", "removed_count": len(valid),
                    "remaining_count": len(rows), "removed_sample_indexes": sorted(valid),
                    "removed_samples": removed}

    def _inject_sample_indices(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{**s, "sample_index": i} for i, s in enumerate(samples)]

    def _resolve_failed_sample(self, sample_index: Optional[Any] = None,
                                limit: int = 100) -> Tuple[Optional[int], Optional[Dict[str, Any]], str]:
        samples = self._read_failed_samples(limit=max(1, min(limit, 200)))
        if not samples:
            return None, None, "暂无失败样本"
        index = max(0, self._safe_int(sample_index, 0))
        if index >= len(samples):
            return None, None, f"索引超出范围，当前共 {len(samples)} 条"
        row = {**samples[index], "sample_index": index}
        return index, row, ""

    def _select_failed_sample_indexes(self, sample_indexes: Optional[List[Any]] = None,
                                       limit: int = 10, pool_limit: int = 200,
                                       ) -> Tuple[List[int], List[Dict[str, Any]], str]:
        current = self._inject_sample_indices(self._read_failed_samples(limit=max(1, min(pool_limit, 1000))))
        if not current:
            return [], [], "暂无失败样本"
        if isinstance(sample_indexes, list) and sample_indexes:
            seen: set = set()
            selected: List[int] = []
            for raw in sample_indexes:
                idx = self._safe_int(raw, -1)
                if idx < 0 or idx >= len(current) or idx in seen:
                    continue
                seen.add(idx)
                selected.append(idx)
        else:
            selected = [int(s.get("sample_index", 0)) for s in current[:max(1, min(limit, 50))]]
        if not selected:
            return [], current, "没有可处理的有效样本索引"
        return selected, current, ""

    # ---- 样本摘要 ----

    def _summarize_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        sample = dict(sample or {})
        guess = sample.get("guess") or {}
        verified = sample.get("verified_media_info") or {}
        inferred_target = {
            "name": verified.get("title") or guess.get("name") or "",
            "year": verified.get("year") or guess.get("year") or "",
            "media_type": self._normalize_media_type(verified.get("type") or guess.get("media_type")),
            "season": self._safe_int(guess.get("season"), 0),
            "episode": self._safe_int(guess.get("episode"), 0),
            "tmdb_id": self._safe_int(verified.get("tmdb_id"), 0),
        }
        return {
            "sample_index": sample.get("sample_index"),
            "title": sample.get("title"),
            "path": sample.get("path"),
            "reason": sample.get("reason"),
            "guess_name": guess.get("name"),
            "guess_confidence": self._safe_float(guess.get("confidence"), 0.0),
            "verified_title": verified.get("title"),
            "verified_year": verified.get("year"),
            "verified_tmdb_id": verified.get("tmdb_id"),
            "inferred_target": inferred_target,
            "can_auto_suggest": bool(inferred_target["name"]),
        }

    def _target_from_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        return self._summarize_sample(sample).get("inferred_target") or {}

    @staticmethod
    def _normalize_reason_tag(reason: Any) -> str:
        text = str(reason or "").strip()
        if not text:
            return "unknown"
        if ":" in text:
            return text.split(":", 1)[0].strip() or "unknown"
        return text

    @staticmethod
    def _sample_group_key(summary: Dict[str, Any]) -> str:
        target = summary.get("inferred_target") or {}
        title = (str(target.get("name") or "").strip() or str(summary.get("verified_title") or "").strip()
                 or str(summary.get("guess_name") or "").strip() or str(summary.get("title") or "").strip())
        return json.dumps({"title": title.lower(),
                           "media_type": str(target.get("media_type") or "unknown").lower(),
                           "season": int(target.get("season") or 0),
                           "episode": int(target.get("episode") or 0)},
                          ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _sample_display_name(summary: Dict[str, Any]) -> str:
        target = summary.get("inferred_target") or {}
        title = (str(target.get("name") or "").strip() or str(summary.get("verified_title") or "").strip()
                 or str(summary.get("guess_name") or "").strip() or str(summary.get("title") or "").strip())
        if not title:
            return "未命名样本"
        media_type = str(target.get("media_type") or "").lower()
        season = int(target.get("season") or 0)
        episode = int(target.get("episode") or 0)
        suffix = f" S{season:02d}E{episode:02d}" if media_type == "tv" and (season or episode) else ""
        return f"{title}{suffix}"

    def _build_sample_insights(self, samples: List[Dict[str, Any]], top: int = 10) -> Dict[str, Any]:
        summaries = [self._summarize_sample(s) for s in samples]
        reason_counter: Counter = Counter()
        title_counter: Counter = Counter()
        group_counter: Counter = Counter()
        for s in summaries:
            reason_counter[self._normalize_reason_tag(s.get("reason"))] += 1
            title_counter[self._sample_display_name(s)] += 1
            group_counter[self._sample_group_key(s)] += 1

        actionable: List[Dict[str, Any]] = []
        for s in summaries:
            dup = group_counter[self._sample_group_key(s)]
            score = 0
            reasons: List[str] = []
            if dup >= 2:
                score += min(dup, 5)
                reasons.append(f"同类样本重复 {dup} 次")
            if s.get("verified_tmdb_id"):
                score += 3
                reasons.append("已有 TMDB 命中")
            if s.get("can_auto_suggest"):
                score += 2
                reasons.append("可直接生成识别词")
            conf = self._safe_float(s.get("guess_confidence"), 0.0)
            if 0 < conf < self._confidence_threshold:
                score += 1
                reasons.append(f"距阈值差 {round(self._confidence_threshold - conf, 2)}")
            row = {**s, "duplicate_count": dup, "priority_score": score, "priority_reasons": reasons}
            actionable.append(row)

        actionable.sort(key=lambda x: (-int(x.get("priority_score") or 0),
                                        -int(x.get("duplicate_count") or 0),
                                        -self._safe_float(x.get("guess_confidence"), 0.0),
                                        int(x.get("sample_index") or 0)))
        return {
            "total_count": len(summaries),
            "reason_counts": [{"reason": r, "count": c} for r, c in reason_counter.most_common(top)],
            "top_titles": [{"title": t, "count": c} for t, c in title_counter.most_common(top)],
            "repeated_groups": [{"title": t, "count": c} for t, c in title_counter.most_common(top) if c >= 2],
            "priority_samples": actionable[:top],
        }

    def _render_sample_brief(self, samples: List[Dict[str, Any]], top: int = 5) -> str:
        summaries = [self._summarize_sample(s) for s in samples[:max(1, min(top, 20))]]
        if not summaries:
            return "当前没有失败样本。"
        lines = [f"失败样本 {len(samples)} 条，展示前 {len(summaries)} 条："]
        for s in summaries:
            label = self._sample_display_name(s)
            conf = round(self._safe_float(s.get("guess_confidence"), 0.0), 2)
            hint = "可建议" if s.get("can_auto_suggest") else "需人工"
            lines.append(f"{s.get('sample_index')}. {label} | 置信度 {conf} | {hint}")
        lines.append("下一步：可直接调用批量建议或批量复查接口。")
        return "\n".join(lines)

    @staticmethod
    def _render_batch_results_brief(action_name: str, requested_count: int,
                                     success_count: int, failed_count: int,
                                     results: List[Dict[str, Any]]) -> str:
        lines = [f"{action_name}：共处理 {requested_count} 条，成功 {success_count}，失败 {failed_count}。"]
        for item in results[:10]:
            idx = item.get("sample_index")
            if item.get("success"):
                label = (((item.get("source_sample") or {}).get("title"))
                         or ((item.get("target") or {}).get("name")) or "样本")
                lines.append(f"{idx}. 成功 | {label}")
            else:
                lines.append(f"{idx}. 失败 | {item.get('message', '未知错误')}")
        return "\n".join(lines)

    # ---- 识别 ----

    def _verify_guess(self, title: str, path: str, guess: AIRecognitionGuess) -> Optional[Dict[str, Any]]:
        """TMDB 二次校验。仅当 _verify_tmdb=True 时调用，失败静默降级。"""
        if not guess.name:
            return None
        try:
            raw_text = path or title or guess.name
            meta = MetaInfo(raw_text)
            meta.name = guess.name
            meta.year = guess.year or None
            meta.begin_season = guess.season or None
            meta.begin_episode = guess.episode or None
            if guess.media_type == "tv" or meta.begin_season or meta.begin_episode:
                meta.type = MediaType.TV
            elif guess.media_type == "movie":
                meta.type = MediaType.MOVIE
            # cache=True：使用缓存避免每次识别都打远端共享识别服务造成 500 噪音
            mediainfo = MediaChain().recognize_media(meta=meta, cache=True)
            if not mediainfo:
                return None
            return mediainfo.to_dict()
        except Exception as exc:
            # 始终 debug 级别，不污染用户日志
            logger.debug(f"[AI识别增强] TMDB 二次校验失败: {exc}")
            return None

    def _recognize(self, title: str, path: str = "", record_failed_sample: bool = True) -> Dict[str, Any]:
        title = str(title or "").strip()
        path = str(path or "").strip()
        if not title and path:
            title = Path(path).name
        if not title:
            return {"success": False, "message": "标题为空"}

        try:
            guess = self._invoke_llm(title, path)
        except Exception as exc:
            if record_failed_sample:
                self._record_failed_sample({
                    "title": title, "path": path,
                    "meta_hint": self._build_meta_hint(path or title),
                    "reason": f"llm_error:{exc}",
                })
            return {"success": False, "message": f"LLM 调用失败: {exc}"}

        # 仅在配置要求时才调 TMDB，避免 "共享媒体识别失败" 500 日志
        verified = self._verify_guess(title, path, guess) if self._verify_tmdb else None

        passed = bool(guess.name and guess.confidence >= self._confidence_threshold)
        # 若配置要求 TMDB 校验必须通过才注入
        if passed and self._require_tmdb_verify:
            passed = verified is not None

        if not passed and record_failed_sample:
            self._record_failed_sample({
                "title": title, "path": path,
                "meta_hint": self._build_meta_hint(path or title),
                "guess": guess.model_dump(),
                "verified_media_info": self._compact_verified_summary(verified),
                "reason": "low_confidence_or_empty_name",
            })
        return {
            "success": passed,
            "message": "success" if passed else "识别结果置信度不足，已放弃注入",
            "guess": guess.model_dump(),
            "verified_media_info": verified,
        }

    def on_chain_name_recognize(self, event) -> None:
        if not self._enabled:
            return
        event_data = getattr(event, "event_data", None) or {}
        title, path = self._extract_title_path(event_data)
        if not title and not path:
            return

        # 在独立线程中执行 LLM 调用，以 request_timeout+2s 为上限等待
        # 保留对 event_data 的写能力（chain 事件同步读取），但限制最长阻塞时间
        result_holder: Dict[str, Any] = {}

        def _run():
            result_holder["result"] = self._recognize(title=title, path=path)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=self._request_timeout + 2)

        if not result_holder:
            logger.warning(f"[AI识别增强] 识别超时（>{self._request_timeout}s）: {title or path}")
            return

        result = result_holder.get("result") or {}
        if not result.get("success"):
            if self._debug:
                logger.info(f"[AI识别增强] 跳过注入: {title or path} - {result.get('message')}")
            return

        guess = result.get("guess") or {}
        if isinstance(event_data, dict):
            existing_name = str(event_data.get("name") or "").strip()
            existing_confidence = self._safe_float(event_data.get("confidence"), 0.0)
            our_confidence = self._safe_float(guess.get("confidence"), 0.0)
            # 原生识别已填充结果（有 name 且无 source_plugin），本插件作为兜底不覆盖
            if existing_name and not event_data.get("source_plugin"):
                if self._debug:
                    logger.info(f"[AI识别增强] 原生识别已填充结果，跳过兜底: {existing_name}")
                return
            # 其他插件已处理且置信度不低，不覆盖
            if event_data.get("source_plugin") and existing_confidence >= our_confidence:
                if self._debug:
                    logger.info(
                        f"[AI识别增强] 已有插件处理且置信度不低，跳过覆盖: "
                        f"{event_data.get('source_plugin')} ({existing_confidence:.2f} >= {our_confidence:.2f})"
                    )
                return
            event_data["name"] = guess.get("name", "")
            event_data["year"] = guess.get("year", "")
            event_data["season"] = guess.get("season", 0)
            event_data["episode"] = guess.get("episode", 0)
            event_data["source_plugin"] = "LLMRecognizer"
            event_data["confidence"] = guess.get("confidence", 0)
            event_data["reason"] = guess.get("reason", "")

    # ---- 识别词建议 ----

    @staticmethod
    def _normalize_media_type(value: Any) -> str:
        if value == MediaType.MOVIE:
            return "movie"
        if value == MediaType.TV:
            return "tv"
        text = str(value or "").strip().lower()
        if text in {"movie", "movies", "电影"}:
            return "movie"
        if text in {"tv", "电视剧", "剧集"}:
            return "tv"
        return "unknown"

    def _build_target(self, body: Dict[str, Any], result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = body or {}
        result = result or {}
        guess = result.get("guess") or {}
        verified = result.get("verified_media_info") or {}
        target = {
            "name": str(body.get("desired_name") or verified.get("title") or guess.get("name") or "").strip(),
            "year": str(body.get("desired_year") or verified.get("year") or guess.get("year") or "").strip(),
            "media_type": self._normalize_media_type(
                body.get("desired_media_type") or self._normalize_media_type(verified.get("type")) or guess.get("media_type")),
            "season": self._safe_int(body.get("desired_season"), self._safe_int(guess.get("season"), 0)),
            "episode": self._safe_int(body.get("desired_episode"), self._safe_int(guess.get("episode"), 0)),
            "tmdb_id": self._safe_int(body.get("desired_tmdb_id") or verified.get("tmdb_id"), 0),
        }
        if len(target["year"]) != 4 or not target["year"].isdigit():
            target["year"] = ""
        return target

    @staticmethod
    def _compact_verified_summary(verified: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        verified = verified or {}
        return {
            "title": verified.get("title"), "year": verified.get("year"),
            "type": verified.get("type"), "tmdb_id": verified.get("tmdb_id"),
            "title_year": verified.get("title_year"), "season_years": verified.get("season_years"),
            "seasons": verified.get("seasons"), "names": (verified.get("names") or [])[:8],
        }

    @staticmethod
    def _normalize_identifier_line(value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    def _validate_identifier_rule(self, rule: str) -> bool:
        rule = self._normalize_identifier_line(rule)
        if not rule or rule.startswith("#"):
            return False
        if " => " in rule or (" >> " in rule and " <> " in rule):
            return True
        return len(rule) >= 4

    def _enrich_identifier_rule(self, rule: str, target: Dict[str, Any]) -> str:
        rule = self._normalize_identifier_line(rule)
        target_name = str((target or {}).get("name") or "").strip()
        if not target_name or " => " not in rule:
            return rule
        left, right = rule.split(" => ", 1)
        suffix = ""
        replace_part = right
        if " && " in right:
            replace_part, extra = right.split(" && ", 1)
            suffix = f" && {extra}"
        if replace_part.startswith("{["):
            replace_part = f"{target_name}{replace_part}"
        return f"{left} => {replace_part}{suffix}"

    @staticmethod
    def _clean_comment_line(comment: str) -> str:
        text = str(comment or "").strip()
        if not text:
            return ""
        return f"#{text.lstrip('#').strip()}"

    def _preview_custom_words(self, title: str, custom_words: List[str],
                               target: Dict[str, Any]) -> Dict[str, Any]:
        prepared_title, apply_words = WordsMatcher().prepare(title, custom_words=custom_words)
        meta = MetaInfo(title=title, custom_words=custom_words)
        preview = {
            "prepared_title": prepared_title, "applied_words": apply_words or [],
            "applied": bool(apply_words),
            "name": getattr(meta, "name", "") or "",
            "year": getattr(meta, "year", "") or "",
            "media_type": self._normalize_media_type(getattr(meta, "type", None)),
            "season": getattr(meta, "begin_season", None) or 0,
            "episode": getattr(meta, "begin_episode", None) or 0,
        }
        if target:
            matched = True
            if target.get("name"):
                matched = matched and (preview["name"].strip().lower() == str(target["name"]).strip().lower())
            if target.get("year"):
                matched = matched and (preview["year"] == target["year"])
            if target.get("media_type") and target.get("media_type") != "unknown":
                matched = matched and (preview["media_type"] == target["media_type"])
            if target.get("season"):
                matched = matched and (preview["season"] == target["season"])
            if target.get("episode"):
                matched = matched and (preview["episode"] == target["episode"])
            preview["matched_target"] = matched
        return preview

    def _preview_identifier_rule(self, title: str, rule: str, target: Dict[str, Any]) -> Dict[str, Any]:
        preview = self._preview_custom_words(title=title, custom_words=[rule], target=target)
        preview["applied"] = rule in (preview.get("applied_words") or [])
        return preview

    def _preview_current_identifiers(self, title: str, target: Dict[str, Any]) -> Dict[str, Any]:
        custom_words = self._get_custom_identifiers()
        preview = self._preview_custom_words(title=title, custom_words=custom_words, target=target)
        preview["custom_identifier_count"] = len(custom_words)
        preview["applied_count"] = len(preview.get("applied_words") or [])
        return preview

    @staticmethod
    def _match_recognize_result_to_target(result: Dict[str, Any], target: Dict[str, Any]) -> bool:
        if not target:
            return bool(result.get("success"))
        guess = result.get("guess") or {}
        matched = bool(result.get("success"))
        if target.get("name"):
            matched = matched and (str(guess.get("name") or "").lower() == str(target.get("name") or "").lower())
        if target.get("year"):
            matched = matched and (str(guess.get("year") or "") == str(target.get("year") or ""))
        if target.get("media_type") and target.get("media_type") != "unknown":
            matched = matched and (str(guess.get("media_type") or "unknown") == str(target.get("media_type") or "unknown"))
        if target.get("season"):
            matched = matched and (int(guess.get("season") or 0) == int(target.get("season") or 0))
        if target.get("episode"):
            matched = matched and (int(guess.get("episode") or 0) == int(target.get("episode") or 0))
        return matched

    def _build_body_from_sample(self, body: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], str]:
        body = dict(body or {})
        title = str(body.get("title") or "").strip()
        path = str(body.get("path") or "").strip()
        if title or path:
            return body, None, ""
        if not (body.get("use_latest_sample") or body.get("sample_index") is not None):
            return body, None, ""
        sample_index, sample, message = self._resolve_failed_sample(body.get("sample_index"), limit=100)
        if not sample:
            return body, None, message
        body["title"] = str(sample.get("title") or "").strip()
        body["path"] = str(sample.get("path") or "").strip()
        verified = sample.get("verified_media_info") or {}
        guess = sample.get("guess") or {}
        if not body.get("desired_name"):
            body["desired_name"] = verified.get("title") or guess.get("name") or ""
        if not body.get("desired_year"):
            body["desired_year"] = verified.get("year") or guess.get("year") or ""
        if not body.get("desired_media_type"):
            body["desired_media_type"] = self._normalize_media_type(
                verified.get("type") or guess.get("media_type"))
        if body.get("desired_season") is None:
            body["desired_season"] = guess.get("season") or 0
        if body.get("desired_episode") is None:
            body["desired_episode"] = guess.get("episode") or 0
        if body.get("desired_tmdb_id") is None:
            body["desired_tmdb_id"] = verified.get("tmdb_id") or 0
        body["sample_index"] = sample_index
        return body, sample, ""

    def _build_exact_identifier_fallback(self, title: str, target: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        target_name = str((target or {}).get("name") or "").strip()
        tmdb_id = self._safe_int((target or {}).get("tmdb_id"), 0)
        media_type = self._normalize_media_type((target or {}).get("media_type"))
        if not title or not target_name or not tmdb_id or media_type == "unknown":
            return None
        replace = target_name
        target_year = str((target or {}).get("year") or "").strip()
        if len(target_year) == 4 and target_year.isdigit():
            replace += f".{target_year}"
        replace += f"{{[tmdbid={tmdb_id};type={'tv' if media_type == 'tv' else 'movie'}"
        if media_type == "tv" and self._safe_int(target.get("season"), 0):
            replace += f";s={self._safe_int(target.get('season'), 0)}"
        if media_type == "tv" and self._safe_int(target.get("episode"), 0):
            replace += f";e={self._safe_int(target.get('episode'), 0)}"
        replace += "]}"
        rule = f"{title} => {replace}"
        preview = self._preview_identifier_rule(title=title, rule=rule, target=target)
        if not preview.get("applied"):
            return None
        lines = ["#精确标题绑定规则（AI建议不可用时的兜底）", rule]
        return {"comment": "精确标题绑定规则（AI建议不可用时的兜底）",
                "comment_line": lines[0], "rule": rule, "confidence": 0.95,
                "reason": "精确匹配当前标题并强制绑定目标 TMDB / 季集，作用域最窄，稳定性最高。",
                "preview": preview, "lines": lines}

    def _suggest_identifiers(self, body: Dict[str, Any]) -> Dict[str, Any]:
        body, source_sample, sample_message = self._build_body_from_sample(body)
        if sample_message:
            return {"success": False, "message": sample_message}
        title = str(body.get("title") or "").strip()
        path = str(body.get("path") or "").strip()
        if not title and path:
            title = Path(path).name
        if not title:
            return {"success": False, "message": "标题为空"}

        result = self._recognize(title=title, path=path, record_failed_sample=False)
        target = self._build_target(body, result=result)
        invoke_error = ""
        try:
            bundle = self._invoke_identifier_llm(title=title, path=path, result=result, target=target)
        except Exception as exc:
            bundle = IdentifierSuggestionBundle(summary="识别词建议模型暂不可用，已自动回退到精确规则兜底。")
            invoke_error = str(exc)

        cleaned: List[Dict[str, Any]] = []
        for item in bundle.suggestions:
            rule = self._enrich_identifier_rule(item.rule, target=target)
            if not self._validate_identifier_rule(rule):
                continue
            comment_line = self._clean_comment_line(item.comment)
            preview = self._preview_identifier_rule(title=title, rule=rule, target=target)
            if not preview.get("applied"):
                continue
            if target and any(target.values()) and preview.get("matched_target") is False:
                continue
            cleaned.append({"comment": item.comment.strip(), "comment_line": comment_line,
                             "rule": rule, "confidence": min(1.0, max(0.0, self._safe_float(item.confidence, 0.0))),
                             "reason": str(item.reason or "").strip(), "preview": preview,
                             "lines": [l for l in [comment_line, rule] if l]})

        if not cleaned:
            fallback = self._build_exact_identifier_fallback(title=title, target=target)
            if fallback:
                if invoke_error:
                    fallback["reason"] = f"{fallback.get('reason', '')} LLM 不可用，已用精确规则兜底。".strip()
                cleaned.append(fallback)

        if not cleaned:
            return {"success": False,
                    "message": f"识别词建议生成失败: {invoke_error}" if invoke_error else "没有生成可直接使用的识别词规则",
                    "data": {"summary": bundle.summary, "target": target, "recognize_result": result}}

        return {"success": True, "message": "success",
                "data": {"summary": bundle.summary,
                         "source_sample_index": (source_sample or {}).get("sample_index"),
                         "source_sample": source_sample, "target": target,
                         "recognize_result": result, "suggestions": cleaned}}

    def _replay_failed_sample(self, body: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(body or {})
        sample_index, sample, message = self._resolve_failed_sample(body.get("sample_index"), limit=1000)
        if not sample:
            return {"success": False, "message": message}
        title = str(sample.get("title") or "").strip()
        path = str(sample.get("path") or "").strip()
        target = self._target_from_sample(sample)
        identifier_preview = self._preview_current_identifiers(title=title, target=target)
        recognize_result = self._recognize(title=title, path=path, record_failed_sample=False)
        resolved_by_id = bool(identifier_preview.get("applied")) and bool(identifier_preview.get("matched_target"))
        resolved_by_rec = self._match_recognize_result_to_target(recognize_result, target)
        resolved = resolved_by_id or resolved_by_rec
        removal_result = None
        if resolved and bool(body.get("remove_if_resolved")):
            removal_result = self._remove_failed_sample(sample_index, limit=1000)
        return {"success": True, "message": "success",
                "data": {"source_sample_index": sample_index, "source_sample": sample, "target": target,
                         "identifier_preview": identifier_preview, "recognize_result": recognize_result,
                         "resolved_by_identifiers": resolved_by_id, "resolved_by_recognizer": resolved_by_rec,
                         "resolved": resolved,
                         "sample_removed": bool(removal_result and removal_result.get("removed")),
                         "sample_removal_result": removal_result}}

    def _replay_failed_samples(self, body: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(body or {})
        limit = max(1, min(self._safe_int(body.get("limit"), 10), 50))
        selected_indexes, _, message = self._select_failed_sample_indexes(
            sample_indexes=body.get("sample_indexes"), limit=limit, pool_limit=200)
        if not selected_indexes:
            return {"success": False, "message": message}
        results: List[Dict[str, Any]] = []
        resolved_indexes: List[int] = []
        for idx in selected_indexes:
            replay = self._replay_failed_sample({"sample_index": idx, "remove_if_resolved": False})
            if not replay.get("success"):
                results.append({"sample_index": idx, "success": False, "message": replay.get("message", "复查失败")})
                continue
            data = replay.get("data") or {}
            results.append({"sample_index": idx, "success": True, "resolved": bool(data.get("resolved")),
                             "resolved_by_identifiers": bool(data.get("resolved_by_identifiers")),
                             "resolved_by_recognizer": bool(data.get("resolved_by_recognizer")),
                             "source_sample": data.get("source_sample"), "target": data.get("target"),
                             "identifier_preview": data.get("identifier_preview"),
                             "recognize_result": data.get("recognize_result")})
            if data.get("resolved"):
                resolved_indexes.append(idx)
        removal_result = None
        if body.get("remove_if_resolved") and resolved_indexes:
            removal_result = self._remove_failed_samples(resolved_indexes, limit=1000)
        success_count = sum(1 for r in results if r.get("success"))
        resolved_count = sum(1 for r in results if r.get("resolved"))
        return {"success": True, "message": "success",
                "data": {"requested_count": len(selected_indexes), "success_count": success_count,
                         "resolved_count": resolved_count, "unresolved_count": success_count - resolved_count,
                         "failed_count": len(results) - success_count,
                         "sample_removed_count": int((removal_result or {}).get("removed_count") or 0),
                         "sample_removal_result": removal_result, "results": results}}

    def _suggest_identifiers_for_failed_samples(self, body: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(body or {})
        limit = max(1, min(self._safe_int(body.get("limit"), 5), 20))
        selected_indexes, _, message = self._select_failed_sample_indexes(
            sample_indexes=body.get("sample_indexes"), limit=limit, pool_limit=200)
        if not selected_indexes:
            return {"success": False, "message": message}
        results: List[Dict[str, Any]] = []
        success_count = 0
        for idx in selected_indexes:
            suggest_body = {**body, "sample_index": idx, "use_latest_sample": False}
            suggest_body.pop("sample_indexes", None)
            suggested = self._suggest_identifiers(suggest_body)
            if suggested.get("success"):
                success_count += 1
                data = suggested.get("data") or {}
                results.append({"sample_index": idx, "success": True, "summary": data.get("summary"),
                                 "source_sample": data.get("source_sample"), "target": data.get("target"),
                                 "suggestions": data.get("suggestions") or []})
            else:
                results.append({"sample_index": idx, "success": False,
                                 "message": suggested.get("message", "建议生成失败"), "data": suggested.get("data")})
        return {"success": True, "message": "success",
                "data": {"requested_count": len(selected_indexes), "success_count": success_count,
                         "failed_count": len(selected_indexes) - success_count,
                         "brief": self._render_batch_results_brief("批量建议", len(selected_indexes),
                                                                    success_count, len(selected_indexes) - success_count, results),
                         "results": results}}

    def _apply_suggested_identifier_internal(self, body: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(body or {})
        if body.get("title") is None and body.get("path") is None:
            body.setdefault("use_latest_sample", True)
        suggested = self._suggest_identifiers(body)
        if not suggested.get("success"):
            return suggested
        data = suggested.get("data") or {}
        suggestions = data.get("suggestions") or []
        suggestion_index = max(0, self._safe_int(body.get("suggestion_index"), 0))
        if suggestion_index >= len(suggestions):
            return {"success": False, "message": f"建议索引超出范围，共 {len(suggestions)} 条"}
        chosen = suggestions[suggestion_index]
        applied = self._append_custom_identifiers(chosen.get("lines") or [])
        should_remove = bool(self._auto_remove_applied_sample if body.get("remove_sample") is None else body.get("remove_sample"))
        removal_result = None
        source_sample = data.get("source_sample") or {}
        if should_remove and source_sample.get("sample_index") is not None:
            removal_result = self._remove_failed_sample(source_sample.get("sample_index"), limit=1000)
        return {"success": True, "message": "success",
                "data": {"chosen_suggestion": chosen, "apply_result": applied,
                         "source_sample_index": source_sample.get("sample_index"),
                         "source_sample": source_sample,
                         "sample_removed": bool(removal_result and removal_result.get("removed")),
                         "sample_removal_result": removal_result, "target": data.get("target")}}

    def _apply_suggested_identifiers_for_failed_samples(self, body: Dict[str, Any]) -> Dict[str, Any]:
        body = dict(body or {})
        limit = max(1, min(self._safe_int(body.get("limit"), 5), 20))
        selected_indexes, _, message = self._select_failed_sample_indexes(
            sample_indexes=body.get("sample_indexes"), limit=limit, pool_limit=200)
        if not selected_indexes:
            return {"success": False, "message": message}
        should_remove = bool(self._auto_remove_applied_sample if body.get("remove_sample") is None else body.get("remove_sample"))
        results: List[Dict[str, Any]] = []
        success_count = 0
        removable: List[int] = []
        for idx in selected_indexes:
            apply_body = {**body, "sample_index": idx, "use_latest_sample": False, "remove_sample": False}
            apply_body.pop("sample_indexes", None)
            applied = self._apply_suggested_identifier_internal(apply_body)
            if applied.get("success"):
                success_count += 1
                data = applied.get("data") or {}
                if should_remove:
                    removable.append(idx)
                results.append({"sample_index": idx, "success": True, "source_sample": data.get("source_sample"),
                                 "target": data.get("target"), "chosen_suggestion": data.get("chosen_suggestion"),
                                 "apply_result": data.get("apply_result"), "sample_removed": False})
            else:
                results.append({"sample_index": idx, "success": False,
                                 "message": applied.get("message", "写入失败"), "data": applied.get("data")})
        removal_result = None
        if should_remove and removable:
            removal_result = self._remove_failed_samples(removable, limit=1000)
            removed_set = set((removal_result or {}).get("removed_sample_indexes") or [])
            for item in results:
                if item.get("success"):
                    item["sample_removed"] = item.get("sample_index") in removed_set
        return {"success": True, "message": "success",
                "data": {"requested_count": len(selected_indexes), "success_count": success_count,
                         "failed_count": len(selected_indexes) - success_count,
                         "sample_removed_count": int((removal_result or {}).get("removed_count") or 0),
                         "sample_removal_result": removal_result,
                         "brief": self._render_batch_results_brief("批量写入", len(selected_indexes),
                                                                    success_count, len(selected_indexes) - success_count, results),
                         "results": results}}

    # ---- 自定义识别词 I/O ----

    def _get_custom_identifiers(self) -> List[str]:
        if not self._systemconfig:
            self._systemconfig = SystemConfigOper()
        return self._systemconfig.get(SystemConfigKey.CustomIdentifiers) or []

    def _append_custom_identifiers(self, lines: List[str]) -> Dict[str, Any]:
        with self._identifiers_lock:
            existing = self._get_custom_identifiers()
            added: List[str] = []
            for line in lines:
                normalized = str(line or "").rstrip()
                if not normalized or normalized in existing or normalized in added:
                    continue
                added.append(normalized)
            if added:
                self._systemconfig.set(SystemConfigKey.CustomIdentifiers, existing + added)
            return {"added": added, "added_count": len(added),
                    "total_count": len(self._get_custom_identifiers())}

    # ---- API 端点 ----

    async def api_health(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        return {"success": True, "data": {
            "plugin_version": self.plugin_version, "enabled": self._enabled,
            "llm_ready": bool(getattr(settings, "LLM_API_KEY", None)),
            "llm_provider": getattr(settings, "LLM_PROVIDER", ""),
            "llm_model": getattr(settings, "LLM_MODEL", ""),
            "confidence_threshold": self._confidence_threshold,
            "request_timeout": self._request_timeout,
            "verify_tmdb": self._verify_tmdb,
            "require_tmdb_verify": self._require_tmdb_verify,
        }}

    async def api_recognize(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        title = str(body.get("title") or "").strip()
        path = str(body.get("path") or "").strip()
        result = self._recognize(title=title, path=path)
        return {"success": result.get("success", False), "message": result.get("message", ""),
                "data": {"guess": result.get("guess"), "verified_media_info": result.get("verified_media_info")}}

    async def api_failed_samples(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        limit = max(1, min(self._safe_int(request.query_params.get("limit"), 20), 100))
        samples = self._inject_sample_indices(self._read_failed_samples(limit=limit))
        return {"success": True, "data": {"count": len(samples), "samples": samples}}

    async def api_sample_worklist(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        limit = max(1, min(self._safe_int(request.query_params.get("limit"), 20), 100))
        samples = self._inject_sample_indices(self._read_failed_samples(limit=limit))
        return {"success": True, "data": {"count": len(samples),
                "samples": [self._summarize_sample(s) for s in samples]}}

    async def api_sample_insights(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        limit = max(1, min(self._safe_int(request.query_params.get("limit"), 50), 200))
        top = max(1, min(self._safe_int(request.query_params.get("top"), 10), 20))
        samples = self._inject_sample_indices(self._read_failed_samples(limit=limit))
        return {"success": True, "data": self._build_sample_insights(samples, top=top)}

    async def api_sample_brief(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        limit = max(1, min(self._safe_int(request.query_params.get("limit"), 5), 20))
        samples = self._inject_sample_indices(self._read_failed_samples(limit=100))
        return {"success": True, "data": {"count": len(samples),
                "text": self._render_sample_brief(samples, top=limit)}}

    async def api_suggest_identifiers(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        return self._suggest_identifiers(body)

    async def api_apply_identifiers(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        identifiers = body.get("identifiers") or []
        if not isinstance(identifiers, list):
            return {"success": False, "message": "identifiers 必须是数组"}
        return {"success": True, "message": "success",
                "data": self._append_custom_identifiers([str(l or "") for l in identifiers])}

    async def api_clear_failed_samples(self, request: Request):
        ok, message = self._check_api_access(request)
        if not ok:
            return {"success": False, "message": message}
        return {"success": True, "message": "success", "data": {"cleared_count": self._clear_failed_samples()}}

    async def api_remove_failed_sample(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        result = self._remove_failed_sample(body.get("sample_index"), limit=1000)
        if not result.get("removed"):
            return {"success": False, "message": result.get("message", "移除失败"), "data": result}
        return {"success": True, "message": "success", "data": result}

    async def api_replay_failed_sample(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        return self._replay_failed_sample(body)

    async def api_replay_failed_samples(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        return self._replay_failed_samples(body)

    async def api_suggest_identifiers_from_sample(self, request: Request):
        body = await request.json()
        body.setdefault("use_latest_sample", True)
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        return self._suggest_identifiers(body)

    async def api_suggest_identifiers_for_failed_samples(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        return self._suggest_identifiers_for_failed_samples(body)

    async def api_apply_suggested_identifier(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        return self._apply_suggested_identifier_internal(body)

    async def api_apply_suggested_identifiers_for_failed_samples(self, request: Request):
        body = await request.json()
        ok, message = self._check_api_access(request, body)
        if not ok:
            return {"success": False, "message": message}
        if not self._enabled:
            return {"success": False, "message": "插件未启用"}
        return self._apply_suggested_identifiers_for_failed_samples(body)

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {"path": "/health", "endpoint": self.api_health, "methods": ["GET"], "summary": "检查运行状态"},
            {"path": "/recognize", "endpoint": self.api_recognize, "methods": ["POST"], "summary": "LLM 识别测试"},
            {"path": "/failed_samples", "endpoint": self.api_failed_samples, "methods": ["GET"], "summary": "查看失败样本"},
            {"path": "/sample_worklist", "endpoint": self.api_sample_worklist, "methods": ["GET"], "summary": "失败样本摘要列表"},
            {"path": "/sample_insights", "endpoint": self.api_sample_insights, "methods": ["GET"], "summary": "失败样本统计分析"},
            {"path": "/sample_brief", "endpoint": self.api_sample_brief, "methods": ["GET"], "summary": "失败样本精简摘要"},
            {"path": "/suggest_identifiers", "endpoint": self.api_suggest_identifiers, "methods": ["POST"], "summary": "生成识别词建议"},
            {"path": "/suggest_identifiers_from_sample", "endpoint": self.api_suggest_identifiers_from_sample, "methods": ["POST"], "summary": "基于样本生成识别词建议"},
            {"path": "/suggest_identifiers_for_failed_samples", "endpoint": self.api_suggest_identifiers_for_failed_samples, "methods": ["POST"], "summary": "批量生成识别词建议"},
            {"path": "/apply_identifiers", "endpoint": self.api_apply_identifiers, "methods": ["POST"], "summary": "追加写入 CustomIdentifiers"},
            {"path": "/clear_failed_samples", "endpoint": self.api_clear_failed_samples, "methods": ["POST"], "summary": "清空失败样本"},
            {"path": "/remove_failed_sample", "endpoint": self.api_remove_failed_sample, "methods": ["POST"], "summary": "移除单条失败样本"},
            {"path": "/replay_failed_sample", "endpoint": self.api_replay_failed_sample, "methods": ["POST"], "summary": "复查单条失败样本"},
            {"path": "/replay_failed_samples", "endpoint": self.api_replay_failed_samples, "methods": ["POST"], "summary": "批量复查失败样本"},
            {"path": "/apply_suggested_identifier", "endpoint": self.api_apply_suggested_identifier, "methods": ["POST"], "summary": "写入建议识别词并移除样本"},
            {"path": "/apply_suggested_identifiers_for_failed_samples", "endpoint": self.api_apply_suggested_identifiers_for_failed_samples, "methods": ["POST"], "summary": "批量写入建议识别词"},
        ]

    def get_page(self) -> List[dict]:
        llm_ready = bool(getattr(settings, "LLM_API_KEY", None))
        samples = self._read_failed_samples(limit=20)
        failed_count = len(self._read_failed_samples(limit=200))
        id_count = len(self._get_custom_identifiers())

        def stat_card(title: str, value: Any, subtitle: str = "") -> dict:
            content = [
                {"component": "div", "props": {"class": "text-caption text-medium-emphasis mb-1"}, "text": title},
                {"component": "div", "props": {"class": "text-h6 font-weight-bold"}, "text": str(value)},
            ]
            if subtitle:
                content.append({"component": "div", "props": {"class": "text-caption text-medium-emphasis mt-1"}, "text": subtitle})
            return {"component": "VCard", "props": {"variant": "tonal", "class": "pa-4 h-100"}, "content": content}

        _reason_map = {
            "low_confidence_or_empty_name": "低置信度",
            "llm_error": "LLM错误",
        }

        def _fmt_reason(reason: Any) -> str:
            tag = self._normalize_reason_tag(reason)
            return _reason_map.get(tag, tag)

        sample_rows = []
        for s in samples:
            summary = self._summarize_sample(s)
            conf = summary.get("guess_confidence", 0.0)
            sample_rows.append({
                "title": summary.get("title") or "-",
                "guess": summary.get("guess_name") or "-",
                "confidence": f"{conf:.0%}" if conf else "-",
                "reason": _fmt_reason(summary.get("reason")),
            })

        samples_section = {"component": "VRow", "props": {"class": "mt-2"}, "content": [
            {"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VCard", "props": {"variant": "outlined"}, "content": [
                    {"component": "VCardTitle", "props": {"class": "text-subtitle-2 pa-3 pb-1"},
                     "text": f"最近识别失败样本（共 {failed_count} 条，显示最新 {len(sample_rows)} 条）"},
                    {"component": "VDivider"},
                    {"component": "VDataTable", "props": {
                        "headers": [
                            {"title": "原始标题", "key": "title", "sortable": False},
                            {"title": "LLM猜测名", "key": "guess", "sortable": False},
                            {"title": "置信度", "key": "confidence", "sortable": False, "width": "80px"},
                            {"title": "原因", "key": "reason", "sortable": False, "width": "100px"},
                        ],
                        "items": sample_rows,
                        "density": "compact",
                        "items-per-page": -1,
                        "hide-default-footer": True,
                        "no-data-text": "暂无失败样本",
                    }},
                ]},
            ]},
        ]}

        return [{"component": "VContainer", "props": {"fluid": True, "class": "pa-0"}, "content": [
            {"component": "VAlert", "props": {"type": "info", "variant": "tonal", "class": "mb-4",
             "title": "本地 LLM 识别兜底",
             "text": "复用 MoviePilot 当前 LLM 配置，在原生识别失败时做结构化兜底，并把结果交回 MoviePilot 继续二次识别。"}},
            {"component": "VRow", "props": {"dense": True, "class": "mb-2"}, "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [stat_card("当前状态", "已启用" if self._enabled else "未启用")]},
                {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [stat_card("LLM", "可用" if llm_ready else "未配置",
                    f"{getattr(settings,'LLM_PROVIDER','-')} / {getattr(settings,'LLM_MODEL','-')}")]},
                {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [stat_card("失败样本", f"{failed_count} 条", f"上限 {self._max_failed_samples} 条")]},
                {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [stat_card("自定义识别词", f"{id_count} 条", "系统 CustomIdentifiers")]},
            ]},
            samples_section,
        ]}]

    @staticmethod
    def get_render_mode() -> Tuple[str, Optional[str]]:
        return "vuetify", None

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        form = [{"component": "VForm", "content": [
            {"component": "VRow", "content": [{"component": "VCol", "props": {"cols": 12}, "content": [
                {"component": "VAlert", "props": {"type": "info", "variant": "tonal",
                 "text": "复用 MoviePilot 当前启用的 LLM 配置，在原生识别失败后做本地结构化兜底。默认不启用 TMDB 二次校验（避免 500 日志噪音）。"}}]}]},
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用 AI识别增强"}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "debug", "label": "调试模式"}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "save_failed_samples", "label": "保存识别失败样本", "hint": "LLM调用失败或置信度不足时保存样本，供后续生成识别词", "persistent-hint": True}}]},
            ]},
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "verify_tmdb", "label": "启用 TMDB 二次校验", "hint": "关闭可消除「共享媒体识别失败」500 日志噪音", "persistent-hint": True}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "require_tmdb_verify", "label": "要求 TMDB 校验通过才注入", "hint": "需同时开启「TMDB 二次校验」", "persistent-hint": True}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "auto_remove_applied_sample", "label": "写入识别词后自动移除样本"}}]},
            ]},
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VTextField", "props": {"model": "confidence_threshold", "label": "置信度阈值", "type": "number", "hint": "低于该值不注入，默认 0.65", "persistent-hint": True}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VTextField", "props": {"model": "request_timeout", "label": "LLM 请求超时（秒）", "type": "number", "hint": "默认 25 秒", "persistent-hint": True}}]},
                {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VTextField", "props": {"model": "max_retries", "label": "结构化输出重试次数", "type": "number", "hint": "默认 2 次", "persistent-hint": True}}]},
            ]},
            {"component": "VRow", "content": [
                {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VTextField", "props": {"model": "max_failed_samples", "label": "失败样本保留上限", "type": "number", "hint": "默认 200 条，重复样本自动去重", "persistent-hint": True}}]},
            ]},
        ]}]
        return form, {
            "enabled": False, "debug": False, "confidence_threshold": 0.65,
            "request_timeout": 25, "max_retries": 2, "save_failed_samples": True,
            "max_failed_samples": 200, "auto_remove_applied_sample": True,
            "verify_tmdb": False, "require_tmdb_verify": False,
        }
