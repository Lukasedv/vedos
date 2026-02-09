"""Pydantic models for the Vedos API."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FilmType(str, Enum):
    COLOR_NEGATIVE = "color_negative"
    BW_NEGATIVE = "bw_negative"


class AIModel(str, Enum):
    CLAUDE_SONNET = "claude-sonnet-4.5"
    CLAUDE_HAIKU = "claude-haiku-4.5"


class MaskRegion(BaseModel):
    x: int
    y: int
    w: int
    h: int


class FileInfo(BaseModel):
    path: str
    filename: str
    format: str
    width: int
    height: int
    file_size: int
    camera_make: str = ""
    camera_model: str = ""


class ProcessingConfig(BaseModel):
    files: list[str]
    output_dir: str = ""
    film_type: FilmType = FilmType.COLOR_NEGATIVE
    mask_region: Optional[MaskRegion] = None
    ai_correction: bool = True
    ai_model: AIModel = AIModel.CLAUDE_SONNET
    inversion_params: Optional[InversionParams] = None


class ProcessingStatus(BaseModel):
    job_id: str
    status: str = Field(description="queued | processing | complete | error")
    progress: float = Field(ge=0, le=100)
    current_file: Optional[str] = None
    total_files: int = 0
    completed_files: int = 0
    errors: list[str] = Field(default_factory=list)


class ChannelCurve(BaseModel):
    shadows: float = 0.0
    midtones: float = 0.0
    highlights: float = 0.0


class CurvesAdjustment(BaseModel):
    r: ChannelCurve = Field(default_factory=ChannelCurve)
    g: ChannelCurve = Field(default_factory=ChannelCurve)
    b: ChannelCurve = Field(default_factory=ChannelCurve)


class AICorrectionParams(BaseModel):
    white_balance_shift: float = 0.0
    tint_shift: float = 0.0
    exposure_compensation: float = 0.0
    curves: CurvesAdjustment = Field(default_factory=CurvesAdjustment)
    saturation_adjustment: float = 0.0
    analysis_notes: str = ""


class InversionParams(BaseModel):
    black_point_percentile: float = 0.1
    white_point_percentile: float = 99.9
    contrast: float = 1.0


class PipelineResult(BaseModel):
    output_path: str
    input_path: str
    corrections: Optional[AICorrectionParams] = None
    processing_time_seconds: float = 0.0
    error: Optional[str] = None


class BatchResult(BaseModel):
    job_id: str
    total_files: int
    completed: int = 0
    failed: int = 0
    results: list[PipelineResult] = Field(default_factory=list)
    total_time_seconds: float = 0.0
