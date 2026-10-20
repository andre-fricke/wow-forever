-- Synthetic WoW frames only. No addon or SavedVariables from a WoW install runs here.
local frames, combat = {}, false
UIParent = {}
DEFAULT_CHAT_FRAME = {AddMessage = function() end}
SlashCmdList = {}
function InCombatLockdown() return combat end
local methods = {}
function methods:SetAlpha(v) self.alpha = v end
function methods:GetAlpha() return self.alpha end
function methods:EnableMouse(v) self.mouse = v end
function methods:IsMouseEnabled() return self.mouse end
function methods:SetBackdrop(v) self.backdrop = v end
function methods:GetBackdrop() return self.backdrop end
function methods:SetBackdropColor(...) self.bg = {...} end
function methods:GetBackdropColor() return unpack(self.bg) end
function methods:SetBackdropBorderColor(...) self.border = {...} end
function methods:GetBackdropBorderColor() return unpack(self.border) end
function methods:GetChildren() return unpack(self.children) end
function methods:SetWidth(v) self.width = v end
function methods:GetWidth() return self.width end
function methods:SetScale(v) self.scale = v end
function methods:GetScale() return self.scale end
function methods:SetSize(w,h) self.width=w; self.height=h end
function methods:SetPoint(...)
    self.point={...}
    self.points = self.points or {}
    for i,p in ipairs(self.points) do if p[1] == self.point[1] then table.remove(self.points,i); break end end
    table.insert(self.points,self.point)
end
function methods:GetNumPoints() return #(self.points or {}) end
function methods:GetPoint(i) return unpack(self.points[i]) end
function methods:ClearAllPoints() self.points = {}; self.point = nil end
function methods:GetEffectiveScale() return self.scale * (self.parent and self.parent:GetEffectiveScale() or 1) end
function methods:GetRight()
    for _,p in ipairs(self.points or {}) do
        if p[1] == 'TOPRIGHT' then return p[2]:GetRight()*p[2]:GetEffectiveScale()/self:GetEffectiveScale() + p[4] end
    end
    return 800
end
function methods:GetTop()
    for _,p in ipairs(self.points or {}) do
        if p[1] == 'TOPRIGHT' then return p[2]:GetTop()*p[2]:GetEffectiveScale()/self:GetEffectiveScale() + p[5] end
    end
    return 600
end
function methods:GetBottom() return self:GetTop() - (self.height or 100) end
function methods:SetClampedToScreen(v) self.clamped = v end
function methods:IsClampedToScreen() return self.clamped ~= false end
function methods:SetFrameStrata() end
function methods:CreateFontString() return {SetAllPoints=function() end,SetText=function() end} end
function methods:SetScript(name, fn) self.scripts[name] = fn end
function methods:RegisterEvent(name) self.events[name] = true end
function methods:Hide() self.shown = false end
function methods:Show() self.shown = true end
function methods:SetShown(v) self.shown = not not v end
function methods:IsShown() return self.shown end
function methods:StartMoving() self.moving = true end
function methods:StopMovingOrSizing() self.moving = false end
function CreateFrame(_, name, parent)
    local f = setmetatable({alpha=1,mouse=true,bg={0.1,0.2,0.3,0.9},border={1,1,1,1},backdrop={},children={},width=220,scale=1,shown=true,scripts={},events={}}, {__index=methods})
    f.parent = parent
    table.insert(frames,f)
    if parent and parent.children then table.insert(parent.children,f) end
    if name then _G[name] = f end
    return f
end
function hooksecurefunc(object, key, hook)
    local original = object[key]
    object[key] = function(self, ...)
        original(self, ...)
        hook(self, ...)
    end
end
UIParent = CreateFrame('Frame')
UIParent:SetScale(0.8)
RXPFrame = CreateFrame('Frame','RXPFrame',UIParent)
RXPFrame:SetPoint('TOPRIGHT',UIParent,'TOPRIGHT',-100,-200)
local root = RXPFrame
root.GuideName = CreateFrame('Frame',nil,root)
root.Footer = CreateFrame('Frame',nil,root)
root.Footer.cog = CreateFrame('Button',nil,root)
root.BottomFrame = CreateFrame('Frame',nil,root)
local scrollButton = CreateFrame('Button',nil,root.BottomFrame)
root.CurrentStepFrame = CreateFrame('Frame',nil,root)
root.CurrentStepFrame.UpdateText = function() end
root.BottomFrame.UpdateFrame = function() end
root.SetStepFrameAnchor = function()
    root.CurrentStepFrame:ClearAllPoints()
    root.CurrentStepFrame:SetPoint('BOTTOMRIGHT',root,'TOPRIGHT',-3,2)
    root.CurrentStepFrame.anchor = 'TOP'
