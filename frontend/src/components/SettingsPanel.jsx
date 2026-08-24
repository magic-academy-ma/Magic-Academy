// frontend/src/components/SettingsPanel.jsx
//
// 설정 저장·변경 화면.
// Draft 상태 → saveDraftConfig (PUT, 전체 파라미터)
// RUNNING/PAUSED 상태 → updateRunningConfig (PATCH, event_frequency/impact만)
//
// App.jsx 컨벤션에 맞춰 token은 상위(App)에서 auth.access_token으로 전달받는다.

import { useState } from "react";
import { saveDraftConfig, updateRunningConfig } from "../api/simulationHistory.js";
import ErrorMessage from "./ErrorMessage";

const LEVELS = ["low", "medium", "high"];

export default function SettingsPanel({ token, simulationId, simulationStatus }) {
  const status = (simulationStatus || "").toLowerCase();
  const isDraft = status === "draft";
  const isRunningOrPaused = status === "running" || status === "paused";

  const [eventFrequency, setEventFrequency] = useState("medium");
  const [eventImpact, setEventImpact] = useState("medium");
  const [magicEnabled, setMagicEnabled] = useState(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [savedAt, setSavedAt] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSavedAt(null);

    try {
      if (isDraft) {
        const result = await saveDraftConfig(token, simulationId, {
          event_frequency: eventFrequency,
          event_impact: eventImpact,
          magic_enabled: magicEnabled,
        });
        setSavedAt(result?.changed_at);
      } else if (isRunningOrPaused) {
        const result = await updateRunningConfig(token, simulationId, {
          eventFrequency,
          eventImpact,
        });
        setSavedAt(result?.changed_at);
      }
    } catch (requestError) {
      setError(requestError);
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = isDraft || isRunningOrPaused;

  return (
    <section className="panel settings-panel" aria-labelledby="settings-panel-title">
      <h2 id="settings-panel-title">설정 저장·변경</h2>

      {!canSubmit && (
        <p className="message" role="status">
          이 시뮬레이션은 현재 상태({simulationStatus})에서 설정을 변경할 수 없습니다.
        </p>
      )}

      <form onSubmit={handleSubmit}>
        <label>
          이벤트 빈도
          <select value={eventFrequency} onChange={(e) => setEventFrequency(e.target.value)}>
            {LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>

        <label>
          이벤트 영향도
          <select value={eventImpact} onChange={(e) => setEventImpact(e.target.value)}>
            {LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>

        {isDraft && (
          <label>
            <input
              type="checkbox"
              checked={magicEnabled}
              onChange={(e) => setMagicEnabled(e.target.checked)}
            />
            Magic Layer 활성화
          </label>
        )}

        <button disabled={loading || !canSubmit}>
          {loading ? "저장 중..." : "설정 저장"}
        </button>
      </form>

      {savedAt && !error && (
        <p className="message" role="status">
          설정이 저장되었습니다. ({savedAt})
        </p>
      )}

      <ErrorMessage error={error} />
    </section>
  );
}
