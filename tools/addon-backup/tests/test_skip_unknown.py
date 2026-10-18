"""Unknown addon opt-out must preserve destination files and activation."""
import copy, io, sys, tempfile, zipfile
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import wow_backup as w

with tempfile.TemporaryDirectory() as td:
 client=Path(td);char=client/'WTF/Account/TEST/Realm/New';char.mkdir(parents=True)
 (char/'AddOns.txt').write_bytes(b'Unknown: disabled\n')
 src='WTF/Account/OLD/Beta/Old'
 payload={
  'client/Interface/AddOns/Unknown/Unknown.toc':b'## Interface: 16001',
  'client/Interface/AddOns/Known/Known.toc':b'## Interface: 16001',
  'client/WTF/Account/OLD/SavedVariables/Unknown.lua':b'UnknownDB = {width=99}',
  'client/'+src+'/SavedVariables/Unknown.lua':b'UnknownChar = {width=99}',
  'client/WTF/Account/OLD/SavedVariables/Known.lua':b'DB = {profileKeys={["Old Name"]="Default"},profiles={Default={width=123}}}',
  'client/'+src+'/AddOns.txt':b'Unknown: enabled\nKnown: enabled\n',
 }
 ident={'name':'Old','full':'Old Name','realm':'Beta','guid':'Player-1','class':'DRUID'}
 manifest={'kind':'addons','source_character':src,'source_identity':ident,'addons':{'Known':{},'Unknown':{}},'files':{k:{'sha256':w.sha(v)} for k,v in payload.items()},'unsupported':['Account file: Unknown.lua','Character file: Unknown.lua']}
 original=copy.deepcopy(manifest)
 for answer in ('','0'):
  with patch('builtins.input',return_value=answer),redirect_stdout(io.StringIO()):
   assert w.select_supported_addons(manifest) is None
 with patch('builtins.input',side_effect=['invalid','1']),redirect_stdout(io.StringIO()) as output:
  selected=w.select_supported_addons(manifest)
 assert 'Unknown.lua' in output.getvalue()
 assert manifest==original and selected['skipped_addons']==['Unknown']
 archive=client/'backup.zip'
 with zipfile.ZipFile(archive,'w') as z:
  for k,v in payload.items():z.writestr(k,v)
 plan=w.install_plan(archive,selected,client,character=char)
 assert not any('Unknown' in k for k in plan)
 assert b'Unknown: disabled' in plan[(char/'AddOns.txt').relative_to(client).as_posix()]
 target=dict(ident,name='New',full='New Name',realm='Release',guid='Player-2')
 with patch.object(w,'identity',return_value=target),patch.object(w,'inventory',return_value={'Known':{},'Unknown':{}}):
  plan,notes,_=w.restore_plan(archive,selected,client,char)
 assert not any('Unknown' in k for k in plan)
 assert any(k.endswith('/Known.lua') for k in plan)
 assert b'Unknown: disabled' in plan[(char/'AddOns.txt').relative_to(client).as_posix()]
 assert 'Skipped addon: Unknown' in notes
 # Missing activation entries must remain missing, rather than inherit the source.
 with zipfile.ZipFile(archive) as z:
  assert b'Unknown:' not in w.activation_data(z,selected,{'Unknown','Known'},target_data=b'')
print('PASS skip/cancel, original manifest, installation, settings and activation preservation')
