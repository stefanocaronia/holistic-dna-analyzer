"""CLI entry point for Holistic DNA Analyzer (hda)."""

import importlib.util
from pathlib import Path
import subprocess
import sys

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _load_context_body(content: str | None, file_path: str | None) -> str:
    if bool(content) == bool(file_path):
        raise click.UsageError("Provide exactly one of --content or --file.")
    if file_path:
        return click.open_file(file_path, "r", encoding="utf-8").read()
    return content or ""


def _parse_metadata_items(items: tuple[str, ...]) -> dict:
    metadata = {}
    for item in items:
        if "=" not in item:
            raise click.UsageError(f"Metadata item '{item}' must use key=value format.")
        key, value = item.split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


@click.group()
def main():
    """Holistic DNA Analyzer — read your DNA, answer your questions."""
    pass


@main.command()
@click.argument("name")
def switch(name: str):
    """Switch the active subject."""
    from hda.config import switch_subject

    try:
        switch_subject(name)
        console.print(f"Active subject: [bold green]{name}[/]")
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)


@main.command("import")
@click.argument("name", required=False)
def import_cmd(name: str | None):
    """Import a subject's source file into SQLite. Defaults to active subject."""
    from hda.config import get_active_subject
    from hda.db.importer import SUPPORTED_FORMATS_LABEL, import_subject

    name = name or get_active_subject()
    console.print(f"Importing [bold]{name}[/]...")

    try:
        count = import_subject(name)
        console.print(f"[green]Done.[/] {count:,} SNPs imported into data/db/{name}.db")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        console.print("[yellow]Tip:[/] check `config.yaml`, `source_file`, and that the raw export is inside `data/sources/`.")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        console.print(f"[yellow]Tip:[/] supported import formats are: {SUPPORTED_FORMATS_LABEL}.")
        console.print("[yellow]Tip:[/] if needed, set `source_format` explicitly in `config.yaml`.")
        raise SystemExit(1)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)


@main.command()
def subjects():
    """List all subjects."""
    from hda.config import get_active_subject, list_subjects

    active = get_active_subject()
    subs = list_subjects()

    table = Table(title="Subjects")
    table.add_column("Key", style="bold")
    table.add_column("Name")
    table.add_column("Sex")
    table.add_column("DOB")
    table.add_column("Source")
    table.add_column("Imported")
    table.add_column("Active", justify="center")

    for key, info in subs.items():
        marker = "[green]*[/]" if key == active else ""
        table.add_row(
            key,
            info.get("name", ""),
            info.get("sex", ""),
            str(info.get("date_of_birth", "") or ""),
            info.get("source_file", ""),
            str(info.get("imported_at", "") or "—"),
            marker,
        )

    console.print(table)


@main.command()
def whoami():
    """Show the active subject profile."""
    from hda.config import get_active_subject, get_subject_profile

    subject = get_active_subject()
    profile = get_subject_profile(subject)

    table = Table(title="Active Subject")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Subject key", subject)
    for key, value in profile.items():
        table.add_row(key.replace("_", " ").title(), str(value or "—"))

    console.print(table)


@main.command()
@click.argument("streamlit_args", nargs=-1, type=click.UNPROCESSED)
def dashboard(streamlit_args: tuple[str, ...]):
    """Launch the Streamlit dashboard."""
    from hda.config import ROOT_DIR

    if importlib.util.find_spec("streamlit") is None:
        console.print("[red]Streamlit is not installed in this environment.[/]")
        console.print(
            'Tip: install the dashboard extra with `python -m pip install -e ".[dashboard,export]"`.',
            markup=False,
        )
        raise SystemExit(1)

    app_path = Path(ROOT_DIR) / "dashboard" / "app.py"
    command = [sys.executable, "-m", "streamlit", "run", str(app_path), *streamlit_args]
    console.print(f"Launching dashboard: [bold]{app_path}[/]")
    try:
        completed = subprocess.run(command, cwd=str(ROOT_DIR), check=False)
    except OSError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)
    raise SystemExit(completed.returncode)


@main.group()
def context():
    """Inspect the persistent context memory for a subject."""
    pass


