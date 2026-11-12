# YT2VM©: YouTube to VM (vibecoded sorry its cuz of school slowing me down with updates)

A lightweight Python project that connects YouTube-related workflows to a virtual machine setup. It is designed to help automate VM-based tasks, stream management, and control flows in a simple and open-source way.

# What does it do?

YT2VM is a project that brings together several tools to make a VM-centered YouTube workflow easier to manage. It can be used to:

- Start and control virtual machines using VirtualBox
- Connect with OBS for stream or scene automation
- Interface with chat-driven tools using `pytchat`
- Run a lightweight web-based control layer with Flask
- Support cross-platform usage across Windows, macOS, and Linux

In short, this project is meant to help automate the parts of a YouTube or streaming workflow that are usually managed through a VM environment, making setup and control more convenient.

# Installation and Dependencies

For working with this script, you need to install several Python packages. This can be done with the following command in your terminal:

```bash
pip install PyQt6 virtualbox Flask pytchat obsws-python pywin32
```

Attention: `pywin32` works on Windows only and should be installed if you use the script on Windows.

The window is built with PyQt6. YT2VM installs any missing required package by itself on start, so updating from an older version pulls in PyQt6 automatically. On Linux, Qt may also need `libxcb-cursor0` from your package manager.

# Features

- Cross-Platform: Supports Windows, macOS, and Linux.
- Open-Source: Full source code is open to everyone.
- VM Integration: Designed to work with VirtualBox-powered environments.
- OBS Support: Can integrate with OBS WebSocket for automation.
- Flask-Based Control: Includes a lightweight Python web interface.
- Plugins: Add your own chat commands, chat reactions, timers and GUI panels without touching `yt2vm.py`.
- Plugin Market: Browse, install and publish reviewed plugins straight from the app (Tools → Plugin Market).
- ChangeVM control: whitelist which VMs `!changevm` can switch to, and pick the snapshot each whitelisted VM reverts to (ChangeVM tab).
- AI player: a local vision AI (Ollama, LM Studio and more) can play the VM with chat commands and learn from chat (AI page).
- Commands Power: set advanced commands (`!revert`, `!startvm`, `!shutdown`, `!switchsnapshot`, `!makesnapshot`, `!changevm`, `!restartvm`, `!remake2`, `!fixvm`, `!forcefixvm`, `!snapshotnow`, `!revertnow`, `!restartnow` and more) to Everyone / Admins only / Disabled, with an optional per-user countdown (Command Power tab).

# Release Notes — 1.8.0

## AI page
- A vision AI can now play the VM. Open the new **AI** page, turn on *Let the AI control the VM*, pick a model and press Start.
- YT2VM finds Ollama, LM Studio, Jan, KoboldCpp, llama.cpp / LocalAI and vLLM on your PC by itself. Any OpenAI-compatible service works through *Custom*. Only models that can read images are listed (for Ollama, for example `ollama pull qwen2.5vl`).
- Every step the AI gets a screenshot of the VM, answers with commands, YT2VM runs them as the user `[ai]` through the normal command queue, waits until they finished, and sends the next screenshot. It keeps going 24/7 if you want, and picks new goals by itself after finishing a task.
- Thinking levels Off / Low / Medium / High, plus creativity, reply length, commands per step, speed, task time and step limits, screenshot and context size.
- Live view of what the AI sees, thinks, plans and runs, with stats and an activity log.
- Per-VM profiles with their own task, model and extra instructions.

## Learning
- The AI learns from its own commands and screenshots, from what viewers run, from `!teach`, and from everything said in YouTube chat and Discord. Everything is stored in `ai_learnings.db`.
- It looks things up with its `Read_Learnings` tool and sees related lessons every step. You can search, add and delete learnings on the AI page.
- `ai_logs.jsonl` logs every step with `timestamp`, `ai_thinking`, `ai_commands`, what ran, the result and the screenshot, plus learning events, errors and finished tasks. Export logs and learnings as a zip from the AI page.

