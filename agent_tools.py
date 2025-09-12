from __future__ import annotations
import os
import re
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

# --- Rich text helpers -----------------------------------------------------

def _looks_like_html(s: str) -> bool:
    """Light heuristic for preformatted HTML content."""
    return bool(re.search(r"<(strong|em|u|p|br|div|span)[^>]*>", s, flags=re.I))

def _markdown_to_html(md: str) -> str:
    """
    Minimal Markdown -> HTML focused on bold/italic/underline + line breaks.
    Supported:
      **bold**   -> <strong>bold</strong>
      *italic*   -> <em>italic</em>
      __under__  -> <u>under</u>
    Paragraphs: blank lines split paragraphs; single newlines become <br>.
    """
    txt = md

    # Protect bold first to avoid greedy single-* matches
    txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", txt)

    # Underline (non-standard Markdown, but useful for this workflow)
    txt = re.sub(r"__([^_]+?)__", r"<u>\1</u>", txt)

    # Italic (single *...*). Avoid conflicting with ** already handled.
    txt = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", txt)

    # Paragraphs & line breaks
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", txt)]
    html_paragraphs = []
    for p in paragraphs:
        html_paragraphs.append(f"<p>{p.replace('\n', '<br>')}</p>")
    return "".join(html_paragraphs)

@function_tool
def add_company(name: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Create a new organization (company)."""
    return _client().create_organization(name=name, domain=domain)

@function_tool
def find_company_ids(query: str) -> List[Dict[str, Any]]:
    """Find company IDs by name or website term."""
    res = _client().search_organizations(term=query)
    orgs = res.get("organizations", []) if isinstance(res, dict) else res
    return [{"id": o.get("id"), "name": o.get("name"), "domain": o.get("domain") or (o.get("domains") or [None])[0]} for o in orgs]

@function_tool
def add_note(
    content: str,
    organization_id: Optional[int] = None,
    person_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    content_format: Optional[str] = None,  # "plain" | "html" | "markdown"
) -> Dict[str, Any]:
    """
    Add a note (plain, HTML, or Markdown).

    - If content_format == "html": send as HTML (type=2) unchanged.
    - If content_format == "markdown": convert to HTML (type=2).
    - If content_format is not provided:
        * auto-detect HTML tags and set type=2, OR
        * auto-convert simple Markdown (**bold**, *italic*, __underline__) to HTML and set type=2.
      Otherwise, send as plain text (type omitted ⇒ defaults to 0).

    The '[JL] CURRENT_DATE_PLACEHOLDER' prefix (required by agent instructions) is preserved.
    """
    org_ids = [organization_id] if organization_id else None
    person_ids = [person_id] if person_id else None
    opp_ids = [opportunity_id] if opportunity_id else None

    final_content = content
    note_type: Optional[int] = None  # 0=plain (default), 2=HTML

    # Explicit format
    if content_format:
        fmt = content_format.strip().lower()
        if fmt == "html":
            note_type = 2
        elif fmt == "markdown":
            final_content = _markdown_to_html(content)
            note_type = 2
        else:
            # treat anything else as plain
            note_type = None
    else:
        # Auto-detect
        if _looks_like_html(content):
            note_type = 2
        elif any(m in content for m in ("**", "__", "*")):
            final_content = _markdown_to_html(content)
            note_type = 2

    return _client().create_note(
        content=final_content,
        organization_ids=org_ids,
        person_ids=person_ids,
        opportunity_ids=opp_ids,
        note_type=note_type,
    )

@function_tool
def read_notes(organization_id: Optional[int] = None, person_id: Optional[int] = None, opportunity_id: Optional[int] = None, creator_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read notes filtered by entity and/or creator."""
    data = _client().get_notes(organization_id=organization_id, person_id=person_id, opportunity_id=opportunity_id, creator_id=creator_id)
    notes = data.get("notes", []) if isinstance(data, dict) else data
    return notes

@function_tool
def find_list_ids(list_name: str) -> List[Dict[str, Any]]:
    """Find list IDs whose name matches the given string (case-insensitive substring)."""
    return _client().find_list_ids_by_name(list_name)

@function_tool
def add_company_to_list(list_id: int, organization_id: int) -> Dict[str, Any] | None:
    """Add an existing organization to a list (idempotent)."""
    return _client().add_organization_to_list_if_needed(list_id=list_id, organization_id=organization_id)

@function_tool
def change_field_in_list(list_id: int, organization_id: int, field_name_or_id: str, value: str | int | float | bool | List[str] | List[int]) -> Dict[str, Any]:
    """Change a field value for a company on a specific list."""
    return _client().change_field_value_in_list(list_id=list_id, organization_id=organization_id, field_name_or_id=field_name_or_id, value=value)
