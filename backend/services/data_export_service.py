"""Everything held about one candidate, for a data access request.

Pilot plan Track 1 #5. GDPR gives a person the right to a copy of the data
held about them; this gathers it as JSON (for a machine or a lawyer) and as
plain text (for the person).

What is in it: one section per table in `erasure_service.ERASURE_STEPS`,
read with the same WHERE clauses the erasure deletes with. The erasure list
is already pinned by a test that walks every foreign key back to
`candidates`, so a table that would survive an erasure cannot be missing
from an export either. On top of that: the job titles, stage names and staff
names those rows refer to by id, and the candidate's access history from
the audit log (when, which role, what kind of access; not which account).

What is left out, and said so in the export itself: search vectors (derived
numbers, not information about the person), the status-page link token (a
live credential; whether one exists and when it was made are included), and
server storage paths. The stored resume files are listed by name; staff can
download each one from the candidate page.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.services.erasure_service import ERASURE_STEPS, CandidateNotFound

# Parents first, the order a person reads it in.
EXPORT_STEPS: tuple[tuple[str, str], ...] = tuple(reversed(ERASURE_STEPS))

SECTION_LABELS: dict[str, str] = {
    "candidates": "Profile",
    "resumes": "Resumes",
    "candidate_experience": "Work experience",
    "candidate_education": "Education",
    "candidate_skills": "Skills",
    "candidate_tags": "Tags",
    "candidate_pitches": "Pitches written about this candidate",
    "saved_jobs": "Saved jobs",
    "job_applications": "Applications",
    "notes": "Notes",
    "email_log": "Emails sent",
    "application_stages": "Pipeline stage history",
    "interviews": "Interviews",
    "feedback": "Interview feedback",
}

# Named columns left out, with the reason printed in the export.
OMITTED_COLUMNS: dict[tuple[str, str], str] = {
    ("resumes", "vector_embedding"): "search vector derived from the resume text",
    ("resumes", "file_path"): "server storage location",
    ("job_applications", "public_token"): (
        "status-page link credential; public_token_created_at shows whether one exists"
    ),
}
# Any column of these database types is left out too, whatever its name.
_OMITTED_TYPES = {"vector": "search vector derived from the profile", "bytea": "binary data"}

# Columns whose value is a staff account id, resolved to a name in references.
_STAFF_COLUMNS = {"author_id", "interviewer_id", "user_id", "sent_by", "changed_by"}


@dataclass
class CandidateExport:
    candidate_id: str
    generated_at: datetime
    sections: list[dict[str, Any]] = field(default_factory=list)
    omitted: list[dict[str, str]] = field(default_factory=list)
    references: dict[str, dict[str, str]] = field(default_factory=dict)
    access_history: list[dict[str, Any]] = field(default_factory=list)

    def section(self, table: str) -> dict[str, Any]:
        return next(s for s in self.sections if s["table"] == table)


def _plain(value: Any) -> Any:
    """A value json.dumps can write, keeping its meaning."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    return value


def _typed_omissions(db: Session, tables: list[str]) -> dict[tuple[str, str], str]:
    rows = db.execute(
        text(
            "SELECT table_name, column_name, udt_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ANY(:tables) "
            "AND udt_name = ANY(:types)"
        ),
        {"tables": tables, "types": list(_OMITTED_TYPES)},
    ).all()
    return {(r.table_name, r.column_name): _OMITTED_TYPES[r.udt_name] for r in rows}


def export_candidate(db: Session, candidate_id: str) -> CandidateExport:
    """Read everything held about the candidate. Changes nothing."""
    params = {"cid": candidate_id}
    if db.execute(text("SELECT 1 FROM candidates WHERE id = :cid"), params).first() is None:
        raise CandidateNotFound(candidate_id)

    tables = [table for table, _ in EXPORT_STEPS]
    omissions = {**_typed_omissions(db, tables), **OMITTED_COLUMNS}
    export = CandidateExport(candidate_id=candidate_id, generated_at=datetime.utcnow())

    present: set[tuple[str, str]] = set()
    for table, where in EXPORT_STEPS:
        result = db.execute(text(f"SELECT * FROM {table} WHERE {where} ORDER BY id"), params)
        columns = list(result.keys())
        kept = [c for c in columns if (table, c) not in omissions]
        present.update((table, c) for c in columns if (table, c) in omissions)
        rows = [{c: _plain(row[c]) for c in kept} for row in result.mappings()]
        export.sections.append(
            {"table": table, "label": SECTION_LABELS.get(table, table), "rows": rows}
        )
    export.omitted = [
        {"table": table, "column": column, "reason": omissions[(table, column)]}
        for table, column in sorted(present)
    ]
    export.references = _references(db, export)
    export.access_history = [
        {
            "occurred_at": _plain(r.occurred_at),
            "actor_role": r.actor_role,
            "action": r.action,
            "subject_type": r.subject_type,
            "endpoint": r.endpoint,
            "status_code": r.status_code,
        }
        for r in db.execute(
            text(
                "SELECT occurred_at, actor_role, action, subject_type, endpoint, status_code "
                "FROM audit_events WHERE candidate_id = :cid ORDER BY id"
            ),
            params,
        )
    ]
    return export


