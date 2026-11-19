import asyncio
import logging
from contextlib import suppress
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from app.core.exceptions import BusinessError
from app.core.security import authenticate_customer, get_current_customer
from app.monitoring.usage import RequestUsage, current_usage
from app.voice.audio import FRAME_BYTES, MAX_PCM_BYTES, wav_bytes
from app.voice.session import Endpoint

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])
Customer = Annotated[str, Depends(get_current_customer)]


def pipeline_for(state):
    if state.voice_pipeline is None or state.chat_engine is None:
        raise BusinessError(503, "VOICE_DISABLED", "The voice service is not available")
    return state.voice_pipeline


@router.post("/turn", responses={200: {"content": {"audio/wav": {}}}})
async def turn(
    request: Request, customer: Customer, session_id: UUID | None = None,
    language: Literal["en", "hi"] | None = None,
):
    state = request.app.state
    pipeline = pipeline_for(state)
    if request.headers.get("content-type", "").split(";")[0] != "application/octet-stream":
        raise BusinessError(415, "UNSUPPORTED_AUDIO", "Send application/octet-stream PCM audio")
    pcm = bytearray()
    async for chunk in request.stream():
        pcm.extend(chunk)
        if len(pcm) > MAX_PCM_BYTES:
            raise BusinessError(413, "AUDIO_TOO_LARGE", "Audio exceeds 20 seconds")
    session_id = session_id or uuid4()
    reply = await pipeline.turn(bytes(pcm), state.chat_engine, customer, session_id, language)
    return Response(wav_bytes(reply.pcm, reply.sample_rate), media_type="audio/wav",
                    headers={"X-Session-ID": str(session_id)})


@router.websocket("/stream")
async def stream(
    socket: WebSocket, session_id: UUID | None = None,
    language: Literal["en", "hi"] | None = None,
):
    state = socket.app.state
    authorization = socket.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        await socket.close(code=1008)
        return
    try:
        customer = await authenticate_customer(authorization[7:], state.settings, state.db)
    except HTTPException:
        await socket.close(code=1008)
        return
    allowed, _ = await state.limiter.allow(f"voice:{customer}", 12)
    if not allowed or state.voice_connections.locked():
        await socket.close(code=1013)
        return
    try:
        pipeline = pipeline_for(state)
    except BusinessError:
        await socket.close(code=1013)
        return
    async with state.voice_connections:
        await voice_session(socket, state, pipeline, customer, session_id or uuid4(), language)


async def voice_session(socket, state, pipeline, customer, session_id, language):
    endpoint = Endpoint(await asyncio.to_thread(pipeline.vad_factory))
    pending = None
    send_lock = asyncio.Lock()
    await socket.accept()
    await socket.send_json({"type": "ready", "session_id": str(session_id), "frame_bytes": FRAME_BYTES})

    async def respond(audio):
        allowed, _ = await state.limiter.allow(f"voice-turn:{customer}", 20)
        if not allowed:
            async with send_lock:
                await socket.send_json({"type": "error", "code": "RATE_LIMIT_EXCEEDED"})
            return
        usage = RequestUsage(state.metrics, state.settings.llm_prices_per_million)
        token = current_usage.set(usage)
        try:
            reply = await pipeline.turn(audio, state.chat_engine, customer, session_id, language)
            async with send_lock:
                await socket.send_json({
                    "type": "reply", "transcript": reply.transcript, "answer": reply.answer,
                    "sample_rate": reply.sample_rate, "timings": reply.elapsed,
                })
                await socket.send_bytes(reply.pcm)
        except BusinessError as exc:
            async with send_lock:
                await socket.send_json({"type": "error", "code": exc.code})
        except (WebSocketDisconnect, OSError):
            return
        except Exception as exc:
            logger.warning("Voice turn failed, type=%s", type(exc).__name__)
            async with send_lock:
                await socket.send_json({"type": "error", "code": "VOICE_TURN_FAILED"})
        finally:
            current_usage.reset(token)

    async def cancel_turn():
        if pending is not None:
            if not send_lock.locked():
                pending.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect, OSError):
                await pending

    try:
        while True:
            packet = await asyncio.wait_for(socket.receive(), timeout=60)
            if packet["type"] == "websocket.disconnect":
                break
            command = packet.get("text")
            if command == "interrupt":
                await cancel_turn()
                pending = None
                endpoint.reset()
                async with send_lock:
                    await socket.send_json({"type": "interrupted"})
                continue
            if command == "end":
                audio = endpoint.finish()
            elif packet.get("bytes") is not None:
                try:
                    audio = await asyncio.to_thread(endpoint.feed, packet["bytes"])
                except ValueError:
                    await socket.close(code=1003)
                    return
            else:
                await socket.close(code=1003)
                return
            if audio:
                if pending is not None and not pending.done():
                    async with send_lock:
                        await socket.send_json({"type": "error", "code": "TURN_IN_PROGRESS"})
                else:
                    pending = asyncio.create_task(respond(audio))
    except TimeoutError:
        await socket.close(code=1000)
    except (WebSocketDisconnect, OSError):
        pass
    finally:
        await cancel_turn()
