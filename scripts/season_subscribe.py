#!/usr/bin/env python
"""Yuc 季度清单逐部核对、逐季订阅；默认只预览，不写 MoviePilot。"""
from __future__ import annotations

import json
import argparse
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

console = Console(markup=False, highlight=False)
log = logging.getLogger("season_subscribe")


@dataclass
class Anime:
    title: str
    original: str = ""
    kind: str = ""
    weekday: str = ""
    air_date: str = ""
    air_time: str = ""
    region: str = ""
    network_release: bool = False
    warnings: list[str] = field(default_factory=list)
    year: int | None = None


def normalized(value: str) -> str:
    # 保留数字及季标记：不能把续作归一成第一季。
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", value).casefold())


def text(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def first_class(node, prefix: str):
    return node.find(class_=lambda value: value and value.startswith(prefix))


def parse_yuc(html: str) -> tuple[list[Anime], int, list[str]]:
    """按 intro 计数和 title_main* 表格边界解析，不按开播月份过滤。"""
    soup = BeautifulSoup(html, "html.parser")
    intro = next((p for p in soup.select(".intro")
                  if re.search(r"本期.*共收录\s*\d+\s*部新番动画", text(p))), None)
    if intro is None:
        raise ValueError("找不到本期共收录声明；停止，避免把放送表当主列表")
    declared = int(re.search(r"共收录\s*(\d+)", text(intro)).group(1))
    schedule = {}
    weekday = ""
    network = False
    for node in soup.find_all(True):
        if node is intro:
            break
        classes = node.get("class", [])
        if "date2" in classes:
            heading = text(node)
            network = "网络放送" in heading
            weekday = heading if not network else ""
        if not any(c.startswith("date_title") for c in classes):
            continue
        card = next((p for p in node.parents if p.name == "div"
                     and "float" in p.get("style", "")), node.find_parent("table"))
        raw = text(card)
        date = re.search(r"\d{1,2}/\d{1,2}", raw)
        time = re.search(r"\d{1,2}:\d{2}", raw)
        schedule.setdefault(normalized(text(node)), []).append({
            "weekday": weekday, "air_date": date.group() if date else "",
            "air_time": time.group() if time else "",
            "region": " / ".join(dict.fromkeys(text(p) for p in card.select(".area"))),
            "network_release": network,
        })
    entries, warnings, seen = [], [], set()
    blocks = intro.find_all_next(class_=lambda v: v and v.startswith("title_main"))
    if len(blocks) != declared:
        warnings.append(f"页面声明 {declared} 部，发现 {len(blocks)} 个详细条目")
    # N 是主列表边界；超出的结构只报警，不把后面的其他推荐混入。
    for index, node in enumerate(blocks[:declared], 1):
        table = node.find_parent("table")
        cn, jp = text(first_class(node, "title_cn")), text(first_class(node, "title_jp"))
        entry = Anime(cn or jp or f"[缺失标题 #{index}]", jp,
                      text(first_class(table, "type_a")))
        if not cn:
            entry.warnings.append("中文标题缺失" if jp else "全部标题缺失，请手动检索")
        key = normalized(jp or cn)
        if key and key in seen:
            warnings.append(f"重复详细作品：{entry.title}（已合并）")
            continue
        seen.add(key)
        matches = schedule.get(normalized(cn), []) or schedule.get(normalized(jp), [])
        if len(matches) == 1:
            for name, value in matches[0].items():
                setattr(entry, name, value)
        elif len(matches) > 1:
            entry.warnings.append("放送表同名多条，未自动合并放送信息")
        broadcast = text(first_class(table, "broadcast"))
        if not entry.air_date:
            match = re.search(r"\d{1,2}/\d{1,2}", broadcast)
            entry.air_date = match.group() if match else ""
        if not entry.year:
            match = re.search(r"(20\d{2})", text(table))
            entry.year = int(match.group(1)) if match else None
        entry.network_release |= "网络放送" in broadcast
        entries.append(entry)
    if len(entries) != declared:
        warnings.append(f"去重后 {len(entries)} 部，与声明 {declared} 不一致")
    return entries, declared, warnings


def request(client, method: str, path: str, **kwargs):
    """错误不回显 URL、响应正文或 headers，避免凭据泄漏。"""
    try:
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"HTTP {exc.response.status_code}") from None
    except (httpx.RequestError, ValueError):
        raise ValueError("网络超时/连接失败或响应不是 JSON") from None


