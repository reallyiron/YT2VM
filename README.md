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
- Commands Power: set advanced commands (`!revert`, `!startvm`, `!shutdown`, `!switchsnapshot`, `!makesnapshot`, `!changevm`, `!restartvm`, `!remake2`, `!fixvm`, `!forcefixvm`, `!snapshotnow`, `!revertnow`, `!restartnow` and more) to Everyone / Admins only / Disabled, with an optional per-user countdown (Command Power tab).

# Release Notes — 1.3.0

## New window
- The whole app now runs on PyQt6 instead of Tkinter: smoother animations, crisp text on high-DPI screens, and a faster, steadier UI under a busy chat.
- New app logo and icon. It is built into `yt2vm.py`, shows in the title bar and taskbar, is written next to the script as `yt2vm.ico` (handy for PyInstaller), and is the overlay server's favicon.
- Every page was rebuilt with cards, live sparklines, animated toggles and a theme crossfade. All themes, accents, text sizes and motion levels carry over.
- Ctrl+K opens the command palette, Ctrl+Tab steps through pages, Ctrl+L jumps to the console, Ctrl+J shows or hides the live chat.

## Plugins
- Plugin API 3: panels and tabs get a `ui` object with simple helpers (`ui.label`, `ui.button`, `ui.input`, `ui.toggle`, `ui.select`, `ui.row`, `ui.card` ...) and `api.qt` for raw PyQt6. Plugins whose panels use Tkinter keep their commands and timers, and their panel shows a note asking for an update.

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

YT2VM updates itself from the [releases on GitHub](https://github.com/reallyiron/YT2VM/releases). It checks about 15 seconds after starting and then every 6 hours. When a new version is out, it shows the release notes and asks before installing.

Updating never interrupts a stream on its own:

1. The app downloads the new `yt2vm.py` and checks it: it must be YT2VM, contain no syntax errors, and carry the same version as the release.
2. It keeps your current file next to it as `yt2vm.py.bak-<old version>`.
3. It replaces `yt2vm.py`, then asks whether to restart now. You can also restart later; the update is used the next time YT2VM starts.

Under **Machine → System → Updates** you can:

- check for updates now (also in the command palette, Ctrl K);
- install an update that's waiting;
- go back with **Restore previous version**;
- choose what happens when a new version is out: **Ask me** (the default), **Install it, I restart later**, or **Don't check**.

Settings, plugins and logs aren't touched by an update. Packaged `.exe` builds don't update themselves.

## Releasing a new version (maintainers)

1. In `yt2vm.py`, raise `version = "..."`, for example to `version = "1.2.0"`, and merge it to `main`.
2. Publish a GitHub release whose tag is `v` plus that exact version, with the changes in the release notes:

   ```bash
   gh release create v1.2.0 --title "YT2VM 1.2.0" --notes "- What changed"
   ```

   You can also use **Releases → Draft a new release** on GitHub. Every copy of YT2VM is offered the update at its next check.

The tag and the `version` in the file must match, or the app refuses the update. Drafts and pre-releases are never offered, so you can use a pre-release to test a version first.

# FAQ

## Do I have to credit you?

Please do it, I spend alot of time on the prompts.

## FILTERS!
Welcome B64 filters, Still wip, Please make a Pull request if you have any fixes!

## Is this script malware?

No. All source code is open to everyone, so you can inspect it yourself. There are no stealers or malicious components in this repository.
