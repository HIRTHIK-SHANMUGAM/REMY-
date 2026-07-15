import { useState } from "react";
import { Check, Copy } from "lucide-react";

interface Props {
  text: string;
  label?: string;
  className?: string;
}

/** Small copy-to-clipboard button with a transient "Copied" confirmation. */
export function CopyButton({ text, label, className = "" }: Props) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback for older webviews without the async clipboard API.
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  return (
    <button
      onClick={copy}
      aria-label={label ?? "Copy"}
      title={label ?? "Copy"}
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink ${className}`}
    >
      {copied ? (
        <>
          <Check size={13} className="text-emerald-400" />
          {label && <span className="text-emerald-400">Copied</span>}
        </>
      ) : (
        <>
          <Copy size={13} />
          {label && <span>{label}</span>}
        </>
      )}
    </button>
  );
}
