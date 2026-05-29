# CodeQuorum: One-Pager

## What Is It?

CodeQuorum is an AI pair engineer that runs three specialist reviewers against your GitHub code simultaneously. Each reviewer has a different philosophy. Where they agree, you have a real bug. Where they disagree, you have a real tradeoff.

---

## How a Review Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   1                   2                    3                        │
│  Developer  ──►  GitHub OAuth   ──►   Code Loaded                  │
│  (you)           Pick any repo        (up to 10 files)             │
│                  public or private                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
             ┌──────────┐  ┌──────────┐  ┌──────────┐
             │    4a    │  │    4b    │  │    4c    │
             │🚢Pragma- │  │🎯 Purist │  │🔧Operator│
             │  tist    │  │          │  │          │
             │"Will it  │  │"Is this  │  │"Will I   │
             │ break?"  │  │ right?"  │  │ know?"   │
             └────┬─────┘  └────┬─────┘  └────┬─────┘
                  │             │             │
                  └─────────────┼─────────────┘
                          ~4 seconds
                       (all run in parallel)
                                │
                                ▼
                    ┌───────────────────────┐
                    │           5           │
                    │   ⚖️  Synthesis       │
                    │   Consensus Engine    │
                    │                       │
                    │  "Who agrees with     │
                    │   whom, and why?"     │
                    └───────────┬───────────┘
                                │
               ┌────────────────┴────────────────┐
               │                                 │
       2+ agents agree                      1 agent flags
               │                                 │
               ▼                                 ▼
    ┌─────────────────────┐          ┌─────────────────────┐
    │         6           │          │          7          │
    │   🔴  FIX IT        │          │   🟡  YOUR CALL     │
    │                     │          │                     │
    │  Issue description  │          │  Issue description  │
    │  Refactor suggest.  │          │  The tradeoff       │
    │  Failing test case  │          │  Human decides      │
    └─────────────────────┘          └─────────────────────┘
```

---

## What You Get Per Finding

| FIX IT (quorum reached) | YOUR CALL (contested) |
|---|---|
| What is wrong and why | What one reviewer saw |
| Concrete refactor suggestion | Why it might matter |
| A test that would catch this bug | The tradeoff to weigh |
| Confidence: 2/3 or 3/3 | Confidence: 1/3 |

---

## Key Design Decisions

**Why three agents with different philosophies, not one agent with three prompts?**

Philosophically distinct system prompts pull reasoning in genuinely different directions. The Pragmatist actively ignores style issues. The Operator actively ignores logic elegance. The Purist actively ignores production concerns. This creates real disagreement, not surface variation.

**Why is YOUR CALL a feature, not a failure?**

A finding that only one reviewer flags is information. It means one engineering philosophy sees a problem that the others do not. That is the definition of a tradeoff. Surfacing it explicitly is more useful than filtering it out or forcing false consensus.

**Why parallel execution?**

Three sequential LLM calls take 12 to 15 seconds. Three parallel calls take 4 to 5 seconds. At review scale, this is the difference between a tool people use and a tool people skip.

---

## Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph (fan-out/fan-in) |
| Parallel execution | Python ThreadPoolExecutor |
| LLM providers | Claude Sonnet 4.6, GPT-4o, Gemini 2.0 Flash |
| GitHub integration | OAuth 2.0, GitHub REST API |
| UI | Streamlit |

---

## Enterprise Relevance

This is a micro-implementation of the multi-agent pattern needed for enterprise WorkOS. Specialist agents, parallel execution, structured handoff, disagreement as signal. The same architecture applies to contract review, compliance checks, customer escalation triage: any domain where one AI reviewer is one point of bias.

---

*CodeQuorum by Subash Natarajan | github.com/suboss87/CodeQuorum*
