"""Focused coverage for native MOBI-family upload metadata extraction."""

import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from cps import mobi, uploader


MOBI_FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample_books" / "alice_in_wonderland.mobi"


def _exth_record(record_type, value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return struct.pack(">II", record_type, len(value) + 8) + value


def _make_mobi_fixture(path):
    """Write a small uncompressed Palm/MOBI file with representative EXTH data."""
    header_length = 232
    mobi_header = bytearray(header_length)
    mobi_header[0:4] = b"MOBI"
    mobi_header[4:8] = struct.pack(">I", header_length)
    mobi_header[12:16] = struct.pack(">I", 65001)  # UTF-8
    mobi_header[0x5C:0x60] = struct.pack(">I", 1)  # first image record

    exth_records = b"".join([
        _exth_record(100, "Doe, Jane & John Smith"),
        _exth_record(101, "Acme Publishing"),
        _exth_record(103, "A description from the native MOBI record."),
        _exth_record(104, "9781234567890"),
        _exth_record(105, "Fantasy"),
        _exth_record(105, "Mystery"),
        _exth_record(106, "2024-03-15T00:00:00Z"),
        _exth_record(201, struct.pack(">I", 0)),
        _exth_record(503, "Synthetic EXTH title"),
        _exth_record(524, "en-US"),
    ])
    exth = b"EXTH" + struct.pack(">II", len(exth_records) + 12, 10) + exth_records
    title = "Native MOBI title".encode("utf-8")
    title_offset = 16 + header_length + len(exth)
    mobi_header[0x44:0x48] = struct.pack(">I", title_offset)
    mobi_header[0x48:0x4C] = struct.pack(">I", len(title))
    record_zero = b"\0" * 16 + bytes(mobi_header) + exth + title
    image_record = b"\x89PNG\r\n\x1a\nsynthetic-cover"

    record_table_end = 78 + 2 * 8
    first_record_offset = record_table_end
    second_record_offset = first_record_offset + len(record_zero)
    pdb_header = bytearray(78)
    pdb_header[76:78] = struct.pack(">H", 2)
    record_table = struct.pack(">I", first_record_offset) + b"\0" * 4
    record_table += struct.pack(">I", second_record_offset) + b"\0" * 4
    path.write_bytes(bytes(pdb_header) + record_table + record_zero + image_record)


@pytest.mark.unit
def test_real_mobi_fixture_extracts_metadata_and_cover(tmp_path):
    """The checked-in MOBI fixture exercises parsing of a real file layout."""
    cover_path = tmp_path / "cover.jpg"

    def save_cover(_, image, extension):
        assert extension == ".jpg"
        assert image.startswith(b"\xff\xd8\xff")
        cover_path.write_bytes(image)
        return str(cover_path)

    with patch.object(mobi.cover, "cover_processing", side_effect=save_cover):
        meta = mobi.get_mobi_info(str(MOBI_FIXTURE), "fallback", ".mobi", False)

    assert meta.title == "Alice's Adventures in Wonderland"
    assert meta.author == "Lewis Carroll"
    assert meta.languages == "eng"
    assert meta.pubdate == "2008-06-27"
    assert "Fantasy fiction" in meta.tags
    assert meta.cover == str(cover_path)
    assert cover_path.exists()


@pytest.mark.unit
def test_synthetic_mobi_extracts_exth_metadata_and_explicit_cover(tmp_path):
    mobi_path = tmp_path / "book.mobi"
    _make_mobi_fixture(mobi_path)
    cover_path = tmp_path / "cover.jpg"

    def save_cover(_, image, extension):
        assert extension == ".png"
        cover_path.write_bytes(image)
        return str(cover_path)

    with patch.object(mobi.cover, "cover_processing", side_effect=save_cover):
        meta = mobi.get_mobi_info(str(mobi_path), "fallback", ".mobi", False)

    assert meta.title == "Native MOBI title"
    assert meta.author == "Jane Doe & John Smith"
    assert meta.publisher == "Acme Publishing"
    assert meta.description == "A description from the native MOBI record."
    assert meta.tags == "Fantasy, Mystery"
    assert meta.languages == "eng"
    assert meta.pubdate == "2024-03-15"
    assert meta.identifiers == [["isbn", "9781234567890"]]
    assert meta.cover == str(cover_path)


@pytest.mark.unit
@pytest.mark.parametrize("extension", [".mobi", ".azw", ".azw3", ".prc", ".pobi"])
def test_uploader_routes_mobi_family_to_native_parser(tmp_path, extension):
    mobi_path = tmp_path / "book.bin"
    _make_mobi_fixture(mobi_path)

    meta = uploader.process(str(mobi_path), "fallback", extension, "", no_cover=True)

    assert meta.title == "Native MOBI title"
    assert meta.author == "Jane Doe & John Smith"
    assert meta.cover is None


@pytest.mark.unit
def test_mobi_metadata_failure_keeps_existing_default_fallback(tmp_path):
    broken_path = tmp_path / "broken.mobi"
    broken_path.write_bytes(b"not a Palm database")

    meta = uploader.process(str(broken_path), "broken", ".mobi", "", no_cover=True)

    assert meta.title == "broken"
    assert meta.author == "Unknown"
    assert meta.cover is None


@pytest.mark.unit
def test_mobi_no_cover_processing_does_not_extract_cover(tmp_path):
    mobi_path = tmp_path / "book.mobi"
    _make_mobi_fixture(mobi_path)

    with patch.object(mobi.cover, "cover_processing") as extract_cover:
        meta = mobi.get_mobi_info(str(mobi_path), "fallback", ".mobi", True)

    assert meta.cover is None
    extract_cover.assert_not_called()
