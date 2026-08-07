const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const ERROR_MESSAGES = {
  401: "로그인이 필요하거나 만료되었습니다.",
  403: "접근 권한이 없습니다.",
  404: "Simulation을 찾을 수 없습니다.",
  500: "서버 오류가 발생했습니다.",
};

export async function apiRequest(path, { token, ...options } = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const error = new Error(ERROR_MESSAGES[response.status] ?? `요청에 실패했습니다. (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}
