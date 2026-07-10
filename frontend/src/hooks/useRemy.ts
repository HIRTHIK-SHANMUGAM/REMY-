import { useCallback, useEffect, useRef, useState } from "react";

export type Role = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  ts: number;
}

export type Backend = "online" | "offline" | "checking";

// API base resolution:
//  - Served over http/https (browser, or the backend serving this bundle, or
//    the Vite dev proxy): use same-origin ("") so relative paths just work
//    and mobile access over the LAN hits the right host.
//  - Bundled in the Tauri app (tauri:// custom protocol): the UI is loaded
//    from local assets, so point at the backend explicitly on localhost.
const API_BASE = window.location.protocol.startsWith("http")
  ? ""
  : "http://127.0.0.1:8377";

const uid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

const GREETING: ChatMessage = {
  id: "greeting",
  role: "assistant",
  content:
    "I'm **REMY** — online and listening. Ask me anything, or tell me what you need done.",
  ts: Date.now(),
};

export function useRemy() {
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [isLoading, setIsLoading] = useState(false);
  const [backend, setBackend] = useState<Backend>("checking");
  const abortRef = useRef<AbortController | null>(null);

  // Health polling: detect if the backend dies while the app is open.
  useEffect(() => {
    let alive = true;
    const ping = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`, {
          method: "GET",
          signal: AbortSignal.timeout(4000),
        });
        if (alive) setBackend(res.ok ? "online" : "offline");
      } catch {
        if (alive) setBackend("offline");
      }
    };
    ping();
    const t = setInterval(ping, 8000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "user", content: trimmed, ts: Date.now() },
      ]);
      setIsLoading(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed }),
          signal: controller.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const reply =
          data.reply ?? data.response ?? "(REMY returned an empty response.)";
        setBackend("online");
        setMessages((prev) => [
          ...prev,
          { id: uid(), role: "assistant", content: String(reply), ts: Date.now() },
        ]);
      } catch (err) {
        const aborted = err instanceof DOMException && err.name === "AbortError";
        setBackend("offline");
        setMessages((prev) => [
          ...prev,
          {
            id: uid(),
            role: "system",
            content: aborted
              ? "Request cancelled."
              : "REMY is offline — check that the backend is running on port 8377.",
            ts: Date.now(),
          },
        ]);
      } finally {
        setIsLoading(false);
        abortRef.current = null;
      }
    },
    [isLoading]
  );

  const resetChat = useCallback(async () => {
    abortRef.current?.abort();
    setMessages([GREETING]);
    try {
      await fetch(`${API_BASE}/api/chat/reset`, { method: "POST" });
    } catch {
      /* non-fatal: server history reset is best-effort */
    }
  }, []);

  return { messages, sendMessage, resetChat, isLoading, backend };
}
