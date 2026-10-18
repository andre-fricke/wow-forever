"""Account migration must leave all existing characters and shared profiles intact."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w

source = {
    "name": "Old",
    "full": "Old Name",
    "realm": "Beta",
    "guid": "Player-1",
    "class": "DRUID",
}
target = {
    "name": "New",
    "full": "New Name",
    "realm": "Release",
    "guid": "Player-2",
    "class": "DRUID",
}
backup = {
    "DB": {
        "profileKeys": {"Old Name": "Shared"},
        "profiles": {"Shared": {"width": 220, "owner": "Old Name", "guid": "Player-1"}},
        "char": {"Old Name": {"completed": 999}},
    }
}
existing = {
    "DB": {
        "profileKeys": {
            "Old Name": "Shared",
            "New Name": "Shared",
            "Third Name": "New Name",
        },
        "profiles": {"Shared": {"width": 100}, "New Name": {"width": 300}},
        "char": {
            "Old Name": {"completed": 99, "guid": "Player-1"},
            "New Name": {"completed": 7, "guid": "Player-2"},
        },
        "realm": {"Beta": {"data": "Old Name"}},
        "factionrealm": {"Horde - Beta": {"data": "Player-1"}},
    }
}
result = w.plain(
    w.parse(
        w.account_config("TestAce", w.dump(backup), w.dump(existing), source, target)
    )
)
r = result["DB"]
for key in ("char", "realm", "factionrealm"):
    assert r[key] == existing["DB"][key], key
for key in ("Old Name", "Third Name"):
    assert r["profileKeys"][key] == existing["DB"]["profileKeys"][key]
for key, profile in existing["DB"]["profiles"].items():
    assert r["profiles"][key] == profile
selected = r["profileKeys"]["New Name"]
assert selected == "New Name [UI Backup]"
assert r["profiles"][selected] == {
    "width": 220,
    "owner": "New Name",
    "guid": "Player-2",
}
assert r["profileKeys"]["New - Release"] == selected
# A repeated restore reuses the same profile; it does not append copies forever.
second = w.plain(
    w.parse(w.account_config("TestAce", w.dump(backup), w.dump(result), source, target))
)
assert second == result
# Fresh accounts also get a private target profile, without stale beta characters.
fresh = w.plain(
    w.parse(w.account_config("TestAce", w.dump(backup), None, source, target))
)["DB"]
assert set(fresh["profiles"]) == {"New Name"} and not fresh.get("char")
# RestedXP's untouched target guide data may contain a source name/GUID.
char = {
    "RXPCData": {"currentStep": 7, "partyMember": "Old Name", "guid": "Player-1"},
    "RXPCTrackingData": {"Old Name": {"level": 42}},
}
restored = w.plain(
    w.parse(
        w.character_config(
            "RXPGuides", w.dump({"RXPCData": {}}), w.dump(char), source, target
        )
    )
)
assert restored == char
print(
    "PASS same-account migration, other characters, shared profile collision, progression, fresh accounts and repeat restores"
)
