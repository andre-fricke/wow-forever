import sys, tempfile, zipfile, json, shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import wow_backup as w

def assert_equal(a,b,message):
 assert a==b,message

def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_bytes(data if isinstance(data,bytes) else data.encode())

def test_lua_and_mapping():
 data='D = {["ü Name"] = "Line\\nA\\001", [3] = {true, false, nil}, ["路径"] = "Interface\\\\Icons"}'.encode()
 assert w.plain(w.parse(w.dump(w.parse(data))))==w.plain(w.parse(data))
 s={'name':'Old','full':'Old Surname','realm':'Beta Realm','guid':'Player-1-OLD','class':'DRUID'}
 t={'name':'New','full':'New Surname','realm':'Release Realm','guid':'Player-2-NEW','class':'SHAMAN'}
 config=b'DB = {profileKeys = {["Old Surname"] = "Old Surname"}, profiles = {["Old Surname"] = {width=144, color={1,0.5,0}, playerGUID="Player-1-OLD"}}, char={["Old Surname"]={quests={99}}}}'
 target=b'DB = {char = {["New Surname"] = {quests={12}, guid="Player-2-NEW"}}}'
 result=w.plain(w.parse(w.account_config('Test',config,target,s,t)))['DB']
 assert result['profileKeys']['New - Release Realm']=='New Surname'
 assert result['profiles']['New Surname']['playerGUID']==t['guid']
 assert result['profiles']['New Surname']['width']==144
 assert result['char']=={'New Surname':{'quests':{1:12},'guid':t['guid']}}
 assert 'Old Surname' not in result['char']
 print('PASS Lua roundtrip, Unicode, new realm/GUID, preserved target progression')

def test_restedxp_profiles():
 s={'name':'Old','full':'Old Surname','realm':'Beta Realm','realmKey':'PvP','guid':'Player-1','class':'DRUID'}
 t={'name':'New','full':'New Surname','realm':'Release Realm','realmKey':'PvE','guid':'Player-2','class':'DRUID'}
 visual={'width':220,'height':125,'x':238,'y':-108,'color':{1:0.4,2:0.7,3:1}}
 for active_key in ['Old Surname','Old - PvP']:
  # Include stale destination and full-name profiles, as seen in real saves.
  keys={'Old Surname':'Old Surname','New - PvE':'New - PvE',active_key:active_key}
  profiles={'Old Surname':{'width':99},'New - PvE':{'width':42},active_key:visual}
  data=w.dump({'RXPSettings':{'profileKeys':keys,'profiles':profiles}})
  result=w.plain(w.parse(w.account_config('RXPGuides',data,data,s,t)))['RXPSettings']
  selected=result['profileKeys']['New - PvE']
  assert result['profiles'][selected]==visual
  assert result['profileKeys']['New Surname']==selected
  assert result['profileKeys']['New - Release Realm']==selected
 # Classic/non-regional clients and older identities without realmKey.
 s.pop('realmKey');t.pop('realmKey')
 data=w.dump({'RXPSettings':{'profileKeys':{'Old - Beta Realm':'Shared'},'profiles':{'Shared':visual}}})
 result=w.plain(w.parse(w.account_config('RXPGuides',data,None,s,t)))['RXPSettings']
 assert result['profiles'][result['profileKeys']['New - Release Realm']]==visual
 # Per-character UI defaults transfer without copying guide progress.
 source=w.dump({'RXPCData':{'localDB':{'profile':visual},'currentStep':99}})
 target=w.dump({'RXPCData':{'currentStep':7}})
 result=w.plain(w.parse(w.character_config('RXPGuides',source,target,s,t)))
 assert result['RXPCData']['localDB']['profile']==visual
 assert result['RXPCData']['currentStep']==7
 print('PASS RestedXP legacy/ruleset profiles, changed realms, visual settings and target progress')

def test_forever_dual_gathering(tmp):
 client=tmp/'gathering-client'
 char=client/'WTF/Account/TEST/Realm/Character'
 settings={'ForeverDualGatheringDB':{'version':14,'hud':{'x':120,'y':-25,'size':430,'mapAlpha':0.08,'trackingInterval':5},'minimap':{'minimapPos':220,'hide':False},'toggleKey':'CTRL-G'}}
 data=w.dump(settings)
 write(client/'Interface/AddOns/ForeverDualGathering/ForeverDualGathering.toc','## SavedVariables: ForeverDualGatheringDB')
 write(char.parent.parent/'SavedVariables/ForeverDualGathering.lua',data)
 assert w.audit_support(client,char)==[]
 source={'name':'Old','full':'Old Name','realm':'Beta','guid':'Player-1'}
 target={'name':'New','full':'New Name','realm':'Release','guid':'Player-2'}
 assert w.plain(w.parse(w.account_config('ForeverDualGathering',data,None,source,target)))==settings
 manifest={'unsupported':['Account file: ForeverDualGathering.lua','Account file: Unknown.lua','Character file: Unknown.lua']}
 assert w.pending_reviews(manifest)==manifest['unsupported'][1:]
 assert len(manifest['unsupported'])==3
 assert w.pending_reviews({'unsupported':['Kontodatei: ForeverDualGathering.lua']})==[]
 print('PASS ForeverDualGathering settings and existing-backup support reassessment')

