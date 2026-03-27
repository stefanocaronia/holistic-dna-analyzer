"""Helpers for subject clinical documents stored under context folders."""

from datetime import UTC, date, datetime
from pathlib import Path
import json
import re
import shutil

from hda.config import get_active_subject, get_context_path
from hda.context_audit import append_context_audit
from hda.context_store import _join_blocks, _split_blocks, read_context, replace_context_section

DOCUMENTS_DIRNAME = "documents"
DOCUMENTS_INBOX_DIRNAME = "documents_inbox"
DOCUMENTS_MANIFEST_FILENAME = ".manifest.json"
DOCUMENT_MARKDOWN_SUFFIX = ".extracted.md"
DOCUMENT_CATEGORY_KEYWORDS = {
    "labs": ("esami-sangue", "blood", "lab", "labs", "emocromo", "ferritina", "ferritin", "cbc"),
    "imaging": ("ecografia", "eco", "rm", "risonanza", "tac", "rx", "xray", "imaging", "holter"),
    "visit": ("visita", "visit", "referto", "consulto", "specialistica"),
    "prescriptions": ("ricetta", "prescrizione", "prescription"),
}
CLINICAL_SECTION_BY_CATEGORY = {
    "labs": "Recent Labs & Imaging",
    "imaging": "Recent Labs & Imaging",
    "visit": "Care Team & Pending Tests",
    "prescriptions": "Current Medications & Supplements",
    "general": "Recent Labs & Imaging",
}
LAB_RESULT_HINTS = ("[", "10^", "g/l", "mg", "mmol", "pg", "fl", "%", "ui/l", "ng/ml")


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "document"


def _normalize_date(document_date: str | None) -> str:
    if not document_date:
        return date.today().isoformat()
    return date.fromisoformat(document_date).isoformat()


def _documents_root(subject: str | None = None) -> Path:
    subject = subject or get_active_subject()
    return get_context_path(subject) / DOCUMENTS_DIRNAME


def _inbox_root(subject: str | None = None) -> Path:
    subject = subject or get_active_subject()
    return get_context_path(subject) / DOCUMENTS_INBOX_DIRNAME


def _manifest_path(subject: str | None = None) -> Path:
    return _documents_root(subject) / DOCUMENTS_MANIFEST_FILENAME


def _load_manifest(subject: str | None = None) -> list[dict]:
    path = _manifest_path(subject)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _save_manifest(entries: list[dict], subject: str | None = None) -> None:
    path = _manifest_path(subject)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _upsert_manifest_entry(subject: str, entry: dict) -> None:
    manifest_entries = [item for item in _load_manifest(subject) if item.get("relative_path") != entry["relative_path"]]
    manifest_entries.append(
        {
            key: value
            for key, value in entry.items()
            if key not in {"path", "subject", "extracted_text"}
        }
    )
    _save_manifest(manifest_entries, subject)


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _scan_documents(subject: str | None = None) -> list[dict]:
    root = _documents_root(subject)
    if not root.exists():
        return []

    scanned = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        if file_path.name.endswith(DOCUMENT_MARKDOWN_SUFFIX):
            continue
        relative = file_path.relative_to(get_context_path(subject or get_active_subject()))
        parts = relative.parts
        document_date = None
        category = "general"
        if len(parts) >= 3 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[1]):
            document_date = parts[1]
        if len(parts) >= 4:
            category = parts[2]
        scanned.append(
            {
                "id": f"{document_date or 'undated'}-{category}-{file_path.stem}",
                "title": file_path.stem.replace("-", " ").replace("_", " ").strip().title(),
                "category": category,
                "document_date": document_date,
                "filename": file_path.name,
                "relative_path": str(relative).replace("\\", "/"),
                "path": str(file_path),
                "source_name": file_path.name,
                "imported_at": None,
                "notes": None,
            }
        )
    return scanned


