# Find the first working Python 3.9+ interpreter from the supplied candidates.
# Keeping this separate lets tests exercise missing/old runtimes without launching WoW tools.
find_python_runtime() {
  local candidate
  for candidate in "$@"; do
    [[ -x "$candidate" && ! -d "$candidate" ]] || continue
    # Avoid triggering the Command Line Tools installer through Apple's Python shim.
    if [[ "$candidate" == /usr/bin/python3 ]] && ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
      continue
    fi
    if "$candidate" -B -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
      print -r -- "$candidate"
      return 0
    fi
  done
  return 1
}