@context.command("sections")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def context_sections(subject: str | None):
    """List the standard context sections and whether the files exist."""
    from hda.context_store import list_context_sections

    try:
        payload = list_context_sections(subject)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    table = Table(title=f"Context Sections — {payload['subject']}")
    table.add_column("Section", style="bold")
    table.add_column("File")
    table.add_column("Exists", justify="center")
    table.add_column("Updated")
    table.add_column("Description")

    for section in payload["sections"]:
        table.add_row(
            section["id"],
            section["filename"],
            "yes" if section["exists"] else "no",
            str(section["metadata"].get("last_updated") or "—"),
            section["description"],
        )

    console.print(table)


@context.command("show")
@click.argument("section", required=False)
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def context_show(section: str | None, subject: str | None):
    """Show one context section or all context files for a subject."""
    from hda.context_store import read_context

    try:
        payload = read_context(subject, section)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    if section is not None:
        console.print(f"[bold]{payload['id']}[/] ({payload['filename']})")
        if not payload["exists"]:
            console.print("[yellow]Context file does not exist yet.[/]")
            return
        if payload["metadata"]:
            console.print(f"[dim]{payload['metadata']}[/]")
        console.print(payload["content"] or "", markup=False)
        return

    for index, item in enumerate(payload["sections"]):
        if index:
            console.print()
        console.print(f"[bold]{item['id']}[/] ({item['filename']})")
        if not item["exists"]:
            console.print("[yellow]Context file does not exist yet.[/]")
            continue
        if item["metadata"]:
            console.print(f"[dim]{item['metadata']}[/]")
        console.print(item["content"] or "", markup=False)


@context.command("audit")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--limit", type=int, default=20, show_default=True, help="Maximum number of recent audit entries")
def context_audit(subject: str | None, limit: int):
    """Show recent context audit events for a subject."""
    from hda.context_audit import read_context_audit

    try:
        payload = read_context_audit(subject, limit)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)
    console.print(f"Context audit for [bold]{payload['subject']}[/]")
    if not payload["entries"]:
        console.print("[yellow]No audit entries found.[/]")
        return

    table = Table(title="Context Audit Trail")
    table.add_column("Timestamp", style="dim")
    table.add_column("Event", style="bold")
    table.add_column("Section")
    table.add_column("Details")
    for entry in payload["entries"]:
        detail_text = ", ".join(f"{key}={value}" for key, value in entry.get("details", {}).items()) or "—"
        table.add_row(
            entry.get("timestamp", "—"),
            entry.get("event_type", "—"),
            str(entry.get("section") or "—"),
            detail_text,
        )
    console.print(table)


@context.command("validate")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--apply", "apply_fixes", is_flag=True, help="Apply safe automatic fixes where supported")
def context_validate(subject: str | None, apply_fixes: bool):
    """Validate context coherence against verified vs non-verified evidence."""
    from hda.context_validator import validate_context

    try:
        payload = validate_context(subject, apply_fixes)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"Validated context for [bold]{payload['subject']}[/]")
    console.print(f"Verified panels: {', '.join(payload['verified_panels'])}")

    if not payload["issues"]:
        console.print("[green]No context issues found.[/]")
    else:
        table = Table(title=f"Context Validation Issues ({payload['issue_count']})")
        table.add_column("Severity", style="bold")
        table.add_column("Section")
        table.add_column("Block")
        table.add_column("Fixable", justify="center")
        table.add_column("Message")
        for issue in payload["issues"]:
            table.add_row(
                issue["severity"],
                issue["section"],
                str(issue.get("block_id") or "—"),
                "yes" if issue.get("fixable") else "no",
                issue["message"],
            )
        console.print(table)

    if payload["applied_fixes"]:
        console.print("[green]Applied fixes:[/]")
        for fix in payload["applied_fixes"]:
            console.print(f"- {fix['section']}: {fix['message']}")


