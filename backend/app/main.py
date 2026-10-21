"""Context Bridge API.

Run from the backend folder:
    python3 -m uvicorn app.main:app --reload
Interactive docs: http://127.0.0.1:8000/docs
"""
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import os  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from . import auth, db, ethics, llm  # noqa: E402
from .auth import current_user  # noqa: E402
from .formatting import fit, wrap_summary  # noqa: E402
from .schemas import (  # noqa: E402
    Credentials, ExtractRequest, HandoffRequest, HandoffResult, IntegrityCheck, IntegrityRequest, Packet, PacketIn,
    User, now_iso,
)

app = FastAPI(title="Context Bridge API")


@app.exception_handler(Exception)
async def unexpected_error(request, exc):  # shows a readable message instead of "Internal Server Error"
    import logging
    logging.getLogger("context_bridge").exception("Unexpected error on %s", request.url.path)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"detail": "Server error (%s: %s). The full error is in the terminal "
                                                            "running the server." % (type(exc).__name__, str(exc)[:150])})
api = APIRouter(prefix="/api")

SEED = PacketIn(
    title="Cross-Tool AI Context Bridge",
    source="Claude",
    goal="Build an app that turns a project's state into a portable context packet that can be pasted into Claude, ChatGPT or Gemini.",
    status="Proposal approved. Synopsis, architecture diagrams and the build plan are next. Editor, formatting and the FastAPI backend are working.",
    decisions=["Packets are structured fields, not raw chat logs",
               "One packet is the source of truth; each AI tool gets its own formatted copy",
               "FastAPI backend with SQLite storage"],
    constraints=["Mini project for the AIAS course", "Must work with tools that have no API, so copy and paste comes first"],
    facts=["Target tools: Claude, ChatGPT, Gemini", "A token is roughly four characters of English"],
    open=["How should packets be versioned when two tools edit the same project?",
          "How can a long transcript be trimmed without losing decisions?"],
    style="Short, practical answers.",
)


# Set CONTEXT_BRIDGE_SECURE_COOKIE=1 when the app is served over https, so the login cookie is never sent over http.
SECURE_COOKIE = os.getenv("CONTEXT_BRIDGE_SECURE_COOKIE", "") == "1"


@app.on_event("startup")
def startup() -> None:
    db.init()


@api.get("/health")
def health():
    return {"ok": True, "llm_configured": llm.configured(), "provider": llm.provider(), "model": llm.model_name()}


# ---------- login ----------

def _login(resp: Response, user: User) -> User:
    resp.set_cookie(auth.COOKIE, auth.start_session(user), max_age=auth.SESSION_DAYS * 86400,
                    httponly=True, samesite="lax", secure=SECURE_COOKIE, path="/")
    return user


@api.post("/auth/register", response_model=User)
def register(cred: Credentials, resp: Response):
    """Create an account and log in. The first account also receives any packets saved before login existed."""
    first = db.user_count() == 0
    user = auth.register(cred.username, cred.password)
    if not (first and db.claim_orphans(user.id)):
        db.create(user.id, SEED)
    return _login(resp, user)


@api.post("/auth/login", response_model=User)
def login(cred: Credentials, resp: Response):
    return _login(resp, auth.authenticate(cred.username, cred.password))


@api.post("/auth/logout")
def logout(resp: Response, cb_session: Optional[str] = Cookie(default=None)):
    auth.end_session(cb_session)
    resp.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@api.get("/auth/me", response_model=User)
def me(user: User = Depends(current_user)):
    return user


# ---------- packets (each user sees only their own) ----------

@api.get("/packets", response_model=List[Packet])
def list_packets(user: User = Depends(current_user)):
    return db.list_packets(user.id)


@api.post("/packets", response_model=Packet)
def create_packet(p: PacketIn, user: User = Depends(current_user)):
    return db.create(user.id, p)


@api.get("/packets/{pid}", response_model=Packet)
def get_packet(pid: str, user: User = Depends(current_user)):
    p = db.get(user.id, pid)
    if not p:
        raise HTTPException(404, "Packet not found")
    return p


@api.put("/packets/{pid}", response_model=Packet)
def update_packet(pid: str, p: PacketIn, user: User = Depends(current_user)):
    out = db.update(user.id, pid, p)
    if not out:
        raise HTTPException(404, "Packet not found")
    return out


@api.delete("/packets/{pid}")
def delete_packet(pid: str, user: User = Depends(current_user)):
    if not db.delete(user.id, pid):
        raise HTTPException(404, "Packet not found")
    return {"deleted": pid}


# ---------- AI features (login required, so the API key is not open to anyone on the network) ----------

@api.post("/extract", response_model=PacketIn, dependencies=[Depends(current_user)])
def extract(req: ExtractRequest):
    """LLM reads a pasted chat and returns packet fields. Nothing is saved here."""
    return PacketIn(**llm.extract_packet(req.transcript, req.source))


@api.post("/integrity", response_model=IntegrityCheck, dependencies=[Depends(current_user)])
def integrity(req: IntegrityRequest):
    """Academic-integrity check on a packet. deep=true lets the LLM double-check the flagged text."""
    if req.deep:
        ethics.deep_check(req.packet)
    return ethics.check(req.packet)


@api.post("/handoff", response_model=HandoffResult, dependencies=[Depends(current_user)])
def handoff(req: HandoffRequest):
    """Format a packet for a target tool within a token limit.

    If the integrity check flags the packet and the student has not answered the prompt, nothing is generated
    (blocked=true). Once answered, a short integrity note is added to the handoff so the next tool sees it too.
    """
    summary = None
    if req.summarize and llm.configured():
        # The AI integrity reading and the AI summary run at the same time, so the student waits for one call, not two.
        with ThreadPoolExecutor(max_workers=2) as pool:
            deep = pool.submit(ethics.deep_check, req.packet)
            summary = pool.submit(llm.summarize, req.packet.model_dump(), req.target)
            try:
                deep.result()
            except HTTPException:
                pass  # if the model is unreachable, the rule check below still runs
            summary.exception()  # wait for it; any error is raised below only if the summary is used
    c = ethics.check(req.packet)
    if not ethics.acknowledged(req.packet, c):
        return HandoffResult(text="", tokens=0, limit=req.limit_tokens, over_limit=False, transcript_chars=0,
                             transcript_used=0, trimmed=False, condensed=False, blocked=True, integrity=c)
    note = ethics.note_for(req.packet, c)
    if req.summarize:
        body = summary.result() if summary is not None else llm.summarize(req.packet.model_dump(), req.target)
        text = wrap_summary(req.packet, req.updated or now_iso(), req.target, body, note)
        return HandoffResult(text=text, tokens=-(-len(text) // 4), limit=req.limit_tokens,
                             over_limit=len(text) > req.limit_tokens * 4, transcript_chars=len(req.packet.transcript),
                             transcript_used=0, trimmed=False, condensed=False, blocked=False, summarized=True, integrity=c)
    out = fit(req.packet, req.updated, req.target, req.limit_tokens, llm.condense if req.condense else None, note)
    return HandoffResult(**out, blocked=False, integrity=c)


app.include_router(api)

# Serve the built React app (frontend/dist) at "/" when it exists.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="web")
