// frontend/src/components/SettingsPanel.jsx
//
// 설정 저장·변경 화면.
// ready 상태 (초기 설정 가능 상태) → saveDraftConfig (PUT, 전체 파라미터)
// RUNNING/PAUSED 상태 → updateRunningConfig (PATCH, event_frequency/impact만)
//
// Magic Layer 파라미터(빈도·영향도·ON/OFF)는 실행 전(ready)에만 변경할 수 있고,
// 실행이 시작되면 읽기 전용이다. 프론트의 disabled 처리는 UX용이며 실제 변경
// 방지는 Backend(PR2 스펙 §5)에서 보장한다.
//
// App.jsx 컨벤션에 맞춰 token은 상위(App)에서 auth.access_token으로 전달받는다.

import { useState } from "react";
import { saveDraftConfig, updateRunningConfig } from "../api/simulationHistory.js";
import ErrorMessage from "./ErrorMessage";

const LEVELS = ["low", "medium", "high"];

export default function SettingsPanel({ token, simulationId, simulationStatus }) {
  const status = (simulationStatus || "").toLowerCase();
  const isReady = status === "ready";
  const isRunningOrPaused = status === "running" || status === "paused";

  const [eventFrequency, setEventFrequency] = useState("medium");
  const [eventImpact, setEventImpact] = useState("medium");
  const [magicLayerFrequency, setMagicLayerFrequency] = useState("medium");
  const [magicLayerImpact, setMagicLayerImpact] = useState("medium");
  const [magicEnabled, setMagicEnabled] = useState(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [savedAt, setSavedAt] = useState(null);

  // 실행 후 Magic 입력은 읽기 전용 (Backend 잠금과 일치).
  const magicLocked = !isReady;

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSavedAt(null);

    try {
      if (isReady) {
        const result = await saveDraftConfig(token, simulationId, {
          event_frequency: eventFrequency,
          event_impact: eventImpact,
          magic_layer_frequency: magicLayerFrequency,
          magic_layer_impact: magicLayerImpact,
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

  const canSubmit = isReady || isRunningOrPaused;

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

        <fieldset className="magic-layer-settings">
          <legend>Magic Layer {magicLocked && <span aria-label="잠김">🔒</span>}</legend>

          <label>
            Magic 빈도
            <select
              value={magicLayerFrequency}
              onChange={(e) => setMagicLayerFrequency(e.target.value)}
              disabled={magicLocked}
            >
              {LEVELS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>

          <label>
            Magic 영향도
            <select
              value={magicLayerImpact}
              onChange={(e) => setMagicLayerImpact(e.target.value)}
              disabled={magicLocked}
            >
              {LEVELS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>

          <label>
            <input
              type="checkbox"
              checked={magicEnabled}
              onChange={(e) => setMagicEnabled(e.target.checked)}
              disabled={magicLocked}
            />
            Magic Layer 활성화
          </label>

          {magicLocked && (
            <p className="message" role="status">
              실행이 시작된 시뮬레이션의 Magic 설정은 변경할 수 없습니다.
            </p>
          )}
        </fieldset>

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
