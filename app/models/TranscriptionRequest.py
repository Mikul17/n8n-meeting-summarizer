from pydantic import BaseModel


class TranscriptionRequest(BaseModel):
    audio_file_path: str