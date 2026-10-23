"""Shared form-post transport for Cookie-authenticated Discuz sign-in pages."""
from ..core.credentials import CredentialSpec

class DiscuzPageAdapter:
    credential_spec = CredentialSpec()
    login_capable = False
    verifier = None
    base = ""
    page_path = ""
    submit_path = ""
    form_fields = {}

    def __init__(self, client):
        self.client = client

    def fetch_page(self):
        return self.client.request("GET", self.page_path).text

    def submit(self, page):
        fields = {**self.form_fields, "formhash": self.verifier.token(page)}
        return self.client.request("POST", self.submit_path, data=fields)
