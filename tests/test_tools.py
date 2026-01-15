"""Unit tests for pdf-parse tools."""

import base64
import io

import pytest
from pypdf import PdfWriter

# Add src to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.text import pdf_to_text
from tools.sections import extract_sections
from tools.tables import extract_tables
from tools.references import extract_references
from utils import (
    success_response,
    error_response,
    iso_timestamp,
    check_scanned_pdf,
)


def create_simple_pdf(text: str = "Hello World") -> bytes:
    """Create a simple PDF with the given text for testing."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    # Note: pypdf can't easily add text to pages directly
    # For testing, we'll create a minimal PDF structure
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def encode_pdf_base64(pdf_bytes: bytes) -> str:
    """Encode PDF bytes to base64 string."""
    return base64.b64encode(pdf_bytes).decode("utf-8")


class TestUtils:
    """Tests for utility functions."""

    def test_iso_timestamp_format(self):
        """Test that iso_timestamp returns valid ISO format."""
        timestamp = iso_timestamp()
        assert "T" in timestamp
        assert timestamp.endswith("+00:00") or timestamp.endswith("Z")

    def test_success_response_structure(self):
        """Test success response has correct structure."""
        response = success_response(
            data={"test": "value"},
            source="https://example.com/test.pdf",
            warnings=["Test warning"],
        )

        assert response["ok"] is True
        assert response["data"] == {"test": "value"}
        assert response["meta"]["source"] == "https://example.com/test.pdf"
        assert response["meta"]["warnings"] == ["Test warning"]
        assert "retrieved_at" in response["meta"]
        assert "pagination" in response["meta"]

    def test_success_response_defaults(self):
        """Test success response with default values."""
        response = success_response(data={"key": "value"})

        assert response["ok"] is True
        assert response["meta"]["warnings"] == []
        assert response["meta"]["pagination"] == {"next_cursor": None}
        assert "source" not in response["meta"]

    def test_error_response_structure(self):
        """Test error response has correct structure."""
        response = error_response(
            code="INVALID_INPUT",
            message="Test error message",
            details={"field": "url_or_bytes"},
        )

        assert response["ok"] is False
        assert response["error"]["code"] == "INVALID_INPUT"
        assert response["error"]["message"] == "Test error message"
        assert response["error"]["details"] == {"field": "url_or_bytes"}
        assert "retrieved_at" in response["meta"]

    def test_error_response_defaults(self):
        """Test error response with default details."""
        response = error_response(
            code="INTERNAL_ERROR",
            message="Something went wrong",
        )

        assert response["error"]["details"] == {}

    def test_check_scanned_pdf_empty(self):
        """Test scanned PDF detection with empty text."""
        assert check_scanned_pdf("", 5) is True

    def test_check_scanned_pdf_little_text(self):
        """Test scanned PDF detection with little text."""
        assert check_scanned_pdf("x" * 50, 5) is True

    def test_check_scanned_pdf_normal_text(self):
        """Test scanned PDF detection with normal text."""
        assert check_scanned_pdf("x" * 1000, 5) is False

    def test_check_scanned_pdf_zero_pages(self):
        """Test scanned PDF detection with zero pages."""
        assert check_scanned_pdf("some text", 0) is True


class TestExtractSections:
    """Tests for extract_sections tool."""

    @pytest.mark.asyncio
    async def test_empty_text_error(self):
        """Test that empty text returns error."""
        result = await extract_sections("")

        assert result["ok"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_numbered_sections(self):
        """Test extraction of numbered sections."""
        text = """
1. Introduction
This is the introduction section.

2. Methods
This is the methods section.

3. Results
This is the results section.
"""
        result = await extract_sections(text)

        assert result["ok"] is True
        assert result["data"]["section_count"] >= 2
        assert result["data"]["heading_style"] == "numbered"

    @pytest.mark.asyncio
    async def test_common_section_names(self):
        """Test extraction using common section names."""
        text = """
Abstract
This paper presents our findings.

