import { mockAgents } from "./fixtures/agents.js";
import { mockSimulations } from "./fixtures/simulations.js";
import { mockAuthUser } from "./fixtures/auth.js";
import { mockWorldMap } from "./fixtures/worldMap.js";

/**
 * 백엔드 미완성 시 프론트엔드 독립 실행을 지원하는 Mock API 핸들러
 */
export async function handleMockRequest(path, options = {}) {
  const method = (options.method ?? "GET").toUpperCase();

  // 지연 시간 시뮬레이션 (100ms)
  await new Promise((resolve) => setTimeout(resolve, 100));

  // 1. Auth API
  if (path === "/v1/auth/login" && method === "POST") {
    return mockAuthUser;
  }
  if (path === "/v1/auth/register" && method === "POST") {
    return mockAuthUser.user;
  }

  // 2. Simulation API
  if (path === "/v1/simulations" && method === "GET") {
    return {
      data: mockSimulations,
      meta: { next_cursor: null, has_more: false },
    };
  }
  if (path === "/v1/simulations" && method === "POST") {
    const body = options.body ? JSON.parse(options.body) : {};
    return {
      ...mockSimulations[0],
      name: body.name ?? "새 시뮬레이션",
      current_tick: 0,
      created_at: new Date().toISOString(),
    };
  }

  // 2-1. Simulation save / restore
  if (/\/v1\/simulations\/[^/]+\/save$/.test(path) && method === "POST") {
    const id = path.split("/")[3];
    return {
      data: {
        id,
        status: "PAUSED",
        current_day: mockSimulations[0].current_day,
        current_tick: mockSimulations[0].current_tick,
        saved_at: new Date().toISOString(),
      },
    };
  }
  if (/\/v1\/simulations\/[^/]+\/restore$/.test(path) && method === "POST") {
    const id = path.split("/")[3];
    return {
      data: {
        ...mockSimulations[0],
        id,
        status: "RUNNING",
        updated_at: new Date().toISOString(),
        user_persona: {
          agent_id: mockAgents[1].id,
          status: "APPLIED",
          locked: true,
        },
      },
    };
  }

  // 3. World Map API
  if (/\/v1\/simulations\/[^/]+\/world\/map/.test(path) && method === "GET") {
    return mockWorldMap;
  }

  // 4. Agents API
  if (path.includes("/agents") && method === "GET") {
    return mockAgents;
  }

  // 5. Fallback: 기본 성공 응답
  return { status: "success", message: "Mock API response", path };
}
