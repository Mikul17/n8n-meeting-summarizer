import os
import queue
import threading
import time
import platform
from typing import Optional, Tuple
import numpy as np
import sounddevice as sd
import soundfile as sf
from app.services.transcription_service.recording import RecordingHandle
from app.utils import get_logger


_current_recording: Optional[RecordingHandle] = None
logger = get_logger("transcription")


def _pick_loopback_device() -> Tuple[int, str, bool]:
    system = platform.system().lower()
    devices = sd.query_devices()

    logger.info("Preparing recording device (system=%s)", system)

    if system == "windows":
        hostapis = sd.query_hostapis()
        wasapi_indices = [
            i for i, api in enumerate(hostapis) if "WASAPI" in str(api.get("name", "")).upper()
        ]

        for api_idx in wasapi_indices:
            api = hostapis[api_idx]
            for dev_index in api.get("devices", []):
                dev = devices[dev_index]
                if dev.get("max_output_channels", 0) > 0:
                    logger.info("Selected WASAPI output device for loopback: %s (index=%s)", dev["name"], dev_index)
                    return int(dev_index), dev["name"], True

        for i, dev in enumerate(devices):
            if dev.get("max_output_channels", 0) > 0:
                logger.info("Selected fallback output device for loopback: %s (index=%s)", dev["name"], i)
                return int(i), dev["name"], True

        raise RuntimeError("No suitable Windows output device found for WASAPI loopback recording.")

    # MacOS
    elif system == "darwin":
        blackhole_16ch = []
        blackhole_2ch = []

        for i, dev in enumerate(devices):
            name = str(dev.get("name", "")).lower()
            in_ch = int(dev.get("max_input_channels", 0))

            if "blackhole" in name and in_ch > 0:
                if "16ch" in name:
                    blackhole_16ch.append((i, dev.get("name"), in_ch))
                elif "2ch" in name:
                    blackhole_2ch.append((i, dev.get("name"), in_ch))

        if blackhole_16ch:
            dev_index, dev_name, in_ch = blackhole_16ch[0]
        elif blackhole_2ch:
            dev_index, dev_name, in_ch = blackhole_2ch[0]
        else:
            raise RuntimeError("No suitable BlackHole device found (16ch or 2ch required)")

        logger.info(
            "Selected BlackHole input device: %s (index=%s, in_ch=%s)",
            dev_name, dev_index, in_ch
        )
        return dev_index, dev_name, False

    else:
        raise RuntimeError(
            f"Unsupported OS for recording: {system}. This service supports Windows and macOS only."
        )


def start_recording(
        output_path: str = "./app/data/audio/recording.wav",
        samplerate: int = 48000,
        channels: int = 2,
        device: Optional[int] = None,
        *,
        overwrite: bool = True,
) -> RecordingHandle:
    global _current_recording

    if _current_recording is not None:
        raise RuntimeError("Recording already in progress. Stop it before starting another one.")

    if os.path.exists(output_path):
        if overwrite:
            os.remove(output_path)
        else:
            raise FileExistsError(f"Output file with given name already exists: {output_path}")

    if device is None:
        device, dev_name, use_loopback = _pick_loopback_device()
    else:
        dev_name = sd.query_devices(device)["name"]
        use_loopback = platform.system().lower() == "windows"

    q: "queue.Queue[np.ndarray]" = queue.Queue()
    stop_event = threading.Event()

    def callback(indata, frames, time_info, status):
        if status:
            logger.warning("Audio stream status: %s", status)

        total_amplitude = np.sum(np.abs(indata))
        if total_amplitude > 0:
            if time.time() % 1 < 0.1:
                logger.debug(f"Audio detected! Amplitude sum: {total_amplitude}")
        else:
            if time.time() % 5 < 0.1:
                logger.warning("Absolute silence (all zeros).")

        q.put(indata.copy())

    def worker():
        with sf.SoundFile(
                output_path,
                mode="w",
                samplerate=samplerate,
                channels=channels,
                subtype="PCM_16",
        ) as f:
            wasapi_stream_kwargs = {
                "samplerate": samplerate,
                "channels": channels,
                "device": device,
                "callback": callback,
                "dtype": "float32",
            }

            if use_loopback:
                try:
                    wasapi_settings = sd.WasapiSettings(loopback=True)
                    stream = sd.RawInputStream(
                        **wasapi_stream_kwargs,
                        extra_settings=wasapi_settings
                    )
                except Exception:
                    stream = sd.InputStream(**wasapi_stream_kwargs)
            else:
                stream = sd.InputStream(**wasapi_stream_kwargs)

            with stream:
                while not stop_event.is_set():
                    try:
                        data = q.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    f.write(data)

                while True:
                    try:
                        data = q.get_nowait()
                    except queue.Empty:
                        break
                    f.write(data)

    t = threading.Thread(target=worker, name="audio-recorder", daemon=True)
    t.start()

    _current_recording = RecordingHandle(
        thread=t,
        stop_event=stop_event,
        started_at=time.time(),
        output_path=output_path,
    )

    logger.info(f"Recording audio from device: {dev_name} (loopback={use_loopback}) -> {output_path}")

    return _current_recording


def stop_recording(timeout_s: float = 5.0) -> Optional[str]:
    global _current_recording

    if _current_recording is None:
        return None

    _current_recording.stop_event.set()
    _current_recording.thread.join(timeout=timeout_s)
    path = _current_recording.output_path
    _current_recording = None
    return path