@context.command("migrate")
@click.argument("section", required=False)
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--apply", is_flag=True, help="Write migrated files to disk")
@click.option("--no-backup", is_flag=True, help="Skip backup creation before applying changes")
@click.option("--backup-dir", default=None, help="Override backup root directory")
def context_migrate(
    section: str | None,
    subject: str | None,
    apply: bool,
    no_backup: bool,
    backup_dir: str | None,
):
    """Plan or apply deterministic context-schema migrations."""
    from hda.context_migrator import migrate_context

    try:
        payload = migrate_context(subject=subject, section=section, apply=apply, backup=not no_backup, backup_root=backup_dir)
    except (KeyError, ValueError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(
        f"Context migration plan for [bold]{payload['subject']}[/] -> schema v{payload['target_schema_version']}"
    )
    table = Table(title="Context Migration")
    table.add_column("Section", style="bold")
    table.add_column("Status")
    table.add_column("Current")
    table.add_column("Target")
    table.add_column("Changes", justify="right")
    for item in payload["sections"]:
        current = "—" if item["current_schema_version"] is None else str(item["current_schema_version"])
        table.add_row(
            item["id"],
            item["status"],
            current,
            str(item["target_schema_version"]),
            str(item["change_count"]),
        )
    console.print(table)

    for item in payload["sections"]:
        if item["changes"]:
            console.print(f"[bold]{item['id']}[/] changes:")
            for change in item["changes"]:
                console.print(f"- {change}")
        for warning in item.get("warnings", []):
            console.print(f"[yellow]Warning ({item['id']}):[/] {warning}")

    if payload["backup_path"]:
        console.print(f"[green]Backup created:[/] {payload['backup_path']}")

    if apply:
        if payload["migrated_count"]:
            console.print(f"[green]Migrated sections:[/] {payload['migrated_count']}")
        else:
            console.print("[green]No migration changes were needed.[/]")
    elif payload["needs_migration"]:
        console.print("[yellow]Dry run only.[/] Re-run with [bold]--apply[/] to write changes.")
    else:
        console.print("[green]All inspected sections are already up to date.[/]")


@context.command("write")
@click.argument("section")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--content", default=None, help="Inline markdown body")
@click.option("--file", "file_path", default=None, help="Path to a markdown body file")
def context_write(section: str, subject: str | None, content: str | None, file_path: str | None):
    """Replace an entire context document."""
    from hda.context_store import write_context_document

    try:
        body = _load_context_body(content, file_path)
        payload = write_context_document(section, body, subject)
    except (KeyError, ValueError, click.UsageError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"[green]Updated[/] {payload['id']} for subject [bold]{payload['subject']}[/]")


@context.command("replace-section")
@click.argument("section")
@click.argument("heading")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--content", default=None, help="Inline markdown body")
@click.option("--file", "file_path", default=None, help="Path to a markdown body file")
def context_replace_section(
    section: str,
    heading: str,
    subject: str | None,
    content: str | None,
    file_path: str | None,
):
    """Replace or append a `##` section inside a maintained document."""
    from hda.context_store import replace_context_section

    try:
        body = _load_context_body(content, file_path)
        payload = replace_context_section(section, heading, body, subject)
    except (KeyError, ValueError, click.UsageError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"[green]Updated section[/] {heading} in [bold]{payload['id']}[/]")


@context.command("upsert-block")
@click.argument("section")
@click.argument("block_id")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--title", default=None, help="Human title for the block/action")
@click.option("--destination", default=None, help="Target destination (required for health_actions)")
@click.option("--meta", "metadata_items", multiple=True, help="Metadata item in key=value format")
@click.option("--content", default=None, help="Inline markdown body")
@click.option("--file", "file_path", default=None, help="Path to a markdown body file")
def context_upsert_block(
    section: str,
    block_id: str,
    subject: str | None,
    title: str | None,
    destination: str | None,
    metadata_items: tuple[str, ...],
    content: str | None,
    file_path: str | None,
):
    """Upsert a structured block in findings or health_actions."""
    from hda.context_store import upsert_context_block

    try:
        body = _load_context_body(content, file_path)
        metadata = _parse_metadata_items(metadata_items)
        payload = upsert_context_block(section, block_id, body, subject, metadata, title, destination)
    except (KeyError, ValueError, click.UsageError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"[green]Upserted block[/] {block_id} in [bold]{payload['id']}[/]")


@context.command("move-block")
@click.argument("section")
@click.argument("block_id")
@click.argument("destination")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def context_move_block(section: str, block_id: str, destination: str, subject: str | None):
    """Move a structured block to another destination."""
    from hda.context_store import move_context_block

    try:
        payload = move_context_block(section, block_id, destination, subject)
    except (KeyError, ValueError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"[green]Moved block[/] {block_id} to [bold]{destination}[/]")


@context.command("archive-block")
@click.argument("section")
@click.argument("block_id")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def context_archive_block(section: str, block_id: str, subject: str | None):
    """Archive a structured block."""
    from hda.context_store import archive_context_block

    try:
        payload = archive_context_block(section, block_id, subject)
    except (KeyError, ValueError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"[green]Archived block[/] {block_id} in [bold]{payload['id']}[/]")


@context.command("append-entry")
@click.argument("section")
@click.option("--title", required=True, help="Entry title")
@click.option("--date", "entry_date", default=None, help="ISO date for the entry heading")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--content", default=None, help="Inline markdown body")
@click.option("--file", "file_path", default=None, help="Path to a markdown body file")
def context_append_entry(
    section: str,
    title: str,
    entry_date: str | None,
    subject: str | None,
    content: str | None,
    file_path: str | None,
):
    """Append a dated chronological entry."""
    from hda.context_store import append_context_entry

    try:
        body = _load_context_body(content, file_path)
        payload = append_context_entry(section, title, body, subject, entry_date)
    except (KeyError, ValueError, click.UsageError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"[green]Appended entry[/] to [bold]{payload['id']}[/]")


@context.command("replace-entry")
@click.argument("section")
@click.argument("heading")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--content", default=None, help="Inline markdown body")
@click.option("--file", "file_path", default=None, help="Path to a markdown body file")
def context_replace_entry(
    section: str,
    heading: str,
    subject: str | None,
    content: str | None,
    file_path: str | None,
):
    """Replace an existing dated chronological entry."""
    from hda.context_store import replace_context_entry

    try:
        body = _load_context_body(content, file_path)
        payload = replace_context_entry(section, heading, body, subject)
    except (KeyError, ValueError, click.UsageError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"[green]Replaced entry[/] {heading} in [bold]{payload['id']}[/]")


@context.group("docs")
def context_docs():
    """Manage dated clinical documents under a subject context folder."""
    pass


@context_docs.command("list")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def context_docs_list(subject: str | None):
    """List archived clinical documents for a subject."""
    from hda.context_documents import list_context_documents

    try:
        payload = list_context_documents(subject)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"Context documents for [bold]{payload['subject']}[/]")
    if not payload["documents"]:
        console.print("[yellow]No context documents found.[/]")
        return

    table = Table(title="Clinical Documents")
    table.add_column("Date", style="bold")
    table.add_column("Category")
    table.add_column("Title")
    table.add_column("File")
    table.add_column("Notes")
    for item in payload["documents"]:
        table.add_row(
            str(item.get("document_date") or "—"),
            str(item.get("category") or "general"),
            str(item.get("title") or "—"),
            str(item.get("filename") or "—"),
            str(item.get("notes") or "—"),
        )
    console.print(table)


