-- Opt-in account template. No filesystem access and no repeated resets of a
-- completed character. Each pending character holds its original template.
local frame = CreateFrame("Frame")
local busy = false
local function Say(message)
    DEFAULT_CHAT_FRAME:AddMessage("WoW UI Transfer: " .. message)
end
local function Copy(value, mapping)
    if type(value) ~= "table" then return mapping and mapping[value] or value end
    local out = {}
    for key, item in pairs(value) do
        out[mapping and mapping[key] or key] = Copy(item, mapping)
    end
    return out
end
local function Merge(dst, src)
    for key, value in pairs(src) do
        if type(value) == "table" and type(dst[key]) == "table" then Merge(dst[key], value)
        else dst[key] = Copy(value) end
    end
end
local function Mapping(source, target)
    local result = {}
    for _, key in ipairs({"name", "full", "guid", "realm", "realmKey", "faction"}) do
        if source[key] and target[key] then result[source[key]] = target[key] end
    end
    for _, separator in ipairs({" - ", "-"}) do
        result[source.name .. separator .. source.realm] = target.name .. separator .. target.realm
    end
    if source.realmKey and target.realmKey then
        result[source.name .. " - " .. source.realmKey] = target.name .. " - " .. target.realmKey
    end
    return result
end
local function Namespaces(dst, source, profile, mapping)
    for name, recipe in pairs(source) do
        dst[name] = dst[name] or {}
        local node = dst[name]
        node.profiles = node.profiles or {}
        node.profiles[profile] = Copy(recipe.profile, mapping)
        node.namespaces = node.namespaces or {}
        Namespaces(node.namespaces, recipe.namespaces, profile, mapping)
    end
end
local function PrivateName(root, guid)
    local name, number = "UI Transfer " .. guid, 1
    local function Occupied(node, candidate)
        if node.profiles and node.profiles[candidate] then return true end
        for _, child in pairs(node.namespaces or {}) do
            if Occupied(child, candidate) then return true end
        end
        return false
    end
    while Occupied(root, name) do number = number + 1; name = "UI Transfer " .. guid .. " " .. number end
    return name
end
local function Load(name)
    if not C_AddOns then error("This client has no supported C_AddOns API") end
    if not C_AddOns.IsAddOnLoaded(name) then
        local loaded, reason = C_AddOns.LoadAddOn(name)
        if not loaded then error("Cannot load " .. name .. ": " .. tostring(reason)) end
    end
end
local function Wanted(template, addon, record)
    if template.flags[addon] == false then return false end
    -- Older prepared templates included orphan SavedVariables even when their
    -- owning addon was no longer installed. Let pending imports recover without
    -- replacing the template or replaying already completed profiles.
    if template.flags[addon] == nil and C_AddOns and C_AddOns.DoesAddOnExist
        and not C_AddOns.DoesAddOnExist(addon) then
        record.skippedAddons = record.skippedAddons or {}
        if not record.skippedAddons[addon] then
            Say("Skipped leftover settings for missing addon: " .. addon)
            record.skippedAddons[addon] = true
        end
        return false
    end
    return true
end
local function Profiles(template, who, record)
    local mapping = Mapping(template.source, who)
    record.profiles = record.profiles or {}
    record.settings = record.settings or {}
    for rootName, recipe in pairs(template.profiles) do
        if Wanted(template, recipe.addon, record) and not record.profiles[rootName] then
            Load(recipe.addon)
            local ace = LibStub and LibStub("AceDB-3.0", true)
            local root = _G[rootName]
            if type(root) ~= "table" then error("Missing addon settings: " .. recipe.addon) end
            local db
            if ace then
                for registered in pairs(ace.db_registry or {}) do
                    if registered.sv == root and not registered.parent then db = registered; break end
                end
            end
            if not db then error("No active AceDB profile adapter for " .. recipe.addon) end
            -- A failed attempt can leave a private profile behind. Allocate a
            -- new one rather than replace a table still cached by AceDB.
            local selected = PrivateName(root, who.guid)
            root.profiles = root.profiles or {}
            root.profiles[selected] = Copy(recipe.profile, mapping)
            root.namespaces = root.namespaces or {}
            Namespaces(root.namespaces, recipe.namespaces, selected, mapping)
            -- SetProfile refreshes cached profile/namespace references. Merely
            -- editing profileKeys after the addon loads is insufficient.
            db:SetProfile(selected)
            if db:GetCurrentProfile() ~= selected then error("Profile switch failed: " .. recipe.addon) end
            root.profileKeys = root.profileKeys or {}
            root.profileKeys[who.full] = selected
            root.profileKeys[who.name .. " - " .. who.realm] = selected
            if recipe.addon == "RXPGuides" and who.realmKey then
                root.profileKeys[who.name .. " - " .. who.realmKey] = selected
            end
            record.profiles[rootName] = true
        end
    end
    for addon, roots in pairs(template.characters) do
        if Wanted(template, addon, record) and not record.settings[addon] then
            Load(addon)
            for name, values in pairs(roots) do
                if type(values) == "table" then
                    _G[name] = _G[name] or {}
                    if type(_G[name]) ~= "table" then error("Unexpected setting type: " .. name) end
                    local imported = Copy(values, mapping)
                    if name == "PawnOptions" and template.source.class ~= who.class then imported.AutoSelectScales = nil end
                    Merge(_G[name], imported)
                else _G[name] = Copy(values, mapping) end
            end
            record.settings[addon] = true
        end
    end
