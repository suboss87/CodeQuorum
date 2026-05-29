import pytest
from github_fetch import parse_github_url


def test_repo_url():
    info = parse_github_url("https://github.com/owner/myrepo")
    assert info["type"] == "repo"
    assert info["owner"] == "owner"
    assert info["repo"] == "myrepo"
    assert info["branch"] is None


def test_file_url():
    info = parse_github_url("https://github.com/owner/myrepo/blob/main/src/app.py")
    assert info["type"] == "file"
    assert info["owner"] == "owner"
    assert info["repo"] == "myrepo"
    assert info["branch"] == "main"
    assert info["path"] == "src/app.py"


def test_trailing_slash_stripped():
    info = parse_github_url("https://github.com/owner/myrepo/")
    assert info["type"] == "repo"
    assert info["repo"] == "myrepo"


def test_non_github_raises():
    with pytest.raises(ValueError, match="Not a GitHub URL"):
        parse_github_url("https://gitlab.com/owner/repo")


def test_missing_repo_raises():
    with pytest.raises(ValueError, match="must include owner/repo"):
        parse_github_url("https://github.com/owner")


def test_file_url_nested_path():
    info = parse_github_url("https://github.com/owner/repo/blob/feature-branch/a/b/c.ts")
    assert info["type"] == "file"
    assert info["branch"] == "feature-branch"
    assert info["path"] == "a/b/c.ts"
