import json
from typing import Any, Dict
from pydantic import BaseModel, Field

# ---- Tool Schemas (OpenAI function calling)

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
    filter: str | None = Field(default=None, description="Optional filter per v2 filtering language")
    total_count: bool | None = Field(default=False)

class AddCompanyToListArgs(BaseModel):
    list_id: int
    company_id: int

class UpdateFieldArgs(BaseModel):
    list_id: int
    list_entry_id: int
    field_id: str
    value_json: Dict[str, Any] = Field(
        ..., description='FieldValueUpdate JSON, e.g. {"type":"text","data":"Hello"}'
    )

class BatchUpdateFieldsArgs(BaseModel):
    list_id: int
    list_entry_id: int
    updates: list = Field(..., description="Array of { id: <fieldId>, value: <FieldValueUpdate> }")

class FindListIdArgs(BaseModel):
    name: str

class FindCompanyIdArgs(BaseModel):
    name: str | None = None
    domain: str | None = None

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "add_company",
        "description": "Create a new Company. Not exposed in v2 per provided docs; returns an actionable message.",
        "parameters": AddCompanyArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "add_note_to_company",
        "description": "Add a note to a Company. Not exposed in v2 per provided docs; returns an actionable message.",
        "parameters": AddNoteArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "read_notes_for_company",
        "description": "Read notes for a Company via v2.",
        "parameters": ReadNotesArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "add_company_to_list",
        "description": "Add a Company row to a List. Creating list entries is not exposed in v2 per provided docs; returns an actionable message.",
        "parameters": AddCompanyToListArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "update_list_field",
        "description": "Update a single field value on a List Entry via v2.",
        "parameters": UpdateFieldArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "batch_update_list_fields",
        "description": "Batch update multiple fields on a List Entry via v2 (operation=update-fields).",
        "parameters": BatchUpdateFieldsArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "find_list_id_by_name",
        "description": "Find a List ID by exact (or fuzzy) name via v2.",
        "parameters": FindListIdArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "find_company_id",
        "description": "Find a Company by name or domain via v2.",
        "parameters": FindCompanyIdArgs.model_json_schema(),
    }},
    {"type": "function", "function": {
        "name": "auth_whoami",
        "description": "Return info about the authenticated user/org/permissions (v2).",
        "parameters": {},
    }},
]

# ---- Dispatcher

def _parse(model_cls, args_json: str):
    data = json.loads(args_json or "{}")
    return model_cls(**data)

def dispatch_tool(name: str, args_json: str, v2):
    try:
        if name == "add_company":
            _ = _parse(AddCompanyArgs, args_json)
            return {"error": "Creating companies isn’t exposed in Affinity v2 per the docs you shared. Use the Affinity UI to create the company, then I can find it and manage its list fields/notes."}

        if name == "add_note_to_company":
            _ = _parse(AddNoteArgs, args_json)
            return {"error": "Creating notes isn’t exposed in Affinity v2 per the docs you shared. Create the note in the UI for now; I can read notes via v2."}

        if name == "read_notes_for_company":
            args = _parse(ReadNotesArgs, args_json)
            return v2.get_company_notes(company_id=args.company_id, limit=args.limit, filter=args.filter, total_count=args.total_count)

        if name == "add_company_to_list":
            _ = _parse(AddCompanyToListArgs, args_json)
            return {"error": "Adding a company to a list (creating a list entry) isn’t exposed in v2 per the docs you shared. Once the row exists, I can update its fields via v2."}

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
                list_id=args.list_id, list_entry_id=args.list_entry_id, updates=args.updates
            )

        if name == "find_list_id_by_name":
            args = _parse(FindListIdArgs, args_json)
            return v2.find_list_id_by_name(name=args.name)

        if name == "find_company_id":
            args = _parse(FindCompanyIdArgs, args_json)
            return v2.find_company(name=args.name, domain=args.domain)

        if name == "auth_whoami":
            return v2.whoami()

        return {"error": f"Unknown tool {name}"}

    except Exception as e:
        return {"error": f"Tool dispatcher error: {e}"}