## Chat commands
- `!ai <message>` talks to the AI while it plays. `!teach <text>` teaches it something (everyone, mods only or off).
- Mods: `!aitask <task>`, `!aistart`, `!aistop`.

## Safety
- The AI only uses viewer commands. `!revert`, `!restartvm` and `!fixvm` need an extra switch, and a block list keeps any command away from it.
- It goes through the same command filter and Protect VM rules as viewers, has its own commands-per-minute limit, can wait while viewers play, and pauses itself after repeated errors.

# Release Notes — 1.7.0

Stability release: a full bug hunt through the script.

## Security
- YouTube display names aren't unique, so anyone could name their channel ReallyIron, System or ReallyBotYT and get owner rights, or start their name with `[` (like `[console]`) and act as the console. Owner and mod rights on YouTube now only come from YouTube's own owner and moderator flags.

## Settings
- A damaged `settings.json` no longer resets everything: YT2VM loads `settings.json.bak` (kept automatically), keeps the damaged file next to it, and tells you.
- Hand-edited values with the wrong type are repaired instead of crashing YT2VM on start.
- An empty or spaced command prefix and negative typing/key/mouse delays are refused.
- Settings, logs and data always live next to `yt2vm.py`, whichever folder YT2VM was started from.

## Stability
- Automatic updates roll back by themselves when the new version fails to start twice, and skip that version until a newer one is out.
- No more frozen window while VirtualBox is slow: listing VMs, snapshots and diagnostics run in the background. Start-up no longer lists VMs when one is already saved.
- Connecting before the stream is live keeps retrying every 15 seconds.
- The overlay server only closes an old YT2VM that holds port 5000, never another program.
- Fixed a race in the music queue, the "(no VMs ...)" text being saved as the VM name, and Save snapshot list failing on unusual VM names.

# Release Notes — 1.6.0

## Closing
- Clicking X on the window or on the black console window closes YT2VM right away. The window disappears at once, settings and stats are saved, and the app exits within a few seconds even if Discord, a plugin or VirtualBox is stuck. No more "Not Responding".

## Updates page
- **Main → Updates**: check now, What's new, restore the previous version, and pick when to check: only when it starts, every minute, every 5 minutes, every hour (default) or every day.
- Choose Update automatically, Ask me first or Don't check. The page shows the last and next check.
- Checks only download `yt2vm.py` again when GitHub says it changed, so checking every minute stays light. Only the start-up check shows the "Checked for updates" message; later checks run quietly and update when there's something new.

# Release Notes — 1.5.0

## Staff skip every vote
- Admins, mods and the owner never have to vote. Their `!revert`, `!restartvm`, `!forcefixvm`, music commands (`!skipsong`, `!pausesong` ...) and OS commands run right away, even while votes are paused, on cooldown or OS voting is off. A vote viewers already started for the same thing is closed.
- `!win7` / `!winxp` style OS commands from staff switch the OS at once.
- Admins on the YT2VM admin list count as staff for every vote, not just YouTube mods and the owner.

# Release Notes — 1.4.0

## Automatic updates
- YT2VM follows `yt2vm.py` on the main branch of this repo. Every time it starts (and every 6 hours) it downloads that file and compares its hash with the one you're running.
- When it changed and the version is the same or higher, YT2VM updates by itself: an **Updating To Version x.y** screen with a progress bar, then it restarts. The old file is kept as `yt2vm.py.bak-<version>`, and the new file must compile and be YT2VM before anything is replaced.
- A lower version on GitHub is never installed over a newer copy, and Windows line endings don't count as a change.
- After the check you get *Checked for updates: you are up to date!* (or what it found) at the top.
- Machine → System → Updates: Update automatically (default), Ask me first, or Don't check, plus Check now and Restore previous version.

## What's new
- Help → **What's new** lists every version's added, changed, fixed and removed items.

## OS voting by name
- OS Voting → **How chat votes**: *Command + name* (`!os win7`), *Name as command* (`!win7`, `!winxp`, `!win10`), or both.
- Short names default to `win7` / `winxp` / `win10` when the VM name starts with Windows. Names that clash with a built-in command (like `!w` or `!c`) can't be used.

