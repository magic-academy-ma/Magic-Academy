// frontend/src/components/SnapshotPanel.jsx
//
// 시점(Tick) 선택 → Snapshot 조회(읽기 전용) → 복원.
//
// ⚠️ 복원(restore)은 백엔드 구현 기준으로 처리한다: 원본 Simulation을
// 제자리에서 갱신하지 않고 새 Simulation(브랜치)을 생성해 반환하므로,
// 복원 성공 시 반환된 새 id로 이동해야 한다. (API 명세 문서상 "제자리 갱신"
// 설명과 다름 — 팀 결정에 따라 백엔드 구현을 기준으로 함)
//
// onRestored(newSimulationId)로 실제 라우팅은 상위(App)에 위임한다.

import { useState } from "react";
import { getSnapshot, restoreSnapshot } from "../api/simulationHistory.js";
import ErrorMessage from "./ErrorMessage";

export default function SnapshotPanel({ token, simulationId, onRestored }) {
  const [tickInput, setTickInput] = useState("");

  const [viewLoading, setViewLoading] = useState(false);
  const [snapshot, setSnapshot] = useState(null);
  const [viewError, setViewError] = useState(null);

  const [confirming, setConfirming] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [restoreDone, setRestoreDone] = useState(false);
  const [restoreError, setRestoreError] = useState(null);

  async function handleView(event) {
    event.preventDefault();
    const tickNumber = Number(tickInput);

    setSnapshot(null);
    setConfirming(false);
    setRestoreDone(false);
    setRestoreError(null);

    if (!Number.isInteger(tickNumber) || tickNumber < 0) {
      setViewError({ status: 400, message: "Tick 번호를 올바르게 입력해 주세요." });
      return;
    }

    setViewLoading(true);
    setViewError(null);
    try {
      const data = await getSnapshot(token, simulationId, tickNumber);
      setSnapshot(data);
    } catch (requestError) {
      setViewError(requestError);
    } finally {
      setViewLoading(false);
    }
  }

  async function handleConfirmRestore() {
    setRestoreLoading(true);
    setRestoreError(null);
    try {
      const result = await restoreSnapshot(
        token,
        simulationId,
        snapshot.snapshot_id ?? snapshot.tick_number
      );
      setRestoreDone(true);
      setConfirming(false);
      // 백엔드가 새 Simulation을 생성하므로, 결과의 id로 이동을 위임한다.
      onRestored?.(result.id);
    } catch (requestError) {
      setRestoreError(requestError);
    } finally {
      setRestoreLoading(false);
    }
  }

  return (
    <section className="panel snapshot-panel" aria-labelledby="snapshot-panel-title">
      <h2 id="snapshot-panel-title">시점 조회·복원</h2>

      <form onSubmit={handleView}>
        <label>
          Tick 번호
          <input
            type="number"
            min="0"
            value={tickInput}
            onChange={(e) => setTickInput(e.target.value)}
          />
        </label>
        <button disabled={viewLoading}>{viewLoading ? "조회 중..." : "조회"}</button>
      </form>

      <ErrorMessage error={viewError} />

      {snapshot && !viewError && (
        <div className="snapshot-result">
          <h3>Tick {snapshot.tick_number} (Day {snapshot.simulation_day})</h3>
          <p className="message">이 화면은 조회 전용이며, 새로운 Tick 실행을 유발하지 않습니다.</p>
          <p>
            Agent {snapshot.agents?.length ?? 0}명 · 관계 {snapshot.relationships?.length ?? 0}건 ·
            Event {snapshot.events?.length ?? 0}건
          </p>

          {!confirming && !restoreDone && (
            <button type="button" onClick={() => setConfirming(true)}>
              이 시점으로 복원
            </button>
          )}

          {confirming && (
            <div role="alertdialog" aria-labelledby="restore-confirm-title" className="restore-confirm">
              <p id="restore-confirm-title">
                이 시점을 기반으로 새 시뮬레이션이 생성됩니다. 계속할까요?
              </p>
              <button type="button" onClick={handleConfirmRestore} disabled={restoreLoading}>
                {restoreLoading ? "복원 중..." : "복원 확인"}
              </button>
              <button type="button" onClick={() => setConfirming(false)} disabled={restoreLoading}>
                취소
              </button>
            </div>
          )}

          {restoreDone && (
            <p className="message" role="status">
              새 시뮬레이션이 생성되었습니다. 이동합니다...
            </p>
          )}

          <ErrorMessage error={restoreError} />
        </div>
      )}
    </section>
  );
}
