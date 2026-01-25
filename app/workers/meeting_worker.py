import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from app.models.MeetingStatusResponse import MeetingStatus, MeetingState
from app.services import (
    connect_meeting,
    select_recording_device,
    ask_to_join,
    wait_for_approve,
    wait_for_meeting_end,
)
from app.services.recording_service.recording_service import (
    stop_recording,
    start_recording,
)
from app.services.transcription_service.transcription_service import (
    send_audio_for_transcription,
    generate_transcription,
)
from app.utils import get_logger

logger = get_logger("meeting_worker")
executor = ThreadPoolExecutor()


async def process_and_send_recording(
    meeting_id: str, active_sessions: Dict[str, MeetingState], audio_path: str
):
    loop = asyncio.get_running_loop()

    await loop.run_in_executor(
        executor, generate_transcription, active_sessions, meeting_id, audio_path
    )


async def join_and_record_meeting(
    meeting_id: str,
    active_sessions: Dict[str, MeetingState],
    *,
    batch_duration: int = 25,
):
    active_sessions[meeting_id].status = MeetingStatus.STARTING

    browser = None
    recording_started = False
    recording_stopped = False
    audio_path = ""
    meeting_url = f"https://meet.google.com/{meeting_id}"

    try:
        page, browser = await connect_meeting(meeting_url)
        active_sessions[meeting_id].status = MeetingStatus.CONNECTED

        await select_recording_device(page, "BlackHole 16ch")
        await ask_to_join(page)
        approved = await wait_for_approve(page, timeout_s=120)
        if not approved:
            active_sessions[meeting_id].status = MeetingStatus.CRASHED
            logger.error("Bot was not approved to join meeting")
            return

        active_sessions[meeting_id].status = MeetingStatus.RECORDING
        audio_path = f"./app/data/recordings/{meeting_id}_record.wav"
        start_recording(output_path=audio_path, channels=2)
        recording_started = True
        ended = await wait_for_meeting_end(page, timeout_s=batch_duration, poll_ms=1000)
        if ended:
            logger.info(
                "Meeting ended early (meeting_id=%s). Stopping recording.", meeting_id
            )

        active_sessions[meeting_id].status = MeetingStatus.FINISHED

    except Exception as e:
        active_sessions[meeting_id].status = MeetingStatus.CRASHED
        logger.exception("Failed to join meeting (meeting_id=%s): %s", meeting_id, e)

    finally:
        if recording_started:
            try:
                path = stop_recording(timeout_s=15.0)
                logger.info("Recording stopped. Saved to: %s", path)
                recording_stopped = True
            except Exception as e:
                active_sessions[meeting_id].status = MeetingStatus.CRASHED
                logger.exception(
                    "Failed to stop recording cleanly (meeting_id=%s): %s",
                    meeting_id,
                    e,
                )

        if recording_stopped:
            try:
                logger.info("Processing recording (meeting_id=%s", meeting_id)
                await process_and_send_recording(
                    meeting_id, active_sessions, audio_path
                )
            except Exception as e:
                active_sessions[meeting_id].status = MeetingStatus.CRASHED
                logger.exception(
                    "Failed to process recording (meeting_id=%s): %s",
                    meeting_id,
                    e,
                )

        if browser is not None:
            try:
                await browser.close()
            except Exception as e:
                logger.exception(
                    "Failed to close browser (meeting_id=%s): %s", meeting_id, e
                )
