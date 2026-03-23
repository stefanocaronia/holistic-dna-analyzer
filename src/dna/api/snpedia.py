"""SNPedia client — fetches SNP annotations from the SNPedia MediaWiki API."""

import json
import re

import httpx

BASE_URL = "https://bots.snpedia.com/api.php"
TIMEOUT = 15.0


def _parse_snpedia_wikitext(wikitext: str) -> dict:
    """Extract structured data from SNPedia wikitext markup."""
    data: dict = {}

    # Extract fields from {{rsnum}} template
    rsnum_match = re.search(r"\{\{[Rr]snum\s*\n(.*?)\}\}", wikitext, re.DOTALL)
    if rsnum_match:
        block = rsnum_match.group(1)
        for m in re.finditer(r"\|\s*(\w+)\s*=\s*(.+?)(?:\n|$)", block):
            key = m.group(1).strip().lower()
            val = m.group(2).strip()
            if val and val != "?":
                data[key] = val

    # Extract summary: first plain-text sentence outside templates
    lines = []
    in_template = 0
    for line in wikitext.split("\n"):
        if "{{" in line:
            in_template += line.count("{{") - line.count("}}")
            continue
        if in_template > 0:
            in_template += line.count("{{") - line.count("}}")
            continue
        stripped = line.strip()
        if stripped and not stripped.startswith("|") and not stripped.startswith("{"):
            # Clean wiki markup
            clean = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", stripped)
            clean = re.sub(r"'''?", "", clean)
            clean = re.sub(r"<ref[^>]*>.*?</ref>", "", clean)
            clean = re.sub(r"<[^>]+>", "", clean)
            clean = clean.strip()
            if clean and len(clean) > 10:
                lines.append(clean)

    if lines:
        data["summary"] = " ".join(lines[:3])

    return data


async def fetch_snp(rsid: str, client: httpx.AsyncClient | None = None) -> dict | None:
    """Fetch SNP annotation from SNPedia.

    Returns dict with keys like: gene, summary, chromosome, position, etc.
    Returns None if the SNP is not found on SNPedia.
    """
    rsid_lower = rsid.lower()
    params = {
        "action": "query",
        "titles": rsid_lower.capitalize(),  # SNPedia uses Rs1234 format
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }

    should_close = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)

    try:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id == "-1":
                return None
            revisions = page.get("revisions", [])
            if not revisions:
                return None
            wikitext = revisions[0].get("*", "")
            parsed = _parse_snpedia_wikitext(wikitext)
            parsed["rsid"] = rsid_lower
            parsed["source"] = "snpedia"
            parsed["raw_wikitext"] = wikitext
            return parsed

        return None
    finally:
        if should_close:
            await client.aclose()


async def fetch_genotype(rsid: str, genotype: str, client: httpx.AsyncClient | None = None) -> dict | None:
    """Fetch genotype-specific info from SNPedia (e.g. Rs1234(A;G) page)."""
    # SNPedia genotype pages use format Rs1234(A;G)
    alleles = f"({genotype[0]};{genotype[1]})" if len(genotype) == 2 else ""
    title = f"{rsid.capitalize()}{alleles}"

    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
    }

    should_close = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)

    try:
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id == "-1":
                return None
            revisions = page.get("revisions", [])
            if not revisions:
                return None
            wikitext = revisions[0].get("*", "")
            parsed = _parse_snpedia_wikitext(wikitext)
            parsed["rsid"] = rsid.lower()
            parsed["genotype"] = genotype
            parsed["source"] = "snpedia_genotype"
            return parsed

        return None
    finally:
        if should_close:
            await client.aclose()
