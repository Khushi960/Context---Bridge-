import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { HandoffResult, IntegrityCheck, Packet, Target } from "../types";
import { TOOLS, fieldsOf } from "../types";

const LIMITS = [4000, 8000, 16000, 32000];

interface Props {
  packet: Packet;
  target: Target;
  limit: number;
  onTarget: (t: Target) => void;
  onLimit: (n: number) => void;
  onBlocked: (c: IntegrityCheck) => void;
  aiOn: boolean;
  onCopy: (t: Target) => void;
  onClose: () => void;
}

export default function HandoffPanel({ packet, target, limit, onTarget, onLimit, onBlocked, aiOn, onCopy, onClose }: Props) {
  const [res, setRes] = useState<HandoffResult | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const outRef = useRef<HTMLPreElement>(null);

  const fields = fieldsOf(packet);
  const sig = JSON.stringify(fields) + target + limit;

  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      api
        .handoff(fields, packet.updated, target, limit, false)
        .then((r) => live && (setRes(r), setErr("")))
        .catch((e) => live && setErr(e.message));
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  const condense = async () => {
    setBusy(true);
    setErr("");
    try {
      const r = await api.handoff(fields, packet.updated, target, limit, true);
      setRes(r);
      if (r.blocked) onBlocked(r.integrity);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const [ai, setAiRes] = useState<HandoffResult | null>(null);
  useEffect(() => setAiRes(null), [sig]); // an AI preview goes stale as soon as the notes change

  const writeAi = async () => {
    setBusy(true);
    setErr("");
    try {
      const r = await api.handoff(fields, packet.updated, target, limit, false, true);
      if (r.blocked) onBlocked(r.integrity);
      else setAiRes(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const shown = aiOn && ai ? ai : res;
  const pct = shown && !shown.blocked ? Math.min(100, Math.round((shown.tokens / shown.limit) * 100)) : 0;
  const how = TOOLS.find((t) => t.id === target)!.how;
  const blocked = !!res && res.blocked;

  return (
    <aside className="panel" aria-label="Handoff preview">
      <div className="panel-head">
        <h2>Handoff</h2>
        <button className="icon" onClick={onClose} aria-label="Close handoff">×</button>
      </div>

      <div className="seg" role="tablist" aria-label="Target tool">
        {TOOLS.map((t) => (
          <button key={t.id} role="tab" aria-selected={target === t.id} className={target === t.id ? "on" : ""} onClick={() => onTarget(t.id)}>
            {t.name}
          </button>
        ))}
      </div>
      <p className="hint">{how}</p>

      <label className="inline" htmlFor="limit">
        Size limit
        <select id="limit" value={limit} onChange={(e) => onLimit(parseInt(e.target.value, 10))}>
          {LIMITS.map((l) => (
            <option key={l} value={l}>about {l.toLocaleString()} tokens</option>
          ))}
        </select>
      </label>

      <div className="meter" aria-live="polite">
        <div className="bar"><div className={pct > 90 ? "hot" : ""} style={{ width: pct + "%" }} /></div>
        <div className="meta">
          <span>{shown && !blocked ? "≈ " + shown.tokens.toLocaleString() + " tokens" : "—"}</span>
          <span>{shown && !blocked ? shown.text.length.toLocaleString() + " characters" : ""}</span>
        </div>
      </div>

      {res && res.trimmed && (
        <p className="note">
          Chat trimmed from {res.transcript_chars.toLocaleString()} to {res.transcript_used.toLocaleString()} characters.{" "}
          <button className="link" onClick={condense} disabled={busy}>
            {busy ? "Condensing…" : "Condense with AI instead"}
          </button>
        </p>
      )}
      {res && res.condensed && <p className="note okc">The model condensed the chat to fit.</p>}
      {res && res.over_limit && <p className="note">The fields alone are over the limit. Shorten them or raise the limit.</p>}
      {err && <p className="warn" role="alert">{err}</p>}

      {blocked && res ? (
        <div className={"lock " + res.integrity.level}>
          <b>{res.integrity.level === "warn" ? "Locked: integrity warning" : "Locked: one question first"}</b>
          <p>{res.integrity.reason}</p>
          <button className="btn primary" onClick={() => onBlocked(res.integrity)}>Answer to unlock</button>
        </div>
      ) : (
        <>
          {aiOn && (
            <p className="note">
              {ai ? "AI summary shown. " : "Showing your notes as typed. "}
              <button className="link" onClick={writeAi} disabled={busy}>{busy ? "Writing…" : ai ? "Rewrite" : "Preview the AI summary"}</button>
            </p>
          )}
          <pre className="out" ref={outRef} tabIndex={0}>{shown ? shown.text : ""}</pre>
        </>
      )}

      <button className="btn primary wide" onClick={() => onCopy(target)} disabled={!res}>
        {aiOn ? "Summarise and copy for " : "Copy for "}{TOOLS.find((t) => t.id === target)!.name}
      </button>
    </aside>
  );
}
