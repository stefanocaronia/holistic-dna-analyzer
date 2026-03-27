# Panel LLM Workflows

This guide defines how an LLM should help with panel authoring and review.

## Two Separate Jobs

There are two different workflows:

1. **Draft a panel**
2. **Verify a panel for core inclusion**

An LLM can assist with both, but the rules are different.
The repository lifecycle and required metadata are defined in [docs/PANEL_REVIEW_WORKFLOW.md](docs/PANEL_REVIEW_WORKFLOW.md).

## Workflow A: Draft a Panel

Use this when exploring a new topic or building a personal/custom panel.

### Allowed

- Propose candidate variants
- Suggest a panel structure
- Write cautious descriptions
- Mark uncertainty clearly
- Recommend follow-up review steps

### Not Allowed

- Label the panel as `verified`
- Present weak associations as settled
- Use diagnostic language
- Invent provenance or citations

### Output Requirements

- Mark the panel as draft or keep it local until reviewed
- Prefer neutral effects like `altered`, `reduced`, `variant`, `unclear`
- Include explicit limitations when evidence is mixed
- If the file is versioned, use a draft-appropriate `review_outcome` such as `needs_sources` or `needs_weaker_language`

### LLM Instruction Template

```text
Create a draft DNA panel in YAML.
Do not mark it as verified or core.
Do not invent citations.
Prefer conservative wording.
If evidence is mixed or weak, say so explicitly.
```

## Workflow B: Verify a Panel for Core Inclusion

Use this only for panels intended to be versioned in the repository.

### Allowed

- Check schema completeness
- Check internal consistency
- Check whether claims are too strong
- Gather and attach provenance
- Recommend de-scoping or rejection

### Not Allowed

- Promote a panel to core when provenance is missing
- Keep highly speculative neuro/behavioral claims as if they were stable
- Fill missing sources from memory without confidence
- Upgrade weak evidence to strong language

### Verification Standard

To be considered core, a panel should:

- have panel-level provenance
- have variant-level evidence metadata
- avoid diagnostic or treatment claims
- avoid overstated behavioral/psychiatric conclusions
- be understandable without hidden assumptions
- end with an explicit repository decision in metadata, not just a narrative opinion

### LLM Instruction Template

```text
Review this panel for possible core inclusion.
Do not invent missing sources.
If evidence or provenance is missing, fail the review.
Downgrade or remove claims that are too strong.
Prefer rejecting a variant over overstating confidence.
```

## Hard Rules for All LLM Panel Work

- Never confuse exploratory interpretation with clinical guidance
- Never use a single SNP to claim a diagnosis
- Never use stronger language than the evidence supports
- Never add a panel to the repository as core without provenance
- If uncertain, keep the panel local and unverified

## Suggested Review Outcome Labels

- `approved_for_core`
- `needs_sources`
- `needs_weaker_language`
- `experimental_only`
- `reject`

Use `hda panel-audit` after edits to confirm the panel still matches the repository workflow.
