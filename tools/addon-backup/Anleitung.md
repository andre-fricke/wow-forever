# WoW-Addon-Backup: letzter Beta-Tag → erster Release-Tag

Start: **WoW-Addon-Backup.command** im Finder doppelklicken. Das öffnet ein Menü in Terminal. Den gesamten Ordner `tools/addon-backup` zusammenhalten: Er enthält das Werkzeug, die Charaktererkennung, Backups und spätere Rücksicherungen.

## Was jetzt bereits vorhanden ist

Ein vollständiger Stand der aktuell auf der Festplatte gespeicherten Beta-Einstellungen von **Cannot Hotalot** vom 14.10.2026. Er enthält 72 Addon-Ordner und insgesamt 8.414 Dateien; das ZIP ist rund 163 MiB groß. Das Backup wurde auf Integrität geprüft. Dieser persönliche Stand liegt nur in der lokalen Arbeitskopie und ist nicht im Git-Repository enthalten.

Das neue Werkzeug ersetzt für den Beta→Release-Umzug den früheren direkten Charaktertransfer. Die alten Sicherungen im Ordner `WoW-Addon-Vorlage` bleiben als Rücksicherung der dort vorgenommenen Änderungen erhalten.

## Morgen oder am letzten Beta-Tag: Backup aktualisieren

1. Mit dem Vorlagencharakter die gewünschten Einstellungen vornehmen.
2. WoW **vollständig beenden**. Ein `/reload` allein genügt nicht für diesen Arbeitsablauf.
3. **WoW-Addon-Backup.command** doppelklicken.
4. **1 – Backup erstellen / aktualisieren** auswählen.
5. Beta-Installation und Vorlagencharakter auswählen. Aktuell sind `_classic_beta_` und `Cannot Hotalot` vorgeschlagen.
6. Bestätigen, dass WoW beendet ist. Warten, bis „Backup geprüft“ erscheint.

Jeder Durchlauf erstellt einen neuen, vollständigen ZIP-Stand unter `Backups`. `latest.json` zeigt auf das neueste erfolgreiche Backup. Frühere Stände werden nicht überschrieben. Änderungen an Einstellungen und neu installierte Addon-Dateien werden beim nächsten Backup neu eingelesen. Falls eine neu hinzugekommene Konfiguration noch keinen geprüften Importadapter hat, meldet das Werkzeug das bereits beim Backup; diese Meldung vor dem Release prüfen lassen.

Anschließend kannst du den gesamten Werkzeugordner auf ein anderes Laufwerk kopieren. Die Wiederherstellung benötigt die ursprüngliche Beta-Installation nicht mehr.

## Am Release-Tag

1. Den **Release-Client** installieren. Wenn es aktualisierte Release-Versionen deiner Addons gibt, diese installieren; das Werkzeug erhält standardmäßig bereits vorhandene Addon-Versionen.
2. Den neuen Charakter erstellen, einmal einloggen und WoW vollständig beenden. Dadurch entstehen sein Account-, Realm- und Charakterordner.
3. **WoW-Addon-Backup.command** starten und **2 – Backup auf Release-Charakter einspielen** wählen.
4. Das neueste Backup mit Enter übernehmen oder einen anderen ZIP-Stand auswählen.
5. Den **Release-Installationsordner** wählen – nicht die alte Beta-Installation. Alternativ kannst du einen vollständigen Pfad eingeben; der Ordner muss `WTF` und den Client enthalten.
6. Den neuen Charakter per Name oder Nummer auswählen und bestätigen, dass WoW beendet ist.
7. Das Werkzeug installiert fehlende Addon-Dateien, übernimmt die Aktivierung für diesen Charakter und installiert die kleine lokale **WoW UI Transfer Identity**-Erkennung.
8. Beim ersten Durchlauf fordert es dich zu **einem zusätzlichen Login mit diesem Charakter** auf. Danach WoW vollständig beenden und im Werkzeug Enter drücken. Die Erkennung speichert den tatsächlichen Namen, Realm, die GUID und Klasse lokal. Bei Bedarf im **AddOns**-Menü „WoW UI Transfer Identity“ aktivieren; falls der Client es als veraltet einstuft, **Load out of date AddOns** aktivieren.
9. Ziel und Änderungsübersicht prüfen, dann `WIEDERHERSTELLEN` eingeben.
10. Nach „Dateien geschrieben und geprüft“ WoW starten. Die Charaktererkennung ist für diesen Charakter anschließend deaktiviert.

Der zusätzliche Login ist für eine zuverlässige Identitätsermittlung vorgesehen. Ein numerischer Realmordner wie `70` reicht nicht aus, um den späteren Realm oder die neue GUID zu erraten. Du musst diese Werte nicht selbst herausfinden oder eingeben.

