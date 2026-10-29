import { useCallback, useEffect, useState } from "react";

import { apiRequest } from "../api/client.js";
import InspectorPanel from "../components/InspectorPanel.jsx";
import SchoolMap from "../components/SchoolMap.jsx";
import "./ClubChallengePage.css";

// CHAPTER 2(팀 갈등)·CHAPTER 4(축제 부스) 공통 플레이 화면. 화면 구성은 CHAPTER 3과 같다.
const CHAPTERS = {
  2: {
    path: "team-revival",
    title: "무너진 팀을 다시 살려라",
    endings: { UNITED: "팀이 다시 하나가 되었습니다", PARTIAL: "대회는 참가하지만 갈등이 남았습니다", DISBANDED: "팀이 해체되고 대회를 포기했습니다" },
  },
  4: {
    path: "festival-booth",
    title: "축제 부스 운영하기",
    endings: { POPULAR: "축제의 인기 부스로 마무리했습니다", COMPLETED: "여러 문제가 있었지만 무사히 운영을 끝냈습니다", HALTED: "부스 운영이 사실상 중단되었습니다" },
  },
};
const ACTION_LABELS = { ATTEND_CLASS: "수업 참석", TEACH_CLASS: "수업 진행", STUDY: "학습", TALK: "대화", EAT: "식사", MOVE: "이동", REST: "휴식", PARTICIPATE_EVENT: "사건 참여", HELP: "도움", AVOID: "회피", WAIT: "대기" };

function visibleSummary(result, agentName) {
  if (/[가-힣]/.test(result.motivation_summary ?? "")) return result.motivation_summary;
  return `${agentName}이(가) ${ACTION_LABELS[result.action_type] ?? "일반"} 행동을 선택했습니다.`;
}

