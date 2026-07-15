import { useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, Loader2 } from "lucide-react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

const LONG_INPUT = 300; // show a character counter past this length

export function MessageInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const grow = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
    if (taRef.current) taRef.current.style.height = "auto";
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const canSend = !disabled && value.trim().length > 0;

  return (
    <div className="border-t border-surface-3 bg-surface-0/80 px-4 py-3 backdrop-blur">
      <div className="mx-auto flex w-full max-w-3xl items-end gap-2">
        <div
          className={[
            "flex flex-1 items-end rounded-2xl border bg-surface-2 transition-shadow",
            focused
              ? "border-accent ring-2 ring-accent/25"
              : "border-surface-3",
          ].join(" ")}
        >
          <textarea
            ref={taRef}
            rows={1}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              grow(e.target);
            }}
            onKeyDown={onKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Message REMY…"
            aria-label="Message REMY"
            className="max-h-40 flex-1 resize-none bg-transparent px-4 py-3 text-[14.5px] text-ink outline-none placeholder:text-ink-faint"
          />
        </div>
        <button
          onClick={submit}
          disabled={!canSend}
          aria-label="Send message"
          className="flex h-11 w-11 flex-none items-center justify-center rounded-xl bg-gradient-to-br from-accent-from to-accent-to text-white shadow-accent-glow transition-all hover:brightness-110 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
        >
          {disabled ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <ArrowUp size={18} />
          )}
        </button>
      </div>

      {/* Meta row: hint only while focused; char counter for long messages. */}
      <div className="mx-auto mt-1.5 flex h-4 w-full max-w-3xl items-center justify-between px-1 text-[11px] text-ink-faint">
        <span
          className={`transition-opacity ${focused ? "opacity-100" : "opacity-0"}`}
        >
          Enter to send · Shift+Enter for a new line
        </span>
        {value.length > LONG_INPUT && (
          <span className="tabular-nums">{value.length} chars</span>
        )}
      </div>
    </div>
  );
}
