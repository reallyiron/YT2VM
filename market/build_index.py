"""Rebuild market/index.json from the folders in market/plugins/.

Run it after adding or changing a market plugin:

    python market/build_index.py

Every file in a plugin folder (except data/, __pycache__ and dotfiles) is listed
with its sha256, which YT2VM checks before it installs anything.
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGINS = os.path.join(HERE, "plugins")
INDEX = os.path.join(HERE, "index.json")
COPY_KEYS = ("id", "name", "version", "author", "description", "tags", "commands", "homepage")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def plugin_files(folder):
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in ("data", "__pycache__"))
        for fn in sorted(filenames):
            if fn.startswith(".") or fn.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, fn)
            out.append({"path": os.path.relpath(full, folder).replace(os.sep, "/"), "sha256": sha256(full)})
    return out


def main():
    try:
        with open(INDEX, "r", encoding="utf-8") as f:
            name = json.load(f).get("name")
    except (OSError, ValueError):
        name = None
    entries = []
    for folder_name in sorted(os.listdir(PLUGINS)):
        folder = os.path.join(PLUGINS, folder_name)
        man_path = os.path.join(folder, "plugin.json")
        if not os.path.isfile(man_path):
            continue
        with open(man_path, "r", encoding="utf-8") as f:
            man = json.load(f)
        if man.get("id") != folder_name:
            sys.exit(f"{folder_name}: folder name must match the plugin.json id ({man.get('id')!r})")
        e = {k: man[k] for k in COPY_KEYS if k in man}
        e["base_url"] = f"plugins/{folder_name}/"
        e["files"] = plugin_files(folder)
        entries.append(e)
    index = {"name": name or "YT2VM official market", "format": 1,
             "updated": time.strftime("%Y-%m-%d"), "plugins": entries}
    with open(INDEX, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    print(f"wrote {INDEX} with {len(entries)} plugin(s)")


if __name__ == "__main__":
    main()
