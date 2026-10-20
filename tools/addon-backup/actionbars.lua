-- Capture standard action slots, including paged/stance bars. Never execute macros.
local frame = CreateFrame("Frame")
local MAX_SLOTS = 180
local ACCOUNT_LIMIT = (Constants and Constants.MacroConsts and Constants.MacroConsts.MAX_ACCOUNT_MACROS)
    or MAX_ACCOUNT_MACROS or 120
local function Say(message)
    DEFAULT_CHAT_FRAME:AddMessage("WoW UI Transfer: " .. message)
end
local function Normalize(body)
    return (body or ""):gsub("\r\n", "\n"):gsub("\n+$", "")
end
-- Spell/item macros may return the resolved spell/item ID, NOT a macro index.
-- Use the action label to find a unique macro; never guess between duplicates.
local function ActionMacro(slot)
    local kind, id, subtype = GetActionInfo(slot)
    if kind ~= "macro" then return nil end
    local getText = C_ActionBar and C_ActionBar.GetActionText or GetActionText
    local label = getText and getText(slot)
    if subtype ~= "spell" and subtype ~= "item" and type(id) == "number" then
        local name = GetMacroInfo(id)
        if name and (not label or label == name) then return id end
    end
    if not label then return nil end
    local accounts, characters = GetNumMacros()
    local found
    for _, range in ipairs({{1, accounts}, {ACCOUNT_LIMIT + 1, ACCOUNT_LIMIT + characters}}) do
        for index = range[1], range[2] do
            local name = GetMacroInfo(index)
            if name == label then
                if found then return nil end
                found = index
            end
        end
    end
    return found
end
local function Capture(atLogout)
    local slots, unresolved, detected, total = {}, {}, 0, 0
    for slot = 1, MAX_SLOTS do
        local kind = GetActionInfo(slot)
        if kind then total = total + 1 end
        if kind == "macro" then
            detected = detected + 1
            local index = ActionMacro(slot)
            local name, body
            if index then
                local icon
                name, icon, body = GetMacroInfo(index)
            end
            if name and body then
                slots[slot] = {
                    scope = index > ACCOUNT_LIMIT and "character" or "account",
                    name = name, body = body,
                }
            else
                unresolved[slot] = true
            end
        end
    end
    -- A client teardown must not erase the last in-world capture.
    if atLogout and total == 0 and WoWUITransferBars and (WoWUITransferBars.totalActions or 0) > 0 then return end
    WoWUITransferBars = {
        schema = 2, slots = slots, savedAt = time(), guid = UnitGUID("player"),
        macroActions = detected, totalActions = total, unresolvedSlots = unresolved,
    }
end
local function Resolve(entry)
    local accounts, characters = GetNumMacros()
    local first = entry.scope == "account" and 1 or ACCOUNT_LIMIT + 1
    local count = entry.scope == "account" and accounts or characters
    for index = first, first + count - 1 do
        local name, _, body = GetMacroInfo(index)
        if name == entry.name and Normalize(body) == Normalize(entry.body) then return index end
    end
end
local function Apply()
    local pending = WoWUITransferBarsPending
    if type(pending) ~= "table" or pending.schema ~= 1 then return end
    if InCombatLockdown() or GetCursorInfo() then
        Say("Macro placement is waiting. Leave combat, clear the cursor and use /wuibars.")
        return
    end
    local remaining, restored = {}, 0
    for slot, entry in pairs(pending.slots or {}) do
        if type(slot) == "number" and slot >= 1 and slot <= MAX_SLOTS and slot == math.floor(slot)
            and type(entry) == "table" and (entry.scope == "account" or entry.scope == "character") then
            local index = Resolve(entry)
            local current = ActionMacro(slot)
            if index and current == index then
                restored = restored + 1
            elseif index then
                PickupMacro(index)
                local cursorKind, cursorIndex = GetCursorInfo()
                if cursorKind == "macro" and cursorIndex == index then
                    PlaceAction(slot)
                    ClearCursor()
                    current = ActionMacro(slot)
                    if current == index then
                        restored = restored + 1
                    else remaining[slot] = entry end
                else
                    ClearCursor()
                    remaining[slot] = entry
                end
            else remaining[slot] = entry end
        end
    end
    -- Completed entries are removed so future logins never overwrite later edits.
    if next(remaining) then
        pending.slots = remaining
        Say(restored .. " macro slots restored. Some macros were missing or blocked; check them and retry with /wuibars.")
    else
        WoWUITransferBarsPending = nil
        Say(restored .. " macro slots restored.")
    end
end
SLASH_WOWUIBARS1 = "/wuibars"
SlashCmdList.WOWUIBARS = Apply
frame:RegisterEvent("PLAYER_ENTERING_WORLD")
frame:RegisterEvent("PLAYER_REGEN_ENABLED")
frame:RegisterEvent("PLAYER_LOGOUT")
frame:RegisterEvent("ACTIONBAR_SLOT_CHANGED")
frame:RegisterEvent("UPDATE_MACROS")
local queued
local function QueueCapture()
    if queued then return end
    queued = true
    C_Timer.After(0.5, function()
        queued = false
        if not InCombatLockdown() then Capture(false) end
    end)
end
frame:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_LOGOUT" then Capture(true)
    elseif event == "PLAYER_ENTERING_WORLD" then
        C_Timer.After(2, function() Apply(); QueueCapture() end)
    elseif event == "PLAYER_REGEN_ENABLED" then Apply(); QueueCapture()
    else QueueCapture() end
end)
