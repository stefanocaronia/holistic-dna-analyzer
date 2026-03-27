# Python API

This document defines the stable Python surface for building agents and local
automation on top of HDA.

## Stable Surface

Use either of these imports:

```python
from hda.tools import run_panel, available_panels, who_am_i
```

or:

```python
from hda.tools.agent_tools import run_panel, available_panels, who_am_i
```

`hda.tools` is the preferred public import path. It re-exports the stable
agent-facing functions from `hda.tools.agent_tools`.

For the structure of the underlying context documents, see
[docs/CONTEXT_SCHEMA.md](docs/CONTEXT_SCHEMA.md).

## Stability Contract

The functions in `hda.tools` are intended to remain stable across normal
project evolution:

- arguments are simple Python types
- return values are plain `dict` / `list` structures
- they default to the active subject when `subject` is omitted
- they expose panel review metadata so agents can distinguish verified results
  from exploratory ones

The following internal modules are not part of the stable public API:

- `hda.analysis.*`
- `hda.db.*`
- `hda.api.*`
- `hda.config`

They may change more freely as the project evolves.

## Available Functions

### Subject and profile

- `who_am_i()`
- `list_all_subjects()`
- `list_context_sections(subject=None)`
- `read_context(subject=None, section=None)`
- `read_context_block(section, block_id, subject=None)`
- `read_context_audit(subject=None, limit=50)`
- `list_context_inbox(subject=None)`
- `list_context_documents(subject=None)`
- `import_context_inbox(subject=None, document_date=None, category=None, move=True, integrate=True)`
- `import_context_document(source_path, subject=None, document_date=None, category=None, title=None, notes=None, move=False, integrate=True)`
- `write_context_document(section, content, subject=None)`
- `replace_context_section(section, heading, content, subject=None)`
- `upsert_context_block(section, block_id, content, subject=None, metadata=None, title=None, destination=None)`
- `move_context_block(section, block_id, destination, subject=None)`
- `migrate_context(subject=None, section=None, apply=False, backup=True, backup_root=None)`
- `archive_context_block(section, block_id, subject=None)`
- `append_context_entry(section, title, content, subject=None, entry_date=None)`
- `replace_context_entry(section, heading, content, subject=None)`
- `validate_context(subject=None, apply=False)`
- `export_doctor_report(subject=None, output_path=None, variant="short")`

`read_context()` returns parsed frontmatter in `metadata` plus the Markdown body in `content`.
For findings, `read_context_block()` returns both a human-readable `heading` and a stable
`metadata["finding_id"]` so the display title can stay readable while updates remain deterministic.
`read_context_audit()` returns the recent append-only operational history for
context writes and migrations. This is for traceability, not user-facing memory.
`list_context_inbox()` and `import_context_inbox()` manage the preferred
drop-folder flow under `data/context/<subject>/documents_inbox/`.
`list_context_documents()` and `import_context_document()` manage the final
dated archive under `data/context/<subject>/documents/`.
When integration is enabled (the default), each imported document also gets an
extracted Markdown sidecar in the archive and a compact index entry in
`clinical_context.md`.

### SNP lookup and search

- `lookup_snp(rsid, subject=None)`
- `search(chromosome=None, position_start=None, position_end=None, genotype=None, rsid_pattern=None, subject=None, limit=100)`
- `get_stats(subject=None)`

### Comparisons

- `compare_variant(rsid, subject_a, subject_b)`
- `compare(subject_a, subject_b, only_different=True, chromosome=None, limit=100)`
- `compare_panel(panel_id, subject_a, subject_b)`
- `estimate_relatedness(subject_a, subject_b)`

### Annotation

- `annotate(rsid, subject=None, sources=None, force_refresh=False)`
- `annotate_my_snp(rsid, sources=None)`

### Panels

- `available_panels()`
- `run_panel(panel_id, subject=None)`
- `run_all_panels(subject=None)`
- `notable_findings(subject=None)`

## Panel Metadata Contract

Panel-related functions expose these fields so agents can behave safely:

- `status`
- `review_status`
- `summary`
- `sources`
- `limitations`
- `requires_disclaimer`
- `interpretation_warning`

Agents should treat these fields as part of the public contract.

## Minimal Example

```python
from hda.tools import available_panels, run_panel, who_am_i

profile = who_am_i()
panels = available_panels()
cardio = run_panel("cardiovascular")

print(profile["name"])
print([(panel["id"], panel["review_status"]) for panel in panels])
print(cardio["panel_name"], cardio["review_status"], cardio["requires_disclaimer"])
```

