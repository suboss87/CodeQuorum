import os
import streamlit as st
from dotenv import load_dotenv
from graph import graph
from github_fetch import fetch_code
from github_auth import (
    oauth_configured, get_auth_url,
    exchange_code, get_github_user, list_user_repos,
)

load_dotenv()

EXAMPLE = """\
def get_user_discount(user, cart_total):
    discount = 0
    if user.is_premium == True:
        discount = cart_total * 0.1
    if cart_total > 100:
        discount = cart_total * 0.15   # overwrites premium discount silently
    if user.loyalty_years > 5:
        discount += cart_total * 0.05
    return cart_total - discount
"""

AGENT_META = {
    "pragmatist": {"icon": "🚢", "label": "Pragmatist", "question": "Will this actually break?"},
    "purist":      {"icon": "🎯", "label": "Purist",      "question": "Is this actually correct?"},
    "operator":    {"icon": "🔧", "label": "Operator",    "question": "Will I know when it fails?"},
}

CALL_FIX  = "FIX_IT"
CALL_YOUR = "YOUR_CALL"

# ── OAuth callback ────────────────────────────────────────────────────────────
params = st.query_params
if "code" in params and "github_token" not in st.session_state:
    with st.spinner("Connecting your GitHub account..."):
        try:
            token = exchange_code(params["code"])
            user  = get_github_user(token)
            repos = list_user_repos(token)
            st.session_state["github_token"] = token
            st.session_state["github_user"]  = user
            st.session_state["github_repos"] = repos
        except Exception as e:
            st.session_state["github_oauth_error"] = str(e)
    st.query_params.clear()
    st.rerun()

# ── Page ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="CodeQuorum", page_icon="⚖️", layout="wide")
st.title("⚖️ CodeQuorum")
st.caption("Detects design flaws. Proposes tests. Refactors. On every pull request.")

c1, c2, c3 = st.columns(3)
for col, meta in zip([c1, c2, c3], AGENT_META.values()):
    col.markdown(f"{meta['icon']} **{meta['label']}** — *{meta['question']}*")

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

    st.markdown("---")
    st.caption("2+ agents agree → **FIX IT** with refactored code + test  \n1 agent flags → **YOUR CALL**")

    st.markdown("---")
    st.subheader("Add to your repo")
    st.caption("Auto-review every PR — no manual step needed.")
    with st.expander("Get the GitHub Action"):
        st.markdown(
            "Copy this file into your repo at `.github/workflows/codequorum.yml`  \n"
            "Then add `ANTHROPIC_API_KEY` as a repo secret.  \n"
            "Every PR gets reviewed automatically."
        )
        st.code(
            """name: CodeQuorum Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install anthropic langgraph python-dotenv requests
      - run: |
          curl -sO https://raw.githubusercontent.com/suboss87/CodeQuorum/main/cli.py
          curl -sO https://raw.githubusercontent.com/suboss87/CodeQuorum/main/agents.py
          curl -sO https://raw.githubusercontent.com/suboss87/CodeQuorum/main/graph.py
      - run: python cli.py --path . --format markdown > review.md
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - uses: actions/github-script@v7
        with:
          script: |
            const body = require('fs').readFileSync('review.md','utf8');
            await github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo, body });""",
            language="yaml",
        )

# ── Main: left = input, right = results ──────────────────────────────────────
left, right = st.columns([1, 1], gap="large")