def ask(prompt: str) -> str:
    answer = console.input(prompt + " ").strip()
    if answer.casefold() == "q":
        raise SystemExit(0)
    return answer


def confirm(prompt: str) -> bool:
    return ask(prompt + " [y/N/q]").casefold() == "y"


def choose(candidates: list[dict], label: str) -> dict:
    if not candidates:
        console.print(f"{label}：无候选")
        return {}
    console.print(f"{label} 候选（包括精确同名也请核对续作；0 跳过）")
    for index, item in enumerate(candidates, 1):
        console.print(f"{index}. {item.get('name_cn') or item.get('name')} | "
                      f"{item.get('name')} | {item.get('date', '')} | "
                      f"{item.get('format', '')} | ID {item.get('id')}")
        console.print("别名：" + " / ".join(item.get("aliases", [])))
    while True:
        value = ask("选择候选编号 [0/q]：")
        if value in ("", "0"):
            return {}
        if value.isdigit() and 1 <= int(value) <= len(candidates):
            return candidates[int(value) - 1]


def name_score(item: dict, anime: Anime) -> int:
    """名称匹配分：完全一致 4，互含 2，无匹配 0。"""
    names = {normalized(anime.title), normalized(anime.original)} - {""}
    fields = {normalized(item.get("name_cn") or ""), normalized(item.get("name") or "")}
    fields |= {normalized(alias) for alias in item.get("aliases", [])}
    fields -= {""}
    if names & fields:
        return 4
    if any(len(n) >= 3 and (n in f or f in n) for n in names for f in fields):
        return 2
    return 0


def match_score(item: dict, anime: Anime) -> int:
    """名称(4) > 年份(2) > 类型(1) 综合评分。"""
    score = name_score(item, anime)
    year = str(item.get("date") or "")[:4]
    if anime.year and year.isdigit():
        gap = abs(int(year) - anime.year)
        score += 2 if gap == 0 else 1 if gap <= 1 else 0
    fmt = str(item.get("format") or "").upper()
    kind = (anime.kind or "").upper()
    if fmt in ("TV", "TV_SHORT", "电视剧") or (fmt and kind and (fmt in kind or kind in fmt)):
        score += 1
    return score


def auto_match(items: list[dict], anime: Anime, label: str) -> dict | None:
    """唯一明显领先且名称对得上才自动选；None 表示需要人工。"""
    if not items:
        return None
    scored = sorted(((match_score(item, anime) + max(0, 3 - index), item)
                     for index, item in enumerate(items, 1)),
                    key=lambda pair: pair[0], reverse=True)
    top_score, top = scored[0]
    second = scored[1][0] if len(scored) > 1 else -1
    if top_score >= 5 and top_score - second >= 2 and name_score(top, anime) >= 2:
        console.print(f"{label} 自动匹配：{top.get('name_cn') or top.get('name')} | "
                      f"{top.get('name')} | {top.get('date', '')} | {top.get('format', '')} "
                      f"| ID {top.get('id')}（匹配分 {top_score}）", style="cyan")
        return top
    return None


def aliases_of(subject: dict) -> list[str]:
    aliases = []
    for entry in subject.get("infobox", []) or []:
        if entry.get("key") in ("别名", "中文名", "中文译名", "英文名"):
            value = entry.get("value", [])
            aliases.extend([value] if isinstance(value, str)
                           else [str(v.get("v", "")) for v in value])
    return [alias for alias in aliases if alias]


def bgm_subject(client, item: dict) -> dict:
    subject = request(client, "GET", f"https://api.bgm.tv/v0/subjects/{int(item['id'])}")
    subject["aliases"] = aliases_of(subject)
    subject["format"] = subject.get("platform") or item.get("format") or ""
    return subject


