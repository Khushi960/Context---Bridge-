import type { HandoffResult, Health, IntegrityCheck, Packet, PacketFields, Target } from "./types";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch("/api" + path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

const body = (o: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(o) });

export const api = {
  health: () => call<Health>("/health"),
  list: () => call<Packet[]>("/packets"),
  create: (p: Partial<PacketFields>) => call<Packet>("/packets", body(p)),
  update: (id: string, p: PacketFields) => call<Packet>("/packets/" + id, { method: "PUT", body: JSON.stringify(p) }),
  remove: (id: string) => call<{ deleted: string }>("/packets/" + id, { method: "DELETE" }),
  extract: (transcript: string, source: string) => call<PacketFields>("/extract", body({ transcript, source })),
  integrity: (packet: PacketFields, deep: boolean) => call<IntegrityCheck>("/integrity", body({ packet, deep })),
  handoff: (packet: PacketFields, updated: string, target: Target, limit_tokens: number, condense: boolean, summarize = false) =>
    call<HandoffResult>("/handoff", body({ packet, updated, target, limit_tokens, condense, summarize })),
};