end
local function MacroLimit()
    return (Constants and Constants.MacroConsts and Constants.MacroConsts.MAX_ACCOUNT_MACROS) or MAX_ACCOUNT_MACROS or 120
end
local function Normalize(body) return (body or ""):gsub("\r\n", "\n"):gsub("\n+$", "") end
local function FindMacro(macro)
    local managed = WoWUITransferManagedMacro and WoWUITransferManagedMacro(macro)
    if managed then return managed end
    local accounts, characters = GetNumMacros()
    local first = macro.scope == "account" and 1 or MacroLimit() + 1
    local count = macro.scope == "account" and accounts or characters
    local conflict = false
    for index = first, first + count - 1 do
        local name, _, body = GetMacroInfo(index)
        if name == macro.name then
            if Normalize(body) == Normalize(macro.body) then return index end
            conflict = true
        end
    end
    return nil, conflict
end
local function Macros(template)
    local missing = {account = {}, character = {}}
    local seen = {account = {}, character = {}}
    for _, macro in pairs(template.macros) do
        local index, conflict = FindMacro(macro)
        if not index then
            if conflict then error("Macro name already exists with different contents: " .. macro.name) end
            local prior = seen[macro.scope][macro.name]
            if prior and Normalize(prior.body) ~= Normalize(macro.body) then error("Ambiguous template macro: " .. macro.name) end
            if not prior then table.insert(missing[macro.scope], macro); seen[macro.scope][macro.name] = macro end
        end
    end
    local accounts, characters = GetNumMacros()
    local charLimit = (Constants and Constants.MacroConsts and Constants.MacroConsts.MAX_CHARACTER_MACROS) or MAX_CHARACTER_MACROS or 18
    if accounts + #missing.account > MacroLimit() or characters + #missing.character > charLimit then
        error("Not enough free macro slots; no existing macros were overwritten")
    end
    for _, scope in ipairs({"account", "character"}) do
        for _, macro in ipairs(missing[scope]) do
            CreateMacro(macro.name, macro.icon, macro.body, scope == "character")
            if not FindMacro(macro) then error("Macro creation blocked: " .. macro.name) end
        end
    end
end
local function BindingKey(binding)
    return binding.button .. ":" .. binding.modifiers .. ":" .. binding.type .. ":" .. binding.actionID
end
local function Clicks(template)
    if not C_ClickBindings or not C_ClickBindings.SetProfileByInfo or not C_ClickBindings.GetProfileInfo then
        error("Native Click Casting API unavailable")
    end
    local requested, expected = {}, {}
    for _, value in ipairs(template.clicks) do
        local binding = Copy(value)
        if binding.type == 2 then
            binding.actionID = FindMacro(template.clickMacros[binding.actionID])
            if not binding.actionID then error("Click Casting macro is missing") end
        end
        table.insert(requested, binding)
        local key = BindingKey(binding)
        expected[key] = (expected[key] or 0) + 1
    end
    C_ClickBindings.SetProfileByInfo(requested)
    local actual = C_ClickBindings.GetProfileInfo()
    if type(actual) ~= "table" or #actual ~= #requested then error("Click Casting import was blocked") end
    for _, binding in ipairs(actual) do
        local key = BindingKey(binding)
        if not expected[key] or expected[key] == 0 then error("Click Casting verification failed") end
        expected[key] = expected[key] - 1
    end
