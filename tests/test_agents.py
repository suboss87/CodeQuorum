import json
import pytest
from agents import _parse_json


def test_parse_clean_json_array():
    raw = '[{"line": 5, "issue": "silent overwrite", "severity": "high", "quote": "x = 1"}]'
    result = _parse_json(raw, [])
    assert isinstance(result, list)
    assert result[0]["severity"] == "high"


def test_parse_fenced_json():
    raw = '```json\n[{"line": 1, "issue": "test", "severity": "medium", "quote": "y"}]\n```'
    result = _parse_json(raw, [])
    assert len(result) == 1
    assert result[0]["line"] == 1


def test_parse_invalid_returns_fallback():
    result = _parse_json("not valid json at all {{", [])
    assert result == []


def test_parse_synthesis_shape():
    raw = json.dumps({
        "findings": [{"issue": "x", "agents": ["pragmatist"], "confidence": "1/3", "call": "YOUR_CALL", "fix": "do y"}],
        "verdict": "One contested finding.",
        "quorum_score": 0.0
    })
    result = _parse_json(raw, {})
    assert result["quorum_score"] == 0.0
    assert result["findings"][0]["call"] == "YOUR_CALL"


def test_empty_findings_return_empty_list():
    result = _parse_json("[]", [])
    assert result == []
