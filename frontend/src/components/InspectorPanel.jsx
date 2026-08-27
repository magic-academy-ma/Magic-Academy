import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../api/client.js";
import "./InspectorPanel.css";

const BIG_FIVE = [
  ["openness", "개방성"],
  ["conscientiousness", "성실성"],
  ["extraversion", "외향성"],
  ["agreeableness", "우호성"],
  ["emotional_stability", "정서안정성"],
];
const STATE_FIELDS = [["hunger", "배고픔"], ["fatigue", "피로도"], ["stress", "스트레스"], ["satisfaction", "만족도"]];
const RELATION_FIELDS = [["affection", "호감도"], ["closeness", "친밀도"], ["trust", "신뢰도"], ["tension", "긴장도"], ["rivalry", "경쟁"], ["dependency", "의존도"]];

function clamp(value, min, max) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : min;
}

function BigFiveBar({ value, label }) {
  const normalized = clamp(value, -50, 50);
  const level = normalized <= -17 ? "Low" : normalized >= 17 ? "High" : "Neutral";
  return <div className="inspector-meter-row">
    <div className="inspector-meter-label"><span>{label}</span><span>{level} · {normalized}</span></div>
    <div className="inspector-meter big-five-meter"><span className={`meter-fill ${level.toLowerCase()}`} style={{ width: `${((normalized + 50) / 100) * 100}%` }} /></div>
  </div>;
}

function StateBar({ value, label }) {
  const normalized = clamp(value, 0, 100);
  return <div className="inspector-meter-row"><div className="inspector-meter-label"><span>{label}</span><span>{normalized}/100</span></div><div className="inspector-meter"><span className="meter-fill" style={{ width: `${normalized}%` }} /></div></div>;
}

function MoodBar({ value }) {
  const normalized = clamp(value, -100, 100);
  const width = Math.abs(normalized) / 2;
  return <div className="inspector-meter-row"><div className="inspector-meter-label"><span>기분</span><span>{normalized}/100</span></div><div className="mood-meter"><span className={`mood-fill ${normalized < 0 ? "negative" : "positive"}`} style={{ width: `${width}%`, left: normalized < 0 ? `${50 - width}%` : "50%" }} /></div></div>;
}

function EmptyState({ children = "데이터가 없습니다." }) {
  return <p className="inspector-empty">{children}</p>;
}

function normalizeList(value) {
  return Array.isArray(value) ? value : value?.items ?? value?.data ?? [];
}

