# Architecture and maintenance

The tool has no third-party runtime dependencies. Keep all Python modules and the launcher files together when distributing it. Existing schema-1 backup ZIPs, flat backup directories, and legacy recovery archives remain readable.

| Module | Responsibility |
| --- | --- |
| `wow_backup.py` | Menu, CLI, shared operation orchestration and compatibility API |
| `models.py` | Storage paths, validated identity/manifest metadata and file-plan preconditions |
| `characters.py` | Character discovery, helper identity and addon inventory |
| `addon_adapters.py` | Central addon policy registry and reviewed settings transformations |
| `addon_support.py` | Support assessment and unknown-addon filtering for both interfaces |
| `saved_variables.py`, `lua_saved.py` | Data-only Lua parsing and serialization |
| `archives.py` | Backup creation, verification, discovery and deletion |
| `restore.py` | Read-only installation, settings and macro plans |
| `recovery.py` | Transactional writes, rollback and recovery-point restoration |
| `file_ops.py` | Path containment, hashes and atomic file operations |
| `runtime.py` | WoW process detection and bounded waiting |
| `legacy.py` | Compatibility with old labels |

## Profile ownership

Imported source data may be remapped; preserved destination data must never be remapped. Account-level AceDB character/realm state is restored from the destination after mapping source settings. Per-character adapters start with untouched destination data and copy only reviewed source fields.

For AceDB profiles, import the selected source profile into a private destination profile, preserve all other profiles and mappings, and avoid collisions with shared names. Repeated restores must reuse the private profile. Account-wide addon settings without character profiles remain shared by design; they cannot be made character-local by this tool.

Add support through `POLICIES` and the corresponding transformation in `addon_adapters.py`. Cover the new format with synthetic fixtures, including a destination with existing data. Unknown formats remain opt-in skips, never implicit raw copies.

## Write boundaries

Plans are read-only. For known identities, installation and settings form one restore plan, confirmed once and applied with one recovery point. Identity detection, if necessary, is a distinct, explicitly accepted preparation. Both interfaces use the process guard; the final plan also records destination hashes and refuses stale previews.

Backup checksums verify archive integrity, not future game compatibility. Never execute personal SavedVariables to inspect them. Lua runtime tests execute only synthetic fixtures.

## Development

- Run `python3 -B run_tests.py`; tests use temporary directories.
- Run `python3 -B run_tests.py --require-lua` with Lua 5.1 available for release validation. `LUA_RUNTIME` can select a temporary local build.
- Install `black==25.1.0` for development formatting; run `black --target-version py39 .` from this directory.
- The optional `tests/test_saved_snapshot.py /path/to/backup.zip` checks a compatible local development snapshot, restoring only into a temporary client. It is not part of CI and no personal data should be committed.
- Keep backup schema compatibility tests, same-account profile tests and full workflow tests when changing adapters or orchestration.

Live addon rendering and future release-client compatibility still require an in-game check. A passing Python/Lua suite does not claim that every addon version is supported.
