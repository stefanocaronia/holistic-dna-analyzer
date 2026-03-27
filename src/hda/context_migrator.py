"""Versioned migrations for subject context documents."""

from datetime import datetime
from pathlib import Path
import re
import shutil

from hda.config import get_active_subject, get_context_path
from hda.context_audit import append_context_audit
from hda.context_store import (
    CONTEXT_SECTIONS,
    CURRENT_CONTEXT_SCHEMA_VERSION,
    PRIORITY_SECTIONS,
    _default_frontmatter,
    _ensure_section_title,
    _humanize_slug,
    _join_blocks,
    _parse_inline_metadata,
    _render_block_content,
    _render_frontmatter,
    _slugify,
    _split_blocks,
    _split_frontmatter,
    _sync_last_updated_line,
    validate_context_section,
)

LEGACY_CONTEXT_SCHEMA_VERSION = 0


def _coerce_schema_version(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return LEGACY_CONTEXT_SCHEMA_VERSION


def _normalize_priority_heading(heading: str) -> str:
    normalized = _slugify(heading)
    aliases = {
        "alta_priorita": "Alta Priorità",
        "high_priority": "Alta Priorità",
        "high": "Alta Priorità",
        "media_priorita": "Media Priorità",
        "medium_priority": "Media Priorità",
        "medium": "Media Priorità",
        "bassa_priorita": "Bassa Priorità",
        "low_priority": "Bassa Priorità",
        "low": "Bassa Priorità",
    }
    return aliases.get(normalized, heading)


def _extract_dated_heading(heading: str) -> tuple[str | None, str]:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})[:\s-]+(.+)$", heading.strip())
    if not match:
        return None, heading.strip()
    return match.group(1), match.group(2).strip()


def _normalize_metadata(subject: str, section: str, metadata: dict, changes: list[str]) -> dict:
    normalized = dict(metadata or {})
    defaults = _default_frontmatter(subject, section)

    if normalized.get("subject") != subject:
        normalized["subject"] = subject
        changes.append("normalized frontmatter subject")

    if normalized.get("doc_type") != section:
        normalized["doc_type"] = section
        changes.append("normalized frontmatter doc_type")

    if not normalized.get("title"):
        normalized["title"] = defaults["title"]
        changes.append("added frontmatter title")

    if not normalized.get("last_updated"):
        normalized["last_updated"] = defaults["last_updated"]
        changes.append("added frontmatter last_updated")

    current_version = _coerce_schema_version(normalized.get("schema_version"))
    if current_version != CURRENT_CONTEXT_SCHEMA_VERSION:
        normalized["schema_version"] = CURRENT_CONTEXT_SCHEMA_VERSION
        changes.append(f"updated schema_version {current_version} -> {CURRENT_CONTEXT_SCHEMA_VERSION}")

    return normalized


def _migrate_findings(body: str, last_updated: str, changes: list[str]) -> str:
    doc_preamble, blocks = _split_blocks(body, 2)
    migrated_blocks = []

    for block in blocks:
        metadata, content = _parse_inline_metadata(block["content"])
        original_heading = block["heading"]
        dated_created, clean_heading = _extract_dated_heading(original_heading)
        if dated_created:
            changes.append(f"converted dated findings heading '{original_heading}' to stable block metadata")

        finding_id = metadata.get("finding_id") or _slugify(clean_heading)
        if finding_id and metadata.get("finding_id") != finding_id:
            metadata["finding_id"] = finding_id
            changes.append(f"added finding_id for '{clean_heading or original_heading}'")

        if not metadata.get("created"):
            metadata["created"] = dated_created or metadata.get("updated") or last_updated
            changes.append(f"added created date for '{clean_heading or original_heading}'")

        if not metadata.get("updated"):
            metadata["updated"] = last_updated
            changes.append(f"added updated date for '{clean_heading or original_heading}'")

        if not metadata.get("status"):
            metadata["status"] = "active"
            changes.append(f"added status for '{clean_heading or original_heading}'")

        final_heading = clean_heading
        if final_heading == finding_id or re.fullmatch(r"[a-z0-9_]+", final_heading):
            final_heading = _humanize_slug(finding_id or final_heading)
        if final_heading != original_heading:
            changes.append(f"replaced technical findings heading '{original_heading}' with readable title")

        migrated_blocks.append(
            {
                "heading": final_heading,
                "content": _render_block_content(
                    metadata,
                    content,
                    ["finding_id", "created", "updated", "status", "domains"],
                ),
            }
        )

    return _join_blocks(doc_preamble, migrated_blocks, 2)


