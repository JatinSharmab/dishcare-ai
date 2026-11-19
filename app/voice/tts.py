from pathlib import Path
from threading import Lock

from piper import PiperVoice


class PiperTTS:
    def __init__(self, english: Path, hindi: Path):
        self.voices = {"en": PiperVoice.load(english), "hi": PiperVoice.load(hindi)}
        self.lock = Lock()

    def synthesize(self, text: str, language: str) -> tuple[bytes, int]:
        voice = self.voices["hi" if language in {"hi", "hindi", "hinglish"} else "en"]
        with self.lock:
            pcm = b"".join(chunk.audio_int16_bytes for chunk in voice.synthesize(text[:2000]))
        return pcm, voice.config.sample_rate
