#!/usr/bin/python3
"""Versioned, offline WoW UI snapshots and character-aware release restores.
No network dependencies. Lua SavedVariables are parsed as data, never executed.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import time
import subprocess
import zipfile
from dataclasses import dataclass
from lua_saved import Lua

HERE = Path(__file__).resolve().parent
INSTALL_ROOTS = (Path('/Applications/World of Warcraft'), Path.home()/'Applications/World of Warcraft')
SNAPSHOTS = HERE / 'Backups'
RECOVERY = HERE / 'Recovery'
# Read earlier recovery folders without changing their contents.
LEGACY_RECOVERY = HERE / 'Ruecksicherungen'
HELPER = 'WoWUITransferIdentity'
SCHEMA = 1

@dataclass
class Atom:
    value: object
    raw: str = None

def quote(value):
    # Lua accepts UTF-8 directly, but not JSON's Unicode escape syntax.
    return '"' + ''.join('\\'+c if c in '\\"' else ('\\%03d' % ord(c) if ord(c)<32 or ord(c)==127 else c) for c in value) + '"'

def decode(data): return data.decode('utf-8', errors='surrogateescape')
def encode(text): return text.encode('utf-8', errors='surrogateescape')
def scalar(value): return value.value if isinstance(value,Atom) else value

def parse(data):
    doc=Lua(decode(data))
    def convert(n):
        if n.entries is not None: return {k:convert(v) for k,v in n.entries.items()}
        return Atom(n.value,doc.raw(n))
    return {k:convert(n) for k,n in doc.roots.items()}

def dump(roots):
    def value(v):
        if isinstance(v,Atom):
            if v.raw is not None:return v.raw
            v=v.value
        if isinstance(v,dict):
            # Preserve sequence constructors, including explicit nil slots.
            # RestedXP calls unpack on {point, nil, relativePoint, x, y}.
            # Rewriting this as hash fields can change Lua's length boundary
            # and truncate unpack at the nil slot even though x/y are present.
            if v and all(type(k) is int for k in v) and set(v)==set(range(1,len(v)+1)):
                return '{\n'+''.join(value(v[k])+',\n' for k in range(1,len(v)+1))+'}'
            return '{\n'+''.join('['+value(k)+'] = '+value(x)+',\n' for k,x in v.items())+'}'
        if isinstance(v,str):return quote(v)
        if v is None:return 'nil'
        if isinstance(v,bool):return 'true' if v else 'false'
        if isinstance(v,(int,float)) and math.isfinite(v):return repr(v)
        raise ValueError('Unsupported Lua value')
    data=encode('\n'.join(k+' = '+value(v) for k,v in roots.items())+'\n')
    parse(data)
    return data

def plain(v):
    if isinstance(v,dict):return {k:plain(x) for k,x in v.items()}
    return scalar(v)

def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(p):
    if not p.exists():return None
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def stamp():return dt.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')
def backup_name_part(value):
    # Keep Unicode names readable, but exclude path separators and reserved characters.
    cleaned=''.join(c if c.isalnum() or c in ' -_' else '-' for c in value)
    cleaned=re.sub(r'[\s-]+','-',cleaned).strip('-_')
    return cleaned.encode('utf-8')[:80].decode('utf-8',errors='ignore').rstrip('-_') or 'Unknown'

def backup_folder_part(value):
    # Use underscores as separators, keeping Unicode letters and digits readable.
    cleaned=''.join(c if c.isalnum() else '_' for c in value)
    cleaned=re.sub(r'_+','_',cleaned).strip('_')
    return cleaned.encode('utf-8')[:80].decode('utf-8',errors='ignore').rstrip('_') or 'Unknown'

def backup_directory(info,kind):
    rooted(HERE,SNAPSHOTS.relative_to(HERE).as_posix())
    relative=backup_folder_part(info['realm'])+'/'+backup_folder_part(info['full'])
    for folder in ('Addons','Macros'):
        rooted(SNAPSHOTS,relative+'/'+folder).mkdir(parents=True,exist_ok=True)
    folder={'addons':'Addons','macros':'Macros','combined':'Combined'}[kind]
    destination=rooted(SNAPSHOTS,relative+'/'+folder)
    destination.mkdir(parents=True,exist_ok=True)
    return destination


def json_write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    os.replace(temp,path)

def valid_relative(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('Unsafe archive path: '+name)
    return p

def rooted(root,relative):
    valid_relative(relative)
    p=root/relative
    if not p.resolve().is_relative_to(root.resolve()):raise ValueError('Path leaves the destination directory: '+relative)
    # Reject symlinks, including ones that still point inside the client.
    cur=p
    while cur!=root:
        if cur.is_symlink():raise ValueError('Symlink in destination path: '+str(cur))
        cur=cur.parent
    return p

def characters(client):
    base=client/'WTF/Account'
    return sorted(p for p in base.glob('*/*/*') if p.is_dir() and p.parent.name!='SavedVariables' and
                  ((p/'SavedVariables').is_dir() or (p/'AddOns.txt').exists() or (p/'config-cache.wtf').exists()))

def identity(char):
    helper=char/'SavedVariables'/f'{HELPER}.lua'
    if helper.exists():
        info=plain(parse(helper.read_bytes()).get(HELPER,{}))
        if all(info.get(k) for k in ['name','full','realm','guid','class']):return info
    # Existing beta saves can identify the template without installing a helper.
    account=char.parent.parent
    full=char.name.replace('-',' ',1); name=char.name.split('-',1)[0]
    info={'name':name,'full':full,'realm':None,'guid':None,'class':None,'realmKey':None,'regional':None}
    p=account/'SavedVariables/EllesmereUI.lua'
    if p.exists():
        d=plain(parse(p.read_bytes())).get('EllesmereUIDB',{})
        entries=[v for v in d.get('goldLedger',{}).get('chars',{}).values() if isinstance(v,dict) and v.get('name')==name]
        realms={v.get('realm') for v in entries if v.get('realm')}
        if len(realms)==1:
            info['realm']=realms.pop()
            for v in entries:
                if v.get('realm')==info['realm']:info['class']=v.get('class')
    p=account/'SavedVariables/Questie.lua'
    if p.exists():
        d=plain(parse(p.read_bytes())).get('QuestieConfig',{}).get('char',{})
        keys=[full,name+' - '+(info['realm'] or char.parent.name)]
        for key in keys:
            if key in d:info['guid']=d[key].get('guid') or info['guid']
    p=char/'SavedVariables/Pawn.lua'
    if p.exists():
        d=plain(parse(p.read_bytes()))
        info['class']=d.get('PawnClassicScaleProviderOptions',{}).get('LastClass') or info['class']
        info['full']=d.get('PawnOptions',{}).get('LastPlayerFullName') or info['full']
    if not info['realm'] and not char.parent.name.isdigit():info['realm']=char.parent.name
    if not all(info.get(k) for k in ['realm','guid','class']):return None
    return info

def inventory(addons):
    result={}
    if not addons.is_dir():return result
    for folder in sorted(addons.iterdir()):
        if not folder.is_dir():continue
        tocs=list(folder.glob('*.toc'))
        if not tocs:continue
        meta={}
        for toc in tocs:
            for k,v in re.findall(r'^##\s*([^:]+):\s*(.*)$',decode(toc.read_bytes()),re.M):
                meta.setdefault(k.strip(),set()).add(v.strip())
        result[folder.name]={k:sorted(v) for k,v in meta.items() if k in ['Version','Interface','Title','SavedVariables','SavedVariablesPerCharacter','Dependencies','RequiredDeps']}
    return result

# Account files with reviewed storage conventions. AceDB databases are also supported generically.
REVIEWED={'ForeverDualGathering','AtlasBIStooltips','AtlasLootClassic','Auctionator','DandersFrames','DandersMover','Decursive','MoveAny','Pawn','Prat-3.0','Questie','RXPGuides','RareScanner','TipTac','Details','Details_Streamer','Bartender4','Grid2','Atlas','AtlasLootContinued','ShadowedUnitFrames','Chatify','Bagnon','MinimapButtonButton'}
CHAR_CONFIG={'DBM-Core','MoveAny','Blizzard_DamageMeter','Blizzard_RaidUI','Blizzard_TimeManager','Auctionator'}
CHAR_SPECIAL={'Questie','DandersFrames','Details','Pawn','RXPGuides','Prat-3.0','EllesmereUIChat','Details_EncounterDetails','Details_Vanguard'}
CHAR_BLIZZARD_RUNTIME={'Blizzard_AuctionHouseUI','Blizzard_ClientSavedVariables','Blizzard_Communities','Blizzard_LegacyChallengeTracker','Blizzard_Professions'}

def active_saved_files(client,char):
    installed=inventory(client/'Interface/AddOns')
    account=char.parent.parent
    return installed, [p for p in (account/'SavedVariables').glob('*.lua') if p.stem in installed]

def audit_support(client,char):
    installed,files=active_saved_files(client,char); unsupported=[]
    for p in files:
        d=parse(p.read_bytes())
        if p.stem not in REVIEWED and not p.stem.startswith(('EllesmereUI','DBM-')) and not all(isinstance(v,dict) and 'profileKeys' in v for v in d.values()):
            unsupported.append('Account file: '+p.name)
    for p in (char/'SavedVariables').glob('*.lua'):
        if p.stem not in installed and not p.stem.startswith('Blizzard_'):continue
        if p.stem not in CHAR_CONFIG|CHAR_SPECIAL|CHAR_BLIZZARD_RUNTIME and p.stem!=HELPER:
            unsupported.append('Character file: '+p.name)
    return unsupported

def pending_reviews(manifest):
    # A snapshot records support at creation time. Newly reviewed account
    # adapters also apply to existing archives without rewriting the backup.
    pending=[]
    for item in manifest.get('unsupported',[]):
        normalized=english_legacy_text(item)
        prefix='Account file: '
        if normalized.startswith(prefix):
            filename=normalized[len(prefix):]
            if filename.endswith('.lua') and filename[:-4] in REVIEWED:
                continue
        pending.append(normalized)
    return pending

def select_supported_addons(manifest):
    reviews=pending_reviews(manifest)
    if not reviews:return manifest
    skipped=set()
    print('Unknown addon configurations:')
    for item in reviews:
        print('  - '+item)
        match=re.fullmatch(r'(?:Account|Character) file: ([^/\\]+)\.lua',item)
        if not match:raise ValueError('Cannot safely skip this review item: '+item)
        skipped.add(match.group(1))
    print('Skipped addons will not be installed or restored. Their existing settings and enabled state are kept.')
    print('1  Skip listed addons and continue\n0  Back')
    while True:
        answer=input('Selection [Enter: back]: ').strip()
        if answer in ('','0'):return None
        if answer=='1':break
        print('Choose 1 or 0.')
    result=copy.deepcopy(manifest)
    result['skipped_addons']=sorted(skipped)
    result['unsupported']=[]
    result['addons']={k:v for k,v in result['addons'].items() if k not in skipped}
    result['files']={k:v for k,v in result['files'].items()
                     if not (PurePosixPath(k).parent.name=='SavedVariables' and PurePosixPath(k).stem in skipped)}
    return result

def create_backup(client,char,kind="combined"):
    if kind not in ("addons","macros","combined"):raise ValueError("Unknown backup type")
    client=client.resolve();char=char.resolve()
    if char not in [p.resolve() for p in characters(client)]:raise ValueError('Character does not belong to the selected installation')
    info=identity(char)
    if not info:raise ValueError('Template identity is missing. Prepare character detection and log in with the template character first.')
    installed=inventory(client/'Interface/AddOns') if kind!='macros' else {}
    unsupported=audit_support(client,char) if kind!='macros' else []
    destination=backup_directory(info,kind)
    filename=stamp()+'_'+backup_name_part(info['full'])+'_'+backup_name_part(info['realm'])+'_'+kind+'.zip'
    dest=destination/filename; temp=dest.with_suffix('.partial')
    members={}; roots=[client/'Interface/AddOns',client/'WTF']
    macro_paths={char/'macros-cache.txt',char.parent.parent/'macros-cache.txt'}
    if kind=='macros':roots=[None]
    if kind=='macros' and not any(p.exists() for p in macro_paths):
        raise ValueError('No saved macro files found for this character or account.')
    print({'addons':'Backing up addon files and locally saved UI settings …','macros':'Backing up character and account macros …','combined':'Backing up addon files, macros, and locally saved WTF settings …'}[kind],flush=True)
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
            count=0
            for root in roots:
                for p in sorted(macro_paths if kind=='macros' else root.rglob('*')):
                    if kind=='addons' and p.name.startswith('macros-cache.'):continue
                    if p.is_symlink():raise ValueError('Review this symlink before creating a backup: '+str(p))
                    if not p.is_file():continue
                    before=p.stat();rel=p.relative_to(client).as_posix()
                    digest=hashlib.sha256()
                    with p.open('rb') as src,z.open('client/'+rel,'w') as dst:
                        for block in iter(lambda:src.read(1024*1024),b''):
                            digest.update(block);dst.write(block)
                    after=p.stat()
                    if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):raise ValueError('A file changed during the backup. Quit WoW and try again.')
                    members['client/'+rel]={'sha256':digest.hexdigest(),'size':after.st_size,'mtime_ns':after.st_mtime_ns}
                    count+=1
                    if count%3000==0:print(f'{count} files backed up …',flush=True)
            manifest={'schema':SCHEMA,'kind':kind,'created':dt.datetime.now().astimezone().isoformat(),'source_client':str(client),'source_character':char.relative_to(client).as_posix(),'source_identity':info,'addons':installed,'unsupported':unsupported,'files':members}
            z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        # Check content integrity before publishing the new current backup.
        print('Verifying backup …',flush=True)
        verify_backup(temp)
        os.replace(temp,dest)
        json_write(HERE/'latest.json',{'backup':dest.relative_to(HERE).as_posix()})
        print(f'Backup verified: {dest}\n{len(members)} files, {dest.stat().st_size//1024//1024} MiB compressed.')
        if unsupported:print('Review before restoring: '+', '.join(unsupported))
        print(f'Backup created: {dest.name}',flush=True)
        print('Verification successful: all archived files passed their checksum checks.',flush=True)
        return dest
    except BaseException:
        temp.unlink(missing_ok=True)
        raise

def verify_backup(path):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive paths')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('schema')!=SCHEMA:raise ValueError('Unknown backup version')
        expected=set(manifest['files'])|{'manifest.json'}
        if set(names)!=expected:raise ValueError('Archive contents do not match the manifest')
        for name,meta in manifest['files'].items():
            valid_relative(name)
            h=hashlib.sha256();size=0
            with z.open(name) as f:
                for block in iter(lambda:f.read(1024*1024),b''):h.update(block);size+=len(block)
            if h.hexdigest()!=meta['sha256'] or size!=meta['size']:raise ValueError('Corrupted backup file: '+name)
        return manifest

@dataclass
class Archived:
    archive: Path
    member: str
    digest: str

def payload_hash(value):return value.digest if isinstance(value,Archived) else sha(value) if value is not None else None

def atomic_payload(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.wow-ui-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as dst:
            if isinstance(value,Archived):
                with zipfile.ZipFile(value.archive) as z,z.open(value.member) as src:shutil.copyfileobj(src,dst,1024*1024)
            else:dst.write(value)
            dst.flush();os.fsync(dst.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def recovery_context(client,files,character=None):
    """Identify the destination of a recovery point, including older manifests."""
    client=Path(client).resolve()
    if character is None:
        candidates=set()
        for filename in files:
            parts=PurePosixPath(filename).parts
            if len(parts)>=6 and parts[:2]==('WTF','Account') and parts[3]!='SavedVariables':
                candidates.add('/'.join(parts[:5]))
        if len(candidates)==1:character=rooted(client,candidates.pop())
    if character is None:return {'realm':'Unknown Realm','character':'Unassigned'}
    character=Path(character).absolute()
    relative=character.relative_to(client).as_posix()
    rooted(client,relative)
    try:info=identity(character) or {}
    except (ValueError,OSError,KeyError,IndexError):info={}
    realm=info.get('realm') or (('Realm folder '+character.parent.name) if character.parent.name.isdigit() else character.parent.name)
    return {'realm':realm,'character':info.get('full') or character.name.replace('-',' ',1),'character_path':relative}


def apply_plan(client,plan,label,character=None,context=None):
    client=client.resolve(); changes={}
    for rel,value in plan.items():
        p=rooted(client,rel)
        if p.exists() and not p.is_file():raise ValueError('Destination is not a file: '+str(p))
        before=file_sha(p); after=payload_hash(value)
        if before!=after:changes[rel]=(value,before,after)
    if not changes:print('No changes required.');return None
    context=context or recovery_context(client,changes,character)
    relative=backup_folder_part(context['realm'])+'/'+backup_folder_part(context['character'])+'/'+stamp()
    if RECOVERY.is_symlink():raise ValueError('Recovery storage must not be a symlink.')
    dest=rooted(RECOVERY,relative);dest.mkdir(parents=True)
    log={'schema':1,'client':str(client),'target':context,'label':label,'status':'preparing','files':[]}
    with zipfile.ZipFile(dest/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
        for rel,(value,before,after) in changes.items():
            p=rooted(client,rel)
            if before is not None:
                z.write(p,rel)
                if file_sha(p)!=before:raise ValueError('Destination file changed concurrently: '+rel)
            log['files'].append({'path':rel,'before':before,'after':after})
    # Verify the rollback data before writing any destination files.
    with zipfile.ZipFile(dest/'before.zip') as z:
        for entry in log['files']:
            if entry['before'] is not None and sha(z.read(entry['path']))!=entry['before']:raise ValueError('Could not verify recovery data')
    log['status']='applying';json_write(dest/'manifest.json',log)
    done=[]
    try:
        for rel,(value,before,after) in changes.items():
            p=rooted(client,rel)
            if file_sha(p)!=before:raise ValueError('Destination file changed concurrently: '+rel)
            if value is None:p.unlink()
            else:atomic_payload(p,value)
            done.append(rel)
            if file_sha(p)!=after:raise ValueError('Write verification failed: '+rel)
            if len(done)%3000==0:print(f'{len(done)} files installed …',flush=True)
        log['status']='complete';json_write(dest/'manifest.json',log)
    except BaseException:
        with zipfile.ZipFile(dest/'before.zip') as z:
            for rel in reversed(done):
                p=rooted(client,rel)
                if changes[rel][1] is None:p.unlink(missing_ok=True)
                else:atomic_payload(p,z.read(rel))
        log['status']='rolled_back';json_write(dest/'manifest.json',log)
        raise
    print(f'{len(changes)} files written and verified. Recovery data: {dest}')
    return dest

def english_legacy_text(text):
    """Translate old tool messages without modifying names, paths, or saved records."""
    # German literals here are input compatibility keys, never new UI messages.
    prefix=''
    while text.startswith(('Rückgängig: ', 'Undo: ')):
        marker='Undo: ' if text.startswith('Undo: ') else 'Rückgängig: '
        prefix+='Undo: ';text=text[len(marker):]
    exact={
        'Addon-Dateien und Charaktererkennung vorbereiten':'Prepare addon files and character detection',
        'Charaktererkennung für Backup vorbereiten':'Prepare character detection for backup',
    }
    if text in exact:return prefix+exact[text]
    for old,new in (
        ('UI-Backup auf ','Restore UI backup to '),
        ('Kontodatei: ','Account file: '),
        ('Charakterdatei: ','Character file: '),
    ):
        if text.startswith(old):return prefix+new+text[len(old):]
    return prefix+text


def recovery_entries():
    entries=[]
    for root in (RECOVERY,LEGACY_RECOVERY):
        if root.is_symlink():continue
        for directory,folders,files in os.walk(root,followlinks=False):
            folders[:]=[name for name in folders if not (Path(directory)/name).is_symlink()]
            if 'manifest.json' in files and not (Path(directory)/'manifest.json').is_symlink():
                entries.append(Path(directory));folders[:]=[]
    return sorted(entries,key=lambda p:(p.name,str(p)),reverse=True)


def undo(recovery):
    log=json.loads((recovery/'manifest.json').read_text());client=Path(log['client'])
    if log['status'] not in ['complete','applying']:raise ValueError('This operation cannot be undone: '+log['status'])
    plan={}
    archive=recovery/'before.zip'
    if not archive.exists():archive=recovery/'vorher.zip'  # Legacy archive name.
    with zipfile.ZipFile(archive) as z:
        for e in log['files']:
            p=rooted(client,e['path']);current=file_sha(p)
            if current not in [e['before'],e['after']]:raise ValueError('File changed after this operation; undo would overwrite newer data: '+e['path'])
            data=z.read(e['path']) if e['before'] is not None else None
            if data is not None and sha(data)!=e['before']:raise ValueError('Recovery data is corrupted')
            plan[e['path']]=data
    context=log.get('target') or recovery_context(client,(e['path'] for e in log['files']))
    result=apply_plan(client,plan,'Undo: '+english_legacy_text(log['label']),context=context)
    log['status']='undone';json_write(recovery/'manifest.json',log)
    return result

def identity_map(source,target):
    pairs={source['full']:target['full'],source['name']:target['name'],source['guid']:target['guid'],source['realm']:target['realm']}
    for sep in [' - ','-']:
        pairs[source['name']+sep+source['realm']]=target['name']+sep+target['realm']
    if source.get('realmKey') and target.get('realmKey'):pairs[source['realmKey']]=target['realmKey']
    if source.get('faction') and target.get('faction'):
        for key in ['realm','realmKey']:
            if source.get(key) and target.get(key):pairs[source['faction']+' - '+source[key]]=target['faction']+' - '+target[key]
    return {k:v for k,v in pairs.items() if k and v}

def remap(value,mapping):
    if isinstance(value,dict):
        out={}
        # A copied source entry takes precedence over a pre-existing target-name entry in the snapshot.
        for k,v in sorted(value.items(),key=lambda item: item[0] in mapping):
            nk=mapping.get(k,k)
            if nk in out and k not in mapping:raise ValueError('Ambiguous key mapping')
            out[nk]=remap(v,mapping)
        return out
    v=scalar(value)
    return Atom(mapping[v]) if isinstance(v,str) and v in mapping else copy.deepcopy(value)

def retain(root,existing,keys):
    for k in keys:
        if k in existing:root[k]=copy.deepcopy(existing[k])
        else:root.pop(k,None)

def sanitize_account(name,roots,existing,source,target):
    out=copy.deepcopy(roots)
    # AceDB separates character/progress state from UI profiles.
    for key,root in out.items():
        if not isinstance(root,dict):continue
        old=existing.get(key,{})
        if not isinstance(old,dict):old={}
        if 'profileKeys' in root:retain(root,old,['char','realm','factionrealm','factionrealmregion'])
    if name=='Questie' and isinstance(out.get('QuestieConfig'),dict):
        g=out['QuestieConfig'].get('global',{})
        old=existing.get('QuestieConfig',{}).get('global',{})
        retain(g,old,['lastKnownDailyReset','unavailableDailyQuestsByNpc','unavailableQuestsDeterminedByTalking'])
    if name=='RareScanner':
        g=out.get('RareScannerDB',{}).get('global',{})
        old=existing.get('RareScannerDB',{}).get('global',{})
        retain(g,old,['containers_found','dragon_glyphs_collected','npc_counters','container_counters','rares_found','recentlySeen','events_found'])
    if name=='Auctionator':
        retain(out,existing,['AUCTIONATOR_PRICE_DATABASE','AUCTIONATOR_POSTING_HISTORY','AUCTIONATOR_VENDOR_PRICE_CACHE','AUCTIONATOR_SAVEDVARS'])
    if name=='RXPGuides':
        root=out.get('RXPData',{})
        if isinstance(root,dict):retain(root,existing.get('RXPData',{}),['cache','cacheVersion','questNames','realmData','gameVersion','maxLoadTime'])
    if name=='EllesmereUI':
        root=out.get('EllesmereUIDB',{});old=existing.get('EllesmereUIDB',{})
        retain(root,old,['goldLedger','dataBarsGold','characterGold','warbandGold','qolUpgradeCalcChars','xpBarChars','restoreOnUninstall','gfxBackup','friendlyPlateVisSaved','chatTellMuted','bagCurrencyByChar','cdmCachedBarSizes','lastSpecByChar'])
        # Apply the captured visual profile; do not let a beta-spec switch select a different one.
        root['specProfiles']={}
        if source['class']!=target['class']:retain(root,old,['clickCast','profileKeybinds'])
    if name.startswith('EllesmereUI'):
        def clean(node,old):
            if not isinstance(node,dict):return
            old=old if isinstance(old,dict) else {}
            retain(node,old,['goldLedger','characterGold','dataBarsGold','warbandGold','qolUpgradeCalcChars','xpBarChars'])
            for k,v in list(node.items()):clean(v,old.get(k,{}))
        for k,v in out.items():clean(v,existing.get(k,{}))
    if name=='DandersFrames':
        if source['class']!=target['class']:retain(out,existing,['DandersFramesClickCastingDB'])
        root=out.get('DandersFramesDB_v2',{})
        if isinstance(root,dict):retain(root,existing.get('DandersFramesDB_v2',{}),['debugLog'])
        retain(out,existing,['DandersFramesDebugDB'])
    if name=='Pawn' and source['class']!=target['class']:
        scales=out.get('PawnCommon',{}).get('Scales',{})
        olds=existing.get('PawnCommon',{}).get('Scales',{})
        for key,scale in scales.items():
            if isinstance(scale,dict):retain(scale,olds.get(key,{}),['PerCharacterOptions'])
    if name.startswith('DBM-'):
        for key in list(out):
            if 'Stats' in key or key=='DBM_Keystones':retain(out,existing,[key])
    return out

def account_config(name,data,target_data,source,target):
    roots=parse(data);existing=parse(target_data) if target_data else {}
    clean=sanitize_account(name,roots,existing,source,target)
    mapping=identity_map(source,target)
    # RestedXP's bundled AceDB uses ruleset names (PvP/PvE/RP/Hardcore)
    # on Forever instead of the displayed realm name. Older saves may still
    # use the full character name, so retain those as fallback candidates.
    rxp_source=source['name']+' - '+(source.get('realmKey') or source['realm'])
    rxp_target=target['name']+' - '+(target.get('realmKey') or target['realm'])
    if name=='RXPGuides':mapping[rxp_source]=rxp_target
    out=remap(clean,mapping)
    for rootkey,root in out.items():
        original=roots[rootkey]
        if not isinstance(root,dict) or not isinstance(original,dict) or 'profileKeys' not in original:continue
        keys=original['profileKeys']
        candidates=[source['full'],source['name']+' - '+source['realm']]
        if name=='RXPGuides':candidates.insert(0,rxp_source)
        chosen=next((scalar(keys[k]) for k in candidates if k in keys),None)
        if chosen is None:continue
        chosen=mapping.get(chosen,chosen)
        root.setdefault('profileKeys',{})[target['full']]=Atom(chosen)
        root['profileKeys'][target['name']+' - '+target['realm']]=Atom(chosen)
        if name=='RXPGuides':root['profileKeys'][rxp_target]=Atom(chosen)
    return dump(out)

def character_config(name,data,target_data,source,target):
    # Identity belongs to the destination and must never be restored from a template.
    if name==HELPER:return target_data
    src=parse(data);dst=parse(target_data) if target_data else {}
    out=copy.deepcopy(dst);mapping=identity_map(source,target)
    if name in CHAR_CONFIG:return dump(remap(src,mapping))
    if name in CHAR_BLIZZARD_RUNTIME or name in ['Questie','Prat-3.0','EllesmereUIChat','Details_EncounterDetails','Details_Vanguard']:return target_data
    if name=='DandersFrames':
        root=out.setdefault('DandersFramesCharDB',{})
        for key in ['currentProfile','languageOverride']:
            if key in src.get('DandersFramesCharDB',{}):root[key]=copy.deepcopy(src['DandersFramesCharDB'][key])
        # Keep the captured layout active while retaining target assignments for later use.
        root['enableSpecSwitch']=Atom(False)
        root.setdefault('specProfiles',{})
    elif name=='RXPGuides':
        local=src.get('RXPCData',{}).get('localDB')
        if local is not None:out.setdefault('RXPCData',{})['localDB']=copy.deepcopy(local)
        if isinstance(src.get('RXPCSettings'),dict):out['RXPCSettings']=copy.deepcopy(src['RXPCSettings'])
    elif name=='Pawn':
        root=out.setdefault('PawnOptions',{})
        for k,v in src.get('PawnOptions',{}).items():
            if k not in ['ItemLevels','LastPlayerFullName','LastVersion','AutoSelectScales']:root[k]=copy.deepcopy(v)
        root['LastPlayerFullName']=Atom(target['full'])
        if source['class']==target['class'] and 'AutoSelectScales' in src.get('PawnOptions',{}):root['AutoSelectScales']=copy.deepcopy(src['PawnOptions']['AutoSelectScales'])
    elif name=='Details':
        root=out.setdefault('_detalhes_database',{})
        for k in ['active_profile','local_instances_config','window_scale']:
            if k in src.get('_detalhes_database',{}):root[k]=copy.deepcopy(src['_detalhes_database'][k])
    else:raise ValueError('Character file requires an adapter: '+name)
    return dump(remap(out,mapping))

UI_CVAR=re.compile(r'^(?:uiScale$|useUiScale$|Brightness$|Contrast$|Gamma$|nameplate|raidFrames|damageMeter|showQuestLevel$|chat|floatingCombatText|UnitName|unitName|showTarget|showParty|showArena|colorblind|colorBlind|profanityFilter|buffDurations$|showCastableBuffs$|showDispelDebuffs$|statusText|displaySpellActivationOverlays$)',re.I)

def merge_cvars(source,target):
    values={k:v for k,v in re.findall(r'^SET (\S+) (.*)$',decode(source),re.M) if UI_CVAR.match(k)}
    lines=decode(target or b'').splitlines();seen=set();out=[]
    for line in lines:
        m=re.match(r'^SET (\S+) (.*)$',line)
        if m and m[1] in values:out.append('SET '+m[1]+' '+values[m[1]]);seen.add(m[1])
        else:out.append(line)
    out.extend('SET '+k+' '+v for k,v in values.items() if k not in seen)
    return encode('\n'.join(out)+'\n')

def merge_chat(source,target):
    if not target:return source
    sa=decode(source).split('WINDOW ');sb=decode(target).split('WINDOW ')
    fields=r'(?:NAME|SIZE|COLOR|LOCKED|UNINTERACTABLE|DOCKED|SHOWN|POSITION|DIMENSIONS)'
    source_windows={part.splitlines()[0].strip():part for part in sa[1:]}
    for i in range(1,len(sb)):
        key=sb[i].splitlines()[0].strip()
        if key not in source_windows:continue
        geometry=re.findall(r'^'+fields+r' [^\r\n]+',source_windows[key],re.M)
        sb[i]=re.sub(r'^'+fields+r' [^\r\n]+[\r\n]*','',sb[i],flags=re.M)
        first,_,tail=sb[i].partition('\n');sb[i]=first+'\n'+'\n'.join(geometry)+'\n'+tail
    return encode('WINDOW '.join(sb))

def helper_plan(client,manifest=None,character=None):
    interfaces=set()
    for meta in inventory(client/'Interface/AddOns').values():
        for line in meta.get('Interface',[]):interfaces.update(re.findall(r'\d+',line))
    cfg=client/'WTF/Config.wtf'
    if cfg.exists():
        for key in ['engineSurveyPatch','lastAddonVersion']:
            m=re.search(r'^SET '+key+r' "(\d+)"',decode(cfg.read_bytes()),re.M)
            if m:interfaces.add(m[1])
    if manifest:
        for meta in manifest['addons'].values():
            for line in meta.get('Interface',[]):interfaces.update(re.findall(r'\d+',line))
    if not interfaces:interfaces.add('16001')
    toc='## Interface: '+', '.join(sorted(interfaces,key=int))+'\n## Title: WoW UI Transfer Identity\n## Notes: Records this character identity locally for UI backup restoration.\n## Version: 1.0\n## SavedVariablesPerCharacter: WoWUITransferIdentity\nidentity.lua\n'
    prefix='Interface/AddOns/'+HELPER+'/'
    plan={prefix+HELPER+'.toc':encode(toc),prefix+'identity.lua':(HERE/'identity.lua').read_bytes()}
    for char in ([character] if character is not None else characters(client)):
        p=char/'AddOns.txt';txt=decode(p.read_bytes()) if p.exists() else ''
        txt=re.sub(r'^'+HELPER+r':[^\r\n]*[\r\n]*','',txt,flags=re.M)
        plan[p.relative_to(client).as_posix()]=encode(txt.rstrip()+'\n'+HELPER+': enabled\n')
    return plan

def require_backup_kind(manifest,kind):
    stored=manifest.get('kind','combined')
    if stored not in ('combined',kind):
        raise ValueError(f'This is a {stored} backup. Select a {kind} backup instead.')

def install_plan(archive,manifest,client,replace=False,character=None):
    require_backup_kind(manifest,"addons")
    plan={};existing=inventory(client/'Interface/AddOns')
    selected=set(manifest['addons']) if replace else set(manifest['addons'])-set(existing)
    for name,meta in manifest['files'].items():
        parts=PurePosixPath(name).parts
        if len(parts)>=5 and parts[:3]==('client','Interface','AddOns') and parts[3] in selected:
            plan['/'.join(parts[1:])]=Archived(archive,name,meta['sha256'])
    if replace:
        for addon in selected:
            folder=client/'Interface/AddOns'/addon
            if folder.exists():
                for p in folder.rglob('*'):
                    if p.is_file():
                        rel=p.relative_to(client).as_posix()
                        if rel not in plan:plan[rel]=None
    plan.update(helper_plan(client,manifest,character))
    if character is not None:
        with zipfile.ZipFile(archive) as z:
            plan[(character/'AddOns.txt').relative_to(client).as_posix()]=activation_data(z,manifest,set(existing)|set(manifest['addons']),helper_enabled=True,target_data=(character/'AddOns.txt').read_bytes() if (character/'AddOns.txt').exists() else None)
    return plan

def activation_data(z,manifest,installed,helper_enabled=False,target_data=None):
    states={}
    member='client/'+manifest['source_character']+'/AddOns.txt'
    if member in manifest['files']:
        for name,state in re.findall(r'^([^:\r\n]+):\s*(enabled|disabled)',decode(z.read(member)),re.M):states[name]=state
    expected=set(manifest['addons'])
    for addon in installed:states[addon]=states.get(addon,'enabled') if addon in expected else 'disabled'
    target_states=dict(re.findall(r'^([^:\r\n]+):\s*(enabled|disabled)',decode(target_data or b''),re.M))
    for addon in manifest.get('skipped_addons',[]):
        states.pop(addon,None)
        if addon in target_states:states[addon]=target_states[addon]
    states[HELPER]='enabled' if helper_enabled else 'disabled'
    return encode(''.join(name+': '+state+'\n' for name,state in sorted(states.items())))


def restore_plan(archive,manifest,client,char):
    require_backup_kind(manifest,"addons")
    target=identity(char)
    if not target:raise ValueError('Target identity is unknown. Complete preparation and log in for character detection first.')
    source=manifest['source_identity'];account=char.parent.parent
    if pending_reviews(manifest):raise ValueError('Backup contains configurations that still need review: '+', '.join(pending_reviews(manifest)))
    expected=set(manifest['addons']);actual=inventory(client/'Interface/AddOns')
    missing=expected-set(actual)
    if missing:raise ValueError('Addon files are missing; run preparation first: '+', '.join(sorted(missing)))
    plan={};notes=['Skipped addon: '+addon for addon in manifest.get('skipped_addons',[])]
    for addon in expected & set(actual):
        if manifest['addons'][addon].get('Version')!=actual[addon].get('Version'):notes.append('Keeping a different installed addon version: '+addon)
    if source['class']!=target['class']:notes.append('Different class: '+source['class']+' → '+target['class']+'. Spells and click-casting may need adjustment in the game.')
    srcchar='client/'+manifest['source_character'];srcacc=str(PurePosixPath(srcchar).parent.parent)
    def put(path,data):
        if data is not None and (not path.exists() or path.read_bytes()!=data):plan[path.relative_to(client).as_posix()]=data
    def existing(path):return path.read_bytes() if path.exists() else None
    with zipfile.ZipFile(archive) as z:
        for member in manifest['files']:
            p=PurePosixPath(member)
            if str(p.parent)==srcacc+'/SavedVariables' and p.suffix=='.lua' and p.stem in expected:
                dst=account/'SavedVariables'/p.name
                put(dst,account_config(p.stem,z.read(member),existing(dst),source,target))
            elif str(p.parent)==srcchar+'/SavedVariables' and p.suffix=='.lua' and (p.stem in expected or p.stem in CHAR_CONFIG):
                dst=char/'SavedVariables'/p.name
                put(dst,character_config(p.stem,z.read(member),existing(dst),source,target))
        for source_dir,dest_dir,names in [
            (srcacc,account,['edit-mode-cache-account.txt','bindings-cache.wtf']),
            (srcchar,char,['layout-local.txt','edit-mode-cache-character.txt','bindings-cache.wtf'])]:
            for name in names:
                member=source_dir+'/'+name
                if member in manifest['files']:put(dest_dir/name,z.read(member))
        for source_dir,dest_dir,name in [('client/WTF',client/'WTF','Config.wtf'),(srcacc,account,'config-cache.wtf'),(srcchar,char,'config-cache.wtf')]:
            member=source_dir+'/'+name
            if member in manifest['files']:put(dest_dir/name,merge_cvars(z.read(member),existing(dest_dir/name)))
        member=srcchar+'/chat-cache.txt'
        if member in manifest['files']:put(char/'chat-cache.txt',merge_chat(z.read(member),existing(char/'chat-cache.txt')))
        put(char/'AddOns.txt',activation_data(z,manifest,set(actual),helper_enabled=False,target_data=existing(char/'AddOns.txt')))
    return plan,notes,target

def macro_plan(archive, manifest, client, char, scope='character'):
    """Restore complete macro files without changing macro bodies or identifiers."""
    require_backup_kind(manifest,"macros")
    client=client.resolve();char=char.resolve()
    if char not in [p.resolve() for p in characters(client)]:
        raise ValueError('Target character does not belong to the destination client')
    if scope not in ('character','account','both'):
        raise ValueError('Unknown macro scope: '+scope)
    source=PurePosixPath('client')/manifest['source_character']
    locations={'character':(source,char),'account':(source.parent.parent,char.parent.parent)}
    plan={};notes=[]
    with zipfile.ZipFile(archive) as z:
        for kind in ('character','account') if scope=='both' else (scope,):
            src,dst=locations[kind]
            member=str(src/'macros-cache.txt')
            if member not in manifest['files']:
                notes.append(kind.capitalize()+': no macro file in this backup; destination unchanged.')
                continue
            data=z.read(member)
            # Validate the selected payload even when called outside the CLI/menu.
            if sha(data)!=manifest['files'][member]['sha256']:
                raise ValueError('Corrupted backup file: '+member)
            rel=(dst/'macros-cache.txt').relative_to(client).as_posix()
            target=rooted(client,rel)
            count=sum(line.startswith(b'VER ') for line in data.splitlines())
            notes.append(f'{kind.capitalize()}: {count} saved macros; replace the complete destination macro file: {rel}')
            if not target.exists() or target.read_bytes()!=data:plan[rel]=data
    return plan,notes

def show_macro_notes(notes):
    for note in notes:print(note)
    print('Macro bodies are copied unchanged. Check class-specific spells and explicit character names in the game.')
    print('Action bar placement is not restored. Check the macros after login; live client/server synchronization has not been validated.')


def latest_backup(kind=None):
    if kind:
        for candidate in backup_entries():
            try:
                with zipfile.ZipFile(candidate) as z:manifest=json.loads(z.read('manifest.json'))
            except (OSError,ValueError,KeyError,zipfile.BadZipFile):continue
            if manifest.get('kind','combined') in (kind,'combined'):return candidate
        raise ValueError(f'No {kind} backup found. Create one in the Backup menu first.')
    p=HERE/'latest.json'
    if p.exists():
        candidate=rooted(HERE,json.loads(p.read_text())['backup'])
        if candidate.is_file():return candidate
    candidates=backup_entries()
    if not candidates:raise ValueError('No backup found. Create one in the Backup menu first.')
    return candidates[0]

def backup_entries():
    rooted(HERE,SNAPSHOTS.relative_to(HERE).as_posix())
    entries=[]
    for directory,folders,files in os.walk(SNAPSHOTS,followlinks=False):
        folders[:]=[name for name in folders if not (Path(directory)/name).is_symlink()]
        for name in files:
            path=Path(directory)/name
            if path.suffix=='.zip' and path.is_file() and not path.is_symlink():entries.append(path)
    # Timestamp-prefixed filenames determine age, not realm/character directory order.
    return sorted(entries,key=lambda p:(p.name,p.as_posix()),reverse=True)

def managed_entry(path,root,nested=False):
    """Allow deletion only inside the selected tool storage directory."""
    path=Path(path).absolute();root=Path(root).absolute()
    if not path.is_relative_to(root) or path==root or (not nested and path.parent!=root):
        raise ValueError('Selection is outside the managed storage directory.')
    rooted(HERE,root.relative_to(HERE.absolute()).as_posix())
    return rooted(root,path.relative_to(root).as_posix())

def delete_backup(path):
    path=managed_entry(path,SNAPSHOTS,nested=True)
    if path.suffix!='.zip' or not path.is_file():raise ValueError('Select an existing backup ZIP.')
    pointer=HERE/'latest.json'
    # Resolve the pointer before deleting, so invalid metadata causes no partial deletion.
    current=rooted(HERE,json.loads(pointer.read_text())['backup']) if pointer.exists() else None
    path.unlink()
    if current==path:
        remaining=backup_entries()
        if remaining:json_write(pointer,{'backup':remaining[0].relative_to(HERE).as_posix()})
        else:pointer.unlink()
    print('Backup deleted: '+path.name)

def delete_recovery_point(path):
    path=Path(path).absolute()
    roots=[root for root in (RECOVERY,LEGACY_RECOVERY) if path!=root.absolute() and path.is_relative_to(root.absolute())]
    if not roots:raise ValueError('Selection is outside the recovery directories.')
    path=managed_entry(path,roots[0],nested=True)
    if not path.is_dir() or not (path/'manifest.json').is_file():
        raise ValueError('Select an existing recovery point.')
    # rmtree removes internal symlinks themselves without following their targets.
    shutil.rmtree(path)
    print('Recovery point deleted: '+path.name)

def deletion_menu(recovery=False):
    selected=choose_recovery() if recovery else choose_snapshot()
    if selected is None:return
    print('Selected: '+str(selected))
    print('Deleting this recovery point permanently removes its undo data.' if recovery else 'Deleting this backup permanently removes this snapshot. Recovery points are kept.')
    if input('Permanently delete this item? [y/N]: ').strip().lower() not in ('y','yes'):
        print('Cancelled; nothing deleted.')
        return
    if recovery:delete_recovery_point(selected)
    else:delete_backup(selected)


def choose_client(release=False):
    candidates=sorted({p.resolve() for root in INSTALL_ROOTS if root.is_dir()
                       for p in root.iterdir() if p.is_dir() and (p/'WTF').is_dir()})
    print('\nSelect a WoW installation'+(' – choose the RELEASE client:' if release else ':'))
    for i,p in enumerate(candidates,1):print(f'{i}: {p}'+(' [Beta]' if 'beta' in p.name.lower() else ''))
    print('Or enter the full path to the client directory (containing WTF and Interface).')
    answer=input('Selection: ').strip()
    if not answer:raise ValueError('No installation selected.')
    if answer.isdigit() and 1<=int(answer)<=len(candidates):client=candidates[int(answer)-1]
    else:client=Path(answer.strip('"\'' )).expanduser()
    if not (client/'WTF').is_dir():raise ValueError('Client WTF directory not found. Log in once using this client, then quit WoW.')
    return client.resolve()

def choose_character(client):
    choices=characters(client)
    if not choices:raise ValueError('No character directory found. Log in with the character once, then quit WoW completely.')
    print('\nTarget / template character:')
    for i,p in enumerate(choices,1):print(f'{i}: {p.name.replace("-"," ",1)} | Directory/Realm: {p.parent.name} | Account: {p.parent.parent.name}')
    answer=input('Character name or number: ').strip()
    if answer.isdigit() and 1<=int(answer)<=len(choices):return choices[int(answer)-1]
    matches=[p for p in choices if answer.casefold() in [p.name.casefold(),p.name.replace('-',' ',1).casefold()]]
    if len(matches)==1:return matches[0]
    raise ValueError('Character name was not found or is ambiguous. Select its number instead.')

def wow_is_running():
    try:
        result=subprocess.run(['/bin/ps','-axo','comm='],capture_output=True,text=True,timeout=2)
    except (OSError,subprocess.TimeoutExpired) as error:
        raise ValueError('Could not check whether WoW is running. Try again before modifying files.') from error
    if result.returncode!=0:
        raise ValueError('Could not check whether WoW is running. Try again before modifying files.')
    return any('World of Warcraft' in line and '/Contents/MacOS/' in line
               and 'Launcher' not in line and 'Helper' not in line
               for line in result.stdout.splitlines())

def wait_for_wow_closed():
    if not wow_is_running():
        print('WoW is closed. Continuing.',flush=True)
        return
    print('WoW is still running. Quit WoW completely; waiting up to 30 seconds …',flush=True)
    deadline=time.monotonic()+30
    countdown=30
    while True:
        remaining=deadline-time.monotonic()
        while countdown>=max(0,math.ceil(remaining)):
            print(f'{countdown} seconds remaining …',flush=True)
            countdown-=5
        if remaining<=0:
            raise ValueError('WoW is still running after 30 seconds. Quit WoW and select the action again.')
        # Check every second; display the countdown every five seconds.
        time.sleep(min(1,remaining))
        if not wow_is_running():
            print('WoW has closed. Continuing.',flush=True)
            return


def select_number(title,labels):
    while True:
        print('\n'+title)
        for index,label in enumerate(labels,1):print(f'{index}: {label}')
        print('0: Back')
        answer=input('Selection [Enter: back]: ').strip()
        if answer in ('','0'):return None
        if answer.isdecimal() and 1<=int(answer)<=len(labels):return int(answer)-1
        print('Invalid selection. Choose a listed number.')

def browse_records(records,item_name):
    if not records:
        print(f'No {item_name.lower()}s found.')
        return None
    realms=sorted({r['realm'] for r in records},key=str.casefold)
    while True:
        selected=select_number('Select realm',realms)
        if selected is None:return None
        realm=realms[selected]
        characters=sorted({r['character'] for r in records if r['realm']==realm},key=str.casefold)
        while True:
            selected=select_number('Select character – '+realm,characters)
            if selected is None:break
            character=characters[selected]
            choices=[r for r in records if r['realm']==realm and r['character']==character]
            selected=select_number(f'Select {item_name.lower()} – {realm} / {character} (newest first)',[r['label'] for r in choices])
            if selected is not None:return choices[selected]['path']

def backup_records(kind=None):
    records=[]
    for path in backup_entries():
        try:
            with zipfile.ZipFile(path) as z:manifest=json.loads(z.read('manifest.json'))
            stored=manifest.get('kind','combined')
            if kind and stored not in (kind,'combined'):continue
            info=manifest['source_identity']
            realm=info['realm'];character=info['full']
            if not isinstance(realm,str) or not isinstance(character,str):raise ValueError('Invalid identity')
            label=f'{path.name} [{stored}]'
        except (OSError,ValueError,KeyError,TypeError,AttributeError,zipfile.BadZipFile):
            if kind:continue
            realm='Unknown Realm';character='Unreadable backups';label=path.name+' [unreadable metadata]'
        records.append({'path':path,'realm':realm,'character':character,'label':label})
    return records

def recovery_records():
    records=[]
    for path in recovery_entries():
        try:
            log=json.loads((path/'manifest.json').read_text())
            target=log.get('target') or recovery_context(log['client'],(e['path'] for e in log['files']))
            realm=target['realm'];character=target['character']
            if not isinstance(realm,str) or not isinstance(character,str):raise ValueError('Invalid identity')
            label=f'{path.name} – {english_legacy_text(log["label"])} [{log["status"]}]'
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            realm='Unknown Realm';character='Unassigned'
            label=path.name+' [unreadable metadata]'
        records.append({'path':path,'realm':realm,'character':character,'label':label})
    return records

def choose_snapshot(kind=None):
    return browse_records(backup_records(kind),'Backup')

def choose_recovery():
    return browse_records(recovery_records(),'Recovery point')


def menu():
    while True:
        try:
            if menu_action() is False:return
        except EOFError:
            print('\nExiting.')
            return
        except KeyboardInterrupt:
            print('\nAction cancelled. Returning to the main menu.')
        except (ValueError,OSError,KeyError,IndexError,zipfile.BadZipFile) as error:
            print('\nCancelled: '+str(error),file=sys.stderr)
        print()

def menu_action():
    print('WoW – Addon Backup for Beta → Release\n')
    print('1  Backup\n2  Restore\n3  Recovery\n0  Exit')
    action=input('Selection: ').strip()
    if action=='0':return False
    if action in ('1','2','3'):
        parent=action
        print({'1':'1.1  Backup Addons\n1.2  Backup Macros\n1.3  Verify Backup\n1.4  Delete Backup',
               '2':'2.1  Restore Addons\n2.2  Restore Macros',
               '3':'3.1  Restore Recovery Point\n3.2  Delete Recovery Point'}[parent])
        print('0  Back to main menu')
        selected=input('Selection [Enter: back]: ').strip()
        if selected in ('','0'):return
        action=selected if '.' in selected else parent+'.'+selected
        if not action.startswith(parent+'.'):raise ValueError('Unknown selection')
    if action in ('1.1','1.2'):
        client=choose_client()
        char=choose_character(client)
        wait_for_wow_closed()
        if not identity(char):
            apply_plan(client,helper_plan(client,character=char),'Prepare character detection for backup',character=char)
            print('Start WoW, log in with the template character, then quit completely. If needed, enable "WoW UI Transfer Identity" in the AddOns menu (and Load out of date AddOns).')
            input('Press Enter when finished …');wait_for_wow_closed()
        create_backup(client,char,kind="addons" if action=="1.1" else "macros")
    elif action=='2.1':
        archive=choose_snapshot('addons')
        if archive is None:return
        print('Verifying backup …',flush=True);manifest=verify_backup(archive)
        require_backup_kind(manifest,'addons')
        manifest=select_supported_addons(manifest)
        if manifest is None:return
        client=choose_client(release=True)
        print('Preparation installs missing addons from the backup and keeps existing installed versions.')
        char=choose_character(client)
        wait_for_wow_closed()
        apply_plan(client,install_plan(archive,manifest,client,character=char),'Prepare addon files and character detection',character=char)
        helper=char/'SavedVariables'/f'{HELPER}.lua'
        if not helper.exists():
            print('\nStart WoW, log in with '+char.name.replace('-',' ',1)+', then quit WoW completely.')
            print('Character detection records the new realm and GUID. Enable "WoW UI Transfer Identity" in the AddOns menu; enable "Load out of date AddOns" if needed.')
            input('Press Enter when finished …');wait_for_wow_closed()
        if not helper.exists():raise ValueError('Character identity has not been saved yet. Enable the addon, log in, and quit WoW; then select Restore → Restore Addons again.')
        plan,notes,target=restore_plan(archive,manifest,client,char)
        print(f'\nBackup: {manifest["created"]}\nTemplate: {manifest["source_identity"]["full"]}\nTarget: {target["full"]} – {target["realm"]}\nInstallation: {client}\n{len(plan)} settings files will be changed.')
        print('Account-wide addon profiles, layouts, and key bindings also affect other characters on the destination account.')
        for note in notes:print(note)
        if input('Are you sure you want to restore the selected addon settings? [y/N]: ').strip().lower() not in ('y','yes'):return
        apply_plan(client,plan,'Restore UI backup to '+target['full']+' – '+target['realm'],character=char)
        print('Done. Start WoW and check the layout. Character detection is now disabled for this character.')
    elif action=='2.2':
        archive=choose_snapshot('macros')
        if archive is None:return
        print('Verifying backup …',flush=True);manifest=verify_backup(archive)
        require_backup_kind(manifest,'macros')
        print('Source character: '+manifest['source_identity']['full'])
        client=choose_client();char=choose_character(client)
        scope=input('Macro scope: character / account / both [Enter: character]: ').strip().lower() or 'character'
        plan,notes=macro_plan(archive,manifest,client,char,scope)
        print('Destination: '+str(char))
        if scope in ('account','both'):print('Account macros are shared by ALL characters on the destination account.')
        show_macro_notes(notes)
        if not plan:print('No changes required.');return
        wait_for_wow_closed()
        if input('Are you sure you want to replace the selected macro files? [y/N]: ').strip().lower() not in ('y','yes'):
            print('Cancelled; no macros restored.')
            return
        apply_plan(client,plan,'Restore macros to '+char.name+' ('+scope+')',character=char)
    elif action=='3.1':
        selected=choose_recovery()
        if selected is None:return
        wait_for_wow_closed();undo(selected)
    elif action=='1.4':
        deletion_menu()
    elif action=='3.2':
        deletion_menu(recovery=True)
    elif action=='1.3':
        archive=choose_snapshot()
        if archive is None:return
        manifest=verify_backup(archive)
        print(f'Backup is valid: {len(manifest["files"])} files, {len(manifest["addons"])} addon directories, created {manifest["created"]}.')
        if pending_reviews(manifest):print('Needs review: '+', '.join(pending_reviews(manifest)))
    else:raise ValueError('Unknown selection')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',nargs='?',choices=['menu','backup','verify','prepare','restore','restore-macros','undo'],default='menu')
    ap.add_argument('--client',type=Path);ap.add_argument('--character',type=Path)
    ap.add_argument('--backup',type=Path);ap.add_argument('--recovery',type=Path)
    ap.add_argument('--apply',action='store_true');ap.add_argument('--closed',action='store_true')
    ap.add_argument('--replace-addons',action='store_true',help='Also replace existing addon versions with versions from the backup')
    ap.add_argument('--macro-scope',choices=['character','account','both'],default='character',help='Macro files to replace with restore-macros (default: character)')
    ap.add_argument('--backup-kind',choices=['addons','macros','combined'],default='addons',help='Contents for backup (default: addons)')
    args=ap.parse_args()
    if args.action=='menu':return menu()
    if args.action=='backup':
        if not args.closed:raise ValueError('Quit WoW before backing up and specify --closed.')
        if not args.client or not args.character:raise ValueError('--client and --character are required')
        return create_backup(args.client,args.character,kind=args.backup_kind)
    if args.action=='undo':
        if not args.closed or not args.recovery:raise ValueError('--closed and --recovery are required')
        return undo(args.recovery)
    archive=args.backup or latest_backup('macros' if args.action=='restore-macros' else 'addons' if args.action in ('prepare','restore') else None);manifest=verify_backup(archive)
    if args.action=='verify':
        print(f'Backup is valid: {len(manifest["files"])} files.');return
    if not args.client:raise ValueError('--client is required')
    client=args.client.resolve()
    if args.action=='restore-macros':
        if not args.character:raise ValueError('--character is required')
        plan,notes=macro_plan(archive,manifest,client,args.character,args.macro_scope)
        if args.macro_scope in ('account','both'):print('Account macros are shared by ALL characters on the destination account.')
        show_macro_notes(notes)
    elif args.action=='prepare':
        if not args.character:raise ValueError('--character is required')
        char=args.character.resolve()
        if char not in [p.resolve() for p in characters(client)]:raise ValueError('Character does not belong to the destination client')
        plan=install_plan(archive,manifest,client,args.replace_addons,character=char)
    else:
        if not args.character:raise ValueError('--character is required')
        char=args.character.resolve()
        if char not in [p.resolve() for p in characters(client)]:raise ValueError('Target character does not belong to the destination client')
        plan,notes,target=restore_plan(archive,manifest,client,char)
        for note in notes:print(note)
        print('Target:',target['full'],target['realm'])
    print(f'Plan: {len(plan)} files. '+('Applying changes next.' if args.apply else 'Preview only; no changes.'))
    if args.apply:
        if not args.closed:raise ValueError('Quit WoW before applying changes and specify --closed.')
        return apply_plan(client,plan,args.action,character=args.character)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,IndexError,zipfile.BadZipFile) as error:
        print('\nCancelled: '+str(error),file=sys.stderr);sys.exit(1)
    except KeyboardInterrupt:
        print('\nCancelled.',file=sys.stderr);sys.exit(130)
