import os
import re
import json
import base64
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "qwen/qwen2.5-vl-32b-instruct:free",
).strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

MAX_ISSUES = 30
MAX_TREE_FILES = 350
MAX_SOURCE_FILES = 6
MAX_FILE_CHARS = 12000
MAX_IMAGE_BYTES = 8 * 1024 * 1024

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in allowed_origins_raw.split(",")
    if origin.strip()
]

app = FastAPI(
    title="OpenFix AI API",
    description="Multimodal open-source contribution copilot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RepoRequest(BaseModel):
    repo_url: str


class SolveIssueRequest(BaseModel):
    repo_url: str
    issue_number: int


def github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "OpenFix-AI",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def parse_repo_url(repo_url: str):
    repo_url = (repo_url or "").strip().rstrip("/")
    match = re.search(r"(?:https?://)?github\.com/([^/\s]+)/([^/\s#?]+)", repo_url, re.I)

    if not match:
        raise HTTPException(
            status_code=400,
            detail="Enter a public GitHub URL such as https://github.com/owner/repo",
        )

    owner = match.group(1)
    repo = match.group(2)

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


def github_get(url: str, params=None):
    try:
        response = requests.get(
            url,
            headers=github_headers(),
            params=params,
            timeout=25,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach GitHub: {exc}",
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Repository or GitHub resource not found. OpenFix currently supports public repositories.",
        )

    if response.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail="GitHub rate limit or access limit reached. Try again later or configure an optional GITHUB_TOKEN.",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"GitHub API error: {response.text[:300]}",
        )

    return response.json()


def clean_json(text: str):
    if not text:
        return None

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    for opener, closer in [("{", "}"), ("[", "]")]:
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            chunk = text[start : end + 1]
            try:
                return json.loads(chunk)
            except Exception:
                pass

    return None


def ensure_openrouter_configured():
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENROUTER_API_KEY is not configured on the backend.",
        )


def call_openrouter_text(prompt: str, max_tokens: int = 2500):
    ensure_openrouter_configured()

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are OpenFix AI, an open-source contribution copilot. "
                    "Use only evidence supplied to you. Clearly distinguish verified "
                    "repository evidence from inference. Never invent files or claim "
                    "to have inspected content that was not provided."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "X-Title": "OpenFix AI",
            },
            json=payload,
            timeout=120,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"OpenRouter request failed: {exc}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter error: {response.text[:500]}",
        )

    try:
        return response.json()["choices"][0]["message"]["content"]
    except Exception:
        raise HTTPException(status_code=502, detail="Unexpected response from OpenRouter.")


def call_openrouter_image(prompt: str, image_bytes: bytes, mime_type: str):
    ensure_openrouter_configured()

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{encoded}"

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are OpenFix AI's multimodal debugging assistant. "
                    "Inspect screenshots carefully. Do not invent text that is not readable."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 2800,
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "X-Title": "OpenFix AI",
            },
            json=payload,
            timeout=150,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"OpenRouter request failed: {exc}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter vision error: {response.text[:500]}",
        )

    try:
        return response.json()["choices"][0]["message"]["content"]
    except Exception:
        raise HTTPException(status_code=502, detail="Unexpected vision response from OpenRouter.")


def get_repo(owner: str, repo: str):
    return github_get(f"{GITHUB_API}/repos/{owner}/{repo}")


def get_readme(owner: str, repo: str):
    try:
        data = github_get(f"{GITHUB_API}/repos/{owner}/{repo}/readme")
    except HTTPException as exc:
        if exc.status_code == 404:
            return ""
        raise

    if data.get("encoding") != "base64":
        return ""

    try:
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def get_issues(owner: str, repo: str):
    data = github_get(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues",
        params={"state": "open", "per_page": MAX_ISSUES},
    )
    return [item for item in data if "pull_request" not in item]


def get_issue(owner: str, repo: str, issue_number: int):
    data = github_get(f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}")
    if "pull_request" in data:
        raise HTTPException(status_code=400, detail="That number refers to a pull request, not an issue.")
    return data


def get_repository_tree(owner: str, repo: str, default_branch: str):
    data = github_get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"},
    )

    ignored = (
        "node_modules/",
        ".git/",
        "dist/",
        "build/",
        ".next/",
        "vendor/",
        "__pycache__/",
        ".venv/",
    )
    useful_extensions = (
        ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".cpp",
        ".go", ".rs", ".php", ".rb", ".html", ".css", ".json",
        ".yaml", ".yml", ".toml", ".md",
    )

    files = []
    for item in data.get("tree", []):
        if item.get("type") != "blob":
            continue

        path = item.get("path", "")
        if any(part in path for part in ignored):
            continue
        if not path.lower().endswith(useful_extensions):
            continue

        files.append(path)
        if len(files) >= MAX_TREE_FILES:
            break

    return files


