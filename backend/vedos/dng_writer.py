"""DNG output module.

Writes processed positive images to Adobe DNG (Digital Negative) format,
preserving full dynamic range and metadata. Supports embedding color profiles
and XMP sidecar data.
"""

from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import Any, Optional

import numpy as np
import tifffile

from vedos.raw_reader import RawMetadata

logger = logging.getLogger(__name__)

# sRGB D65 color matrix (sRGB primaries → XYZ under D65)
SRGB_D65_MATRIX = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ],
    dtype=np.float64,
)

# DNG tag IDs (TIFF tag numbers)
TAG_DNG_VERSION = 50706
TAG_DNG_BACKWARD_VERSION = 50707
TAG_UNIQUE_CAMERA_MODEL = 50708
TAG_COLOR_MATRIX_1 = 50721
TAG_AS_SHOT_NEUTRAL = 50728
TAG_CALIBRATION_ILLUMINANT_1 = 50778
TAG_BASELINE_EXPOSURE = 50730


def _rational(value: float) -> tuple[int, int]:
    """Convert a float to a TIFF SRATIONAL (signed 32-bit num/denom)."""
    denom = 10000
    num = int(round(value * denom))
    return (num, denom)


def _color_matrix_rational(matrix: np.ndarray) -> list[tuple[int, int]]:
    """Flatten a 3x3 matrix into 9 SRATIONAL values."""
    flat = matrix.flatten()
    return [_rational(v) for v in flat]


def write_dng(
    image_data: np.ndarray,
    output_path: str | Path,
    metadata: RawMetadata | None = None,
    color_matrix: np.ndarray | None = None,
    as_shot_neutral: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> str:
    """Write a Linear DNG file.

    Args:
        image_data: (H, W, 3) uint16 RGB data.
        output_path: Where to save the DNG file.
        metadata: Optional original RAW metadata to embed.
        color_matrix: Optional 3x3 color matrix (sRGB to XYZ).
                      Defaults to sRGB D65 matrix.
        as_shot_neutral: White balance coefficients.

    Returns:
        Path to the written DNG file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if image_data.ndim != 3 or image_data.shape[2] != 3:
        raise ValueError(f"Expected (H, W, 3) image, got {image_data.shape}")

    if image_data.dtype != np.uint16:
        image_data = image_data.astype(np.uint16)

    if color_matrix is None:
        color_matrix = SRGB_D65_MATRIX

    cm_rationals = _color_matrix_rational(color_matrix)
    # Pack as bytes: 9 pairs of signed 32-bit ints
    cm_bytes = b"".join(struct.pack("<ii", n, d) for n, d in cm_rationals)

    # AsShotNeutral as RATIONAL (unsigned)
    asn_rationals = [_rational(v) for v in as_shot_neutral]
    asn_bytes = b"".join(struct.pack("<II", abs(n), d) for n, d in asn_rationals)

    # BaselineExposure as SRATIONAL
    be_num, be_denom = _rational(0.0)
    be_bytes = struct.pack("<ii", be_num, be_denom)

    camera_model = "Vedos Film Scanner"
    if metadata and metadata.camera_model:
        camera_model = f"Vedos ({metadata.camera_model})"

    # DNG-specific TIFF extra tags
    # Format: (tag_id, dtype_code, count, value)
    # dtype codes: 1=BYTE, 2=ASCII, 5=RATIONAL, 7=UNDEFINED, 10=SRATIONAL
    extratags: list[tuple[int, int, int, Any]] = [
        # DNGVersion 1.4.0.0
        (TAG_DNG_VERSION, 1, 4, b"\x01\x04\x00\x00"),
        # DNGBackwardVersion 1.4.0.0
        (TAG_DNG_BACKWARD_VERSION, 1, 4, b"\x01\x04\x00\x00"),
        # UniqueCameraModel
        (TAG_UNIQUE_CAMERA_MODEL, 2, len(camera_model) + 1, camera_model),
        # ColorMatrix1 (9 SRATIONALs)
        (TAG_COLOR_MATRIX_1, 10, 9, cm_bytes),
        # AsShotNeutral (3 RATIONALs)
        (TAG_AS_SHOT_NEUTRAL, 5, 3, asn_bytes),
        # CalibrationIlluminant1 = 21 (D65)
        (TAG_CALIBRATION_ILLUMINANT_1, 3, 1, 21),
        # BaselineExposure (1 SRATIONAL)
        (TAG_BASELINE_EXPOSURE, 10, 1, be_bytes),
    ]

    # Build description string with metadata
    description = "Linear DNG created by Vedos"
    software = "Vedos Film Scanner"

    with tifffile.TiffWriter(str(output_path), bigtiff=False) as tif:
        tif_metadata: dict[str, Any] = {}

        tif.write(
            image_data,
            photometric="rgb",
            compression="adobe_deflate",
            predictor=True,
            tile=(256, 256),
            extratags=extratags,
            subfiletype=0,
            metadata=tif_metadata,
            software=software,
            description=description,
        )

    logger.info("Wrote DNG: %s (%dx%d)", output_path, image_data.shape[1], image_data.shape[0])
    return str(output_path)


def write_tiff_16bit(
    image_data: np.ndarray,
    output_path: str | Path,
    metadata: RawMetadata | None = None,
) -> str:
    """Write a 16-bit TIFF as fallback (simpler, widely supported).

    Args:
        image_data: (H, W, 3) uint16 RGB data.
        output_path: Where to save the TIFF file.
        metadata: Optional original RAW metadata to embed.

    Returns:
        Path to the written TIFF file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if image_data.ndim != 3 or image_data.shape[2] != 3:
        raise ValueError(f"Expected (H, W, 3) image, got {image_data.shape}")

    if image_data.dtype != np.uint16:
        image_data = image_data.astype(np.uint16)

    description = "16-bit TIFF created by Vedos"
    software = "Vedos Film Scanner"
    if metadata and metadata.camera_model:
        description = f"16-bit TIFF from {metadata.camera_model} via Vedos"

    with tifffile.TiffWriter(str(output_path), bigtiff=False) as tif:
        tif.write(
            image_data,
            photometric="rgb",
            compression="adobe_deflate",
            predictor=True,
            tile=(256, 256),
            software=software,
            description=description,
        )

    logger.info("Wrote TIFF: %s (%dx%d)", output_path, image_data.shape[1], image_data.shape[0])
    return str(output_path)


# Keep backward-compatible aliases
def write_dng_compat(
    image: np.ndarray,
    output_path: str | Path,
    metadata: Optional[dict[str, Any]] = None,
) -> Path:
    """Backward-compatible wrapper matching the original signature."""
    raw_meta = None
    result = write_dng(image, output_path, metadata=raw_meta)
    return Path(result)


def write_tiff(
    image: np.ndarray,
    output_path: str | Path,
    bit_depth: int = 16,
) -> Path:
    """Backward-compatible wrapper matching the original signature."""
    if bit_depth == 8:
        image = (image / 256).astype(np.uint8) if image.dtype == np.uint16 else image.astype(np.uint8)
        image = image.astype(np.uint16)
    result = write_tiff_16bit(image, output_path)
    return Path(result)
