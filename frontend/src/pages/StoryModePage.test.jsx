import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import StoryModePage from "./StoryModePage.jsx";
import { apiRequest } from "../api/client.js";

vi.mock("../api/client.js", () => ({ apiRequest: vi.fn() }));
vi.mock("../components/SchoolMap.jsx", () => ({ default: () => <div>map</div> }));
vi.mock("../components/InspectorPanel.jsx", () => ({ default: () => <aside>inspector</aside> }));

const auth = { access_token: "token", user: { display_name: "조정관" } };
const story = (overrides) => ({
  id: "story-1",
  chapter: 1,
  status: "in_progress",
  chapter_run_id: null,
  records: [],
  final_ending: null,
  ...overrides,
});
const record = (chapter, grade, ending) => ({ chapter, grade, ending, interventions: [] });

const teamRevivalRun = {
  id: "run-2",
  simulation_id: "sim-2",
  chapter: 2,
  status: "completed",
  current_tick: 9,
  current_round: 3,
  ending: "UNITED",
  chapter_record: record(2, "GOOD", "UNITED"),
  agent_results: [],
  members: [],
  next_choice: null,
  round_title: "대회 직전",
  total_ticks: 9,
};

describe("StoryModePage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("starts the semester from the prologue", async () => {
    apiRequest
      .mockResolvedValueOnce({ data: null })
      .mockResolvedValueOnce({ data: story() });
    render(<StoryModePage auth={auth} onBack={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "임시 조정관 임명을 받아들인다" }));

    expect(await screen.findByRole("heading", { name: "거짓 소문의 확산을 막아라" })).toBeInTheDocument();
    expect(apiRequest).toHaveBeenLastCalledWith("/v1/story", { token: "token", method: "POST" });
  });

  it("plays a chapter and moves on to the next one", async () => {
    apiRequest.mockImplementation(async (path) => {
      if (path === "/v1/story/current") return { data: story({ chapter: 2, records: [record(1, "MIXED", "MISUNDERSTANDING")] }) };
      if (path === "/v1/story/story-1/chapter/start") return { data: story({ chapter: 2, chapter_run_id: "run-2" }) };
      if (path === "/v1/story/chapters/team-revival/run-2") return { data: teamRevivalRun };
      if (path === "/v1/simulations/sim-2/agents") return [];
      if (path === "/v1/story/story-1/chapter/complete") {
        return { data: story({
          chapter: 3,
          records: [record(1, "MIXED", "MISUNDERSTANDING"), record(2, "GOOD", "UNITED")],
          new_achievements: [{ id: "CHAPTER2_CLEAR", name: "CHAPTER 2 클리어" }],
        }) };
      }
      throw new Error(`unexpected ${path}`);
    });
    render(<StoryModePage auth={auth} onBack={vi.fn()} />);

    expect(await screen.findByText("소문은 진정되었지만 일부 오해가 남았다.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "사건을 맡는다" }));
    fireEvent.click(await screen.findByRole("button", { name: "활동 기록 남기고 계속" }));

    expect(await screen.findByRole("heading", { name: "동아리를 폐부에서 구하기" })).toBeInTheDocument();
    expect(screen.getByText("서로의 갈등을 해결하고 팀이 다시 하나가 되었다.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "새 업적" })).toHaveTextContent("CHAPTER 2 클리어");
  });

  it("does not show the achievement notice when nothing new was earned", async () => {
    apiRequest.mockResolvedValueOnce({ data: story({ chapter: 2, new_achievements: [] }) });
    render(<StoryModePage auth={auth} onBack={vi.fn()} />);

    expect(await screen.findByRole("heading", { name: "무너진 팀을 다시 살려라" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "새 업적" })).not.toBeInTheDocument();
  });

  it("shows the four records and the final ending", async () => {
    apiRequest.mockResolvedValueOnce({
      data: story({
        chapter: 5,
        status: "completed",
        final_ending: "NORMAL",
        records: [
          record(1, "GOOD", "RESOLVED"),
          record(2, "BAD", "DISBANDED"),
          record(3, "MIXED", "CONDITIONAL"),
          record(4, "GOOD", "POPULAR"),
        ],
      }),
    });
    render(<StoryModePage auth={auth} onBack={vi.fn()} />);

    expect(await screen.findByRole("heading", { name: "한 학기의 기록" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "「완벽하지 않은 해결사」" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("list", { name: "활동 기록" }).children).toHaveLength(4));
  });
});
