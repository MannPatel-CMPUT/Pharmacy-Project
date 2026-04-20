from typing import Literal

from pydantic import BaseModel, Field

class StatusUpdate(BaseModel):
    status: Literal[
        "new",
        "triage",
        "waiting_info",
        "ready_to_fill",
        "filled",
        "dispensed",
        "completed",
    ]

class AssignUser(BaseModel):
    user: str = Field(..., min_length=1, max_length=100)
