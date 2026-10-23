-- API snapshots retain macro identities; cache-file IDs are not API indices.
local frame = CreateFrame("Frame")
local function Capture()
    if InCombatLockdown() or not UnitGUID("player") then return end
    local accountLimit = (Constants and Constants.MacroConsts and Constants.MacroConsts.MAX_ACCOUNT_MACROS)
        or MAX_ACCOUNT_MACROS or 120
    local accounts, characters = GetNumMacros()
    local macros = {}
    for _, range in ipairs({{1, accounts, "account"}, {accountLimit + 1, accountLimit + characters, "character"}}) do
        for index = range[1], range[2] do
            local name, icon, body = GetMacroInfo(index)
            if not name or not body then return end -- Keep the last complete capture.
            macros[index] = {name = name, icon = icon, body = body, scope = range[3]}
        end
    end
    local snapshot = {schema = 1, guid = UnitGUID("player"), savedAt = time(), macros = macros}
    if WoWUITransferChat then snapshot.chat = WoWUITransferChat.Capture() end
    if C_ClickBindings and C_ClickBindings.GetProfileInfo then
        local ok, bindings = pcall(C_ClickBindings.GetProfileInfo)
        if ok and type(bindings) == "table" then
            snapshot.clicks = {}
            for _, binding in ipairs(bindings) do
                table.insert(snapshot.clicks, {type = binding.type, actionID = binding.actionID,
                    button = binding.button, modifiers = binding.modifiers})
            end
        end
    end
    WoWUITransferSetup = snapshot
end
frame:RegisterEvent("PLAYER_ENTERING_WORLD")
frame:RegisterEvent("UPDATE_MACROS")
frame:RegisterEvent("PLAYER_REGEN_ENABLED")
frame:SetScript("OnEvent", function() C_Timer.After(3, Capture) end)
if hooksecurefunc and C_ClickBindings then
    for _, name in ipairs({"SetProfileByInfo", "ResetCurrentProfile"}) do
        if C_ClickBindings[name] then hooksecurefunc(C_ClickBindings, name, Capture) end
    end
end
-- Do not read APIs during logout teardown. Capture periodically while in world
-- so edits made in the native Click Casting panel are included after logout.
C_Timer.NewTicker(5, Capture)
