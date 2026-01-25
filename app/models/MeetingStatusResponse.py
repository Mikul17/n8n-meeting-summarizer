from enum import Enum

from pydantic import BaseModel


class MeetingStatus(str, Enum):
    STARTING = "starting"
    CONNECTED = "connected"
    RECORDING = "recording"
    FINISHED = "finished"
    CRASHED = "crashed"
    TRANSCRIBED = "transcribed"
    PROCESSING = "processing"


class MeetingStatusResponse(BaseModel):
    status: MeetingStatus
    meeting_id: str


class MeetingState(BaseModel):
    status: MeetingStatus
    resume_url: str
