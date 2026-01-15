"""PDF to text extraction tool."""

from typing import Any

import httpx
from dedalus_mcp import tool
from pypdf import PdfReader

from utils import (
    check_scanned_pdf,
    error_response,
    fetch_pdf_bytes,
    get_pdf_stream,
    success_response,
)


@tool(description="Extract all text from a PDF (url or base64-encoded bytes)")
async def pdf_to_text(url_or_bytes: str) -> dict[str, Any]:
    """Extract all text from a PDF.

    Args:
        url_or_bytes: Either a URL (http:// or https://) to fetch the PDF from,
                      or base64-encoded PDF bytes.

    Returns:
        Standard response envelope with extracted text and metadata.
    """
    try:
        pdf_bytes, source = await fetch_pdf_bytes(url_or_bytes)
    except ValueError as e:
        return error_response(
            code="INVALID_INPUT",
            message=str(e),
            details={"input_type": "base64"},
        )
    except httpx.HTTPStatusError as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"Failed to fetch PDF: HTTP {e.response.status_code}",
            details={"url": url_or_bytes, "status_code": e.response.status_code},
        )
    except httpx.TimeoutException:
        return error_response(
            code="TIMEOUT",
            message="Timeout while fetching PDF",
            details={"url": url_or_bytes},
        )
    except httpx.HTTPError as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"Failed to fetch PDF: {e}",
            details={"url": url_or_bytes},
        )

    try:
        stream = get_pdf_stream(pdf_bytes)
        reader = PdfReader(stream)

        pages_text = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            pages_text.append({
                "page_number": i + 1,
                "text": page_text,
            })

        full_text = "\n\n".join(p["text"] for p in pages_text)
        page_count = len(reader.pages)

        warnings = []
        if check_scanned_pdf(full_text, page_count):
            warnings.append(
                "This PDF appears to be scanned or image-based. "
                "Text extraction may be incomplete. OCR is not supported."
            )

        metadata = {}
        if reader.metadata:
            for key in ["title", "author", "subject", "creator", "producer"]:
                value = getattr(reader.metadata, key, None)
                if value:
                    metadata[key] = str(value)

        return success_response(
            data={
                "text": full_text,
                "pages": pages_text,
                "page_count": page_count,
                "metadata": metadata,
            },
            source=source,
            warnings=warnings,
        )

    except Exception as e:
        return error_response(
            code="PARSE_ERROR",
            message=f"Failed to parse PDF: {e}",
            details={"error_type": type(e).__name__},
        )
