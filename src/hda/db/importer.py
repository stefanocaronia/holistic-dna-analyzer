"""Import raw DNA data files into SQLite."""

import csv
import re
import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from io import TextIOWrapper
from pathlib import Path
from typing import Iterator, TextIO

from hda.config import SOURCES_DIR, get_db_path, load_config, save_config
from hda.db.schema import get_connection, init_db

BATCH_SIZE = 50_000
SUPPORTED_FORMATS = ("MyHeritage", "23andMe", "AncestryDNA")
SUPPORTED_FORMATS_LABEL = "MyHeritage (.csv), 23andMe (.txt/.zip), AncestryDNA (.txt/.zip)"


@contextmanager
def open_source_text(filepath: Path) -> Iterator[TextIO]:
    """Open a raw DNA source file as text, including zipped downloads."""
    if filepath.suffix.lower() == ".zip":
        with zipfile.ZipFile(filepath) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            if not members:
                raise ValueError(f"Zip archive is empty: {filepath}")

            preferred = next(
                (m for m in members if Path(m.filename).suffix.lower() in {".txt", ".csv"}),
                members[0],
            )
            with zf.open(preferred, "r") as raw:
                with TextIOWrapper(raw, encoding="utf-8-sig", newline="") as f:
                    yield f
        return

    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        yield f


def read_header_lines(filepath: Path, limit: int = 20) -> list[str]:
    """Read a few leading lines for format detection."""
    lines: list[str] = []
    with open_source_text(filepath) as f:
        for _ in range(limit):
            line = f.readline()
            if not line:
                break
            lines.append(line.rstrip("\n"))
    return lines


def normalize_chromosome(value: str) -> str:
    """Normalize chromosome labels across providers."""
    chrom = value.strip().strip('"').upper()
    if chrom.startswith("CHR"):
        chrom = chrom[3:]

    aliases = {
        "23": "X",
        "24": "Y",
        "25": "MT",
        "26": "MT",
        "M": "MT",
    }
    return aliases.get(chrom, chrom)


def normalize_genotype(*alleles: str) -> str:
    """Normalize genotype strings from one or two-allele provider exports."""
    cleaned = []
    for allele in alleles:
        part = allele.strip().strip('"').upper()
        if part in {"", "0", "-", "--"}:
            cleaned.append("-")
        else:
            cleaned.append(part)

    if not cleaned:
        return "--"
    if len(cleaned) == 1:
        genotype = cleaned[0]
    else:
        genotype = "".join(cleaned)

    return "--" if set(genotype) == {"-"} else genotype


def split_fields(line: str) -> list[str]:
    """Split a provider row using comma or tab delimiters."""
    return [field.strip() for field in re.split(r"[\t,]+", line.strip())]


def format_detected_mismatch(source_file: Path, configured: str, detected: str) -> str:
    """Build an explicit mismatch error for configured vs detected source format."""
    return (
        f"Configured source_format '{configured}' does not match the file '{source_file.name}', "
        f"which looks like '{detected}'. Update config.yaml or use the correct raw data file. "
        f"Supported formats: {SUPPORTED_FORMATS_LABEL}."
    )


def parse_myheritage(filepath: Path) -> list[tuple[str, str, int, str]]:
    """Parse a MyHeritage CSV file, yielding (rsid, chromosome, position, genotype) tuples."""
    rows = []
    with open_source_text(filepath) as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                header = split_fields(stripped)
                if [h.upper() for h in header] != ["RSID", "CHROMOSOME", "POSITION", "RESULT"]:
                    raise ValueError(f"Unexpected MyHeritage header in {filepath}: {stripped}")
                break
        else:
            raise ValueError(f"No data header found in {filepath}")

        reader = csv.DictReader(f, fieldnames=["RSID", "CHROMOSOME", "POSITION", "RESULT"])
        for row in reader:
            rsid = row["RSID"].strip('"')
            chrom = normalize_chromosome(row["CHROMOSOME"])
            pos = int(row["POSITION"].strip('"'))
            genotype = normalize_genotype(row["RESULT"])
            rows.append((rsid, chrom, pos, genotype))
    return rows


