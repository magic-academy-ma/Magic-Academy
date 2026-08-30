import { useState, useEffect, useRef } from "react";

// 인증 계약(PR #154): URL query token 금지, 첫 frame은 반드시 AUTH.
// 서버는 인증 실패/소유권 불일치 시 close(1008)로 응답한다.
const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 15000;
const MAX_EVENT_LOG = 100;

export function useSimulationWS(simulationId, token, { onReconnect } = {}) {
  const [connected, setConnected] = useState(false);
  const [lastTick, setLastTick] = useState(null);
  const [eventLog, setEventLog] = useState([]);
  const [wsRelationshipDeltas, setWsRelationshipDeltas] = useState([]);
  // agent_id → { action_type, location } — AGENT_ACTION_UPDATED 수신 시 갱신
  const [agentActions, setAgentActions] = useState(new Map());
  const wsRef = useRef(null);
  const onReconnectRef = useRef(onReconnect);
  onReconnectRef.current = onReconnect;

  useEffect(() => {
    if (!simulationId || !token) return undefined;

    let unmounted = false;
    let reconnectTimer = null;
    let reconnectAttempt = 0;
    let hasConnectedOnce = false;

    function connect() {
      const baseUrl = import.meta.env.VITE_API_URL ?? "";
      const wsBase = baseUrl.replace(/^https/, "wss").replace(/^http/, "ws");
      const ws = new WebSocket(`${wsBase}/v1/ws/simulations/${simulationId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        // 인증은 첫 frame으로만 수행한다 (URL query token 금지).
        ws.send(JSON.stringify({ type: "AUTH", token }));
      };

      ws.onmessage = (event) => {
        let message;
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }

        if (message.type === "AUTHENTICATED") {
          setConnected(true);
          if (hasConnectedOnce) {
            onReconnectRef.current?.();
          }
          hasConnectedOnce = true;
          reconnectAttempt = 0;
          return;
        }

        const data = message.data ?? {};
        switch (message.type) {
          case "TICK_UPDATED":
            setLastTick({
              current_tick: data.tick_number,
              current_day: data.current_day,
            });
            setWsRelationshipDeltas([]);
            break;
          case "EVENT_CREATED":
            setEventLog((prev) => {
              const description = data.title ?? data.description;
              return [
                {
                  id: data.event_id,
                  description,
                  involved_agents: data.participant_agent_ids ?? [],
                  tick: data.tick_number,
                },
                ...prev.filter(
                  (item) => item.id !== data.event_id && item.description !== description
                ),
              ].slice(0, MAX_EVENT_LOG);
            });
            break;
          case "AGENT_ACTION_UPDATED": {
            const { agent_id, action_type, location } = data;
            if (agent_id) {
              setAgentActions((prev) => {
                const next = new Map(prev);
                next.set(agent_id, { action_type, location });
                return next;
              });
            }
            break;
          }
          case "RELATIONSHIP_UPDATED": {
            const changes = data.changes ?? {};
            const deltas = Object.entries(changes).map(([metric, delta]) => ({
              source_agent_id: data.source_agent_id,
              target_agent_id: data.target_agent_id,
              metric,
              delta,
            }));
            setWsRelationshipDeltas((prev) => [...prev, ...deltas]);
            break;
          }
          default:
            break;
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;

        if (unmounted) return;

        reconnectAttempt += 1;
        const delay = Math.min(
          RECONNECT_BASE_DELAY_MS * 2 ** (reconnectAttempt - 1),
          RECONNECT_MAX_DELAY_MS
        );
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer);
      const ws = wsRef.current;
      if (ws) {
        ws.onclose = null;
        ws.close();
        wsRef.current = null;
      }
    };
  }, [simulationId, token]);

  return { connected, lastTick, eventLog, wsRelationshipDeltas, agentActions };
}
