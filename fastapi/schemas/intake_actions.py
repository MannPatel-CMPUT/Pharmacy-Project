from pydantic import BaseModel

class StatusUpdate(BaseModel):
    status: str

class AssignUser(BaseModel):
    user: str