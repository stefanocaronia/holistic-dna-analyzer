"""CLI entry point for Holistic DNA Analyzer (hda)."""

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def main():
    """Holistic DNA Analyzer — read your DNA, answer your questions."""
    pass


@main.command()
@click.argument("name")
def switch(name: str):
    """Switch the active subject."""
    from hda.config import switch_subject

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
    from hda.config import get_active_subject
    from hda.db.importer import SUPPORTED_FORMATS_LABEL, import_subject

    name = name or get_active_subject()
    console.print(f"Importing [bold]{name}[/]...")

    try:
        count = import_subject(name)
        console.print(f"[green]Done.[/] {count:,} SNPs imported into data/db/{name}.db")
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        console.print("[yellow]Tip:[/] check `config.yaml`, `source_file`, and that the raw export is inside `data/sources/`.")
        raise SystemExit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        console.print(f"[yellow]Tip:[/] supported import formats are: {SUPPORTED_FORMATS_LABEL}.")
        console.print("[yellow]Tip:[/] if needed, set `source_format` explicitly in `config.yaml`.")
        raise SystemExit(1)
    except KeyError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)


@main.command()
def subjects():
    """List all subjects."""
    from hda.config import get_active_subject, list_subjects

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
def whoami():
    """Show the active subject profile."""
    from hda.config import get_active_subject, get_subject_profile

    subject = get_active_subject()
    profile = get_subject_profile(subject)

    table = Table(title="Active Subject")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Subject key", subject)
    for key, value in profile.items():
        table.add_row(key.replace("_", " ").title(), str(value or "—"))

    console.print(table)


@main.command()
@click.argument("rsid")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def snp(rsid: str, subject: str | None):
    """Look up a single SNP by rsid."""
    from hda.db.query import get_snp

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
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--chromosome", "-c", default=None, help="Chromosome filter (e.g. 1, X, MT)")
@click.option("--start", type=int, default=None, help="Minimum base-pair position")
@click.option("--end", type=int, default=None, help="Maximum base-pair position")
@click.option("--genotype", "-g", default=None, help="Exact genotype filter (e.g. AA, CT)")
@click.option("--rsid-pattern", default=None, help="SQL LIKE pattern for rsid (e.g. rs53%)")
@click.option("--limit", type=int, default=25, show_default=True, help="Maximum number of rows")
def search(
    subject: str | None,
    chromosome: str | None,
    start: int | None,
    end: int | None,
    genotype: str | None,
    rsid_pattern: str | None,
    limit: int,
):
    """Search SNPs with basic filters."""
    from hda.db.query import search_snps

    try:
        results = search_snps(
            chromosome=chromosome,
            position_start=start,
            position_end=end,
            genotype=genotype,
            rsid_pattern=rsid_pattern,
            subject=subject,
            limit=limit,
        )
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    title = f"SNP Search ({len(results)} result{'s' if len(results) != 1 else ''})"
    table = Table(title=title)
    table.add_column("rsid", style="bold")
    table.add_column("Chromosome", justify="right")
    table.add_column("Position", justify="right")
    table.add_column("Genotype", justify="center")

    for row in results:
        table.add_row(row["rsid"], row["chromosome"], str(row["position"]), row["genotype"])

    console.print(table)


@main.command()
@click.option("--subject", "-s", default=None)
def stats(subject: str | None):
    """Show chromosome summary for a subject."""
    from hda.db.query import chromosome_summary, count_snps

    total = count_snps(subject)
    summary = chromosome_summary(subject)

    table = Table(title=f"Chromosome Summary ({total:,} total SNPs)")
    table.add_column("Chromosome", justify="right")
    table.add_column("SNPs", justify="right")

    for row in summary:
        table.add_row(row["chromosome"], f"{row['count']:,}")

    console.print(table)


@main.command("compare-variant")
@click.argument("rsid")
@click.argument("subject_a")
@click.argument("subject_b")
def compare_variant_cmd(rsid: str, subject_a: str, subject_b: str):
    """Compare one SNP between two subjects."""
    from hda.db.query import compare_snp

    try:
        result = compare_snp(rsid, subject_a, subject_b)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    table = Table(title=f"Variant Comparison: {rsid}")
    table.add_column("rsid", style="bold")
    table.add_column(subject_a, justify="center")
    table.add_column(subject_b, justify="center")
    table.add_column("Match", justify="center")
    table.add_row(
        result["rsid"],
        str(result.get(subject_a) or "—"),
        str(result.get(subject_b) or "—"),
        "yes" if result.get("match") else "no",
    )
    console.print(table)