def enrich(client, anime: Anime) -> tuple[dict, dict]:
    queries = list(dict.fromkeys(q for q in (anime.original, anime.title) if q))
    bgm, ani = {}, {}
    try:
        items, seen = [], set()
        for query in queries:
            found = request(client, "POST", "https://api.bgm.tv/v0/search/subjects",
                            params={"limit": 8}, json={"keyword": query, "filter": {"type": [2]}})
            for item in found.get("data", []) or []:
                if item.get("id") in seen:
                    continue
                seen.add(item.get("id"))
                entry = dict(item)
                entry["format"] = item.get("platform") or ""
                items.append(entry)
        pick = auto_match(items, anime, "Bangumi")
        if pick is None and items:
            # 检索结果名称弱匹配（如罗马音对片假名）时，拉详情用别名复核。
            for item in items[:3]:
                detail = bgm_subject(client, item)
                if name_score(detail, anime) >= 4 and match_score(detail, anime) >= 6:
                    console.print(f"Bangumi 自动匹配（别名复核）：{detail.get('name_cn') or detail.get('name')} "
                                  f"| {detail.get('name')} | {detail.get('date', '')} | ID {detail.get('id')}", style="cyan")
                    pick = detail
                    break
        if pick is None:
            pick = choose(items, "Bangumi")
        if pick:
            bgm = pick if "aliases" in pick else bgm_subject(client, pick)
    except (ValueError, KeyError, TypeError, AttributeError):
        log.warning("Bangumi 补充失败：网络/HTTP 状态或数据结构异常；可继续")
    try:
        result = request(client, "POST", "https://graphql.anilist.co", json={
            "query": "query($search:String){Page(perPage:8){media(search:$search,type:ANIME){id title{romaji english native} synonyms format description averageScore startDate{year month day}}}}",
            "variables": {"search": bgm.get("name") or (queries[0] if queries else "")}})
        if result.get("errors"):
            raise ValueError("GraphQL 返回错误")
        candidates = []
        for item in result["data"]["Page"]["media"]:
            title = item.get("title") or {}
            candidates.append({**item, "name": title.get("native") or title.get("romaji"),
                               "aliases": [v for v in title.values() if v] + (item.get("synonyms") or []),
                               "date": str(item.get("startDate", {}).get("year") or "")})
        pick = auto_match(candidates, anime, "AniList")
        ani = pick if pick is not None else choose(candidates, "AniList")
    except (ValueError, KeyError, TypeError, AttributeError):
        log.warning("AniList 补充失败：网络/HTTP 状态或数据结构异常；可继续")
    return bgm, ani


def display_title(anime: Anime, bgm: dict, ani: dict) -> str:
    # AniList 没有独立中文字段；native 是本地标题，可能是日文，不冒称中文译名。
    return (bgm.get("name_cn") or (ani.get("title") or {}).get("native")
            or anime.title or bgm.get("name") or anime.original or ani.get("name") or "未知标题")


def score(value, maximum: int) -> str:
    return f"{value} / {maximum}" if value and float(value) > 0 else "暂无"


class MoviePilot:
    """适配本地 MoviePilot-v3 的 REST 身份对及统一响应信封。"""
    def __init__(self, client, apply: bool = False):
        self.client = client
        self.apply = apply

    def call(self, method: str, path: str, **kwargs):
        data = request(self.client, method, path, **kwargs)
        if isinstance(data, dict) and "success" in data:
            if not data["success"]:
                raise ValueError("MP 返回失败（请在 MP 中查看详情）")
            return data.get("data")
        return data

    def recognize(self, title: str) -> dict:
        result = self.call("GET", "media/recognize", params={"title": title})
        return (result or {}).get("media_info") or {}

    def seasons(self, media: dict) -> list:
        return self.call("GET", "media/seasons", params=identity(media))

    def subscriptions(self) -> list:
        # 不传 page/count 是宿主显式支持的全量兼容模式。
        result = self.call("GET", "subscribe/")
        if not isinstance(result, list):
            raise ValueError("MP 订阅列表结构异常；不允许假定未订阅")
        return result

    def create(self, payload: dict, confirmed: bool = False):
        if not self.apply or not confirmed:
            return {"dry_run": True}
        return self.call("POST", "subscribe/", json=payload)


def identity(media: dict) -> dict:
    source, media_id = media.get("media_source"), media.get("media_id")
    if not source or not media_id:
        raise ValueError("MP 未返回 media_source/media_id；不能安全订阅")
    return {"media_source": source, "media_id": str(media_id)}


def existing(subscriptions: list, media: dict, season: int) -> list:
    wanted = identity(media)
    return [s for s in subscriptions if s.get("media_source") == wanted["media_source"]
            and str(s.get("media_id")) == wanted["media_id"]
            and s.get("season") == season]


def select_seasons(value: str, available: list[int]) -> list[int]:
    if value in ("", "0"):
        return []
    if value.casefold() == "all":
        return available[:]
    try:
        chosen = list(dict.fromkeys(int(v.strip().lower().removeprefix("s")) for v in value.split(",")))
    except ValueError:
        raise ValueError("请输入季号，如 2,3 / S00 / all / 0") from None
    if not set(chosen) <= set(available):
        raise ValueError("包含不可选或已订阅的季号")
    return chosen


