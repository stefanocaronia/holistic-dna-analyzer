"""Panel analysis engine — run curated SNP panels against a subject's genome."""

from pathlib import Path

import yaml

from hda.config import DATA_DIR, get_active_subject
from hda.db.query import get_snp

PANELS_DIR = DATA_DIR / "panels"
PANEL_SUFFIX_REVIEW_STATUS = {
    ".experimental": "exploratory",
    ".draft": "draft",
}
PANEL_ID_ALIASES = {
    "nutrigenomics": "nutrition_metabolism",
    "nutrition_advanced": "nutrition_micronutrients",
}
PANEL_REVIEW_OUTCOMES = {
    "approved_for_core",
    "experimental_only",
    "needs_sources",
    "needs_weaker_language",
    "reject",
}


def _require_mapping(data: object, path: Path) -> dict:
    """Ensure the decoded YAML document is a mapping."""
    if not isinstance(data, dict):
        raise ValueError(f"Panel '{path.name}' must decode to a mapping.")
    return data


def _split_panel_filename(path: Path) -> tuple[str, str | None]:
    """Split a panel filename into base id and optional status suffix."""
    stem = path.stem
    for suffix, review_status in PANEL_SUFFIX_REVIEW_STATUS.items():
        if stem.endswith(suffix):
            return stem.removesuffix(suffix), review_status
    return stem, None


def _validate_panel_definition(path: Path, panel_id: str, data: dict, inferred_review_status: str | None = None) -> None:
    """Validate the panel schema used by the runtime."""
    review_status = data.get("review_status") or inferred_review_status or "verified"
    status = data.get("status")
    review_outcome = data.get("review_outcome")
    review_notes = data.get("review_notes")

    required_panel_fields = (
        "name",
        "description",
        "category",
        "summary",
        "sources",
        "limitations",
        "version",
        "last_reviewed",
        "review_outcome",
        "review_notes",
    )
    missing_panel_fields = [field for field in required_panel_fields if not data.get(field)]
    if missing_panel_fields:
        raise ValueError(
            f"Panel '{panel_id}' is missing required metadata: {', '.join(missing_panel_fields)}."
        )

    if not isinstance(data.get("sources"), list):
        raise ValueError(f"Panel '{panel_id}' must define 'sources' as a list.")
    if not isinstance(data.get("limitations"), list):
        raise ValueError(f"Panel '{panel_id}' must define 'limitations' as a list.")
    if not isinstance(data.get("variants", []), list):
        raise ValueError(f"Panel '{panel_id}' must define 'variants' as a list.")
    if data.get("composites") is not None and not isinstance(data.get("composites"), list):
        raise ValueError(f"Panel '{panel_id}' must define 'composites' as a list when present.")
    if review_outcome not in PANEL_REVIEW_OUTCOMES:
        raise ValueError(
            f"Panel '{panel_id}' has invalid review_outcome '{review_outcome}'. "
            f"Allowed: {sorted(PANEL_REVIEW_OUTCOMES)}."
        )
    if not isinstance(review_notes, str):
        raise ValueError(f"Panel '{panel_id}' must define 'review_notes' as a string.")

    if review_status == "verified" and status not in (None, "core"):
        raise ValueError(f"Verified panel '{panel_id}' must have status 'core'.")
    if review_status == "exploratory" and status not in (None, "experimental"):
        raise ValueError(f"Exploratory panel '{panel_id}' must have status 'experimental'.")
    if review_status == "draft" and status not in (None, "draft"):
        raise ValueError(f"Draft panel '{panel_id}' must have status 'draft'.")
    if review_status == "verified" and review_outcome != "approved_for_core":
        raise ValueError(f"Verified panel '{panel_id}' must have review_outcome 'approved_for_core'.")
    if review_status == "exploratory" and review_outcome != "experimental_only":
        raise ValueError(f"Exploratory panel '{panel_id}' must have review_outcome 'experimental_only'.")
    if review_status == "draft" and review_outcome not in {"needs_sources", "needs_weaker_language", "reject"}:
        raise ValueError(
            f"Draft panel '{panel_id}' must have review_outcome in "
            "{'needs_sources', 'needs_weaker_language', 'reject'}."
        )

    for variant in data.get("variants", []):
        missing_variant_fields = [
            field for field in ("rsid", "gene", "trait", "evidence_level", "sources", "genotypes")
            if not variant.get(field)
        ]
        if missing_variant_fields:
            rsid = variant.get("rsid", "<unknown>")
            raise ValueError(
                f"Panel '{panel_id}' variant '{rsid}' is missing required fields: "
                f"{', '.join(missing_variant_fields)}."
            )
        if not isinstance(variant.get("sources"), list):
            raise ValueError(f"Panel '{panel_id}' variant '{variant['rsid']}' must define 'sources' as a list.")
        if not isinstance(variant.get("genotypes"), dict):
            raise ValueError(f"Panel '{panel_id}' variant '{variant['rsid']}' must define 'genotypes' as a mapping.")

    for composite in data.get("composites", []):
        missing_composite_fields = [
            field for field in ("id", "gene", "trait", "components", "genotypes")
            if not composite.get(field)
        ]
        if missing_composite_fields:
            composite_id = composite.get("id", "<unknown>")
            raise ValueError(
                f"Panel '{panel_id}' composite '{composite_id}' is missing required fields: "
                f"{', '.join(missing_composite_fields)}."
            )
        if not isinstance(composite.get("components"), list):
            raise ValueError(f"Panel '{panel_id}' composite '{composite['id']}' must define 'components' as a list.")
        if not isinstance(composite.get("genotypes"), dict):
            raise ValueError(f"Panel '{panel_id}' composite '{composite['id']}' must define 'genotypes' as a mapping.")


