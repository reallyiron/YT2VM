import json
import os
import threading
import tkinter as tk

_counts = {}
_lock = threading.Lock()
_dirty = [False]


def _file(api):
    d = os.path.join(api.path, "data")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "stats.json")


def _top(n):
    with _lock:
        return sorted(_counts.items(), key=lambda kv: kv[1], reverse=True)[:n]


def _save(api):
    with _lock:
        snap = dict(_counts)
    with open(_file(api), "w", encoding="utf-8") as f:
        json.dump(snap, f)


def setup(api):
    _counts.clear()
    try:
        with open(_file(api), "r", encoding="utf-8") as f:
            _counts.update(json.load(f))
    except (OSError, ValueError):
        pass

    @api.on("chat")
    def on_chat(user, message, is_mod, is_owner, source):
        key = str(user).lstrip("@").lower()
        with _lock:
            _counts[key] = _counts.get(key, 0) + 1
        _dirty[0] = True

    @api.command("top", help="Show the five most active chatters")
    def top(ctx):
        rows = _top(5)
        ctx.reply("Top chatters: " + (", ".join(f"{u} ({n})" for u, n in rows) or "nobody yet"))

    @api.command("mystats", help="How many messages you have sent")
    def mystats(ctx):
        with _lock:
            n = _counts.get(ctx.clean_user, 0)
        ctx.reply(f"{ctx.user}: {n} message(s)")

    @api.command("resetstats", help="Clear all counts", mod_only=True)
    def resetstats(ctx):
        with _lock:
            _counts.clear()
        _dirty[0] = True
        ctx.reply("Chat stats reset.")

    @api.every(30)
    def autosave():
        if _dirty[0]:
            _dirty[0] = False
            _save(api)

    def panel(parent):
        lbl = tk.Label(parent, text="", justify="left", anchor="w", bg=parent["bg"], fg="#D3D8DF", font=("Consolas", 9))
        lbl.pack(fill="x")

        def tick():
            if not lbl.winfo_exists():
                return
            rows = _top(10)
            lbl.configure(text="\n".join(f"{i + 1:>2}. {u:<24} {n}" for i, (u, n) in enumerate(rows)) or "No messages yet.")
            lbl.after(3000, tick)
        tick()

    api.add_panel(panel, "Leaderboard")


def teardown(api):
    try:
        _save(api)
    except OSError:
        pass
