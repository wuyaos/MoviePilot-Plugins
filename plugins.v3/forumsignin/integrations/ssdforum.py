from ..verifiers.ssdforum import SSDForumVerifier
from .discuz import DiscuzPageAdapter

class SSDForum(DiscuzPageAdapter):
    verifier = SSDForumVerifier()
    base = "https://ssdforum.org"
    page_path = "/dsu_paulsign-sign.html?mobile=no"
    submit_path = "/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1"
    form_fields = {"qdxq":"kx", "qdmode":"1", "todaysay":"愿今天也是充实而愉快的一天。", "fastreply":"0"}

SITE = {"id":"ssdforum", "name":"SSDForum", "domain":"ssdforum.org", "source":"插件适配",
        "signin_capable":True, "login_capable":False,
        "fields":[{"key":"ssdforum_cookie","label":"Cookie","type":"password"}]}
ADAPTER = SSDForum
