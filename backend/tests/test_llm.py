import io
import json
import os
import unittest
from unittest import mock

from app import llm


class Provider(unittest.TestCase):
    def env(self, **kw):
        base = {k: "" for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "CONTEXT_BRIDGE_PROVIDER")}
        base.update(kw)
        return mock.patch.dict(os.environ, base)

    def test_choice(self):
        with self.env():
            self.assertEqual(llm.provider(), "")
        with self.env(GEMINI_API_KEY="x"):
            self.assertEqual(llm.provider(), "gemini")
        with self.env(ANTHROPIC_API_KEY="x", GEMINI_API_KEY="y"):
            self.assertEqual(llm.provider(), "anthropic")
        with self.env(ANTHROPIC_API_KEY="x", GEMINI_API_KEY="y", CONTEXT_BRIDGE_PROVIDER="gemini"):
            self.assertEqual(llm.provider(), "gemini")
        with self.env(ANTHROPIC_API_KEY="x", CONTEXT_BRIDGE_PROVIDER="gemini"):
            self.assertEqual(llm.provider(), "")

    def test_gemini_call_and_parse(self):
        reply = {"candidates": [{"content": {"parts": [{"text": '{"level": "ask", "reason": "maybe graded"}'}]}}]}
        seen = {}

        def fake(req, timeout=0):
            seen["url"], seen["key"], seen["body"] = req.full_url, req.get_header("X-goog-api-key"), json.loads(req.data)
            return io.BytesIO(json.dumps(reply).encode())

        with self.env(GEMINI_API_KEY="k123"), mock.patch("urllib.request.urlopen", fake):
            out = llm.classify_integrity("solve my quiz")
        self.assertEqual(out["level"], "ask")
        self.assertEqual(seen["key"], "k123")
        self.assertNotIn("k123", seen["url"])  # key goes in a header, never in the URL
        self.assertEqual(seen["body"]["systemInstruction"]["parts"][0]["text"], llm.INTEGRITY_SYSTEM)


if __name__ == "__main__":
    unittest.main()


class Summary(unittest.TestCase):
    def test_summary_wrapped_and_note_kept(self):
        from app import ethics
        from app.formatting import wrap_summary, _bullets
        from app.schemas import PacketIn
        p = PacketIn(title="Demo", source="Claude", open=["."], goal="x")
        self.assertEqual(_bullets(p.open), "")  # a lone '.' is not content
        for t, marker in (("claude", "<context_summary"), ("chatgpt", "# Context handoff"), ("gemini", "CONTEXT HANDOFF")):
            out = wrap_summary(p, "2026-10-20", t, "BODY", "NOTE")
            self.assertIn("BODY", out); self.assertIn("NOTE", out); self.assertTrue(out.startswith(marker))

    def test_summarize_uses_packet_and_target_style(self):
        seen = {}

        def fake_ask(system, user, max_tokens=2000):
            seen["system"], seen["user"] = system, user
            return "  A tidy briefing.  "

        with mock.patch.object(llm, "ask", fake_ask):
            out = llm.summarize({"title": "T", "goal": "shift this to another ai", "transcript": "User: hi", "id": "secret-id"}, "gemini")
        self.assertEqual(out, "A tidy briefing.")
        self.assertIn("shift this to another ai", seen["user"])
        self.assertIn("END OF CHAT", seen["user"])
        self.assertNotIn("secret-id", seen["user"])
        self.assertIn("UPPERCASE", seen["system"])
