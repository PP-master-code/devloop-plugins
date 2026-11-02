#!/bin/sh
# Starts guard.py with whatever Python 3 exists (python3 on Linux/macOS, python or py on Windows/Git Bash).
# No Python: the guard stays off instead of breaking the session.
dir=$(dirname "$0")
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    exec "$py" "$dir/guard.py" "$@"
  fi
done
echo "devloop-hub: no Python 3.9+ found, guard hooks are off" >&2
exit 0
