
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "../api/client.js";
import InspectorPanel from "./InspectorPanel.jsx";

vi.mock("../api/client.js", () => ({
  apiRequest: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const agent = {
  id: "agent-1",
  name: "Adel",
  agent_type: "student",
  mbti_type: "ISTJ",
  profile: {},
  state: {},
};

describe("InspectorPanel", () => {
  it("keeps signed relationship values instead of clamping them to zero", async () => {
    client.apiRequest.mockImplementation((path) => {
      if (path.endsWith("/relationships")) {
        return Promise.resolve([
          {
            target_agent_id: "agent-2",
            target_agent_name: "Leo",
            affection: -20,
            closeness: -40,
            trust: -10,
            tension: 30,
            rivalry: 20,
            dependency: 10,
          },
        ]);
      }
      return Promise.resolve([]);
    });

    const { container } = render(
      <InspectorPanel
        agent={agent}
        simulationId="simulation-1"
        token="token"
        currentTick={1}
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
