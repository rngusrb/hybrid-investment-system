"""
Root conftest.py — pytest 세션 시작 시 테스트용 더미 API 키를 주입.
실제 API를 호출하지 않는 단위/통합 테스트가 EnvironmentError 없이 provider를 초기화할 수 있도록 한다.
"""
import os


def pytest_configure(config):
    """테스트 실행 전 환경변수에 더미 키 삽입 (이미 설정된 경우 덮어쓰지 않음)."""
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key-placeholder")
    os.environ.setdefault("OPENAI_API_KEY", "test-openai-key-placeholder")
    os.environ.setdefault("POLYGON_API_KEY", "test-polygon-key-placeholder")
