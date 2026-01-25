from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks

from app.models.JiraTaskRequest import JiraTaskRequest
from app.models.MeetingRequest import MeetingRequest
from app.models.MeetingStatusResponse import (
    MeetingStatusResponse,
    MeetingStatus,
    MeetingState,
)
from app.services.jira_service import process_jira_response
from app.services.transcription_service.transcription_service import (
    send_audio_for_transcription,
)
from app.utils import get_logger
from app.workers.meeting_worker import join_and_record_meeting

app = FastAPI(title="n8n Teams Meeting")
load_dotenv()
logger = get_logger()

active_sessions: Dict[str, MeetingState] = {}


@app.post("/join-meeting", response_model=MeetingStatusResponse)
async def join_meeting_endpoint(
    request: MeetingRequest, background_tasks: BackgroundTasks
):
    meeting_id = request.meeting_id
    active_sessions[meeting_id] = MeetingState(
        status=MeetingStatus.STARTING,
        resume_url=request.resume_url,
    )
    # 5 min
    batch_duration = 5 * 60

    background_tasks.add_task(
        join_and_record_meeting,
        meeting_id,
        active_sessions,
        batch_duration=batch_duration,
    )

    return MeetingStatusResponse(
        status=active_sessions.get(meeting_id).status, meeting_id=meeting_id
    )


@app.get("/download-file", response_model=MeetingStatusResponse)
async def download_file_endpoint(meeting_id: str, background_tasks: BackgroundTasks):

    background_tasks.add_task(send_audio_for_transcription, active_sessions, meeting_id)

    return MeetingStatusResponse(
        status=active_sessions.get(meeting_id).status, meeting_id=meeting_id
    )


@app.post("/create-tasks", response_model=MeetingStatusResponse)
async def create_jira_tasks(
    meeting_id: str, request: JiraTaskRequest, background_tasks: BackgroundTasks
):

    background_tasks.add_task(
        process_jira_response, active_sessions, meeting_id, request
    )

    return MeetingStatusResponse(
        status=active_sessions.get(meeting_id).status, meeting_id=meeting_id
    )
