// frontend/src/components/SnapshotPanel.jsx
//
// 시점(Tick) 선택 → Snapshot 조회(읽기 전용) → 복원.
//
// 복원(restore)은 백엔드 구현(SimulationSnapshotService.restore_snapshot) 기준으로
// 처리한다: 새 Simulation을 생성하지 않고, 선택한 시점의 저장된 payload를
// 읽기 전용으로 반환한다. 새 Simulation으로 이동하지 않고, 반환된 payload를
// 그대로 이 화면에 표시한다. Runtime/LLM/Tick은 다시 실행되지 않는다.

import { useState } from "react";
import { getSnapshot, restoreSnapshot } from "../api/simulationHistory.js";
import ErrorMessage from "./ErrorMessage";

export default function SnapshotPanel({ token, simulationId }) {
  const [tickInput, setTickInput] = useState("");

  const [viewLoading, setViewLoading] = useState(false);
  const [snapshot, setSnapshot] = useState(null);
  const [viewError, setViewError] = useState(null);

  const [confirming, setConfirming] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [restoredPayload, setRestoredPayload] = useState(null);
  const [restoreError, setRestoreError] = useState(null);

  async function handleView(event) {
    event.preventDefault();
    const tickNumber = Number(tickInput);

    setSnapshot(null);
    setConfirming(false);
    setRestoredPayload(null);
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
      // 새 Simulation을 생성하지 않는다 — 반환된 payload를 그대로 표시한다.
      setRestoredPayload(result);
      setConfirming(false);
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

          {!confirming && !restoredPayload && (
            <button type="button" onClick={() => setConfirming(true)}>
              이 시점으로 복원
            </button>
          )}

          {confirming && (
            <div role="alertdialog" aria-labelledby="restore-confirm-title" className="restore-confirm">
              <p id="restore-confirm-title">
                이 시점의 저장 상태를 복원합니다. 계속할까요?
              </p>
              <button type="button" onClick={handleConfirmRestore} disabled={restoreLoading}>
                {restoreLoading ? "복원 중..." : "복원 확인"}
              </button>
              <button type="button" onClick={() => setConfirming(false)} disabled={restoreLoading}>
                취소
              </button>
            </div>
          )}

          {restoredPayload && (
            <p className="message" role="status">
              선택한 시점(Tick {snapshot.tick_number})의 저장 상태가 복원되었습니다.
            </p>
          )}

          <ErrorMessage error={restoreError} />
        </div>
      )}
    </section>
  );
}