def recognize_any(mp: MoviePilot, queries: list[str]) -> tuple[dict, str]:
    """依次尝试主标题、原名与别名，返回第一个识别成功的结果。"""
    for query in dict.fromkeys(q for q in queries if q):
        media = mp.recognize(query)
        if media:
            return media, query
    return {}, ""


def subscribe_anime(mp: MoviePilot, anime: Anime, bgm: dict, ani: dict):
    title = display_title(anime, bgm, ani)
    summary = bgm.get("summary") or text(BeautifulSoup(ani.get("description") or "", "html.parser"))
    console.rule(title)
    console.print(f"Yuc 中文标题：{anime.title}")
    console.print(f"原名：{bgm.get('name') or anime.original or ani.get('name') or '暂无'}")
    console.print("别名：" + " / ".join(bgm.get("aliases", []) + ani.get("aliases", [])))
    console.print(f"类型：{ani.get('format') or anime.kind or '暂无'}")
    console.print(f"Bangumi：{score((bgm.get('rating') or {}).get('score'), 10)} | ID {bgm.get('id', '暂无')}")
    console.print(f"AniList：{score(ani.get('averageScore'), 100)} | ID {ani.get('id', '暂无')}")
    console.print(f"放送：{anime.weekday} {anime.air_date} {anime.air_time} | 地区：{anime.region or '暂无'} | 网络/其他：{anime.network_release}")
    console.print(summary or "简介：暂无")
    for warning in anime.warnings:
        console.print("警告：" + warning, style="yellow")
    queries = [title, bgm.get("name"), anime.original, ani.get("name"),
               *bgm.get("aliases", [])[:3], *ani.get("aliases", [])[:3]]
    media, used = recognize_any(mp, queries)
    if not media:
        console.print("MP 未识别到结果（已尝试主标题、原名与别名）；本部跳过，可稍后在 MP 中手动检索",
                      style="bold yellow")
        return
    console.print(f"MP 匹配（检索词 {used}）：{media.get('title')} ({media.get('year')}) "
                  f"| {media.get('type')} | {identity(media)}", style="bold green")
    media_year = str(media.get("year") or "")[:4]
    if anime.year and media_year.isdigit() and abs(int(media_year) - anime.year) > 1:
        console.print(f"警告：MP 年份 {media_year} 与季度年份 {anime.year} 相差较大，注意续作/重制版", style="yellow")
    if media.get("type") not in ("电视剧", "tv", "TV"):
        console.print("不是电视剧；本工具仅按季订阅，跳过", style="bold yellow")
        return
    if not confirm("确认这是目标作品（注意续作/重制版）？"):
        return
    seasons = mp.seasons(media)
    subscriptions = mp.subscriptions()
    table = Table("季", "名称", "首播/年份", "订阅状态/信息")
    available = []
    for season in seasons:
        number = season.get("season_number")
        if not isinstance(number, int) or number < 0:
            raise ValueError("MP 季信息缺少非负整数 season_number")
        matches = existing(subscriptions, media, number)
        status = "; ".join(f"已订阅 ID={s.get('id')} 状态={s.get('state')} 用户={s.get('username')} 缺集={s.get('lack_episode')}" for s in matches)
        table.add_row(f"S{number:02}", str(season.get("name") or ""), str(season.get("air_date") or season.get("year") or "暂无"), status or "未订阅")
        if not matches:
            available.append(number)
    console.print(table)
    while True:
        try:
            selected = select_seasons(ask("多选未订阅季号：2,3 / S00 / all / 0 跳过 / q："), available)
            break
        except ValueError as exc:
            console.print(str(exc))
    if not selected:
        return
    console.print(f"{'真实提交' if mp.apply else 'DRY-RUN 预览'}：{media.get('title')} " + ", ".join(f"S{s:02}" for s in selected),
                  style="bold red" if mp.apply else "bold cyan")
    if not confirm("统一确认以上季？"):
        return
    for number in selected:
        try:
            if existing(mp.subscriptions(), media, number):
                console.print(f"S{number:02} 已订阅，跳过")
                continue
            payload = {**identity(media), "name": media.get("title") or title,
                       "year": str(media.get("year") or ""), "type": "电视剧", "season": number}
            result = mp.create(payload, confirmed=True)
            console.print(f"S{number:02} " + ("DRY-RUN：未发送 POST" if not mp.apply else f"提交成功 ID={(result or {}).get('id')}"))
        except (ValueError, TypeError, AttributeError):
            console.print(f"S{number:02} 请求失败或响应异常；不自动重试，请在 MP 核查是否已创建")


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="JSON 配置文件；命令行参数优先")
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int, choices=[1, 4, 7, 10], help="季度起始月")
    parser.add_argument("--yuc-url")
    parser.add_argument("--mp-url", help="MP 根 URL（不含 /api/v1）")
    parser.add_argument("--mp-api-key-file", type=Path, help="否则读取配置、MP_API_KEY")
    parser.add_argument("--proxy", default=None, help="仅公开上游代理，如 http://127.0.0.1:7890")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", default=None, help="允许真实 POST，仍需交互确认")
    mode.add_argument("--dry-run", action="store_true", default=None, help="默认模式，不创建订阅")
    args = parser.parse_args(argv)

    config = {}
    if args.config:
        try:
            config = json.loads(args.config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"配置文件读取失败：{exc}")
        if not isinstance(config, dict):
            parser.error("配置文件必须是 JSON 对象")

    def value(name, config_name=None, default=None):
        current = getattr(args, name)
        return current if current is not None else config.get(config_name or name, default)

    args.year = value("year")
    args.month = value("month")
    args.yuc_url = value("yuc_url", default="")
    args.mp_url = value("mp_url")
    args.mp_api_key_file = value("mp_api_key_file")
    if isinstance(args.mp_api_key_file, str):
        args.mp_api_key_file = Path(args.mp_api_key_file)
    args.mp_api_key = config.get("mp_api_key", "")
    args.proxy = value("proxy", default=os.getenv("HTTPS_PROXY"))
    args.apply = args.apply if args.apply is not None else bool(config.get("apply", False))
    args.dry_run = args.dry_run if args.dry_run is not None else not args.apply

    if not args.mp_url:
        parser.error("提供 --mp-url 或在配置文件中填写 mp_url")
    if not args.yuc_url and not (args.year and args.month):
        parser.error("提供 --year 和 --month，或 --yuc-url/配置中的 yuc_url")
    return args


