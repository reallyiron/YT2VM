import time
import tkinter as tk

DEFAULT_MSG = "Type !help to see what you can do in the VM!"
_last = [0.0]


def setup(api):
    _last[0] = time.time()

    @api.every(5)
    def tick():
        if not api.get("enabled", True):
            return
        minutes = max(1.0, float(api.get("minutes", 10)))
        if time.time() - _last[0] < minutes * 60:
            return
        _last[0] = time.time()
        msg = api.get("message", DEFAULT_MSG)
        api.say(msg)
        api.flash(msg, "info", 8)

    @api.command("announce_now", help="Post the announcement on the next tick", mod_only=True)
    def now(ctx):
        _last[0] = 0.0

    def panel(parent):
        bg = parent["bg"]
        row1 = tk.Frame(parent, bg=bg)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="Message", width=10, anchor="w", bg=bg, fg="#8C95A3").pack(side="left")
        msg = tk.Entry(row1)
        msg.insert(0, api.get("message", DEFAULT_MSG))
        msg.pack(side="left", fill="x", expand=True, padx=6)
        row2 = tk.Frame(parent, bg=bg)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="Every (min)", width=10, anchor="w", bg=bg, fg="#8C95A3").pack(side="left")
        mins = tk.Entry(row2, width=6)
        mins.insert(0, str(api.get("minutes", 10)))
        mins.pack(side="left", padx=6)
        on = tk.BooleanVar(value=bool(api.get("enabled", True)))
        tk.Checkbutton(row2, text="Enabled", variable=on, bg=bg, fg="#D3D8DF", selectcolor=bg,
                       activebackground=bg).pack(side="left", padx=10)

        def save():
            try:
                m = max(1.0, float(mins.get()))
            except ValueError:
                api.toast("Minutes must be a number", "bad")
                return
            api.set("message", msg.get().strip() or DEFAULT_MSG)
            api.set("minutes", m)
            api.set("enabled", bool(on.get()))
            api.toast("Announcer saved", "ok")
        tk.Button(row2, text="Save", command=save).pack(side="right")

    api.add_panel(panel, "Settings")
