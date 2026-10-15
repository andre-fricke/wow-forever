#!/bin/zsh
cd -- "${0:A:h}" || exit 1
source ./python_runtime.zsh || exit 1
candidates=("${commands[python3]:-}" /opt/homebrew/bin/python3 /usr/local/bin/python3
            /Library/Frameworks/Python.framework/Versions/Current/bin/python3
            /Library/Frameworks/Python.framework/Versions/*/bin/python3(N) /usr/bin/python3)
if python_runtime=$(find_python_runtime "${candidates[@]}"); then
  "$python_runtime" -B ./wow_backup.py
  result=$?
else
  print -r -- 'Python 3.9 or newer was not found.'
  print -r -- 'Install Python 3 for macOS from https://www.python.org/downloads/macos/, then run this tool again.'
  print -r -- 'If Python is already installed elsewhere, add it to PATH or run: /path/to/python3 -B wow_backup.py'
  result=1
fi
printf '\nPress Enter to close.'
read
exit "$result"
