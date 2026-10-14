# WoW Addon-Backup

Eigenständiges macOS-Werkzeug für versionierte Addon-/UI-Backups und die Übernahme auf einen neuen Charakter mit anderem Account, Realm und GUID. Python 3.9 oder neuer; keine zusätzlichen Python-Pakete erforderlich.

## Start

`WoW-Addon-Backup.command` im Finder doppelklicken. Das Menü bietet Backup erstellen/aktualisieren, Wiederherstellen, Rückgängig und Integritätsprüfung. WoW vor einem Backup oder Import vollständig beenden.

- [Bedienungsanleitung](Anleitung.md)
- [Bisheriger Prüfbericht](Pruefbericht.md)

Ein Git-Clone enthält keine persönlichen Backups. Diese entstehen unter `Backups/`; `latest.json` verweist auf den aktuellen Stand. Rücksicherungen liegen in `Ruecksicherungen/`. Alle drei Pfade sind absichtlich von Git ausgeschlossen. Den vollständigen Werkzeugordner einschließlich dieser lokalen Daten separat sichern.

## Tests

Aus diesem Ordner ausführen:

```sh
python3 -B tests/test_core.py
python3 -B tests/test_snapshots.py
```

Die Tests erstellen ausschließlich synthetische Daten in temporären Ordnern und verändern keine WoW-Installation. Sie prüfen Charakterzuordnungen, Unicode, Archivierung, Backup-Aktualisierung, Installation, Rücksicherung und Fehlerfälle.

Optionaler Integrationstest mit der vorhandenen Cannot-Beta-Vorlage (stellt nur in einem temporären Ordner wieder her):

```sh
python3 -B tests/test_saved_snapshot.py /vollstaendiger/pfad/zum/backup.zip
```

Eine CLI-Übersicht liefert `python3 -B wow_backup.py --help`.
