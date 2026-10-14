local frame = CreateFrame("Frame")
local function Capture()
    local raw = UnitNameUnmodified or UnitName
    local first, second = raw("player")
    local regional = RegionalUniqueNamesEnabled and RegionalUniqueNamesEnabled() or false
    local full = first
    if regional and second and second ~= "" then full = first .. " " .. second end
    local _, class = UnitClass("player")
    local _, race = UnitRace("player")
    local version, build, _, interface = GetBuildInfo()
    local realm = GetRealmName()
    if not first or not realm or not UnitGUID("player") then return end
    local realmKey = realm
    if regional and C_GameRules and Enum and Enum.GameRule then
        local function Rule(key)
            local id = Enum.GameRule[key]
            return id and C_GameRules.IsGameRuleActive(id)
        end
        realmKey = Rule("HardcoreRuleset") and "Hardcore" or Rule("RPRuleset") and "RP" or Rule("PvPRuleset") and "PvP" or "PvE"
    end
    WoWUITransferIdentity = {
        schema = 1, name = first, full = full, realm = realm, realmKey = realmKey,
        guid = UnitGUID("player"), class = class, race = race,
        faction = UnitFactionGroup("player"), regional = regional,
        version = version, build = build, interface = interface, savedAt = time(),
    }
end
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_LOGOUT")
frame:SetScript("OnEvent", Capture)
