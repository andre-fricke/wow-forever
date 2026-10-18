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
 write(client/('Interface/AddOns/'+w.HELPER+'/'+w.HELPER+'.toc'),b'## Interface: 16001\n## Version: 1\n')
 write(char/'AddOns.txt',b'TestAce: disabled\n')
 write(client/'Interface/AddOns/TestAce/TestAce.toc',b'## Interface: 16001\n## Version: 1\n## SavedVariables: TestDB\nmain.lua\n')
 write(client/'Interface/AddOns/TestAce/main.lua',b'-- addon payload version 1\n')
 write(char.parent.parent/'SavedVariables/TestAce.lua',w.dump({'TestDB':{'profileKeys':{'Éowyn Surname':'Default'},'profiles':{'Default':{'width':100}}}}))
 write(char/'macros-cache.txt',b'character macros v1')
 write(char.parent.parent/'macros-cache.txt',b'account macros')
 first=w.create_backup(client,char)
 assert first.name.endswith('_Éowyn-Surname_Beta_combined.zip')
 assert first.parent==w.SNAPSHOTS/'Beta'/'Éowyn_Surname'/'Combined'
 assert (first.parent.parent/'Addons').is_dir() and (first.parent.parent/'Macros').is_dir()
 assert w.backup_folder_part('Classic Beta PvP 2')=='Classic_Beta_PvP_2'
 assert w.backup_folder_part('  Cannot  Hotalot\t')=='Cannot_Hotalot'
 assert w.backup_folder_part('Realm / Test-PvP')=='Realm_Test_PvP'
 assert '/' not in w.backup_folder_part('../Realm/Test')
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
 # Separate backup types contain only their intended data.
 addon_backup=w.create_backup(client,char,kind='addons')
 macro_backup=w.create_backup(client,char,kind='macros')
 assert addon_backup.parent==w.SNAPSHOTS/'Beta'/'Éowyn_Surname'/'Addons'
 assert macro_backup.parent==w.SNAPSHOTS/'Beta'/'Éowyn_Surname'/'Macros'
 assert json.loads((tool/'latest.json').read_text())['backup']==macro_backup.relative_to(tool).as_posix()
 flat=w.SNAPSHOTS/'00000000-legacy.zip';flat.write_bytes(first.read_bytes())
 other=w.SNAPSHOTS/'Zulu Realm'/'Other Character'/'Addons'/'00000001-old.zip'
 write(other,addon_backup.read_bytes())
 assert flat in w.backup_entries() and other in w.backup_entries()
 (tool/'latest.json').unlink()
 assert w.latest_backup()==macro_backup
 am=w.verify_backup(addon_backup);mm=w.verify_backup(macro_backup)
 assert am['kind']=='addons' and mm['kind']=='macros'
 assert not any(Path(n).name.startswith('macros-cache.') for n in am['files'])
 assert any(n.startswith('client/Interface/AddOns/') for n in am['files'])
 assert set(mm['files'])=={'client/'+char.relative_to(client).as_posix()+'/macros-cache.txt','client/'+char.parent.parent.relative_to(client).as_posix()+'/macros-cache.txt'}
 assert w.latest_backup('addons')==addon_backup and w.latest_backup('macros')==macro_backup
 assert len(w.macro_plan(macro_backup,mm,release,dst,'both')[0])==2
 for operation in (lambda:w.install_plan(macro_backup,mm,release,character=dst),lambda:w.restore_plan(macro_backup,mm,release,dst),lambda:w.macro_plan(addon_backup,am,release,dst)):
  try:operation()
  except ValueError:pass
  else:raise AssertionError('Wrong backup type accepted')
 # Full restore with the identity addon installed must preserve target identity.
 w.apply_plan(release,w.install_plan(addon_backup,am,release,character=dst),'prepare restore')
 target=dict(source,name='New',full='New Surname',realm='Release',guid='Player-2-B')
 identity_file=dst/'SavedVariables'/f'{w.HELPER}.lua'
 identity_bytes=w.dump({w.HELPER:target});write(identity_file,identity_bytes)
 plan,notes,detected=w.restore_plan(addon_backup,am,release,dst)
 assert identity_file.relative_to(release).as_posix() not in plan
 w.apply_plan(release,plan,'restore addon settings')
 assert identity_file.read_bytes()==identity_bytes and detected==target
 restored=w.plain(w.parse((dst.parent.parent/'SavedVariables/TestAce.lua').read_bytes()))
 assert restored['TestDB']['profiles'][restored['TestDB']['profileKeys']['New Surname']]['width']==100
 # Legacy combined archives are eligible for either restore action.
 with zipfile.ZipFile(first) as z:
  legacy_manifest=json.loads(z.read('manifest.json'));legacy_manifest.pop('kind')
  legacy=root/'legacy.zip'
  with zipfile.ZipFile(legacy,'w') as out:
   for n in z.namelist():out.writestr(n,json.dumps(legacy_manifest) if n=='manifest.json' else z.read(n))
 lm=w.verify_backup(legacy)
 w.require_backup_kind(lm,'addons');w.require_backup_kind(lm,'macros')
 assert len(w.macro_plan(legacy,lm,release,dst,'both')[0])==2
 # A redirected realm directory must not write outside the backup tree.
 (w.SNAPSHOTS/'Redirect').symlink_to(outside,target_is_directory=True)
 try:w.backup_directory({'realm':'Redirect','full':'Test'},'addons')
 except ValueError:pass
 else:raise AssertionError('Backup destination symlink accepted')
 assert not (outside/'Test').exists()
 w.HERE,w.SNAPSHOTS,w.RECOVERY=original
print('PASS backup refresh/history, archive payload install, pre-login activation, undo, corruption and symlink checks')
