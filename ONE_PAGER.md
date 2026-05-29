# CodeQuorum: One-Pager

## What Is It?

An AI that codes alongside developers — detecting design flaws, proposing tests, and refactoring. Add one YAML file and every pull request is automatically reviewed by three specialist agents running in parallel. Results are posted as a PR comment. No UI, no manual step.

---

## How It Works

```
  Developer               GitHub Action               Three Agents (parallel, ~4s)
  opens a PR    ──────►   triggers on PR    ──────►   ┌─────────────────────────┐
                           git diff identifies          │ 🚢 Pragmatist           │
                           only changed files           │    Will this break?     │
                                                        │                         │
                                                        │ 🎯 Purist               │
                                                        │    Is this correct?     │
                                                        │                         │
                                                        │ 🔧 Operator             │
                                                        │    Will I know it fails?│
                                                        └─────────────────────────┘
                                                                    │
                                                                    ▼
                                                        ┌─────────────────────────┐
                                                        │  ⚖️  Synthesis           │
                                                        │  Compares all findings  │
                                                        │  "Same root cause?"     │
                                                        └────────────┬────────────┘
                                                                     │
                                          ┌──────────────────────────┴────────────────────────┐
                                          │                                                   │
                                   2+ agents agreed                                    1 agent flagged
                                          │                                                   │
                                          ▼                                                   ▼
                               ┌─────────────────────┐                          ┌─────────────────────┐
                               │  🔴 FIX IT           │                          │  🟡 YOUR CALL       │
                               │  Design flaw         │                          │  Design tradeoff    │
                               │  Refactored code     │                          │  Human decides      │
                               │  Proposed test       │                          └─────────────────────┘
                               └─────────────────────┘
                                          │
                                          ▼
                               💬 Posted as PR comment
```

---

## What You Get Per Finding

| 🔴 FIX IT — quorum reached (2+ agents) | 🟡 YOUR CALL — contested (1 agent) |
|---|---|
| What is wrong and why | What one reviewer noticed |
| Refactored code that fixes the flaw | The design tradeoff to weigh |
| A test that would have caught the bug | Human decides |
| Confidence: 2/3 or 3/3 | Confidence: 1/3 |

---

## Key Design Decisions

**Why three agents with different philosophies?**

Philosophically distinct system prompts pull reasoning in genuinely different directions. The Pragmatist actively ignores style. The Operator ignores logic elegance. The Purist ignores production concerns. This creates real disagreement — not surface variation — which is how you separate confirmed design flaws from genuine tradeoffs.

**Why consensus for confidence?**

An LLM cannot reliably rate its own certainty. But when two or three agents with fundamentally different priorities all flag the same root cause, that convergence is meaningful. Confidence comes from inter-agent agreement, not self-assessment.

**Why parallel execution?**

Three sequential LLM calls take 12–15 seconds. Three parallel calls take 4–5 seconds. At review scale, this is the difference between a tool people use and one they skip.

**Why review only changed files on a PR?**

`git diff origin/{base}...HEAD` identifies exactly what changed. Reviewing only those files keeps the feedback tight, relevant, and fast — not a re-audit of the whole codebase.

---

## Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph (fan-out / fan-in) |
| Parallel execution | Python ThreadPoolExecutor |
| LLM | Claude Sonnet 4.6 |
| GitHub integration | GitHub Actions, GitHub REST API, OAuth 2.0 |
| Interactive UI | Streamlit (optional) |

---

*CodeQuorum by Subash Natarajan · github.com/suboss87/CodeQuorum*
