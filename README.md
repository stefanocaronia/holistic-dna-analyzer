# HDA — Holistic DNA Analyzer

A Python/agent framework that can read your DNA data and answer your questions about it.

You bring your raw genotyping file (MyHeritage, 23andMe, AncestryDNA, etc.), the framework imports it, and then any AI agent (Claude, GPT, local LLMs) can have a fluent, informed conversation about your genome — not as a lookup tool, but as an integrative analyst that cross-references multiple biological systems and gives you a coherent picture.

## What It Does

- Imports raw DNA data into a personal SQLite database
- Runs **13 curated analysis panels**: pharmacogenomics, cardiovascular, nutrition, mental health, ADHD/neurodivergence, cognitive performance, addiction, inflammation, sleep, traits, and more (78+ well-studied variants)
- Annotates your SNPs from **SNPedia, ClinVar, and Ensembl** (free, no API keys needed)
- Maintains a **persistent context** per person — the agent remembers what it found in previous sessions
- Supports **multiple subjects** — each person gets their own database, like git branches
- Includes a **Streamlit dashboard** for visual exploration

HDA provides the local data layer, navigation tools, curated panels, and agent-facing functions. When you use an LLM on top of HDA, the model is still generating an interpretation. That interpretation can be useful, but it can also overstate evidence, miss context, or hallucinate. Use it for exploration, not diagnosis.

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

### Activate `hda` in this folder

From the project root, activate the local virtualenv so the `hda` command is available in the current shell.

PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

If `.venv` does not exist yet:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

After activation, you can run:
```powershell
hda subjects
```

Without activating the shell, you can still call the local command directly:
```powershell
.\.venv\Scripts\hda.exe subjects
```

### First-time project setup

```bash
python -m pip install -e .

# Configure your profile
cp config.yaml.example config.yaml
# Edit config.yaml with your name, sex, date of birth

# Place your raw DNA file in data/sources/
# Supported examples:
#   dna-john.csv          -> MyHeritage
#   genome_john.txt       -> AncestryDNA / 23andMe
#   genome_john.zip       -> 23andMe / AncestryDNA zipped download
# Import it
hda import
```

## CLI

Besides talking to the agent, you can use the CLI directly:

```bash
hda subjects          # List all subjects
hda switch <name>     # Switch active subject (like git switch)
hda import [name]     # Import DNA source file into SQLite
hda snp <rsid>        # Look up a single SNP
hda stats             # Chromosome summary
hda annotate <rsid>   # Fetch online annotations (SNPedia, ClinVar, Ensembl)
hda panels            # List analysis panels
hda analyze <panel>   # Run a panel (e.g. pharmacogenomics, cardiovascular)
hda report            # All notable findings across panels
```

## Testing

Run the current automated checks from the project root:

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
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
