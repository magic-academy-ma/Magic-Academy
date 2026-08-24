const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const ERROR_MESSAGES = {
  400: "입력한 값이 허용 범위를 벗어났습니다.",
  401: "로그인이 필요하거나 만료되었습니다.",
  403: "접근 권한이 없습니다.",
  404: "Simulation을 찾을 수 없습니다.",
  409: "이미 적용되었거나 Simulation이 시작되어 변경할 수 없습니다.",
  422: "시작 조건을 만족하지 않습니다.",
  500: "서버 오류가 발생했습니다.",
};

export async function apiRequest(path, { token, ...options } = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  let body;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }

  if (!response.ok) {
    // 두 가지 에러 포맷을 모두 지원한다.
    // - {"code","message","details"}: User Persona API
    // - {"detail": "..."}: 기존 FastAPI 기본 예외 포맷
    const message =
      (typeof body?.message === "string" && body.message) ||
      (typeof body?.error?.message === "string" && body.error.message) ||
      (typeof body?.detail === "string" && body.detail) ||
      ERROR_MESSAGES[response.status] ||
      `요청에 실패했습니다. (${response.status})`;

    const error = new Error(message);
    error.status = response.status;
    error.code = body?.code ?? body?.error?.code;
    error.details = body?.details;

    throw error;
  }

  return body;
}

// --- User Persona (Slice 4 Task 4) ---
export async function getUserPersonaConfig(simulationId, { token } = {}) {
  const response = await apiRequest(
    `/v1/simulations/${simulationId}/user-persona/config`,
    { token }
  );
  return response.data;
}

// 아직 User Persona가 설정되지 않았으면 404 RESOURCE_NOT_FOUND를 던진다.
export async function getUserPersona(simulationId, { token } = {}) {
  const response = await apiRequest(
    `/v1/simulations/${simulationId}/user-persona`,
    { token }
  );
  return response.data;
}

export async function setUserPersona(simulationId, payload, { token } = {}) {
  const response = await apiRequest(
    `/v1/simulations/${simulationId}/user-persona`,
    {
      token,
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  return response.data;
}

export async function startSimulation(simulationId, { token } = {}) {
  const response = await apiRequest(
    `/v1/simulations/${simulationId}/start`,
    {
      token,
      method: "POST",
      body: JSON.stringify({}),
    }
  );
  return response.data;
}