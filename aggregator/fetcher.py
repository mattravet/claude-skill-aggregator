"""Fetch Claude Code tips from Reddit and GitHub."""

import os
import re
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional
import requests

@dataclass
class Skill:
    id: str
    title: str
    content: str
    source: str
    url: str
    author: str
    score: int
    date: str
    category: str
    metadata: dict
    
    def to_dict(self):
        return asdict(self)

def generate_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:12]

def categorize_content(title: str, content: str) -> str:
    text = (title + " " + content).lower()
    if "claude.md" in text:
        return "claude-md"
    if "hook" in text or "#!/" in content:
        return "hook"
    if any(w in text for w in ["workflow", "process", "pipeline"]):
        return "workflow"
    if any(w in text for w in ["command", "flag", "--", "cli"]):
        return "command"
    return "prompt-pattern"

class RedditFetcher:
    def __init__(self, config: dict):
        self.config = config.get('reddit', {})
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'ClaudeSkillAggregator/1.0'
    
    def fetch_subreddit(self, subreddit: str, limit: int = 50) -> list[dict]:
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()['data']['children']
        except Exception as e:
            print(f"Error fetching r/{subreddit}: {e}")
            return []
    
    def search_subreddit(self, subreddit: str, query: str) -> list[dict]:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = {'q': query, 'restrict_sr': 'on', 'sort': 'new', 'limit': 25}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()['data']['children']
        except Exception as e:
            print(f"Error searching r/{subreddit}: {e}")
            return []
    
    def extract_skill(self, post: dict) -> Optional[Skill]:
        data = post['data']
        min_score = self.config.get('min_score', 20)
        if data.get('score', 0) < min_score:
            return None
        
        lookback = self.config.get('lookback_days', 7)
        post_time = datetime.fromtimestamp(data['created_utc'])
        if datetime.now() - post_time > timedelta(days=lookback):
            return None
        
        content = data.get('selftext', '').strip()
        if not content or content == '[removed]' or len(content) < 50:
            return None
        
        title = data.get('title', '')
        text = (title + " " + content).lower()
        keywords = ['claude', 'prompt', 'tip', 'workflow', 'trick', 'technique']
        if not any(k in text for k in keywords):
            return None
        
        return Skill(
            id=generate_id(data['permalink']),
            title=title,
            content=content,
            source='reddit',
            url=f"https://reddit.com{data['permalink']}",
            author=f"u/{data['author']}",
            score=data['score'],
            date=post_time.strftime('%Y-%m-%d'),
            category=categorize_content(title, content),
            metadata={'subreddit': f"r/{data['subreddit']}", 'num_comments': data.get('num_comments', 0)}
        )
    
    def fetch_all(self) -> list[Skill]:
        skills, seen = [], set()
        for sub in self.config.get('subreddits', []):
            for post in self.fetch_subreddit(sub):
                skill = self.extract_skill(post)
                if skill and skill.id not in seen:
                    skills.append(skill)
                    seen.add(skill.id)
            for query in self.config.get('queries', []):
                for post in self.search_subreddit(sub, query):
                    skill = self.extract_skill(post)
                    if skill and skill.id not in seen:
                        skills.append(skill)
                        seen.add(skill.id)
        return skills

class GitHubFetcher:
    def __init__(self, config: dict):
        self.config = config.get('github', {})
        self.session = requests.Session()
        self.session.headers['Accept'] = 'application/vnd.github.v3+json'
        token = os.getenv('GITHUB_TOKEN')
        if token:
            self.session.headers['Authorization'] = f"token {token}"
    
    def search_code(self, query: str) -> list[dict]:
        url = "https://api.github.com/search/code"
        params = {'q': query, 'per_page': 30}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get('items', [])
        except Exception as e:
            print(f"Error searching GitHub: {e}")
            return []
    
    def fetch_file_content(self, url: str) -> Optional[str]:
        raw_url = url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
        try:
            resp = self.session.get(raw_url, timeout=10)
            resp.raise_for_status()
            return resp.text
        except:
            return None
    
    def extract_skill_from_file(self, item: dict) -> Optional[Skill]:
        repo = item.get('repository', {})
        min_stars = self.config.get('min_stars', 10)
        trusted = self.config.get('trusted_authors', [])
        owner = repo.get('owner', {}).get('login', '')
        stars = repo.get('stargazers_count', 0)
        
        if owner not in trusted and stars < min_stars:
            return None
        
        content = self.fetch_file_content(item['html_url'])
        if not content or len(content) < 50:
            return None
        
        return Skill(
            id=generate_id(item['html_url']),
            title=f"{item['name']} from {repo['full_name']}",
            content=content[:5000],
            source='github',
            url=item['html_url'],
            author=owner,
            score=stars,
            date=datetime.now().strftime('%Y-%m-%d'),
            category=categorize_content(item['name'], content),
            metadata={'repo': repo['full_name'], 'path': item['path']}
        )
    
    def fetch_all(self) -> list[Skill]:
        skills, seen = [], set()
        for query in self.config.get('queries', []):
            for item in self.search_code(query):
                skill = self.extract_skill_from_file(item)
                if skill and skill.id not in seen:
                    skills.append(skill)
                    seen.add(skill.id)
        return skills

def fetch_all_sources(config: dict) -> list[Skill]:
    skills = []
    reddit = RedditFetcher(config)
    skills.extend(reddit.fetch_all())
    print(f"Fetched {len(skills)} from Reddit")
    github = GitHubFetcher(config)
    gh_skills = github.fetch_all()
    skills.extend(gh_skills)
    print(f"Fetched {len(gh_skills)} from GitHub")
    return skills
