# ⚖️ CodeQuorum

> *A finding is real when agents agree. A tradeoff is real when they don't.*

## The Problem

Every AI code review tool simulates one reviewer. One reviewer has one set of biases. When that reviewer is an LLM, it produces fluent, confident output that human reviewers skim and approve — including the bugs.

Real code review is a panel. A pragmatist who wants to ship, a purist who cares about correctness, an operator who's been paged at 3am. They disagree. That disagreement is signal, not noise. It tells you where the real tradeoffs live.

No existing tool captures this. CodeQuorum does.

## How It Works

Three specialist agents review your code independently, each with a distinct philosophy:

| Agent | Philosophy | Asks |
|---|---|---|
| 🚢 **Pragmatist** | Ship working software | *Will this actually break?* |
| 🎯 **Purist** | Correctness and clarity | *Is this actually right?* |
| 🔧 **Operator** | Survive production | *Will I know when this fails?* |

A **Synthesis agent** then receives all three sets of findings and does one thing: finds consensus and names conflict.

- **2+ agents agree on the same root cause** → `FIX IT` (quorum reached, high confidence)
- **Only 1 agent flags something** → `YOUR CALL` (genuine tradeoff, human judgment needed)

The confidence score per finding comes from inter-agent agreement — not from an LLM self-assessing its own certainty.

## Architecture

```
Code Input
    │
    ├──→ 🚢 Pragmatist Agent ─┐
    ├──→ 🎯 Purist Agent      ├──→ ⚖️ Synthesis Agent → Ranked findings + confidence
    └──→ 🔧 Operator Agent   ─┘         (waits for all three)
```

Built on **LangGraph** (fan-out → fan-in superstep), **Anthropic Claude**, and **Streamlit**.

The graph structure: `START → [pragmatist, purist, operator] → synthesis → END`

Synthesis waits for all three predecessors before running — this is LangGraph's built-in fan-in behaviour, not custom coordination.

## Why This Pattern Matters for Enterprise AI

This is a micro-implementation of the exact orchestration pattern needed for enterprise WorkOS:

- **Specialist agents** with distinct value systems, not generic reviewers
- **Parallel execution** with structured fan-in
- **Disagreement as a first-class output** — surfaces human judgment calls rather than replacing them
- **Confidence from consensus** — trustworthy because it's derived from agreement across independent agents, not from a single model's self-assessment

At enterprise scale, this pattern applies beyond code: multi-agent review of contracts, compliance checks, customer escalations — any domain where a single AI reviewer is a single point of bias.

## Research Basis

Multi-agent debate (MAD) improves factuality over single-agent review. The key finding from recent work ([Agree or Disagree, 2025](https://hungleai.substack.com/p/agree-or-disagree-a-review-of-multi); [DiscoUQ, 2026](https://arxiv.org/html/2603.20975)): **the information is in the disagreement**, not just the consensus. CodeQuorum is designed around this property.

Known limitation: agents sharing the same base model can exhibit correlated biases. Mitigation: philosophically distinct system prompts that actively pull reasoning in different directions, combined with a synthesis step that looks for divergence rather than forcing consensus.

## Quick Start

```bash
git clone https://github.com/suboss87/CodeQuorum
cd CodeQuorum
pip install -r requirements.txt

# Add your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

streamlit run app.py
```

Or provide the key directly in the sidebar when the app opens.

## Run Tests

```bash
pytest tests/ -v
```

## Example Output

Given this code with a known logic flaw (discount overwrite):

```python
def get_user_discount(user, cart_total):
    discount = 0
    if user.is_premium == True:
        discount = cart_total * 0.1
    if cart_total > 100:
        discount = cart_total * 0.15   # silently overwrites premium discount
    if user.loyalty_years > 5:
        discount += cart_total * 0.05
    return cart_total - discount
```

**CodeQuorum output:**

| Finding | Confidence | Call |
|---|---|---|
| `if` chain overwrites premium discount silently | 3/3 | 🔴 FIX IT |
| No validation on `cart_total` (negative values) | 2/3 | 🔴 FIX IT |
| No logging of discount applied — invisible in prod | 1/3 | 🟡 YOUR CALL |

*Verdict: Core discount logic has a silent priority bug that affects all premium users with large carts.*

## Submission

Challenge #2 — The AI Pair Engineer | Careem WorkOS FDE Application

---

*Built by Subash Natarajan*
