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

## Command-Line Parity

The Python API mirrors the CLI:

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