## Was wiederhergestellt wird

- Installierte Addon-Pakete aus dem Backup, soweit sie im Ziel fehlen. Vorhandene Release-Versionen werden standardmäßig behalten.
- Welche Addons für den Zielcharakter eingeschaltet und ausgeschaltet sind. Zusätzliche Ziel-Addons, die nicht im Backup waren, werden für diesen Charakter deaktiviert.
- Kontoweite und charakterbezogene Addon-Einstellungen über geprüfte Adapter: Profile, Farben, Schriftarten, Positionen, Größen, Skalierung und Anker.
- EllesmereUIs vollständige visuelle Profile, das aktive Profil, UI-Skalierung, Farben, Schriftarten und Layout-Verknüpfungen.
- WoW-Edit-Mode-Layouts, gespeicherte Fensterpositionen und Chat-Fenstergeometrie.
- Tastenzuweisungen und ausgewählte UI-/Darstellungsvariablen, einschließlich UI-Skalierung, Helligkeit, Kontrast, Nameplate- und Schadensanzeigen-Einstellungen.
- Bekannte Namensformate, Realmbezüge und exakte eigene GUID-Verweise werden auf die vom Release-Client ermittelte Identität umgesetzt.

**Kontoweite Einstellungen gelten auch für andere Charaktere desselben Zielaccounts.** Das Werkzeug sichert die betroffenen Zieldateien vorher. Für einen frischen Release-Account ist die vollständige Übernahme vorgesehen; bei einem bereits intensiv genutzten Account sollte dieser gemeinsame Umfang berücksichtigt werden.

## Charakterdaten und Klassen

Questfortschritt, Taschen-/Ausrüstungsdaten, Gold, Guidefortschritt und andere bekannte laufende Charakterdaten werden beim Import nicht vom Beta-Charakter auf den neuen Charakter übertragen. Sie bleiben im vollständigen Rohbackup enthalten, werden aber bei der Einstellungsübernahme ausgespart beziehungsweise durch vorhandene Zieldaten ersetzt.

Die Zauber in Aktionsleisten und andere serverseitige Charakterdaten werden dadurch nicht erzeugt. Makro-Dateien werden nicht automatisch eingespielt. Bei einer anderen Klasse können Zauber, Makro-bezogene Tasten und Click-Casting eine Anpassung im Spiel benötigen. Die GUI-Anordnung wird übernommen. Bei EllesmereUI wird das gesicherte aktive Layout verwendet; automatische Beta-Spezialisierungswechsel werden für den Import zurückgesetzt.

## Grenze der Release-Zusage

Das Werkzeug kann Dateien, Einstellungen und die Zuordnung zum neuen Charakter sichern und wiederherstellen. Ob eine heutige Beta-Addon-Version am Release-Tag geladen wird und mit den dann vorhandenen Spiel-APIs funktioniert, lässt sich heute nicht garantieren. Bestehende Release-Versionen bleiben deshalb erhalten; Versionsunterschiede werden angezeigt. Ein großer Wechsel des Addon-Einstellungsformats kann einen angepassten Importadapter erfordern.

Der Ablauf wurde mit einer simulierten leeren Release-Installation, neuem Account, anderem Realm, neuer GUID und anderer Klasse getestet. Der zukünftige Release-Client selbst konnte noch nicht getestet werden.

## Rückgängig machen

**3 – Letzte Änderungen rückgängig machen** wählen. Die Vorbereitung der Addon-Dateien und die eigentliche Einstellungsübernahme sind getrennte Vorgänge. Mehrere Vorgänge in umgekehrter Reihenfolge rückgängig machen: zuerst die Einstellungen, danach bei Bedarf die Vorbereitung.

Die Rücksicherungen liegen unter `Ruecksicherungen`. Spätere Änderungen an betroffenen Dateien werden erkannt; das Werkzeug stoppt dann, statt neuere Einstellungen zu überschreiben. Ein neuer Rückgängig-Vorgang erstellt wiederum eine eigene Rücksicherung.

## Backup prüfen

**4 – Backup prüfen** kontrolliert die gespeicherten Prüfsummen aller archivierten Dateien. Bei einem beschädigten Backup wird vor dem Einspielen abgebrochen.

## Für technische Verwendung

`wow_backup.py` besitzt zusätzlich die Befehle `backup`, `verify`, `prepare`, `restore` und `undo`. `prepare` und `restore` zeigen ohne `--apply` nur eine Vorschau. Schreibende CLI-Vorgänge benötigen `--closed`; damit bestätigt der Aufrufer, dass WoW vollständig beendet ist. `--replace-addons` ist eine explizite Option für `prepare`, um auch vorhandene Versionen durch die gesicherten Dateien zu ersetzen. Im normalen Menü werden vorhandene Versionen behalten.
