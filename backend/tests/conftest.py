import os

# 테스트 환경에서 Settings 초기화에 필요한 최소 환경 변수
os.environ.setdefault("JWT_SECRET", "test-secret-key-minimum-32-characters-long")
