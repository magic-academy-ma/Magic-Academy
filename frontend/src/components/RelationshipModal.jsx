import { useState, useEffect, useMemo } from "react";
import { apiRequest } from "../api/client.js";
import "./RelationshipModal.css";

// ── Layout constants ──────────────────────────────────────────────
const GRAPH_W   = 1060;
const GRAPH_H   = 530;
const CENTER    = { x: GRAPH_W / 2, y: GRAPH_H / 2 };
const RADIUS    = Math.min(GRAPH_W, GRAPH_H) * 0.35;
const SEL_R     = 30;
const NORM_R    = 24;
const ARROW_GAP = 7;

const EDGE_CONFIG = {
  favor:   { stroke: "rgba(92,230,122,0.55)",  dash: null,    fill: "rgba(92,230,122,0.7)",  sw: 2   },
  trust:   { stroke: "rgba(52,179,199,0.55)",  dash: "5 2",   fill: "rgba(52,179,199,0.7)",  sw: 2   },
  tension: { stroke: "rgba(219,76,76,0.55)",   dash: "3 3",   fill: "rgba(219,76,76,0.7)",   sw: 2   },
  dep:     { stroke: "rgba(212,178,111,0.5)",  dash: null,    fill: "rgba(212,178,111,0.7)", sw: 1.5 },
  neutral: { stroke: "rgba(169,174,199,0.25)", dash: null,    fill: "rgba(169,174,199,0.4)", sw: 1   },
};

const FILTER_CHIPS = [
  { key: "all",     label: "전체",        cls: "" },
  { key: "favor",   label: "호감·친밀",   cls: "chip-favor" },
  { key: "trust",   label: "신뢰",        cls: "chip-trust" },
  { key: "tension", label: "긴장·라이벌", cls: "chip-tension" },
  { key: "dep",     label: "의존",        cls: "chip-dep" },
];

const SCOPE_CHIPS = [
  { key: "all",    label: "전체" },
  { key: "focus",  label: "선택 Agent 중심" },
  { key: "direct", label: "직접 관계만" },
];

const LEGEND_ITEMS = [
  { label: "호감·친밀",   lineStyle: { background: "#5CE67A" } },
  { label: "신뢰",        lineStyle: { background: "var(--c-inspector)" } },
  { label: "긴장·라이벌", lineStyle: { borderTop: "2px dashed var(--c-critical)", background: "transparent" } },
  { label: "의존",        lineStyle: { background: "var(--c-cream)" } },
  { label: "중립",        lineStyle: { background: "rgba(169,174,199,0.3)" } },
];

function classifyEdge(rel) {
  if ((rel.tension    ?? 0) > 50 || (rel.rivalry    ?? 0) > 50) return "tension";
  if ((rel.trust      ?? 0) > 50)                                return "trust";
  if ((rel.affection  ?? 0) > 50 || (rel.closeness  ?? 0) > 50) return "favor";
  if ((rel.dependency ?? 0) > 50)                                return "dep";
  return "neutral";
}

function computePositions(centerId, agents) {
  const positions = { [centerId]: { ...CENTER } };
  const others = agents.filter(a => a.id !== centerId);
  others.forEach((agent, i) => {
    const angle = (2 * Math.PI * i / others.length) - Math.PI / 2;
    positions[agent.id] = {
      x: CENTER.x + RADIUS * Math.cos(angle),
      y: CENTER.y + RADIUS * Math.sin(angle),
    };
  });
  return positions;
}

