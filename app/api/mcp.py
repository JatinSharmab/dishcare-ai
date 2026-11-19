from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request

from app.core.audit import audit
from app.core.security import get_current_customer

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP"])


@router.get("/{tool}")
async def invoke(
    tool: Literal["get_balance", "get_subscription"], request: Request,
    customer_id: Annotated[str, Depends(get_current_customer)],
):
    result = await request.app.state.executor.execute(customer_id, tool, {})
    await audit(request.app.state.db, customer_id, tool, "completed" if result["ok"] else "failed")
    return result
