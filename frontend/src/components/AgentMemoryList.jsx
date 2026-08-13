// AgentMemoryList.jsx
// Issue #73 - Task 4
// 위치: frontend/src/components/AgentMemoryList.jsx
//
// 초안: retrieved_memories 실제 값 확정 전, 더미 데이터로 UI만 구성.
// 스키마 확정 후 DUMMY_DATA를 제거하고 실제 API 응답(props)으로 교체하세요.

import React from "react";

// 개발용 더미 데이터 - 실제 연결 시 제거
const DUMMY_DATA = [
  {
    agent_id: "agent_001",
    memory_ids_passed: ["mem_001", "mem_002"],
    memories: [
      {
        id: "mem_001",
        content: "조별 과제를 성공적으로 마쳤다.",
        created_tick: 42,
        event_id: "event_010",
      },
    ],
  },
  {
    agent_id: "agent_002",
    memory_ids_passed: [],
    memories: [], // Memory 없는 Agent 케이스
  },
];

function AgentMemoryCard({ data }) {
  return (
    <div className="agent-memory-card" data-agent-id={data.agent_id}>
      <h4>{data.agent_id}</h4>
      {data.memories.length === 0 ? (
        <p className="empty-state">사용된 기억 없음</p>
      ) : (
        <ul>
          {data.memories.map((m) => (
            <li key={m.id}>
              <div className="memory-content">{m.content}</div>
              <div className="memory-meta">
                tick #{m.created_tick}
                {m.event_id ? ` · event: ${m.event_id}` : ""}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function AgentMemoryList({ data = DUMMY_DATA }) {
  return (
    <div className="agent-memory-list">
      {data.map((d) => (
        <AgentMemoryCard key={d.agent_id} data={d} />
      ))}
    </div>
  );
}