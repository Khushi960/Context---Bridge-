import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { copyText } from "./clipboard";
import IntegrityGate from "./components/IntegrityGate";
import ExtractDialog from "./components/ExtractDialog";
import HandoffPanel from "./components/HandoffPanel";
import Page from "./components/Page";
import Sidebar from "./components/Sidebar";
import type { Health, IntegrityCheck, Packet, PacketFields, Target } from "./types";
import { TOOLS, fieldsOf } from "./types";

type Save = "idle" | "saving" | "saved" | "error";

const union = (a: string[], b: string[]) => {
  const seen = new Set(a.map((s) => s.trim().toLowerCase()).filter(Boolean));
  const extra = b.filter((s) => s.trim() && !seen.has(s.trim().toLowerCase()));
  return [...a.filter((s) => s.trim()), ...extra];
};

export default function App() {
  const [packets, setPackets] = useState<Packet[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [save, setSave] = useState<Save>("idle");
  const [loadErr, setLoadErr] = useState("");
  const [navOpen, setNavOpen] = useState(false);
  const [panel, setPanel] = useState(() => window.innerWidth > 1100);
  const [extract, setExtract] = useState(false);
  const [target, setTarget] = useState<Target>("claude");
  const [limit, setLimit] = useState(8000);
  const [gate, setGate] = useState<{ check: IntegrityCheck; then: Target | null } | null>(null);
  const [toast, setToast] = useState("");
  const [flag, setFlag] = useState<IntegrityCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [ai, setAi] = useState(() => {
    try {
      return localStorage.getItem("cb.ai") !== "off";
    } catch {
      return true;
    }
  });
  const setAiPref = (v: boolean) => {
    setAi(v);
    try {
      localStorage.setItem("cb.ai", v ? "on" : "off");
    } catch {
      /* ignore */
    }
  };
  const aiOn = ai && !!health && health.llm_configured;

  const latest = useRef<Packet[]>([]);
  latest.current = packets;
  const timers = useRef<Record<string, number>>({});

  useEffect(() => {
    (async () => {
      try {
        api.health().then(setHealth).catch(() => undefined);
        let list = await api.list();
        if (!list.length) list = [await api.create({ title: "Untitled" })];
        setPackets(list);
        setActiveId(list[0].id);
      } catch {
        setLoadErr("Cannot reach the server. Start the backend with: python3 -m uvicorn app.main:app --reload");
      }
    })();
  }, []);

  const flush = useCallback(async (id: string) => {
    const p = latest.current.find((x) => x.id === id);
    if (!p) return;
    try {
      const saved = await api.update(id, fieldsOf(p));
      setPackets((ps) => ps.map((x) => (x.id === id ? { ...x, updated: saved.updated } : x)));
      setSave("saved");
    } catch {
      setSave("error");
    }
  }, []);

  const patch = useCallback(
    (id: string, part: Partial<PacketFields>) => {
      setPackets((ps) => ps.map((p) => (p.id === id ? { ...p, ...part } : p)));
      setSave("saving");
      window.clearTimeout(timers.current[id]);
      timers.current[id] = window.setTimeout(() => flush(id), 600);
    },
    [flush]
  );

  const active = packets.find((p) => p.id === activeId) || null;

  // Keep a warning banner in step with the page (fast phrase rules; the AI reading is added when asked for or on copy).
  const fsig = active ? JSON.stringify(fieldsOf(active)) : "";
  useEffect(() => {
    if (!active) return;
    let live = true;
    const t = window.setTimeout(() => {
      api.integrity(fieldsOf(active), false).then((c) => live && setFlag(c)).catch(() => undefined);
    }, 700);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fsig]);

  const runDeepSoon = () => runDeepRef.current();
  const runDeepRef = useRef<() => void>(() => undefined);
  const runDeep = async () => {
    if (!active) return;
    setChecking(true);
    try {
      const c = await api.integrity(fieldsOf(active), true);
      setFlag(c);
      if (c.level === "allow") say("The AI read the whole chat and found nothing to warn about.");
    } catch (e) {
      say(e instanceof Error ? e.message : "The AI check could not run.");
    } finally {
      setChecking(false);
    }
  };
  runDeepRef.current = runDeep;
  const unanswered = !!flag && flag.level !== "allow" && !(active && active.ack_sig === flag.signature && active.ack_purpose);

  const newPacket = async () => {
    try {
      const p = await api.create({ title: "Untitled" });
      setPackets((ps) => [p, ...ps]);
      setActiveId(p.id);
      setNavOpen(false);
    } catch {
      setSave("error");
    }
  };

  const remove = async (id: string) => {
    const p = packets.find((x) => x.id === id);
    if (!window.confirm('Delete "' + ((p && p.title) || "Untitled") + '"? This cannot be undone.')) return;
    window.clearTimeout(timers.current[id]);
    try {
      await api.remove(id);
      const rest = packets.filter((x) => x.id !== id);
      if (!rest.length) {
        const fresh = await api.create({ title: "Untitled" });
        setPackets([fresh]);
        setActiveId(fresh.id);
      } else {
        setPackets(rest);
        if (activeId === id) setActiveId(rest[0].id);
      }
    } catch {
      setSave("error");
    }
  };

  const say = (t: string) => {
    setToast(t);
    window.setTimeout(() => setToast(""), 2600);
  };

  /** One click: fetch the handoff for a tool and copy it. If the integrity check blocks it, ask first. */
  const copyFor = async (t: Target, override?: PacketFields) => {
    if (!active) return;
    const f = override || fieldsOf(active);
    const name = TOOLS.find((x) => x.id === t)!.name;
    try {
      let r;
      let fell = "";
      if (aiOn) {
        setToast("Writing the summary…");
        try {
          r = await api.handoff(f, active.updated, t, limit, false, true);
        } catch (e) {
          fell = e instanceof Error ? e.message : "AI summary failed.";
          r = await api.handoff(f, active.updated, t, limit, false, false);
        }
      } else {
        r = await api.handoff(f, active.updated, t, limit, false, false);
      }
      if (r.blocked) {
        setToast("");
        setGate({ check: r.integrity, then: t });
        return;
      }
      setTarget(t);
      const ok = await copyText(r.text);
      say(
        !ok
          ? "Copy was blocked. Use the Preview panel and copy the text there."
          : fell
          ? "AI summary failed (" + fell + "). Copied the plain version for " + name + "."
          : "Copied " + (r.summarized ? "an AI summary" : "the handoff") + " for " + name
      );
    } catch (e) {
      say(e instanceof Error ? e.message : "Could not build the handoff.");
    }
  };

  const confirmGate = (purpose: string) => {
    if (!active || !gate) return;
    const part = { ack_sig: gate.check.signature, ack_purpose: purpose };
    patch(active.id, part);
    const then = gate.then;
    setGate(null);
    if (then) copyFor(then, { ...fieldsOf(active), ...part });
  };

  const deepCheck = async () => {
    if (!active || !gate) return;
    const c = await api.integrity(fieldsOf(active), true);
    if (c.level === "allow") {
      setGate(null);
      say("The AI read it again and found nothing wrong.");
    } else {
      setGate({ ...gate, check: c });
    }
  };

  const applyExtract = (f: PacketFields) => {
    if (!active) return;
    // After a chat is pasted in, let the AI read it for signs of an exam or graded question.
    if (health && health.llm_configured) window.setTimeout(() => runDeepSoon(), 900);
    const noTitle = !active.title.trim() || active.title === "Untitled";
    patch(active.id, {
      title: noTitle ? f.title : active.title,
      goal: f.goal || active.goal,
      status: f.status || active.status,
      style: f.style || active.style,
      decisions: union(active.decisions, f.decisions),
      constraints: union(active.constraints, f.constraints),
      facts: union(active.facts, f.facts),
      open: union(active.open, f.open),
      transcript: f.transcript || active.transcript,
    });
  };

  if (loadErr) return <div className="center">{loadErr}</div>;
  if (!active) return <div className="center">Loading…</div>;

  const saveText = { idle: "", saving: "Saving…", saved: "Saved", error: "Not saved. Check the server." }[save];

  return (
    <div className={"app" + (panel ? " with-panel" : "")}>
      <Sidebar
        packets={packets}
        activeId={activeId}
        open={navOpen}
        health={health}
        onSelect={(id) => {
          setActiveId(id);
          setNavOpen(false);
        }}
        onNew={newPacket}
        onDelete={remove}
      />
      {navOpen && <div className="veil" onClick={() => setNavOpen(false)} />}

      <main className="main">
        <header className="topbar">
          <button className="icon menu" aria-label="Open packets" onClick={() => setNavOpen(true)}>☰</button>
          <div className="crumb">{active.title || "Untitled"}</div>
          <span className={"save" + (save === "error" ? " err" : "")} role="status">{saveText}</span>
          <button className="btn quiet" onClick={() => setExtract(true)}>Fill from chat</button>
          <label className={"aiswitch" + (health && !health.llm_configured ? " off" : "")} title={health && !health.llm_configured ? "Add an API key in backend/.env to turn this on" : "The AI rewrites your notes as a clean briefing before copying"}>
            <input type="checkbox" checked={aiOn} disabled={!health || !health.llm_configured} onChange={(e) => setAiPref(e.target.checked)} />
            AI summary
          </label>
          <div className="copybar" role="group" aria-label="Copy handoff">
            <span>Copy for</span>
            {TOOLS.map((t) => (
              <button key={t.id} className="btn primary" onClick={() => copyFor(t.id)}>{t.name}</button>
            ))}
          </div>
          <button className={"btn" + (panel ? " on" : "")} onClick={() => setPanel(!panel)} aria-pressed={panel}>Preview</button>
        </header>
        {unanswered && flag && (
          <div className={"banner " + flag.level} role="alert">
            <div>
              <b>{flag.level === "warn" ? "Stop and think: this may be an exam or graded work." : "Is this graded work?"}</b>{" "}
              {flag.reason} If a test or exam is going on, ask your instructor what is allowed before you copy this to another AI.
            </div>
            <div className="bn-actions">
              <button className="btn" onClick={() => setGate({ check: flag, then: null })}>Review and answer</button>
              {health && health.llm_configured && (
                <button className="btn quiet" onClick={runDeep} disabled={checking}>{checking ? "Reading…" : "Check the chat with AI"}</button>
              )}
            </div>
          </div>
        )}
        <div className="scroll">
          <Page key={active.id} packet={active} onChange={(part) => patch(active.id, part)} onCheck={health && health.llm_configured ? runDeep : undefined} checking={checking} />
        </div>
      </main>

      {panel && (
        <HandoffPanel
          packet={active}
          target={target}
          limit={limit}
          onTarget={setTarget}
          onLimit={setLimit}
          onBlocked={(c) => setGate({ check: c, then: null })}
          aiOn={aiOn}
          onCopy={copyFor}
          onClose={() => setPanel(false)}
        />
      )}
      {gate && <IntegrityGate check={gate.check} llmReady={!!health && health.llm_configured} onDeep={deepCheck} onConfirm={confirmGate} onClose={() => setGate(null)} />}
      {toast && <div className="toast" role="status">{toast}</div>}
      {extract && (
        <ExtractDialog source={active.source} llmReady={!!health && health.llm_configured} onClose={() => setExtract(false)} onApply={applyExtract} />
      )}
    </div>
  );
}
