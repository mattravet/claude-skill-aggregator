# Claude Skill Aggregator - User Guide

A tool that pulls Claude Code tips from Reddit and GitHub, lets you review them for safety, synthesizes them into actionable instructions, and integrates them directly into your CLAUDE.md configuration.

## What This Does

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   fetch     │────▶│   approve   │────▶│  integrate  │────▶│ merge + sync│
│ (Reddit/GH) │     │  (review)   │     │ (PR to main)│     │   (live)    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

1. **Fetches** tips from Reddit (r/ClaudeAI, r/anthropic, etc.) and GitHub
2. **Scans** for dangerous patterns (shell injection, prompt injection)
3. **Queues** safe content for your review
4. **Synthesizes** raw tips into actionable instructions using Claude
5. **Integrates** directly into your CLAUDE.md via PR
6. **Syncs** changes to where Claude actually reads them

## Installation

The tool is installed at:
- **Aggregator:** `~/claude-skill-aggregator/`
- **Steering repo:** `~/claude-steering/` (GitHub: mattravet/claude-steering)
- **Active config:** `~/.claude/CLAUDE.md` (symlinked to steering repo)

To use the CLI:
```bash
cd ~/claude-skill-aggregator
source .venv/bin/activate
```

## Daily Workflow

### Step 1: Fetch New Tips

```bash
skill-agg fetch
```

Pulls from Reddit and GitHub, scans for safety, adds safe content to pending queue.

### Step 2: Review Pending Tips

```bash
skill-agg pending              # See the queue
skill-agg show <id>            # Inspect a specific tip
```

### Step 3: Approve or Reject

```bash
skill-agg approve <id>         # Add to library
skill-agg reject <id> -r "reason"  # Reject with reason
```

### Step 4: Integrate into CLAUDE.md

This is the key step. It:
1. Synthesizes the raw tip into actionable instructions
2. Analyzes your existing CLAUDE.md
3. Determines if it's adding new content or modifying existing
4. Creates a PR with the integrated changes

```bash
skill-agg integrate <id>
```

Example output:
```
Integrating: I feel like I've just had a breakthrough...
✓ Synthesized actionable content
✓ Analysis complete: ➕ ADDITION
  Sections: New section: TODO Management
✓ PR created!

Review PR: https://github.com/mattravet/claude-steering/pull/4
```

### Step 5: Review and Merge PR

Go to the PR link and review what's being added to your CLAUDE.md:
- **ADDITION**: New section being added
- **MODIFICATION**: Existing section being updated
- **REPLACEMENT**: Existing content being replaced

Merge when satisfied.

### Step 6: Sync to Claude

```bash
skill-agg sync
```

This pulls the merged changes and updates the symlink. Your new instructions are now live.

## Commands Reference

| Command | Description |
|---------|-------------|
| `skill-agg fetch` | Pull tips from Reddit/GitHub |
| `skill-agg pending` | Show review queue |
| `skill-agg show <id>` | View tip details |
| `skill-agg approve <id>` | Approve a tip |
| `skill-agg reject <id> -r "reason"` | Reject a tip |
| `skill-agg integrate <id>` | Synthesize + integrate + create PR |
| `skill-agg sync` | Pull changes and update symlinks |
| `skill-agg library` | Show approved tips |
| `skill-agg stats` | Show counts |
| `skill-agg synthesize <id>` | Preview synthesis without PR |

### Legacy Commands

| Command | Description |
|---------|-------------|
| `skill-agg promote <id>` | Add to skills/*.md (not CLAUDE.md) |
| `skill-agg promote <id> --raw` | Promote without synthesis |

## File Locations

| Path | What It Is |
|------|------------|
| `~/claude-skill-aggregator/` | The tool |
| `~/claude-skill-aggregator/.env` | API keys |
| `~/claude-skill-aggregator/config.yaml` | Configuration |
| `~/claude-skill-aggregator/data/pending.json` | Review queue |
| `~/claude-skill-aggregator/data/approved/` | Approved tips |
| `~/claude-steering/` | Your Claude config (git repo) |
| `~/claude-steering/global/CLAUDE.md` | Main config file |
| `~/.claude/CLAUDE.md` | Symlink (what Claude reads) |

## Configuration

Edit `~/claude-skill-aggregator/config.yaml`:

```yaml
reddit:
  subreddits:
    - ClaudeAI
    - anthropic
    - cursor
  min_score: 20          # Minimum upvotes
  lookback_days: 7       # How far back to search

github:
  queries:
    - "filename:CLAUDE.md"
  min_stars: 10
  trusted_authors:
    - anthropics

scanner:
  use_llm: true          # Use Claude for safety scanning
```

## API Keys

Edit `~/claude-skill-aggregator/.env`:

```bash
# Required for synthesis and integration
ANTHROPIC_API_KEY=sk-ant-...

# Optional: higher rate limits
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
GITHUB_TOKEN=...
```

## Project-Specific Configs

1. Add to `config.yaml`:
```yaml
sync:
  projects:
    my-project: ~/code/my-project
```

2. Create the config:
```bash
mkdir -p ~/claude-steering/projects/my-project
nano ~/claude-steering/projects/my-project/CLAUDE.md
```

3. Sync:
```bash
skill-agg sync
```

## Safety

- All content is pattern-scanned for dangerous code
- LLM analysis catches subtle prompt injection
- Human approval required at every step
- PRs let you review exact changes before they go live
- Git history enables rollback of any change

## Quick Reference

```bash
# Activate
cd ~/claude-skill-aggregator && source .venv/bin/activate

# Full workflow
skill-agg fetch              # Get new tips
skill-agg pending            # Review queue
skill-agg show <id>          # Inspect
skill-agg approve <id>       # Approve
skill-agg integrate <id>     # Create PR to CLAUDE.md
# Review + merge PR on GitHub
skill-agg sync               # Activate changes
```
