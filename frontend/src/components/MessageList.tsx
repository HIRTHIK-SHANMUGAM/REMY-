import { useEffect, useRef } from "react";
import { Sparkles } from "lucide-react";
import type { ChatMessage } from "../hooks/useRemy";
import { Message } from "./Message";

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
}

function TypingIndicator() {
  return (
    <div className="flex animate-fade-in gap-3">
      <div className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-full bg-accent/15 text-accent">
        <Sparkles size={16} />
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-surface-3 bg-surface-1 px-4 py-3.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 animate-blink rounded-full bg-ink-muted"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </div>
    </div>
  );
}

export function MessageList({ messages, isLoading }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="scroll-thin flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-3xl flex-col px-4 py-6">
        {messages.map((m, i) => {
          const prev = messages[i - 1];
          // Group consecutive same-role, non-system messages under one avatar.
          const grouped =
            !!prev &&
            prev.role === m.role &&
            m.role !== "system" &&
            prev.role !== "system";
          return <Message key={m.id} message={m} grouped={grouped} />;
        })}
        {isLoading && (
          <div className="mt-4">
            <TypingIndicator />
          </div>
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
