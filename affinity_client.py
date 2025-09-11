from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth


class AffinityAPI:
    """Thin wrapper around the Affinity REST API.

    Auth: HTTP Basic with blank username and API key as password.
    Base URL: https://api.affinity.co
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.affinity.co"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("AFFINITY_API_KEY")
        if not self.api_key:
            raise ValueError("Missing AFFINITY_API_KEY")
        self.auth = HTTPBasicAuth("", self.api_key)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # --- internal helpers --------------------------------------------------
    def _request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None, data: dict | None = None,
                 headers: dict | None = None, retries: int = 3) -> Any:
        url = f"{self.base_url}{path}"
        backoff = 1.0
        for attempt in range(retries):
            resp = self.session.request(method, url, auth=self.auth, params=params, json=json, data=data, headers=headers)
            if resp.status_code in (429, 500, 502, 503, 504):
                # exponential backoff
                time.sleep(backoff)
                backoff *= 2
                continue
            if not resp.ok:
                try:
                    err = resp.json()
                except Exception:
                    err = resp.text
                raise RuntimeError(f"Affinity API error {resp.status_code} {url}: {err}")
            if resp.content:
                try:
                    return resp.json()
                except Exception:
                    return resp.text
            return None
        resp.raise_for_status()

    # --- organizations -----------------------------------------------------
    def create_organization(self, name: str, domain: Optional[str] = None, person_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": name}
        if domain:
            payload["domain"] = domain
        if person_ids:
            payload["person_ids"] = person_ids
        return self._request("POST", "/organizations", json=payload)

    def search_organizations(self, term: str, page_token: Optional[str] = None, page_size: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"term": term}
        if page_token:
            params["page_token"] = page_token
        if page_size:
            params["page_size"] = page_size
        return self._request("GET", "/organizations", params=params)

    def get_organization(self, organization_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/organizations/{organization_id}")

    # --- notes -------------------------------------------------------------
    def create_note(
        self,
        content: str,
        person_ids: Optional[List[int]] = None,
        organization_ids: Optional[List[int]] = None,
        opportunity_ids: Optional[List[int]] = None,
        note_type: Optional[int] = None,
        parent_id: Optional[int] = None,
        creator_id: Optional[int] = None,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"content": content}
        if person_ids:
            payload["person_ids"] = person_ids
        if organization_ids:
            payload["organization_ids"] = organization_ids
        if opportunity_ids:
            payload["opportunity_ids"] = opportunity_ids
        if note_type is not None:
            payload["type"] = note_type
        if parent_id is not None:
            payload["parent_id"] = parent_id
        if creator_id is not None:
            payload["creator_id"] = creator_id
        if created_at is not None:
            payload["created_at"] = created_at
        # Affinity accepts JSON or x-www-form-urlencoded; we send JSON
        return self._request("POST", "/notes", json=payload)

    def get_notes(
        self,
        person_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        opportunity_id: Optional[int] = None,
        creator_id: Optional[int] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if person_id is not None:
            params["person_id"] = person_id
        if organization_id is not None:
            params["organization_id"] = organization_id
        if opportunity_id is not None:
            params["opportunity_id"] = opportunity_id
        if creator_id is not None:
            params["creator_id"] = creator_id
        if page_size is not None:
            params["page_size"] = page_size
        if page_token is not None:
            params["page_token"] = page_token
        return self._request("GET", "/notes", params=params)

    # --- lists & list entries ---------------------------------------------
    def get_lists(self) -> List[Dict[str, Any]]:
        data = self._request("GET", "/lists")
        # API returns an array
        return data if isinstance(data, list) else data.get("lists", data)

    def find_list_ids_by_name(self, name: str) -> List[Dict[str, Any]]:
        name_lower = name.lower().strip()
        matches = []
        for lst in self.get_lists():
            if name_lower in str(lst.get("name", "")).lower():
                matches.append({"id": lst.get("id"), "name": lst.get("name"), "type": lst.get("type")})
        return matches

    def get_list_entries(self, list_id: int, page_size: Optional[int] = None) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {}
        if page_size:
            params["page_size"] = page_size
        next_token: Optional[str] = None
        while True:
            if next_token:
                params["page_token"] = next_token
            data = self._request("GET", f"/lists/{list_id}/list-entries", params=params)
            if isinstance(data, dict) and "list_entries" in data:
                entries.extend(data.get("list_entries", []))
                next_token = data.get("next_page_token")
            else:
                # Some responses may just be an array
                if isinstance(data, list):
                    entries.extend(data)
                next_token = None
            if not next_token:
                break
        return entries

    def add_organization_to_list(self, list_id: int, organization_id: int) -> Dict[str, Any]:
        payload = {"entity_id": organization_id}
        return self._request("POST", f"/lists/{list_id}/list-entries", json=payload)

    def get_list_entry_id(self, list_id: int, organization_id: int) -> Optional[int]:
        for entry in self.get_list_entries(list_id):
            if int(entry.get("entity_id")) == int(organization_id):
                return int(entry.get("id"))
        return None

    # --- fields & field values --------------------------------------------
    def get_fields(self, list_id: Optional[int] = None, with_modified_names: bool = False, exclude_dropdown_options: bool = False) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if list_id is not None:
            params["list_id"] = list_id
        if with_modified_names:
            params["with_modified_names"] = "true"
        if exclude_dropdown_options:
            params["exclude_dropdown_options"] = "true"
        data = self._request("GET", "/fields", params=params)
        return data if isinstance(data, list) else data.get("fields", data)

    def create_field_value(self, field_id: int, value: Any, *, entity_id: Optional[int] = None, list_entry_id: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"field_id": field_id, "value": value}
        if entity_id is not None:
            payload["entity_id"] = entity_id
        if list_entry_id is not None:
            payload["list_entry_id"] = list_entry_id
        return self._request("POST", "/field-values", json=payload)

    def update_field_value(self, field_value_id: int, value: Any) -> Dict[str, Any]:
        return self._request("PUT", f"/field-values/{field_value_id}", json={"value": value})

    def get_field_values(self, *, person_id: Optional[int] = None, organization_id: Optional[int] = None, opportunity_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if person_id is not None:
            params["person_id"] = person_id
        if organization_id is not None:
            params["organization_id"] = organization_id
        if opportunity_id is not None:
            params["opportunity_id"] = opportunity_id
        data = self._request("GET", "/field-values", params=params)
        return data if isinstance(data, list) else data.get("field_values", data)

    # High-level convenience
    def change_field_value_in_list(self, list_id: int, organization_id: int, field_name_or_id: str | int, value: Any) -> Dict[str, Any]:
        # Resolve field_id
        if isinstance(field_name_or_id, int) or str(field_name_or_id).isdigit():
            field_id = int(field_name_or_id)
        else:
            fields = self.get_fields(list_id=list_id, with_modified_names=True)
            target_name = str(field_name_or_id).strip().lower()
            lookup = {str(f.get("name", "")).strip().lower(): int(f.get("id")) for f in fields}
            if target_name not in lookup:
                raise RuntimeError(f"Field '{field_name_or_id}' not found on list {list_id}.")
            field_id = lookup[target_name]

        # Resolve list_entry_id
        le_id = self.get_list_entry_id(list_id, organization_id)
        if le_id is None:
            raise RuntimeError(f"Organization {organization_id} is not on list {list_id}.")

        # Try to find existing field value to update (avoid duplicates)
        existing = [fv for fv in self.get_field_values(organization_id=organization_id) if int(fv.get("field_id")) == field_id and int(fv.get("list_entry_id", 0)) == le_id]
        if existing:
            return self.update_field_value(int(existing[0]["id"]), value)
        return self.create_field_value(field_id=field_id, value=value, entity_id=organization_id, list_entry_id=le_id)
