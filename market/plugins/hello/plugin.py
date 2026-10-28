import tkinter as tk


def setup(api):
    @api.command("hello", help="Say hi to the viewer")
    def hello(ctx):
        greeting = api.get("greeting", "Hello")
        ctx.reply(f"{greeting}, {ctx.user}!")

    def panel(parent):
        bg = parent["bg"]
        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x")
        tk.Label(row, text="Greeting", bg=bg, fg="#8C95A3").pack(side="left")
        entry = tk.Entry(row, width=24)
        entry.insert(0, api.get("greeting", "Hello"))
        entry.pack(side="left", padx=8)

        def save():
            api.set("greeting", entry.get().strip() or "Hello")
            api.toast("Greeting saved", "ok")
        tk.Button(row, text="Save", command=save).pack(side="left")

    api.add_panel(panel, "Settings")
