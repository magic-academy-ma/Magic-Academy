import { useCallback, useEffect, useRef, useState } from "react";
import {
  getUserPersonaConfig,
  getUserPersona,
  setUserPersona,
  startSimulation,
} from "../api/client.js";

const BIG_FIVE_TRAITS = [
  { key: "openness", label: "개방성" },
  { key: "conscientiousness", label: "성실성" },
  { key: "extraversion", label: "외향성" },
  { key: "agreeableness", label: "우호성" },
  { key: "emotional_stability", label: "정서 안정성" },
];

function defaultsFromRule(mbtiRule) {
  return BIG_FIVE_TRAITS.reduce((acc, trait) => {
    acc[trait.key] = mbtiRule[trait.key].default;
    return acc;
  }, {});
}

export default function UserPersonaSetup({
  simulationId,
  students,
  token,
  refreshKey,
  onSaved,
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [config, setConfig] = useState(null);
  const [locked, setLocked] = useState(false);
  const [personaSaved, setPersonaSaved] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [mbtiType, setMbtiType] = useState("");
  const [bigFive, setBigFive] = useState(null);

  // App.jsx가 onSaved로 인라인 함수를 넘기므로,
  // effect의 의존성에는 포함하지 않고 최신 함수만 ref로 참조한다.
  const onSavedRef = useRef(onSaved);

  useEffect(() => {
    onSavedRef.current = onSaved;
  }, [onSaved]);

  // 서버에 저장된 Persona 상태를 조회해 폼/잠금 상태에 반영한다.
  // 최초 로딩과, Simulation 시작 시 409 충돌 발생 후 재동기화에 모두 쓰인다.
  const loadPersona = useCallback(
    async ({ isCancelled } = {}) => {
      const cancelled = isCancelled ?? (() => false);

      try {
        const persona = await getUserPersona(simulationId, { token });

        if (cancelled()) return persona;

        setSelectedAgentId(persona.agent_id);
        setMbtiType(persona.mbti_type);

        setBigFive(
          BIG_FIVE_TRAITS.reduce((acc, trait) => {
            acc[trait.key] = persona[trait.key];
            return acc;
          }, {})
        );

        setPersonaSaved(true);
        setLocked(Boolean(persona.locked));

        // 이미 설정된 Persona를 발견한 경우 상위 컴포넌트에도 알린다.
        onSavedRef.current?.(persona);

        return persona;
      } catch (personaError) {
        if (personaError.status !== 404) {
          throw personaError;
        }

        // 404 = 아직 User Persona가 설정되지 않음.
        if (!cancelled()) {
          setSelectedAgentId("");
          setMbtiType("");
          setBigFive(null);
          setPersonaSaved(false);
          setLocked(false);
        }

        return null;
      }
    },
    [simulationId, token]
  );

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");

      try {
        const configResult = await getUserPersonaConfig(simulationId, {
          token,
        });

        if (cancelled) return;

        setConfig(configResult);

        await loadPersona({ isCancelled: () => cancelled });
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError.message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [simulationId, token, refreshKey, loadPersona]);

  function selectMbti(nextMbti) {
    setMbtiType(nextMbti);
    setPersonaSaved(false);
    if (!nextMbti || !config) {
      setBigFive(null);
      return;
    }

    setBigFive(defaultsFromRule(config.mbti_rules[nextMbti]));
  }

  function updateTrait(key, delta) {
    if (!mbtiType || !config) return;

    const rule = config.mbti_rules[mbtiType][key];

    setBigFive((prev) => {
      const next = Math.min(
        rule.max,
        Math.max(rule.min, prev[key] + delta)
      );

      return { ...prev, [key]: next };
    });
    setPersonaSaved(false);
  }

  // Persona 저장만 수행한다. Simulation 시작은 별도 액션(handleStart)에서 담당한다.
  async function savePersona() {
    setSaving(true);
    setError("");

    try {
      const result = await setUserPersona(
        simulationId,
        {
          agent_id: selectedAgentId,
          mbti_type: mbtiType,
          personality_rule_version: config.rule_version,
          ...bigFive,
        },
        { token }
      );

      setPersonaSaved(true);
      onSavedRef.current?.(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  // 저장된 Persona를 기준으로 Simulation을 시작하고, 성공 시에만 Persona를 잠근다.
  async function handleStart() {
    setStarting(true);
    setError("");

    try {
      await startSimulation(simulationId, { token });
      setLocked(true);
    } catch (requestError) {
      if (requestError.status === 409) {
        // 이미 다른 경로로 Simulation이 시작된 상태 — 서버 상태로 다시 동기화한다.
        setError(
          requestError.message || "Simulation이 이미 시작되어 있습니다."
        );

        try {
          await loadPersona();
        } catch (_syncError) {
          // 동기화에 실패해도 위 충돌 메시지는 그대로 유지한다.
        }
      } else {
        setError(requestError.message);
      }
    } finally {
      setStarting(false);
    }
  }

  if (loading) {
    return (
      <div className="panel persona-setup">
        <h2>User Persona</h2>
        <p className="message">Persona 설정을 불러오는 중...</p>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="panel persona-setup">
        <h2>User Persona</h2>

        {error && (
          <p className="message error" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }

  const mbtiOptions = Object.keys(config.mbti_rules);

  const canSave =
    Boolean(selectedAgentId && mbtiType && bigFive) && !saving && !locked;

  const canStart = personaSaved && !locked && !starting && !saving;

  return (
    <div className="panel persona-setup">
      <h2>User Persona</h2>

      {locked && (
        <p className="message" role="status">
          Simulation이 시작되어 Persona 설정이 잠겼습니다.
        </p>
      )}

      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}

      <fieldset disabled={locked || saving || starting}>
        <legend>Student 선택</legend>

        <div
          className="persona-student-list"
          role="radiogroup"
          aria-label="User Persona Student 선택"
        >
          {students.map((student) => (
            <label
              key={student.id}
              className={
                selectedAgentId === student.id
                  ? "persona-student active"
                  : "persona-student"
              }
            >
              <input
                type="radio"
                name="persona-student"
                value={student.id}
                checked={selectedAgentId === student.id}
                onChange={() => {
                  setSelectedAgentId(student.id);
                  setPersonaSaved(false);
                }}
              />
              {student.name}
            </label>
          ))}
        </div>

        <label className="persona-mbti">
          MBTI preset

          <select
            value={mbtiType}
            onChange={(e) => selectMbti(e.target.value)}
          >
            <option value="">선택 안 함</option>

            {mbtiOptions.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>

        {!mbtiType && (
          <p className="message">
            MBTI를 먼저 선택하세요.
          </p>
        )}

        <div className="persona-big-five">
          {BIG_FIVE_TRAITS.map(({ key, label }) => {
            const rule = mbtiType
              ? config.mbti_rules[mbtiType][key]
              : null;

            const value = bigFive?.[key];

            return (
              <div className="big-five-row" key={key}>
                <span>{label}</span>

                <button
                  type="button"
                  aria-label={`${label} 감소`}
                  onClick={() => updateTrait(key, -config.step)}
                  disabled={!rule || value <= rule.min}
                >
                  -{config.step}
                </button>

                <output>{rule ? value : "-"}</output>

                <button
                  type="button"
                  aria-label={`${label} 증가`}
                  onClick={() => updateTrait(key, config.step)}
                  disabled={!rule || value >= rule.max}
                >
                  +{config.step}
                </button>
              </div>
            );
          })}
        </div>
      </fieldset>

      {!locked && (
        <div className="persona-actions">
          <button type="button" onClick={savePersona} disabled={!canSave}>
            {saving ? "저장 중..." : "Persona 저장"}
          </button>

          <button
            type="button"
            onClick={handleStart}
            disabled={!canStart}
            title={
              !personaSaved
                ? "먼저 Persona를 저장해야 Simulation을 시작할 수 있습니다."
                : undefined
            }
          >
            {starting ? "시작 중..." : "Simulation 시작"}
          </button>
        </div>
      )}
    </div>
  );
}