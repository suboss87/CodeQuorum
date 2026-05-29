import json
import re
from typing import Optional, Literal, List
from pydantic import BaseModel, ValidationError


# ---------------------------------------------------------------------------
# Pydantic models — single source of truth for what agents return
# ---------------------------------------------------------------------------

class AgentFinding(BaseModel):
    line: Optional[int] = None
    issue: str
    severity: Literal["high", "medium"]
    quote: str


class SynthesisFinding(BaseModel):
    issue: str
    agents: List[str]
    confidence: Literal["1/3", "2/3", "3/3"]
    call: Literal["FIX_IT", "YOUR_CALL"]
    fix: str
    refactored_code: Optional[str] = None
    test: Optional[str] = None


class SynthesisOutput(BaseModel):
    findings: List[SynthesisFinding]
    verdict: str
    quorum_score: float


# ---------------------------------------------------------------------------
# Agent prompts — explicitly adversarial so disagreement is structural
# ---------------------------------------------------------------------------

PRAGMATIST_PROMPT = """You are the Pragmatist — a senior engineer whose only measure is: will this break in production?

Your question: "Will this actually produce wrong output or crash at runtime?"

DO NOT FLAG:
- Logging or observability gaps
- Missing test coverage
- Code style, naming, or readability
- Error message quality or exception types
- Theoretical correctness debates
- Anything that won't cause a real user to see a wrong result

ONLY FLAG concrete failures:
- Logic that computes the wrong value on real inputs
- Null/zero paths that will actually trigger and crash
- Missing guards on inputs the system genuinely receives
- External calls that will fail under real conditions

Return ONLY a JSON array — no markdown fences, no explanation:
[{"line": <int or null>, "issue": "<what breaks and why>", "severity": "high|medium", "quote": "<relevant snippet>"}]

Maximum 3 findings. Return [] if the code will ship and work."""


PURIST_PROMPT = """You are the Purist — an engineer for whom correctness is non-negotiable and production concerns are someone else's problem.

Your question: "Does this code actually do what its name and comments claim?"

DO NOT FLAG:
- Performance or latency
- Error handling or exception propagation
- Logging, monitoring, or observability
- Operational concerns of any kind
- Whether it will be easy to debug if it fails

ONLY FLAG logical violations:
- Off-by-one errors and boundary condition mistakes
- Conditions that silently compute a wrong result
- Misused standard library APIs that return unexpected values
- Assumptions in the implementation that contradict the function's stated contract
- Logic that produces a correct-looking result for the happy path but wrong results on edge cases

Return ONLY a JSON array — no markdown fences, no explanation:
[{"line": <int or null>, "issue": "<what is wrong and why>", "severity": "high|medium", "quote": "<relevant snippet>"}]

Maximum 3 findings. Return [] if the logic is correct."""


OPERATOR_PROMPT = """You are the Operator — the on-call engineer paged at 3am because of code like this. Correctness is not your concern. Survivability is.

Your question: "When this fails, will I know? Can I diagnose it in 5 minutes at 3am?"

DO NOT FLAG:
- Whether the logic is correct
- Code style or naming
- Design patterns or architecture
- Test coverage
- Theoretical edge cases that produce wrong results but are still visible

ONLY FLAG invisible failure modes:
- Exceptions swallowed without logging — the operation fails and nobody knows
- External calls (HTTP, DB, file, queue) with no error handling or retry
- Resource leaks (file handles, connections) that degrade silently over time
- Inputs that reach deep into the stack unvalidated and cause cryptic internal errors
- Failure modes that are invisible until they cascade into something catastrophic

Return ONLY a JSON array — no markdown fences, no explanation:
[{"line": <int or null>, "issue": "<what fails silently and why>", "severity": "high|medium", "quote": "<relevant snippet>"}]

Maximum 3 findings. Return [] if failure modes are well-handled."""


_AGENT_SCHEMA = json.dumps([
    {"line": "<int or null>", "issue": "<string>", "severity": "high|medium", "quote": "<string>"}
], indent=2)

