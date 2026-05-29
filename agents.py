import json
import re
import os

MODELS = {
    "Claude Sonnet 4.6": "claude-sonnet-4-6",
    "GPT-4o":            "gpt-4o",
    "Gemini 2.0 Flash":  "gemini-2.0-flash",
}
DEFAULT_MODEL = "claude-sonnet-4-6"

PRAGMATIST_PROMPT = """You are the Pragmatist, a senior engineer who values shipping working software.
You ask: "Is this actually broken? Would I block this PR?"

Flag only issues that WILL produce wrong behaviour or failures in production.
Ignore style, theoretical concerns, and "could be cleaner" notes.
Focus on: logic that produces wrong output, null/error paths that WILL trigger,
missing guards on real inputs, or calls that will actually fail.

Return ONLY a JSON array (no markdown fences, no explanation):
[{"line": <int or null>, "issue": "<what breaks and why>", "severity": "high|medium", "quote": "<relevant snippet>"}]

Maximum 3 findings. Return [] if code is shippable."""

PURIST_PROMPT = """You are the Purist, an engineer for whom correctness and clarity are non-negotiable.
You ask: "Does this code actually do what it claims? Is the intent honest?"

Flag: logical errors, off-by-one mistakes, conditions that silently produce wrong results,
hallucinated or misused API methods, assumptions that contradict the code's stated purpose,
and implementation that obscures rather than reveals intent.

Return ONLY a JSON array (no markdown fences, no explanation):
[{"line": <int or null>, "issue": "<what is wrong and why>", "severity": "high|medium", "quote": "<relevant snippet>"}]

Maximum 3 findings. Return [] if code is correct."""

OPERATOR_PROMPT = """You are the Operator, the on-call engineer paged at 3am because of code like this.
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
- If 2 or more agents flag the SAME root cause (even described differently): quorum reached, call is FIX_IT
- If only 1 agent flags something: contested, call is YOUR_CALL (a real tradeoff, not a clear bug)
- Merge duplicate findings into one canonical description
- The quorum_score is the fraction of findings that reached 2/3 or 3/3 agreement

Return ONLY valid JSON (no markdown fences, no extra text). Example structure:
{
  "findings": [
    {
      "issue": "Discount overwrite silently ignores premium status",
      "agents": ["pragmatist", "purist"],
      "confidence": "2/3",
      "call": "FIX_IT",
      "fix": "Use elif or combine conditions to preserve premium discount",
      "test": "assert get_user_discount(premium_user, 150) > get_user_discount(regular_user, 150)"
    }
  ],
  "verdict": "Silent logic bug affects all premium users with large carts.",
  "quorum_score": 0.67
}

Rules for field values:
- confidence: must be exactly "3/3", "2/3", or "1/3"
- call: must be exactly "FIX_IT" or "YOUR_CALL"
- quorum_score: float 0.0 to 1.0, fraction of findings at 2/3 or higher
- agents: list containing only the names that flagged this issue
- test: for FIX_IT findings only, one concrete test case that would catch this bug. For YOUR_CALL, omit this field."""


def _parse_json(text: str, fallback):
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


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


def _call_openai(system: str, user: str, max_tokens: int) -> str:
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content


def _call_gemini(system: str, user: str, max_tokens: int) -> str:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system,
    )
    response = model.generate_content(
        user,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
    )
    return response.text


def _llm_call(model: str, system: str, user: str, max_tokens: int) -> str:
    if model.startswith("claude"):
        return _call_claude(system, user, max_tokens)
    elif model.startswith("gpt"):
        return _call_openai(system, user, max_tokens)
    elif model.startswith("gemini"):
        return _call_gemini(system, user, max_tokens)
    raise ValueError(f"Unknown model: {model}")


def call_agent(system_prompt: str, code: str, model: str = DEFAULT_MODEL) -> list[dict]:
    text = _llm_call(model, system_prompt, f"```\n{code}\n```", 1024)
    return _parse_json(text, [])


def call_synthesis(pragmatist: list, purist: list, operator: list, model: str = DEFAULT_MODEL) -> dict:
    payload = json.dumps({"pragmatist": pragmatist, "purist": purist, "operator": operator}, indent=2)
    text = _llm_call(model, SYNTHESIS_PROMPT, payload, 2048)
    return _parse_json(
        text,
        {"findings": [], "verdict": "Synthesis unavailable.", "quorum_score": 0.0},
    )