end
local function Activate(template, who)
    local api = C_AddOns
    if not api then error("This client has no supported C_AddOns API") end
    local changed = false
    for name, enabled in pairs(template.flags) do
        if api.DoesAddOnExist and not api.DoesAddOnExist(name) then error("Missing addon: " .. name) end
        local state = api.GetAddOnEnableState(name, who.guid)
        if state == nil then error("Missing addon: " .. name) end
        if (state > 0) ~= enabled then
            if enabled then api.EnableAddOn(name, who.guid) else api.DisableAddOn(name, who.guid) end
            if (api.GetAddOnEnableState(name, who.guid) > 0) ~= enabled then error("Addon activation failed: " .. name) end
            changed = true
        end
    end
    if changed and api.SaveAddOns then api.SaveAddOns() end
    return changed
end
local function Apply(manual)
    local state, who = WoWUITransferAuto, WoWUITransferIdentity
    local function Skip(message)
        if manual then Say(message) end
    end
    if busy then Skip("Automatic setup is already running."); return end
    if state == nil then
        -- Report this once per session even without the slash command.
        if manual or not frame.missingTemplateReported then
            Say("No automatic setup template is configured for this account. Quit WoW and use tool menu 4.2.")
            frame.missingTemplateReported = true
        end
        return
    end
    if type(state) ~= "table" or state.schema ~= 1 then Skip("Unsupported automatic setup data. Update the helper and review tool menu 4.3."); return end
    if not state.enabled then Skip("Automatic setup is disabled. Quit WoW and configure it with tool menu 4.2."); return end
    if not who or not who.guid then Skip("Character identity is not available yet. Retry after login."); return end
    if type(state.characters) ~= "table" or type(state.excluded) ~= "table" then Skip("Automatic setup state is incomplete. Review tool menu 4.3."); return end
    if InCombatLockdown() then Skip("Leave combat before retrying /wuisetup."); return end
    if GetCursorInfo() then Skip("Clear the cursor before retrying /wuisetup."); return end
    if (InCinematic and InCinematic()) or (MovieFrame and MovieFrame.IsShown and MovieFrame:IsShown()) then return end
    local record = state.characters[who.guid]
    if record and record.done then
        if record.classSkipped then Skip("Older setup skipped bindings for this class. Use /wuisetup bindings to import them from the current template.")
        else Skip("Automatic setup is already complete for this character. Your changes are preserved.") end
        return
    end
    if not record then
        if state.excluded[who.guid] or (state.excludedNames and state.excludedNames[who.full]) then
            Skip("This character is excluded because it already existed when setup was configured. Use manual restore, or create a new character after configuring the template.")
            return
        end
        if type(state.template) ~= "table" then Skip("Automatic setup template is missing. Quit WoW and configure it with tool menu 4.2."); return end
        if UnitLevel("player") ~= 1 then
            state.excluded[who.guid] = true
            Say("Automatic setup skipped: this character is not level 1.")
            return
        end
        record = {template = Copy(state.template), phase = "activate", full = who.full, realm = who.realm}
        state.characters[who.guid] = record
    end
    busy = true
    local previousError = record.error
    record.error = nil
    local ok, message = pcall(function()
        local template = record.template
        if who.class ~= template.source.class and template.hasMacros and not record.macroPolicyApplied then
            if template.macroPolicy ~= 1 or not template.differentClass then
                error("This pending template has no cross-class macro variant. Quit WoW and reconfigure with tool menu 4.2 to upgrade it, then log in with this same character")
            end
            for _, key in ipairs({"macros", "slots", "clickMacros"}) do
                template[key] = Copy(template.differentClass[key])
            end
            record.macroPolicyApplied = true
        end
        if record.phase == "activate" then
            local changed = Activate(template, who)
            record.phase = "settings"
            if changed then Say("Addon activation saved; reloading for automatic setup."); ReloadUI(); return end
        end
        if record.phase == "settings" then
            if not record.editMode then
                WoWUITransferSelectEditMode(template.editModeLayout or "default")
                record.editMode = true
            end
            Profiles(template, who, record)
            record.phase = "bindings"
            Say("Addon settings applied; reloading once to initialize the layout.")
            ReloadUI()
            return
        end
        if template.chat and not record.chat then
            WoWUITransferChat.Apply(template.chat)
            record.chat = true
        end
        if template.hasMacros and not record.macros then Macros(template); record.macros = true end
        if template.hasClicks and not record.clicks then Clicks(template); record.clicks = true end
        if template.hasMacros and not record.slots then
            if not record.slotsQueued then
                if WoWUITransferBarsPending then error("Another macro placement is pending; finish it with /wuibars first") end
                WoWUITransferBarsPending = {schema = 1, slots = Copy(template.slots), autoSetup = true}
                record.slotsQueued = true
            end
            SlashCmdList.WOWUIBARS()
            if WoWUITransferBarsPending then error("Macro placement is pending; use /wuisetup after resolving the reported issue") end
            record.slots = true
        end
        record.classSkipped = nil
        record.done, record.templateID, record.template = true, template.id, nil
        record.error = nil
        Say("Automatic setup complete. Future logins will preserve your changes.")
        if record.skippedAddons and next(record.skippedAddons) then
            Say("Some leftover addon settings were skipped; see the messages above and tool menu 4.3.")
        end
        if template.chat then
            -- Persist completion before reloading: chat addons initialize their
            -- windows from the restored cache, and the next login is a no-op.
            Say("Reloading once to finish initializing the restored chat windows.")
            ReloadUI()
        end
    end)
    busy = false
    if not ok then
        record.error = tostring(message)
        if manual or record.error ~= previousError then
            Say("Automatic setup pending: " .. tostring(message) .. ". Automatic retries continue briefly; /wuisetup can retry later.")
        end
    end
