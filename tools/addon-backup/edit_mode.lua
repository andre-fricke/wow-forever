-- Select an existing named custom layout; never rewrite shared layout contents.
function WoWUITransferSelectEditMode(name)
    if InCombatLockdown() then error("Leave combat before selecting an Edit Mode layout") end
    if not C_EditMode or not C_EditMode.GetLayouts or not C_EditMode.SetActiveLayout then
        error("Edit Mode API unavailable")
    end
    local manager = EditModePresetLayoutManager
    local presets = manager and manager.GetCopyOfPresetLayouts and manager:GetCopyOfPresetLayouts()
    local info = C_EditMode.GetLayouts()
    if type(presets) ~= "table" or #presets == 0 or type(info) ~= "table" or type(info.layouts) ~= "table" then
        error("Edit Mode layouts are not ready; retry /wuisetup after login")
    end
    local selected
    for index, layout in ipairs(info.layouts) do
        if layout.layoutName == name then
            if selected then error("More than one Edit Mode layout is named " .. name) end
            -- API active indices include the presets, GetLayouts omits them.
            selected = #presets + index
        end
    end
    if not selected then error("Edit Mode layout '" .. name .. "' is missing. Create or import it in ESC > Edit Mode, then retry") end
    if info.activeLayout ~= selected then C_EditMode.SetActiveLayout(selected) end
    if C_EditMode.GetLayouts().activeLayout ~= selected then error("Edit Mode layout selection was blocked; retry outside combat") end
end
SLASH_WOWUIEDITMODE1 = "/wuieditmode"
SlashCmdList.WOWUIEDITMODE = function()
    local ok, message = pcall(WoWUITransferSelectEditMode, "default")
    DEFAULT_CHAT_FRAME:AddMessage("WoW UI Transfer: " .. (ok and "Edit Mode layout 'default' selected." or tostring(message)))
end
