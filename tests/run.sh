#!/usr/bin/env bash
# The whole suite: tests/test_contract.py and tests/test_pure.py, on any Python 3.11+, without torch or a GPU.
# No test generates an image (AGENTS.md, "Testing"). Exit code 0 when everything passes.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
py="${AIGEN_PYTHON_TESTS:-python3}"
failed=0
for test in test_contract.py test_pure.py; do
    echo "== $test"
    "$py" "$ROOT/tests/$test" || failed=1
done
[ "$failed" -eq 0 ] && echo "== all passed" || echo "== FAILED" >&2
exit "$failed"
