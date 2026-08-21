const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// wss://{server}/v1/ws/simulations/{simulation_id} (§14.1), 인증 없음 (§1.2, MVP 기준)
export function buildSimulationSocketUrl(simulationId) {
  const wsBase = API_URL.replace(/^http/, "ws");
  return `${wsBase}/v1/ws/simulations/${simulationId}`;
}
