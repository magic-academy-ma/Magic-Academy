// frontend/src/components/SharedBrowser.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SharedBrowser from "./SharedBrowser";
import * as api from "../api/sharing.js";

vi.mock("../api/sharing.js", () => ({
  listShares: vi.fn(),
  getShareDetail: vi.fn(),
  importShare: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

const sampleShare = {
  id: "share_01",
  title: "마법 대학 표준 설정",
  description: "6인 기본 구성",
  visibility: "public",
  export_schema_version: "slice7-share-v1",
};

const sampleDetail = {
  ...sampleShare,
  export_payload: {
    agents: [
      { role_profile: { profile_type: "student" } },
      { role_profile: { profile_type: "student" } },
      { role_profile: { profile_type: "professor" } },
    ],
    organizations: [{}],
  },
};

describe("SharedBrowser", () => {
  it("목록을 불러와 표시하고, 결과가 없으면 안내 메시지를 보여준다", async () => {
    api.listShares.mockResolvedValue([]);

    render(<SharedBrowser token="tok" />);

    expect(await screen.findByText("공개된 공유 설정이 없습니다.")).toBeInTheDocument();
  });

  it("방금 만든 비공개 공유는 작성자의 둘러보기 목록에 표시한다", async () => {
    api.listShares.mockResolvedValue([]);
    const privateShare = { ...sampleShare, id: "share_private", visibility: "private" };

    render(<SharedBrowser token="tok" recentShare={privateShare} />);

    expect(await screen.findByText("마법 대학 표준 설정")).toBeInTheDocument();
    expect(screen.getByText("private")).toBeInTheDocument();
  });

  it("목록 항목을 선택하면 상세와 roster 요약을 보여준다", async () => {
    api.listShares.mockResolvedValue([sampleShare]);
    api.getShareDetail.mockResolvedValue(sampleDetail);

    render(<SharedBrowser token="tok" />);
    await screen.findByText("마법 대학 표준 설정");
    fireEvent.click(screen.getByRole("button", { name: /마법 대학 표준 설정/ }));

    expect(await screen.findByText(/Student 2명 · Professor 1명 · Organization 1개/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "이 설정 가져오기" })).toBeInTheDocument();
  });

  it("검색어를 제출하면 listShares에 q가 전달된다", async () => {
    api.listShares.mockResolvedValue([]);
    render(<SharedBrowser token="tok" />);
    await screen.findByText("공개된 공유 설정이 없습니다.");

    await userEvent.type(screen.getByLabelText("검색"), "마법");
    fireEvent.click(screen.getByRole("button", { name: "검색" }));

    expect(api.listShares).toHaveBeenLastCalledWith("tok", { q: "마법" });
  });

  it("가져오기를 확인하면 새 Simulation을 전달하며 onImported를 호출한다", async () => {
    api.listShares.mockResolvedValue([sampleShare]);
    api.getShareDetail.mockResolvedValue(sampleDetail);
    api.importShare.mockResolvedValue({ id: "sim_new", name: "가져온 Simulation", status: "ready" });
    const onImported = vi.fn();

    render(<SharedBrowser token="tok" onImported={onImported} />);
    await screen.findByText("마법 대학 표준 설정");
    fireEvent.click(screen.getByRole("button", { name: /마법 대학 표준 설정/ }));
    fireEvent.click(await screen.findByRole("button", { name: "이 설정 가져오기" }));
    fireEvent.click(screen.getByRole("button", { name: "가져오기 확인" }));

    await vi.waitFor(() => expect(onImported).toHaveBeenCalledWith({
      id: "sim_new",
      name: "가져온 Simulation",
      status: "ready",
    }));
    const [, , idempotencyKey] = api.importShare.mock.calls[0];
    expect(typeof idempotencyKey).toBe("string");
    expect(idempotencyKey.length).toBeGreaterThan(0);
  });

  it("가져오기 실패 시 오류를 표시하고 onImported를 호출하지 않는다", async () => {
    api.listShares.mockResolvedValue([sampleShare]);
    api.getShareDetail.mockResolvedValue(sampleDetail);
    const error = new Error("공유를 찾을 수 없습니다.");
    error.status = 404;
    api.importShare.mockRejectedValue(error);
    const onImported = vi.fn();

    render(<SharedBrowser token="tok" onImported={onImported} />);
    await screen.findByText("마법 대학 표준 설정");
    fireEvent.click(screen.getByRole("button", { name: /마법 대학 표준 설정/ }));
    fireEvent.click(await screen.findByRole("button", { name: "이 설정 가져오기" }));
    fireEvent.click(screen.getByRole("button", { name: "가져오기 확인" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("공유를 찾을 수 없습니다.");
    expect(onImported).not.toHaveBeenCalled();
  });
});
