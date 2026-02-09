"""RAW file reading module.

Handles reading camera RAW files (CR2, NEF, ARW, DNG, etc.) using rawpy/libraw.
Extracts pixel data, metadata (EXIF), and provides the raw Bayer data for
downstream inversion processing.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rawpy
from PIL import Image

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: list[str] = [
    ".arw", ".cr2", ".cr3", ".nef", ".raf",
    ".dng", ".orf", ".rw2", ".pef", ".srw", ".x3f",
]


@dataclass
class RawMetadata:
    """Metadata extracted from a RAW file."""

    camera_make: str
    camera_model: str
    iso: int | None
    exposure_time: float | None
    f_number: float | None
    focal_length: float | None
    timestamp: str | None
    width: int
    height: int


@dataclass
class RawImage:
    """Demosaiced linear 16-bit RGB image with metadata."""

    data: np.ndarray  # (H, W, 3) uint16 linear RGB
    metadata: RawMetadata
    file_path: str
    black_levels: list[int] = field(default_factory=list)
    white_level: int = 0


def _validate_path(file_path: str | Path) -> Path:
    """Validate that the file exists and has a supported extension."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"RAW file not found: {file_path}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension: {p.suffix}. "
            f"Supported: {SUPPORTED_EXTENSIONS}"
        )
    return p


def _extract_metadata(raw: rawpy.RawPy, file_path: Path) -> RawMetadata:
    """Extract metadata from an open rawpy handle."""
    sizes = raw.sizes
    # camera_make/model from color_desc or fallback
    color_desc = raw.color_desc.decode("utf-8", errors="replace") if raw.color_desc else ""

    # Try to get camera make/model from raw internals
    camera_make = ""
    camera_model = ""
    try:
        camera_make = raw.camera_make.decode("utf-8", errors="replace") if hasattr(raw, "camera_make") and raw.camera_make else ""
    except Exception:
        pass
    try:
        camera_model = raw.camera_model.decode("utf-8", errors="replace") if hasattr(raw, "camera_model") and raw.camera_model else ""
    except Exception:
        pass

    if not camera_make and not camera_model and color_desc:
        camera_model = color_desc

    # Timestamp
    timestamp = None
    try:
        if hasattr(raw, "metadata") and hasattr(raw.metadata, "timestamp"):
            ts = raw.metadata.timestamp
            if ts:
                timestamp = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        pass

    return RawMetadata(
        camera_make=camera_make,
        camera_model=camera_model,
        iso=None,
        exposure_time=None,
        f_number=None,
        focal_length=None,
        timestamp=timestamp,
        width=sizes.width,
        height=sizes.height,
    )


def read_raw(file_path: str | Path) -> RawImage:
    """Read a RAW file and return demosaiced linear 16-bit RGB data.

    Returns a RawImage dataclass containing:
    - data: numpy array, shape (H, W, 3), dtype uint16, linear RGB
    - metadata: RawMetadata (camera make/model, ISO, exposure, etc.)
    - file_path: str
    - black_levels: per-channel black levels from sensor
    - white_level: sensor saturation level
    """
    p = _validate_path(file_path)

    with rawpy.imread(str(p)) as raw:
        metadata = _extract_metadata(raw, p)
        black_levels = list(raw.black_level_per_channel)
        white_level = int(raw.white_level)

        rgb = raw.postprocess(
            output_bps=16,
            output_color=rawpy.ColorSpace.sRGB,
            no_auto_bright=True,
            gamma=(1, 1),
            use_camera_wb=False,
            use_auto_wb=False,
        )

    return RawImage(
        data=rgb,
        metadata=metadata,
        file_path=str(p.resolve()),
        black_levels=black_levels,
        white_level=white_level,
    )


def get_raw_thumbnail(file_path: str | Path, max_size: int = 400) -> bytes:
    """Extract the embedded JPEG thumbnail from a RAW file.

    Returns JPEG bytes for quick preview in the UI.
    If no embedded thumbnail, demosaic and create one.
    """
    p = _validate_path(file_path)

    with rawpy.imread(str(p)) as raw:
        try:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                return thumb.data
            elif thumb.format == rawpy.ThumbFormat.BITMAP:
                img = Image.fromarray(thumb.data)
            else:
                raise rawpy.LibRawNoThumbnailError()
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawError):
            # No embedded thumbnail — demosaic a quick preview
            rgb = raw.postprocess(
                output_bps=8,
                output_color=rawpy.ColorSpace.sRGB,
                use_camera_wb=True,
                half_size=True,
            )
            img = Image.fromarray(rgb)

    # Resize to max_size
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def get_raw_metadata(file_path: str | Path) -> RawMetadata:
    """Extract metadata without fully demosaicing the image."""
    p = _validate_path(file_path)

    with rawpy.imread(str(p)) as raw:
        return _extract_metadata(raw, p)


def get_supported_extensions() -> list[str]:
    """Return list of supported RAW file extensions."""
    return list(SUPPORTED_EXTENSIONS)
