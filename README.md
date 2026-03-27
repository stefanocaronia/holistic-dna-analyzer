# HDA — Holistic DNA Analyzer

A Python/agent framework that can read your DNA data and answer your questions about it.

You bring your raw genotyping file (MyHeritage, 23andMe, AncestryDNA, etc.), the framework imports it, and then any AI agent (Claude Code, Codex, Gemini CLI, local LLMs, or similar tools) can have a fluent, informed conversation about your genome — not as a lookup tool, but as an integrative analyst that cross-references multiple biological systems and gives you a coherent picture.

HDA provides the local data layer, navigation tools, curated panels, and agent-facing functions. When you use an LLM on top of HDA, the model is still generating an interpretation. That interpretation can be useful, but it can also overstate evidence, miss context, or hallucinate. Use it for exploration, not diagnosis.

This project is also developed with the help of LLM-assisted workflows. Code,
documentation, and panel content are reviewed and curated in-repo through
multiple iterations, including Codex 5.4. Without that help this project would
have taken much longer. I still hope it is useful, and if you notice any major
problems feel free to open an issue.

LLM-generated interpretations should still be treated as exploratory outputs,
not authoritative conclusions.

## Index

- [What It Does](#what-it-does)
- [Talking to the Agent](#talking-to-the-agent)
- [Setup](#setup)
- [Multi-Subject](#multi-subject)
- [Dashboard](#dashboard)
- [Persistent Context And Clinical Documents](#persistent-context-and-clinical-documents)
- [CLI](#cli)
- [Python API](#python-api)
- [Interpretation Safety](#interpretation-safety)
- [Privacy](#privacy)
- [Supported Formats](#supported-formats)
- [Import Troubleshooting](#import-troubleshooting)
- [Testing](#testing)
- [License](#license)

## What It Does

- Imports raw DNA data into a personal SQLite database
- Runs a small **verified core set** plus additional **exploratory panels** kept in the repository with explicit warnings
- Annotates your SNPs from **SNPedia, ClinVar, and Ensembl** (free, no API keys needed)
- Maintains a **persistent context** per person — the agent remembers what it found in previous sessions
- Supports **multiple subjects** — each person gets their own database and context
- Includes a **Streamlit dashboard** for visual exploration
- Stores non-genetic clinical context such as medications, labs, family history, and follow-ups
- Exports a doctor-facing PDF summary

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

This is the primary way to use the framework. Open a conversation with any AI agent/CLI that has access to this project. The agent reads [AGENTS.md](AGENTS.md) and knows how to use the tools, panels, context, and subject switching rules.

**First time:**

```text
You: Hi, I'm Stefano
Agent: [switches to your profile, loads your context]
       Hey Stefano! I've loaded your profile.
       What would you like to talk about?

You: How's my heart doing?
Agent: [runs cardiovascular, inflammation, nutrition panels; cross-references findings;
       checks your age and profile]
       Your genetic cardiovascular risk is moderate, and it comes from two directions
       that reinforce each other...
```

The important point is that the agent does not just look up SNPs. A question about mood may trigger checks on serotonin, dopamine, cortisol, inflammation, folate metabolism, sleep, previous context, and even imported clinical documents if they exist.

**What you can ask:**
- "Am I lactose intolerant?"
- "How do I metabolize caffeine?"
- "Do I have a predisposition to depression?"
- "What are the most important things to know for my health after 50?"
- "Compare my dopamine profile with Marco's"
- "What should I add to my diet?"
- "Am I prone to nicotine addiction?"

The agent saves findings in `data/context/<name>/` so that the next session starts from memory instead of from zero.

## Setup

```bash
git clone https://github.com/YOUR_USER/holistic-dna-analyzer.git
cd holistic-dna-analyzer
```

### Environment Setup

From the project root, create and install the local virtual environment.

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

If you want PDF export and dashboard support in the same environment:

```bash
python -m pip install -e ".[export,dashboard]"
```

If `.venv` already exists, you only need to activate it:

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

After activation, `hda` should work in the current shell:

```bash
hda subjects
```

Without activating the shell, call the local command directly:

Windows PowerShell:

```powershell
.\.venv\Scripts\hda.exe subjects
```

macOS / Linux:

```bash
.venv/bin/hda subjects
```

### First Subject Setup And Import

Create your local config:

Windows PowerShell:

```powershell
Copy-Item config.yaml.example config.yaml
```

macOS / Linux:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` with your name, sex, date of birth, source file, and source format.

Place your raw DNA file in `data/sources/`.

Supported examples:
- `dna-john.csv` -> MyHeritage
- `genome_john.txt` -> AncestryDNA / 23andMe
- `genome_john.zip` -> 23andMe / AncestryDNA zipped download

`data/sources/`, `data/db/`, `data/context/`, generated outputs under `output/`, and temporary files under `tmp/` are gitignored by default because they may contain personal data.

Then import it:

```bash
hda import
```

## Multi-Subject

Each person gets:
- their own SQLite database
- their own context folder
- their own imported clinical documents
- their own findings, actions, and reports

Switch subjects like branches:

```bash
hda switch marco
```

From that point on, queries, panel runs, reports, and context operations target Marco until you switch again.

Example `config.yaml`:

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
    source_format: 23andMe
```

Direct comparisons are built in:

```bash
hda compare stefano marco
hda compare-panel cardiovascular stefano marco
hda relatedness stefano marco
```

## Dashboard

Run this from the repository root:

```bash
hda dashboard
```

You can also forward raw Streamlit flags, for example:

```bash
hda dashboard -- --server.port 8502
```

Main pages:
- Profile & Overview
- Panel Reports
- Notable Findings
- SNP Explorer
- Compare

The dashboard respects configured subjects and the active subject state, so it fits naturally into the multi-subject workflow.

## Persistent Context And Clinical Documents

Each subject has a persistent context folder under `data/context/<name>/`.

This is where HDA stores:
- `profile_summary.md`
- `findings.md`
- `health_actions.md`
- `session_notes.md`
- `clinical_context.md`

These files remain readable Markdown, but use light structure:
- YAML frontmatter
- predictable headings
- stable block IDs where needed

That keeps them readable for the user and reliable for tooling.

`clinical_context.md` is where non-genetic information lives:
- medications and supplements
- diagnoses or symptoms
- family history
- pending evaluations
- recent labs and imaging

It should stay concise. It is an index and summary layer, not a dump of full referti.

### Importing Clinical Documents

Drop files into:

```text
data/context/<subject>/documents_inbox/
```

Then import them:

```bash
hda context docs inbox
hda context docs import
```

By default, import does three things:
1. archives the original file under `data/context/<subject>/documents/`
2. creates an extracted Markdown sidecar next to it
3. updates `clinical_context.md` with an index entry and short summary

Typical examples:
- PDFs of blood tests
- visit summaries
- plain text notes
- Markdown notes
- CSV lab exports

If the inbox path already contains a date like `documents_inbox/2026-03-27/labs/...`, that date wins. Otherwise HDA falls back to the file timestamp unless you override it.

If a file is dropped in the inbox root, HDA applies a light filename heuristic before falling back to `general`. Names like `esami-sangue`, `emocromo`, `cbc`, `eco`, or `holter` are classified more sensibly by default.

The full memory/document contract is described in [docs/CONTEXT_SCHEMA.md](docs/CONTEXT_SCHEMA.md).

## CLI

Besides talking to the agent, you can use the CLI directly.

### Subject and setup

```bash
hda subjects            # List configured subjects
hda whoami              # Show the active subject profile
hda switch <name>       # Switch the active subject
hda import [name]       # Import the raw DNA file for the active or given subject
```

### Analysis and lookup

```bash
hda panels                                    # List available analysis panels
hda panel-audit                               # Audit panel metadata and review status
hda analyze cardiovascular                    # Run one panel for the active subject
hda report                                    # Show notable findings across all panels
hda snp rs429358                              # Look up one SNP in the active genome
hda annotate rs429358                         # Fetch online annotations for one SNP
hda search --chromosome 19 --start 44900000 --end 45500000  # Search a genomic region
hda stats                                     # Show chromosome and SNP count summary
```

### Comparison

```bash
hda compare stefano marco                          # Compare raw SNP differences between two subjects
hda compare-variant rs429358 stefano marco        # Compare one SNP between two subjects
hda compare-panel cardiovascular stefano marco    # Compare one curated panel between two subjects
hda relatedness stefano marco                     # Get a heuristic relatedness estimate
```

### Context memory

```bash
hda context sections              # List the standard context files for the active subject
hda context show                  # Show the full persistent context
hda context show findings         # Show only the findings registry
hda context show clinical_context # Show non-genetic clinical context
hda context validate              # Check context coherence and evidence boundaries
hda context validate --apply      # Apply safe automatic fixes where possible
hda context audit                 # Show recent context write and migration events
hda context migrate               # Preview deterministic schema migrations
hda context migrate --apply       # Apply deterministic schema migrations with backup
```

### Context editing

```bash
hda context write profile_summary --file summary.md   # Replace an entire maintained document
hda context replace-section profile_summary "Sleep & Recovery" --file sleep.md  # Replace one section
hda context upsert-block findings dopamine_reward_deficiency --file finding.md --meta domains=adhd,addiction  # Create or update one finding block
hda context move-block health_actions sleep_apnea_evaluation "Alta Priorità"    # Move one action between priority sections
hda context archive-block findings dopamine_reward_deficiency                    # Archive one finding block
hda context append-entry session_notes --title "Follow-up" --file note.md       # Append a dated diary entry
hda context replace-entry session_notes "2026-03-27: Follow-up" --file note.md  # Replace an existing diary entry
```

### Clinical documents

```bash
hda context docs inbox                                             # Show files waiting in the subject inbox
hda context docs import                                            # Import all pending inbox documents
hda context docs import --archive-only                             # Import without sidecar/index integration
hda context docs list                                              # List archived clinical documents
hda context docs add C:\reports\cbc.pdf --date 2026-03-27 --category labs  # Import one file directly
```

### Reports and UI

```bash
hda export doctor-report               # Build the short doctor-facing PDF
hda export doctor-report --variant long  # Include exploratory/contextual sections too
hda dashboard                         # Launch the Streamlit dashboard
```

## Python API

The stable agent-facing import surface is `hda.tools`:

```python
from hda.tools import (
    available_panels,
    export_doctor_report,
    read_context,
    run_panel,
    upsert_context_block,
    who_am_i,
)
```

Use the CLI for interactive work and repeatable shell usage. Use the Python API when you want to compose multiple operations programmatically or build automation or agents on top of HDA.

Important notes:
- `export_doctor_report()` writes the short clinical PDF by default
- `variant="long"` includes exploratory themes, interpretation boundaries, and validator notes
- PDF export requires the `export` extra
- `hda context migrate` is dry-run by default and applies only deterministic, versioned migrations
- context writes and migrations maintain a lightweight audit log at `data/context/<subject>/.audit_log.jsonl`

Internal modules under `hda.analysis`, `hda.db`, and `hda.api` are not the stable public surface. Details and examples are in [docs/PYTHON_API.md](docs/PYTHON_API.md).

Related technical docs:
- [Context schema](docs/CONTEXT_SCHEMA.md)
- [Backup and privacy](docs/BACKUP_AND_PRIVACY.md)
- [Panel review workflow](docs/PANEL_REVIEW_WORKFLOW.md)

## Interpretation Safety

- HDA gives you structured access to genotype data, curated panels, context, and external annotations
- Any narrative explanation produced by an LLM is still an LLM output, not a medical conclusion
- Genetic predispositions are probabilistic and incomplete; environment, labs, symptoms, and clinical history matter
- Important health decisions should be reviewed with a physician, genetic counselor, or other qualified professional

## Privacy

Your DNA data stays local. Raw files, databases, context folders, generated reports, and temporary outputs are gitignored. The example file contains synthetic data only.

For backup, migration, and local-family-use assumptions, see [docs/BACKUP_AND_PRIVACY.md](docs/BACKUP_AND_PRIVACY.md).

## Supported Formats

- **MyHeritage** (CSV export)
- **23andMe** (`.txt` or `.zip` raw data export)
- **AncestryDNA** (`.txt` or `.zip` raw data export)

## Import Troubleshooting

- If `hda import` says the source file is missing, check `config.yaml` and place the raw export in `data/sources/`
- If `source_format` does not match the file, fix `config.yaml` or replace the file with the correct provider export
- If the format is not detected, set `source_format` explicitly to `MyHeritage`, `23andMe`, or `AncestryDNA`

## Testing

Run the current automated checks from the project root.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -e ".[export]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m hda.cli panels
```

macOS / Linux:

```bash
source .venv/bin/activate
python -m pip install -e ".[export]"
python -m unittest discover -s tests -v
python -m hda.cli panels
```

## License

MIT
