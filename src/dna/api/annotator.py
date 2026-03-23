"""Unified annotation module — fetches from all sources, caches in SQLite."""

import asyncio
import json
from datetime import datetime, timezone

import httpx

from dna.api import clinvar, ensembl, snpedia
from dna.config import get_active_subject, get_db_path
from dna.db.schema import get_connection, init_db

SOURCES = ["snpedia", "clinvar", "ensembl"]


def _get_cached(rsid: str, db_path, source: str | None = None) -> list[dict]:
    """Get cached annotations from SQLite."""
    conn = get_connection(db_path)
    if source:
        rows = conn.execute(
            "SELECT * FROM annotations WHERE rsid = ? AND source = ?",
            (rsid.lower(), source),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM annotations WHERE rsid = ?",
            (rsid.lower(),),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _save_annotation(annotation: dict, db_path) -> None:
    """Save or update an annotation in the cache."""
    conn = get_connection(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO annotations
           (rsid, source, gene, clinical_significance, condition, summary,
            risk_allele, population_frequency, raw_data, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            annotation.get("rsid", "").lower(),
            annotation.get("source", ""),
            annotation.get("gene"),
            annotation.get("clinical_significance"),
            annotation.get("condition"),
            annotation.get("summary"),
            annotation.get("risk_allele"),
            annotation.get("population_frequency"),
            json.dumps({k: v for k, v in annotation.items()
                        if k not in ("rsid", "source", "gene", "clinical_significance",
                                     "condition", "summary", "risk_allele",
                                     "population_frequency")}),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


async def annotate_snp(
    rsid: str,
    subject: str | None = None,
    sources: list[str] | None = None,
    force_refresh: bool = False,
) -> dict:
    """Annotate a SNP from all online sources, with local caching.

    Args:
        rsid: SNP identifier (e.g. 'rs1234')
        subject: Subject key (for cache DB). Uses active subject if not specified.
        sources: Which sources to query. Defaults to all.
        force_refresh: If True, bypass cache and re-fetch.

    Returns:
        Dict with merged annotations from all sources.
    """
    subject = subject or get_active_subject()
    db_path = get_db_path(subject)
    init_db(db_path)

    sources = sources or SOURCES
    rsid = rsid.lower()

    # Check cache first
    if not force_refresh:
        cached = _get_cached(rsid, db_path)
        cached_sources = {c["source"] for c in cached}
        missing_sources = [s for s in sources if s not in cached_sources]
    else:
        cached = []
        missing_sources = list(sources)

    # Fetch missing from online
    fetched = []
    if missing_sources:
        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = []
            for src in missing_sources:
                if src == "snpedia":
                    tasks.append(("snpedia", snpedia.fetch_snp(rsid, client)))
                elif src in ("clinvar", "dbsnp"):
                    tasks.append(("clinvar", clinvar.fetch_snp(rsid, client)))
                elif src == "ensembl":
                    tasks.append(("ensembl", ensembl.fetch_snp(rsid, client)))

            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

            for (src_name, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    continue
                if result is not None:
                    _save_annotation(result, db_path)
                    fetched.append(result)

    # Merge all annotations
    all_annotations = cached + fetched
    return _merge_annotations(rsid, all_annotations)


def _merge_annotations(rsid: str, annotations: list[dict]) -> dict:
    """Merge annotations from multiple sources into a single result."""
    merged = {
        "rsid": rsid,
        "sources": [],
        "gene": None,
        "clinical_significance": None,
        "condition": None,
        "summary": None,
        "risk_allele": None,
        "population_frequency": None,
        "details": {},
    }

    for ann in annotations:
        source = ann.get("source", "unknown")
        merged["sources"].append(source)
        merged["details"][source] = ann

        # Prefer non-null values, prioritize clinvar > ensembl > snpedia for clinical
        if ann.get("gene") and not merged["gene"]:
            merged["gene"] = ann["gene"]
        if ann.get("clinical_significance") and not merged["clinical_significance"]:
            merged["clinical_significance"] = ann["clinical_significance"]
        if ann.get("condition") and not merged["condition"]:
            merged["condition"] = ann["condition"]
        if ann.get("summary") and not merged["summary"]:
            merged["summary"] = ann["summary"]
        if ann.get("risk_allele") and not merged["risk_allele"]:
            merged["risk_allele"] = ann["risk_allele"]
        if ann.get("population_frequency") and not merged["population_frequency"]:
            merged["population_frequency"] = ann["population_frequency"]

    return merged


def annotate_snp_sync(
    rsid: str,
    subject: str | None = None,
    sources: list[str] | None = None,
    force_refresh: bool = False,
) -> dict:
    """Synchronous wrapper around annotate_snp."""
    return asyncio.run(annotate_snp(rsid, subject, sources, force_refresh))


async def annotate_batch(
    rsids: list[str],
    subject: str | None = None,
    sources: list[str] | None = None,
    delay: float = 0.5,
) -> list[dict]:
    """Annotate multiple SNPs with rate limiting.

    Args:
        rsids: List of SNP identifiers
        subject: Subject key
        sources: Which sources to query
        delay: Seconds between requests (rate limiting)
    """
    results = []
    for rsid in rsids:
        result = await annotate_snp(rsid, subject, sources)
        results.append(result)
        if delay > 0:
            await asyncio.sleep(delay)
    return results
