from __future__ import annotations
import base64
import requests
from typing import Any, Dict
from tenacity import retry, wait_exponential, stop_after_attempt

BASE_URL = "https://api.affinity.co"

class AffinityV1:
    """
    Minimal v1 client for create actions. v1 uses Basic auth with the API key as the username.
    This file implements *common* create flows used in older integrations.
    Adjust payloads/paths to match your tenant's v1 schema if needed.
    """
    def __init__(self, api_key: str | None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            b64 = base64.b64encode(f"{api_key}:".encode()).decode()
            self.session.headers.update({"Authorization": f"Basic {b64}"})
        self.session.headers.update({"Content-Type": "application/json"})

    def _check(self):
        if not self.api_key:
            raise RuntimeError("Affinity v1 key missing")

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _req(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        self._check()
        url = f"{BASE_URL}{path}"
        r = self.session.request(method, url, timeout=30, **kwargs)
        if r.status_code >= 400:
            raise RuntimeError(f"Affinity v1 error {r.status_code}: {r.text}")
        return r.json() if r.text else {}

    # ---- Create Company (Organization)
    def create_company(self, name: str, domain: str | None = None, website: str | None = None):
        # Common legacy path for organizations
        body = {"name": name}
        if domain:
            body["domain"] = domain
        if website:
            body["website"] = website
        return self._req("POST", "/organizations", json=body)

    # ---- Add a Note attached to a Company
    def create_company_note(self, company_id: int, html: str):
        # Common legacy path for notes; some tenants use 'content' or 'note_html'
        body = {"entity_type": "organization", "entity_id": company_id, "content": html}
        return self._req("POST", "/notes", json=body)

    # ---- Add Company to List (create list entry)
    def add_company_to_list(self, list_id: int, company_id: int):
        body = {"entity_id": company_id, "entity_type": "organization"}
        return self._req("POST", f"/lists/{list_id}/list-entries", json=body)
