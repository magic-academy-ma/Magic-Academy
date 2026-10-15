import { render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "../api/client.js";
import InspectorPanel from "./InspectorPanel.jsx";

vi.mock("../api/client.js", () => ({ apiRequest: vi.fn() }));

const agent = {
  id: "agent-1",
  name: "아델",
  agent_type: "student",
  mbti_type: "ISTJ",
  profile: {},
  state: {},
};

describe("InspectorPanel", () => {
  afterEach(() => vi.clearAllMocks());

  it("Tick 0에서는 존재하지 않는 판단 설명을 요청하지 않는다", async () => {
    apiRequest.mockResolvedValue([]);

    render(
      <InspectorPanel
        agent={agent}
        simulationId="simulation-1"
        token="token"
        currentTick={0}
        onClose={() => {}}
      />
    );

    await waitFor(() => expect(apiRequest).toHaveBeenCalled());
    expect(apiRequest.mock.calls.map(([path]) => path)).not.toContain(
      "/v1/agents/agent-1/decision-explanation?tick=0"
    );
    expect(apiRequest.mock.calls.map(([path]) => path)).toContain(
      "/v1/agents/agent-1/behavior-log?limit=5"
    );
  });
});
