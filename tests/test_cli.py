from cli import findings_to_markdown


SAMPLE_SYNTHESIS = {
    "findings": [
        {
            "issue": "Discount logic overwrites premium status silently",
            "agents": ["pragmatist", "purist"],
            "confidence": "2/3",
            "call": "FIX_IT",
            "fix": "Use max() so larger discount wins, then stack loyalty bonus",
            "refactored_code": "def get_discount(user, total):\n    d = max(total*0.15 if total>100 else 0, total*0.10 if user.is_premium else 0)\n    return d",
            "test": "def test_premium_not_overwritten():\n    assert get_discount(premium_user, 120) >= 0.10 * 120",
        },
        {
            "issue": "No audit log when discount is applied",
            "agents": ["operator"],
            "confidence": "1/3",
            "call": "YOUR_CALL",
            "fix": "Add logging if this feeds into billing",
        },
    ],
    "verdict": "One confirmed design flaw. One design tradeoff.",
    "quorum_score": 0.5,
}


def test_markdown_contains_fix_section():
    md = findings_to_markdown("my-repo (2 files)", SAMPLE_SYNTHESIS)
    assert "🔴 Fix It" in md


def test_markdown_contains_your_call_section():
    md = findings_to_markdown("my-repo (2 files)", SAMPLE_SYNTHESIS)
    assert "🟡 Your Call" in md


def test_markdown_contains_refactored_code():
    md = findings_to_markdown("my-repo (2 files)", SAMPLE_SYNTHESIS)
    assert "Refactored" in md
    assert "get_discount" in md


def test_markdown_contains_proposed_test():
    md = findings_to_markdown("my-repo (2 files)", SAMPLE_SYNTHESIS)
    assert "Proposed test" in md
    assert "test_premium_not_overwritten" in md


def test_markdown_contains_verdict():
    md = findings_to_markdown("my-repo (2 files)", SAMPLE_SYNTHESIS)
    assert "One confirmed design flaw" in md


def test_markdown_contains_source_label():
    md = findings_to_markdown("my-repo (2 files)", SAMPLE_SYNTHESIS)
    assert "my-repo (2 files)" in md


def test_empty_synthesis_no_sections():
    md = findings_to_markdown("empty-repo", {"findings": [], "verdict": "", "quorum_score": 0.0})
    assert "### 🔴 Fix It" not in md
    assert "### 🟡 Your Call" not in md


def test_fix_it_shows_agent_icons():
    md = findings_to_markdown("repo", SAMPLE_SYNTHESIS)
    assert "🚢" in md
    assert "🎯" in md


def test_your_call_shows_operator_icon():
    md = findings_to_markdown("repo", SAMPLE_SYNTHESIS)
    assert "🔧" in md