## Context Memory Example

```python
from hda.tools import append_context_entry, export_doctor_report, import_context_document, import_context_inbox, list_context_documents, list_context_inbox, list_context_sections, read_context, upsert_context_block, validate_context

sections = list_context_sections()
summary = read_context(section="profile_summary")
upsert_context_block(
    "findings",
    "dopamine_reward_deficiency",
    "### Summary\nShort integrated conclusion.",
    metadata={"domains": "adhd, addiction"},
    title="Profilo dopaminergico di reward deficiency",
)
append_context_entry("session_notes", "Follow-up", "- User reported improvement")
validation = validate_context(apply=False)
inbox = list_context_inbox()
import_context_inbox()
import_context_document("C:/reports/cbc.pdf", document_date="2026-03-27", category="labs", title="CBC")
docs = list_context_documents()
pdf_path = export_doctor_report(variant="short")
full_pdf_path = export_doctor_report(variant="long")

print([section["id"] for section in sections["sections"]])
print(summary["metadata"])
print(summary["content"])
print(validation["issue_count"])
print(inbox["count"])
print(docs["count"])
print(pdf_path)
print(full_pdf_path)
```

By default, `export_doctor_report()` writes the short report to
`output/pdf/doctor-report-<subject>.pdf`. The long variant writes by default to
`output/pdf/doctor-report-<subject>-long.pdf`. PDF export depends on the
optional `export` extra.
`migrate_context()` is dry-run by default and only supports versioned context
documents that already carry YAML frontmatter plus `schema_version`.

## Command-Line Parity

The Python API mirrors the CLI:

- `list_context_sections()` <-> `hda context sections`
- `read_context()` <-> `hda context show`
- `read_context(section="findings")` <-> `hda context show findings`
- `read_context_audit()` <-> `hda context audit`
- `list_context_inbox()` <-> `hda context docs inbox`
- `import_context_inbox()` <-> `hda context docs import`
- `import_context_inbox(integrate=False)` <-> `hda context docs import --archive-only`
- `list_context_documents()` <-> `hda context docs list`
- `import_context_document(...)` <-> `hda context docs add ...`
- `write_context_document("profile_summary", "...")` <-> `hda context write profile_summary --content "..."`
- `replace_context_section("profile_summary", "Overview", "...")` <-> `hda context replace-section profile_summary "Overview" --content "..."`
- `upsert_context_block("findings", "dopamine_reward_deficiency", "...")` <-> `hda context upsert-block findings dopamine_reward_deficiency --content "..."`
- `move_context_block("health_actions", "sleep_apnea_evaluation", "Alta Priorità")` <-> `hda context move-block health_actions sleep_apnea_evaluation "Alta Priorità"`
- `migrate_context()` <-> `hda context migrate`
- `migrate_context(apply=True)` <-> `hda context migrate --apply`
- `archive_context_block("findings", "dopamine_reward_deficiency")` <-> `hda context archive-block findings dopamine_reward_deficiency`
- `append_context_entry("session_notes", "Follow-up", "...")` <-> `hda context append-entry session_notes --title "Follow-up" --content "..."`
- `replace_context_entry("session_notes", "2026-03-27: Follow-up", "...")` <-> `hda context replace-entry session_notes "2026-03-27: Follow-up" --content "..."`
- `validate_context(apply=False)` <-> `hda context validate`
- `validate_context(apply=True)` <-> `hda context validate --apply`
- `export_doctor_report(variant="short")` <-> `hda export doctor-report`
- `export_doctor_report(variant="long")` <-> `hda export doctor-report --variant long`
- `available_panels()` <-> `hda panels`
- `run_panel("cardiovascular")` <-> `hda analyze cardiovascular`
- `lookup_snp("rs53576")` <-> `hda snp rs53576`
- `search(...)` <-> `hda search ...`
- `compare("alice", "bob")` <-> `hda compare alice bob`
- `compare_variant("rs429358", "alice", "bob")` <-> `hda compare-variant rs429358 alice bob`
- `compare_panel("cardiovascular", "alice", "bob")` <-> `hda compare-panel cardiovascular alice bob`
- `estimate_relatedness("alice", "bob")` <-> `hda relatedness alice bob`
- `notable_findings()` <-> `hda report`

If you are building an agent, prefer the Python API. If you are scripting from
the shell, prefer `hda`.
