#!/bin/zsh
cd -- "${0:A:h}" || exit 1
/usr/bin/python3 -B ./wow_backup.py
result=$?
printf '\nPress Enter to close.'
read
exit "$result"
