"""Run a read-only MCP server on stdio using a customer JWT from its environment."""

import os

import httpx
from mcp.server.fastmcp import FastMCP

server = FastMCP("DishCare support")


async def query(path: str) -> dict:
    async with httpx.AsyncClient(
        base_url=os.environ.get("DISHCARE_API_URL", "http://127.0.0.1:8000"),
        headers={"Authorization": f"Bearer {os.environ['DISHCARE_CUSTOMER_TOKEN']}"},
        timeout=10,
    ) as client:
        response = await client.get(f"/api/v1/mcp/{path}")
        response.raise_for_status()
        return response.json()


@server.tool()
async def get_balance() -> dict:
    """Get the authenticated customer's current account balance."""
    return await query("get_balance")


@server.tool()
async def get_subscription() -> dict:
    """Get the authenticated customer's subscription."""
    return await query("get_subscription")


if __name__ == "__main__":
    server.run(transport="stdio")
