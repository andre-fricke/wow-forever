"""Exercise repeated interactive actions without touching a WoW installation."""
import io, sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import wow_backup as w

# A backup can be followed immediately by another action in the same session.
with patch('builtins.input',side_effect=['1','4','0']), \
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
