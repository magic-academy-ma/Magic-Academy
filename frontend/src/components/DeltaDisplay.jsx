import React from "react";

const METRIC_VALENCE = {
  trust: "positive",
  affection: "positive",
  closeness: "positive",
  tension: "negative",
  rivalry: "negative",
  dependency: "neutral", // TODO: §4.2 확인 필요

  hunger: "negative",
  fatigue: "negative",
  stress: "negative",
  satisfaction: "positive",
  mood: "positive",
};

const METRIC_LABEL_KO = {
  trust: "신뢰",
  affection: "호감",
  closeness: "친밀도",
  tension: "긴장",
  rivalry: "경쟁심",
  dependency: "의존도",
  hunger: "허기",
  fatigue: "피로",
  stress: "스트레스",
  satisfaction: "만족감",
  mood: "기분",
};

function isRelationshipEffect(effect) {
  if (effect.target_type) return effect.target_type === "RELATIONSHIP";
  return ["trust", "affection", "closeness", "tension", "rivalry", "dependency"].includes(
    effect.metric
  );
}

function getDeltaColor(metric, delta) {
  if (delta === 0) return { fg: "#8b8f97", bg: "#f1f2f4", ring: "#e1e3e6" };

  const valence = METRIC_VALENCE[metric] ?? "neutral";
  if (valence === "neutral") {
    return { fg: "#6b6f76", bg: "#f1f2f4", ring: "#d8dade" };
  }

  const isGood = valence === "positive" ? delta > 0 : delta < 0;
  return isGood
    ? { fg: "#1a7f4e", bg: "#e6f6ee", ring: "#b8e6cc" }
    : { fg: "#c22b2b", bg: "#fdecec", ring: "#f6c6c6" };
}

export function DeltaBadge({ effect, compact = false }) {
  const {
    metric,
    delta,
    before,
    after,
    reason,
    rule_id,
    source_agent_id,
    target_agent_id,
    agent_name,
    source_agent_name,
    target_agent_name,
  } = effect;
  const color = getDeltaColor(metric, delta);
  const committedAfter = after;
  const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "▬";
  const sign = delta > 0 ? `+${delta}` : `${delta}`;
  const isRelationship = isRelationshipEffect(effect);
  const metricLabel = METRIC_LABEL_KO[metric] ?? metric;
  const subject = isRelationship
    ? `${source_agent_name ?? source_agent_id}에서 ${target_agent_name ?? target_agent_id}로`
    : `${agent_name ?? source_agent_id}의`;
  const accessibleLabel = `${subject} ${metricLabel} ${sign}, ${before}에서 ${committedAfter}으로 변화`;
  const tooltip = [reason, rule_id ? `rule: ${rule_id}` : null]
    .filter(Boolean)
    .join("\n");

  return (
    <div
      aria-label={accessibleLabel}
      title={tooltip}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: compact ? "3px 8px" : "5px 10px",
        borderRadius: 999,
        background: color.bg,
        border: `1px solid ${color.ring}`,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        fontSize: compact ? 11 : 12,
        lineHeight: 1,
        cursor: reason ? "help" : "default",
        whiteSpace: "nowrap",
      }}
    >
      <span
        style={{
          fontSize: 9,
          textTransform: "uppercase",
          letterSpacing: 0.4,
          color: "#9a9da3",
        }}
      >
        {isRelationship ? "REL" : "STATE"}
      </span>
      {isRelationship && source_agent_id != null && target_agent_id != null && (
        <span style={{ color: "#b0b3b9", fontSize: 10 }}>
          {source_agent_name ?? source_agent_id}→{target_agent_name ?? target_agent_id}
        </span>
      )}
      {!isRelationship && agent_name && (
        <span style={{ color: "#6b6f76", fontSize: 10 }}>{agent_name}</span>
      )}
      <span style={{ color: "#3b3d42", fontWeight: 600 }}>
        {metricLabel}
      </span>
      <span style={{ color: color.fg, fontWeight: 700 }}>
        {arrow} {sign}
      </span>
      {!compact && (
        <span style={{ color: "#9a9da3" }}>
          {before} → {committedAfter}
        </span>
      )}
    </div>
  );
}

export function DeltaGroup({ effects, compact = false }) {
  if (!effects?.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {effects.map((e) => (
        <DeltaBadge key={e.effect_id} effect={e} compact={compact} />
      ))}
    </div>
  );
}
