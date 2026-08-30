import { useCallback, useEffect, useRef, useState } from "react";

import { apiRequest } from "./api/client.js";
import SettingsPanel from "./components/SettingsPanel.jsx";
import ReplayPanel from "./components/ReplayPanel.jsx";
import SnapshotPanel from "./components/SnapshotPanel.jsx";
import SharingPanel from "./components/SharingPanel.jsx";
import SharedBrowser from "./components/SharedBrowser.jsx";
import RelationshipModal from "./components/RelationshipModal.jsx";
import EventLogPanel from "./components/EventLogPanel.jsx";
import InspectorPanel from "./components/InspectorPanel.jsx";
import SchoolMap from "./components/SchoolMap.jsx";
import UserPersonaSetup from "./components/UserPersonaSetup.jsx";
import PersonaSelectPage from "./pages/PersonaSelectPage.jsx";
import PersonaSetupPage from "./pages/PersonaSetupPage.jsx";
import { useSimulationWS } from "./hooks/useSimulationWS.js";
import BrandingPage from "./pages/BrandingPage.jsx";
import MainPage from "./pages/MainPage.jsx";
import SavePage from "./pages/SavePage.jsx";
import MyPage from "./pages/MyPage.jsx";
import "./App.css";

function AuthPanel({ onLogin, notice }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    email: "",
    display_name: "",
    password: "",
  });
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
          body: JSON.stringify({
            username: form.email,
            display_name: form.display_name,
            password: form.password,
          }),
        });
      }

      const result = await apiRequest("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: form.email,
          password: form.password,
        }),
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
      <form className="auth-panel" onSubmit={submit}>
        <div className="login-top">
          <div className="login-brand">
            <img src="/assets/concept/logo.png" alt="" width="40" height="40" />
            Magic Academy
          </div>
          <h1 className="login-title">마법학교에<br />입학하세요.</h1>
          <p className="login-sub">
            계정으로 로그인하여 시뮬레이션을 시작하거나 이어서 관찰합니다.
          </p>
        </div>

        {notice && (
          <p className="message error" role="alert">
            {notice}
          </p>
        )}

        <div className="login-form">
          <div className="field-group">
            <label className="field-label" htmlFor="auth-email">이메일</label>
            <input
              id="auth-email"
              className="field-input"
              aria-label="아이디"
              required
              type="text"
              placeholder="아이디 또는 이메일"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>

          {mode === "register" && (
            <div className="field-group">
              <label className="field-label" htmlFor="auth-display-name">표시 이름</label>
              <input
                id="auth-display-name"
                className="field-input"
                required
                value={form.display_name}
                onChange={(e) =>
                  setForm({ ...form, display_name: e.target.value })
                }
              />
            </div>
          )}

          <div className="field-group">
            <label className="field-label" htmlFor="auth-password">비밀번호</label>
            <input
              id="auth-password"
              className="field-input"
              required
              minLength="8"
              type="password"
              placeholder="••••••••"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>

          {error && (
            <p className="message error" role="alert">
              {error}
            </p>
          )}

          <button className="login-submit" disabled={loading}>
            {loading
              ? "처리 중..."
              : mode === "login"
                ? "로그인"
                : "가입하고 로그인"}
          </button>

          {mode === "login" && (
            <>
              <div className="login-divider">
                <span className="login-divider-text">OR</span>
              </div>

              <button
                className="oauth-btn"
                type="button"
                onClick={() => console.log("TODO: Google OAuth")}
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                  <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
                  <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
                  <path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
                  <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
                </svg>
                Google로 계속하기
              </button>
            </>
          )}
        </div>

        <div className="login-bottom">
          <p className="login-note">
            {mode === "login" ? "계정이 없으신가요?" : "이미 계정이 있으신가요?"}{" "}
            <button
              className="login-signup"
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
              }}
            >
              {mode === "login" ? "회원가입" : "로그인으로 돌아가기"}
            </button>
          </p>
        </div>
      </form>
    </main>
  );
}

// MVP 공간 6종. 백엔드는 location code/name만 제공하고, 배경 표현은 프론트가
// code로 매핑한다 (별도 배경 asset이 아직 없어 이모지로 간단히 표시).
const LOCATION_BACKDROP = {
  classroom: "🏫",
  restaurant: "🍽️",
  library: "📚",
  lab: "⚗️",
  dormitory: "🛏️",
  central_square: "⛲",
};

