import io
import logging
import os
from pathlib import Path
from typing import Dict, Optional

import httpx
from elevenlabs import ElevenLabs
from pydub import AudioSegment

from app.models.MeetingStatusResponse import MeetingStatus, MeetingState

logger = logging.getLogger("transcription_service")


def compress_audio(
    audio_path: Path, *, format: str = "mp3", bitrate: str = "128k"
) -> Optional[io.BytesIO]:
    try:
        logger.info(f"Attempting audio compression")
        audio = AudioSegment.from_wav(str(audio_path))
        mp3_buffer = io.BytesIO()
        audio.export(mp3_buffer, format=format, bitrate=bitrate)
        mp3_buffer.seek(0)
        logger.info(
            f"Successfully compressed audio to {format} format (bitrate: {bitrate}"
        )
        return mp3_buffer
    except Exception as e:
        logger.error(f"Could not compress file {audio_path}, error: {e}")
        return None


def send_audio_for_transcription(
    active_sessions: Dict[str, MeetingState], meeting_id: str, audio_path: str
):
    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise FileNotFoundError(f"Recording not found: {audio_path}")

    state = active_sessions.get(meeting_id)
    if state is None:
        raise RuntimeError(f"Meeting {meeting_id} does not exist")

    if state.status != MeetingStatus.FINISHED:
        raise RuntimeError(
            f"Meeting {meeting_id} not yet ended (status={state.status})"
        )

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
        with httpx.Client(timeout=120) as client:
            response = client.post(
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


def generate_transcription(
    active_sessions: Dict[str, MeetingState], meeting_id: str, audio_path: str
):
    audio_path = Path(audio_path)
    audio = compress_audio(audio_path)

    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    state = active_sessions.get(meeting_id)

    try:
        logger.info(f"Sending transcription request (meeting_id {meeting_id})")
        response = client.speech_to_text.convert(
            file=audio,
            model_id="scribe_v2",
            tag_audio_events=False,
            language_code="pl",
            diarize=True,
        )

        formatted_segments = []
        if response.words:
            current_speaker = response.words[0].speaker_id
            current_text = []
            start_time = response.words[0].start
            last_word_end = 0.0

            for word in response.words:
                if word.speaker_id != current_speaker:
                    formatted_segments.append(
                        {
                            "speaker": current_speaker,
                            "text": " ".join(current_text),
                            "start": start_time,
                            "end": last_word_end,
                        }
                    )
                    current_speaker = word.speaker_id
                    current_text = [word.text]
                    start_time = word.start
                else:
                    current_text.append(word.text)

                last_word_end = word.end

            formatted_segments.append(
                {
                    "speaker": current_speaker,
                    "text": " ".join(current_text),
                    "start": start_time,
                    "end": last_word_end,
                }
            )

        logger.info(
            f"Grouped {len(response.words)} words into {len(formatted_segments)} speaker segments"
        )

        state.status = MeetingStatus.TRANSCRIBED

        with httpx.Client(timeout=120) as http_client:
            http_client.post(
                state.resume_url,
                json={
                    "meeting_id": meeting_id,
                    "full_text": response.text,
                    "segments": formatted_segments,
                },
            )

    except Exception as e:
        state.status = MeetingStatus.CRASHED
        logger.error(f"Error while generating transcription for {meeting_id}: {e}")
        raise e
