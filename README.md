# HDA — Holistic DNA Analyzer

A Python/agent framework that can read your DNA data and answer your questions about it.

You bring your raw genotyping file (MyHeritage, 23andMe, AncestryDNA, etc.), the framework imports it, and then any AI agent (Claude, GPT, local LLMs) can have a fluent, informed conversation about your genome — not as a lookup tool, but as an integrative analyst that cross-references multiple biological systems and gives you a coherent picture.

## What It Does

- Imports raw DNA data into a personal SQLite database
- Runs a small **verified core set** plus additional **exploratory panels** kept in the repository with explicit warnings
- Annotates your SNPs from **SNPedia, ClinVar, and Ensembl** (free, no API keys needed)
- Maintains a **persistent context** per person — the agent remembers what it found in previous sessions
- Supports **multiple subjects** — each person gets their own database, like git branches
- Includes a **Streamlit dashboard** for visual exploration

HDA provides the local data layer, navigation tools, curated panels, and agent-facing functions. When you use an LLM on top of HDA, the model is still generating an interpretation. That interpretation can be useful, but it can also overstate evidence, miss context, or hallucinate. Use it for exploration, not diagnosis.

The stable Python API for agents and automation is documented in [docs/PYTHON_API.md](docs/PYTHON_API.md).

This project is also developed with the help of LLM-assisted workflows. Code,
documentation, and panel content are reviewed and curated in-repo, but
LLM-generated interpretations should still be treated as exploratory outputs,
not authoritative conclusions.

Current verified core panels:
- `cardiovascular`
- `pharmacogenomics`
- `inflammation`
- `nutrition_metabolism`
- `nutrition_micronutrients`
- `traits`

Additional panels in the repo may be marked `exploratory` and require extra caution.

Exploratory panels currently kept in the repository are best treated as a secondary library:
- higher-value exploratory: `sleep`, `health_over50`
- medium-value exploratory: `wellness`, `mental_health`
- later / stricter review targets: `adhd_neurodivergence`, `autism_spectrum`, `addiction`, `cognitive`

## Talking to the Agent

This is the primary way to use the framework. Open a conversation with any AI agent that has access to this project (e.g. Claude Code, Cursor, Copilot, or any agent that can read files and run Python). The agent reads [AGENTS.md](AGENTS.md) and knows how to use all the tools.

**First time:**
```
You: Hi, I'm Stefano
Agent: [switches to your profile, loads your context] Hey Stefano! I've loaded your
       profile. What would you like to talk about?

You: How's my heart doing?
Agent: [runs cardiovascular, inflammation, nutrition panels; cross-references findings;
       checks your age and profile]
       Your genetic cardiovascular risk is moderate, and it comes from two directions
       that reinforce each other...
```

**The agent doesn't just look up SNPs — it reasons.** A question about depression triggers checks on serotonin, dopamine, cortisol, inflammation, folate metabolism, and sleep. It iterates through the tools until it has a complete picture, then gives you a conversational answer with practical advice.

**What you can ask:**
- "Am I lactose intolerant?"
- "How do I metabolize caffeine?"
- "Do I have a predisposition to depression?"
- "What are the most important things to know for my health after 50?"
- "Compare my dopamine profile with Marco's"
- "What should I add to my diet?"
- "Am I prone to nicotine addiction?"

The agent saves its findings in `data/context/<name>/` so that next session it already knows your profile and can build on previous analyses.

## Interpretation Safety

- HDA gives you structured access to genotype data, curated panels, and external annotations
- Any narrative explanation produced by an LLM is still an LLM output, not a medical conclusion
- Genetic predispositions are probabilistic and incomplete; environment, labs, symptoms, and clinical history matter
- Important health decisions should be reviewed with a physician, genetic counselor, or other qualified professional

## Setup

```bash
# Clone and enter the project folder
git clone https://github.com/YOUR_USER/holistic-dna-analyzer.git
cd holistic-dna-analyzer
```

### Environment Setup

From the project root, create and install the local virtual environment:

PowerShell:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

If `.venv` already exists, you only need:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Activate `hda` in this folder

