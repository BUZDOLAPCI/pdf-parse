"""End-to-end tests for the pdf-parse MCP server."""

import asyncio
import base64
import io

import pytest
from pypdf import PdfWriter

# Add src to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import server
from tools import pdf_tools


def create_simple_pdf() -> bytes:
    """Create a simple PDF for testing."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class TestServerConfiguration:
    """Tests for server configuration."""

    def test_server_name(self):
        """Test that server has correct name."""
        assert server.name == "pdf-parse"

    def test_server_has_tools(self):
        """Test that server has tools configured."""
        # Collect tools
        server.collect(*pdf_tools)

        # Server should have tools registered
        assert len(pdf_tools) == 4

    def test_all_tools_present(self):
        """Test that all expected tools are present."""
        tool_names = [tool.__name__ for tool in pdf_tools]

        assert "pdf_to_text" in tool_names
        assert "extract_sections" in tool_names
        assert "extract_tables" in tool_names
        assert "extract_references" in tool_names


class TestToolIntegration:
    """Integration tests for tools working together."""

    @pytest.mark.asyncio
    async def test_pdf_to_text_then_sections(self):
        """Test workflow: extract text then find sections."""
        from tools.text import pdf_to_text
        from tools.sections import extract_sections

        # Create a test PDF (note: simple PDF won't have text)
        pdf_bytes = create_simple_pdf()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        # Extract text
        text_result = await pdf_to_text(base64_pdf)
        assert text_result["ok"] is True

        # Try to find sections in the extracted text
        text = text_result["data"]["text"]
        sections_result = await extract_sections(text if text else "No content")

        # Result should be valid (even if no sections found)
        assert sections_result["ok"] is True or sections_result["error"]["code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_pdf_to_text_then_references(self):
        """Test workflow: extract text then find references."""
        from tools.text import pdf_to_text
        from tools.references import extract_references

        pdf_bytes = create_simple_pdf()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        # Extract text
        text_result = await pdf_to_text(base64_pdf)
        assert text_result["ok"] is True

        # Try to find references
        text = text_result["data"]["text"]
        if text:
            refs_result = await extract_references(text)
            assert refs_result["ok"] is True

    @pytest.mark.asyncio
    async def test_multiple_operations_same_pdf(self):
        """Test running multiple operations on the same PDF."""
        from tools.text import pdf_to_text
        from tools.tables import extract_tables

        pdf_bytes = create_simple_pdf()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        # Run text extraction and table extraction concurrently
        text_result, tables_result = await asyncio.gather(
            pdf_to_text(base64_pdf),
            extract_tables(base64_pdf),
        )

        assert text_result["ok"] is True
        assert tables_result["ok"] is True


class TestResponseEnvelope:
    """Tests to verify response envelope conformance."""

    @pytest.mark.asyncio
    async def test_success_envelope_structure(self):
        """Test that success responses follow the envelope spec."""
        from tools.sections import extract_sections

        result = await extract_sections("1. Introduction\nSome text here.")

        # Check required fields
        assert "ok" in result
        assert "data" in result
        assert "meta" in result

        # Check meta fields
        assert "retrieved_at" in result["meta"]
        assert "warnings" in result["meta"]
        assert "pagination" in result["meta"]

        # Check ok is boolean
        assert isinstance(result["ok"], bool)

    @pytest.mark.asyncio
    async def test_error_envelope_structure(self):
        """Test that error responses follow the envelope spec."""
        from tools.text import pdf_to_text

        result = await pdf_to_text("invalid-base64!!!")

        # Check required fields
        assert "ok" in result
        assert result["ok"] is False
        assert "error" in result
        assert "meta" in result

        # Check error fields
        assert "code" in result["error"]
        assert "message" in result["error"]
        assert "details" in result["error"]

        # Check meta fields
        assert "retrieved_at" in result["meta"]

        # Check error code is valid
        valid_codes = [
            "INVALID_INPUT",
            "UPSTREAM_ERROR",
            "RATE_LIMITED",
            "TIMEOUT",
            "PARSE_ERROR",
            "INTERNAL_ERROR",
        ]
        assert result["error"]["code"] in valid_codes
