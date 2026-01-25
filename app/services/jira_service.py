from typing import Dict

from app.models.JiraTaskRequest import JiraTaskRequest
from app.models.MeetingStatusResponse import MeetingState, MeetingStatus
from app.utils import get_logger

logger = get_logger("jira-service")


async def process_jira_response(active_sessions: Dict[str, MeetingState], meeting_id: str, request: JiraTaskRequest):
    state = active_sessions.get(meeting_id)
    if state is None:
        raise RuntimeError(f"Meeting {meeting_id} does not exist")

    if state.status != MeetingStatus.TRANSCRIBED:
        raise RuntimeError(f"Attempted to process jira tickets without transcription")

    logger.info(f"Processing jira tickets for meeting {meeting_id}")

    return None


async def create_jira_features():
    return None


async def create_jira_tasks():
    return None


async def create_jira_bugs():
    return None
