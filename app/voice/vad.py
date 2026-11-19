import numpy as np
import torch
from silero_vad import load_silero_vad

from app.voice.audio import SAMPLE_RATE


class SileroVAD:
    def __init__(self):
        self.model = load_silero_vad(onnx=True)

    def __call__(self, frame: bytes) -> bool:
        samples = np.frombuffer(frame, dtype="<i2").astype(np.float32) / 32768
        return self.model(torch.from_numpy(samples), SAMPLE_RATE).item() >= 0.5

    def reset(self):
        self.model.reset_states()
