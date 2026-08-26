// frontend/src/components/ReplayPanel.jsx
//
// Replay 진입 + 실행 기록(tick) 목록 선택 + 선택한 tick 상세 조회.
// 조회만 하며 부수 효과 없음(§3.12, §3.13).

import { useEffect, useState } from "react";
import { getReplayList, getReplayTick } from "../api/simulationHistory.js";
import ErrorMessage from "./ErrorMessage";

export default function ReplayPanel({ token, simulationId }) {
  const [ticks, setTicks] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);

  const [selectedTick, setSelectedTick] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadList() {
      setListLoading(true);
      setListError(null);
      try {
        const { items } = await getReplayList(token, simulationId);
        if (cancelled) return;
        setTicks(items ?? []);
      } catch (requestError) {
        if (cancelled) return;
        setListError(requestError);
      } finally {
        if (!cancelled) setListLoading(false);
      }
    }

    loadList();
    return () => {
      cancelled = true;
    };
  }, [token, simulationId]);

  async function handleSelectTick(tickNumber) {
    setSelectedTick(tickNumber);
    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    try {
      const data = await getReplayTick(token, simulationId, tickNumber);
      setDetail(data);
    } catch (requestError) {
      setDetailError(requestError);
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <section className="panel replay-panel" aria-labelledby="replay-panel-title">
      <h2 id="replay-panel-title">Replay</h2>

      {listLoading && <p className="message">실행 기록을 불러오는 중...</p>}
      {listError && <ErrorMessage error={listError} />}
      {!listLoading && !listError && ticks.length === 0 && (
        <p className="message">재생 가능한 실행 기록이 없습니다.</p>
      )}

      {!listLoading && !listError && ticks.length > 0 && (
        <ul className="replay-tick-list">
          {ticks.map((tick) => (
            <li key={tick.tick_number}>
              <button
                type="button"
                className={selectedTick === tick.tick_number ? "tick active" : "tick"}
                onClick={() => handleSelectTick(tick.tick_number)}
              >
                Day {tick.simulation_day} · Tick {tick.tick_number}
              </button>
            </li>
          ))}
        </ul>
      )}

      {selectedTick !== null && (
        <div className="replay-detail" aria-live="polite">
          {detailLoading && <p className="message">Tick {selectedTick} 데이터를 불러오는 중...</p>}
          {detailError && <ErrorMessage error={detailError} />}

          {detail && !detailLoading && !detailError && (
            <div>
              <h3>Tick {detail.tick_number} (Day {detail.simulation_day})</h3>

              <h4>Events</h4>
              {detail.events?.length ? (
                <ul>
                  {detail.events.map((event) => (
                    <li key={event.id}>{event.title} ({event.event_type})</li>
                  ))}
                </ul>
              ) : (
                <p className="message">이 Tick에 발생한 Event가 없습니다.</p>
              )}

              <h4>Agent Snapshots</h4>
              {detail.agent_snapshots?.length ? (
                <ul>
                  {detail.agent_snapshots.map((snap) => (
                    <li key={snap.agent_id}>
                      {snap.agent_id}: {snap.current_action ?? "-"} (mood {snap.mood})
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="message">Agent 상태 데이터가 없습니다.</p>
              )}

              <h4>Relationship Deltas</h4>
              {detail.relationship_deltas?.length ? (
                <ul>
                  {detail.relationship_deltas.map((delta) => (
                    <li key={delta.relationship_id}>
                      {delta.source_agent_id} → {delta.target_agent_id}: affection{" "}
                      {delta.affection_delta >= 0 ? "+" : ""}
                      {delta.affection_delta}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="message">관계 변화가 없습니다.</p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
