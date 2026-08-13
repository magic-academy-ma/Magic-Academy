import React from "react";
import {
  ReactFlow,
  Background,
  Controls,
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { DeltaGroup } from "./DeltaDisplay";

// --- delta를 보여주는 커스텀 edge ---
function DeltaEdge({ id, sourceX, sourceY, targetX, targetY, data }) {
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  return (
    <>
      <BaseEdge id={id} path={edgePath} />
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: "all",
          }}
        >
          <DeltaGroup effects={data.effects} compact />
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const edgeTypes = { delta: DeltaEdge };

// --- agent 2명 (mock) ---
const nodes = [
  {
    id: "3",
    position: { x: 0, y: 100 },
    data: { label: "Agent 3" },
  },
  {
    id: "7",
    position: { x: 300, y: 100 },
    data: { label: "Agent 7" },
  },
];

// --- 그 사이 관계 edge (mock delta 포함) ---
const edges = [
  {
    id: "e3-7",
    source: "3",
    target: "7",
    type: "delta",
    data: {
      effects: [
        {
          effect_id: "sim-20260721-01:42:3:reaction:TRUST_UP:7",
          target_type: "RELATIONSHIP",
          source_agent_id: 3,
          target_agent_id: 7,
          metric: "trust",
          delta: 3,
          before: 21,
          after_preview: 24,
          reason: "TALK의 MEDIUM TRUST_UP 반응",
          rule_id: "REL_SIGNAL_TRUST_UP_MEDIUM",
        },
        {
          effect_id: "sim-20260721-01:42:7:reaction:TENSION_UP:3",
          target_type: "RELATIONSHIP",
          source_agent_id: 7,
          target_agent_id: 3,
          metric: "tension",
          delta: 2,
          before: 20,
          after_preview: 22,
          reason: "의식 실패로 긴장 고조",
        },
      ],
    },
  },
];
export default function RelationshipFlow({ edges: edgesProp = edges }) {
  const hasEdges = edgesProp.length > 0;

  return (
    <div style={{ width: "100%", height: 400, position: "relative" }}>
      <ReactFlow nodes={nodes} edges={edgesProp} edgeTypes={edgeTypes} fitView>
        <Background />
        <Controls />
      </ReactFlow>

      {!hasEdges && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: 12,
            color: "#9a9da3",
            background: "#fafbfc",
            border: "1px solid #e1e3e6",
            borderRadius: 999,
            padding: "4px 12px",
            pointerEvents: "none",
          }}
        >
          이번 tick에는 관계 변화가 없습니다
        </div>
      )}
    </div>
  );
}