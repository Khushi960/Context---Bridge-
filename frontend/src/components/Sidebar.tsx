import type { Health, Packet } from "../types";

interface Props {
  packets: Packet[];
  activeId: string | null;
  open: boolean;
  health: Health | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export default function Sidebar({ packets, activeId, open, health, onSelect, onNew, onDelete }: Props) {
  return (
    <nav className={"sidebar" + (open ? " open" : "")} aria-label="Packets">
      <div className="brand">
        <svg width="26" height="20" viewBox="0 0 26 20" aria-hidden="true">
          <path d="M1 18V15C1 7 6 2 13 2s12 5 12 13v3" fill="none" stroke="currentColor" strokeWidth="2.2" />
          <path d="M1 12h24" stroke="currentColor" strokeWidth="2.2" />
        </svg>
        <span>Context Bridge</span>
      </div>
      <button className="new" onClick={onNew}>
        <span aria-hidden="true">+</span> New packet
      </button>
      <ul>
        {packets.map((p) => (
          <li key={p.id} className={p.id === activeId ? "active" : ""}>
            <button className="item" onClick={() => onSelect(p.id)} aria-current={p.id === activeId ? "page" : undefined}>
              <span className="name">{p.title || "Untitled"}</span>
              <span className="src">{p.source}</span>
            </button>
            <button className="del" aria-label={"Delete " + (p.title || "Untitled")} title="Delete" onClick={() => onDelete(p.id)}>
              ×
            </button>
          </li>
        ))}
      </ul>
      <div className="foot">
        <div><i className="pip on" /> Integrity guard on</div>
        <div><i className={"pip" + (health && health.llm_configured ? " on" : "")} /> {health && health.llm_configured ? "AI: " + (health.provider === "gemini" ? "Gemini" : "Claude") : "AI features need an API key"}</div>
      </div>
    </nav>
  );
}
