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

# Prat module namespaces must follow the selected parent profile.
prat = {"Prat3DB": {
    "profileKeys": {"Old Name": "Default"},
    "profiles": {"Default": {"modules": {"Editbox": 2, "Font": 2}}},
    "namespaces": {
        "Prat_Editbox": {"profiles": {"Default": {
            "attach": "FREE", "editX": 627, "editY": 524, "editW": 598,
            "border": "None", "font": "Friz Quadrata TT",
        }}},
        "Prat_Font": {"profiles": {"Default": {
            "size": {"ChatFrame1": 15, "ChatFrame2": 14},
        }}},
        "Prat_Buttons": {"profiles": {"Other": {"showMenu": False}}},
    },
}}
old_prat = {"Prat3DB": {
    "profileKeys": {"New Name": "Shared", "Third Name": "Shared"},
    "profiles": {"Shared": {"modules": {"Font": 2}}},
    "namespaces": {
        "Prat_Editbox": {
            "profiles": {"Shared": {"border": "Blizzard Tooltip"},
                         "New Name": {"editX": 999}},
            "char": {"New Name": {"history": "keep"}},
            "global": {"keep": True},
        },
        "Prat_Font": {"profiles": {"Shared": {"size": {"ChatFrame2": 12}}}},
        "TargetOnly": {"profiles": {"Shared": {"width": 400}}},
    },
}}
def restore_prat(existing):
    return w.plain(w.parse(w.account_config(
        "Prat-3.0", w.dump(prat), w.dump(existing) if existing else None,
        source, target,
    )))

result = restore_prat(old_prat)
root = result["Prat3DB"]
selected = root["profileKeys"]["New Name"]
# Avoid names occupied only in a namespace as well.
assert selected == "New Name [UI Backup]"
for module in ("Prat_Editbox", "Prat_Font"):
    assert root["namespaces"][module]["profiles"][selected] == (
        prat["Prat3DB"]["namespaces"][module]["profiles"]["Default"]
    )
for module, state in old_prat["Prat3DB"]["namespaces"].items():
    for key, value in state.items():
        if key == "profiles":
            for profile, settings in value.items():
                assert root["namespaces"][module]["profiles"][profile] == settings
        else:
            assert root["namespaces"][module][key] == value
# Missing module overrides reset to defaults, including target-only modules.
assert root["namespaces"]["Prat_Buttons"]["profiles"][selected] == {}
assert root["namespaces"]["TargetOnly"]["profiles"][selected] == {}
assert restore_prat(result) == result
fresh = restore_prat(None)["Prat3DB"]
assert fresh["namespaces"]["Prat_Font"]["profiles"]["New Name"]["size"]["ChatFrame2"] == 14
assert set(fresh["namespaces"]["Prat_Editbox"]["profiles"]) == {"New Name"}
# A later backup with default settings clears stale destination overrides.
prat["Prat3DB"]["namespaces"]["Prat_Editbox"]["profiles"].pop("Default")
assert restore_prat(result)["Prat3DB"]["namespaces"]["Prat_Editbox"]["profiles"][selected] == {}
# Namespace migration does not copy Prat's per-character chat history.
history = b'Prat3CharDB = { history = { "private target chat" } }'
assert w.character_config("Prat-3.0", b'Prat3CharDB = {}', history, source, target) == history
print("PASS Prat editbox layout/border, chat/combat-log fonts, module defaults, namespace collisions, other characters and repeat restores")
