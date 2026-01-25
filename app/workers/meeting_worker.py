import asyncio
from typing import Dict
from app.models.MeetingStatusResponse import MeetingStatus

from app.services.meeting_service.meeting_service import connect_meeting, select_recording_device, ask_to_join, \
    wait_for_meeting_end, wait_for_approve
from app.services.recording_service.recording_service import start_recording, stop_recording
from app.utils import get_logger

logger = get_logger("meeting_worker")


async def join_and_record_meeting(
        meeting_id: str,
        meeting_url: str,
        active_sessions: Dict[str, MeetingStatus],
        *,
        batch_duration: int = 25,
):
    active_sessions[meeting_id] = MeetingStatus.STARTING

    browser = None
    recording_started = False

    try:
        page, browser = await connect_meeting(meeting_url)
        active_sessions[meeting_id] = MeetingStatus.CONNECTED

        await select_recording_device(page, "BlackHole 16ch")
        await ask_to_join(page)
        approved = await wait_for_approve(page, timeout_s=120)
        if not approved:
            active_sessions[meeting_id] = MeetingStatus.CRASHED
            logger.error("Bot was not approved to join meeting")
            return

        active_sessions[meeting_id] = MeetingStatus.RECORDING
        start_recording(output_path=f"./app/data/recordings/{meeting_id}_record.wav", channels=2)
        recording_started = True
        ended = await wait_for_meeting_end(page, timeout_s=batch_duration, poll_ms=1000)
        if ended:
            logger.info("Meeting ended early (meeting_id=%s). Stopping recording.", meeting_id)

        active_sessions[meeting_id] = MeetingStatus.FINISHED

    except Exception as e:
        active_sessions[meeting_id] = MeetingStatus.CRASHED
        logger.exception("Failed to join meeting (meeting_id=%s): %s", meeting_id, e)

    finally:
        if recording_started:
            try:
                path = stop_recording(timeout_s=15.0)
                logger.info("Recording stopped. Saved to: %s", path)
            except Exception as e:
                active_sessions[meeting_id] = MeetingStatus.CRASHED
                logger.exception("Failed to stop recording cleanly (meeting_id=%s): %s", meeting_id, e)

        if browser is not None:
            try:
                await browser.close()
            except Exception as e:
                logger.exception("Failed to close browser (meeting_id=%s): %s", meeting_id, e)
