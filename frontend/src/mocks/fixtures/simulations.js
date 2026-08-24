import { mockAuthUser } from "./auth.js";

/**
 * SimulationResponse 계약과 일치하는 Mock 데이터
 */
export const mockSimulations = [
  {
    id: "01900000-0000-7000-8000-000000000002",
    owner_id: mockAuthUser.user.id,
    name: "Magic Academy Spring 2026",
    status: "ready",
    current_day: 1,
    current_tick: 42,
    magic_enabled: true,
    created_at: "2026-08-17T09:00:00Z",
  },
];