with left:
    github_token = st.session_state.get("github_token")
    github_user  = st.session_state.get("github_user", {})
    github_repos = st.session_state.get("github_repos", [])

    # ── Step 1: GitHub connection ─────────────────────────────────────────
    st.subheader("Step 1 — Connect GitHub")

    if github_token:
        login  = github_user.get("login", "")
        avatar = github_user.get("avatar_url", "")
        col_av, col_info, col_btn = st.columns([1, 4, 2])
        if avatar:
            col_av.image(avatar, width=40)
        col_info.markdown(f"**@{login}**")
        col_info.caption(f"{len(github_repos)} repos loaded")
        if col_btn.button("Disconnect", use_container_width=True):
            for key in ("github_token", "github_user", "github_repos"):
                st.session_state.pop(key, None)
            st.rerun()
    else:
        if "github_oauth_error" in st.session_state:
            st.error(st.session_state.pop("github_oauth_error"))

        if oauth_configured():
            st.link_button(
                "Connect GitHub Account",
                get_auth_url(),
                use_container_width=True,
            )
            st.caption("Connects your GitHub — public and private repos.")
        else:
            st.info(
                "**For public repos** — no connection needed, enter a URL below.\n\n"
                "**For private repos** — enter a GitHub access token."
            )
            pat = st.text_input(
                "GitHub access token (private repos)",
                type="password",
                placeholder="ghp_...",
                help="github.com/settings/tokens — 'repo' scope",
            )
            if pat:
                st.session_state["github_token"] = pat
                github_token = pat
            with st.expander("Enable one-click Connect (self-hosting)"):
                st.markdown(
                    "> Only needed if you're running your own instance.\n\n"
                    "1. Register an OAuth App at **github.com/settings/developers**\n"
                    "   Add callbacks: `http://localhost:8501` + your deployed URL\n"
                    "2. Add to `.env`:\n"
                    "```\nGITHUB_CLIENT_ID=...\nGITHUB_CLIENT_SECRET=...\n"
                    "APP_URL=https://your-app.streamlit.app\n```"
                )

    st.markdown("")

    # ── Step 2: Pick a repo ───────────────────────────────────────────────
    st.subheader("Step 2 — Select Repository")

    code         = ""
    source_label = ""
    selected_url = ""

    if github_repos:
        repo_names = [r["full_name"] for r in github_repos]
        chosen = st.selectbox("Your repositories", repo_names, index=0)
        if chosen:
            selected_url = f"https://github.com/{chosen}"
    else:
        selected_url = st.text_input(
            "Repository or file URL",
            placeholder="https://github.com/owner/repo",
        )

    if selected_url:
        with st.spinner("Fetching code..."):
            try:
                code, source_label = fetch_code(selected_url, github_token or None)
                st.success(f"Ready: {source_label}")
            except Exception as e:
                st.error(f"Could not fetch: {e}")
                code = ""

    with st.expander("Or paste code directly"):
        if st.button("Load example snippet", use_container_width=False):
            st.session_state["paste_value"] = EXAMPLE
        pasted = st.text_area(
            "",
            value=st.session_state.get("paste_value", ""),
            height=220,
            label_visibility="collapsed",
            placeholder="Paste code here...",
        )
        if pasted.strip() and not code:
            code = pasted
            source_label = "pasted code"

    st.markdown("")

    # ── Step 3: Run ───────────────────────────────────────────────────────
    st.subheader("Step 3 — Run Review")

    ready = bool(code.strip() and api_key)
    if not api_key:
        st.warning("Add your Anthropic API Key in the sidebar.")
    elif not code:
        st.caption("Select a repo or paste code above.")

    run = st.button(
        "⚖️ Convene Quorum",
        type="primary",
        use_container_width=True,
        disabled=not ready,
    )

# ── Run review and store results ──────────────────────────────────────────────
if run and code.strip():
    with right:
        st.subheader("What Was Reviewed")
        st.markdown(f"**{source_label}**")
        st.markdown("")
        st.subheader("Agents Reviewing")

        placeholders = {k: st.empty() for k in AGENT_META}
        for k, meta in AGENT_META.items():
            placeholders[k].markdown(f"{meta['icon']} **{meta['label']}** — reviewing...")

        agent_findings = {}
        synthesis      = {}
        initial = {
            "code": code,
            "pragmatist": [], "purist": [], "operator": [], "synthesis": {},
        }

        try:
            for event in graph.stream(initial):
                for node_name, state_update in event.items():
                    if node_name == "agents":
                        for agent_name, meta in AGENT_META.items():
                            findings = state_update.get(agent_name, [])
                            agent_findings[agent_name] = findings
                            count = len(findings)
                            placeholders[agent_name].markdown(
                                f"{meta['icon']} **{meta['label']}** — "
                                f"{count} design flaw{'s' if count != 1 else ''} found"
                            )
                    elif node_name == "synthesis":
                        synthesis = state_update.get("synthesis", {})
        except Exception as e:
            st.error(f"Review failed: {e}")
            st.stop()

        st.session_state["last_results"] = {
            "source_label":   source_label,
            "agent_findings": agent_findings,
            "synthesis":      synthesis,
        }
        st.rerun()

