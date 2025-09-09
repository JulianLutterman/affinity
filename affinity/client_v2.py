from __future__ import annotations
import requests
from typing import Any, Dict
from tenacity import retry, wait_exponential, stop_after_attempt

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

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _req(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        self._check()
        url = f"{BASE_URL}{path}"
        r = self.session.request(method, url, timeout=30, **kwargs)
        if r.status_code >= 400:
            raise RuntimeError(f"Affinity v2 error {r.status_code}: {r.text}")
        return r.json() if r.text else {}

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
                if name.lower() in lst.get("name", "").lower():
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
        # naive scan across pages; refine with your own caching/indexing as needed
        if not name and not domain:
            return {"error": "Provide name or domain"}
        results = []
        cursor = None
        while True:
            page = self.companies(cursor=cursor)
            for c in page.get("data", []):
                cname = (c.get("name") or "").lower()
                cdom = (c.get("domain") or "").lower()
                if name and name.lower() in cname:
                    results.append({"id": c.get("id"), "name": c.get("name"), "domain": c.get("domain")})
                if domain and (domain.lower() == cdom or domain.lower() in (" ".join((c.get("domains") or []))).lower()):
                    results.append({"id": c.get("id"), "name": c.get("name"), "domain": c.get("domain")})
            pagination = page.get("pagination") or {}
            next_url = pagination.get("nextUrl")
            if not next_url:
                break
            # Affinity returns full nextUrl; pull cursor param if present
            # Simpler: just set to None to stop (demo). For full crawl, parse nextUrl.
            break
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
