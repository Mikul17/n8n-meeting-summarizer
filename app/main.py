from fastapi import FastAPI

from app.models.MeetingRequest import MeetingRequest
from app.services import connect_meeting
from app.utils import get_logger

app = FastAPI(title="n8n Teams Meeting")
logger = get_logger()


@app.post("/join-meeting")
async def join_meeting(request: MeetingRequest):
    logger.info(f"Hello world: {request.meeting_url}")
    await connect_meeting(request.meeting_url)
