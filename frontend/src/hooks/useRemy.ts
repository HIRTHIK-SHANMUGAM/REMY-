import { useCallback, useEffect, useRef, useState } from "react";

export type Role = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  ts: number;
  streaming?: boolean; // assistant message currently receiving tokens
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

export function useRemy() {
  // Starts empty so the Welcome screen (with suggestion chips) shows on first
  // run; the first user/assistant turn replaces it with the conversation.
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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

      // Placeholder assistant message that tokens stream into.
      const assistantId = uid();
      let started = false;
      const ensureAssistant = () => {
        if (started) return;
        started = true;
        setMessages((prev) => [
          ...prev,
          { id: assistantId, role: "assistant", content: "", ts: Date.now(), streaming: true },
        ]);
      };
      const appendToken = (text: string) => {
        ensureAssistant();
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + text } : m
          )
        );
      };
      const finishAssistant = () => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
        );
      };

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: trimmed }),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
        setBackend("online");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        // Parse the Server-Sent Events stream (events separated by blank line).
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split("\n\n");
          buffer = events.pop() ?? ""; // keep the trailing partial event
          for (const evt of events) {
            const line = evt.split("\n").find((l) => l.startsWith("data:"));
            if (!line) continue;
            let payload: { type: string; text?: string; message?: string };
            try {
              payload = JSON.parse(line.slice(5).trim());
            } catch {
              continue;
            }
            if (payload.type === "token") appendToken(payload.text ?? "");
            else if (payload.type === "error") appendToken(`\n\n_[Error streaming response: ${payload.message ?? "unknown"}]_`);
          }
        }
        finishAssistant();
        // Empty reply (e.g. immediate error before any token) → surface it.
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && m.content === ""
              ? { ...m, content: "(REMY returned an empty response.)" }
              : m
          )
        );
      } catch (err) {
        finishAssistant();
        const aborted = err instanceof DOMException && err.name === "AbortError";
        setBackend(aborted ? "online" : "offline");
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
    setMessages([]);
    try {
      await fetch(`${API_BASE}/api/chat/reset`, { method: "POST" });
    } catch {
      /* non-fatal: server history reset is best-effort */
    }
  }, []);

  return { messages, sendMessage, resetChat, isLoading, backend };
}