def main(argv=None) -> int:
    args = arguments(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    try:
        key = (args.mp_api_key.strip() or (args.mp_api_key_file.read_text(encoding="utf-8").strip() if args.mp_api_key_file else os.getenv("MP_API_KEY", "").strip()))
        if not key:
            raise ValueError("请提供 MP_API_KEY 或 --mp-api-key-file")
        parsed = urlsplit(args.mp_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("MP URL 必须是无凭据、无查询参数的 http(s) 地址")
        url = args.yuc_url or f"https://yuc.wiki/{args.year:04}{args.month:02}/"
        with httpx.Client(proxy=args.proxy, timeout=25, follow_redirects=True, trust_env=False,
                          headers={"User-Agent": "season-subscribe/1.0 (interactive personal CLI)"}) as public, \
             httpx.Client(base_url=args.mp_url.rstrip("/") + "/api/v1/", timeout=30,
                          trust_env=False, follow_redirects=False, headers={"X-API-KEY": key}) as private:
            try:
                response = public.get(url)
                response.raise_for_status()
            except httpx.HTTPError:
                raise ValueError("Yuc 请求失败，请检查 URL、代理及网络") from None
            entries, declared, warnings = parse_yuc(response.text)
            console.print(f"季度：{args.year or 'URL 指定'} / {args.month or 'URL 指定'}；声明 {declared} 部，解析 {len(entries)} 部")
            for warning in warnings:
                console.print("警告：" + warning)
            if warnings and not confirm("数量/重复异常，仍继续？"):
                return 0
            mp = MoviePilot(private, apply=args.apply)
            console.print("APPLY：允许真实订阅" if args.apply else "DRY-RUN：不会创建订阅")
            for index, anime in enumerate(entries, 1):
                if not anime.year:
                    anime.year = args.year
                console.rule(f"{index}/{len(entries)} {anime.title}")
                bgm, ani = enrich(public, anime)
                try:
                    subscribe_anime(mp, anime, bgm, ani)
                except (ValueError, TypeError, KeyError, AttributeError):
                    console.print("MP 请求失败或响应结构不兼容；本部停止，请检查服务及 API 版本")
        return 0
    except (OSError, ValueError):
        console.print("运行失败：请检查依赖、密钥文件、URL、代理或 Yuc 页面结构（不回显敏感内容）")
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        console.print("已退出；未发送的季不会提交，已提交的订阅不会回滚")
        raise SystemExit(0)
