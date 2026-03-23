"""Ensembl REST API client — variant info, gene context, population frequencies."""

import httpx

BASE_URL = "https://rest.ensembl.org"
GRCH37_URL = "https://grch37.rest.ensembl.org"  # For build37 coordinates
TIMEOUT = 15.0


async def fetch_snp(rsid: str, client: httpx.AsyncClient | None = None) -> dict | None:
    """Fetch variant info from Ensembl REST API.

    Returns gene, consequence, population frequencies, etc.
    Returns None if not found.
    """
    should_close = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)

    try:
        # Use GRCh37 endpoint since our data is build37
        resp = await client.get(
            f"{GRCH37_URL}/variation/human/{rsid}",
            headers={"Content-Type": "application/json"},
        )

        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        data = resp.json()

        # Extract most clinically relevant consequence
        mappings = data.get("mappings", [])
        genes = set()
        consequences = set()
        for m in mappings:
            if m.get("assembly_name") == "GRCh37":
                pass  # All mappings from grch37 endpoint are GRCh37
            # Collect consequences from VEP-style data if present

        # Get population frequencies
        populations = data.get("populations", [])
        pop_freqs = {}
        for pop in populations:
            pop_name = pop.get("population", "")
            if any(key in pop_name for key in ["1000GENOMES", "gnomAD"]):
                allele = pop.get("allele", "")
                freq = pop.get("frequency", 0)
                if freq > 0:
                    pop_freqs[f"{pop_name}:{allele}"] = freq

        # Get clinical significance
        clinical = data.get("clinical_significance", [])

        # Fetch VEP consequences
        vep_data = await _fetch_vep(rsid, client)
        if vep_data:
            for tc in vep_data.get("transcript_consequences", []):
                gene = tc.get("gene_symbol")
                if gene:
                    genes.add(gene)
                for c in tc.get("consequence_terms", []):
                    consequences.add(c)

        # Select top population frequencies (keep it concise)
        top_freqs = dict(sorted(pop_freqs.items(), key=lambda x: -x[1])[:10])

        return {
            "rsid": rsid.lower(),
            "source": "ensembl",
            "gene": ", ".join(sorted(genes)) if genes else None,
            "clinical_significance": ", ".join(clinical) if clinical else None,
            "consequence": ", ".join(sorted(consequences)) if consequences else None,
            "population_frequency": str(top_freqs) if top_freqs else None,
            "ancestral_allele": data.get("ancestral_allele"),
            "minor_allele": data.get("minor_allele"),
            "maf": data.get("MAF"),
            "var_class": data.get("var_class"),
        }

    finally:
        if should_close:
            await client.aclose()


async def _fetch_vep(rsid: str, client: httpx.AsyncClient) -> dict | None:
    """Fetch Variant Effect Predictor data for gene/consequence info."""
    try:
        resp = await client.get(
            f"{GRCH37_URL}/vep/human/id/{rsid}",
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data[0] if data else None
    except Exception:
        return None
