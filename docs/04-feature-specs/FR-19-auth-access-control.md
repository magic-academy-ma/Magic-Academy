---
title: "FR-19 인증 및 접근 제어 — Slice 0"
status: approved
visibility: public
updated: 2026-08-05
---

# FR-19 인증 및 접근 제어 — Slice 0

- 회원가입과 로그인은 `/v1/auth/register`, `/v1/auth/login`으로 제공한다.
- 비밀번호는 Argon2로 해시하며 신규 사용자의 역할은 `USER`로 고정한다.
- JWT는 `sub`, `roles`, `iss`, `aud`, `iat`, `exp`, `jti`를 포함한다.
- 보호 API는 유효한 JWT와 `USER` 역할을 요구한다.
- Simulation의 `owner_id`는 JWT `sub`의 내부 사용자 UUID다.
- 인증 실패는 401, 역할 부족이나 다른 사용자의 Simulation 접근은 403,
  존재하지 않는 Simulation은 404로 응답한다.
