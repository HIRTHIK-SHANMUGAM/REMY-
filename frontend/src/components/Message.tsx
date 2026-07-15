import { memo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Sparkles } from "lucide-react";
import type { ChatMessage } from "../hooks/useRemy";
import { CopyButton } from "./CopyButton";

function relativeTime(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(ts).toLocaleDateString();
}

// Extract the raw text from a <pre> node's children so it can be copied.
function textOf(node: ReactNode): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (node && typeof node === "object" && "props" in (node as any))
    return textOf((node as any).props.children);
  return "";
}

// Code blocks: wrap <pre> with a hover-reveal copy button.
function PreBlock({ children }: { children?: ReactNode }) {
  const code = textOf(children).replace(/\n$/, "");
  return (
    <div className="group/code relative">
      <div className="absolute right-1.5 top-1.5 opacity-0 transition-opacity group-hover/code:opacity-100">
        <CopyButton text={code} className="bg-surface-1/80 backdrop-blur" />
      </div>
      <pre>{children}</pre>
    </div>
  );
}

const MARKDOWN_COMPONENTS = { pre: PreBlock };

function MessageBase({
  message,
  grouped = false,
}: {
  message: ChatMessage;
  grouped?: boolean;
}) {
  const { role, content, ts, streaming } = message;

  if (role === "system") {
    return (
      <div className="mt-4 flex justify-center animate-fade-in">
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-500 dark:text-amber-300">
          <AlertTriangle size={13} />
          <span>{content}</span>
        </div>
      </div>
    );
  }

  const isUser = role === "user";

  return (
    <div
      className={[
        "group/msg flex animate-fade-in gap-3",
        isUser ? "justify-end" : "justify-start",
        grouped ? "mt-1" : "mt-4",
      ].join(" ")}
    >
      {!isUser &&
        (grouped ? (
          <div className="w-8 flex-none" aria-hidden />
        ) : (
          <div className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-full bg-gradient-to-br from-accent-from to-accent-to text-white shadow-bubble">
            <Sparkles size={16} />
          </div>
        ))}

      <div className={`flex min-w-0 flex-col ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={[
            "max-w-full px-4 py-2.5 text-[14.5px] leading-relaxed shadow-bubble",
            isUser
              ? "rounded-2xl rounded-br-md bg-gradient-to-br from-accent-from to-accent-to text-white"
              : "rounded-2xl rounded-bl-md border border-surface-3 bg-surface-1 text-ink",
            grouped && !isUser ? "rounded-tl-md" : "",
            grouped && isUser ? "rounded-tr-md" : "",
          ].join(" ")}
        >
          {isUser ? (
            <span className="whitespace-pre-wrap break-words">{content}</span>
          ) : (
            <div className="markdown break-words">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
                {content}
              </ReactMarkdown>
              {streaming && (
                <span
                  aria-hidden
                  className="ml-0.5 inline-block h-[1.05em] w-[3px] translate-y-[3px] animate-pulse rounded-sm bg-accent align-middle"
                />
              )}
            </div>
          )}
        </div>

        {/* Hover-reveal action row: timestamp + copy the whole message.
            Hidden while the message is still streaming. */}
        <div
          className={[
            "mt-1 flex items-center gap-1 px-1 opacity-0 transition-opacity",
            streaming ? "" : "group-hover/msg:opacity-100",
            isUser ? "flex-row-reverse" : "flex-row",
          ].join(" ")}
        >
          <span className="text-[11px] text-ink-faint">{relativeTime(ts)}</span>
          {!isUser && <CopyButton text={content} />}
        </div>
      </div>
    </div>
  );
}

export const Message = memo(MessageBase);
