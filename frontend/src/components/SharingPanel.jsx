// frontend/src/components/SharingPanel.jsx
//
// 현재 Simulation 설정 공유 생성·취소.
// status=ready(시작 전)인 Simulation만 공유할 수 있다(Slice 7 계약).
// 서버가 공유 시점의 불변 export payload를 직접 조립하므로 이 화면은
// visibility/title/description만 입력받는다.

import { useState } from "react";
import { cancelShare, createShare } from "../api/sharing.js";
import ErrorMessage from "./ErrorMessage";

export default function SharingPanel({ token, simulationId, simulationStatus }) {
  const isReady = (simulationStatus || "").toLowerCase() === "ready";

  const [visibility, setVisibility] = useState("private");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [share, setShare] = useState(null);

  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelError, setCancelError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await createShare(token, simulationId, { visibility, title, description });
      setShare(result);
      setCancelError(null);
    } catch (requestError) {
      setError(requestError);
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel() {
    setCancelLoading(true);
    setCancelError(null);
    try {
      await cancelShare(token, share.id);
      setShare(null);
    } catch (requestError) {
      setCancelError(requestError);
    } finally {
      setCancelLoading(false);
    }
  }

  return (
    <section className="panel sharing-panel" aria-labelledby="sharing-panel-title">
      <h2 id="sharing-panel-title">설정 공유</h2>

      {!isReady && (
        <p className="message" role="status">
          이 Simulation은 현재 상태({simulationStatus})에서 공유할 수 없습니다. 시작 전(ready)
          상태의 Simulation만 공유할 수 있습니다.
        </p>
      )}

      {isReady && !share && (
        <form onSubmit={handleSubmit}>
          <label>
            공개 범위
            <select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
              <option value="private">private (나만 보기)</option>
              <option value="unlisted">unlisted (링크로만 접근)</option>
              <option value="public">public (검색·목록 노출)</option>
            </select>
          </label>
          <label>
            제목
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          </label>
          <label>
            설명
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={2000}
            />
          </label>
          <button disabled={loading}>{loading ? "공유하는 중..." : "공유하기"}</button>
        </form>
      )}

      <ErrorMessage error={error} />

      {share && (
        <div className="share-result" role="status">
          <p className="message">
            설정이 공유되었습니다. ({share.visibility})
          </p>
          <dl>
            <dt>공유 ID</dt>
            <dd>{share.id}</dd>
          </dl>
          <button type="button" onClick={handleCancel} disabled={cancelLoading}>
            {cancelLoading ? "취소하는 중..." : "공유 취소"}
          </button>
          <ErrorMessage error={cancelError} />
        </div>
      )}
    </section>
  );
}
