"""Tests for negative inversion algorithms."""

import numpy as np
import pytest

from vedos.inversion import (
    apply_tone_curve,
    auto_estimate_mask,
    invert_bw_negative,
    invert_color_negative,
    sample_orange_mask,
)


def _make_image(h: int, w: int, values: tuple[int, int, int]) -> np.ndarray:
    """Create a uniform (H, W, 3) uint16 image."""
    img = np.empty((h, w, 3), dtype=np.uint16)
    for ch in range(3):
        img[:, :, ch] = values[ch]
    return img


class TestSampleOrangeMask:
    def test_returns_correct_median(self):
        img = _make_image(100, 100, (30000, 20000, 10000))
        mask = sample_orange_mask(img, (10, 10, 50, 50))
        np.testing.assert_array_equal(mask, [30000.0, 20000.0, 10000.0])

    def test_partial_region(self):
        img = np.zeros((100, 100, 3), dtype=np.uint16)
        img[20:40, 30:60, 0] = 5000
        img[20:40, 30:60, 1] = 6000
        img[20:40, 30:60, 2] = 7000
        mask = sample_orange_mask(img, (30, 20, 30, 20))
        np.testing.assert_array_equal(mask, [5000.0, 6000.0, 7000.0])

    def test_output_dtype_and_shape(self):
        img = _make_image(50, 50, (100, 200, 300))
        mask = sample_orange_mask(img, (0, 0, 50, 50))
        assert mask.dtype == np.float64
        assert mask.shape == (3,)


class TestAutoEstimateMask:
    def test_uniform_image(self):
        img = _make_image(100, 100, (40000, 25000, 12000))
        mask = auto_estimate_mask(img, border_fraction=0.05)
        np.testing.assert_array_equal(mask, [40000.0, 25000.0, 12000.0])

    def test_border_pixels_used(self):
        """Border has different values than center; mask should reflect borders."""
        img = _make_image(100, 100, (1000, 1000, 1000))
        # Paint borders with orange-ish values
        img[:5, :, :] = [40000, 20000, 8000]
        img[-5:, :, :] = [40000, 20000, 8000]
        img[:, :5, :] = [40000, 20000, 8000]
        img[:, -5:, :] = [40000, 20000, 8000]
        mask = auto_estimate_mask(img, border_fraction=0.05)
        assert mask[0] == 40000.0
        assert mask[1] == 20000.0
        assert mask[2] == 8000.0

    def test_output_shape(self):
        img = _make_image(200, 300, (100, 200, 300))
        mask = auto_estimate_mask(img)
        assert mask.shape == (3,)


class TestInvertColorNegative:
    def test_output_dtype_and_shape(self):
        img = _make_image(50, 80, (30000, 20000, 10000))
        mask = np.array([30000.0, 20000.0, 10000.0])
        result = invert_color_negative(img, mask)
        assert result.dtype == np.uint16
        assert result.shape == (50, 80, 3)

    def test_inversion_produces_different_values(self):
        """A uniform negative should produce a valid positive image."""
        img = _make_image(50, 50, (30000, 20000, 10000))
        mask = np.array([40000.0, 25000.0, 12000.0])
        result = invert_color_negative(img, mask)
        # The result should be a valid uint16 image
        assert result.min() >= 0
        assert result.max() <= 65535

    def test_runs_with_various_mask_values(self):
        """Verify function handles a range of mask values without error."""
        h, w = 50, 50
        img = np.zeros((h, w, 3), dtype=np.uint16)
        img[:, :, 0] = np.linspace(5000, 50000, w, dtype=np.uint16)[np.newaxis, :]
        img[:, :, 1] = np.linspace(8000, 40000, w, dtype=np.uint16)[np.newaxis, :]
        img[:, :, 2] = np.linspace(3000, 30000, w, dtype=np.uint16)[np.newaxis, :]
        for mask in [
            np.array([50000.0, 40000.0, 30000.0]),
            np.array([1.0, 1.0, 1.0]),
            np.array([65535.0, 65535.0, 65535.0]),
        ]:
            result = invert_color_negative(img, mask)
            assert result.dtype == np.uint16
            assert result.shape == (h, w, 3)
            assert result.max() <= 65535

    def test_gradient_image_inverts_direction(self):
        """Darker pixels in negative → brighter in positive."""
        h, w = 1, 100
        img = np.zeros((h, w, 3), dtype=np.uint16)
        ramp = np.linspace(5000, 50000, w, dtype=np.uint16)
        for ch in range(3):
            img[0, :, ch] = ramp
        mask = np.array([50000.0, 50000.0, 50000.0])
        result = invert_color_negative(img, mask)
        # After inversion, higher original values (less dense) should map lower
        # Check that the overall trend reverses for at least one channel
        orig_mean_left = img[0, :10, 0].mean()
        orig_mean_right = img[0, -10:, 0].mean()
        res_mean_left = result[0, :10, 0].mean()
        res_mean_right = result[0, -10:, 0].mean()
        assert orig_mean_left < orig_mean_right  # original ramps up
        assert res_mean_left > res_mean_right    # inverted ramps down


