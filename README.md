# WoW Forever

Tools for the local WoW Forever installation.

## Addon backup

The tool in [`tools/addon-backup`](tools/addon-backup/README.md) backs up addons and UI settings and prepares their migration from beta to a new release character.

On macOS, double-click `tools/addon-backup/WoW-Addon-Backup.command` in Finder.

Personal backups and recovery data are stored locally alongside the tool and excluded from Git. A clone contains only source code, documentation, and tests.

## RestedXP Text Only

The optional companion addon in [`addon/RestedXPTextOnly`](addon/RestedXPTextOnly/README.md) removes the classic RestedXP guide window decoration while retaining text, inline icons and step controls. Its per-character settings are supported by the backup tool.
