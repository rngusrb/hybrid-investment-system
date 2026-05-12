#!/bin/sh
# scripts/install_git_hooks.sh — git hooks 설치
# 사용: sh scripts/install_git_hooks.sh

HOOKS_DIR=".git/hooks"
PRE_COMMIT="$HOOKS_DIR/pre-commit"

cat > "$PRE_COMMIT" << 'HOOK'
#!/bin/sh
echo "[ pre-commit ] python scripts/harness.py all 실행 중..."
python scripts/harness.py all
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ harness all 실패 — 커밋 차단"
    echo "   원인 수정 후 재시도하거나, 긴급 시 git commit --no-verify"
    exit 1
fi
echo "✅ harness all 통과 — 커밋 허용"
HOOK

chmod +x "$PRE_COMMIT"
echo "✅ pre-commit hook 설치 완료: $PRE_COMMIT"
