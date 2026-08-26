// frontend/src/components/SnapshotPanel.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import SnapshotPanel from "./SnapshotPanel";
import * as api from "../api/simulationHistory.js";

vi.mock("../api/simulationHistory.js", () => ({
  getSnapshot: vi.fn(),
  restoreSnapshot: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

function fillTickAndSubmit(tick) {
  fireEvent.change(screen.getByLabelText("Tick 번호"), { target: { value: String(tick) } });
  fireEvent.click(screen.getByRole("button", { name: "조회" }));
}

describe("SnapshotPanel", () => {
  it("시점 조회 성공 시 읽기 전용임을 안내하고 복원 버튼을 보여준다", async () => {
    api.getSnapshot.mockResolvedValue({
      tick_number: 5,
      simulation_day: 1,
      agents: [],
      relationships: [],
      events: [],
    });

    render(<SnapshotPanel token="tok" simulationId="sim_01" />);
    fillTickAndSubmit(5);

    expect(await screen.findByText(/새로운 Tick 실행을 유발하지 않습니다/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "이 시점으로 복원" })).toBeInTheDocument();
  });

  it("존재하지 않는 시점 조회 시 404 오류를 표시한다", async () => {
    const error = new Error("Snapshot을 찾을 수 없습니다.");
    error.status = 404;
    error.code = "RESOURCE_NOT_FOUND";
    api.getSnapshot.mockRejectedValue(error);

    render(<SnapshotPanel token="tok" simulationId="sim_01" />);
    fillTickAndSubmit(999);

    expect(await screen.findByRole("alert")).toHaveTextContent("찾을 수 없습니다");
  });

  it("복원 확인 후 성공 시 정확한 snapshot identifier로 요청하고, 반환된 payload를 화면에 표시한다 (새 Simulation id 불필요)", async () => {
    api.getSnapshot.mockResolvedValue({
      tick_number: 5,
      simulation_day: 1,
      snapshot_id: "snap_01",
      agents: [],
      relationships: [],
      events: [],
    });
    api.restoreSnapshot.mockResolvedValue({
      schema_version: "slice6-snapshot-v1",
      simulation: { id: "sim_01", current_tick: 5, current_day: 1 },
      agents: [],
      relationships: [],
      events: [],
    });

    render(<SnapshotPanel token="tok" simulationId="sim_01" />);
    fillTickAndSubmit(5);
    fireEvent.click(await screen.findByRole("button", { name: "이 시점으로 복원" }));
    fireEvent.click(screen.getByRole("button", { name: "복원 확인" }));

    await waitFor(() =>
      expect(api.restoreSnapshot).toHaveBeenCalledWith("tok", "sim_01", "snap_01")
    );
    expect(await screen.findByText(/저장 상태가 복원되었습니다/)).toBeInTheDocument();
  });

  it("복원 충돌(409) 시 오류를 표시한다", async () => {
    api.getSnapshot.mockResolvedValue({
      tick_number: 5,
      simulation_day: 1,
      snapshot_id: "snap_01",
      agents: [],
      relationships: [],
      events: [],
    });
    const error = new Error("복원할 수 없는 상태입니다.");
    error.status = 409;
    error.code = "CONFLICT";
    api.restoreSnapshot.mockRejectedValue(error);

    render(<SnapshotPanel token="tok" simulationId="sim_01" />);
    fillTickAndSubmit(5);
    fireEvent.click(await screen.findByRole("button", { name: "이 시점으로 복원" }));
    fireEvent.click(screen.getByRole("button", { name: "복원 확인" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("처리할 수 없습니다");
  });
});
