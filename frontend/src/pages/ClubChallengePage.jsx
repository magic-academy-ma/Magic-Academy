import { useEffect, useState } from "react";

import { apiRequest } from "../api/client.js";
import InspectorPanel from "../components/InspectorPanel.jsx";
import SchoolMap from "../components/SchoolMap.jsx";
import "./ClubChallengePage.css";

const INTRO = [
  { name: "레오 · ESTP", image: "/assets/character/Leo_ESTP.png", text: "큰일이야! 우리 동아리에 폐부 경고가 내려왔어. 이대로면 정말 사라질지도 몰라." },
  { name: "아델 · ISTJ", image: "/assets/character/Adel_ISTJ.png", text: "회원 수와 평판을 회복해야 해. 중요한 순간마다 네 선택이 필요해." },
  { name: "레오 · ESTP", image: "/assets/character/Leo_ESTP.png", text: "3일 동안 우리와 함께 동아리를 다시 살려 보자!" },
];
const ROUND_TITLES = { 1: "폐부 경고와 내부 갈등", 2: "신입 회원 모집 및 홍보", 3: "성과 발표와 최종 심사" };
const ENDING_LABELS = { REVIVAL: "동아리 부활", CONDITIONAL: "조건부 유지", ONE_MEMBER: "나 홀로 동아리", CLOSED: "동아리 폐부" };
const ACTION_LABELS = { ATTEND_CLASS: "수업 참석", TEACH_CLASS: "수업 진행", STUDY: "학습", TALK: "대화", EAT: "식사", MOVE: "이동", REST: "휴식", PARTICIPATE_EVENT: "사건 참여", HELP: "도움", AVOID: "회피", WAIT: "대기" };

function visibleSummary(result, agentName) {
  if (/[가-힣]/.test(result.motivation_summary ?? "")) return result.motivation_summary;
  return `${agentName}이(가) ${ACTION_LABELS[result.action_type] ?? "일반"} 행동을 선택했습니다.`;
}

