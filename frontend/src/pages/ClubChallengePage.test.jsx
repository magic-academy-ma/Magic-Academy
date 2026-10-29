import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClubChallengePage from "./ClubChallengePage.jsx";
import { apiRequest } from "../api/client.js";

vi.mock("../api/client.js", () => ({ apiRequest: vi.fn() }));

const running = {
  id: "run-1",
  simulation_id: "simulation-1",
  status: "in_progress",
  current_tick: 2,
  current_round: 1,
  tick_in_round: 2,
  member_count: 2,
  reputation: 40,
  choices: {},
  ending: null,
  next_choice_options: [
    { value: "MEDIATE", label: "중재하기", description: "두 회원이 직접 대화하도록 돕습니다." },
    { value: "REASSIGN_ROLES", label: "역할 재배정", description: "강점에 맞게 업무를 다시 나눕니다." },
  ],
  next_story: "두 회원의 갈등이 깊어졌습니다.",
  member_agent_ids: ["agent-1", "agent-2"],
  agent_results: [],
};

describe("ClubChallengePage", () => {
  beforeEach(() => vi.clearAllMocks());

  function finishIntro() {
    fireEvent.click(screen.getByRole("button", { name: "다음 →" }));
    fireEvent.click(screen.getByRole("button", { name: "다음 →" }));
    fireEvent.click(screen.getByRole("button", { name: "도전과제 시작" }));
  }

  it("starts an independent club challenge", async () => {
    apiRequest
      .mockResolvedValueOnce({ data: { ...running, current_tick: 0 } })
      .mockResolvedValueOnce([
        { id: "agent-1", name: "아델", agent_type: "student", mbti_type: "ISTJ" },
        { id: "agent-3", name: "리아", agent_type: "student", mbti_type: "INFP" },
      ]);
    render(<ClubChallengePage token="token" onBack={() => {}} />);
    finishIntro();
    await screen.findByText(/TICK 0\/9/);
    expect(screen.getByText("정회원")).toBeInTheDocument();
    expect(screen.getByText("가입 후보")).toBeInTheDocument();
    expect(apiRequest).toHaveBeenCalledWith("/v1/challenges/club-revival", {
      token: "token",
      method: "POST",
    });
  });

  it("requires and submits a choice at intervention ticks", async () => {
    apiRequest
      .mockResolvedValueOnce({ data: running })
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({
        data: {
          ...running,
          current_tick: 3,
          next_choice_options: [],
          agent_results: [
            {
              agent_id: "agent-1",
              action_type: "PARTICIPATE_EVENT",
              motivation_summary: "Mandatory club event.",
            },
          ],
        },
      })
      .mockResolvedValueOnce([]);
    render(<ClubChallengePage token="token" onBack={() => {}} />);
    finishIntro();
    await screen.findByText("중재하기");
    expect(screen.getByText("두 회원의 갈등이 깊어졌습니다.")).toBeInTheDocument();
    expect(screen.getByText("두 회원이 직접 대화하도록 돕습니다.")).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "선택하고 진행" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("역할 재배정"));
    fireEvent.click(submit);
    await waitFor(() =>
      expect(apiRequest).toHaveBeenLastCalledWith(
        "/v1/challenges/club-revival/run-1/advance",
        {
          token: "token",
          method: "POST",
          body: JSON.stringify({ choice: "REASSIGN_ROLES" }),
        }
      )
    );
    expect(await screen.findByText("사건 참여")).toBeInTheDocument();
    expect(screen.getByText("에이전트이(가) 사건 참여 행동을 선택했습니다.")).toBeInTheDocument();
    expect(screen.queryByText("Mandatory club event.")).not.toBeInTheDocument();
  });

  it("shows the final ending", async () => {
    apiRequest
      .mockResolvedValueOnce({
        data: { ...running, status: "completed", current_tick: 9, ending: "REVIVAL" },
      })
      .mockResolvedValueOnce([]);
    render(<ClubChallengePage token="token" onBack={() => {}} />);
    finishIntro();
    expect(await screen.findByRole("heading", { name: "동아리 부활" })).toBeInTheDocument();
  });
});
