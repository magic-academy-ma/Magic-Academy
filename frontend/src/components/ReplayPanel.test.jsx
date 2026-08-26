// frontend/src/components/ReplayPanel.test.jsx

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ReplayPanel from "./ReplayPanel";
import * as api from "../api/simulationHistory.js";

vi.mock("../api/simulationHistory.js", () => ({
  getReplayList: vi.fn(),
  getReplayTick: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ReplayPanel", () => {
  it("실행 기록이 없으면 빈 상태 메시지를 표시한다", async () => {
    api.getReplayList.mockResolvedValue({ items: [], meta: { has_more: false } });

    render(<ReplayPanel token="tok" simulationId="sim_01" />);

    expect(await screen.findByText("재생 가능한 실행 기록이 없습니다.")).toBeInTheDocument();
  });

  it("목록 조회 실패(404) 시 오류를 표시한다", async () => {
    const error = new Error("Simulation을 찾을 수 없습니다.");
    error.status = 404;
    error.code = "RESOURCE_NOT_FOUND";
    api.getReplayList.mockRejectedValue(error);

    render(<ReplayPanel token="tok" simulationId="sim_01" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("찾을 수 없습니다");
  });

  it("tick을 선택하면 상세 데이터를 조회해 표시한다", async () => {
    api.getReplayList.mockResolvedValue({
      items: [{ tick_number: 1, simulation_day: 1 }],
      meta: { has_more: false },
    });
    api.getReplayTick.mockResolvedValue({
      tick_number: 1,
      simulation_day: 1,
      events: [{ id: "e1", title: "수업", event_type: "CLASS" }],
      agent_snapshots: [],
      relationship_deltas: [],
    });

    render(<ReplayPanel token="tok" simulationId="sim_01" />);

    fireEvent.click(await screen.findByRole("button", { name: /Tick 1/ }));

    await waitFor(() => expect(api.getReplayTick).toHaveBeenCalledWith("tok", "sim_01", 1));
    expect(await screen.findByText(/수업/)).toBeInTheDocument();
  });
});
