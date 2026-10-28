# Plugin market

YT2VM has one plugin market, built into the app at **Tools → Plugin Market**. Every plugin in it is reviewed before it's published.

How to write a plugin is covered in the [Plugins guide](plugins.md).

---

## Using the market

1. Open **Tools → Plugin Market**. The market loads on its own a moment after startup, or when you press **Refresh**.
2. Search by name, author, description or tag.
3. Click **Install**. The plugin is downloaded, checked, enabled and loaded at once, with no restart needed.
4. When a newer version is published, the button changes to **Update x → y**. Updating keeps the plugin's `data/` folder and its settings.
5. **Uninstall** deletes the plugin's folder.

Installed plugins are then managed on the **Plugins** page. To stop the market from loading at startup, set `"plugin_market_autoload": false` in `settings.json`.

### What the app checks before installing

- The market lists every file of a plugin with a **sha256** checksum. The app downloads all files into a temporary folder and refuses the whole install if any checksum doesn't match.
- File paths can't be absolute or contain `..`. Each file can be at most 4 MB.
- The downloaded `plugin.json` must have the same `id` as the market listing.
- Only when all of these checks pass is the old plugin folder swapped for the new one.

The checksums make sure you get exactly the files that were reviewed. A plugin still runs with the same access to your PC as YT2VM itself.

---

## Publishing your plugin

Click **Submit** on the plugin's card (Tools → Plugins). The steps, the owner key and updates are explained under "Releasing a plugin" in the [Plugins guide](plugins.md).

In short:

1. **Submit** uploads the plugin's files.
2. The market checks them straight away:
   - at most 25 text files and 600 KB in total;
   - a valid `plugin.json` with `id`, `name`, `version`, `author` and `description`;
   - every `.py` file must compile (it is never run);
   - every other `.json` file must parse;
   - for updates, a version higher than the published one.
3. Your first submission reserves the plugin id for you with an **owner key**, which the app saves. Only that key can publish updates to the id.
4. The market's admin reads the code and approves or rejects it.
5. Approved plugins appear on everyone's Plugin Market page within a minute or so.

### Review guidelines

A plugin is approved when it:

- does what its description says, and nothing else;
- doesn't download or run code from elsewhere, read files outside its own folder without a clear reason, or send data anywhere the description doesn't mention;
- uses `ctx.run` for viewer-triggered input and never passes chat text to `api.run`;
- marks destructive commands `mod_only` or `owner_only`.

If your plugin is rejected, fix the problem, raise the version and submit again.
