-- Capture persistent chat windows, including the built-in Combat Log (ID 2).
-- Coordinates use UIParent fractions, independent of frame/UI scale.
WoWUITransferChat = {}
local function ChatMethod(frame, globalName, method)
    if type(_G[globalName]) == "function" then
        return function(...) return _G[globalName](frame, ...) end
    end
    if frame and type(frame[method]) == "function" then
        return function(...) return frame[method](frame, ...) end
    end
    error("Custom chat window API unavailable: " .. globalName .. " / " .. method)
end
local function Geometry(frame)
    local ratio = frame:GetEffectiveScale() / UIParent:GetEffectiveScale()
    return frame:GetLeft() * ratio / UIParent:GetWidth(),
        frame:GetBottom() * ratio / UIParent:GetHeight(),
        frame:GetWidth() * ratio / UIParent:GetWidth(),
        frame:GetHeight() * ratio / UIParent:GetHeight()
end
function WoWUITransferChat.Capture()
    if not GetChatWindowInfo or not UIParent then return nil end
    local result = {}
    for id = 1, NUM_CHAT_WINDOWS or 10 do
        local frame = _G["ChatFrame" .. id]
        local name, _, _, _, _, alpha, shown, locked, docked = GetChatWindowInfo(id)
        if frame and not frame.isTemporary and ((shown and shown ~= 0) or (docked and docked ~= 0)) and frame:GetLeft() and frame:GetBottom() then
            local x, y, width, height = Geometry(frame)
            result[id] = {name = name, x = x, y = y, width = width, height = height,
                alpha = alpha,
                dock = type(docked) == "number" and docked or (docked and id or 0), locked = not not (locked and locked ~= 0)}
            if id > 2 and GetChatWindowMessages and GetChatWindowChannels then
                local channels, names = {GetChatWindowChannels(id)}, {}
                for i = 1, #channels, 2 do names[#names + 1] = channels[i] end
                result[id].subscriptions = {messages = {GetChatWindowMessages(id)}, channels = names}
            end
        end
    end
    return next(result) and result or nil
end
function WoWUITransferChat.Apply(layout)
    if InCombatLockdown() then error("Leave combat before restoring chat positions") end
    if not FCF_SavePositionAndDimensions or not FCF_DockFrame or not FCF_UnDockFrame then
        error("Chat layout API unavailable")
    end
    local order, frames = {}, {}
    for id, entry in pairs(layout) do
        local frame = _G["ChatFrame" .. id]
        local name = GetChatWindowInfo(id)
        if id > 2 and entry.subscriptions then
            -- Match by name, since the next free window ID can differ on a new character.
            frame = nil
            for candidate = 3, NUM_CHAT_WINDOWS or 10 do
                local existing = _G["ChatFrame" .. candidate]
                local existingName, _, _, _, _, _, shown, _, docked = GetChatWindowInfo(candidate)
                if existing and not existing.isTemporary and existingName == entry.name
                    and ((shown and shown ~= 0) or (docked and docked ~= 0)) then
                    if frame then error("Ambiguous custom chat window: " .. entry.name) end
                    frame = existing
                end
            end
            if not frame then
                if not FCF_OpenNewWindow then error("Custom chat window API unavailable: FCF_OpenNewWindow") end
                frame = FCF_OpenNewWindow(entry.name)
            end
            if not frame then error("No free chat window for: " .. entry.name) end
            name = entry.name
        end
        if id > 2 and (not frame or frame.isTemporary or name ~= entry.name) then
            DEFAULT_CHAT_FRAME:AddMessage("WoW UI Transfer: Skipped chat position for missing or renamed custom window: " .. id .. " (" .. entry.name .. ").")
        elseif not frame then
            error("Built-in chat window missing: " .. id)
        else
            table.insert(order, id)
            frames[id] = frame
        end
    end
    table.sort(order, function(a,b)
        local da, db = layout[a].dock, layout[b].dock
        if da == db then return a < b end
        return da < db
    end)
    for _, id in ipairs(order) do
        local entry, frame = layout[id], frames[id]
        if entry.alpha ~= nil and not FCF_SetWindowAlpha then error("Chat opacity API unavailable: FCF_SetWindowAlpha") end
        if id > 2 and entry.subscriptions then
            -- Newer clients move channel APIs from globals onto ChatFrameMixin.
            -- Resolve every operation before clearing any subscriptions.
            local clearGroups = ChatMethod(frame, "ChatFrame_RemoveAllMessageGroups", "RemoveAllMessageGroups")
            local addGroup = ChatMethod(frame, "ChatFrame_AddMessageGroup", "AddMessageGroup")
            local clearChannels = ChatMethod(frame, "ChatFrame_RemoveAllChannels", "RemoveAllChannels")
            local addChannel = ChatMethod(frame, "ChatFrame_AddChannel", "AddChannel")
            clearGroups()
            for _, group in ipairs(entry.subscriptions.messages) do addGroup(group) end
            clearChannels()
            for _, channel in ipairs(entry.subscriptions.channels) do addChannel(channel) end
        end
        if id ~= 1 then
            if entry.dock > 0 then FCF_DockFrame(frame, entry.dock, false)
            else FCF_UnDockFrame(frame) end
        end
        -- The main window belongs to the active shared Edit Mode layout.
        -- Moving/saving it can be mirrored into that layout by chat addons,
        -- changing the position for other characters using the same layout.
        local editModeOwned = id == 1 and C_EditMode and C_EditMode.GetLayouts
        if not editModeOwned and (id == 1 or entry.dock == 0) then
            local ratio = UIParent:GetEffectiveScale() / frame:GetEffectiveScale()
            frame:ClearAllPoints()
            frame:SetSize(entry.width * UIParent:GetWidth() * ratio, entry.height * UIParent:GetHeight() * ratio)
            frame:SetPoint("BOTTOMLEFT", UIParent, "BOTTOMLEFT", entry.x * UIParent:GetWidth() * ratio, entry.y * UIParent:GetHeight() * ratio)
            frame:Show()
            if frame.SetUserPlaced then frame:SetUserPlaced(true) end
            FCF_SavePositionAndDimensions(frame)
            local x, y, width, height = Geometry(frame)
            if math.abs(x-entry.x) > 0.005 or math.abs(y-entry.y) > 0.005
                or math.abs(width-entry.width) > 0.005 or math.abs(height-entry.height) > 0.005 then
                error("Chat position was constrained or overridden: " .. id)
            end
        end
        if FCF_SetLocked then FCF_SetLocked(frame, entry.locked) end
        if entry.alpha ~= nil then FCF_SetWindowAlpha(frame, entry.alpha) end
    end
end
SLASH_WOWUICHAT1 = "/wuichat"
SlashCmdList.WOWUICHAT = function()
    local template = WoWUITransferAuto and WoWUITransferAuto.template
    local ok, message = pcall(function()
        if not template or not template.chat then error("No chat layout captured. Update the helper, capture a new addon backup and select it in tool menu 4.2") end
        WoWUITransferChat.Apply(template.chat)
    end)
    DEFAULT_CHAT_FRAME:AddMessage("WoW UI Transfer: " .. (ok and "Chat positions restored from the current template." or tostring(message)))
end