@context_docs.command("inbox")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def context_docs_inbox(subject: str | None):
    """List files waiting in the subject document inbox."""
    from hda.context_documents import list_context_inbox

    try:
        payload = list_context_inbox(subject)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"Document inbox for [bold]{payload['subject']}[/]: {payload['inbox_path']}")
    if not payload["documents"]:
        console.print("[yellow]Inbox is empty.[/]")
        return

    table = Table(title="Pending Inbox Documents")
    table.add_column("Date", style="bold")
    table.add_column("Category")
    table.add_column("Title")
    table.add_column("File")
    table.add_column("Inbox Path")
    for item in payload["documents"]:
        table.add_row(
            str(item.get("document_date") or "—"),
            str(item.get("category") or "general"),
            str(item.get("title") or "—"),
            str(item.get("filename") or "—"),
            str(item.get("relative_path") or "—"),
        )
    console.print(table)


@context_docs.command("import")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--date", "document_date", default=None, help="Override document date for all imported files")
@click.option("--category", default=None, help="Override category for all imported files")
@click.option("--move/--copy", default=True, show_default=True, help="Move or copy files out of the inbox")
@click.option("--integrate/--archive-only", default=True, show_default=True, help="Update clinical_context and sidecar markdown")
def context_docs_import(
    subject: str | None,
    document_date: str | None,
    category: str | None,
    move: bool,
    integrate: bool,
):
    """Import every pending file from the subject document inbox."""
    from hda.context_documents import import_context_inbox

    try:
        payload = import_context_inbox(
            subject=subject,
            document_date=document_date,
            category=category,
            move=move,
            integrate=integrate,
        )
    except (FileNotFoundError, KeyError, ValueError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"Document inbox import for [bold]{payload['subject']}[/]")
    if not payload["imported"]:
        console.print("[yellow]No inbox documents to import.[/]")
        return

    table = Table(title="Imported Documents")
    table.add_column("Date", style="bold")
    table.add_column("Category")
    table.add_column("Title")
    table.add_column("File")
    table.add_column("Archive Path")
    for item in payload["imported"]:
        table.add_row(
            str(item.get("document_date") or "—"),
            str(item.get("category") or "general"),
            str(item.get("title") or "—"),
            str(item.get("filename") or "—"),
            str(item.get("relative_path") or "—"),
        )
    console.print(table)