end
local step = CreateFrame('Frame',nil,root.CurrentStepFrame)
step.number = CreateFrame('Frame',nil,step)
step.elements = {{text='Keep |Tinline:16|t and |Hitem:1|h[link]|h', button=CreateFrame('Button',nil,step)}}
root.CurrentStepFrame.framePool = {step}
local savedPosition, openedMenu = 0, 0
root.OnMouseUp = function() savedPosition=savedPosition+1 end
root.DropDownMenu = function() openedMenu=openedMenu+1 end
assert(loadfile(arg[1]))('RestedXPTextOnly')
local driver
for _,f in ipairs(frames) do if f.events.PLAYER_LOGIN then driver=f end end
assert(driver)
driver.scripts.OnEvent(driver,'PLAYER_LOGIN')
local command = SlashCmdList.RESTEDXPTEXTONLY
assert(RestedXPTextOnlyDB.enabled == true)
local function corner()
    local f = root.CurrentStepFrame
    return f:GetRight()*f:GetEffectiveScale(), f:GetTop()*f:GetEffectiveScale()
end
local right, top = corner()
local function sameCorner()
    local r,t = corner()
    assert(math.abs(r-right)<0.00001 and math.abs(t-top)<0.00001, 'top-right corner moved')
    assert(root.CurrentStepFrame.anchor == 'BOTTOM')
end
for _,height in ipairs({100,300,900,40}) do
    root.CurrentStepFrame.height=height
    root.SetStepFrameAnchor()
    sameCorner()
    assert(root.CurrentStepFrame:GetBottom() == root.CurrentStepFrame:GetTop()-height)
end
combat=true;root.SetStepFrameAnchor();sameCorner();combat=false
assert(not root:IsClampedToScreen() and not step:IsClampedToScreen())
assert(step.bg[4] == 0 and step.border[4] == 0 and step.number.border[4] == 0)
assert(root.GuideName.alpha == 0 and root.Footer.alpha == 0 and root.Footer.cog.alpha == 0)
assert(scrollButton.mouse == false and root.mouse == false)
assert(step.alpha == 1 and step.elements[1].button.mouse == true)
assert(step.elements[1].text == 'Keep |Tinline:16|t and |Hitem:1|h[link]|h')
-- RestedXP redraws/theme changes must not bring decoration back.
step:SetBackdropColor(0.3,0.4,0.5,0.8)
root.GuideName:SetAlpha(0.75)
root.Footer.cog:EnableMouse(true)
assert(step.bg[4] == 0 and root.GuideName.alpha == 0 and not root.Footer.cog.mouse)
-- Lazily allocated step frames are discovered by the bounded scan.
local newStep = CreateFrame('Frame',nil,root.CurrentStepFrame)
root.CurrentStepFrame.framePool[2] = newStep
driver.scripts.OnUpdate(driver,0.3)
assert(newStep.bg[4] == 0)
command('off')
assert(step.bg[1] == 0.3 and step.bg[4] == 0.8 and newStep.bg[4] == 0.9)
assert(root.GuideName.alpha == 0.75 and root.Footer.cog.mouse == true and root.mouse == true)
assert(root:IsClampedToScreen() and step:IsClampedToScreen())
assert(root.point[4] == -100 and root.point[5] == -200)
command('on');command('unlock')
local handle = RestedXPTextOnlyHandle
assert(handle.shown)
handle.scripts.OnMouseDown(handle,'LeftButton');assert(root.moving)
root:ClearAllPoints();root:SetPoint('TOPRIGHT',UIParent,'TOPRIGHT',-200,-100)
handle.scripts.OnMouseUp(handle);assert(not root.moving and savedPosition==1)
assert(RestedXPTextOnlyDB.anchor.x == -200 and RestedXPTextOnlyDB.anchor.y == -100)
right,top=corner()
handle.scripts.OnMouseDown(handle,'RightButton');assert(not handle.shown)
command('width 300');sameCorner();command('scale 1.2');sameCorner()
assert(root.width == 300 and root.scale == 1.2)
assert(RestedXPTextOnlyDB.width == 300 and RestedXPTextOnlyDB.scale == 1.2)
command('menu');assert(openedMenu==1)
combat=true;command('off');assert(RestedXPTextOnlyDB.enabled)
combat=false;command('off');assert(root.width==220 and root.scale==1)
command('on');assert(root.width==300 and root.scale==1.2);sameCorner()
command('reset');assert(root.width==220 and root.scale==1)
assert(RestedXPTextOnlyDB.width==nil and RestedXPTextOnlyDB.scale==nil)
-- Simulate a fresh login with restored per-character settings.
command('off')
RestedXPTextOnlyDB = {enabled=true, width=320, scale=1.4, anchor={x=-210,y=-120}}
assert(loadfile(arg[1]))('RestedXPTextOnly')
for _,f in ipairs(frames) do if f.events.PLAYER_LOGIN then driver=f end end
driver.scripts.OnEvent(driver,'PLAYER_LOGIN')
local r,t=corner()
assert(math.abs(r-(UIParent:GetRight()-210)*UIParent:GetEffectiveScale())<0.00001)
assert(math.abs(t-(UIParent:GetTop()-120)*UIParent:GetEffectiveScale())<0.00001)
print('PASS fixed top-right anchor, downward growth, combat step changes, drag persistence, scale invariance, text-only skin, theme refresh, lazy steps, intact text/buttons, reversal, drag, scale, width and combat guard')
