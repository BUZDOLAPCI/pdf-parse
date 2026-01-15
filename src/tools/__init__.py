"""PDF parsing tools for the MCP server."""

from tools.references import extract_references
from tools.sections import extract_sections
from tools.tables import extract_tables
from tools.text import pdf_to_text

# All tools to be registered with the MCP server
pdf_tools = [
    pdf_to_text,
    extract_sections,
    extract_tables,
    extract_references,
]

__all__ = [
    "pdf_tools",
    "pdf_to_text",
    "extract_sections",
    "extract_tables",
    "extract_references",
]
