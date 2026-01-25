from threading import Thread, Event
from dataclasses import dataclass


@dataclass
class RecordingHandle:
    thread: Thread
    stop_event: Event
    started_at: float
    output_path: str
