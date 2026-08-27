// frontend/src/api/sharing.js
//
// Slice 7 설정 공유·가져오기 API 클라이언트.
// 기준: docs/04-feature-specs/slice-7-config-sharing-import-deployment.md
// 기존 client.js(apiRequest) 컨벤션을 그대로 따른다:
//   - apiRequest(path, { token, method, body, headers })
//   - 성공 응답 본문을 그대로 반환 (이 API는 {data} 래핑 없이 리소스를 직접 반환한다)
//   - 실패 시 이미 status/code/message가 채워진 Error를 throw

import { apiRequest } from "./client.js";

/**
 * 현재 Simulation을 공유한다. status=ready인 시작 전 Simulation만 가능하며
 * 서버가 공유 시점의 불변 export payload(slice7-share-v1)를 직접 조립한다 —
 * 클라이언트는 payload를 제출하지 않는다.
 * POST /simulations/{simulation_id}/shares
 */
export async function createShare(token, simulationId, { visibility, title = "", description = null }) {
  return apiRequest(`/v1/simulations/${simulationId}/shares`, {
    token,
    method: "POST",
    body: JSON.stringify({ visibility, title, description }),
  });
}

/**
 * 공유를 취소한다(soft delete). 이후 외부 상세 조회·가져오기는 404가 된다.
 * DELETE /shares/{share_id}
 */
export async function cancelShare(token, shareId) {
  await apiRequest(`/v1/shares/${shareId}`, { token, method: "DELETE" });
}

/**
 * 공개(public) 공유 목록/검색. 인증 없이도 조회 가능하다.
 * GET /shares
 */
export async function listShares(token, { q, limit = 20, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return apiRequest(`/v1/shares?${params.toString()}`, { token });
}

/**
 * 공유 상세 조회. public/unlisted는 누구나(정확한 id 필요), private는 소유자만.
 * GET /shares/{share_id}
 */
export async function getShareDetail(token, shareId) {
  return apiRequest(`/v1/shares/${shareId}`, { token });
}

/**
 * 공유를 가져와 요청자 소유의 새 Simulation을 생성한다. body는 없으며
 * Idempotency-Key header가 필수다. 같은 key로 같은 공유를 다시 요청하면
 * 새 Simulation을 만들지 않고 기존 결과를 반환한다.
 * POST /shares/{share_id}/imports
 */
export async function importShare(token, shareId, idempotencyKey) {
  return apiRequest(`/v1/shares/${shareId}/imports`, {
    token,
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}
