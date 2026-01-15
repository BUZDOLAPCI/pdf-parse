"""Reference extraction tool for academic PDF text."""

import re
from typing import Any

from dedalus_mcp import tool

from utils import error_response, success_response

# Patterns to find references section
REFERENCES_SECTION_PATTERNS = [
    re.compile(r"(?:^|\n)\s*references?\s*\n", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*bibliography\s*\n", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*works?\s+cited\s*\n", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*literature\s+cited\s*\n", re.IGNORECASE),
]

# Common citation patterns
# [1], [2], [3] style
NUMBERED_BRACKET_PATTERN = re.compile(r"^\s*\[(\d+)\]\s*(.+?)(?=\n\s*\[\d+\]|\n\n|\Z)", re.MULTILINE | re.DOTALL)

# 1., 2., 3. style
NUMBERED_DOT_PATTERN = re.compile(r"^\s*(\d+)\.\s+(.+?)(?=\n\s*\d+\.|\n\n|\Z)", re.MULTILINE | re.DOTALL)

# Author (Year) style - common in APA
AUTHOR_YEAR_PATTERN = re.compile(
    r"^([A-Z][a-zA-Z\-\']+(?:,?\s+(?:and\s+)?[A-Z]\.?\s*)+\.?\s*\(\d{4}\).+?)(?=\n[A-Z][a-zA-Z\-\']+(?:,?\s+(?:and\s+)?[A-Z]\.?\s*)+|\n\n|\Z)",
    re.MULTILINE | re.DOTALL,
)

# DOI pattern
DOI_PATTERN = re.compile(r"(?:doi[:\s]*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,}/[^\s]+)", re.IGNORECASE)

# URL pattern
URL_PATTERN = re.compile(r"https?://[^\s\]\)]+")

# Year pattern
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def _find_references_section(text: str) -> tuple[str, int]:
    """Find the references section in the text.

    Returns:
        Tuple of (references_text, start_position) or ("", -1) if not found.
    """
    for pattern in REFERENCES_SECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            # Get text from the match to the end (or next major section)
            start = match.end()
            remaining = text[start:]

            # Try to find where references end (common patterns)
            end_patterns = [
                re.compile(r"\n\s*appendix", re.IGNORECASE),
                re.compile(r"\n\s*supplementary", re.IGNORECASE),
                re.compile(r"\n\s*acknowledgment", re.IGNORECASE),
                re.compile(r"\n\s*acknowledgement", re.IGNORECASE),
            ]

            end_pos = len(remaining)
            for end_pattern in end_patterns:
                end_match = end_pattern.search(remaining)
                if end_match and end_match.start() < end_pos:
                    end_pos = end_match.start()

            return remaining[:end_pos].strip(), match.start()

    return "", -1


def _parse_numbered_bracket_refs(text: str) -> list[dict[str, Any]]:
    """Parse [1], [2] style references."""
    refs = []
    for match in NUMBERED_BRACKET_PATTERN.finditer(text):
        ref_num = match.group(1)
        ref_text = match.group(2).strip()
        ref_text = re.sub(r"\s+", " ", ref_text)  # Normalize whitespace

        refs.append(_parse_reference_details(ref_text, ref_num))

    return refs


def _parse_numbered_dot_refs(text: str) -> list[dict[str, Any]]:
    """Parse 1., 2. style references."""
    refs = []
    for match in NUMBERED_DOT_PATTERN.finditer(text):
        ref_num = match.group(1)
        ref_text = match.group(2).strip()
        ref_text = re.sub(r"\s+", " ", ref_text)

        refs.append(_parse_reference_details(ref_text, ref_num))

    return refs


def _parse_author_year_refs(text: str) -> list[dict[str, Any]]:
    """Parse Author (Year) style references."""
    refs = []
    for match in AUTHOR_YEAR_PATTERN.finditer(text):
        ref_text = match.group(1).strip()
        ref_text = re.sub(r"\s+", " ", ref_text)

        refs.append(_parse_reference_details(ref_text, None))

    return refs


def _parse_reference_details(ref_text: str, ref_number: str | None) -> dict[str, Any]:
    """Extract details from a single reference."""
    ref_data: dict[str, Any] = {
        "raw_text": ref_text,
    }

    if ref_number:
        ref_data["number"] = ref_number

    # Extract DOI
    doi_match = DOI_PATTERN.search(ref_text)
    if doi_match:
        ref_data["doi"] = doi_match.group(1)

    # Extract URL (if not a DOI URL)
    url_match = URL_PATTERN.search(ref_text)
    if url_match:
        url = url_match.group(0)
        if "doi.org" not in url:
            ref_data["url"] = url

    # Extract year
    year_matches = YEAR_PATTERN.findall(ref_text)
    if year_matches:
        # Take the first year found (usually publication year)
        ref_data["year"] = year_matches[0] + year_matches[0][-2:]  # Wrong, fix:
        ref_data["year"] = "".join(year_matches[0])
        # Actually just extract properly
        year_match = YEAR_PATTERN.search(ref_text)
        if year_match:
            ref_data["year"] = year_match.group(0)

    # Try to extract authors (text before the year typically)
    year_match = YEAR_PATTERN.search(ref_text)
    if year_match:
        authors_text = ref_text[: year_match.start()].strip()
        # Clean up
        authors_text = re.sub(r"[\(\[]?\d+[\)\]]?\.?\s*$", "", authors_text).strip()
        authors_text = authors_text.rstrip(",").strip()
        if authors_text and len(authors_text) > 2:
            ref_data["authors"] = authors_text

    return ref_data


def _detect_citation_style(text: str) -> str:
    """Detect the citation style used in the references section."""
    bracket_count = len(NUMBERED_BRACKET_PATTERN.findall(text))
    dot_count = len(NUMBERED_DOT_PATTERN.findall(text))
    author_year_count = len(AUTHOR_YEAR_PATTERN.findall(text))

    counts = {
        "numbered_bracket": bracket_count,
        "numbered_dot": dot_count,
        "author_year": author_year_count,
    }

    if max(counts.values()) == 0:
        return "unknown"

    return max(counts, key=counts.get)  # type: ignore


@tool(description="Extract bibliography/references from academic PDF text")
async def extract_references(text: str) -> dict[str, Any]:
    """Extract bibliography/references from academic PDF text.

    Looks for common reference section headers and parses citations
    using various format patterns (numbered, author-year, etc.).

    Args:
        text: The text from an academic PDF to extract references from.

    Returns:
        Standard response envelope with extracted references.
    """
    if not text or not text.strip():
        return error_response(
            code="INVALID_INPUT",
            message="Input text is empty",
            details={},
        )

    try:
        # Find references section
        refs_text, refs_start = _find_references_section(text)

        warnings = []
        if not refs_text:
            warnings.append(
                "No references section found. "
                "The document may not have a standard references/bibliography section."
            )
            return success_response(
                data={
                    "references": [],
                    "reference_count": 0,
                    "citation_style": "unknown",
                    "section_found": False,
                },
                warnings=warnings,
            )

        # Detect citation style
        citation_style = _detect_citation_style(refs_text)

        # Parse references based on detected style
        references = []
        if citation_style == "numbered_bracket":
            references = _parse_numbered_bracket_refs(refs_text)
        elif citation_style == "numbered_dot":
            references = _parse_numbered_dot_refs(refs_text)
        elif citation_style == "author_year":
            references = _parse_author_year_refs(refs_text)

        # If style detection failed but we have text, try all parsers
        if not references and refs_text:
            # Try each parser
            for parser in [
                _parse_numbered_bracket_refs,
                _parse_numbered_dot_refs,
                _parse_author_year_refs,
            ]:
                references = parser(refs_text)
                if references:
                    break

        # If still no references, do a simple line-based split
        if not references and refs_text:
            # Split by double newlines or numbered patterns
            lines = re.split(r"\n\n+", refs_text)
            for i, line in enumerate(lines):
                line = line.strip()
                if line and len(line) > 20:  # Skip very short lines
                    references.append(_parse_reference_details(line, str(i + 1)))
            citation_style = "line_based"
            warnings.append(
                "Citation style could not be determined. "
                "References were extracted using line-based parsing."
            )

        return success_response(
            data={
                "references": references,
                "reference_count": len(references),
                "citation_style": citation_style,
                "section_found": True,
                "section_start_position": refs_start,
            },
            warnings=warnings,
        )

    except Exception as e:
        return error_response(
            code="INTERNAL_ERROR",
            message=f"Failed to extract references: {e}",
            details={"error_type": type(e).__name__},
        )
