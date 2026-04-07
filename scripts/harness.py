#!/usr/bin/env python3
"""
scripts/harness.py — 폴더/파일 단위 테스트 하네스

사용법:
    python scripts/harness.py agents/               # 테스트 실행
    python scripts/harness.py agents/bob.py         # 파일 단위
    python scripts/harness.py agents/ --gc          # 테스트 + GC 체크
    python scripts/harness.py agents/ --diff        # 이전 결과와 비교
    python scripts/harness.py all                   # 전체 실행

_GUIDE.md의 하네스 섹션에서 테스트 목록을 읽어 실행.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / ".harness_cache"
CACHE_DIR.mkdir(exist_ok=True)

# 폴더 → 테스트 파일 기본 매핑 (fallback용, _GUIDE.md 우선)
DEFAULT_MAP = {
    "agents": [
        "tests/unit/test_agents.py",
        "tests/integration/test_e2e_fixes.py",
    ],
    "schemas": [
        "tests/unit/test_schemas.py",
        "tests/unit/test_agents.py",
    ],
    "graph": [
        "tests/integration/test_daily_cycle.py",
        "tests/integration/test_e2e_fixes.py",
        "tests/integration/test_multicycle.py",
    ],
    "graph/nodes": [
        "tests/integration/test_daily_cycle.py",
        "tests/integration/test_e2e_fixes.py",
        "tests/integration/test_multicycle.py",
        "tests/integration/test_risk_alert.py",
    ],
    "transforms": [
        "tests/unit/test_transforms.py",
    ],
    "memory": [
        "tests/unit/test_retrieval.py",
        "tests/integration/test_e2e_fixes.py",
        "tests/integration/test_multicycle.py",
    ],
    "simulation": [
        "tests/unit/test_simulation.py",
    ],
    "execution": [
        "tests/unit/test_position_sizer.py",
    ],
    "utils": [
        "tests/integration/test_e2e_fixes.py",
        "tests/integration/test_multicycle.py",
    ],
    "llm": [
        "tests/unit/test_llm_providers.py",
    ],
    "data": [
        "tests/unit/test_data.py",
    ],
    "evaluation": [
        "tests/unit/test_calibration.py",
        "tests/unit/test_simulation.py",
    ],
    "reliability": [
        "tests/unit/test_reliability.py",
    ],
    "calibration": [
        "tests/unit/test_calibration.py",
    ],
    "tools": [
        "tests/unit/test_tools.py",
    ],
    "meetings": [
        "tests/integration/test_weekly_cycle.py",
        "tests/integration/test_risk_alert.py",
    ],
}

# 파일 → 폴더 매핑
FILE_TO_FOLDER = {
    "bob.py": "agents",
    "emily.py": "agents",
    "dave.py": "agents",
    "otto.py": "agents",
    "base_agent.py": "agents",
    "policy.py": "graph/nodes",
    "order.py": "graph/nodes",
    "logging_node.py": "graph/nodes",
    "risk_check.py": "graph/nodes",
    "agent_reliability.py": "graph/nodes",
    "utility.py": "utils",
    "forward_return.py": "utils",
    "position_sizer.py": "execution",
    "trading_engine.py": "simulation",
    "strategy_executor.py": "simulation",
    "polygon_fetcher.py": "data",
}


def parse_guide_tests(guide_path: Path) -> list[str]:
    """_GUIDE.md의 하네스 섹션에서 테스트 파일 목록 파싱."""
    if not guide_path.exists():
        return []
    content = guide_path.read_text()
    # ## 하네스 섹션 찾기
    match = re.search(r"## 하네스.*?```\s*(.*?)```", content, re.DOTALL)
    if not match:
        return []
    block = match.group(1)
    tests = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("tests/") and line.endswith(".py"):
            tests.append(line)
    return tests


def parse_guide_gc(guide_path: Path) -> dict:
    """_GUIDE.md의 GC 체크 패턴 파싱."""
    if not guide_path.exists():
        return {}
    content = guide_path.read_text()
    match = re.search(r"## GC 체크 패턴.*?```(.*?)```", content, re.DOTALL)
    if not match:
        return {}
    # 간단한 패턴 파싱 (forbidden 섹션)
    block = match.group(1)
    forbidden = re.findall(r'pattern:\s*"([^"]+)"', block)
    messages = re.findall(r'message:\s*"([^"]+)"', block)
    return {
        "forbidden": list(zip(forbidden, messages + [""] * len(forbidden)))
    }


def resolve_target(target: str) -> tuple[str, Path]:
    """target 문자열 → (folder_key, guide_path)"""
    p = Path(target.rstrip("/"))

    # 파일 단위인 경우
    if p.suffix == ".py":
        folder_key = FILE_TO_FOLDER.get(p.name, str(p.parent))
        guide_path = ROOT / p.parent / "_GUIDE.md"
        return folder_key, guide_path

    # 폴더 단위
    folder_key = str(p)
    guide_path = ROOT / p / "_GUIDE.md"
    return folder_key, guide_path


def get_tests(folder_key: str, guide_path: Path) -> list[str]:
    """_GUIDE.md 우선, fallback은 DEFAULT_MAP."""
    from_guide = parse_guide_tests(guide_path)
    if from_guide:
        return from_guide
    # fallback: 가장 긴 prefix match
    for key in sorted(DEFAULT_MAP.keys(), key=len, reverse=True):
        if folder_key.startswith(key) or key.startswith(folder_key):
            return DEFAULT_MAP[key]
    return []


def run_tests(tests: list[str]) -> dict:
    """pytest 실행 후 결과 반환."""
    if not tests:
        return {"status": "no_tests", "passed": 0, "failed": 0, "errors": []}

    existing = [t for t in tests if (ROOT / t).exists()]
    missing = [t for t in tests if not (ROOT / t).exists()]

    if not existing:
        return {"status": "missing", "passed": 0, "failed": 0,
                "errors": [f"테스트 파일 없음: {t}" for t in missing]}

    cmd = ["python", "-m", "pytest"] + existing + ["-q", "--tb=short"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)

    output = result.stdout + result.stderr
    passed = len(re.findall(r"(\d+) passed", output))
    failed = len(re.findall(r"(\d+) failed", output))
    passed_n = int(re.search(r"(\d+) passed", output).group(1)) if re.search(r"(\d+) passed", output) else 0
    failed_n = int(re.search(r"(\d+) failed", output).group(1)) if re.search(r"(\d+) failed", output) else 0

    return {
        "status": "pass" if result.returncode == 0 else "fail",
        "passed": passed_n,
        "failed": failed_n,
        "returncode": result.returncode,
        "output": output,
        "tests": existing,
        "missing": missing,
    }


def check_guide_staleness(folder_key: str, guide_path: Path) -> dict | None:
    """_GUIDE.md가 폴더 내 .py 파일보다 오래됐으면 경고."""
    if not guide_path.exists():
        return None
    folder_path = ROOT / folder_key
    if not folder_path.is_dir():
        return None
    py_files = [f for f in folder_path.rglob("*.py") if "__pycache__" not in str(f)]
    if not py_files:
        return None
    latest_py_mtime = max(f.stat().st_mtime for f in py_files)
    guide_mtime = guide_path.stat().st_mtime
    if latest_py_mtime > guide_mtime:
        from datetime import datetime
        latest_py = max(py_files, key=lambda f: f.stat().st_mtime)
        delta_days = int((latest_py_mtime - guide_mtime) / 86400)
        return {
            "type": "stale_guide",
            "file": str(guide_path.relative_to(ROOT)),
            "message": (
                f"_GUIDE.md가 최신 코드보다 {delta_days}일 오래됨 "
                f"(최근 변경: {latest_py.relative_to(ROOT)}) — 규칙 갱신 필요"
            ),
        }
    return None


def run_gc(folder_key: str, guide_path: Path) -> list[dict]:
    """GC 체크: forbidden 패턴, unused imports, staleness."""
    findings = []
    gc_config = parse_guide_gc(guide_path)

    # 1. forbidden 패턴 체크
    folder_path = ROOT / folder_key
    if folder_path.is_dir():
        py_files = list(folder_path.rglob("*.py"))
    elif folder_path.with_suffix(".py").exists():
        py_files = [folder_path.with_suffix(".py")]
    else:
        py_files = []

    for pattern, message in gc_config.get("forbidden", []):
        for fpath in py_files:
            if "__pycache__" in str(fpath):
                continue
            content = fpath.read_text()
            if re.search(pattern, content):
                findings.append({
                    "type": "forbidden_pattern",
                    "file": str(fpath.relative_to(ROOT)),
                    "pattern": pattern,
                    "message": message,
                })

    # 2. _GUIDE.md 존재 여부 + staleness 체크
    if not guide_path.exists():
        findings.append({
            "type": "missing_guide",
            "file": str(guide_path.relative_to(ROOT)),
            "message": "_GUIDE.md 없음 — 하네스 미설정",
        })
    else:
        stale = check_guide_staleness(folder_key, guide_path)
        if stale:
            findings.append(stale)

    # 3. ruff로 unused import 체크 (있으면)
    ruff_result = subprocess.run(
        ["python", "-m", "ruff", "check", str(folder_path), "--select=F401", "--quiet"],
        capture_output=True, text=True, cwd=ROOT
    )
    if ruff_result.returncode != 0 and ruff_result.stdout:
        for line in ruff_result.stdout.splitlines()[:10]:  # 최대 10개만
            findings.append({
                "type": "unused_import",
                "message": line.strip(),
            })

    return findings


def load_cache(folder_key: str) -> dict:
    cache_file = CACHE_DIR / f"{folder_key.replace('/', '_')}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    return {}


def save_cache(folder_key: str, result: dict):
    cache_file = CACHE_DIR / f"{folder_key.replace('/', '_')}.json"
    result["timestamp"] = datetime.now().isoformat()
    cache_file.write_text(json.dumps(result, indent=2))


def print_diff(prev: dict, curr: dict):
    """이전 결과와 비교해서 달라진 것만 출력."""
    prev_status = prev.get("status", "unknown")
    curr_status = curr.get("status", "unknown")
    prev_passed = prev.get("passed", 0)
    curr_passed = curr.get("passed", 0)
    prev_failed = prev.get("failed", 0)
    curr_failed = curr.get("failed", 0)

    print(f"\n  이전: {prev_status} ({prev_passed} passed, {prev_failed} failed)"
          f"  [{prev.get('timestamp', 'unknown')}]")
    print(f"  현재: {curr_status} ({curr_passed} passed, {curr_failed} failed)")

    if prev_failed == 0 and curr_failed > 0:
        print(f"\n  ⚠️  새로 실패한 테스트 {curr_failed}개 발생!")
    elif prev_failed > 0 and curr_failed == 0:
        print(f"\n  ✅ 이전 실패 {prev_failed}개 모두 해결!")
    elif curr_passed > prev_passed:
        print(f"\n  📈 테스트 {curr_passed - prev_passed}개 추가됨")


def main():
    parser = argparse.ArgumentParser(description="Hybrid Investment System 테스트 하네스")
    parser.add_argument("target", help="폴더 또는 파일 경로 (예: agents/, agents/bob.py, all)")
    parser.add_argument("--gc", action="store_true", help="GC 체크 포함 (drift/forbidden 패턴)")
    parser.add_argument("--diff", action="store_true", help="이전 실행 결과와 비교")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Harness: {args.target}")
    print(f"{'='*60}")

    # 전체 실행
    if args.target == "all":
        cmd = ["python", "-m", "pytest", "tests/", "-q"]
        result = subprocess.run(cmd, cwd=ROOT)
        sys.exit(result.returncode)

    folder_key, guide_path = resolve_target(args.target)

    # 이전 결과 로드
    prev_result = load_cache(folder_key) if args.diff else {}

    # 테스트 실행
    tests = get_tests(folder_key, guide_path)
    print(f"\n  대상 폴더: {folder_key}")
    print(f"  가이드:   {guide_path.relative_to(ROOT) if guide_path.exists() else '없음 ⚠️'}")
    print(f"  테스트:   {len(tests)}개 파일\n")

    result = run_tests(tests)

    # 결과 출력
    icon = "✅" if result["status"] == "pass" else "❌"
    print(f"  {icon} 테스트: {result['passed']} passed / {result['failed']} failed")

    if result.get("missing"):
        print(f"\n  ⚠️  파일 없음: {result['missing']}")

    if result["status"] == "fail":
        print("\n" + "-"*40)
        # 실패 부분만 출력
        output = result.get("output", "")
        for line in output.splitlines():
            if any(k in line for k in ["FAILED", "ERROR", "assert", "short test"]):
                print(f"  {line}")

    # diff 출력
    if args.diff and prev_result:
        print_diff(prev_result, result)

    # GC 체크
    if args.gc:
        print(f"\n{'─'*40}")
        print("  GC 체크 실행 중...")
        findings = run_gc(folder_key, guide_path)
        if not findings:
            print("  ✅ GC: 문제 없음")
        else:
            print(f"  ⚠️  GC: {len(findings)}개 발견")
            for f in findings:
                ftype = f["type"]
                msg = f["message"]
                ffile = f.get("file", "")
                print(f"\n  [{ftype}] {ffile}")
                print(f"  → {msg}")

    # 캐시 저장
    save_cache(folder_key, result)

    # 종료 코드
    print(f"\n{'='*60}\n")
    sys.exit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
