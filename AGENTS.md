# Repository instructions

- This repository is the canonical working directory for the WoW Forever tools.
- The addon backup tool lives in `tools/addon-backup`. Make future changes here, not in historical Codex output copies.
- Keep personal WoW snapshots, saved variables, recovery archives, and `latest.json` out of Git. Do not force-add ignored runtime data.
- Run the synthetic tests documented in `tools/addon-backup/README.md` after relevant code changes. Use isolated temporary directories for restore tests, never a live WoW installation.
- The user's macOS interface is English. Use English macOS menu, button, and settings names, including in German explanations.