@main.command("compare")
@click.argument("subject_a")
@click.argument("subject_b")
@click.option("--all", "show_all", is_flag=True, help="Include matching SNPs too")
@click.option("--chromosome", "-c", default=None, help="Optional chromosome filter")
@click.option("--limit", type=int, default=25, show_default=True, help="Maximum number of rows")
def compare_cmd(subject_a: str, subject_b: str, show_all: bool, chromosome: str | None, limit: int):
    """Compare SNPs between two subjects."""
    from hda.db.query import compare_subjects

    try:
        results = compare_subjects(
            subject_a=subject_a,
            subject_b=subject_b,
            only_different=not show_all,
            chromosome=chromosome,
            limit=limit,
        )
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    title = f"Compare {subject_a} vs {subject_b} ({len(results)} result{'s' if len(results) != 1 else ''})"
    table = Table(title=title)
    table.add_column("rsid", style="bold")
    table.add_column("Chromosome", justify="right")
    table.add_column("Position", justify="right")
    table.add_column(subject_a, justify="center")
    table.add_column(subject_b, justify="center")

    for row in results:
        table.add_row(
            row["rsid"],
            row["chromosome"],
            str(row["position"]),
            row["genotype_a"],
            row["genotype_b"],
        )

    console.print(table)


@main.command("compare-panel")
@click.argument("panel_id")
@click.argument("subject_a")
@click.argument("subject_b")
def compare_panel_cmd(panel_id: str, subject_a: str, subject_b: str):
    """Compare one analysis panel between two subjects."""
    from hda.tools import compare_panel

    try:
        result = compare_panel(panel_id, subject_a, subject_b)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    if result.get("requires_disclaimer"):
        console.print(
            f"[yellow]Note:[/] panel review status is '{result['review_status']}'. "
            "Treat comparison output as exploratory unless independently reviewed."
        )

    summary = result["summary"]
    console.print(
        f"[bold]{result['panel_name']}[/] — {subject_a} vs {subject_b} "
        f"(same effect: {summary['same_effect_count']}, "
        f"different effect: {summary['different_effect_count']}, "
        f"missing: {summary['missing_count']})"
    )

    table = Table(title="Panel Comparison")
    table.add_column("Gene", style="bold")
    table.add_column("rsid")
    table.add_column("Trait")
    table.add_column(subject_a, justify="center")
    table.add_column(subject_b, justify="center")
    table.add_column("Comparison")

    for row in result["results"]:
        table.add_row(
            row["gene"],
            row["rsid"],
            row["trait"],
            f"{row.get('subject_a_genotype') or '—'} / {row.get('subject_a_effect') or '—'}",
            f"{row.get('subject_b_genotype') or '—'} / {row.get('subject_b_effect') or '—'}",
            row["comparison"],
        )

    console.print(table)

    if result.get("composite_results"):
        composite_table = Table(title="Composite Panel Comparison")
        composite_table.add_column("Gene", style="bold")
        composite_table.add_column("Components")
        composite_table.add_column("Trait")
        composite_table.add_column(subject_a, justify="center")
        composite_table.add_column(subject_b, justify="center")
        composite_table.add_column("Comparison")

        for row in result["composite_results"]:
            composite_table.add_row(
                row["gene"],
                ", ".join(row.get("components", [])),
                row["trait"],
                f"{row.get('subject_a_genotype') or '—'} / {row.get('subject_a_effect') or '—'}",
                f"{row.get('subject_b_genotype') or '—'} / {row.get('subject_b_effect') or '—'}",
                row["comparison"],
            )

        console.print(composite_table)


