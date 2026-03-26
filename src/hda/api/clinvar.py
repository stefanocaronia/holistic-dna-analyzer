"""ClinVar / dbSNP client via NCBI E-utilities API."""

import httpx

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TIMEOUT = 15.0


async def fetch_snp(rsid: str, client: httpx.AsyncClient | None = None) -> dict | None:
    """Fetch SNP info from dbSNP/ClinVar via NCBI E-utilities.

    Returns dict with clinical significance, gene, condition, etc.
    Returns None if not found.
    """
    # Strip 'rs' prefix for the numeric ID
    rs_id = rsid.lower().replace("rs", "")

    should_close = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)

    try:
        # Step 1: Search ClinVar for this rsid
        search_resp = await client.get(
            f"{EUTILS_BASE}/esearch.fcgi",
            params={
                "db": "clinvar",
                "term": f"{rsid}[Variant ID]",
                "retmode": "json",
                "retmax": 5,
            },
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()

        id_list = search_data.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            # Try dbSNP directly for basic info
            return await _fetch_dbsnp(rsid, rs_id, client)

        # Step 2: Fetch ClinVar summaries
        summary_resp = await client.get(
            f"{EUTILS_BASE}/esummary.fcgi",
            params={
                "db": "clinvar",
                "id": ",".join(id_list),
                "retmode": "json",
            },
        )
        summary_resp.raise_for_status()
        summary_data = summary_resp.json()

        result = summary_data.get("result", {})
        annotations = []

        for uid in id_list:
            entry = result.get(uid, {})
            if not entry or "error" in entry:
                continue

            genes = entry.get("genes", [])
            gene_name = genes[0]["symbol"] if genes else None

            clinical_sig = entry.get("clinical_significance", {})
            description = clinical_sig.get("description", "") if isinstance(clinical_sig, dict) else str(clinical_sig)

            trait_set = entry.get("trait_set", [])
            conditions = []
            for trait in trait_set:
                trait_name = trait.get("trait_name", "")
                if trait_name:
                    conditions.append(trait_name)

            annotations.append({
                "clinvar_id": uid,
                "gene": gene_name,
                "clinical_significance": description,
                "condition": "; ".join(conditions) if conditions else None,
                "title": entry.get("title", ""),
            })

        if not annotations:
            return await _fetch_dbsnp(rsid, rs_id, client)

        # Merge annotations into a single result
        best = annotations[0]
        all_conditions = set()
        all_significances = set()
        for a in annotations:
            if a.get("condition"):
                all_conditions.update(a["condition"].split("; "))
            if a.get("clinical_significance"):
                all_significances.add(a["clinical_significance"])

        return {
            "rsid": rsid.lower(),
            "source": "clinvar",
            "gene": best.get("gene"),
            "clinical_significance": "; ".join(sorted(all_significances)) or None,
            "condition": "; ".join(sorted(all_conditions)) or None,
            "summary": best.get("title"),
            "clinvar_ids": id_list,
        }

    finally:
        if should_close:
            await client.aclose()


async def _fetch_dbsnp(rsid: str, rs_id: str, client: httpx.AsyncClient) -> dict | None:
    """Fallback: fetch basic info from dbSNP."""
    try:
        resp = await client.get(
            f"{EUTILS_BASE}/esummary.fcgi",
            params={
                "db": "snp",
                "id": rs_id,
                "retmode": "json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        result = data.get("result", {})
        entry = result.get(rs_id, {})

        if not entry or "error" in entry:
            return None

        genes = entry.get("genes", [])
        gene_name = genes[0]["name"] if genes else None

        clinical = entry.get("clinical_significance", "")

        return {
            "rsid": rsid.lower(),
            "source": "dbsnp",
            "gene": gene_name,
            "clinical_significance": clinical or None,
            "condition": None,
            "summary": entry.get("docsum", None),
            "snp_class": entry.get("snp_class", None),
        }
    except Exception:
        return None
