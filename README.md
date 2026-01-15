# pdf-parse

An MCP server for parsing PDFs into text, sections, tables, and references.

## Overview

`pdf-parse` is a stateless MCP (Model Context Protocol) server that provides tools for extracting structured information from PDF documents. It uses `pypdf` for text extraction and `pdfplumber` for table detection.

## Tools

### `pdf_to_text`

Extract all text from a PDF.

**Parameters:**
- `url_or_bytes` (string): Either a URL (http:// or https://) to fetch the PDF from, or base64-encoded PDF bytes.

**Returns:**
- Full text content
- Per-page text breakdown
- PDF metadata (title, author, etc.)
- Page count

**Example:**
```json
{
  "url_or_bytes": "https://example.com/document.pdf"
}
```

### `extract_sections`

Analyze text and identify sections/headings structure.

**Parameters:**
- `text` (string): The text to analyze for section structure.

**Returns:**
- Detected sections with titles and levels
- Section hierarchy
- Heading style detected (numbered, uppercase, etc.)

**Example:**
```json
{
  "text": "1. Introduction\nThis paper discusses...\n\n2. Methods\nWe used..."
}
```

### `extract_tables`

Best-effort table extraction from PDF.

**Parameters:**
- `url_or_bytes` (string): Either a URL or base64-encoded PDF bytes.

**Returns:**
- Extracted tables with headers and rows
- Table count
- Page location for each table

**Example:**
```json
{
  "url_or_bytes": "aGVsbG8gd29ybGQ="
}
```

### `extract_references`

Extract bibliography/references from academic PDF text.

**Parameters:**
- `text` (string): The text from an academic PDF.

**Returns:**
- Parsed references with extracted metadata (authors, year, DOI, etc.)
- Citation style detected
- Reference count

**Example:**
```json
{
  "text": "...document content...\n\nReferences\n[1] Smith, J. (2020). A study..."
}
```

## Response Format

All tools return responses in the standard Dedalus envelope format:

### Success Response
```json
{
  "ok": true,
  "data": {
    // Tool-specific data
  },
  "meta": {
    "source": "https://example.com/doc.pdf",
    "retrieved_at": "2024-01-15T10:30:00+00:00",
    "pagination": {"next_cursor": null},
    "warnings": []
  }
}
```

### Error Response
```json
{
  "ok": false,
  "error": {
    "code": "PARSE_ERROR",
    "message": "Failed to parse PDF: Invalid format",
    "details": {"error_type": "ValueError"}
  },
  "meta": {
    "retrieved_at": "2024-01-15T10:30:00+00:00"
  }
}
```

### Error Codes
- `INVALID_INPUT`: Bad input parameters
- `UPSTREAM_ERROR`: Error fetching from URL
- `RATE_LIMITED`: Rate limit exceeded
- `TIMEOUT`: Operation timed out
- `PARSE_ERROR`: Failed to parse PDF
- `INTERNAL_ERROR`: Unexpected internal error

## Limitations

### Scanned PDFs
This server does **not** include OCR capabilities. Scanned or image-based PDFs will return little to no text. When this is detected, a warning is included in the response.

### Table Extraction
Table extraction is best-effort using `pdfplumber`. Results may vary depending on:
- How tables are formatted in the PDF
- Complex merged cells or nested tables
- Tables rendered as images

### Section Detection
Section detection uses heuristics and works best with:
- Numbered headings (1., 1.1, 2.3.1)
- Common academic section names (Introduction, Methods, etc.)
- Uppercase headings

Documents with non-standard formatting may not have sections detected correctly.

### Reference Extraction
Reference extraction works best with:
- Numbered citation styles ([1], 1.)
- Author-year formats (Smith, 2020)
- Standard "References" or "Bibliography" section headers

## Installation

```bash
# Using uv
uv sync

# Install test dependencies
uv sync --group test
```

## Running the Server

```bash
cd src
python main.py
```

The server will start on port 8080.

## Running Tests

```bash
uv run pytest
```

## Configuration

Copy `.env.example` to `.env` and configure as needed:

```bash
cp .env.example .env
```

No authentication is required - this is a stateless server.

## Dependencies

- `dedalus-mcp>=0.4.1` - MCP server framework
- `pypdf>=4.0` - PDF text extraction
- `pdfplumber>=0.10` - Table extraction
- `httpx>=0.27` - HTTP client for fetching URLs
- `pydantic>=2.0` - Data validation
- `python-dotenv>=1.0` - Environment configuration

## License

MIT
