"""Panel analysis engine — run curated SNP panels against a subject's genome."""

from pathlib import Path

import yaml

from hda.config import DATA_DIR, get_active_subject
from hda.db.query import get_snp

PANELS_DIR = DATA_DIR / "panels"


def list_panels() -> list[dict]:
    """List all available analysis panels."""
    panels = []
    for f in sorted(PANELS_DIR.glob("*.yaml")):
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        panels.append({
            "id": f.stem,
            "name": data.get("name", f.stem),
            "description": data.get("description", ""),
            "category": data.get("category", ""),
            "variant_count": len(data.get("variants", [])),
        })
    return panels


def load_panel(panel_id: str) -> dict:
    """Load a panel definition from YAML."""
    path = PANELS_DIR / f"{panel_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Panel '{panel_id}' not found. Available: {[p['id'] for p in list_panels()]}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def analyze_panel(panel_id: str, subject: str | None = None) -> dict:
    """Run a panel analysis against a subject's genome.

    Args:
        panel_id: Panel identifier (e.g. 'pharmacogenomics', 'cardiovascular')
        subject: Subject key. Uses active subject if not specified.

    Returns:
        Dict with panel info and per-variant results including genotype and interpretation.
    """
    subject = subject or get_active_subject()
    panel = load_panel(panel_id)

    results = []
    found_count = 0
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

    return {
        "panel_id": panel_id,
        "panel_name": panel.get("name", panel_id),
        "description": panel.get("description", ""),
        "category": panel.get("category", ""),
        "subject": subject,
        "total_variants": len(results),
        "found_in_genome": found_count,
        "results": results,
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
            if effect and effect not in ("normal", "lower_risk", "no_e4", "no_e2"):
                notable.append({
                    "panel": panel["panel_name"],
                    "rsid": result["rsid"],
                    "gene": result["gene"],
                    "trait": result["trait"],
                    "genotype": result["genotype"],
                    "effect": effect,
                    "description": result["description"],
                })

    return notable
