import json
from typing import Any, Dict
from pydantic import BaseModel, Field

# ---- Tool Schemas

class AddCompanyArgs(BaseModel):
    name: str
    domain: str | None = None
    website: str | None = None

class AddNoteArgs(BaseModel):
    company_id: int = Field(..., description="Affinity Company ID")
    html: str = Field(..., description="HTML content of the note")

class ReadNotesArgs(BaseModel):
    company_id: int
    limit: int | None = Field(default=20)

class AddCompanyToListArgs(BaseModel):
    list_id: int
    company_id: int

class UpdateFieldArgs(BaseModel):
    list_id: int
    list_entry_id: int
    field_id: str
    value_json: Dict[str, Any] = Field(
        ..., description='FieldUpdate.value JSON, e.g. {"type":"text","data":"Hello"}'
    )

class BatchUpdateFieldsArgs(BaseModel):
    list_id: int
    list_entry_id: int
    operations: list = Field(..., description="ListEntryBatchOperationRequest.operations array")

class FindListIdArgs(BaseModel):
    name: str

class FindCompanyIdArgs(BaseModel):
    name: str | None = None
    domain: str | None = None

class WhoAmIArgs(BaseModel):
    pass

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "add_company",
        "description": "Create a new Company (Organization). Uses Affinity v1 if configured.",
        "parameters": AddCompanyArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "add_note_to_company",
        "description": "Add a note to a Company (v1 fallback).",
        "parameters": AddNoteArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "read_notes_for_company",
        "description": "Read notes for a Company via v2.",
        "parameters": ReadNotesArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "add_company_to_list",
        "description": "Add a Company row to a List (v1 fallback).",
        "parameters": AddCompanyToListArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "update_list_field",
        "description": "Update a single field value on a List Entry via v2.",
        "parameters": UpdateFieldArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "batch_update_list_fields",
        "description": "Batch update multiple fields on a List Entry via v2.",
        "parameters": BatchUpdateFieldsArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "find_list_id_by_name",
        "description": "Find a List ID by exact (or fuzzy) name via v2.",
        "parameters": FindListIdArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "find_company_id",
        "description": "Find a Company by name or domain via v2; falls back to v1 search if available.",
        "parameters": FindCompanyIdArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "auth_whoami",
        "description": "Return info about the authenticated user/org/permissions (v2).",
        "parameters": WhoAmIArgs.model_json_schema(),
    }},
]

def _parse(model_cls, args_json: str):
    data = json.loads(args_json or "{}")
    return model_cls(**data)

def dispatch_tool(name: str, args_json: str, v2, v1=None):
    try:
        if name == "add_company":
            args = _parse(AddCompanyArgs, args_json)
            if not v1:
                return {"error": "Affinity v1 key not configured; cannot create companies."}
            return v1.create_company(name=args.name, domain=args.domain, website=args.website)

        if name == "add_note_to_company":
            args = _parse(AddNoteArgs, args_json)
            if not v1:
                return {"error": "Affinity v1 key not configured; cannot add notes."}
            return v1.create_company_note(company_id=args.company_id, html=args.html)

        if name == "read_notes_for_company":
            args = _parse(ReadNotesArgs, args_json)
            return v2.get_company_notes(company_id=args.company_id, limit=args.limit)

        if name == "add_company_to_list":
            args = _parse(AddCompanyToListArgs, args_json)
            if not v1:
                return {"error": "Affinity v1 key not configured; cannot add to lists."}
            return v1.add_company_to_list(list_id=args.list_id, company_id=args.company_id)

        if name == "update_list_field":
            args = _parse(UpdateFieldArgs, args_json)
            return v2.update_list_field(
                list_id=args.list_id,
                list_entry_id=args.list_entry_id,
                field_id=args.field_id,
                value=args.value_json,
            )

        if name == "batch_update_list_fields":
            args = _parse(BatchUpdateFieldsArgs, args_json)
            return v2.batch_update_list_fields(
                list_id=args.list_id, list_entry_id=args.list_entry_id, operations=args.operations
            )

        if name == "find_list_id_by_name":
            args = _parse(FindListIdArgs, args_json)
            return v2.find_list_id_by_name(name=args.name)

        if name == "find_company_id":
            args = _parse(FindCompanyIdArgs, args_json)
            # Try v2
            try:
                return v2.find_company(name=args.name, domain=args.domain)
            except PermissionError as e:
                # Optional fallback to v1 search, if available
                if v1 and (args.name or args.domain):
                    term = args.domain or args.name
                    return {
                        "warning": f"v2 companies listing not permitted; fell back to v1 search for term={term}",
                        "v1_results": v1.search_companies(term=term)
                    }
                return {"error": str(e)}
            except Exception as e:
                return {"error": f"find_company_id failed: {e}"}

        if name == "auth_whoami":
            _ = _parse(WhoAmIArgs, args_json)
            return v2.whoami()

        return {"error": f"Unknown tool {name}"}

    except Exception as e:
        return {"error": f"Tool dispatcher error: {e}"}
