from collections import deque

from app.voice.audio import FRAME_BYTES, MAX_PCM_BYTES


class Endpoint:
    def __init__(self, vad, silence_frames: int = 19):
        self.vad = vad
        self.silence_frames = silence_frames
        self.prefix = deque(maxlen=6)
        self.audio = bytearray()
        self.silence = 0

    def feed(self, frame: bytes) -> bytes | None:
        if len(frame) != FRAME_BYTES:
            raise ValueError("Each audio frame must be 1024 bytes")
        speech = self.vad(frame)
        if not self.audio and not speech:
            self.prefix.append(frame)
            return None
        if not self.audio:
            self.audio.extend(b"".join(self.prefix))
            self.prefix.clear()
        self.audio.extend(frame)
        self.silence = 0 if speech else self.silence + 1
        if self.silence >= self.silence_frames or len(self.audio) + FRAME_BYTES > MAX_PCM_BYTES:
            return self.finish()
        return None

    def finish(self) -> bytes:
        result = bytes(self.audio)
        self.reset()
        return result

    def reset(self):
        self.audio.clear()
        self.prefix.clear()
        self.silence = 0
        self.vad.reset()