def _migrate_health_actions(body: str, changes: list[str], warnings: list[str]) -> str:
    doc_preamble, priority_sections = _split_blocks(body, 2)

    if not priority_sections:
        action_preamble, action_blocks = _split_blocks(body, 3)
        if action_blocks:
            priority_sections = [
                {
                    "heading": "Media Priorità",
                    "content": _join_blocks(action_preamble, action_blocks, 3).rstrip("\n"),
                }
            ]
            doc_preamble = ""
            changes.append("wrapped legacy flat health actions into 'Media Priorità'")

    rebuilt_sections = []
    unknown_sections = []
    for priority_section in priority_sections:
        original_heading = priority_section["heading"]
        normalized_heading = _normalize_priority_heading(original_heading)
        if normalized_heading != original_heading:
            changes.append(f"normalized priority heading '{original_heading}' -> '{normalized_heading}'")

        section_preamble, blocks = _split_blocks(priority_section["content"], 3)
        migrated_blocks = []
        for block in blocks:
            metadata, content = _parse_inline_metadata(block["content"])
            action_id = metadata.get("action_id") or _slugify(block["heading"])
            if action_id and metadata.get("action_id") != action_id:
                metadata["action_id"] = action_id
                changes.append(f"added action_id for '{block['heading']}'")
            if not metadata.get("status"):
                metadata["status"] = "active"
                changes.append(f"added status for '{block['heading']}'")
            migrated_blocks.append(
                {
                    "heading": block["heading"],
                    "content": _render_block_content(metadata, content, ["action_id", "status"]),
                }
            )

        rebuilt = {
            "heading": normalized_heading,
            "content": _join_blocks(section_preamble, migrated_blocks, 3).rstrip("\n"),
        }
        if normalized_heading in PRIORITY_SECTIONS:
            rebuilt_sections.append(rebuilt)
        else:
            unknown_sections.append(rebuilt)
            warnings.append(
                f"Section '{original_heading}' is not a canonical priority heading and was preserved as-is."
            )

    ordered_sections = []
    for priority in PRIORITY_SECTIONS:
        match = next((item for item in rebuilt_sections if item["heading"] == priority), None)
        if match is not None:
            ordered_sections.append(match)
    ordered_sections.extend(unknown_sections)
    return _join_blocks(doc_preamble, ordered_sections, 2)


def _normalize_current_document(subject: str, section: str, body: str, metadata: dict, changes: list[str], warnings: list[str]) -> str:
    if section == "findings":
        body = _migrate_findings(body, metadata["last_updated"], changes)
    elif section == "health_actions":
        body = _migrate_health_actions(body, changes, warnings)

    body = _ensure_section_title(body, subject, section)

    if section in {"profile_summary", "clinical_context", "health_actions"}:
        synced = _sync_last_updated_line(body, metadata["last_updated"])
        if synced != body:
            changes.append("synchronized in-body Last updated line")
            body = synced

    return body


