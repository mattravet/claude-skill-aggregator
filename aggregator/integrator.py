"""Integrate synthesized skills into existing steering files."""

import os
from pathlib import Path
from typing import Optional

STEERING_REPO = Path.home() / "claude-steering"
GLOBAL_CLAUDE_MD = STEERING_REPO / "global" / "CLAUDE.md"


def analyze_and_integrate(skill: dict, config: dict) -> Optional[dict]:
    """
    Analyze a synthesized skill and integrate it into existing CLAUDE.md.

    Returns dict with:
    - integrated_content: The new CLAUDE.md content
    - change_type: 'addition' | 'modification' | 'replacement'
    - summary: Human-readable summary of changes
    - sections_affected: List of section names affected
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return None

    # Read existing CLAUDE.md
    if GLOBAL_CLAUDE_MD.exists():
        existing_content = GLOBAL_CLAUDE_MD.read_text()
    else:
        existing_content = "# Claude Configuration\n\n"

    # Get the synthesized instructions
    impl = skill.get('implementation', {})
    claude_instructions = impl.get('claude_instructions', '')

    if not claude_instructions or claude_instructions.lower() == 'n/a':
        # No CLAUDE.md changes needed - this is just reference material
        return {
            'integrated_content': None,
            'change_type': 'reference_only',
            'summary': 'This skill is reference material only - no CLAUDE.md changes needed.',
            'sections_affected': [],
            'skill_summary': impl.get('summary', skill['title']),
            'instructions': impl.get('instructions', ''),
            'code': impl.get('code', ''),
        }

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        prompt = f"""You are helping integrate a new instruction into an existing CLAUDE.md configuration file.

## Existing CLAUDE.md:
```markdown
{existing_content}
```

## New instruction to integrate:
```markdown
{claude_instructions}
```

## Context about this skill:
- Title: {skill['title']}
- Summary: {impl.get('summary', 'N/A')}
- Source: {skill['url']}

## Your task:
1. Analyze where this instruction best fits in the existing CLAUDE.md
2. Determine if this is:
   - ADDITION: New functionality that doesn't overlap with existing content
   - MODIFICATION: Changes or enhances existing instructions
   - REPLACEMENT: Replaces/supersedes existing instructions
3. Produce the integrated CLAUDE.md with the new instruction merged in appropriately
4. Keep the file well-organized with clear sections

## Response format:
Respond with exactly this structure:

CHANGE_TYPE: [ADDITION|MODIFICATION|REPLACEMENT]

SECTIONS_AFFECTED: [comma-separated list of section names, or "New section: <name>" if adding new]

SUMMARY: [2-3 sentence explanation of what changed and why it was placed there]

INTEGRATED_CONTENT:
```markdown
[The complete new CLAUDE.md content with the instruction integrated]
```"""

        response = client.messages.create(
            model=config.get('integrator', {}).get('model', 'claude-sonnet-4-20250514'),
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text
        return parse_integration_response(result_text, skill, impl)

    except Exception as e:
        print(f"Integration error: {e}")
        return None


def parse_integration_response(text: str, skill: dict, impl: dict) -> dict:
    """Parse the LLM integration response."""
    result = {
        'integrated_content': None,
        'change_type': 'addition',
        'summary': '',
        'sections_affected': [],
        'skill_summary': impl.get('summary', skill['title']),
        'instructions': impl.get('instructions', ''),
        'code': impl.get('code', ''),
    }

    lines = text.split('\n')
    in_content_block = False
    content_lines = []

    for line in lines:
        if in_content_block:
            if line.strip() == '```':
                in_content_block = False
            else:
                content_lines.append(line)
        elif line.startswith('CHANGE_TYPE:'):
            change_type = line.replace('CHANGE_TYPE:', '').strip().lower()
            if change_type in ['addition', 'modification', 'replacement']:
                result['change_type'] = change_type
        elif line.startswith('SECTIONS_AFFECTED:'):
            sections = line.replace('SECTIONS_AFFECTED:', '').strip()
            result['sections_affected'] = [s.strip() for s in sections.split(',')]
        elif line.startswith('SUMMARY:'):
            result['summary'] = line.replace('SUMMARY:', '').strip()
        elif line.startswith('INTEGRATED_CONTENT:'):
            pass  # Next line with ``` starts the block
        elif line.strip() == '```markdown' or line.strip() == '```':
            if not in_content_block and not content_lines:
                in_content_block = True

    if content_lines:
        result['integrated_content'] = '\n'.join(content_lines)

    return result


def format_integration_pr_body(skill: dict, integration: dict) -> str:
    """Format the PR body for an integration."""
    change_emoji = {
        'addition': '➕',
        'modification': '✏️',
        'replacement': '🔄',
        'reference_only': '📚',
    }

    emoji = change_emoji.get(integration['change_type'], '📝')

    body = f"""## {emoji} Skill Integration

**Skill:** {skill['title']}
**Source:** [{skill['source']}]({skill['url']})
**Author:** {skill['author']} | **Score:** {skill['score']}

---

### Change Type: `{integration['change_type'].upper()}`

{integration['summary']}

### Sections Affected
{', '.join(integration['sections_affected']) if integration['sections_affected'] else 'N/A'}

---

### What This Skill Does
{integration.get('skill_summary', 'N/A')}

### Implementation Steps
{integration.get('instructions', 'N/A')}
"""

    if integration.get('code') and integration['code'].lower() != 'n/a':
        body += f"""
### Code/Scripts
```
{integration['code'][:1000]}{'...' if len(integration.get('code', '')) > 1000 else ''}
```
"""

    body += """
---
*Auto-generated by claude-skill-aggregator*
"""
    return body
