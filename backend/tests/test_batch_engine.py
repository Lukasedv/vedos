"""Tests for batch processing engine and pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from vedos.batch_engine import BatchProcessor
from vedos.models import (
    BatchResult,
    FilmType,
    InversionParams,
    MaskRegion,
    PipelineResult,
    ProcessingConfig,
    ProcessingStatus,
)
from vedos.pipeline import process_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(files: list[str] | None = None, **kwargs) -> ProcessingConfig:
    return ProcessingConfig(
        files=files or ["/tmp/test1.cr2", "/tmp/test2.cr2"],
        output_dir="/tmp/vedos_test_output",
        **kwargs,
    )


def _fake_raw_image():
    """Create a fake RawImage-like object."""
    raw = MagicMock()
    raw.data = np.full((100, 100, 3), 30000, dtype=np.uint16)
    raw.metadata = MagicMock()
    raw.metadata.camera_make = "Test"
    raw.metadata.camera_model = "TestCam"
    return raw


# ---------------------------------------------------------------------------
# BatchProcessor creation
# ---------------------------------------------------------------------------

class TestBatchProcessorCreation:
    def test_creates_with_valid_config(self):
        config = _make_config()
        bp = BatchProcessor(config, job_id="test-123")
        assert bp.job_id == "test-123"
        assert bp.config is config
        assert isinstance(bp.status, ProcessingStatus)
        assert bp.status.status == "queued"
        assert bp.status.total_files == 2

    def test_initial_state(self):
        config = _make_config(files=["/a.cr2"])
        bp = BatchProcessor(config, job_id="j1")
        assert bp.cancel_requested is False
        assert bp.status.progress == 0.0
        assert bp.status.completed_files == 0
        assert bp.status.errors == []

    def test_different_film_types(self):
        config = _make_config(film_type=FilmType.BW_NEGATIVE)
        bp = BatchProcessor(config, job_id="bw-job")
        assert bp.config.film_type == FilmType.BW_NEGATIVE

    def test_with_inversion_params(self):
        config = _make_config(
            inversion_params=InversionParams(contrast=0.8)
        )
        bp = BatchProcessor(config, job_id="ip-job")
        assert bp.config.inversion_params is not None
        assert bp.config.inversion_params.contrast == 0.8


# ---------------------------------------------------------------------------
# Cancel flag
# ---------------------------------------------------------------------------

class TestCancellation:
    def test_cancel_sets_flag(self):
        bp = BatchProcessor(_make_config(), job_id="c1")
        assert bp.cancel_requested is False
        bp.cancel()
        assert bp.cancel_requested is True

    @pytest.mark.asyncio
    async def test_cancel_stops_processing(self):
        files = [f"/tmp/file{i}.cr2" for i in range(5)]
        config = _make_config(files=files)
        bp = BatchProcessor(config, job_id="c2")

        call_count = 0

        async def mock_process_file(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                bp.cancel()
            return PipelineResult(
                output_path="/tmp/out.dng",
                input_path=kwargs["file_path"],
                processing_time_seconds=0.01,
            )

        with patch("vedos.batch_engine.process_file", side_effect=mock_process_file):
            result = await bp.process_all()

        # Should have processed at most 3 files (cancel after 2nd, 3rd may start)
        assert result.completed <= 3
        assert bp.cancel_requested is True


# ---------------------------------------------------------------------------
# process_file with mocked dependencies
# ---------------------------------------------------------------------------

class TestProcessFile:
    @pytest.mark.asyncio
    async def test_color_negative_pipeline(self, tmp_path):
        fake_raw = _fake_raw_image()
        inverted = np.full((100, 100, 3), 40000, dtype=np.uint16)

        with (
            patch("vedos.pipeline.read_raw", return_value=fake_raw) as mock_read,
            patch("vedos.pipeline.auto_estimate_mask", return_value=np.array([100.0, 80.0, 60.0])),
            patch("vedos.pipeline.invert_color_negative", return_value=inverted) as mock_inv,
            patch("vedos.pipeline.write_dng", return_value=str(tmp_path / "out.dng")) as mock_write,
        ):
            result = await process_file(
                file_path="/tmp/test.cr2",
                output_dir=str(tmp_path),
                film_type="color_negative",
                ai_correction=False,
            )

        mock_read.assert_called_once_with("/tmp/test.cr2")
        mock_inv.assert_called_once()
        mock_write.assert_called_once()
        assert result.error is None
        assert result.input_path == "/tmp/test.cr2"
        assert result.output_path != ""

    @pytest.mark.asyncio
    async def test_bw_negative_pipeline(self, tmp_path):
        fake_raw = _fake_raw_image()
        inverted = np.full((100, 100, 3), 40000, dtype=np.uint16)

        with (
            patch("vedos.pipeline.read_raw", return_value=fake_raw),
            patch("vedos.pipeline.invert_bw_negative", return_value=inverted) as mock_bw,
            patch("vedos.pipeline.write_dng", return_value=str(tmp_path / "out.dng")),
        ):
            result = await process_file(
                file_path="/tmp/test.cr2",
                output_dir=str(tmp_path),
                film_type="bw_negative",
                ai_correction=False,
            )

        mock_bw.assert_called_once()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_with_mask_region(self, tmp_path):
        fake_raw = _fake_raw_image()
        inverted = np.full((100, 100, 3), 40000, dtype=np.uint16)

        with (
            patch("vedos.pipeline.read_raw", return_value=fake_raw),
            patch("vedos.pipeline.sample_orange_mask", return_value=np.array([100.0, 80.0, 60.0])) as mock_sample,
            patch("vedos.pipeline.invert_color_negative", return_value=inverted),
            patch("vedos.pipeline.write_dng", return_value=str(tmp_path / "out.dng")),
        ):
            result = await process_file(
                file_path="/tmp/test.cr2",
                output_dir=str(tmp_path),
                film_type="color_negative",
                mask_region=(10, 20, 30, 40),
                ai_correction=False,
            )

        mock_sample.assert_called_once()
        assert result.error is None

    @pytest.mark.asyncio
    async def test_error_handling(self, tmp_path):
        with patch("vedos.pipeline.read_raw", side_effect=FileNotFoundError("not found")):
            result = await process_file(
                file_path="/nonexistent.cr2",
                output_dir=str(tmp_path),
                film_type="color_negative",
                ai_correction=False,
            )

        assert result.error is not None
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_inversion_params_passed(self, tmp_path):
        fake_raw = _fake_raw_image()
        inverted = np.full((100, 100, 3), 40000, dtype=np.uint16)

        with (
            patch("vedos.pipeline.read_raw", return_value=fake_raw),
            patch("vedos.pipeline.auto_estimate_mask", return_value=np.array([100.0, 80.0, 60.0])),
            patch("vedos.pipeline.invert_color_negative", return_value=inverted) as mock_inv,
            patch("vedos.pipeline.write_dng", return_value=str(tmp_path / "out.dng")),
        ):
            await process_file(
                file_path="/tmp/test.cr2",
                output_dir=str(tmp_path),
                film_type="color_negative",
                ai_correction=False,
                inversion_params={"contrast": 0.5},
            )

        _, kwargs = mock_inv.call_args
        assert kwargs.get("contrast") == 0.5


# ---------------------------------------------------------------------------
# Progress callbacks
# ---------------------------------------------------------------------------

class TestProgressCallbacks:
    @pytest.mark.asyncio
    async def test_progress_callback_fires(self, tmp_path):
        fake_raw = _fake_raw_image()
        inverted = np.full((100, 100, 3), 40000, dtype=np.uint16)
        steps_seen: list[str] = []

        def on_progress(step: str, pct: float):
            steps_seen.append(step)

        with (
            patch("vedos.pipeline.read_raw", return_value=fake_raw),
            patch("vedos.pipeline.auto_estimate_mask", return_value=np.array([100.0, 80.0, 60.0])),
            patch("vedos.pipeline.invert_color_negative", return_value=inverted),
            patch("vedos.pipeline.write_dng", return_value=str(tmp_path / "out.dng")),
        ):
            await process_file(
                file_path="/tmp/test.cr2",
                output_dir=str(tmp_path),
                film_type="color_negative",
                ai_correction=False,
                progress_callback=on_progress,
            )

        assert steps_seen == ["reading", "inverting", "writing_dng", "complete"]

    @pytest.mark.asyncio
    async def test_batch_progress_events(self):
        config = _make_config(files=["/tmp/a.cr2", "/tmp/b.cr2"])
        bp = BatchProcessor(config, job_id="ev1")
        events: list[dict] = []
        bp.on_progress(lambda e: events.append(e))

        async def mock_process_file(**kwargs):
            return PipelineResult(
                output_path="/tmp/out.dng",
                input_path=kwargs["file_path"],
                processing_time_seconds=0.01,
            )

        with patch("vedos.batch_engine.process_file", side_effect=mock_process_file):
            result = await bp.process_all()

        event_types = [e["type"] for e in events]
        assert "started" in event_types
        assert "complete" in event_types
        assert result.completed == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_batch_error_events(self):
        config = _make_config(files=["/tmp/fail.cr2"])
        bp = BatchProcessor(config, job_id="err1")
        events: list[dict] = []
        bp.on_progress(lambda e: events.append(e))

        async def mock_fail(**kwargs):
            return PipelineResult(
                output_path="",
                input_path=kwargs["file_path"],
                processing_time_seconds=0.01,
                error="test error",
            )

        with patch("vedos.batch_engine.process_file", side_effect=mock_fail):
            result = await bp.process_all()

        event_types = [e["type"] for e in events]
        assert "error" in event_types
        assert result.failed == 1


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_pipeline_result_defaults(self):
        r = PipelineResult(output_path="/out.dng", input_path="/in.cr2")
        assert r.corrections is None
        assert r.processing_time_seconds == 0.0
        assert r.error is None

    def test_batch_result_defaults(self):
        r = BatchResult(job_id="j1", total_files=3)
        assert r.completed == 0
        assert r.failed == 0
        assert r.results == []
        assert r.total_time_seconds == 0.0

    def test_inversion_params_defaults(self):
        p = InversionParams()
        assert p.black_point_percentile == 0.1
        assert p.white_point_percentile == 99.9
        assert p.contrast == 1.0