def get_file_content(owner: str, repo: str, path: str):
    try:
        data = github_get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")
    except HTTPException:
        return ""

    if data.get("encoding") != "base64":
        return ""

    try:
        decoded = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
        return decoded[:MAX_FILE_CHARS]
    except Exception:
        return ""


def summarize_repo(repo_info: dict, readme: str):
    prompt = f"""
Analyze this public GitHub repository.

Repository: {repo_info.get("full_name")}
Description: {repo_info.get("description")}
Primary language: {repo_info.get("language")}
Stars: {repo_info.get("stargazers_count")}
Forks: {repo_info.get("forks_count")}

README excerpt:
{readme[:7000] if readme else "No README available."}

Return ONLY valid JSON in this schema:
{{
  "summary": "2-4 sentence repository overview",
  "purpose": "what the project does",
  "target_users": "who uses it",
  "tech_stack": ["technology"],
  "contributor_notes": ["important note"],
  "beginner_friendly": true
}}

Do not claim a technology is verified unless it is supported by the supplied data.
"""

    raw = call_openrouter_text(prompt)
    parsed = clean_json(raw)

    if isinstance(parsed, dict):
        return parsed

    return {
        "summary": raw,
        "purpose": "",
        "target_users": "",
        "tech_stack": [],
        "contributor_notes": [],
        "beginner_friendly": None,
    }


def classify_issues(issues: list):
    if not issues:
        return []

    compact = []
    for issue in issues:
        compact.append(
            {
                "number": issue["number"],
                "title": issue["title"],
                "body": (issue.get("body") or "")[:900],
                "labels": [label["name"] for label in issue.get("labels", [])],
            }
        )

    prompt = f"""
You help contributors choose open-source issues.

Analyze these issues:
{json.dumps(compact, ensure_ascii=False)}

For EVERY issue return an object with:
- number
- type: bug|feature|docs|question|chore|other
- priority: low|medium|high
- difficulty: beginner|intermediate|advanced
- skills: array of short skill names
- contributor_friendliness: integer 0-100
- short_summary: one short sentence

Return ONLY a JSON array.
"""

    raw = call_openrouter_text(prompt, max_tokens=3200)
    parsed = clean_json(raw)

    return parsed if isinstance(parsed, list) else []


def choose_relevant_files(issue: dict, file_tree: list):
    prompt = f"""
Investigate this GitHub issue.

Title:
{issue.get("title")}

Body:
{issue.get("body") or "No description provided."}

Repository file tree:
{chr(10).join(file_tree)}

Choose at most {MAX_SOURCE_FILES} files most likely to contain code or configuration relevant to the issue.

Rules:
- Choose only exact paths present in the supplied tree.
- Prefer implementation files over documentation unless documentation is the issue.
- Do not invent paths.

Return ONLY valid JSON:
{{
  "files": [
    {{"path": "exact/path/from/tree.py", "reason": "why it may matter"}}
  ]
}}
"""

    raw = call_openrouter_text(prompt)
    parsed = clean_json(raw)
    if not isinstance(parsed, dict):
        return []

    valid = set(file_tree)
    result = []
    for item in parsed.get("files", []):
        path = item.get("path")
        if path in valid:
            result.append({"path": path, "reason": item.get("reason", "")})

    return result[:MAX_SOURCE_FILES]


def generate_solution(repo_info: dict, issue: dict, relevant_files: list, source_contents: dict):
    code_context = ""
    for path, content in source_contents.items():
        code_context += f"\n\n===== FILE: {path} =====\n{content}"

    prompt = f"""
You are preparing a repository-aware contribution plan.

Repository: {repo_info.get("full_name")}
Description: {repo_info.get("description")}

Issue #{issue.get("number")}: {issue.get("title")}
Issue body:
{issue.get("body") or "No description provided."}

Potentially relevant files:
{json.dumps(relevant_files, indent=2)}

Actual source supplied:
{code_context or "No source file contents could be loaded."}

Return ONLY valid JSON:
{{
  "issue_summary": "short summary",
  "root_cause": {{
    "explanation": "evidence-grounded root cause or best hypothesis",
    "confidence": 0,
    "evidence": ["specific evidence"]
  }},
  "files_to_edit": [
    {{"path": "file path", "reason": "why"}}
  ],
  "fix_plan": ["step"],
  "suggested_patch": "unified diff, or empty string if evidence is insufficient",
  "testing_steps": ["test step"],
  "skills_needed": ["skill"],
  "difficulty": "beginner|intermediate|advanced",
  "contribution_checklist": [
    "review repository contribution rules",
    "create a focused branch",
    "implement the change",
    "run relevant tests",
    "review the diff",
    "open a pull request"
  ],
  "limitations": ["anything not verified"]
}}

Requirements:
- Do not invent files.
- Use only supplied repository evidence.
- If the exact fix is uncertain, explain the uncertainty and leave suggested_patch empty.
- A patch is guidance only and must be reviewed and tested.
"""

    raw = call_openrouter_text(prompt, max_tokens=4500)
    parsed = clean_json(raw)

    if isinstance(parsed, dict):
        return parsed

    return {
        "issue_summary": raw,
        "root_cause": {"explanation": "", "confidence": 0, "evidence": []},
        "files_to_edit": [],
        "fix_plan": [],
        "suggested_patch": "",
        "testing_steps": [],
        "skills_needed": [],
        "difficulty": "unknown",
        "contribution_checklist": [],
        "limitations": ["The model response could not be parsed into the requested structure."],
    }


