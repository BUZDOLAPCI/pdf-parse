"""Section extraction tool for analyzing text structure."""

import re
from typing import Any

from dedalus_mcp import tool

from utils import error_response, success_response

# Common heading patterns
NUMBERED_HEADING_PATTERN = re.compile(
    r"^(\d+(?:\.\d+)*\.?)\s+([A-Z][^\n]{2,80})$",
    re.MULTILINE,
)
ROMAN_HEADING_PATTERN = re.compile(
    r"^([IVXLCDM]+\.?)\s+([A-Z][^\n]{2,80})$",
    re.MULTILINE,
)
LETTER_HEADING_PATTERN = re.compile(
    r"^([A-Z]\.)\s+([A-Z][^\n]{2,80})$",
    re.MULTILINE,
)
UPPERCASE_HEADING_PATTERN = re.compile(
    r"^([A-Z][A-Z\s]{3,60})$",
    re.MULTILINE,
)
COMMON_SECTION_NAMES = [
    "abstract",
    "introduction",
    "background",
    "related work",
    "methodology",
    "methods",
    "materials and methods",
    "experimental setup",
    "experiments",
    "results",
    "discussion",
    "conclusion",
    "conclusions",
    "future work",
    "acknowledgments",
    "acknowledgements",
    "references",
    "bibliography",
    "appendix",
    "appendices",
    "supplementary material",
    "supplementary materials",
]


def _detect_heading_style(text: str) -> str:
    """Detect the predominant heading style in the text."""
    numbered_count = len(NUMBERED_HEADING_PATTERN.findall(text))
    roman_count = len(ROMAN_HEADING_PATTERN.findall(text))
    letter_count = len(LETTER_HEADING_PATTERN.findall(text))
    uppercase_count = len(UPPERCASE_HEADING_PATTERN.findall(text))

    counts = {
        "numbered": numbered_count,
        "roman": roman_count,
        "letter": letter_count,
        "uppercase": uppercase_count,
    }

    if max(counts.values()) == 0:
        return "unknown"

    return max(counts, key=counts.get)  # type: ignore


def _extract_numbered_sections(text: str) -> list[dict[str, Any]]:
    """Extract sections with numbered headings (1., 1.1, 2.3.1, etc.)."""
    sections = []
    matches = list(NUMBERED_HEADING_PATTERN.finditer(text))

    for i, match in enumerate(matches):
        number = match.group(1).rstrip(".")
        title = match.group(2).strip()
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start_pos:end_pos].strip()

        # Determine level from number of dots
        level = number.count(".") + 1

        sections.append({
            "number": number,
            "title": title,
            "level": level,
            "start_position": match.start(),
            "content_preview": content[:200] + "..." if len(content) > 200 else content,
        })

    return sections


def _extract_common_sections(text: str) -> list[dict[str, Any]]:
    """Extract sections based on common academic section names."""
    sections = []
    text_lower = text.lower()

    for section_name in COMMON_SECTION_NAMES:
        # Look for section name at start of line
        pattern = re.compile(
            rf"^{re.escape(section_name)}s?\s*\n",
            re.IGNORECASE | re.MULTILINE,
        )
        for match in pattern.finditer(text):
            title = text[match.start() : match.end()].strip()
            sections.append({
                "number": None,
                "title": title,
                "level": 1,
                "start_position": match.start(),
                "content_preview": text[match.end() : match.end() + 200].strip() + "...",
            })

    # Sort by position in document
    sections.sort(key=lambda x: x["start_position"])

    return sections


def _extract_uppercase_sections(text: str) -> list[dict[str, Any]]:
    """Extract sections with all-uppercase headings."""
    sections = []
    matches = list(UPPERCASE_HEADING_PATTERN.finditer(text))

    # Filter out false positives (very short or too long)
    matches = [
        m
        for m in matches
        if 4 <= len(m.group(1).strip()) <= 50
        and not m.group(1).strip().isdigit()
    ]

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start_pos:end_pos].strip()

        sections.append({
            "number": None,
            "title": title,
            "level": 1,
            "start_position": match.start(),
            "content_preview": content[:200] + "..." if len(content) > 200 else content,
        })

    return sections


@tool(description="Analyze text and identify sections/headings structure")
async def extract_sections(text: str) -> dict[str, Any]:
    """Analyze text and identify sections/headings structure.

    Uses heuristics to detect common heading patterns:
    - Numbered sections (1., 1.1, 2.3.1)
    - Roman numerals (I., II., III.)
    - Letter sections (A., B., C.)
    - Uppercase headings
    - Common academic section names

    Args:
        text: The text to analyze for section structure.

    Returns:
        Standard response envelope with detected sections.
    """
    if not text or not text.strip():
        return error_response(
            code="INVALID_INPUT",
            message="Input text is empty",
            details={},
        )

    try:
        # Detect heading style
        heading_style = _detect_heading_style(text)

        # Extract sections based on detected style
        sections = []

        if heading_style == "numbered":
            sections = _extract_numbered_sections(text)
        elif heading_style == "uppercase":
            sections = _extract_uppercase_sections(text)

        # If no sections found or few sections, try common section names
        if len(sections) < 3:
            common_sections = _extract_common_sections(text)
            if len(common_sections) > len(sections):
                sections = common_sections
                heading_style = "common_names"

        # Build hierarchy based on levels
        hierarchy = []
        for section in sections:
            hierarchy.append({
                "number": section["number"],
                "title": section["title"],
                "level": section["level"],
            })

        warnings = []
        if not sections:
            warnings.append(
                "No clear section structure detected. "
                "The document may not have standard headings."
            )

        return success_response(
            data={
                "sections": sections,
                "hierarchy": hierarchy,
                "heading_style": heading_style,
                "section_count": len(sections),
            },
            warnings=warnings,
        )

    except Exception as e:
        return error_response(
            code="INTERNAL_ERROR",
            message=f"Failed to extract sections: {e}",
            details={"error_type": type(e).__name__},
        )