export default function RelationshipModal({
  selectedAgent: initialAgent,
  agents,
  auth,
  onSelectAgent,
  onClose,
}) {
  const [localSel, setLocalSel]    = useState(initialAgent);
  const [edges, setEdges]          = useState([]);
  const [activeFilter, setFilter]  = useState("all");
  const [scope, setScope]          = useState("all");
  const [selectedEdge, setSelEdge] = useState(null);

  useEffect(() => {
    if (!agents.length || !auth) return;
    Promise.allSettled(
      agents.map(agent =>
        apiRequest(`/v1/agents/${agent.id}/relationships`, {
          token: auth.access_token,
        })
      )
    ).then(results => {
      const all = [];
      results.forEach((r, i) => {
        if (r.status === "fulfilled") {
          (r.value ?? []).forEach(rel =>
            all.push({ sourceId: agents[i].id, ...rel })
          );
        }
      });
      setEdges(all);
    });
  }, [agents, auth]);

  const positions = useMemo(
    () => computePositions(localSel.id, agents),
    [localSel.id, agents]
  );

  const agentById = useMemo(
    () => Object.fromEntries(agents.map(a => [a.id, a])),
    [agents]
  );

  const directIds = useMemo(() => {
    const s = new Set([localSel.id]);
    edges.forEach(e => {
      if (e.sourceId        === localSel.id) s.add(e.target_agent_id);
      if (e.target_agent_id === localSel.id) s.add(e.sourceId);
    });
    return s;
  }, [localSel.id, edges]);

  function edgeOpacity(e, type) {
    if (activeFilter !== "all" && type !== activeFilter) return 0.1;
    if (scope === "focus") {
      return (e.sourceId === localSel.id || e.target_agent_id === localSel.id) ? 1 : 0.06;
    }
    if (scope === "direct") {
      const ok =
        directIds.has(e.sourceId) &&
        directIds.has(e.target_agent_id) &&
        (e.sourceId === localSel.id || e.target_agent_id === localSel.id);
      return ok ? 1 : 0.06;
    }
    return 1;
  }

  function nodeOpacity(agentId) {
    return scope === "direct" && !directIds.has(agentId) ? 0.3 : 1;
  }

  function handleNodeClick(agent) {
    setLocalSel(agent);
    setSelEdge(null);
    onSelectAgent(agent);
  }

  function renderEdges() {
    return edges.flatMap((rel, idx) => {
      const p1 = positions[rel.sourceId];
      const p2 = positions[rel.target_agent_id];
      if (!p1 || !p2) return [];

      const type = classifyEdge(rel);
      const opacity = edgeOpacity(rel, type);
      const { stroke, dash, sw } = EDGE_CONFIG[type];

      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const len = Math.sqrt(dx * dx + dy * dy);
      if (len < 1) return [];

      const ux = dx / len;
      const uy = dy / len;
      const ox = (-dy / len) * 5;
      const oy = ( dx / len) * 5;

      const r1 = rel.sourceId       === localSel.id ? SEL_R : NORM_R;
      const r2 = rel.target_agent_id === localSel.id ? SEL_R : NORM_R;

      const x1a = p1.x + ux * r1 + ox,            y1a = p1.y + uy * r1 + oy;
      const x2a = p2.x - ux * (r2 + ARROW_GAP) + ox, y2a = p2.y - uy * (r2 + ARROW_GAP) + oy;

      const x1b = p2.x - ux * r2 - ox,            y1b = p2.y - uy * r2 - oy;
      const x2b = p1.x + ux * (r1 + ARROW_GAP) - ox, y2b = p1.y + uy * (r1 + ARROW_GAP) - oy;

      const lineProps = {
        stroke,
        strokeWidth: sw,
        strokeDasharray: dash ?? undefined,
        strokeLinecap: "round",
        style: { opacity, cursor: "pointer", transition: "opacity 0.2s" },
        onClick: () => setSelEdge(rel),
      };

      return [
        <line key={`${idx}-ab`} className={`edge-base edge-${type}`}
          x1={x1a} y1={y1a} x2={x2a} y2={y2a}
          markerEnd={`url(#arr-${type})`} {...lineProps}
        />,
        <line key={`${idx}-ba`} className={`edge-base edge-${type}`}
          x1={x1b} y1={y1b} x2={x2b} y2={y2b}
          markerEnd={`url(#arr-${type})`} {...lineProps}
        />,
      ];
    });
  }

  return (
    <div className="rel-modal" onClick={onClose}>
      <div
        role="dialog"
        aria-label="관계 그래프"
        aria-modal="true"
        className="rel-modal__inner"
        onClick={e => e.stopPropagation()}
      >
        <div className="rel-modal__header">
          <span className="rel-modal__title">관계 그래프</span>
          <span className="rel-modal__selected-label">{localSel.name} 선택 중</span>
          <div className="rel-filter-chips">
            {FILTER_CHIPS.map(({ key, label, cls }) => (
              <button
                key={key}
                type="button"
                className={["chip", cls, activeFilter === key ? "active" : ""].filter(Boolean).join(" ")}
                onClick={() => setFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="rel-modal__close"
            aria-label="닫기"
            onClick={onClose}
          >
            <svg width="10" height="10" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M3 3L11 11M11 3L3 11" stroke="#a4b5d6" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="scope-bar">
          <span className="scope-label">보이는 Agent</span>
          {SCOPE_CHIPS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className={["chip", "scope-chip", scope === key ? "active" : ""].filter(Boolean).join(" ")}
              onClick={() => setScope(key)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="rel-modal__body">
          <svg
            className="rm-svg"
            viewBox={`0 0 ${GRAPH_W} ${GRAPH_H}`}
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <defs>
              {Object.entries(EDGE_CONFIG).map(([type, { fill }]) => (
                <marker
                  key={type}
                  id={`arr-${type}`}
                  markerWidth="7"
                  markerHeight="7"
                  refX="5"
                  refY="3"
                  orient="auto"
                >
                  <path d="M0,0 L0,6 L7,3 z" fill={fill} />
                </marker>
              ))}
            </defs>
            {renderEdges()}
          </svg>

          {agents.map(agent => {
            const pos = positions[agent.id];
            if (!pos) return null;
            const isSel = agent.id === localSel.id;
            const r     = isSel ? SEL_R : NORM_R;
            return (
              <div
                key={agent.id}
                className={`graph-node${isSel ? " selected" : ""}`}
                data-id={agent.id}
                data-testid={`graph-node-${agent.id}`}
                style={{ left: `${pos.x - r}px`, top: `${pos.y - r}px`, opacity: nodeOpacity(agent.id) }}
                role="button"
                tabIndex={0}
                aria-label={`${agent.name} 선택`}
                aria-pressed={isSel}
                onClick={() => handleNodeClick(agent)}
                onKeyDown={e => {
                  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleNodeClick(agent); }
                }}
              >
                <AgentPortrait agent={agent} size={r * 2} />
                <div className="graph-node__name">
                  {agent.name}{agent.mbti_type ? ` · ${agent.mbti_type}` : ""}
                </div>
              </div>
            );
          })}
        </div>

        <div className="rel-modal__footer">
          <ul className="rel-legend" role="list" aria-label="범례">
            {LEGEND_ITEMS.map(({ label, lineStyle }) => (
              <li key={label} className="rel-legend-item">
                <div className="rel-legend-line" style={lineStyle} aria-hidden="true" />
                <span>{label}</span>
              </li>
            ))}
          </ul>
          {selectedEdge && <EdgeDetail edge={selectedEdge} agentById={agentById} />}
        </div>
      </div>
    </div>
  );
}

function AgentPortrait({ agent, size }) {
  const [err, setErr] = useState(false);
  const src = `/assets/character/${agent.name}_${agent.mbti_type ?? ""}.png`;
  return err ? (
    <div
      className="graph-node__portrait graph-node__portrait--fallback"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {agent.name.slice(0, 2)}
    </div>
  ) : (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      className="graph-node__portrait"
      style={{ width: size, height: size }}
      onError={() => setErr(true)}
    />
  );
}

function EdgeDetail({ edge, agentById }) {
  const src = agentById[edge.sourceId];
  const tgt = agentById[edge.target_agent_id];
  if (!src || !tgt) return null;
  const stats = [
    ["호감도", edge.affection],
    ["친밀도", edge.closeness],
    ["신뢰도", edge.trust],
    ["긴장도", edge.tension],
    ["경쟁",   edge.rivalry],
    ["의존도", edge.dependency],
  ].filter(([, v]) => v !== undefined && v !== null);
  const bg = a => `url(/assets/character/${a.name}_${a.mbti_type ?? ""}.png)`;
  return (
    <div className="rel-detail">
      <div className="rel-detail-pair">
        <div className="rel-detail-portrait" style={{ backgroundImage: bg(src) }} role="img" aria-label={src.name} />
        <div className="rel-arrow">↔</div>
        <div className="rel-detail-portrait" style={{ backgroundImage: bg(tgt) }} role="img" aria-label={tgt.name} />
      </div>
      <div className="rel-stats">
        {stats.map(([key, val]) => (
          <div key={key} className="rel-stat-row">
            <span className="rel-stat-key">{key}</span>
            <span className="rel-stat-val">{val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
