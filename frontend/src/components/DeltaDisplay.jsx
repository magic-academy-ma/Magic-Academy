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
    after_preview,
    reason,
    rule_id,
    source_agent_id,
    target_agent_id,
  } = effect;
  const color = getDeltaColor(metric, delta);
  const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "▬";
  const sign = delta > 0 ? `+${delta}` : `${Math.abs(delta)}`;
  const isRelationship = isRelationshipEffect(effect);
  const tooltip = [reason, rule_id ? `rule: ${rule_id}` : null]
    .filter(Boolean)
    .join("\n");

  return (
    <div
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
          {source_agent_id}→{target_agent_id}
        </span>
      )}
      <span style={{ color: "#3b3d42", fontWeight: 600 }}>
        {METRIC_LABEL_KO[metric] ?? metric}
      </span>
      <span style={{ color: color.fg, fontWeight: 700 }}>
        {arrow} {sign}
      </span>
      {!compact && (
        <span style={{ color: "#9a9da3" }}>
          {before} → {after_preview}
          <sup style={{ marginLeft: 3, color: "#c7c9cd", fontSize: 9 }}>
            preview
          </sup>
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

const FIXTURE = [
  {
    effect_id: "sim-20260721-01:42:3:reaction:TRUST_UP:7",
    source_type: "AGENT_REACTION",
    source_id: "3",
    rule_id: "REL_SIGNAL_TRUST_UP_MEDIUM",
    target_type: "RELATIONSHIP",
    source_agent_id: 3,
    target_agent_id: 7,
    metric: "trust",
    delta: 3,
    before: 21,
    after_preview: 24,
    reason: "TALK의 MEDIUM TRUST_UP 반응",
  },
  {
    effect_id: "sim-20260721-01:42:3:reaction:TENSION_UP:7",
    source_type: "AGENT_REACTION",
    source_id: "3",
    rule_id: "REL_SIGNAL_TENSION_UP_LOW",
    target_type: "RELATIONSHIP",
    source_agent_id: 7,
    target_agent_id: 3,
    metric: "tension",
    delta: 2,
    before: 20,
    after_preview: 22,
    reason: "의식 실패로 긴장 고조",
  },
  {
    effect_id: "sim-20260721-01:42:3:state:FATIGUE_UP",
    source_type: "AGENT_REACTION",
    source_id: "3",
    rule_id: "STATE_FATIGUE_RITUAL_PARTICIPATION",
    target_type: "AGENT_STATE",
    source_agent_id: 3,
    target_agent_id: null,
    metric: "fatigue",
    delta: 8,
    before: 30,
    after_preview: 38,
    reason: "장시간 의식 참여로 피로 누적",
  },
  {
    effect_id: "sim-20260721-01:42:3:reaction:DEPENDENCY_UP:7",
    source_type: "AGENT_REACTION",
    source_id: "3",
    rule_id: "REL_SIGNAL_DEPENDENCY_UP_LOW",
    target_type: "RELATIONSHIP",
    source_agent_id: 3,
    target_agent_id: 7,
    metric: "dependency",
    delta: 4,
    before: 10,
    after_preview: 14,
    reason: "위기 상황에서 상대에게 의존 증가 (valence 확인 필요)",
  },
];

export default function DeltaDisplay() {
  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
        Delta 표시 (mock)
      </h3>
      <DeltaGroup effects={FIXTURE} />
    </div>
  );
}