import { Moon, RotateCcw, Sun } from "lucide-react";
import { useRemy, type Backend } from "../hooks/useRemy";
import { useTheme } from "../hooks/useTheme";
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
  const { theme, toggle } = useTheme();

  const isEmpty = messages.length === 0 && !isLoading;
  const iconBtn =
    "flex h-8 w-8 items-center justify-center rounded-lg border border-surface-3 text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink";

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
          <div className="flex items-center gap-2 sm:gap-3">
            <StatusDot backend={backend} />
            <button
              onClick={toggle}
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              title={theme === "dark" ? "Light theme" : "Dark theme"}
              className={iconBtn}
            >
              {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            <button
              onClick={resetChat}
              aria-label="New conversation"
              title="New conversation"
              className={iconBtn}
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
