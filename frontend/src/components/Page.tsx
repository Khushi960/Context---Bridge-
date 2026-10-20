import { useState } from "react";
import type { Packet, PacketFields } from "../types";
import { SOURCES } from "../types";
import AutoText from "./AutoText";
import ListBlock from "./ListBlock";

interface Props {
  packet: Packet;
  onChange: (part: Partial<PacketFields>) => void;
  onCheck?: () => void;
  checking?: boolean;
}

function Row({ title, hint, filled, children }: { title: string; hint: string; filled: boolean; children: React.ReactNode }) {
  return (
    <section className="row-f">
      <div className="lab">
        <h3>
          <i className={"tick" + (filled ? " on" : "")} aria-hidden="true" />
          {title}
        </h3>
        <p>{hint}</p>
      </div>
      <div className="val">{children}</div>
    </section>
  );
}

function fmt(iso: string) {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

const real = (s: string) => /[\p{L}\p{N}]/u.test(s); // a lone "." is not content
const has = (v: string | string[]) => (Array.isArray(v) ? v.some(real) : real(v));

export default function Page({ packet: p, onChange, onCheck, checking }: Props) {
  const [showChat, setShowChat] = useState(!!p.transcript);
  const parts = [p.goal, p.status, p.decisions, p.constraints, p.facts, p.open, p.style];
  const done = parts.filter(has).length;
  return (
    <article className="page">
      <input className="title" aria-label="Packet title" value={p.title} placeholder="Name this project" onChange={(e) => onChange({ title: e.target.value })} />

      <div className="meta-line">
        <label>
          Worked on in{" "}
          <select aria-label="Source tool" value={p.source} onChange={(e) => onChange({ source: e.target.value })}>
            {SOURCES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <span>Edited {fmt(p.updated)}</span>
        <span className="done" title={done + " of 7 sections have something in them"}>
          <span className="ticks" aria-hidden="true">
            {parts.map((x, i) => (
              <i key={i} className={has(x) ? "on" : ""} />
            ))}
          </span>
          {done} of 7 filled
        </span>
      </div>

      <Row title="Goal" hint="What you are trying to get done." filled={has(p.goal)}>
        <AutoText label="Goal" value={p.goal} onChange={(v) => onChange({ goal: v })} placeholder="One or two sentences" />
      </Row>
      <Row title="Where things stand" hint="What is finished, and what you were doing last." filled={has(p.status)}>
        <AutoText label="Where things stand" value={p.status} onChange={(v) => onChange({ status: v })} placeholder="Current state" />
      </Row>
      <Row title="Decisions" hint="Already settled. The next tool treats these as fixed." filled={has(p.decisions)}>
        <ListBlock label="Decision" items={p.decisions} onChange={(v) => onChange({ decisions: v })} placeholder="Add a decision, press Enter for another" />
      </Row>
      <Row title="Constraints" hint="Stack, deadlines, rules, things to avoid." filled={has(p.constraints)}>
        <ListBlock label="Constraint" items={p.constraints} onChange={(v) => onChange({ constraints: v })} placeholder="Add a constraint" />
      </Row>
      <Row title="Key facts" hint="Names, numbers and definitions it needs." filled={has(p.facts)}>
        <ListBlock label="Fact" items={p.facts} onChange={(v) => onChange({ facts: v })} placeholder="Add a fact" />
      </Row>
      <Row title="Open questions" hint="What the next tool should help with." filled={has(p.open)}>
        <ListBlock label="Open question" items={p.open} onChange={(v) => onChange({ open: v })} placeholder="Add a question" />
      </Row>
      <Row title="Answer style" hint="Tone, format, level of detail." filled={has(p.style)}>
        <AutoText label="Answer style" value={p.style} onChange={(v) => onChange({ style: v })} placeholder="For example: short, with code examples" />
      </Row>

      <section className="row-f">
        <div className="lab">
          <h3>
            <i className={"tick" + (has(p.transcript) ? " on" : "")} aria-hidden="true" />
            Recent chat
          </h3>
          <p>Optional. Trimmed from the top to fit the size limit.</p>
        </div>
        <div className="val">
          {!showChat && !p.transcript ? (
            <button className="btn quiet" onClick={() => setShowChat(true)}>Paste a chat</button>
          ) : (
            <>
              <AutoText mono label="Recent chat" value={p.transcript} onChange={(v) => onChange({ transcript: v })} placeholder="Paste the end of the conversation here" />
              {p.transcript && (
                <p className="count">
                  {p.transcript.length.toLocaleString()} characters
                  {onCheck && (
                    <>
                      {" · "}
                      <button className="link" onClick={onCheck} disabled={checking}>{checking ? "Reading the chat…" : "Check this chat for exam or graded work"}</button>
                    </>
                  )}
                </p>
              )}
            </>
          )}
        </div>
      </section>
    </article>
  );
}
