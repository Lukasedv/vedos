"""Tests for the AI prompt, JSON parsing, and value clamping."""

from __future__ import annotations

import json

import pytest

from vedos.ai_correction import (
    ANALYSIS_PROMPT,
    REFINE_PROMPT,
    parse_correction_response,
)
from vedos.models import AICorrectionParams


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_RESPONSE = json.dumps(
    {
        "white_balance_shift_kelvin": 500,
        "tint_shift": -5.0,
        "exposure_compensation": 0.3,
        "channel_curves": {
            "red": {"shadows": 10, "midtones": 0, "highlights": -5},
            "green": {"shadows": 0, "midtones": 3, "highlights": 0},
            "blue": {"shadows": -15, "midtones": 0, "highlights": 8},
        },
        "saturation_adjustment": 12.0,
        "analysis_notes": "Slight warm cast in shadows, minor blue lift in highlights.",
    }
)


# ---------------------------------------------------------------------------
# Prompt content checks
# ---------------------------------------------------------------------------


class TestPromptContent:
    def test_analysis_prompt_mentions_negative(self):
        assert "film negative" in ANALYSIS_PROMPT.lower()

    def test_analysis_prompt_mentions_artifacts(self):
        assert "orange mask" in ANALYSIS_PROMPT.lower()
        assert "uneven fading" in ANALYSIS_PROMPT.lower()
        assert "scanner" in ANALYSIS_PROMPT.lower()
        assert "shadow tinting" in ANALYSIS_PROMPT.lower()

    def test_analysis_prompt_requests_json_only(self):
        assert "ONLY" in ANALYSIS_PROMPT
        assert "markdown" in ANALYSIS_PROMPT.lower()

    def test_analysis_prompt_conservative(self):
        assert "conservative" in ANALYSIS_PROMPT.lower()

    def test_refine_prompt_mentions_delta(self):
        assert "delta" in REFINE_PROMPT.lower()


# ---------------------------------------------------------------------------
# parse_correction_response
# ---------------------------------------------------------------------------


class TestParseCorrectionResponse:
    def test_valid_json(self):
        params = parse_correction_response(VALID_RESPONSE)
        assert isinstance(params, AICorrectionParams)
        assert params.white_balance_shift == pytest.approx(500.0)  # raw Kelvin
        assert params.tint_shift == pytest.approx(-5.0)
        assert params.exposure_compensation == pytest.approx(0.3)
        assert params.curves.r.shadows == pytest.approx(10.0)
        assert params.curves.b.shadows == pytest.approx(-15.0)
        assert params.saturation_adjustment == pytest.approx(12.0)
        assert "warm" in params.analysis_notes.lower()

    def test_json_in_markdown_code_block(self):
        text = "Here is my analysis:\n```json\n" + VALID_RESPONSE + "\n```\nHope this helps."
        params = parse_correction_response(text)
        assert params.exposure_compensation == pytest.approx(0.3)
        assert params.curves.g.midtones == pytest.approx(3.0)

    def test_json_in_bare_code_block(self):
        text = "```\n" + VALID_RESPONSE + "\n```"
        params = parse_correction_response(text)
        assert params.tint_shift == pytest.approx(-5.0)

    def test_json_surrounded_by_text(self):
        text = "I found some issues. " + VALID_RESPONSE + " Let me know if you need more."
        params = parse_correction_response(text)
        assert params.saturation_adjustment == pytest.approx(12.0)

    def test_invalid_json_returns_defaults(self):
        params = parse_correction_response("{ this is not valid json }")
        assert isinstance(params, AICorrectionParams)
        assert "ERROR" in params.analysis_notes

    def test_no_json_returns_defaults(self):
        params = parse_correction_response("The image looks perfectly fine, no corrections needed.")
        assert isinstance(params, AICorrectionParams)
        assert "ERROR" in params.analysis_notes
        # All numeric values should be defaults (0)
        assert params.white_balance_shift == 0.0
        assert params.tint_shift == 0.0
        assert params.exposure_compensation == 0.0


# ---------------------------------------------------------------------------
# Value clamping
# ---------------------------------------------------------------------------


class TestValueClamping:
    def test_white_balance_clamped(self):
        data = json.dumps(
            {
                "white_balance_shift_kelvin": 5000,  # over +3000 max → clamped to 3000
                "tint_shift": 0,
                "exposure_compensation": 0,
                "channel_curves": {"red": {}, "green": {}, "blue": {}},
                "saturation_adjustment": 0,
                "analysis_notes": "",
            }
        )
        params = parse_correction_response(data)
        assert params.white_balance_shift <= 3000.0

    def test_negative_white_balance_clamped(self):
        data = json.dumps(
            {
                "white_balance_shift_kelvin": -5000,
                "tint_shift": 0,
                "exposure_compensation": 0,
                "channel_curves": {"red": {}, "green": {}, "blue": {}},
                "saturation_adjustment": 0,
                "analysis_notes": "",
            }
        )
        params = parse_correction_response(data)
        assert params.white_balance_shift >= -3000.0

    def test_tint_clamped(self):
        data = json.dumps(
            {
                "white_balance_shift_kelvin": 0,
                "tint_shift": 100.0,
                "exposure_compensation": 0,
                "channel_curves": {"red": {}, "green": {}, "blue": {}},
                "saturation_adjustment": 0,
                "analysis_notes": "",
            }
        )
        params = parse_correction_response(data)
        assert params.tint_shift <= 50.0

    def test_exposure_clamped(self):
        data = json.dumps(
            {
                "white_balance_shift_kelvin": 0,
                "tint_shift": 0,
                "exposure_compensation": 5.0,
                "channel_curves": {"red": {}, "green": {}, "blue": {}},
                "saturation_adjustment": 0,
                "analysis_notes": "",
            }
        )
        params = parse_correction_response(data)
        assert params.exposure_compensation <= 2.0

    def test_channel_curves_clamped(self):
        data = json.dumps(
            {
                "white_balance_shift_kelvin": 0,
                "tint_shift": 0,
                "exposure_compensation": 0,
                "channel_curves": {
                    "red": {"shadows": 100, "midtones": -100, "highlights": 0},
                    "green": {"shadows": 0, "midtones": 0, "highlights": 0},
                    "blue": {"shadows": 0, "midtones": 0, "highlights": 0},
                },
                "saturation_adjustment": 0,
                "analysis_notes": "",
            }
        )
        params = parse_correction_response(data)
        assert params.curves.r.shadows <= 50.0
        assert params.curves.r.midtones >= -50.0

    def test_saturation_clamped(self):
        data = json.dumps(
            {
                "white_balance_shift_kelvin": 0,
                "tint_shift": 0,
                "exposure_compensation": 0,
                "channel_curves": {"red": {}, "green": {}, "blue": {}},
                "saturation_adjustment": -99.0,
                "analysis_notes": "",
            }
        )
        params = parse_correction_response(data)
        assert params.saturation_adjustment >= -50.0
