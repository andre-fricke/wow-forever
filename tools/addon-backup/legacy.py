"""Read compatibility for historical labels without modifying stored records."""


def english_legacy_text(text):
    """Translate old tool messages without modifying names, paths, or saved records."""
    # German literals here are input compatibility keys, never new UI messages.
    prefix = ""
    while text.startswith(("Rückgängig: ", "Undo: ")):
        marker = "Undo: " if text.startswith("Undo: ") else "Rückgängig: "
        prefix += "Undo: "
        text = text[len(marker) :]
    exact = {
        "Addon-Dateien und Charaktererkennung vorbereiten": "Prepare addon files and character detection",
        "Charaktererkennung für Backup vorbereiten": "Prepare character detection for backup",
    }
    if text in exact:
        return prefix + exact[text]
    for old, new in (
        ("UI-Backup auf ", "Restore UI backup to "),
        ("Kontodatei: ", "Account file: "),
        ("Charakterdatei: ", "Character file: "),
    ):
        if text.startswith(old):
            return prefix + new + text[len(old) :]
    return prefix + text
