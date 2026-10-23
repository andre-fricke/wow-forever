-- Read addon CODE only; never execute personal SavedVariables.
-- Opt-in Lua 5.1 diagnostic, not an in-game addon or an automatic test.
-- Usage: lua reproduce_chat_store.lua /path/to/EUI_Chat_Position.lua /path/to/autosetup.lua
assert(arg[1] and arg[2], "Provide the EUI position source and helper autosetup source paths")
local path=arg[1]
local file=assert(io.open(path,'rb'));local source=file:read('*a');file:close()
local boundary=assert(source:find("-- Unlock mode's Reset",1,true))
local function copy(t)
    if type(t)~='table' then return t end
    local out={};for k,v in pairs(t) do out[k]=copy(v) end;return out
end
local function sys(x,y,w,h)
    return {system=8,anchorInfo={point='BOTTOMLEFT',relativePoint='BOTTOMLEFT',relativeTo='UIParent',offsetX=x,offsetY=y},
        settings={{setting=0,value=math.floor(w/100)},{setting=1,value=w%100},{setting=2,value=math.floor(h/100)},{setting=3,value=h%100}}}
end
local baseline={activeLayout=3,layouts={{layoutType=0},{layoutType=0},
    {layoutName='default',layoutType=1,systems={sys(0,120,640,480)}},
    {layoutName='Other',layoutType=1,systems={sys(20,30,600,400)}}}}
local live=copy(baseline)
local cfg={chatPosition={point='BOTTOMLEFT',relPoint='BOTTOMLEFT',x=40,y=20},chatSize={w=500,h=300}}
local writes=0
local ns={_internals={},ECHAT={DB=function() return cfg end}}
local env={math=math,min=math.min,max=math.max,floor=math.floor,type=type,ipairs=ipairs,pairs=pairs,pcall=pcall,
    InCombatLockdown=function() return false end,
    ChatFrame1={GetScale=function() return 1 end},
    Enum={EditModeSystem={ChatFrame=8},EditModeChatFrameSetting={WidthHundreds=0,WidthTensAndOnes=1,HeightHundreds=2,HeightTensAndOnes=3},EditModeLayoutType={Preset=0}},
    C_EditMode={GetLayouts=function() return live end,SaveLayouts=function(blob) writes=writes+1;live=copy(blob) end},
    EllesmereUI={EditModeOpen=function() return false end,EditModeLayoutsForSave=function() return copy(live),2 end,
        NoteEditModeSetting=function() end,NoteEditModeAnchor=function() end}}
env._G=env
local chunk=assert(loadstring(source:sub(1,boundary-1),'EUI_Chat_Position excerpt'))
setfenv(chunk,env);chunk('EllesmereUIChat',ns)
ns.EMChatSync()
local current=live.layouts[3].systems[1]
local w=current.settings[1].value*100+current.settings[2].value
local h=current.settings[3].value*100+current.settings[4].value
assert(writes==1 and current.anchorInfo.offsetX==40 and current.anchorInfo.offsetY==20 and w==500 and h==300)
assert(live.layouts[4].systems[1].anchorInfo.offsetY==30)
print('REPRODUCED: exact installed EMChatSync changes default from y=120 / 640x480 to y=20 / 500x300.')
ns.EMChatSync();assert(writes==1)
print('REPRODUCED: the shared change persists; no further write is required on later calls.')
-- A competing addon can run while the helper waits for its four-second timer.
-- The helper later disabling that addon does not roll back a completed save.
local addonEnabled=true
local helper=assert(io.open(arg[2],'rb'));local helperSource=helper:read('*a');helper:close()
local start=assert(helperSource:find('local function Activate(template, who)',1,true))
local finish=assert(helperSource:find('\nlocal function Apply(manual)',start,true))
local activate=assert(loadstring(helperSource:sub(start,finish-1)..'\nreturn Activate','real helper Activate'))
local helperEnv={pairs=pairs,error=error,C_AddOns={DoesAddOnExist=function() return true end,
    GetAddOnEnableState=function() return addonEnabled and 2 or 0 end,
    DisableAddOn=function() addonEnabled=false end}}
setfenv(activate,helperEnv)
assert(activate()({flags={EllesmereUIChat=false}},{guid='Player-synthetic'}))
assert(not addonEnabled and live.layouts[3].systems[1].anchorInfo.offsetY==20)
print('REPRODUCED: real helper Activate disables the addon but leaves its earlier shared-layout write intact.')
