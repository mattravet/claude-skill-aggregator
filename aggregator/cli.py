"""CLI for Claude Skill Aggregator."""

import click
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from . import fetcher, scanner, storage, steering, synthesizer, integrator

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

    # Filter out already-seen URLs BEFORE scanning (saves API credits)
    seen_urls = storage.get_seen_urls()
    original_count = len(skills)
    skills = [s for s in skills if s.url not in seen_urls]
    skipped = original_count - len(skills)

    if skipped > 0:
        console.print(f"[dim]Skipped {skipped} already-seen posts[/dim]")

    if not skills:
        console.print("[yellow]No new skills to process.[/yellow]")
        return

    console.print(f"[green]Found {len(skills)} new skills[/green]")

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

@cli.command()
@click.argument('skill_id')
@click.option('--target', '-t', default=None, help='Target file path relative to steering repo')
@click.option('--no-pr', is_flag=True, help='Skip PR creation, just create local branch')
@click.option('--raw', is_flag=True, help='Skip synthesis, use raw content')
def promote(skill_id, target, no_pr, raw):
    """Promote an approved skill to steering repo via PR.

    By default, uses Claude to synthesize actionable implementation from raw content.
    Use --raw to skip synthesis and use original content.
    """
    config = load_config()

    # Find the skill in approved library
    approved = storage.get_approved()
    skill = next((s for s in approved if s['id'] == skill_id or s['id'].startswith(skill_id)), None)

    if not skill:
        console.print(f"[red]Skill {skill_id} not found in approved library.[/red]")
        console.print("[dim]Use 'skill-agg library' to see approved skills.[/dim]")
        return

    console.print(f"[bold]Promoting:[/bold] {skill['title'][:60]}")
    console.print(f"[dim]Category: {skill.get('category', 'unknown')} -> {steering.get_target_file(skill.get('category', 'misc')).name}[/dim]")

    # Synthesize unless --raw flag is set
    if not raw and not skill.get('implementation'):
        import os
        if not os.getenv('ANTHROPIC_API_KEY'):
            console.print("[yellow]No ANTHROPIC_API_KEY set. Using raw content.[/yellow]")
            console.print("[dim]Set the key in ~/.claude-skill-aggregator/.env for synthesis.[/dim]")
        else:
            with console.status("[bold blue]Synthesizing implementation..."):
                synthesized = synthesizer.synthesize_skill(skill, config)
                if synthesized:
                    skill = synthesized
                    console.print("[green]Synthesized actionable implementation[/green]")
                else:
                    console.print("[yellow]Synthesis failed, using raw content[/yellow]")

    with console.status("[bold blue]Creating branch and PR..."):
        result = steering.promote_skill(skill, target=target, create_pr=not no_pr)

    if result['success']:
        console.print(f"[green]Success![/green] {result['message']}")
        if result.get('pr_url'):
            console.print(f"\n[bold]Review PR:[/bold] {result['pr_url']}")
        else:
            console.print(f"\n[dim]Branch: {result['branch']}[/dim]")
            console.print("[dim]To create PR manually: cd ~/claude-steering && gh pr create[/dim]")
    else:
        console.print(f"[red]Failed:[/red] {result['message']}")

@cli.command()
@click.argument('skill_id')
def synthesize(skill_id):
    """Preview synthesized implementation for a skill (without promoting)."""
    import os
    config = load_config()

    if not os.getenv('ANTHROPIC_API_KEY'):
        console.print("[red]ANTHROPIC_API_KEY not set.[/red]")
        console.print("[dim]Add it to ~/claude-skill-aggregator/.env[/dim]")
        return

    # Find in approved or pending
    items = storage.get_approved() + storage.get_pending()
    skill = next((s for s in items if s['id'] == skill_id or s['id'].startswith(skill_id)), None)

    if not skill:
        console.print(f"[red]Skill {skill_id} not found.[/red]")
        return

    console.print(f"[bold]Synthesizing:[/bold] {skill['title'][:60]}")

    with console.status("[bold blue]Analyzing and creating implementation..."):
        result = synthesizer.synthesize_skill(skill, config)

    if not result:
        console.print("[red]Synthesis failed.[/red]")
        return

    impl = result.get('implementation', {})

    console.print(Panel(impl.get('summary', 'N/A'), title="Summary"))

    if impl.get('instructions'):
        console.print(Panel(impl['instructions'], title="How to Implement"))

    if impl.get('code') and impl['code'].lower() != 'n/a':
        console.print(Panel(impl['code'], title="Code"))

    if impl.get('claude_instructions') and impl['claude_instructions'].lower() != 'n/a':
        console.print(Panel(impl['claude_instructions'], title="Add to CLAUDE.md"))

