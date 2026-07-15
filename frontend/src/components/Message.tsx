import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Sparkles } from "lucide-react";
import type { ChatMessage } from "../hooks/useRemy";

function MessageBase({
  message,
  grouped = false,
}: {
  message: ChatMessage;
  grouped?: boolean;
}) {
  const { role, content } = message;

  if (role === "system") {
    return (
      <div className="flex justify-center animate-fade-in">
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-300">
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
        "flex animate-fade-in gap-3",
        isUser ? "justify-end" : "justify-start",
        grouped ? "mt-1" : "mt-4", // tighter spacing within a run
      ].join(" ")}
    >
      {!isUser &&
        (grouped ? (
          // keep bubbles aligned under the avatar without repeating it
          <div className="w-8 flex-none" aria-hidden />
        ) : (
          <div className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-full bg-gradient-to-br from-accent-from to-accent-to text-white shadow-bubble">
            <Sparkles size={16} />
          </div>
        ))}
      <div
        className={[
          "max-w-[85%] px-4 py-2.5 text-[14.5px] leading-relaxed shadow-bubble sm:max-w-[75%]",
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
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

export const Message = memo(MessageBase);
