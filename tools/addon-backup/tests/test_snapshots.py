import sys,tempfile,zipfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import wow_backup as w

def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v)
with tempfile.TemporaryDirectory() as td:
 root=Path(td).resolve();client=root/'beta';char=client/'WTF/Account/OLD/70/Éowyn-Surname';tool=root/'tool';tool.mkdir()
 original=(w.HERE,w.SNAPSHOTS,w.RECOVERY)
 (tool/'identity.lua').write_bytes((w.HERE/'identity.lua').read_bytes())
 w.HERE=tool;w.SNAPSHOTS=tool/'Backups';w.RECOVERY=tool/'Recovery'
 source={'schema':1,'name':'Éowyn','full':'Éowyn Surname','realm':'Beta','guid':'Player-1-A','class':'DRUID'}
 write(char/'SavedVariables/WoWUITransferIdentity.lua',w.dump({'WoWUITransferIdentity':source}))
 write(char/'AddOns.txt',b'TestAce: disabled\n')
 write(client/'Interface/AddOns/TestAce/TestAce.toc',b'## Interface: 16001\n## Version: 1\n## SavedVariables: TestDB\nmain.lua\n')
 write(client/'Interface/AddOns/TestAce/main.lua',b'-- addon payload version 1\n')
 write(char.parent.parent/'SavedVariables/TestAce.lua',w.dump({'TestDB':{'profileKeys':{'Éowyn Surname':'Default'},'profiles':{'Default':{'width':100}}}}))
 write(char/'macros-cache.txt',b'character macros v1')
 write(char.parent.parent/'macros-cache.txt',b'account macros')
 first=w.create_backup(client,char)
 assert first.name.endswith('_Éowyn-Surname_Beta.zip')
 assert w.backup_name_part('Realm / Test: PvP 2')=='Realm-Test-PvP-2'
 assert len(w.backup_name_part('界'*100).encode())<=80
 write(char/'macros-cache.txt',b'character macros v2')
 write(client/'Interface/AddOns/TestAce/main.lua',b'-- addon payload version 2\n')
 second=w.create_backup(client,char)
 assert first.exists() and second.exists() and first!=second and w.latest_backup()==second
 (tool/'latest.json').unlink()
 assert w.latest_backup()==second
 with zipfile.ZipFile(first) as z:assert z.read('client/Interface/AddOns/TestAce/main.lua').endswith(b'1\n')
 release=root/'release';dst=release/'WTF/Account/NEW/New Realm/New-Surname';dst.mkdir(parents=True)
 with zipfile.ZipFile(first) as z:assert z.read('client/'+char.relative_to(client).as_posix()+'/macros-cache.txt')==b'character macros v1'
 write(dst/'config-cache.wtf',b'')
 manifest=w.verify_backup(second)
 macro_files,_=w.macro_plan(second,manifest,release,dst,'both')
 assert set(macro_files.values())=={b'character macros v2',b'account macros'}
 plan=w.install_plan(second,manifest,release,character=dst)
 receipt=w.apply_plan(release,plan,'install archived files')
 assert (release/'Interface/AddOns/TestAce/main.lua').read_bytes().endswith(b'2\n')
 assert b'TestAce: disabled' in (dst/'AddOns.txt').read_bytes()
 assert b'WoWUITransferIdentity: enabled' in (dst/'AddOns.txt').read_bytes()
 w.undo(receipt)
 assert not (release/'Interface/AddOns/TestAce/main.lua').exists()
 corrupt=root/'corrupt.zip'
 with zipfile.ZipFile(second) as src,zipfile.ZipFile(corrupt,'w') as out:
  for name in src.namelist():out.writestr(name,b'tampered' if name.endswith('/main.lua') else src.read(name))
 try:w.verify_backup(corrupt)
 except ValueError:pass
 else:raise AssertionError('Corrupt snapshot accepted')
 # The installer must refuse symbolic-link destinations.
 release.mkdir(exist_ok=True); outside=root/'outside';outside.mkdir();(release/'escape').symlink_to(outside,target_is_directory=True)
 try:w.apply_plan(release,{'escape/file':b'x'},'unsafe')
 except ValueError:pass
 else:raise AssertionError('Symlink destination accepted')
 w.HERE,w.SNAPSHOTS,w.RECOVERY=original
print('PASS backup refresh/history, archive payload install, pre-login activation, undo, corruption and symlink checks')