def _infer_category_from_name(filename: str) -> str | None:
    normalized = _slugify(Path(filename).stem)
    for category, keywords in DOCUMENT_CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return None


def _clinical_heading_for_document(entry: dict) -> str:
    return f"{entry['document_date']} - {entry['title']}"


def _extract_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""
    if suffix in {".txt", ".md", ".csv"}:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1", errors="ignore")
    return ""


def _markdown_sidecar_path(document_path: Path) -> Path:
    return document_path.with_name(f"{document_path.stem}{DOCUMENT_MARKDOWN_SUFFIX}")


def _clean_summary_lines(text: str, limit: int = 3) -> list[str]:
    lines = []
    seen = set()
    for raw_line in text.splitlines():
        line = " ".join(raw_line.strip().split())
        if len(line) < 3:
            continue
        if line.lower() in seen:
            continue
        seen.add(line.lower())
        lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _summary_lines_for_entry(entry: dict, extracted_text: str, limit: int = 3) -> list[str]:
    if entry.get("category") == "labs":
        lab_lines = []
        for raw_line in extracted_text.splitlines():
            line = " ".join(raw_line.strip().split())
            normalized = line.lower()
            if len(line) < 8 or not re.search(r"\d", line):
                continue
            if not any(hint in normalized for hint in LAB_RESULT_HINTS):
                continue
            if any(noise in normalized for noise in ("tel.", "date of birth", "accettazione", "ricezione", "req.", "source:")):
                continue
            lab_lines.append(line)
            if len(lab_lines) >= limit:
                return lab_lines
    return _clean_summary_lines(extracted_text, limit=limit)


def _document_section_for_category(category: str) -> str:
    return CLINICAL_SECTION_BY_CATEGORY.get(category, "Recent Labs & Imaging")


def _render_document_integration(entry: dict, extracted_text: str) -> str:
    summary_lines = _summary_lines_for_entry(entry, extracted_text)
    bullets = [
        f"- Category: {entry['category']}",
        f"- Original document: `{entry['relative_path']}`",
    ]
    if entry.get("markdown_relative_path"):
        bullets.append(f"- Extracted markdown: `{entry['markdown_relative_path']}`")
    if summary_lines:
        bullets.append("- Indexed summary:")
        bullets.extend(f"  - {line}" for line in summary_lines)
    else:
        bullets.append("- Indexed summary: extraction unavailable or inconclusive; review the original document or sidecar.")
    return "\n".join(bullets)


def _render_extracted_markdown(entry: dict, extracted_text: str) -> str:
    extracted_text = extracted_text.strip()
    parts = [
        f"# {entry['title']}",
        "",
        f"- Document date: {entry['document_date']}",
        f"- Category: {entry['category']}",
        f"- Original document: `{entry['relative_path']}`",
    ]
    if entry.get("source_name"):
        parts.append(f"- Source name: {entry['source_name']}")
    if entry.get("imported_at"):
        parts.append(f"- Imported at: {entry['imported_at']}")
    parts.extend(["", "## Extracted Text", ""])
    if extracted_text:
        parts.append(extracted_text)
    else:
        parts.append("Text extraction unavailable or inconclusive. Review the original document.")
    return "\n".join(parts).rstrip() + "\n"


def _read_extracted_markdown_text(markdown_path: Path) -> str:
    if not markdown_path.exists():
        return ""
    content = markdown_path.read_text(encoding="utf-8")
    marker = "\n## Extracted Text\n\n"
    if marker in content:
        return content.split(marker, 1)[1].strip()
    return content.strip()


def ensure_document_sidecar(entry: dict) -> dict:
    """Create or refresh the extracted Markdown sidecar for an archived document."""
    document_path = Path(entry["path"])
    markdown_path = _markdown_sidecar_path(document_path)
    extracted_text = _extract_document_text(document_path)
    markdown_path.write_text(_render_extracted_markdown(entry, extracted_text), encoding="utf-8")
    relative = markdown_path.relative_to(get_context_path(entry["subject"]))
    return {
        **entry,
        "markdown_path": str(markdown_path),
        "markdown_filename": markdown_path.name,
        "markdown_relative_path": str(relative).replace("\\", "/"),
        "extracted_text": extracted_text,
    }