export default function InspectorPanel({ agent, simulationId, token, currentTick, onClose }) {
  const [detail, setDetail] = useState(agent);
  const [state, setState] = useState(agent?.state);
  const [explanation, setExplanation] = useState(null);
  const [memories, setMemories] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setDetail(agent);
    setState(agent?.state);
    setExplanation(null);
    setMemories([]);
    setRelationships([]);
    if (!agent?.id) return undefined;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    const request = (path) => apiRequest(path, { token, signal: controller.signal });
    Promise.allSettled([
      request(`/v1/agents/${agent.id}`),
      request(`/v1/agents/${agent.id}/state`),
      request(`/v1/agents/${agent.id}/decision-explanation?tick=${Number.isFinite(Number(currentTick)) ? currentTick : 0}`),
      request(`/v1/agents/${agent.id}/behavior-log?limit=5`),
      request(`/v1/agents/${agent.id}/memories?limit=10`),
      request(`/v1/agents/${agent.id}/relationships`),
    ]).then((results) => {
      if (controller.signal.aborted) return;
      const [agentResult, stateResult, explanationResult, behaviorResult, memoryResult, relationshipResult] = results;
      if (agentResult.status === "fulfilled" && agentResult.value?.id) setDetail(agentResult.value);
      if (stateResult.status === "fulfilled" && stateResult.value?.mood !== undefined) setState(stateResult.value);
      if (explanationResult.status === "fulfilled") setExplanation(explanationResult.value);
      if (memoryResult.status === "fulfilled") setMemories(normalizeList(memoryResult.value));
      if (relationshipResult.status === "fulfilled") setRelationships(normalizeList(relationshipResult.value));
      if (behaviorResult.status === "fulfilled") setBehavior(normalizeList(behaviorResult.value));
      if (results.some((result) => result.status === "rejected" && result.reason?.status !== 404)) setError("일부 Inspector 데이터를 불러오지 못했습니다.");
      setLoading(false);
    });
    return () => controller.abort();
  }, [agent, token, currentTick, simulationId]);

  const [behavior, setBehavior] = useState([]);
  const profile = detail?.profile ?? {};
  const currentState = state ?? detail?.state ?? {};
  const organizations = detail?.organizations ?? [];
  const latestMemoryIds = useMemo(() => new Set(memories.slice(0, 2).map((memory) => memory.id)), [memories]);

  if (!agent) return <aside className="panel inspector-panel"><h2>Inspector</h2><EmptyState>Agent를 선택하세요.</EmptyState></aside>;

  return <aside className="panel inspector-panel" aria-label="Agent Inspector">
    <div className="inspector-header"><div><h2>Inspector</h2><h3>{detail?.name ?? agent.name}</h3></div><button type="button" className="inspector-close" onClick={onClose}>닫기</button></div>
    {loading && <p className="inspector-loading">상세 데이터를 불러오는 중...</p>}
    {error && <p className="message error" role="alert">{error}</p>}
    <section><h3>프로필</h3><div className="profile-summary"><strong>{detail?.name ?? agent.name}</strong><span>{detail?.agent_type ?? agent.agent_type}</span><span>{detail?.mbti_type ?? agent.mbti_type}</span>{detail?.is_user_persona && <b className="persona-badge">User Persona</b>}</div><dl className="inspector-details"><dt>학년</dt><dd>{detail?.student_profile ? `${detail.student_profile.grade}학년` : "-"}</dd><dt>전공</dt><dd>{detail?.student_profile?.interest_field ?? organizations.find((item) => item.organization_type === "major")?.name ?? "-"}</dd><dt>위치</dt><dd>{detail?.location?.name ?? "-"}</dd></dl><div className="meter-list">{BIG_FIVE.map(([key, label]) => <BigFiveBar key={key} value={profile[key]} label={label} />)}</div></section>
    <section><h3>내부 상태</h3><div className="meter-list">{STATE_FIELDS.map(([key, label]) => <StateBar key={key} value={currentState[key]} label={label} />)}<MoodBar value={currentState.mood} /></div></section>
    <section><h3>Decision Explanation <small>Tick {currentTick ?? 0}</small></h3>{explanation?.alternatives?.length ? <div className="alternative-list">{explanation.alternatives.slice(0, 3).map((item, index) => <div className={`alternative ${item.selected ? "selected" : ""}`} key={`${item.action_type}-${index}`}><div><b>{item.action_type}</b><span className="priority">{item.relative_priority}</span></div><p>{item.description}</p></div>)}</div> : <EmptyState>이번 Tick 데이터 없음</EmptyState>}{explanation?.influencing_factors?.length ? <ul className="factor-list">{explanation.influencing_factors.map((factor, index) => <li key={`${factor.source}-${index}`}><b>{factor.source}</b> <span className={factor.direction === "SUPPORT" ? "support" : "oppose"}>{factor.direction}</span> {factor.description}</li>)}</ul> : null}</section>
    <section><h3>행동 로그</h3>{behavior.length ? <ul className="log-list">{behavior.map((item, index) => <li key={item.id ?? index}><div><b>Tick {item.tick ?? item.tick_number ?? "-"}</b><span className={`status-tag ${String(item.status ?? item.runtime_status ?? "").toLowerCase()}`}>{item.status ?? item.runtime_status ?? "-"}</span></div><strong>{item.action_type ?? item.action ?? "-"}</strong>{item.utterance && <p>“{item.utterance}”</p>}{item.motivation_summary && <small>{item.motivation_summary}</small>}</li>)}</ul> : <EmptyState>행동 로그 API가 아직 없거나 기록이 없습니다.</EmptyState>}</section>
    <section><h3>Memory</h3>{memories.length ? <ul className="memory-list">{memories.map((memory, index) => <li key={memory.id ?? index} className={`${latestMemoryIds.has(memory.id) ? "latest" : ""}`}><div><span className="memory-type">{memory.memory_type}</span>{latestMemoryIds.has(memory.id) && <span className="highlight-tag">LATEST</span>}{memory.retrieval_rank && memory.retrieval_rank <= 3 && <span className="highlight-tag rag">RAG TOP {memory.retrieval_rank}</span>}</div><p>{memory.content}</p><small>중요도 {memory.importance} · Tick {memory.created_tick}</small></li>)}</ul> : <EmptyState>저장된 Memory가 없습니다.</EmptyState>}</section>
    <section><h3>관계</h3>{relationships.length ? <div className="relationship-list">{relationships.map((relationship, index) => <article key={relationship.target_agent_id ?? index}><div className="relationship-heading"><strong>{relationship.target_agent_name ?? relationship.target_agent?.name ?? "알 수 없음"}</strong>{relationship.relationship_type && <span className="relationship-tag">{String(relationship.relationship_type).toUpperCase()}</span>}</div>{RELATION_FIELDS.map(([key, label]) => <div className="mini-meter" key={key}><span>{label}</span><span className="mini-meter-track"><i style={{ width: `${clamp(relationship[key], 0, 100)}%` }} /></span><small>{clamp(relationship[key], 0, 100)}</small></div>)}</article>)}</div> : <EmptyState>표시할 관계가 없습니다.</EmptyState>}</section>
  </aside>;
}
