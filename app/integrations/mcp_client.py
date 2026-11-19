import argparse
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(tool: str):
    environment = {
        name: os.environ[name]
        for name in ("DISHCARE_API_URL", "DISHCARE_CUSTOMER_TOKEN")
        if name in os.environ
    }
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "app.integrations.mcp_server"], env=environment,
    )
    async with stdio_client(server) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        result = await session.call_tool(tool, {})
        if result.isError:
            raise SystemExit("The MCP tool failed. Verify the API URL and customer token.")
        print(result.structuredContent or result.content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tool", choices=["get_balance", "get_subscription"])
    asyncio.run(run(parser.parse_args().tool))
