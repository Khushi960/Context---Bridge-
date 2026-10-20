import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Target = Literal["claude", "chatgpt", "gemini"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:10]


class PacketIn(BaseModel):
    """The editable part of a packet (what the frontend sends)."""
    title: str = "Untitled"
    source: str = "Claude"
    goal: str = ""
    status: str = ""
    decisions: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)
    open: List[str] = Field(default_factory=list)
    style: str = ""
    transcript: str = ""
    # Student's answer to an academic-integrity prompt, tied to the flagged text by signature.
    ack_sig: str = ""
    ack_purpose: str = ""


class Packet(PacketIn):
    id: str
    created: str
    updated: str


class User(BaseModel):
    id: str
    username: str
    created: str


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ExtractRequest(BaseModel):
    transcript: str = Field(min_length=1)
    source: str = "Claude"


class IntegrityCheck(BaseModel):
    level: Literal["allow", "ask", "warn"] = "allow"
    reason: str = ""
    where: str = ""      # which part of the packet was flagged
    snippet: str = ""    # the flagged text, shortened
    signature: str = ""  # identifies this flag, so an answer only counts for the same text


class IntegrityRequest(BaseModel):
    packet: PacketIn
    deep: bool = False   # ask the LLM to double-check the flagged text


class HandoffRequest(BaseModel):
    packet: PacketIn
    updated: Optional[str] = None
    target: Target = "claude"
    limit_tokens: int = Field(default=8000, ge=500, le=200000)
    condense: bool = False
    summarize: bool = False   # let the LLM write a clean summary instead of copying the fields as typed


class HandoffResult(BaseModel):
    text: str
    tokens: int
    limit: int
    over_limit: bool
    transcript_chars: int
    transcript_used: int
    trimmed: bool
    condensed: bool
    blocked: bool = False
    summarized: bool = False
    integrity: IntegrityCheck = Field(default_factory=IntegrityCheck)
