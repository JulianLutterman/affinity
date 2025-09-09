from __future__ import annotations
import requests
from typing import Any, Dict

BASE_URL = "https://api.affinity.co"

class AffinityV2:
    def __init__(self, api_key: str | None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
        self.session.headers.update({"Content-Type": "application/json"})

    def _check(self):
        if not self.api_key:
            raise RuntimeError("Affinity v2 bearer key missing")

    def _req(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """
        Single-shot request (no blanket retries).
        We surface 4xx errors directly so users see permission/validation messages.
        """
        self._check()
        url = f"{BASE_URL}{path}"
        r = self.session.request(method, url, timeout=30, **kwargs)
        if r.status_code < 400:
            return r.json() if r.text else {}

        # Helpful error messages:
        body = r.text
        if r.status_code == 401:
            raise RuntimeError(f"Affinity v2 401 Unauthorized. Check your bearer token. Body: {body}")
        if r.status_code == 403:
            # Common case when calling GET /v2/companies without permission
            if path.startswith("/v2/companies"):
                raise PermissionError(
                    "Affinity v2 403 Forbidden when calling /v2/companies. "
                    "Your key likely lacks the 'Export All Organizations directory' permission required by this endpoint."
                )
            raise PermissionError(f"Affinity v2 403 Forbidden for {path}. Body: {body}")
        if r.status_code == 429:
            raise RuntimeError(f"Affinity v2 429 Rate Limited. Body: {body}")
        if 400 <= r.status_code < 500:
            raise RuntimeError(f"Affinity v2 {r.status_code} client error for {path}. Body: {body}")
        raise RuntimeError(f"Affinity v2 {r.status_code} server error for {path}. Body: {body}")

    # ---- Diagnostics ----
    def whoami(self):
        return self._req("GET", "/v2/auth/whoami")

    # ---- Lists & IDs ----
    def lists(self, limit: int = 100):
        return self._req("GET", "/v2/lists", params={"limit": limit})

    def find_list_id_by_name(self, name: str) -> Dict[str, Any]:
        out = {"query": name, "matches": []}
        cursor = None
        while True:
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            data = self._req("GET", "/v2/lists", params=params)
            for lst in data.get("data", []):
                if name.lower() in (lst.get("name") or "").lower():
                    out["matches"].append({"id": lst.get("id"), "name": lst.get("name"), "type": lst.get("type")})
            cursor = (data.get("pagination") or {}).get("nextUrl")
            if not cursor:
                break
        return out

    # ---- Companies ----
    def companies(self, limit: int = 100, cursor: str | None = None):
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._req("GET", "/v2/companies", params=params)

    def find_company(self, name: str | None = None, domain: str | None = None) -> Dict[str, Any]:
        if not name and not domain:
            return {"error": "Provide name or domain"}
        results = []
        cursor = None
        # Simple single-page scan (extend as needed by parsing pagination.nextUrl)
        page = self.companies(cursor=cursor)
        for c in page.get("data", []):
            cname = (c.get("name") or "").lower()
            cdom = (c.get("domain") or "").lower()
            if name and name.lower() in cname:
                results.append({"id": c.get("id"), "name": c.get("name"), "domain": c.get("domain")})
            if domain and (domain.lower() == cdom):
                results.append({"id": c.get("id"), "name": c.get("name"), "domain": c.get("domain")})
        return {"query": {"name": name, "domain": domain}, "matches": results}

    # ---- Notes (read) ----
    def get_company_notes(self, company_id: int, limit: int | None = 20):
        params = {"limit": limit} if limit else {}
        return self._req("GET", f"/v2/companies/{company_id}/notes", params=params)

    # ---- List Fields (updates) ----
    def update_list_field(self, list_id: int, list_entry_id: int, field_id: str, value: Dict[str, Any]):
        body = {"value": value}
        return self._req(
            "POST",
            f"/v2/lists/{list_id}/list-entries/{list_entry_id}/fields/{field_id}",
            json=body,
        )

    def batch_update_list_fields(self, list_id: int, list_entry_id: int, operations: list):
        body = {"operations": operations}
        return self._req(
            "PATCH",
            f"/v2/lists/{list_id}/list-entries/{list_entry_id}/fields",
            json=body,
        )
