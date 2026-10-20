"""Academic-integrity guard.

Reads the text of a packet and returns one of three levels:
  allow  nothing worrying, handoff works as normal
  ask    looks like it could be graded work, so the student must say what it is for
  warn   looks like a live test or an attempt to hide AI use, so the student gets a clear warning first

It is a nudge, not enforcement. The rules are deliberately simple and readable so they can be explained and
tested. An optional LLM "deep check" (llm.classify_integrity) can refine a flagged snippet. Its verdict is
cached by snippet, so ordinary handoffs never wait on a model call.
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple

from .formatting import _real
from .schemas import IntegrityCheck, PacketIn

LEVELS = ("allow", "ask", "warn")
RANK = {"allow": 0, "ask": 1, "warn": 2}

# What the student may answer when asked. Both mean "this is not cheating", so we record which one it was.
PURPOSES = {
    "practice": "I am studying or practising. This is not graded.",
    "allowed": "My instructor allows AI help for this work.",
}

ANSWER_ASK = re.compile(
    r"\b(give|tell|send|write|solve|provide|get|find|share)\b[^.\n]{0,30}\b(answers?|solutions?|key)\b"
    r"|\banswer\s*key\b|\bsolve (this|these|the|my) (paper|test|quiz|exam|questions?)\b"
    r"|\bdo my (homework|assignment|exam|test|quiz|lab|project|cca)\b|\bwrite my (essay|assignment|report|answers?)\b"
    r"|\bcomplete (my|this) (assignment|test|exam|quiz)\b", re.I)
ASSESSMENT = re.compile(
    r"\b(exam|test|quiz|mid[- ]?sem|end[- ]?sem|viva|assessment|assignment|homework|cca\s?\d?|internals?|proctor\w*|"
    r"online test|hackerrank|coding round|graded)\b", re.I)
LIVE = re.compile(
    r"\b(right now|live|ongoing|going on|in the (exam|test)|during (the|my) (exam|test|quiz)|timer|\d+ ?min(ute)?s? left|"
    r"submit (it )?(by|before|in)|due (today|tonight|in)|invigilator|proctored|"
    r"\d+(\.\d+)? ?(h|hrs?|hours?|m|mins?|minutes?|secs?|seconds?) (left|remaining|to go)|"
    r"(only|just) \d+(\.\d+)? ?(h|hrs?|hours?|mins?|minutes?)|half an? hour|"
    r"time (is )?(left|remaining|up|almost up|running out)|before (the )?time (runs out|ends|is up)|"
    r"hurry|quick,? (please|pls|plz)|fast,? (please|pls|plz)|asap|urgent(ly)?)\b", re.I)
# A plain request for ready-made answers ("give answers to these questions"), with nothing saying it is practice.
WANTS_ANSWERS = re.compile(
    r"\b(give|tell|send|write|provide|share|get|need|want)\b[^.\n]{0,30}\b(answers?|ans)\b|\banswer (these|this|all|the following)\b", re.I)
HIDE = re.compile(
    r"\b(submit|turn in|hand in)\b[^.\n]{0,25}\b(as (my|mine)|my own|under my name)\b"
    r"|\b(so|such that|make sure|ensure)\b[^.\n]{0,40}\b(can'?t|won'?t|doesn'?t|don'?t|cannot) (detect|notice|find out|catch|know)\b"
    r"|\b(bypass|avoid|beat|fool|evade)\b[^.\n]{0,15}\b(turnitin|ai[- ]?detect\w*|plagiarism|proctor\w*)\b"
    r"|\bhumani[sz]e\b[^.\n]{0,20}\bto (pass|avoid|bypass)\b", re.I)
SAFE = re.compile(
    r"\b(mock|practice|practise|sample|past (year )?papers?|previous year|study|revis\w+|explain|understand|why|how (does|do|to)|"
    r"concept|check my (own )?(answer|work)|feedback on)\b", re.I)


def _units(p: PacketIn) -> List[Tuple[str, str]]:
    """Pieces of text checked on their own, so unrelated lines are never stitched together."""
    out: List[Tuple[str, str]] = []
    for name, v in (("goal", p.goal), ("status", p.status), ("style", p.style)):
        if v.strip():
            out.append((name, v))
    for name, items in (("decision", p.decisions), ("constraint", p.constraints), ("fact", p.facts), ("open question", p.open)):
        out.extend((name, i) for i in items if i.strip())
    t = p.transcript[-20000:]
    for para in re.split(r"\n\s*\n", t):
        if para.strip():
            out.append(("recent conversation", para))
            if "\n" in para.strip():
                out.extend(("recent conversation", ln) for ln in para.splitlines() if ln.strip())
    return out


def classify_text(text: str) -> Tuple[str, str]:
    """Rule verdict for one piece of text: (level, reason)."""
    if HIDE.search(text):
        return "warn", "This asks for AI work to be passed off as your own, or to avoid detection."
    asks = ANSWER_ASK.search(text) or WANTS_ANSWERS.search(text)
    if not asks:
        return "allow", ""
    assess, live = ASSESSMENT.search(text), LIVE.search(text)
    if assess and live:
        return "warn", "This asks for answers while a test or deadline seems to be happening right now."
    if SAFE.search(text) and not live:
        return "allow", ""
    if assess:
        return "ask", "This asks for answers to what may be graded work."
    if WANTS_ANSWERS.search(text) and not SAFE.search(text):
        return "ask", "This asks for ready-made answers. If a test or exam may be going on, this could be misuse of AI."
    return "allow", ""


def _snippet(text: str) -> str:
    s = " ".join(text.split())
    return s if len(s) <= 140 else s[:137] + "..."


def _sig(level: str, snippet: str) -> str:
    return hashlib.sha1((level + "|" + snippet.lower()).encode()).hexdigest()[:12]


_chat: Dict[str, Tuple[str, str]] = {}  # packet-content hash -> (level, reason) from the LLM, filled by deep_check()


def _chat_text(p: PacketIn) -> str:
    parts = []
    for label, v in (("Goal", p.goal), ("Status", p.status)):
        if _real(v):
            parts.append("%s: %s" % (label, v.strip()))
    parts.extend("Open: " + i.strip() for i in p.open if _real(i))
    if _real(p.transcript):
        parts.append("CHAT (most recent part):\n" + p.transcript.strip()[-6000:])
    return "\n".join(parts)


def _chat_key(p: PacketIn) -> str:
    return hashlib.sha1(_chat_text(p).encode()).hexdigest()[:12]


def deep_check(p: PacketIn) -> None:
    """Ask the LLM to read the notes and the whole chat. The verdict is cached by content, so repeats are free."""
    from . import llm  # imported here so the rules work (and are testable) without any LLM setup
    text = _chat_text(p)
    if not _real(text) or _chat_key(p) in _chat:
        return
    v = llm.classify_integrity(text)
    _chat[_chat_key(p)] = (v["level"], v["reason"])


def check(p: PacketIn) -> IntegrityCheck:
    best: Optional[Tuple[str, str, str, str]] = None  # level, reason, where, snippet
    for where, text in _units(p):
        level, reason = classify_text(text)
        if level == "allow":
            continue
        if best is None or RANK[level] > RANK[best[0]]:
            best = (level, reason, where, _snippet(text))
    # Look across the whole packet too: "give answers to these questions" in the goal and "1hr left" in the
    # constraints are harmless one by one, but together they look like a test that is going on right now.
    units = _units(p)
    ask_u = next(((w, t) for w, t in units if (ANSWER_ASK.search(t) or WANTS_ANSWERS.search(t)) and not SAFE.search(t)), None)
    live_u = next(((w, t) for w, t in units if LIVE.search(t)), None)
    if ask_u and live_u and (best is None or best[0] != "warn"):
        where = ask_u[0] if ask_u[0] == live_u[0] else "%s and %s" % (ask_u[0], live_u[0])
        snip = ask_u[1] if ask_u[1] == live_u[1] else "%s ... %s" % (" ".join(ask_u[1].split())[:90], " ".join(live_u[1].split())[:40])
        best = ("warn", "You are asking for answers and your notes say time is running out. A test or exam may be going on right now.",
                where, _snippet(snip))
    # The LLM's reading of the whole chat can raise the level. It never lowers a rule hit (rules stay a safety net).
    deep = _chat.get(_chat_key(p))
    if deep and deep[0] != "allow" and (best is None or RANK[deep[0]] > RANK[best[0]]):
        tail = p.transcript.strip()[-200:] or p.goal or p.status
        best = (deep[0], deep[1], "recent chat" if p.transcript.strip() else "your notes", _snippet(tail))
    if best is None:
        return IntegrityCheck(level="allow", reason="", where="", snippet="", signature="")
    level, reason, where, snip = best
    return IntegrityCheck(level=level, reason=reason, where=where, snippet=snip, signature=_sig(level, snip))


def acknowledged(p: PacketIn, c: IntegrityCheck) -> bool:
    return c.level == "allow" or (p.ack_sig == c.signature and p.ack_purpose in PURPOSES)


def note_for(p: PacketIn, c: IntegrityCheck) -> str:
    """One line that travels inside the handoff so the next tool also knows the situation."""
    if c.level == "allow":
        return ""
    why = PURPOSES.get(p.ack_purpose, "")
    return ("The student was asked about academic integrity and said: \"%s\" "
            "If any part of this is graded or assessed work, help them learn and check their own thinking "
            "instead of handing over final answers to submit." % why)
