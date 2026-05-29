"""
Integration test — runs a known-bad code snippet through the full LangGraph pipeline.

Mocks _call_claude at the lowest level so no API key is required.
Tests the complete path: fan-out → JSON parsing → Pydantic validation → synthesis → output schema.
"""
import json
import pytest
from unittest.mock import patch

from agents import SynthesisOutput, AgentFinding


# A real-world-style buggy snippet with three distinct failure modes:
# 1. Pragmatist/Purist: discount overwrite silently ignores premium status
# 2. Operator: external payment call has no error handling
BUGGY_CODE = """
def process_payment(user, cart_total, payment_client):
    discount = cart_total * 0.15 if cart_total > 100 else 0
    if user.is_premium:
        discount = cart_total * 0.10  # overwrites bulk discount — bug
    final = cart_total - discount
    result = payment_client.charge(user.id, final)
    return result
"""

# Simulated agent responses — realistic findings each agent would return
_PRAGMATIST_FINDINGS = json.dumps([
    {
        "line": 4,
        "issue": "Premium discount always overwrites bulk discount regardless of which is larger",
        "severity": "high",
        "quote": "discount = cart_total * 0.10"
    }
])

_PURIST_FINDINGS = json.dumps([
    {
        "line": 4,
        "issue": "Assignment on line 4 contradicts the stated discount policy — premium user with cart >100 gets 10% instead of 15%",
        "severity": "high",
        "quote": "if user.is_premium: discount = cart_total * 0.10"
    }
])

_OPERATOR_FINDINGS = json.dumps([
    {
        "line": 6,
        "issue": "payment_client.charge() has no error handling — network failure or declined card raises an unhandled exception with no log",
        "severity": "high",
        "quote": "result = payment_client.charge(user.id, final)"
    }
])

_SYNTHESIS_OUTPUT = json.dumps({
    "findings": [
        {
            "issue": "Discount overwrite silently ignores bulk discount for premium users with large carts",
            "agents": ["pragmatist", "purist"],
            "confidence": "2/3",
            "call": "FIX_IT",
            "fix": "Use max() so the larger discount wins",
            "refactored_code": "discount = max(cart_total * 0.15 if cart_total > 100 else 0, cart_total * 0.10 if user.is_premium else 0)",
            "test": "def test_bulk_discount_not_overwritten():\n    user = Mock(is_premium=True)\n    assert process_payment(user, 200, mock_client) == 200 * 0.85"
        },
        {
            "issue": "External payment call has no error handling",
            "agents": ["operator"],
            "confidence": "1/3",
            "call": "YOUR_CALL",
            "fix": "Wrap in try/except and log the failure before re-raising"
        }
    ],
    "verdict": "One confirmed design flaw in discount logic. One contested observability gap.",
    "quorum_score": 0.5
})


def _make_claude_responses(*responses):
    """Return a side_effect list for sequential _call_claude mock calls."""
    return list(responses)


def test_full_graph_produces_valid_synthesis():
    """Full pipeline: fan-out agents → synthesis → Pydantic-validated output."""
    from graph import build_graph

    call_sequence = [_PRAGMATIST_FINDINGS, _PURIST_FINDINGS, _OPERATOR_FINDINGS, _SYNTHESIS_OUTPUT]

    with patch("agents._call_claude", side_effect=call_sequence):
        g = build_graph()
        synthesis = {}
        for event in g.stream({
            "code": BUGGY_CODE,
            "pragmatist": [], "purist": [], "operator": [], "synthesis": {}
        }):
            for node_name, state_update in event.items():
                if node_name == "synthesis":
                    synthesis = state_update.get("synthesis", {})

    # Validate the full output against our Pydantic schema
    parsed = SynthesisOutput(**synthesis)

    assert len(parsed.findings) == 2
    assert parsed.quorum_score == 0.5
    assert parsed.verdict != ""


