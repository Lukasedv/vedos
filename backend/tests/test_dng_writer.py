"""Tests for the DNG/TIFF writer module."""

from __future__ import annotations

import numpy as np
import pytest
import tifffile

from vedos.dng_writer import (
    SRGB_D65_MATRIX,
    write_dng,
    write_tiff,
    write_tiff_16bit,
)
from vedos.raw_reader import RawMetadata


def _synthetic_image(h: int = 100, w: int = 100) -> np.ndarray:
    """Create a synthetic (H, W, 3) uint16 test image."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 65535, size=(h, w, 3), dtype=np.uint16)


def _sample_metadata() -> RawMetadata:
    return RawMetadata(
        camera_make="TestMake",
        camera_model="TestModel",
        iso=400,
        exposure_time=1 / 125,
        f_number=5.6,
        focal_length=50.0,
        timestamp="2024-01-15T12:00:00+00:00",
        width=100,
        height=100,
    )


class TestWriteDng:
    def test_basic_write(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "test.dng"
        result = write_dng(img, str(out))
        assert out.exists()
        assert result == str(out)

    def test_output_is_valid_tiff(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "test.dng"
        write_dng(img, str(out))
        with tifffile.TiffFile(str(out)) as tif:
            assert len(tif.pages) == 1
            page = tif.pages[0]
            assert page.shape == (100, 100, 3)
            assert page.dtype == np.uint16

    def test_roundtrip_data(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "test.dng"
        write_dng(img, str(out))
        read_back = tifffile.imread(str(out))
        np.testing.assert_array_equal(img, read_back)

    def test_with_metadata(self, tmp_path):
        img = _synthetic_image()
        meta = _sample_metadata()
        out = tmp_path / "meta.dng"
        result = write_dng(img, str(out), metadata=meta)
        assert out.exists()
        with tifffile.TiffFile(str(out)) as tif:
            page = tif.pages[0]
            desc = page.description
            assert "Vedos" in (desc or "")

    def test_custom_color_matrix(self, tmp_path):
        img = _synthetic_image()
        custom_matrix = np.eye(3, dtype=np.float64)
        out = tmp_path / "custom.dng"
        write_dng(img, str(out), color_matrix=custom_matrix)
        assert out.exists()

    def test_custom_as_shot_neutral(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "neutral.dng"
        write_dng(img, str(out), as_shot_neutral=(0.9, 1.0, 0.8))
        assert out.exists()

    def test_dng_tags_present(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "tags.dng"
        write_dng(img, str(out))
        with tifffile.TiffFile(str(out)) as tif:
            page = tif.pages[0]
            tags = {t.name: t for t in page.tags.values()}
            assert "DNGVersion" in tags or 50706 in {t.code for t in page.tags.values()}

    def test_invalid_shape_raises(self, tmp_path):
        img = np.zeros((100, 100), dtype=np.uint16)
        out = tmp_path / "bad.dng"
        with pytest.raises(ValueError, match="Expected"):
            write_dng(img, str(out))

    def test_creates_parent_dirs(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "sub" / "dir" / "test.dng"
        write_dng(img, str(out))
        assert out.exists()

    def test_accepts_path_object(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "pathobj.dng"
        result = write_dng(img, out)
        assert out.exists()
        assert result == str(out)


class TestWriteTiff16bit:
    def test_basic_write(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "test.tiff"
        result = write_tiff_16bit(img, str(out))
        assert out.exists()
        assert result == str(out)

    def test_output_is_valid_tiff(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "test.tiff"
        write_tiff_16bit(img, str(out))
        with tifffile.TiffFile(str(out)) as tif:
            page = tif.pages[0]
            assert page.shape == (100, 100, 3)
            assert page.dtype == np.uint16

    def test_roundtrip_data(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "test.tiff"
        write_tiff_16bit(img, str(out))
        read_back = tifffile.imread(str(out))
        np.testing.assert_array_equal(img, read_back)

    def test_with_metadata(self, tmp_path):
        img = _synthetic_image()
        meta = _sample_metadata()
        out = tmp_path / "meta.tiff"
        result = write_tiff_16bit(img, str(out), metadata=meta)
        assert out.exists()
        with tifffile.TiffFile(str(out)) as tif:
            desc = tif.pages[0].description
            assert "TestModel" in (desc or "")

    def test_invalid_shape_raises(self, tmp_path):
        img = np.zeros((100,), dtype=np.uint16)
        out = tmp_path / "bad.tiff"
        with pytest.raises(ValueError, match="Expected"):
            write_tiff_16bit(img, str(out))


class TestBackwardCompat:
    def test_write_tiff_alias(self, tmp_path):
        img = _synthetic_image()
        out = tmp_path / "compat.tiff"
        result = write_tiff(img, str(out))
        assert out.exists()
        assert isinstance(result, type(out))
