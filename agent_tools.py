from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from agents import function_tool

from affinity_client import AffinityAPI

# We bind tools to a *module-level* client instance set from the Streamlit app.
AFFINITY: Optional[AffinityAPI] = None

def _client() -> AffinityAPI:
    global AFFINITY
    if AFFINITY is None:
        AFFINITY = AffinityAPI(os.getenv("AFFINITY_API_KEY"))
    return AFFINITY


@function_tool
def add_company(name: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Create a new organization (company).

    Args:
        name: Organization name.
        domain: Primary domain, e.g. "example.com" (optional).
    Returns: The created organization resource.
    """
    return _client().create_organization(name=name, domain=domain)


@function_tool
def find_company_ids(query: str) -> List[Dict[str, Any]]:
    """Find company IDs by name or website term.

    Args:
        query: A name fragment or domain, e.g. "Acme" or "acme.com".
    Returns: [{ id, name, domain }]
    """
    res = _client().search_organizations(term=query)
    orgs = res.get("organizations", []) if isinstance(res, dict) else res
    return [{"id": o.get("id"), "name": o.get("name"), "domain": o.get("domain") or (o.get("domains") or [None])[0]} for o in orgs]


@function_tool
def add_note(content: str, organization_id: Optional[int] = None, person_id: Optional[int] = None, opportunity_id: Optional[int] = None) -> Dict[str, Any]:
    """Add a note. Provide one or more of organization_id, person_id, opportunity_id.

    Args:
        content: The note body.
        organization_id: Optional organization ID to tag.
        person_id: Optional person ID to tag.
        opportunity_id: Optional opportunity ID to tag.
    Returns: The created note resource.
    """
    org_ids = [organization_id] if organization_id else None
    person_ids = [person_id] if person_id else None
    opp_ids = [opportunity_id] if opportunity_id else None
    return _client().create_note(content=content, organization_ids=org_ids, person_ids=person_ids, opportunity_ids=opp_ids)


@function_tool
def read_notes(organization_id: Optional[int] = None, person_id: Optional[int] = None, opportunity_id: Optional[int] = None, creator_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read notes filtered by entity and/or creator.

    Args:
        organization_id: Filter by organization.
        person_id: Filter by person.
        opportunity_id: Filter by opportunity.
        creator_id: Filter by the note's creator.
    Returns: A list of note objects.
    """
    data = _client().get_notes(organization_id=organization_id, person_id=person_id, opportunity_id=opportunity_id, creator_id=creator_id)
    notes = data.get("notes", []) if isinstance(data, dict) else data
    return notes


@function_tool
def find_list_ids(list_name: str) -> List[Dict[str, Any]]:
    """Find list IDs whose name matches the given string (case-insensitive substring).

    Args:
        list_name: Name fragment, e.g. "Target Accounts".
    Returns: [{ id, name, type }]
    """
    return _client().find_list_ids_by_name(list_name)


@function_tool
def add_company_to_list(list_id: int, organization_id: int) -> Dict[str, Any]:
    """Add an existing organization to a list.

    Args:
        list_id: List ID (must be an organization-type list).
        organization_id: Organization ID to add.
    Returns: The created list entry.
    """
    return _client().add_organization_to_list(list_id=list_id, organization_id=organization_id)


@function_tool
def change_field_in_list(list_id: int, organization_id: int, field_name_or_id: str, value: str) -> Dict[str, Any]:
    """Change a field value for a company on a specific list.

    Args:
        list_id: The list containing the company.
        organization_id: The target company ID.
        field_name_or_id: Display name (on that list) or numeric field ID.
        value: New value (string). For dropdowns, pass the option text. For numbers/dates, pass the string representation.
    Returns: The updated/created field value resource.
    """
    return _client().change_field_value_in_list(list_id=list_id, organization_id=organization_id, field_name_or_id=field_name_or_id, value=value)
