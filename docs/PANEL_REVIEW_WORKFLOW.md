# Panel Review Workflow

This document defines the repository lifecycle for analysis panels.

The goal is to keep a clear separation between:
- panels that are safe enough for trusted default use
- panels that remain useful but exploratory
- panels that are still drafts and should not be treated as repository-ready

## Lifecycle States

The panel filename and metadata together define the current lifecycle state.

### Draft

Filename:
- `<panel>.draft.yaml`

Metadata:
- `review_status: draft`
- `status: draft`

Allowed review outcomes:
- `needs_sources`
- `needs_weaker_language`
- `reject`

Meaning:
- work in progress
- not safe for trusted default use
- should normally stay local until reviewed

### Exploratory

Filename:
- `<panel>.experimental.yaml`

Metadata:
- `review_status: exploratory`
- `status: experimental`
- `review_outcome: experimental_only`

Meaning:
- repository-kept panel with real user value
- not part of the trusted core set
- must always be interpreted with explicit caution

### Verified Core

Filename:
- `<panel>.yaml`

Metadata:
- `review_status: verified`
- `status: core`
- `review_outcome: approved_for_core`

Meaning:
- passed repository review for trusted default use
- still probabilistic and non-diagnostic
- should have tighter scope, stronger provenance, and more conservative language

## Required Review Metadata

Every versioned repository panel must include:

- `version`
- `last_reviewed`
- `review_outcome`
- `review_notes`

`review_notes` should briefly explain why the panel is in its current lifecycle
state.

## Promotion Rules

### Draft -> Exploratory

Allowed when:
- schema is complete
- provenance exists at panel level
- wording is conservative
- the panel is useful enough to keep in the repo
- evidence is still too mixed or context-heavy for trusted-core use

Required changes:
- rename to `.experimental.yaml`
- set `review_status: exploratory`
- set `status: experimental`
- set `review_outcome: experimental_only`
- update `review_notes`

### Exploratory -> Verified Core

Allowed when:
- scope has been pruned to stronger claims only
- panel-level provenance is present
- variant-level evidence metadata is present
- language is conservative and non-diagnostic
- behavioral / psychiatric overreach has been removed

Required changes:
- rename to plain `.yaml`
- set `review_status: verified`
- set `status: core`
- set `review_outcome: approved_for_core`
- update `last_reviewed`
- update `review_notes`

## De-scope / Demotion Rules

### Verified -> Exploratory

Use when:
- provenance becomes outdated or incomplete
- claims are broader than the evidence supports
- interpretation risk is discovered after review

Required changes:
- rename to `.experimental.yaml`
- set `review_status: exploratory`
- set `status: experimental`
- set `review_outcome: experimental_only`
- update `last_reviewed`
- update `review_notes`

### Exploratory -> Reject / Local Only

Use when:
- evidence is too weak
- language cannot be made safe without hollowing out the panel
- the panel is misleading even with caveats

Recommended action:
- remove it from the repository or keep it only as a local draft
- if retained temporarily as draft, use `review_outcome: reject`

## Repository Checks

Use:

```powershell
hda panel-audit
```

This audits all repository panels for:
- schema completeness
- review/status consistency
- presence of required review metadata
- valid review outcomes for the current lifecycle state

## Practical Rule

If there is doubt between two states:
- prefer `draft` over `exploratory`
- prefer `exploratory` over `verified`

The workflow should bias toward under-claiming, not over-promoting.
