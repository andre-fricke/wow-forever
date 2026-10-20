local frame, cursor, combat, blocked
local actions = {[1]={"macro",1}, [73]={"macro",121}, [180]={"macro",1}, [3]={"spell",42}}
local macros = {[1]={"Account",1,"/say hi\n"}, [121]={"Character",2,"/dance\n"}}
MAX_ACCOUNT_MACROS=120
SlashCmdList={}
DEFAULT_CHAT_FRAME={AddMessage=function() end}
C_Timer={After=function(_, fn) fn() end}
function CreateFrame()
    frame={RegisterEvent=function() end, SetScript=function(self,_,fn) self.event=fn end}
    return frame
end
function GetActionInfo(slot) if actions[slot] then return unpack(actions[slot]) end end
function GetMacroInfo(index) if macros[index] then return unpack(macros[index]) end end
function GetNumMacros() return 2,1 end
function GetCursorInfo() if cursor then return unpack(cursor) end end
function PickupMacro(index) cursor={"macro",index} end
function PlaceAction(slot) if not blocked then actions[slot]=cursor end end
function ClearCursor() cursor=nil end
function InCombatLockdown() return combat end
function time() return 123 end
function UnitGUID() return "Player-1" end
assert(loadfile(arg[1]))()
frame.event(frame,"PLAYER_LOGOUT")
assert(WoWUITransferBars.slots[73].scope=="character")
assert(WoWUITransferBars.slots[180].name=="Account")
assert(WoWUITransferBars.slots[3]==nil)
WoWUITransferBarsPending={schema=1, slots=WoWUITransferBars.slots}
-- IDs changed; same name with a different body must not be selected.
macros[2]=macros[1];macros[1]={"Account",1,"/wrong"}
actions[1]={"spell",9};actions[73]=nil
combat=true;SlashCmdList.WOWUIBARS();assert(actions[1][1]=="spell")
combat=false;cursor={"item",99};SlashCmdList.WOWUIBARS();assert(cursor[1]=="item")
cursor=nil;blocked=true;SlashCmdList.WOWUIBARS();assert(WoWUITransferBarsPending)
blocked=false;frame.event(frame,"PLAYER_ENTERING_WORLD")
assert(actions[1][2]==2 and actions[73][2]==121 and actions[180][2]==2)
assert(actions[3][1]=="spell" and WoWUITransferBarsPending==nil and cursor==nil)
actions[1]={"spell",5};frame.event(frame,"PLAYER_ENTERING_WORLD")
assert(actions[1][1]=="spell") -- completed restore never replays
WoWUITransferBarsPending={schema=1,slots={[10]={scope="account",name="Missing",body="/missing"}}}
SlashCmdList.WOWUIBARS()
assert(WoWUITransferBarsPending.slots[10] and not actions[10])
-- The modern API returns resolved spell/item IDs, not macro indices.
local originalInfo = GetActionInfo
function GetActionInfo(slot)
    local kind,index=originalInfo(slot)
    if kind=="macro" then return kind,slot==73 and 999999 or 777777,slot==73 and "item" or "spell" end
    return kind,index
end
C_ActionBar={GetActionText=function(slot)
    local kind,index=originalInfo(slot)
    return kind=="macro" and macros[index][1] or nil
end}
-- Modern constants only; the legacy global may no longer exist.
Constants={MacroConsts={MAX_ACCOUNT_MACROS=120}}
MAX_ACCOUNT_MACROS=nil
assert(loadfile(arg[1]))()
actions={[1]={"macro",2},[73]={"macro",121},[3]={"spell",42}}
-- Rename unrelated macro to remove duplicate names.
macros[1]={"Other",1,"/wrong"}
frame.event(frame,"ACTIONBAR_SLOT_CHANGED")
assert(WoWUITransferBars.schema==2 and WoWUITransferBars.macroActions==2)
assert(WoWUITransferBars.slots[73].scope=="character")
assert(WoWUITransferBars.slots[1].scope=="account")
assert(not next(WoWUITransferBars.unresolvedSlots))
WoWUITransferBarsPending={schema=1,slots=WoWUITransferBars.slots}
actions[1]={"spell",5};actions[73]=nil
SlashCmdList.WOWUIBARS()
assert(actions[1][2]==2 and actions[73][2]==121 and not WoWUITransferBarsPending)
-- All APIs becoming empty during logout must not destroy the live snapshot.
frame.event(frame,"UPDATE_MACROS")
actions={}
frame.event(frame,"PLAYER_LOGOUT")
assert(WoWUITransferBars.macroActions==2)
-- Ambiguous labels must be reported, not silently saved as a successful empty list.
actions[1]={"macro",2};macros[1]={"Account",1,"/wrong"}
frame.event(frame,"UPDATE_MACROS")
assert(WoWUITransferBars.macroActions==1 and WoWUITransferBars.unresolvedSlots[1])
-- A truly empty in-world action bar remains a valid empty capture.
actions={}
frame.event(frame,"ACTIONBAR_SLOT_CHANGED")
assert(WoWUITransferBars.macroActions==0 and not next(WoWUITransferBars.slots))
print("PASS macro capture, changed IDs, scope, combat/cursor guards, blocked placement, missing macros, one-shot restore")
print("PASS resolved spell/item IDs, modern constants, placement verification, ambiguous names and logout teardown")
