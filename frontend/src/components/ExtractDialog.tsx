import { useEffect, useState } from "react";
import { api } from "../api";
import type { PacketFields } from "../types";

interface Props {
  source: string;
  llmReady: boolean;
  onClose: () => void;
  onApply: (f: PacketFields) => void;
}

export default function ExtractDialog({ source, llmReady, onClose, onApply }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  const run = async () => {
    setBusy(true);
    setErr("");
    try {
      onApply(await api.extract(text, source));
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-t">
        <h2 id="dlg-t">Fill from a chat</h2>
        <p className="hint">
          Paste a conversation from {source}. The model reads it and fills the goal, decisions, constraints, facts and open questions. Existing
          items on the page are kept.
        </p>
        {!llmReady && <p className="warn">No API key found. Add ANTHROPIC_API_KEY or GEMINI_API_KEY to backend/.env and restart the server.</p>}
        <textarea
          className="paste"
          aria-label="Chat transcript"
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="User: …&#10;Assistant: …"
        />
        {err && <p className="warn" role="alert">{err}</p>}
        <div className="actions">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={run} disabled={busy || !text.trim()}>
            {busy ? "Reading chat…" : "Fill page"}
          </button>
        </div>
      </div>
    </div>
  );
}