@context_docs.command("add")
@click.argument("source_path")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--date", "document_date", default=None, help="Document date (ISO YYYY-MM-DD)")
@click.option("--category", default="general", show_default=True, help="Document category, e.g. labs, imaging, visit")
@click.option("--title", default=None, help="Display title")
@click.option("--notes", default=None, help="Short notes to persist in the manifest")
@click.option("--move", is_flag=True, help="Move instead of copying the source file")
@click.option("--integrate/--archive-only", default=True, show_default=True, help="Update clinical_context and sidecar markdown")
def context_docs_add(
    source_path: str,
    subject: str | None,
    document_date: str | None,
    category: str,
    title: str | None,
    notes: str | None,
    move: bool,
    integrate: bool,
):
    """Copy or move a clinical document into the subject context archive."""
    from hda.context_documents import import_context_document

    try:
        payload = import_context_document(
            source_path,
            subject=subject,
            document_date=document_date,
            category=category,
            title=title,
            notes=notes,
            move=move,
            integrate=integrate,
        )
    except (FileNotFoundError, KeyError, ValueError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    doc = payload["document"]
    console.print(
        f"[green]Stored document[/] {doc['filename']} for [bold]{payload['subject']}[/] "
        f"under {doc['relative_path']}"
    )


@main.group()
def export():
    """Export human-readable artifacts from HDA."""
    pass


@export.command("doctor-report")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--output", "output_path", default=None, help="Output PDF path")
@click.option(
    "--variant",
    type=click.Choice(["short", "long"], case_sensitive=False),
    default="short",
    show_default=True,
    help="Report variant",
)
def export_doctor_report_cmd(subject: str | None, output_path: str | None, variant: str):
    """Export a doctor-facing PDF report."""
    from hda.doctor_report import export_doctor_report

    try:
        path = export_doctor_report(subject, output_path, variant=variant)
    except Exception as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    console.print(f"[green]Doctor report exported:[/] {path}")


@main.command()
@click.argument("rsid")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def snp(rsid: str, subject: str | None):
    """Look up a single SNP by rsid."""
    from hda.db.query import get_snp

    try:
        result = get_snp(rsid, subject)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)
    if result is None:
        console.print(f"[yellow]SNP {rsid} not found.[/]")
        raise SystemExit(1)

    table = Table(title=f"SNP {rsid}")
    for key in result:
        table.add_column(key.capitalize())
    table.add_row(*[str(v) for v in result.values()])
    console.print(table)


@main.command()
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--chromosome", "-c", default=None, help="Chromosome filter (e.g. 1, X, MT)")
@click.option("--start", type=int, default=None, help="Minimum base-pair position")
@click.option("--end", type=int, default=None, help="Maximum base-pair position")
@click.option("--genotype", "-g", default=None, help="Exact genotype filter (e.g. AA, CT)")
@click.option("--rsid-pattern", default=None, help="SQL LIKE pattern for rsid (e.g. rs53%)")
@click.option("--limit", type=int, default=25, show_default=True, help="Maximum number of rows")
def search(
    subject: str | None,
    chromosome: str | None,
    start: int | None,
    end: int | None,
    genotype: str | None,
    rsid_pattern: str | None,
    limit: int,
):
    """Search SNPs with basic filters."""
    from hda.db.query import search_snps

    try:
        results = search_snps(
            chromosome=chromosome,
            position_start=start,
            position_end=end,
            genotype=genotype,
            rsid_pattern=rsid_pattern,
            subject=subject,
            limit=limit,
        )
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    title = f"SNP Search ({len(results)} result{'s' if len(results) != 1 else ''})"
    table = Table(title=title)
    table.add_column("rsid", style="bold")
    table.add_column("Chromosome", justify="right")
    table.add_column("Position", justify="right")
    table.add_column("Genotype", justify="center")

    for row in results:
        table.add_row(row["rsid"], row["chromosome"], str(row["position"]), row["genotype"])

    console.print(table)


