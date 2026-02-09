"""Tests for the AI color correction module."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest
from PIL import Image

from vedos.ai_correction import (
    apply_corrections,
    generate_preview_jpeg,
    parse_correction_json,
)
from vedos.models import (
    AICorrectionParams,
    ChannelCurve,
    CurvesAdjustment,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_uint16_image() -> np.ndarray:
    """A small synthetic 16-bit RGB image with a gradient."""
    h, w = 100, 150
    ramp = np.linspace(0, 65535, w, dtype=np.uint16)
    channel = np.tile(ramp, (h, 1))
    return np.stack([channel, channel, channel], axis=-1)


@pytest.fixture
def neutral_corrections() -> AICorrectionParams:
    """Corrections that should leave the image unchanged."""
    return AICorrectionParams()


# ---------------------------------------------------------------------------
# generate_preview_jpeg
# ---------------------------------------------------------------------------

class TestGeneratePreviewJpeg:
    def test_creates_valid_jpeg(self, synthetic_uint16_image: np.ndarray):
        path = generate_preview_jpeg(synthetic_uint16_image)
        try:
            assert os.path.exists(path)
            img = Image.open(path)
            assert img.format == "JPEG"
            assert img.mode == "RGB"
        finally:
            os.unlink(path)

    def test_respects_max_size(self, synthetic_uint16_image: np.ndarray):
        path = generate_preview_jpeg(synthetic_uint16_image, max_size=50)
        try:
            img = Image.open(path)
            assert max(img.size) <= 50
        finally:
            os.unlink(path)

    def test_handles_uint8_input(self):
        img = np.full((80, 120, 3), 128, dtype=np.uint8)
        path = generate_preview_jpeg(img)
        try:
            assert os.path.exists(path)
            pil = Image.open(path)
            assert pil.format == "JPEG"
        finally:
            os.unlink(path)

    def test_handles_float_input(self):
        img = np.random.rand(60, 90, 3).astype(np.float32)
        path = generate_preview_jpeg(img)
        try:
            assert os.path.exists(path)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# parse_correction_json
# ---------------------------------------------------------------------------

SAMPLE_AI_RESPONSE = json.dumps({
    "white_balance_shift_kelvin": 300,
    "tint_shift": -0.15,
    "exposure_compensation": 0.5,
    "channel_curves": {
        "red":   {"shadows": 0.05, "midtones": 0.0,  "highlights": -0.02},
        "green": {"shadows": 0.0,  "midtones": 0.02, "highlights": 0.0},
        "blue":  {"shadows": -0.1, "midtones": 0.0,  "highlights": 0.05},
    },
    "saturation_adjustment": 0.1,
    "analysis_notes": "Slight orange cast in shadows from film base.",
})


class TestParseCorrectionJson:
    def test_parses_plain_json(self):
        params = parse_correction_json(SAMPLE_AI_RESPONSE)
        assert isinstance(params, AICorrectionParams)
        assert params.white_balance_shift == pytest.approx(300.0)  # raw Kelvin
        assert params.tint_shift == pytest.approx(-0.15)
        assert params.exposure_compensation == pytest.approx(0.5)
        assert params.curves.r.shadows == pytest.approx(0.05)
        assert params.curves.b.shadows == pytest.approx(-0.1)
        assert params.saturation_adjustment == pytest.approx(0.1)
        assert "orange" in params.analysis_notes.lower()

    def test_parses_markdown_fenced_json(self):
        text = "Here are my suggestions:\n```json\n" + SAMPLE_AI_RESPONSE + "\n```\n"
        params = parse_correction_json(text)
        assert params.exposure_compensation == pytest.approx(0.5)

    def test_parses_json_with_surrounding_text(self):
        text = "I found issues. " + SAMPLE_AI_RESPONSE + " Hope this helps!"
        params = parse_correction_json(text)
        assert params.tint_shift == pytest.approx(-0.15)

    def test_returns_defaults_on_no_json(self):
        params = parse_correction_json("No corrections needed, the image looks great!")
        assert isinstance(params, AICorrectionParams)
        assert "ERROR" in params.analysis_notes

    def test_handles_missing_optional_fields(self):
        minimal = json.dumps({
            "white_balance_shift_kelvin": 0,
            "tint_shift": 0.0,
            "exposure_compensation": 0.0,
            "channel_curves": {
                "red": {}, "green": {}, "blue": {}
            },
            "saturation_adjustment": 0.0,
            "analysis_notes": "",
        })
        params = parse_correction_json(minimal)
        assert params.curves.r.shadows == 0.0


# ---------------------------------------------------------------------------
# apply_corrections
# ---------------------------------------------------------------------------

class TestApplyCorrections:
    def test_neutral_corrections_preserve_image(
        self,
        synthetic_uint16_image: np.ndarray,
        neutral_corrections: AICorrectionParams,
    ):
        result = apply_corrections(synthetic_uint16_image, neutral_corrections)
        assert result.dtype == np.uint16
        assert result.shape == synthetic_uint16_image.shape
        np.testing.assert_array_equal(result, synthetic_uint16_image)

    def test_output_dtype_and_shape(self, synthetic_uint16_image: np.ndarray):
        corrections = AICorrectionParams(
            white_balance_shift=2.0,
            tint_shift=0.1,
            exposure_compensation=0.3,
            saturation_adjustment=0.1,
        )
        result = apply_corrections(synthetic_uint16_image, corrections)
        assert result.dtype == np.uint16
        assert result.shape == synthetic_uint16_image.shape

    def test_exposure_brightens_image(self, synthetic_uint16_image: np.ndarray):
        bright = AICorrectionParams(exposure_compensation=1.0)
        result = apply_corrections(synthetic_uint16_image, bright)
        # Non-zero pixels should be brighter (or clipped at max)
        mask = synthetic_uint16_image > 0
        assert np.all(result[mask] >= synthetic_uint16_image[mask])

    def test_exposure_darkens_image(self, synthetic_uint16_image: np.ndarray):
        dark = AICorrectionParams(exposure_compensation=-1.0)
        result = apply_corrections(synthetic_uint16_image, dark)
        assert np.all(result <= synthetic_uint16_image)

    def test_clipping_stays_in_range(self):
        bright_img = np.full((10, 10, 3), 60000, dtype=np.uint16)
        corrections = AICorrectionParams(exposure_compensation=2.0)
        result = apply_corrections(bright_img, corrections)
        assert result.max() <= 65535

    def test_curves_adjustment(self, synthetic_uint16_image: np.ndarray):
        corrections = AICorrectionParams(
            curves=CurvesAdjustment(
                r=ChannelCurve(shadows=0.1, midtones=0.05, highlights=0.0),
                g=ChannelCurve(),
                b=ChannelCurve(shadows=-0.1, midtones=0.0, highlights=0.1),
            )
        )
        result = apply_corrections(synthetic_uint16_image, corrections)
        assert result.dtype == np.uint16
        assert result.shape == synthetic_uint16_image.shape

    def test_saturation_adjustment(self):
        # Image with some colour variation
        img = np.zeros((10, 10, 3), dtype=np.uint16)
        img[:, :, 0] = 40000  # red-ish
        img[:, :, 1] = 30000
        img[:, :, 2] = 20000
        corrections = AICorrectionParams(saturation_adjustment=0.3)
        result = apply_corrections(img, corrections)
        assert result.dtype == np.uint16

    def test_white_balance_shift(self, synthetic_uint16_image: np.ndarray):
        corrections = AICorrectionParams(white_balance_shift=500.0)
        result = apply_corrections(synthetic_uint16_image, corrections)
        # Red should be boosted, blue reduced for positive shift
        mid = synthetic_uint16_image.shape[1] // 2
        mid_row = synthetic_uint16_image.shape[0] // 2
        orig_r = synthetic_uint16_image[mid_row, mid, 0]
        if orig_r > 0:
            assert result[mid_row, mid, 0] >= orig_r

    def test_extreme_corrections_no_nan(self, synthetic_uint16_image: np.ndarray):
        corrections = AICorrectionParams(
            white_balance_shift=3000.0,
            tint_shift=50.0,
            exposure_compensation=2.0,
            curves=CurvesAdjustment(
                r=ChannelCurve(shadows=50, midtones=50, highlights=50),
                g=ChannelCurve(shadows=-50, midtones=-50, highlights=-50),
                b=ChannelCurve(shadows=50, midtones=-50, highlights=50),
            ),
            saturation_adjustment=50.0,
        )
        result = apply_corrections(synthetic_uint16_image, corrections)
        assert result.dtype == np.uint16
        assert not np.any(np.isnan(result.astype(np.float64)))
        assert result.max() <= 65535

    def test_extreme_negative_corrections(self):
        img = np.full((10, 10, 3), 32768, dtype=np.uint16)
        corrections = AICorrectionParams(
            white_balance_shift=-3000.0,
            tint_shift=-50.0,
            exposure_compensation=-2.0,
            saturation_adjustment=-50.0,
        )
        result = apply_corrections(img, corrections)
        assert result.dtype == np.uint16
        assert result.min() >= 0
        assert result.max() <= 65535
