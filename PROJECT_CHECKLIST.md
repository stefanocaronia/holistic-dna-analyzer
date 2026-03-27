# Project Checklist

This is a maturity checklist for the project. It is intentionally not tied to a release number.

## Core Stability

- [x] Package and CLI naming are aligned on `hda`
- [x] Basic CLI workflow is documented from the project folder
- [x] Public Python API is documented as a stable surface
- [x] CLI commands have automated coverage for success and failure paths
- [x] CI runs smoke checks automatically on every change
- [x] Persistent context has a documented schema, stable API surface, and automated tests
- [x] Context validation exists for verified vs exploratory evidence boundaries
- [x] Versioned context migration exists for supported schema changes
- [x] Doctor-facing PDF export exists

## Import Pipeline

- [x] MyHeritage import works
- [x] 23andMe import support exists
- [x] AncestryDNA import support exists
- [x] `.zip` raw data imports are supported where applicable
- [x] Import errors explain what to fix in `config.yaml` or `data/sources/`
- [x] Synthetic automated tests cover format detection and parser behavior
- [ ] 23andMe import validated on a real export file
- [ ] AncestryDNA import validated on a real export file
- [x] Unsupported or malformed raw files have dedicated regression tests

## Analysis Engine

- [x] Panel-driven analysis exists and is usable through CLI and agent tools
- [x] Core panel schema and provenance requirements are enforced consistently
- [x] Panel filename conventions (`.yaml`, `.experimental.yaml`, `.draft.yaml`) are enforced consistently
- [x] Panel review lifecycle is documented and audited (`draft` -> `experimental` -> `verified`)
- [x] Core panels include panel-level provenance metadata
- [x] Core panels include variant-level evidence metadata
- [x] Panel engine supports validated multi-SNP / haplotype interpretations where single SNPs are insufficient (for example APOE)
- [x] Every panel kept in the core set is reviewed, improved, and promoted to `verified`
- [x] Panels have automated regression tests against fixture data
- [x] Annotation fetch/caching paths have automated tests
- [x] Risk summary behavior is covered by tests

## Product Readiness

- [x] Multi-subject workflow exists
- [x] Low-level subject comparison is available through CLI and API (`compare`, `compare-variant`, `search`)
- [x] Panel-level subject comparison exists through CLI and API (`compare-panel`, `compare_panel`)
- [x] Heuristic relatedness summaries exist with explicit exploratory warnings
- [x] Persistent subject context exists
- [x] Dashboard exists for manual exploration
- [x] README includes troubleshooting for common import failures
- [x] README explains clearly that HDA provides DNA navigation/analysis tools, while LLM-generated interpretations remain exploratory and should be validated with a qualified professional
- [ ] Changelog or release notes process exists
- [x] Backup / migration guidance exists for `config.yaml`, `data/db/`, and `data/context/`

## Subject Isolation & Data Safety

- [x] Database access only accepts configured subject keys
- [x] Context folder paths are derived from configured subject keys
- [x] Automated tests cover subject isolation across CLI, API tools, and dashboard flows
- [x] Session context loading/writing is routed through validated helper functions instead of ad hoc paths
- [ ] Optional per-subject export / backup commands exist
- [x] Sensitive-data handling and local family-use assumptions are documented explicitly
- [x] Repository ignores raw sources, subject context, generated reports, and temp artifacts by default
- [x] CI checks that sensitive user data paths are not accidentally tracked
- [ ] Relatedness heuristics are validated against known family relationships or pruned marker sets

## Current Focus

- [x] Improve import diagnostics in CLI
- [x] Add synthetic tests for supported provider formats
- [ ] Validate the new provider imports on real 23andMe and AncestryDNA exports
- [x] Decide and document a stable testing command for contributors
- [x] Improve each core panel and move it to verified status with provenance and safer wording
- [x] Introduce structured context memory with schema, validation, migration, and doctor-report export

## Next Priorities

- [x] Add semantic guardrails that detect duplicated findings or contradictions across `profile_summary`, `findings`, and `health_actions`
- [x] Add audit trail metadata for context writes and migrations
- [x] Improve doctor export into short/long report variants and clearer verified vs exploratory separation
- [ ] Add optional backup/export CLI commands per subject
- [x] Clarify dependency tiers (`core` vs export/dashboard extras) in packaging and docs

## Exploratory Panel Triage

- [x] Keep `sleep.experimental` as high-value exploratory: several chronotype/circadian ideas are useful, but the panel needs pruning before any promotion
- [x] Keep `health_over50.experimental` as high-value exploratory: contains useful age-related screening themes, but mixes solid loci with weak or over-assertive claims
- [x] Keep `wellness.experimental` as medium-value exploratory: some fitness traits are plausible, but overlap and behavioral interpretation are still too noisy
- [x] Keep `mental_health.experimental` as medium/high-value exploratory: high user value, but too much risk of over-interpretation for core inclusion right now
- [x] Treat `adhd_neurodivergence.experimental` and `autism_spectrum.experimental` with the most conservative standards because both are high-risk for over-interpretation
- [x] Treat `addiction.experimental` and `cognitive.experimental` as exploratory-only until a stricter evidence pass is done
- [x] Prune `sleep.experimental` to a smaller evidence-led exploratory panel with provenance metadata
- [x] Prune `health_over50.experimental` and split out anything that belongs in core cardiovascular or APOE handling
- [x] Prune `mental_health.experimental` to a smaller exploratory panel centered on stress response, neuroplasticity, and cautious serotonin signaling
- [x] Prune `wellness.experimental` to a smaller exercise-focused exploratory panel
- [x] Prune `addiction.experimental` to a smaller nicotine/alcohol exploratory panel
- [x] Prune `cognitive.experimental` to a smaller memory/plasticity/aging exploratory panel
- [x] Prune `adhd_neurodivergence.experimental` to a minimal exploratory panel centered on attention-regulation and medication-response signals
- [x] Prune `autism_spectrum.experimental` to a minimal exploratory common-variant panel with explicit non-diagnostic limitations
- [x] Add minimum panel-level metadata (`summary`, `sources`, `limitations`) to all exploratory panels kept in the repository
