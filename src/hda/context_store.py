"""Helpers for subject context files.

Context remains human-readable Markdown on disk, but these helpers provide a
stable access layer so agents do not need to know file paths or ad hoc naming
conventions. They also implement constrained write operations so context can be
edited without collapsing back into free-form file appends.
"""

from datetime import date, datetime
from pathlib import Path
import re

import yaml

from hda.config import get_active_subject, get_context_path
from hda.context_audit import append_context_audit

CONTEXT_SECTIONS: dict[str, dict[str, str]] = {
    "profile_summary": {
        "filename": "profile_summary.md",
        "description": "Integrated one-page genetic portrait for quick session startup.",
    },
    "clinical_context": {
        "filename": "clinical_context.md",
        "description": "Non-genetic health context: medications, diagnoses, family history, labs, and intake details.",
    },
    "findings": {
        "filename": "findings.md",
        "description": "Notable discoveries worth preserving across sessions.",
    },
    "health_actions": {
        "filename": "health_actions.md",
        "description": "Consolidated recommendations synthesized from findings.",
    },
    "session_notes": {
        "filename": "session_notes.md",
        "description": "User-specific notes, concerns, and follow-ups from conversations.",
    },
}

CURRENT_CONTEXT_SCHEMA_VERSION = 1
PRIORITY_SECTIONS = ["Alta Priorità", "Media Priorità", "Bassa Priorità"]
FRONTMATTER_ORDER = ["subject", "doc_type", "title", "last_updated", "schema_version", "status", "tags"]


def validate_context_section(section: str) -> str:
    """Ensure the section key is one of the supported context files."""
    if section not in CONTEXT_SECTIONS:
        available = ", ".join(CONTEXT_SECTIONS)
        raise KeyError(f"Unknown context section '{section}'. Available: {available}")
    return section


def _today_iso() -> str:
    return date.today().isoformat()


