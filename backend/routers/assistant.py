"""Assistant router.

Phase 2 replaced the 4,338-line regex intent processor (30+ hand-written
intents) with native LLM tool calling: the model reads the conversation,
picks from 8 tool definitions (see services/assistant_tools.py), and the
tool loop (services/tool_loop.py) executes them against the database.

The /chat contract is unchanged: {message, conversation_history,
conversation_context} -> {response, conversation_context}.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..services.agent_framework.task_orchestrator import TaskOrchestrator, get_agent_orchestrator
from ..services.assistant_tools import build_assistant_tools
from ..services.tool_loop import ToolLoopError, run_tool_loop
from ..utils.config import get_settings
from ..utils.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant")

SYSTEM_PROMPT = """You are RecruitIQ's recruiting assistant, helping a recruiter work their
applicant tracking system. You have tools that read live data: candidate search
(semantic, with an optional location filter), candidate/job lookups, job
matching with scores, match explanations, salary benchmarks, pipeline stats,
and parsed resumes.

Rules:
- When the answer depends on ATS data, call a tool. Never invent candidates,
  jobs, scores, or counts. If a tool returns an error or nothing, say so plainly
  and suggest a nearby question the tools can answer. Never tell the user a
  database or table is missing or not configured: the tools are your database
  access, and they work.
- For place-based searches like "Python engineers in Seattle" or "data
  engineers on the west coast", call search_candidates with the skills or role
  as query and the place as location. Regions like "west coast" are understood.
  If nothing matches the location, the result includes candidates_elsewhere:
  say nobody matched in that place and present those candidates with where they
  actually are. Present search similarity as relevance to the search, never as
  a match score: real match scores come only from match_to_job or explain_match.
- Your reply ends the turn. Never say you will search, check, or look
  something up: there is no later. Make every tool call you need first, then
  answer only from results you already have.
- Answer from conversation context alone for greetings or general recruiting
  questions that need no data.
- When you name a candidate or job that a tool returned, make the name a
  markdown link to its profile using the id from the tool result:
  [Ava Chen](/candidates/<id>) or [Data Engineer](/jobs/<id>). Only link ids
  that appeared in a tool result. Everything else stays plain text.
- Fit the shape of the answer to the question: a ranked list with percentage
  scores for matching, a short profile for one person, matched versus missing
  skills for fit questions, a compact breakdown for pipeline stats, a range
  with context for salary questions. Vary your wording from answer to answer
  instead of repeating one template.
- Be concise and recruiter-friendly: short paragraphs or tight bullet lists,
  scores as percentages. No preamble.
- Never use em dashes or en dashes anywhere, including between a name and a
  title in a list. Use a period, comma, colon, or hyphen instead. This is a
  hard formatting rule, not a style preference.
