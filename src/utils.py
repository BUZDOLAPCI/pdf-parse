"""Shared utilities for the pdf-parse MCP server."""

import base64
import io
from datetime import datetime, timezone
from typing import Any

import httpx


def iso_timestamp() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def success_response(
    data: dict[str, Any],
    source: str | None = None,
    warnings: list[str] | None = None,
    pagination: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard success response envelope."""
    meta: dict[str, Any] = {
        "retrieved_at": iso_timestamp(),
        "warnings": warnings or [],
    }
    if source:
        meta["source"] = source
    if pagination:
        meta["pagination"] = pagination
    else:
        meta["pagination"] = {"next_cursor": None}

    return {
        "ok": True,
        "data": data,
        "meta": meta,
    }


def error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard error response envelope.

    Valid error codes:
    - INVALID_INPUT: Bad input parameters
    - UPSTREAM_ERROR: Error fetching from URL
    - RATE_LIMITED: Rate limit exceeded
    - TIMEOUT: Operation timed out
    - PARSE_ERROR: Failed to parse PDF
    - INTERNAL_ERROR: Unexpected internal error
    """
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "meta": {
            "retrieved_at": iso_timestamp(),
        },
    }


async def fetch_pdf_bytes(url_or_bytes: str) -> tuple[bytes, str | None]:
    """Fetch PDF bytes from URL or decode from base64.

    Args:
        url_or_bytes: Either a URL (http:// or https://) or base64-encoded PDF bytes

    Returns:
        Tuple of (pdf_bytes, source_url_or_none)

    Raises:
        ValueError: If input is invalid
        httpx.HTTPError: If URL fetch fails
    """
    if url_or_bytes.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url_or_bytes)
            response.raise_for_status()
            return response.content, url_or_bytes
    else:
        # Treat as base64-encoded bytes
        try:
            pdf_bytes = base64.b64decode(url_or_bytes)
            return pdf_bytes, None
        except Exception as e:
            raise ValueError(f"Invalid base64 data: {e}")


def get_pdf_stream(pdf_bytes: bytes) -> io.BytesIO:
    """Create a BytesIO stream from PDF bytes."""
    return io.BytesIO(pdf_bytes)


def check_scanned_pdf(text: str, page_count: int) -> bool:
    """Check if PDF appears to be scanned (little/no extractable text).

    Heuristic: If average characters per page is very low, it's likely scanned.
    """
    if page_count == 0:
        return True
    avg_chars_per_page = len(text) / page_count
    # Less than 100 characters per page on average suggests scanned PDF
    return avg_chars_per_page < 100
