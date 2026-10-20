import { useEffect, useLayoutEffect, useRef, useState } from "react";

interface Props {
  items: string[];
  onChange: (items: string[]) => void;
  placeholder: string;
  label: string;
}

function Line(props: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { inner: (el: HTMLTextAreaElement | null) => void }) {
  const { inner, ...rest } = props;
  const ref = useRef<HTMLTextAreaElement | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = el.scrollHeight + "px";
    }
  }, [props.value]);
  return (
    <textarea
      {...rest}
      rows={1}
      ref={(el) => {
        ref.current = el;
        inner(el);
      }}
    />
  );
}

/** Bulleted list: Enter adds a bullet, Backspace on an empty bullet removes it. */
export default function ListBlock({ items, onChange, placeholder, label }: Props) {
  const rows = items.length ? items : [""];
  const refs = useRef<(HTMLTextAreaElement | null)[]>([]);
  const [focusIdx, setFocusIdx] = useState<number | null>(null);

  useEffect(() => {
    if (focusIdx !== null) {
      refs.current[focusIdx]?.focus();
      setFocusIdx(null);
    }
  }, [focusIdx, rows.length]);

  const set = (i: number, v: string) => {
    const next = rows.slice();
    next[i] = v;
    onChange(next);
  };

  const key = (e: React.KeyboardEvent<HTMLTextAreaElement>, i: number) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const next = rows.slice();
      next.splice(i + 1, 0, "");
      onChange(next);
      setFocusIdx(i + 1);
    } else if (e.key === "Backspace" && rows[i] === "" && rows.length > 1) {
      e.preventDefault();
      const next = rows.slice();
      next.splice(i, 1);
      onChange(next);
      setFocusIdx(Math.max(0, i - 1));
    } else if (e.key === "ArrowUp" && i > 0) {
      refs.current[i - 1]?.focus();
    } else if (e.key === "ArrowDown" && i < rows.length - 1) {
      refs.current[i + 1]?.focus();
    }
  };

  const blur = (e: React.FocusEvent<HTMLDivElement>) => {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    const clean = items.map((s) => s.trim()).filter(Boolean);
    if (clean.length !== items.length || clean.some((s, i) => s !== items[i])) onChange(clean);
  };

  return (
    <div className="list" onBlur={blur} role="list" aria-label={label}>
      {rows.map((v, i) => (
        <div className="li" key={i} role="listitem">
          <span className="dot" aria-hidden="true" />
          <Line
            inner={(el) => {
              refs.current[i] = el;
            }}
            value={v}
            aria-label={label + " " + (i + 1)}
            placeholder={i === 0 ? placeholder : ""}
            onChange={(e) => set(i, e.target.value)}
            onKeyDown={(e) => key(e, i)}
          />
        </div>
      ))}
    </div>
  );
}
