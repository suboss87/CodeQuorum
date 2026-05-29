import json
import anthropic

MODEL = "claude-sonnet-4-6"

PRAGMATIST_PROMPT = """You are the Pragmatist — a senior engineer who values shipping working software.
You ask: "Is this actually broken? Would I block this PR?"

Flag only issues that WILL produce wrong behaviour or failures in production.
Ignore style, theoretical concerns, and "could be cleaner" notes.
Focus on: logic that produces wrong output, null/error paths that WILL trigger,
missing guards on real inputs, or calls that will actually fail.

Return ONLY a JSON array (no markdown fences, no explanation):
[{"line": <int or null>, "issue": "<what breaks and why>", "severity": "high|medium", "quote": "<relevant snippet>"}]

Maximum 3 findings. Return [] if code is shippable."""

PURIST_PROMPT = """You are the Purist — an engineer for whom correctness and clarity are non-negotiable.
You ask: "Does this code actually do what it claims? Is the intent honest?"

Flag: logical errors, off-by-one mistakes, conditions that silently produce wrong results,
hallucinated or misused API methods, assumptions that contradict the code's stated purpose,
and implementation that obscures rather than reveals intent.

Return ONLY a JSON array (no markdown fences, no explanation):
[{"line": <int or null>, "issue": "<what is wrong and why>", "severity": "high|medium", "quote": "<relevant snippet>"}]

Maximum 3 findings. Return [] if code is correct."""

OPERATOR_PROMPT = """You are the Operator — the on-call engineer paged at 3am because of code like this.
You ask: "When this fails in production, will I know? Can I fix it fast?"

Flag: silent failures with no logging, missing error handling on external calls,
resource leaks, operations that timeout under load, unvalidated inputs that reach
deep into the stack, and failure modes that are invisible until they cascade.

Return ONLY a JSON array (no markdown fences, no explanation):
[{"line": <int or null>, "issue": "<what fails silently and why>", "severity": "high|medium", "quote": "<relevant snippet>"}]

Maximum 3 findings. Return [] if failure modes are well-handled."""

SYNTHESIS_PROMPT = """You receive code review findings from three engineers with fundamentally different value systems.
Your job: identify consensus and surface genuine conflict.

Rules:
- If 2 or more agents flag the SAME root cause (even described differently): quorum reached → FIX_IT
- If only 1 agent flags something: contested → YOUR_CALL (a real tradeoff, not a clear bug)
- Merge duplicate findings into one canonical description
- The quorum_score is the fraction of findings that reached 2/3 or 3/3 agreement

Return ONLY this JSON (no markdown fences):
{
  "findings": [
    {
      "issue": "<merged, canonical description>",
      "agents": ["pragmatist", "purist", "operator"],
      "confidence": "3/3" | "2/3" | "1/3",
      "call": "FIX_IT" | "YOUR_CALL",
      "fix": "<one-line concrete suggestion>"
    }
  ],
  "verdict": "<one sentence: what this code's main risk is>",
  "quorum_score": <float 0.0 to 1.0>
}"""


def _parse_json(text: str, fallback):
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def call_agent(system_prompt: str, code: str) -> list[dict]:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": f"```\n{code}\n```"}],
    )
    return _parse_json(response.content[0].text, [])


def call_synthesis(pragmatist: list, purist: list, operator: list) -> dict:
    client = anthropic.Anthropic()
    payload = json.dumps({"pragmatist": pragmatist, "purist": purist, "operator": operator}, indent=2)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYNTHESIS_PROMPT,
        messages=[{"role": "user", "content": payload}],
    )
    return _parse_json(
        response.content[0].text,
        {"findings": [], "verdict": "Synthesis unavailable.", "quorum_score": 0.0},
    )
