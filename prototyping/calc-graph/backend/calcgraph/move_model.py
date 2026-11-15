"""The request body every move-a-column route takes (`Move`).

Its own module so the routers that take it (move_api, as_of) can both import it at the top without
importing each other: as_of's /impact/timeline needs the model, and move_api already imports as_of
lazily. The field descriptions are the API docs and the generated MCP / OpenAPI schema.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Move(BaseModel):
    """One column move (or removal) - the body of /impact, /impact/timeline, /rerun, /apply,
    /change-order and /etabs/send."""
    column: str = Field(description='column id, "COL-2B" or "2B"')
    dx: float = Field(default=0.0, description="feet along +x = east = toward higher grid numbers (1 -> 5)")
    dy: float = Field(default=0.0, description="feet along +y = north = toward later grid letters (A -> D)")
    remove: bool = Field(default=False, description="remove the column instead of moving it (dx / dy ignored)")
    records: list[str] | None = Field(default=None, description="/rerun only: the calc record ids to re-run; "
                                      "omitted = every record the impact marks stale")
    label: str | None = Field(default=None, description="/apply only: the model revision label")
    as_of: str | None = Field(default=None, description='approval date: "today" | "+1w" | "+2w" | "+1m" | "YYYY-MM-DD"; '
                              "omitted = today (US Eastern)")
