import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import InspectorPanel from "./InspectorPanel.jsx";
import * as client from "../api/client.js";

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

    await screen.findByText("Leo");
    expect(screen.getByText("-20")).toBeInTheDocument();
    expect(container.querySelector(".mini-meter-track i")).toHaveStyle({ width: "40%" });
  });
});
