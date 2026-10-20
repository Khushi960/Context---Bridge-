"""Scores the integrity rules on a labelled prompt file.  Run from backend/:  python3 eval/run_eval.py [file.jsonl]

Prints a confusion matrix and, for the question "should this be flagged at all?", precision and recall.
The bundled prompts are only a starter set. For a paper, replace them with a larger set that was labelled
by people who have not read the rules, and report the numbers from that.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import ethics  # noqa: E402
from app.schemas import PacketIn  # noqa: E402

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("prompts.jsonl")
rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
levels = ["allow", "ask", "warn"]
cm = {a: {b: 0 for b in levels} for a in levels}
for r in rows:
    cm[r["label"]][ethics.check(PacketIn(open=[r["text"]])).level] += 1
print("rows = true label, columns = predicted\n%8s" % "" + "".join("%7s" % l for l in levels))
for a in levels:
    print("%8s" % a + "".join("%7d" % cm[a][b] for b in levels))
tp = sum(cm[a][b] for a in levels[1:] for b in levels[1:])
fp = sum(cm["allow"][b] for b in levels[1:])
fn = sum(cm[a]["allow"] for a in levels[1:])
exact = sum(cm[l][l] for l in levels)
print("\nflagged-or-not: precision %.2f  recall %.2f   exact level match %d/%d" % (tp / max(tp + fp, 1), tp / max(tp + fn, 1), exact, len(rows)))
