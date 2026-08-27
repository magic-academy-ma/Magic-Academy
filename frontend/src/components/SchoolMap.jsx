import "./SchoolMap.css";

const SPACES = [
  { code: "classroom",  name: "교실",   emoji: "🏫" },
  { code: "restaurant", name: "식당",   emoji: "🍽️" },
  { code: "library",    name: "도서관", emoji: "📚" },
  { code: "lab",        name: "연구실", emoji: "⚗️" },
  { code: "dormitory",  name: "기숙사", emoji: "🛏️" },
];

const ACTION_LABEL = {
  STUDYING:          "공부중",
  EATING:            "식사중",
  ATTENDING_CLASS:   "수업중",
  RESTING:           "휴식중",
  SOCIALIZING:       "대화중",
  READING:           "독서중",
  RESEARCHING:       "연구중",
  SLEEPING:          "취침중",
  EXERCISING:        "운동중",
  WORKING:           "활동중",
};

function actionLabel(type) {
  if (!type) return null;
  return ACTION_LABEL[type.toUpperCase()] ?? type;
}

// 지도 토큰은 시각적 보조 수단 — 주 Agent 선택은 좌측 목록 패널 사용.
// <button> 대신 tabIndex div를 사용해 좌측 패널의 버튼 접근성 트리와 분리한다.
function AgentToken({ agent, action, spaceName, onClick }) {
  const initials = agent.name.slice(0, 2);
  const label = actionLabel(action?.action_type ?? agent.state?.current_action);

  function handleKeyDown(e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick(agent);
    }
  }

  return (
    <div
      className="agent-token"
      tabIndex={0}
      title={`${spaceName} — ${agent.name}${label ? ` (${label})` : ""}`}
      onClick={() => onClick(agent)}
      onKeyDown={handleKeyDown}
    >
      {label && <span className="action-bubble">{label}</span>}
      <span className="agent-avatar" aria-hidden="true">{initials}</span>
    </div>
  );
}

export default function SchoolMap({ agents, agentActions, onAgentSelect }) {
  return (
    <div className="school-map" aria-label="학교 공간 맵">
      {SPACES.map((space) => {
        const occupants = agents.filter((agent) => {
          const liveLocation = agentActions?.get(agent.id)?.location;
          const locationName = liveLocation?.name ?? agent.location?.name;
          return locationName === space.name;
        });

        return (
          <div key={space.code} className="space-tile" data-code={space.code}>
            {/* 공간명은 CSS content: attr(data-name) 으로만 표시해 DOM 텍스트 충돌 방지 */}
            <div
              className="space-header"
              data-name={space.name}
              aria-label={space.name}
              title={space.name}
            >
              <span aria-hidden="true">{space.emoji}</span>
              {occupants.length > 0 && (
                <span className="occupant-count" aria-label={`${occupants.length}명`}>{occupants.length}</span>
              )}
            </div>
            <div className="space-agents" aria-label={`${space.name} 내 Agent`}>
              {occupants.map((agent) => (
                <AgentToken
                  key={agent.id}
                  agent={agent}
                  action={agentActions?.get(agent.id)}
                  spaceName={space.name}
                  onClick={onAgentSelect}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
