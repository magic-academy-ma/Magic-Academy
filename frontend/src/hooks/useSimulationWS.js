import { useState, useEffect, useRef } from "react";

const MAX_RETRIES = 5;
const RETRY_DELAY_MS = 3000;
const MAX_EVENT_LOG = 100;

export function useSimulationWS(simulationId, token) {
  const [connected, setConnected] = useState(false);
  const [lastTick, setLastTick] = useState(null);
  const [eventLog, setEventLog] = useState([]);
  const [wsRelationshipDeltas, setWsRelationshipDeltas] = useState([]);
  const retryCount = useRef(0);
  const retryTimeout = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!simulationId || !token) return;

    function connect() {
      const baseUrl = import.meta.env.VITE_API_URL ?? "";
      const wsBase = baseUrl.replace(/^https/, "wss").replace(/^http/, "ws");
      const ws = new WebSocket(
        `${wsBase}/v1/ws/simulations/${simulationId}?token=${encodeURIComponent(token)}`
      );
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retryCount.current = 0;
      };

      ws.onmessage = (event) => {
        let message;
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }
        switch (message.type) {
          case "TICK_UPDATED":
            setLastTick({
              current_tick: message.current_tick,
              current_day: message.current_day,
              status: message.status,
            });
            setWsRelationshipDeltas([]);
            break;
          case "EVENT_CREATED":
            setEventLog((prev) =>
              [
                {
                  id: message.id,
                  description: message.description,
                  involved_agents: message.involved_agents ?? [],
                  tick: message.tick,
                },
                ...prev,
              ].slice(0, MAX_EVENT_LOG)
            );
            break;
          case "RELATIONSHIP_UPDATED":
            setWsRelationshipDeltas((prev) => [...prev, message]);
            break;
          default:
            break;
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (retryCount.current < MAX_RETRIES) {
          retryCount.current += 1;
          retryTimeout.current = setTimeout(connect, RETRY_DELAY_MS);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      clearTimeout(retryTimeout.current);
      const ws = wsRef.current;
      if (ws) {
        ws.onclose = null;
        ws.close();
        wsRef.current = null;
      }
    };
  }, [simulationId, token]);

  return { connected, lastTick, eventLog, wsRelationshipDeltas };
}
