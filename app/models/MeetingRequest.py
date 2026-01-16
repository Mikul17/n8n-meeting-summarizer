from pydantic import BaseModel


class MeetingRequest(BaseModel):
    meeting_url: str
    estimated_duration: int
