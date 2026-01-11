"""Git-backed storage for skills."""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
PENDING_FILE = DATA_DIR / "pending.json"
REJECTED_FILE = DATA_DIR / "rejected.json"
SOURCES_FILE = DATA_DIR / "sources.json"
APPROVED_DIR = DATA_DIR / "approved"

def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    APPROVED_DIR.mkdir(exist_ok=True)
    for f in [PENDING_FILE, REJECTED_FILE]:
        if not f.exists(): f.write_text("[]")
    if not SOURCES_FILE.exists(): SOURCES_FILE.write_text("{}")

def load_json(path: Path):
    ensure_dirs()
    try: return json.loads(path.read_text())
    except: return [] if "sources" not in str(path) else {}

def save_json(path: Path, data):
    ensure_dirs()
    path.write_text(json.dumps(data, indent=2))

def git_commit(message: str, config: dict):
    if not config.get('export', {}).get('auto_commit', True): return
    prefix = config.get('export', {}).get('commit_prefix', 'skills:')
    try:
        subprocess.run(["git", "add", str(DATA_DIR)], cwd=DATA_DIR.parent, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"{prefix} {message}"], cwd=DATA_DIR.parent, check=True, capture_output=True)
    except: pass

def get_seen_urls() -> set:
    return set(load_json(SOURCES_FILE).keys())

def mark_url_seen(url: str, skill_id: str):
    sources = load_json(SOURCES_FILE)
    sources[url] = {"id": skill_id, "seen": datetime.now().isoformat()}
    save_json(SOURCES_FILE, sources)

def add_pending(skills: list[dict], config: dict) -> int:
    seen, pending = get_seen_urls(), load_json(PENDING_FILE)
    pending_ids = {s['id'] for s in pending}
    added = 0
    for skill in skills:
        if skill['url'] in seen or skill['id'] in pending_ids: continue
        skill['added_at'] = datetime.now().isoformat()
        pending.append(skill)
        mark_url_seen(skill['url'], skill['id'])
        added += 1
    save_json(PENDING_FILE, pending)
    if added > 0: git_commit(f"added {added} pending skills", config)
    return added

def get_pending() -> list[dict]: return load_json(PENDING_FILE)
def get_rejected() -> list[dict]: return load_json(REJECTED_FILE)

def get_approved() -> list[dict]:
    ensure_dirs()
    skills = []
    for f in APPROVED_DIR.glob("*.json"):
        try: skills.append(json.loads(f.read_text()))
        except: pass
    return sorted(skills, key=lambda s: s.get('approved_at', ''), reverse=True)

def approve_skill(skill_id: str, config: dict) -> Optional[dict]:
    pending = load_json(PENDING_FILE)
    skill = next((s for s in pending if s['id'] == skill_id), None)
    if not skill: return None
    pending = [s for s in pending if s['id'] != skill_id]
    save_json(PENDING_FILE, pending)
    skill['approved_at'] = datetime.now().isoformat()
    (APPROVED_DIR / f"{skill_id}.json").write_text(json.dumps(skill, indent=2))
    (APPROVED_DIR / f"{skill_id}.md").write_text(skill_to_markdown(skill, config))
    git_commit(f"approved: {skill['title'][:50]}", config)
    return skill

def reject_skill(skill_id: str, reason: str, config: dict) -> Optional[dict]:
    pending = load_json(PENDING_FILE)
    skill = next((s for s in pending if s['id'] == skill_id), None)
    if not skill: return None
    pending = [s for s in pending if s['id'] != skill_id]
    save_json(PENDING_FILE, pending)
    skill['rejected_at'] = datetime.now().isoformat()
    skill['rejection_reason'] = reason
    rejected = load_json(REJECTED_FILE)
    rejected.append(skill)
    save_json(REJECTED_FILE, rejected)
    git_commit(f"rejected: {skill['title'][:50]}", config)
    return skill

def remove_approved(skill_id: str, config: dict) -> bool:
    removed = False
    for ext in ['json', 'md']:
        f = APPROVED_DIR / f"{skill_id}.{ext}"
        if f.exists(): f.unlink(); removed = True
    if removed: git_commit(f"removed skill {skill_id}", config)
    return removed

def skill_to_markdown(skill: dict, config: dict) -> str:
    lines = [f"# {skill['title']}", ""]
    if config.get('export', {}).get('include_metadata', True):
        lines.extend([f"**Source:** [{skill['source']}]({skill['url']})", f"**Author:** {skill['author']}", f"**Category:** {skill['category']}", f"**Score:** {skill['score']}", ""])
    lines.extend(["---", "", skill['content']])
    return "\n".join(lines)

def export_to_target(target_dir: str, config: dict) -> int:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    approved = get_approved()
    for skill in approved:
        (target / f"{skill['category']}_{skill['id']}.md").write_text(skill_to_markdown(skill, config))
    return len(approved)

def get_stats() -> dict:
    return {'pending': len(get_pending()), 'approved': len(list(APPROVED_DIR.glob("*.json"))), 'rejected': len(get_rejected()), 'total_seen': len(load_json(SOURCES_FILE))}
