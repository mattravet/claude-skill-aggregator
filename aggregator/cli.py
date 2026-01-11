"""CLI for Claude Skill Aggregator."""

import click
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from . import fetcher, scanner, storage

console = Console()
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def load_config() -> dict:
    if CONFIG_PATH.exists(): return yaml.safe_load(CONFIG_PATH.read_text())
    return {}

@click.group()
def cli():
    """Claude Code Skill Aggregator - Curate tips from Reddit & GitHub."""
    pass

@cli.command()
@click.option('--source', '-s', type=click.Choice(['all', 'reddit', 'github']), default='all')
@click.option('--scan/--no-scan', default=True)
def fetch(source, scan):
    """Fetch new skills from configured sources."""
    config = load_config()
    with console.status("[bold blue]Fetching skills..."):
        if source == 'reddit': skills = fetcher.RedditFetcher(config).fetch_all()
        elif source == 'github': skills = fetcher.GitHubFetcher(config).fetch_all()
        else: skills = fetcher.fetch_all_sources(config)
    
    if not skills:
        console.print("[yellow]No new skills found.[/yellow]")
        return
    
    console.print(f"[green]Found {len(skills)} potential skills[/green]")
    
    if scan:
        with console.status("[bold blue]Running safety scan..."):
            results = scanner.scan_batch(skills, config)
        for skill in results['auto_reject']:
            storage.mark_url_seen(skill['url'], skill['id'])
            console.print(f"[red]Auto-rejected:[/red] {skill['title'][:60]}")
            for flag in skill['scan']['flags']: console.print(f"  {flag}")
        to_add = results['auto_approve'] + results['review']
        added = storage.add_pending(to_add, config)
        console.print(f"\n[bold]Results:[/bold]")
        console.print(f"  ✅ Safe: {len(results['auto_approve'])}")
        console.print(f"  ⚠️  Review: {len(results['review'])}")
        console.print(f"  🚫 Rejected: {len(results['auto_reject'])}")
        console.print(f"  📥 Added: {added}")
    else:
        added = storage.add_pending([s.to_dict() for s in skills], config)
        console.print(f"[green]Added {added} skills to pending[/green]")

@cli.command()
@click.option('--category', '-c', default=None)
@click.option('--limit', '-n', default=10)
def pending(category, limit):
    """Show pending skills for review."""
    items = storage.get_pending()
    if category: items = [i for i in items if i.get('category') == category]
    if not items:
        console.print("[yellow]No pending skills.[/yellow]")
        return
    table = Table(title=f"Pending Skills ({len(items)} total)")
    table.add_column("ID", style="dim", width=12)
    table.add_column("Category", width=14)
    table.add_column("Title", width=40)
    table.add_column("Source", width=10)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Risk", width=8)
    for item in items[:limit]:
        risk = item.get('scan', {}).get('risk_level', '?')
        style = {'safe': 'green', 'warning': 'yellow', 'danger': 'red'}.get(risk, 'dim')
        table.add_row(item['id'], item['category'], item['title'][:40], item['source'], str(item['score']), f"[{style}]{risk}[/{style}]")
    console.print(table)
    if len(items) > limit: console.print(f"[dim]... and {len(items) - limit} more[/dim]")

@cli.command()
@click.argument('skill_id')
def show(skill_id):
    """Show full details of a skill."""
    items = storage.get_pending() + storage.get_approved()
    skill = next((s for s in items if s['id'] == skill_id), None)
    if not skill:
        console.print(f"[red]Skill {skill_id} not found.[/red]")
        return
    console.print(Panel(f"[bold]{skill['title']}[/bold]\n\nSource: {skill['source']} | Author: {skill['author']} | Score: {skill['score']}\nCategory: {skill['category']} | URL: {skill['url']}", title=f"Skill: {skill_id}"))
    console.print(Panel(skill['content'], title="Content"))
    if 'scan' in skill:
        scan = skill['scan']
        color = {'safe': 'green', 'warning': 'yellow', 'danger': 'red'}.get(scan['risk_level'], 'white')
        console.print(f"\n[bold]Security Scan:[/bold] [{color}]{scan['risk_level'].upper()}[/{color}]")
        for flag in scan.get('flags', []): console.print(f"  {flag}")
        if scan.get('llm_analysis'): console.print(f"\n[bold]LLM Analysis:[/bold]\n{scan['llm_analysis']}")

@cli.command()
@click.argument('skill_id')
def approve(skill_id):
    """Approve a pending skill."""
    skill = storage.approve_skill(skill_id, load_config())
    if skill: console.print(f"[green]✅ Approved:[/green] {skill['title']}")
    else: console.print(f"[red]Skill {skill_id} not found.[/red]")

@cli.command()
@click.argument('skill_id')
@click.option('--reason', '-r', default='Manual rejection')
def reject(skill_id, reason):
    """Reject a pending skill."""
    skill = storage.reject_skill(skill_id, reason, load_config())
    if skill: console.print(f"[red]🚫 Rejected:[/red] {skill['title']}")
    else: console.print(f"[red]Skill {skill_id} not found.[/red]")

@cli.command()
@click.option('--limit', '-n', default=20)
def library(limit):
    """Show approved skills library."""
    items = storage.get_approved()
    if not items:
        console.print("[yellow]No approved skills yet.[/yellow]")
        return
    table = Table(title=f"Approved Skills ({len(items)} total)")
    table.add_column("ID", style="dim", width=12)
    table.add_column("Category", width=14)
    table.add_column("Title", width=50)
    table.add_column("Approved", width=12)
    for item in items[:limit]:
        table.add_row(item['id'], item['category'], item['title'][:50], item.get('approved_at', '')[:10])
    console.print(table)

@cli.command()
@click.argument('target_dir')
def export(target_dir):
    """Export approved skills to target directory."""
    count = storage.export_to_target(target_dir, load_config())
    console.print(f"[green]Exported {count} skills to {target_dir}[/green]")

@cli.command()
def stats():
    """Show aggregator statistics."""
    s = storage.get_stats()
    console.print(Panel(f"📥 Pending: {s['pending']}\n✅ Approved: {s['approved']}\n🚫 Rejected: {s['rejected']}\n👁️  Total seen: {s['total_seen']}", title="Stats"))

def main():
    cli()

if __name__ == '__main__':
    main()