@main.command()
@click.argument("subject_a")
@click.argument("subject_b")
def relatedness(subject_a: str, subject_b: str):
    """Estimate rough genetic relatedness between two subjects."""
    from hda.tools import estimate_relatedness

    try:
        result = estimate_relatedness(subject_a, subject_b)
    except (FileNotFoundError, KeyError) as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    table = Table(title=f"Relatedness: {subject_a} vs {subject_b}")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Shared SNPs", f"{result['shared_snps']:,}")
    table.add_row("Comparable SNPs", f"{result['comparable_snps']:,}")
    table.add_row("Exact match rate", f"{result['exact_match_rate']:.2%}")
    table.add_row("IBS0 rate", f"{result.get('ibs0_rate', 0.0):.2%}")
    table.add_row("IBS1 rate", f"{result.get('ibs1_rate', 0.0):.2%}")
    table.add_row("IBS2 rate", f"{result.get('ibs2_rate', 0.0):.2%}")
    table.add_row("Heuristic relationship", result["heuristic_relationship"])
    table.add_row("Warning", result["interpretation_warning"])
    console.print(table)


@main.command()
@click.argument("rsid")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
@click.option("--source", multiple=True, help="Sources to query (snpedia, clinvar, ensembl)")
@click.option("--refresh", is_flag=True, help="Bypass cache and re-fetch")
def annotate(rsid: str, subject: str | None, source: tuple, refresh: bool):
    """Annotate a SNP with info from online databases."""
    import asyncio
    from hda.api.annotator import annotate_snp

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
    from hda.analysis.panels import list_panels

    all_panels = list_panels()
    table = Table(title="Available Panels")
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Review")
    table.add_column("Variants", justify="right")
    table.add_column("Description")

    for p in all_panels:
        table.add_row(
            p["id"],
            p["name"],
            p["category"],
            p.get("review_status", "unknown"),
            str(p["variant_count"]),
            p["description"],
        )

    console.print(table)


@main.command()
@click.argument("panel_id")
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def analyze(panel_id: str, subject: str | None):
    """Run a panel analysis against a subject's genome."""
    from hda.analysis.panels import analyze_panel

    try:
        result = analyze_panel(panel_id, subject)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        raise SystemExit(1)

    review_status = result.get("review_status", "unknown")
    title = (
        f"{result['panel_name']} [{review_status}] — "
        f"{result['subject']} ({result['found_in_genome']}/{result['total_variants']} found)"
    )
    table = Table(title=title)
    table.add_column("Gene", style="bold")
    table.add_column("rsid")
    table.add_column("Trait")
    table.add_column("Genotype", justify="center")
    table.add_column("Effect")
    table.add_column("Description")

    if review_status != "verified":
        console.print(
            f"[yellow]Note:[/] panel review status is '{review_status}'. "
            "Treat interpretations as exploratory unless independently reviewed."
        )

    for r in result["results"]:
        if not r["found"]:
            table.add_row(r["gene"], r["rsid"], r["trait"], "[dim]—[/]", "[dim]not in chip[/]", "")
        else:
            effect = r["effect"] or ""
            style = ""
            if effect in ("normal", "lower_risk", "no_e4", "no_e2", "typical", "protective"):
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

    composite_results = result.get("composite_results", [])
    if composite_results:
        composite_table = Table(title=f"{result['panel_name']} — Composite Interpretations")
        composite_table.add_column("Gene", style="bold")
        composite_table.add_column("Components")
        composite_table.add_column("Trait")
        composite_table.add_column("Genotype", justify="center")
        composite_table.add_column("Effect")
        composite_table.add_column("Description")

        for r in composite_results:
            components = ", ".join(r.get("components", []))
            if not r["found"]:
                composite_table.add_row(r["gene"], components, r["trait"], "[dim]—[/]", "[dim]not available[/]", r["description"] or "")
            else:
                effect = r["effect"] or ""
                style = ""
                if effect in ("normal", "lower_risk", "no_e4", "no_e2", "typical", "protective"):
                    style = "green"
                elif "reduced" in effect or "risk" in effect or "altered" in effect:
                    style = "yellow"
                elif "significantly" in effect or "higher" in effect or "poor" in effect or "at_risk" in effect:
                    style = "red"

                composite_table.add_row(
                    r["gene"],
                    components,
                    r["trait"],
                    f"[bold]{r.get('label') or r['genotype']}[/]",
                    f"[{style}]{effect}[/]" if style else effect,
                    r["description"] or "",
                )

        console.print(composite_table)


@main.command()
@click.option("--subject", "-s", default=None, help="Subject key (default: active)")
def report(subject: str | None):
    """Show notable findings across all panels."""
    from hda.analysis.panels import get_risk_summary

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
