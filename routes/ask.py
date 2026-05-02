"""
Ask Route — Main AI query endpoint.

Endpoints:
  POST /api/atlas/ask              — standard request/response
  POST /api/atlas/ask/stream-http  — Server-Sent Events streaming (SSE)
  WS   /api/atlas/ask/stream       — WebSocket streaming (legacy)
"""
import asyncio
import json
import logging
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime

from models.database import get_db, User, Conversation, Message, AgentRun
from models.schemas import AskRequest, AskResponse
from services.auth_utils import get_current_user
from agents.strategist import StrategistAgent

router = APIRouter(prefix="/api/atlas", tags=["Atlas AI"])
logger = logging.getLogger(__name__)


@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Main AI query endpoint.
    Routes question to the appropriate agent and returns a full response.
    """
    # Get or create conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id,
        ).first()
    else:
        conversation = None

    if not conversation:
        conversation = Conversation(
            user_id=current_user.id,
            title=request.query[:60] + ("..." if len(request.query) > 60 else ""),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.query,
    )
    db.add(user_message)
    db.commit()

    # Run through Strategist
    strategist = StrategistAgent()
    result_str = await strategist.investigate(question=request.query)
    result = json.loads(result_str)

    # Save assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.get("answer", ""),
        agent_trace=result.get("agent_trace", []),
        citations=result.get("citations", []),
    )
    db.add(assistant_message)

    # Log agent run
    agent_run = AgentRun(
        conversation_id=conversation.id,
        agent_type="strategist",
        input_query=request.query,
        output=result.get("answer", ""),
        steps=result.get("agent_trace", []),
        duration_ms=result.get("duration_ms", 0),
        success=True,
    )
    db.add(agent_run)
    db.commit()

    return AskResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=result.get("answer", ""),
        agent_trace=result.get("agent_trace", []),
        citations=result.get("citations", []),
        suggested_followups=result.get("suggested_followups", []),
    )


@router.post("/ask/stream-http")
async def ask_stream_http(
    request: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    SSE streaming endpoint for the Atlas AI.

    Streams three kinds of events as they happen:

      {"type": "start",        "message": "...", "timestamp": "..."}
      {"type": "agent_action", "agent": "...", "tool": "...", "description": "...", "timestamp": "..."}
      {"type": "token",        "content": "..."}          ← answer text, word-by-word
      {"type": "complete",     "answer": "...", "citations": [...], ...}
      data: [DONE]

    The frontend can consume this with EventSource or fetch + ReadableStream.
    """
    # ── Conversation setup (before streaming begins) ───────────────────────
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id,
        ).first()
    else:
        conversation = None

    if not conversation:
        conversation = Conversation(
            user_id=current_user.id,
            title=request.query[:60] + ("..." if len(request.query) > 60 else ""),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    conversation_id = conversation.id

    # ── Strategist + trace queue setup ────────────────────────────────────
    trace_queue: asyncio.Queue = asyncio.Queue()
    strategist = StrategistAgent()
    original_log = strategist._log_trace

    def _patched_log(agent: str, tool: str, description: str):
        original_log(agent, tool, description)
        trace_queue.put_nowait({
            "type": "agent_action",
            "agent": agent,
            "tool": tool,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
        })

    strategist._log_trace = _patched_log

    async def event_stream():
        # ── Start ──────────────────────────────────────────────────────────
        yield _sse({"type": "start", "message": "Atlas is thinking...", "timestamp": datetime.utcnow().isoformat()})

        # ── Run investigation concurrently, stream trace events ────────────
        investigate_task = asyncio.create_task(
            strategist.investigate(question=request.query)
        )

        while not investigate_task.done():
            try:
                event = trace_queue.get_nowait()
                yield _sse(event)
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.05)

        # Drain any remaining trace events
        while not trace_queue.empty():
            yield _sse(trace_queue.get_nowait())

        # ── Collect result ─────────────────────────────────────────────────
        try:
            result_str = investigate_task.result()
            result = json.loads(result_str)
        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        # ── Stream answer word-by-word (token simulation) ──────────────────
        answer = result.get("answer", "")
        words = answer.split(" ")
        for i in range(0, len(words), 4):
            chunk = " ".join(words[i : i + 4])
            if i + 4 < len(words):
                chunk += " "
            yield _sse({"type": "token", "content": chunk})
            await asyncio.sleep(0.015)

        # ── Complete event ─────────────────────────────────────────────────
        yield _sse({
            "type": "complete",
            "answer": answer,
            "citations": result.get("citations", []),
            "suggested_followups": result.get("suggested_followups", []),
            "agent_trace": result.get("agent_trace", []),
            "duration_ms": result.get("duration_ms", 0),
        })

        # ── Persist to DB (fresh session — dependency may be expired) ──────
        try:
            from models.database import SessionLocal as _SL
            _db = _SL()
            try:
                _db.add(Message(
                    conversation_id=conversation_id,
                    role="user",
                    content=request.query,
                ))
                assistant_msg = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                    agent_trace=result.get("agent_trace", []),
                    citations=result.get("citations", []),
                )
                _db.add(assistant_msg)
                _db.add(AgentRun(
                    conversation_id=conversation_id,
                    agent_type="strategist",
                    input_query=request.query,
                    output=answer,
                    steps=result.get("agent_trace", []),
                    duration_ms=result.get("duration_ms", 0),
                    success=True,
                ))
                _db.commit()
            finally:
                _db.close()
        except Exception as e:
            logger.error(f"SSE: failed to persist to DB: {e}")

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    """Format a dict as a single SSE data line."""
    return f"data: {json.dumps(payload)}\n\n"


