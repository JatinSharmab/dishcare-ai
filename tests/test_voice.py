import threading
import wave
from io import BytesIO
from types import SimpleNamespace

import pytest
from starlette.websockets import WebSocketDisconnect

from app.voice.audio import FRAME_BYTES
from app.voice.pipeline import VoicePipeline
from conftest import auth_headers

VOICE = "/api/v1/voice"
SPEECH = b"\x01\x00" * 512
SILENCE = bytes(FRAME_BYTES)


class TestVAD:
    __test__ = False

    def __call__(self, frame):
        return frame != SILENCE

    def reset(self):
        pass


@pytest.fixture
def voice(client):
    state = client.app.state
    seen = []

    def transcribe(pcm, language):
        assert SPEECH in pcm
        return "मेरा बैलेंस कितना है?", language or "hi"

    async def chat(customer, transcript, session_id):
        seen.append((customer, transcript, session_id))
        return SimpleNamespace(answer="आपका बैलेंस 350 रुपये है।", language="hindi")

    def synthesize(text, language):
        assert language == "hindi"
        return SPEECH, 22050

    state.voice_pipeline = VoicePipeline(
        SimpleNamespace(transcribe=transcribe), SimpleNamespace(synthesize=synthesize), TestVAD, state.metrics,
    )
    state.chat_engine = SimpleNamespace(chat=chat)
    return seen


def test_audio_turn_wav_and_auth(client, voice):
    assert client.post(VOICE + "/turn", content=SPEECH).status_code == 401
    headers = {**auth_headers(client), "Content-Type": "application/octet-stream"}
    assert client.post(VOICE + "/turn", content=b"\x01", headers=headers).status_code == 422
    response = client.post(VOICE + "/turn?language=hi", content=SPEECH, headers=headers)
    assert response.status_code == 200
    with wave.open(BytesIO(response.content)) as audio:
        assert audio.getframerate() == 22050
        assert audio.getnchannels() == 1
        assert audio.readframes(512) == SPEECH
    assert voice[0][0] == "CUST001"
    assert response.headers["X-Session-ID"] == str(voice[0][2])


def test_websocket_turn_endpointing_and_bound_session(client, voice):
    headers = auth_headers(client)
    with client.websocket_connect(VOICE + "/stream?language=hi", headers=headers) as socket:
        ready = socket.receive_json()
        assert ready["type"] == "ready"
        socket.send_bytes(SPEECH)
        for _ in range(19):
            socket.send_bytes(SILENCE)
        reply = socket.receive_json()
        assert reply["type"] == "reply"
        assert socket.receive_bytes() == SPEECH
        assert str(voice[0][2]) == ready["session_id"]


def test_websocket_interrupt_discards_turn(client, voice):
    state = client.app.state
    entered = threading.Event()

    async def chat(customer, transcript, session_id):
        import asyncio

        entered.set()
        await asyncio.sleep(30)

    state.chat_engine.chat = chat
    with client.websocket_connect(VOICE + "/stream", headers=auth_headers(client)) as socket:
        socket.receive_json()
        socket.send_bytes(SPEECH)
        socket.send_text("end")
        assert entered.wait(timeout=5)
        socket.send_text("interrupt")
        assert socket.receive_json()["type"] == "interrupted"


def test_websocket_denies_missing_token(client):
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(VOICE + "/stream"):
        pass
