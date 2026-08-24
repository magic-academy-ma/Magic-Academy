import { useState } from "react";
import { apiRequest } from "./api/client.js";
import RelationshipFlow from "./components/RelationshipFlow.jsx";
import "./App.css";

function AuthPanel({ onLogin, notice }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", display_name: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [authNotice, setAuthNotice] = useState("");

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        await apiRequest("/v1/auth/register", {
          method: "POST",
          body: JSON.stringify(form),
        });
      }
      const result = await apiRequest("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: form.username, password: form.password }),
      });
      onLogin(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <form className="panel auth-panel" onSubmit={submit}>
        <h1>Magic Academy</h1>
        <p>Slice 0 통합 환경</p>
        {notice && <p className="message error" role="alert">{notice}</p>}
        <label>아이디<input required minLength="3" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></label>
        {mode === "register" && <label>표시 이름<input required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></label>}
        <label>비밀번호<input required minLength="8" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
        {error && <p className="message error" role="alert">{error}</p>}
        <button disabled={loading}>{loading ? "처리 중..." : mode === "login" ? "로그인" : "가입하고 로그인"}</button>
        <button className="link-button" type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
          {mode === "login" ? "계정 만들기" : "로그인으로 돌아가기"}
        </button>
      </form>
    </main>
  );
}

