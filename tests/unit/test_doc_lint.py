"""
tests/unit/test_doc_lint.py — run_doc_lint() 행동 단위 테스트

검증 대상:
  1. YAML 콜론 문법 실제 키 → secret_pattern FAIL
  2. placeholder 값 → 잡지 않음
  3. null 값 → 잡지 않음
  4. TASKS.md 깨진 아카이브 링크 → broken_archive_link FAIL
  5. 유효한 아카이브 링크 → 잡지 않음
  6. TASKS.md completed 본문 → tasks_completed_body FAIL
"""
import pytest
from pathlib import Path
from unittest.mock import patch


def _lint(tmp_path: Path) -> list[dict]:
    """tmp_path를 ROOT로 삼아 run_doc_lint() 실행."""
    meta = tmp_path / "meta" / "project_state.yaml"
    with patch("scripts.harness.ROOT", tmp_path), \
         patch("scripts.harness.META_PATH", meta):
        from scripts.harness import run_doc_lint
        return run_doc_lint()


def _types(findings: list[dict]) -> list[str]:
    return [f["type"] for f in findings]


# ── 시크릿 탐지 ────────────────────────────────────────────────────────────

class TestSecretDetection:

    def test_yaml_colon_real_key_caught(self, tmp_path):
        """YAML 콜론 문법으로 박힌 실제 키를 잡는다."""
        (tmp_path / "TASKS.md").write_text("# TASKS\n")
        cfg = tmp_path / "config.yaml"
        cfg.write_text('polygon_api_key: "rDrRIWoHnZPSjaNoYmeUfJRWMuDd_Ntk"\n')

        assert "secret_pattern" in _types(_lint(tmp_path))

    def test_python_assign_real_key_caught(self, tmp_path):
        """Python = 문법 하드코딩도 잡는다."""
        (tmp_path / "TASKS.md").write_text("# TASKS\n")
        (tmp_path / "test.py").write_text('POLYGON_API_KEY = "rDrRIWoHnZPSjaNoYmeUfJRWMuDd_Ntk"\n')

        assert "secret_pattern" in _types(_lint(tmp_path))

    def test_placeholder_not_caught(self, tmp_path):
        """your_xxx 형태 placeholder는 잡지 않는다."""
        (tmp_path / "TASKS.md").write_text("# TASKS\n")
        (tmp_path / "example.yaml").write_text('polygon_api_key: "your_polygon_api_key_here"\n')

        assert "secret_pattern" not in _types(_lint(tmp_path))

    def test_null_value_not_caught(self, tmp_path):
        """null 값은 잡지 않는다 (길이 부족)."""
        (tmp_path / "TASKS.md").write_text("# TASKS\n")
        (tmp_path / "config.yaml").write_text("polygon_api_key: null\n")

        assert "secret_pattern" not in _types(_lint(tmp_path))

    def test_env_example_not_scanned(self, tmp_path):
        """.env.example 파일은 탐지 대상이 아니다."""
        (tmp_path / "TASKS.md").write_text("# TASKS\n")
        (tmp_path / ".env.example").write_text(
            'POLYGON_API_KEY=rDrRIWoHnZPSjaNoYmeUfJRWMuDd_Ntk\n'
        )

        assert "secret_pattern" not in _types(_lint(tmp_path))

    def test_anthropic_key_caught(self, tmp_path):
        """ANTHROPIC_API_KEY 하드코딩 잡는다."""
        (tmp_path / "TASKS.md").write_text("# TASKS\n")
        (tmp_path / "config.yaml").write_text(
            'ANTHROPIC_API_KEY: "sk-ant-realkey1234567890abcdef"\n'
        )

        assert "secret_pattern" in _types(_lint(tmp_path))


# ── 아카이브 링크 검증 ────────────────────────────────────────────────────

class TestArchiveLinkValidation:

    def test_broken_link_caught(self, tmp_path):
        """존재하지 않는 아카이브 링크를 잡는다."""
        (tmp_path / "TASKS.md").write_text(
            "# TASKS\n"
            "| 2026-04-28 | Sprint | `docs/sprints/SPRINT_missing.md` |\n"
        )

        assert "broken_archive_link" in _types(_lint(tmp_path))

    def test_valid_link_not_caught(self, tmp_path):
        """실제로 존재하는 아카이브 링크는 잡지 않는다."""
        sprints = tmp_path / "docs" / "sprints"
        sprints.mkdir(parents=True)
        (sprints / "SPRINT_2026-04-28_test.md").write_text("# Sprint\n")
        (tmp_path / "TASKS.md").write_text(
            "# TASKS\n"
            "| 2026-04-28 | Sprint | `docs/sprints/SPRINT_2026-04-28_test.md` |\n"
        )

        assert "broken_archive_link" not in _types(_lint(tmp_path))


# ── TASKS.md 상태 검사 ────────────────────────────────────────────────────

class TestTasksState:

    def test_completed_body_caught(self, tmp_path):
        """completed 본문이 TASKS.md에 남아있으면 잡는다."""
        (tmp_path / "TASKS.md").write_text(
            "# TASKS\n"
            "## D-001: 테스트\n"
            "**상태**: completed\n"
        )

        assert "tasks_completed_body" in _types(_lint(tmp_path))

    def test_clean_tasks_not_caught(self, tmp_path):
        """현재판 전용 TASKS.md (completed 없음)는 잡지 않는다."""
        (tmp_path / "TASKS.md").write_text(
            "# TASKS\n\n## 현재 스프린트: 없음\n"
        )

        assert "tasks_completed_body" not in _types(_lint(tmp_path))
