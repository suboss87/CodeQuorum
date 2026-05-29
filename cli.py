#!/usr/bin/env python3
"""
CodeQuorum CLI — runs a review on a local directory and outputs results.
Used by the GitHub Actions workflow to post PR comments automatically.

Usage:
    python cli.py --path . --format markdown
    python cli.py --path ./src --model gpt-4o --format json
"""

import argparse
import json
import os
import sys
from pathlib import Path

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".rs",
    ".cpp", ".c", ".cs", ".php", ".swift", ".kt", ".scala", ".sh",
}
SKIP_DIRS = {"node_modules", "dist", "build", ".git", "venv", "__pycache__", ".next", "vendor"}
MAX_FILES   = 10
MAX_BYTES   = 30_000


def get_pr_changed_files() -> list[str]:
    """Return list of files changed in the current PR using git diff against base branch."""
    import subprocess
    base = os.getenv("GITHUB_BASE_REF", "main")
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{base}...HEAD"],
            capture_output=True, text=True, check=True,
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def read_local_files(path: str, pr_files: list[str] | None = None) -> tuple[str, str]:
    root = Path(path).resolve()
    sections = []

    if pr_files:
        # PR mode: review only what changed
        candidates = [
            root / f for f in pr_files
            if Path(f).suffix in CODE_EXTENSIONS
            and not any(part in SKIP_DIRS for part in Path(f).parts)
        ]
        label_suffix = f"{len(candidates)} changed files"
    else:
        candidates = sorted(
            [f for f in root.rglob("*")
             if f.is_file()
             and f.suffix in CODE_EXTENSIONS
             and not any(part in SKIP_DIRS for part in f.parts)],
            key=lambda f: f.stat().st_size,
            reverse=True,
        )
        label_suffix = f"{min(len(candidates), MAX_FILES)} files"

    for f in candidates[:MAX_FILES]:
        try:
            content = Path(f).read_text(errors="ignore")[:MAX_BYTES]
            rel = Path(f).relative_to(root)
            sections.append(f"# --- {rel} ---\n{content}")
        except Exception:
            pass

    if not sections:
        print("No code files found.", file=sys.stderr)
        sys.exit(1)

    label = f"{root.name} ({label_suffix})"
    return "\n\n".join(sections), label


def findings_to_markdown(source_label: str, model_label: str, synthesis: dict) -> str:
    findings   = synthesis.get("findings", [])
    verdict    = synthesis.get("verdict", "")
    fix_items  = [f for f in findings if f.get("call") == "FIX_IT"]
    call_items = [f for f in findings if f.get("call") == "YOUR_CALL"]

    AGENT_ICONS = {"pragmatist": "🚢", "purist": "🎯", "operator": "🔧"}

    lines = [
        "## ⚖️ CodeQuorum Review",
        "",
        f"**Reviewed:** `{source_label}` · **Model:** {model_label}",
        f"**Findings:** {len(findings)} total · 🔴 {len(fix_items)} Fix It · 🟡 {len(call_items)} Your Call",
        "",
    ]

    if verdict:
        lines += [f"> {verdict}", ""]

    if fix_items:
        lines += ["### 🔴 Fix It — Quorum Reached (2+ agents agreed)", ""]
        for f in fix_items:
            agents = f.get("agents", [])
            icons  = " ".join(AGENT_ICONS.get(a, "") for a in agents)
            conf   = f.get("confidence", "")
            lines += [f"**{f.get('issue', '')}** — `{conf}` {icons}", ""]
            if f.get("fix"):
                lines += [f"*{f['fix']}*", ""]
            if f.get("refactored_code"):
                lines += ["**Refactored:**", f"```python\n{f['refactored_code']}\n```", ""]
            if f.get("test"):
                lines += ["**Test:**", f"```python\n{f['test']}\n```", ""]
            lines.append("---")

    if call_items:
        lines += ["", "### 🟡 Your Call — Genuine Tradeoff (1 agent flagged)", ""]
        for f in call_items:
            agents = f.get("agents", [])
            icons  = " ".join(AGENT_ICONS.get(a, "") for a in agents)
            lines += [f"**{f.get('issue', '')}** {icons}", ""]
            if f.get("fix"):
                lines += [f"*{f['fix']}*", ""]
            lines.append("---")

    lines += [
        "",
        "*Reviewed by [CodeQuorum](https://github.com/suboss87/CodeQuorum) — "
        "3 specialist agents, parallel execution, confidence from consensus*",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="CodeQuorum CLI — AI pair engineer review")
    parser.add_argument("--path",   default=".", help="Path to local repo or directory")
    parser.add_argument("--model",  default="claude-sonnet-4-6",
                        choices=["claude-sonnet-4-6", "gpt-4o", "gemini-2.0-flash"])
    parser.add_argument("--format", default="markdown", choices=["markdown", "json"],
                        help="Output format")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    # Lazy import so CLI startup is fast
    from graph import graph

    MODEL_LABELS = {
        "claude-sonnet-4-6": "Claude Sonnet 4.6",
        "gpt-4o":            "GPT-4o",
        "gemini-2.0-flash":  "Gemini 2.0 Flash",
    }

    # In a GitHub Actions PR context, review only changed files
    pr_files = get_pr_changed_files() if os.getenv("GITHUB_BASE_REF") else None
    if pr_files:
        print(f"PR mode: reviewing {len(pr_files)} changed files", file=sys.stderr)
    code, source_label = read_local_files(args.path, pr_files)

    initial = {
        "code": code, "model": args.model,
        "pragmatist": [], "purist": [], "operator": [], "synthesis": {},
    }

    synthesis = {}
    for event in graph.stream(initial):
        for node_name, state_update in event.items():
            if node_name == "synthesis":
                synthesis = state_update.get("synthesis", {})

    if args.format == "json":
        print(json.dumps(synthesis, indent=2))
    else:
        print(findings_to_markdown(source_label, MODEL_LABELS[args.model], synthesis))


if __name__ == "__main__":
    main()
