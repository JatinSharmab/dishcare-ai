import asyncio
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from app.core.exceptions import BusinessError
from app.voice.audio import MAX_PCM_BYTES


@dataclass
class VoiceReply:
    transcript: str
    answer: str
    pcm: bytes
    sample_rate: int
    elapsed: dict[str, float]


class VoicePipeline:
    def __init__(self, asr, tts, vad_factory, metrics=None):
        self.asr = asr
        self.tts = tts
        self.vad_factory = vad_factory
        self.metrics = metrics
        self.capacity = asyncio.Semaphore(4)

    async def turn(
        self, pcm: bytes, chat, customer_id: str, session_id: UUID, language: str | None = None,
    ) -> VoiceReply:
        if not pcm or len(pcm) % 2 or len(pcm) > MAX_PCM_BYTES:
            raise BusinessError(422, "INVALID_AUDIO", "Expected up to 20 seconds of PCM16 mono audio")
        async with self.capacity:
            started = perf_counter()
            transcript, detected = await asyncio.to_thread(self.asr.transcribe, pcm, language)
            decoded = perf_counter()
            if not transcript:
                raise BusinessError(422, "NO_SPEECH", "No speech could be recognized")
            reply = await chat.chat(customer_id, transcript[:2000], session_id)
            answered = perf_counter()
            synthesis_language = reply.language
            if detected == "hi" and synthesis_language not in {"hindi", "hinglish", "hi"}:
                synthesis_language = "hi"
            output, rate = await asyncio.to_thread(self.tts.synthesize, reply.answer, synthesis_language)
            if not output:
                raise BusinessError(502, "NO_AUDIO_OUTPUT", "Speech synthesis returned no audio")
            finished = perf_counter()
        elapsed = {"asr": decoded - started, "chat": answered - decoded,
                   "tts": finished - answered, "total": finished - started}
        if self.metrics is not None:
            for stage, seconds in elapsed.items():
                self.metrics.observe(f"voice.{stage}", seconds)
        return VoiceReply(transcript, reply.answer, output, rate, elapsed)
