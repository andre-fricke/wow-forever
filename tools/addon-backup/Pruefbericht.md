# Validierung am 14.10.2026

## Ausgangsdaten

- Vorlage: Cannot Hotalot, Druide, Classic Beta PvP 2.
- Quelle: `/Applications/World of Warcraft/_classic_beta_`.
- Eigenständiger Stand: `Backups/20261014-161319-002099.zip`.
- 72 Addon-Ordner; 8.414 archivierte Dateien; 163 MiB komprimiert.
- Vollständiger Rohstand von `Interface/AddOns` und `WTF`, jeweils mit Dateiprüfsummen.
- Keine unbekannten, noch nicht unterstützten Konfigurationsdateien in dieser Vorlage festgestellt.

## Erfolgreich geprüft

1. Vollständige Integrität des echten Backups anhand der gespeicherten Dateiprüfsummen.
2. Lua-Daten lesen und schreiben, einschließlich Umlauten, Unicode, Steuerzeichen, Tabellen und Zahlen. Die Konfigurationsdateien werden nicht als Code ausgeführt.
3. Profilschlüssel von vollständigem Charaktername und `Name - Realm` auf neue Namen und neuen Realm umsetzen; eigene GUID ersetzen.
4. Simulation eines neuen Zielaccounts mit Charakter `New Surname`, Realm `Actual Release Realm`, neuer GUID und Klasse Schamane.
5. In dieser Simulation stimmen EllesmereUIs vollständige visuelle Profile semantisch mit dem Backup überein. Zusätzlich geprüft: UI-Skalierung, Schriftarten, Farben, Anker sowie Höhen- und Breitenverknüpfungen.
6. Aktivierung und Deaktivierung der Addons übernommen; Charaktererkennung nach Import deaktiviert.
7. Vorhandener Ziel-Questfortschritt, Ziel-Ausrüstung, Zielklasse und RXP-Guidefortschritt erhalten; Beta-Gold und alte Spezialisierungs-Caches nicht importiert.
8. Ziel-Realm und Account in der Client-Konfiguration erhalten; Beta-Verbindungsdaten nicht übernommen.
9. Bestehende Ziel-Addon-Versionen bei normaler Vorbereitung erhalten. Für fehlende Addons sind die vollständigen archivierten Dateimengen eingeplant. Expliziter Versionsersatz berücksichtigt überzählige alte Dateien.
10. Archivierte Addon-Dateien in einer isolierten Testinstallation tatsächlich geschrieben, geprüft und erfolgreich zurückgenommen.
11. Erste Aktualisierung erzeugt einen neuen Snapshot und aktualisiert die aktuelle Vorlage, während der vorherige Snapshot unverändert erhalten bleibt.
12. Schreibfehler künstlich ausgelöst: bereits geschriebene Änderungen wurden zurückgerollt.
13. Rücksicherung und Konflikterkennung bei späteren Benutzereingriffen geprüft.
14. Manipuliertes Archiv abgewiesen; Symlink-Ziel außerhalb des Zielclients abgewiesen.
15. Echten Konfigurationsimport in der simulierten Zielinstallation angewendet: 51 Dateien. Zweiter Durchlauf: keine weiteren Änderungen.

## Grenzen des Tests

Die Tests liefen in isolierten Testordnern. Es wurde keine Release-Installation auf diesem Rechner verändert. Der Helfer für die Charaktererkennung wurde vorbereitet, aber noch nicht im zukünftigen Release-Client ausgeführt. Der Test bestätigt den Offline-Dateiimport und die Struktur der erhaltenen Einstellungen; die tatsächliche Darstellung und API-Kompatibilität der Addons sind beim ersten Release-Login zu prüfen.
