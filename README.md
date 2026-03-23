# DNA Analysis Framework

Personal DNA analysis toolkit: import raw genotyping data into SQLite, query SNPs, compare subjects, and use AI agents to cross-reference with online genomics databases.

## Quick Start

```bash
# Clone and install
git clone https://github.com/YOUR_USER/dna.git
cd dna
uv venv && uv pip install -e "."

# Set up your config
cp config.yaml.example config.yaml
# Edit config.yaml with your details

# Place your raw DNA file in data/sources/
# (MyHeritage CSV exports supported out of the box)

# Import into SQLite
dna import

# Explore
dna stats
dna snp rs3131972
dna subjects
```

## Multi-Subject Support

Each subject gets their own SQLite database (`data/db/{name}.db`). Switch between subjects like git branches:

```bash
dna switch marco
dna stats            # now shows Marco's data
```

Add subjects by editing `config.yaml`:

```yaml
active_subject: stefano

subjects:
  stefano:
    name: Stefano
    sex: male
    date_of_birth: 1990-01-15
    source_file: dna-stefano.csv
    source_format: MyHeritage
    chip: GSA
    reference: build37
    notes: ""
  marco:
    name: Marco
    # ...
```

## AI Agent Integration

The framework exposes tool functions in `src/dna/tools/agent_tools.py` that any AI agent can call:

```python
from dna.tools.agent_tools import lookup_snp, search, get_stats, who_am_i

who_am_i()                    # active subject's profile
lookup_snp("rs3131972")       # look up a specific SNP
search(chromosome="7")        # search with filters
get_stats()                   # chromosome summary
```

See [AGENTS.md](AGENTS.md) for full details on available tools and how to query the data.

## Project Structure

```
├── config.yaml.example    # Template config (copy to config.yaml)
├── AGENTS.md              # Instructions for AI agents
├── data/
│   ├── sources/           # Raw DNA CSV files (gitignored, except example)
│   └── db/                # SQLite databases (gitignored)
├── src/dna/
│   ├── config.py          # Config management
│   ├── cli.py             # CLI commands
│   ├── db/
│   │   ├── schema.py      # SQLite schema
│   │   ├── importer.py    # CSV → SQLite
│   │   └── query.py       # Query helpers
│   ├── api/               # Online database clients (SNPedia, ClinVar, Ensembl)
│   ├── analysis/          # Analysis modules
│   └── tools/
│       └── agent_tools.py # Functions for AI agents
└── dashboard/             # Streamlit dashboard (future)
```

## Supported Formats

- **MyHeritage** (CSV export)
- 23andMe, AncestryDNA — planned

## Privacy

Your DNA data stays local. Raw files and databases are gitignored by default. The example file (`dna-example.csv`) contains synthetic data only.

## License

MIT
