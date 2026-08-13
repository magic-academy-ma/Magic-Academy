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
    // 정확히 0 이라는 텍스트가 뜨는지만 확인 (색상은 스냅샷/시각 테스트 영역이라 여기선 값만 검증)
    expect(screen.getByText(/0/)).toBeInTheDocument();
  });
});

describe("DeltaGroup", () => {
  it("effect가 여러 개면 모두 렌더링한다", () => {
    render(<DeltaGroup effects={[trustUp, tensionUp]} />);
    expect(screen.getByText("신뢰")).toBeInTheDocument();
    expect(screen.getByText("긴장")).toBeInTheDocument();
  });

  // 7번에서 다룬 "빈 결과" 케이스
  it("effects가 빈 배열이면 아무것도 렌더링하지 않는다", () => {
    const { container } = render(<DeltaGroup effects={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("effects가 undefined여도 에러 없이 아무것도 렌더링하지 않는다", () => {
    const { container } = render(<DeltaGroup effects={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});