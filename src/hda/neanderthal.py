"""Exploratory Neanderthal variant counting from consumer-genotyping data.

This module does not attempt to estimate "percent Neanderthal DNA". Instead it
counts copies of a curated starter panel of Neanderthal-associated alleles that
are commonly present on consumer chips, then compares the observed copy count
with rough 1000 Genomes superpopulation expectations.
"""

from math import erf, sqrt

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

# Trait-associated Neanderthal-derived variants listed in the official 23andMe
# Neanderthal Ancestry Inference white paper (2020), Table 1. These are not a
# substitute for a full introgression map; they are a practical starter panel.
WHITE_PAPER_MARKERS = [
    {"rsid": "rs72686076", "allele": "A", "trait": "Ability to smell", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs62405860", "allele": "C", "trait": "Fear of heights / hoarding", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs114344942", "allele": "T", "trait": "Body shape / stretch marks", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs62569478", "allele": "C", "trait": "Body shape", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs75906140", "allele": "A", "trait": "Chin dimple", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs75859481", "allele": "G", "trait": "Crying while cutting onions", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs62243065", "allele": "T", "trait": "Dandruff", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs17068342", "allele": "T", "trait": "Earlobes", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs113229445", "allele": "A", "trait": "Fear of public speaking", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs2308321", "allele": "G", "trait": "Full stomach sneeze reflex", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs7169404", "allele": "T", "trait": "Feeling hangry", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs17404153", "allele": "T", "trait": "Hitchhiker's thumb", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs3807714", "allele": "G", "trait": "Leafy greens / sweet-vs-salty preference", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs12440878", "allele": "A", "trait": "Mosquito bite itch", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs74606019", "allele": "C", "trait": "Mosquito bite itch", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs17672692", "allele": "T", "trait": "Sprint vs. distance", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs2562762", "allele": "G", "trait": "Sprint vs. distance", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs12912713", "allele": "C", "trait": "Sprint vs. distance", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs117334853", "allele": "G", "trait": "Sweat during a workout", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs78329842", "allele": "G", "trait": "Salt preference", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs61740705", "allele": "G", "trait": "Salt preference", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs13097409", "allele": "G", "trait": "Fear of heights", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs1566479", "allele": "C", "trait": "Fear of heights", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs4849721", "allele": "T", "trait": "Blushing / sweat during a workout", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs11213819", "allele": "T", "trait": "Chocolate preference / dark chocolate sneeze reflex", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs3818532", "allele": "G", "trait": "Dandruff / sprint vs. distance", "source": "23andMe White Paper 23-05 (2020)"},
    {"rsid": "rs1364405", "allele": "A", "trait": "Sense of direction", "source": "23andMe White Paper 23-05 (2020)"},
]

# A few literature-grounded loci with strong public visibility are added so the
# panel is not limited to trait-report SNPs alone.
LITERATURE_MARKERS = [
    {
        "rsid": "rs4833095",
        "allele": "T",
        "trait": "TLR1/6/10 immune haplotype",
        "source": "Dannemann et al. 2016, PMID 26748514",
    },
    {
        "rsid": "rs10774671",
        "allele": "G",
        "trait": "OAS1 splice isoform / antiviral response",
        "source": "Mendez et al. 2013 and Sams et al. 2016",
    },
    {
        "rsid": "rs35044562",
        "allele": "G",
        "trait": "Chromosome 3 COVID-19 risk haplotype",
        "source": "Zeberg and Pääbo 2020, Nature",
    },
]

NEANDERTHAL_MARKERS = WHITE_PAPER_MARKERS + LITERATURE_MARKERS


def _extract_superpopulation_frequencies(populations: list[dict] | None) -> dict[str, dict[str, float]]:
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


def _load_ensembl_details(rsid: str, subject: str, force_refresh: bool) -> dict:
    annotation = annotate_snp_sync(rsid, subject=subject, sources=["ensembl"], force_refresh=force_refresh)
    details = annotation.get("details", {}).get("ensembl", {})
    if details.get("populations") or force_refresh:
        return details
    refreshed = annotate_snp_sync(rsid, subject=subject, sources=["ensembl"], force_refresh=True)
    return refreshed.get("details", {}).get("ensembl", {})


def _count_allele(genotype: str, allele: str) -> int:
    return sum(1 for base in genotype.upper() if base == allele.upper())


def _normal_cdf(z_score: float) -> float:
    return 0.5 * (1 + erf(z_score / sqrt(2)))


def _comparison_label(z_score: float) -> str:
    if z_score >= 1.5:
        return "higher_than_expected"
    if z_score <= -1.5:
        return "lower_than_expected"
    return "within_expected_range"


def estimate_neanderthal_ancestry(
    subject: str | None = None,
    force_refresh: bool = False,
) -> dict:
    """Count a starter panel of Neanderthal-associated alleles.

    This is an exploratory marker-count score, not a whole-genome percentage.
    """
    subject = subject or get_active_subject()
    observed_copy_count = 0
    markers_found = 0
    positive_markers = 0
    marker_rows = []
    superpop_stats = {
        code: {"expected_copy_count": 0.0, "variance": 0.0, "markers_with_frequency": 0}
        for code in SUPERPOPULATIONS
    }

    for marker in NEANDERTHAL_MARKERS:
        row = get_snp(marker["rsid"], subject)
        if not row or not row.get("genotype"):
            marker_rows.append({**marker, "status": "missing_in_genome"})
            continue

        genotype = row["genotype"]
        dosage = _count_allele(genotype, marker["allele"])
        found_row = {
            **marker,
            "genotype": genotype,
            "copies": dosage,
            "status": "present",
        }
        markers_found += 1
        observed_copy_count += dosage
        if dosage:
            positive_markers += 1

        details = _load_ensembl_details(marker["rsid"], subject, force_refresh)
        frequencies = _extract_superpopulation_frequencies(details.get("populations"))
        if len(frequencies) == len(SUPERPOPULATIONS):
            archaic_freqs = {}
            for code, alleles in frequencies.items():
                p = alleles.get(marker["allele"].upper(), 0.0)
                superpop_stats[code]["expected_copy_count"] += 2 * p
                superpop_stats[code]["variance"] += 2 * p * (1 - p)
                superpop_stats[code]["markers_with_frequency"] += 1
                archaic_freqs[code] = round(p, 4)
            found_row["archaic_allele_frequency"] = archaic_freqs

        marker_rows.append(found_row)

    comparisons = []
    for code, stats in superpop_stats.items():
        variance = stats["variance"]
        stddev = sqrt(variance) if variance > 0 else 0.0
        z_score = (observed_copy_count - stats["expected_copy_count"]) / stddev if stddev else 0.0
        percentile = _normal_cdf(z_score)
        comparisons.append(
            {
                "population": code,
                "label": SUPERPOPULATIONS[code],
                "expected_copy_count": round(stats["expected_copy_count"], 2),
                "markers_with_frequency": stats["markers_with_frequency"],
                "z_score": round(z_score, 2),
                "percentile": percentile,
                "comparison": _comparison_label(z_score),
            }
        )

    comparisons.sort(key=lambda item: item["population"])

    positive_rows = [row for row in marker_rows if row.get("copies", 0) > 0]
    status = "ok" if markers_found >= 8 else "limited_coverage"

    return {
        "subject": subject,
        "status": status,
        "review_status": "exploratory",
        "requires_disclaimer": True,
        "interpretation_warning": (
            "This output is not a percent-Neanderthal estimate. It is a starter-panel count of known "
            "Neanderthal-associated alleles present on the subject's chip. It is useful for exploration, "
            "not for formal ancestry inference."
        ),
        "method": (
            "Counts copies of curated Neanderthal-associated alleles from an initial consumer-chip-friendly panel, "
            "then compares the observed copy count with coarse 1000 Genomes superpopulation expectations."
        ),
        "observed_copy_count": observed_copy_count,
        "positive_markers": positive_markers,
        "markers_found": markers_found,
        "candidate_markers": len(NEANDERTHAL_MARKERS),
        "positive_marker_examples": positive_rows[:10],
        "comparisons": comparisons,
        "markers": marker_rows,
        "limitations": [
            "This is a starter panel, not the full 23andMe or research-grade variant set.",
            "A copy count is correlated with archaic signal, but it is not a direct genomic percentage.",
            "Many true Neanderthal-introgressed regions are not tagged on consumer arrays.",
            "Population comparisons are rough because they rely on unphased single-marker frequencies.",
        ],
        "sources": [
            {
                "type": "official_method",
                "label": "23andMe White Paper 23-05: Neanderthal Ancestry Inference (2020)",
                "url": "https://permalinks.23andme.com/pdf/23-05_neanderthal_ancestry_inference.pdf",
            },
            {
                "type": "paper",
                "label": "Dannemann et al. 2016: TLR introgressed haplotypes",
                "url": "https://pubmed.ncbi.nlm.nih.gov/26748514/",
            },
            {
                "type": "paper",
                "label": "Sams et al. 2016: OAS Neandertal haplotype",
                "url": "https://genomebiology.biomedcentral.com/articles/10.1186/s13059-016-1098-6",
            },
            {
                "type": "paper",
                "label": "Zeberg and Pääbo 2020: severe COVID-19 risk haplotype",
                "url": "https://www.nature.com/articles/s41586-020-2818-3",
            },
        ],
    }