After the virtualenv is active, `hda` is available in the current shell:

```powershell
hda subjects
```

Without activating the shell, call the local command directly:

```powershell
.\.venv\Scripts\hda.exe subjects
```

### First-Time Project Setup

Once the environment is installed and `hda` is available:

```powershell
Copy-Item config.yaml.example config.yaml
```

Edit `config.yaml` with your name, sex, date of birth, source file, and source format.

Place your raw DNA file in `data/sources/`.

Supported examples:
- `dna-john.csv` -> MyHeritage
- `genome_john.txt` -> AncestryDNA / 23andMe
- `genome_john.zip` -> 23andMe / AncestryDNA zipped download

Then import it:

```powershell
hda import
```

## CLI

Besides talking to the agent, you can use the CLI directly:

```bash
hda subjects          # List all subjects
hda whoami            # Show the active subject profile
hda switch <name>     # Switch active subject (like git switch)
hda import [name]     # Import DNA source file into SQLite
hda snp <rsid>        # Look up a single SNP
hda search ...        # Search SNPs by chromosome, position, genotype, or rsid pattern
hda compare a b       # Compare SNPs between two subjects
hda compare-variant   # Compare one SNP between two subjects
hda compare-panel     # Compare one analysis panel between two subjects
hda relatedness a b   # Heuristic relatedness summary between two subjects
hda stats             # Chromosome summary
hda annotate <rsid>   # Fetch online annotations (SNPedia, ClinVar, Ensembl)
hda panels            # List analysis panels
hda analyze <panel>   # Run a panel (e.g. pharmacogenomics, cardiovascular)
hda report            # All notable findings across panels
```

## Python API

The stable agent-facing import surface is `hda.tools`:

```python
from hda.tools import available_panels, run_panel, who_am_i
```

Use this layer for agents, scripts, and local automation. It returns plain
Python dictionaries/lists and exposes panel review metadata such as
`review_status`, `requires_disclaimer`, and `interpretation_warning`.

Prefer the CLI for interactive work and repeatable shell usage. Use the Python
API when you want to compose multiple operations programmatically or build
agent-side automation on top of HDA.

Subject-to-subject comparison is available in both layers:
- low-level SNP comparison via `hda compare`, `hda compare-variant`, and `search`
- characteristic-level comparison via `hda compare-panel`
- heuristic family/relatedness estimation via `hda relatedness`

Internal modules under `hda.analysis`, `hda.db`, and `hda.api` are not the
stable public surface. Details and examples are in [docs/PYTHON_API.md](docs/PYTHON_API.md).

## Testing

Run the current automated checks from the project root:

```powershell
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m hda.cli panels
```

## Dashboard

```bash
uv pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

Five pages: Profile & Overview, Panel Reports, Notable Findings, SNP Explorer, and Compare (multi-subject).

## Multi-Subject

Each person gets their own database and context folder. Switch like branches:

```bash
hda switch marco
# Now all queries, panels, and agent conversations target Marco
```

Add subjects in `config.yaml`:

```yaml
active_subject: stefano

subjects:
  stefano:
    name: Stefano
    sex: male
    date_of_birth: 1985-03-15
    source_file: dna-stefano.csv
    source_format: MyHeritage
    chip: GSA
    reference: build37
  marco:
    name: Marco
    sex: male
    date_of_birth: 1990-07-22
    source_file: dna-marco.csv
    # ...
```

## Privacy

Your DNA data stays local. Raw files, databases, and context folders are all gitignored. The example file contains synthetic data only.

## Supported Formats

- **MyHeritage** (CSV export)
- **23andMe** (`.txt` or `.zip` raw data export)
- **AncestryDNA** (`.txt` or `.zip` raw data export)

## Import Troubleshooting

- If `hda import` says the source file is missing, check `config.yaml` and place the raw export in `data/sources/`
- If `source_format` does not match the file, fix `config.yaml` or replace the file with the correct provider export
- If the format is not detected, set `source_format` explicitly to `MyHeritage`, `23andMe`, or `AncestryDNA`

## License

MIT