def parse_23andme(filepath: Path) -> list[tuple[str, str, int, str]]:
    """Parse a 23andMe raw data export (txt or zip)."""
    rows = []
    with open_source_text(filepath) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            fields = re.split(r"\s+", stripped)
            if len(fields) != 4:
                raise ValueError(f"Unexpected 23andMe row in {filepath}: {stripped}")

            rsid, chrom, pos, genotype = fields
            rows.append((rsid, normalize_chromosome(chrom), int(pos), normalize_genotype(genotype)))
    return rows


def parse_ancestrydna(filepath: Path) -> list[tuple[str, str, int, str]]:
    """Parse an AncestryDNA raw data export (txt or zip)."""
    rows = []
    with open_source_text(filepath) as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                lowered = stripped.lstrip("#").strip().lower()
                if lowered.startswith("rsid"):
                    continue
                continue

            fields = split_fields(stripped)
            if [field.lower() for field in fields] == ["rsid", "chromosome", "position", "allele1", "allele2"]:
                continue
            if len(fields) != 5:
                raise ValueError(f"Unexpected AncestryDNA row in {filepath}: {stripped}")

            rsid, chrom, pos, allele1, allele2 = fields
            rows.append(
                (
                    rsid,
                    normalize_chromosome(chrom),
                    int(pos),
                    normalize_genotype(allele1, allele2),
                )
            )
    return rows


def detect_format(filepath: Path) -> str:
    """Detect the source file format from its header."""
    header_blob = "\n".join(read_header_lines(filepath)).lower()
    normalized = header_blob.replace(" ", "")

    if "myheritage" in header_blob or "rsid,chromosome,position,result" in normalized:
        return "MyHeritage"
    if "ancestrydna" in header_blob or "allele1" in normalized and "allele2" in normalized:
        return "AncestryDNA"
    if "23andme" in normalized or "rsid\tchromosome\tposition\tgenotype" in normalized:
        return "23andMe"
    return "unknown"


PARSERS = {
    "MyHeritage": parse_myheritage,
    "23andMe": parse_23andme,
    "AncestryDNA": parse_ancestrydna,
}


def import_subject(subject_key: str) -> int:
    """Import a subject's source file into their SQLite database. Returns row count."""
    config = load_config()
    subject = config["subjects"][subject_key]
    source_file = SOURCES_DIR / subject["source_file"]

    if not source_file.exists():
        raise FileNotFoundError(
            f"Source file not found: {source_file}. Put the raw DNA export in data/sources/ "
            f"and check the subject's source_file in config.yaml."
        )

    configured_format = subject.get("source_format")
    detected_format = detect_format(source_file)
    fmt = configured_format or detected_format

    if configured_format and detected_format != "unknown" and configured_format != detected_format:
        raise ValueError(format_detected_mismatch(source_file, configured_format, detected_format))

    parser = PARSERS.get(fmt)
    if parser is None:
        if detected_format == "unknown":
            raise ValueError(
                f"Could not detect the format of '{source_file.name}'. Supported formats: "
                f"{SUPPORTED_FORMATS_LABEL}. If the file is valid, set source_format explicitly in config.yaml."
            )
        raise ValueError(
            f"Unsupported format: {fmt}. Supported formats: {SUPPORTED_FORMATS_LABEL}."
        )

    db_path = get_db_path(subject_key)
    init_db(db_path)

    try:
        rows = parser(source_file)
    except ValueError as e:
        if configured_format and detected_format != "unknown" and configured_format != detected_format:
            raise ValueError(format_detected_mismatch(source_file, configured_format, detected_format)) from e
        raise ValueError(
            f"Failed to parse '{source_file.name}' as {fmt}: {e} "
            f"Supported formats: {SUPPORTED_FORMATS_LABEL}."
        ) from e

    conn = get_connection(db_path)
    try:
        # Clear existing data for clean re-import
        conn.execute("DELETE FROM snps")

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            conn.executemany(
                "INSERT INTO snps (rsid, chromosome, position, genotype) VALUES (?, ?, ?, ?)",
                batch,
            )
        conn.commit()
    finally:
        conn.close()

    # Update imported_at in config
    config["subjects"][subject_key]["imported_at"] = datetime.now(timezone.utc).isoformat()
    if not subject.get("source_format"):
        config["subjects"][subject_key]["source_format"] = fmt
    save_config(config)

    return len(rows)
