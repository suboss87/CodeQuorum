import os
import requests

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com/user"


def oauth_configured() -> bool:
    return bool(os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"))


def get_redirect_uri() -> str:
    """
    Resolve the OAuth callback URL.
    Set APP_URL in .env (local) or Streamlit Cloud secrets (production).
    Defaults to localhost for local development.
    """
    url = os.getenv("APP_URL", "http://localhost:8501").rstrip("/")
    return url


def get_auth_url() -> str:
    client_id    = os.getenv("GITHUB_CLIENT_ID")
    redirect_uri = get_redirect_uri()
    return (
        f"{GITHUB_AUTHORIZE_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=repo"
    )


def exchange_code(code: str) -> str:
    """Exchange OAuth code for access token. Returns the token string."""
    resp = requests.post(
        GITHUB_TOKEN_URL,
        headers={"Accept": "application/json"},
        data={
            "client_id": os.getenv("GITHUB_CLIENT_ID"),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
            "code": code,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"GitHub OAuth failed: {data.get('error_description', data)}")
    return data["access_token"]


def get_github_user(token: str) -> dict:
    """Return GitHub user info dict (login, avatar_url, name)."""
    resp = requests.get(
        GITHUB_API_URL,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def list_user_repos(token: str) -> list[dict]:
    """Return list of repos the authenticated user has access to."""
    repos = []
    page  = 1
    while len(repos) < 100:
        resp = requests.get(
            "https://api.github.com/user/repos",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            params={"per_page": 50, "page": page, "sort": "pushed", "affiliation": "owner,collaborator"},
            timeout=10,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos
