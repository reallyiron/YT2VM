# Plugins

Plugins add things to YT2VM without editing `yt2vm.py`: new chat commands, reactions to chat messages, timers, and small settings panels in the GUI.

Everything here works with nothing but `yt2vm.py`. The app creates the `plugins` folder itself, these docs are built into the app (**Tools → Plugin Docs**), and you can create, test and package a plugin from the GUI.

- [Installing and managing plugins](#installing-and-managing-plugins)
- [Your first plugin](#your-first-plugin)
- [plugin.json](#pluginjson)
- [API reference](#api-reference)
- [Threads and the UI](#threads-and-the-ui)
- [Releasing a plugin](#releasing-a-plugin)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

To get plugins from the market, see the [Plugin market guide](plugin-market.md).

---

## Installing and managing plugins

Plugins live in a `plugins` folder next to `yt2vm.py`. The app creates it on first start. Each plugin is its own folder:

```
yt2vm.py
plugins/
  hello/
    plugin.json
    plugin.py
  chat-stats/
    plugin.json
    plugin.py
    data/          <- the plugin's own files (kept when you update it)
```

There are four ways to get a plugin:

1. **Plugin Market page** (Tools → Plugin Market): click **Install**.
2. **New plugin button** (Tools → Plugins): creates a working starter plugin for you to edit.
3. **By hand:** copy a plugin folder into `plugins`, then click **Reload all** on the Plugins page (or restart the app).
4. **From chat or the console** (owner only): drop the folder in, then run `!plugin reload`.

The **Plugins** page (Tools → Plugins) lists every installed plugin with its status (`Running`, `Disabled` or `Error`), the commands it adds, and these buttons:

| Button | What it does |
|---|---|
| Enable / Disable | Turns the plugin on or off. The choice is saved in `settings.json` under `plugins_enabled`. |
| Reload | Re-reads the plugin's files from disk. Use it while you're writing a plugin. |
| Open folder | Opens the plugin's folder. |
| Package | Builds a release of the plugin for a market. See [Releasing a plugin](#releasing-a-plugin). |
| Uninstall | Deletes the plugin's folder, after you confirm. |

Plugin panels (settings, leaderboards and so on) appear inside each plugin's card.

### Owner chat commands

| Command | Effect |
|---|---|
| `!plugins` | Lists installed plugins. |
| `!plugin reload` | Reloads all plugins. |
| `!plugin reload <id>` | Reloads one plugin. |
| `!plugin enable <id>` / `!plugin disable <id>` | Turns one plugin on or off. |

The command palette (Ctrl K) also has **Open plugins**, **Open the plugin market**, **Open the plugin docs** and **Reload all plugins**.

---

## Your first plugin

The quickest start: on **Tools → Plugins**, click **New plugin**, type an id such as `greeter`, and the app writes a working plugin into `plugins/greeter/`, loads it, and opens its folder. Type `!greeter` in the Dashboard console to try it.

To make one by hand, create a folder `plugins/greeter/` with two files.

**plugins/greeter/plugin.json**

```json
{
    "id": "greeter",
    "name": "Greeter",
    "version": "1.0.0",
    "author": "you",
    "description": "Says hi.",
    "api": 1
}
```

**plugins/greeter/plugin.py**

```python
def setup(api):
    @api.command("hi", help="Say hi")
    def hi(ctx):
        ctx.reply(f"Hi {ctx.user}!")
```

Click **Reload all** on the Plugins page and type `!hi` in the Dashboard console. You should see `[Greeter]: Hi [console]!`.

Here is a bigger example that uses every part of the API:

```python
import tkinter as tk


def setup(api):
    # a chat command anyone can use
    @api.command("dance", help="Make the VM dance")
    def dance(ctx):
        ctx.run("!key left | !key right | !key left | !key right")
        ctx.reply(f"{ctx.user} started a dance")

    # a command only mods and owners can use
    @api.command("panic", help="Revert the VM", mod_only=True)
    def panic(ctx):
        api.run("!revert")            # runs with console rights, see "Security" below

    # react to every chat message (YouTube and Discord)
    @api.on("chat")
    def on_chat(user, message, is_mod, is_owner, source):
        if "gg" in message.lower():
            api.say(f"gg {user}")

    # run something every 5 minutes
    @api.every(300)
    def reminder():
        api.flash("Remember to follow!", "info", 6)

    # settings that persist in settings.json
    if api.get("first_run", True):
        api.log("first run!")
        api.set("first_run", False)

    # a small panel on the Plugins page
    def panel(parent):
        tk.Label(parent, text="Hello from my plugin", bg=parent["bg"], fg="#D3D8DF").pack(anchor="w")
    api.add_panel(panel, "Status")


def teardown(api):
    # optional: called on disable, reload, uninstall and app exit
    pass
```

The official market's sample plugins are short, working examples. Install them from the Plugin Market page and click **Open folder** to read them, or browse them on GitHub: <https://github.com/reallyiron/YT2VM/tree/main/market/plugins>

| Plugin | Shows how to |
|---|---|
| `hello` | register a command, store a setting, build a settings panel |
| `chat-stats` | use the `chat` event, run a timer, keep files in `data/`, use `teardown` |
| `shortcuts` | register many commands in a loop and queue VM input with `ctx.run` |
| `announcer` | build a timer-driven feature with an editable panel |

---

## plugin.json

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Unique id: lowercase letters, digits, `-` and `_`, 2–40 characters. Never change it after release, because the market uses it to match updates. |
| `name` | no | Display name. Defaults to `id`. |
| `version` | no | Version such as `1.2.0`. The market compares versions to offer updates. |
| `author` | no | Shown in the GUI. |
| `description` | no | One or two sentences, shown in the GUI. |
| `api` | no | Plugin API version the plugin needs. Defaults to `1`. If it is higher than the app supports, the plugin doesn't load and shows an error telling the user to update YT2VM. |
| `entry` | no | Python file to load. Defaults to `plugin.py`. Must be inside the plugin folder. |
| `tags`, `commands`, `homepage` | no | Only used by the market listing. |

---

## API reference

### setup(api) and teardown(api)

`setup(api)` is required. It runs once when the plugin loads and should register everything the plugin needs. If it raises an exception, the plugin shows **Error** and nothing it registered stays active.

`teardown(api)` is optional. It runs when the plugin is disabled, reloaded or uninstalled, and when the app closes. YT2VM removes the plugin's commands, events, timers and panels automatically, so use `teardown` only for the plugin's own cleanup, such as saving files or stopping threads it started.

### Registering things

| Call | Description |
|---|---|
| `@api.command(name, help="", mod_only=False, owner_only=False)` | Adds `!name`. The handler receives a `ctx` (see below). Names are lowercase letters, digits and `_`, at most 32 characters, and can't replace a built-in command or one from another plugin. The command uses the user's configured prefix, so `!name` becomes `?name` if the prefix is `?`. |
| `@api.on(event)` | Subscribes to an event (see below). Also works as `api.on(event, fn)`. |
| `@api.every(seconds)` | Calls `fn()` every `seconds` (minimum 1). Also works as `api.every(seconds, fn)`. |
| `api.add_panel(build_fn, title=None)` | `build_fn(parent)` is called on the UI thread whenever the Plugins page redraws. Put your Tk widgets inside `parent`. Use `parent["bg"]` as the background so the panel matches the theme. |

Viewer commands go through the same protections as built-in ones before they reach your handler: blacklist, timed bans, cooldown, rate limit, chat pause and disabled commands. Built-in commands always take priority over plugin commands.

### Events

| Event | Handler signature | When |
|---|---|---|
| `ready` | `fn()` | After the app finishes starting, or right after loading if the app is already running. |
| `chat` | `fn(user, message, is_mod, is_owner, source)` | For every chat message. `source` is `"youtube"` or `"discord"`. |
| `command` | `fn(user, cmd, arg)` | For every command that gets past the security checks, including built-in ones. `cmd` includes the `!`. |
| `shutdown` | `fn()` | When the window closes. |

### The ctx object

| Attribute / method | Description |
|---|---|
| `ctx.user` | Display name of the person who ran the command. |
| `ctx.clean_user` | Lowercase name without `@`, which is the form used for bans and stats. |
| `ctx.command` | Command name without the prefix. |
| `ctx.arg` / `ctx.args` | Everything after the command, as one string and split on spaces. |
| `ctx.is_mod`, `ctx.is_owner`, `ctx.is_admin` | Permission flags. |
| `ctx.source` | `"youtube"` or `"discord"`. Commands from the console and from automations report `"youtube"`. |
| `ctx.reply(text)` | Posts `[Plugin Name]: text` to the console and overlay chat. |
| `ctx.run(chain)` | Queues VM input **on behalf of the user**. Only viewer action commands are accepted: `!type !send !key !combo !keydown !keyup !move !abs !click !rclick !mclick !scroll !drag !wait !cmd !run !startvm !roll !coinflip` and their short aliases. For non-admins the normal payload filter applies. Returns the number of steps queued. |

### Everything else on api

| Member | Description |
|---|---|
| `api.say(text)` | Posts `[Plugin Name]: text` to the console and overlay chat. |
| `api.log(text)` | Writes to `output_log.txt` only. |
| `api.toast(text, kind="info")` | Shows a toast in the GUI. `kind` is `info`, `ok` or `bad`. |
| `api.flash(text, kind="info", dur=6)` | Shows a flash message on the OBS overlay. |
| `api.run(chain)` | Runs any command chain **as the console, with owner rights**. |
| `api.get(key, default=None)` / `api.set(key, value)` | Per-plugin settings saved in `settings.json` under `plugin_settings.<id>`. Values must be JSON-serialisable. |
| `api.settings` | A copy of all of this plugin's settings. |
| `api.ui(fn, *args)` | Runs `fn` on the Tk UI thread. |
| `api.id`, `api.manifest`, `api.path` | The plugin's id, its parsed `plugin.json`, and its folder. Keep your own files in `os.path.join(api.path, "data")`, which survives market updates. |
| `api.api_version`, `api.app_version` | Plugin API version (currently `1`) and the YT2VM version string. |
| `api.app` | The `ChatPlaysApp` object itself. It is powerful but internal and can change between releases, so prefer the API above. |

---

## Threads and the UI

- Command handlers, event handlers and timers all run on one background thread named `plugins`, in order. A slow handler delays every other plugin, so do long work (network calls, big files) in your own `threading.Thread`. If a callback takes more than 2 seconds, a warning is written to the log.
- **Never touch Tk widgets from a handler or timer.** Wrap UI updates in `api.ui(fn)`. Panel `build_fn`s already run on the UI thread, and so do callbacks from widgets such as button commands and `widget.after(...)`.
- An exception in a callback is written to `crash_log.txt` and the console. It doesn't stop the plugin or the app.

---

## Releasing a plugin

A release is a copy of your plugin folder plus a market index (`index.json`) that lists every file with its sha256 checksum. Users get your plugin by adding the index URL to **Sources** on the Plugin Market page. When you publish a higher version, they see an **Update** button.

### 1. Get it ready

- Pick an `id` you will keep forever, and fill in `name`, `author`, `description` and `version` in `plugin.json`. Adding `tags`, `commands` and `homepage` makes the market card more useful.
- Use version numbers like `1.0.0`. Raise the last number for fixes (`1.0.1`), the middle one for new features (`1.1.0`), and the first one for changes that break existing settings (`2.0.0`). The market only offers an update when the new version is higher.
- Set `api` to the plugin API version you tested with (currently `1`).
- Don't put passwords, tokens or anything personal in the plugin folder. Everything in it except `data/` gets published.

### 2. Test it

- Click **Reload** on the plugin's card and check that it shows **Running**, not **Error**.
- Try every command from the Dashboard console. Also try them as a viewer, through chat or with the Chat Tools test message, to check `mod_only` and the payload filter.
- Disable and enable it, then restart the app, to check that `teardown` and saved settings work.
- Read `crash_log.txt` for anything with your plugin's id in it.

### 3. Package it

On **Tools → Plugins**, click **Package** on your plugin's card and choose a folder for your market (an empty folder the first time). The app then:

- copies the plugin into `<folder>/plugins/<id>/`, leaving out `data/`, `__pycache__` and dotfiles;
- writes or updates `<folder>/index.json` with the plugin's details and a sha256 for every file;
- keeps any other plugins already in that folder's index.

Package into the same folder again for each new version. In a clone of the YT2VM repo, `python market/build_index.py` does the same for `market/`.

### 4. Publish it

**In your own market.** Upload the folder to anywhere that serves raw files, for example a GitHub repo:

1. Create a public GitHub repo, such as `yourname/yt2vm-plugins`.
2. Upload `index.json` and the `plugins` folder to its root, keeping the folder structure.
3. Share this URL: `https://raw.githubusercontent.com/yourname/yt2vm-plugins/main/index.json`
4. Users paste it into **Sources** on the Plugin Market page, then click **Save sources**.

Upload the files exactly as they are. If anything changes the bytes, such as an editor or Git converting line endings, the checksums no longer match and installs are refused. In a Git repo, add a `.gitattributes` file containing `* -text`.

**In the official market.** Open a pull request to <https://github.com/reallyiron/YT2VM> that adds `market/plugins/<id>/` and the updated `market/index.json`. The [Plugin market guide](plugin-market.md) has the details.

### 5. Ship updates

1. Raise `version` in `plugin.json`.
2. Package into the same folder again.
3. Upload the changed files and `index.json`.

Users who click **Refresh** on the Plugin Market page then see **Update x → y**. Updating keeps their `data/` folder and their settings.

---

## Security

**A plugin is ordinary Python code running inside YT2VM with full access to your PC.** It can read files, start programs and use the network. Only install plugins whose code you have read or whose author you trust.

When you write a plugin:

- Use `ctx.run(...)` for anything a viewer triggers. It keeps the viewer's own permissions and goes through the payload filter.
- Use `api.run(...)` only with text you wrote yourself, never with text that came from chat. It runs with owner rights, so passing viewer text to it would give viewers owner powers.
- Use `mod_only=True` or `owner_only=True` for anything destructive.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| The plugin doesn't appear at all | `plugin.json` is missing, is invalid JSON, or has a bad `id`. The reason is in `output_log.txt` (search for `PLUGIN`). Folders starting with `.` or `_` are ignored. |
| Status is **Error** | The message is shown on the card. The full traceback is in `crash_log.txt`. |
| "`!x is a built-in command`" | Choose another command name. |
| "already registered by plugin …" | Two plugins use the same command name. Disable one of them. |
| The command does nothing for viewers | Check whether it is `mod_only`, whether chat is paused, and whether the viewer is on cooldown. |
| Changes don't show up | Click **Reload** on the plugin's card. |
| Users get "checksum mismatch" | The uploaded files differ from what you packaged, usually because of line-ending conversion. Package again and upload the files unchanged. |
