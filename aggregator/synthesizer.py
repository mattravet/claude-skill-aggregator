"""Synthesize raw tips into actionable implementations."""

import os
from typing import Optional

def synthesize_skill(skill: dict, config: dict) -> Optional[dict]:
    """
    Use Claude to transform a raw tip into actionable content.

    Returns the skill dict with added 'implementation' field containing:
    - summary: Brief description of what this enables
    - instructions: Step-by-step how to use it
    - code: Any code snippets (scripts, config, etc.)
    - claude_instructions: Text to add to CLAUDE.md if applicable
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return None

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        category = skill.get('category', 'unknown')

        prompt = f"""Analyze this Claude Code tip and create an actionable implementation.

**Title:** {skill['title']}
**Category:** {category}
**Source:** {skill['url']}

**Raw Content:**
```
{skill['content']}
```

Based on this tip, create a structured implementation. Return your response in this exact format:

## Summary
[1-2 sentence description of what this tip enables]

## Instructions
[Numbered step-by-step instructions to implement this. Be specific and actionable.]

## Code
[If applicable, provide any scripts, config files, or code snippets needed. Use appropriate code blocks with language tags. If no code is needed, write "N/A"]

## CLAUDE.md Addition
[If this tip suggests instructions or patterns for Claude to follow, write the exact text that should be added to CLAUDE.md. If not applicable, write "N/A"]

Be concise and practical. Extract the actionable essence - don't just summarize, create something the user can actually use."""

        response = client.messages.create(
            model=config.get('synthesizer', {}).get('model', 'claude-sonnet-4-20250514'),
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        implementation = response.content[0].text

        # Parse the response into sections
        sections = parse_implementation(implementation)

        skill['implementation'] = {
            'raw_response': implementation,
            **sections
        }

        return skill

    except Exception as e:
        print(f"Synthesis error: {e}")
        return None


def parse_implementation(text: str) -> dict:
    """Parse the structured implementation response into sections."""
    sections = {
        'summary': '',
        'instructions': '',
        'code': '',
        'claude_instructions': ''
    }

    current_section = None
    current_content = []

    for line in text.split('\n'):
        line_lower = line.lower().strip()

        if line_lower.startswith('## summary'):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'summary'
            current_content = []
        elif line_lower.startswith('## instructions'):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'instructions'
            current_content = []
        elif line_lower.startswith('## code'):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'code'
            current_content = []
        elif line_lower.startswith('## claude.md') or line_lower.startswith('## claude_instructions'):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = 'claude_instructions'
            current_content = []
        elif current_section:
            current_content.append(line)

    # Don't forget the last section
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections


def format_synthesized_skill(skill: dict) -> str:
    """Format a synthesized skill for the steering repo."""
    impl = skill.get('implementation', {})

    lines = [
        f"# {skill['title'][:80]}",
        "",
        f"> Source: [{skill['source']}]({skill['url']})",
        f"> Author: {skill['author']} | Score: {skill['score']}",
        "",
    ]

    if impl.get('summary'):
        lines.extend([
            "## Summary",
            impl['summary'],
            "",
        ])

    if impl.get('instructions'):
        lines.extend([
            "## How to Implement",
            impl['instructions'],
            "",
        ])

    if impl.get('code') and impl['code'].lower() != 'n/a':
        lines.extend([
            "## Code",
            impl['code'],
            "",
        ])

    if impl.get('claude_instructions') and impl['claude_instructions'].lower() != 'n/a':
        lines.extend([
            "## Add to CLAUDE.md",
            "```markdown",
            impl['claude_instructions'],
            "```",
            "",
        ])

    lines.extend([
        "---",
        f"*Original content from {skill['url']}*",
        "",
    ])

    return '\n'.join(lines)
