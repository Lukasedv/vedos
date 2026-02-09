"""AI-powered color correction via Copilot SDK.

Uses the GitHub Copilot SDK to analyze inverted positive images and suggest
color correction parameters (white balance, tint, exposure, per-channel curves)
to produce accurate, natural-looking results.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Optional

import numpy as np
from PIL import Image
from scipy.interpolate import PchipInterpolator

from vedos.models import (
    AICorrectionParams,
    AIModel,
    ChannelCurve,
    CurvesAdjustment,
)

ANALYSIS_PROMPT = """\
You are an expert photo color correction assistant. This image was \
algorithmically converted from a scanned color film negative to a positive. \
The conversion applies an automatic orange-mask removal and channel inversion, \
but the result often still needs fine-tuning.

Common artifacts from this process:
- Orange mask residue causing warm color casts, especially in shadows
- Uneven fading across the frame (older film stocks lose dye density unevenly)
- Scanner-introduced color shifts (LED vs halogen light source differences)
- Shadow tinting — shadows may appear muddy brown, green, or cyan
- Highlight crossover — highlights may take on an unnatural hue

Analyze this image and identify any remaining color issues. Be conservative — \
subtle corrections are preferred over dramatic ones. A value of 0 means \
"no correction needed"; only suggest non-zero values for actual issues.

Respond with ONLY the following JSON object. Do NOT include markdown fences, \
commentary, or any text outside the JSON:

{
  "white_balance_shift_kelvin": <int, range -3000 to +3000, positive=warmer>,
  "tint_shift": <float, range -50.0 to +50.0, positive=magenta negative=green>,
  "exposure_compensation": <float, range -2.0 to +2.0, in EV stops>,
  "channel_curves": {
    "red":   {"shadows": <-50 to 50>, "midtones": <-50 to 50>, "highlights": <-50 to 50>},
    "green": {"shadows": <-50 to 50>, "midtones": <-50 to 50>, "highlights": <-50 to 50>},
    "blue":  {"shadows": <-50 to 50>, "midtones": <-50 to 50>, "highlights": <-50 to 50>}
  },
  "saturation_adjustment": <float, range -50.0 to +50.0>,
  "analysis_notes": "<brief description of what was found>"
}
"""

REFINE_PROMPT = """\
The previous AI-suggested color corrections have been applied to this image. \
Examine the result and determine if additional adjustments are needed.

If the image now looks correct, return all-zero values. If residual issues \
remain, return ONLY the additional delta corrections needed (not cumulative). \
Be conservative — only suggest further changes for clearly visible problems.

Respond with ONLY the JSON object, no markdown fences or extra text:

{
  "white_balance_shift_kelvin": <int, range -3000 to +3000>,
  "tint_shift": <float, range -50.0 to +50.0>,
  "exposure_compensation": <float, range -2.0 to +2.0>,
  "channel_curves": {
    "red":   {"shadows": <-50 to 50>, "midtones": <-50 to 50>, "highlights": <-50 to 50>},
    "green": {"shadows": <-50 to 50>, "midtones": <-50 to 50>, "highlights": <-50 to 50>},
    "blue":  {"shadows": <-50 to 50>, "midtones": <-50 to 50>, "highlights": <-50 to 50>}
  },
  "saturation_adjustment": <float, range -50.0 to +50.0>,
  "analysis_notes": "<brief description of what was found>"
}
"""


def generate_preview_jpeg(
    image_data: np.ndarray, max_size: int = 2000
) -> str:
    """Generate a temporary JPEG preview for AI analysis.

    Resizes to *max_size* on the long edge, applies a basic sRGB gamma
    curve for viewing, and writes to a temporary file.

    Returns:
        Path to the temporary JPEG file.
    """
    h, w = image_data.shape[:2]
    scale = min(max_size / max(h, w), 1.0)
    new_w, new_h = int(w * scale), int(h * scale)

    # Convert to float for processing
    if image_data.dtype == np.uint16:
        img_float = image_data.astype(np.float32) / 65535.0
    elif image_data.dtype == np.uint8:
        img_float = image_data.astype(np.float32) / 255.0
    else:
        img_float = image_data.astype(np.float32)

    # Apply sRGB gamma for preview
    img_float = np.clip(img_float, 0.0, 1.0)
    gamma = np.where(
        img_float <= 0.0031308,
        img_float * 12.92,
        1.055 * np.power(img_float, 1.0 / 2.4) - 0.055,
    )
    img_uint8 = np.clip(gamma * 255.0, 0, 255).astype(np.uint8)

    pil_img = Image.fromarray(img_uint8, mode="RGB")
    if (new_w, new_h) != (w, h):
        pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

    fd, path = tempfile.mkstemp(suffix=".jpg", prefix="vedos_preview_")
    os.close(fd)
    pil_img.save(path, format="JPEG", quality=90)
    return path


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp a numeric value to [lo, hi]."""
    return max(lo, min(hi, float(value)))


