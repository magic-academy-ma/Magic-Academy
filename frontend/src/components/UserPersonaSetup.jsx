import { useEffect, useRef, useState } from "react";
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
  const [error, setError] = useState("");
  const [config, setConfig] = useState(null);
  const [locked, setLocked] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [mbtiType, setMbtiType] = useState("");
  const [bigFive, setBigFive] = useState(null);

  // App.jsx가 onSaved로 인라인 함수를 넘기므로,
  // effect의 의존성에는 포함하지 않고 최신 함수만 ref로 참조한다.
  const onSavedRef = useRef(onSaved);

  useEffect(() => {
    onSavedRef.current = onSaved;
  }, [onSaved]);

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

        try {
          const persona = await getUserPersona(simulationId, { token });

          if (cancelled) return;

          setSelectedAgentId(persona.agent_id);
          setMbtiType(persona.mbti_type);

          setBigFive(
            BIG_FIVE_TRAITS.reduce((acc, trait) => {
              acc[trait.key] = persona[trait.key];
              return acc;
            }, {})
          );

          setLocked(Boolean(persona.locked));

          // 이미 설정된 Persona를 발견한 경우 상위 컴포넌트에도 알린다.
          onSavedRef.current?.(persona);
        } catch (personaError) {
          if (personaError.status !== 404) {
            throw personaError;
          }

          // 404 = 아직 User Persona가 설정되지 않음.
          setSelectedAgentId("");
          setMbtiType("");
          setBigFive(null);
          setLocked(false);
        }
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
  }, [simulationId, token, refreshKey]);

  function selectMbti(nextMbti) {
    setMbtiType(nextMbti);

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
  }

  async function save() {
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

      await startSimulation(simulationId, { token });

      setLocked(true);
      onSavedRef.current?.(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
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
    Boolean(selectedAgentId && mbtiType && bigFive) && !saving;

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

      <fieldset disabled={locked || saving}>
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
                onChange={() => setSelectedAgentId(student.id)}
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
        <button
          type="button"
          onClick={save}
          disabled={!canSave}
        >
          {saving ? "저장 중..." : "Persona 저장"}
        </button>
      )}
    </div>
  );
}