@main.command()
@click.option("--subject", "-s", default=None)
def stats(subject: str | None):
    """Show chromosome summary for a subject."""
    from hda.db.query import chromosome_summary, count_snps

    try:
        total = count_snps(subject)
        summary = chromosome_summary(subject)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    table = Table(title=f"Chromosome Summary ({total:,} total SNPs)")
    table.add_column("Chromosome", justify="right")
    table.add_column("SNPs", justify="right")

    for row in summary:
        table.add_row(row["chromosome"], f"{row['count']:,}")

    console.print(table)


@main.command("compare-variant")
@click.argument("rsid")
@click.argument("subject_a")
@click.argument("subject_b")
def compare_variant_cmd(rsid: str, subject_a: str, subject_b: str):
    """Compare one SNP between two subjects."""
    from hda.db.query import compare_snp

    try:
        result = compare_snp(rsid, subject_a, subject_b)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    table = Table(title=f"Variant Comparison: {rsid}")
    table.add_column("rsid", style="bold")
    table.add_column(subject_a, justify="center")
    table.add_column(subject_b, justify="center")
    table.add_column("Match", justify="center")
    table.add_row(
        result["rsid"],
        str(result.get(subject_a) or "—"),
        str(result.get(subject_b) or "—"),
        "yes" if result.get("match") else "no",
    )
    console.print(table)


@main.command("compare")
@click.argument("subject_a")
@click.argument("subject_b")
@click.option("--all", "show_all", is_flag=True, help="Include matching SNPs too")
@click.option("--chromosome", "-c", default=None, help="Optional chromosome filter")
@click.option("--limit", type=int, default=25, show_default=True, help="Maximum number of rows")
def compare_cmd(subject_a: str, subject_b: str, show_all: bool, chromosome: str | None, limit: int):
    """Compare SNPs between two subjects."""
    from hda.db.query import compare_subjects

    try:
        results = compare_subjects(
            subject_a=subject_a,
            subject_b=subject_b,
            only_different=not show_all,
            chromosome=chromosome,
            limit=limit,
        )
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    title = f"Compare {subject_a} vs {subject_b} ({len(results)} result{'s' if len(results) != 1 else ''})"
    table = Table(title=title)
    table.add_column("rsid", style="bold")
    table.add_column("Chromosome", justify="right")
    table.add_column("Position", justify="right")
    table.add_column(subject_a, justify="center")
    table.add_column(subject_b, justify="center")

    for row in results:
        table.add_row(
            row["rsid"],
            row["chromosome"],
            str(row["position"]),
            row["genotype_a"],
            row["genotype_b"],
        )

    console.print(table)


