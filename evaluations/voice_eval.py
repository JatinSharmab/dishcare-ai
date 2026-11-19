import argparse
import json
from pathlib import Path
from time import perf_counter

from app.voice.audio import read_wav


def main():
    from jiwer import wer

    parser = argparse.ArgumentParser(description="Measure ASR word error rate against labeled WAV clips")
    parser.add_argument("manifest", type=Path, nargs="?", help="JSON list with wav, reference, and optional language")
    parser.add_argument("--synthetic", action="store_true", help="Generate two local Piper test clips")
    parser.add_argument("--model", default="base")
    args = parser.parse_args()
    if bool(args.manifest) == args.synthetic:
        parser.error("Provide a manifest or use --synthetic")
    from app.voice.asr import WhisperASR

    model = WhisperASR(args.model)
    rows = []
    if args.synthetic:
        clips = synthetic_clips()
    else:
        entries = json.loads(args.manifest.read_text(encoding="utf-8"))
        clips = ((entry, read_wav(args.manifest.parent / entry["wav"])) for entry in entries)
    for entry, pcm in clips:
        started = perf_counter()
        hypothesis, _ = model.transcribe(pcm, entry.get("language"))
        latency_ms = (perf_counter() - started) * 1000
        rows.append({
            "wav": entry["wav"], "asr_ms": round(latency_ms, 3),
            "tts_ms": entry.get("tts_ms"), "vad_speech_frames": entry.get("vad_speech_frames"),
            "reference": entry["reference"], "hypothesis": hypothesis,
            "wer": wer(entry["reference"].casefold(), hypothesis.casefold()),
        })
    if not rows:
        parser.error("Manifest has no audio")
    print(json.dumps({
        "mode": "piper-synthetic" if args.synthetic else "recording-manifest",
        "clips": rows,
        "corpus_wer": wer([r["reference"].casefold() for r in rows],
                          [r["hypothesis"].casefold() for r in rows]),
    }, indent=2, ensure_ascii=True))


def synthetic_clips():
    import numpy as np

    from app.config import Settings
    from app.voice.audio import FRAME_BYTES, SAMPLE_RATE
    from app.voice.tts import PiperTTS
    from app.voice.vad import SileroVAD

    settings = Settings()
    piper = PiperTTS(settings.piper_english_model, settings.piper_hindi_model)
    vad = SileroVAD()
    for language, reference in (
        ("en", "What is my current balance?"),
        ("hi", "मेरा बैलेंस कितना है?"),
    ):
        started = perf_counter()
        pcm, rate = piper.synthesize(reference, language)
        tts_ms = (perf_counter() - started) * 1000
        samples = np.frombuffer(pcm, dtype="<i2")
        positions = np.arange(int(len(samples) * SAMPLE_RATE / rate)) * rate / SAMPLE_RATE
        audio = np.interp(positions, np.arange(len(samples)), samples).astype("<i2").tobytes()
        vad.reset()
        speech_frames = sum(
            vad(audio[index:index + FRAME_BYTES])
            for index in range(0, len(audio) - FRAME_BYTES + 1, FRAME_BYTES)
        )
        yield {"wav": "generated-" + language, "reference": reference, "language": language,
               "tts_ms": round(tts_ms, 3), "vad_speech_frames": int(speech_frames)}, audio


if __name__ == "__main__":
    main()
