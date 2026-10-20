-- A reversible skin for RestedXP's classic (V1) guide window.
-- Never changes guide content, targeting, themes or the original addon files.
local name = ...
local driver = CreateFrame("Frame")
local root, db, handle
local active, changing, dragging = false, false, false
local saved = {}
local elapsed = 0
local baseWidth, baseScale, basePoints

local function Say(text)
    DEFAULT_CHAT_FRAME:AddMessage("|cff80dfffRestedXP Text Only:|r " .. text)
end

local function OwnChange(fn)
    local previous = changing
    changing = true
    fn()
    changing = previous
end

-- Remember the most recent value requested by RestedXP, including theme changes.
-- Our own transparent overrides never replace the saved original values.
local function Override(object, setter, getter, value)
    if not object or not object[setter] or not object[getter] then return end
    local entry = saved[object]
    if not entry then entry = {}; saved[object] = entry end
    local state = entry[setter]
    if not state then
        state = {original = {object[getter](object)}, value = value}
        entry[setter] = state
        hooksecurefunc(object, setter, function(self, ...)
            if changing then return end
            state.original = {...}
            if active and not InCombatLockdown() then
                OwnChange(function() self[setter](self, unpack(state.value)) end)
            end
        end)
    else
        state.value = value
    end
    if active then
        OwnChange(function() object[setter](object, unpack(value)) end)
    end
end

local function NoMouse(frame)
    Override(frame, "EnableMouse", "IsMouseEnabled", {false})
    if frame and frame.GetChildren then
        for _, child in ipairs({frame:GetChildren()}) do NoMouse(child) end
    end
end

local function Chrome(frame)
    if not frame then return end
    Override(frame, "SetAlpha", "GetAlpha", {0})
    NoMouse(frame)
end

local function Transparent(frame)
    if not frame or not frame.GetBackdrop or not frame:GetBackdrop() then return end
    Override(frame, "SetBackdropColor", "GetBackdropColor", {0, 0, 0, 0})
    Override(frame, "SetBackdropBorderColor", "GetBackdropBorderColor", {0, 0, 0, 0})
end

-- Store offsets in UIParent units, independent of the addon's own scale.
local function CaptureAnchor(frame)
    local right, top = frame:GetRight(), frame:GetTop()
    if not right or not top then return nil end
    local ratio = frame:GetEffectiveScale() / UIParent:GetEffectiveScale()
    return {x = right * ratio - UIParent:GetRight(), y = top * ratio - UIParent:GetTop()}
end

local function AnchorText()
    if not active or not db.anchor then return end
    if not dragging then
        local ratio = UIParent:GetEffectiveScale() / root:GetEffectiveScale()
        root:ClearAllPoints()
        root:SetPoint("TOPRIGHT", UIParent, "TOPRIGHT", db.anchor.x * ratio, db.anchor.y * ratio)
    end
    local frame = root.CurrentStepFrame
    frame:ClearAllPoints()
    frame:SetPoint("TOPLEFT", root, "TOPLEFT", 0, 0)
    frame:SetPoint("TOPRIGHT", root, "TOPRIGHT", 0, 0)
    frame.anchor = "BOTTOM" -- RestedXP's name for downward-growing steps.
end

local function RefreshLayout()
    if root.BottomFrame and root.BottomFrame.UpdateFrame then root.BottomFrame.UpdateFrame() end
    if root.CurrentStepFrame.UpdateText then root.CurrentStepFrame.UpdateText() end
    if root.SetStepFrameAnchor then root.SetStepFrameAnchor() end
end

local function Restore()
    active = false
    OwnChange(function()
        for object, entry in pairs(saved) do
            for setter, state in pairs(entry) do object[setter](object, unpack(state.original)) end
        end
    end)
    if handle then handle:Hide() end
    if root and baseWidth then
        root:SetWidth(baseWidth)
        root:SetScale(baseScale)
        root:ClearAllPoints()
        for _, point in ipairs(basePoints) do root:SetPoint(unpack(point)) end
        baseWidth, baseScale, basePoints = nil, nil, nil
        RefreshLayout()
    end
end

local function Apply()
    if not root or not db or InCombatLockdown() then return end
    if not db.enabled then
        if active then Restore() end
        return
    end
    if not active then
        db.anchor = db.anchor or CaptureAnchor(root.CurrentStepFrame) or CaptureAnchor(root)
        if not db.anchor then return end -- Wait until the first layout has coordinates.
        baseWidth, baseScale = root:GetWidth(), root:GetScale()
        basePoints = {}
        for i = 1, root:GetNumPoints() do basePoints[i] = {root:GetPoint(i)} end
        active = true
        if db.width then root:SetWidth(db.width) end
        if db.scale then root:SetScale(db.scale) end
        RefreshLayout()
    end
    -- Alpha instead of Hide: RestedXP uses IsShown to decide its window layout.
    Chrome(root.GuideName)
    Chrome(root.Footer)
    if root.Footer then Chrome(root.Footer.cog) end -- Parent is RXPFrame, not Footer.
    Chrome(root.BottomFrame)
    Override(root, "EnableMouse", "IsMouseEnabled", {false})
    Override(root, "SetClampedToScreen", "IsClampedToScreen", {false})
    AnchorText()
    Transparent(root)
    for _, step in pairs(root.CurrentStepFrame.framePool or {}) do
        Override(step, "SetClampedToScreen", "IsClampedToScreen", {false})
        Transparent(step)
        Transparent(step.number) -- Keep the small "Step 30" text, remove its box.
    end
    if handle then handle:SetShown(db.unlocked and root.CurrentStepFrame:IsShown()) end
