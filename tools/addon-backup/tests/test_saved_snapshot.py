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
 data='D = {["ü Name"] = "Zeile\\nA\\001", [3] = {true, false, nil}, ["路径"] = "Interface\\\\Icons"}'.encode()
 assert w.plain(w.parse(w.dump(w.parse(data))))==w.plain(w.parse(data))
 s={'name':'Alt','full':'Alt Nachname','realm':'Beta Realm','guid':'Player-1-OLD','class':'DRUID'}
 t={'name':'Neu','full':'Neu Nachname','realm':'Release Realm','guid':'Player-2-NEW','class':'SHAMAN'}
 config=b'DB = {profileKeys = {["Alt Nachname"] = "Alt Nachname"}, profiles = {["Alt Nachname"] = {width=144, color={1,0.5,0}, playerGUID="Player-1-OLD"}}, char={["Alt Nachname"]={quests={99}}}}'
 target=b'DB = {char = {["Neu Nachname"] = {quests={12}, guid="Player-2-NEW"}}}'
 result=w.plain(w.parse(w.account_config('Test',config,target,s,t)))['DB']
 assert result['profileKeys']['Neu - Release Realm']=='Neu Nachname'
 assert result['profiles']['Neu Nachname']['playerGUID']==t['guid']
 assert result['profiles']['Neu Nachname']['width']==144
 assert result['char']=={'Neu Nachname':{'quests':{1:12},'guid':t['guid']}}
 assert 'Alt Nachname' not in result['char']
 print('PASS Lua roundtrip, Unicode, new realm/GUID, preserved target progression')

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

