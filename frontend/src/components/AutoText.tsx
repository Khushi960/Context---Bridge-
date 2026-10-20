import { useLayoutEffect, useRef } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
  id?: string;
  label: string;
}

/** Borderless textarea that grows with its content, like a Notion text block. */
export default function AutoText({ value, onChange, placeholder, mono, id, label }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }, [value]);
  return (
    <textarea
      ref={ref}
      id={id}
      aria-label={label}
      className={"auto" + (mono ? " mono" : "")}
      rows={1}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
