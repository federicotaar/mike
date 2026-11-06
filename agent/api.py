"""HTTP API the iPhone app talks to, reached only through the secure tunnel.

Every endpoint reads or writes real state in Memory. Where a capability is
not built yet, the API says so instead of pretending.
"""
from __future__ import annotations
from pathlib import Path
import secrets
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from .brain import InvalidProviderResponse, ProviderNotConfigured, QuotaSpent, think
from .config import settings
from .memory import Memory

async def require_token(authorization: str = Header(default="")):
    """Every endpoint needs the shared token once one is configured.

    With no MIKE_TOKEN set the core is expected on 127.0.0.1 only (local
    testing). Never expose it on a network without a token.
    """
    if settings.api_token and not secrets.compare_digest(authorization.encode(), f"Bearer {settings.api_token}".encode()):
        raise HTTPException(status_code=401, detail="bad or missing bearer token")


VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
STARTED_AT = time.time()  # process start, for honest uptime reporting


def core_version() -> str:
    """Version shown to the app comes from the repo's VERSION file, not a constant."""
    try:
        return VERSION_FILE.read_text().strip()
    except OSError:
        return "unknown"


@asynccontextmanager
async def lifespan(app):
    from .scheduler import start
    scheduler = start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="mike", version=core_version(), lifespan=lifespan,
              dependencies=[Depends(require_token)])
# Created lazily: importing this module must not require a writable data dir.
memory: Memory | None = None


def mem() -> Memory:
    global memory
    if memory is None:
        memory = Memory(settings.db_path)
    return memory


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=32000)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class FeedbackIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("feedback must not be blank")
        return value


class ApprovalDecision(BaseModel):
    approve: bool


@app.get("/status")
async def status():
    return {
        "providerConfigured": bool(settings.groq_api_key),
        # Honest null: the provider's remaining free quota cannot be read.
        "quotaRemainingToday": None,
        # What Mike itself counted today, and the optional local cap (0 = none).
        "requestsSentToday": mem().requests_today(),
        "localDailyCap": settings.local_daily_cap,
        "paused": mem().is_paused(),
        "version": core_version(),
        "uptimeSeconds": int(time.time() - STARTED_AT),
    }


@app.post("/chat")
async def chat(body: ChatIn):
    if mem().is_paused():
        return {"reply": "I'm paused. Start me again from the Activity tab and I'll pick this up."}
    memories = "\n".join(f"- {text}" for _, _, text in mem().recall())
    system = (
        f"You are {settings.agent_name}, the user's personal agent. "
        "Known about the user:\n" + (memories or "(nothing yet)")
    )
    cap = settings.local_daily_cap
    if cap and mem().requests_today() >= cap:
        mem().log_activity("chat", body.message[:140])
        return {"reply": f"I've reached the daily limit of {cap} requests you set for me. It resets tomorrow, or raise MIKE_LOCAL_DAILY_CAP."}
    mem().count_request()
    try:
        reply = await think([
            {"role": "system", "content": system},
            {"role": "user", "content": body.message},
        ])
    except QuotaSpent:
        reply = "I'm out of free requests for today. I'll be back at full speed tomorrow."
    except ProviderNotConfigured:
        reply = "I don't have an approved model key yet. Ask me again once that's set up."
    except InvalidProviderResponse:
        reply = "The model returned no usable reply. Try again in a moment."
    except httpx.HTTPError:
        reply = "I can't reach the model right now. Check the connection and try again in a moment."
    mem().log_activity("chat", body.message[:140])
    return {"reply": reply}


@app.post("/feedback")
async def feedback(body: FeedbackIn):
    """How it learns: the user's correction becomes memory."""
    mem().remember("feedback", body.text)
    mem().log_activity("feedback", body.text[:140])
    return {"stored": True}


@app.get("/approvals/pending")
async def pending_approvals():
    return mem().pending_approvals()


@app.get("/approvals")
async def approvals_history():
    """Full approval record (pending, approved, denied) for the Activity tab."""
    return mem().approvals_history()


@app.post("/approvals/{approval_id}")
async def decide_approval(approval_id: int, body: ApprovalDecision):
    if not mem().decide_approval(approval_id, body.approve):
        raise HTTPException(status_code=404, detail="no pending approval with that id")
    mem().log_activity(
        "approval",
        f"{'approved' if body.approve else 'denied'} approval #{approval_id}",
    )
    return {"ok": True}


@app.get("/memories/search")
async def search_memories(q: str = ""):
    """Find active memories containing the query text, case-insensitive."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="q must not be blank")
    return [
        {"id": str(i), "kind": k, "text": t}
        for i, k, t in mem().search_memories(q)
    ]


@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int):
    """The user owns their memory: delete one for good, with a real 404."""
    if not mem().forget(memory_id):
        raise HTTPException(status_code=404, detail="no memory with that id")
    mem().log_activity("memory", f"deleted memory #{memory_id}")
    return {"deleted": True}


@app.get("/activity")
async def activity():
    return mem().recent_activity()


@app.post("/stop")
async def stop():
    mem().set_paused(True)
    mem().log_activity("stop", "Mike paused by user")
    return {"paused": True}


@app.post("/start")
async def start():
    mem().set_paused(False)
    mem().log_activity("start", "Mike resumed by user")
    return {"paused": False}
