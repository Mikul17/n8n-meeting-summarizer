import logging

import io
import httpx
from pathlib import Path
from typing import Dict, Optional, Any
from app.models.MeetingStatusResponse import MeetingStatus, MeetingState

from pydub import AudioSegment

logger = logging.getLogger()


def compress_audio(audio_path: Path, *, format: str = "mp3", bitrate: str = "128k") -> Optional[io.BytesIO]:
    try:
        audio = AudioSegment.from_wav(str(audio_path))
        mp3_buffer = io.BytesIO()
        audio.export(mp3_buffer, format=format, bitrate=bitrate)
        mp3_buffer.seek(0)
        return mp3_buffer
    except Exception as e:
        logger.error(f"Could not compress file {audio_path}, error: {e}")
        return None


async def send_audio_for_transcription(active_sessions: Dict[str, MeetingState], meeting_id: str):
    audio_path = Path("app/data/recordings") / f"{meeting_id}_record.wav"

    if not audio_path.exists():
        raise FileNotFoundError(f"Recording not found: {audio_path}")

    state = active_sessions.get(meeting_id)
    if state is None:
        raise RuntimeError(f"Meeting {meeting_id} does not exist")

    if state.status != MeetingStatus.FINISHED:
        raise RuntimeError(f"Meeting {meeting_id} not yet ended (status={state.status})")

    audio_payload = compress_audio(audio_path)

    if audio_payload:
        files = {
            "file": (f"{meeting_id}_record.mp3", audio_payload, "audio/mpeg"),
        }
    else:
        f = open(audio_path, "rb")
        files = {
            "file": (audio_path.name, f, "audio/wav"),
        }

    try:
        data = {"meeting_id": str(meeting_id)}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                state.resume_url,
                files=files,
                data=data,
            )
        response.raise_for_status()
        state.status = MeetingStatus.TRANSCRIBED
        return response.json()
    finally:
        if not audio_payload:
            files["file"][1].close()