"""

MAX_MESSAGE_CHARS = 2000

# Shared by /chat and /chat/stream so the two never drift apart in wording.
EMPTY_MESSAGE_REPLY = (
    "I need a question or request to assist you. Could you please provide more "
    "details about what you're looking for?"
)
TOO_LONG_REPLY = "Your message is too long. Please try a shorter query (under 2000 characters)."
DB_DOWN_REPLY = (
    "I'm having trouble connecting to the database at the moment. Please try again shortly."
)
PROVIDERS_DOWN_REPLY = (
    "I'm having trouble reaching my AI service right now. Please try again in a moment."
)


class ChatResponse(BaseModel):
    """The /chat contract, unchanged since Phase 2 — now merely written down."""
    response: str
    conversation_context: Dict[str, Any] = Field(default_factory=dict)


class BufferedFileWrapper:
    """A wrapper for file-like objects that holds name attribute"""

    def __init__(self, filename: str):
        self.name = filename


class BufferedUploadFile:
    """A wrapper for UploadFile that buffers the content and maintains compatibility."""

    def __init__(self, original_file: UploadFile, content: bytes):
        self.filename = original_file.filename
        self.content_type = original_file.content_type
        self.size = len(content)
        self._content = content
        self.file = BufferedFileWrapper(f"buffer:{self.filename}")
        self._original = original_file

    async def read(self, size: int = -1) -> bytes:
        if size == -1:
            return self._content
        return self._content[:size]

    async def seek(self, offset: int) -> None:
        pass

    def __getattr__(self, name):
        if hasattr(self._original, name):
            return getattr(self._original, name)
        raise AttributeError(f"{self.__class__.__name__} has no attribute {name}")


@router.post("/agent-task", summary="Starts an agent task and returns a task ID")
async def execute_agent_task(
    agent_name: str = Form(...),
    task_details_json: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    orchestrator: TaskOrchestrator = Depends(get_agent_orchestrator),
):
    logger.info(f"Received agent task request for agent: {agent_name}")
    try:
        task_details = json.loads(task_details_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in task_details_json.")

    buffered_files = []
    for file in files:
        try:
            content = await file.read()
            try:
                await file.seek(0)
            except Exception:
                pass
            buffered_files.append(BufferedUploadFile(file, content))
            logger.info(f"Successfully buffered file {file.filename} ({len(content)} bytes)")
        except Exception as e:
            logger.error(f"Failed to buffer file {file.filename}: {e}")
            buffered_files.append(file)

    task = {
        "details": task_details,
        "files": buffered_files,
        "session_id": task_details.get("session_id"),
    }

    try:
        result = await orchestrator.execute_task(agent_name, task)
        logger.info(f"Agent {agent_name} completed synchronously.")
        return result
    except ValueError as e:
        logger.error(f"Agent not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start agent task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start task.")


@router.get("/task-status/{task_id}", summary="Get the status of an agent task")
async def get_task_status(
    task_id: str,
    orchestrator: TaskOrchestrator = Depends(get_agent_orchestrator),
):
    logger.info(f"Checking status for task_id: {task_id}")
    try:
        status = await orchestrator.get_task_status(task_id)
        if status is None:
            logger.warning(f"Task {task_id} not found.")
            raise HTTPException(status_code=404, detail="Task not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching task status for {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching task status.")


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    message: str = Body(..., embed=True),
    conversation_history: Optional[List[Dict[str, str]]] = Body(default=[], embed=True),
    conversation_context: Optional[Dict[str, Any]] = Body(default={}, embed=True),
    db: Session = Depends(get_db),
):
    conversation_context = conversation_context or {}

    if not message or message.strip() == "":
        return {
            "response": EMPTY_MESSAGE_REPLY,
            "conversation_context": conversation_context,
        }

    if len(message) > MAX_MESSAGE_CHARS:
        logger.warning(f"Received excessively long message of {len(message)} characters")
        return {
            "response": TOO_LONG_REPLY,
            "conversation_context": conversation_context,
        }

    try:
        db.execute(text("SELECT 1")).fetchone()
        conversation_context["db_available"] = True
    except Exception as db_error:
        logger.error(f"Database connection error: {db_error}")
        conversation_context["db_available"] = False
        return {
            "response": DB_DOWN_REPLY,
            "conversation_context": conversation_context,
        }

    logger.info(f"ASSISTANT: chat query: {message!r} (history={len(conversation_history or [])})")

    try:
        result = await run_tool_loop(
            get_settings(),
            system=SYSTEM_PROMPT,
            message=message,
            history=conversation_history,
            tools=build_assistant_tools(db),
        )
    except ToolLoopError as e:
        logger.error(f"Assistant tool loop failed: {e}")
        return {
            "response": PROVIDERS_DOWN_REPLY,
            "conversation_context": conversation_context,
        }

    logger.info(
        "ASSISTANT: served by %s (%s) in %d ms, tools=%s",
        result.provider,
        result.model,
        result.latency_ms,
        [t["tool"] for t in result.tool_trace],
    )
    conversation_context["last_provider"] = result.provider
    conversation_context["last_tools_used"] = [t["tool"] for t in result.tool_trace]
    return {
        "response": result.text,
        "conversation_context": conversation_context,
    }


def _sse(event: dict) -> str:
    """Format one Server-Sent Event. The `type` key doubles as the event name."""
    payload = dict(event)
    name = payload.pop("type", "message")
    return f"event: {name}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.post("/chat/stream")
async def chat_with_assistant_streaming(
    message: str = Body(..., embed=True),
    conversation_history: Optional[List[Dict[str, str]]] = Body(default=[], embed=True),
    conversation_context: Optional[Dict[str, Any]] = Body(default={}, embed=True),
    db: Session = Depends(get_db),
):
    """The same answer as /chat, with the tool calls narrated as they happen.

    A turn is typically three model calls plus database work, and only the last
    one produces prose — so streaming tokens would cover about the final fifth of
    the wait and leave the rest as dead air. Streaming the *tool activity* covers
    all of it, and shows the thing worth showing: that the assistant is querying
    real ATS data rather than inventing it (spec §5).

    /chat is untouched. Phase 2's contract and its tests stand.
    """
    context = dict(conversation_context or {})

    async def event_stream():
        if not message or not message.strip():
            yield _sse({"type": "message", "response": EMPTY_MESSAGE_REPLY, "conversation_context": context})
            return

        if len(message) > MAX_MESSAGE_CHARS:
            logger.warning("Received excessively long message of %d characters", len(message))
            yield _sse({"type": "message", "response": TOO_LONG_REPLY, "conversation_context": context})
            return

        try:
            db.execute(text("SELECT 1")).fetchone()
            context["db_available"] = True
        except Exception as db_error:  # noqa: BLE001
            logger.error(f"Database connection error: {db_error}")
            context["db_available"] = False
            yield _sse({"type": "message", "response": DB_DOWN_REPLY, "conversation_context": context})
            return

        logger.info("ASSISTANT: stream query: %r (history=%d)", message, len(conversation_history or []))

        # The tool loop pushes events onto the queue from its own task while
        # this generator drains it, so a tool_start reaches the browser the
        # moment it happens rather than when the whole turn finishes.
        queue: asyncio.Queue = asyncio.Queue()
        done = object()

        async def sink(event: dict) -> None:
            await queue.put(event)

        async def drive() -> None:
            try:
                result = await run_tool_loop(
                    get_settings(),
                    system=SYSTEM_PROMPT,
                    message=message,
                    history=conversation_history,
                    tools=build_assistant_tools(db),
                    on_event=sink,
                )
                context["last_provider"] = result.provider
                context["last_tools_used"] = [t["tool"] for t in result.tool_trace]
                logger.info(
                    "ASSISTANT: streamed by %s (%s) in %d ms, tools=%s",
                    result.provider,
                    result.model,
                    result.latency_ms,
                    [t["tool"] for t in result.tool_trace],
                )
                await queue.put(
                    {"type": "message", "response": result.text, "conversation_context": context}
                )
            except ToolLoopError as e:
                logger.error(f"Assistant tool loop failed: {e}")
                await queue.put({"type": "error", "detail": PROVIDERS_DOWN_REPLY})
            except Exception as e:  # noqa: BLE001
                logger.exception("Unexpected failure in the streaming assistant")
                await queue.put({"type": "error", "detail": str(e)})
            finally:
                await queue.put(done)

        task = asyncio.create_task(drive())
        try:
            while True:
                event = await queue.get()
                if event is done:
                    break
                yield _sse(event)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx buffers proxied responses by default, which would deliver
            # the whole stream in one lump and make the feature invisible. The
            # site config sets proxy_buffering off for this location; this
            # header says the same thing from the application side so a
            # misconfigured proxy cannot silently undo it.
            "X-Accel-Buffering": "no",
        },
    )
