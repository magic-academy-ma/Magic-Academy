// frontend/src/components/SharedBrowser.jsx
//
// 공유 설정 목록·검색·상세·가져오기.
// - 목록/검색은 public 공유만 노출한다(private/unlisted는 서버가 애초에 반환하지 않는다).
// - 상세는 정확한 share_id로 unlisted도 조회 가능하다(서버 접근 제어를 그대로 따른다).
// - 가져오기는 POST /shares/{share_id}/imports (Idempotency-Key 필수, body 없음)만 호출하며,
//   원본 payload를 클라이언트가 다시 제출하지 않는다.

import { useEffect, useState } from "react";
import { getShareDetail, importShare, listShares } from "../api/sharing.js";
import ErrorMessage from "./ErrorMessage";

function newIdempotencyKey() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `import-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function rosterSummary(payload) {
  const agents = payload?.agents ?? [];
  const studentCount = agents.filter((a) => a.role_profile?.profile_type === "student").length;
  const professorCount = agents.filter((a) => a.role_profile?.profile_type === "professor").length;
  return { studentCount, professorCount, organizationCount: payload?.organizations?.length ?? 0 };
}

export default function SharedBrowser({ token, onImported, onClose }) {
  const [query, setQuery] = useState("");
  const [shares, setShares] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  const [confirming, setConfirming] = useState(false);
  const [importKey, setImportKey] = useState(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importError, setImportError] = useState(null);

  async function loadShares(q) {
    setListLoading(true);
    setListError(null);
    try {
      const results = await listShares(token, { q });
      setShares(results ?? []);
    } catch (requestError) {
      setListError(requestError);
    } finally {
      setListLoading(false);
    }
  }

  useEffect(() => {
    loadShares();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSearchSubmit(event) {
    event.preventDefault();
    loadShares(query);
  }

  async function handleSelect(shareId) {
    setSelectedId(shareId);
    setDetail(null);
    setDetailError(null);
    setConfirming(false);
    setImportError(null);
    setDetailLoading(true);
    try {
      const data = await getShareDetail(token, shareId);
      setDetail(data);
    } catch (requestError) {
      setDetailError(requestError);
    } finally {
      setDetailLoading(false);
    }
  }

  function startImport() {
    setImportKey(newIdempotencyKey());
    setImportError(null);
    setConfirming(true);
  }

  async function confirmImport() {
    setImportLoading(true);
    setImportError(null);
    try {
      const simulation = await importShare(token, selectedId, importKey);
      onImported?.(simulation);
    } catch (requestError) {
      setImportError(requestError);
    } finally {
      setImportLoading(false);
    }
  }

  const summary = detail ? rosterSummary(detail.export_payload) : null;

  return (
    <section className="panel shared-browser" aria-labelledby="shared-browser-title">
      <header className="shared-browser-header">
        <h2 id="shared-browser-title">공유 설정 둘러보기</h2>
        {onClose && (
          <button type="button" onClick={onClose}>
            닫기
          </button>
        )}
      </header>

      <form onSubmit={handleSearchSubmit}>
        <label>
          검색
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="제목·설명 검색" />
        </label>
        <button disabled={listLoading}>{listLoading ? "검색 중..." : "검색"}</button>
      </form>

      {listLoading && <p className="message">공유 목록을 불러오는 중...</p>}
      <ErrorMessage error={listError} />
      {!listLoading && !listError && shares.length === 0 && (
        <p className="message">공개된 공유 설정이 없습니다.</p>
      )}

      {!listLoading && !listError && shares.length > 0 && (
        <ul className="shared-list">
          {shares.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={selectedId === item.id ? "shared-item active" : "shared-item"}
                onClick={() => handleSelect(item.id)}
              >
                <b>{item.title || "(제목 없음)"}</b>
                <span className="visibility-badge">{item.visibility}</span>
                {item.description && <p>{item.description}</p>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {selectedId && (
        <div className="shared-detail" aria-live="polite">
          {detailLoading && <p className="message">공유 상세를 불러오는 중...</p>}
          <ErrorMessage error={detailError} />

          {detail && !detailLoading && !detailError && (
            <div>
              <h3>{detail.title || "(제목 없음)"}</h3>
              {detail.description && <p>{detail.description}</p>}
              {summary && (
                <p>
                  Student {summary.studentCount}명 · Professor {summary.professorCount}명 ·
                  Organization {summary.organizationCount}개
                </p>
              )}

              {!confirming && (
                <button type="button" onClick={startImport}>
                  이 설정 가져오기
                </button>
              )}

              {confirming && (
                <div role="alertdialog" aria-labelledby="import-confirm-title" className="import-confirm">
                  <p id="import-confirm-title">
                    이 공유 설정으로 새 Simulation을 만듭니다. 원본 Simulation은 변경되지 않습니다.
                    계속할까요?
                  </p>
                  <button type="button" onClick={confirmImport} disabled={importLoading}>
                    {importLoading ? "가져오는 중..." : "가져오기 확인"}
                  </button>
                  <button type="button" onClick={() => setConfirming(false)} disabled={importLoading}>
                    취소
                  </button>
                </div>
              )}

              <ErrorMessage error={importError} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
