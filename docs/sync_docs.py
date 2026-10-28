"""Regenerate docs/plugins.md and docs/plugin-market.md from yt2vm.py.

The plugin docs live inside yt2vm.py (PLUGIN_DOCS) so the app can show them on
the Plugin Docs page with no extra files. Edit them there, then run:

    python docs/sync_docs.py

Use  --check  to fail (exit 1) when the .md files are out of date, e.g. in CI.
yt2vm.py is only parsed, never run.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "yt2vm.py")


def load_docs():
    with open(APP, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PLUGIN_DOCS" for t in node.targets):
            return ast.literal_eval(node.value)
    sys.exit("PLUGIN_DOCS not found in yt2vm.py")


def main():
    check = "--check" in sys.argv
    stale = []
    for key, _title, md in load_docs():
        path = os.path.join(HERE, f"{key}.md")
        want = md.strip("\n") + "\n"
        try:
            with open(path, "r", encoding="utf-8") as f:
                have = f.read()
        except OSError:
            have = None
        if have == want:
            continue
        stale.append(path)
        if not check:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(want)
            print(f"wrote {path}")
    if check and stale:
        sys.exit("out of date: " + ", ".join(stale) + "  (run python docs/sync_docs.py)")
    if not stale:
        print("docs up to date")


if __name__ == "__main__":
    main()
