// frontend/src/components/ErrorMessage.jsx
//
// client.js의 apiRequest가 throw하는 Error(.status, .code, .message)를 그대로 받아 표시한다.
// message는 이미 client.js에서 서버 메시지 또는 상태 기반 fallback으로 채워져 있으므로
// 여기서는 상태별 라벨만 덧붙인다. client.js의 ERROR_MESSAGES는 401/403/404/500만
// 커버하므로, 400/409/422처럼 이 화면에서 새로 다루는 상태는 라벨로 구분해 보여준다.

const STATUS_LABELS = {
  400: "입력 오류",
  401: "인증 필요",
  403: "접근 권한 없음",
  404: "찾을 수 없음",
  409: "처리할 수 없습니다",
  422: "규칙 위반",
  500: "서버 오류",
  503: "서비스 준비 안 됨",
};

export default function ErrorMessage({ error }) {
  if (!error) return null;

  const label = STATUS_LABELS[error.status] ?? "오류";

  return (
    <p className={`message error error-status-${error.status ?? "unknown"}`} role="alert">
      <strong>{label}</strong> {error.message}
    </p>
  );
}
