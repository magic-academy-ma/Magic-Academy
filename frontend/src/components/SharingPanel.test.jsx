// frontend/src/components/SharingPanel.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SharingPanel from "./SharingPanel";
import * as api from "../api/sharing.js";

vi.mock("../api/sharing.js", () => ({
  createShare: vi.fn(),
  cancelShare: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe("SharingPanel", () => {
  it("ready 상태가 아니면 공유 폼 대신 안내 메시지를 보여준다", () => {
    render(<SharingPanel token="tok" simulationId="sim_01" simulationStatus="running" />);

    expect(screen.getByText(/현재 상태\(running\)에서 공유할 수 없습니다/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "공유하기" })).not.toBeInTheDocument();
  });

  it("ready 상태에서 공유 생성에 성공하면 공유 ID와 취소 버튼을 보여준다", async () => {
    api.createShare.mockResolvedValue({
      id: "share_01",
      visibility: "public",
      export_schema_version: "slice7-share-v1",
    });

    render(<SharingPanel token="tok" simulationId="sim_01" simulationStatus="ready" />);
    fireEvent.click(screen.getByRole("button", { name: "공유하기" }));

    expect(await screen.findByText(/설정이 공유되었습니다/)).toBeInTheDocument();
    expect(screen.getByText("share_01")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "공유 취소" })).toBeInTheDocument();
    expect(api.createShare).toHaveBeenCalledWith("tok", "sim_01", {
      visibility: "private",
      title: "",
      description: "",
    });
  });

  it("실행 중 Simulation 공유 시 409 오류를 표시한다", async () => {
    const error = new Error("이미 적용되었거나 Simulation이 시작되어 변경할 수 없습니다.");
    error.status = 409;
    error.code = "SIMULATION_SHARE_NOT_READY";
    api.createShare.mockRejectedValue(error);

    render(<SharingPanel token="tok" simulationId="sim_01" simulationStatus="ready" />);
    fireEvent.click(screen.getByRole("button", { name: "공유하기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/처리할 수 없습니다/);
  });

  it("공유 취소가 성공하면 다시 공유 폼을 보여준다", async () => {
    api.createShare.mockResolvedValue({ id: "share_02", visibility: "private" });
    api.cancelShare.mockResolvedValue(undefined);

    render(<SharingPanel token="tok" simulationId="sim_01" simulationStatus="ready" />);
    fireEvent.click(screen.getByRole("button", { name: "공유하기" }));
    await screen.findByText(/설정이 공유되었습니다/);

    fireEvent.click(screen.getByRole("button", { name: "공유 취소" }));

    expect(await screen.findByRole("button", { name: "공유하기" })).toBeInTheDocument();
    expect(api.cancelShare).toHaveBeenCalledWith("tok", "share_02");
  });
});
