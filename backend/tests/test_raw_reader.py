"""Tests for the raw_reader module."""

import pytest

from vedos.raw_reader import (
    RawImage,
    RawMetadata,
    get_raw_metadata,
    get_raw_thumbnail,
    get_supported_extensions,
    read_raw,
)


class TestGetSupportedExtensions:
    def test_returns_list(self):
        exts = get_supported_extensions()
        assert isinstance(exts, list)
        assert len(exts) > 0

    def test_contains_common_formats(self):
        exts = get_supported_extensions()
        for ext in [".arw", ".cr2", ".cr3", ".nef", ".dng", ".raf"]:
            assert ext in exts, f"Expected {ext} in supported extensions"

    def test_all_start_with_dot(self):
        for ext in get_supported_extensions():
            assert ext.startswith("."), f"Extension {ext} should start with '.'"

    def test_all_lowercase(self):
        for ext in get_supported_extensions():
            assert ext == ext.lower(), f"Extension {ext} should be lowercase"

    def test_returns_copy(self):
        """Ensure modifying the returned list doesn't affect the source."""
        exts = get_supported_extensions()
        exts.clear()
        assert len(get_supported_extensions()) > 0


class TestReadRaw:
    def test_nonexistent_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="RAW file not found"):
            read_raw("/nonexistent/path/image.cr2")

    def test_unsupported_extension_raises_value_error(self, tmp_path):
        fake = tmp_path / "photo.jpg"
        fake.write_bytes(b"\xff\xd8\xff")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            read_raw(str(fake))


class TestGetRawMetadata:
    def test_nonexistent_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="RAW file not found"):
            get_raw_metadata("/nonexistent/path/image.nef")

    def test_unsupported_extension_raises_value_error(self, tmp_path):
        fake = tmp_path / "photo.png"
        fake.write_bytes(b"\x89PNG")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            get_raw_metadata(str(fake))


class TestGetRawThumbnail:
    def test_nonexistent_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="RAW file not found"):
            get_raw_thumbnail("/nonexistent/path/image.arw")

    def test_unsupported_extension_raises_value_error(self, tmp_path):
        fake = tmp_path / "photo.bmp"
        fake.write_bytes(b"BM")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            get_raw_thumbnail(str(fake))


class TestDataclasses:
    def test_raw_metadata_fields(self):
        meta = RawMetadata(
            camera_make="Sony",
            camera_model="A7III",
            iso=400,
            exposure_time=0.01,
            f_number=2.8,
            focal_length=50.0,
            timestamp="2024-01-01T00:00:00+00:00",
            width=6000,
            height=4000,
        )
        assert meta.camera_make == "Sony"
        assert meta.width == 6000

    def test_raw_image_defaults(self):
        import numpy as np

        img = RawImage(
            data=np.zeros((10, 10, 3), dtype=np.uint16),
            metadata=RawMetadata(
                camera_make="", camera_model="", iso=None,
                exposure_time=None, f_number=None, focal_length=None,
                timestamp=None, width=10, height=10,
            ),
            file_path="/tmp/test.cr2",
        )
        assert img.black_levels == []
        assert img.white_level == 0
