# Plugin market

The **Plugin Market** page (Tools → Plugin Market) lets you browse, install, update and remove plugins from one or more *market indexes*. An index is a JSON file hosted anywhere: GitHub, your own site, or a folder on your PC.

How to write a plugin is covered in [plugins.md](plugins.md).

---

## Using the market

1. Open **Tools → Plugin Market**. The market loads on its own a moment after startup, or when you press **Refresh**.
2. Search by name, author, description or tag.
3. Click **Install**. The plugin is downloaded, checked, enabled and loaded at once, with no restart needed.
4. When an index has a newer version than you have, the button changes to **Update x → y**. Updating keeps the plugin's `data/` folder.
5. **Uninstall** deletes the plugin's folder.

Installed plugins are then managed on the **Plugins** page.

### Sources

The **Sources** box takes one index URL per line. `https://`, `http://` and `file://` URLs all work. The official source is:

```
https://raw.githubusercontent.com/reallyiron/YT2VM/main/market/index.json
```

**Reset to official** restores that URL. Sources are saved in `settings.json` as `plugin_market_sources`. If the same plugin id appears in more than one source, the first source wins. To stop the market from loading at startup, set `"plugin_market_autoload": false` in `settings.json`.

### What the app checks before installing

- Every file in an index entry has a **sha256**. The app downloads all files into a temporary folder and refuses the whole install if any checksum doesn't match.
- File paths can't be absolute or contain `..`. Each file can be at most 4 MB.
- The downloaded `plugin.json` must have the same `id` as the index entry.
- Only when all of these checks pass is the old plugin folder swapped for the new one.
- For any source other than the official one, the app asks you to confirm and shows the source URL first.

The checksums make sure you get exactly the files the index lists. **They don't make a plugin safe.** A plugin runs with the same access to your PC as YT2VM itself, so only add sources you trust.

---

## Publishing to the official market

1. Fork <https://github.com/reallyiron/YT2VM>.
2. Add your plugin as `market/plugins/<id>/`. The folder name must equal the `id` in `plugin.json`. Fill in `name`, `version`, `author`, `description`, and preferably `tags`, `commands` and `homepage`.
3. Regenerate the index:

   ```bash
   python market/build_index.py
   ```

4. Commit both your plugin folder and the updated `market/index.json`, then open a pull request.

To release an update, bump `version` in `plugin.json`, run `build_index.py` again and open another PR. Users then see an **Update** button.

> The repo's `.gitattributes` marks `market/**` as `-text` so Git never changes line endings there. Changed line endings would change the bytes, and the checksums would no longer match.

---

## Hosting your own market

Any folder laid out like this works:

```
my-market/
  index.json
  plugins/
    my-plugin/
      plugin.json
      plugin.py
```

Copy `market/build_index.py` into `my-market/`, run it, and host the folder anywhere that serves raw files (a GitHub repo through `raw.githubusercontent.com`, GitHub Pages, any static host). Then add the URL of `index.json` to **Sources**.

To test locally without hosting, use a `file://` URL, for example `file:///C:/Users/me/my-market/index.json`.

### Index format

```json
{
  "name": "My market",
  "format": 1,
  "updated": "2026-10-28",
  "plugins": [
    {
      "id": "hello",
      "name": "Hello",
      "version": "1.0.0",
      "author": "reallyiron",
      "description": "!hello greets whoever runs it.",
      "tags": ["example", "fun"],
      "commands": ["hello"],
      "homepage": "https://github.com/reallyiron/YT2VM",
      "base_url": "plugins/hello/",
      "files": [
        { "path": "plugin.json", "sha256": "…" },
        { "path": "plugin.py",   "sha256": "…" }
      ]
    }
  ]
}
```

| Key | Meaning |
|---|---|
| `name` | Source name shown on each card ("from …"). |
| `plugins[].id` | Plugin id, which must match the id in its `plugin.json`. |
| `plugins[].base_url` | Where the files are, relative to the index URL (or absolute). Defaults to `plugins/<id>/`. |
| `plugins[].files[]` | Every file to download: `path` is relative to the plugin folder, `sha256` is required, and an optional `url` overrides `base_url` for that one file. |
| `version`, `author`, `description`, `tags`, `commands`, `homepage` | Shown in the GUI. `version` drives update detection. |

Entries that fail validation are skipped, and the reason is written to `output_log.txt` under `MARKET`. The rest of the index still loads.
