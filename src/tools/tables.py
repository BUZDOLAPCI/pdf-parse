"""Table extraction tool using pdfplumber."""

from typing import Any

import httpx
import pdfplumber
from dedalus_mcp import tool

from utils import (
    error_response,
    fetch_pdf_bytes,
    get_pdf_stream,
    success_response,
)


def _clean_table_cell(cell: Any) -> str:
    """Clean and normalize a table cell value."""
    if cell is None:
        return ""
    return str(cell).strip()


def _table_to_dict(table: list[list[Any]], use_header: bool = True) -> dict[str, Any]:
    """Convert a table to a dictionary with rows and optional headers."""
    if not table:
        return {"headers": [], "rows": [], "row_count": 0, "column_count": 0}

    cleaned_table = [[_clean_table_cell(cell) for cell in row] for row in table]

    if use_header and len(cleaned_table) > 1:
        headers = cleaned_table[0]
        rows = cleaned_table[1:]
    else:
        headers = []
        rows = cleaned_table

    return {
        "headers": headers,
        "rows": rows,
        "row_count": len(rows),
        "column_count": len(cleaned_table[0]) if cleaned_table else 0,
    }


@tool(description="Best-effort table extraction from PDF")
async def extract_tables(url_or_bytes: str) -> dict[str, Any]:
    """Extract tables from a PDF using pdfplumber.

    This is a best-effort extraction - results may vary depending on
    the PDF structure and how tables are formatted.

    Args:
        url_or_bytes: Either a URL (http:// or https://) to fetch the PDF from,
                      or base64-encoded PDF bytes.

    Returns:
        Standard response envelope with extracted tables and metadata.
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
        tables_data = []
        warnings = []

        with pdfplumber.open(stream) as pdf:
            page_count = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                page_tables = page.extract_tables()

                for table_idx, table in enumerate(page_tables):
                    if not table or not any(table):
                        continue

                    table_dict = _table_to_dict(table)

                    # Skip empty or trivial tables
                    if table_dict["row_count"] == 0:
                        continue

                    tables_data.append({
                        "page_number": page_num,
                        "table_index": table_idx + 1,
                        **table_dict,
                    })

        if not tables_data:
            warnings.append(
                "No tables were detected in this PDF. "
                "Tables may be embedded as images or have non-standard formatting."
            )

        return success_response(
            data={
                "tables": tables_data,
                "table_count": len(tables_data),
                "page_count": page_count,
            },
            source=source,
            warnings=warnings,
        )

    except Exception as e:
        return error_response(
            code="PARSE_ERROR",
            message=f"Failed to extract tables from PDF: {e}",
            details={"error_type": type(e).__name__},
        )
