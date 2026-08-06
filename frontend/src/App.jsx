import { useState } from "react";
import { apiRequest } from "./api/client.js";
import "./App.css";

function AuthPanel({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", display_name: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

export default function App() {
  const [auth, setAuth] = useState(null);
  const [simulation, setSimulation] = useState(null);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [name, setName] = useState("Slice 0 Simulation");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!auth) return <AuthPanel onLogin={setAuth} />;

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
      if (requestError.status === 401) setAuth(null);
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
      if (requestError.status === 401) setAuth(null);
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

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
          </section>
        )}
      </main>
    </div>
  );
}