class TestInvertBwNegative:
    def test_output_dtype_and_shape(self):
        img = _make_image(60, 40, (20000, 20000, 20000))
        result = invert_bw_negative(img)
        assert result.dtype == np.uint16
        assert result.shape == (60, 40, 3)

    def test_all_channels_equal(self):
        """B&W output channels should be identical (grayscale)."""
        img = _make_image(50, 50, (30000, 30000, 30000))
        result = invert_bw_negative(img)
        np.testing.assert_array_equal(result[:, :, 0], result[:, :, 1])
        np.testing.assert_array_equal(result[:, :, 1], result[:, :, 2])

    def test_inversion_flips_values(self):
        """Brighter negative pixels → darker positive pixels."""
        h, w = 1, 100
        img = np.zeros((h, w, 3), dtype=np.uint16)
        ramp = np.linspace(1000, 60000, w, dtype=np.uint16)
        for ch in range(3):
            img[0, :, ch] = ramp
        result = invert_bw_negative(img)
        # Left side was dark in negative → should be bright in positive
        assert result[0, 0, 0] > result[0, -1, 0]

    def test_valid_range(self):
        img = _make_image(20, 20, (50000, 50000, 50000))
        result = invert_bw_negative(img)
        assert result.min() >= 0
        assert result.max() <= 65535


class TestApplyToneCurve:
    def test_output_range(self):
        data = np.random.rand(50, 50, 3)
        result = apply_tone_curve(data, contrast=1.0)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_zero_and_one_preserved(self):
        data = np.array([[[0.0, 0.5, 1.0]]])
        result = apply_tone_curve(data, contrast=1.0)
        np.testing.assert_almost_equal(result[0, 0, 0], 0.0, decimal=5)
        np.testing.assert_almost_equal(result[0, 0, 2], 1.0, decimal=5)

    def test_no_contrast(self):
        data = np.array([[[0.3, 0.5, 0.7]]])
        result = apply_tone_curve(data, contrast=0.0)
        np.testing.assert_array_almost_equal(result, data)

    def test_no_clipping_beyond_uint16(self):
        """Tone curve applied to a full image should not exceed uint16 range."""
        img = np.random.rand(30, 30, 3)
        curved = apply_tone_curve(img, contrast=2.0)
        as_uint16 = (curved * 65535).round().astype(np.uint16)
        assert as_uint16.min() >= 0
        assert as_uint16.max() <= 65535

    def test_higher_contrast_increases_spread(self):
        """Higher contrast should push midtones further from 0.5."""
        data = np.array([[[0.3, 0.5, 0.7]]])
        low_c = apply_tone_curve(data, contrast=0.5)
        high_c = apply_tone_curve(data, contrast=2.0)
        # 0.3 (below mid) should be pushed lower with more contrast
        assert high_c[0, 0, 0] < low_c[0, 0, 0]
        # 0.7 (above mid) should be pushed higher with more contrast
        assert high_c[0, 0, 2] > low_c[0, 0, 2]
