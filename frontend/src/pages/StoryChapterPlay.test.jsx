import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import StoryChapterPlay from "./StoryChapterPlay.jsx";
import { apiRequest } from "../api/client.js";

vi.mock("../api/client.js", () => ({ apiRequest: vi.fn() }));
vi.mock("../components/SchoolMap.jsx", () => ({ default: () => <div>map</div> }));
vi.mock("../components/InspectorPanel.jsx", () => ({ default: () => <aside>inspector</aside> }));

const agents = [
  { id: "a1", name: "아델", agent_type: "student" },
  { id: "a2", name: "레오", agent_type: "student" },
];
const setupRun = {
  id: "run-4",
  simulation_id: "sim-4",
  chapter: 4,
  status: "in_progress",
  current_tick: 1,
  current_round: 1,
  ending: null,
  chapter_record: null,
  agent_results: [],
  members: [{ agent_id: "a1", label: "역할 자율" }, { agent_id: "a2", label: "역할 자율" }],
  concept: null,
  incident: null,
  vacant_ticks: 0,
  staffing: [],
  round_title: "기획·준비",
  total_ticks: 9,
  next_choice: {
    point: "BOOTH_SETUP",
    story: "기획 회의가 끝났습니다.",
    concepts: [{ value: "FOOD", label: "먹거리 부스", description: "먹거리" }],
    roles: [{ value: "COUNTER", label: "부스 담당" }, { value: "SUPPLY", label: "조달" }],
    options: [],
  },
};

describe("StoryChapterPlay", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sends the booth concept and role assignment", async () => {
    apiRequest.mockImplementation(async (path) => {
      if (path.endsWith("/agents")) return agents;
      if (path.endsWith("/advance")) return { data: { ...setupRun, current_tick: 2, next_choice: null } };
      return { data: setupRun };
    });
    render(<StoryChapterPlay chapter={4} runId="run-4" token="token" onBack={vi.fn()} onComplete={vi.fn()} />);

    const submit = await screen.findByRole("button", { name: "선택하고 진행" });
    fireEvent.click(screen.getByLabelText("먹거리 부스"));
    expect(submit).toBeDisabled();
    fireEvent.change(await screen.findByLabelText("아델 역할"), { target: { value: "COUNTER" } });
    fireEvent.change(screen.getByLabelText("레오 역할"), { target: { value: "SUPPLY" } });
    fireEvent.click(submit);

    expect(await screen.findByText("map")).toBeInTheDocument();
    expect(apiRequest).toHaveBeenCalledWith("/v1/story/chapters/festival-booth/run-4/advance", {
      token: "token",
      method: "POST",
      body: JSON.stringify({ concept: "FOOD", roles: { a1: "COUNTER", a2: "SUPPLY" } }),
    });
  });

  it("can leave role assignment to the students", async () => {
    apiRequest.mockImplementation(async (path) => {
      if (path.endsWith("/agents")) return agents;
      if (path.endsWith("/advance")) return { data: { ...setupRun, current_tick: 2, next_choice: null } };
      return { data: setupRun };
    });
    render(<StoryChapterPlay chapter={4} runId="run-4" token="token" onBack={vi.fn()} onComplete={vi.fn()} />);

    fireEvent.click(await screen.findByLabelText("먹거리 부스"));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "선택하고 진행" }));

    await screen.findByText("map");
    expect(apiRequest).toHaveBeenCalledWith("/v1/story/chapters/festival-booth/run-4/advance", {
      token: "token",
      method: "POST",
      body: JSON.stringify({ concept: "FOOD", roles: null }),
    });
  });
});
