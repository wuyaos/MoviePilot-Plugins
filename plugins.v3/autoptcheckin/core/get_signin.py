"""Single action GET, reusing Nexus safe pre-read and unconditional readback."""
from urllib.parse import urljoin

from .nexus import NexusSignin, SigninForm


class GetSignin(NexusSignin):
    action_path: str
    action_referer: bool = False

    def discover_form(self, ctx, page):
        return SigninForm(urljoin(self.url, self.action_path), [],
                          self.url if self.action_referer else None)

    def submit(self, ctx, form):
        kwargs = {"referer": form.referer} if form.referer else {}
        ctx.http.get(form.action, **kwargs)
