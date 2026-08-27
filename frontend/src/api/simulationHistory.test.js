// frontend/src/api/simulationHistory.test.js
// client.test.js와 동일한 스타일: fetch를 직접 모킹하고 apiRequest를 거쳐 검증.

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  saveDraftConfig,
  updateRunningConfig,
  getSnapshot,
  restoreSnapshot,
  getReplayList,
  getReplayTick,
} from "./simulationHistory.js";

afterEach(() => vi.restoreAllMocks());

function mockFetchOnce(status, body) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

describe("saveDraftConfig", () => {
  it("PUT으로 요청하고 data를 반환한다", async () => {
    mockFetchOnce(200, {
      data: { event_frequency: "high", config_version: 1, changed_at: "2026-08-24T00:00:00Z" },
    });

    const result = await saveDraftConfig("tok", "sim_01", {
      event_frequency: "high",
      event_impact: "medium",
      magic_enabled: true,
    });

    expect(result.event_frequency).toBe("high");
    const [, options] = fetch.mock.calls[0];
    expect(options.method).toBe("PUT");
    expect(options.token).toBe("tok");
  });

  it("422 응답을 그대로 throw한다 (status/code/message)", async () => {
    mockFetchOnce(422, {
      error: { code: "BUSINESS_RULE_VIOLATION", message: "허용 범위 초과", trace_id: "req_1" },
    });

    await expect(
      saveDraftConfig("tok", "sim_01", {
        event_frequency: "extreme",
        event_impact: "medium",
        magic_enabled: true,
      })
    ).rejects.toMatchObject({ status: 422, code: "BUSINESS_RULE_VIOLATION", message: "허용 범위 초과" });
  });
});

describe("updateRunningConfig", () => {
  it("PATCH로 event_frequency/event_impact만 보낸다", async () => {
    mockFetchOnce(200, { data: { event_frequency: "low", config_version: 4 } });

    await updateRunningConfig("tok", "sim_01", { eventFrequency: "low", eventImpact: "low" });

    const [, options] = fetch.mock.calls[0];
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body)).toEqual({ event_frequency: "low", event_impact: "low" });
  });

  it("400 VALIDATION_ERROR를 그대로 전달한다", async () => {
    mockFetchOnce(400, {
      error: { code: "VALIDATION_ERROR", message: "magic_layer 필드는 허용되지 않습니다.", trace_id: "req_2" },
    });

    await expect(
      updateRunningConfig("tok", "sim_01", { eventFrequency: "low", eventImpact: "low" })
    ).rejects.toMatchObject({ status: 400, code: "VALIDATION_ERROR" });
  });
});

describe("getSnapshot", () => {
  it("시점 조회 성공 시 data를 반환한다", async () => {
    mockFetchOnce(200, { data: { tick_number: 5, simulation_day: 1, agents: [] } });

    const result = await getSnapshot("tok", "sim_01", 5);

    expect(result.tick_number).toBe(5);
  });

  it("404 RESOURCE_NOT_FOUND를 그대로 전달한다", async () => {
    mockFetchOnce(404, {
      error: { code: "RESOURCE_NOT_FOUND", message: "Snapshot을 찾을 수 없습니다.", trace_id: "req_3" },
    });

    await expect(getSnapshot("tok", "sim_01", 999)).rejects.toMatchObject({
      status: 404,
      code: "RESOURCE_NOT_FOUND",
    });
  });
});

describe("restoreSnapshot", () => {
  it("복원 성공 시 새 Simulation을 생성하지 않고 저장된 시점의 snapshot payload를 그대로 반환한다", async () => {
    mockFetchOnce(200, {
      data: {
        schema_version: "slice6-snapshot-v1",
        simulation: { id: "sim_01", current_tick: 5, current_day: 1 },
        agents: [],
        relationships: [],
        events: [],
      },
    });

    const result = await restoreSnapshot("tok", "sim_01", "snap_01");

    expect(result.schema_version).toBe("slice6-snapshot-v1");
    expect(result.simulation.id).toBe("sim_01");
    expect(result).not.toHaveProperty("origin_simulation_id");

    const [url, options] = fetch.mock.calls[0];
    expect(url).toContain("/simulations/sim_01/restore");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ snapshot_id: "snap_01" });
  });

  it("409 CONFLICT를 그대로 전달한다", async () => {
    mockFetchOnce(409, {
      error: { code: "CONFLICT", message: "복원할 수 없는 상태입니다.", trace_id: "req_4" },
    });

    await expect(restoreSnapshot("tok", "sim_01", "snap_01")).rejects.toMatchObject({
      status: 409,
      code: "CONFLICT",
    });
  });
});

describe("getReplayList / getReplayTick", () => {
  it("Replay 목록을 items/meta로 반환한다", async () => {
    mockFetchOnce(200, {
      data: [{ tick_number: 1, simulation_day: 1 }],
      meta: { next_cursor: null, has_more: false },
    });

    const result = await getReplayList("tok", "sim_01");

    expect(result.items).toHaveLength(1);
    expect(result.meta.has_more).toBe(false);
  });

  it("Replay 상세 조회 성공 시 data를 반환한다", async () => {
    mockFetchOnce(200, {
      data: { tick_number: 1, simulation_day: 1, events: [], agent_snapshots: [], relationship_deltas: [] },
    });

    const result = await getReplayTick("tok", "sim_01", 1);

    expect(result.tick_number).toBe(1);
  });
});
