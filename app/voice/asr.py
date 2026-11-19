from threading import Lock

import numpy as np
from faster_whisper import WhisperModel


class WhisperASR:
    def __init__(self, model: str):
        self.model = WhisperModel(model, device="cpu", compute_type="int8")
        self.lock = Lock()

    def transcribe(self, pcm: bytes, language: str | None = None) -> tuple[str, str]:
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        with self.lock:
            segments, info = self.model.transcribe(
                samples, language=language, beam_size=1, condition_on_previous_text=False,
                initial_prompt="यह हिंदी वार्तालाप देवनागरी लिपि में है।" if language == "hi" else None,
            )
            return " ".join(segment.text.strip() for segment in segments).strip(), info.language
