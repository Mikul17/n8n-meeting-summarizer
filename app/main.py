import asyncio
from fastapi import FastAPI

from app.models.MeetingRequest import MeetingRequest
from app.services import connect_meeting
from app.services import start_recording, stop_recording
from app.utils import get_logger

app = FastAPI(title="n8n Teams Meeting")
logger = get_logger()


@app.post("/join-meeting")
async def join_meeting(request: MeetingRequest):
    await connect_meeting(request.meeting_url)

#Test endpoint which records 5 seconds of meeting
@app.post("/begin-recording")
async def begin_recording():
    logger.info("Starting 5-second recording")
    start_recording(channels=2)
    await asyncio.sleep(25)
    path = stop_recording()
    logger.info("Recording finished: %s", path)
    return {"status": "ok", "duration_seconds": 5, "file": path}