def _panel_metadata(panel_id: str, data: dict, inferred_review_status: str | None = None) -> dict:
    """Extract common panel metadata exposed to tools and UI."""
    review_status = data.get("review_status") or inferred_review_status or "verified"
    status = data.get("status")
    if not status:
        if inferred_review_status is None:
            status = "core"
        elif inferred_review_status == "exploratory":
            status = "experimental"
        elif inferred_review_status == "draft":
            status = "draft"
        else:
            status = "custom"

    return {
        "id": panel_id,
        "name": data.get("name", panel_id),
        "description": data.get("description", ""),
        "category": data.get("category", ""),
        "status": status,
        "review_status": review_status,
        "version": data.get("version"),
        "last_reviewed": data.get("last_reviewed"),
        "review_outcome": data.get("review_outcome"),
        "review_notes": data.get("review_notes", ""),
        "summary": data.get("summary", ""),
        "sources": data.get("sources", []),
        "limitations": data.get("limitations", []),
        "variant_count": len(data.get("variants", [])),
    }


def resolve_panel_id(panel_id: str) -> str:
    """Map legacy panel ids to their canonical names."""
    return PANEL_ID_ALIASES.get(panel_id, panel_id)


def list_panels() -> list[dict]:
    """List all available analysis panels."""
    panels = []
    for f in sorted(PANELS_DIR.glob("*.yaml")):
        with open(f, "r", encoding="utf-8") as fh:
            data = _require_mapping(yaml.safe_load(fh), f)
        panel_id, inferred_review_status = _split_panel_filename(f)
        _validate_panel_definition(f, panel_id, data, inferred_review_status)
        panels.append(_panel_metadata(panel_id, data, inferred_review_status))
    return panels


def load_panel(panel_id: str) -> dict:
    """Load a panel definition from YAML."""
    canonical_id = resolve_panel_id(panel_id)
    candidates = [PANELS_DIR / f"{canonical_id}.yaml"]
    candidates.extend(PANELS_DIR / f"{canonical_id}{suffix}.yaml" for suffix in PANEL_SUFFIX_REVIEW_STATUS)

    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError(f"Panel '{panel_id}' not found. Available: {[p['id'] for p in list_panels()]}")
    with open(path, "r", encoding="utf-8") as f:
        data = _require_mapping(yaml.safe_load(f), path)

    _, inferred_review_status = _split_panel_filename(path)
    _validate_panel_definition(path, canonical_id, data, inferred_review_status)
    metadata = _panel_metadata(canonical_id, data, inferred_review_status)
    return {**data, **metadata}


def audit_panels() -> list[dict]:
    """Audit repository panels against the panel review workflow and schema."""
    audits = []
    for path in sorted(PANELS_DIR.glob("*.yaml")):
        panel_id, inferred_review_status = _split_panel_filename(path)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = _require_mapping(yaml.safe_load(fh), path)
            _validate_panel_definition(path, panel_id, data, inferred_review_status)
            metadata = _panel_metadata(panel_id, data, inferred_review_status)
            audits.append(
                {
                    "id": panel_id,
                    "path": str(path),
                    "status": metadata["status"],
                    "review_status": metadata["review_status"],
                    "review_outcome": metadata.get("review_outcome"),
                    "last_reviewed": metadata.get("last_reviewed"),
                    "ready": metadata.get("review_outcome") in {"approved_for_core", "experimental_only"},
                    "issues": [],
                }
            )
        except Exception as e:
            audits.append(
                {
                    "id": panel_id,
                    "path": str(path),
                    "status": "invalid",
                    "review_status": inferred_review_status or "verified",
                    "review_outcome": None,
                    "last_reviewed": None,
                    "ready": False,
                    "issues": [str(e)],
                }
            )
    return audits