def integrate_context_document(entry: dict, subject: str | None = None) -> dict:
    """Summarize an archived document into clinical_context.md."""
    subject = subject or get_active_subject()
    entry = {**entry, "subject": subject}
    if not entry.get("markdown_relative_path"):
        entry = ensure_document_sidecar(entry)
        _upsert_manifest_entry(subject, entry)
    section_heading = _document_section_for_category(entry["category"])
    heading = _clinical_heading_for_document(entry)
    text = entry.get("extracted_text", "")
    if not text:
        text = _extract_document_text(Path(entry["path"]))
    if not text and entry.get("markdown_path"):
        text = _read_extracted_markdown_text(Path(entry["markdown_path"]))
    if not text and entry.get("markdown_relative_path"):
        text = _read_extracted_markdown_text(get_context_path(subject) / entry["markdown_relative_path"])
    rendered = _render_document_integration(entry, text)

    clinical = read_context(subject, "clinical_context")
    body = clinical.get("content") or ""
    _, sections = _split_blocks(body, 2)
    existing_section = next((block for block in sections if block["heading"] == section_heading), None)
    section_body = existing_section["content"] if existing_section else ""
    preamble, blocks = _split_blocks(section_body, 3)

    replaced = False
    for block in blocks:
        if block["heading"] == heading:
            block["content"] = rendered
            replaced = True
            break
    if not replaced:
        blocks.append({"heading": heading, "content": rendered})

    replace_context_section("clinical_context", section_heading, _join_blocks(preamble, blocks, 3).rstrip("\n"), subject)
    append_context_audit(
        "integrate_document",
        subject=subject,
        section="clinical_context",
        details={"filename": entry["filename"], "category": entry["category"], "heading": heading},
    )
    return {
        "subject": subject,
        "section": section_heading,
        "heading": heading,
        "markdown_relative_path": entry.get("markdown_relative_path"),
        "summary_lines": _summary_lines_for_entry(entry, text),
    }


def _infer_inbox_metadata(file_path: Path, inbox_root: Path) -> dict:
    relative = file_path.relative_to(inbox_root)
    folder_parts = relative.parts[:-1]
    document_date = date.fromtimestamp(file_path.stat().st_mtime).isoformat()
    category = "general"

    if folder_parts:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", folder_parts[0]):
            document_date = folder_parts[0]
            if len(folder_parts) >= 2:
                category = _slugify(folder_parts[1])
        else:
            category = _slugify(folder_parts[0])
    else:
        category = _infer_category_from_name(file_path.name) or category

    return {
        "document_date": document_date,
        "category": category,
        "title": file_path.stem.replace("-", " ").replace("_", " ").strip().title(),
        "relative_path": str(relative).replace("\\", "/"),
        "source_path": str(file_path),
        "filename": file_path.name,
    }


def _scan_inbox(subject: str | None = None) -> list[dict]:
    root = _inbox_root(subject)
    if not root.exists():
        return []

    inbox_documents = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        inbox_documents.append(_infer_inbox_metadata(file_path, root))
    return inbox_documents


def _prune_empty_dirs(root: Path) -> None:
    if not root.exists():
        return
    for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            continue
    try:
        root.rmdir()
    except OSError:
        pass


