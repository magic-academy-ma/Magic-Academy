import { useState } from "react";
import "./SchoolMap.css";

const SPACES = [
  { code: "classroom",  name: "교실",   emoji: "🏫", top: "28%", left: "38%", bgImage: "/assets/classroom.png" },
  { code: "restaurant", name: "식당",   emoji: "🍽️", top: "48%", left: "62%", bgImage: "/assets/restaurant.png" },
  { code: "library",    name: "도서관", emoji: "📚", top: "62%", left: "30%", bgImage: "/assets/library.png" },
  { code: "lab",        name: "연구실", emoji: "⚗️", top: "30%", left: "68%", bgImage: "/assets/lab.png" },
  { code: "dormitory",  name: "기숙사", emoji: "🏠", top: "65%", left: "58%", bgImage: "/assets/dormitory.png" },
];

const ACTION_LABEL = {
  STUDYING:        "공부중",
  EATING:          "식사중",
  ATTENDING_CLASS: "수업중",
  RESTING:         "휴식중",
  SOCIALIZING:     "대화중",
  READING:         "독서중",
  RESEARCHING:     "연구중",
  SLEEPING:        "취침중",
  EXERCISING:      "운동중",
  WORKING:         "활동중",
};

function actionLabel(type) {
  if (!type) return null;
  return ACTION_LABEL[type.toUpperCase()] ?? type;
}

// 지도 토큰은 시각적 보조 수단 — 주 Agent 선택은 좌측 목록 패널 사용.
function AgentDot({ agent, action, spaceName, selected, onClick }) {
  const [imgError, setImgError] = useState(false);
  const src = !imgError && agent.name && agent.mbti_type
    ? `/assets/character/${agent.name}_${agent.mbti_type}.png`
    : null;
  const label = actionLabel(action?.action_type ?? agent.state?.current_action);
  const initials = agent.name.slice(0, 2);

  function handleKeyDown(e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick(agent);
    }
  }

  return (
    <div
      className={`map-agent-dot-sm${selected ? " selected" : ""}`}
      tabIndex={0}
      title={`${spaceName} — ${agent.name}${label ? ` (${label})` : ""}`}
      onClick={(e) => { e.stopPropagation(); onClick(agent); }}
      onKeyDown={handleKeyDown}
    >
      {src ? (
        <img src={src} alt={agent.name} onError={() => setImgError(true)} draggable={false} />
      ) : (
        <span aria-hidden="true">{initials}</span>
      )}
    </div>
  );
}

