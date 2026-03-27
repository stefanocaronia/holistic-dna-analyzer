# Context Schema

This document defines the data model for subject context under
`data/context/<subject>/`.

The goal is to keep context:
- human-readable
- agent-writable
- machine-parsable
- holistic across panels and domains

This is intentionally **database-like**, but the source of truth remains
Markdown files, not SQLite tables.

## Design Principles

- Context is **persistent memory**, not a chat transcript dump.
- Structure should be stable at the file and block level.
- Prose inside blocks should remain natural and discursive.
- The schema must support cross-panel synthesis rather than one-note-per-SNP.
- The user should be able to open any context file and understand it directly.

## Storage Model

Each subject has exactly four canonical files:

- `profile_summary.md`
- `findings.md`
- `health_actions.md`
- `session_notes.md`

These files are the canonical storage layer.

`hda context ...` and `hda.tools` context helpers are the official access
layer. Write operations should use these APIs rather than inventing ad hoc file
edits.

## File-Level Contract

Every context file starts with YAML frontmatter:

```yaml
---
subject: stefano
doc_type: findings
title: Stefano — Findings
last_updated: 2026-03-27
schema_version: 1
---
```

Required frontmatter fields:

- `subject`: configured subject key
- `doc_type`: one of `profile_summary`, `findings`, `health_actions`, `session_notes`
- `title`: human-readable title
- `last_updated`: ISO date of latest meaningful edit
- `schema_version`: current schema version, starting at `1`

Optional frontmatter fields:

- `status`: optional document-wide status such as `active` or `archived`
- `tags`: optional coarse labels if the project later needs them

## Document Types

### `profile_summary.md`

Purpose:
- quick-load genetic portrait
- current integrated snapshot
- fast orientation at session start

Behavior:
- single maintained document
- updated in place
- not chronological

Recommended top-level headings:

- `## Overview`
- `## Key Strengths`
- `## Key Vulnerabilities`
- integrated system headings as needed, for example:
  - `## Cardiovascular`
  - `## Neurocognitive`
  - `## Sleep & Recovery`
  - `## Nutrition`
  - `## Lifestyle Interactions`

Write policy:
- `replace` entire document
- `replace_section`
- no append-only diary behavior

### `findings.md`

Purpose:
- stable findings registry
- canonical knowledge blocks worth reusing
- durable integrated conclusions

Behavior:
- **not a diary**
- **not one file per finding**
- each finding should have a stable block id
- existing findings should be updated when refined, not duplicated by date

Why this stays a single registry document:

- the user can read the whole longitudinal picture in one place
- cross-finding synthesis stays visible instead of being fragmented across files
- future tooling can still address single findings through `finding_id`
- updates remain structured without turning the context folder into a mini filesystem database

Canonical block shape:

```md
## Profilo dopaminergico di reward deficiency

finding_id: dopamine_reward_deficiency
created: 2026-03-24
updated: 2026-03-27
status: active
domains: adhd, addiction, pharmacogenomics

### Summary
Free prose.

### Integrated Interpretation
Free prose.

### Evidence Threads
Free prose. The model may add its own subheadings here.

### Implications
Free prose.

### Follow-up
Optional prose or bullets.
```

Block rules:

- `## <Human-readable title>` is required
- `finding_id` is required and should be stable across updates
- metadata lines directly under the heading are preferred
- `Summary` and `Integrated Interpretation` should exist
- extra subsections are allowed

Write policy:
- `upsert_context_block`
- `archive_context_block`
- avoid blind append of dated notes

### `health_actions.md`

Purpose:
- current action plan
- prioritized recommendations
- integrated interventions rather than panel-specific tips

Behavior:
- maintained document
- organized by priority
- actions may be revised, promoted, demoted, or retired

Recommended top-level headings:

- `## Alta Priorità`
- `## Media Priorità`
- `## Bassa Priorità`

Canonical action block shape:

```md
### Valutazione apnea del sonno

action_id: sleep_apnea_evaluation
status: active

Free prose explaining rationale, mechanism, and practical next step.
Optional subheadings are allowed.
```

Block rules:

- `### <Action title>` is required
- `action_id` is recommended and should be stable
- `status` is recommended, for example `active`, `monitoring`, `paused`, `done`
- actions must live under exactly one priority section at a time

Write policy:
- `upsert_context_block(..., destination=...)`
- `move_context_block`
- `archive_context_block`
- avoid adding the same action under multiple priorities

### `session_notes.md`

Purpose:
- conversation memory
- user preferences
- subjective reports
- follow-up promises
- corrections to previous interpretations

Behavior:
- chronological
- this is the only file that intentionally behaves like a diary

Canonical block shape:

```md
## 2026-03-27: Sonno in ritardo, debito di sonno ed extrasistoli

- Bullet or short paragraph notes
- Follow-ups
- User-reported symptoms or context
```

Block rules:

- date in the heading is required
- chronological append is normal
- compact prose or bullets are both acceptable

Write policy:
- `append_entry`
- `replace_entry` only when correcting the same dated block

## Allowed Narrative Freedom

The model is free to:
- write discursive prose inside sections
- add helpful subheadings inside a finding or action block
- connect multiple panels, systems, and life-context factors in one block

The model is not free to:
- invent new canonical files
- turn every panel into a separate silo by default
- treat `findings.md` like a raw session log
- duplicate the same action in multiple priority sections

## API Model

The schema is implemented through constrained read/write APIs.

Available read operations:

- `list_context_sections(subject=None)`
- `read_context(subject=None, section=None)`
- `read_context_block(section, block_id, subject=None)`
- `validate_context(subject=None, apply=False)`

Available write operations:

- `write_context_document(section, content)`
- `replace_context_section(section, heading, content)`
- `upsert_context_block(section, block_id, content, subject=None, metadata=None, title=None, destination=None)`
- `move_context_block(section, block_id, destination)`
- `archive_context_block(section, block_id)`
- `append_context_entry(section, title, content, subject=None, entry_date=None)`
- `replace_context_entry(section, heading, content, subject=None)`

Operation limits by document type:

- `profile_summary`: `write_context_document`, `replace_context_section`
- `findings`: `upsert_context_block`, `archive_context_block`
- `health_actions`: `upsert_context_block`, `move_context_block`, `archive_context_block`
- `session_notes`: `append_context_entry`, `replace_context_entry`

## Migration Guidance

Existing context files may still contain older formats.

Migration direction:

- `profile_summary`: normalize headings and frontmatter
- `findings`: convert dated diary entries into stable finding ids where possible
- `health_actions`: ensure one action belongs to one priority section
- `session_notes`: keep chronological

### Migration Contract

- `hda context migrate` and `migrate_context()` are **dry-run by default**
- `--apply` writes migrated files
- apply mode creates a backup by default under `output/context-backups/`
- `--no-backup` disables backup creation explicitly
- `--backup-dir` overrides the backup root

### Version Strategy

- the current supported context schema version is `1`
- migrations are defined **version-to-version**, even if today only `0 -> 1` exists
- the migrator is intended for **deterministic** changes: metadata normalization,
  stable ids, readable headings, and priority-shape cleanup
- semantically ambiguous rewrites remain out of scope for automatic migration

### Supported Scope

- only documents that already have YAML frontmatter plus `schema_version` are in
  the supported migration contract
- unversioned legacy files from the pre-frontmatter era are treated as manual
  intervention cases, not auto-converted inputs

During migration, preserving meaning is more important than preserving exact
wording.
