// frontend/src/components/SettingsPanel.test.jsx
// Follow project convention: userEvent + vi.spyOn(globalThis, 'fetch')

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingsPanel from "./SettingsPanel";

function response(body, status = 200) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, json: () => Promise.resolve(body) });
}

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe("SettingsPanel", () => {
  it("ready 상태에서 저장 시 PUT 요청을 보내고 성공 메시지를 표시한다", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce((url, options) => {
      // Expect a PUT to parameters endpoint
      expect(options?.method).toBe("PUT");
      return response({ data: { changed_at: "2026-08-24T00:00:00Z" } });
    });

    render(<SettingsPanel token="tok" simulationId="sim_01" simulationStatus="ready" />);
    await userEvent.click(screen.getByRole("button", { name: "설정 저장" }));

    expect(await screen.findByText(/설정이 저장되었습니다/)).toBeInTheDocument();
  });

  it("running 상태에서 저장 시 PATCH 요청을 보낸다", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce((url, options) => {
      expect(options?.method).toBe("PATCH");
      return response({ data: { changed_at: "2026-08-24T00:00:10Z" } });
    });

    render(<SettingsPanel token="tok" simulationId="sim_01" simulationStatus="running" />);
    await userEvent.click(screen.getByRole("button", { name: "설정 저장" }));

    // success indicated by saved message
    expect(await screen.findByText(/설정이 저장되었습니다/)).toBeInTheDocument();
  });

  it("저장 실패(422) 시 오류 메시지를 표시한다", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() =>
      response({ error: { code: "BUSINESS_RULE_VIOLATION", message: "허용 범위 초과" } }, 422)
    );

    render(<SettingsPanel token="tok" simulationId="sim_01" simulationStatus="ready" />);
    await userEvent.click(screen.getByRole("button", { name: "설정 저장" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("허용 범위 초과");
  });

  it("completed 등 변경 불가 상태에서는 저장 버튼이 비활성화된다", () => {
    render(<SettingsPanel token="tok" simulationId="sim_01" simulationStatus="completed" />);
    expect(screen.getByRole("button", { name: "설정 저장" })).toBeDisabled();
  });
});
