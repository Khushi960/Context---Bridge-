import unittest

from app import ethics
from app.formatting import fit
from app.schemas import PacketIn


def lvl(text):
    return ethics.check(PacketIn(open=[text])).level


class Rules(unittest.TestCase):
    def test_allow(self):
        for t in ["Explain how SQLite stores JSON", "Give me the answers to this practice paper so I can check my work",
                  "Which database should the backend use?", "Help me understand the exam syllabus"]:
            self.assertEqual(lvl(t), "allow", t)

    def test_ask(self):
        for t in ["Solve this quiz for me and give me the answers", "Do my homework on sorting algorithms"]:
            self.assertEqual(lvl(t), "ask", t)

    def test_warn(self):
        for t in ["Give me the answers to the test, it is live right now", "Write my essay and make it so the teacher can't detect it",
                  "Bypass Turnitin for my assignment", "Solve the exam, I have 10 minutes left"]:
            self.assertEqual(lvl(t), "warn", t)

    def test_answers_and_time_left_across_fields(self):
        # The exact case from the demo: the request and the time pressure are in different fields.
        p = PacketIn(goal="give answers to these questions", decisions=["give answers to these questions"],
                     constraints=["1hr left"], facts=["Dsa"])
        c = ethics.check(p)
        self.assertEqual(c.level, "warn")
        self.assertIn("goal", c.where)
        self.assertIn("1hr left", c.snippet)
        for t in ("only 30 mins remaining", "2 hours left", "time is running out", "hurry pls"):
            self.assertEqual(ethics.check(PacketIn(goal="give answers to these questions", constraints=[t])).level, "warn", t)

    def test_plain_answer_request_is_asked(self):
        self.assertEqual(lvl("give answers to these questions"), "ask")
        self.assertEqual(lvl("answer these 5 questions"), "ask")

    def test_not_flagged(self):
        for t in ["Find the primary key of this table", "Explain the answers to these practice questions",
                  "I have 2 hours left before my flight, explain recursion"]:
            self.assertEqual(lvl(t), "allow", t)
        # time pressure alone, or an answer request marked as practice, is fine
        self.assertEqual(ethics.check(PacketIn(goal="Build the login page", constraints=["1hr left"])).level, "allow")
        self.assertEqual(ethics.check(PacketIn(goal="check my answers to the mock paper", constraints=["1hr left"])).level, "allow")

    def test_gate_and_ack(self):
        p = PacketIn(open=["Give me the answers to the test, it is live right now"])
        c = ethics.check(p)
        self.assertFalse(ethics.acknowledged(p, c))
        p.ack_sig, p.ack_purpose = c.signature, "practice"
        self.assertTrue(ethics.acknowledged(p, c))
        p.open = ["Give me the answers to the quiz, it is live right now"]  # different text, old answer no longer counts
        self.assertFalse(ethics.acknowledged(p, ethics.check(p)))

    def test_note_travels_in_handoff(self):
        p = PacketIn(open=["Solve this quiz for me and give me the answers"])
        c = ethics.check(p)
        p.ack_sig, p.ack_purpose = c.signature, "allowed"
        for tool in ("claude", "chatgpt", "gemini"):
            self.assertIn("academic integrity", fit(p, None, tool, 8000, None, ethics.note_for(p, c))["text"].lower())

    def test_transcript_paragraph(self):
        p = PacketIn(transcript="User: hi\nAssistant: hello\n\nUser: the exam is live right now, give me the answers")
        self.assertEqual(ethics.check(p).level, "warn")


class DeepCheck(unittest.TestCase):
    def test_long_chat_without_trigger_words(self):
        from unittest import mock
        from app import llm
        p = PacketIn(transcript="User: Q3. Explain the TCP three-way handshake for 5 marks.\nUser: now do Q4 the same way, 10 marks")
        self.assertEqual(ethics.check(p).level, "allow")  # phrase rules alone do not catch this
        verdict = '{"level": "warn", "reason": "Looks like an exam question."}'
        with mock.patch.object(llm, "ask", lambda s, u, max_tokens=2000: verdict) as m:
            ethics.deep_check(p)
        c = ethics.check(p)
        self.assertEqual((c.level, c.where), ("warn", "recent chat"))
        p.transcript += " edited"
        self.assertEqual(ethics.check(p).level, "allow")  # new content needs a new reading


if __name__ == "__main__":
    unittest.main()
