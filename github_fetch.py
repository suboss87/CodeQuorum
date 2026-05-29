import re
import requests
from urllib.parse import urlparse

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".rs",
    ".cpp", ".c", ".cs", ".php", ".swift", ".kt", ".scala", ".r", ".sh",
    ".html", ".css", ".vue", ".svelte",
}

SKIP_DIRS = {"node_modules", "dist", "build", ".git", "venv", "__pycache__", ".next", "vendor"}

MAX_FILES = 10
MAX_FILE_BYTES = 30_000


def parse_github_url(url: str) -> dict:
    """Return {type: 'file'|'repo', owner, repo, branch, path} or raise ValueError."""
    url = url.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.netloc not in ("github.com", "www.github.com"):
        raise ValueError("Not a GitHub URL")

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("URL must include owner/repo")

    owner, repo = parts[0], parts[1]

    if len(parts) >= 5 and parts[2] == "blob":
        branch = parts[3]
        path = "/".join(parts[4:])
        return {"type": "file", "owner": owner, "repo": repo, "branch": branch, "path": path}

    return {"type": "repo", "owner": owner, "repo": repo, "branch": None, "path": None}


def _headers(token: str | None) -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _default_branch(owner: str, repo: str, token: str | None) -> str:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    r = requests.get(url, headers=_headers(token), timeout=10)
    r.raise_for_status()
    return r.json().get("default_branch", "main")


def _fetch_file_content(owner: str, repo: str, branch: str, path: str, token: str | None) -> str:
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.text[:MAX_FILE_BYTES]


def _is_code_file(path: str) -> bool:
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext not in CODE_EXTENSIONS:
        return False
    parts = path.split("/")
    return not any(part in SKIP_DIRS for part in parts[:-1])


def fetch_code(url: str, token: str | None = None) -> tuple[str, str]:
    """
    Returns (code_content, source_label).
    code_content is all fetched files concatenated with file headers.
    source_label is a human-readable description of what was fetched.
    """
    info = parse_github_url(url)
    owner, repo = info["owner"], info["repo"]

    if info["type"] == "file":
        branch = info["branch"]
        path = info["path"]
        content = _fetch_file_content(owner, repo, branch, path, token)
        label = f"{owner}/{repo}: {path}"
        return content, label

    # Repo fetch: get tree, filter code files, fetch up to MAX_FILES
    branch = info["branch"] or _default_branch(owner, repo, token)
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    r = requests.get(tree_url, headers=_headers(token), timeout=15)
    r.raise_for_status()
    tree = r.json()

    if tree.get("truncated"):
        pass  # best effort on large repos

    code_files = [
        item["path"] for item in tree.get("tree", [])
        if item["type"] == "blob" and _is_code_file(item["path"])
    ][:MAX_FILES]

    if not code_files:
        raise ValueError(f"No code files found in {owner}/{repo}")

    sections = []
    for path in code_files:
        try:
            content = _fetch_file_content(owner, repo, branch, path, token)
            sections.append(f"# --- {path} ---\n{content}")
        except Exception:
            pass  # skip unreadable files

    if not sections:
        raise ValueError("Could not read any files from the repository")

    label = f"{owner}/{repo} ({len(sections)} files, branch: {branch})"
    return "\n\n".join(sections), label