def _references(db: Session, export: CandidateExport) -> dict[str, dict[str, str]]:
    """Names for the ids the rows point at: jobs, pipeline stages, staff."""
    job_ids: set[int] = set()
    stage_ids: set[int] = set()
    staff_ids: set[str] = set()
    for section in export.sections:
        for row in section["rows"]:
            if row.get("job_id") is not None:
                job_ids.add(row["job_id"])
            if row.get("stage_id") is not None:
                stage_ids.add(row["stage_id"])
            for column in _STAFF_COLUMNS:
                if row.get(column):
                    staff_ids.add(str(row[column]))

    def lookup(sql: str, ids: set) -> dict[str, str]:
        if not ids:
            return {}
        return {str(r[0]): r[1] or "" for r in db.execute(text(sql), {"ids": list(ids)})}

    return {
        "jobs": lookup("SELECT id, title FROM jobs WHERE id = ANY(:ids)", job_ids),
        "stages": lookup("SELECT id, name FROM pipeline_stages WHERE id = ANY(:ids)", stage_ids),
        "staff": lookup("SELECT id, COALESCE(name, email) FROM users WHERE id = ANY(:ids)", staff_ids),
    }


# --- plain text ---------------------------------------------------------------

_LABEL_OVERRIDES = {"id": "Record id", "job_id": "Job", "stage_id": "Stage"}


def _field_label(column: str) -> str:
    if column in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[column]
    if column in _STAFF_COLUMNS:
        column = column.removesuffix("_id")
    return column.replace("_", " ").capitalize()


def _display(column: str, value: Any, refs: dict[str, dict[str, str]]) -> str:
    if column == "job_id":
        return f"{refs['jobs'].get(str(value), 'Job')} (#{value})"
    if column == "stage_id":
        return refs["stages"].get(str(value), f"#{value}")
    if column in _STAFF_COLUMNS:
        return refs["staff"].get(str(value), "a former staff account")
    if isinstance(value, (dict, list)):
        return "\n" + "\n".join("    " + line for line in json.dumps(value, indent=2).splitlines())
    if isinstance(value, bool):
        return "yes" if value else "no"
    text_value = str(value)
    if "\n" in text_value:
        return "\n" + "\n".join("    " + line for line in text_value.splitlines())
    return text_value


def render_text(export: CandidateExport) -> str:
    """The export as a document a person can read. Empty fields are skipped."""
    profile = export.section("candidates")["rows"]
    name = " ".join(
        part for part in ((profile[0].get("first_name"), profile[0].get("last_name")) if profile else ())
        if part
    ) or "this candidate"
    lines = [
        f"Data held about {name}",
        f"Candidate id: {export.candidate_id}",
        f"Generated: {export.generated_at.strftime('%Y-%m-%d %H:%M')} UTC by RecruitIQ",
        "",
        "Every record below is held in RecruitIQ's database. Ids link records to",
        "each other; the names they refer to are filled in where known.",
    ]
    skip = {"candidate_id"}
    for section in export.sections:
        lines += ["", "", section["label"].upper(), "=" * len(section["label"])]
        if not section["rows"]:
            lines.append("None held.")
            continue
        for index, row in enumerate(section["rows"]):
            if index:
                lines.append("-" * 20)
            for column, value in row.items():
                if column in skip or value is None or value == "":
                    continue
                lines.append(f"{_field_label(column)}: {_display(column, value, export.references)}")

    lines += ["", "", "WHO HAS ACCESSED THIS RECORD", "=" * 28]
    if not export.access_history:
        lines.append("No recorded access by staff accounts.")
    for event in export.access_history:
        lines.append(
            f"{event['occurred_at']}  {event['actor_role']}  {event['action']}  "
            f"{event['subject_type']}  ({event['endpoint']}, status {event['status_code']})"
        )

    if export.omitted:
        lines += ["", "", "LEFT OUT OF THIS EXPORT", "=" * 23]
        for item in export.omitted:
            lines.append(f"{item['table']}.{item['column']}: {item['reason']}")
    return "\n".join(lines) + "\n"


def filename_stem(export: CandidateExport, today: Optional[date] = None) -> str:
    day = (today or export.generated_at.date()).isoformat()
    return f"candidate-data-{export.candidate_id[:8]}-{day}"
