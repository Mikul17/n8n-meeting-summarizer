from pydantic import BaseModel


class SummaryRequest(BaseModel):
    transcript: str