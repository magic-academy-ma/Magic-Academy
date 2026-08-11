import os

# 통합 테스트에서 app.main import 시 필요한 최소 환경 변수
os.environ.setdefault("JWT_SECRET", "test-only-dummy-secret-at-least-32chars!!")
