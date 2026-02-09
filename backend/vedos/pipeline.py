"""Single-file processing pipeline.

Orchestrates reading a RAW file, inverting the negative, optionally running
AI color correction, and writing the result as a DNG.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

from vedos.ai_correction import (
    CopilotColorAnalyzer,
    apply_corrections,
    generate_preview_jpeg,
)
from vedos.dng_writer import write_dng
from vedos.inversion import (
    auto_estimate_mask,
    invert_bw_negative,
    invert_color_negative,
    sample_orange_mask,
)
from vedos.models import AICorrectionParams, PipelineResult
from vedos.raw_reader import read_raw

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float], None]


async def process_file(
    file_path: str,
    output_dir: str,
    film_type: str,
    mask_region: tuple[int, int, int, int] | None = None,
    ai_correction: bool = False,
    ai_model: str = "claude-sonnet-4.5",
    inversion_params: dict | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PipelineResult:
    """Process a single RAW file through the complete pipeline.

    Returns PipelineResult with output_path, corrections_applied, processing_time, etc.
    """
    inv_params = inversion_params or {}
    start = time.monotonic()

    def _progress(step: str, pct: float) -> None:
        if progress_callback is not None:
            progress_callback(step, pct)

    try:
        # Step 1: Read RAW
        _progress("reading", 0.1)
        raw_image = read_raw(file_path)

        # Step 2: Invert
        _progress("inverting", 0.3)
        if film_type == "color_negative":
            if mask_region:
                mask = sample_orange_mask(raw_image.data, mask_region)
            else:
                mask = auto_estimate_mask(raw_image.data)
            positive = invert_color_negative(raw_image.data, mask, **inv_params)
        else:
            positive = invert_bw_negative(raw_image.data, **inv_params)

        # Step 3: AI correction (optional)
        corrections: AICorrectionParams | None = None
        if ai_correction:
            _progress("ai_analysis", 0.5)
            analyzer = CopilotColorAnalyzer(model=ai_model)
            preview_path: str | None = None
            try:
                await analyzer.start()
                preview_path = generate_preview_jpeg(positive)
                corrections = await analyzer.analyze_image(preview_path)
                positive = apply_corrections(positive, corrections)
            finally:
                await analyzer.stop()
                if preview_path and os.path.exists(preview_path):
                    os.unlink(preview_path)

        # Step 4: Write DNG
        _progress("writing_dng", 0.8)
        output_filename = Path(file_path).stem + "_positive.dng"
        output_path = Path(output_dir) / output_filename
        write_dng(positive, str(output_path), raw_image.metadata)

        elapsed = time.monotonic() - start
        _progress("complete", 1.0)
        return PipelineResult(
            output_path=str(output_path),
            input_path=file_path,
            corrections=corrections,
            processing_time_seconds=round(elapsed, 3),
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.error("Pipeline failed for %s: %s", file_path, exc, exc_info=True)
        return PipelineResult(
            output_path="",
            input_path=file_path,
            processing_time_seconds=round(elapsed, 3),
            error=str(exc),
        )
