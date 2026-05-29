import os
import streamlit as st
from dotenv import load_dotenv
from graph import graph

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

st.set_page_config(page_title="CodeQuorum", page_icon="⚖️", layout="wide")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚖️ CodeQuorum")
st.caption("Three reviewers. Different philosophies. Confidence from consensus, signal from conflict.")

# ── API key ───────────────────────────────────────────────────────────────────
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    with st.sidebar:
        st.subheader("Configuration")
        api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

with st.sidebar:
    st.markdown("---")
    st.markdown("**The three reviewers**")
    for meta in AGENT_META.values():
        st.markdown(f"{meta['icon']} **{meta['label']}** — *{meta['question']}*")
    st.markdown("---")
    st.caption("2+ agents agree → **FIX IT** (quorum reached)")
    st.caption("1 agent flags → **YOUR CALL** (genuine tradeoff)")

if not api_key:
    st.info("Add your Anthropic API key in the sidebar to start.")
    st.stop()

# ── Layout ────────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("Code Under Review")
    code = st.text_area("", value=EXAMPLE, height=320, label_visibility="collapsed")
    run = st.button("⚖️ Convene Quorum", type="primary", use_container_width=True)

# ── Execution ─────────────────────────────────────────────────────────────────
if run and code.strip():
    with right:
        st.subheader("Quorum in Progress")

        placeholders = {k: st.empty() for k in AGENT_META}
        for k, meta in AGENT_META.items():
            placeholders[k].markdown(f"{meta['icon']} **{meta['label']}** — reviewing…")

        agent_findings: dict = {}
        synthesis: dict = {}

        initial = {"code": code, "pragmatist": [], "purist": [], "operator": [], "synthesis": {}}

        for event in graph.stream(initial):
            for node_name, state_update in event.items():
                if node_name in AGENT_META:
                    findings = state_update.get(node_name, [])
                    agent_findings[node_name] = findings
                    meta = AGENT_META[node_name]
                    count = len(findings)
                    label = f"{count} finding{'s' if count != 1 else ''}"
                    placeholders[node_name].markdown(
                        f"{meta['icon']} **{meta['label']}** — ✅ {label}"
                    )
                elif node_name == "synthesis":
                    synthesis = state_update.get("synthesis", {})

        # ── Results ───────────────────────────────────────────────────────────
        st.divider()
        findings = synthesis.get("findings", [])
        verdict  = synthesis.get("verdict", "")
        score    = synthesis.get("quorum_score", 0.0)

        fix_count  = sum(1 for f in findings if f.get("call") == "FIX_IT")
        your_count = sum(1 for f in findings if f.get("call") == "YOUR_CALL")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Findings", len(findings))
        c2.metric("⚖️ Fix It", fix_count, help="Quorum: 2+ agents agreed")
        c3.metric("🤔 Your Call", your_count, help="Contested: only 1 agent flagged")

        if verdict:
            st.caption(f"*{verdict}*")

        st.divider()

        for f in findings:
            call       = f.get("call", "YOUR_CALL")
            confidence = f.get("confidence", "1/3")
            agents     = f.get("agents", [])

            border_color = "#d32f2f" if call == "FIX_IT" else "#f9a825"
            badge        = "🔴 **FIX IT**" if call == "FIX_IT" else "🟡 **YOUR CALL**"
            icons        = " ".join(AGENT_META[a]["icon"] for a in agents if a in AGENT_META)

            with st.container(border=True):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(f"**{f.get('issue', '')}**")
                    if f.get("fix"):
                        st.caption(f"↳ {f['fix']}")
                with col_b:
                    st.markdown(badge)
                    st.caption(f"{confidence} · {icons}")

        # ── Raw agent detail ──────────────────────────────────────────────────
        if agent_findings:
            with st.expander("Raw agent findings"):
                for key, meta in AGENT_META.items():
                    items = agent_findings.get(key, [])
                    st.markdown(f"{meta['icon']} **{meta['label']}** ({len(items)} findings)")
                    for item in items:
                        st.markdown(f"- `L{item.get('line','?')}` {item.get('issue','')} — *{item.get('severity','')}*")
                    if not items:
                        st.caption("No findings.")

elif run:
    with right:
        st.warning("Paste some code to review.")