@main.command("compare-panel")
@click.argument("panel_id")
@click.argument("subject_a")
@click.argument("subject_b")
def compare_panel_cmd(panel_id: str, subject_a: str, subject_b: str):
    """Compare one analysis panel between two subjects."""
    from hda.tools import compare_panel

    try:
        result = compare_panel(panel_id, subject_a, subject_b)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    if result.get("requires_disclaimer"):
        console.print(
            f"[yellow]Note:[/] panel review status is '{result['review_status']}'. "
            "Treat comparison output as exploratory unless independently reviewed."
        )

    summary = result["summary"]
    console.print(
        f"[bold]{result['panel_name']}[/] — {subject_a} vs {subject_b} "
        f"(same effect: {summary['same_effect_count']}, "
        f"different effect: {summary['different_effect_count']}, "
        f"missing: {summary['missing_count']})"
    )

    table = Table(title="Panel Comparison")
    table.add_column("Gene", style="bold")
    table.add_column("rsid")
    table.add_column("Trait")
    table.add_column(subject_a, justify="center")
    table.add_column(subject_b, justify="center")
    table.add_column("Comparison")

    for row in result["results"]:
        table.add_row(
            row["gene"],
            row["rsid"],
            row["trait"],
            f"{row.get('subject_a_genotype') or '—'} / {row.get('subject_a_effect') or '—'}",
            f"{row.get('subject_b_genotype') or '—'} / {row.get('subject_b_effect') or '—'}",
            row["comparison"],
        )

    console.print(table)

    if result.get("composite_results"):
        composite_table = Table(title="Composite Panel Comparison")
        composite_table.add_column("Gene", style="bold")
        composite_table.add_column("Components")
        composite_table.add_column("Trait")
        composite_table.add_column(subject_a, justify="center")
        composite_table.add_column(subject_b, justify="center")
        composite_table.add_column("Comparison")

        for row in result["composite_results"]:
            composite_table.add_row(
                row["gene"],
                ", ".join(row.get("components", [])),
                row["trait"],
                f"{row.get('subject_a_genotype') or '—'} / {row.get('subject_a_effect') or '—'}",
                f"{row.get('subject_b_genotype') or '—'} / {row.get('subject_b_effect') or '—'}",
                row["comparison"],
            )

        console.print(composite_table)


@main.command()
@click.argument("subject_a")
@click.argument("subject_b")
def relatedness(subject_a: str, subject_b: str):
    """Estimate rough genetic relatedness between two subjects."""
    from hda.tools import estimate_relatedness

    try:
        result = estimate_relatedness(subject_a, subject_b)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    table = Table(title=f"Relatedness: {subject_a} vs {subject_b}")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Shared SNPs", f"{result['shared_snps']:,}")
    table.add_row("Comparable SNPs", f"{result['comparable_snps']:,}")
    table.add_row("Exact match rate", f"{result['exact_match_rate']:.2%}")
    table.add_row("IBS0 rate", f"{result.get('ibs0_rate', 0.0):.2%}")
    table.add_row("IBS1 rate", f"{result.get('ibs1_rate', 0.0):.2%}")
    table.add_row("IBS2 rate", f"{result.get('ibs2_rate', 0.0):.2%}")
    table.add_row("Heuristic relationship", result["heuristic_relationship"])
    table.add_row("Warning", result["interpretation_warning"])
    console.print(table)


@main.command()
@click.argument("rsid")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--source", multiple=True, help="Sources to query (snpedia, clinvar, ensembl)")
@click.option("--refresh", is_flag=True, help="Bypass cache and re-fetch")
def annotate(rsid: str, subject: str | None, source: tuple, refresh: bool):
    """Annotate a SNP with info from online databases."""
    import asyncio
    from hda.api.annotator import annotate_snp

    sources = list(source) if source else None

    try:
        with console.status(f"Fetching annotations for [bold]{rsid}[/]..."):
            result = asyncio.run(annotate_snp(rsid, subject, sources, refresh))
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    if not result.get("sources"):
        console.print(f"[yellow]No annotations found for {rsid}.[/]")
        return

    table = Table(title=f"Annotations for {rsid}")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    for field in ("gene", "clinical_significance", "condition", "summary",
                  "risk_allele", "population_frequency"):
        value = result.get(field)
        if value:
            table.add_row(field.replace("_", " ").title(), str(value))

    table.add_row("Sources", ", ".join(result.get("sources", [])))
    console.print(table)


@main.command()
def panels():
    """List available analysis panels."""
    from hda.analysis.panels import list_panels

    all_panels = list_panels()
    table = Table(title="Available Panels")
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Review")
    table.add_column("Variants", justify="right")
    table.add_column("Description")

    for p in all_panels:
        table.add_row(
            p["id"],
            p["name"],
            p["category"],
            p.get("review_status", "unknown"),
            str(p["variant_count"]),
            p["description"],
        )

    console.print(table)


