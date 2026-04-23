"""Exploratory ancestry estimation using 1000 Genomes superpopulation frequencies.

This module intentionally stays conservative:

- it estimates coarse macro-ancestry / superpopulation fit, not ethnicity
- it uses a small panel of ancestry-informative markers common on consumer chips
- it relies on 1000 Genomes Phase 3 superpopulation frequencies exposed by
  Ensembl, so results are only as good as marker coverage and reference fit
"""

from math import exp, log

from hda.api.annotator import annotate_snp_sync
from hda.config import get_active_subject
from hda.db.query import get_snp

SUPERPOPULATIONS = {
    "AFR": "Africa",
    "AMR": "Americas",
    "EAS": "East Asia",
    "EUR": "Europe",
    "SAS": "South Asia",
}

# Small starter AIM panel. These loci are widely genotyped on consumer chips and
# show strong frequency differences across broad world regions, but the method
# remains exploratory and should not be treated as an ethnicity classifier.
DEFAULT_ANCESTRY_MARKERS = [
    {"rsid": "rs1426654", "gene": "SLC24A5", "label": "Pigmentation / West Eurasian skew"},
    {"rsid": "rs16891982", "gene": "SLC45A2", "label": "Pigmentation / European skew"},
    {"rsid": "rs2814778", "gene": "ACKR1", "label": "Duffy-null / African skew"},
    {"rsid": "rs3827760", "gene": "EDAR", "label": "Hair / tooth morphology / East Asian skew"},
    {"rsid": "rs17822931", "gene": "ABCC11", "label": "Earwax / body odor / East Asian skew"},
    {"rsid": "rs12913832", "gene": "HERC2/OCA2", "label": "Eye color / European skew"},
    {"rsid": "rs1800414", "gene": "OCA2", "label": "Pigmentation / East Asian skew"},
    {"rsid": "rs1229984", "gene": "ADH1B", "label": "Alcohol metabolism / East Asian skew"},
    {"rsid": "rs671", "gene": "ALDH2", "label": "Alcohol flush / East Asian skew"},
    {"rsid": "rs9282541", "gene": "ABCA1", "label": "Native-American-linked signal within AMR"},
    {"rsid": "rs738409", "gene": "PNPLA3", "label": "Frequency-skewed liver-fat locus"},
    {"rsid": "rs4988235", "gene": "MCM6/LCT", "label": "Lactase persistence / European skew"},
    {"rsid": "rs1042602", "gene": "TYR", "label": "Pigmentation / frequency-skewed across Eurasia"},
    {"rsid": "rs1545397", "gene": "OCA2", "label": "Pigmentation / frequency-skewed across Eurasia"},
]

MIN_ALLELE_FREQUENCY = 1e-4
DEFAULT_INFORMATIVE_SPREAD = 0.35


def _extract_superpopulation_frequencies(populations: list[dict] | None) -> dict[str, dict[str, float]]:
    """Extract 1000 Genomes Phase 3 superpopulation allele frequencies."""
    by_pop: dict[str, dict[str, float]] = {}
    for row in populations or []:
        population = row.get("population")
        allele = row.get("allele")
        frequency = row.get("frequency")
        if (
            not population
            or not allele
            or frequency is None
            or not population.startswith("1000GENOMES:phase_3:")
        ):
            continue
        code = population.rsplit(":", 1)[-1]
        if code not in SUPERPOPULATIONS:
            continue
        by_pop.setdefault(code, {})[allele.upper()] = float(frequency)
    return by_pop


def _marker_informativeness(frequencies: dict[str, dict[str, float]]) -> float:
    """Return the strongest allele-frequency spread across superpopulations."""
    alleles = {allele for pop in frequencies.values() for allele in pop}
    if not alleles:
        return 0.0
    spreads = []
    for allele in alleles:
        values = [pop.get(allele, 0.0) for pop in frequencies.values()]
        spreads.append(max(values) - min(values))
    return max(spreads, default=0.0)


def _genotype_likelihood(genotype: str, population_frequencies: dict[str, float]) -> float:
    """Estimate the genotype likelihood under Hardy-Weinberg equilibrium."""
    alleles = [allele.upper() for allele in genotype if allele.isalpha()]
    if len(alleles) != 2:
        return MIN_ALLELE_FREQUENCY**2

    a = max(population_frequencies.get(alleles[0], 0.0), MIN_ALLELE_FREQUENCY)
    b = max(population_frequencies.get(alleles[1], 0.0), MIN_ALLELE_FREQUENCY)
    if alleles[0] == alleles[1]:
        return max(a * a, MIN_ALLELE_FREQUENCY**2)
    return max(2 * a * b, 2 * (MIN_ALLELE_FREQUENCY**2))


def _normalize_scores(log_scores: dict[str, float]) -> list[dict]:
    """Convert log-likelihoods into normalized posterior-like scores."""
    if not log_scores:
        return []
    max_score = max(log_scores.values())
    weights = {code: exp(score - max_score) for code, score in log_scores.items()}
    total = sum(weights.values()) or 1.0
    results = []
    for code, label in SUPERPOPULATIONS.items():
        results.append(
            {
                "population": code,
                "label": label,
                "probability": weights.get(code, 0.0) / total,
            }
        )
    return sorted(results, key=lambda item: item["probability"], reverse=True)


