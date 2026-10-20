import { useEffect, useState } from "react";
import { PURPOSES } from "../types";
import type { IntegrityCheck } from "../types";

interface Props {
  check: IntegrityCheck;
  llmReady: boolean;
  onDeep: () => Promise<void>;
  onConfirm: (purpose: string) => void;
  onClose: () => void;
}

export default function IntegrityGate({ check, llmReady, onDeep, onConfirm, onClose }: Props) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const strong = check.level === "warn";

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  const deep = async () => {
    setBusy(true);
    setErr("");
    try {
      await onDeep();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not reach the model.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={"dialog gate " + (strong ? "strong" : "soft")} role="alertdialog" aria-modal="true" aria-labelledby="gate-t" aria-describedby="gate-d">
        <p className="eyebrow">{strong ? "Academic integrity warning" : "Quick check before you copy"}</p>
        <h2 id="gate-t">{strong ? "This looks like it could be cheating." : "Is this for graded work?"}</h2>
        <p id="gate-d" className="hint">
          {check.reason} The handoff stays locked until you tell us what this is for. Your answer is added to the handoff, so the next AI tool knows too.
        </p>
        <blockquote className="quote">
          <span className="quote-k">Found in {check.where}</span>
          {check.snippet}
        </blockquote>
        <div className="choices">
          {PURPOSES.map((p) => (
            <button key={p.id} className="choice" onClick={() => onConfirm(p.id)}>
              {p.label}
            </button>
          ))}
        </div>
        <p className="fine">
          Do not choose either if it is not true. If this is a live or graded test, close this and ask your instructor what is allowed.
          {strong ? " Getting final answers to submit as your own is academic misconduct at most universities." : ""}
        </p>
        {err && <p className="warn" role="alert">{err}</p>}
        <div className="actions">
          {llmReady && (
            <button className="btn quiet" onClick={deep} disabled={busy} title="Ask the AI model to re-read the flagged line">
              {busy ? "Checking…" : "Double-check with AI"}
            </button>
          )}
          <button className="btn" onClick={onClose}>Go back and edit</button>
        </div>
      </div>
    </div>
  );
}
