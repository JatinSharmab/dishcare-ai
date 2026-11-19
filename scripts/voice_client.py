"""Record a WAV turn or use a microphone over the DishCare WebSocket."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from app.voice.audio import FRAME_SAMPLES, SAMPLE_RATE, read_wav


async def microphone(base_url, headers, language):
    import sounddevice as sd
    from websockets.asyncio.client import connect

    url = base_url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    endpoint = f"{url}/api/v1/voice/stream" + (f"?language={language}" if language else "")
    loop = asyncio.get_running_loop()
    frames = asyncio.Queue(maxsize=64)
    listening = True
    interrupting = False

    def enqueue(frame):
        if not frames.full():
            frames.put_nowait(frame)

    def capture(indata, count, time_info, status):
        if listening:
            loop.call_soon_threadsafe(enqueue, bytes(indata))

    async with connect(endpoint, additional_headers=headers, max_size=4 * 1024 * 1024) as socket:
        ready = json.loads(await socket.recv())
        print("Session", ready["session_id"])
        print("Speak after each reply. Headphones reduce feedback. Ctrl+C exits.")
        print("Press Space on Windows, or Enter on Unix, to interrupt.")

        async def send():
            while True:
                try:
                    frame = await asyncio.wait_for(frames.get(), timeout=15)
                except TimeoutError:
                    continue
                if listening:
                    await socket.send(frame)

        async def interrupt():
            nonlocal interrupting
            if os.name == "nt":
                import msvcrt

                def key_pressed():
                    return msvcrt.kbhit() and msvcrt.getwch() == " "
            else:
                import select

                def key_pressed():
                    if not select.select([sys.stdin], [], [], 0)[0]:
                        return False
                    return sys.stdin.readline().strip() == "" and sys.stdin.isatty()

            while True:
                await asyncio.sleep(0.1)
                if key_pressed() and not interrupting:
                    interrupting = True
                    sd.stop()
                    while not frames.empty():
                        frames.get_nowait()
                    await socket.send("interrupt")

        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES,
                               channels=1, dtype="int16", callback=capture):
            sender = asyncio.create_task(send())
            keyboard = asyncio.create_task(interrupt())
            try:
                async for packet in socket:
                    event = json.loads(packet)
                    if event["type"] != "reply":
                        if event["type"] == "interrupted":
                            interrupting = False
                        print(event)
                        continue
                    listening = False
                    try:
                        while not frames.empty():
                            frames.get_nowait()
                        audio = await socket.recv()
                        if interrupting:
                            continue
                        print("You:", event["transcript"], "\nDishCare:", event["answer"])
                        await asyncio.to_thread(play, audio, event["sample_rate"])
                    finally:
                        listening = True
            finally:
                sender.cancel()
                keyboard.cancel()
                await asyncio.gather(sender, keyboard, return_exceptions=True)


def play(pcm, sample_rate):
    import numpy as np
    import sounddevice as sd

    sd.play(np.frombuffer(pcm, dtype="<i2"), samplerate=sample_rate, blocking=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--language", choices=["en", "hi"])
    parser.add_argument("--wav", type=Path, help="Send a 16 kHz mono PCM WAV as a single turn")
    parser.add_argument("--output", type=Path, default=Path("reply.wav"))
    args = parser.parse_args()
    token = os.environ.get("DISHCARE_CUSTOMER_TOKEN")
    if not token:
        parser.error("Set DISHCARE_CUSTOMER_TOKEN to a customer JWT")
    headers = {"Authorization": "Bearer " + token}
    base_url = args.base_url.rstrip("/")
    if args.wav:
        with httpx.Client(base_url=base_url, headers=headers, timeout=120) as client:
            response = client.post(
                "/api/v1/voice/turn", content=read_wav(args.wav),
                params={"language": args.language} if args.language else None,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
            args.output.write_bytes(response.content)
            print("Saved", args.output, "session", response.headers["X-Session-ID"])
    else:
        asyncio.run(microphone(base_url, headers, args.language))


if __name__ == "__main__":
    main()