def _confidence_bucket(best_probability: float, markers_used: int, min_markers: int) -> str:
    """Keep confidence language conservative for this exploratory feature."""
    if markers_used < min_markers:
        return "low"
    if markers_used >= 8 and best_probability >= 0.75:
        return "moderate"
    return "low"


def _load_ensembl_details(rsid: str, subject: str, force_refresh: bool) -> dict:
    """Fetch cached/fresh Ensembl details, refreshing older cache entries if needed."""
    annotation = annotate_snp_sync(rsid, subject=subject, sources=["ensembl"], force_refresh=force_refresh)
    details = annotation.get("details", {}).get("ensembl", {})
    if details.get("populations") or force_refresh:
        return details

    refreshed = annotate_snp_sync(rsid, subject=subject, sources=["ensembl"], force_refresh=True)
    return refreshed.get("details", {}).get("ensembl", {})


def estimate_ancestry(
    subject: str | None = None,
    force_refresh: bool = False,
    min_markers: int = 6,
    informative_spread: float = DEFAULT_INFORMATIVE_SPREAD,
) -> dict:
    """Estimate coarse ancestry fit across 1000 Genomes superpopulations.

    This is deliberately broad and exploratory. It should be interpreted as a
    macro-ancestry likelihood over AFR / AMR / EAS / EUR / SAS, not as an
    ethnicity or nationality detector.
    """
    subject = subject or get_active_subject()
    log_scores = {code: 0.0 for code in SUPERPOPULATIONS}
    marker_rows = []
    markers_in_genome = 0
    markers_with_reference = 0
    markers_used = 0

    for marker in DEFAULT_ANCESTRY_MARKERS:
        snp = get_snp(marker["rsid"], subject)
        if not snp or not snp.get("genotype"):
            marker_rows.append({**marker, "status": "missing_in_genome"})
            continue

        markers_in_genome += 1
        genotype = snp["genotype"]
        details = _load_ensembl_details(marker["rsid"], subject, force_refresh)
        frequencies = _extract_superpopulation_frequencies(details.get("populations"))

        if len(frequencies) != len(SUPERPOPULATIONS):
            marker_rows.append(
                {
                    **marker,
                    "genotype": genotype,
                    "status": "missing_reference_data",
                }
            )
            continue

        markers_with_reference += 1
        spread = _marker_informativeness(frequencies)
        if spread < informative_spread:
            marker_rows.append(
                {
                    **marker,
                    "genotype": genotype,
                    "status": "low_informativeness",
                    "informative_spread": round(spread, 3),
                }
            )
            continue

        likelihoods = {
            code: _genotype_likelihood(genotype, pop_freqs)
            for code, pop_freqs in frequencies.items()
        }
        for code, likelihood in likelihoods.items():
            log_scores[code] += log(likelihood)
        markers_used += 1

        top_population = max(likelihoods, key=likelihoods.get)
        marker_rows.append(
            {
                **marker,
                "genotype": genotype,
                "status": "used",
                "informative_spread": round(spread, 3),
                "top_population": top_population,
                "top_population_label": SUPERPOPULATIONS[top_population],
            }
        )

    scores = _normalize_scores(log_scores) if markers_used else []
    best_probability = scores[0]["probability"] if scores else 0.0
    confidence = _confidence_bucket(best_probability, markers_used, min_markers)
    status = "ok" if markers_used >= min_markers else "insufficient_markers"

    return {
        "subject": subject,
        "status": status,
        "review_status": "exploratory",
        "requires_disclaimer": True,
        "interpretation_warning": (
            "This ancestry output is exploratory and intentionally coarse. It estimates fit to "
            "1000 Genomes macro-populations (AFR/AMR/EAS/EUR/SAS), not ethnicity, nationality, "
            "or recent family origin. Mixed backgrounds and underrepresented populations can be misfit."
        ),
        "method": (
            "Likelihood-based comparison of the subject genotype against 1000 Genomes Phase 3 "
            "superpopulation allele frequencies exposed by the Ensembl GRCh37 variation API."
        ),
        "confidence": confidence,
        "candidate_markers": len(DEFAULT_ANCESTRY_MARKERS),
        "markers_in_genome": markers_in_genome,
        "markers_with_reference_data": markers_with_reference,
        "markers_used": markers_used,
        "min_markers_requested": min_markers,
        "scores": scores,
        "primary_population": scores[0] if scores else None,
        "markers": marker_rows,
        "limitations": [
            "This is a coarse superpopulation estimate, not an ethnicity breakdown.",
            "The AMR reference in 1000 Genomes is admixed and is not a Native-American-specific model.",
            "A small marker panel can miss recent admixture and overstate the nearest reference cluster.",
            "Older cached Ensembl annotations are auto-refreshed because population frequencies require the pops=1 endpoint.",
        ],
        "sources": [
            {
                "type": "ensembl",
                "label": "Ensembl GRCh37 variation endpoint with pops=1",
                "url": "https://grch37.rest.ensembl.org/documentation/info/variation_id",
            },
            {
                "type": "reference_panel",
                "label": "1000 Genomes Phase 3 superpopulations (AFR, AMR, EAS, EUR, SAS)",
                "url": "https://www.internationalgenome.org/sites/1000genomes.org/files/documents/nhgri_flyer_2013.pdf",
            },
        ],
    }