# ── Render stored results ─────────────────────────────────────────────────────
elif "last_results" in st.session_state:
    r          = st.session_state["last_results"]
    synthesis  = r["synthesis"]
    findings   = synthesis.get("findings", [])
    verdict    = synthesis.get("verdict", "")
    fix_items  = [f for f in findings if f.get("call") == CALL_FIX]
    call_items = [f for f in findings if f.get("call") == CALL_YOUR]

    with right:
        st.subheader("What Was Reviewed")
        st.markdown(f"**{r['source_label']}**")

        st.divider()

        if not findings:
            st.success("No design flaws found. Code looks clean.")
        else:
            st.subheader("Design Flaws Found")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Flaws", len(findings))
            m2.metric("🔴 Fix It", len(fix_items), help="2+ agents agreed — refactor + test included")
            m3.metric("🟡 Your Call", len(call_items), help="1 agent flagged — genuine tradeoff")

            if verdict:
                st.info(f"**Verdict:** {verdict}")

            with st.expander("Per-agent breakdown"):
                for key, meta in AGENT_META.items():
                    items = r["agent_findings"].get(key, [])
                    st.markdown(f"{meta['icon']} **{meta['label']}** — {len(items)} flaw{'s' if len(items) != 1 else ''}")
                    for item in items:
                        st.markdown(f"  - `L{item.get('line','?')}` {item.get('issue','')} *({item.get('severity','')})*")

            st.divider()

            if fix_items:
                st.subheader("🔴 Fix It — Refactored Code + Test")
                st.caption("2+ agents agreed. Includes refactored code and a failing test.")
                for f in fix_items:
                    agents = f.get("agents", [])
                    icons  = " ".join(AGENT_META[a]["icon"] for a in agents if a in AGENT_META)
                    with st.container(border=True):
                        col_a, col_b = st.columns([4, 1])
                        with col_a:
                            st.markdown(f"**{f.get('issue', '')}**")
                            if f.get("fix"):
                                st.caption(f"↳ {f['fix']}")
                            if f.get("refactored_code"):
                                st.markdown("**Refactored code:**")
                                st.code(f["refactored_code"], language="python")
                            if f.get("test"):
                                st.markdown("**Proposed test:**")
                                st.code(f["test"], language="python")
                        with col_b:
                            st.caption(f.get("confidence", ""))
                            st.caption(icons)
            else:
                st.success("No confirmed design flaws.")

            if call_items:
                st.subheader("🟡 Your Call — Design Tradeoffs")
                st.caption("One agent flagged these. Real considerations, not clear bugs.")
                for f in call_items:
                    agents = f.get("agents", [])
                    icons  = " ".join(AGENT_META[a]["icon"] for a in agents if a in AGENT_META)
                    with st.container(border=True):
                        col_a, col_b = st.columns([4, 1])
                        with col_a:
                            st.markdown(f"**{f.get('issue', '')}**")
                            if f.get("fix"):
                                st.caption(f"↳ {f['fix']}")
                        with col_b:
                            st.caption("1/3")
                            st.caption(icons)

else:
    with right:
        st.subheader("Results will appear here")
        st.caption("Connect GitHub, select a repo, then click Convene Quorum.")
        st.divider()
        st.markdown("**For every confirmed design flaw you get:**")
        with st.container(border=True):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.markdown("🔴 **Discount logic silently overwrites premium discount**")
                st.caption("↳ Use max() so the larger discount wins, then stack loyalty bonus")
                st.code(
                    "def get_user_discount(user, cart_total):\n"
                    "    discount = cart_total * 0.15 if cart_total > 100 else 0\n"
                    "    if user.is_premium:\n"
                    "        discount = max(discount, cart_total * 0.10)\n"
                    "    if user.loyalty_years > 5:\n"
                    "        discount += cart_total * 0.05\n"
                    "    return cart_total - discount",
                    language="python",
                )
                st.code(
                    "def test_premium_discount_not_overwritten():\n"
                    "    user = User(is_premium=True, loyalty_years=0)\n"
                    "    assert get_user_discount(user, 120) >= 120 * 0.10",
                    language="python",
                )
            with col_b:
                st.caption("2/3")
                st.caption("🚢 🎯")
        st.caption("Every Fix It finding: confirmed design flaw → refactored code → failing test.")
        st.divider()
        st.markdown("**Or add it to your repo to review every PR automatically:**")
        st.caption("See 'Add to your repo' in the sidebar.")