**Updating from 1.3.0 or older:** download `yt2vm.py` once by hand. From 1.4.0 on, YT2VM updates itself from the main branch.

# Release Notes — 1.3.0

## New window
- The whole app now runs on PyQt6 instead of Tkinter: smoother animations, crisp text on high-DPI screens, and a faster, steadier UI under a busy chat.
- New app logo and icon. It is built into `yt2vm.py`, shows in the title bar and taskbar, is written next to the script as `yt2vm.ico` (handy for PyInstaller), and is the overlay server's favicon.
- Every page was rebuilt with cards, live sparklines, animated toggles and a theme crossfade. All themes, accents, text sizes and motion levels carry over.
- Ctrl+K opens the command palette, Ctrl+Tab steps through pages, Ctrl+L jumps to the console, Ctrl+J shows or hides the live chat.

## Plugins
- Plugin API 3: panels and tabs get a `ui` object with simple helpers (`ui.label`, `ui.button`, `ui.input`, `ui.toggle`, `ui.select`, `ui.row`, `ui.card` ...) and `api.qt` for raw PyQt6. Plugins whose panels use Tkinter keep their commands and timers, and their panel shows a note asking for an update.

## Discord
- The command channel and log channel can now be a voice channel's chat (`VC:`) or a stage channel's chat (`Stage:`), not just text channels. The bot reads and posts in that chat without joining the call. Pick it from the same dropdown on the Discord page; the bot needs View Channel, Send Messages and Read Message History there.

## OS voting
- Chat now votes for a specific OS: `!changevm win7`. The first OS to reach the votes needed wins; voting for another OS moves your vote. `!changevm` on its own lists the options.
- The vote command can be renamed (for example `!os`) on the OS Voting page; `!changevm` keeps working too.
- Set the votes needed, how long an OS vote stays open and a cooldown after each switch, and see the live vote with a cancel button.
- Pick which VMs chat can vote for, give each one a short name viewers type, and the snapshot it starts from. VMs that are off stay out of reach for viewers and mods; the owner can still switch to any VM.
- Votes needed and vote time for `!revert`, `!restartvm` and `!forcefixvm` are now settings too.

## Vote fixes
- Switching VMs used to cycle through every VM, ignoring the whitelist and the chosen snapshot. It now only goes to votable VMs and uses their snapshot.
- Force switching left the old VM running in the background and started the new one next to it. The old VM is now shut down first.
- On VMware, switching VMs did nothing. It now stops the current VM, picks the new .vmx, reverts its snapshot and starts it.
- A passing vote no longer wipes every other running vote.
- Chat now gets told when a vote is full, paused, on cooldown or runs out of time, instead of silence.

## File drop
- `!sendfile` on Discord: admins and the owner attach a file (or type `!sendfile` and upload it within 2 minutes) and the bot puts it on the VM desktop. Everyone else gets told no.
- The file is never opened on the host: it lands in a temp folder under a cleaned-up name, is copied into the VM with VirtualBox Guest Additions (`guestcontrol copyto`) or VMware Tools (`CopyFileFromHostToGuest`), and is deleted right after.
- Set the VM's Windows username and password under **Discord → File drop** (the password is stored encrypted with Windows DPAPI and passed to VirtualBox through a temp file, never on the command line or in logs). Size limit 10-100 MB, up to 5 files per message. **Send test file** checks the setup.

## Encoding filter
- The base64 filter now catches every common encoding: base64/base64url, base32, base16 (hex), base58, base62, base36, base85/ascii85, binary, `\x` / `\u` / octal / percent / HTML escapes, char-code lists, split-up blobs, fullwidth and zero-width tricks, and decoder calls (certutil, FromBase64String, b32decode, xxd -r, atob, fromCharCode, ...).
- It covers YouTube and Discord, commands and plain chat. Only the console, the owner, admins and mods get through.
- A viewer whose command is blocked can't send commands anymore (`!unblock <user>` clears them). A plain chat message is hidden from overlays and chat, and deleted on Discord.

