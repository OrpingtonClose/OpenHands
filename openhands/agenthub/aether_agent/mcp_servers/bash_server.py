"""Minimal MCP server that exposes a single tool: run_bash.

This server is used by mcp-agent's agents to execute bash commands
inside the container and return stdout + stderr.
"""

import subprocess

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server('bash')


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of available tools."""
    return [
        Tool(
            name='run_bash',
            description='Execute a bash command and return stdout + stderr.',
            inputSchema={
                'type': 'object',
                'properties': {
                    'command': {
                        'type': 'string',
                        'description': 'The bash command to execute.',
                    }
                },
                'required': ['command'],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool invocations."""
    if name != 'run_bash':
        return [TextContent(type='text', text=f'Unknown tool: {name}')]

    command = arguments.get('command', '')
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (
            f'Exit code: {result.returncode}\n'
            f'Stdout:\n{result.stdout}\n'
            f'Stderr:\n{result.stderr}'
        )
    except subprocess.TimeoutExpired:
        output = 'Error: Command timed out after 120 seconds.'
    except Exception as exc:
        output = f'Error executing command: {exc}'

    return [TextContent(type='text', text=output)]


async def main() -> None:
    """Run the bash MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
