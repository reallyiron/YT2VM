import tkinter as tk

# command -> chain of normal YT2VM viewer commands
SHORTCUTS = {
    "copy": "!combo ctrl+c",
    "paste": "!combo ctrl+v",
    "cut": "!combo ctrl+x",
    "undo": "!combo ctrl+z",
    "redo": "!combo ctrl+y",
    "selectall": "!combo ctrl+a",
    "save": "!combo ctrl+s",
    "closetab": "!combo ctrl+w",
    "newtab": "!combo ctrl+t",
    "desktop": "!combo win+d",
    "taskmgr": "!combo ctrl+shift+esc",
    "explorer": "!combo win+e",
    "alttab": "!combo alt+tab",
}


def setup(api):
    for name, chain in SHORTCUTS.items():
        def handler(ctx, chain=chain):
            ctx.run(chain)
        api.command(name, help=chain)(handler)

    def panel(parent):
        text = "\n".join(f"!{k:<11} {v}" for k, v in SHORTCUTS.items())
        tk.Label(parent, text=text, justify="left", anchor="w", bg=parent["bg"], fg="#D3D8DF",
                 font=("Consolas", 9)).pack(fill="x")

    api.add_panel(panel, "Mappings")