## Overlays
- The OG classic overlay is back at `/ogchat`: red vote counter on top (`!revert: 0/2`, or "No active votes"), viewers and likes, and the chat below with bold outlined names. Add `?transparent=1` for a see-through background in OBS.
- Chat overlays are bigger by default, with a Chat size switch (Small / Normal / Big / Huge) on the Overlays page that resizes every chat overlay live in OBS. Add `?scale=1.6` to one overlay's URL to pin its size.
- New `/clock` overlay: local time, date and how long the app has been live. `?h12=1` for AM/PM, `?seconds=0` to hide seconds.
- Every chat overlay and the live chat in the app now show a YouTube or Discord icon next to each message, a crown next to the owner and a wrench next to mods.
- The YouTube and Discord icons are the official full-colour logos (from SVG Logos), the crown, wrench, eye and thumbs-up come from Material Design Icons. They are built into `yt2vm.py` and also ship in `assets/icons`. Put your own `youtube.svg`, `discord.svg`, `owner.svg`, `mod.svg`, `eye.svg` or `likes.svg` in `assets/icons` (or an `icons` folder) next to `yt2vm.py` to replace them.

## Fixes
- The ChangeVM whitelist and snapshots now load on start (they were read before settings loaded, so they reset on every launch).
- "Admins only" on the Command Power page now actually limits the command to admins.

# Release Notes — 1.2.0

## Plugins
- Add chat commands, chat reactions, timers, panels and even whole pages to YT2VM without editing `yt2vm.py`. Plugins live in the `plugins` folder next to it.
- **Tools → Plugins**: enable, disable, reload or uninstall plugins, or start one with **New plugin**.
- **Tools → Plugin Docs**: the full guide to writing and releasing plugins, built into the app.
- Single-file `.py` / `.y2vp` plugins work too.

## Plugin Market
- **Tools → Plugin Market**: install and update reviewed plugins from plugins.reallyiron.net in one click. Every file is checked with a checksum before it's installed.
- Publish your own plugin with the **Submit** button, with no GitHub account needed. It goes live once it's reviewed.

## Automatic updates
- YT2VM now checks for new releases and asks before updating. It keeps a backup of your current version and never restarts by itself.
- Settings are under **Machine → System → Updates**: Ask me, Install it and I restart later, or Don't check.

## Discord
- Clearer messages for every command, and VM maintenance is announced with a screenshot.
- `!s` / `!screen` / `!screenshot` post a VM screenshot.
- Long commands are shortened in Discord but still run.
- `!ban @user` works with mentions.

## Commands and input
- `!help` lists every command.
- New: `!ban`, `!unban`, `!lock` and `!unlock`.
- `!wait` accepts units: `2`, `2s`, `500ms`, `1.5 sec` or `2m`, capped at 30 s.
- Keyboard layout fixes for Danish, Turkish, Norwegian and UK, and dead keys now type correctly.

**Updating from 1.0.0:** download `yt2vm.py` from this release once. From 1.1.0 on, YT2VM updates itself.

# Plugins

Plugins are folders inside `plugins/` next to `yt2vm.py`. Manage them on **Tools → Plugins**, or install them from **Tools → Plugin Market**. A plugin can be as small as:

```python
# plugins/greeter/plugin.py   (plus a plugin.json with "id": "greeter")
def setup(api):
    @api.command("hi", help="Say hi")
    def hi(ctx):
        ctx.reply(f"Hi {ctx.user}!")
```

You only need `yt2vm.py`. The app creates the `plugins` folder itself, and the full docs are built in under **Tools → Plugin Docs**. **New plugin** creates a starter plugin, and **Submit** sends it to the plugin market for review, all from the GUI. No GitHub account is needed.

- [docs/plugins.md](docs/plugins.md): installing, writing and releasing plugins, and the full API
- [docs/plugin-market.md](docs/plugin-market.md): using the market, publishing a plugin, and the review guidelines

