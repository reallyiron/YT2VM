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
pip install virtualbox Flask pytchat obsws-python pywin32
```

Attention: `pywin32` works on Windows only and should be installed if you use the script on Windows.

# Features

- Cross-Platform: Supports Windows, macOS, and Linux.
- Open-Source: Full source code is open to everyone.
- VM Integration: Designed to work with VirtualBox-powered environments.
- OBS Support: Can integrate with OBS WebSocket for automation.
- Flask-Based Control: Includes a lightweight Python web interface.
- Plugins: Add your own chat commands, chat reactions, timers and GUI panels without touching `yt2vm.py`.
- Plugin Market: Browse, install and publish reviewed plugins straight from the app (Tools → Plugin Market).

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

1. In `yt2vm.py`, raise `version = "..."`, for example to `version = "1.0.1"`, and merge it to `main`.
2. Publish a GitHub release whose tag is `v` plus that exact version, with the changes in the release notes:

   ```bash
   gh release create v1.0.1 --title "YT2VM 1.0.1" --notes "- What changed"
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

