"""
REMY MCP Server — Entry Point
Run with: python server.py

Binds to localhost only by default (REMY_BIND_HOST). Every registered tool is
wrapped by the permission engine before it can execute.
"""

from mcp.server.fastmcp import FastMCP

from remy.config import config
from remy.identity import build_system_prompt
from remy.prompts import register_all_prompts
from remy.resources import register_all_resources
from remy.tools import register_all_tools

mcp = FastMCP(
    name=config.SERVER_NAME,
    host=config.BIND_HOST,
    port=config.MCP_PORT,
    instructions=build_system_prompt(),
)

register_all_tools(mcp)
register_all_prompts(mcp)
register_all_resources(mcp)


def main():
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
