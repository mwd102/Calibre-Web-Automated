"""Kobo sync must offer a downloadable PDF for PDF-only library entries."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


@pytest.mark.unit
@pytest.mark.parametrize(
    ("formats", "expected_format", "expected_suffix"),
    [
        (["PDF"], "PDF", "/pdf"),
        (["PDF", "EPUB"], "EPUB3", "/epub"),
        (["PDF", "KEPUB"], "KEPUB", "/kepub"),
    ],
)
def test_kobo_download_metadata_includes_pdf_without_replacing_ebook_preference(
    monkeypatch, formats, expected_format, expected_suffix
):
    from cps import kobo

    assert "PDF" in kobo.KOBO_FORMATS
    monkeypatch.setattr(kobo.config, "config_kepubifypath", None, raising=False)
    monkeypatch.setattr(kobo, "_get_cover_image_id", lambda book: book.uuid)
    monkeypatch.setattr(kobo, "get_download_url_for_book", lambda book_id, fmt: f"/download/{book_id}/{fmt}")
    monkeypatch.setattr(kobo, "get_description", lambda book: None)
    monkeypatch.setattr(kobo, "get_author", lambda book: {"Contributors": None})
    monkeypatch.setattr(kobo, "get_publisher", lambda book: None)
    monkeypatch.setattr(kobo, "get_series", lambda book: None)
    monkeypatch.setattr(kobo, "get_language", lambda book: "en")
    monkeypatch.setattr(kobo, "convert_to_kobo_timestamp_string", lambda value: value.isoformat())
    monkeypatch.setattr(kobo, "get_epub_layout", lambda book, data: "reflowable")

    now = datetime.now(timezone.utc)
    book = SimpleNamespace(
        id=42,
        uuid="12345678-1234-1234-1234-123456789abc",
        title="Example PDF",
        pubdate=now,
        data=[SimpleNamespace(format=fmt, uncompressed_size=1024) for fmt in formats],
    )

    urls = kobo.get_metadata(book)["DownloadUrls"]
    assert len(urls) == 1
    assert urls[0]["Format"] == expected_format
    assert urls[0]["Size"] == 1024
    assert urls[0]["Url"].endswith(expected_suffix)