@cli.command()
def sync():
    """Sync steering files to actual locations via symlinks."""
    config = load_config()

    console.print("[bold]Syncing steering files...[/bold]")

    try:
        results = steering.sync_to_locations(config)
        for location, message in results.items():
            console.print(f"  [green]{location}:[/green] {message}")
        console.print("\n[green]Sync complete![/green]")
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")

@cli.command()
def promoted():
    """List skills that have been promoted to steering repo."""
    items = steering.list_promoted()
    if not items:
        console.print("[yellow]No skills promoted yet.[/yellow]")
        console.print("[dim]Use 'skill-agg promote <id>' to promote approved skills.[/dim]")
        return

    table = Table(title="Promoted Skills")
    table.add_column("File", width=30)
    table.add_column("Size", justify="right", width=10)
    for item in items:
        table.add_row(item['file'], f"{item['size']} bytes")
    console.print(table)

@cli.command()
@click.argument('skill_id')
def integrate(skill_id):
    """Synthesize and integrate a skill directly into CLAUDE.md via PR.

    This command:
    1. Synthesizes the skill into actionable content
    2. Analyzes your existing CLAUDE.md
    3. Determines if this adds/modifies/replaces functionality
    4. Creates a PR with the integrated changes
    """
    import os
    config = load_config()

    if not os.getenv('ANTHROPIC_API_KEY'):
        console.print("[red]ANTHROPIC_API_KEY not set.[/red]")
        return

    # Find skill in approved library
    approved = storage.get_approved()
    skill = next((s for s in approved if s['id'] == skill_id or s['id'].startswith(skill_id)), None)

    if not skill:
        console.print(f"[red]Skill {skill_id} not found in approved library.[/red]")
        return

    console.print(f"[bold]Integrating:[/bold] {skill['title'][:60]}")

    # Step 1: Synthesize if needed
    if not skill.get('implementation'):
        with console.status("[bold blue]Step 1/3: Synthesizing implementation..."):
            skill = synthesizer.synthesize_skill(skill, config)
            if not skill:
                console.print("[red]Synthesis failed.[/red]")
                return
        console.print("[green]✓[/green] Synthesized actionable content")
    else:
        console.print("[dim]✓ Already synthesized[/dim]")

    # Step 2: Integrate into CLAUDE.md
    with console.status("[bold blue]Step 2/3: Analyzing and integrating..."):
        integration = integrator.analyze_and_integrate(skill, config)

    if not integration:
        console.print("[red]Integration analysis failed.[/red]")
        return

    change_type = integration['change_type']
    emoji = {'addition': '➕', 'modification': '✏️', 'replacement': '🔄', 'reference_only': '📚'}.get(change_type, '📝')

    console.print(f"[green]✓[/green] Analysis complete: {emoji} {change_type.upper()}")
    console.print(f"[dim]  {integration['summary']}[/dim]")

    if integration['sections_affected']:
        console.print(f"[dim]  Sections: {', '.join(integration['sections_affected'])}[/dim]")

    # Step 3: Create PR
    if integration['integrated_content']:
        with console.status("[bold blue]Step 3/3: Creating PR..."):
            result = steering.create_integration_pr(
                skill=skill,
                integrated_content=integration['integrated_content'],
                pr_body=integrator.format_integration_pr_body(skill, integration),
                change_type=change_type
            )

        if result['success']:
            console.print(f"[green]✓[/green] PR created!")
            if result.get('pr_url'):
                console.print(f"\n[bold]Review PR:[/bold] {result['pr_url']}")
            else:
                console.print(f"[dim]Branch: {result['branch']}[/dim]")
        else:
            console.print(f"[red]Failed:[/red] {result['message']}")
    else:
        console.print("\n[yellow]No CLAUDE.md changes needed.[/yellow]")
        console.print("[dim]This skill is reference material only.[/dim]")

        # Show the reference content
        if integration.get('instructions'):
            console.print(Panel(integration['instructions'], title="Implementation Steps"))
        if integration.get('code') and integration['code'].lower() != 'n/a':
            console.print(Panel(integration['code'], title="Code"))

def main():
    cli()

if __name__ == '__main__':
    main()