@main.command("panel-audit")
def panel_audit():
    """Audit panel review metadata and repository-readiness state."""
    from hda.analysis.panels import audit_panels

    audits = audit_panels()
    table = Table(title="Panel Review Audit")
    table.add_column("ID", style="bold")
    table.add_column("Status")
    table.add_column("Review")
    table.add_column("Outcome")
    table.add_column("Last Reviewed")
    table.add_column("Issues", justify="right")

    for item in audits:
        table.add_row(
            item["id"],
            item["status"],
            item["review_status"],
            str(item.get("review_outcome") or "—"),
            str(item.get("last_reviewed") or "—"),
            str(len(item.get("issues", []))),
        )

    console.print(table)

    problem_count = 0
    for item in audits:
        for issue in item.get("issues", []):
            problem_count += 1
            console.print(f"[red]{item['id']}:[/] {issue}")

    if problem_count:
        raise SystemExit(1)


@main.command()
@click.argument("panel_id")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def analyze(panel_id: str, subject: str | None):
    """Run a panel analysis against a subject's genome."""
    from hda.analysis.panels import analyze_panel

    try:
        result = analyze_panel(panel_id, subject)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    review_status = result.get("review_status", "unknown")
    title = (
        f"{result['panel_name']} [{review_status}] — "
        f"{result['subject']} ({result['found_in_genome']}/{result['total_variants']} found)"
    )
    table = Table(title=title)
    table.add_column("Gene", style="bold")
    table.add_column("rsid")
    table.add_column("Trait")
    table.add_column("Genotype", justify="center")
    table.add_column("Effect")
    table.add_column("Description")

    if review_status != "verified":
        console.print(
            f"[yellow]Note:[/] panel review status is '{review_status}'. "
            "Treat interpretations as exploratory unless independently reviewed."
        )

    for r in result["results"]:
        if not r["found"]:
            table.add_row(r["gene"], r["rsid"], r["trait"], "[dim]—[/]", "[dim]not in chip[/]", "")
        else:
            effect = r["effect"] or ""
            style = ""
            if effect in ("normal", "lower_risk", "no_e4", "no_e2", "typical", "protective"):
                style = "green"
            elif "reduced" in effect or "risk" in effect or "altered" in effect:
                style = "yellow"
            elif "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
                style = "red"

            table.add_row(
                r["gene"], r["rsid"], r["trait"],
                f"[bold]{r['genotype']}[/]",
                f"[{style}]{effect}[/]" if style else effect,
                r["description"] or "",
            )

    console.print(table)

    composite_results = result.get("composite_results", [])
    if composite_results:
        composite_table = Table(title=f"{result['panel_name']} — Composite Interpretations")
        composite_table.add_column("Gene", style="bold")
        composite_table.add_column("Components")
        composite_table.add_column("Trait")
        composite_table.add_column("Genotype", justify="center")
        composite_table.add_column("Effect")
        composite_table.add_column("Description")

        for r in composite_results:
            components = ", ".join(r.get("components", []))
            if not r["found"]:
                composite_table.add_row(r["gene"], components, r["trait"], "[dim]—[/]", "[dim]not available[/]", r["description"] or "")
            else:
                effect = r["effect"] or ""
                style = ""
                if effect in ("normal", "lower_risk", "no_e4", "no_e2", "typical", "protective"):
                    style = "green"
                elif "reduced" in effect or "risk" in effect or "altered" in effect:
                    style = "yellow"
                elif "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
                    style = "red"

                composite_table.add_row(
                    r["gene"],
                    components,
                    r["trait"],
                    f"[bold]{r.get('label') or r['genotype']}[/]",
                    f"[{style}]{effect}[/]" if style else effect,
                    r["description"] or "",
                )

        console.print(composite_table)


@main.command()
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def report(subject: str | None):
    """Show notable findings across all panels."""
    from hda.analysis.panels import get_risk_summary

    try:
        findings = get_risk_summary(subject)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    if not findings:
        console.print("[green]No notable findings across all panels.[/]")
        return

    table = Table(title=f"Notable Findings ({len(findings)} variants)")
    table.add_column("Panel")
    table.add_column("Gene", style="bold")
    table.add_column("Trait")
    table.add_column("Genotype", justify="center")
    table.add_column("Effect")
    table.add_column("Description")

    for f in findings:
        effect = f["effect"] or ""
        style = "yellow"
        if "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
            style = "red"

        table.add_row(
            f["panel"], f["gene"], f["trait"],
            f"[bold]{f['genotype']}[/]",
            f"[{style}]{effect}[/]",
            f["description"] or "",
        )

    console.print(table)


if __name__ == "__main__":
    main()
