"""Steering file management - promote skills to Claude config via PRs."""

import os
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

STEERING_REPO = Path.home() / "claude-steering"
GLOBAL_DIR = STEERING_REPO / "global"
SKILLS_DIR = GLOBAL_DIR / "skills"
PROJECTS_DIR = STEERING_REPO / "projects"

# Category to file mapping
CATEGORY_FILES = {
    "workflow": "workflows.md",
    "prompt-pattern": "prompts.md",
    "claude-md": "claude-md-examples.md",
    "command": "commands.md",
    "hook": "hooks.md",
}

def ensure_steering_repo():
    """Ensure steering repo exists."""
    if not STEERING_REPO.exists():
        raise RuntimeError(f"Steering repo not found at {STEERING_REPO}. Run setup first.")
    if not (STEERING_REPO / ".git").exists():
        raise RuntimeError(f"{STEERING_REPO} is not a git repository.")

def get_target_file(category: str) -> Path:
    """Get the target skills file for a category."""
    filename = CATEGORY_FILES.get(category, "misc.md")
    return SKILLS_DIR / filename

def format_skill_for_steering(skill: dict, use_synthesis: bool = True) -> str:
    """Format a skill for inclusion in steering files.

    If skill has 'implementation' field (from synthesizer), uses that.
    Otherwise falls back to raw content.
    """
    # If synthesized, use the structured format
    if use_synthesis and skill.get('implementation'):
        from . import synthesizer
        return synthesizer.format_synthesized_skill(skill)

    # Fallback: raw content format
    lines = [
        f"## {skill['title'][:80]}",
        "",
        f"> Source: [{skill['source']}]({skill['url']})",
        f"> Author: {skill['author']} | Score: {skill['score']} | Added: {skill.get('approved_at', '')[:10]}",
        "",
    ]

    # For claude-md category, include the full content as a code block
    if skill.get('category') == 'claude-md':
        lines.extend([
            "```markdown",
            skill['content'],
            "```",
        ])
    else:
        lines.append(skill['content'])

    lines.extend(["", "---", ""])
    return "\n".join(lines)

def run_git(args: list[str], cwd: Path = STEERING_REPO) -> tuple[bool, str]:
    """Run a git command and return (success, output)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def run_gh(args: list[str], cwd: Path = STEERING_REPO) -> tuple[bool, str]:
    """Run a gh CLI command and return (success, output)."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except FileNotFoundError:
        return False, "gh CLI not found. Install with: brew install gh"

def get_current_branch() -> str:
    """Get current git branch."""
    success, output = run_git(["branch", "--show-current"])
    return output.strip() if success else "main"

def promote_skill(skill: dict, target: Optional[str] = None, create_pr: bool = True) -> dict:
    """
    Promote a skill to the steering repo.

    Returns dict with: success, branch, pr_url, message
    """
    ensure_steering_repo()

    # Determine target file
    if target:
        target_path = STEERING_REPO / target
    else:
        target_path = get_target_file(skill.get('category', 'misc'))

    # Ensure target directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Create branch name
    branch_name = f"skill/{skill['id'][:8]}-{datetime.now().strftime('%Y%m%d')}"
    original_branch = get_current_branch()

    result = {
        "success": False,
        "branch": branch_name,
        "pr_url": None,
        "message": ""
    }

    try:
        # Ensure we're on main and up to date
        run_git(["checkout", "main"])
        run_git(["pull", "--rebase"], cwd=STEERING_REPO)  # May fail if no remote, that's ok

        # Create and checkout new branch
        success, err = run_git(["checkout", "-b", branch_name])
        if not success:
            result["message"] = f"Failed to create branch: {err}"
            return result

        # Format and append skill to target file
        formatted = format_skill_for_steering(skill)

        # Read existing content or create header
        if target_path.exists():
            existing = target_path.read_text()
        else:
            category_name = skill.get('category', 'misc').replace('-', ' ').title()
            existing = f"# {category_name} Skills\n\nCurated tips from the community.\n\n---\n\n"

        # Append new skill
        new_content = existing + formatted
        target_path.write_text(new_content)

        # Commit
        run_git(["add", str(target_path)])
        commit_msg = f"Add skill: {skill['title'][:50]}\n\nSource: {skill['url']}\nCategory: {skill.get('category', 'unknown')}"
        success, err = run_git(["commit", "-m", commit_msg])
        if not success:
            result["message"] = f"Failed to commit: {err}"
            run_git(["checkout", original_branch])
            return result

        result["success"] = True
        result["message"] = f"Created branch {branch_name} with skill"

        # Create PR if requested and remote exists
        if create_pr:
            # Check if remote exists
            has_remote, _ = run_git(["remote", "get-url", "origin"])
            if has_remote:
                # Push branch
                success, err = run_git(["push", "-u", "origin", branch_name])
                if success:
                    # Create PR
                    pr_title = f"Add skill: {skill['title'][:60]}"
                    pr_body = f"""## New Skill from Aggregator

**Title:** {skill['title']}
**Source:** [{skill['source']}]({skill['url']})
**Author:** {skill['author']}
**Category:** {skill.get('category', 'unknown')}
**Score:** {skill['score']}

### Content Preview
```
{skill['content'][:500]}{'...' if len(skill['content']) > 500 else ''}
```

---
Auto-generated by claude-skill-aggregator
"""
                    success, output = run_gh(["pr", "create", "--title", pr_title, "--body", pr_body])
                    if success:
                        result["pr_url"] = output.strip()
                        result["message"] = f"Created PR: {result['pr_url']}"
                    else:
                        result["message"] = f"Branch pushed but PR creation failed: {output}"
                else:
                    result["message"] = f"Branch created locally but push failed: {err}"
            else:
                result["message"] = f"Branch {branch_name} created locally (no remote configured)"

        # Return to main
        run_git(["checkout", original_branch])

    except Exception as e:
        result["message"] = f"Error: {str(e)}"
        run_git(["checkout", original_branch])

    return result

