from enum import Enum

from pydantic import BaseModel


class MeetingStatus(str, Enum):
    STARTING = "starting"
    CONNECTED = "connected"
    RECORDING = "recording"
    FINISHED = "finished"
    CRASHED = "crashed"


class MeetingStatusResponse(BaseModel):
    status: MeetingStatus
    meeting_id: str
