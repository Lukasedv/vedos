"""Negative inversion algorithms.

Converts scanned film negatives (color or B&W) to positive images.
Handles orange mask removal for color negatives, per-channel curve inversion,
and optional histogram-based auto-exposure compensation.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from vedos.models import MaskRegion

_UINT16_MAX = 65535
# ITU-R BT.709 luminance weights
_LUMA_WEIGHTS = np.array([0.2126, 0.7152, 0.0722], dtype=np.float64)


def sample_orange_mask(
    image_data: np.ndarray, region: tuple[int, int, int, int]
) -> np.ndarray:
    """Sample the orange mask from the given region.

    Args:
        image_data: (H, W, 3) uint16 array.
        region: (x, y, width, height) of the mask area.

    Returns:
        (3,) float64 array of per-channel median values.
    """
    x, y, w, h = region
    patch = image_data[y : y + h, x : x + w, :]
    return np.median(patch.reshape(-1, 3).astype(np.float64), axis=0)


def auto_estimate_mask(
    image_data: np.ndarray, border_fraction: float = 0.02
) -> np.ndarray:
    """Auto-estimate orange mask from image borders.

    Samples a thin strip from all four edges and takes the median.
    """
    h, w = image_data.shape[:2]
    bw = max(1, int(w * border_fraction))
    bh = max(1, int(h * border_fraction))

    strips = np.concatenate(
        [
            image_data[:bh, :, :].reshape(-1, 3),   # top
            image_data[-bh:, :, :].reshape(-1, 3),   # bottom
            image_data[:, :bw, :].reshape(-1, 3),    # left
            image_data[:, -bw:, :].reshape(-1, 3),   # right
        ],
        axis=0,
    )
    return np.median(strips.astype(np.float64), axis=0)


def apply_tone_curve(
    image_data: np.ndarray, contrast: float = 1.0
) -> np.ndarray:
    """Apply a sigmoid S-curve for pleasing contrast.

    Operates on float64 data in [0, 1] range, returns same range.
    """
    if contrast == 0.0:
        return image_data

    # Sigmoid-based S-curve: shift midpoint to 0, scale by contrast
    k = 5.0 * contrast
    out = 1.0 / (1.0 + np.exp(-k * (image_data - 0.5)))
    # Re-normalize so that 0 maps to 0 and 1 maps to 1
    low = 1.0 / (1.0 + np.exp(-k * (-0.5)))
    high = 1.0 / (1.0 + np.exp(-k * 0.5))
    out = (out - low) / (high - low)
    return np.clip(out, 0.0, 1.0)


def _normalize_channels(
    data: np.ndarray,
    black_point_percentile: float,
    white_point_percentile: float,
) -> np.ndarray:
    """Per-channel percentile normalization to [0, 1]."""
    out = np.empty_like(data)
    for ch in range(data.shape[2]):
        channel = data[:, :, ch]
        bp = np.percentile(channel, black_point_percentile)
        wp = np.percentile(channel, white_point_percentile)
        if wp <= bp:
            wp = bp + 1e-10
        out[:, :, ch] = (channel - bp) / (wp - bp)
    return np.clip(out, 0.0, 1.0)


def invert_color_negative(
    image_data: np.ndarray,
    mask_values: np.ndarray,
    black_point_percentile: float = 0.1,
    white_point_percentile: float = 99.9,
    contrast: float = 1.0,
) -> np.ndarray:
    """Full C-41 color negative to positive conversion.

    Steps:
        1. Mask compensation (divide by orange mask values)
        2. Log-space inversion (-log10 of compensated data)
        3. Per-channel percentile normalization
        4. S-curve tone mapping
    """
    data = image_data.astype(np.float64)
    mask = mask_values.astype(np.float64)
    mask[mask < 1.0] = 1.0  # avoid division by zero

    # 1. Mask compensation
    compensated = data / mask[np.newaxis, np.newaxis, :]

    # Clamp to positive for log
    compensated = np.clip(compensated, 1e-10, None)

    # 2. Log-space inversion: density = -log10(transmittance)
    # High density = opaque film = bright original scene → high output value
    inverted = -np.log10(compensated)

    # 3. Per-channel normalization
    normalized = _normalize_channels(
        inverted, black_point_percentile, white_point_percentile
    )

    # 4. Tone curve
    curved = apply_tone_curve(normalized, contrast)

    return (curved * _UINT16_MAX).round().astype(np.uint16)


def invert_bw_negative(
    image_data: np.ndarray,
    black_point_percentile: float = 0.5,
    white_point_percentile: float = 99.5,
    contrast: float = 1.0,
) -> np.ndarray:
    """B&W negative to positive conversion.

    1. Convert to luminance (weighted RGB average)
    2. Invert (max - value)
    3. Normalize per-channel
    4. Apply tone curve
    Returns a 3-channel image for DNG compatibility.
    """
    data = image_data.astype(np.float64)

    # Luminance
    if data.ndim == 3 and data.shape[2] == 3:
        luma = np.sum(data * _LUMA_WEIGHTS[np.newaxis, np.newaxis, :], axis=2)
    else:
        luma = data.squeeze()

    # Invert
    inverted = _UINT16_MAX - luma

    # Expand to 3 channels
    inv3 = np.stack([inverted, inverted, inverted], axis=-1)

    # Normalize
    normalized = _normalize_channels(
        inv3, black_point_percentile, white_point_percentile
    )

    # Tone curve
    curved = apply_tone_curve(normalized, contrast)

    return (curved * _UINT16_MAX).round().astype(np.uint16)


# ---------------------------------------------------------------------------
# Convenience wrappers matching the original placeholder API
# ---------------------------------------------------------------------------

def estimate_orange_mask(
    image: np.ndarray, region: Optional[MaskRegion] = None
) -> np.ndarray:
    """Estimate the orange mask color from a film border or user-selected region."""
    if region is not None:
        return sample_orange_mask(image, (region.x, region.y, region.w, region.h))
    return auto_estimate_mask(image)


def invert_negative(
    image: np.ndarray,
    mask: Optional[np.ndarray] = None,
    is_bw: bool = False,
) -> np.ndarray:
    """Invert a film negative to a positive image."""
    if is_bw:
        return invert_bw_negative(image)

    if mask is None:
        mask = auto_estimate_mask(image)
    return invert_color_negative(image, mask)


def auto_exposure(image: np.ndarray) -> np.ndarray:
    """Apply histogram-based auto-exposure compensation."""
    return _normalize_to_uint16(image)


def _normalize_to_uint16(image: np.ndarray) -> np.ndarray:
    data = image.astype(np.float64)
    normalized = _normalize_channels(data, 0.5, 99.5)
    return (normalized * _UINT16_MAX).round().astype(np.uint16)
