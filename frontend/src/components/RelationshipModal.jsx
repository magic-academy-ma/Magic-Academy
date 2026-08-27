import { useState, useEffect } from "react";
import { apiRequest } from "../api/client.js";
import "./RelationshipModal.css";

export default function RelationshipModal({ selectedAgent, agents, auth, onSelectAgent, onClose }) {
  const [relationships, setRelationships] = useState([]);

  useEffect(() => {
    apiRequest(`/v1/agents/${selectedAgent.id}/relationships`, {
      token: auth.access_token,
    })
      .then((data) => setRelationships(data))
      .catch(() => {});
  }, [selectedAgent.id]);

  const agentById = Object.fromEntries(agents.map((a) => [a.id, a]));

  function handleNodeClick(agentId) {
    const agent = agentById[agentId];
    if (agent) onSelectAgent(agent);
    onClose();
  }

  return (
    <div className="relationship-modal-backdrop" onClick={onClose}>
      <div
        role="dialog"
        aria-label="관계 그래프"
        className="relationship-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relationship-modal-header">
          <h2>관계 그래프</h2>
          <button type="button" onClick={onClose}>닫기</button>
        </div>
        <div className="relationship-modal-body">
          {relationships.map((rel, idx) => {
            const targetAgent = agentById[rel.target_agent_id];
            const targetName = targetAgent?.name ?? String(rel.target_agent_id);
            return (
              <div key={idx} className="relationship-entry">
                <button
                  type="button"
                  className="relationship-node"
                  onClick={() => handleNodeClick(rel.target_agent_id)}
                >
                  {targetName}
                </button>
                <ul className="relationship-metrics">
                  <li>호감도 {rel.affection}</li>
                  <li>친밀도 {rel.closeness}</li>
                  <li>신뢰도 {rel.trust}</li>
                  <li>긴장도 {rel.tension}</li>
                  <li>경쟁 {rel.rivalry}</li>
                  <li>의존도 {rel.dependency}</li>
                </ul>
              </div>
            );
          })}
          {relationships.length === 0 && (
            <p className="message">관계 데이터를 불러오는 중...</p>
          )}
        </div>
      </div>
    </div>
  );
}