function locationLabel(location) {
  if (!location) return "-";
  const backdrop = LOCATION_BACKDROP[location.code];
  return backdrop ? `${backdrop} ${location.name}` : location.name;
}

// 서버 응답의 code/HTTP status를 프론트에서 보여줄 오류 종류로 분류한다.
function classifyTickError(requestError) {
  const status = requestError?.status;
  const code = requestError?.code;

  if (status === 401) {
    return {
      type: "AUTH",
      message: requestError.message,
    };
  }

  if (status === 404 || code === "RESOURCE_NOT_FOUND") {
    return {
      type: "NOT_FOUND",
      message: "Simulation을 찾을 수 없습니다.",
    };
  }

  if (code === "TICK_ALREADY_RUNNING") {
    return {
      type: "TICK_ALREADY_RUNNING",
      message: "이미 진행 중인 Tick이 있습니다. 잠시 후 다시 시도해 주세요.",
    };
  }

  if (status === 503) {
    return {
      type: "RUNTIME_NOT_CONFIGURED",
      message: requestError.message,
    };
  }

  if (status >= 500) {
    return {
      type: "RUNTIME",
      message:
        "Tick 실행 중 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    };
  }

  return {
    type: "GENERIC",
    message:
      requestError?.message || "알 수 없는 오류가 발생했습니다.",
  };
}

export default function App() {
  const [auth, setAuth] = useState(null);
  const [screen, setScreen] = useState("main");
  const [simulationId, setSimulationId] = useState(null);
  const [personaId, setPersonaId] = useState(null);
  const [personaSetupDone, setPersonaSetupDone] = useState(false);
  const [simulation, setSimulation] = useState(null);
  const [agents, setAgents] = useState([]);
  const [personaAgentId, setPersonaAgentId] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [tickLoading, setTickLoading] = useState(false);
  const [tickResult, setTickResult] = useState(null);
  const [tickError, setTickError] = useState(null);

  const [authNotice, setAuthNotice] = useState("");
  const [managementView, setManagementView] = useState(null); // null | "settings" | "replay" | "snapshot" | "sharing"
  const [isImported, setIsImported] = useState(false); // 이 Simulation이 공유 설정을 가져와 생성됐는지
  const [sharedBrowserOpen, setSharedBrowserOpen] = useState(false);
  const [recentShare, setRecentShare] = useState(null);
  const refreshAgentsSilentlyRef = useRef(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [agentTypeFilter, setAgentTypeFilter] = useState("전체");
  const [isPaused, setIsPaused] = useState(false);
  const [showInspectorModal, setShowInspectorModal] = useState(false);
  const [showRelationshipModal, setShowRelationshipModal] = useState(false);

  const { connected, lastTick, eventLog, agentActions } = useSimulationWS(
    simulation?.id,
    auth?.access_token,
    { onReconnect: () => refreshAgentsSilentlyRef.current?.() }
  );

  function resetSession(notice = "") {
    setAuth(null);
    setScreen("main");
    setSimulationId(null);
    setSimulation(null);
    setAgents([]);
    setSelectedAgent(null);
    setPersonaAgentId(null);
    setPersonaId(null);
    setPersonaSetupDone(false);
    setError("");
    setTickResult(null);
    setTickError(null);
    setAuthNotice(notice);
    setManagementView(null);
    setIsImported(false);
    setSharedBrowserOpen(false);
    setRecentShare(null);
  }

  function handleEnroll(newSimulation) {
    setSimulationId(newSimulation.id);
    setSimulation(newSimulation);
    setIsImported(false);
    loadAgents(newSimulation.id);
    setScreen("persona-select");
  }

  // 공유 설정 가져오기 성공 시 호출된다. import는 요청자 소유의 새 Simulation을
  // 정확히 하나 생성할 뿐 Runtime/LLM/Tick을 실행하지 않으므로, 응답으로 받은
  // Simulation으로 그대로 이동한다(원본과는 무관한 새 Simulation).
  function handleImported(newSimulation) {
    setSimulationId(newSimulation.id);
    setSimulation(newSimulation);
    setIsImported(true);
    setSharedBrowserOpen(false);
    setManagementView(null);
    loadAgents(newSimulation.id);
  }

  async function fetchAgents(simulationId) {
    const agentList = await apiRequest(
      `/v1/simulations/${simulationId}/agents`,
      {
        token: auth.access_token,
      }
    );

    setAgents(agentList);

    return agentList;
  }

  async function loadAgents(simulationId) {
    setLoading(true);
    setError("");

    try {
      const agentList = await fetchAgents(simulationId);
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

  // loadAgents와 달리 loading/error 상태를 건드리지 않는 조용한 재조회
  const refreshAgentsSilently = useCallback(
    async (simulationId) => {
      if (!auth) return;

      try {
        await fetchAgents(simulationId);
      } catch (requestError) {
        if (requestError.status === 401) {
          resetSession();
          return;
        }

        console.error("[App] Agent 상태 재조회 실패", requestError);
      }
    },
    [auth]
  );
  refreshAgentsSilentlyRef.current = refreshAgentsSilently;

  // Persona는 기존 Student 5명 중 하나를 가리킬 뿐 별도 Agent를 생성하지 않으므로
  // agents 목록에는 손대지 않고 personaAgentId만 별도로 추적한다.
  const students = agents.filter((agent) => agent.agent_type === "student");

  // agents 목록이 갱신되면 selectedAgent도 최신 상태로 동기화
  useEffect(() => {
    if (!selectedAgent) return;

    const updated = agents.find(
      (agent) => agent.id === selectedAgent.id
    );

    if (updated && updated !== selectedAgent) {
      setSelectedAgent(updated);
    }
  }, [agents, selectedAgent]);

  if (!auth) return <AuthPanel onLogin={setAuth} notice={authNotice} />;
  if (screen === "main") return (
    <MainPage
      displayName={auth.user.display_name}
      onStart={() => setScreen("branding")}
      onMyPage={() => setScreen("my-page")}
    />
  );
  if (screen === "my-page") return (
    <MyPage
      auth={auth}
      onBack={() => setScreen("main")}
      onRestore={(restoredSimulation) => {
        const restoredPersona = restoredSimulation.user_persona;
        setSimulationId(restoredSimulation.id);
        setSimulation(restoredSimulation);
        setPersonaId(restoredPersona.agent_id);
        setPersonaAgentId(restoredPersona.agent_id);
        setPersonaSetupDone(
          restoredPersona.status === "APPLIED" && restoredPersona.locked
        );
        loadAgents(restoredSimulation.id);
        setScreen("simulation");
      }}
    />
  );
  if (screen === "branding") return <BrandingPage auth={auth} onEnroll={handleEnroll} />;
  if (screen === "save") return (
    <SavePage
      simulationName={simulation?.name ?? "시뮬레이션"}
      onComplete={() => setScreen("simulation")}
      onCancel={() => setScreen("simulation")}
    />
  );
  if (!personaId) return <PersonaSelectPage simulationId={simulationId} onConfirm={setPersonaId} />;
  if (!personaSetupDone) return (
    <PersonaSetupPage
      simulationId={simulationId}
      charId={personaId}
      onBack={() => setPersonaId(null)}
      onStart={async (_charId, _config) => { setPersonaSetupDone(true); setScreen("simulation"); }}
    />
  );

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

  const agentResults = tickResult?.agent_results ?? [];
  const tickSucceeded = (tickResult?.status || "").toLowerCase() === "completed";
  const tickFailed = tickResult && !tickSucceeded;

  const agentNameById = Object.fromEntries(agents.map((a) => [a.id, a.name]));

  const filteredAgents = agents.filter((agent) => {
    const matchesSearch = !searchQuery || agent.name.includes(searchQuery);
    const matchesType =
      agentTypeFilter === "전체" ||
      (agentTypeFilter === "학생" && agent.agent_type === "student") ||
      (agentTypeFilter === "교수" && agent.agent_type === "professor");
    return matchesSearch && matchesType;
  });

  async function handleNightSkip() {
    try {
      await apiRequest(
        `/v1/simulations/${simulation.id}/night/skip`,
        { token: auth.access_token, method: "POST" }
      );
    } catch (requestError) {
      if (requestError.status === 401) resetSession(requestError.message);
    }
  }

  function handleEventAgentSelect(agentId) {
    const agent = agents.find((a) => a.id === agentId);
    if (agent) setSelectedAgent(agent);
  }

  return (
    <div className="app-shell sim-screen">
      <div className="sim-atmosphere" aria-hidden="true" />
      <header className="sim-topbar">
        <div className="sim-brand-mark" aria-hidden="true">M</div>
        <strong className="sim-brand">Magic Academy</strong>
        {simulation && lastTick && (
          <span className="tick-info">DAY {lastTick.current_day} · TICK {lastTick.current_tick}</span>
        )}
        <div className="header-controls">
          <button type="button" onClick={runTick} disabled={tickLoading}>
            {tickLoading ? "Tick 실행 중..." : "Tick 실행"}
          </button>
          <button type="button" onClick={() => setIsPaused((p) => !p)}>
            {isPaused ? "재개" : "일시정지"}
          </button>
          <button type="button" onClick={handleNightSkip}>
            밤 스킵
          </button>
          <button type="button" className="topbar-action" onClick={() => setShowInspectorModal(true)}>Inspector 열기</button>
        </div>
        <div className="header-right">
          <button type="button" className="topbar-action header-save" onClick={() => setScreen("save")}>저장</button>
          {simulation && (
            <span
              className={`ws-indicator ${connected ? "connected" : "disconnected"}`}
              title={connected ? "실시간 연결됨" : "연결 끊김"}
            >●</span>
          )}
          <button type="button" className="topbar-action" onClick={() => setSharedBrowserOpen(true)}>
            공유 설정 둘러보기
          </button>
          <div className="profile"><span>{auth.user.display_name}</span><small>@{auth.user.username}</small></div>
        </div>
      </header>
      <main className="simulation-stage">
        {sharedBrowserOpen ? (
          <SharedBrowser
            token={auth.access_token}
            recentShare={recentShare}
            onImported={handleImported}
            onClose={() => setSharedBrowserOpen(false)}
          />
        ) : (
        <>
        <section className="workspace sim-workspace">
            <div className="panel agent-list sim-left">
              <h1>
                {simulation.name}
                {isImported && <span className="imported-badge">가져온 Simulation</span>}
              </h1>
              <p className="agent-count">Agent {agents.length}명</p>
              <input
                type="search"
                aria-label="Agent 검색"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Agent 검색"
              />
              <div className="agent-type-filter" role="group" aria-label="Agent 종류 필터">
                <button type="button" onClick={() => setAgentTypeFilter("전체")}>전체</button>
                <button type="button" onClick={() => setAgentTypeFilter("학생")}>학생</button>
                <button type="button" onClick={() => setAgentTypeFilter("교수")}>교수</button>
              </div>
              {loading && <p className="message">Agent를 불러오는 중...</p>}
              {error && <p className="message error" role="alert">{error}</p>}
              {error && <button type="button" onClick={() => loadAgents(simulation.id)}>Agent 다시 불러오기</button>}
              {!loading && !error && agents.length === 0 && <p className="message">표시할 Agent가 없습니다.</p>}
              {filteredAgents.map((agent) => (
                <button
                  data-agent-id={agent.id}
                  className={selectedAgent?.id === agent.id ? "agent active" : "agent"}
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent)}
                >
                  <span className="agent-portrait" data-agent-name={agent.name} aria-hidden="true" />
                  <span className="agent-list-copy"><b>{agent.name}</b><small data-location={locationLabel(agent.location)}>{agent.mbti_type}</small></span>
                  {agent.id === personaAgentId && <span className="persona-tag">Persona</span>}
                </button>
              ))}
            </div>

            <div className="runtime-persona-setup">
              <UserPersonaSetup
                simulationId={simulation.id}
                students={students}
                token={auth.access_token}
                onSaved={(result) => setPersonaAgentId(result.agent_id)}
              />
            </div>

            <div className="panel agent-detail sim-right">
              <InspectorPanel
                agent={selectedAgent}
                simulationId={simulation?.id}
                token={auth?.access_token}
                currentTick={lastTick?.current_tick}
                onClose={() => setSelectedAgent(null)}
              />
              {selectedAgent && (
                <button type="button" className="relationship-modal-btn" onClick={() => setShowRelationshipModal(true)}>관계 보기</button>
              )}
            </div>

            {/* Tick 실행 및 결과 */}
            <div className={`panel tick-panel utility-panel${tickLoading || tickResult || tickError ? " is-open" : ""}`}>
              <h2>Tick</h2>

              {tickError && (
                <p
                  className={`message error tick-error-${tickError.type.toLowerCase()}`}
                  role="alert"
                >
                  {tickError.message}
                </p>
              )}

              {tickError && tickError.type !== "AUTH" && (
                <button
                  type="button"
                  onClick={runTick}
                  disabled={tickLoading}
                >
                  다시 시도
                </button>
              )}

              {tickFailed && (
                <p className="message error" role="alert">
                  Tick이 완료되지 않았습니다 (상태:{" "}
                  {tickResult.status}).
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
                      이번 Tick에서 표시할 Agent 행동 결과가
                      없습니다.
                    </p>
                  ) : (
                    <ul className="agent-result-list">
										  {agentResults.map((agentResult) => {
										    const status = agentResult.runtime_status;
										    return (
										      <li key={agentResult.agent_id} className={`agent-result status-${status?.toLowerCase()}`}>
										        <b>{agentResult.agent_name ?? agentResult.agent_id}</b>
										        <span className={`runtime-status runtime-status-${status?.toLowerCase()}`}>
										          {status?.toUpperCase() === "PROPOSED" && "정상 진행"}
										          {status?.toUpperCase() === "FALLBACK" && "재시도 실패 → Fallback 적용"}
										          {status?.toUpperCase() === "SKIPPED" && "이번 Tick 미참여"}
										        </span>
										        {status?.toUpperCase() === "SKIPPED" ? (
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
										        {status?.toUpperCase() === "FALLBACK" && (
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

                  {tickResult.relationship_deltas?.length > 0 && (
                    <section className="relationship-delta-summary">
                      <h4>관계 변화</h4>
                    </section>
                  )}

                </div>
              )}
            </div>
            <div className="panel management-panel utility-panel">
              <h2>관리</h2>
              <div className="management-tabs">
                <button
                  type="button"
                  aria-pressed={managementView === "settings"}
                  onClick={() => setManagementView("settings")}
                >
                  설정
                </button>
                <button
                  type="button"
                  aria-pressed={managementView === "replay"}
                  onClick={() => setManagementView("replay")}
                >
                  Replay
                </button>
                <button
                  type="button"
                  aria-pressed={managementView === "snapshot"}
                  onClick={() => setManagementView("snapshot")}
                >
                  Snapshot
                </button>
                <button
                  type="button"
                  aria-pressed={managementView === "sharing"}
                  onClick={() => setManagementView("sharing")}
                >
                  공유
                </button>
              </div>

              {managementView === "settings" && (
                <SettingsPanel
                  token={auth.access_token}
                  simulationId={simulation.id}
                  simulationStatus={simulation.status}
                />
              )}
              {managementView === "replay" && (
                <ReplayPanel token={auth.access_token} simulationId={simulation.id} />
              )}
              {managementView === "snapshot" && (
                <SnapshotPanel token={auth.access_token} simulationId={simulation.id} />
              )}
              {managementView === "sharing" && (
                <SharingPanel
                  token={auth.access_token}
                  simulationId={simulation.id}
                  simulationStatus={simulation.status}
                  onShareCreated={setRecentShare}
                  onShareCancelled={(shareId) => {
                    setRecentShare((current) => current?.id === shareId ? null : current);
                  }}
                />
              )}
            </div>

            <div className="panel school-map-panel map-view-panel">
              <SchoolMap
                agents={agents}
                agentActions={agentActions}
                simulationId={simulation.id}
                token={auth.access_token}
                onAgentSelect={setSelectedAgent}
              />
            </div>

            <div className="panel relationship-panel">
              <h4>관계 그래프</h4>
            </div>

          </section>
          <EventLogPanel
            eventLog={eventLog}
            agentNames={agentNameById}
            onAgentSelect={handleEventAgentSelect}
          />
        </>
        )}
      </main>
      {showInspectorModal && selectedAgent && (
        <div role="dialog" aria-label="Agent Inspector" className="inspector-modal-backdrop" onClick={() => setShowInspectorModal(false)}>
          <div className="inspector-modal" onClick={(e) => e.stopPropagation()}>
            <h2>Agent Inspector</h2>
            <button type="button" onClick={() => setShowInspectorModal(false)}>Inspector 닫기</button>
            <dl>
              <dt>이름</dt><dd>{selectedAgent.name}</dd>
              <dt>종류</dt><dd>{selectedAgent.agent_type}</dd>
              <dt>MBTI</dt><dd>{selectedAgent.mbti_type}</dd>
            </dl>
          </div>
        </div>
      )}
      {showRelationshipModal && selectedAgent && (
        <RelationshipModal
          selectedAgent={selectedAgent}
          agents={agents}
          auth={auth}
          onSelectAgent={(agent) => setSelectedAgent(agent)}
          onClose={() => setShowRelationshipModal(false)}
        />
      )}
    </div>
  );
}
