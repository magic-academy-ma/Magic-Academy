import { useEffect, useRef, useState } from "react";
import { getUserPersonaConfig, getUserPersona, setUserPersona } from "../api/client.js";

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

/**
 * Student 5명 중 User Persona를 선택하고 MBTI/Big Five를 설정하는 컴포넌트.
 *
 * 계약 출처: 1단계 API 명세서 §12, MBTI → Big Five 정책 문서(mbti-big-five-v0.1)
 * - 선택 가능한 MBTI와 Big Five 허용 범위는 서버 config(mbti_rules)를 그대로 사용한다.
 *   프론트엔드에 값을 하드코딩하지 않는다 (정책 버전이 바뀌어도 코드 수정 불필요).
 * - MBTI를 선택하기 전에는 Big Five 조절이 불가능하다.
 * - MBTI를 다시 선택하면 기존 조절값을 모두 버리고 새 MBTI의 기본값으로 초기화한다 (§6).
 * - 각 Big Five 값은 선택한 MBTI의 min~max, config.step(5) 단위 안에서만 조절된다.
 * - Persona는 새 Agent를 만들지 않고 기존 Student를 갱신하므로 별도 목록 추가가 필요 없다.
 * - onSaved는 저장 성공 시뿐 아니라, 마운트 시 이미 적용된 Persona를 발견했을 때도 호출된다.
 *   상위(App.jsx)가 새로고침/재마운트 후에도 personaAgentId 등 표시 상태를 정확히 반영하려면 필요하다.
 */
export default function UserPersonaSetup({ simulationId, students, token, onSaved }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [config, setConfig] = useState(null); // { rule_version, global_min, global_max, step, mbti_rules }
  const [locked, setLocked] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [mbtiType, setMbtiType] = useState("");
  const [bigFive, setBigFive] = useState(null);

  // App.jsx가 onSaved로 인라인 함수를 넘기므로, 그 함수를 effect의 의존성으로 두면
  // 매 렌더마다 재조회가 일어난다. ref로 최신 함수만 참조하고 effect deps에서는 제외한다.
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
        const configResult = await getUserPersonaConfig(simulationId, { token });
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
          // 이미 설정된(또는 잠긴) Persona를 마운트 시점에 발견한 경우에도 상위에 알린다.
          // App.jsx가 이 값을 받아야 새로고침 후에도 Inspector·Agent 목록의 Persona 표시가 정확해진다.
          onSavedRef.current?.(persona);
        } catch (personaError) {
          if (personaError.status !== 404) throw personaError;
          // 404 = 아직 User Persona가 설정되지 않음. 정상 흐름이므로 에러로 표시하지 않는다.
          setSelectedAgentId("");
          setMbtiType("");
          setBigFive(null);
          setLocked(false);
        }
      } catch (requestError) {
        if (!cancelled) setError(requestError.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [simulationId, token]);

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
      const next = Math.min(rule.max, Math.max(rule.min, prev[key] + delta));
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
      setLocked(Boolean(result.locked));
      onSavedRef.current?.(result);
    } catch (requestError) {
      // 400 INVALID_PERSONALITY_CONFIGURATION: 범위·단위·규칙버전 불일치
      // 404 RESOURCE_NOT_FOUND: Simulation 또는 Student 없음
      // 409 CONFLICT: 이미 적용됨 또는 Simulation 시작으로 잠김
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
  const canSave = Boolean(selectedAgentId && mbtiType && bigFive) && !saving;

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
        <div className="persona-student-list" role="radiogroup" aria-label="User Persona Student 선택">
          {students.map((student) => (
            <label
              key={student.id}
              className={selectedAgentId === student.id ? "persona-student active" : "persona-student"}
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
          <select value={mbtiType} onChange={(e) => selectMbti(e.target.value)}>
            <option value="">선택 안 함</option>
            {mbtiOptions.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>

        {!mbtiType && <p className="message">MBTI를 먼저 선택하세요.</p>}

        <div className="persona-big-five">
          {BIG_FIVE_TRAITS.map(({ key, label }) => {
            const rule = mbtiType ? config.mbti_rules[mbtiType][key] : null;
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
        <button type="button" onClick={save} disabled={!canSave}>
          {saving ? "저장 중..." : "Persona 저장"}
        </button>
      )}
    </div>
  );
}