def _normalize_metadata(value):
    """Convert YAML-native objects to plain serializable values."""
    if isinstance(value, dict):
        return {k: _normalize_metadata(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_metadata(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _humanize_slug(text: str) -> str:
    parts = [part for part in text.strip().split("_") if part]
    if not parts:
        return text
    return " ".join(part.capitalize() for part in parts)


def _default_title(subject: str, section: str) -> str:
    pretty_subject = subject.replace("_", " ").title()
    if section == "profile_summary":
        return f"{pretty_subject} — Genetic Profile Summary"
    if section == "clinical_context":
        return f"{pretty_subject} — Clinical Context"
    if section == "health_actions":
        return f"{pretty_subject} — Recommended Health Actions"
    if section == "session_notes":
        return f"{pretty_subject} — Session Notes"
    return f"{pretty_subject} — Findings"


def _default_frontmatter(subject: str, section: str) -> dict:
    return {
        "subject": subject,
        "doc_type": section,
        "title": _default_title(subject, section),
        "last_updated": _today_iso(),
        "schema_version": CURRENT_CONTEXT_SCHEMA_VERSION,
    }


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split optional YAML frontmatter from Markdown body."""
    if not text.startswith("---\n"):
        return {}, text

    marker = "\n---\n"
    end_index = text.find(marker, 4)
    if end_index == -1:
        return {}, text

    frontmatter_text = text[4:end_index]
    body = text[end_index + len(marker) :]
    if body.startswith("\n"):
        body = body[1:]
    metadata = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return _normalize_metadata(metadata), body


def _render_frontmatter(metadata: dict) -> str:
    normalized = _normalize_metadata(metadata)
    ordered: dict = {}
    for key in FRONTMATTER_ORDER:
        if key in normalized and normalized[key] is not None:
            ordered[key] = normalized[key]
    for key, value in normalized.items():
        if key not in ordered and value is not None:
            ordered[key] = value
    yaml_text = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{yaml_text}\n---\n\n"


def _sync_last_updated_line(body: str, iso_date: str) -> str:
    return re.sub(r"(?m)^Last updated: .+$", f"Last updated: {iso_date}", body, count=1)


def _split_blocks(text: str, level: int) -> tuple[str, list[dict]]:
    """Split markdown text into a preamble and heading-based blocks."""
    pattern = re.compile(rf"(?m)^{'#' * level} (.+)$")
    matches = list(pattern.finditer(text))
    if not matches:
        return text.rstrip("\n"), []

    preamble = text[: matches[0].start()].rstrip("\n")
    blocks = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = match.group(1).strip()
        content = text[match.end() : end]
        if content.startswith("\n"):
            content = content[1:]
        blocks.append({"heading": heading, "content": content.rstrip("\n")})
    return preamble, blocks


def _join_blocks(preamble: str, blocks: list[dict], level: int) -> str:
    parts: list[str] = []
    preamble = preamble.rstrip("\n")
    if preamble:
        parts.append(preamble)
    for block in blocks:
        if parts:
            parts.append("")
        parts.append(f"{'#' * level} {block['heading']}")
        if block["content"]:
            parts.append("")
            parts.append(block["content"].rstrip("\n"))
    return ("\n".join(parts).rstrip() + "\n") if parts else ""


def _parse_inline_metadata(content: str) -> tuple[dict, str]:
    """Parse `key: value` lines at the top of a block."""
    lines = content.splitlines()
    metadata: dict[str, str] = {}
    index = 0

    while index < len(lines) and not lines[index].strip():
        index += 1

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            break
        if ":" not in line:
            break
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or " " in key:
            break
        metadata[key] = value
        index += 1

    body = "\n".join(lines[index:]).lstrip("\n").rstrip("\n")
    return metadata, body


def _render_inline_metadata(metadata: dict, preferred_order: list[str] | None = None) -> list[str]:
    preferred_order = preferred_order or []
    lines = []
    seen = set()
    for key in preferred_order:
        if key in metadata and metadata[key] is not None:
            value = metadata[key]
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            lines.append(f"{key}: {value}")
            seen.add(key)
    for key, value in metadata.items():
        if key in seen or value is None:
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        lines.append(f"{key}: {value}")
    return lines


def _render_block_content(metadata: dict, body: str, preferred_order: list[str] | None = None) -> str:
    body = body.rstrip("\n")
    metadata_lines = _render_inline_metadata(metadata, preferred_order)
    parts: list[str] = []
    if metadata_lines:
        parts.extend(metadata_lines)
    if body:
        if parts:
            parts.append("")
        parts.append(body)
    return "\n".join(parts).rstrip("\n")


def _ensure_section_title(body: str, subject: str, section: str) -> str:
    body = body.lstrip("\n")
    if body.startswith("# "):
        return body
    return f"# {_default_title(subject, section)}\n\n{body}".rstrip() + "\n"


def _section_payload(context_path: Path, section_id: str) -> dict:
    meta = CONTEXT_SECTIONS[section_id]
    path = context_path / meta["filename"]
    exists = path.exists()
    raw_content = path.read_text(encoding="utf-8") if exists else None
    metadata = {}
    content = raw_content
    if raw_content is not None:
        metadata, content = _split_frontmatter(raw_content)
    return {
        "id": section_id,
        "filename": meta["filename"],
        "description": meta["description"],
        "path": str(path),
        "exists": exists,
        "metadata": metadata,
        "content": content,
        "raw_content": raw_content,
    }


def _read_existing(subject: str, section: str) -> tuple[Path, dict, str]:
    section_id = validate_context_section(section)
    payload = _section_payload(get_context_path(subject), section_id)
    path = Path(payload["path"])
    metadata = payload["metadata"] or _default_frontmatter(subject, section_id)
    body = payload["content"] or ""
    return path, metadata, body


def _write_section(subject: str, section: str, metadata: dict, body: str) -> dict:
    path = get_context_path(subject) / CONTEXT_SECTIONS[section]["filename"]
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _render_frontmatter(metadata) + body.rstrip() + "\n"
    path.write_text(raw, encoding="utf-8")
    return read_context(subject, section)


def list_context_sections(subject: str | None = None) -> dict:
    """List the standard context sections for a subject."""
    subject = subject or get_active_subject()
    context_path = get_context_path(subject)
    sections = []
    for section_id in CONTEXT_SECTIONS:
        payload = _section_payload(context_path, section_id)
        payload.pop("content")
        payload.pop("raw_content")
        sections.append(payload)
    return {
        "subject": subject,
        "context_path": str(context_path),
        "sections": sections,
    }


def read_context(subject: str | None = None, section: str | None = None) -> dict:
    """Read one or all context sections for a subject."""
    subject = subject or get_active_subject()
    context_path = get_context_path(subject)

    if section is not None:
        section_id = validate_context_section(section)
        payload = _section_payload(context_path, section_id)
        return {
            "subject": subject,
            "context_path": str(context_path),
            **payload,
        }

    return {
        "subject": subject,
        "context_path": str(context_path),
        "sections": [_section_payload(context_path, section_id) for section_id in CONTEXT_SECTIONS],
    }


def read_context_block(section: str, block_id: str, subject: str | None = None) -> dict:
    """Read a single structured block from findings, health_actions, or session_notes."""
    subject = subject or get_active_subject()
    section = validate_context_section(section)
    _, _, body = _read_existing(subject, section)

    if section == "findings":
        _, blocks = _split_blocks(body, 2)
        for block in blocks:
            metadata, content = _parse_inline_metadata(block["content"])
            finding_id = metadata.get("finding_id") or _slugify(block["heading"])
            if finding_id == block_id:
                metadata["finding_id"] = finding_id
                return {
                    "subject": subject,
                    "section": section,
                    "block_id": finding_id,
                    "heading": block["heading"],
                    "metadata": metadata,
                    "content": content,
                }
        raise KeyError(f"Block '{block_id}' not found in section '{section}'")

    if section == "health_actions":
        _, sections = _split_blocks(body, 2)
        for priority_section in sections:
            _, blocks = _split_blocks(priority_section["content"], 3)
            for block in blocks:
                metadata, content = _parse_inline_metadata(block["content"])
                action_id = metadata.get("action_id") or _slugify(block["heading"])
                if action_id == block_id:
                    metadata["action_id"] = action_id
                    return {
                        "subject": subject,
                        "section": section,
                        "block_id": block_id,
                        "heading": block["heading"],
                        "destination": priority_section["heading"],
                        "metadata": metadata,
                        "content": content,
                    }
        raise KeyError(f"Block '{block_id}' not found in section '{section}'")

    if section == "session_notes":
        _, blocks = _split_blocks(body, 2)
        for block in blocks:
            if block["heading"] == block_id:
                return {
                    "subject": subject,
                    "section": section,
                    "block_id": block_id,
                    "heading": block["heading"],
                    "metadata": {},
                    "content": block["content"],
                }
        raise KeyError(f"Block '{block_id}' not found in section '{section}'")

    raise ValueError(f"Section '{section}' does not expose block-level reads")


def write_context_document(section: str, content: str, subject: str | None = None) -> dict:
    """Replace an entire context document while preserving frontmatter."""
    subject = subject or get_active_subject()
    section = validate_context_section(section)
    _, metadata, _ = _read_existing(subject, section)
    metadata = {**metadata, "subject": subject, "doc_type": section, "last_updated": _today_iso()}
    body = _ensure_section_title(_sync_last_updated_line(content, metadata["last_updated"]), subject, section)
    payload = _write_section(subject, section, metadata, body)
    append_context_audit("write_document", subject=subject, section=section, details={"mode": "replace_document"})
    return payload


def replace_context_section(
    section: str,
    heading: str,
    content: str,
    subject: str | None = None,
) -> dict:
    """Replace or append a `##` section inside a maintained document."""
    subject = subject or get_active_subject()
    section = validate_context_section(section)
    if section not in {"profile_summary", "clinical_context", "health_actions"}:
        raise ValueError("replace_context_section is only supported for profile_summary, clinical_context, and health_actions")

    _, metadata, body = _read_existing(subject, section)
    preamble, blocks = _split_blocks(body, 2)
    block_content = content.strip()

    replaced = False
    for block in blocks:
        if block["heading"] == heading:
            block["content"] = block_content
            replaced = True
            break
    if not replaced:
        blocks.append({"heading": heading, "content": block_content})

    metadata["last_updated"] = _today_iso()
    new_body = _join_blocks(preamble, blocks, 2)
    new_body = _ensure_section_title(_sync_last_updated_line(new_body, metadata["last_updated"]), subject, section)
    payload = _write_section(subject, section, metadata, new_body)
    append_context_audit("replace_section", subject=subject, section=section, details={"heading": heading})
    return payload


def upsert_context_block(
    section: str,
    block_id: str,
    content: str,
    subject: str | None = None,
    metadata: dict | None = None,
    title: str | None = None,
    destination: str | None = None,
    _skip_audit: bool = False,
) -> dict:
    """Upsert a structured block inside findings or health_actions."""
    subject = subject or get_active_subject()
    section = validate_context_section(section)
    metadata = dict(metadata or {})

    if section == "findings":
        payload = _upsert_finding(subject, block_id, content, metadata)
        if not _skip_audit:
            append_context_audit(
                "upsert_block",
                subject=subject,
                section=section,
                details={"block_id": block_id, "title": title or block_id},
            )
        return payload
    if section == "health_actions":
        payload = _upsert_health_action(subject, block_id, title, content, metadata, destination)
        if not _skip_audit:
            append_context_audit(
                "upsert_block",
                subject=subject,
                section=section,
                details={"block_id": block_id, "title": title or block_id, "destination": destination},
            )
        return payload
    raise ValueError("upsert_context_block is only supported for findings and health_actions")


def move_context_block(section: str, block_id: str, destination: str, subject: str | None = None) -> dict:
    """Move a structured block to another destination."""
    subject = subject or get_active_subject()
    section = validate_context_section(section)
    if section != "health_actions":
        raise ValueError("move_context_block is currently only supported for health_actions")
    if destination not in PRIORITY_SECTIONS:
        raise ValueError(f"Destination must be one of: {', '.join(PRIORITY_SECTIONS)}")

    _, file_metadata, body = _read_existing(subject, section)
    doc_preamble, priority_sections = _split_blocks(body, 2)
    moving_block = None

    parsed_sections = []
    for priority_section in priority_sections:
        section_preamble, blocks = _split_blocks(priority_section["content"], 3)
        kept_blocks = []
        for block in blocks:
            block_metadata, _ = _parse_inline_metadata(block["content"])
            action_id = block_metadata.get("action_id") or _slugify(block["heading"])
            if action_id == block_id:
                moving_block = block
                block_metadata["action_id"] = action_id
                block["content"] = _render_block_content(block_metadata, _parse_inline_metadata(block["content"])[1], ["action_id", "status"])
            else:
                kept_blocks.append(block)
        parsed_sections.append(
            {
                "heading": priority_section["heading"],
                "preamble": section_preamble,
                "blocks": kept_blocks,
            }
        )

    if moving_block is None:
        raise KeyError(f"Block '{block_id}' not found in section '{section}'")

    inserted = False
    for priority_section in parsed_sections:
        if priority_section["heading"] == destination:
            priority_section["blocks"].append(moving_block)
            inserted = True
            break
    if not inserted:
        parsed_sections.append({"heading": destination, "preamble": "", "blocks": [moving_block]})

    blocks = []
    for priority in PRIORITY_SECTIONS:
        match = next((section_data for section_data in parsed_sections if section_data["heading"] == priority), None)
        if match is None:
            continue
        blocks.append(
            {
                "heading": match["heading"],
                "content": _join_blocks(match["preamble"], match["blocks"], 3).rstrip("\n"),
            }
        )

    file_metadata["last_updated"] = _today_iso()
    new_body = _join_blocks(doc_preamble, blocks, 2)
    new_body = _ensure_section_title(_sync_last_updated_line(new_body, file_metadata["last_updated"]), subject, section)
    payload = _write_section(subject, section, file_metadata, new_body)
    append_context_audit(
        "move_block",
        subject=subject,
        section=section,
        details={"block_id": block_id, "destination": destination},
    )
    return payload


def archive_context_block(section: str, block_id: str, subject: str | None = None) -> dict:
    """Archive a structured block."""
    subject = subject or get_active_subject()
    section = validate_context_section(section)

    if section == "findings":
        block = read_context_block(section, block_id, subject)
        metadata = {**block["metadata"], "status": "archived", "updated": _today_iso()}
        payload = upsert_context_block(section, block_id, block["content"], subject=subject, metadata=metadata, _skip_audit=True)
        append_context_audit("archive_block", subject=subject, section=section, details={"block_id": block_id})
        return payload

    if section == "health_actions":
        block = read_context_block(section, block_id, subject)
        metadata = {**block["metadata"], "status": "archived"}
        result = upsert_context_block(
            section,
            block_id,
            block["content"],
            subject=subject,
            metadata=metadata,
            title=block["heading"],
            destination="Bassa Priorità",
            _skip_audit=True,
        )
        append_context_audit("archive_block", subject=subject, section=section, details={"block_id": block_id})
        return result

    raise ValueError("archive_context_block is only supported for findings and health_actions")


def append_context_entry(
    section: str,
    title: str,
    content: str,
    subject: str | None = None,
    entry_date: str | None = None,
) -> dict:
    """Append a dated entry to a chronological context file."""
    subject = subject or get_active_subject()
    section = validate_context_section(section)
    if section != "session_notes":
        raise ValueError("append_context_entry is only supported for session_notes")

    _, metadata, body = _read_existing(subject, section)
    entry_date = entry_date or _today_iso()
    heading = f"{entry_date}: {title}"
    doc_preamble, blocks = _split_blocks(body, 2)
    blocks.append({"heading": heading, "content": content.strip()})

    metadata["last_updated"] = _today_iso()
    new_body = _join_blocks(doc_preamble, blocks, 2)
    new_body = _ensure_section_title(new_body, subject, section)
    payload = _write_section(subject, section, metadata, new_body)
    append_context_audit(
        "append_entry",
        subject=subject,
        section=section,
        details={"heading": heading},
    )
    return payload


def replace_context_entry(
    section: str,
    heading: str,
    content: str,
    subject: str | None = None,
) -> dict:
    """Replace an existing dated entry in session_notes."""
    subject = subject or get_active_subject()
    section = validate_context_section(section)
    if section != "session_notes":
        raise ValueError("replace_context_entry is only supported for session_notes")

    _, metadata, body = _read_existing(subject, section)
    doc_preamble, blocks = _split_blocks(body, 2)
    replaced = False
    for block in blocks:
        if block["heading"] == heading:
            block["content"] = content.strip()
            replaced = True
            break
    if not replaced:
        raise KeyError(f"Entry '{heading}' not found in section '{section}'")

    metadata["last_updated"] = _today_iso()
    new_body = _join_blocks(doc_preamble, blocks, 2)
    new_body = _ensure_section_title(new_body, subject, section)
    payload = _write_section(subject, section, metadata, new_body)
    append_context_audit(
        "replace_entry",
        subject=subject,
        section=section,
        details={"heading": heading},
    )
    return payload


def _upsert_finding(subject: str, block_id: str, content: str, metadata: dict) -> dict:
    _, file_metadata, body = _read_existing(subject, "findings")
    doc_preamble, blocks = _split_blocks(body, 2)
    content = content.strip()
    today = _today_iso()
    heading_title = title = metadata.pop("title", None)

    found = False
    for block in blocks:
        existing_metadata, _ = _parse_inline_metadata(block["content"])
        existing_id = existing_metadata.get("finding_id") or _slugify(block["heading"])
        if existing_id != block_id:
            continue
        merged_metadata = {**existing_metadata, **metadata}
        merged_metadata["finding_id"] = block_id
        merged_metadata.setdefault("created", existing_metadata.get("created", today))
        merged_metadata["updated"] = today
        merged_metadata.setdefault("status", "active")
        if title:
            block["heading"] = title
        block["content"] = _render_block_content(
            merged_metadata,
            content,
            ["finding_id", "created", "updated", "status", "domains"],
        )
        found = True
        break

    if not found:
        new_metadata = {**metadata}
        new_metadata["finding_id"] = block_id
        new_metadata.setdefault("created", today)
        new_metadata["updated"] = today
        new_metadata.setdefault("status", "active")
        blocks.append(
            {
                "heading": heading_title or _humanize_slug(block_id),
                "content": _render_block_content(
                    new_metadata,
                    content,
                    ["finding_id", "created", "updated", "status", "domains"],
                ),
            }
        )

    file_metadata["last_updated"] = today
    new_body = _join_blocks(doc_preamble, blocks, 2)
    new_body = _ensure_section_title(new_body, subject, "findings")
    return _write_section(subject, "findings", file_metadata, new_body)


def _upsert_health_action(
    subject: str,
    block_id: str,
    title: str | None,
    content: str,
    metadata: dict,
    destination: str | None,
) -> dict:
    if destination is None:
        raise ValueError("destination is required for health_actions upserts")
    if destination not in PRIORITY_SECTIONS:
        raise ValueError(f"Destination must be one of: {', '.join(PRIORITY_SECTIONS)}")

    _, file_metadata, body = _read_existing(subject, "health_actions")
    doc_preamble, priority_sections = _split_blocks(body, 2)
    action_title = title or block_id.replace("_", " ").title()
    content = content.strip()

    parsed_sections = []
    existing_metadata = None
    for priority_section in priority_sections:
        section_preamble, blocks = _split_blocks(priority_section["content"], 3)
        kept_blocks = []
        for block in blocks:
            block_metadata, block_body = _parse_inline_metadata(block["content"])
            action_id = block_metadata.get("action_id") or _slugify(block["heading"])
            if action_id == block_id:
                existing_metadata = block_metadata
                if not title:
                    action_title = block["heading"]
                continue
            kept_blocks.append(block)
        parsed_sections.append(
            {
                "heading": priority_section["heading"],
                "preamble": section_preamble,
                "blocks": kept_blocks,
            }
        )

    merged_metadata = {**(existing_metadata or {}), **metadata}
    merged_metadata["action_id"] = block_id
    merged_metadata.setdefault("status", "active")
    rendered_block = {
        "heading": action_title,
        "content": _render_block_content(merged_metadata, content, ["action_id", "status"]),
    }

    target_section = next((section_data for section_data in parsed_sections if section_data["heading"] == destination), None)
    if target_section is None:
        target_section = {"heading": destination, "preamble": "", "blocks": []}
        parsed_sections.append(target_section)
    target_section["blocks"].append(rendered_block)

    rebuilt_sections = []
    for priority in PRIORITY_SECTIONS:
        match = next((section_data for section_data in parsed_sections if section_data["heading"] == priority), None)
        if match is None:
            continue
        rebuilt_sections.append(
            {
                "heading": match["heading"],
                "content": _join_blocks(match["preamble"], match["blocks"], 3).rstrip("\n"),
            }
        )

    file_metadata["last_updated"] = _today_iso()
    new_body = _join_blocks(doc_preamble, rebuilt_sections, 2)
    new_body = _ensure_section_title(_sync_last_updated_line(new_body, file_metadata["last_updated"]), subject, "health_actions")
    return _write_section(subject, "health_actions", file_metadata, new_body)
