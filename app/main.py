import uuid
from typing import Dict

from fastapi import FastAPI, BackgroundTasks

from app.models.MeetingRequest import MeetingRequest
from app.models.MeetingStatusResponse import MeetingStatusResponse, MeetingStatus
from app.utils import get_logger
from app.workers.meeting_worker import join_and_record_meeting

app = FastAPI(title="n8n Teams Meeting")
logger = get_logger()

active_sessions: Dict[str, MeetingStatus] = {}


@app.post("/join-meeting", response_model=MeetingStatusResponse)
async def join_meeting_endpoint(request: MeetingRequest, background_tasks: BackgroundTasks):
    meeting_id = str(uuid.uuid4())
    active_sessions[meeting_id] = MeetingStatus.STARTING
    #5 min
    batch_duration = 5 * 60

    background_tasks.add_task(
        join_and_record_meeting,
        meeting_id,
        request.meeting_url,
        active_sessions,
        batch_duration=batch_duration
    )

    return MeetingStatusResponse(
        status=active_sessions.get(meeting_id),
        meeting_id=meeting_id
    )