def test_fix_it_finding_has_required_fields():
    """FIX_IT findings must include refactored_code and test."""
    from graph import build_graph

    call_sequence = [_PRAGMATIST_FINDINGS, _PURIST_FINDINGS, _OPERATOR_FINDINGS, _SYNTHESIS_OUTPUT]

    with patch("agents._call_claude", side_effect=call_sequence):
        g = build_graph()
        synthesis = {}
        for event in g.stream({
            "code": BUGGY_CODE,
            "pragmatist": [], "purist": [], "operator": [], "synthesis": {}
        }):
            for node_name, state_update in event.items():
                if node_name == "synthesis":
                    synthesis = state_update.get("synthesis", {})

    fix_it = [f for f in synthesis["findings"] if f["call"] == "FIX_IT"]
    assert len(fix_it) == 1
    assert fix_it[0]["refactored_code"] is not None
    assert fix_it[0]["test"] is not None
    assert fix_it[0]["confidence"] == "2/3"


def test_your_call_finding_omits_code_and_test():
    """YOUR_CALL findings must NOT include refactored_code or test."""
    from graph import build_graph

    call_sequence = [_PRAGMATIST_FINDINGS, _PURIST_FINDINGS, _OPERATOR_FINDINGS, _SYNTHESIS_OUTPUT]

    with patch("agents._call_claude", side_effect=call_sequence):
        g = build_graph()
        synthesis = {}
        for event in g.stream({
            "code": BUGGY_CODE,
            "pragmatist": [], "purist": [], "operator": [], "synthesis": {}
        }):
            for node_name, state_update in event.items():
                if node_name == "synthesis":
                    synthesis = state_update.get("synthesis", {})

    your_call = [f for f in synthesis["findings"] if f["call"] == "YOUR_CALL"]
    assert len(your_call) == 1
    assert your_call[0].get("refactored_code") is None
    assert your_call[0].get("test") is None


def test_agent_findings_validated_against_pydantic_schema():
    """Individual agent findings must pass AgentFinding validation."""
    valid = json.loads(_PRAGMATIST_FINDINGS)
    for item in valid:
        finding = AgentFinding(**item)
        assert finding.severity in ("high", "medium")
        assert finding.issue != ""


def test_invalid_agent_json_triggers_retry():
    """If first call returns garbage JSON, second call (retry) is used."""
    garbage = "not json at all {{{"
    valid_response = _PRAGMATIST_FINDINGS
    call_count = {"n": 0}

    def side_effect(system, user, max_tokens):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return garbage
        return valid_response

    from agents import call_agent, PRAGMATIST_PROMPT
    with patch("agents._call_claude", side_effect=side_effect):
        result = call_agent(PRAGMATIST_PROMPT, BUGGY_CODE)

    assert call_count["n"] == 2
    assert len(result) == 1
    assert result[0]["severity"] == "high"


def test_invalid_synthesis_json_triggers_retry():
    """If synthesis returns invalid JSON, retry fires and returns fallback on second failure."""
    from agents import call_synthesis

    with patch("agents._call_claude", return_value="{{bad json"):
        result = call_synthesis([], [], [])

    assert result["verdict"] == "Synthesis unavailable."
    assert result["findings"] == []


def test_synthesis_pydantic_validation_on_valid_output():
    """Synthesis output passes Pydantic validation with a full valid response."""
    from agents import call_synthesis

    with patch("agents._call_claude", return_value=_SYNTHESIS_OUTPUT):
        result = call_synthesis(
            json.loads(_PRAGMATIST_FINDINGS),
            json.loads(_PURIST_FINDINGS),
            json.loads(_OPERATOR_FINDINGS),
        )

    parsed = SynthesisOutput(**result)
    assert len(parsed.findings) == 2
    assert all(f.call in ("FIX_IT", "YOUR_CALL") for f in parsed.findings)
    assert 0.0 <= parsed.quorum_score <= 1.0
