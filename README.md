# Claude Skill Aggregator

Automatically pull Claude Code tips from Reddit and GitHub, scan them for safety, synthesize them into actionable instructions, and integrate them directly into your CLAUDE.md configuration via PR.

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   fetch     │────▶│   approve   │────▶│  integrate  │────▶│ merge + sync│
│ (Reddit/GH) │     │  (review)   │     │ (PR to main)│     │   (live)    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

1. **Fetch** - Pulls tips from Reddit (r/ClaudeAI, r/anthropic, etc.) and GitHub
2. **Scan** - Pattern matching + LLM analysis for dangerous content
3. **Approve** - Human review of safe content
4. **Synthesize** - Claude transforms raw tips into actionable instructions
5. **Integrate** - Analyzes your existing CLAUDE.md and merges changes via PR
6. **Sync** - Symlinks merged config to where Claude reads it

## Installation

```bash
# Clone and setup
git clone https://github.com/mattravet/claude-skill-aggregator.git
cd claude-skill-aggregator
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Add your API key
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# Initialize steering repo
mkdir -p ~/claude-steering/global
cd ~/claude-steering && git init
echo "# Claude Configuration" > global/CLAUDE.md
git add . && git commit -m "Initial config"
```

## Usage

```bash
# Activate
cd ~/claude-skill-aggregator && source .venv/bin/activate

# Daily workflow
skill-agg fetch              # Pull tips from Reddit/GitHub
skill-agg pending            # Review queue
skill-agg show <id>          # Inspect a tip
skill-agg approve <id>       # Approve for integration
skill-agg integrate <id>     # Synthesize + create PR to CLAUDE.md

# After merging PR on GitHub:
skill-agg sync               # Activate changes
```

## Commands

| Command | Description |
|---------|-------------|
| `fetch` | Pull tips from configured sources |
| `pending` | Show review queue |
| `show <id>` | View tip details |
| `approve <id>` | Approve a tip |
| `reject <id> -r "reason"` | Reject a tip |
| `integrate <id>` | Synthesize + merge into CLAUDE.md + create PR |
| `sync` | Pull changes and update symlinks |
| `library` | Show approved tips |
| `stats` | Show counts |
| `synthesize <id>` | Preview synthesis without PR |

## Configuration

Edit `config.yaml`:

```yaml
reddit:
  subreddits:
    - ClaudeAI
    - anthropic
    - cursor
  min_score: 20
  lookback_days: 7

github:
  queries:
    - "filename:CLAUDE.md"
  min_stars: 10

scanner:
  use_llm: true
```

## Safety

- Pattern-based scanning for shell injection, prompt injection
- LLM analysis for subtle attacks
- Human approval required at every step
- PRs for review before any config changes
- Git history enables rollback

## File Structure

```
~/claude-skill-aggregator/     # This tool
├── aggregator/                # Python modules
├── data/
│   ├── pending.json          # Review queue
│   ├── approved/             # Approved tips
│   └── sources.json          # Seen URLs (dedup)
├── config.yaml               # Configuration
└── .env                      # API keys

~/claude-steering/             # Your config repo
├── global/
│   └── CLAUDE.md             # Main config
└── projects/                  # Project-specific configs

~/.claude/CLAUDE.md            # Symlink (what Claude reads)
```

## License

MIT
