// frontend/src/api/simulationHistory.js
//
// 설정 저장·Replay·시점 복원 관련 API 클라이언트.
// 기준: API_명세_및_공통_규약.md v1.6, §3.7~3.13
// 기존 client.js(apiRequest) 컨벤션을 그대로 따른다:
//   - apiRequest(path, { token, method, body, headers })
//   - 성공 시 응답 JSON({data} 또는 {data, meta})을 그대로 반환 → 이 파일에서 .data를 꺼내 돌려줌
//   - 실패 시 이미 status/code/message가 채워진 Error를 throw (별도 에러 클래스 불필요)

import { apiRequest } from "./client.js";

// ---------------------------------------------------------------------------
// 3.11 설정 저장·변경
// ---------------------------------------------------------------------------

/**
 * Draft 상태 Simulation의 초기 파라미터 전체 저장/변경.
 * PUT /simulations/{simulation_id}/parameters
 */
export async function saveDraftConfig(token, simulationId, config) {
  const result = await apiRequest(`/v1/simulations/${simulationId}/parameters`, {
    token,
    method: "PUT",
    body: JSON.stringify(config),
  });
  return result.data ?? result;
}

/**
 * 실행 중(RUNNING/PAUSED) Simulation의 event_frequency, event_impact만 변경.
 * PATCH /simulations/{simulation_id}/parameters
 */
export async function updateRunningConfig(token, simulationId, { eventFrequency, eventImpact }) {
  const result = await apiRequest(`/v1/simulations/${simulationId}/parameters`, {
    token,
    method: "PATCH",
    body: JSON.stringify({
      event_frequency: eventFrequency,
      event_impact: eventImpact,
    }),
  });
  return result.data ?? result;
}

// ---------------------------------------------------------------------------
// 3.9 / 3.10 시점 조회 · 복원
// ---------------------------------------------------------------------------

/**
 * 특정 Tick 시점 상태 조회 (읽기 전용, 부수 효과 없음, 새 Simulation 생성 안 함).
 * GET /simulations/{simulation_id}/snapshots/{tick_number}
 */
export async function getSnapshot(token, simulationId, tickNumber) {
  const result = await apiRequest(
    `/v1/simulations/${simulationId}/snapshots/${tickNumber}`,
    { token }
  );
  return result.data ?? result;
}

/**
 * 저장본 복원.
 *
 * ⚠️ 백엔드 구현(SimulationSnapshotService.restore_as_branch) 기준:
 * 원본 Simulation을 제자리에서 갱신하지 않고, origin_simulation_id /
 * origin_snapshot_id로 원본을 참조하는 새 Simulation을 생성해 반환한다.
 * 호출 측(컴포넌트)에서는 응답의 id를 원본과 동일하다고 가정하지 말고,
 * 반환된 새 id로 이동(navigate)해야 한다.
 *
 * POST /simulations/{simulation_id}/restore
 */
export async function restoreSnapshot(token, simulationId, snapshotId) {
  const result = await apiRequest(`/v1/simulations/${simulationId}/restore`, {
    token,
    method: "POST",
    body: JSON.stringify({ snapshot_id: snapshotId }),
  });
  return result.data ?? result;
}

// ---------------------------------------------------------------------------
// 3.12 / 3.13 Replay
// ---------------------------------------------------------------------------

/**
 * 재생 가능한 Tick 목록 조회.
 * GET /simulations/{simulation_id}/replay
 */
export async function getReplayList(token, simulationId, { cursor, limit = 20 } = {}) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);

  const result = await apiRequest(
    `/v1/simulations/${simulationId}/replay?${params.toString()}`,
    { token }
  );
  return { items: result.data ?? [], meta: result.meta };
}

/**
 * 특정 Tick의 Replay 데이터(Event, Agent Snapshot, Relationship Delta) 조회.
 * GET /simulations/{simulation_id}/replay/{tick_number}
 */
export async function getReplayTick(token, simulationId, tickNumber) {
  const result = await apiRequest(
    `/v1/simulations/${simulationId}/replay/${tickNumber}`,
    { token }
  );
  return result.data ?? result;
}