@app.get("/")
def root():
    return {
        "name": "OpenFix AI",
        "status": "online",
        "model": OPENROUTER_MODEL,
        "main_flow": "repository URL",
        "optional_flow": "screenshot debugging",
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "model": OPENROUTER_MODEL,
        "openrouter_configured": bool(OPENROUTER_API_KEY),
    }


@app.post("/api/repository/analyze")
def analyze_repository(request: RepoRequest):
    owner, repo = parse_repo_url(request.repo_url)
    repo_info = get_repo(owner, repo)
    readme = get_readme(owner, repo)
    issues = get_issues(owner, repo)

    ai_summary = summarize_repo(repo_info, readme)
    triage = classify_issues(issues)
    triage_map = {
        item.get("number"): item
        for item in triage
        if isinstance(item, dict) and item.get("number") is not None
    }

    enriched = []
    for issue in issues:
        enriched.append(
            {
                "number": issue["number"],
                "title": issue["title"],
                "body": issue.get("body"),
                "url": issue.get("html_url"),
                "created_at": issue.get("created_at"),
                "labels": [label["name"] for label in issue.get("labels", [])],
                "ai": triage_map.get(issue["number"], {}),
            }
        )

    return {
        "repository": {
            "name": repo_info.get("full_name"),
            "description": repo_info.get("description"),
            "language": repo_info.get("language"),
            "stars": repo_info.get("stargazers_count"),
            "forks": repo_info.get("forks_count"),
            "open_issues": repo_info.get("open_issues_count"),
            "default_branch": repo_info.get("default_branch"),
            "license": (repo_info.get("license") or {}).get("name"),
            "github_url": repo_info.get("html_url"),
        },
        "ai_summary": ai_summary,
        "issues": enriched,
        "model": OPENROUTER_MODEL,
    }


@app.post("/api/issue/solve")
def solve_issue(request: SolveIssueRequest):
    owner, repo = parse_repo_url(request.repo_url)
    repo_info = get_repo(owner, repo)
    issue = get_issue(owner, repo, request.issue_number)

    tree = get_repository_tree(
        owner,
        repo,
        repo_info.get("default_branch") or "main",
    )
    relevant_files = choose_relevant_files(issue, tree)

    source_contents = {}
    for item in relevant_files:
        content = get_file_content(owner, repo, item["path"])
        if content:
            source_contents[item["path"]] = content

    solution = generate_solution(
        repo_info,
        issue,
        relevant_files,
        source_contents,
    )

    return {
        "repository": repo_info.get("full_name"),
        "issue": {
            "number": issue["number"],
            "title": issue["title"],
            "url": issue.get("html_url"),
        },
        "relevant_files": relevant_files,
        "files_inspected": list(source_contents.keys()),
        "solution": solution,
        "model": OPENROUTER_MODEL,
    }


@app.post("/api/vision/debug")
async def vision_debug(
    image: UploadFile = File(...),
    repo_url: Optional[str] = Form(None),
    note: Optional[str] = Form(""),
):
    mime_type = image.content_type or ""

    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(
            status_code=400,
            detail="Upload a PNG, JPG/JPEG, or WEBP image.",
        )

    data = await image.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image must be smaller than 8 MB.")

    repository_context = "No repository URL supplied."

    if repo_url and repo_url.strip():
        owner, repo = parse_repo_url(repo_url)
        info = get_repo(owner, repo)
        readme = get_readme(owner, repo)
        issues = get_issues(owner, repo)

        issue_titles = [
            f"#{item['number']} {item['title']}"
            for item in issues[:15]
        ]

        repository_context = f"""
Repository: {info.get("full_name")}
Description: {info.get("description")}
Primary language: {info.get("language")}
README excerpt:
{readme[:3000] if readme else "No README available."}

Open issue titles:
{chr(10).join(issue_titles) if issue_titles else "No open issues found."}
"""

    prompt = f"""
Analyze this developer screenshot.

User note:
{note or "No note provided."}

Optional repository context:
{repository_context}

Produce a concise debugging report containing:
1. What is visibly shown
2. Exact error text, only if clearly readable
3. Most likely cause
4. Debugging steps
5. Repository areas likely involved, if repository context exists
6. Suggested fix
7. How to verify the fix
8. Confidence and uncertainty

Do not pretend unreadable text is readable.
Do not claim you inspected repository source code in this screenshot route.
"""

    analysis = call_openrouter_image(prompt, data, mime_type)

    return {
        "analysis": analysis,
        "model": OPENROUTER_MODEL,
    }