def _migrate_document(subject: str, section: str, raw_content: str) -> tuple[str, dict]:
    metadata, body = _split_frontmatter(raw_content)
    if not metadata or "schema_version" not in metadata:
        return raw_content, {
            "id": section,
            "exists": True,
            "current_schema_version": None,
            "target_schema_version": CURRENT_CONTEXT_SCHEMA_VERSION,
            "needs_migration": False,
            "applied": False,
            "change_count": 0,
            "changes": [],
            "warnings": [
                "Missing YAML frontmatter or schema_version. Unversioned context files are outside the supported migration contract."
            ],
            "status": "manual_intervention_required",
        }

    current_version = _coerce_schema_version(metadata.get("schema_version"))
    changes: list[str] = []
    warnings: list[str] = []

    if current_version > CURRENT_CONTEXT_SCHEMA_VERSION:
        return raw_content, {
            "id": section,
            "exists": True,
            "current_schema_version": current_version,
            "target_schema_version": CURRENT_CONTEXT_SCHEMA_VERSION,
            "needs_migration": False,
            "applied": False,
            "change_count": 0,
            "changes": [],
            "warnings": [
                f"Section schema_version {current_version} is newer than supported version {CURRENT_CONTEXT_SCHEMA_VERSION}; skipped."
            ],
            "status": "unsupported_future_version",
        }

    normalized_metadata = _normalize_metadata(subject, section, metadata, changes)
    migrated_body = _normalize_current_document(subject, section, body, normalized_metadata, changes, warnings)
    migrated_raw = _render_frontmatter(normalized_metadata) + migrated_body.rstrip() + "\n"

    if migrated_raw == raw_content:
        changes = []

    return migrated_raw, {
        "id": section,
        "exists": True,
        "current_schema_version": current_version,
        "target_schema_version": CURRENT_CONTEXT_SCHEMA_VERSION,
        "needs_migration": bool(changes),
        "applied": False,
        "change_count": len(changes),
        "changes": changes,
        "warnings": warnings,
        "status": "needs_migration" if changes else "up_to_date",
    }


def _backup_context_dir(subject: str, backup_root: str | None = None) -> str:
    context_path = get_context_path(subject)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = Path(backup_root) if backup_root else Path("output/context-backups")
    target = base / subject / stamp
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(context_path, target)
    return str(target)


def migrate_context(
    subject: str | None = None,
    section: str | None = None,
    apply: bool = False,
    backup: bool = True,
    backup_root: str | None = None,
) -> dict:
    """Plan or apply deterministic context migrations to the current schema version."""
    subject = subject or get_active_subject()
    section_ids = [validate_context_section(section)] if section else list(CONTEXT_SECTIONS)
    context_path = get_context_path(subject)

    plan_sections = []
    pending_writes: dict[str, str] = {}
    for section_id in section_ids:
        path = context_path / CONTEXT_SECTIONS[section_id]["filename"]
        if not path.exists():
            plan_sections.append(
                {
                    "id": section_id,
                    "exists": False,
                    "current_schema_version": None,
                    "target_schema_version": CURRENT_CONTEXT_SCHEMA_VERSION,
                    "needs_migration": False,
                    "applied": False,
                    "change_count": 0,
                    "changes": [],
                    "warnings": [],
                    "status": "missing",
                    "path": str(path),
                }
            )
            continue

        raw_content = path.read_text(encoding="utf-8")
        migrated_raw, plan = _migrate_document(subject, section_id, raw_content)
        plan["path"] = str(path)
        if plan["needs_migration"]:
            pending_writes[section_id] = migrated_raw
        plan_sections.append(plan)

    backup_path = None
    if apply and pending_writes:
        if backup:
            backup_path = _backup_context_dir(subject, backup_root)
        for section_id, migrated_raw in pending_writes.items():
            path = context_path / CONTEXT_SECTIONS[section_id]["filename"]
            path.write_text(migrated_raw, encoding="utf-8")
            append_context_audit(
                "migrate_section",
                subject=subject,
                section=section_id,
                details={"target_schema_version": CURRENT_CONTEXT_SCHEMA_VERSION},
            )
        for plan in plan_sections:
            if plan["id"] in pending_writes:
                plan["applied"] = True
                plan["status"] = "migrated"

    return {
        "subject": subject,
        "context_path": str(context_path),
        "target_schema_version": CURRENT_CONTEXT_SCHEMA_VERSION,
        "apply": apply,
        "backup_requested": backup,
        "backup_path": backup_path,
        "needs_migration": any(plan["needs_migration"] for plan in plan_sections),
        "section_count": len(plan_sections),
        "migrated_count": sum(1 for plan in plan_sections if plan.get("applied")),
        "sections": plan_sections,
    }
