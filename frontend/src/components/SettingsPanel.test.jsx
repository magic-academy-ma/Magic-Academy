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

  it("ready 상태 PUT 본문에 Magic Layer 파라미터를 포함한다", async () => {
    let sentBody = null;
    vi.spyOn(globalThis, "fetch").mockImplementationOnce((url, options) => {
      sentBody = JSON.parse(options.body);
      return response({ data: { changed_at: "2026-08-27T00:00:00Z" } });
    });

    render(<SettingsPanel token="tok" simulationId="sim_01" simulationStatus="ready" />);
    await userEvent.click(screen.getByRole("button", { name: "설정 저장" }));
    await screen.findByText(/설정이 저장되었습니다/);

    expect(sentBody).toMatchObject({
      magic_layer_frequency: "medium",
      magic_layer_impact: "medium",
      magic_enabled: true,
    });
  });

  it("running 상태에서 Magic 입력은 읽기 전용이고 PATCH 본문에 Magic 필드가 없다", async () => {
    let sentBody = null;
    vi.spyOn(globalThis, "fetch").mockImplementationOnce((url, options) => {
      sentBody = JSON.parse(options.body);
      return response({ data: { changed_at: "2026-08-27T00:00:10Z" } });
    });

    render(<SettingsPanel token="tok" simulationId="sim_01" simulationStatus="running" />);

    expect(screen.getByLabelText("Magic 빈도")).toBeDisabled();
    expect(screen.getByLabelText("Magic 영향도")).toBeDisabled();
    expect(screen.getByLabelText("Magic Layer 활성화")).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "설정 저장" }));
    await screen.findByText(/설정이 저장되었습니다/);

    expect(Object.keys(sentBody)).toEqual(["event_frequency", "event_impact"]);
  });

  it("Magic 잠금 오류(409)를 사용자에게 표시한다", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() =>
      response(
        { error: { code: "INITIAL_SETTINGS_LOCKED", message: "실행 후 Magic 설정을 변경할 수 없습니다" } },
        409
      )
    );

    render(<SettingsPanel token="tok" simulationId="sim_01" simulationStatus="ready" />);
    await userEvent.click(screen.getByRole("button", { name: "설정 저장" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "실행 후 Magic 설정을 변경할 수 없습니다"
    );
  });
});
