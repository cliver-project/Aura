import { useEffect, useRef, useState } from "react";

import { api, wsUrl } from "@/api/client";
import type { AgentEvent } from "@/api/types";

function mergeEvents(current: AgentEvent[], incoming: AgentEvent[]): AgentEvent[] {
  const seen = new Set(current.map((event) => event.seq));
  const merged = [...current];
  for (const event of incoming) {
    if (event.type === "ping") continue;
    if (event.seq != null && seen.has(event.seq)) continue;
    if (event.seq != null) seen.add(event.seq);
    merged.push(event);
  }
  return merged;
}

/**
 * Replay persisted events, then follow the live WebSocket. If the socket
 * closes before the run is done, poll for the remaining events.
 */
export function useRunEvents(runId: string | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const lastSeq = useRef(0);
  const closed = useRef(false);

  useEffect(() => {
    setEvents([]);
    lastSeq.current = 0;
    closed.current = false;
    if (!runId) return;

    let cancelled = false;
    let socket: WebSocket | null = null;
    let timer: number | null = null;

    const append = (incoming: AgentEvent[]) => {
      if (cancelled) return;
      setEvents((current) => {
        const merged = mergeEvents(current, incoming);
        const last = merged[merged.length - 1];
        if (last?.seq != null) lastSeq.current = last.seq;
        return merged;
      });
    };

    const fetchEvents = async () => {
      try {
        const response = await api.get<AgentEvent[]>(`/agent-runs/${runId}/events`, {
          params: { after_seq: lastSeq.current },
        });
        append(response.data);
      } catch {
        // A transient read failure is retried by the next poll.
      }
    };

    const poll = () => {
      if (timer != null) return;
      timer = window.setInterval(() => {
        void fetchEvents();
      }, 2500);
    };

    void fetchEvents().then(() => {
      if (cancelled) return;
      try {
        socket = new WebSocket(wsUrl(`/api/ws/agent-runs/${runId}`));
        socket.onopen = () => {
          setConnected(true);
          if (timer != null) {
            window.clearInterval(timer);
            timer = null;
          }
        };
        socket.onmessage = (message) => {
          try {
            const event = JSON.parse(message.data as string) as AgentEvent;
            append([event]);
          } catch {
            // Ignore malformed frames.
          }
        };
        socket.onclose = () => {
          setConnected(false);
          if (!cancelled && !closed.current) {
            void fetchEvents();
            poll();
          }
        };
        socket.onerror = () => {
          socket?.close();
        };
      } catch {
        poll();
      }
    });

    return () => {
      cancelled = true;
      closed.current = true;
      if (timer != null) window.clearInterval(timer);
      socket?.close();
    };
  }, [runId]);

  return { events, connected };
}