def analyze_panel(panel_id: str, subject: str | None = None) -> dict:
    """Run a panel analysis against a subject's genome.

    Args:
        panel_id: Panel identifier (e.g. 'pharmacogenomics', 'cardiovascular')
        subject: Subject key. Uses active subject if not specified.

    Returns:
        Dict with panel info and per-variant results including genotype and interpretation.
    """
    subject = subject or get_active_subject()
    canonical_id = resolve_panel_id(panel_id)
    panel = load_panel(panel_id)

    results = []
    found_count = 0
    genotype_by_rsid = {}
    for variant in panel.get("variants", []):
        rsid = variant["rsid"]
        snp_data = get_snp(rsid, subject)

        entry = {
            "rsid": rsid,
            "gene": variant.get("gene", ""),
            "trait": variant.get("trait", ""),
            "genotype": None,
            "effect": None,
            "description": None,
            "found": False,
        }

        if snp_data:
            genotype = snp_data["genotype"]
            entry["genotype"] = genotype
            entry["found"] = True
            found_count += 1
            genotype_by_rsid[rsid] = genotype

            # Look up interpretation — try direct match first, then aliases
            genotypes = variant.get("genotypes", {})
            aliases = variant.get("aliases", {})

            interpretation = genotypes.get(genotype)
            if not interpretation and genotype in aliases:
                interpretation = genotypes.get(aliases[genotype])
            # Try reversed genotype (e.g. TC → CT)
            if not interpretation and len(genotype) == 2:
                reversed_gt = genotype[1] + genotype[0]
                interpretation = genotypes.get(reversed_gt)
                if not interpretation and reversed_gt in aliases:
                    interpretation = genotypes.get(aliases[reversed_gt])

            if interpretation:
                entry["effect"] = interpretation.get("effect")
                entry["description"] = interpretation.get("description")
            else:
                entry["description"] = f"Genotype {genotype} not in panel definitions."

        results.append(entry)

    composite_results = []
    composite_found_count = 0
    for composite in panel.get("composites", []):
        component_rsids = composite.get("components", [])
        component_genotypes = {}
        missing_components = []
        for rsid in component_rsids:
            genotype = genotype_by_rsid.get(rsid)
            if genotype is None:
                snp_data = get_snp(rsid, subject)
                genotype = snp_data["genotype"] if snp_data else None
                if genotype:
                    genotype_by_rsid[rsid] = genotype
            if genotype is None:
                missing_components.append(rsid)
            else:
                component_genotypes[rsid] = genotype

        entry = {
            "id": composite.get("id"),
            "gene": composite.get("gene", ""),
            "trait": composite.get("trait", ""),
            "genotype": None,
            "effect": None,
            "description": None,
            "found": False,
            "composite": True,
            "components": component_rsids,
            "component_genotypes": component_genotypes,
        }

        if missing_components:
            entry["description"] = f"Missing component SNPs: {', '.join(missing_components)}."
        else:
            key = "|".join(component_genotypes[rsid] for rsid in component_rsids)
            entry["genotype"] = key
            interpretation = composite.get("genotypes", {}).get(key)
            if interpretation:
                entry["found"] = True
                composite_found_count += 1
                entry["effect"] = interpretation.get("effect")
                entry["description"] = interpretation.get("description")
                entry["label"] = interpretation.get("label")
            else:
                entry["description"] = f"Composite genotype {key} not in panel definitions."

        composite_results.append(entry)

    return {
        "panel_id": canonical_id,
        "requested_panel_id": panel_id,
        "panel_name": panel.get("name", canonical_id),
        "description": panel.get("description", ""),
        "category": panel.get("category", ""),
        "status": panel.get("status", "unknown"),
        "review_status": panel.get("review_status", "unknown"),
        "version": panel.get("version"),
        "last_reviewed": panel.get("last_reviewed"),
        "summary": panel.get("summary", ""),
        "sources": panel.get("sources", []),
        "limitations": panel.get("limitations", []),
        "subject": subject,
        "total_variants": len(results) + len(composite_results),
        "found_in_genome": found_count + composite_found_count,
        "results": results,
        "composite_results": composite_results,
    }


def analyze_all_panels(subject: str | None = None) -> list[dict]:
    """Run all available panels against a subject's genome."""
    subject = subject or get_active_subject()
    panels = list_panels()
    return [analyze_panel(p["id"], subject) for p in panels]


def get_risk_summary(subject: str | None = None) -> list[dict]:
    """Get a summary of notable findings across all panels.

    Returns only variants where the subject carries a non-normal effect.
    """
    subject = subject or get_active_subject()
    all_results = analyze_all_panels(subject)
    notable = []

    for panel in all_results:
        for result in panel["results"]:
            if not result["found"]:
                continue
            effect = result.get("effect", "")
            if effect and effect not in ("normal", "lower_risk", "no_e4", "no_e2", "typical", "protective"):
                notable.append({
                    "panel": panel["panel_name"],
                    "panel_review_status": panel.get("review_status", "unknown"),
                    "rsid": result["rsid"],
                    "gene": result["gene"],
                    "trait": result["trait"],
                    "genotype": result["genotype"],
                    "effect": effect,
                    "description": result["description"],
                })
        for result in panel.get("composite_results", []):
            if not result["found"]:
                continue
            effect = result.get("effect", "")
            if effect and effect not in ("normal", "lower_risk", "no_e4", "no_e2", "typical", "protective"):
                notable.append({
                    "panel": panel["panel_name"],
                    "panel_review_status": panel.get("review_status", "unknown"),
                    "rsid": ",".join(result.get("components", [])),
                    "gene": result["gene"],
                    "trait": result["trait"],
                    "genotype": result.get("label") or result["genotype"],
                    "effect": effect,
                    "description": result["description"],
                })

    return notable
