"""MCP Server configuration for pdf-parse."""

from dedalus_mcp import MCPServer
from dedalus_mcp.server import TransportSecuritySettings

from tools import pdf_tools

server = MCPServer(
    name="pdf-parse",
    http_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    streamable_http_stateless=True,
)


async def main() -> None:
    """Start the MCP server."""
    server.collect(*pdf_tools)
    await server.serve(port=8080)