def test_position_sequence_serialization():
 # Match the actual RestedXP SetPoint argument list, including the nil parent.
 original=b'DB = {framePositions = {RXPFrame = {{"LEFT", nil, "LEFT", 0, -136.7}}}, frameSizes = {RXPFrame = {220, 28}}}'
 parsed=w.parse(original)
 emitted=w.dump(parsed)
 assert b'"LEFT",\nnil,\n"LEFT",\n0,\n-136.7,' in emitted
 assert b'[1] =' not in emitted and b'[2] =' not in emitted
 assert w.plain(w.parse(emitted))==w.plain(parsed)
 # Unordered numeric keys still produce the correct argument order.
 assert w.dump({'DB':{3:'LEFT',5:-136.7,1:'LEFT',4:0,2:None}})==b'DB = {\n"LEFT",\nnil,\n"LEFT",\n0,\n-136.7,\n}\n'
 sparse={'DB':{1:'first',100:'last','label':'mixed'}}
 assert w.plain(w.parse(w.dump(sparse)))==sparse
 print('PASS Lua position sequences retain nil slots, order and sparse table semantics')

def test_transaction(tmp):
 client=tmp/'transaction';client.mkdir();write(client/'same','before')
 recovery=w.RECOVERY;w.RECOVERY=tmp/'recovery'
 transaction=w.apply_plan(client,{'same':b'after','new':b'new'},'test')
 assert (client/'same').read_bytes()==b'after'
 w.undo(transaction)
 assert (client/'same').read_bytes()==b'before' and not (client/'new').exists()
 real=w.atomic_payload;count=0
 def fail(path,data):
  nonlocal count
  count+=1
  if count==2:raise OSError('Injected write failure')
  return real(path,data)
 w.atomic_payload=fail
 try:
  try:w.apply_plan(client,{'same':b'changed','new2':b'new2'},'rollback test')
  except OSError:pass
  else:raise AssertionError('Injected error did not happen')
 finally:w.atomic_payload=real
 assert (client/'same').read_bytes()==b'before' and not (client/'new2').exists()
 # Reject a later edit rather than erasing it during undo.
 tx=w.apply_plan(client,{'same':b'after2'},'conflict test');write(client/'same','user-edit')
 try:w.undo(tx)
 except ValueError:pass
 else:raise AssertionError('Undo accepted conflicting user edit')
 assert (client/'same').read_text()=='user-edit'
 w.RECOVERY=recovery
 print('PASS transactional writes, rollback, undo and conflict detection')

def test_legacy_recovery(tmp):
 client=tmp/'legacy-client';client.mkdir();write(client/'settings','original')
 recovery,legacy=w.RECOVERY,w.LEGACY_RECOVERY
 w.RECOVERY=tmp/'compatibility'/'Recovery';w.LEGACY_RECOVERY=tmp/'compatibility'/'Ruecksicherungen'
 try:
  transaction=w.apply_plan(client,{'settings':b'changed'},'compatibility test')
  assert (transaction/'before.zip').is_file()
  assert w.recovery_entries()==[transaction]
  # Simulate a record written by the earlier German version.
  w.LEGACY_RECOVERY.mkdir()
  old=w.LEGACY_RECOVERY/transaction.name
  transaction.rename(old)
  (old/'before.zip').rename(old/'vorher.zip')
  assert w.recovery_entries()==[old]
  w.undo(old)
  assert (client/'settings').read_text()=='original'
  entries=w.recovery_entries()
  assert len(entries)==2 and entries[0].is_relative_to(w.RECOVERY) and entries[1]==old
 finally:
  w.RECOVERY,w.LEGACY_RECOVERY=recovery,legacy
 print('PASS English recovery archives and legacy recovery discovery/undo')

if __name__ == '__main__':
 test_lua_and_mapping()
 test_position_sequence_serialization()
 test_restedxp_profiles()
 with tempfile.TemporaryDirectory() as name:
  test_forever_dual_gathering(Path(name).resolve())
  test_transaction(Path(name).resolve())
  test_legacy_recovery(Path(name).resolve())
 print('All core tests passed.')
