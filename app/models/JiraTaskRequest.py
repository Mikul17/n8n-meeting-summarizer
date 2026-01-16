from pydantic import BaseModel


class JiraTaskRequest(BaseModel):
    summary: str
    action_items: list[str]