@router.websocket("/ask/stream")
async def ask_stream(websocket: WebSocket, token: str):
    """
    WebSocket endpoint for streaming agent trace to the frontend in real time.
    The frontend shows each agent action as it happens.
    """
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)
            query = request.get("query", "")

            if not query:
                await websocket.send_json({"type": "error", "message": "No query provided"})
                continue

            # Send trace events as agents work
            await websocket.send_json({
                "type": "start",
                "message": "Atlas is thinking...",
                "timestamp": datetime.utcnow().isoformat(),
            })

            strategist = StrategistAgent()

            # Use a queue so trace events can be sent from the sync _log_trace
            # call site without needing an async patch (which would be a no-op
            # since strategist calls _log_trace synchronously).
            ws_queue: asyncio.Queue = asyncio.Queue()
            original_log = strategist._log_trace

            def _ws_log(agent: str, tool: str, description: str):
                original_log(agent, tool, description)
                ws_queue.put_nowait({
                    "type": "agent_action",
                    "agent": agent,
                    "tool": tool,
                    "description": description,
                    "timestamp": datetime.utcnow().isoformat(),
                })

            strategist._log_trace = _ws_log

            investigate_task = asyncio.create_task(
                strategist.investigate(question=query)
            )

            while not investigate_task.done():
                try:
                    event = ws_queue.get_nowait()
                    await websocket.send_json(event)
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.05)

            while not ws_queue.empty():
                await websocket.send_json(ws_queue.get_nowait())

            result_str = investigate_task.result()
            result = json.loads(result_str)

            await websocket.send_json({
                "type": "complete",
                "answer": result.get("answer", ""),
                "citations": result.get("citations", []),
                "suggested_followups": result.get("suggested_followups", []),
                "agent_trace": result.get("agent_trace", []),
                "duration_ms": result.get("duration_ms", 0),
            })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@router.get("/conversations")
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all conversations for the current user."""
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).limit(50).all()

    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "message_count": len(c.messages),
            }
            for c in conversations
        ]
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all messages in a conversation."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if not conversation:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "agent_trace": m.agent_trace,
                "citations": m.citations,
                "created_at": m.created_at,
            }
            for m in conversation.messages
        ],
    }


@router.post("/briefing")
async def morning_briefing(
    current_user: User = Depends(get_current_user),
):
    """Generate a personalised morning briefing for the current user."""
    from agents.strategist import StrategistAgent
    strategist = StrategistAgent()
    result_str = await strategist.morning_briefing(
        user_department=current_user.department or "General"
    )
    return json.loads(result_str)
