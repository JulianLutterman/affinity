from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional, Tuple

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

    def get_list_entry_field_values(
        self,
        list_id: int,
        organization_id: int,
        *,
        resolve_dropdowns: bool = True,
        include_field_meta: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Return field values for a specific list entry (company-on-list).
    
        - Filters /field-values by the list_entry_id for (list_id, organization_id).
        - If include_field_meta=True, adds: field_name, value_type.
        - If resolve_dropdowns=True, adds value_text with dropdown option labels
          (or list of labels for multi-selects).
    
        Returns an empty list if the organization is not on the list.
        """
        le_id = self.get_list_entry_id(list_id, organization_id)
        if le_id is None:
            return []
    
        # Get all org field values, then keep only those for this list entry
        values = [
            fv for fv in self.get_field_values(organization_id=organization_id)
            if int(fv.get("list_entry_id", 0)) == le_id
        ]
    
        if not (resolve_dropdowns or include_field_meta):
            return values
    
        # Fetch field metadata for this list
        fields = {int(f["id"]): f for f in self.get_fields(list_id=list_id)}
        for fv in values:
            try:
                fid = int(fv.get("field_id"))
            except Exception:
                continue
            field = fields.get(fid)
            if not field:
                continue
    
            if include_field_meta:
                fv["field_name"] = field.get("name")
                fv["value_type"] = field.get("value_type")
    
            if resolve_dropdowns:
                opts = field.get("dropdown_options") or field.get("options") or []
                by_id = {int(o["id"]): o.get("text") for o in opts if o.get("id") is not None}
                v = fv.get("value")
    
                if isinstance(v, list):
                    fv["value_text"] = [by_id.get(int(x), x) for x in v if x is not None]
                else:
                    # handle int or stringified int
                    try:
                        fv["value_text"] = by_id.get(int(v), v)
                    except Exception:
                        fv["value_text"] = v
    
        return values


    def add_organization_to_list(self, list_id: int, organization_id: int) -> Dict[str, Any]:
        payload = {"entity_id": organization_id}
        return self._request("POST", f"/lists/{list_id}/list-entries", json=payload)

    def add_organization_to_list_if_needed(self, list_id: int, organization_id: int) -> Dict[str, Any] | None:
        """Idempotent add. Returns the created list-entry if added, else None if already present."""
        existing = self.get_list_entry_id(list_id, organization_id)
        if existing is not None:
            return None
        return self.add_organization_to_list(list_id, organization_id)

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

    def _get_field_details(self, list_id: int, field_name_or_id: str | int) -> Tuple[Dict[str, Any], int]:
        """Return (field_obj, field_id) for a list-specific field by name or id."""
        # If numeric, trust as ID but also try to fetch to inspect options
        if isinstance(field_name_or_id, int) or str(field_name_or_id).isdigit():
            field_id = int(field_name_or_id)
            fields = self.get_fields(list_id=list_id)
            field = next((f for f in fields if int(f.get("id")) == field_id), None)
            if not field:
                raise RuntimeError(f"Field id {field_id} not found on list {list_id}.")
            return field, field_id
        # otherwise name match
        fields = self.get_fields(list_id=list_id, with_modified_names=True)
        target = str(field_name_or_id).strip().lower()
        for f in fields:
            nm = str(f.get("name", "")).strip().lower()
            if nm == target or target in nm:
                return f, int(f.get("id"))
        raise RuntimeError(f"Field '{field_name_or_id}' not found on list {list_id}.")

    def _coerce_value_for_field(self, field: Dict[str, Any], value: Any) -> Any:
        """Coerce human text to API-expected types.
    
        - Dropdowns: map option text ⇒ option id (int), with exact/substring/fuzzy fallback
        - Multi-select dropdowns: list (or comma-separated string) ⇒ list of ids, with fuzzy fallback per item
        - Numbers: convert numeric strings to float/int
        - Booleans: map 'true/false/yes/no' ⇒ bool
        - Dates: pass-through (expect ISO date strings)
        """
        value_type = field.get("value_type")
        options: List[Dict[str, Any]] = field.get("dropdown_options") or field.get("options") or []
    
        def normalize(s: str) -> str:
            return str(s).strip().lower()
    
        # Build lookup once if options exist
        by_text = {normalize(o.get("text")): int(o.get("id")) for o in options if o.get("id") is not None}
    
        # Helper: fuzzy fallback for a single string value
        def fuzzy_one(s: str, *, min_score: float = 0.6) -> Optional[int]:
            best, score = self._closest_option(options, s)
            if best and score >= min_score:
                return int(best["id"])
            return None
    
        # Allow comma-separated strings as multi-select input
        if options and isinstance(value, str) and ("," in value):
            value = [v.strip() for v in value.split(",") if v.strip()]
    
        # Dropdown (single)
        if options and not isinstance(value, list):
            if isinstance(value, str):
                key = normalize(value)
    
                # Exact match
                if key in by_text:
                    return by_text[key]
    
                # Substring fallback
                for txt, oid in by_text.items():
                    if key in txt:
                        return oid
    
                # Numeric id as text
                if value.isdigit():
                    return int(value)
    
                # Fuzzy fallback
                fuzzy_id = fuzzy_one(value)
                if fuzzy_id is not None:
                    return fuzzy_id
    
                raise RuntimeError(f"Dropdown value '{value}' not found among options: {[o.get('text') for o in options]}")
            if isinstance(value, int):
                return value
    
        # Multi-select (list of ids/texts)
        if options and isinstance(value, list):
            out: List[int] = []
            for v in value:
                if isinstance(v, int):
                    out.append(v)
                    continue
                vkey = normalize(v)
                if vkey in by_text:
                    out.append(by_text[vkey])
                    continue
    
                # substring
                found = next((oid for txt, oid in by_text.items() if vkey in txt), None)
                if found is not None:
                    out.append(found)
                    continue
    
                # fuzzy
                fuzzy_id = fuzzy_one(v)
                if fuzzy_id is not None:
                    out.append(fuzzy_id)
                    continue
    
                raise RuntimeError(f"Dropdown value '{v}' not found among options: {[o.get('text') for o in options]}")
            return out
    
        # Numbers
        if value_type in (2, 3, "number", "float", "integer") and isinstance(value, str):
            try:
                if "." in value:
                    return float(value)
                return int(value)
            except Exception:
                pass
    
        # Booleans
        if value_type in (5, "boolean", "bool") and isinstance(value, str):
            if normalize(value) in ("true", "yes", "y", "1"):
                return True
            if normalize(value) in ("false", "no", "n", "0"):
                return False
    
        return value


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

    # High-level convenience -------------------------------------------------
    def change_field_value_in_list(self, list_id: int, organization_id: int, field_name_or_id: str | int, value: Any) -> Dict[str, Any]:
        """Ensure org is on the list, then create/update the field value.

        - If org is not in the list, add it (idempotent)
        - Coerce human input (e.g., dropdown text) to API-expected value (e.g., option id)
        - Update existing field value if present; else create
        """
        # Ensure membership (idempotent)
        le_id = self.get_list_entry_id(list_id, organization_id)
        if le_id is None:
            self.add_organization_to_list_if_needed(list_id, organization_id)
            le_id = self.get_list_entry_id(list_id, organization_id)
            if le_id is None:
                raise RuntimeError(f"Failed to add organization {organization_id} to list {list_id}.")

        # Resolve field & coerce value
        field, field_id = self._get_field_details(list_id, field_name_or_id)
        coerced_value = self._coerce_value_for_field(field, value)

        # Try to find existing field value to update (avoid duplicates)
        existing = [
            fv for fv in self.get_field_values(organization_id=organization_id)
            if int(fv.get("field_id")) == field_id and int(fv.get("list_entry_id", 0)) == le_id
        ]
        if existing:
            return self.update_field_value(int(existing[0]["id"]), coerced_value)
        return self.create_field_value(field_id=field_id, value=coerced_value, entity_id=organization_id, list_entry_id=le_id)
