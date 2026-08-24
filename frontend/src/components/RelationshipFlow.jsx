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
          <DeltaGroup effects={data?.effects} compact />
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const edgeTypes = { delta: DeltaEdge };

export default function RelationshipFlow({ nodes = [], edges = [] }) {
  const hasChanges = edges.some((e) => e.data?.effects?.length > 0);

  return (
    <div style={{ width: "100%", height: 400, position: "relative" }}>
      <ReactFlow nodes={nodes} edges={edges} edgeTypes={edgeTypes} fitView>
        <Background />
        <Controls />
      </ReactFlow>

      {!hasChanges && (
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
