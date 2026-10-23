local folder = arg[1]
local callbacks, reloads, combat, cursor = {}, 0, false, false
local macroList, bindings, placements = {}, {}, 0
local level, blockedClicks = 1, false
local function clone(t)
    if type(t) ~= "table" then return t end
    local out = {}; for k,v in pairs(t) do out[k] = clone(v) end; return out
end
local validEvents={PLAYER_ENTERING_WORLD=true,PLAYER_REGEN_ENABLED=true,CINEMATIC_STOP=true,STOP_MOVIE=true,
    UPDATE_MACROS=true,PLAYER_LOGOUT=true,ACTIONBAR_SLOT_CHANGED=true}
CreateFrame = function() return {RegisterEvent = function(_, event) assert(validEvents[event], "Unknown event: " .. event) end,
    SetScript = function(_, _, fn) table.insert(callbacks, fn) end} end
C_Timer = {After = function(_, fn) fn() end}
local messages = {}
DEFAULT_CHAT_FRAME = {AddMessage = function(_, message) table.insert(messages, message) end}
InCombatLockdown = function() return combat end
GetCursorInfo = function() return cursor end
UnitLevel = function() return level end
ReloadUI = function() reloads = reloads + 1 end
SlashCmdList = {}
local enabled = {Example = 2}
C_AddOns = {
    DoesAddOnExist = function(name) return name ~= "RemovedAddon" end,
    GetAddOnEnableState = function(name, guid) assert(guid:match("Player")); return enabled[name] or 0 end,
    EnableAddOn = function(name) enabled[name] = 2 end,
    DisableAddOn = function(name) enabled[name] = 0 end,
    IsAddOnLoaded = function() return true end,
}
MAX_ACCOUNT_MACROS, MAX_CHARACTER_MACROS = 120, 30
GetNumMacros = function()
    local a,c=0,0; for index in pairs(macroList) do if index>120 then c=c+1 else a=a+1 end end; return a,c
end
GetMacroInfo = function(index)
    local m=macroList[index]; if m then return m.name,m.icon,m.body end
end
CreateMacro = function(name,icon,body,character)
    local a,c=GetNumMacros(); local index=character and 121+c or 1+a
    macroList[index]={name=name,icon=icon,body=body}; return index
end
C_ClickBindings = {
    SetProfileByInfo = function(t) if not blockedClicks then bindings=clone(t) end end,
    GetProfileInfo = function() return clone(bindings) end,
}
SlashCmdList.WOWUIBARS = function() if WoWUITransferBarsPending then placements=placements+1; WoWUITransferBarsPending=nil end end
local source = {name="Old",full="Old Surname",guid="Player-old",realm="Beta",realmKey="PvP",class="DRUID"}
local chatApplications = 0
local editSelections = 0
WoWUITransferSelectEditMode = function(name) assert(name=="default");editSelections=editSelections+1 end
WoWUITransferChat = {Apply=function() chatApplications=chatApplications+1 end}
local macro = {scope="character",name="Heal",body="/cast Heal",icon=123}
local template = {id="v1",source=source,flags={Example=true},
    profiles={ExampleDB={addon="Example",profile={owner="Old Surname",width=150},namespaces={Font={profile={size=18},namespaces={}}}}},
    characters={Example={ExampleChar={height=60}}},macros={[121]=macro},slots={[3]=macro},hasMacros=true,hasClicks=true,
    clicks={{type=2,actionID=121,button="LeftButton",modifiers=0}},clickMacros={[121]=macro}}
