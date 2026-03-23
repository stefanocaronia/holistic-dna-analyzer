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


if __name__ == "__main__":
    main()