def list_context_documents(subject: str | None = None) -> dict:
    """List stored context documents for a subject, including manually added files."""
    subject = subject or get_active_subject()
    root = _documents_root(subject)
    manifest_entries = _load_manifest(subject)
    merged = {}

    for entry in _scan_documents(subject):
        merged[entry["relative_path"]] = entry

    for entry in manifest_entries:
        rel = entry.get("relative_path")
        if not rel:
            continue
        path = get_context_path(subject) / rel
        merged[rel] = {
            **merged.get(rel, {}),
            **entry,
            "path": str(path),
            "exists": path.exists(),
        }

    documents = list(merged.values())
    for item in documents:
        item.setdefault("exists", Path(item["path"]).exists())
    documents.sort(
        key=lambda item: (
            item.get("document_date") or "",
            item.get("imported_at") or "",
            item.get("filename") or "",
        ),
        reverse=True,
    )
    return {
        "subject": subject,
        "documents_path": str(root),
        "manifest_path": str(_manifest_path(subject)),
        "count": len(documents),
        "documents": documents,
    }


def list_context_inbox(subject: str | None = None) -> dict:
    """List pending files dropped into the subject document inbox."""
    subject = subject or get_active_subject()
    inbox_root = _inbox_root(subject)
    inbox_root.mkdir(parents=True, exist_ok=True)
    documents = _scan_inbox(subject)
    return {
        "subject": subject,
        "inbox_path": str(inbox_root),
        "count": len(documents),
        "documents": documents,
    }


def import_context_document(
    source_path: str,
    subject: str | None = None,
    document_date: str | None = None,
    category: str | None = None,
    title: str | None = None,
    notes: str | None = None,
    move: bool = False,
    integrate: bool = True,
) -> dict:
    """Copy or move a clinical document into the subject context folder."""
    subject = subject or get_active_subject()
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Document not found: {source}")
    if not source.is_file():
        raise ValueError(f"Document path must be a file: {source}")

    normalized_date = _normalize_date(document_date)
    category_slug = _slugify(category or "general")
    title_slug = _slugify(title or source.stem)
    target_dir = _documents_root(subject) / normalized_date / category_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(target_dir / f"{title_slug}{source.suffix.lower()}")

    if move:
        shutil.move(str(source), str(destination))
    else:
        shutil.copy2(source, destination)

    relative = destination.relative_to(get_context_path(subject))
    imported_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    entry = {
        "id": f"{normalized_date}-{category_slug}-{destination.stem}",
        "subject": subject,
        "title": title or source.stem,
        "category": category_slug,
        "document_date": normalized_date,
        "filename": destination.name,
        "relative_path": str(relative).replace("\\", "/"),
        "path": str(destination),
        "source_name": source.name,
        "imported_at": imported_at,
        "notes": notes,
    }

    if integrate:
        entry = ensure_document_sidecar(entry)

    _upsert_manifest_entry(subject, entry)
    append_context_audit(
        "import_document",
        subject=subject,
        section="clinical_context",
        details={
            "document_date": normalized_date,
            "category": category_slug,
            "filename": destination.name,
        },
    )
    integration = integrate_context_document(entry, subject) if integrate else None
    return {
        "subject": subject,
        "documents_path": str(_documents_root(subject)),
        "document": entry,
        "integration": integration,
    }


def import_context_inbox(
    subject: str | None = None,
    document_date: str | None = None,
    category: str | None = None,
    move: bool = True,
    integrate: bool = True,
) -> dict:
    """Import every pending file from the subject inbox into the dated archive."""
    subject = subject or get_active_subject()
    inbox_root = _inbox_root(subject)
    inbox_root.mkdir(parents=True, exist_ok=True)
    pending = _scan_inbox(subject)
    imported = []

    for item in pending:
        result = import_context_document(
            item["source_path"],
            subject=subject,
            document_date=document_date or item["document_date"],
            category=category or item["category"],
            title=item["title"],
            move=move,
            integrate=integrate,
        )
        imported.append(result["document"])

    if move:
        _prune_empty_dirs(inbox_root)

    return {
        "subject": subject,
        "inbox_path": str(inbox_root),
        "documents_path": str(_documents_root(subject)),
        "imported_count": len(imported),
        "imported": imported,
    }
