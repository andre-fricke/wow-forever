"""Check first-run selection and launcher behavior without a WoW installation."""

import io, os, shutil, subprocess, sys, tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w

with tempfile.TemporaryDirectory() as td:
    root = Path(td).resolve()
    install = root / "Applications/World of Warcraft"
    beta = install / "_classic_beta_"
    release = install / "_classic_"
    for client in (beta, release):
        (client / "WTF").mkdir(parents=True)
    custom = root / "External Drive/Custom Client"
    (custom / "WTF").mkdir(parents=True)
    with (
        patch.object(w, "INSTALL_ROOTS", (install, root / "missing")),
        redirect_stdout(io.StringIO()),
    ):
        with patch("builtins.input", return_value="1"):
            assert w.choose_client() == release
        with patch("builtins.input", return_value='"' + str(custom) + '"'):
            assert w.choose_client() == custom
        with patch("builtins.input", return_value=""):
            try:
                w.choose_client()
            except ValueError as error:
                assert str(error) == "No installation selected."
            else:
                raise AssertionError("Empty selection chose an installation")
    char = custom / "WTF/Account/NEW/Realm/Another-Player"
    char.mkdir(parents=True)
    (char / "AddOns.txt").write_text("")
    with (
        patch("builtins.input", return_value="1") as prompt,
        redirect_stdout(io.StringIO()),
    ):
        assert w.choose_character(custom) == char
        assert "Cannot" not in prompt.call_args.args[0]
    tool = root / "Tool with spaces"
    tool.mkdir()
    for name in ("WoW-Addon-Backup.command", "python_runtime.zsh"):
        shutil.copy2(w.HERE / name, tool / name)
    (tool / "wow_backup.py").write_text('import sys\nprint("LAUNCH_OK")\nsys.exit(7)\n')
    bin_dir = root / "Custom Python/bin"
    bin_dir.mkdir(parents=True)
    compatible = bin_dir / "python3"
    # Delegate to this test's real interpreter, including when its path has spaces.
    import shlex

    compatible.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' "$@"\n')
    compatible.chmod(0o755)
    old = root / "old-python"
    old.write_text("#!/bin/sh\nexit 1\n")
    old.chmod(0o755)

    def resolve(*candidates):
        return subprocess.run(
            [
                "/bin/zsh",
                "-c",
                'source "$1"; shift; find_python_runtime "$@"',
                "test",
                str(tool / "python_runtime.zsh"),
                *map(str, candidates),
            ],
            capture_output=True,
            text=True,
        )

    result = resolve(root / "missing-python", old, compatible)
    assert result.returncode == 0 and result.stdout.strip() == str(compatible), result
    assert resolve(old, root / "missing").returncode == 1
    env = dict(os.environ, PATH=str(bin_dir) + ":/usr/bin:/bin")
    result = subprocess.run(
        ["/bin/zsh", str(tool / "WoW-Addon-Backup.command")],
        input="\n",
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
    )
    assert result.returncode == 7 and "LAUNCH_OK" in result.stdout, (
        result.stdout,
        result.stderr,
    )
print(
    "PASS explicit client/character selection, custom paths, runtime fallback, missing runtime, launcher paths and exit status"
)
