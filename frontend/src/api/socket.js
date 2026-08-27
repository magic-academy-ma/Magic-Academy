const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";


export function buildSimulationSocketUrl(simulationId) {
  if (!API_URL.startsWith("http")) {
    throw new Error(`VITE_API_URL에 프로토콜이 없습니다: ${API_URL}`);
  }

  const wsBase = API_URL.replace(/^http/, "ws");
  return `${wsBase}/v1/ws/simulations/${simulationId}`;
}

