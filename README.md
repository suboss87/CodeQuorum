# ⚖️ CodeQuorum

> *A finding is real when agents agree. A tradeoff is real when they don't.*

**Challenge #2 — The AI Pair Engineer** | Careem WorkOS FDE Application

---

## What It Does

Most code review tools simulate one reviewer. One reviewer has one set of biases.

Real engineering review is a panel. A pragmatist who wants to ship. A purist who cares about correctness. An operator who's been paged at 3am. They disagree. That disagreement is signal.

CodeQuorum runs three specialist agents in parallel — each with a distinct philosophy — then surfaces where they agree (fix it, no debate) and where they conflict (your call, genuine tradeoff). Confidence comes from inter-agent consensus, not from one LLM self-assessing certainty.

## How It Works

```
Your GitHub repo
      │
      ├──→ 🚢 Pragmatist  "Will this actually break?"
      ├──→ 🎯 Purist      "Is this actually correct?"     ──→ ⚖️ Synthesis
      └──→ 🔧 Operator    "Will I know when it fails?"
                │                │                │
           [parallel, ~4s — not 12s sequential]
```

**Synthesis agent** receives all three finding sets and does two things:
- **2+ agents agree** on the same root cause → `FIX IT` + suggested refactor + test case
- **Only 1 agent flags** something → `YOUR CALL` (genuine tradeoff — human judgment needed)

## What You Get Per Finding

| Field | Description |
|---|---|
| Issue | What is wrong and why |
| Fix | Concrete refactor suggestion |
| Test | A specific test that would catch this bug |
| Confidence | 3/3, 2/3, or 1/3 — from inter-agent agreement |
| Call | FIX IT or YOUR CALL |

## Architecture

Built on **LangGraph** (fan-out → fan-in), **ThreadPoolExecutor** (true parallel API calls), and **Streamlit**.

```
START → agents_node (parallel) → synthesis_node → END
```

Supports **Claude Sonnet 4.6**, **GPT-4o**, and **Gemini 2.0 Flash** — switch model in the sidebar.

GitHub integration: connect your account via OAuth, pick any repo from your list (public or private), review starts immediately.

## Why This Pattern Matters for Enterprise

This is a micro-implementation of the orchestration pattern needed for enterprise WorkOS:

- **Specialist agents** with distinct value systems, not generic reviewers
- **Parallel execution** with structured fan-in — no wasted latency
- **Disagreement as first-class output** — surfaces human judgment calls rather than replacing them
- **Confidence from consensus** — trustworthy because it's derived from agreement, not self-assessment

At enterprise scale this applies beyond code: multi-agent review of contracts, compliance documents, customer escalations — any domain where a single AI reviewer is a single point of bias.

## Research Basis

Multi-agent debate (MAD) improves factuality and catches more errors than single-agent review. The key insight: **the information is in the disagreement**, not just the consensus. CodeQuorum is designed around this property.

## Quick Start

```bash
git clone https://github.com/suboss87/CodeQuorum
cd CodeQuorum
pip install -r requirements.txt
cp .env.example .env   # add your API key
streamlit run app.py
```

For GitHub OAuth (one-click repo connect), see `.env.example`.

## Tests

```bash
pytest tests/ -v   # 11 tests, all passing
```

---

*Built by Subash Natarajan*