function MapView({ agents, agentActions, activeSpace, selectedAgentId, onPinClick, onAgentClick }) {
  function getOccupants(spaceName) {
    return agents.filter((agent) => {
      const liveLocation = agentActions?.get(agent.id)?.location;
      const locationName = liveLocation?.name ?? agent.location?.name;
      return locationName === spaceName;
    });
  }

  return (
    <div className="school-map-mapview" aria-label="학교 전체 맵">
      <div className="map-bg" aria-hidden="true" />
      <div className="map-vignette" aria-hidden="true" />
      {SPACES.map((space) => {
        const occupants = getOccupants(space.name);
        const isActive = activeSpace === space.code;
        return (
          <div
            key={space.code}
            className={`map-zone-pin${isActive ? " active" : ""}`}
            style={{ top: space.top, left: space.left }}
            role="button"
            tabIndex={0}
            aria-label={`${space.name}${occupants.length > 0 ? `, ${occupants.length}명` : ""}`}
            aria-pressed={isActive}
            onClick={() => onPinClick(space.code)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPinClick(space.code); } }}
          >
            {occupants.length > 0 && (
              <div className="map-agent-cluster" aria-label={`${space.name} 내 Agent`}>
                {occupants.map((agent) => (
                  <AgentDot
                    key={agent.id}
                    agent={agent}
                    action={agentActions?.get(agent.id)}
                    spaceName={space.name}
                    selected={selectedAgentId === agent.id}
                    onClick={onAgentClick}
                  />
                ))}
              </div>
            )}
            <div className="map-zone-pin__ring">
              <span className="map-zone-pin__icon" aria-hidden="true">{space.emoji}</span>
            </div>
            <div className="map-zone-pin__label-box">
              <div className="map-zone-pin__name">{space.name}</div>
              <div className="map-zone-pin__count">
                {occupants.length > 0 ? `${occupants.length}명 재실` : "비어 있음"}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CardView({ agents, agentActions, activeSpace, selectedAgentId, onCardClick, onAgentClick }) {
  function getOccupants(spaceName) {
    return agents.filter((agent) => {
      const liveLocation = agentActions?.get(agent.id)?.location;
      const locationName = liveLocation?.name ?? agent.location?.name;
      return locationName === spaceName;
    });
  }

  return (
    <div className="school-map-cardview" aria-label="학교 구역 카드">
      {SPACES.map((space) => {
        const occupants = getOccupants(space.name);
        const isActive = activeSpace === space.code;
        return (
          <div
            key={space.code}
            className={`zone-card${isActive ? " active" : ""}`}
            role="button"
            tabIndex={0}
            aria-label={`${space.name}${occupants.length > 0 ? `, ${occupants.length}명` : ""}`}
            aria-pressed={isActive}
            onClick={() => onCardClick(space.code)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onCardClick(space.code); } }}
          >
            <div
              className="zone-card__bg"
              style={{ backgroundImage: `url('${space.bgImage}')` }}
              aria-hidden="true"
            />
            <div className="zone-card__content">
              <div className="zone-card__tag">{space.code.toUpperCase()}</div>
              <div className="zone-card__name">{space.name}</div>
              {occupants.length > 0 && (
                <span className="zone-card__count">{occupants.length}명</span>
              )}
              <div className="zone-card__agents" aria-label={`${space.name} 내 Agent`}>
                {occupants.length > 0 ? (
                  occupants.map((agent) => (
                    <AgentDot
                      key={agent.id}
                      agent={agent}
                      action={agentActions?.get(agent.id)}
                      spaceName={space.name}
                      selected={selectedAgentId === agent.id}
                      onClick={onAgentClick}
                    />
                  ))
                ) : (
                  <span className="zone-card__empty">Agent 없음</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function SchoolMap({ agents, agentActions, simulationId, token, onAgentSelect }) {
  const [view, setView] = useState("map");
  const [activeSpace, setActiveSpace] = useState(null);
  const [selectedAgentId, setSelectedAgentId] = useState(null);

  function handleAgentClick(agent) {
    setSelectedAgentId(agent.id);
    onAgentSelect(agent);
  }

  function handleSpaceClick(code) {
    setActiveSpace(activeSpace === code ? null : code);
  }

  return (
    <div className="school-map-wrapper" aria-label="학교 공간 맵">
      <div className="school-map-toolbar">
        <div className="view-toggle-group" role="group" aria-label="뷰 전환">
          <button
            className={`view-toggle-btn${view === "map" ? " active" : ""}`}
            onClick={() => setView("map")}
            aria-pressed={view === "map"}
          >
            전체 뷰
          </button>
          <button
            className={`view-toggle-btn${view === "card" ? " active" : ""}`}
            onClick={() => setView("card")}
            aria-pressed={view === "card"}
          >
            4분할 뷰
          </button>
        </div>
      </div>

      {view === "map" ? (
        <MapView
          agents={agents}
          agentActions={agentActions}
          activeSpace={activeSpace}
          selectedAgentId={selectedAgentId}
          onPinClick={handleSpaceClick}
          onAgentClick={handleAgentClick}
        />
      ) : (
        <CardView
          agents={agents}
          agentActions={agentActions}
          activeSpace={activeSpace}
          selectedAgentId={selectedAgentId}
          onCardClick={handleSpaceClick}
          onAgentClick={handleAgentClick}
        />
      )}
    </div>
  );
}
