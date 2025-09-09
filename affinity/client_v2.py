from __future__ import annotations
import requests
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

BASE_URL = "https://api.affinity.co"

class AffinityV2:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
        self.session.headers.update({"Content-Type": "application/json"})

    def _check(self):
        if not self.api_key:
            raise RuntimeError("Affinity v2 bearer key missing")

    def _req(self, method: str, path_or_url: str, **kwargs) -> Dict[str, Any]:
        self._check()
        # Support absolute nextUrl links
        url = path_or_url if path_or_url.startswith("http") else f"{BASE_URL}{path_or_url}"
        r = self.session.request(method, url, timeout=30, **kwargs)
        if r.status_code in (204, 205):
            return {}
        if r.status_code < 400:
            return r.json() if r.text else {}
        body = r.text
        if r.status_code == 401:
            raise RuntimeError(f"Affinity v2 401 Unauthorized. Body: {body}")
        if r.status_code == 403:
            raise RuntimeError(f"Affinity v2 403 Forbidden for {url}. Body: {body}")
        if r.status_code == 429:
            raise RuntimeError(f"Affinity v2 429 Rate Limited. Body: {body}")
        if 400 <= r.status_code < 500:
            raise RuntimeError(f"Affinity v2 {r.status_code} client error for {url}. Body: {body}")
        raise RuntimeError(f"Affinity v2 {r.status_code} server error for {url}. Body: {body}")

    # ---- Diagnostics ----
    def whoami(self):
        return self._req("GET", "/v2/auth/whoami")

    # ---- Lists & IDs ----
    def lists(self, limit: int = 100, cursor: Optional[str] = None):
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._req("GET", "/v2/lists", params=params)

    def _extract_cursor(self, next_url: Optional[str]) -> Optional[str]:
        if not next_url:
            return None
        try:
            q = parse_qs(urlparse(next_url).query)
            cur = q.get("cursor", [None])[0]
            return cur
        except Exception:
            return None

    def find_list_id_by_name(self, name: str) -> Dict[str, Any]:
        out = {"query": name, "matches": []}
        cursor = None
        seen = 0
        while True:
            data = self.lists(limit=100, cursor=cursor)
            for lst in data.get("data", []):
                if name.lower() in (lst.get("name") or "").lower():
                    out["matches"].append({"id": lst.get("id"), "name": lst.get("name"), "type": lst.get("type")})
            cursor = self._extract_cursor((data.get("pagination") or {}).get("nextUrl"))
            seen += 1
            if not cursor or seen > 25:
                break
        return out

    # ---- Companies ----
    def companies(self, limit: int = 100, cursor: Optional[str] = None, field_ids: Optional[List[str]] = None, field_types: Optional[List[str]] = None):
        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if field_ids:
            for fid in field_ids:
                params.setdefault("fieldIds", []).append(fid)
        if field_types:
            for ft in field_types:
                params.setdefault("fieldTypes", []).append(ft)
        return self._req("GET", "/v2/companies", params=params)

    def find_company(self, name: Optional[str] = None, domain: Optional[str] = None, max_pages: int = 10) -> Dict[str, Any]:
        if not name and not domain:
            return {"error": "Provide name or domain"}
        results = []
        cursor = None
        pages = 0
        while True:
            page = self.companies(limit=100, cursor=cursor)
            for c in page.get("data", []):
                cname = (c.get("name") or "").lower()
                cdom = (c.get("domain") or "").lower()
                domains = " ".join(c.get("domains") or []).lower()
                match = False
                if name and name.lower() in cname:
                    match = True
                if domain and (domain.lower() == cdom or domain.lower() in domains):
                    match = True
                if match:
                    results.append({"id": c.get("id"), "name": c.get("name"), "domain": c.get("domain")})
            cursor = self._extract_cursor((page.get("pagination") or {}).get("nextUrl"))
            pages += 1
            if not cursor or pages >= max_pages:
                break
        return {"query": {"name": name, "domain": domain}, "matches": results}

    # ---- Notes (read) ----
    def get_company_notes(self, company_id: int, limit: Optional[int] = 20, filter: Optional[str] = None, total_count: Optional[bool] = False):
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if filter:
            params["filter"] = filter
        if total_count:
            params["totalCount"] = str(bool(total_count)).lower()
        return self._req("GET", f"/v2/companies/{company_id}/notes", params=params)

    # ---- List Fields (updates) ----
    def update_list_field(self, list_id: int, list_entry_id: int, field_id: str, value: Dict[str, Any]):
        body = {"value": value}
        # 204 No Content on success per docs
        self._req(
            "POST",
            f"/v2/lists/{list_id}/list-entries/{list_entry_id}/fields/{field_id}",
            json=body,
        )
        return {"status": "ok", "method": "POST", "listId": list_id, "listEntryId": list_entry_id, "fieldId": field_id}

    def batch_update_list_fields(self, list_id: int, list_entry_id: int, updates: List[Dict[str, Any]]):
        body = {"operation": "update-fields", "updates": updates}
        # 200 OK with operation echo per docs
        return self._req(
            "PATCH",
            f"/v2/lists/{list_id}/list-entries/{list_entry_id}/fields",
            json=body,
        )
