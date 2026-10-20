# RestedXP Text Only

A small, reversible skin for the **classic/V1 RestedXP guide window**, tested against the locally installed RXP Beta v4.11.26 UI. It does not modify RestedXP's files or guide data.

It makes active-step backgrounds and borders transparent and hides the guide-name/logo panel, footer, cogwheel and separate step-list panel. Step text, the small step-number label, text colors, inline icons, links and clickable completion markers remain intact. Text Only starts enabled for each character.

## Installation

Copy this entire folder to the client's `Interface/AddOns/RestedXPTextOnly/` directory, alongside `RXPGuides`. Fully restart WoW after adding a new addon folder. Enable **RestedXP Text Only** in the character's **AddOns** list. RestedXP must also be enabled.

The TOC targets WoW Forever interface `16001`. A different game interface or a major RestedXP UI update needs a compatibility review. The experimental V2 guide window is not skinned by this version.

## Commands

| Command | Action |
| --- | --- |
| `/rxpt` | Toggle text-only and normal appearance |
| `/rxpt on` / `/rxpt off` | Enable / disable the skin |
| `/rxpt unlock` | Show a temporary drag handle above the text |
| `/rxpt lock` | Hide the handle; right-clicking it also locks |
| `/rxpt width 260` | Set window width (160–800) |
| `/rxpt scale 1.1` | Set window scale (0.5–2) |
| `/rxpt menu` | Open RestedXP's guide menu, including its options |
| `/rxpt reset` | Clear this addon's position/width/scale overrides and enable the skin |
| `/rxpt help` | Show available commands |

Commands that change the layout wait until you are out of combat. Move the text using the handle. Its upper-right corner stays fixed: longer steps grow downward and wider windows grow leftward. Position is stored in UIParent units so changing the addon scale keeps that corner in place. The initial corner is taken from the visible step window. RestedXP's native top/bottom option can automatically flip at screen edges; while enabled, this skin overrides that behavior. Long content can extend below the screen; move the handle upward or reduce the scale if needed. The handle is always locked again after login. Disabling the skin restores the appearance most recently requested by RestedXP, including theme changes made while the skin was active.

The implementation keeps layout frames present so RestedXP's anchoring logic continues to work. Hidden decoration has mouse input disabled, while active-step controls remain interactive. A throttled scan every 0.25 seconds catches lazily created step frames; it does not replace RestedXP functions or text.

## Reproducible backups

Settings are per character in `RestedXPTextOnlyDB`. The repository's addon-backup tool recognizes this addon and transfers its enabled state, width and scale settings. The fixed upper-right position is stored in the same per-character settings and transferred too. RestedXP's own position record is also updated after dragging.

After installation, log in with the template character, adjust the appearance, **quit WoW completely**, then create a **new addon backup**. The new archive includes this addon, its activation state and its settings. Older archives do not contain it and can disable it when restoring their addon activation list.

Copying this folder installs the code only; do not copy another player's personal SavedVariables manually. Use the backup tool for character-to-character transfer.

## Validation

The synthetic WoW-frame harness covers fixed upper-right anchoring, downward growth, scale invariance, combat step changes, position persistence, transparency, hidden decoration, retained text/buttons, theme redraws, lazy step creation, reversal, drag persistence calls, width/scale, reset and the combat guard. The backup tests cover support detection and character settings transfer. Run the full suite with Lua 5.1:

```sh
LUA_RUNTIME=/path/to/lua python3 -B tools/addon-backup/run_tests.py --require-lua
```

These tests do not replace an in-game visual check. Guide content and addon APIs are owned by RestedXP; major updates may need an adjustment to this skin.
