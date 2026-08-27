import "./EventLogPanel.css";

export default function EventLogPanel({ eventLog = [], agentNames = {}, onAgentSelect }) {
  function handleItemClick(involvedAgents) {
    const firstId = involvedAgents?.[0];
    if (firstId && onAgentSelect) onAgentSelect(firstId);
  }

  function handleItemKeyDown(e, involvedAgents) {
    if (e.key === "Enter" || e.key === " ") handleItemClick(involvedAgents);
  }

  return (
    <div className="panel event-log-panel sim-eventlog">
      <div className="event-log-header">
        <h2>Event Log</h2>
        <span>실시간 기록</span>
      </div>
      {eventLog.length === 0 ? (
        <p className="message">수신된 이벤트가 없습니다.</p>
      ) : (
        <ul className="event-log-list">
          {eventLog.map((event) => {
            const clickable = event.involved_agents?.length > 0;
            return (
              <li
                key={event.id}
                className={`event-log-item${clickable ? " clickable" : ""}`}
                onClick={() => handleItemClick(event.involved_agents)}
                role={clickable ? "button" : undefined}
                tabIndex={clickable ? 0 : undefined}
                onKeyDown={(e) => handleItemKeyDown(e, event.involved_agents)}
              >
                <span className="event-tick">Tick {event.tick}</span>
                <span className="event-description">{event.description}</span>
                {event.involved_agents?.length > 0 && (
                  <span className="event-agents">
                    {event.involved_agents.map((id) => agentNames[id] ?? id).join(", ")}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
