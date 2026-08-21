import { useEffect, useRef, useState } from "react";

// API 명세 §14 + Tick Engine 스펙(§1, §6) 기준 — Agent 상태 push는 없어 TICK_UPDATED로 대체
const RECONNECT_BASE_DELAY = 1000; // ms
const RECONNECT_MAX_DELAY = 15000; // ms

export function useSimulationSocket({
  wsUrl,
  onAgentAction,
  onEventCreated,
  onRelationshipUpdated,
  onTickUpdated,
  onReconnect,
}) {
  const [connected, setConnected] = useState(false);
  const [tick, setTick] = useState(null); // { simulation_id, current_day, tick_number }
  const [simulationStatus, setSimulationStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [relationshipUpdates, setRelationshipUpdates] = useState([]);

  const onAgentActionRef = useRef(onAgentAction);
  onAgentActionRef.current = onAgentAction;
  const onEventCreatedRef = useRef(onEventCreated);
  onEventCreatedRef.current = onEventCreated;
  const onRelationshipUpdatedRef = useRef(onRelationshipUpdated);
  onRelationshipUpdatedRef.current = onRelationshipUpdated;
  const onTickUpdatedRef = useRef(onTickUpdated);
  onTickUpdatedRef.current = onTickUpdated;
  const onReconnectRef = useRef(onReconnect);
  onReconnectRef.current = onReconnect;

  useEffect(() => {
    if (!wsUrl) {
      setConnected(false);
      return undefined;
    }

    let unmounted = false;
    let ws = null;
    let reconnectTimer = null;
    let reconnectAttempt = 0;
    let hasConnectedOnce = false;
    let lastTickNumber = null;
    const seenEventIds = new Set();

    function handleMessage(raw) {
      let message;
      try {
        message = JSON.parse(raw);
      } catch (err) {
        console.error("[useSimulationSocket] payload 파싱 실패", err);
        return;
      }

      switch (message.type) {
        case "TICK_UPDATED":
          setTick(message.data);
          // 같은 tick_number 재전송(Outbox 재시도)은 중복 트리거하지 않음
          if (message.data?.tick_number !== lastTickNumber) {
            lastTickNumber = message.data?.tick_number;
            onTickUpdatedRef.current?.(message.data);
          }
          break;
        case "AGENT_ACTION_UPDATED":
          onAgentActionRef.current?.(message.data);
          break;
        case "EVENT_CREATED":
          // event_id 기준 중복 제거 (§6: Outbox 재전송 대비)
          if (message.data?.event_id && seenEventIds.has(message.data.event_id)) {
            break;
          }
          if (message.data?.event_id) seenEventIds.add(message.data.event_id);
          setEvents((prev) => [...prev, message.data]);
          onEventCreatedRef.current?.(message.data);
          break;
        case "RELATIONSHIP_UPDATED":
          // ⚠️ 이 메시지엔 중복 제거용 식별자가 없음 (§14.5) — 확인 필요
          setRelationshipUpdates((prev) => [...prev, message.data]);
          onRelationshipUpdatedRef.current?.(message.data);
          break;
        case "SIMULATION_STATUS_UPDATED":
          setSimulationStatus(message.data);
          break;
        default:
          console.warn("[useSimulationSocket] 알 수 없는 메시지 타입", message.type);
      }
    }

    function connect() {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnected(true);
        if (hasConnectedOnce && onReconnectRef.current) {
          onReconnectRef.current();
        }
        hasConnectedOnce = true;
        reconnectAttempt = 0;
      };

      ws.onmessage = (event) => handleMessage(event.data);

      ws.onclose = () => {
        setConnected(false);
        if (unmounted) return;
        reconnectAttempt += 1;
        const delay = Math.min(
          RECONNECT_BASE_DELAY * 2 ** (reconnectAttempt - 1),
          RECONNECT_MAX_DELAY
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
      ws?.close();
    };
  }, [wsUrl]);

  return { connected, tick, simulationStatus, events, relationshipUpdates };
}