export default function ClubChallengePage({ token, onBack, runId, onComplete }) {
  const [intro, setIntro] = useState(0);
  const [run, setRun] = useState(null);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [selectedChoice, setSelectedChoice] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadAgents(simulationId) {
    const agentList = await apiRequest(`/v1/simulations/${simulationId}/agents`, { token });
    setAgents(agentList);
    setSelectedAgent((current) => agentList.find((agent) => agent.id === current?.id) ?? agentList[0] ?? null);
  }

  // 스토리모드에서는 이미 시작된 챕터 run을 이어서 연다.
  useEffect(() => {
    if (!runId) return;
    let active = true;
    apiRequest(`/v1/challenges/club-revival/${runId}`, { token })
      .then(async (response) => {
        if (!active) return;
        setRun(response.data);
        await loadAgents(response.data.simulation_id);
      })
      .catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, token]);

  async function startChallenge() {
    setLoading(true);
    setError("");
    try {
      const response = await apiRequest("/v1/challenges/club-revival", { token, method: "POST" });
      setRun(response.data);
      await loadAgents(response.data.simulation_id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function advanceChallenge() {
    setLoading(true);
    setError("");
    try {
      const response = await apiRequest(`/v1/challenges/club-revival/${run.id}/advance`, {
        token, method: "POST", body: JSON.stringify({ choice: selectedChoice || null }),
      });
      setRun(response.data);
      setSelectedChoice("");
      await loadAgents(response.data.simulation_id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  if (!run && runId) {
    return <main className="club-intro-page">{error ? <p className="message error" role="alert">{error}</p> : <p role="status">사건 기록을 불러오는 중...</p>}</main>;
  }

  if (!run) {
    const slide = INTRO[intro];
    return <main className="club-intro-page">
      <button type="button" className="club-back" onClick={onBack}>← 홈으로</button>
      <section className="club-intro-card">
        <p className="club-intro-brand">MAGIC ACADEMY</p>
        <div className="club-intro-badge">● STORY CHALLENGE 3</div>
        <div className="club-intro-dialogue">
          <img src={slide.image} alt="" />
          <div><b>{slide.name}</b><p>{slide.text}</p></div>
        </div>
        {error && <p className="message error" role="alert">{error}</p>}
        <button type="button" className="club-intro-next" disabled={loading} onClick={() => intro < INTRO.length - 1 ? setIntro(intro + 1) : startChallenge()}>
          {loading ? "시작 중..." : intro < INTRO.length - 1 ? "다음 →" : "도전과제 시작"}
        </button>
        <div className="club-intro-pagination"><span>{INTRO.map((_, index) => <i key={index} className={index === intro ? "active" : ""} />)}</span><b>0{intro + 1} / 0{INTRO.length}</b></div>
      </section>
    </main>;
  }

  const requiresChoice = (run.next_choice_options?.length ?? 0) > 0;
  const actionByAgent = new Map((run.agent_results ?? []).map((result) => [result.agent_id, result]));
  const memberAgentIds = new Set(run.member_agent_ids ?? []);

  return <div className="club-game-page">
    <header className="club-game-topbar">
      <button type="button" onClick={onBack}>← 홈</button><strong>Magic Academy</strong>
      <span>STORY 3 · ROUND {run.current_round} · TICK {run.current_tick}/9</span>
      <div className="club-game-stats"><b>회원 {run.member_count}명</b><b>평판 {run.reputation}</b></div>
      <button type="button" onClick={advanceChallenge} disabled={loading || requiresChoice}>{loading ? "Agent 판단 중..." : "다음 Tick 실행"}</button>
    </header>
    <main className="club-game-layout">
      <aside className="club-agent-list">
        <h1>동아리를 폐부에서 구하기</h1><p>{ROUND_TITLES[run.current_round]}</p>
        {agents.map((agent) => <button key={agent.id} type="button" className={selectedAgent?.id === agent.id ? "active" : ""} onClick={() => setSelectedAgent(agent)}><span>{agent.name}</span><small>{agent.location?.name ?? "위치 미상"} · {agent.mbti_type}</small><em className="club-agent-role">{agent.agent_type === "professor" ? "지도 교수" : memberAgentIds.has(agent.id) ? "정회원" : "가입 후보"}</em></button>)}
      </aside>
      <section className="club-map-stage">
        <SchoolMap agents={agents} agentActions={actionByAgent} simulationId={run.simulation_id} token={token} onAgentSelect={setSelectedAgent} />
        <div className="club-round-banner"><b>ROUND {run.current_round}</b><span>{ROUND_TITLES[run.current_round]}</span></div>
      </section>
      <InspectorPanel agent={selectedAgent} simulationId={run.simulation_id} token={token} currentTick={run.current_tick} onClose={() => setSelectedAgent(null)} />
    </main>
    <section className="club-event-log"><h2>사건 기록</h2>{(run.agent_results ?? []).length === 0 ? <p>아직 기록된 에이전트 행동이 없습니다.</p> : run.agent_results.map((result) => { const agentName = agents.find((agent) => agent.id === result.agent_id)?.name ?? "에이전트"; return <article key={result.agent_id}><b>{agentName}</b><span>{ACTION_LABELS[result.action_type] ?? "일반 행동"}</span><p>{visibleSummary(result, agentName)}</p></article>; })}</section>
    {requiresChoice && <div className="club-choice-backdrop" role="dialog" aria-label="도전과제 선택"><section className="club-choice-modal"><p>사용자 개입</p><h2>{ROUND_TITLES[run.current_round]}</h2><p className="club-choice-story">{run.next_story}</p><div>{run.next_choice_options.map((option) => <label key={option.value} aria-label={option.label}><input type="radio" name="club-choice" value={option.value} checked={selectedChoice === option.value} onChange={(event) => setSelectedChoice(event.target.value)} /><span><strong>{option.label}</strong><small>{option.description}</small></span></label>)}</div><button type="button" onClick={advanceChallenge} disabled={loading || !selectedChoice}>{loading ? "Agent 판단 중..." : "선택하고 진행"}</button></section></div>}
    {run.status === "completed" && <div className="club-choice-backdrop"><section className="club-choice-modal club-ending"><p>최종 결과</p><h2>{ENDING_LABELS[run.ending]}</h2>{onComplete ? <button type="button" onClick={onComplete}>활동 기록 남기고 계속</button> : <button type="button" onClick={onBack}>홈으로 돌아가기</button>}</section></div>}
    {error && <p className="club-game-error" role="alert">{error}</p>}
  </div>;
}