def _clamp_channel_curve(data: dict) -> dict:
    """Clamp channel curve values to [-50, 50]."""
    return {
        k: _clamp(data.get(k, 0.0), -50.0, 50.0)
        for k in ("shadows", "midtones", "highlights")
    }


def parse_correction_response(response_text: str) -> AICorrectionParams:
    """Parse the AI model's response into correction parameters.

    Handles:
    - Pure JSON responses
    - JSON wrapped in ```json ... ``` blocks
    - JSON with surrounding text
    - Partial/invalid JSON (returns defaults with error note)
    """
    # 1. Try markdown fenced block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    if match:
        raw = match.group(1)
    else:
        # 2. Find the outermost { ... } block
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not match:
            return AICorrectionParams(
                analysis_notes="ERROR: No JSON found in AI response"
            )
        raw = match.group(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return AICorrectionParams(
            analysis_notes=f"ERROR: Invalid JSON in AI response: {exc}"
        )

    # Map and clamp values
    curves_data = data.get("channel_curves", {})
    curves = CurvesAdjustment(
        r=ChannelCurve(**_clamp_channel_curve(curves_data.get("red", {}))),
        g=ChannelCurve(**_clamp_channel_curve(curves_data.get("green", {}))),
        b=ChannelCurve(**_clamp_channel_curve(curves_data.get("blue", {}))),
    )

    wb_kelvin = data.get("white_balance_shift_kelvin", 0)
    wb_shift = _clamp(
        float(wb_kelvin) if isinstance(wb_kelvin, (int, float)) else 0.0,
        -3000.0, 3000.0,
    )

    return AICorrectionParams(
        white_balance_shift=wb_shift,
        tint_shift=_clamp(data.get("tint_shift", 0.0), -50.0, 50.0),
        exposure_compensation=_clamp(
            data.get("exposure_compensation", 0.0), -2.0, 2.0
        ),
        curves=curves,
        saturation_adjustment=_clamp(
            data.get("saturation_adjustment", 0.0), -50.0, 50.0
        ),
        analysis_notes=data.get("analysis_notes", ""),
    )


# Backward-compatible alias
parse_correction_json = parse_correction_response


class CopilotColorAnalyzer:
    """Manages Copilot SDK sessions for AI-powered color correction."""

    def __init__(self, model: str = "claude-sonnet-4.5"):
        self.model = model
        self.client = None
        self.session = None

    async def start(self) -> None:
        """Initialize the Copilot client and create a session."""
        from copilot import CopilotClient

        self.client = CopilotClient()
        await self.client.start()
        self.session = await self.client.create_session({"model": self.model})

    async def stop(self) -> None:
        """Clean up session and client."""
        if self.session:
            await self.session.destroy()
            self.session = None
        if self.client:
            await self.client.stop()
            self.client = None

    async def analyze_image(
        self, preview_path: str, prompt: str | None = None
    ) -> AICorrectionParams:
        """Send a preview image to the AI model for color analysis.

        Args:
            preview_path: Path to a JPEG preview of the converted image.
            prompt: Optional custom prompt (defaults to ANALYSIS_PROMPT).

        Returns:
            AICorrectionParams with suggested corrections.
        """
        if not self.session:
            raise RuntimeError("Analyzer not started; call start() first")

        response = await self.session.send_and_wait(
            {
                "prompt": prompt or ANALYSIS_PROMPT,
                "attachments": [{"type": "file", "path": preview_path}],
            }
        )

        return parse_correction_response(response.data.content)


async def analyze_image(
    image: np.ndarray,
    model: AIModel = AIModel.CLAUDE_SONNET,
) -> AICorrectionParams:
    """Analyze an inverted positive image and return AI-suggested corrections.

    High-level convenience wrapper: generates a preview, sends it to the
    Copilot SDK, and returns parsed correction parameters.

    Args:
        image: Positive image data (H, W, 3) uint16.
        model: AI model to use for analysis.

    Returns:
        Suggested correction parameters.
    """
    preview_path: Optional[str] = None
    analyzer = CopilotColorAnalyzer(model=model.value)
    try:
        await analyzer.start()
        preview_path = generate_preview_jpeg(image)
        return await analyzer.analyze_image(preview_path)
    finally:
        await analyzer.stop()
        if preview_path and os.path.exists(preview_path):
            os.unlink(preview_path)


def _build_curve_lut(curve: ChannelCurve) -> np.ndarray:
    """Build a 65536-entry uint16 LUT from a ChannelCurve adjustment.

    Uses PCHIP interpolation through five control points (black, shadow,
    midtone, highlight, white) shifted by the curve parameters.
    """
    xs = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    # Scale curve parameters (range ±50) into reasonable offsets
    s = curve.shadows / 200.0
    m = curve.midtones / 200.0
    h = curve.highlights / 200.0
    ys = np.array([
        0.0 + s * 0.5,
        0.25 + s,
        0.5 + m,
        0.75 + h,
        1.0 + h * 0.5,
    ])
    ys = np.clip(ys, 0.0, 1.0)

    interp = PchipInterpolator(xs, ys)
    lut_x = np.linspace(0.0, 1.0, 65536)
    lut_y = np.clip(interp(lut_x), 0.0, 1.0)
    return (lut_y * 65535.0).astype(np.uint16)


def apply_corrections(
    image_data: np.ndarray,
    corrections: AICorrectionParams,
) -> np.ndarray:
    """Apply AI-suggested corrections to 16-bit image data.

    Args:
        image_data: (H, W, 3) uint16 array.
        corrections: AI-generated correction parameters.

    Returns:
        Corrected (H, W, 3) uint16 array.
    """
    img = image_data.astype(np.float64)

    # 1. White balance shift (Kelvin) — adjust R/B relative to G
    wb = corrections.white_balance_shift
    if wb != 0.0:
        # Positive wb = warmer → boost red, reduce blue
        img[:, :, 0] *= 1.0 + wb / 10000.0  # red
        img[:, :, 2] *= 1.0 - wb / 10000.0  # blue

    # 2. Tint shift — adjust G channel
    tint = corrections.tint_shift
    if tint != 0.0:
        img[:, :, 1] *= 1.0 + tint / 200.0

    # 3. Exposure compensation (EV stops)
    ev = corrections.exposure_compensation
    if ev != 0.0:
        img *= 2.0 ** ev

    # Clip to valid range before curve LUT indexing
    img = np.clip(img, 0, 65535).astype(np.uint16)

    # 4. Per-channel curves
    curves = corrections.curves
    for ch, curve in enumerate([curves.r, curves.g, curves.b]):
        if curve.shadows != 0.0 or curve.midtones != 0.0 or curve.highlights != 0.0:
            lut = _build_curve_lut(curve)
            img[:, :, ch] = lut[img[:, :, ch]]

    # 5. Saturation adjustment
    sat = corrections.saturation_adjustment
    if sat != 0.0:
        img_f = img.astype(np.float64)
        # Luminance via Rec. 709 coefficients
        lum = (
            0.2126 * img_f[:, :, 0]
            + 0.7152 * img_f[:, :, 1]
            + 0.0722 * img_f[:, :, 2]
        )
        lum = lum[:, :, np.newaxis]
        img_f = lum + (1.0 + sat / 100.0) * (img_f - lum)
        img = np.clip(img_f, 0, 65535).astype(np.uint16)

    return img
