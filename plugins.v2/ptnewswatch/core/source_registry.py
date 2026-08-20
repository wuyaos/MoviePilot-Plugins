"""PTNewsWatch 固定来源注册表。"""
from .models import SourceAuthMode, SourceKind, SourceSpec


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        source_id="pter_digest",
        site_id="pterclub",
        title="PTerClub 动态汇总帖",
        kind=SourceKind.NEXUS_TOPIC,
        url="https://pterclub.net/forums.php?action=viewtopic&topicid=2327&page=last#last",
        auth_mode=SourceAuthMode.MP_SITE_COOKIE,
        site_domain="pterclub.net",
    ),
    SourceSpec(
        source_id="tjupt_digest",
        site_id="tjupt",
        title="TJUPT 开放注册汇总帖",
        kind=SourceKind.NEXUS_TOPIC,
        url="https://www.tjupt.org/forums.php?action=viewtopic&topicid=15461&page=last#last",
        auth_mode=SourceAuthMode.MP_SITE_COOKIE,
        site_domain="tjupt.org",
    ),
    SourceSpec(
        source_id="fengchao_pt",
        site_id="fengchao",
        title="蜂巢 · PT生态",
        kind=SourceKind.RSS,
        url="https://pting.club/boards/pt/rss.xml",
        auth_mode=SourceAuthMode.PUBLIC,
        site_domain="pting.club",
    ),
    SourceSpec(
        source_id="fengchao_invites",
        site_id="fengchao",
        title="蜂巢 · PT邀请专区",
        kind=SourceKind.RSS,
        url="https://pting.club/boards/pt-invites/rss.xml",
        auth_mode=SourceAuthMode.PUBLIC,
        site_domain="pting.club",
    ),
    SourceSpec(
        source_id="invites_pt_fy",
        site_id="invites",
        title="药丸 · PT_FY 标签活动",
        kind=SourceKind.ATOM,
        url="https://invites.fun/atom/t/PT_FY",
        auth_mode=SourceAuthMode.INVITES_COOKIE,
        site_domain="invites.fun",
    ),
)

SOURCE_BY_ID = {source.source_id: source for source in SOURCES}