def test_release_snapshot(tmp,archive):
 manifest=w.verify_backup(archive)
 client=tmp/'release';char=client/'WTF/Account/NEW-ACCOUNT/999/New-Surname';char.mkdir(parents=True)
 target={'schema':1,'name':'New','full':'New Surname','realm':'Actual Release Realm','realmKey':'PvP','guid':'Player-9999-NEW123','class':'SHAMAN','regional':True}
 write(char/'SavedVariables/WoWUITransferIdentity.lua',w.dump({'WoWUITransferIdentity':target}))
 # Simulate updated release addons, with only their metadata required to build the config plan.
 with zipfile.ZipFile(archive) as z:
  for name in manifest['addons']:
   prefix='client/Interface/AddOns/'+name+'/'
   toc=next(n for n in manifest['files'] if n.startswith(prefix) and n.endswith('.toc') and n.count('/')==4)
   write(client/str(Path(toc).relative_to('client')),z.read(toc))
  helper=w.helper_plan(client,manifest)
  for rel,value in helper.items():write(client/rel,value)
  account=char.parent.parent
  write(account/'SavedVariables/Questie.lua',b'QuestieConfig = {char={["New Surname"]={guid="Player-9999-NEW123",completedQuests={[42]=true}}},global={lastKnownDailyReset=999}}')
  write(char/'SavedVariables/RXPGuides.lua',b'RXPCData={currentStep=9,playerGUID="Player-9999-NEW123"}\nRXPCTrackingData={guid="Player-9999-NEW123"}')
  write(char/'SavedVariables/Pawn.lua',b'PawnOptions={LastPlayerFullName="New Surname",ItemLevels={[1]={ID=123}}}\nPawnClassicScaleProviderOptions={LastClass="SHAMAN"}')
  write(client/'WTF/Config.wtf',b'SET realmName "Actual Release Realm"\nSET accountName "NEW"\nSET uiScale "0.8"\n')
  write(char/'chat-cache.txt',b'VERSION 9\nCHANNELS\nNEW_RELEASE_CHANNEL\nEND\nWINDOW 1\nNAME General\nSIZE 12\nLOCKED 0\nDOCKED 1\nSHOWN 1\nMESSAGES\nSAY\nEND\n')
  plan,notes,identity=w.restore_plan(archive,manifest,client,char)
  assert identity['realm']=='Actual Release Realm'
  assert any('Andere Klasse' in note for note in notes)
  assert all(str(Path(manifest['source_character']).parent.parent) not in rel for rel in plan)
  assert all(Path(manifest['source_character']).name not in rel for rel in plan)
  eui_rel=(account/'SavedVariables/EllesmereUI.lua').relative_to(client).as_posix()
  original=w.plain(w.parse(z.read('client/'+str(Path(manifest['source_character']).parent.parent)+'/SavedVariables/EllesmereUI.lua')))['EllesmereUIDB']
  restored=w.plain(w.parse(plan[eui_rel]))['EllesmereUIDB']
  assert original['profiles']==restored['profiles'], 'EllesmereUI complete visual profiles must match'
  for key in ['ppUIScale','fonts','customColors','unlockAnchors','unlockHeightMatch','unlockWidthMatch']:
   assert original.get(key)==restored.get(key),key
  assert 'goldLedger' not in restored and 'lastSpecByChar' not in restored
  q=w.plain(w.parse(plan[(account/'SavedVariables/Questie.lua').relative_to(client).as_posix()]))['QuestieConfig']
  assert q['char']=={'New Surname':{'guid':'Player-9999-NEW123','completedQuests':{42:True}}}
  pawn=char/'SavedVariables/Pawn.lua';pr=w.plain(w.parse(plan.get(pawn.relative_to(client).as_posix(),pawn.read_bytes())))
  assert pr['PawnOptions']['ItemLevels'][1]['ID']==123
  assert pr['PawnClassicScaleProviderOptions']['LastClass']=='SHAMAN'
  rxp=char/'SavedVariables/RXPGuides.lua'
  assert w.plain(w.parse(plan.get(rxp.relative_to(client).as_posix(),rxp.read_bytes())))==w.plain(w.parse(rxp.read_bytes()))
  cfg=plan['WTF/Config.wtf'];assert b'Actual Release Realm' in cfg and b'accountName "NEW"' in cfg
  assert b'NEW_RELEASE_CHANNEL' in plan[(char/'chat-cache.txt').relative_to(client).as_posix()]
  flags=plan[(char/'AddOns.txt').relative_to(client).as_posix()]
  assert b'EllesmereUI: enabled' in flags and b'Bartender4: disabled' in flags and b'WoWUITransferIdentity: disabled' in flags
  # Installation plan keeps installed release folders and includes all files for missing addons.
  preserved=w.install_plan(archive,manifest,client)
  assert not any(k.startswith('Interface/AddOns/EllesmereUI/') for k in preserved)
  shutil.rmtree(client/'Interface/AddOns/TipTac')
  missing=w.install_plan(archive,manifest,client)
  expected={n[len('client/'):] for n in manifest['files'] if n.startswith('client/Interface/AddOns/TipTac/')}
  assert expected and expected<=set(missing)
  write(client/'Interface/AddOns/TipTac/stale.txt','obsolete')
  replacement=w.install_plan(archive,manifest,client,replace=True)
  assert replacement['Interface/AddOns/TipTac/stale.txt'] is None
  # Apply real migration settings, then re-run: all settings must be stable.
  # Restore the removed TOC so the preflight inventory is complete again.
  for rel,value in missing.items():
   if rel.startswith('Interface/AddOns/TipTac/') and rel.endswith('.toc'):
    write(client/rel,z.read(value.member))
  recovery=w.RECOVERY;w.RECOVERY=tmp/'migration-recovery'
  w.apply_plan(client,plan,'simulated beta to release')
  repeated,_,_=w.restore_plan(archive,manifest,client,char)
  assert not repeated, list(repeated)
  w.RECOVERY=recovery
 print('PASS actual snapshot → fresh account, new realm/GUID/class; complete EllesmereUI visuals, activation, target progress, release versions and idempotency')

test_lua_and_mapping()
with tempfile.TemporaryDirectory() as name:
 tmp=Path(name).resolve()
 test_transaction(tmp)
 if len(sys.argv)>1:test_release_snapshot(tmp,Path(sys.argv[1]).resolve())
print('All tests passed.')
