#!/bin/sh
# Starts lint.py with whatever Python 3 exists (python3 on Linux/macOS, python or py on Windows/Git Bash).
# No Python: the hook stays off instead of breaking the session.
dir=$(dirname "$0")
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    exec "$py" "$dir/lint.py" "$@"
  fi
done
echo "gdscript-lint: no Python 3.9+ found, gdscript-lint hook is off" >&2
exit 0