end
SLASH_WOWUISETUP1 = "/wuisetup"
SlashCmdList.WOWUISETUP = function(command)
    if command and command:match("^%s*bindings%s*$") then
        local state, who = WoWUITransferAuto, WoWUITransferIdentity
        local record = state and who and state.characters and state.characters[who.guid]
        if not state or not state.enabled then Say("Automatic setup is not enabled. Configure it in tool menu 4.2."); return end
        if not record or not record.classSkipped then Say("No previously class-skipped bindings to restore on this character."); return end
        if InCombatLockdown() or GetCursorInfo() then Say("Leave combat and clear the cursor before retrying /wuisetup bindings."); return end
        if not record.done then Apply(true); return end
        if not state.template or not (state.template.hasMacros or state.template.hasClicks) then
            Say("The current template contains no macros or Click Casting. Update it in tool menu 4.2."); return
        end
        -- Explicitly resume only the skipped bindings from the current template.
        -- Do not replay profiles, chat geometry, or already completed bindings.
        record.template = Copy(state.template)
        record.template.chat = nil
        record.done, record.phase = false, "bindings"
    end
    Apply(true)
end
-- Identity, cursor state and other addons may not be ready on the first timer.
-- Retry for one minute after login/cinematic/combat, with one active timer chain.
local generation = 0
frame:SetScript("OnEvent", function()
    generation = generation + 1
    local current, attempts = generation, 0
    local function Resume()
        if current ~= generation then return end
        attempts = attempts + 1
        Apply()
        local state, who = WoWUITransferAuto, WoWUITransferIdentity
        if not state or not state.enabled then return end
        local record = who and state.characters and state.characters[who.guid]
        if record and record.done then return end
        if who and ((state.excluded and state.excluded[who.guid]) or (state.excludedNames and state.excludedNames[who.full])) and not record then return end
        if attempts < 12 then C_Timer.After(5, Resume)
        elseif record and not record.done then
            Say("Automatic setup is still pending after one minute: " .. (record.error or record.phase or "waiting for client readiness") .. ". Use /wuisetup to retry.")
        end
    end
    C_Timer.After(4, Resume)
end)
-- Install the handler before registering optional client-specific events.
-- An unsupported movie event must never disable all automatic continuation.
frame:RegisterEvent("PLAYER_ENTERING_WORLD")
frame:RegisterEvent("PLAYER_REGEN_ENABLED")
frame:RegisterEvent("CINEMATIC_STOP")
if not C_EventUtils or not C_EventUtils.IsEventValid or C_EventUtils.IsEventValid("STOP_MOVIE") then
    pcall(frame.RegisterEvent, frame, "STOP_MOVIE")
end