end

local function StopDragging()
    if not dragging then return end
    dragging = false
    root:StopMovingOrSizing()
    db.anchor = CaptureAnchor(root) or db.anchor
    AnchorText()
    -- Keep RestedXP's own position record in sync as well.
    if root.OnMouseUp then root.OnMouseUp(root, "LeftButton") end
end

local function CreateHandle()
    handle = CreateFrame("Button", "RestedXPTextOnlyHandle", root, "BackdropTemplate")
    handle:SetSize(200, 20)
    handle:SetPoint("BOTTOMRIGHT", root.CurrentStepFrame, "TOPRIGHT", 0, 6)
    handle:SetFrameStrata("DIALOG")
    handle:SetBackdrop({bgFile = "Interface/Buttons/WHITE8X8"})
    handle:SetBackdropColor(0.04, 0.14, 0.2, 0.9)
    local text = handle:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    text:SetAllPoints()
    text:SetText("Drag to move | Right-click: lock")
    handle:EnableMouse(true)
    handle:SetScript("OnMouseDown", function(_, button)
        if InCombatLockdown() then return end
        if button == "RightButton" then
            StopDragging(); db.unlocked = false; handle:Hide()
        elseif button == "LeftButton" then
            dragging = true; root:StartMoving()
        end
    end)
    handle:SetScript("OnMouseUp", StopDragging)
    handle:Hide()
end

local function Initialize()
    if root then return true end
    local candidate = _G.RXPFrame
    if not candidate or not candidate.CurrentStepFrame or not candidate.GuideName or not candidate.Footer then return false end
    root = candidate
    RestedXPTextOnlyDB = type(RestedXPTextOnlyDB) == "table" and RestedXPTextOnlyDB or {}
    db = RestedXPTextOnlyDB
    if type(db.enabled) ~= "boolean" then db.enabled = true end
    db.unlocked = false -- Never leave an editing handle visible after login.
    if type(db.width) ~= "number" or db.width < 160 or db.width > 800 then db.width = nil end
    if type(db.scale) ~= "number" or db.scale < 0.5 or db.scale > 2 then db.scale = nil end
    local function Finite(value)
        return type(value) == "number" and value == value and math.abs(value) < math.huge
    end
    if type(db.anchor) ~= "table" or not Finite(db.anchor.x) or not Finite(db.anchor.y) then db.anchor = nil end
    -- Post-hook also prevents RestedXP's screen-edge auto-flip during step updates.
    -- These are ordinary, unprotected guide frames; the anchor remains stable in combat.
    if root.SetStepFrameAnchor then hooksecurefunc(root, "SetStepFrameAnchor", AnchorText) end
    CreateHandle()
    -- Some step frames are created lazily, after login. A bounded scan catches
    -- new frames without replacing RestedXP's functions or per-frame scripts.
    driver:SetScript("OnUpdate", function(_, seconds)
        elapsed = elapsed + seconds
        if elapsed < 0.25 then return end
        elapsed = 0
        if root:IsShown() then Apply() end
    end)
    Apply()
    return true
end

SLASH_RESTEDXPTEXTONLY1 = "/rxpt"
SlashCmdList.RESTEDXPTEXTONLY = function(message)
    if not Initialize() then Say("Classic RestedXP guide window not found."); return end
    local command, argument = string.match(string.lower(message or ""), "^%s*(%S*)%s*(.-)%s*$")
    if command == "help" then
        Say("/rxpt [on|off] | unlock | lock | width 160-800 | scale 0.5-2 | menu | reset")
        Say("Classic/V1 window only. Inline icons and step controls are retained.")
        return
    end
    if InCombatLockdown() then Say("Wait until combat ends before changing the layout."); return end
    StopDragging()
    if command == "menu" then
        if root.DropDownMenu then root.DropDownMenu() end
        return
    elseif command == "" then db.enabled = not db.enabled
    elseif command == "on" then db.enabled = true
    elseif command == "off" then db.enabled = false
    elseif command == "unlock" then db.enabled = true; db.unlocked = true
    elseif command == "lock" then db.unlocked = false
    elseif command == "width" or command == "scale" then
        local number = tonumber(argument)
        local low, high = command == "width" and 160 or 0.5, command == "width" and 800 or 2
        if not number or number < low or number > high then Say(command .. " must be between " .. low .. " and " .. high); return end
        db[command] = number
        db.enabled = true
        Apply()
        if command == "width" then root:SetWidth(number) else root:SetScale(number) end
        RefreshLayout()
    elseif command == "reset" then
        Restore(); db.width = nil; db.scale = nil; db.anchor = nil; db.enabled = true; db.unlocked = false
    else Say("Unknown command. Use /rxpt help."); return end
    Apply()
    Say(db.enabled and "Text only enabled." or "Normal RestedXP appearance restored.")
end

driver:RegisterEvent("PLAYER_LOGIN")
driver:RegisterEvent("PLAYER_REGEN_ENABLED")
driver:RegisterEvent("PLAYER_REGEN_DISABLED")
driver:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_REGEN_DISABLED" then
        StopDragging()
        if handle then handle:Hide() end
        return
    end
    Initialize()
    Apply()
end)
