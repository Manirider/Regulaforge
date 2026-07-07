"""Tests for metadata extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from regulaforge.document_intelligence.extraction.metadata import (
    PdfMetadataExtractor,
    TextMetadataExtractor,
)


def test_pdf_metadata_name():
    ext = PdfMetadataExtractor()
    assert ext.name == "pdf-metadata"


@pytest.mark.asyncio
async def test_pdf_metadata_not_available():
    ext = PdfMetadataExtractor()
    available = await ext.is_available()
    assert isinstance(available, bool)


def test_parse_pdf_date():
    ext = PdfMetadataExtractor()
    d = ext._parse_pdf_date("D:20240115120000Z")
    assert d is not None
    assert d.year == 2024
    assert d.month == 1
    assert d.day == 15


def test_parse_pdf_date_none():
    ext = PdfMetadataExtractor()
    assert ext._parse_pdf_date(None) is None


def test_parse_pdf_date_empty():
    ext = PdfMetadataExtractor()
    assert ext._parse_pdf_date("") is None


@pytest.mark.asyncio
async def test_text_metadata_empty():
    ext = TextMetadataExtractor()
    result = await ext.extract(Path("/fake.txt"), text=None)
    assert result.title is None


@pytest.mark.asyncio
async def test_text_metadata_empty_string():
    ext = TextMetadataExtractor()
    result = await ext.extract(Path("/fake.txt"), text="")
    assert result.title is None


@pytest.mark.asyncio
async def test_text_metadata_detects_regulation_title():
    ext = TextMetadataExtractor()
    text = "Circular on Risk Management\n\nThis circular applies to all banks."
    result = await ext.extract(Path("/fake.txt"), text=text)
    assert result.title is not None
    assert "Circular" in result.title


@pytest.mark.asyncio
async def test_text_metadata_detects_date():
    ext = TextMetadataExtractor()
    text = (
        "Guidelines for Foreign Investment\n"
        "15 January 2024\n"
        "The Board of Directors\n"
    )
    result = await ext.extract(Path("/fake.txt"), text=text)
    assert result.creation_date is not None
    assert result.creation_date.year == 2024
    assert result.creation_date.month == 1
    assert result.creation_date.day == 15


@pytest.mark.asyncio
async def test_text_metadata_confidence():
    ext = TextMetadataExtractor()
    result = await ext.extract(Path("/fake.txt"), text="Some random text without patterns.")
    assert result.confidence == 0.6


@pytest.mark.asyncio
async def test_text_metadata_page_count():
    ext = TextMetadataExtractor()
    result = await ext.extract(Path("/fake.txt"), text="text", page_count=5)
    assert result.page_count == 5