These `.md` files are generated from the docs inside `yt2vm.py`. To change them, edit `PLUGIN_DOCS` in `yt2vm.py`, then run `python docs/sync_docs.py`.

Plugins run with the same access to your PC as YT2VM, so only install ones you trust.

# ChangeVM tab (Machine → ChangeVM)

Lets you decide which VMs are whitelisted for the `!changevm` chat command, and what snapshot each whitelisted VM reverts to when switched to.

- **Enable !changevm** - turn the chat command on or off.
- **VM list** - every VM found by VirtualBox (or VMware `.vmx` files) shows up with a checkbox. Tick a VM to whitelist it for `!changevm`. If the whitelist is empty, only the current VM can be switched to.
- **Snapshot per VM** - each whitelisted VM has a snapshot dropdown. When `!changevm <vm>` is used, YT2VM switches to that VM and reverts to the snapshot you picked for it.
- **SAVE CHANGEVM LIST** - writes the whitelist and snapshot picks to settings so they survive restarts.

Usage in chat: `!changevm` (reverts current VM to its snapshot) or `!changevm <VM Name>` (switches to a whitelisted VM and reverts its snapshot). Access to `!changevm` is also governed by the Commands Power tab.

# Commands Power tab (Machine → Command Power)

Lets you decide who can run the advanced VM commands and how often.

For each command you can choose:

- **Everyone** - any viewer can use the command (subject to cooldowns/rate limits).
- **Admins only** - only mods/admins/owner can use it.
- **Disabled** - the command is blocked for everyone except the owner.

**Countdown (s)** - optional per-user cooldown for that command. A viewer who runs the command can't run it again until the countdown expires. Set to `0` to turn it off. The owner always bypasses these limits.

Covered commands include: `!revert`, `!startvm`, `!shutdown`, `!restartvm`, `!switchsnapshot`, `!makesnapshot`, `!changevm`, `!remake2`, `!fixvm`, `!forcefixvm`, `!snapshotnow`, `!revertnow`, `!restartnow`.

# Updates

YT2VM updates itself from [`yt2vm.py` on the main branch](https://github.com/reallyiron/YT2VM/blob/main/yt2vm.py). It checks right after starting and then as often as you pick on **Main → Updates** (only on start, every minute, 5 minutes, hour or day), and tells you at the top after the start-up check: *Checked for updates: you are up to date!*

When the file on GitHub has a different hash and the same or a higher version:

1. An **Updating To Version x.y** screen with a progress bar appears.
2. The app checks the new `yt2vm.py`: it must be YT2VM and contain no syntax errors.
3. It keeps your current file next to it as `yt2vm.py.bak-<old version>`.
4. It replaces `yt2vm.py` and restarts by itself. If the VM is busy switching or reverting, it waits for that first.

A lower version on GitHub is never installed over a newer copy.

On **Main → Updates** you can:

- check for updates now (also in the command palette, Ctrl K);
- see **What's new** (also on the Help page);
- go back with **Restore previous version**;
- choose what happens when `yt2vm.py` changes on GitHub: **Update automatically** (the default), **Ask me first**, or **Don't check**.

Settings, plugins and logs aren't touched by an update. Packaged `.exe` builds don't update themselves.

## Releasing a new version (maintainers)

1. In `yt2vm.py`, raise `version = "..."` by 0.1 (for example `1.4.0` to `1.5.0`) and add the version to `CHANGELOG` with what was added, changed, fixed and removed.
2. Merge it to `main`. Every copy of YT2VM installs it the next time it starts.

Pushing a file with the same version also updates everyone, so always raise the version: the What's new page and the update screen show it.

# FAQ

## Do I have to credit you?

Please do it, I spend alot of time on the prompts.

## FILTERS!
Welcome B64 filters, Still wip, Please make a Pull request if you have any fixes!

## Is this script malware?

No. All source code is open to everyone, so you can inspect it yourself. There are no stealers or malicious components in this repository.