// 서버 응답의 code/HTTP status를 프론트에서 보여줄 오류 종류로 분류한다.
// NOTE: ticks/advance 스펙(§4.2)에 정의된 코드(UNAUTHORIZED/RESOURCE_NOT_FOUND/CONFLICT) 기준.
// "재시도 실패"는 백엔드가 별도 code로 내려주는 필드가 아직 확정되지 않아, 우선 CONFLICT(409)를
// "지금은 재시도할 수 없는 상태"로 간주해 매핑했다. 실제 재시도 관련 code가 확정되면 이 매핑만
// 바꾸면 되도록 분리해뒀다.
function classifyTickError(requestError) {
  const status = requestError?.status;
  const code = requestError?.code;

  if (status === 401) {
    return { type: "AUTH", message: requestError.message };
  }
  if (status === 404 || code === "RESOURCE_NOT_FOUND") {
    return { type: "NOT_FOUND", message: "Simulation을 찾을 수 없습니다." };
  }
  if (code === "TICK_ALREADY_RUNNING") {
    return {
      type: "TICK_ALREADY_RUNNING",
      message: "이미 진행 중인 Tick이 있습니다. 잠시 후 다시 시도해 주세요.",
    };
  }
  if (status >= 500) {
    return {
      type: "RUNTIME",
      message: "Tick 실행 중 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    };
  }
  return { type: "GENERIC", message: requestError?.message || "알 수 없는 오류가 발생했습니다." };
}

export default function App() {
  const [auth, setAuth] = useState(null);
  const [simulation, setSimulation] = useState(null);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [name, setName] = useState("Slice 0 Simulation");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [tickLoading, setTickLoading] = useState(false);
  const [tickResult, setTickResult] = useState(null);
  const [tickError, setTickError] = useState(null); // { type, message }
  const [sessionNotice, setSessionNotice] = useState("");
  const [authNotice, setAuthNotice] = useState("");
  function resetSession(notice = "") {
    setAuth(null);
    setSimulation(null);
    setAgents([]);
    setSelectedAgent(null);
    setError("");
    setTickResult(null);
    setTickError(null);
    setAuthNotice(notice);
  }

  if (!auth) return <AuthPanel onLogin={setAuth} notice={authNotice} />;

  async function loadAgents(simulationId) {
    setLoading(true);
    setError("");
    try {
      const agentList = await apiRequest(`/v1/simulations/${simulationId}/agents`, {
        token: auth.access_token,
      });
      setAgents(agentList);
      setSelectedAgent(agentList[0] ?? null);
    } catch (requestError) {
      if (requestError.status === 401) {
        resetSession();
        return;
      }
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function createSimulation(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const created = await apiRequest("/v1/simulations", {
        token: auth.access_token,
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setSimulation(created);
      await loadAgents(created.id);
    } catch (requestError) {
      if (requestError.status === 401) {
        resetSession();
        return;
      }
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function runTick() {
    setTickLoading(true);
    setTickError(null);
    setTickResult(null);

    try {
      const result = await apiRequest(
        `/v1/simulations/${simulation.id}/ticks/advance`,
        {
          token: auth.access_token,
          method: "POST",
        }
      );

      setTickResult(result.data ?? result);
    } catch (requestError) {
      const classified = classifyTickError(requestError);
      if (classified.type === "AUTH") {
        resetSession(classified.message);
        return;
      }
      setTickError(classified);
    } finally {
      setTickLoading(false);
    }
  }
  // agent_results: agent_id, agent_name, runtime_status(PROPOSED/FALLBACK/SKIPPED),
  // action_type, utterance, motivation_summary, decision_explanation.influencing_factors,
  // retry_count, failure_reason (은혜님 스펙 확정, §3.2)
  const agentResults = tickResult?.agent_results ?? [];
  const relationshipDeltas = tickResult?.relationship_deltas ?? [];
  const tickSucceeded = tickResult?.status === "COMPLETED";
  const tickFailed = tickResult && !tickSucceeded;

  const agentNameById = Object.fromEntries(agents.map((a) => [a.id, a.name]));
  const relationshipAgentIds = [
    ...new Set(
      relationshipDeltas.flatMap((d) => [d.source_agent_id, d.target_agent_id])
    ),
  ];
  const flowNodes = relationshipAgentIds.map((id, index) => ({
    id: String(id),
    position: { x: (index % 4) * 200, y: Math.floor(index / 4) * 150 },
    data: { label: agentNameById[id] ?? String(id) },
  }));
  const edgesByPair = new Map();
  for (const delta of relationshipDeltas) {
    const key = `${delta.source_agent_id}->${delta.target_agent_id}`;
    if (!edgesByPair.has(key)) {
      edgesByPair.set(key, {
        id: `e-${key}`,
        source: String(delta.source_agent_id),
        target: String(delta.target_agent_id),
        type: "delta",
        data: { effects: [] },
      });
    }
    edgesByPair.get(key).data.effects.push(delta);
  }
  const flowEdges = [...edgesByPair.values()];

  return (
    <div className="app-shell">
      <header><strong>Magic Academy</strong><div className="profile"><span>{auth.user.display_name}</span><small>@{auth.user.username}</small></div></header>
      <main>
        {!simulation ? (
          <form className="panel create-panel" onSubmit={createSimulation}>
            <h1>Simulation 생성</h1>
            <label>이름<input required value={name} onChange={(e) => setName(e.target.value)} /></label>
            {error && <p className="message error" role="alert">{error}</p>}
            <button disabled={loading}>{loading ? "Simulation과 Agent를 생성하는 중..." : "Simulation 생성"}</button>
          </form>
        ) : (
          <section className="workspace">
            <div className="panel agent-list">
              <h1>{simulation.name}</h1><p>Agent {agents.length}명</p>
              {loading && <p className="message">Agent를 불러오는 중...</p>}
              {error && <p className="message error" role="alert">{error}</p>}
              {error && <button type="button" onClick={() => loadAgents(simulation.id)}>Agent 다시 불러오기</button>}
              {!loading && !error && agents.length === 0 && <p className="message">표시할 Agent가 없습니다.</p>}
              {agents.map((agent) => <button data-agent-id={agent.id} className={selectedAgent?.id === agent.id ? "agent active" : "agent"} key={agent.id} onClick={() => setSelectedAgent(agent)}><b>{agent.name}</b><span>{agent.agent_type} · {agent.mbti_type}</span></button>)}
            </div>
            <aside className="panel inspector">
              <h2>Inspector</h2>
              {!selectedAgent ? <p>Agent를 선택하세요.</p> : <>
                <h3>{selectedAgent.name}</h3>
                <dl><dt>종류</dt><dd>{selectedAgent.agent_type}</dd><dt>MBTI</dt><dd>{selectedAgent.mbti_type}</dd><dt>학년</dt><dd>{selectedAgent.student_profile ? `${selectedAgent.student_profile.grade}학년` : "-"}</dd><dt>위치</dt><dd>{selectedAgent.location.name}</dd><dt>기분</dt><dd>{selectedAgent.state.mood}</dd><dt>배고픔</dt><dd>{selectedAgent.state.hunger}</dd><dt>피로도</dt><dd>{selectedAgent.state.fatigue}</dd><dt>스트레스</dt><dd>{selectedAgent.state.stress}</dd><dt>만족도</dt><dd>{selectedAgent.state.satisfaction}</dd></dl>
              </>}
            </aside>
            <div className="panel tick-panel">
              <h2>Tick</h2>

              <button type="button" onClick={runTick} disabled={tickLoading}>
                {tickLoading ? "Tick 실행 중..." : "Tick 실행"}
              </button>

              {tickError && (
                <p className={`message error tick-error-${tickError.type.toLowerCase()}`} role="alert">
                  {tickError.message}
                </p>
              )}

              {tickError && tickError.type !== "AUTH" && (
                <button type="button" onClick={runTick} disabled={tickLoading}>
                  다시 시도
                </button>
              )}

              {tickFailed && (
                <p className="message error" role="alert">
                  Tick이 완료되지 않았습니다 (상태: {tickResult.status}).
                </p>
              )}

              {tickSucceeded && (
                <div className="tick-result">
                  <h3>실행 결과</h3>
                  <p>이전 Tick: {tickResult.previous_tick}</p>
                  <p>현재 Tick: {tickResult.current_tick}</p>
                  <p>현재 Day: {tickResult.current_day}</p>
                  <p>상태: {tickResult.status}</p>

                  <h4>Agent 행동</h4>
                  {agentResults.length === 0 ? (
                    <p className="message">
                      이번 Tick에서 표시할 Agent 행동 결과가 없습니다.
                    </p>
                  ) : (
                    <ul className="agent-result-list">
										  {agentResults.map((agentResult) => {
										    const status = agentResult.runtime_status;
										    return (
										      <li key={agentResult.agent_id} className={`agent-result status-${status?.toLowerCase()}`}>
										        <b>{agentResult.agent_name ?? agentResult.agent_id}</b>
										        <span className={`runtime-status runtime-status-${status?.toLowerCase()}`}>
										          {status === "PROPOSED" && "정상 진행"}
										          {status === "FALLBACK" && "재시도 실패 → Fallback 적용"}
										          {status === "SKIPPED" && "이번 Tick 미참여"}
										        </span>
										        {status === "SKIPPED" ? (
										          <p className="message">비활성 상태로 이번 Tick에서 행동하지 않았습니다.</p>
										        ) : (
										          <>
										            <span className="action-type">{agentResult.action_type}</span>
										            {agentResult.utterance && <p className="utterance">“{agentResult.utterance}”</p>}
										            {agentResult.motivation_summary && (
										              <p className="motivation">{agentResult.motivation_summary}</p>
										            )}
										            {agentResult.decision_explanation?.influencing_factors?.length > 0 && (
										              <ul className="influencing-factors">
										                {agentResult.decision_explanation.influencing_factors.map((factor, idx) => (
										                  <li key={idx}>
										                    [{factor.source}] {factor.description} ({factor.direction})
										                  </li>
										                ))}
										              </ul>
										            )}
										          </>
										        )}
										        {status === "FALLBACK" && (
										          <p className="fallback-info">
										            재시도 {agentResult.retry_count}회 실패
										            {agentResult.failure_reason && ` — 사유: ${agentResult.failure_reason}`}
										          </p>
										        )}
										      </li>
										    );
										  })}
										</ul>
                  )}

                  <h4>관계 변화</h4>
                  <RelationshipFlow
                    nodes={flowNodes}
                    edges={flowEdges}
                  />
                </div>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