SYNTHESIS_PROMPT = f"""You receive code review findings from three engineers with fundamentally different value systems.
Your job: identify which design flaws are real (consensus), propose the refactored code, and propose the test.

Rules:
- If 2 or more agents flag the SAME root cause (even described differently): quorum reached → FIX_IT
- If only 1 agent flags something: genuine tradeoff → YOUR_CALL
- Merge duplicates into one canonical description
- quorum_score is the fraction of findings that reached 2/3 or 3/3 agreement

Return ONLY valid JSON matching this exact schema (no markdown fences, no extra keys):
{{
  "findings": [
    {{
      "issue": "<canonical description of the root cause>",
      "agents": ["pragmatist"|"purist"|"operator", ...],
      "confidence": "1/3"|"2/3"|"3/3",
      "call": "FIX_IT"|"YOUR_CALL",
      "fix": "<one-sentence fix description>",
      "refactored_code": "<corrected code as a single string, \\n for newlines — FIX_IT only, omit for YOUR_CALL>",
      "test": "<one concrete failing test — FIX_IT only, omit for YOUR_CALL>"
    }}
  ],
  "verdict": "<one sentence summary of findings>",
  "quorum_score": <float 0.0-1.0>
}}

Field constraints:
- confidence: exactly "3/3", "2/3", or "1/3"
- call: exactly "FIX_IT" or "YOUR_CALL"
- quorum_score: float between 0.0 and 1.0
- refactored_code and test: present only when call is "FIX_IT", absent for "YOUR_CALL\""""


# ---------------------------------------------------------------------------
# LLM call + validation
# ---------------------------------------------------------------------------

def _call_claude(system: str, user: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text


def _parse_json(text: str, fallback):
    """Parse JSON from LLM output, stripping markdown fences."""
    try:
        return json.loads(_strip_fences(text))
    except json.JSONDecodeError:
        return fallback


def _parse_and_validate_findings(text: str) -> list[dict]:
    """Parse agent JSON and validate each finding against AgentFinding schema.
    Returns only the findings that pass validation."""
    raw = _parse_json(text, [])
    if not isinstance(raw, list):
        return []
    validated = []
    for item in raw:
        try:
            validated.append(AgentFinding(**item).model_dump())
        except (ValidationError, TypeError):
            pass
    return validated


def _parse_and_validate_synthesis(text: str) -> dict:
    """Parse synthesis JSON and validate against SynthesisOutput schema.
    On failure, retry once with a correction prompt that embeds the schema."""
    raw = _parse_json(text, None)
    if raw is not None:
        try:
            return SynthesisOutput(**raw).model_dump()
        except (ValidationError, TypeError):
            pass
    return None


def call_agent(system_prompt: str, code: str) -> list[dict]:
    text = _call_claude(system_prompt, f"```\n{code}\n```", 1024)
    findings = _parse_and_validate_findings(text)
    if not findings:
        # Retry once with explicit schema reminder
        correction = (
            f"Your previous response could not be parsed as a JSON array. "
            f"Return ONLY a raw JSON array matching this schema:\n{_AGENT_SCHEMA}\n\n"
            f"Original code:\n```\n{code}\n```"
        )
        text = _call_claude(system_prompt, correction, 1024)
        findings = _parse_and_validate_findings(text)
    return findings


def call_synthesis(pragmatist: list, purist: list, operator: list) -> dict:
    fallback = {"findings": [], "verdict": "Synthesis unavailable.", "quorum_score": 0.0}
    payload = json.dumps({"pragmatist": pragmatist, "purist": purist, "operator": operator}, indent=2)
    text = _call_claude(SYNTHESIS_PROMPT, payload, 2048)
    result = _parse_and_validate_synthesis(text)
    if result is not None:
        return result
    # Retry once — embed schema in the correction prompt
    correction = (
        f"Your previous response was not valid JSON or did not match the required schema. "
        f"Return ONLY valid JSON matching the schema defined in the system prompt.\n\n"
        f"Findings to synthesise:\n{payload}"
    )
    text = _call_claude(SYNTHESIS_PROMPT, correction, 2048)
    result = _parse_and_validate_synthesis(text)
    return result if result is not None else fallback
