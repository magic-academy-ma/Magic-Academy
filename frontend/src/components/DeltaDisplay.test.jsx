import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DeltaBadge, DeltaGroup } from "./DeltaDisplay";

const trustUp = {
  effect_id: "e1",
  target_type: "RELATIONSHIP",
  source_agent_id: 3,
  target_agent_id: 7,
  metric: "trust",
  delta: 3,
  before: 21,
  after_preview: 24,
  reason: "TALK의 MEDIUM TRUST_UP 반응",
};

const tensionUp = {
  effect_id: "e2",
  target_type: "RELATIONSHIP",
  source_agent_id: 7,
  target_agent_id: 3,
  metric: "tension",
  delta: 2,
  before: 20,
  after_preview: 22,
  reason: "긴장 고조",
};

describe("DeltaBadge", () => {
  it("metric 이름과 증감 표시를 렌더링한다", () => {
    render(<DeltaBadge effect={trustUp} />);
    expect(screen.getByText("신뢰")).toBeInTheDocument();
    expect(screen.getByText(/\+3/)).toBeInTheDocument();
  });

  it("delta가 0이면 중립(회색) 표시가 된다", () => {
    const flat = { ...trustUp, delta: 0, after_preview: 21 };
    render(<DeltaBadge effect={flat} />);

    expect(screen.getByText(/0/)).toBeInTheDocument();
  });

  it("delta가 음수이면 절댓값으로 표시된다", () => {
    const down = { ...tensionUp, delta: -2, after_preview: 18 };
    render(<DeltaBadge effect={down} />);
    expect(screen.getByText(/▼\s*2/)).toBeInTheDocument();
  });

  it("negative valence 지표(fatigue) 증가는 경고색으로 표시된다", () => {
    const fatigueUp = {
      effect_id: "e3",
      target_type: "AGENT_STATE",
      metric: "fatigue",
      delta: 8,
      before: 30,
      after_preview: 38,
      reason: "피로 누적",
    };
    render(<DeltaBadge effect={fatigueUp} />);
    expect(screen.getByText("피로")).toBeInTheDocument();
  });

  it("compact 모드에서는 preview 영역이 렌더링되지 않는다", () => {
    render(<DeltaBadge effect={trustUp} compact />);
    expect(screen.queryByText(/preview/)).not.toBeInTheDocument();
  });
});

describe("DeltaGroup", () => {
  it("effect가 여러 개면 모두 렌더링한다", () => {
    render(<DeltaGroup effects={[trustUp, tensionUp]} />);
    expect(screen.getByText("신뢰")).toBeInTheDocument();
    expect(screen.getByText("긴장")).toBeInTheDocument();
  });

  it("effects가 빈 배열이면 아무것도 렌더링하지 않는다", () => {
    const { container } = render(<DeltaGroup effects={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("effects가 undefined여도 에러 없이 아무것도 렌더링하지 않는다", () => {
    const { container } = render(<DeltaGroup effects={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});