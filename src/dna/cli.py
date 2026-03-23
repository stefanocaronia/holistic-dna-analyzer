"""CLI entry point for the dna framework."""

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def main():
    """Personal DNA analysis framework."""
    pass


@main.command()
@click.argument("name")
def switch(name: str):
    """Switch the active subject."""
    from dna.config import switch_subject

    try:
        switch_subject(name)
        console.print(f"Active subject: [bold green]{name}[/]")
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)


@main.command("import")
@click.argument("name", required=False)
def import_cmd(name: str | None):
    """Import a subject's source file into SQLite. Defaults to active subject."""
    from dna.config import get_active_subject
    from dna.db.importer import import_subject

    name = name or get_active_subject()
    console.print(f"Importing [bold]{name}[/]...")

    try:
        count = import_subject(name)
        console.print(f"[green]Done.[/] {count:,} SNPs imported into data/db/{name}.db")
    except (FileNotFoundError, ValueError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)


@main.command()
def subjects():
    """List all subjects."""
    from dna.config import get_active_subject, list_subjects

    active = get_active_subject()
    subs = list_subjects()

    table = Table(title="Subjects")
    table.add_column("Key", style="bold")
    table.add_column("Name")
    table.add_column("Sex")
    table.add_column("DOB")
    table.add_column("Source")
    table.add_column("Imported")
    table.add_column("Active", justify="center")

    for key, info in subs.items():
        marker = "[green]*[/]" if key == active else ""
        table.add_row(
            key,
            info.get("name", ""),
            info.get("sex", ""),
            str(info.get("date_of_birth", "") or ""),
            info.get("source_file", ""),
            str(info.get("imported_at", "") or "—"),
            marker,
        )

    console.print(table)


@main.command()
@click.argument("rsid")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def snp(rsid: str, subject: str | None):
    """Look up a single SNP by rsid."""
    from dna.db.query import get_snp

    result = get_snp(rsid, subject)
    if result is None:
        console.print(f"[yellow]SNP {rsid} not found.[/]")
        raise SystemExit(1)

    table = Table(title=f"SNP {rsid}")
    for key in result:
        table.add_column(key.capitalize())
    table.add_row(*[str(v) for v in result.values()])
    console.print(table)


@main.command()
@click.option("--subject", "-s", default=None)
def stats(subject: str | None):
    """Show chromosome summary for a subject."""
    from dna.db.query import chromosome_summary, count_snps

    total = count_snps(subject)
    summary = chromosome_summary(subject)

    table = Table(title=f"Chromosome Summary ({total:,} total SNPs)")
    table.add_column("Chromosome", justify="right")
    table.add_column("SNPs", justify="right")

    for row in summary:
        table.add_row(row["chromosome"], f"{row['count']:,}")

    console.print(table)


@main.command()
@click.argument("rsid")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--source", multiple=True, help="Sources to query (snpedia, clinvar, ensembl)")
@click.option("--refresh", is_flag=True, help="Bypass cache and re-fetch")
def annotate(rsid: str, subject: str | None, source: tuple, refresh: bool):
    """Annotate a SNP with info from online databases."""
    import asyncio
    from dna.api.annotator import annotate_snp

    sources = list(source) if source else None

    with console.status(f"Fetching annotations for [bold]{rsid}[/]..."):
        result = asyncio.run(annotate_snp(rsid, subject, sources, refresh))

    if not result.get("sources"):
        console.print(f"[yellow]No annotations found for {rsid}.[/]")
        return

    table = Table(title=f"Annotations for {rsid}")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    for field in ("gene", "clinical_significance", "condition", "summary",
                  "risk_allele", "population_frequency"):
        value = result.get(field)
        if value:
            table.add_row(field.replace("_", " ").title(), str(value))

    table.add_row("Sources", ", ".join(result.get("sources", [])))
    console.print(table)


@main.command()
def panels():
    """List available analysis panels."""
    from dna.analysis.panels import list_panels

    all_panels = list_panels()
    table = Table(title="Available Panels")
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Variants", justify="right")
    table.add_column("Description")

    for p in all_panels:
        table.add_row(p["id"], p["name"], p["category"], str(p["variant_count"]), p["description"])

    console.print(table)


@main.command()
@click.argument("panel_id")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def analyze(panel_id: str, subject: str | None):
    """Run a panel analysis against a subject's genome."""
    from dna.analysis.panels import analyze_panel

    try:
        result = analyze_panel(panel_id, subject)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    table = Table(title=f"{result['panel_name']} — {result['subject']} ({result['found_in_genome']}/{result['total_variants']} found)")
    table.add_column("Gene", style="bold")
    table.add_column("rsid")
    table.add_column("Trait")
    table.add_column("Genotype", justify="center")
    table.add_column("Effect")
    table.add_column("Description")

    for r in result["results"]:
        if not r["found"]:
            table.add_row(r["gene"], r["rsid"], r["trait"], "[dim]—[/]", "[dim]not in chip[/]", "")
        else:
            effect = r["effect"] or ""
            style = ""
            if effect in ("normal", "lower_risk", "no_e4", "no_e2"):
                style = "green"
            elif "reduced" in effect or "risk" in effect or "altered" in effect:
                style = "yellow"
            elif "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
                style = "red"

            table.add_row(
                r["gene"], r["rsid"], r["trait"],
                f"[bold]{r['genotype']}[/]",
                f"[{style}]{effect}[/]" if style else effect,
                r["description"] or "",
            )

    console.print(table)


@main.command()
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def report(subject: str | None):
    """Show notable findings across all panels."""
    from dna.analysis.panels import get_risk_summary

    findings = get_risk_summary(subject)

    if not findings:
        console.print("[green]No notable findings across all panels.[/]")
        return

    table = Table(title=f"Notable Findings ({len(findings)} variants)")
    table.add_column("Panel")
    table.add_column("Gene", style="bold")
    table.add_column("Trait")
    table.add_column("Genotype", justify="center")
    table.add_column("Effect")
    table.add_column("Description")

    for f in findings:
        effect = f["effect"] or ""
        style = "yellow"
        if "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
            style = "red"

        table.add_row(
            f["panel"], f["gene"], f["trait"],
            f"[bold]{f['genotype']}[/]",
            f"[{style}]{effect}[/]",
            f["description"] or "",
        )

    console.print(table)


if __name__ == "__main__":
    main()
