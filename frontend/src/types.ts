export type Target = "claude" | "chatgpt" | "gemini";

export interface PacketFields {
  title: string;
  source: string;
  goal: string;
  status: string;
  decisions: string[];
  constraints: string[];
  facts: string[];
  open: string[];
  style: string;
  transcript: string;
  ack_sig: string;
  ack_purpose: string;
}

export interface Packet extends PacketFields {
  id: string;
  created: string;
  updated: string;
}

export type Level = "allow" | "ask" | "warn";

export interface IntegrityCheck {
  level: Level;
  reason: string;
  where: string;
  snippet: string;
  signature: string;
}

export const PURPOSES: { id: string; label: string }[] = [
  { id: "practice", label: "I am studying or practising. This is not graded." },
  { id: "allowed", label: "My instructor allows AI help for this work." },
];

export const TOOLS: { id: Target; name: string; how: string }[] = [
  { id: "claude", name: "Claude", how: "Paste into a new chat or a Project's instructions. Uses XML tags." },
  { id: "chatgpt", name: "ChatGPT", how: "Paste as the first message or in Custom Instructions. Uses Markdown." },
  { id: "gemini", name: "Gemini", how: "Paste as the first prompt or save it in a Gem. Uses plain sections." },
];

export interface HandoffResult {
  text: string;
  tokens: number;
  limit: number;
  over_limit: boolean;
  transcript_chars: number;
  transcript_used: number;
  trimmed: boolean;
  condensed: boolean;
  blocked: boolean;
  summarized: boolean;
  integrity: IntegrityCheck;
}

export interface Health {
  ok: boolean;
  llm_configured: boolean;
  provider: string;
  model: string;
}

export const SOURCES = ["Claude", "ChatGPT", "Gemini", "Copilot", "Other"];

export function fieldsOf(p: Packet): PacketFields {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { id, created, updated, ...fields } = p;
  return fields;
}
