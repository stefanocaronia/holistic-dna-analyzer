# Panel Schema

This document defines the minimum structure for panels that are safe to version in the repository.

The runtime validates this schema when loading panels, so versioned panels
should follow it exactly.

## Repository Policy

- The repository should version only **core** panels.
- Core panels should use the plain filename, for example `nutrition_metabolism.yaml`.
- Exploratory panels should use the suffix `.experimental.yaml`.
- Draft panels should use the suffix `.draft.yaml`.
- Exploratory panels may stay in the repository if they are clearly marked and documented as non-core.
- Draft or user-customized panels should stay local unless they are promoted after review.
- A panel is not considered core just because an LLM drafted it.

## Panel File Naming

Examples:

- `nutrition_micronutrients.yaml`
- `cardiovascular.yaml`
- `pharmacogenomics.yaml`
- `mental_health.experimental.yaml`
- `custom_focus_panel.draft.yaml`

## Minimum Panel-Level Metadata

Every versioned panel should include at least:

```yaml
name: Advanced Nutrition & Vitamins
description: Detailed nutrient metabolism panel
category: nutrition
status: core
review_status: verified
version: 1
last_reviewed: 2026-03-26
summary: >
  Curated panel for relatively stable nutrient-metabolism associations.
sources:
  - type: review
    citation: "Short citation here"
limitations:
  - Associations are probabilistic, not diagnostic
  - Replication strength differs across variants and populations
```

## Minimum Variant Structure

```yaml
variants:
  - rsid: rs1801394
    gene: MTRR
    trait: Methionine synthase reductase — B12 recycling
    evidence_level: medium
    sources:
      - type: snpedia
        id: rs1801394
      - type: review
        citation: "Short citation here"
    genotypes:
      AA:
        effect: normal
        description: Normal B12 recycling and methionine metabolism.
      AG:
        effect: reduced
        description: Reduced enzyme efficiency. Adequate B12 and folate intake important.
      GG:
        effect: significantly_reduced
        description: Significantly reduced B12 recycling. Higher homocysteine risk.
    aliases:
      GA: AG
```

## Required Rules

- Plain `.yaml` files are treated as `review_status=verified` unless explicitly overridden.
- `.experimental.yaml` files are treated as `review_status=exploratory`.
- `.draft.yaml` files are treated as `review_status=draft`.
- Plain `.yaml` files default to `status=core`.
- `.experimental.yaml` files default to `status=experimental`.
- `.draft.yaml` files default to `status=draft`.
- `sources` must exist at panel level.
- `evidence_level` should exist for each variant.
- Descriptions must avoid diagnostic claims.
- If evidence is mixed or weak, the panel should not be promoted to core.

## Recommended Evidence Levels

- `high`: replicated and commonly accepted association with relatively stable interpretation
- `medium`: useful and plausible, but context-dependent or not uniformly replicated
- `low`: exploratory, conflicting, or easily over-interpreted

Panels dominated by `low` evidence variants should remain local or experimental, not core.

## Review Status Meanings

- `verified`: reviewed for repository inclusion; safest default status
- `exploratory`: usable, but not part of the trusted default set
- `draft`: LLM-authored or user-authored draft with no verification yet

## Status Meanings

- `core`: verified default panel shipped as part of the trusted set
- `experimental`: shipped with the repository, but intentionally outside the trusted default set
- `draft`: unverified work in progress; normally local only
- `custom`: reserved for explicitly user-defined statuses when needed
