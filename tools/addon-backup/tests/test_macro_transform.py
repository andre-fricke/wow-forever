"""One import policy feeds cache files, runtime macros and placement identities."""
import sys
import tempfile
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from macro_transform import transform_body, transform_cache, compile_variants
from restore import macro_plan
from saved_variables import dump, parse, plain
from file_ops import sha

body = '#showtooltip Healing Touch\r\n/cast [@mouseover,help][help] Healing Touch; [harm] Wrath\r\n/castsequence reset=target/5 [mod:alt] Moonfire, Rejuvenation, null\n/use 13\n/use Healthstone\n/run print("Healing Touch")\n/say Healing Touch\n'
expected = '#showtooltip Healing Touch\r\n/cast [@mouseover,help][help] null; [harm] null\r\n/castsequence reset=target/5 [mod:alt] null, null, null\n/use 13\n/use Healthstone\n/run print("Healing Touch")\n/say Healing Touch\n'
assert transform_body(body, True) == expected
assert transform_body(body, False) == body
assert transform_body(expected, True) == expected
assert transform_body('/cast [help] Heilende Berührung(Rang 2)', True) == '/cast [help] null'
data = ('VER 3 010000001 "Heal" "123"\r\n'+body+'END\r\n').encode()
assert transform_cache(data, True) == ('VER 3 010000001 "Heal" "123"\r\n'+expected+'END\r\n').encode()
assert transform_cache(data) == data
entry = dict(name="Heal",body=body,scope="character")
template = {"macros":{121:entry},"slots":{5:entry},"clickMacros":{123:entry}}
compile_variants(template)
for key,index in (("macros",121),("slots",5),("clickMacros",123)):
    assert template["differentClass"][key][index]["body"] == expected
    assert template[key][index]["body"] == body
try:
    transform_cache(b'VER 3 1 "Heal" "1"\n/cast Heal\n', True)
except ValueError:
    pass
else:
    raise AssertionError("Truncated cache accepted")
print("PASS shared macro transformation: conditionals, sequences, Unicode, CRLF, untouched commands, cache files and all runtime identities")

with tempfile.TemporaryDirectory() as temp:
    client = Path(temp)
    char = client / "WTF/Account/A/Realm/Target"
    saved = char / "SavedVariables/WoWUITransferIdentity.lua"
    saved.parent.mkdir(parents=True)
    saved.write_bytes(dump({"WoWUITransferIdentity": dict(name="Target",full="Target",realm="Realm",guid="Player-target",**{"class":"SHAMAN"})}))
    source = "WTF/Account/B/Beta/Source"
    helper_member = "client/"+source+"/SavedVariables/WoWUITransferIdentity.lua"
    macro_member = "client/"+source+"/macros-cache.txt"
    payloads = {macro_member:data, helper_member:dump({"WoWUITransferBars":{"schema":2,"macroActions":1,"slots":{5:entry}}})}
    manifest = {"kind":"macros","source_character":source,"source_identity":{"class":"DRUID"},"files":{k:{"sha256":sha(v)} for k,v in payloads.items()}}
    archive=client/"fixture.zip"
    with zipfile.ZipFile(archive,"w") as z:
        for key,value in payloads.items(): z.writestr(key,value)
    files,_=macro_plan(archive,manifest,client,char,restore_slots=True)
    assert files[(char/"macros-cache.txt").relative_to(client).as_posix()]==transform_cache(data,True)
    pending=plain(parse(files[saved.relative_to(client).as_posix()]))["WoWUITransferBarsPending"]
    assert pending["slots"][5]["body"]==template["differentClass"]["slots"][5]["body"]
    assert saved.read_bytes().find(b"Pending")==-1
print("PASS offline macro file and pending action slots use the same bodies as automatic templates")
