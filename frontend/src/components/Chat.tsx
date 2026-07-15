import { RotateCcw } from "lucide-react";
import { useRemy, type Backend } from "../hooks/useRemy";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";
import { Welcome } from "./Welcome";

function StatusDot({ backend }: { backend: Backend }) {
  const map: Record<Backend, { color: string; label: string }> = {
    online: { color: "bg-emerald-400", label: "Online" },
    offline: { color: "bg-red-400", label: "Offline" },
    checking: { color: "bg-amber-400", label: "Connecting" },
  };
  const { color, label } = map[backend];
  return (
    <span className="flex items-center gap-1.5 text-xs text-ink-muted">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}

export function Chat() {
  const { messages, sendMessage, resetChat, isLoading, backend } = useRemy();

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex h-full flex-col bg-surface-0">
      <header className="flex items-center justify-between border-b border-surface-3 bg-surface-1/60 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent-from to-accent-to font-bold text-white shadow-bubble">
              R
            </div>
            <div className="leading-tight">
              <h1 className="text-sm font-semibold tracking-wide text-ink">REMY</h1>
              <p className="text-[11px] text-ink-faint">Autonomous Desktop Agent</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusDot backend={backend} />
            <button
              onClick={resetChat}
              aria-label="New conversation"
              title="New conversation"
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-surface-3 text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
            >
              <RotateCcw size={15} />
            </button>
          </div>
        </div>
      </header>

      {isEmpty ? (
        <Welcome onPick={sendMessage} />
      ) : (
        <MessageList messages={messages} isLoading={isLoading} />
      )}
      <MessageInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
