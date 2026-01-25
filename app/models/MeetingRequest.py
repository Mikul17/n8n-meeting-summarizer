from pydantic import BaseModel


class MeetingRequest(BaseModel):
    meeting_id: str
    estimated_duration: int
    resume_url: str
