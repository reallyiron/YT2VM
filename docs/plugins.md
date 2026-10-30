# Plugins

Plugins add things to YT2VM without editing `yt2vm.py`: new chat commands, reactions to chat messages, timers, and small settings panels in the GUI.

Everything here works with nothing but `yt2vm.py`. The app creates the `plugins` folder itself, these docs are built into the app (**Tools → Plugin Docs**), and you can create, test and publish a plugin from the GUI, with no GitHub account.

- [Installing and managing plugins](#installing-and-managing-plugins)
- [Your first plugin](#your-first-plugin)
- [plugin.json](#pluginjson)
- [API reference](#api-reference)
- [Building UI](#building-ui)
- [Threads and the UI](#threads-and-the-ui)
- [Releasing a plugin](#releasing-a-plugin)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

How the plugin market works is covered in the [Plugin market guide](plugin-market.md).

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
| Submit | Uploads the plugin to the plugin market for review. Only shown for plugins you made: plugins installed from the market belong to their author. See [Releasing a plugin](#releasing-a-plugin). |
| Uninstall | Deletes the plugin's folder, after you confirm. |

Plugin panels (settings, leaderboards and so on) appear inside each plugin's card.

### Owner chat commands

| Command | Effect |
|---|---|
| `!plugins` | Lists installed plugins. |
| `!plugin reload` | Reloads all plugins. |
| `!plugin reload <id>` | Reloads one plugin. |
| `!plugin enable <id>` / `!plugin disable <id>` | Turns one plugin on or off. |

The command palette (Ctrl K) also has **Open plugins**, **Open the plugin market**, **Open the plugin docs**, **Create a new plugin** and **Reload all plugins**.

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
    def panel(ui):
        ui.label("Hello from my plugin")
        row = ui.row()
        row.button("Flash it", lambda: api.flash("Hello!", "good", 4), "primary")
        row.toggle("Greet gg", api.get("greet", True), lambda on: api.set("greet", on))
        row.stretch()
    api.add_panel(panel, "Status")


def teardown(api):
    # optional: called on disable, reload, uninstall and app exit
    pass
```

### Single-file plugins (.py / .y2vp)

You don't need a folder or a `plugin.json` for a quick plugin. Drop a single file straight into `plugins/`:

```
plugins/
  greeter.py        <- a single-file plugin, id "greeter"
  mymacros.y2vp     <- also a plugin (.y2vp = "yt2vm plugin"), id "mymacros"
```

A `.y2vp` file is just Python with the YT2VM plugin API available (same as `.py`); the different extension only keeps your plugins easy to spot. The plugin's **id** is the file name without the extension, so it must be lowercase letters, digits, `-` and `_`. The file needs a `setup(api)` function, exactly like `plugin.py`. There is no `plugin.json`, so set these at the top of the file if you want them:

```python
PLUGIN_NAME = "My Macros"
PLUGIN_VERSION = "1.0.0"
PLUGIN_AUTHOR = "you"
PLUGIN_DESCRIPTION = "A couple of handy macros."

def setup(api):
    @api.command("np", help="open notepad")
    def np(ctx):
        ctx.run("!combo win+r | !wait 1 | !send notepad")

def teardown(api):
    pass
```

Single-file plugins get the whole API, including tabs and buttons. They can't be submitted to the market (put them in a folder with a `plugin.json` first), but everything else works the same. Click **Reload all** on the Plugins page after adding one.

The market's starter plugins are short, working examples. Install them from the Plugin Market page and click **Open folder** on the Plugins page to read them:

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
| `name` | yes for the market | Display name. Defaults to `id`. |
| `version` | yes for the market | Version such as `1.2.0`. The market compares versions to offer updates. |
| `author` | yes for the market | Shown in the GUI. |
| `description` | yes for the market | One or two sentences, shown in the GUI. |
| `api` | no | Plugin API version the plugin needs. Set it to `3` if you draw panels or tabs (the PyQt6 UI helpers below), or `2` if you only use `add_button`, `hide_tab` and `hide_button`. Plugins without any UI work on every version. If it is higher than the app supports, the plugin doesn't load and shows an error telling the user to update YT2VM. |
| `entry` | no | Python file to load. Defaults to `plugin.py`. Must be inside the plugin folder. |
| `tags`, `commands`, `homepage` | no | Shown on the market card. |

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
| `api.add_panel(build_fn, title=None)` | `build_fn(ui)` is called on the UI thread whenever the Plugins page redraws. `ui` is a [PluginUI](#building-ui) for drawing controls on the plugin's card. |
| `api.add_tab(title, build_fn=None, group="TOOLS")` | Adds a new sidebar tab. `build_fn(ui)` draws its contents (runs on the UI thread). The tab is removed automatically when the plugin unloads. Returns the tab's widget. |
| `api.add_button(page, text, fn, variant="neutral")` | Adds a button to a page. `page` is a tab (from `add_tab` or `api.page(title)`), a `ui` object, or a tab title. `fn()` runs when clicked. Removed automatically on unload. `variant` is `neutral`, `go`, `primary`, `danger`, `warn`, `info` or `violet`. |
| `api.hide_tab(title)` | Hides any tab by its title (built-in or added). Restored automatically on unload. |
| `api.hide_button(text, page=None)` | Hides buttons whose text matches, on one page (tab or title) or everywhere. Restored automatically on unload. |
| `api.remove_tab(title)` | Removes a tab this plugin added. |
| `api.pages()` / `api.page(title)` | List all tab titles / get one tab's widget (or `None`) so you can add buttons to it. |

Viewer commands go through the same protections as built-in ones before they reach your handler: blacklist, timed bans, cooldown, rate limit, chat pause and disabled commands. Built-in commands always take priority over plugin commands.

### Events

| Event | Handler signature | When |
|---|---|---|
| `ready` | `fn()` | After the app finishes starting, or right after loading if the app is already running. |
| `chat` | `fn(user, message, is_mod, is_owner, source)` | For every chat message. `source` is `"youtube"` or `"discord"`. |
| `command` | `fn(user, cmd, arg)` | For every command that gets past the security checks, including built-in ones and those of plugins. `cmd` includes the `!`. Commands typed in the Dashboard console, run by automations, or queued with `api.run` arrive with `user` set to `"[console]"`. Check `user.startswith("[")` to skip them, for example when you only care about viewers. |
| `shutdown` | `fn()` | When the window closes. |

### The ctx object

| Attribute / method | Description |
|---|---|
| `ctx.user` | Display name of the person who ran the command, or `"[console]"` for the Dashboard console and automations. |
| `ctx.clean_user` | Lowercase name without `@`, which is the form used for bans and stats. |
| `ctx.command` | Command name without the prefix. |
| `ctx.arg` / `ctx.args` | Everything after the command, as one string and split on spaces. |
| `ctx.is_mod`, `ctx.is_owner`, `ctx.is_admin` | Permission flags. |
| `ctx.source` | `"youtube"` or `"discord"`. Commands from the console and from automations report `"youtube"`. |
| `ctx.reply(text)` | Posts `[Plugin Name]: text` to the console and overlay chat. If the command came from Discord, it is also posted back to the Discord command channel. |
| `ctx.run(chain)` | Queues VM input **on behalf of the user**. Only viewer action commands are accepted: `!type !send !key !combo !keydown !keyup !move !abs !click !rclick !mclick !scroll !drag !wait !cmd !run !startvm !roll !coinflip` and their short aliases. For non-admins the normal payload filter applies. Returns the number of steps queued. |

### Everything else on api

| Member | Description |
|---|---|
| `api.say(text)` | Posts `[Plugin Name]: text` to the console and overlay chat. |
| `api.log(text)` | Writes to `output_log.txt` only. |
| `api.toast(text, kind="info")` | Shows a toast in the GUI. `kind` is `info`, `ok` or `bad`. |
| `api.flash(text, kind="info", dur=6)` | Shows a flash message on the OBS overlay for `dur` seconds. `kind` is `info`, `good`, `warn` or `err` and sets the banner's colour. |
| `api.run(chain)` | Runs any command chain **as the console, with owner rights**. It is queued: the call returns at once and the commands run shortly after, as user `"[console]"`, so they also fire the `command` event. |
| `api.get(key, default=None)` / `api.set(key, value)` | Per-plugin settings saved in `settings.json` under `plugin_settings.<id>`. Values must be JSON-serialisable. |
| `api.settings` | A copy of all of this plugin's settings. |
| `api.ui(fn, *args)` | Runs `fn` on the UI thread. |
| `api.qt` | The PyQt6 modules: `api.qt.QtWidgets`, `api.qt.QtCore` and `api.qt.QtGui`. See [Building UI](#building-ui). |
| `api.id`, `api.manifest`, `api.path` | The plugin's id, its parsed `plugin.json`, and its folder. Keep your own files in `os.path.join(api.path, "data")`, which survives market updates. |
| `api.api_version`, `api.app_version` | Plugin API version (currently `3`) and the YT2VM version string. |
| `api.app` | The `ChatPlaysApp` object itself. It is powerful but internal and can change between releases, so prefer the API above. |

---

## Building UI

The app window is built with PyQt6. Panels and tabs receive a `ui` object with simple helpers, so most plugins never need to import Qt. Every helper returns the widget it made, and callbacks are wrapped so an exception is logged instead of crashing the app.

| Helper | Description |
|---|---|
| `ui.label(text, muted=False, mono=False, bold=False, size=10, color=None)` | A text label. `color` is a role (`ok`, `bad`, `warn`, `info`, `violet`, `accent`, `muted`, `faint`, `hi`) or a hex colour. Change it later with `.setText(...)`. |
| `ui.heading(text)` | A section heading. |
| `ui.button(text, fn, variant="neutral", icon=None)` | A button. `variant` is `neutral`, `primary`, `go`, `danger`, `warn`, `soft`, `ghost`, `link`, `info` or `violet`. |
| `ui.input(placeholder="", value="", on_enter=None, on_change=None, secret=False, mono=False)` | A one-line text box. Read it with `.get()` and change it with `.set(text)`. `on_change(text)` runs on every edit. |
| `ui.toggle(text, value=False, on_change=None)` | An on/off switch. `.get()` / `.set(bool)`. `on_change(on)` runs when the user flips it. |
| `ui.select(options, value=None, on_change=None, editable=False)` | A drop-down. `.get()` / `.set(text)`. `on_change(text)` runs when the user picks an option. |
| `ui.number(value=0)` | A small number box. `.number(default)` returns it as a float. |
| `ui.text(value="", height=120, readonly=False)` | A multi-line text box. `.get()` / `.set(text)`. |
| `ui.log(height=140)` | A read-only log. Add lines with `.append_line(text, color=None)`. |
| `ui.row()` | A horizontal row. Returns another `ui` whose helpers place widgets side by side. |
| `ui.card(title=None, subtitle=None)` | A card with its own `ui` inside. |
| `ui.separator()`, `ui.space(px)`, `ui.stretch()` | Layout helpers. `stretch()` pushes the rest of a row to the right. |
| `ui.add(widget)` | Adds any Qt widget you built yourself. |
| `ui.clear()` | Removes everything this `ui` holds, so you can redraw. |
| `ui.after(ms, fn)` | Runs `fn` once on the UI thread after `ms` milliseconds. |
| `ui.widget`, `ui.layout` | The underlying `QWidget` and its layout, for raw Qt. |

```python
def setup(api):
    def tab(ui):
        card = ui.card("Counter", "Counts how often !hi was used")
        total = card.label(str(api.get("count", 0)), bold=True, size=18)
        row = card.row()
        row.button("Reset", lambda: (api.set("count", 0), total.setText("0")), "danger")
        row.stretch()

        def refresh():
            total.setText(str(api.get("count", 0)))
            ui.after(1000, refresh)
        refresh()
    api.add_tab("Counter", tab)
```

### Raw Qt

`api.qt` gives you the PyQt6 modules if the helpers aren't enough. Create widgets on the UI thread (inside a build function, a widget callback or `api.ui(fn)`) and add them with `ui.add(widget)`:

```python
def setup(api):
    QtWidgets = api.qt.QtWidgets

    def panel(ui):
        slider = QtWidgets.QSlider(api.qt.QtCore.Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(api.get("volume", 50))
        slider.valueChanged.connect(lambda v: api.set("volume", v))
        ui.add(slider)
    api.add_panel(panel, "Volume")
```

### Plugins made for the old window

YT2VM used Tkinter before 1.2.0. Plugins whose panels or tabs create Tkinter widgets still load, and their commands, events and timers keep working, but their panels show a note asking for an update instead of drawing. Porting is usually a few lines: `tk.Label(parent, text=...).pack()` becomes `ui.label(...)`, `tk.Button(parent, text=..., command=fn).pack()` becomes `ui.button(..., fn)`, and `tk.Entry` becomes `ui.input(...)`. Set `"api": 3` in `plugin.json` once you have.

---

## Threads and the UI

- Command handlers, event handlers and timers all run on one background thread named `plugins`, in order. A slow handler delays every other plugin, so do long work (network calls, big files) in your own `threading.Thread`. If a callback takes more than 2 seconds, a warning is written to the log.
- **Never touch widgets from a handler or timer.** Wrap UI updates in `api.ui(fn)`. Panel and tab `build_fn`s already run on the UI thread, and so do callbacks from widgets such as button clicks and `ui.after(ms, fn)`.
- An exception in a callback is written to `crash_log.txt` and the console. It doesn't stop the plugin or the app.

---

## Releasing a plugin

You release a plugin by clicking **Submit** on its card. The app uploads it to the plugin market, the market's admin reviews the code, and once approved it appears on everyone's Plugin Market page. You need no GitHub account and no website.

### 1. Get it ready

- Pick an `id` you will keep forever, and fill in `name`, `author`, `description` and `version` in `plugin.json`. The market requires all four. Adding `tags`, `commands` and `homepage` makes the market card more useful.
- Use version numbers like `1.0.0`. Raise the last number for fixes (`1.0.1`), the middle one for new features (`1.1.0`), and the first one for changes that break existing settings (`2.0.0`). The market only accepts a version higher than the published one.
- Set `api` to the plugin API version you tested with (currently `2`; use `1` if you only use commands, events, timers and panels).
- Don't put passwords, tokens or anything personal in the plugin folder. Every file in it except `data/` and dotfiles gets uploaded. Only text files can be published, up to 25 files and 600 KB in total.

### 2. Test it

- Click **Reload** on the plugin's card and check that it shows **Running**, not **Error**.
- Try every command from the Dashboard console. Also try them as a viewer, through chat or with the Chat Tools test message, to check `mod_only` and the payload filter.
- Disable and enable it, then restart the app, to check that `teardown` and saved settings work.
- Read `crash_log.txt` for anything with your plugin's id in it.

### 3. Submit it

1. On **Tools → Plugins**, click **Submit** on your plugin's card. You can add a note for the reviewer.
2. The market checks the files right away. If something is wrong, such as a syntax error, a missing field or a version that isn't higher, you get a list of problems. Fix them and submit again.
3. The first time you submit a plugin id, the market reserves it for you and returns an **owner key**. The app saves it in `settings.json`, under `plugin_owner_keys`, and shows it once. Back it up, because without it you can't publish updates to that id, for example from another PC.
4. Your plugin is now waiting for review. While it waits you can fix it and submit the same version again.
5. Once the admin approves it, it appears on the Plugin Market page for everyone.

### 4. Ship updates

1. Raise `version` in `plugin.json`.
2. Click **Submit** again. Your saved owner key is sent along automatically.

Once the update is approved, users see **Update x → y** on the Plugin Market page. Updating keeps their `data/` folder and their settings.

---

## Security

**A plugin is ordinary Python code running inside YT2VM with full access to your PC.** It can read files, start programs and use the network. Every plugin in the market is reviewed before it's published, but only install plugins you're comfortable running, and plugins you got elsewhere only if you've read their code or trust the author.

When you write a plugin:

- Use `ctx.run(...)` for anything a viewer triggers. It keeps the viewer's own permissions and goes through the payload filter.
- Use `api.run(...)` only with text you wrote yourself, never with text that came from chat. It runs with owner rights, so passing viewer text to it would give viewers owner powers.
- Use `mod_only=True` or `owner_only=True` for anything destructive.

Plugins that ignore these rules, hide what they do, or contact unexpected servers won't be approved.

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
| Submit says the id belongs to someone else | Another author already reserved that id, or your owner key is missing or wrong. Pick another id, or copy your key back into `plugin_owner_keys` in `settings.json`. |
| Submit says the version was already submitted | Raise `version` in `plugin.json`. |
