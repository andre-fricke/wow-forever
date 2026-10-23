-- Shared by automatic import and queued action-bar placement. Only known
-- addon-owned names with a loaded owner and a unique same-scope match qualify.
function WoWUITransferManagedMacro(entry)
    local owners = {Decursive = "Decursive", RS_MACRO = "RareScanner"}
    local owner = owners[entry.name]
    if not owner or not C_AddOns or not C_AddOns.IsAddOnLoaded(owner) then return nil end
    local limit = (Constants and Constants.MacroConsts and Constants.MacroConsts.MAX_ACCOUNT_MACROS) or MAX_ACCOUNT_MACROS or 120
    local accounts, characters = GetNumMacros()
    local first = entry.scope == "account" and 1 or limit + 1
    local count = entry.scope == "account" and accounts or characters
    local found
    for index = first, first + count - 1 do
        if GetMacroInfo(index) == entry.name then
            if found then error("Ambiguous addon-managed macro: " .. entry.name) end
            found = index
        end
    end
    return found
end
