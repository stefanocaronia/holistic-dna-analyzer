# DNA Analysis Framework — Agent Instructions

This project contains personal genomic data (SNP genotyping) and tools to query, analyze, and compare it.

## Project Layout

```
dna/
├── config.yaml              # Subject profiles + active subject
├── data/
│   ├── sources/             # Raw DNA files (CSV exports from MyHeritage, 23andMe, etc.)
│   └── db/                  # SQLite databases, one per subject ({name}.db)
├── src/dna/
│   ├── config.py            # Config loader, subject switching
│   ├── cli.py               # CLI commands (dna switch, dna import, dna snp, etc.)
│   ├── db/
│   │   ├── schema.py        # SQLite schema and connection helpers
│   │   ├── importer.py      # CSV → SQLite import (supports MyHeritage format)
│   │   └── query.py         # Query helpers (get_snp, search, compare, stats)
│   ├── api/                 # Clients for online databases (SNPedia, ClinVar, Ensembl)
│   ├── analysis/            # Analysis functions (traits, health risks, ancestry)
│   └── tools/
│       └── agent_tools.py   # Functions designed to be called by AI agents
└── dashboard/               # Streamlit dashboard (future)
```

## Active Subject

`config.yaml` has an `active_subject` field. All queries default to this subject.
The subject's profile (name, sex, date_of_birth, etc.) is also in config.yaml.
Each subject has a separate SQLite database at `data/db/{subject_key}.db`.

## Available Tool Functions

Import and call from `dna.tools.agent_tools`:

| Function | Description |
|---|---|
| `who_am_i()` | Get active subject's profile |
| `list_all_subjects()` | List all subjects with profiles |
| `lookup_snp(rsid, subject?)` | Look up a SNP by rsid (e.g. "rs53576") |
| `search(chromosome?, position_start?, position_end?, genotype?, rsid_pattern?, subject?, limit?)` | Search SNPs with filters |
| `get_stats(subject?)` | Total SNPs + per-chromosome breakdown |
| `compare_variant(rsid, subject_a, subject_b)` | Compare one SNP between two subjects |
| `compare(subject_a, subject_b, only_different?, chromosome?, limit?)` | Bulk compare SNPs between subjects |
| `annotate(rsid, subject?, sources?, force_refresh?)` | Fetch annotations from online DBs (SNPedia, ClinVar, Ensembl). Cached locally |
| `annotate_my_snp(rsid, sources?)` | Look up genotype + annotate in one call — the go-to tool for "what does this SNP mean for me?" |
| `available_panels()` | List all analysis panels (pharmacogenomics, cardiovascular, etc.) |
| `run_panel(panel_id, subject?)` | Run a curated panel — returns per-variant genotype, effect, interpretation |
| `run_all_panels(subject?)` | Run all panels at once |
| `notable_findings(subject?)` | Get only non-normal findings across all panels — the quick health overview |

## CLI Commands

```bash
dna subjects          # List all subjects
dna switch <name>     # Switch active subject
dna import [name]     # Import source CSV into SQLite
dna snp <rsid>        # Look up a SNP
dna stats             # Chromosome summary
dna annotate <rsid>   # Fetch online annotations (SNPedia, ClinVar, Ensembl)
dna panels            # List available analysis panels
dna analyze <panel>   # Run a panel (e.g. pharmacogenomics, cardiovascular)
dna report            # Notable findings across all panels
```

## Data Format

Each SQLite database contains a `snps` table:
- `rsid` (TEXT) — SNP identifier (e.g. "rs53576")
- `chromosome` (TEXT) — "1"-"22", "X", "Y", "MT"
- `position` (INTEGER) — base pair position (GRCh37/hg19)
- `genotype` (TEXT) — two alleles (e.g. "AA", "CT", "GG")

## How to Query

```python
from dna.tools.agent_tools import lookup_snp, search, get_stats, annotate_my_snp

# Look up the "empathy gene"
result = lookup_snp("rs53576")

# Find all SNPs on chromosome 7 between positions 1M-2M
results = search(chromosome="7", position_start=1_000_000, position_end=2_000_000)

# Get overview
stats = get_stats()

# What does this SNP mean for the active subject? (genotype + online annotation)
info = annotate_my_snp("rs1801133")
# Returns: genotype, gene (MTHFR), clinical significance, conditions, summary
```

## Online Annotation

Annotations are fetched from three sources and cached locally in the subject's SQLite DB:
- **SNPedia** — community-curated wiki with genotype-specific interpretations
- **ClinVar** (NCBI) — clinical significance and associated conditions
- **Ensembl** — variant consequences, gene context, population frequencies

Results are cached in the `annotations` table so each SNP is fetched only once.
Use `force_refresh=True` to bypass cache.

## Important Notes

- All positions use **GRCh37/hg19** reference genome (build37)
- Genotypes are on the **forward (+) strand**
- This data is for **research and personal exploration**, not medical diagnosis
- When analyzing health-related variants, always note that professional genetic counseling is recommended
