# Backup, Migration, and Privacy

This project is designed for local family use. The main assets to protect are:

- `config.yaml`
- `data/db/`
- `data/context/`
- optionally `data/sources/` if you want to keep the original raw exports
- optionally `output/` if you want to keep generated doctor reports or other exports

## Local Family-Use Assumptions

HDA assumes:

- the repository is used locally, not as a multi-tenant hosted service
- one trusted person or one family machine manages subject switching
- DNA databases and context notes are sensitive and should stay out of public repositories
- relatedness summaries and LLM interpretations are exploratory, not legal, forensic, or clinical outputs

If you move beyond this usage model, the current safeguards are not enough by themselves.

## What To Back Up

Minimum:

- `config.yaml`
- `data/db/`
- `data/context/`

Recommended:

- `data/sources/`
- `output/` if you want generated exports preserved

`data/db/` contains imported SNP and annotation cache data.  
`data/context/` contains the subject memory used by agents across sessions.
`output/` may contain generated doctor-facing reports or other derived artifacts.

## Simple Backup Workflow

From the repository root in PowerShell:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = "..\\hda-backup-$stamp"
New-Item -ItemType Directory -Path $target | Out-Null
Copy-Item config.yaml $target
Copy-Item data\\db $target -Recurse
Copy-Item data\\context $target -Recurse
```

If you also want the original raw files:

```powershell
Copy-Item data\\sources $target -Recurse
```

## Migration To Another Machine

1. Clone the repository on the new machine.
2. Create and activate the local environment.
3. Install the project:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

4. Copy over:
   - `config.yaml`
   - `data/db/`
   - `data/context/`
   - optionally `data/sources/`
   - optionally `output/`
5. Verify the active subject and panel list:

```powershell
hda whoami
hda panels
```

## Recovering From Cache Issues

Online annotations are cached in each subject database. If annotation data looks stale or corrupted:

- rerun annotation with refresh flags where available
- or re-import only the annotation cache by recreating the DB from raw files if needed

For a full rebuild of one subject:

1. keep `config.yaml` and the raw source export
2. remove only the affected `data/db/<subject>.db`
3. rerun:

```powershell
hda import <subject>
```

This rebuilds SNP storage. Annotation cache will repopulate on demand.

## Privacy Notes

- DNA data, context notes, annotation cache, and exported reports should be treated as sensitive personal data.
- Keep `config.yaml`, `data/db/`, `data/context/`, `data/sources/`, and `output/` out of shared or public repos.
- Be cautious when sharing screenshots, logs, or exported comparison output, especially for relatives.
- If you use an external LLM, remember that the model output is only as private as the environment where it runs.

## Relatedness and Comparison Safety

- `hda relatedness` is a heuristic summary based on chip overlap and IBS-style counts.
- It is not a formal kinship estimator.
- Do not use it for legal, forensic, insurance, or medical decision-making.
