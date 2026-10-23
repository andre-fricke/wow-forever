# Shared chat layout investigation — October 23, 2026

## Release test baseline

Runtime baseline: **953119c**, pushed to `main` before this investigation.
Keep this behavior for the first November 4 in-game test. This report and its
optional reproducer do not change the helper, installed addons or live settings.
The remaining first-login shared-layout issue is **not fixed** by that baseline.

The baseline uses `C_UI.Reload()` where available, leaves the Edit Mode-owned main
chat geometry alone, and still restores Combat Log/custom chat windows. The
existing `default` layout remains selected; no per-character layout copies were
introduced.

## What the local evidence establishes

1. The source's `AddOns.txt` disables **EllesmereUIChat** and enables **Prat-3.0**.
   The account still contains older EllesmereUIChat position/size values. Across
   recent addon snapshots those EUI values stay unchanged, while the helper's
   captured source geometry and the account Edit Mode cache change. Presence of
   an addon's saved data does not mean that addon is enabled on the source.
2. EUI's child `EllesmereUIChatDB` is an empty compatibility table. The actual
   values are at `EllesmereUIDB.profiles[activeProfile].addons.EllesmereUIChat.chat`.
   `EllesmereUI_Lite.lua:NewDB` exposes that shared table to the chat module.
   The inspected account has one EUI profile and no alternative chat profile in
   the recent source snapshots. Treating this as an ordinary AceDB per-character
   profile problem would be misleading.
3. In EllesmereUIChat 9.6.1, `EUI_Chat_Position.lua:EMChatSync` writes its saved
   `chatPosition` **and** `chatSize` into the active non-preset Edit Mode layout via
   `C_EditMode.SaveLayouts`. It does this when they differ from the layout, not
   only after an explicit drag. `ApplyChatPosition` queues this write after the
   anchor guard has been installed. `EUI_Chat_Init.lua` initializes that path on
   `LOADING_SCREEN_DISABLED`, and later layout updates can re-apply it.
4. Our helper's `Activate` runs after `PLAYER_ENTERING_WORLD` plus a four-second
   timer, and waits through a cinematic. It changes addon flags for the target
   GUID and requests a reload. It does **not** unload an already running addon or
   roll back changes that addon made to account-wide settings.
5. `configure_plan` preserves existing account-wide EUI data. That is intentional:
   configuring a new-character template must not reset other characters' EUI
   settings. It also means the stale data for a source-disabled module remains
   available if that module is initially enabled on a new character.
6. A Lua 5.1 reproduction executed the **actual installed EUI store function**
   against synthetic frames/layouts. It changed both main-chat coordinates and
   dimensions in a shared `default` layout. Executing the **actual helper
   activation function** afterwards disabled the module but left those layout
   changes intact. Other layouts were unchanged. No personal SavedVariables were
   executed and no WoW files were modified.

Inspected position-file SHA-256:
`350a7322343f46a7ef5d69d89ebe6c81ea20568cc16c7691a3ddb241988a9d27`.
The reproducer uses invented geometry, not an exported user profile.

## Strongest explanation, and its remaining uncertainty

On a new character, a module disabled on the source can initially be enabled and
load before the helper has applied the source flags. EllesmereUIChat can then
write its old shared geometry into the active custom layout. The later helper
reload removes the module but retains the changed account layout. Other
characters selecting that layout consequently see the changed size and position.

This explains the observed values and the persistent cross-character effect.
It also explains why skipping the helper's main-window geometry write is not a
complete solution. **The beta's precise first-login event ordering and initial
addon state were not recorded in game.** In particular, the active layout at the
moment of EUI's write must still be checked. The reproduction establishes the
mechanism, not that missing event trace. A UI reload by itself is not evidence
that account data has been restored.

The earlier claim that the helper's own geometry call was the complete cause was
too strong. Likewise, cloning `default` per character would isolate later writes
only after the clone becomes active; it would not prevent an earlier write to the
shared layout and is not the first fix to make.

## Focused November 4 test

1. Update the helper with menu **4.1** while WoW is closed. Existing backups and
   the current template remain usable. Before testing a fresh release account,
   ensure the intended `default` Edit Mode layout exists: automatic setup selects
   it, but does not import the complete layout. Manual addon restore **2.1** can
   restore account Edit Mode cache data and therefore affects the whole account;
   do not use it casually on an account with newer layouts.
2. On an existing configured character, establish the desired main-chat position
   and size and record them (or take a screenshot). Quit WoW. Preserve an addon
   backup of this baseline; a failed test may change a shared layout.
3. Create a test character, but **before its first world login**, open **AddOns**
   from character selection, select that character in the dropdown and check
   whether **EllesmereUIChat** is enabled. Record its original state, then disable
   it for that character. Keep the helper and the intended chat addon enabled.
4. Enter the world and skip the cinematic normally. Allow setup to finish without
   `/wuisetup` or `/reload`. Check General, Combat Log and the custom window, then
   check the same shared layout on the original character. Record whether all
   automatic reloads occurred and whether the completion message appeared.
5. If that avoids the drift, the unwanted initial load is strongly corroborated.
   An optional comparison with another fresh character using the original addon
   state is useful only after preserving the layout baseline; it can reproduce
   the shared mutation. If the drift occurs even with EUI Chat disabled before
   first login, investigate Prat/docking and the release client's Edit Mode
   synchronization before changing the profile architecture.

For useful follow-up evidence, include the initially selected AddOns state, the
active Edit Mode layout, helper chat messages/reload count and before/after main
chat dimensions. A completed character's final `AddOns.txt` alone cannot prove
which addons ran during its first login.

## Candidate remedies after that test

- Prefer preventing source-disabled addons from running **before first login**.
  A later timer or another reload cannot undo their previous writes. The manual
  per-character AddOns selection above is a narrow test/workaround, not the final
  promised automatic workflow.
- An offline option to change addon defaults before character creation needs an
  explicit scope and recovery design. Altering TOC defaults, global enable states
  or load managers affects installation behavior, other accounts or addon updates;
  it should not be silently added as a one-off EUI patch.
- Do not blindly copy stale EUI geometry from a disabled source module, erase its
  saved data, reset the account-wide EUI profile, or restore an old Edit Mode
  snapshot on every new-character login.
- Keep `default` shared until evidence justifies a different model. A private
  layout is an optional product decision, not a proven timing fix.

## Repeat the isolated mechanism check

From this repository, with Lua 5.1 installed:

```sh
lua tools/addon-backup/diagnostics/reproduce_chat_store.lua \
  '/path/to/Interface/AddOns/EllesmereUIChat/EUI_Chat_Position.lua' \
  tools/addon-backup/autosetup.lua
```

This opt-in diagnostic reads **addon source code**, never SavedVariables. The
selected functions execute in restricted environments with synthetic UI/API
stubs. It does not connect to WoW or change configuration. It targets the inspected
EUI function structure; an addon update may require adapting the diagnostic.
