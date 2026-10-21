"""Turns a packet into paste-ready text for each AI tool. No LLM involved here."""
from typing import Callable, Dict, List, Optional, Tuple

from .schemas import PacketIn, Target, now_iso


def _real(s: str) -> bool:
    """True if the text has at least one letter or digit (a lone '.' does not count)."""
    return any(c.isalnum() for c in s)


def _bullets(items: List[str]) -> str:
    return "\n".join("- " + i.lstrip("-*• ").strip() for i in items if _real(i))


def _sections(p: PacketIn, note: str = "") -> List[Tuple[str, str, str]]:
    return [s for s in [
        ("goal", "Goal", p.goal.strip() if _real(p.goal) else ""),
        ("current_state", "Where things stand", p.status.strip() if _real(p.status) else ""),
        ("decisions", "Decisions made", _bullets(p.decisions)),
        ("constraints", "Constraints", _bullets(p.constraints)),
        ("key_facts", "Key facts", _bullets(p.facts)),
        ("open_questions", "Open questions", _bullets(p.open)),
        ("answer_style", "How I want answers", p.style.strip() if _real(p.style) else ""),
        ("academic_integrity", "Academic integrity", note.strip()),
    ] if s[2]]


def build(p: PacketIn, updated: str, target: Target, transcript: str, note: str = "") -> str:
    date, secs, t = updated[:10], _sections(p, note), transcript.strip()
    if target == "claude":
        out = '<context_packet project="%s" from="%s" updated="%s">\n' % (p.title, p.source, date)
        out += "".join("<%s>\n%s\n</%s>\n" % (tag, body, tag) for tag, _, body in secs)
        if t:
            out += "<recent_conversation>\n%s\n</recent_conversation>\n" % t
        out += ("<instructions>\nThis is context carried over from %s. Treat the decisions and constraints as "
                "settled unless I say otherwise. In two sentences, tell me what you understood, then start on "
                "the open questions.\n</instructions>\n</context_packet>" % p.source)
        return out
    if target == "chatgpt":
        out = ("# Context handoff: %s\n\nI have been working on this in %s (last updated %s). "
               "Use the notes below as background for this chat.\n" % (p.title, p.source, date))
        out += "".join("\n## %s\n%s\n" % (label, body) for _, label, body in secs)
        if t:
            out += "\n## Recent conversation\n```\n%s\n```\n" % t
        return out + ("\n## What to do first\nSummarize your understanding in two sentences. Treat the decisions "
                      "and constraints as settled unless I say otherwise. Then start on the open questions.")
    out = "CONTEXT HANDOFF: %s\nFrom: %s   Updated: %s\n" % (p.title.upper(), p.source, date)
    out += "".join("\n%s:\n%s\n" % (label.upper(), body) for _, label, body in secs)
    if t:
        out += "\nRECENT CONVERSATION:\n%s\n" % t
    return out + ("\nYOUR TASK:\nRead everything above. Reply with a two-sentence summary of what you understood, "
                  "treat the decisions and constraints as settled, then begin on the open questions.")


def wrap_summary(p: PacketIn, updated: str, target: Target, body: str, note: str = "") -> str:
    """Put an LLM-written summary inside the same per-tool wrapper the structured handoff uses."""
    date, body, note = updated[:10], body.strip(), note.strip()
    if target == "claude":
        out = '<context_summary project="%s" from="%s" updated="%s">\n%s\n' % (p.title, p.source, date, body)
        if note:
            out += "<academic_integrity>\n%s\n</academic_integrity>\n" % note
        return out + ("<instructions>\nThis is context carried over from %s. Treat the decisions as settled unless I say "
                      "otherwise. In two sentences, tell me what you understood, then continue from the next steps.\n"
                      "</instructions>\n</context_summary>" % p.source)
    if target == "chatgpt":
        out = "# Context handoff: %s\n\nFrom %s, last updated %s. Use this as background for this chat.\n\n%s\n" % (p.title, p.source, date, body)
        if note:
            out += "\n## Academic integrity\n%s\n" % note
        return out + "\n## What to do first\nSummarize your understanding in two sentences, then continue from the next steps."
    out = "CONTEXT HANDOFF: %s\nFrom: %s   Updated: %s\n\n%s\n" % (p.title.upper(), p.source, date, body)
    if note:
        out += "\nACADEMIC INTEGRITY:\n%s\n" % note
    return out + "\nYOUR TASK:\nReply with a two-sentence summary of what you understood, then continue from the next steps."


def fit(p: PacketIn, updated: Optional[str], target: Target, limit_tokens: int,
        condenser: Optional[Callable[[str, int], str]] = None, note: str = "") -> Dict:
    """Build the handoff and make it fit the token budget (tokens are estimated as chars / 4)."""
    updated = updated or now_iso()
    max_chars = limit_tokens * 4
    full = p.transcript.strip()
    room = max_chars - len(build(p, updated, target, "", note)) - 60
    used, trimmed, condensed = full, False, False
    if len(full) > max(room, 0):
        if condenser and room > 300:
            used, condensed = condenser(full, room)[:room], True
        elif room > 200:
            used = full[-room:]
            nl = used.find("\n")
            if 0 <= nl < 200:
                used = used[nl + 1:]
            trimmed = True
        else:
            used, trimmed = "", True
    text = build(p, updated, target, used, note)
    return {
        "text": text, "tokens": -(-len(text) // 4), "limit": limit_tokens, "over_limit": len(text) > max_chars,
        "transcript_chars": len(full), "transcript_used": len(used), "trimmed": trimmed, "condensed": condensed,
    }
