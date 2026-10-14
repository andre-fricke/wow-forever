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

if __name__ == '__main__':
 test_lua_and_mapping()
 with tempfile.TemporaryDirectory() as name:
  test_transaction(Path(name).resolve())
 print('All core tests passed.')