function BoothSetupForm({ choice, members, agentName, value, onChange }) {
  return <>
    <div>{choice.concepts.map((concept) => <label key={concept.value} aria-label={concept.label}>
      <input type="radio" name="booth-concept" value={concept.value} checked={value.concept === concept.value} onChange={() => onChange({ ...value, concept: concept.value })} />
      <span><strong>{concept.label}</strong><small>{concept.description}</small></span>
    </label>)}</div>
    <label><input type="checkbox" checked={value.assignRoles} onChange={(event) => onChange({ ...value, assignRoles: event.target.checked })} />
      <span><strong>학생들에게 역할을 맡긴다</strong><small>맡기지 않으면 학생들이 스스로 역할을 나눕니다.</small></span></label>
    {value.assignRoles && <div className="story-role-grid">{members.map((member) => <label key={member.agent_id} className="story-role-row">
      <span>{agentName(member.agent_id)}</span>
      <select aria-label={`${agentName(member.agent_id)} 역할`} value={value.roles[member.agent_id] ?? ""} onChange={(event) => onChange({ ...value, roles: { ...value.roles, [member.agent_id]: event.target.value } })}>
        <option value="">역할 선택</option>
        {choice.roles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
      </select>
    </label>)}</div>}
  </>;
}

const EMPTY_SETUP = { concept: "", assignRoles: true, roles: {} };

export default function StoryChapterPlay({ chapter, runId, token, onBack, onComplete }) {
  const meta = CHAPTERS[chapter];
  const root = `/v1/story/chapters/${meta.path}/${runId}`;
  const [run, setRun] = useState(null);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [selectedChoice, setSelectedChoice] = useState("");
  const [helpTarget, setHelpTarget] = useState("");
  const [setup, setSetup] = useState(EMPTY_SETUP);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadAgents = useCallback(async (simulationId) => {
    const agentList = await apiRequest(`/v1/simulations/${simulationId}/agents`, { token });
    setAgents(agentList);
    setSelectedAgent((current) => agentList.find((agent) => agent.id === current?.id) ?? agentList[0] ?? null);
  }, [token]);

  useEffect(() => {
    let active = true;
    apiRequest(root, { token })
      .then(async (response) => {
        if (!active) return;
        setRun(response.data);
        await loadAgents(response.data.simulation_id);
      })
      .catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, [root, token, loadAgents]);

  const choice = run?.next_choice ?? null;
  const agentName = (agentId) => agents.find((agent) => agent.id === agentId)?.name ?? "학생";

  function requestBody() {
    if (!choice) return {};
    if (choice.point === "BOOTH_SETUP") {
      return { concept: setup.concept, roles: setup.assignRoles ? setup.roles : null };
    }
    return { choice: selectedChoice, help_agent_id: selectedChoice === "SEND_HELP" && helpTarget ? helpTarget : null };
  }

  function choiceReady() {
    if (!choice) return true;
    if (choice.point === "BOOTH_SETUP") {
      return Boolean(setup.concept) && (!setup.assignRoles || run.members.every((member) => setup.roles[member.agent_id]));
    }
    return Boolean(selectedChoice);
  }

  async function advance() {
    setLoading(true);
    setError("");
    try {
      const response = await apiRequest(`${root}/advance`, { token, method: "POST", body: JSON.stringify(requestBody()) });
      setRun(response.data);
      setSelectedChoice("");
      setHelpTarget("");
      setSetup(EMPTY_SETUP);
      await loadAgents(response.data.simulation_id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  if (!run) {
    return <main className="club-intro-page">{error ? <p className="message error" role="alert">{error}</p> : <p role="status">사건 기록을 불러오는 중...</p>}</main>;
  }

  const actionByAgent = new Map((run.agent_results ?? []).map((result) => [result.agent_id, result]));
  const memberLabels = new Map((run.members ?? []).map((member) => [member.agent_id, member.label]));

  return <div className="club-game-page">
    <header className="club-game-topbar">
      <button type="button" onClick={onBack}>← 홈</button><strong>Magic Academy</strong>
      <span>CHAPTER {chapter} · ROUND {run.current_round} · TICK {run.current_tick}/{run.total_ticks}</span>
      <div className="club-game-stats">
        {run.concept && <b>{run.concept}</b>}
        {run.incident && <b>돌발: {run.incident}</b>}
        {chapter === 4 && <b>부스 공백 {run.vacant_ticks}회</b>}
      </div>
      <button type="button" onClick={advance} disabled={loading || Boolean(choice) || run.status === "completed"}>{loading ? "Agent 판단 중..." : "다음 Tick 실행"}</button>
    </header>
    <main className="club-game-layout">
      <aside className="club-agent-list">
        <h1>{meta.title}</h1><p>{run.round_title}</p>
        {agents.map((agent) => <button key={agent.id} type="button" className={selectedAgent?.id === agent.id ? "active" : ""} onClick={() => setSelectedAgent(agent)}><span>{agent.name}</span><small>{agent.location?.name ?? "위치 미상"} · {agent.mbti_type}</small><em className="club-agent-role">{agent.agent_type === "professor" ? "교수" : memberLabels.get(agent.id) ?? "학생"}</em></button>)}
      </aside>
      <section className="club-map-stage">
        <SchoolMap agents={agents} agentActions={actionByAgent} simulationId={run.simulation_id} token={token} onAgentSelect={setSelectedAgent} />
        <div className="club-round-banner"><b>ROUND {run.current_round}</b><span>{run.round_title}</span></div>
      </section>
      <InspectorPanel agent={selectedAgent} simulationId={run.simulation_id} token={token} currentTick={run.current_tick} onClose={() => setSelectedAgent(null)} />
    </main>
    <section className="club-event-log"><h2>사건 기록</h2>{(run.agent_results ?? []).length === 0 ? <p>다음 Tick을 실행하면 학생들의 행동이 기록됩니다.</p> : run.agent_results.map((result, index) => { const name = agentName(result.agent_id); return <article key={`${result.agent_id}-${index}`}><b>{name}</b><span>{result.event_title}</span><p>{visibleSummary(result, name)}</p></article>; })}</section>
    {choice && <div className="club-choice-backdrop" role="dialog" aria-label="조정관 개입"><section className="club-choice-modal">
      <p>조정관 개입</p><h2>{run.round_title}</h2><p className="club-choice-story">{choice.story}</p>
      {choice.point === "BOOTH_SETUP"
        ? <BoothSetupForm choice={choice} members={run.members} agentName={agentName} value={setup} onChange={setSetup} />
        : <div>{choice.options.map((option) => <label key={option.value} aria-label={option.label}><input type="radio" name="story-choice" value={option.value} checked={selectedChoice === option.value} onChange={(event) => setSelectedChoice(event.target.value)} /><span><strong>{option.label}</strong><small>{option.description}</small></span></label>)}</div>}
      {choice.help_target && selectedChoice === "SEND_HELP" && <label className="story-role-row"><span>부탁할 학생</span>
        <select aria-label="부탁할 학생" value={helpTarget} onChange={(event) => setHelpTarget(event.target.value)}>
          <option value="">지목하지 않음 (누가 갈지 학생들이 정함)</option>
          {run.members.map((member) => <option key={member.agent_id} value={member.agent_id}>{agentName(member.agent_id)}</option>)}
        </select></label>}
      <button type="button" onClick={advance} disabled={loading || !choiceReady()}>{loading ? "Agent 판단 중..." : "선택하고 진행"}</button>
    </section></div>}
    {run.status === "completed" && <div className="club-choice-backdrop"><section className="club-choice-modal club-ending"><p>사건 종료</p><h2>{meta.endings[run.ending]}</h2><button type="button" onClick={onComplete}>활동 기록 남기고 계속</button></section></div>}
    {error && <p className="club-game-error" role="alert">{error}</p>}
  </div>;
}