template.profiles.RemovedDB = {addon="RemovedAddon",profile={},namespaces={}}
template.characters.RemovedAddon = {RemovedCharDB={size=123}}
template.chat = {}
template.macroPolicy=1
local nullMacro=clone(macro);nullMacro.body="/cast null"
template.differentClass={macros={[121]=nullMacro},slots={[3]=nullMacro},clickMacros={[121]=nullMacro}}
ExampleDB={profiles={Default={width=99}},profileKeys={Existing="Default"},namespaces={}}
ExampleChar={untouched=true}
local db={sv=ExampleDB,SetProfile=function(self,p) self.selected=p end,GetCurrentProfile=function(self) return self.selected end}
LibStub=function() return {db_registry={[db]=true}} end
WoWUITransferIdentity={name="New",full="New Surname",guid="Player-new",realm="Release",realmKey="PvE",class="DRUID"}
WoWUITransferAuto={schema=1,enabled=true,excluded={["Player-existing"]=true},characters={},template=clone(template)}
dofile(folder .. "/autosetup.lua")
local apply=SlashCmdList.WOWUISETUP
local configured = WoWUITransferAuto
WoWUITransferAuto = nil; apply()
assert(messages[#messages]:match("No automatic setup template"))
WoWUITransferAuto = configured
configured.enabled = false; apply()
assert(messages[#messages]:match("disabled"))
configured.enabled = true
combat=true; apply(); assert(not next(WoWUITransferAuto.characters)); combat=false
cursor=true; apply(); assert(not next(WoWUITransferAuto.characters)); cursor=false
WoWUITransferIdentity.guid="Player-existing"; apply(); assert(not next(WoWUITransferAuto.characters))
assert(messages[#messages]:match("excluded"))
WoWUITransferIdentity.guid="Player-new"; apply()
assert(reloads==1 and WoWUITransferAuto.characters["Player-new"].phase=="bindings")
assert(WoWUITransferAuto.characters["Player-new"].skippedAddons.RemovedAddon and RemovedCharDB == nil)
assert(ExampleDB.profiles["UI Transfer Player-new"].owner=="New Surname")
assert(ExampleDB.profiles.Default.width==99 and ExampleDB.profileKeys.Existing=="Default")
assert(ExampleDB.namespaces.Font.profiles["UI Transfer Player-new"].size==18)
assert(ExampleChar.height==60 and ExampleChar.untouched)
-- A different existing macro shifts the source macro's destination API index.
macroList[121]={name="Other",body="/dance",icon=1}
blockedClicks=true; apply()
assert(not WoWUITransferAuto.characters["Player-new"].done)
assert(WoWUITransferAuto.characters["Player-new"].macros)
assert(macroList[122].name=="Heal")
-- Updating the account template never changes an in-progress character.
WoWUITransferAuto.template.id="v2"
blockedClicks=false; apply()
assert(bindings[1].actionID==122 and placements==1)
assert(WoWUITransferAuto.characters["Player-new"].done and WoWUITransferAuto.characters["Player-new"].templateID=="v1")
ExampleChar.height=999; bindings={}; apply()
assert(messages[#messages]:match("already complete"))
assert(ExampleChar.height==999 and #bindings==0 and placements==1 and reloads==2)
assert(chatApplications==1)
assert(editSelections==1)
WoWUITransferIdentity.guid="Player-highlevel"; level=5; apply(); assert(WoWUITransferAuto.excluded["Player-highlevel"])
level=1; WoWUITransferIdentity.guid="Player-disabled"; WoWUITransferAuto.enabled=false; apply(); assert(not WoWUITransferAuto.characters["Player-disabled"])
macroList={[121]={name="Other",body="/dance",icon=1}}
WoWUITransferAuto.enabled=true; WoWUITransferIdentity.guid="Player-rogue"; WoWUITransferIdentity.class="ROGUE"; apply(); apply()
assert(WoWUITransferAuto.characters["Player-rogue"].done and not WoWUITransferAuto.characters["Player-rogue"].classSkipped and placements==2)
assert(bindings[1].actionID==122)
assert(macroList[122].body=="/cast null")
-- A legacy completed record explicitly resumes bindings without replaying UI.
WoWUITransferIdentity.guid="Player-legacy"
WoWUITransferAuto.characters["Player-legacy"]={done=true,classSkipped=true}
local oldReloads, oldChat, oldPlacements = reloads, chatApplications, placements
ExampleChar.height=777
combat=true;apply("bindings");assert(WoWUITransferAuto.characters["Player-legacy"].done);combat=false
apply("bindings")
assert(WoWUITransferAuto.characters["Player-legacy"].done and not WoWUITransferAuto.characters["Player-legacy"].classSkipped)
assert(reloads==oldReloads and chatApplications==oldChat and ExampleChar.height==777 and placements==oldPlacements+1)
apply("bindings");assert(placements==oldPlacements+1)
-- Macro conflicts stay pending and never overwrite the existing macro.
WoWUITransferIdentity.class="DRUID"; WoWUITransferIdentity.guid="Player-conflict"
macroList={[121]={name="Heal",body="/say keep",icon=1}}; apply(); apply()
assert(not WoWUITransferAuto.characters["Player-conflict"].done and macroList[121].body=="/say keep")
-- Capacity failure happens before creating any of the missing macros.
WoWUITransferIdentity.guid="Player-full"; MAX_CHARACTER_MACROS=1
macroList={[121]={name="Other",body="/say keep",icon=1}}; apply(); apply()
assert(not macroList[122] and not WoWUITransferAuto.characters["Player-full"].done)
-- Activation uses a character GUID and reloads before settings.
WoWUITransferIdentity.guid="Player-activation"; enabled.Example=0; apply()
assert(WoWUITransferAuto.characters["Player-activation"].phase=="settings" and enabled.Example==2)
print("PASS Lua first-login/reload lifecycle, identity remapping, private namespaces, exclusions, class guards, macro remapping/conflicts/capacity and blocked Click Casting retry")

-- Capture is side-effect-free and retains both macro scopes and native IDs.
WoWUITransferChat = nil
local tick, hooks
hooks = {}
C_Timer.NewTicker = function(_, fn) tick = fn end
UnitGUID = function() return "Player-source" end
time = function() return 123456 end
hooksecurefunc = function(_, name, fn) hooks[name] = fn end
macroList = {[1]={name="Shared",body="/dance",icon=1},[121]={name="Heal",body="/cast Heal",icon=123}}
bindings = {{type=2,actionID=121,button="LeftButton",modifiers=1}}
dofile(folder .. "/setup_capture.lua")
tick()
assert(WoWUITransferSetup.macros[1].scope=="account" and WoWUITransferSetup.macros[121].scope=="character")
assert(WoWUITransferSetup.guid=="Player-source" and WoWUITransferSetup.clicks[1].actionID==121)
bindings[1].modifiers=2; hooks.SetProfileByInfo()
assert(WoWUITransferSetup.clicks[1].modifiers==2)
combat=true; bindings={}; tick(); assert(#WoWUITransferSetup.clicks==1)
print("PASS API capture scopes, native bindings, edit hooks and combat guard")

combat = false
UIParent = {GetWidth=function() return 2000 end, GetHeight=function() return 1000 end, GetEffectiveScale=function() return 1 end}
local function Window(id,x,y)
    return {id=id,x=x,y=y,w=400,h=180,GetEffectiveScale=function() return 0.8 end,
        GetLeft=function(s) return s.x end,GetBottom=function(s) return s.y end,
        GetWidth=function(s) return s.w end,GetHeight=function(s) return s.h end,
        ClearAllPoints=function() end,SetSize=function(s,w,h) s.w=w;s.h=h end,
        SetPoint=function(s,_,_,_,x,y) s.x=x;s.y=y end,Show=function() end}
end
ChatFrame1=Window(1,20,30);ChatFrame2=Window(2,1500,100)
NUM_CHAT_WINDOWS=2
local dock=0
GetChatWindowInfo=function(id) return id==1 and "General" or "Combat Log",14,1,1,1,1,true,true,id==2 and dock or 1 end
local saves=0
FCF_SavePositionAndDimensions=function() saves=saves+1 end
FCF_UnDockFrame=function() dock=0 end
FCF_DockFrame=function(_,index) dock=index end
FCF_SetLocked=function(s,v) s.locked=v end
FCF_SetWindowAlpha=function(s,v) s.alpha=v end
dofile(folder .. "/chat_layout.lua")
local layout=WoWUITransferChat.Capture()
assert(layout[2].alpha==1)
layout[1].alpha=0;layout[2].alpha=0.35
assert(math.abs(layout[2].x-0.6)<0.0001 and layout[2].dock==0)
ChatFrame2.x=0;ChatFrame2.y=0;dock=2
WoWUITransferChat.Apply(layout)
assert(math.abs(ChatFrame2.x-1500)<0.0001 and ChatFrame2.y==100 and dock==0 and saves==2)
assert(ChatFrame1.alpha==0 and ChatFrame2.alpha==0.35)
C_EditMode={GetLayouts=function() return {} end}
ChatFrame1.x=123;ChatFrame1.y=456;ChatFrame1.w=555;ChatFrame1.h=222
ChatFrame2.x=0
local savedBefore=saves
WoWUITransferChat.Apply(layout)
assert(ChatFrame1.x==123 and ChatFrame1.y==456 and ChatFrame1.w==555 and ChatFrame1.h==222)
assert(saves==savedBefore+1 and math.abs(ChatFrame2.x-1500)<0.0001)
assert(ChatFrame1.alpha==0)
C_EditMode=nil
layout[2].dock=2; WoWUITransferChat.Apply(layout); assert(dock==2)
combat=true;local before=saves;assert(not pcall(WoWUITransferChat.Apply,layout));assert(saves==before)
combat=false
WoWUITransferAuto.template.chat=layout
SlashCmdList.WOWUICHAT();assert(messages[#messages]:match("Chat positions restored"))
print("PASS Combat Log capture, scaling, docking, saved geometry, combat guard and explicit chat-only restore")
layout[4]={name="NoSpam",x=0.2,y=0.3,width=0.2,height=0.18,dock=0,locked=true}
local chatInfo=GetChatWindowInfo
GetChatWindowInfo=function(id)
    if id==4 then return "Other" end
    return chatInfo(id)
end
before=saves
WoWUITransferChat.Apply(layout)
assert(saves==before+1 and messages[#messages]:match("Skipped chat position"))
ChatFrame4=Window(4,99,88)
WoWUITransferChat.Apply(layout)
assert(ChatFrame4.x==99 and ChatFrame4.y==88)
GetChatWindowInfo=function(id)
    if id==4 then return "NoSpam" end
    return chatInfo(id)
end
ChatFrame4.isTemporary=true
WoWUITransferChat.Apply(layout)
assert(ChatFrame4.x==99)
ChatFrame4.isTemporary=nil
WoWUITransferChat.Apply(layout)
assert(math.abs(ChatFrame4.x-500)<0.001 and math.abs(ChatFrame4.y-375)<0.001)
local builtin=ChatFrame2
ChatFrame2=nil
before=saves
assert(not pcall(WoWUITransferChat.Apply,layout) and saves==before)
ChatFrame2=builtin
layout[4]=nil;ChatFrame4=nil;GetChatWindowInfo=chatInfo
print("PASS missing, renamed and temporary custom windows do not block setup; matching windows restore; missing built-ins still fail")
NUM_CHAT_WINDOWS=4
local created=0
GetChatWindowInfo=function(id)
    if id>2 then return id==3 and created>0 and "NoSpam" or "",14,1,1,1,1,id==3 and created>0,true,0 end
    return chatInfo(id)
end
FCF_OpenNewWindow=function(name)
    assert(name=="NoSpam");created=created+1
    ChatFrame3=Window(3,0,0); return ChatFrame3
end
ChatFrame_RemoveAllMessageGroups=function(f) f.groups={} end
ChatFrame_AddMessageGroup=function(f,g) table.insert(f.groups,g) end
ChatFrame_RemoveAllChannels=function(f) f.channels={} end
ChatFrame_AddChannel=function(f,c) table.insert(f.channels,c) end
layout[4]={name="NoSpam",x=0.2,y=0.3,width=0.2,height=0.18,dock=0,locked=true,
    subscriptions={messages={"SAY","GUILD"},channels={"General"}}}
WoWUITransferChat.Apply(layout)
assert(created==1 and ChatFrame3.groups[2]=="GUILD" and ChatFrame3.channels[1]=="General")
assert(math.abs(ChatFrame3.x-500)<0.001)
WoWUITransferChat.Apply(layout);assert(created==1 and #ChatFrame3.groups==2)
local globalAddChannel = ChatFrame_AddChannel
ChatFrame_AddChannel = nil
ChatFrame3.AddChannel = globalAddChannel
WoWUITransferChat.Apply(layout)
assert(created==1 and ChatFrame3.channels[1]=="General")
ChatFrame3.AddChannel = nil
local originalGroups = ChatFrame3.groups
local apiOK, apiError = pcall(WoWUITransferChat.Apply,layout)
assert(not apiOK and apiError:match("AddChannel") and ChatFrame3.groups==originalGroups)
ChatFrame_AddChannel = globalAddChannel
GetChatWindowMessages=function() return "SAY","GUILD" end
GetChatWindowChannels=function() return "General",1 end
local capturedChat=WoWUITransferChat.Capture()
assert(capturedChat[3].subscriptions.messages[2]=="GUILD" and capturedChat[3].subscriptions.channels[1]=="General")
FCF_OpenNewWindow=function() return nil end
ChatFrame3=nil;created=0
assert(not pcall(WoWUITransferChat.Apply,layout))
layout[4]=nil;NUM_CHAT_WINDOWS=2;GetChatWindowInfo=chatInfo
print("PASS custom window capture, creation with different ID, subscriptions, retry without duplicates and capacity failure")

local layoutInfo={activeLayout=1,layouts={{layoutName="Other"},{layoutName="default"}}}
EditModePresetLayoutManager={GetCopyOfPresetLayouts=function() return {{},{}} end}
local switches=0
C_EditMode={GetLayouts=function() return layoutInfo end,SetActiveLayout=function(id) switches=switches+1;layoutInfo.activeLayout=id end}
dofile(folder .. "/edit_mode.lua")
WoWUITransferSelectEditMode("default");assert(layoutInfo.activeLayout==4 and switches==1)
WoWUITransferSelectEditMode("default");assert(switches==1)
assert(not pcall(WoWUITransferSelectEditMode,"missing"));assert(switches==1)
table.insert(layoutInfo.layouts,{layoutName="default"})
assert(not pcall(WoWUITransferSelectEditMode,"default"));assert(switches==1)
table.remove(layoutInfo.layouts)
combat=true;assert(not pcall(WoWUITransferSelectEditMode,"default"));combat=false
layoutInfo.activeLayout=1;C_EditMode.SetActiveLayout=function() end
assert(not pcall(WoWUITransferSelectEditMode,"default"))
print("PASS named Edit Mode selection, preset index offset, idempotence, missing/ambiguous layouts, combat and blocked selection")

-- Generated macros can legitimately differ on every character and login.
dofile(folder .. "/managed_macros.lua")
local loadedOwner=true
C_AddOns.IsAddOnLoaded=function() return loadedOwner end
macroList={[1]={name="Decursive",body="/cast Current Dispel",icon=1}}
local owned={name="Decursive",body="/cast null",scope="account",icon=1}
assert(WoWUITransferManagedMacro(owned)==1)
loadedOwner=false;assert(WoWUITransferManagedMacro(owned)==nil);loadedOwner=true
assert(WoWUITransferManagedMacro({name="Decursive",scope="character"})==nil)
macroList[2]=clone(macroList[1]);assert(not pcall(WoWUITransferManagedMacro,owned));macroList[2]=nil
WoWUITransferIdentity.guid="Player-managed";WoWUITransferIdentity.class="DRUID"
local ownedTemplate={id="managed",source=source,hasMacros=true,hasClicks=true,
    macros={[1]=owned},slots={[7]=owned},clickMacros={[1]=owned},
    clicks={{type=2,actionID=1,button="LeftButton",modifiers=0}}}
WoWUITransferAuto.characters["Player-managed"]={phase="bindings",template=ownedTemplate}
apply()
assert(WoWUITransferAuto.characters["Player-managed"].done)
assert(macroList[1].body=="/cast Current Dispel" and bindings[1].actionID==1)
-- The same resolver handles queued placement even if the addon edits again.
local actions, held={},nil
GetActionInfo=function(slot) if actions[slot] then return "macro",actions[slot] end end
GetCursorInfo=function() if held then return "macro",held end end
PickupMacro=function(index) held=index end
PlaceAction=function(slot) actions[slot]=held end
ClearCursor=function() held=nil end
dofile(folder .. "/actionbars.lua")
WoWUITransferBarsPending={schema=1,slots={[7]=owned}}
macroList[1].body="/cast Updated Again"
SlashCmdList.WOWUIBARS()
assert(actions[7]==1 and WoWUITransferBarsPending==nil and macroList[1].body=="/cast Updated Again")
macroList[1].name="RS_MACRO";owned.name="RS_MACRO"
assert(WoWUITransferManagedMacro(owned)==1)
owned.name="User Macro";assert(WoWUITransferManagedMacro(owned)==nil)
print("PASS managed macro conflicts, owner/scope/ambiguity checks, retained bodies, Click Casting and live action-slot resolution")
local timers={}
C_Timer.After=function(_, fn) timers[#timers+1]=fn end
WoWUITransferAuto={schema=1,enabled=true,excluded={},characters={}}
local readyIdentity=WoWUITransferIdentity
WoWUITransferIdentity=nil
callbacks[1](nil,"PLAYER_ENTERING_WORLD")
table.remove(timers,1)()
assert(#timers==1) -- initial identity was not ready: automatically retry
WoWUITransferIdentity=readyIdentity
WoWUITransferAuto.characters[readyIdentity.guid]={phase="bindings",template={source={class=readyIdentity.class}}}
table.remove(timers,1)()
assert(WoWUITransferAuto.characters[readyIdentity.guid].done and #timers==0)
callbacks[1](nil,"PLAYER_ENTERING_WORLD")
callbacks[1](nil,"CINEMATIC_STOP")
assert(#timers==2)
table.remove(timers,1)();assert(#timers==1) -- stale chain cancelled
table.remove(timers,1)();assert(#timers==0) -- completed state not replayed
WoWUITransferIdentity=nil
callbacks[1](nil,"PLAYER_ENTERING_WORLD")
local attempts=0
while #timers>0 do attempts=attempts+1;assert(attempts<=12);table.remove(timers,1)() end
assert(attempts==12)
print("PASS delayed identity, automatic continuation without slash command, cinematic timer deduplication and bounded retries")
WoWUITransferIdentity=readyIdentity
local tries=0
WoWUITransferChat.Apply=function()
    tries=tries+1
    if tries<3 then error("Chat client not ready") end
end
WoWUITransferAuto.characters[readyIdentity.guid]={phase="bindings",error="old saved error",
    template={source={class=readyIdentity.class},chat={}}}
callbacks[1](nil,"PLAYER_ENTERING_WORLD")
table.remove(timers,1)();assert(#timers==1 and tries==1)
table.remove(timers,1)();assert(#timers==1 and tries==2)
table.remove(timers,1)()
assert(tries==3 and #timers==0 and WoWUITransferAuto.characters[readyIdentity.guid].done)
assert(WoWUITransferAuto.characters[readyIdentity.guid].error==nil)
print("PASS transient errors and stale saved errors automatically recover without slash commands")
-- Simulate cinematic skip and actual Lua reloads: discard timers/local state,
-- retain SavedVariables, and load the helper again before ENTERING_WORLD.
local cinematic, reloadRequested = true, false
InCinematic=function() return cinematic end
ReloadUI=function() reloadRequested=true end
C_UI={Reload=function() reloadRequested=true end}
ReloadUI=function() error("Legacy reload must not be called when C_UI.Reload is available") end
WoWUITransferIdentity=clone(readyIdentity)
WoWUITransferIdentity.guid="Player-reload-test"
local reloadTemplate={id="reload-test",source=clone(source),flags={Example=true},profiles={},characters={},chat={}}
WoWUITransferAuto={schema=1,enabled=true,excluded={},characters={},template=reloadTemplate}
WoWUITransferSelectEditMode=function() end
enabled.Example=0
local function LoadSession()
    timers={} -- all old timer callbacks disappear on reload
    dofile(folder .. "/autosetup.lua")
    return callbacks[#callbacks]
end
local event=LoadSession()
event(nil,"PLAYER_ENTERING_WORLD")
table.remove(timers,1)()
assert(next(WoWUITransferAuto.characters)==nil) -- never configure during cinematic
cinematic=false
event=LoadSession() -- cinematic skip causes an additional UI reload
event(nil,"PLAYER_ENTERING_WORLD")
table.remove(timers,1)()
local record=WoWUITransferAuto.characters[WoWUITransferIdentity.guid]
assert(reloadRequested and record.phase=="settings")
reloadRequested=false
event=LoadSession();event(nil,"PLAYER_ENTERING_WORLD");table.remove(timers,1)()
assert(reloadRequested and record.phase=="bindings")
reloadRequested=false
event=LoadSession();event(nil,"PLAYER_ENTERING_WORLD");table.remove(timers,1)()
assert(record.done and reloadRequested and #timers==0)
reloadRequested=false
event=LoadSession();event(nil,"PLAYER_ENTERING_WORLD");table.remove(timers,1)()
assert(record.done and not reloadRequested and #timers==0)
-- Older clients can reject STOP_MOVIE without breaking the main handler.
validEvents.STOP_MOVIE=nil
event=LoadSession();event(nil,"PLAYER_ENTERING_WORLD");table.remove(timers,1)()
assert(record.done and #timers==0)
print("PASS cinematic skip, three automatic phases across real session resets, strict event names and unavailable optional movie event")