def sync_to_locations(config: dict) -> dict:
    """
    Sync steering files to actual locations via symlinks.

    Returns dict with results of each sync operation.
    """
    ensure_steering_repo()
    results = {}

    # Sync global CLAUDE.md to ~/.claude/
    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(exist_ok=True)

    global_claude = GLOBAL_DIR / "CLAUDE.md"
    target_claude = claude_dir / "CLAUDE.md"

    if global_claude.exists():
        if target_claude.exists() or target_claude.is_symlink():
            target_claude.unlink()
        target_claude.symlink_to(global_claude)
        results["global"] = f"Linked {target_claude} -> {global_claude}"

    # Sync project-specific configs
    sync_config = config.get("sync", {})
    project_mappings = sync_config.get("projects", {})

    for project_name, project_path in project_mappings.items():
        project_steering = PROJECTS_DIR / project_name / "CLAUDE.md"
        target_path = Path(project_path).expanduser() / "CLAUDE.md"

        if project_steering.exists():
            if target_path.exists() or target_path.is_symlink():
                target_path.unlink()
            target_path.symlink_to(project_steering)
            results[project_name] = f"Linked {target_path} -> {project_steering}"
        else:
            results[project_name] = f"No steering file at {project_steering}"

    return results

def list_promoted() -> list[dict]:
    """List all skills that have been promoted (exist in steering repo)."""
    promoted = []
    for skill_file in SKILLS_DIR.glob("*.md"):
        if skill_file.name == ".gitkeep":
            continue
        promoted.append({
            "file": skill_file.name,
            "path": str(skill_file),
            "size": skill_file.stat().st_size,
        })
    return promoted


def create_integration_pr(skill: dict, integrated_content: str, pr_body: str, change_type: str) -> dict:
    """
    Create a PR that modifies CLAUDE.md directly with integrated content.

    Returns dict with: success, branch, pr_url, message
    """
    ensure_steering_repo()

    target_path = GLOBAL_DIR / "CLAUDE.md"
    branch_name = f"integrate/{skill['id'][:8]}-{datetime.now().strftime('%Y%m%d')}"
    original_branch = get_current_branch()

    result = {
        "success": False,
        "branch": branch_name,
        "pr_url": None,
        "message": ""
    }

    try:
        # Ensure we're on main and up to date
        run_git(["checkout", "main"])
        run_git(["pull", "--rebase"], cwd=STEERING_REPO)

        # Create and checkout new branch
        success, err = run_git(["checkout", "-b", branch_name])
        if not success:
            result["message"] = f"Failed to create branch: {err}"
            return result

        # Write the integrated content
        target_path.write_text(integrated_content)

        # Commit
        run_git(["add", str(target_path)])
        commit_msg = f"Integrate skill: {skill['title'][:50]}\n\nChange type: {change_type}\nSource: {skill['url']}"
        success, err = run_git(["commit", "-m", commit_msg])
        if not success:
            result["message"] = f"Failed to commit: {err}"
            run_git(["checkout", original_branch])
            run_git(["branch", "-D", branch_name])
            return result

        result["success"] = True
        result["message"] = f"Created branch {branch_name}"

        # Push and create PR
        has_remote, _ = run_git(["remote", "get-url", "origin"])
        if has_remote:
            success, err = run_git(["push", "-u", "origin", branch_name])
            if success:
                pr_title = f"[{change_type.upper()}] {skill['title'][:50]}"
                success, output = run_gh(["pr", "create", "--title", pr_title, "--body", pr_body])
                if success:
                    result["pr_url"] = output.strip()
                    result["message"] = f"Created PR: {result['pr_url']}"
                else:
                    result["message"] = f"Branch pushed but PR creation failed: {output}"
            else:
                result["message"] = f"Branch created locally but push failed: {err}"
        else:
            result["message"] = f"Branch {branch_name} created locally (no remote configured)"

        # Return to main
        run_git(["checkout", original_branch])

    except Exception as e:
        result["message"] = f"Error: {str(e)}"
        run_git(["checkout", original_branch])

    return result