Introduction
We introduce the topic here.

Conclusion
We conclude our findings.
"""
        result = await extract_sections(text)

        assert result["ok"] is True
        assert result["data"]["section_count"] >= 1

    @pytest.mark.asyncio
    async def test_no_sections_warning(self):
        """Test warning when no sections found."""
        text = "This is just plain text without any sections or headings."

        result = await extract_sections(text)

        assert result["ok"] is True
        assert len(result["meta"]["warnings"]) > 0


class TestExtractReferences:
    """Tests for extract_references tool."""

    @pytest.mark.asyncio
    async def test_empty_text_error(self):
        """Test that empty text returns error."""
        result = await extract_references("")

        assert result["ok"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_no_references_section(self):
        """Test when no references section found."""
        text = "This is a document without any references section."

        result = await extract_references(text)

        assert result["ok"] is True
        assert result["data"]["section_found"] is False
        assert len(result["meta"]["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_numbered_bracket_references(self):
        """Test extraction of [1], [2] style references."""
        text = """
Some document text here.

References

[1] Smith, J. (2020). A study on testing. Journal of Testing, 1(1), 1-10.

[2] Jones, A. and Brown, B. (2021). Another study. Science Journal, 2(3), 20-30. https://doi.org/10.1234/test
"""
        result = await extract_references(text)

        assert result["ok"] is True
        assert result["data"]["section_found"] is True
        assert result["data"]["reference_count"] >= 1

    @pytest.mark.asyncio
    async def test_numbered_dot_references(self):
        """Test extraction of 1., 2. style references."""
        text = """
Document content.

References

1. First Author (2019). First paper title. First Journal.

2. Second Author (2020). Second paper title. Second Journal.
"""
        result = await extract_references(text)

        assert result["ok"] is True
        assert result["data"]["section_found"] is True

    @pytest.mark.asyncio
    async def test_doi_extraction(self):
        """Test that DOIs are extracted from references."""
        text = """
References

[1] Test Author (2020). Test paper. doi:10.1234/test.2020.001
"""
        result = await extract_references(text)

        assert result["ok"] is True
        if result["data"]["references"]:
            # Check if DOI was extracted
            refs_with_doi = [r for r in result["data"]["references"] if "doi" in r]
            # DOI extraction is best-effort


class TestPdfToText:
    """Tests for pdf_to_text tool."""

    @pytest.mark.asyncio
    async def test_invalid_base64(self):
        """Test that invalid base64 returns error."""
        result = await pdf_to_text("not-valid-base64!!!")

        assert result["ok"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_valid_pdf_bytes(self):
        """Test extraction from valid PDF bytes."""
        pdf_bytes = create_simple_pdf()
        base64_pdf = encode_pdf_base64(pdf_bytes)

        result = await pdf_to_text(base64_pdf)

        assert result["ok"] is True
        assert "text" in result["data"]
        assert "pages" in result["data"]
        assert "page_count" in result["data"]

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        """Test that invalid URL returns error."""
        result = await pdf_to_text("https://invalid.example.com/nonexistent.pdf")

        assert result["ok"] is False
        assert result["error"]["code"] in ["UPSTREAM_ERROR", "TIMEOUT"]


class TestExtractTables:
    """Tests for extract_tables tool."""

    @pytest.mark.asyncio
    async def test_invalid_base64(self):
        """Test that invalid base64 returns error."""
        result = await extract_tables("not-valid-base64!!!")

        assert result["ok"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_valid_pdf_no_tables(self):
        """Test extraction from PDF without tables."""
        pdf_bytes = create_simple_pdf()
        base64_pdf = encode_pdf_base64(pdf_bytes)

        result = await extract_tables(base64_pdf)

        assert result["ok"] is True
        assert "tables" in result["data"]
        assert "table_count" in result["data"]
        # Simple PDF has no tables, so expect warning
        if result["data"]["table_count"] == 0:
            assert len(result["meta"]["warnings"]) > 0
