"""Exercise repeated interactive actions without touching a WoW installation."""
import io, sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import wow_backup as w

# A backup can be followed immediately by another action in the same session.
with patch('builtins.input',side_effect=['1','1','1','3','0']), \
     patch.object(w,'choose_client',return_value=Path('/test/client')), \
     patch.object(w,'choose_character',return_value=Path('/test/character')), \
     patch.object(w,'closed_prompt'), patch.object(w,'identity',return_value={'name':'Test'}), \
     patch.object(w,'create_backup') as backup, \
     patch.object(w,'choose_snapshot',return_value=Path('/test/snapshot.zip')), \
     patch.object(w,'verify_backup',return_value={'files':{},'addons':{},'created':'test','unsupported':[]}) as verify, \
     redirect_stdout(io.StringIO()) as output:
    w.menu()
    backup.assert_called_once();verify.assert_called_once()
    assert output.getvalue().count('0  Exit')==3

# Invalid selections and interrupted actions do not terminate the session.
with patch('builtins.input',side_effect=['invalid',KeyboardInterrupt(),'0']), \
     redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
    w.menu()
    assert 'Unknown selection' in errors.getvalue()
    assert 'Action cancelled' in output.getvalue()
    assert output.getvalue().count('0  Exit')==3

# Closed stdin exits rather than spinning forever.
with patch('builtins.input',side_effect=EOFError()), redirect_stdout(io.StringIO()) as output:
    w.menu()
    assert output.getvalue().count('0  Exit')==1
print('PASS repeated menu actions, explicit exit, recoverable errors, interruption and EOF')

# Returning from undo must never select an entry, including through negative indexing.
for answer in ('0','','  ','-1','2','invalid','1'):
    entry=Path('/test/recovery/entry')
    with patch('builtins.input',side_effect=['3','1',answer,'0']), \
         patch.object(w,'recovery_entries',return_value=[entry]), \
         patch.object(Path,'read_text',return_value='{"label":"Test restore","status":"complete"}'), \
         patch.object(w,'closed_prompt') as closed, patch.object(w,'undo') as undo, \
         redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
        w.menu()
        assert '0: Back to main menu' in output.getvalue()
        assert output.getvalue().count('0  Exit')==2
        if answer=='1':
            closed.assert_called_once();undo.assert_called_once_with(entry)
        else:
            closed.assert_not_called();undo.assert_not_called()
print('PASS undo return, empty input, invalid indices and explicit selection')

# Both nested menus support a no-action return.
for answers in (['1','0','0'],['2','','0'],['3','0','0']):
    with patch('builtins.input',side_effect=answers), redirect_stdout(io.StringIO()) as output:
        w.menu()
        assert output.getvalue().count('0  Exit')==2
# Macro backup is dispatched separately from addon backup.
with patch('builtins.input',side_effect=['1','2','0']), \
     patch.object(w,'choose_client',return_value=Path('/test/client')), \
     patch.object(w,'choose_character',return_value=Path('/test/character')), \
     patch.object(w,'closed_prompt'), patch.object(w,'identity',return_value={'name':'Test'}), \
     patch.object(w,'create_backup') as backup, redirect_stdout(io.StringIO()):
    w.menu()
    backup.assert_called_once_with(Path('/test/client'),Path('/test/character'),kind='macros')
print('PASS backup submenus, macro dispatch and back navigation')

# Legacy tool labels are translated, but embedded character names are left intact.
assert w.english_legacy_text('Addon-Dateien und Charaktererkennung vorbereiten')=='Prepare addon files and character detection'
assert w.english_legacy_text('Charaktererkennung für Backup vorbereiten')=='Prepare character detection for backup'
assert w.english_legacy_text('Rückgängig: UI-Backup auf Miese Makrele – Realm')=='Undo: Restore UI backup to Miese Makrele – Realm'
assert w.english_legacy_text('Undo: Rückgängig: UI-Backup auf Name')=='Undo: Undo: Restore UI backup to Name'
assert w.english_legacy_text('Kontodatei: Example.lua')=='Account file: Example.lua'
assert w.english_legacy_text('Charakterdatei: Example.lua')=='Character file: Example.lua'
assert w.english_legacy_text('Restore macros to Name')=='Restore macros to Name'
with patch('builtins.input',side_effect=['3','1','0','0']), \
     patch.object(w,'recovery_entries',return_value=[Path('/test/recovery/entry')]), \
     patch.object(Path,'read_text',return_value='{"label":"UI-Backup auf Miese Makrele","status":"complete"}'), \
     patch.object(w,'undo') as undo, redirect_stdout(io.StringIO()) as output:
    w.menu()
    assert 'Restore UI backup to Miese Makrele' in output.getvalue()
    assert 'UI-Backup auf' not in output.getvalue()
    undo.assert_not_called()
print('PASS English legacy labels and unchanged character names')
