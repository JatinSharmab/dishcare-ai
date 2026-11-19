import io
import wave

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512
FRAME_BYTES = FRAME_SAMPLES * 2
MAX_PCM_BYTES = SAMPLE_RATE * 2 * 20


def wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)
    return stream.getvalue()


def read_wav(path):
    with wave.open(str(path), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError("Audio must be 16 kHz mono, signed 16-bit PCM WAV")
        if source.getnframes() * 2 > MAX_PCM_BYTES:
            raise ValueError("Audio exceeds 20 seconds")
        return source.readframes(source.getnframes())
