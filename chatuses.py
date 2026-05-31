import tkinter as tk
from tkinter import scrolledtext, ttk, filedialog, messagebox
import threading, time, sys, traceback, random, subprocess, os, re, json, platform, ctypes, collections, math, gc, queue, shutil, signal
import urllib.request, urllib.error, urllib.parse
from ctypes import wintypes

sys.coinit_flags = 0

try:
    import pythoncom
except ImportError:
    pass

try:
    import virtualbox
    vbox_pkg = "virtualbox"
except ImportError:
    try:
        from vboxapi import VirtualBoxManager
        vbox_pkg = "vboxapi"
    except ImportError:
        vbox_pkg = None

if platform.system() == "Darwin":
    class MacLabelButton(tk.Label):
        def __init__(self, master=None, cnf={}, **kw):
            cmd = kw.pop('command', None)
            abg = kw.pop('activebackground', None)
            afg = kw.pop('activeforeground', None)
            bg = kw.get('bg', kw.get('background', '#18181B'))
            fg = kw.get('fg', kw.get('foreground', 'white'))
            kw.pop('bd', None)
            kw.pop('relief', None)
            super().__init__(master, cnf, **kw)
            self.config(cursor="hand2")
            if cmd:
                self.bind("<Button-1>", lambda e: cmd())
            if abg:
                self.bind("<Enter>", lambda e: self.config(bg=abg, fg=afg or fg))
            self.bind("<Leave>", lambda e: self.config(bg=bg, fg=fg))
    tk.Button = MacLabelButton

try:
    import obsws_python as obs
    obs_available = True
except ImportError:
    obs_available = False

try:
    from flask import Flask, jsonify, render_template_string
    import logging as flask_logging
    flask_available = True
except ImportError:
    flask_available = False

try:
    import pytchat
    pytchat_available = True
except ImportError:
    pytchat_available = False

instance_id = 1
for arg in sys.argv:
    if arg == "--multistream":
        instance_id = 2
    elif arg.startswith("--multistream") and arg != "--multistream":
        try:
            instance_id = int(arg.replace("--multistream", "")) + 1
        except Exception:
            pass

is_multistream = instance_id > 1
flask_port = 5000 + instance_id - 1
version = "v43.0.vbox.only"

suffix = f"_multi{instance_id-1}" if instance_id > 2 else ("_multi" if instance_id == 2 else "")
settings_file = f"settings{suffix}.json"
stats_file = f"stats{suffix}.json"
log_file = f"server_log{suffix}.txt"
snap_file = f"snapshot{suffix}.txt"
session_file = f"session{suffix}.txt"
logs_file = f"logs{suffix}.json"
modlogs_file = f"modlogsandownerlogs{suffix}.json"
allmsglogs_file = f"allmsglogs{suffix}.json"
voteslogs_file = f"voteslogs{suffix}.json"
scancodes_file = "keycodes.json"

refresh_rate = 100  
keyboard_layout = "US" 
available_layouts = ["US", "UK", "DANISH", "TURKISH", "GERMAN", "FRENCH"]
vote_timeout = 60

obs_host = "localhost"
obs_port = 4454 + instance_id  
obs_password = ""  
obs_scene_main = "main2" if is_multistream else "main"
obs_scene_revert = "revert2" if is_multistream else "revert"
obs_scene_error = "serverdown2" if is_multistream else "serverdown"
obs_scene_changevm = "changevm2" if is_multistream else "changevm"
obs_scene_starting = "starting2" if is_multistream else "starting"

admins = [] 
owners = []
announcement_data = {"id": 0, "author": "reallyiron", "message": ""}

gui_log_queue = queue.Queue(maxsize=300)
log_lock = threading.Lock()

possible_paths = [
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
    "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage",
    "/usr/bin/VBoxManage",
    "/usr/local/bin/VBoxManage",
    "VBoxManage"
]

vbox_manage_cmd = "VBoxManage"
for path in possible_paths:
    if os.path.exists(path):
        vbox_manage_cmd = path
        break

def get_all_vbox_vms(vbox_path="VBoxManage"):
    vms = []
    try:
        res = subprocess.run([vbox_path, "list", "vms"], capture_output=True, text=True, timeout=2)
        for line in res.stdout.splitlines():
            if '"' in line:
                vms.append(line.split('"')[1])
    except Exception:
        pass
    return vms if vms else ["Windows10ChatVm", "Windows8ChatVm"]

def get_vbox_snapshots(vbox_path, vm_name):
    snaps = []
    try:
        res = subprocess.run([vbox_path, "snapshot", vm_name, "list"], capture_output=True, text=True, timeout=2)
        for line in res.stdout.splitlines():
            if "Name:" in line and "(UUID:" in line:
                part = line.split("Name:")[1].split("(UUID:")[0].strip()
                if part:
                    snaps.append(part)
    except Exception:
        pass
    return snaps

available_vms = get_all_vbox_vms(vbox_manage_cmd)
vm_name = "Windows10ChatVm"
if available_vms:
    if len(available_vms) >= instance_id:
        vm_name = available_vms[instance_id - 1]
    else:
        vm_name = available_vms[0]

default_blocked_terms = [] 
banned_words = []
custom_commands = {}

default_keydata = {
    "RAW": {
        "esc": [1], "1": [2], "2": [3], "3": [4], "4": [5], "5": [6], "6": [7], "7": [8], "8": [9], "9": [10], "0": [11], 
        "-": [12], "=": [13], "backspace": [14], "tab": [15], "q": [16], "w": [17], "e": [18], "r": [19], "t": [20], "y": [21], 
        "u": [22], "i": [23], "o": [24], "p": [25], "[": [26], "]": [27], "enter": [28], "ctrl": [29], "lctrl": [29], "rctrl": [224, 29], 
        "a": [30], "s": [31], "d": [32], "f": [33], "g": [34], "h": [35], "j": [36], "k": [37], "l": [38], ";": [39], "'": [40], "`": [41], 
        "shift": [42], "lshift": [42], "\\": [43], "z": [44], "x": [45], "c": [46], "v": [47], "b": [48], "n": [49], "m": [50], 
        ",": [51], ".": [52], "/": [53], "rshift": [54], "alt": [56], "lalt": [56], "ralt": [224, 56], "space": [57], "capslock": [58], 
        "f1": [59], "f2": [60], "f3": [61], "f4": [62], "f5": [63], "f6": [64], "f7": [65], "f8": [66], "f9": [67], "f10": [68], "f11": [87], "f12": [88], 
        "numlock": [69], "scrolllock": [70], "home": [224, 71], "up": [224, 72], "pageup": [224, 73], "left": [224, 75], 
        "right": [224, 77], "end": [224, 79], "down": [224, 80], "pagedown": [224, 81], "insert": [224, 82], "delete": [224, 83], "del": [224, 83], 
        "win": [224, 91], "lwin": [224, 91], "rwin": [224, 92], "cmd": [224, 91], "super": [224, 91], "menu": [224, 93], "plus": [13], "minus": [12], "return": [28],
        "numpad0": [82], "numpad1": [79], "numpad2": [80], "numpad3": [81], "numpad4": [75], "numpad5": [76], "numpad6": [77], 
        "numpad7": [71], "numpad8": [72], "numpad9": [73], "numpad_dot": [83], "numpad_enter": [224, 28], "numpad_plus": [78], 
        "numpad_minus": [74], "numpad_mul": [55], "numpad_div": [224, 53], "printscreen": [224, 55, 224, 183], "pause": [225, 29, 69, 225, 157, 197],
        "vol_mute": [224, 32], "vol_down": [224, 46], "vol_up": [224, 48], "media_next": [224, 25], "media_prev": [224, 16], "media_stop": [224, 36], "media_play_pause": [224, 34]
    },
    "LAYOUTS": {
        "US": {"noshift": {'1':[0x02], '2':[0x03], '3':[0x04], '4':[0x05], '5':[0x06], '6':[0x07], '7':[0x08], '8':[0x09], '9':[0x0A], '0':[0x0B], 'q':[0x10], 'w':[0x11], 'e':[0x12], 'r':[0x13], 't':[0x14], 'y':[0x15], 'u':[0x16], 'i':[0x17], 'o':[0x18], 'p':[0x19], 'a':[0x1E], 's':[0x1F], 'd':[0x20], 'f':[0x21], 'g':[0x22], 'h':[0x23], 'j':[0x24], 'k':[0x25], 'l':[0x26], 'z':[0x2C], 'x':[0x2D], 'c':[0x2E], 'v':[0x2F], 'b':[0x30], 'n':[0x31], 'm':[0x32], ' ':[0x39], '-':[0x0C], '=':[0x0D], '[':[0x1A], ']':[0x1B], '\\':[0x2B], ';':[0x27], '\'':[0x28], '`':[0x29], ',':[0x33], '.':[0x34], '/':[0x35]}, "shift": {'!':[0x02], '@':[0x03], '#':[0x04], '$':[0x05], '%':[0x06], '^':[0x07], '&':[0x08], '*':[0x09], '(':[0x0A], ')':[0x0B], '_':[0x0C], '+':[0x0D], '{':[0x1A], '}':[0x1B], '|':[0x2B], ':':[0x27], '"':[0x28], '~':[0x29], '<':[0x33], '>':[0x34], '?':[0x35]}, "altgr": {}},
        "UK": {"noshift": {'1':[0x02], '2':[0x03], '3':[0x04], '4':[0x05], '5':[0x06], '6':[0x07], '7':[0x08], '8':[0x09], '9':[0x0A], '0':[0x0B], 'q':[0x10], 'w':[0x11], 'e':[0x12], 'r':[0x13], 't':[0x14], 'y':[0x15], 'u':[0x16], 'i':[0x17], 'o':[0x18], 'p':[0x19], 'a':[0x1E], 's':[0x1F], 'd':[0x20], 'f':[0x21], 'g':[0x22], 'h':[0x23], 'j':[0x24], 'k':[0x25], 'l':[0x26], 'z':[0x2C], 'x':[0x2D], 'c':[0x2E], 'v':[0x2F], 'b':[0x30], 'n':[0x31], 'm':[0x32], ' ':[0x39], '-':[0x0C], '=':[0x0D], '[':[0x1A], ']':[0x1B], '#':[0x2B], ';':[0x27], '\'':[0x28], '`':[0x29], ',':[0x33], '.':[0x34], '/':[0x35], '\\':[0x56]}, "shift": {'!':[0x02], '"':[0x03], '£':[0x04], '$':[0x05], '%':[0x06], '^':[0x07], '&':[0x08], '*':[0x09], '(':[0x0A], ')':[0x0B], '_':[0x0C], '+':[0x0D], '{':[0x1A], '}':[0x1B], '~':[0x2B], ':':[0x27], '@':[0x28], '¬':[0x29], '<':[0x33], '>':[0x34], '?':[0x35], '|':[0x56]}, "altgr": {'€':[0x05], '¦':[0x29]}},
        "DANISH": {"noshift": {'1':[0x02], '2':[0x03], '3':[0x04], '4':[0x05], '5':[0x06], '6':[0x07], '7':[0x08], '8':[0x09], '9':[0x0A], '0':[0x0B], 'q':[0x10], 'w':[0x11], 'e':[0x12], 'r':[0x13], 't':[0x14], 'y':[0x15], 'u':[0x16], 'i':[0x17], 'o':[0x18], 'p':[0x19], 'a':[0x1E], 's':[0x1F], 'd':[0x20], 'f':[0x21], 'g':[0x22], 'h':[0x23], 'j':[0x24], 'k':[0x25], 'l':[0x26], 'z':[0x2C], 'x':[0x2D], 'c':[0x2E], 'v':[0x2F], 'b':[0x30], 'n':[0x31], 'm':[0x32], ' ':[0x39], '+': [0x0C], '´': [0x0D], 'å': [0x1A], '¨': [0x1B], '\'': [0x2B], 'æ': [0x27], 'ø': [0x28], '½': [0x29], ',': [0x33], '.': [0x34], '-': [0x35], '<': [0x56]}, "shift": {'!':[0x02], '"':[0x03], '#':[0x04], '¤':[0x05], '%':[0x06], '&':[0x07], '/':[0x08], '(': [0x09], ')': [0x0A], '=': [0x0B], '?': [0x0C], '`': [0x0D], 'Å': [0x1A], '^': [0x1B], '*': [0x2B], 'Æ': [0x27], 'Ø': [0x28], '§': [0x29], ';': [0x33], ':': [0x34], '_': [0x35], '>': [0x56]}, "altgr": {'@':[0x03], '£':[0x04], '$':[0x05], '€':[0x12], '{':[0x08], '[':[0x09], ']':[0x0A], '}':[0x0B], '|':[0x0D], '~':[0x1B], '\\':[0x56], 'µ':[0x32]}},
        "TURKISH": {"noshift": {'1':[0x02], '2':[0x03], '3':[0x04], '4':[0x05], '5':[0x06], '6':[0x07], '7':[0x08], '8':[0x09], '9':[0x0A], '0':[0x0B], 'q':[0x10], 'w':[0x11], 'e':[0x12], 'r':[0x13], 't':[0x14], 'y':[0x15], 'u':[0x16], 'i':[0x17], 'o':[0x18], 'p':[0x19], 'a':[0x1E], 's':[0x1F], 'd':[0x20], 'f':[0x21], 'g':[0x22], 'h':[0x23], 'j':[0x24], 'k':[0x25], 'l':[0x26], 'z':[0x2C], 'x':[0x2D], 'c':[0x2E], 'v':[0x2F], 'b':[0x30], 'n':[0x31], 'm':[0x32], ' ':[0x39], 'ı': [0x17], 'i': [0x28], '*': [0x0C], '-': [0x0D], 'ğ': [0x1A], 'ü': [0x1B], ',': [0x2B], 'ş': [0x27], '"': [0x29], 'ö': [0x33], 'ç': [0x34], '.': [0x35], '<': [0x56]}, "shift": {'!':[0x02], '\'':[0x03], '^':[0x04], '+':[0x05], '%':[0x06], '&':[0x07], '/':[0x08], '(': [0x09], ')': [0x0A], '=': [0x0B], '?': [0x0C], '_': [0x0D], 'I': [0x17], 'İ': [0x28], 'Ğ': [0x1A], 'Ü': [0x1B], ';': [0x2B], 'Ş': [0x27], 'é': [0x29], 'Ö': [0x33], 'Ç': [0x34], ':': [0x35], '>': [0x56]}, "altgr": {'>':[0x02], '£':[0x03], '#':[0x04], '$':[0x05], '½':[0x06], '{':[0x08], '[':[0x09], ']':[0x0A], '}':[0x0B], '\\':[0x0C], '|':[0x0D], '~':[0x1B], '´':[0x27], '₺':[0x14], 'æ':[0x1E], 'ß':[0x1F], '`':[0x2B]}},
        "GERMAN": {"noshift": {'1':[0x02], '2':[0x03], '3':[0x04], '4':[0x05], '5':[0x06], '6':[0x07], '7':[0x08], '8':[0x09], '9':[0x0A], '0':[0x0B], 'q':[0x10], 'w':[0x11], 'e':[0x12], 'r':[0x13], 't':[0x14], 'y':[0x2C], 'u':[0x16], 'i':[0x17], 'o':[0x18], 'p':[0x19], 'a':[0x1E], 's':[0x1F], 'd':[0x20], 'f':[0x21], 'g':[0x22], 'h':[0x23], 'j':[0x24], 'k':[0x25], 'l':[0x26], 'z':[0x15], 'x':[0x2D], 'c':[0x2E], 'v':[0x2F], 'b':[0x30], 'n':[0x31], 'm':[0x32], ' ':[0x39], 'ß': [0x0C], '´': [0x0D], 'ü': [0x1A], '+': [0x1B], '#': [0x2B], 'ö': [0x27], 'ä': [0x28], '^': [0x29], ',': [0x33], '.': [0x34], '-': [0x35], '<': [0x56]}, "shift": {'!':[0x02], '"':[0x03], '§':[0x04], '$':[0x05], '%':[0x06], '&':[0x07], '/':[0x08], '(': [0x09], ')': [0x0A], '=': [0x0B], '?': [0x0C], '`': [0x0D], 'Ü': [0x1A], '*': [0x1B], '\'': [0x2B], 'Ö': [0x27], 'Ä': [0x28], '°': [0x29], ';': [0x33], ':': [0x34], '_': [0x35], '>': [0x56]}, "altgr": {'²':[0x03], '³':[0x04], '{':[0x08], '[':[0x09], ']':[0x0A], '}':[0x0B], '\\':[0x0C], '@':[0x10], '€':[0x12], '~':[0x1B], 'µ':[0x32], '|':[0x56]}},
        "FRENCH": {"noshift": {'1':[0x02], '2':[0x03], '3':[0x04], '4':[0x05], '5':[0x06], '6':[0x07], '7':[0x08], '8':[0x09], '9':[0x0A], '0':[0x0B], 'q':[0x1E], 'w':[0x2C], 'e':[0x12], 'r':[0x13], 't':[0x14], 'y':[0x15], 'u':[0x16], 'i':[0x17], 'o':[0x18], 'p':[0x19], 'a':[0x10], 's':[0x1F], 'd':[0x20], 'f':[0x21], 'g':[0x22], 'h':[0x23], 'j':[0x24], 'k':[0x25], 'l':[0x26], 'z':[0x11], 'x':[0x2D], 'c':[0x2E], 'v':[0x2F], 'b':[0x30], 'n':[0x31], 'm':[0x27], ' ':[0x39], '&': [0x02], 'é': [0x03], '"': [0x04], '\'': [0x05], '(': [0x06], '-': [0x07], 'è': [0x08], '_': [0x09], 'ç': [0x0A], 'à': [0x0B], ')': [0x0C], '=': [0x0D], '^': [0x1A], '$': [0x1B], '*': [0x2B], 'ù': [0x28], '²': [0x29], ',': [0x32], ';': [0x33], ':': [0x34], '!': [0x35], '<': [0x56]}, "shift": {'1':[0x02], '2':[0x03], '3':[0x04], '4':[0x05], '5':[0x06], '6':[0x07], '7':[0x08], '8':[0x09], '9':[0x0A], '0':[0x0B], '°': [0x0C], '+': [0x0D], '¨': [0x1A], '£': [0x1B], 'µ': [0x2B], '%': [0x28], '?': [0x32], '.': [0x33], '/': [0x34], '§': [0x35], '>': [0x56]}, "altgr": {'~':[0x03], '#':[0x04], '{':[0x05], '[':[0x06], '|':[0x07], '`':[0x08], '\\':[0x09], '^':[0x0A], '@':[0x0B], ']':[0x0C], '}':[0x0D], '¤':[0x1B], '€':[0x12]}}
    }
}

_needs_update = False
if os.path.exists(scancodes_file):
    try:
        with open(scancodes_file, "r", encoding="utf-8") as f:
            _loaded_data = json.load(f)
        if "LAYOUTS" not in _loaded_data or "RAW" not in _loaded_data:
            _needs_update = True
        else:
            for lang, layout_dict in default_keydata["LAYOUTS"].items():
                if lang not in _loaded_data["LAYOUTS"]:
                    _loaded_data["LAYOUTS"][lang] = layout_dict
                    _needs_update = True
            for key, key_data in default_keydata["RAW"].items():
                if key not in _loaded_data["RAW"]:
                    _loaded_data["RAW"][key] = key_data
                    _needs_update = True
    except Exception:
        _loaded_data = default_keydata.copy()
        _needs_update = True
else:
    _loaded_data = default_keydata.copy()
    _needs_update = True

if _needs_update:
    try:
        with open(scancodes_file, "w", encoding="utf-8") as f:
            json.dump(_loaded_data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

scancodes = _loaded_data["RAW"]
_layouts = _loaded_data["LAYOUTS"]

def get_typed_codes(char, layout="US"):
    SHIFT = [[0x2A]]
    ALTGR = [[0x1D], [0xE0, 0x38]]
    target = _layouts.get(layout, _layouts["US"])
    active_no = target.get("noshift", {})
    active_sh = target.get("shift", {})
    active_al = target.get("altgr", {})
    
    if char in active_sh:
        return (SHIFT, active_sh[char])
    if char in active_al:
        return (ALTGR, active_al[char])
    if char in active_no:
        return ([], active_no[char])
        
    char_lower = char.lower()
    if char.isupper() and char_lower in active_no:
        return (SHIFT, active_no[char_lower])
    if char_lower != char and char_lower in active_no:
        return (SHIFT, active_no[char_lower])
    if char_lower in active_no:
        return ([], active_no[char_lower])
        
    us = _layouts["US"]
    if char in us["shift"]:
        return (SHIFT, us["shift"][char])
    if char in us["noshift"]:
        return ([], us["noshift"][char])
    if char.isupper() and char_lower in us["noshift"]:
        return (SHIFT, us["noshift"][char_lower])
    if char_lower in us["noshift"]:
        return ([], us["noshift"][char_lower])
        
    return ([], [0])

def safe_json_dump(filename, data):
    tmp_file = filename + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_file, filename)
    except Exception:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

def append_to_json_log(filename, user, command):
    try:
        with log_lock:
            entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "username": user, "command": command}
            logs = []
            if os.path.exists(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                except Exception:
                    pass
            logs.append(entry)
            if len(logs) > 1000:
                logs = logs[-1000:]
            safe_json_dump(filename, logs)
    except Exception:
        pass

def append_to_all_msgs_log(user, msg):
    try:
        with log_lock:
            entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "username": user, "message": msg}
            with open(allmsglogs_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def log_vote_action(action, user, vote_type, target, current_votes=0):
    try:
        with log_lock:
            entry = {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "action": action.lower(),
                "user": user,
                "vote": vote_type,
                "progress": f"{current_votes}/{target}" if current_votes else str(target)
            }
            logs = []
            if os.path.exists(voteslogs_file):
                try:
                    with open(voteslogs_file, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                except Exception:
                    pass
            logs.append(entry)
            if len(logs) > 1000:
                logs = logs[-1000:]
            safe_json_dump(voteslogs_file, logs)
    except Exception:
        pass

def console_log(level, msg):
    timestamp = time.strftime("%H:%M:%S")
    date_stamp = time.strftime("%Y-%m-%d")
    log_line = f"[{timestamp}] [{level.lower()}] {msg.lower()}"
    print(log_line, flush=True)
    try:
        gui_log_queue.put_nowait((level, log_line))
    except queue.Full:
        pass
    try:
        with log_lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{date_stamp} {timestamp}] [{level.lower()}] {msg.lower()}\n")
    except Exception:
        pass

global_msg_id = 0
web_chat_history = collections.deque(maxlen=50)
history_lock = threading.Lock()
messages_buffer = collections.deque(maxlen=200)
buffer_lock = threading.Lock()
script_start_time = time.time()
total_commands_executed = 0
total_commands_failed = 0
stats_lock = threading.Lock()

try:
    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            _saved = json.load(f)
            total_commands_executed = _saved.get("commands", 0)
            total_commands_failed = _saved.get("failed", 0)
            script_start_time = time.time() - _saved.get("uptime", 0)
except Exception:
    pass

def save_stats():
    try:
        uptime = int(time.time() - script_start_time)
        with stats_lock:
            tmp_file = stats_file + ".tmp"
            with open(tmp_file, "w") as f:
                json.dump({
                    "uptime": uptime,
                    "commands": total_commands_executed,
                    "failed": total_commands_failed,
                    "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
                }, f)
            os.replace(tmp_file, stats_file)
    except Exception:
        pass

current_status = "initializing..."
current_vote_info = {"active": False, "text": ""}
current_viewers = "0"
current_likes = "0"
overlay_chat_visible = True
split_overlay_mode = False

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print("\n==================================================")
    print("critical script error encountered:")
    print("==================================================")
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    print("==================================================\n")
    try:
        with open("crash_log.txt", "w") as f:
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    except Exception:
        pass
    set_obs_scene(obs_scene_error)
sys.excepthook = handle_exception

def clean_text(text):
    if not isinstance(text, str): return str(text)
    return ''.join(c for c in text if c <= '\uFFFF')

def escape_html(text):
    if not isinstance(text, str): return str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

def add_to_history(user, msg, tag, is_mod=False, is_owner=False):
    global global_msg_id
    global_msg_id += 1
    safe_user = escape_html(user)
    safe_msg = escape_html(msg)
    msg_obj = {
        "id": global_msg_id,
        "u": safe_user,
        "m": safe_msg,
        "t": tag,
        "is_admin": is_mod,
        "is_owner": is_owner
    }
    with buffer_lock:
        messages_buffer.append(msg_obj)
    with history_lock:
        web_chat_history.append(msg_obj)

def set_obs_scene(scene_name):
    try:
        if not obs_available: return
        def _switch():
            try:
                if obs_password:
                    cl = obs.ReqClient(host=obs_host, port=obs_port, password=obs_password, timeout=3)
                else:
                    cl = obs.ReqClient(host=obs_host, port=obs_port, timeout=3)
                cl.set_current_program_scene(scene_name)
            except Exception:
                pass
        threading.Thread(target=_switch, daemon=True).start()
    except Exception:
        pass

if flask_available:
    obs_web_overlay_app = Flask(__name__)
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)
    
    @obs_web_overlay_app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    html_index = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>chat controls</title>
        <style>
            body { background: #09090b; color: #00E5FF; font-family: 'Segoe UI', Consolas, monospace; text-align: center; padding: 40px; }
            h1 { color: #10B981; font-size: 36px; text-shadow: 0 0 10px rgba(16,185,129,0.3); margin-bottom: 5px; }
            .grid { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; max-width: 800px; margin: 40px auto; }
            a { background: #18181b; border: 1px solid #27272a; color: #fff; text-decoration: none; padding: 20px; border-radius: 12px; width: 300px; transition: all 0.2s; box-shadow: 0 4px 6px rgba(0,0,0,0.3); text-align: left; }
            a:hover { transform: translateY(-5px); border-color: #00E5FF; box-shadow: 0 8px 15px rgba(0,229,255,0.2); }
            .title { font-size: 20px; font-weight: bold; margin-bottom: 10px; color: #00E5FF; }
            .desc { font-size: 14px; color: #a1a1aa; }
        </style>
    </head>
    <body>
        <h1>[active] chat server active</h1>
        <p style="color:#71717a;font-size:18px">add one of these links to your obs browser source:</p>
        <div class="grid">
            <a href="/obsnew"><div class="title">liquid glass chat (/obsnew)</div><div class="desc">sleek gray bubbles with a glass background.</div></a>
            <a href="/oldobsnew"><div class="title">classic dark chat (/oldobsnew)</div><div class="desc">the og dark background modern chat.</div></a>
            <a href="/ultrachat"><div class="title">ultra chat (/ultrachat)</div><div class="desc">pure old basic chat with material 3 mod icons.</div></a>
            <a href="/announcement"><div class="title">announcements (/announcement)</div><div class="desc">animated popup for server announcements.</div></a>
            <a href="/stats"><div class="title">live stats (/stats)</div><div class="desc">viewers, likes, and uptime widget.</div></a>
            <a href="/obs"><div class="title">legacy chat (/obs)</div><div class="desc">the original transparent overlay.</div></a>
        </div>
    </body>
    </html>
    """
    
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');
            @keyframes slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
            html, body { background-color: rgba(0,0,0,0) !important; margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden; }
            body { font-family: 'Fira Code', 'Consolas', monospace; display: flex; flex-direction: column; padding: 10px; text-shadow: 2px 2px 0 #000; color: #ccc; font-size: 16px; justify-content: flex-end; }
            .header { position: absolute; top: 10px; right: 10px; text-align: right; display: flex; flex-direction: column; align-items: flex-end; z-index: 10; }
            div[id="vote-text"] { font-family: 'Impact', sans-serif; font-size: 24px; color: red; text-transform: uppercase; margin-bottom: 5px; text-shadow: 2px 2px 0 #000; background: rgba(0,0,0,0.85); padding: 5px 12px; border: 1px solid #444; border-radius: 4px; display: none; }
            .stats-container { display: flex; gap: 15px; font-family: 'Fira Code', monospace; font-weight: bold; font-size: 20px; align-items: center; background: rgba(0,0,0,0.85); padding: 5px 12px; border: 1px solid #444; border-radius: 4px; }
            .stat-item { display: flex; align-items: center; gap: 6px; }
            .icon-eye { fill: #0af; width: 22px; height: 22px; filter: drop-shadow(0 0 2px #0af); }
            .icon-thumb { fill: #0f0; width: 22px; height: 22px; filter: drop-shadow(0 0 2px #0f0); }
            .stat-text { color: #fff; text-shadow: 0 0 2px #fff; }
            .chat-box { flex-grow: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: flex-end; padding-bottom: 10px; z-index: 5; }
            .line { font-size: 18px; font-weight: 500; margin-bottom: 3px; color: #fff; line-height: 1.3; word-wrap: break-word; overflow-wrap: break-word; display: flex; align-items: flex-start; justify-content: flex-end; width: 100%; animation: slideIn 0.2s ease-out forwards; }
            .admin-name { color: #5e84f1; font-weight: 700; text-shadow: 0 0 3px #5e84f1; }
            .owner-name { color: #ffd700; font-weight: 700; text-shadow: 0 0 3px #ffd700; }
            .user-name { color: #e0e0e0; font-weight: 700; }
            .sys-text { color: #f0f; font-weight: 700; text-shadow: 0 0 3px #f0f; }
            .sys-msg-text { color: #0f0; font-weight: bold; }
            .err-text { color: #f33; font-weight: bold; }
            .msg-text { color: #fff; }
            .separator { margin-right: 8px; color: #888; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="header">
            <div id="vote-text">no active votes</div>
            <div class="stats-container">
                <div class="stat-item">
                    <svg class="icon-eye" viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.61 11 7.61s9.27-3.22 11-7.61C21.27 7.61 17 4.5 12 4.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
                    <span id="viewers" class="stat-text">0</span>
                </div>
                <div class="stat-item">
                    <svg class="icon-thumb" viewBox="0 0 24 24"><path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-1.91l-.01-.01L23 10z"/></svg>
                    <span id="likes" class="stat-text">0</span>
                </div>
            </div>
        </div>
        <div class="chat-box" id="chat"></div>
        <script>
            let lastId = -1;
            let fetchingUpdates = false;
            setInterval(function(){
                if(fetchingUpdates) return;
                fetchingUpdates = true;
                fetch('/history?t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    if(data && Array.isArray(data)){
                        const c = document.getElementById('chat');
                        if(!c) return;
                        const fragment = document.createDocumentFragment();
                        let added = false;
                        data.forEach(i => {
                            if(i.id > lastId){
                                lastId = i.id;
                                try {
                                    let nameClass = "user-name";
                                    let msgClass = "msg-text";
                                    if(i.is_owner) { nameClass = "owner-name"; }
                                    else if(i.is_admin) { nameClass = "admin-name"; }
                                    let u = i.u || "Unknown";
                                    let m = i.m || "";
                                    if(u === '[system]' || u === 'system'){
                                        u = "[system]";
                                        nameClass = "sys-text";
                                        msgClass = m.includes("[err]") ? "err-text" : "sys-msg-text";
                                    } else if(u === '[console]' || u === '[announcement]') {
                                        nameClass = "admin-name";
                                    } else {
                                        if(typeof u === 'string' && !u.startsWith('@')) u = "@" + u;
                                    }
                                    const div = document.createElement('div');
                                    div.className = 'line';
                                    div.innerHTML = `<span class='${nameClass}'>${u}</span><span class="separator">:</span><span class='${msgClass}'>${m}</span>`;
                                    fragment.appendChild(div);
                                    added = true;
                                } catch(err){}
                            }
                        });
                        if(added){
                            c.appendChild(fragment);
                            window.scrollTo(0, document.body.scrollHeight);
                            while(c.children.length > 50) c.removeChild(c.firstChild);
                        }
                    }
                    fetchingUpdates = false;
                }).catch(e => { fetchingUpdates = false; });
            }, 1000);
            
            let fetchingStatus = false;
            setInterval(function(){
                if(fetchingStatus) return;
                fetchingStatus = true;
                fetch('/status_update?t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    try {
                        const v = document.getElementById('vote-text');
                        const chatBox = document.getElementById('chat');
                        const headerBox = document.querySelector('.header');
                        if(chatBox){ chatBox.style.display = data.chat_visible ? 'flex' : 'none'; }
                        if(headerBox){
                            if(data.split_mode){
                                headerBox.style.display = 'none';
                            } else {
                                headerBox.style.display = 'flex';
                                if(v && data.vote && data.vote.active){
                                    v.innerHTML = (data.vote.text || "").replace('[vote]', '');
                                    v.style.display = "block";
                                } else if(v) {
                                    v.style.display = "none";
                                }
                                const viewEl = document.getElementById('viewers');
                                const likeEl = document.getElementById('likes');
                                if(viewEl) viewEl.innerText = data.viewers || "0";
                                if(likeEl) likeEl.innerText = data.likes || "0";
                            }
                        }
                    } catch(err){}
                    fetchingStatus = false;
                }).catch(e => { fetchingStatus = false; });
            }, 2000);
        </script>
    </body>
    </html>
    """

    html_template_2 = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');
            html, body { background-color: rgba(0,0,0,0) !important; margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden; }
            body { font-family: 'Fira Code', 'Consolas', monospace; display: flex; flex-direction: column; align-items: flex-end; padding: 3vw; box-sizing: border-box; }
            .header { text-align: right; display: flex; flex-direction: column; align-items: flex-end; }
            div[id="vote-text"] { font-family: 'Impact', sans-serif; font-size: 10vw; color: red; text-transform: uppercase; margin-bottom: 2vw; text-shadow: 0.5vw 0.5vw 0 #000; display: none; line-height: 1; }
            .stats-container { display: flex; gap: 5vw; font-family: 'Fira Code', monospace; font-weight: bold; font-size: 8vw; align-items: center; }
            .stat-item { display: flex; align-items: center; gap: 2vw; }
            .icon-eye { fill: #0af; width: 9vw; height: 9vw; filter: drop-shadow(0.4vw 0.4vw 0 #000); }
            .icon-thumb { fill: #0f0; width: 9vw; height: 9vw; filter: drop-shadow(0.4vw 0.4vw 0 #000); }
            .stat-text { color: #fff; text-shadow: 0.4vw 0.4vw 0 #000; }
        </style>
    </head>
    <body>
        <div class="header">
            <div id="vote-text"></div>
            <div class="stats-container">
                <div class="stat-item">
                    <svg class="icon-eye" viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.61 11 7.61s9.27-3.22 11-7.61C21.27 7.61 17 4.5 12 4.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg>
                    <span id="viewers" class="stat-text">0</span>
                </div>
                <div class="stat-item">
                    <svg class="icon-thumb" viewBox="0 0 24 24"><path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-1.91l-.01-.01L23 10z"/></svg>
                    <span id="likes" class="stat-text">0</span>
                </div>
            </div>
        </div>
        <script>
            let fetchingStatus2 = false;
            setInterval(function(){
                if(fetchingStatus2) return;
                fetchingStatus2 = true;
                fetch('/status_update?t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    try {
                        const v = document.getElementById('vote-text');
                        if(data.vote && data.vote.active){
                            v.innerHTML = (data.vote.text || "").replace('[vote] ', '');
                            v.style.display = "block";
                        } else if(v) {
                            v.style.display = "none";
                        }
                        const viewEl = document.getElementById('viewers');
                        const likeEl = document.getElementById('likes');
                        if(viewEl) viewEl.innerText = data.viewers || "0";
                        if(likeEl) likeEl.innerText = data.likes || "0";
                    } catch(err){}
                    fetchingStatus2 = false;
                }).catch(e => { fetchingStatus2 = false; });
            }, 2000);
        </script>
    </body>
    </html>
    """

    html_template_new = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            html, body { background-color: rgba(0,0,0,0) !important; margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; }
            body { font-family: '-apple-system', 'BlinkMacSystemFont', 'Inter', sans-serif; display: flex; flex-direction: column; padding: 25px; justify-content: flex-end; box-sizing: border-box; }
            .chat-box { display: flex; flex-direction: column; align-items: flex-end; gap: 16px; width: 100%; }
            .msg-block { background: rgba(80,80,85,0.25); backdrop-filter: blur(25px) saturate(200%); -webkit-backdrop-filter: blur(25px) saturate(200%); padding: 12px 18px; display: flex; align-items: flex-start; font-size: 16px; border-radius: 22px; box-shadow: 0 8px 32px rgba(0,0,0,0.15), inset 0 1px 1px rgba(255,255,255,0.4); animation: popIn 0.35s cubic-bezier(0.175,0.885,0.32,1.2) forwards; max-width: 90%; word-wrap: break-word; border: 1px solid rgba(255,255,255,0.15); border-bottom: 1px solid rgba(255,255,255,0.05); }
            .msg-block.cmd-border { box-shadow: 0 8px 32px rgba(0,0,0,0.15), inset 0 1px 1px rgba(255,255,255,0.4), inset 4px 0 0 #00E5FF; }
            .msg-block.chat-border { box-shadow: 0 8px 32px rgba(0,0,0,0.15), inset 0 1px 1px rgba(255,255,255,0.4), inset 4px 0 0 #10B981; }
            .msg-block.vote-border { box-shadow: 0 8px 32px rgba(0,0,0,0.15), inset 0 1px 1px rgba(255,255,255,0.4), inset 4px 0 0 #F59E0B; }
            .msg-block.err-border { box-shadow: 0 8px 32px rgba(0,0,0,0.15), inset 0 1px 1px rgba(255,255,255,0.4), inset 4px 0 0 #EF4444; }
            .badge { padding: 4px 10px; font-weight: 800; font-size: 11px; border-radius: 20px; margin-right: 14px; flex-shrink: 0; align-self: center; color: #fff; letter-spacing: 0.8px; text-transform: uppercase; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
            .badge.cmd { background: linear-gradient(135deg, #00E5FF, #0083B0); }
            .badge.chat { background: linear-gradient(135deg, #10B981, #047857); }
            .badge.vote { background: linear-gradient(135deg, #F59E0B, #B45309); }
            .badge.err { background: linear-gradient(135deg, #EF4444, #991B1B); }
            .msg-content { display: flex; flex-direction: column; gap: 2px; }
            .username { font-weight: 700; font-size: 14px; letter-spacing: 0.3px; text-shadow: 0 1px 4px rgba(0,0,0,0.3); }
            .username.cmd { color: #40C4FF; }
            .username.chat { color: #34D399; }
            .username.vote { color: #FBBF24; }
            .username.err { color: #FF8A8A; }
            .message { color: #fff; font-weight: 500; line-height: 1.4; font-size: 16px; text-shadow: 0 1px 3px rgba(0,0,0,0.4); }
            @keyframes popIn { from { transform: translateY(20px) scale(0.95); opacity: 0; filter: blur(4px); } to { transform: translateY(0) scale(1); opacity: 1; filter: blur(0); } }
        </style>
    </head>
    <body>
        <div class="chat-box" id="chat"></div>
        <script>
            let lastId = -1;
            let fetchingUpdates = false;
            let hasConnected = false;
            setInterval(function(){
                if(fetchingUpdates) return;
                fetchingUpdates = true;
                fetch('/history?t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    try {
                        if(data && Array.isArray(data)){
                            const c = document.getElementById('chat');
                            if(c){
                                if(!hasConnected){
                                    hasConnected = true;
                                    const div = document.createElement('div');
                                    div.className = 'msg-block chat-border';
                                    div.innerHTML = `<div class="badge chat">SYS</div><div class="msg-content"><span class="username chat">system</span> <span class="message">ui connected successfully</span></div>`;
                                    c.appendChild(div);
                                }
                                const fragment = document.createDocumentFragment();
                                let added = false;
                                data.forEach(i => {
                                    if(i.id > lastId){
                                        lastId = i.id;
                                        try {
                                            let u = i.u || "Unknown";
                                            let m = i.m || "";
                                            if(u === '[system]' && !m.includes('vote') && !m.includes('[err]') && !m.includes('waiting') && !m.includes('ready') && !m.includes('chat listener') && !m.includes('running') && !m.includes('[ban]') && !m.includes('[warn]')) return;
                                            let isCmd = m.trim().startsWith('!');
                                            let badgeClass = isCmd ? 'cmd' : 'chat';
                                            let badgeText = isCmd ? 'CMD' : 'CHAT';
                                            let borderClass = isCmd ? 'cmd-border' : 'chat-border';
                                            let unameClass = isCmd ? 'username cmd' : 'username chat';
                                            let cleanU = u.replace(/^@+/, '');
                                            let displayU = '@' + cleanU;
                                            if(u === '[console]') {
                                                displayU = 'CONSOLE';
                                                badgeText = 'SYS';
                                            } else if(u === '[announcement]') {
                                                displayU = 'ANNOUNCEMENT';
                                                badgeText = 'INFO';
                                                badgeClass = 'cmd';
                                                borderClass = 'cmd-border';
                                                unameClass = 'username cmd';
                                            } else if(u === '[system]') {
                                                displayU = 'SYSTEM';
                                                badgeText = 'SYS';
                                                badgeClass = 'cmd';
                                                borderClass = 'cmd-border';
                                                unameClass = 'username cmd';
                                                if(m.includes('[vote]')){
                                                    badgeText = 'VOTE';
                                                    badgeClass = 'vote';
                                                    borderClass = 'vote-border';
                                                    unameClass = 'username vote';
                                                } else if(m.includes('[err]') || m.includes('[ban]') || m.includes('[warn]')){
                                                    badgeText = 'ERR';
                                                    badgeClass = 'err';
                                                    borderClass = 'err-border';
                                                    unameClass = 'username err';
                                                } else if(m.includes('running:')){
                                                    badgeText = 'EXEC';
                                                    badgeClass = 'cmd';
                                                    borderClass = 'cmd-border';
                                                    unameClass = 'username cmd';
                                                } else if(m.includes('[debug]')){
                                                    badgeText = 'DBG';
                                                    badgeClass = 'cmd';
                                                    borderClass = 'cmd-border';
                                                    unameClass = 'username cmd';
                                                }
                                            }
                                            const div = document.createElement('div');
                                            div.className = `msg-block ${borderClass}`;
                                            div.innerHTML = `<div class="badge ${badgeClass}">${badgeText}</div><div class="msg-content"><span class="${unameClass}">${displayU}</span> <span class="message">${m}</span></div>`;
                                            fragment.appendChild(div);
                                            added = true;
                                        } catch(err){}
                                    }
                                });
                                if(added){
                                    c.appendChild(fragment);
                                    window.scrollTo(0, document.body.scrollHeight);
                                    while(c.children.length > 15) c.removeChild(c.firstChild);
                                }
                            }
                        }
                    } finally {
                        fetchingUpdates = false;
                    }
                }).catch(e => { fetchingUpdates = false; });
            }, 1000);
        </script>
    </body>
    </html>
    """

    html_template_oldnew = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');
            html, body { background-color: rgba(0,0,0,0) !important; margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; }
            body { font-family: 'Fira Code', 'Consolas', monospace; display: flex; flex-direction: column; padding: 15px; justify-content: flex-end; box-sizing: border-box; }
            .chat-box { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; width: 100%; }
            .msg-block { background-color: rgba(0,0,0,0.85); padding: 6px 10px; display: flex; align-items: baseline; font-size: 16px; border-radius: 6px; box-shadow: 2px 2px 4px rgba(0,0,0,0.5); animation: slideIn 0.2s ease-out forwards; margin-bottom: 2px; max-width: 95%; word-wrap: break-word; }
            .msg-block.cmd-border { border-left: 5px solid #00e5ff; }
            .msg-block.chat-border { border-left: 5px solid #00e676; }
            .msg-block.vote-border { border-left: 5px solid orange; }
            .msg-block.err-border { border-left: 5px solid #f33; }
            .badge { padding: 2px 6px; font-weight: 800; color: #111; font-size: 11px; border-radius: 3px; margin-right: 8px; flex-shrink: 0; align-self: flex-start; margin-top: 3px; }
            .badge.cmd { background-color: #00e5ff; }
            .badge.chat { background-color: #00e676; }
            .badge.vote { background-color: orange; }
            .badge.err { background-color: #f33; color: #fff; }
            .msg-content { display: block; word-break: break-word; }
            .username { font-weight: 900; text-shadow: 1px 1px 0 rgba(0,0,0,0.8); margin-right: 5px; }
            .username.cmd { color: #00e5ff; }
            .username.chat { color: #00e676; }
            .username.vote { color: orange; }
            .username.err { color: #f33; }
            .message { color: #fff; font-weight: 600; text-shadow: 1px 1px 0 rgba(0,0,0,0.8); line-height: 1.4; }
            .owner-icon { width: 16px; height: 16px; fill: #ffd700; vertical-align: -3px; margin-right: 4px; }
            .mod-icon { width: 16px; height: 16px; fill: #58a6ff; vertical-align: -3px; margin-right: 4px; }
            @keyframes slideIn { from { transform: translateX(30px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        </style>
    </head>
    <body>
        <div class="chat-box" id="chat"></div>
        <script>
            let lastId = -1;
            let fetchingUpdates = false;
            let hasConnected = false;
            setInterval(function(){
                if(fetchingUpdates) return;
                fetchingUpdates = true;
                fetch('/history?t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    try {
                        if(data && Array.isArray(data)){
                            const c = document.getElementById('chat');
                            if(c){
                                if(!hasConnected){
                                    hasConnected = true;
                                    const div = document.createElement('div');
                                    div.className = 'msg-block cmd-border';
                                    div.innerHTML = `<div class="badge cmd">SYS</div><div class="msg-content"><span class="username cmd">system</span> <span class="message">connected</span></div>`;
                                    c.appendChild(div);
                                }
                                const fragment = document.createDocumentFragment();
                                let added = false;
                                data.forEach(i => {
                                    if(i.id > lastId){
                                        lastId = i.id;
                                        try {
                                            let u = i.u || "Unknown";
                                            let m = i.m || "";
                                            if(u === '[system]' && !m.includes('vote') && !m.includes('[debug]') && !m.includes('[err]') && !m.includes('waiting') && !m.includes('ready') && !m.includes('chat listener') && !m.includes('running') && !m.includes('[ban]') && !m.includes('[warn]')) return;
                                            let isCmd = m.trim().startsWith('!');
                                            let badgeClass = isCmd ? 'cmd' : 'chat';
                                            let badgeText = isCmd ? 'CMD' : 'CHAT';
                                            let borderClass = isCmd ? 'cmd-border' : 'chat-border';
                                            let unameClass = isCmd ? 'username cmd' : 'username chat';
                                            let cleanU = u.replace(/^@+/, '');
                                            let displayU = '@' + cleanU;
                                            
                                            let badgeIcon = "";
                                            if(i.is_owner || u.toLowerCase() === 'reallyiron') {
                                                badgeIcon = `<svg class='owner-icon' viewBox='0 0 24 24'><path d='M5 16h14l-1.5-9-3.5 4-2-5-2 5-3.5-4L5 16zm0 2h14v2H5v-2z'/></svg>`;
                                            } else if(i.is_admin) {
                                                badgeIcon = `<svg class='mod-icon' viewBox='0 0 24 24'><path d='M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z'/></svg>`;
                                            }
                                            displayU = badgeIcon + displayU;
                                            
                                            if(u === '[console]') {
                                                displayU = 'CONSOLE';
                                                badgeText = 'SYS';
                                            } else if(u === '[announcement]') {
                                                displayU = 'ANNOUNCEMENT';
                                                badgeText = 'INFO';
                                                badgeClass = 'cmd';
                                                borderClass = 'cmd-border';
                                                unameClass = 'username cmd';
                                            } else if(u === '[system]') {
                                                displayU = 'SYSTEM';
                                                badgeText = 'SYS';
                                                badgeClass = 'cmd';
                                                borderClass = 'cmd-border';
                                                unameClass = 'username cmd';
                                                if(m.includes('[vote]')){
                                                    badgeText = 'VOTE';
                                                    badgeClass = 'vote';
                                                    borderClass = 'vote-border';
                                                    unameClass = 'username vote';
                                                } else if(m.includes('[err]') || m.includes('[ban]') || m.includes('[warn]')){
                                                    badgeText = 'ERR';
                                                    badgeClass = 'err';
                                                    borderClass = 'err-border';
                                                    unameClass = 'username err';
                                                } else if(m.includes('running:')){
                                                    badgeText = 'EXEC';
                                                    badgeClass = 'cmd';
                                                    borderClass = 'cmd-border';
                                                    unameClass = 'username cmd';
                                                } else if(m.includes('[debug]')){
                                                    badgeText = 'DBG';
                                                    badgeClass = 'cmd';
                                                    borderClass = 'cmd-border';
                                                    unameClass = 'username cmd';
                                                }
                                            }
                                            const div = document.createElement('div');
                                            div.className = `msg-block ${borderClass}`;
                                            div.innerHTML = `<div class="badge ${badgeClass}">${badgeText}</div><div class="msg-content"><span class="${unameClass}">${displayU}</span> <span class="message">${m}</span></div>`;
                                            fragment.appendChild(div);
                                            added = true;
                                        } catch(err){}
                                    }
                                });
                                if(added){
                                    c.appendChild(fragment);
                                    window.scrollTo(0, document.body.scrollHeight);
                                    while(c.children.length > 20) c.removeChild(c.firstChild);
                                }
                            }
                        }
                    } finally {
                        fetchingUpdates = false;
                    }
                }).catch(e => { fetchingUpdates = false; });
            }, 1000);
        </script>
    </body>
    </html>
    """

    html_stats = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');
            html, body { background-color: rgba(0,0,0,0) !important; margin: 0; padding: 20px; overflow: hidden; font-family: 'Fira Code', Consolas, monospace; }
            .stats-widget { background: rgba(20,20,25,0.85); backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px 30px; display: inline-block; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            .stat-row { display: flex; align-items: center; justify-content: space-between; margin: 12px 0; gap: 40px; }
            .stat-label { color: #a1a1aa; font-weight: bold; font-size: 16px; text-transform: uppercase; letter-spacing: 1px; }
            .stat-value { color: #fff; font-weight: bold; font-size: 24px; text-shadow: 0 0 10px rgba(255,255,255,0.2); }
            .stat-row.cmds .stat-value { color: #00E5FF; text-shadow: 0 0 10px rgba(0,229,255,0.3); }
            .stat-row.views .stat-value { color: #3B82F6; text-shadow: 0 0 10px rgba(59,130,246,0.3); }
            .stat-row.likes .stat-value { color: #10B981; text-shadow: 0 0 10px rgba(16,185,129,0.3); }
            .stat-row.errs .stat-value { color: #EF4444; text-shadow: 0 0 10px rgba(239,68,68,0.3); }
            .version-tag { font-size: 12px; color: #52525b; text-align: right; margin-top: 15px; font-weight: bold; border-top: 1px solid #3f3f46; padding-top: 10px; }
        </style>
    </head>
    <body>
        <div class="stats-widget">
            <div class="stat-row">
                <span class="stat-label">UPTIME</span>
                <span class="stat-value" id="uptime">0d 0h 0m 0s</span>
            </div>
            <div class="stat-row views">
                <span class="stat-label">VIEWERS</span>
                <span class="stat-value" id="viewers">0</span>
            </div>
            <div class="stat-row likes">
                <span class="stat-label">LIKES</span>
                <span class="stat-label" id="likes">0</span>
            </div>
            <div class="stat-row cmds">
                <span class="stat-label">CMDS EXECUTED</span>
                <span class="stat-value" id="cmds">0</span>
            </div>
            <div class="stat-row errs">
                <span class="stat-label">FAILED CMDS</span>
                <span class="stat-value" id="failed">0</span>
            </div>
            <div class="version-tag">{{ version }}</div>
        </div>
        <script>
            setInterval(function(){
                fetch('/stats_data?t=' + Date.now())
                .then(r => r.json())
                .then(data => {
                    document.getElementById('uptime').innerText = data.uptime;
                    document.getElementById('cmds').innerText = data.commands;
                    document.getElementById('failed').innerText = data.failed;
                    if(document.getElementById('viewers')) document.getElementById('viewers').innerText = data.viewers || "0";
                    if(document.getElementById('likes')) document.getElementById('likes').innerText = data.likes || "0";
                }).catch(e => {});
            }, 1000);
        </script>
    </body>
    </html>
    """

    html_ultrachat = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;700;900&display=swap');
            body { 
                background: transparent; 
                color: #c9d1d9; 
                font-family: 'Inter', Consolas, monospace; 
                font-weight: 700; 
                font-size: 18px; 
                display: flex; 
                flex-direction: column; 
                justify-content: flex-end; 
                height: 100vh; 
                margin: 0; 
                padding: 20px; 
                overflow: hidden; 
            }
            .msg-row { margin: 4px 0; animation: slide 0.2s; }
            .user-msg { display: flex; align-items: flex-start; margin-bottom: 6px; }
            
            .sys-box { 
                background: rgba(20, 25, 20, 0.9); 
                border-left: 4px solid #2ea043; 
                border-radius: 6px; 
                padding: 8px 12px; 
                display: flex; 
                align-items: center; 
                margin-top: 4px; 
                margin-bottom: 8px; 
                max-width: 90%; 
            }
            .sys-box.blue { border-left-color: #3b82f6; background: rgba(20, 20, 30, 0.9); }
            .sys-box.red { border-left-color: #f85149; background: rgba(30, 20, 20, 0.9); }
            
            .sys-label { color: #2ea043; margin-right: 8px; font-weight: 900; }
            .sys-box.blue .sys-label { color: #3b82f6; }
            .sys-box.red .sys-label { color: #f85149; }
            
            .u { color: #3fb950; margin-right: 8px; display: flex; align-items: center; font-weight: 900; }
            .u.mod { color: #58a6ff; }
            .u.owner { color: #e3b341; }
            
            .text { color: #8b949e; word-wrap: break-word; font-weight: 700; }
            .user-msg .text { color: #c9d1d9; }
            
            .material-symbols-outlined { font-size: 20px; margin-right: 6px; }
            
            @keyframes slide { 
                from { transform: translateX(20px); opacity: 0; } 
                to { transform: translateX(0); opacity: 1; } 
            }
        </style>
    </head>
    <body>
        <div id="c"></div>
        <script>
            let lid = -1;
            setInterval(() => fetch('/history').then(r => r.json()).then(d => {
                let c = document.getElementById('c');
                let a = false;
                d.forEach(m => {
                    if(m.id > lid) {
                        lid = m.id;
                        let isSys = m.u.includes('[system]') || m.u.includes('[console]') || m.u.includes('[announcement]');
                        let html = '';
                        
                        if(isSys) {
                            let boxClass = 'sys-box';
                            let label = 'System:';
                            
                            if(m.u.includes('[announcement]')) { 
                                boxClass += ' blue'; 
                                label = 'Announcement:'; 
                            } else if(m.m.includes('[err]') || m.m.includes('error') || m.m.includes('failed')) { 
                                boxClass += ' red'; 
                                label = 'Error:'; 
                            } else if(m.m.includes('vote')) { 
                                boxClass += ' blue'; 
                                label = 'Vote:'; 
                            }
                            
                            let cleanMsg = m.m.replace('[err]', '').replace('[debug]', '').trim();
                            html = `<div class='msg-row'><div class='${boxClass}'><span class='sys-label'>${label}</span><span class='text'>${cleanMsg}</span></div></div>`;
                        } else {
                            let icon = "<span class='material-symbols-outlined' style='color:#a1a1aa;'>person</span>";
                            let uClass = "u";
                            
                            if(m.is_owner || m.u.toLowerCase().includes('reallyiron')) { 
                                icon = "<span class='material-symbols-outlined' style='color:#e3b341;'>stars</span>"; 
                                uClass = "u owner"; 
                            } else if(m.is_admin) { 
                                icon = "<span class='material-symbols-outlined' style='color:#58a6ff;'>local_police</span>"; 
                                uClass = "u mod"; 
                            }
                            
                            let uName = m.u.startsWith('@') ? m.u : '@' + m.u;
                            html = `<div class='msg-row'><div class='user-msg'>${icon}<span class='${uClass}'>${uName}</span><span class='text'>${m.m}</span></div></div>`;
                        }
                        
                        c.insertAdjacentHTML('beforeend', html);
                        a = true;
                    }
                });
                if(a) {
                    while(c.children.length > 25) c.removeChild(c.firstChild);
                    window.scrollTo(0, document.body.scrollHeight);
                }
            }), 1000);
        </script>
    </body>
    </html>
    """

    html_announcement = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { 
                margin: 0; 
                overflow: hidden; 
                font-family: 'Segoe UI', sans-serif; 
                display: flex; 
                justify-content: center; 
                align-items: flex-start; 
                padding-top: 80px; 
                background: transparent; 
            }
            .box { 
                background: #333; 
                border: 2px solid #555; 
                padding: 2px; 
                border-radius: 8px; 
                transform: translateY(-250%); 
                transition: transform 0.4s ease; 
                box-shadow: 0 10px 20px rgba(0,0,0,0.5); 
                max-width: 85%; 
            }
            .box.show { transform: translateY(0); }
            .inner { 
                background: #222; 
                border-radius: 6px; 
                padding: 20px 30px; 
                text-align: center; 
            }
            .auth { 
                color: #aaa; 
                font-size: 16px; 
                font-weight: bold; 
                text-transform: uppercase; 
                margin-bottom: 8px; 
            }
            .msg { 
                color: #fff; 
                font-size: 28px; 
                font-weight: bold; 
                word-wrap: break-word; 
            }
        </style>
    </head>
    <body>
        <div id="box" class="box">
            <div class="inner">
                <div id="auth" class="auth"></div>
                <div id="msg" class="msg"></div>
            </div>
        </div>
        <script>
            let last_id = 0;
            setInterval(() => {
                fetch('/get_announcement').then(r=>r.json()).then(d => {
                    if(d.id > last_id){
                        last_id = d.id;
                        document.getElementById('auth').innerText = d.author + " announces:";
                        document.getElementById('msg').innerText = d.message;
                        let b = document.getElementById('box');
                        b.classList.add('show');
                        setTimeout(() => { b.classList.remove('show'); }, 5000);
                    }
                });
            }, 1000);
        </script>
    </body>
    </html>
    """

    @obs_web_overlay_app.route('/')
    def index_page():
        return render_template_string(html_index)

    @obs_web_overlay_app.route('/obs')
    def obs_overlay():
        return render_template_string(html_template, padding=10)

    @obs_web_overlay_app.route('/obs2')
    def obs_overlay2():
        return render_template_string(html_template_2)

    @obs_web_overlay_app.route('/obsnew')
    def obs_overlay_new():
        return render_template_string(html_template_new)

    @obs_web_overlay_app.route('/oldobsnew')
    def obs_overlay_oldnew():
        return render_template_string(html_template_oldnew)

    @obs_web_overlay_app.route('/debugchat')
    def obs_overlay_debugchat():
        return render_template_string(html_basic)

    @obs_web_overlay_app.route('/ultrachat')
    def ultrachat_overlay():
        return render_template_string(html_ultrachat)

    @obs_web_overlay_app.route('/announcement')
    def announcement_overlay():
        return render_template_string(html_announcement)

    @obs_web_overlay_app.route('/stats')
    def stats_overlay():
        return render_template_string(html_stats, version=version)

    @obs_web_overlay_app.route('/stats_data')
    def get_stats_data(): 
        uptime_sec = int(time.time() - script_start_time)
        d, r = divmod(uptime_sec, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        uptime_str = f"{d}d {h}h {m}m {s}s" if d > 0 else f"{h}h {m}m {s}s"
        return jsonify({
            "uptime": uptime_str,
            "commands": total_commands_executed,
            "failed": total_commands_failed,
            "viewers": current_viewers,
            "likes": current_likes
        })

    @obs_web_overlay_app.route('/updates')
    def get_updates(): 
        with buffer_lock:
            data = list(messages_buffer)
            messages_buffer.clear()
        return jsonify(data)

    @obs_web_overlay_app.route('/history')
    def get_history(): 
        with history_lock:
            return jsonify(list(web_chat_history))

    @obs_web_overlay_app.route('/get_announcement')
    def get_announcement_data():
        return jsonify(announcement_data)

    @obs_web_overlay_app.route('/status_update')
    def get_status_update():
        return jsonify({
            "status": current_status,
            "vote": current_vote_info,
            "viewers": current_viewers,
            "likes": current_likes,
            "chat_visible": overlay_chat_visible,
            "split_mode": split_overlay_mode
        })

def start_flask():
    global flask_port
    if flask_available:
        try: 
            if 'flask.cli' in sys.modules:
                sys.modules['flask.cli'].show_server_banner = lambda *x: None
            if platform.system() == "Windows":
                try:
                    out = subprocess.check_output("netstat -ano", shell=True).decode()
                    for line in out.splitlines():
                        if "LISTENING" in line and f":{flask_port} " in line + " ":
                            pid = line.strip().split()[-1]
                            if pid.isdigit() and int(pid) > 0 and int(pid) != os.getpid():
                                subprocess.call(["taskkill", "/F", "/PID", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                time.sleep(0.5) 
                except Exception:
                    pass
            for port in range(flask_port, flask_port + 10):
                try:
                    flask_port = port
                    obs_web_overlay_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
                    break
                except OSError:
                    continue
        except Exception:
            pass

class ChatPlaysApp:
    def __init__(self, root):
        try:
            self.root = root
            self.vm_crashed = False
            self.is_multistream = is_multistream
            self.changevm_enabled = not self.is_multistream
            self.last_gc_time = time.time()
            self.last_vbox_refresh = time.time()
            self.vm_frozen_since = None
            self.watchdog_action_level = 0
            self.last_watchdog_action_time = 0
            self.consecutive_failures = 0
            self.last_success_time = time.time()
            self.api_watchdog_level = 0
            self.last_api_watchdog_action_time = 0
            self.maintenance_lock = threading.Lock()
            self.maintenance_gen = 0
            self.revert_disabled = False
            self.recent_bot_messages = collections.deque(maxlen=50)
            self.config = self.load_settings()
            
            self.cmd_queue = queue.Queue()
            self.ultra_speed = self.config.get("ultra_speed", False)
            
            global vm_name, keyboard_layout, vbox_manage_cmd
            vm_name = self.config.get("vm_name", vm_name)
            keyboard_layout = self.config.get("keyboard_layout", keyboard_layout)
            vbox_manage_cmd = self.config.get("vbox_path", vbox_manage_cmd)
            self.command_prefix = self.config.get("command_prefix", "!")
            self.custom_commands = self.config.get("custom_commands", {})
            self.app_name = self.config.get("app_name", "YT2VM")

            self.root.title(f"{self.app_name} {version}: {vm_name}")
            x_cood = int((self.root.winfo_screenwidth()/2) - (1150/2))
            y_cood = int((self.root.winfo_screenheight()/2) - (800/2))
            self.root.geometry(f"1150x800+{x_cood}+{y_cood}")
            self.root.configure(bg="#09090B")
            self.accent_main = "#8B5CF6" if self.is_multistream else "#00E5FF"
            self.accent_hover = "#7C3AED" if self.is_multistream else "#00B3CC"

            if platform.system() == "Windows":
                self.root.overrideredirect(False)
                self.root.update_idletasks()
                try:
                    hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
                    ctypes.windll.user32.SetWindowLongW(hwnd, -16, style & ~0x00C00000)
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int))
                except Exception:
                    pass
            elif platform.system() == "Darwin":
                self.root.overrideredirect(False)
                try:
                    self.root.wm_attributes('-titlebar', 0)
                except Exception:
                    pass
            else:
                self.root.overrideredirect(True)

            self.root.option_add('*TCombobox*Listbox.background', '#18181B')
            self.root.option_add('*TCombobox*Listbox.foreground', 'white')
            self.root.option_add('*TCombobox*Listbox.selectBackground', self.accent_main)
            self.root.option_add('*TCombobox*Listbox.selectForeground', 'black')

            style = ttk.Style()
            if platform.system() == "Darwin" and "aqua" in style.theme_names():
                style.theme_use("aqua")
            elif "clam" in style.theme_names():
                style.theme_use("clam")
                style.configure("TCombobox", fieldbackground="#09090B", background="#27272A", foreground="white", bordercolor="#27272A", arrowcolor="white")
                style.map("TCombobox", fieldbackground=[("readonly", "#09090B")], foreground=[("readonly", "white")])

            style.configure(".", background="#09090B", foreground="#F4F4F5")
            style.configure("TFrame", background="#09090B")
            style.configure("Card.TFrame", background="#18181B")
            style.configure("TLabel", background="#09090B", foreground="#D4D4D8", font=("Segoe UI", 10))
            style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#FFFFFF", background="#09090B")
            style.configure("TNotebook", background="#09090B", tabmargins=[20, 10, 20, 0], borderwidth=0)
            style.configure("TNotebook.Tab", background="#18181B", foreground="#A1A1AA", padding=[25, 8], font=("Segoe UI", 11, "bold"), borderwidth=0)
            style.map("TNotebook.Tab", background=[("selected", self.accent_main)], foreground=[("selected", "#000000")])
            style.configure("Toggle.TCheckbutton", background="#18181B", foreground="#D4D4D8", font=("Segoe UI", 10), indicatorcolor="#27272A", padding=5)
            style.map("Toggle.TCheckbutton", indicatorcolor=[("selected", "#10B981")])
            
            self.is_maximized = False
            self.build_custom_titlebar()
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            self.log_queue = queue.Queue(maxsize=300)
            self.connect_queue = queue.Queue()
            self.running = True
            self.active_url = self.config.get("youtube_url", "")
            self.listening_to_chat = self.config.get("enable_chat", True)
            self.disabled_commands = set()
            self.say_admin_only = True
            self.blocked_terms = list(default_blocked_terms)
            self.twenty_four_seven_mode = self.config.get("auto_start", False)
            self.blacklisted_users = set()
            self.active_votes = {}
            self.vote_lock = threading.Lock()
            self.processed_msg_ids = set()
            self.last_command_time = time.time()
            self.listener_id = 0
            self.executor_id = 0
            self.lag_multiplier = 1.0
            self.chat_paused = False
            self.shared_kb = None
            self.shared_mouse = None
            self.shared_session = None
            self.vbox_mouse_btns = 0
            self.input_lock = threading.RLock()
            self.vm_maintenance = False
            self.last_com_rebuild_time = time.time()
            self.echo_commands = self.config.get("echo_commands", True)

            self.current_snapshot = ""
            if os.path.exists(snap_file):
                try:
                    with open(snap_file, "r") as f:
                        saved_snap = f.read().strip()
                        if saved_snap:
                            self.current_snapshot = saved_snap
                except Exception:
                    pass

            if not self.current_snapshot:
                snaps_found = get_vbox_snapshots(vbox_manage_cmd, vm_name)
                if snaps_found:
                    self.current_snapshot = snaps_found[-1]

            self.vbox = None
            self.mgr = None

            if vbox_pkg == "virtualbox":
                try:
                    self.vbox = virtualbox.VirtualBox()
                except Exception:
                    pass
            elif vbox_pkg == "vboxapi":
                try:
                    self.mgr = VirtualBoxManager(None, None)
                    self.vbox = self.mgr.getVirtualBox()
                except Exception:
                    pass

            try:
                set_obs_scene(obs_scene_main) 
            except Exception:
                pass
                
            self.build_unified_dashboard()
            self.start_app_threads()
            
            if self.twenty_four_seven_mode and self.active_url:
                self.go_live()
                
            self.root.after(refresh_rate, self.process_ui_queue)
            
        except Exception as e:
            err_msg = f"[error] init crashed: {e}"
            print(err_msg + f"\n{traceback.format_exc()}")
            try:
                messagebox.showerror("error", err_msg)
            except Exception:
                pass

    def build_custom_titlebar(self):
        self.title_bar = tk.Frame(self.root, bg="#000000", relief="flat", bd=0, height=35)
        self.title_bar.pack(expand=0, fill="x", side="top")
        self.title_bar.pack_propagate(False)
        
        self.title_label = tk.Label(self.title_bar, text=f"{self.app_name} {version}", bg="#000000", fg=self.accent_main, font=("segoe ui", 10, "bold"))
        self.title_label.pack(side="left", pady=4, padx=15)
        
        self.close_btn = tk.Label(self.title_bar, text="X", bg="#000000", fg="#ffffff", font=("segoe ui", 12, "bold"), width=5, cursor="hand2", anchor="center")
        self.close_btn.pack(side="right", fill="y")
        self.close_btn.bind("<Button-1>", lambda e: self.on_closing())
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(bg="#ef4444"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(bg="#000000"))
        
        self.max_btn = tk.Label(self.title_bar, text="+", bg="#000000", fg="#ffffff", font=("segoe ui", 14, "bold"), width=5, cursor="hand2", anchor="center")
        self.max_btn.pack(side="right", fill="y")
        self.max_btn.bind("<Button-1>", self.toggle_maximize)
        self.max_btn.bind("<Enter>", lambda e: self.max_btn.config(bg="#3f3f46"))
        self.max_btn.bind("<Leave>", lambda e: self.max_btn.config(bg="#000000"))
        
        self.min_btn = tk.Label(self.title_bar, text="-", bg="#000000", fg="#ffffff", font=("segoe ui", 12, "bold"), width=5, cursor="hand2", anchor="center")
        self.min_btn.pack(side="right", fill="y")
        self.min_btn.bind("<Button-1>", lambda e: self.minimize())
        self.min_btn.bind("<Enter>", lambda e: self.min_btn.config(bg="#3f3f46"))
        self.min_btn.bind("<Leave>", lambda e: self.min_btn.config(bg="#000000"))
        
        self.title_bar.bind("<B1-Motion>", self.move_window)
        self.title_bar.bind("<Button-1>", self.get_pos)
        self.title_label.bind("<B1-Motion>", self.move_window)
        self.title_label.bind("<Button-1>", self.get_pos)

    def toggle_maximize(self, event=None):
        if self.is_maximized:
            self.root.state('normal')
            self.is_maximized = False
        else:
            self.root.state('zoomed')
            self.is_maximized = True

    def get_pos(self, event):
        self.xwin = event.x
        self.ywin = event.y

    def move_window(self, event):
        if self.is_maximized:
            self.root.state('normal')
            self.is_maximized = False
        self.root.geometry(f"+{event.x_root - self.xwin}+{event.y_root - self.ywin}")

    def minimize(self):
        self.root.iconify()

    def load_settings(self):
        all_vms = get_all_vbox_vms(vbox_manage_cmd)
        default_vm = all_vms[instance_id - 1] if (all_vms and len(all_vms) >= instance_id) else (all_vms[0] if all_vms else "Windows10ChatVm")
        default_config = {
            "youtube_url": "",
            "vm_name": default_vm,
            "vbox_path": vbox_manage_cmd,
            "auto_start": False,
            "enable_chat": True,
            "strict_live_check": True,
            "keyboard_layout": "US",
            "command_prefix": "!",
            "stats_interval": 15,
            "typing_speed": 0.015,
            "key_delay": 0.015,
            "mouse_delay": 0.005,
            "max_wait_time": 20.0,
            "enable_starting_scene": True,
            "app_name": "YT2VM",
            "ultra_speed": False,
            "show_scancodes": False,
            "custom_commands": {}
        }
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r") as f:
                    default_config.update(json.load(f))
            except Exception:
                pass
        return default_config

    def save_settings(self):
        try:
            tmp_file = settings_file + ".tmp"
            with open(tmp_file, "w") as f:
                json.dump(self.config, f, indent=4)
            os.replace(tmp_file, settings_file)
        except Exception:
            pass

    def trigger_command(self, action_tuple):
        if self.cmd_queue.qsize() > 200:
            self.log("[system]", "[warn] command dropped: system overloaded", "err")
            self.force_session_refresh = True
            return
        self.cmd_queue.put(action_tuple)

    def trigger_command_chain(self, action_chain):
        if self.cmd_queue.qsize() > 200:
            self.log("[system]", "[warn] macro dropped: system overloaded", "err")
            self.force_session_refresh = True
            return
        for action in action_chain:
            self.cmd_queue.put(action)

    def clear_commands(self):
        with self.cmd_queue.mutex:
            self.cmd_queue.queue.clear()

    def on_closing(self):
        self.running = False
        save_stats()
        self.root.update()
        time.sleep(0.2)
        os._exit(0)

    def extract_all_msgs(self):
        try:
            if not os.path.exists(allmsglogs_file):
                messagebox.showinfo("extract", "no messages logged yet.")
                return
            save_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                initialfile="extracted_messages.txt",
                title="save extracted messages",
                filetypes=[("text files", "*.txt")]
            )
            if not save_path:
                return
            count = 0
            with open(save_path, "w", encoding="utf-8") as out_f:
                with open(allmsglogs_file, "r", encoding="utf-8") as in_f:
                    for line in in_f:
                        line = line.strip()
                        if not line or line in ["[", "]"]:
                            continue
                        try:
                            entry = json.loads(line.rstrip(","))
                            out_f.write(f"[{entry.get('time', '')}] {entry.get('username', '')}: {entry.get('message', '')}\n")
                            count += 1
                        except:
                            pass
            self.log("[system]", f"extracted {count} messages to {save_path}", "sysmsg")
            messagebox.showinfo("success", f"extracted {count} messages!")
        except Exception as e:
            self.log("[system]", f"[error] extract failed: {e}", "err")

    def spawn_multistream(self, suffix_id=""):
        try:
            self.log("[system]", f"[debug] spawning multi-stream instance {suffix_id}...", "sysmsg")
            script_path = os.path.abspath(sys.argv[0])
            base_dir = os.path.dirname(script_path)
            base_name = os.path.basename(script_path)
            name, ext = os.path.splitext(base_name)
            multi_script_path = os.path.join(base_dir, f"{name}_multi{suffix_id}{ext}")
            try:
                shutil.copyfile(script_path, multi_script_path)
                self.log("[system]", f"[debug] copied script to {multi_script_path}", "sysmsg")
            except Exception as e:
                self.log("[system]", f"[error] failed to copy script: {e}. using original.", "err")
                multi_script_path = script_path
            args = [sys.executable, multi_script_path, f"--multistream{suffix_id}"]
            if platform.system() == "Windows":
                subprocess.Popen(args, creationflags=0x00000010, close_fds=True)
            else:
                subprocess.Popen(args, start_new_session=True, close_fds=True)
            self.log("[system]", f"[debug] successfully spawned instance {suffix_id}!", "sysmsg")
        except Exception as e:
            err_msg = f"[error] spawn_multistream crashed: {e}"
            console_log("ERROR", err_msg + f"\n{traceback.format_exc()}")
            self.log("[system]", err_msg, "err")
            messagebox.showerror("error", err_msg)

    def build_unified_dashboard(self):
        try:
            self.tabview = ttk.Notebook(self.root, style="TNotebook")
            self.tabview.pack(fill="both", expand=True, padx=10, pady=(10, 10))
            
            self.tab_dash = ttk.Frame(self.tabview, style="TFrame")
            self.tab_vbox = ttk.Frame(self.tabview, style="TFrame")
            self.tab_cmds = ttk.Frame(self.tabview, style="TFrame")
            self.tab_sett = ttk.Frame(self.tabview, style="TFrame")
            self.tab_extra = ttk.Frame(self.tabview, style="TFrame")
            self.tab_announce = ttk.Frame(self.tabview, style="TFrame")
            
            self.tabview.add(self.tab_dash, text="  Dashboard  ")
            self.tabview.add(self.tab_vbox, text="  VM Config  ")
            self.tabview.add(self.tab_cmds, text="  Commands  ")
            self.tabview.add(self.tab_sett, text="  Settings  ")
            self.tabview.add(self.tab_extra, text="  Extra Things  ")
            self.tabview.add(self.tab_announce, text="  Announcements  ")
            
            dash_left = ttk.Frame(self.tab_dash, style="TFrame", width=380)
            dash_left.pack(side="left", fill="both", expand=False, padx=20, pady=20)
            dash_right = ttk.Frame(self.tab_dash, style="TFrame")
            dash_right.pack(side="right", fill="both", expand=True, padx=(0, 20), pady=20)
            
            def create_card(parent, title):
                border = tk.Frame(parent, bg="#27272A", bd=0)
                border.pack(fill="x", pady=(0, 20))
                card = tk.Frame(border, bg="#18181B", bd=0)
                card.pack(fill="both", expand=True, padx=1, pady=1)
                tk.Label(card, text=title, bg="#18181B", fg="#A1A1AA", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
                return card
                
            conn_card = create_card(dash_left, "YOUTUBE STREAM LINK")
            self.entry_url = tk.Entry(conn_card, font=("Consolas", 12), bg="#09090B", fg="#F4F4F5", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main, justify="center")
            self.entry_url.pack(fill="x", padx=15, pady=(5, 15), ipady=8)
            self.entry_url.insert(0, self.config.get("youtube_url", "@yourchannel"))
            self.btn_connect = tk.Button(conn_card, text="Connect Chat", font=("Segoe UI", 10, "bold"), bg=self.accent_main, fg="black", activebackground=self.accent_hover, activeforeground="black", bd=0, cursor="hand2", command=self.go_live)
            self.btn_connect.pack(fill="x", padx=15, pady=(0, 15), ipady=6)
            
            status_card = create_card(dash_left, "SYSTEM STATUS")
            self.lbl_status = tk.Label(status_card, text="BOOTING...", font=("Segoe UI", 16, "bold"), bg="#18181B", fg="#10B981")
            self.lbl_status.pack(anchor="w", padx=15, pady=(0, 5))
            self.btn_vm = tk.Button(status_card, text=f"target: {vm_name}", font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=self.cycle_vm)
            self.btn_vm.pack(fill="x", padx=15, pady=(5, 15), ipady=5)
            
            stats_card = create_card(dash_left, "LIVE STATS")
            stat_grid = tk.Frame(stats_card, bg="#18181B")
            stat_grid.pack(fill="x", padx=15, pady=(0, 15))
            stat_grid.columnconfigure(1, weight=1)
            tk.Label(stat_grid, text="Uptime", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", pady=4)
            self.lbl_uptime_val = tk.Label(stat_grid, text="0h 0m 0s", bg="#18181B", fg="#FFFFFF", font=("Consolas", 12, "bold"))
            self.lbl_uptime_val.grid(row=0, column=1, sticky="e", pady=4)
            tk.Label(stat_grid, text="Commands Run", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", pady=4)
            self.lbl_cmds_val = tk.Label(stat_grid, text="0 (0 Failed)", bg="#18181B", fg="#FFFFFF", font=("Consolas", 12, "bold"))
            self.lbl_cmds_val.grid(row=1, column=1, sticky="e", pady=4)
            tk.Label(stat_grid, text="Viewers", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 11)).grid(row=2, column=0, sticky="w", pady=4)
            self.lbl_viewers_val = tk.Label(stat_grid, text="0", bg="#18181B", fg=self.accent_main, font=("Consolas", 12, "bold"))
            self.lbl_viewers_val.grid(row=2, column=1, sticky="e", pady=4)
            tk.Label(stat_grid, text="Likes", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 11)).grid(row=3, column=0, sticky="w", pady=4)
            self.lbl_likes_val = tk.Label(stat_grid, text="0", bg="#18181B", fg="#10B981", font=("Consolas", 12, "bold"))
            self.lbl_likes_val.grid(row=3, column=1, sticky="e", pady=4)
            
            actions_card = create_card(dash_left, "SYSTEM CONTROLS")
            def quick_cmd(c, a=""):
                self.trigger_command((c, a, "[console]"))
            btn_grid = tk.Frame(actions_card, bg="#18181B")
            btn_grid.pack(fill="x", padx=10, pady=(0, 15))
            btn_grid.columnconfigure(0, weight=1)
            btn_grid.columnconfigure(1, weight=1)
            tk.Button(btn_grid, text="Start VM", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=lambda: quick_cmd("!startvm")).grid(row=0, column=0, padx=5, pady=5, sticky="we", ipady=5)
            tk.Button(btn_grid, text="Restart", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=lambda: quick_cmd("!restartvm")).grid(row=0, column=1, padx=5, pady=5, sticky="we", ipady=5)
            tk.Button(btn_grid, text="Shutdown", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=lambda: quick_cmd("shutdown")).grid(row=1, column=0, padx=5, pady=5, sticky="we", ipady=5)
            tk.Button(btn_grid, text="Revert VM", font=("Segoe UI", 10, "bold"), bg="#EF4444", fg="white", activebackground="#DC2626", activeforeground="white", bd=0, cursor="hand2", command=lambda: quick_cmd("revert")).grid(row=1, column=1, padx=5, pady=5, sticky="we", ipady=5)
            tk.Button(btn_grid, text="Rebuild COM", font=("Segoe UI", 10, "bold"), bg="#3B82F6", fg="white", activebackground="#2563EB", activeforeground="white", bd=0, cursor="hand2", command=lambda: setattr(self, 'force_session_refresh', True)).grid(row=2, column=0, padx=5, pady=5, sticky="we", ipady=5)
            tk.Button(btn_grid, text="Extract All Msgs", font=("Segoe UI", 10, "bold"), bg="#8B5CF6", fg="white", activebackground="#7C3AED", activeforeground="white", bd=0, cursor="hand2", command=self.extract_all_msgs).grid(row=2, column=1, padx=5, pady=5, sticky="we", ipady=5)
            tk.Button(btn_grid, text="Toggle Action Echo", font=("Segoe UI", 10, "bold"), bg="#F59E0B", fg="white", activebackground="#D97706", activeforeground="white", bd=0, cursor="hand2", command=self.toggle_echo).grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="we", ipady=5)
            
            ttk.Label(dash_right, text="Live Output Console", style="Header.TLabel").pack(anchor="w", pady=(0, 10))
            console_border = tk.Frame(dash_right, bg="#27272A", bd=0)
            console_border.pack(fill="both", expand=True)
            console_inner = tk.Frame(console_border, bg="#09090B", bd=0)
            console_inner.pack(fill="both", expand=True, padx=1, pady=1)
            self.console_text = scrolledtext.ScrolledText(console_inner, font=("Consolas", 11), bg="#09090B", fg="#D4D4D8", bd=0, highlightthickness=0, insertbackground="white", padx=15, pady=15)
            self.console_text.pack(fill="both", expand=True)
            self.console_text.configure(state='disabled')
            self.console_text.tag_config("SYSTEM", foreground="#10B981", font=("Consolas", 11, "bold"))
            self.console_text.tag_config("ERROR", foreground="#EF4444", font=("Consolas", 11, "bold"))
            self.console_text.tag_config("EXEC", foreground="#A78BFA")
            self.console_text.tag_config("CHAT", foreground="#A1A1AA")
            
            cmd_frame = tk.Frame(dash_right, bg="#09090B")
            cmd_frame.pack(fill="x", pady=(20, 0))
            tk.Label(cmd_frame, text=">_", font=("Consolas", 18, "bold"), fg=self.accent_main, bg="#09090B").pack(side="left", padx=(0, 15))
            self.entry_cmd = tk.Entry(cmd_frame, font=("Consolas", 14), bg="#18181B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
            self.entry_cmd.pack(side="left", fill="x", expand=True, ipady=8)
            self.entry_cmd.bind("<Return>", self.on_manual_cmd)
            tk.Button(cmd_frame, text="Execute", font=("Segoe UI", 11, "bold"), bg=self.accent_main, fg="black", activebackground=self.accent_hover, activeforeground="black", bd=0, cursor="hand2", command=self.on_manual_cmd).pack(side="right", padx=(15, 0), ipady=6, ipadx=20)
            
            vbox_wrapper = tk.Frame(self.tab_vbox, bg="#09090B")
            vbox_wrapper.pack(fill="both", expand=True)
            vbox_card_border = tk.Frame(vbox_wrapper, bg="#27272A")
            vbox_card_border.pack(pady=40, padx=40, fill="x")
            vbox_content = tk.Frame(vbox_card_border, bg="#18181B", padx=30, pady=30)
            vbox_content.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Label(vbox_content, text="VBoxManage Path", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=1, column=0, sticky="e", pady=15, padx=(0, 20))
            path_frame = tk.Frame(vbox_content, bg="#18181B")
            path_frame.grid(row=1, column=1, sticky="w", pady=15)
            self.entry_vbox_new = tk.Entry(path_frame, width=55, font=("Consolas", 11), bg="#09090B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
            self.entry_vbox_new.pack(side="left", ipady=7, padx=(0, 10))
            self.entry_vbox_new.insert(0, self.config.get("vbox_path", vbox_manage_cmd))
            
            def browse_vbox():
                fp = filedialog.askopenfilename(title="select vboxmanage.exe", filetypes=[("executable", "*.exe")])
                if fp:
                    self.entry_vbox_new.delete(0, 'end')
                    self.entry_vbox_new.insert(0, fp)
                    refresh_vms()
                    
            tk.Button(path_frame, text="Browse", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=browse_vbox).pack(side="left", ipady=5, ipadx=15)
            
            tk.Label(vbox_content, text="Target VM Name", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=2, column=0, sticky="e", pady=15, padx=(0, 20))
            vm_frame = tk.Frame(vbox_content, bg="#18181B")
            vm_frame.grid(row=2, column=1, sticky="w", pady=15)
            self.cb_vm_new = ttk.Combobox(vm_frame, width=45, state="readonly", font=("Segoe UI", 11))
            self.cb_vm_new.pack(side="left", padx=(0, 10))
            
            tk.Label(vbox_content, text="Target Snapshot", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=3, column=0, sticky="e", pady=15, padx=(0, 20))
            snap_frame = tk.Frame(vbox_content, bg="#18181B")
            snap_frame.grid(row=3, column=1, sticky="w", pady=15)
            self.cb_snap_new = ttk.Combobox(snap_frame, width=45, font=("Segoe UI", 11))
            self.cb_snap_new.pack(side="left", padx=(0, 10))
            
            def refresh_snaps(event=None):
                current_vm = self.cb_vm_new.get()
                if not current_vm: return
                snaps = get_vbox_snapshots(self.entry_vbox_new.get().strip() or vbox_manage_cmd, current_vm)
                if not snaps:
                    self.cb_snap_new['values'] = [""]
                    self.cb_snap_new.set("")
                else:
                    self.cb_snap_new['values'] = snaps
                    if self.current_snapshot in snaps:
                        self.cb_snap_new.set(self.current_snapshot)
                    else:
                        self.cb_snap_new.set(snaps[-1])
                        
            tk.Button(snap_frame, text="Refresh", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=refresh_snaps).pack(side="left", ipady=5, ipadx=15)
            
            def refresh_vms():
                vms = get_all_vbox_vms(self.entry_vbox_new.get().strip() or vbox_manage_cmd)
                if vms:
                    self.cb_vm_new['values'] = vms
                    current_conf = self.config.get("vm_name")
                    if current_conf in vms:
                        self.cb_vm_new.set(current_conf)
                    else:
                        self.cb_vm_new.set(vms[0])
                refresh_snaps()
                
            tk.Button(vm_frame, text="Refresh", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=refresh_vms).pack(side="left", ipady=5, ipadx=15)
            refresh_vms()
            self.cb_vm_new.bind("<<ComboboxSelected>>", refresh_snaps)
            
            tk.Button(vbox_content, text="Save VM Configuration", font=("Segoe UI", 11, "bold"), bg="#10B981", fg="#000000", activebackground="#059669", activeforeground="#000000", bd=0, cursor="hand2", command=self.save_vbox_settings).grid(row=8, column=1, sticky="w", pady=40, ipady=8, ipadx=20)
            
            self.build_commands_tab()
            
            sett_wrapper = tk.Frame(self.tab_sett, bg="#09090B")
            sett_wrapper.pack(fill="both", expand=True)
            sett_card_border = tk.Frame(sett_wrapper, bg="#27272A")
            sett_card_border.pack(pady=30, padx=40, fill="both", expand=True)
            sett_content = tk.Frame(sett_card_border, bg="#18181B", padx=20, pady=20)
            sett_content.pack(fill="both", expand=True, padx=1, pady=1)
            sett_cols = tk.Frame(sett_content, bg="#18181B")
            sett_cols.pack(fill="both", expand=True)
            sett_left = tk.Frame(sett_cols, bg="#18181B")
            sett_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
            sett_right = tk.Frame(sett_cols, bg="#18181B")
            sett_right.pack(side="right", fill="both", expand=True, padx=(10, 0))
            
            tk.Label(sett_left, text="GENERAL SETTINGS", font=("Segoe UI", 12, "bold"), bg="#18181B", fg=self.accent_main).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
            tk.Label(sett_left, text="Command Prefix", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=1, column=0, sticky="e", pady=10, padx=(0, 20))
            self.entry_prefix_new = tk.Entry(sett_left, width=15, font=("Consolas", 13), bg="#09090B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main, justify="center")
            self.entry_prefix_new.grid(row=1, column=1, sticky="w", pady=10, ipady=5)
            self.entry_prefix_new.insert(0, str(self.config.get("command_prefix", "!")))
            
            tk.Label(sett_left, text="Keyboard Layout", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=2, column=0, sticky="e", pady=10, padx=(0, 20))
            self.cb_layout_new = ttk.Combobox(sett_left, values=available_layouts, width=30, state="readonly", font=("Segoe UI", 11))
            self.cb_layout_new.grid(row=2, column=1, sticky="w", pady=10)
            if self.config.get("keyboard_layout") in available_layouts:
                self.cb_layout_new.set(self.config["keyboard_layout"])
            else:
                self.cb_layout_new.set("US")
                
            self.var_auto_new = tk.BooleanVar(value=self.config.get("auto_start", False))
            ttk.Checkbutton(sett_left, text="Auto-start VM on launch", variable=self.var_auto_new, style="Toggle.TCheckbutton").grid(row=3, column=0, columnspan=2, sticky="w", pady=6)
            
            self.var_chat_new = tk.BooleanVar(value=self.config.get("enable_chat", True))
            ttk.Checkbutton(sett_left, text="Enable chat listener", variable=self.var_chat_new, style="Toggle.TCheckbutton").grid(row=4, column=0, columnspan=2, sticky="w", pady=6)
            
            self.say_admin_var = tk.BooleanVar(value=self.say_admin_only)
            ttk.Checkbutton(sett_left, text="Require Admin for !say", variable=self.say_admin_var, command=self.update_say_admin, style="Toggle.TCheckbutton").grid(row=5, column=0, columnspan=2, sticky="w", pady=6)
            
            self.var_starting_scene = tk.BooleanVar(value=self.config.get("enable_starting_scene", True))
            ttk.Checkbutton(sett_left, text="Enable 'Starting' OBS Scene", variable=self.var_starting_scene, style="Toggle.TCheckbutton").grid(row=6, column=0, columnspan=2, sticky="w", pady=6)
            
            self.var_strict_live = tk.BooleanVar(value=self.config.get("strict_live_check", True))
            ttk.Checkbutton(sett_left, text="Strict Live Check (Only connect if currently LIVE)", variable=self.var_strict_live, style="Toggle.TCheckbutton").grid(row=7, column=0, columnspan=2, sticky="w", pady=6)
            
            self.var_scancodes_new = tk.BooleanVar(value=self.config.get("show_scancodes", False))
            ttk.Checkbutton(sett_left, text="Show Scancodes in UI / Ultrachat", variable=self.var_scancodes_new, style="Toggle.TCheckbutton").grid(row=8, column=0, columnspan=2, sticky="w", pady=6)
            
            tk.Label(sett_left, text="App Name", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=9, column=0, sticky="e", pady=10, padx=(0, 20))
            self.cb_app_name = ttk.Combobox(sett_left, values=["YT2VM", "c2vm", "ycpv", "ytpvm"], width=30, state="readonly", font=("Segoe UI", 11))
            self.cb_app_name.grid(row=9, column=1, sticky="w", pady=10)
            self.cb_app_name.set(self.config.get("app_name", "YT2VM"))
            
            tk.Label(sett_right, text="PERFORMANCE & TIMINGS", font=("Segoe UI", 12, "bold"), bg="#18181B", fg="#10B981").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
            
            self.var_ultra_speed = tk.BooleanVar(value=self.config.get("ultra_speed", False))
            ttk.Checkbutton(sett_right, text="ULTRA SPEED MODE (Zero Delay)", variable=self.var_ultra_speed, style="Toggle.TCheckbutton").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
            
            tk.Label(sett_right, text="Stats Update Interval (s)", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=2, column=0, sticky="e", pady=10, padx=(0, 20))
            self.entry_stats_int = tk.Entry(sett_right, width=15, font=("Consolas", 12), bg="#09090B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981", justify="center")
            self.entry_stats_int.grid(row=2, column=1, sticky="w", pady=10, ipady=5)
            self.entry_stats_int.insert(0, str(self.config.get("stats_interval", 15)))
            
            tk.Label(sett_right, text="Typing Speed (s)", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=3, column=0, sticky="e", pady=10, padx=(0, 20))
            self.entry_type_spd = tk.Entry(sett_right, width=15, font=("Consolas", 12), bg="#09090B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981", justify="center")
            self.entry_type_spd.grid(row=3, column=1, sticky="w", pady=10, ipady=5)
            self.entry_type_spd.insert(0, str(self.config.get("typing_speed", 0.015)))
            
            tk.Label(sett_right, text="Key Press Delay (s)", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=4, column=0, sticky="e", pady=10, padx=(0, 20))
            self.entry_key_del = tk.Entry(sett_right, width=15, font=("Consolas", 12), bg="#09090B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981", justify="center")
            self.entry_key_del.grid(row=4, column=1, sticky="w", pady=10, ipady=5)
            self.entry_key_del.insert(0, str(self.config.get("key_delay", 0.015)))
            
            tk.Label(sett_right, text="Mouse Click Delay (s)", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=5, column=0, sticky="e", pady=10, padx=(0, 20))
            self.entry_mouse_del = tk.Entry(sett_right, width=15, font=("Consolas", 12), bg="#09090B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981", justify="center")
            self.entry_mouse_del.grid(row=5, column=1, sticky="w", pady=10, ipady=5)
            self.entry_mouse_del.insert(0, str(self.config.get("mouse_delay", 0.005)))
            
            tk.Label(sett_right, text="Max !wait Time (s)", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=6, column=0, sticky="e", pady=10, padx=(0, 20))
            self.entry_max_wait = tk.Entry(sett_right, width=15, font=("Consolas", 12), bg="#09090B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981", justify="center")
            self.entry_max_wait.grid(row=6, column=1, sticky="w", pady=10, ipady=5)
            self.entry_max_wait.insert(0, str(self.config.get("max_wait_time", 20.0)))
            
            btn_save_frame = tk.Frame(sett_content, bg="#18181B")
            btn_save_frame.pack(fill="x", pady=(20, 0))
            tk.Button(btn_save_frame, text="SAVE ALL SETTINGS", font=("Segoe UI", 11, "bold"), bg=self.accent_main, fg="black", activebackground=self.accent_hover, activeforeground="black", bd=0, cursor="hand2", command=self.save_general_settings).pack(ipady=8, ipadx=40)
            
            self.build_extra_tab()
            
            ann_wrap = tk.Frame(self.tab_announce, bg="#09090B")
            ann_wrap.pack(fill="both", expand=True)
            ann_card = tk.Frame(ann_wrap, bg="#18181B", padx=30, pady=30)
            ann_card.pack(pady=40, padx=40, fill="both", expand=True)
            tk.Label(ann_card, text="Stream Announcements", font=("Segoe UI", 16, "bold"), bg="#18181B", fg=self.accent_main).pack(pady=(0, 20))
            tk.Label(ann_card, text="Author Name:", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").pack(anchor="w", padx=20)
            self.ann_author = tk.Entry(ann_card, font=("Consolas", 12), bg="#09090B", fg="white", bd=0, insertbackground="white")
            self.ann_author.pack(fill="x", padx=20, pady=5, ipady=6)
            self.ann_author.insert(0, "ReallyIron")
            tk.Label(ann_card, text="Message:", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").pack(anchor="w", padx=20, pady=(15, 5))
            self.ann_msg = tk.Text(ann_card, font=("Consolas", 14), bg="#09090B", fg="white", bd=0, height=5, insertbackground="white")
            self.ann_msg.pack(fill="x", padx=20, pady=5)
            def fire_ann():
                global announcement_data
                announcement_data["id"] += 1
                announcement_data["author"] = self.ann_author.get().strip()
                announcement_data["message"] = self.ann_msg.get("1.0", "end").strip()
                self.log("[system]", f"fired announcement: {announcement_data['message']}", "sysmsg")
            tk.Button(ann_card, text="Fire Announcement", font=("Segoe UI", 14, "bold"), bg="#EC4899", fg="white", bd=0, cursor="hand2", command=fire_ann).pack(fill="x", padx=20, pady=30, ipady=10)
            
        except Exception as e:
            self.log("[system]", f"[error] ui build error: {e}", "err")
            console_log("ERROR", f"[error] ui build error: {e}\n{traceback.format_exc()}")

    def build_extra_tab(self):
        try:
            extra_wrapper = tk.Frame(self.tab_extra, bg="#09090B")
            extra_wrapper.pack(fill="both", expand=True)
            extra_card_border = tk.Frame(extra_wrapper, bg="#27272A")
            extra_card_border.pack(pady=40, padx=40, fill="x")
            extra_content = tk.Frame(extra_card_border, bg="#18181B", padx=30, pady=30)
            extra_content.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Label(extra_content, text="MULTI-STREAMING SETUP", font=("Segoe UI", 12, "bold"), bg="#18181B", fg=self.accent_main).pack(anchor="w", pady=(0, 5))
            tk.Label(extra_content, text="Launch secondary instances. They will automatically increment the web server ports (5001, 5002, 5003...).", font=("Segoe UI", 10), bg="#18181B", fg="#A1A1AA").pack(anchor="w", pady=(0, 20))
            
            if instance_id == 1:
                for i in range(1, 6):
                    port = 5000 + i
                    suffix_arg = "" if i == 1 else str(i)
                    tk.Button(extra_content, text=f"Spawn Multi-Stream {i} (Port {port})", font=("Segoe UI", 11, "bold"), bg="#8B5CF6", fg="white", activebackground="#7C3AED", activeforeground="white", bd=0, cursor="hand2", command=lambda s=suffix_arg: self.spawn_multistream(s)).pack(anchor="w", ipady=8, ipadx=20, pady=5)
            else:
                tk.Label(extra_content, text=f"[active] this is currently multi-stream {instance_id-1} running on port {flask_port}.", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#8B5CF6").pack(anchor="w", pady=10)
        except Exception as e:
            self.log("[system]", f"[error] extra tab build error: {e}", "err")
            console_log("ERROR", f"[error] extra tab build error: {e}\n{traceback.format_exc()}")

    def build_commands_tab(self):
        try:
            cmd_wrapper = tk.Frame(self.tab_cmds, bg="#09090B")
            cmd_wrapper.pack(fill="both", expand=True, padx=20, pady=20)
            
            left_col = tk.Frame(cmd_wrapper, bg="#18181B", width=340)
            left_col.pack(side="left", fill="y", padx=(0, 10))
            left_col.pack_propagate(False)
            
            tk.Label(left_col, text="BUILT-IN COMMANDS", font=("Segoe UI", 12, "bold"), bg="#18181B", fg=self.accent_main).pack(pady=(15, 10))
            
            help_text = (
                "!type (!t) <text>\n   Types raw text into the VM.\n\n"
                "!key (!k) <key>\n   Presses a single key (e.g. !k enter)\n\n"
                "!combo (!c) <key>+<key>\n   Key combo (e.g. !c win+r)\n\n"
                "!click (!lc) [count]\n   Left clicks mouse.\n\n"
                "!rclick (!rc) [count]\n   Right clicks mouse.\n\n"
                "!move (!m) <dir> <amt>\n   Moves cursor by amount.\n\n"
                "!abs <x> <y>\n   Moves cursor to exact coords.\n\n"
                "!scroll <amt>\n   Scrolls mouse wheel.\n\n"
                "!drag (!d) <dx> <dy>\n   Clicks and drags mouse.\n\n"
                "!wait (!w) <seconds>\n   Pauses the action chain.\n\n"
                "!cmd <command>\n   Runs command in admin CMD.\n\n"
                "!run <command>\n   Runs command in Win+R dialog.\n\n"
                "!startvm\n   Boots the selected VM.\n\n"
                "!restartvm\n   Force restarts the VM.\n\n"
                "!shutdown\n   Power offs the VM.\n\n"
                "!revert\n   Restores target snapshot.\n\n"
                "!roll\n   Rolls a random number 1-100.\n\n"
                "!coinflip\n   Flips heads or tails.\n"
            )
            
            ht = scrolledtext.ScrolledText(left_col, font=("Consolas", 10), bg="#09090B", fg="#D4D4D8", bd=0, highlightthickness=1, highlightbackground="#27272A")
            ht.pack(fill="both", expand=True, padx=15, pady=(0, 15))
            ht.insert("1.0", help_text)
            ht.config(state="disabled")
            
            right_col = tk.Frame(cmd_wrapper, bg="#18181B")
            right_col.pack(side="right", fill="both", expand=True, padx=(10, 0))
            
            tk.Label(right_col, text="CUSTOM COMMAND BUILDER (MACROS)", font=("Segoe UI", 12, "bold"), bg="#18181B", fg="#10B981").pack(anchor="w", padx=20, pady=(15, 5))
            tk.Label(right_col, text="Create your own commands by chaining built-in commands with '|'", font=("Segoe UI", 10), bg="#18181B", fg="#A1A1AA").pack(anchor="w", padx=20, pady=(0, 15))
            
            form_frame = tk.Frame(right_col, bg="#18181B")
            form_frame.pack(fill="x", padx=20)
            
            tk.Label(form_frame, text="Trigger (e.g., !hack)", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=0, column=0, sticky="w", pady=8)
            self.entry_macro_name = tk.Entry(form_frame, font=("Consolas", 12), bg="#09090B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981")
            self.entry_macro_name.grid(row=0, column=1, sticky="we", padx=(15, 0), pady=8, ipady=6)
            
            tk.Label(form_frame, text="Action Chain", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=1, column=0, sticky="w", pady=8)
            self.entry_macro_actions = tk.Entry(form_frame, font=("Consolas", 12), bg="#09090B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981")
            self.entry_macro_actions.grid(row=1, column=1, sticky="we", padx=(15, 0), pady=8, ipady=6)
            
            form_frame.columnconfigure(1, weight=1)
            
            btn_frame = tk.Frame(right_col, bg="#18181B")
            btn_frame.pack(fill="x", padx=20, pady=15)
            
            tk.Button(btn_frame, text="SAVE COMMAND", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", activebackground="#059669", activeforeground="black", bd=0, cursor="hand2", command=self.save_custom_cmd).pack(side="left", ipady=5, ipadx=15)
            tk.Button(btn_frame, text="DELETE SELECTED", font=("Segoe UI", 10, "bold"), bg="#EF4444", fg="white", activebackground="#DC2626", activeforeground="white", bd=0, cursor="hand2", command=self.delete_custom_cmd).pack(side="right", ipady=5, ipadx=15)
            
            list_frame = tk.Frame(right_col, bg="#27272A", bd=1)
            list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
            
            self.macro_listbox = tk.Listbox(list_frame, font=("Consolas", 12), bg="#09090B", fg=self.accent_main, bd=0, highlightthickness=0, selectbackground="#27272A")
            self.macro_listbox.pack(side="left", fill="both", expand=True, padx=1, pady=1)
            scroll = ttk.Scrollbar(list_frame, command=self.macro_listbox.yview)
            scroll.pack(side="right", fill="y")
            self.macro_listbox.config(yscrollcommand=scroll.set)
            self.macro_listbox.bind('<<ListboxSelect>>', self.on_macro_select)
            self.refresh_macro_list()
        except Exception as e:
            self.log("[system]", f"[error] commands tab build error: {e}", "err")
            console_log("ERROR", f"[error] commands tab build error: {e}\n{traceback.format_exc()}")

    def save_custom_cmd(self):
        name = self.entry_macro_name.get().strip().lower()
        actions = self.entry_macro_actions.get().strip()
        if not name or not actions: return
        if not name.startswith(self.command_prefix):
            name = self.command_prefix + name
        self.custom_commands[name] = {"type": "chain", "value": actions}
        self.config["custom_commands"] = self.custom_commands
        self.save_settings()
        self.refresh_macro_list()
        self.entry_macro_name.delete(0, 'end')
        self.entry_macro_actions.delete(0, 'end')
        console_log("SYSTEM", f"saved custom command: {name}")

    def delete_custom_cmd(self):
        sel = self.macro_listbox.curselection()
        if not sel: return
        val = self.macro_listbox.get(sel[0])
        name = val.split(" -> ")[0].strip()
        if name in self.custom_commands:
            del self.custom_commands[name]
            self.config["custom_commands"] = self.custom_commands
            self.save_settings()
            self.refresh_macro_list()
            console_log("SYSTEM", f"deleted custom command: {name}")

    def refresh_macro_list(self):
        self.macro_listbox.delete(0, 'end')
        for k, v in self.custom_commands.items():
            if isinstance(v, dict) and "value" in v:
                self.macro_listbox.insert('end', f"{k} -> {v['value']}")
            elif isinstance(v, str):
                self.macro_listbox.insert('end', f"{k} -> {v}")

    def on_macro_select(self, evt):
        sel = self.macro_listbox.curselection()
        if not sel: return
        val = self.macro_listbox.get(sel[0])
        if " -> " not in val: return
        name, actions = val.split(" -> ", 1)
        self.entry_macro_name.delete(0, 'end')
        self.entry_macro_name.insert(0, name)
        self.entry_macro_actions.delete(0, 'end')
        self.entry_macro_actions.insert(0, actions)

    def auto_refresh_vbox_ui(self):
        try:
            vms = get_all_vbox_vms(self.entry_vbox_new.get().strip() or vbox_manage_cmd)
            if vms:
                current_vm_val = self.cb_vm_new.get()
                self.cb_vm_new['values'] = vms
                if current_vm_val not in vms and vm_name in vms:
                    self.cb_vm_new.set(vm_name)
            active_vm = self.cb_vm_new.get()
            if active_vm:
                snaps = get_vbox_snapshots(self.entry_vbox_new.get().strip() or vbox_manage_cmd, active_vm)
                self.cb_snap_new['values'] = snaps if snaps else [""]
                if self.current_snapshot not in snaps and snaps:
                    self.current_snapshot = snaps[-1]
                    self.cb_snap_new.set(self.current_snapshot)
        except Exception:
            pass

    def update_say_admin(self):
        self.say_admin_only = self.say_admin_var.get()

    def save_vbox_settings(self):
        self.config["vm_name"] = self.cb_vm_new.get()
        self.config["vbox_path"] = self.entry_vbox_new.get()
        self.current_snapshot = self.cb_snap_new.get()
        try:
            with open(snap_file, "w") as f:
                f.write(self.current_snapshot)
        except Exception:
            pass
        self.save_settings()
        global vm_name, vbox_manage_cmd
        vm_name = self.config["vm_name"]
        vbox_manage_cmd = self.config["vbox_path"]
        self.title_label.configure(text=f"{self.config.get('app_name', 'YT2VM')} {version}")
        self.btn_vm.configure(text=f"target: {vm_name}")
        console_log("SYSTEM", "vm settings saved!")

    def save_general_settings(self):
        self.config["auto_start"] = self.var_auto_new.get()
        self.config["enable_chat"] = self.var_chat_new.get()
        self.config["keyboard_layout"] = self.cb_layout_new.get()
        self.config["command_prefix"] = self.entry_prefix_new.get()
        self.config["enable_starting_scene"] = self.var_starting_scene.get()
        self.config["strict_live_check"] = self.var_strict_live.get()
        self.config["show_scancodes"] = self.var_scancodes_new.get()
        self.config["app_name"] = self.cb_app_name.get()
        self.config["ultra_speed"] = self.var_ultra_speed.get()
        try:
            self.config["stats_interval"] = float(self.entry_stats_int.get())
        except:
            self.config["stats_interval"] = 15
        try:
            self.config["typing_speed"] = float(self.entry_type_spd.get())
        except:
            self.config["typing_speed"] = 0.015
        try:
            self.config["key_delay"] = float(self.entry_key_del.get())
        except:
            self.config["key_delay"] = 0.015
        try:
            self.config["mouse_delay"] = float(self.entry_mouse_del.get())
        except:
            self.config["mouse_delay"] = 0.005
        try:
            self.config["max_wait_time"] = float(self.entry_max_wait.get())
        except:
            self.config["max_wait_time"] = 20.0
            
        self.save_settings()
        
        global keyboard_layout
        keyboard_layout = self.config["keyboard_layout"]
        self.command_prefix = self.config["command_prefix"]
        self.listening_to_chat = self.config["enable_chat"]
        self.twenty_four_seven_mode = self.config["auto_start"]
        self.app_name = self.config["app_name"]
        self.ultra_speed = self.config["ultra_speed"]
        self.title_label.configure(text=f"{self.app_name} {version}")
        console_log("SYSTEM", "general settings & timings saved!")

    def update_gui_console(self):
        try:
            while not gui_log_queue.empty():
                level, msg = gui_log_queue.get_nowait()
                self.console_text.configure(state='normal')
                if level in ["SYSTEM", "ERROR", "EXEC", "CHAT"]:
                    self.console_text.insert(tk.END, msg + "\n", level)
                else:
                    self.console_text.insert(tk.END, msg + "\n")
                self.console_text.see(tk.END)
                try:
                    line_count = int(self.console_text.index('end-1c').split('.')[0])
                    if line_count > 300:
                        self.console_text.delete('1.0', f'{line_count - 250}.0')
                except Exception:
                    pass
                self.console_text.configure(state='disabled')
        except Exception:
            pass

    def update_status_display(self, text, is_error=False):
        global current_status
        if current_status != text:
            current_status = text 
            if hasattr(self, 'lbl_status'):
                self.lbl_status.configure(text=text.upper(), fg="#EF4444" if is_error else "#10B981")

    def toggle_overlay_chat(self):
        global overlay_chat_visible
        overlay_chat_visible = not overlay_chat_visible

    def toggle_split_overlay(self):
        global split_overlay_mode
        split_overlay_mode = not split_overlay_mode

    def toggle_247(self):
        self.twenty_four_seven_mode = not self.twenty_four_seven_mode
        self.config["auto_start"] = self.twenty_four_seven_mode
        self.save_settings()

    def toggle_chat(self):
        self.listening_to_chat = not self.listening_to_chat
        self.config["enable_chat"] = self.listening_to_chat
        self.save_settings()

    def toggle_echo(self):
        self.echo_commands = not getattr(self, 'echo_commands', True)
        self.config["echo_commands"] = self.echo_commands
        self.save_settings()
        state = "ON" if self.echo_commands else "OFF"
        self.log("[system]", f"Action echo is now {state}", "sysmsg")

    def cycle_layout(self):
        global keyboard_layout
        try:
            current_index = available_layouts.index(keyboard_layout)
            next_index = (current_index + 1) % len(available_layouts)
        except ValueError:
            next_index = 0
        keyboard_layout = available_layouts[next_index]

    def cycle_vm(self):
        global vm_name, available_vms
        try:
            res = subprocess.run([vbox_manage_cmd, "list", "vms"], capture_output=True, text=True, timeout=2)
            fresh_vms = [line.split('"')[1] for line in res.stdout.splitlines() if '"' in line]
            if fresh_vms:
                available_vms = fresh_vms
        except:
            pass
        try:
            current_index = available_vms.index(vm_name)
            next_index = (current_index + 1) % len(available_vms)
        except ValueError:
            next_index = 0
        vm_name = available_vms[next_index]
        snaps = get_vbox_snapshots(vbox_manage_cmd, vm_name)
        if snaps:
            self.current_snapshot = snaps[-1]
        else:
            self.current_snapshot = ""
        self.config["vm_name"] = vm_name
        self.save_settings()
        self.title_label.configure(text=f"{self.config.get('app_name', 'YT2VM')} {version}")
        if hasattr(self, 'btn_vm'):
            self.btn_vm.configure(text=f"target: {vm_name}")

    def go_live(self):
        try:
            url = self.entry_url.get().strip()
            if url:
                if self.active_url != url:
                    self.yt_bot_chat_id = None
                self.active_url = url
                self.force_connect = True
                self.config["youtube_url"] = url
                self.save_settings() 
        except Exception as e:
            self.log("[system]", f"[error] go live error: {e}", "err")
            console_log("ERROR", f"[error] go live error: {e}\n{traceback.format_exc()}")

    def resolve_live_video_id(self, url):
        if not hasattr(self, 'resolved_id_cache'):
            self.resolved_id_cache = {}
        if url in self.resolved_id_cache:
            return self.resolved_id_cache[url]
        if "v=" in url: 
            vid = url.split("v=")[1].split("&")[0]
            self.resolved_id_cache[url] = vid
            return vid
        if "youtu.be/" in url: 
            vid = url.split("youtu.be/")[1].split("?")[0]
            self.resolved_id_cache[url] = vid
            return vid
        if "@" in url or "channel/" in url or "c/" in url:
            try:
                check_url = url
                if not check_url.startswith("http"):
                    check_url = "https://www.youtube.com/" + check_url.lstrip("/")
                parsed = urllib.parse.urlparse(check_url)
                if not (parsed.netloc.endswith("youtube.com") or parsed.netloc.endswith("youtu.be")):
                    return url
                if not check_url.endswith("live"):
                    check_url = check_url.rstrip("/") + "/live"
                req = urllib.request.Request(check_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8').lower()
                if 'consent.youtube.com' in html or 'captcha' in html:
                    return url
                match = re.search(r'rel="canonical" href="https://www.youtube.com/watch\?v=([^"]+)"', html)
                if not match:
                    match = re.search(r'"videoid":"([a-zA-Z0-9_-]{11})"', html)
                if not match:
                    match = re.search(r'watch\?v=([a-zA-Z0-9_-]{11})', html)
                if match: 
                    vid = match.group(1)
                    if len(vid) == 11:
                        self.resolved_id_cache[url] = vid
                        return vid
            except Exception as e:
                self.log("[system]", f"[error] resolve live video error: {e}", "err")
        return url
        
    def is_video_currently_live(self, vid):
        try:
            req = urllib.request.Request(f"https://www.youtube.com/watch?v={vid}", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8').lower()
            if 'live_stream_offline' in html:
                return False
            return True
        except Exception:
            return True

    def process_vote(self, user, vote_type, target=2):
        if getattr(self, 'vm_maintenance', False):
            self.log("[system]", "[warn] vm is processing commands. votes paused.", "sysmsg")
            return
        with self.vote_lock:
            if vote_type in self.active_votes:
                vote = self.active_votes[vote_type]
                if target < vote["target"]:
                    vote["target"] = target
                if user not in vote["voters"]:
                    vote["voters"].add(user)
                    current_votes = len(vote["voters"])
                    self.log("[system]", f"[vote] [alert] {vote_type.lower()} progress: {current_votes}/{vote['target']}!", "sysmsg")
                    log_vote_action("vote_progress", user, vote_type, vote['target'], current_votes)
                    if current_votes >= vote["target"]:
                        self.log("[system]", f"[vote] [success] {vote_type.lower()} passed! executing now...", "sysmsg")
                        log_vote_action("vote_passed", user, vote_type, vote['target'], current_votes)
                        clean_cmd = vote_type
                        if clean_cmd.startswith(self.command_prefix):
                            clean_cmd = clean_cmd[len(self.command_prefix):]
                        self.active_votes.clear()
                        if clean_cmd == "fixscript":
                            self.save_settings()
                            time.sleep(1)
                            script_path = os.path.abspath(sys.argv[0])
                            args = [sys.executable, script_path]
                            for arg_val in sys.argv:
                                if arg_val.startswith("--multistream"):
                                    args.append(arg_val)
                                    break
                            flags = 0x00000010 if platform.system() == "Windows" else 0
                            subprocess.Popen(args, creationflags=flags)
                            os._exit(0)
                        elif clean_cmd == "forcefixvm":
                            self.clear_commands()
                            self.trigger_command(("forcefixvm", "", "vote_passed"))
                        else:
                            self.trigger_command((clean_cmd, "", "vote_passed"))
                        return
                return
            if len(self.active_votes) < 3:
                self.log("[system]", f"[vote] [started] {vote_type.lower()} vote started by {user}! progress: 1/{target}.", "sysmsg")
                self.active_votes[vote_type] = {"voters": {user}, "target": target, "start_time": time.time()}
                log_vote_action("vote_started", user, vote_type, target, 1)

    def on_manual_cmd(self, event=None):
        try:
            cmd = self.entry_cmd.get().strip()
            if cmd:
                if not cmd.startswith(self.command_prefix) and not cmd.startswith("!"):
                    cmd = self.command_prefix + cmd
                elif cmd.startswith("!") and not cmd.startswith(self.command_prefix):
                    cmd = self.command_prefix + cmd[1:]
                self.log("[console]", cmd, "user", is_mod=True, is_owner=True)
                self.parse_command(cmd, "[console]", is_mod=True, is_owner=True)
                self.entry_cmd.delete(0, 'end')
        except Exception as e:
            self.log("[system]", f"[error] manual cmd error: {e}", "err")
            console_log("ERROR", f"[error] manual cmd error: {e}\n{traceback.format_exc()}")

    def log(self, user, message, tag="sysmsg", is_mod=False, is_owner=False): 
        if not isinstance(message, str): message = str(message)
        if not isinstance(user, str): user = str(user)
        if user == "[system]" or user.lower() == "system" or user == "[SYSTEM]":
            user = "[system]"
            is_mod = True
            is_owner = True
            self.recent_bot_messages.append(message)
        self.log_queue.put(("log", (user, message, tag, is_mod, is_owner)))
        add_to_history(user, message, tag, is_mod, is_owner)
    
    def set_status(self, text): 
        if isinstance(text, str):
            self.log_queue.put(("status", text.lower()))

    def process_ui_queue(self):
        try:
            self.update_gui_console()
            uptime_sec = int(time.time() - script_start_time)
            m, s = divmod(uptime_sec, 60)
            h, m = divmod(m, 60)
            if hasattr(self, 'lbl_uptime_val'):
                self.lbl_uptime_val.config(text=f"{h}h {m}m {s}s")
                self.lbl_cmds_val.config(text=f"{total_commands_executed} ({total_commands_failed} failed)")
                self.lbl_viewers_val.config(text=str(current_viewers))
                self.lbl_likes_val.config(text=str(current_likes))
            if time.time() - self.last_gc_time > 60:
                self.last_gc_time = time.time()
                gc.collect()
            if time.time() - getattr(self, 'last_vbox_refresh', 0) > 10:
                self.last_vbox_refresh = time.time()
                self.auto_refresh_vbox_ui()
            global current_vote_info
            if time.time() - getattr(self, 'last_thread_check', 0) > 15:
                self.last_thread_check = time.time()
                self.start_app_threads()
            while not self.log_queue.empty():
                try:
                    msg_type, data = self.log_queue.get_nowait()
                    if msg_type == "status":
                        self.update_status_display(data, "broke" in data)
                except queue.Empty:
                    break
                except Exception:
                    pass
            with self.vote_lock:
                now = time.time()
                to_remove = []
                for vtype, data in self.active_votes.items():
                     if now - data["start_time"] > vote_timeout:
                         to_remove.append(vtype)
                for vtype in to_remove:
                    del self.active_votes[vtype]
                if self.active_votes:
                     parts = []
                     for vtype, data in self.active_votes.items():
                         parts.append(f"{vtype.lower()}: {len(data['voters'])}/{data['target']}")
                     text = " | ".join(parts).lower()
                     current_vote_info = {"active": True, "text": f"[vote] {text}"}
                else:
                    current_vote_info = {"active": False, "text": "no active votes"}
        except Exception:
            pass
        finally:
            if self.running:
                self.root.after(refresh_rate, self.process_ui_queue)

    def save_session_data_threadsafe(self):
        try:
            url = self.active_url if self.active_url else ""
            mode = str(self.twenty_four_seven_mode)
            layout = str(keyboard_layout)
            with open(session_file, "w") as f:
                f.write(f"{url}|{mode}|{layout}")
        except:
            pass

    def parse_command(self, msg, user, is_mod=False, is_owner=False):
        global total_commands_executed
        self.last_command_time = time.time()
        if not msg.startswith(self.command_prefix): return
        first_word = msg.split()[0].lower()
        if first_word in self.custom_commands:
            macro_chain = self.custom_commands[first_word]
            self.parse_command(macro_chain.get("value", macro_chain), user, is_mod, is_owner)
            return
        clean_user = user.replace("@", "").lower().strip()
        if clean_user in self.blacklisted_users: return 
        for t in self.blocked_terms:
            if t in msg.lower(): return
        cmds = []
        if '|' in msg:
            cmds = msg.split('|')
        else:
            tokens = msg.split()
            curr = []
            for t in tokens:
                if t.startswith(self.command_prefix):
                    if curr: cmds.append(" ".join(curr))
                    curr = [t]
                else:
                    curr.append(t)
            if curr: cmds.append(" ".join(curr))
        action_chain = []
        for c in cmds:
            parts = c.strip().split(maxsplit=1)
            if not parts: continue
            raw_cmd = parts[0].lower()
            if not raw_cmd.startswith(self.command_prefix): continue
            cmd = "!" + raw_cmd[len(self.command_prefix):]
            aliases = {
                "!c": "!combo", "!k": "!key", "!t": "!type", "!s": "!send", 
                "!m": "!move", "!d": "!drag", "!w": "!wait", "!kd": "!keydown", 
                "!ku": "!keyup", "!lc": "!click", "!rc": "!rclick"
            }
            if cmd in aliases: cmd = aliases[cmd]
            arg = parts[1].strip() if len(parts) > 1 else ""
            total_commands_executed += 1
            if clean_user in owners or clean_user == "reallyiron": is_owner = True
            is_admin = is_owner or is_mod or user == "[console]" or user == "[CONSOLE]" or clean_user in admins
            if cmd == "!pausechat":
                if is_owner:
                    self.chat_paused = True
                    self.log("[system]", "chat has been paused by owner. only owners can send commands.", "sysmsg")
                continue
            if cmd == "!enablechat":
                if is_owner:
                    self.chat_paused = False
                    self.log("[system]", "chat has been unpaused. everyone can send commands again.", "sysmsg")
                continue
            if self.chat_paused and not is_owner: continue
            append_to_json_log(logs_file, user, f"{cmd} {arg}".strip())
            if is_admin: append_to_json_log(modlogs_file, user, f"{cmd} {arg}".strip())
            if cmd == "!ping":
                self.log("[system]", "pong! chat control is active.", "sysmsg")
                continue
            if cmd == "!uptime":
                uptime_sec = int(time.time() - script_start_time)
                m, s = divmod(uptime_sec, 60)
                h, m = divmod(m, 60)
                self.log("[system]", f"bot uptime: {h}h {m}m {s}s", "sysmsg")
                continue
            if cmd == "!opme":
                 if clean_user not in admins: admins.append(clean_user)
                 return
            if cmd == "!enablecv":
                 if is_owner: self.changevm_enabled = True
                 return
            if cmd in self.disabled_commands and not is_admin: continue
            if cmd in ["!votestop", "!clear", "!changevm", "!switchsnapshot", "!swichsnapshot", "!say", "!fixvm", "!forcefixvm", "!shutdown", "!remake2", "!makesnapshot"]:
                if cmd == "!say" and not self.say_admin_only:
                     if any(bad_word in arg.lower() for bad_word in banned_words): pass
                     else: self.log("[announcement]", arg, "sysmsg")
                     continue
                if is_admin:
                    if cmd == "!votestop":
                        with self.vote_lock: self.active_votes.clear()
                    elif cmd == "!clear":
                        global web_chat_history
                        with history_lock: web_chat_history.clear()
                    elif cmd == "!changevm":
                         if self.changevm_enabled: action_chain.append(("changevm", "", user))
                    elif cmd in ["!switchsnapshot", "!swichsnapshot"]:
                         snaps = get_vbox_snapshots(vbox_manage_cmd, vm_name)
                         if len(snaps) > 1:
                             try:
                                 idx = snaps.index(self.current_snapshot)
                                 self.current_snapshot = snaps[(idx + 1) % len(snaps)]
                             except ValueError: self.current_snapshot = snaps[-1]
                             self.log("[system]", f"switched to snapshot: {self.current_snapshot}", "sysmsg")
                             try:
                                 with open(snap_file, "w") as f: f.write(self.current_snapshot)
                             except: pass
                    elif cmd == "!makesnapshot": action_chain.append(("makesnapshot", arg, user))
                    elif cmd == "!say": self.log("[announcement]", arg, "sysmsg")
                    elif cmd == "!fixvm": action_chain.append(("fixvm", "", user))
                    elif cmd == "!shutdown": action_chain.append(("shutdown", "", user))
                    elif cmd == "!remake2": action_chain.append(("remake2", "", user))
                    elif cmd == "!forcefixvm": action_chain.append(("forcefixvm", "", user))
                    elif cmd == "!fixscript":
                        self.save_settings()
                        time.sleep(1)
                        script_path = os.path.abspath(sys.argv[0])
                        args = [sys.executable, script_path]
                        for arg_val in sys.argv:
                            if arg_val.startswith("--multistream"):
                                args.append(arg_val)
                                break
                        flags = 0x00000010 if platform.system() == "Windows" else 0
                        subprocess.Popen(args, creationflags=flags)
                        os._exit(0)
                    else: action_chain.append((cmd.replace("!", ""), arg, user))
                else:
                    if cmd == "!forcefixvm": self.process_vote(user, f"{self.command_prefix}forcefixvm", 2)
                    elif cmd == "!fixscript": self.process_vote(user, f"{self.command_prefix}fixscript", 2)
                continue
            if cmd == "!restartvm":
                if is_admin: action_chain.append(("restartvm", "", user))
                else: self.process_vote(user, f"{self.command_prefix}restartvm", 2)
                continue
            if cmd == "!revert":
                if self.revert_disabled:
                    self.log("[system]", "[warn] !revert is temporarily disabled while the system recovers.", "sysmsg")
                    continue
                if is_admin: action_chain.append(("revert", "", user))
                else: self.process_vote(user, f"{self.command_prefix}revert", 2)
                continue
            valid_user_cmds = ["!run", "!startvm", "!type", "!send", "!key", "!combo", "!keydown", "!keyup", "!move", "!abs", "!click", "!rclick", "!mclick", "!scroll", "!drag", "!wait", "!cmd", "!roll", "!coinflip"]
            if cmd in valid_user_cmds: action_chain.append((cmd, arg, user))
        if action_chain:
            self.trigger_command_chain(action_chain)

    def chat_listener_loop(self, thread_id=0):
        if not pytchat_available:
            while self.running and getattr(self, 'listener_id', 0) == thread_id:
                time.sleep(1)
            return
        chat = None
        connected_url = None
        retry_delay = 2 
        error_count = 0
        chat_start_time = time.time()
        self.last_msg_time = time.time()
        is_first_fetch = True
        is_connected = False
        first_connect = True
        while self.running and getattr(self, 'listener_id', 0) == thread_id:
            self.listener_tick = time.time()
            try:
                target_url = getattr(self, "active_url", None)
                if (target_url and target_url != connected_url) or (target_url and getattr(self, "force_connect", False)):
                    self.force_connect = False
                    if target_url == "[DEBUG_MODE]":
                        chat = "[DEBUG_MODE]"
                        connected_url = target_url
                        retry_delay = 2 
                    else:
                        try:
                            vid = self.resolve_live_video_id(target_url)
                            if vid and len(vid) == 11:
                                if self.config.get("strict_live_check", True):
                                    if not self.is_video_currently_live(vid):
                                        self.log("[system]", f"[warn] video {vid} is not currently live! refusing to connect.", "err")
                                        connected_url = target_url
                                        time.sleep(5)
                                        continue
                            if chat and hasattr(chat, 'terminate'):
                                try: chat.terminate()
                                except: pass
                            chat = pytchat.create(video_id=vid, interruptable=False)
                            if chat.is_alive():
                                connected_url = target_url
                                retry_delay = 2 
                                chat_start_time = time.time()
                                self.last_msg_time = time.time()
                                is_first_fetch = True
                                self.start_stats_thread()
                                if not is_connected:
                                    is_connected = True
                                    if first_connect:
                                        self.log("[system]", "connected to yt chat", "sysmsg")
                                        first_connect = False
                                    else:
                                        self.log("[system]", "successfully connected to yt chat", "sysmsg")
                            else:
                                 time.sleep(retry_delay)
                                 retry_delay = min(retry_delay * 2, 60) 
                                 if is_connected:
                                     self.log("[system]", "disconnected from yt connecting to stream", "sysmsg")
                                     is_connected = False
                        except Exception as parse_err:
                            err_msg = str(parse_err)
                            if "ReadTimeout" in err_msg or "timeout" in err_msg.lower() or "429" in err_msg:
                                self.log("[system]", f"[warn] youtube chat connection dropped. retrying in {retry_delay}s...", "sysmsg")
                            else:
                                console_log("ERROR", f"chat init error: {parse_err}\n{traceback.format_exc()}")
                                self.log("[system]", f"[error] chat init error: {parse_err}", "err")
                            chat = None
                            time.sleep(retry_delay)
                            retry_delay = min(retry_delay * 2, 60) 
                            if is_connected:
                                self.log("[system]", "disconnected from yt connecting to stream", "sysmsg")
                                is_connected = False
                try:
                    if chat == "[DEBUG_MODE]":
                        pass
                    elif chat and chat.is_alive():
                        if retry_delay > 2:
                            retry_delay = 2
                        if time.time() - chat_start_time > 21600:
                            if hasattr(self, 'resolved_id_cache'):
                                self.resolved_id_cache.clear()
                            if hasattr(chat, 'terminate'):
                                try: chat.terminate()
                                except: pass
                            chat = None
                            connected_url = None
                            chat_start_time = time.time()
                            self.last_msg_time = time.time()
                            continue
                        try:
                            chat_data = chat.get()
                        except Exception as e:
                            chat_data = None
                            time.sleep(1)
                        if chat_data:
                            error_count = 0
                            if is_first_fetch:
                                is_first_fetch = False
                                for c in chat_data.items:
                                    if hasattr(c, 'id'):
                                        self.processed_msg_ids.add(c.id)
                                continue
                            new_items = [c for c in chat_data.items if hasattr(c, 'id') and c.id not in self.processed_msg_ids]
                            for c in new_items:
                                self.last_msg_time = time.time()
                                self.processed_msg_ids.add(c.id)
                                if not self.listening_to_chat:
                                    continue 
                                msg_lower = c.message.lower().strip()
                                clean_name = c.author.name.replace("@", "").lower().strip()
                                if clean_name == "nightbot":
                                    continue
                                if clean_name in ["reallybotyt", "system"]:
                                    c.author.name = "[system]"
                                    is_owner = True
                                    is_mod = True
                                else:
                                    is_owner = c.author.isChatOwner or clean_name in owners or clean_name == "reallyiron"
                                    is_mod = is_owner or c.author.isChatModerator or clean_name in admins
                                if msg_lower.startswith(f"{self.command_prefix}forcefixvm"):
                                    if is_mod:
                                        if platform.system() == "Windows":
                                            subprocess.run(["taskkill", "/F", "/IM", "VirtualBoxVM.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                            subprocess.run(["taskkill", "/F", "/IM", "VirtualBox.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                        self.clear_commands()
                                        self.trigger_command(("!startvm", "", c.author.name))
                                    else:
                                        self.process_vote(c.author.name, f"{self.command_prefix}forcefixvm", 2)
                                    continue
                                elif msg_lower.startswith(f"{self.command_prefix}fixscript"):
                                    if is_mod:
                                        self.save_settings()
                                        time.sleep(1)
                                        script_path = os.path.abspath(sys.argv[0])
                                        args = [sys.executable, script_path]
                                        for arg_val in sys.argv:
                                            if arg_val.startswith("--multistream"):
                                                args.append(arg_val)
                                                break
                                        flags = 0x00000010 if platform.system() == "Windows" else 0
                                        subprocess.Popen(args, creationflags=flags)
                                        os._exit(0)
                                    else:
                                        self.process_vote(c.author.name, f"{self.command_prefix}fixscript", 2)
                                    continue
                                add_to_history(c.author.name, c.message, "user", is_mod, is_owner)
                                console_log("CHAT", f"[{c.author.name}]: {c.message}")
                                append_to_all_msgs_log(c.author.name, c.message)
                                if self.listening_to_chat:
                                    try:
                                        self.parse_command(c.message, c.author.name, is_mod, is_owner)
                                    except Exception as parse_err:
                                        console_log("ERROR", f"command parsing error: {parse_err}\n{traceback.format_exc()}")
                                        self.log("[system]", f"[error] command parsing error: {parse_err}", "err")
                            if len(self.processed_msg_ids) > 5000:
                                self.processed_msg_ids = set(list(self.processed_msg_ids)[-1000:])
                    elif chat and not chat.is_alive():
                        if is_connected:
                            self.log("[system]", "disconnected from yt connecting to stream", "sysmsg")
                            is_connected = False
                        if hasattr(self, 'resolved_id_cache'):
                            self.resolved_id_cache.clear()
                        if hasattr(chat, 'terminate'):
                            try: chat.terminate()
                            except: pass
                        chat = None
                        connected_url = None
                        chat_start_time = time.time()
                        self.last_msg_time = time.time()
                except Exception as e:
                    console_log("ERROR", f"chat listener error: {e}\n{traceback.format_exc()}")
                    self.log("[system]", f"[error] chat listener error: {e}", "err")
                    error_count += 1
                    if error_count > 5:
                        if hasattr(self, 'resolved_id_cache'):
                            self.resolved_id_cache.clear()
                        if chat and hasattr(chat, 'terminate'):
                            try: chat.terminate()
                            except: pass
                        chat = None
                        connected_url = None
                        error_count = 0
                        chat_start_time = time.time()
                time.sleep(0.001)
            except Exception as e:
                console_log("ERROR", f"critical chat error: {e}\n{traceback.format_exc()}")
                self.log("[system]", f"[error] critical chat error: {e}", "err")
                error_count += 1
                if error_count > 5:
                    if hasattr(self, 'resolved_id_cache'):
                        self.resolved_id_cache.clear()
                    connected_url = None
                    if chat and hasattr(chat, 'terminate'):
                        try: chat.terminate()
                        except: pass
                    chat = None
                    error_count = 0
                time.sleep(2)
        if chat and hasattr(chat, 'terminate'):
            try: chat.terminate()
            except: pass

    def _kill_vbox_tasks(self):
        if platform.system() == "Windows":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "VirtualBoxVM.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(["taskkill", "/F", "/IM", "VirtualBox.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except Exception as ex:
                self.log("[system]", f"[error] taskkill failed: {ex}", "err")
        time.sleep(2)

    def _start_vm_safely(self):
        if self.config.get("enable_starting_scene", True):
            set_obs_scene(OBS_SCENE_STARTING)
        self.log("[system]", f"[debug] executing startvm for {vm_name}...", "sysmsg")
        success = False
        err_text = ""
        for attempt in range(5):
            self.vm_start_time = time.time()
            res = subprocess.run([vbox_manage_cmd, "startvm", vm_name, "--type", "gui"], capture_output=True, text=True)
            if res.returncode == 0:
                success = True
                self.log("[system]", f"[debug] startvm successful. pinging...", "sysmsg")
                for _ in range(40):
                    try:
                        check_res = subprocess.run([vbox_manage_cmd, "list", "runningvms"], capture_output=True, text=True, timeout=2)
                        if f'"{vm_name}"' in check_res.stdout:
                            self.log("[system]", f"[debug] vm pinged true! ready.", "sysmsg")
                            break
                    except: pass
                    time.sleep(0.5)
                break
            else:
                err_text = res.stderr.strip()
                err_lower = err_text.lower()
                if "vboxhardening" in err_lower or "exit code 1" in err_lower:
                    self.log("[system]", f"[error] virtualbox hardening error! reboot pc.", "err")
                    console_log("ERROR", f"hardening error: {err_text}")
                    break
                if "0x80004005" in err_lower or "e_fail" in err_lower:
                    self.log("[system]", f"[warn] boot failed with e_fail. brutally killing vbox tasks to clear lock...", "sysmsg")
                    self._kill_vbox_tasks()
                    subprocess.run([vbox_manage_cmd, "discardstate", vm_name], capture_output=True, text=True, timeout=10)
                    time.sleep(1.0)
                    continue
                if "locked" in err_lower or "0x80bb0007" in err_lower:
                    self.log("[system]", f"[debug] lock lingering. waiting 2s...", "sysmsg")
                    time.sleep(2.0)
                else:
                    self.log("[system]", f"[error] startvm failed! code {res.returncode}.", "err")
                    console_log("ERROR", f"raw startvm error: {err_text}")
                    break
        if not success and ("locked" in err_text.lower() or "0x80bb0007" in err_text.lower()):
            self.log("[system]", f"[warn] locked! forcing taskkill...", "sysmsg")
            self._kill_vbox_tasks()
            subprocess.run([vbox_manage_cmd, "startvm", vm_name, "--type", "gui"], capture_output=True, text=True)
            self.vm_start_time = time.time()

    def _do_vm_maintenance(self, cmd_type, target_snap=None):
        now = time.time()
        self.log("[system]", f"[debug] requesting lock for: {cmd_type}", "sysmsg")
        if getattr(self, 'vm_maintenance', False) and (now - getattr(self, 'maintenance_start_time', 0) > 180):
            self.log("[system]", "[error] lock hung for 3 minutes! forcing release.", "err")
            try:
                self.maintenance_lock.release()
            except:
                pass
            self.vm_maintenance = False
        if cmd_type in ["forcefixvm", "startvm"]:
            try:
                self.maintenance_lock.release()
            except RuntimeError:
                pass
            self.maintenance_lock.acquire(blocking=True)
        else:
            self.log("[system]", f"[debug] waiting for vm lock...", "sysmsg")
            if not self.maintenance_lock.acquire(blocking=True, timeout=120.0):
                self.log("[system]", f"[warn] timed out waiting for vm.", "sysmsg")
                return
        self.log("[system]", f"[debug] lock acquired. starting {cmd_type}.", "sysmsg")
        self.vm_maintenance = True
        self.maintenance_start_time = time.time()
        self.revert_disabled = True 
        try:
            if getattr(self, 'shared_session', None):
                try: 
                    self.log("[system]", "[debug] unlocking session...", "sysmsg")
                    if vbox_pkg == "virtualbox":
                        self.shared_session.unlock_machine()
                    else:
                        self.shared_session.unlockMachine()
                except Exception as ex:
                    self.log("[system]", f"[debug] unlock failed: {ex}", "sysmsg")
            self.shared_session = None
            is_off = False
            if cmd_type == "startvm":
                try:
                    res = subprocess.run([vbox_manage_cmd, "list", "runningvms"], capture_output=True, text=True, timeout=3)
                    if f'"{vm_name}"' in res.stdout:
                        self.log("[system]", f"[warn] {vm_name} already running! ignoring.", "sysmsg")
                        return
                except:
                    pass
            if cmd_type in ["changevm", "shutdown", "restartvm", "remake2", "revert", "fixvm", "forcefixvm"]:
                try:
                    self.log("[system]", f"[debug] sending poweroff...", "sysmsg")
                    subprocess.run([vbox_manage_cmd, "controlvm", vm_name, "poweroff"], capture_output=True, text=True, timeout=5)
                except Exception as ex:
                    self.log("[system]", f"[error] poweroff exception: {ex}", "err")
                self.log("[system]", f"[debug] waiting for power off...", "sysmsg")
                for _ in range(15): 
                    try:
                        res = subprocess.run([vbox_manage_cmd, "list", "runningvms"], capture_output=True, text=True, timeout=3)
                        if f'"{vm_name}"' not in res.stdout:
                            is_off = True
                            self.log("[system]", f"[debug] vm is powered off.", "sysmsg")
                            break
                    except Exception as ex:
                        self.log("[system]", f"[error] list vms error: {ex}", "err")
                    time.sleep(0.5)
                self.log("[system]", "[debug] forcing lock release...", "sysmsg")
                if platform.system() == "Windows":
                    subprocess.run(["taskkill", "/F", "/IM", "VirtualBoxVM.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run([vbox_manage_cmd, "startvm", vm_name, "--type", "emergencystop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                if not is_off:
                    self.log("[system]", f"[debug] still running. killing tasks...", "sysmsg")
                    self._kill_vbox_tasks()
                else:
                    time.sleep(1.0)
            if cmd_type == "changevm":
                self.root.after(0, self.cycle_vm)
                time.sleep(0.5) 
                self._start_vm_safely()
            elif cmd_type in ["startvm", "restartvm", "fixvm", "forcefixvm"]:
                self._start_vm_safely()
            elif cmd_type in ["revert", "remake2"]:
                self.log("[system]", f"[debug] fetching snapshots...", "sysmsg")
                actual_snaps = get_vbox_snapshots(vbox_manage_cmd, vm_name)
                self.log("[system]", f"[debug] snapshots: {actual_snaps}", "sysmsg")
                if not target_snap or target_snap not in actual_snaps:
                    if not actual_snaps:
                        self.log("[system]", f"[error] no snapshots exist! killing tasks...", "sysmsg")
                        self._kill_vbox_tasks()
                        self._start_vm_safely()
                        return
                    else:
                        self.log("[system]", f"[warn] '{target_snap}' not found. falling back to '{actual_snaps[-1]}'", "sysmsg")
                        target_snap = actual_snaps[-1]
                        self.current_snapshot = target_snap
                        try:
                            with open(snap_file, "w") as f: f.write(target_snap)
                        except Exception as ex:
                            self.log("[system]", f"[error] snap file write: {ex}", "err")
                try:
                    self.log("[system]", f"[debug] restoring '{target_snap}'...", "sysmsg")
                    restore_success = False
                    for attempt in range(5):
                        res = subprocess.run([vbox_manage_cmd, "snapshot", vm_name, "restore", target_snap], capture_output=True, text=True, timeout=60)
                        if res.returncode == 0:
                            restore_success = True
                            self.log("[system]", f"[debug] restore successful.", "sysmsg")
                            break
                        else:
                            err_msg = res.stderr.lower()
                            if "locked" in err_msg or "0x80bb0007" in err_msg:
                                self.log("[system]", f"[debug] lock lingering. waiting 2s...", "sysmsg")
                                time.sleep(2.0)
                            else:
                                break
                    if not restore_success:
                        self.log("[system]", f"[error] restore failed. forcing cleanup...", "sysmsg")
                        self._kill_vbox_tasks()
                except subprocess.TimeoutExpired:
                    self.log("[system]", "[error] restore timed out! cleanup...", "sysmsg")
                    self._kill_vbox_tasks()
                except Exception as e:
                    console_log("ERROR", f"snapshot exception: {e}\n{traceback.format_exc()}")
                    self.log("[system]", f"[error] snapshot exception: {e}", "err")
                time.sleep(0.5)
                self._start_vm_safely()
        except Exception as maint_e:
            console_log("ERROR", f"maintenance exception: {maint_e}\n{traceback.format_exc()}")
            self.log("[system]", f"[error] maintenance exception: {maint_e}", "err")
        finally:
            self.log("[system]", "[debug] maintenance complete. releasing locks.", "sysmsg")
            set_obs_scene(obs_scene_main)
            self.vm_start_time = time.time()
            self.vm_crashed = False
            self.vm_maintenance = False
            self.revert_disabled = False 
            self.maintenance_gen += 1
            self.clear_commands()
            try:
                self.maintenance_lock.release()
            except RuntimeError:
                pass

    def run_cmd_worker(self, action_tuple):
        cmd, arg, user = action_tuple
        try:
            try:
                if 'pythoncom' in sys.modules:
                    pythoncom.CoInitialize()
            except Exception:
                pass
            cmd_clean = cmd if cmd.startswith(self.command_prefix) else self.command_prefix + cmd
            core_cmd = cmd_clean.lstrip("!").lstrip(self.command_prefix).lower()
            if core_cmd == "admin_cmd":
                core_cmd = "cmd"
            maintenance_cmds = ["startvm", "changevm", "shutdown", "restartvm", "remake2", "revert", "makesnapshot", "fixvm", "forcefixvm"]
            if self.vm_maintenance and core_cmd in maintenance_cmds and core_cmd not in ["forcefixvm", "startvm"]:
                self.log("[system]", f"[warn] '{core_cmd}' blocked: vm busy.", "sysmsg")
                return
            if self.vm_maintenance and core_cmd not in maintenance_cmds:
                return
            if getattr(self, 'vm_frozen_since', None) is not None and core_cmd not in maintenance_cmds:
                return
            display_cmd = f"{self.command_prefix}{core_cmd}"
            echo_msg = f"running: {display_cmd} {arg}".strip()
            if getattr(self, 'echo_commands', True):
                self.log("[system]", echo_msg, "sysmsg")
            self.active_com_time = time.time()
            self.is_com_active = True
            if core_cmd not in maintenance_cmds and core_cmd not in ["roll", "coinflip"] and (not getattr(self, 'shared_kb', None) or not getattr(self, 'shared_mouse', None)):
                for _ in range(200):
                    time.sleep(0.05)
                    if getattr(self, 'shared_kb', None) and getattr(self, 'shared_mouse', None):
                        break
            if core_cmd not in maintenance_cmds and core_cmd not in ["roll", "coinflip"] and (not getattr(self, 'shared_kb', None) or not getattr(self, 'shared_mouse', None)):
                self.log("[system]", f"[warn] '{display_cmd}' dropped: com disconnected. rebuilding...", "err")
                self.force_session_refresh = True
                return
            lm = getattr(self, 'lag_multiplier', 1.0)
            try:
                if self.ultra_speed:
                    base_type_spd, base_key_del, base_mouse_del, max_wait = 0.001, 0.001, 0.001, 20.0
                else:
                    base_type_spd = float(self.config.get("typing_speed", 0.02))
                    base_key_del = float(self.config.get("key_delay", 0.02))
                    base_mouse_del = float(self.config.get("mouse_delay", 0.005))
                    max_wait = float(self.config.get("max_wait_time", 20.0))
            except:
                base_type_spd, base_key_del, base_mouse_del, max_wait = 0.02, 0.02, 0.005, 20.0

            def get_release_codes(codes):
                rel = []
                for c in codes:
                    if c in (224, 225):
                        rel.append(c)
                    else:
                        rel.append(c | 0x80)
                return rel

            def handle_input_error(err_obj, action="input"):
                self.force_session_refresh = True
                self.log("[system]", f"[error] com lost during {action}: {err_obj}", "err")
                console_log("ERROR", f"input com error: {err_obj}\n{traceback.format_exc()}")
                raise Exception("ABORT")

            def safe_put_scancodes(codes):
                if getattr(self, 'force_session_refresh', False):
                    raise Exception("ABORT")
                if self.config.get("show_scancodes", False):
                    self.log("[system]", f"[debug] sending scancodes: {codes}", "sysmsg")
                with self.input_lock:
                    for attempt in range(3):
                        kb_obj = getattr(self, 'shared_kb', None)
                        if not kb_obj:
                            time.sleep(0.05 * lm)
                            continue
                        try:
                            int_codes = [int(c) for c in codes]
                            if hasattr(kb_obj, 'put_scancodes'):
                                res = kb_obj.put_scancodes(int_codes)
                            else:
                                res = kb_obj.putScancodes(int_codes)
                            if res == 0:
                                self.log("[system]", "[warn] com stale (0 bytes). forcing instant rebuild.", "sysmsg")
                                self.force_session_refresh = True
                                raise Exception("COM STALE")
                            return
                        except Exception as e:
                            time.sleep(0.01 * lm)
                            last_e = e
                    try:
                        handle_input_error(last_e, "scancodes")
                    except:
                        raise Exception("ABORT")

            def press_scancodes_vbox(codes, delay=base_key_del):
                if getattr(self, 'force_session_refresh', False):
                    raise Exception("ABORT")
                with self.input_lock:
                    safe_put_scancodes(codes)
                    time.sleep(delay * lm) 
                    safe_put_scancodes(get_release_codes(codes))

            def type_char_smart(char, type_delay=base_type_spd):
                if getattr(self, 'force_session_refresh', False):
                    raise Exception("ABORT")
                modifiers, base_code = get_typed_codes(char, keyboard_layout)
                if base_code == [0]:
                    return
                with self.input_lock:
                    for mod in modifiers:
                        safe_put_scancodes(mod)
                        time.sleep(0.002 * lm) 
                    press_scancodes_vbox(base_code, delay=type_delay)
                    for mod in reversed(modifiers):
                        time.sleep(0.002 * lm)
                        if mod == [0x2A]:
                            safe_put_scancodes([0xAA])
                        elif mod == [0xE0, 0x38]:
                            safe_put_scancodes([0xE0, 0xB8])
                        else:
                            safe_put_scancodes(get_release_codes(mod))
                        time.sleep(0.002 * lm)
                    dead_keys = {"DANISH": ['~', '^', '`', '´', '¨'], "GERMAN": ['^', '`', '´'], "FRENCH": ['^', '¨'], "TURKISH": ['~', '^', '`', '´', '¨'], "UK": ['`']}
                    if char in dead_keys.get(keyboard_layout, []):
                        time.sleep(0.01 * lm)
                        press_scancodes_vbox([0x39], delay=type_delay)

            def safe_put_mouse_event(dx, dy, dz, dw, button_state):
                if getattr(self, 'force_session_refresh', False):
                    raise Exception("ABORT")
                with self.input_lock:
                    for attempt in range(3):
                        mouse_obj = getattr(self, 'shared_mouse', None)
                        if not mouse_obj:
                            time.sleep(0.05 * lm)
                            continue
                        try:
                            if hasattr(mouse_obj, 'put_mouse_event'):
                                mouse_obj.put_mouse_event(int(dx), int(dy), int(dz), int(dw), int(button_state))
                            else:
                                mouse_obj.putMouseEvent(int(dx), int(dy), int(dz), int(dw), int(button_state))
                            return
                        except Exception as e:
                            time.sleep(0.01 * lm)
                            last_e = e
                    try:
                        handle_input_error(last_e, "mouse")
                    except:
                        raise Exception("ABORT")

            def safe_put_mouse_event_absolute(x, y, dz, dw, button_state):
                if getattr(self, 'force_session_refresh', False):
                    raise Exception("ABORT")
                with self.input_lock:
                    for attempt in range(3):
                        mouse_obj = getattr(self, 'shared_mouse', None)
                        if not mouse_obj:
                            time.sleep(0.05 * lm)
                            continue
                        try:
                            if hasattr(mouse_obj, 'put_mouse_event_absolute'):
                                mouse_obj.put_mouse_event_absolute(int(x), int(y), int(dz), int(dw), int(button_state))
                            else:
                                mouse_obj.putMouseEventAbsolute(int(x), int(y), int(dz), int(dw), int(button_state))
                            return
                        except Exception as e:
                            time.sleep(0.01 * lm)
                            last_e = e
                    try:
                        handle_input_error(last_e, "mouse_abs")
                    except:
                        raise Exception("ABORT")

            def do_mouse_click(btn_code, count_str):
                if getattr(self, 'force_session_refresh', False):
                    raise Exception("ABORT")
                count = 1
                if count_str.isdigit():
                    count = int(count_str)
                with self.input_lock:
                    for _ in range(min(count, 50)):
                        safe_put_mouse_event(0, 0, 0, 0, self.vbox_mouse_btns | btn_code)
                        time.sleep(base_mouse_del * lm)
                        safe_put_mouse_event(0, 0, 0, 0, self.vbox_mouse_btns & ~btn_code)
                        time.sleep(base_mouse_del * lm)

            def run_windows_command(command_str, is_admin=False):
                if getattr(self, 'force_session_refresh', False):
                    raise Exception("ABORT")
                with self.input_lock:
                    safe_put_scancodes(scancodes.get('win', [224, 91]))
                    time.sleep(0.2 * lm)
                    type_char_smart('r', type_delay=base_type_spd)
                    time.sleep(0.2 * lm)
                    safe_put_scancodes(get_release_codes(scancodes.get('win', [224, 91])))
                    time.sleep(0.5 * lm) 
                    full_cmd = f"cmd /c {command_str}" if is_admin else command_str
                    for char in full_cmd:
                        type_char_smart(char, type_delay=base_type_spd)
                        time.sleep(0.005 * lm) 
                    time.sleep(0.1 * lm) 
                    if is_admin:
                        safe_put_scancodes(scancodes['lctrl'])
                        safe_put_scancodes(scancodes['lshift'])
                        time.sleep(0.1 * lm)
                        press_scancodes_vbox(scancodes['enter'], delay=base_key_del)
                        time.sleep(0.1 * lm)
                        safe_put_scancodes(get_release_codes(scancodes['lshift']))
                        safe_put_scancodes(get_release_codes(scancodes['lctrl']))
                        time.sleep(0.5 * lm)
                        press_scancodes_vbox(scancodes['left'], delay=base_key_del)
                        time.sleep(0.1 * lm)
                    press_scancodes_vbox(scancodes['enter'], delay=base_key_del)
                    time.sleep(0.5 * lm)

            if core_cmd == "wait":
                try:
                    wait_time = max(0.0, min(float(arg), max_wait))
                    end_time = time.time() + wait_time
                    while time.time() < end_time and self.running:
                        time.sleep(0.1)
                except ValueError:
                    self.log("[system]", f"[error] invalid wait time: '{arg}'", "sysmsg")
            elif core_cmd == "startvm":
                self._do_vm_maintenance("startvm")
            elif core_cmd == "changevm":
                set_obs_scene(obs_scene_changevm) 
                self._do_vm_maintenance("changevm")
            elif core_cmd == "shutdown":
                self._do_vm_maintenance("shutdown")
                self.vm_crashed = True
            elif core_cmd == "restartvm":
                self._do_vm_maintenance("restartvm")
            elif core_cmd == "remake2":
                self.current_snapshot = "SnapshotRemake2"
                try:
                    with open(snap_file, "w") as f:
                        f.write(self.current_snapshot)
                except:
                    pass
                set_obs_scene("remake 2")
                self._do_vm_maintenance("remake2", self.current_snapshot)
            elif core_cmd == "revert": 
                set_obs_scene(obs_scene_revert) 
                self._do_vm_maintenance("revert", self.current_snapshot)
            elif core_cmd == "makesnapshot":
                snap_name = arg if arg else f"ManualSnap_{int(time.time())}"
                if not self.maintenance_lock.acquire(blocking=False):
                    self.log("[system]", "[warn] snapshot ignored: vm busy.", "sysmsg")
                    return
                self.vm_maintenance = True
                try:
                    session_locked = False
                    if getattr(self, 'shared_session', None):
                        if vbox_pkg == "virtualbox" and self.shared_session.state == virtualbox.library.SessionState.locked:
                            session_locked = True
                        elif vbox_pkg == "vboxapi" and self.shared_session.state == self.mgr.constants.SessionState_Locked:
                            session_locked = True
                    if session_locked:
                        try:
                            if vbox_pkg == "virtualbox":
                                self.shared_session.unlock_machine()
                            else:
                                self.shared_session.unlockMachine()
                        except Exception:
                            pass
                    self.log("[system]", f"[debug] creating snapshot '{snap_name}'...", "sysmsg")
                    res = subprocess.run([vbox_manage_cmd, "snapshot", vm_name, "take", snap_name, "--live"], capture_output=True, text=True, timeout=60)
                    self.log("[system]", f"[debug] snapshot result: {res.returncode}", "sysmsg")
                    if res.returncode == 0:
                        self.current_snapshot = snap_name
                        self.log("[system]", f"snapshot {snap_name} created!", "sysmsg")
                        try:
                            with open(snap_file, "w") as f:
                                f.write(snap_name)
                        except:
                            pass
                    else:
                        self.log("[system]", f"[error] snapshot failed: {res.stderr.strip()}", "sysmsg")
                except Exception as e:
                    console_log("ERROR", f"snapshot exception: {e}\n{traceback.format_exc()}")
                    self.log("[system]", f"[error] snapshot exception: {e}", "err")
                finally:
                    self.vm_maintenance = False
                    self.maintenance_gen += 1
                    self.clear_commands()
                    try:
                        self.maintenance_lock.release()
                    except RuntimeError:
                        pass
            elif core_cmd == "fix":
                set_obs_scene(obs_scene_main)
            elif core_cmd == "fixvm":
                set_obs_scene(obs_scene_revert) 
                self._do_vm_maintenance("fixvm")
            elif core_cmd == "forcefixvm":
                set_obs_scene(obs_scene_revert) 
                self._do_vm_maintenance("forcefixvm")
            elif core_cmd == "cmd":
                run_windows_command(arg, is_admin=True)
            elif core_cmd in ["run", "open_app"]:
                run_windows_command(arg, is_admin=False)
            elif core_cmd == "roll":
                res = str(random.randint(1, 100))
                with self.input_lock:
                    for char in f"rolling... {res}": 
                        type_char_smart(char, type_delay=base_type_spd)
                        time.sleep(0.005 * lm)
                    time.sleep(0.1 * lm)
                    press_scancodes_vbox(scancodes['enter'], delay=base_key_del)
            elif core_cmd == "coinflip":
                res = random.choice(["heads", "tails"])
                with self.input_lock:
                    for char in res: 
                        type_char_smart(char, type_delay=base_type_spd)
                        time.sleep(0.005 * lm)
                    time.sleep(0.1 * lm)
                    press_scancodes_vbox(scancodes['enter'], delay=base_key_del)
            elif core_cmd == "type":
                if len(arg) >= 2 and arg.startswith('"') and arg.endswith('"'):
                    arg = arg[1:-1]
                with self.input_lock:
                    for char in arg: 
                        type_char_smart(char, type_delay=base_type_spd)
                        time.sleep(0.005 * lm) 
            elif core_cmd == "send":
                if len(arg) >= 2 and arg.startswith('"') and arg.endswith('"'):
                    arg = arg[1:-1]
                with self.input_lock:
                    for char in arg: 
                        type_char_smart(char, type_delay=base_type_spd)
                        time.sleep(0.005 * lm) 
                    time.sleep(0.1 * lm)
                    press_scancodes_vbox(scancodes['enter'], delay=base_key_del)
            elif core_cmd == "combo":
                keys = arg.split("+")
                with self.input_lock:
                    pressed_codes = []
                    valid_combo = True
                    for k in keys:
                        k = k.strip()
                        if k.lower() in scancodes:
                            codes = scancodes[k.lower()]
                            safe_put_scancodes(codes)
                            pressed_codes.append(codes)
                            time.sleep(0.1 * lm) 
                        else:
                            self.log("[system]", f"[error] key '{k}' not found.", "sysmsg")
                            valid_combo = False
                            break
                    if valid_combo:
                        time.sleep(0.1 * lm) 
                    for codes in reversed(pressed_codes):
                        safe_put_scancodes(get_release_codes(codes))
                        time.sleep(0.02 * lm) 
                    time.sleep(0.5 * lm)
            elif core_cmd == "keydown":
                if arg.lower() in scancodes:
                    safe_put_scancodes(scancodes[arg.lower()])
                else:
                    self.log("[system]", f"[error] key '{arg}' not found.", "sysmsg")
            elif core_cmd == "keyup":
                if arg.lower() in scancodes:
                    safe_put_scancodes(get_release_codes(scancodes[arg.lower()]))
                else:
                    self.log("[system]", f"[error] key '{arg}' not found.", "sysmsg")
            elif core_cmd == "key":
                with self.input_lock:
                    if arg.lower() in scancodes:
                        safe_put_scancodes(scancodes[arg.lower()])
                        time.sleep(max(0.1, base_key_del * lm))
                        safe_put_scancodes(get_release_codes(scancodes[arg.lower()]))
                        if arg.lower() in ['win', 'lwin', 'rwin', 'cmd', 'super', 'menu', 'esc', 'enter', 'return']:
                            time.sleep(0.5 * lm)
                    elif len(arg) == 1:
                        type_char_smart(arg, type_delay=base_type_spd)
                    else:
                        self.log("[system]", f"[error] key '{arg}' not found.", "sysmsg")
            elif core_cmd == "click":
                do_mouse_click(0x01, arg)
            elif core_cmd == "rclick":
                do_mouse_click(0x02, arg)
            elif core_cmd == "mclick":
                do_mouse_click(0x04, arg)
            elif core_cmd == "move":
                args = arg.split()
                if len(args) == 2:
                    try:
                        dir = args[0].lower()
                        amt = int(args[1])
                        dx = -amt if dir == "left" else (amt if dir == "right" else 0)
                        dy = -amt if dir == "up" else (amt if dir == "down" else 0)
                        with self.input_lock:
                            safe_put_mouse_event(dx, dy, 0, 0, self.vbox_mouse_btns)
                    except ValueError:
                        pass
            elif core_cmd == "abs":
                args = arg.split()
                if len(args) == 2:
                    try:
                        x, y = int(args[0]), int(args[1])
                        with self.input_lock:
                            safe_put_mouse_event_absolute(x, y, 0, 0, self.vbox_mouse_btns)
                    except ValueError:
                        pass
            elif core_cmd == "drag":
                args = arg.split()
                if len(args) == 2:
                    try:
                        dx, dy = int(args[0]), int(args[1])
                        with self.input_lock:
                            safe_put_mouse_event(0, 0, 0, 0, self.vbox_mouse_btns | 0x01)
                            time.sleep(base_mouse_del * lm)
                            steps = 5
                            for i in range(1, steps + 1):
                                step_x = dx // steps
                                step_y = dy // steps
                                safe_put_mouse_event(step_x, step_y, 0, 0, self.vbox_mouse_btns | 0x01)
                                time.sleep(base_mouse_del * lm)
                            safe_put_mouse_event(0, 0, 0, 0, self.vbox_mouse_btns & ~0x01)
                    except ValueError:
                        pass
            elif core_cmd == "scroll":
                try:
                    amt = int(arg)
                    btn = 8 if amt > 0 else 16
                    with self.input_lock:
                        for _ in range(min(abs(amt), 50)):
                            safe_put_mouse_event(0, 0, 0, 0, self.vbox_mouse_btns | btn)
                            time.sleep(base_mouse_del * lm)
                            safe_put_mouse_event(0, 0, 0, 0, self.vbox_mouse_btns & ~btn)
                            time.sleep(base_mouse_del * lm)
                except ValueError:
                    pass
            self.consecutive_failures = 0
            self.last_success_time = time.time()
        except Exception as loop_e:
            if "ABORT" not in str(loop_e):
                global total_commands_failed
                total_commands_failed += 1
                self.consecutive_failures = getattr(self, 'consecutive_failures', 0) + 1
                console_log("ERROR", f"execution failed: {display_cmd} {arg}: {loop_e}\n{traceback.format_exc()}")
                self.log("[system]", f"[error] something went wrong: {loop_e}", "err")
        finally:
            self.is_com_active = False
            try:
                if 'pythoncom' in sys.modules:
                    pythoncom.CoUninitialize()
            except Exception:
                pass

    def action_processor_loop(self):
        try:
            if 'pythoncom' in sys.modules:
                pythoncom.CoInitialize()
        except Exception:
            pass
        while self.running:
            try:
                action = self.cmd_queue.get(timeout=1.0)
                self.run_cmd_worker(action)
            except queue.Empty:
                pass
            except Exception as e:
                self.log("[system]", f"[error] action loop: {e}", "err")
        try:
            if 'pythoncom' in sys.modules:
                pythoncom.CoUninitialize()
        except Exception:
            pass

    def executor_loop(self, thread_id=0):
        try: signal.signal = lambda *args, **kwargs: None
        except Exception: pass
        try:
            if 'pythoncom' in sys.modules:
                pythoncom.CoInitialize()
        except Exception:
            pass
        while self.running and getattr(self, 'executor_id', 0) == thread_id:
            self.executor_tick = time.time()
            try:
                if getattr(self, 'vm_maintenance', False):
                    if getattr(self, 'shared_session', None):
                        try:
                            if vbox_pkg == "virtualbox" and self.shared_session.state == virtualbox.library.SessionState.locked:
                                self.shared_session.unlock_machine()
                            elif vbox_pkg == "vboxapi" and self.shared_session.state == self.mgr.constants.SessionState_Locked:
                                self.shared_session.unlockMachine()
                        except:
                            pass
                    self.shared_session = None
                    time.sleep(0.5)
                    continue
                if self.vbox is None:
                    try:
                        if vbox_pkg == "virtualbox":
                            self.vbox = virtualbox.VirtualBox()
                        elif vbox_pkg == "vboxapi":
                            self.mgr = VirtualBoxManager(None, None)
                            self.vbox = self.mgr.getVirtualBox()
                        if self.vbox:
                            set_obs_scene(obs_scene_main) 
                    except Exception as e: 
                        set_obs_scene(obs_scene_error)
                        self.log("[system]", f"[error] failed to init vbox api: {e}", "err")
                        if getattr(self, 'vbox', None):
                            del self.vbox
                        self.vbox = None
                        time.sleep(2)
                        continue 
                current_time = time.time()
                if getattr(self, 'shared_session', None) and (current_time - getattr(self, 'last_com_rebuild_time', current_time)) > 300:
                    self.log("[system]", "[debug] scheduled 5-min com memory rebuild to prevent freezing...", "sysmsg")
                    self.force_session_refresh = True
                    self.last_com_rebuild_time = current_time
                if current_time - getattr(self, 'last_health_check', 0) > 0.5: 
                    self.last_health_check = current_time
                    if getattr(self, 'force_session_refresh', False):
                        self.force_session_refresh = False
                        self.log("[system]", "[debug] rebuilding memory...", "sysmsg")
                        try:
                            if getattr(self, 'shared_session', None):
                                if vbox_pkg == "virtualbox" and self.shared_session.state == virtualbox.library.SessionState.locked:
                                    self.shared_session.unlock_machine()
                                elif vbox_pkg == "vboxapi" and self.shared_session.state == self.mgr.constants.SessionState_Locked:
                                    self.shared_session.unlockMachine()
                        except Exception:
                            pass
                        self.shared_session = None
                        self.shared_kb = None
                        self.shared_mouse = None
                        if getattr(self, 'vbox', None):
                            del self.vbox
                        self.vbox = None
                        try:
                            if 'pythoncom' in sys.modules:
                                pythoncom.CoFreeUnusedLibraries()
                        except:
                            pass
                        gc.collect() 
                        time.sleep(0.01) 
                        continue
                    machine_check = None
                    try:
                        if vbox_pkg == "virtualbox":
                            machine_check = self.vbox.find_machine(vm_name)
                        else:
                            machine_check = self.vbox.findMachine(vm_name)
                    except Exception:
                        pass 
                    if machine_check:
                        try:
                            m_state = machine_check.state
                        except Exception:
                            if vbox_pkg == "virtualbox":
                                m_state = virtualbox.library.MachineState.running 
                            else:
                                m_state = self.mgr.constants.MachineState_Running
                        is_running = False
                        if vbox_pkg == "virtualbox" and m_state == virtualbox.library.MachineState.running:
                            is_running = True
                        elif vbox_pkg == "vboxapi" and m_state == self.mgr.constants.MachineState_Running:
                            is_running = True
                        if is_running:
                            self.set_status("running")
                            session_locked = False
                            try:
                                if getattr(self, 'shared_session', None):
                                    if vbox_pkg == "virtualbox" and self.shared_session.state == virtualbox.library.SessionState.locked:
                                        session_locked = True
                                    elif vbox_pkg == "vboxapi" and self.shared_session.state == self.mgr.constants.SessionState_Locked:
                                        session_locked = True
                            except Exception:
                                session_locked = True 
                            if not session_locked:
                                if vbox_pkg == "virtualbox":
                                    session = virtualbox.Session()
                                else:
                                    session = self.mgr.getSessionObject(self.vbox)
                                lock_attempts = 0
                                is_session_locked = False
                                while not is_session_locked and lock_attempts < 20:
                                    if vbox_pkg == "virtualbox":
                                        is_session_locked = (session.state == virtualbox.library.SessionState.locked)
                                    else:
                                        is_session_locked = (session.state == self.mgr.constants.SessionState_Locked)
                                    if not is_session_locked:
                                        if time.time() - getattr(self, 'vm_start_time', 0) > 0.5:
                                            try:
                                                if vbox_pkg == "virtualbox":
                                                    machine_check.lock_machine(session, virtualbox.library.LockType.shared)
                                                else:
                                                    machine_check.lockMachine(session, self.mgr.constants.LockType_Shared)
                                            except Exception:
                                                time.sleep(0.05) 
                                        lock_attempts += 1
                                if vbox_pkg == "virtualbox" and session.state == virtualbox.library.SessionState.locked:
                                    self.shared_session = session
                                    self.shared_kb = session.console.keyboard
                                    self.shared_mouse = session.console.mouse
                                    self.last_com_rebuild_time = time.time()
                                elif vbox_pkg == "vboxapi" and session.state == self.mgr.constants.SessionState_Locked:
                                    self.shared_session = session
                                    self.shared_kb = session.console.keyboard
                                    self.shared_mouse = session.console.mouse
                                    self.last_com_rebuild_time = time.time()
                                else:
                                    self.shared_session = None
                                    self.shared_kb = None
                                    self.shared_mouse = None
                        else:
                            self.set_status("stopped")
                            self.shared_session = None
                            self.shared_kb = None
                            self.shared_mouse = None
                time.sleep(0.01) 
            except Exception:
                time.sleep(1)

    def error_watcher_loop(self):
        if platform.system() != "Windows": return
        user32 = ctypes.windll.user32
        wndenumproc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [wndenumproc, wintypes.LPARAM]
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsHungAppWindow.argtypes = [wintypes.HWND]
        user32.IsHungAppWindow.restype = wintypes.BOOL
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        wm_close = 0x0010
        hung_state = {"found": False}
        @wndenumproc
        def foreach_window(hwnd, lParam):
            if not user32.IsWindowVisible(hwnd): return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0: return True
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.lower()
            class_buff = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buff, 256)
            cls_name = class_buff.value
            error_titles = ["virtualbox - error", "suplibosinit", "application error", "fatal:", "guru meditation", "not responding", "svarer ikke", "keine rückmeldung", "pas de réponse", "yanıt vermiyor"]
            if any(err in title for err in error_titles) or (cls_name == "#32770" and "virtualbox" in title):
                self.vm_crashed = True
                user32.PostMessageW(hwnd, wm_close, 0, 0)
                return True
            if vm_name.lower() in title and ("virtualbox" in title or "oracle" in title):
                if user32.IsHungAppWindow(hwnd): hung_state["found"] = True
            return True
        while self.running:
            if getattr(self, 'vm_maintenance', False):
                self.vm_frozen_since = None
                self.executor_tick = time.time()
                self.active_com_time = time.time()
                time.sleep(1.0)
                continue
            hung_state["found"] = False
            try: user32.EnumWindows(foreach_window, 0)
            except Exception: pass
            api_frozen_timeout = (time.time() - getattr(self, 'executor_tick', time.time())) > 25
            com_stuck = getattr(self, 'is_com_active', False) and (time.time() - getattr(self, 'active_com_time', time.time())) > 30
            is_frozen = hung_state["found"] or api_frozen_timeout or com_stuck
            if is_frozen:
                if getattr(self, 'vm_frozen_since', None) is None:
                    self.vm_frozen_since = time.time()
                    self.revert_disabled = True
                    reason = "ui" if hung_state["found"] else ("com stuck" if com_stuck else "api")
                    self.log("[system]", f"[warn] virtualbox {reason} frozen. watchdog active...", "sysmsg")
                else:
                    frozen_duration = time.time() - self.vm_frozen_since
                    if frozen_duration >= 20:
                        time_since_last_action = time.time() - getattr(self, 'last_watchdog_action_time', 0)
                        if time_since_last_action > 120: self.watchdog_action_level = 0
                        if getattr(self, 'watchdog_action_level', 0) == 0:
                            self.log("[system]", "[error] vm frozen for 20s! auto-reverting...", "sysmsg")
                            self.watchdog_action_level = 1
                            self.last_watchdog_action_time = time.time()
                            self.vm_frozen_since = None
                            self.trigger_command(("revert", "", "watchdog"))
                        else:
                            self.log("[system]", "[error] vm still frozen! killing tasks...", "sysmsg")
                            self.watchdog_action_level = 2
                            self.last_watchdog_action_time = time.time()
                            self.vm_frozen_since = None
                            self._kill_vbox_tasks()
                            if self.config.get("enable_starting_scene", True): set_obs_scene(obs_scene_starting)
                            subprocess.Popen([vbox_manage_cmd, "startvm", vm_name, "--type", "gui"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            time.sleep(15)
                            set_obs_scene(obs_scene_main)
                            self.watchdog_action_level = 0
            else:
                if getattr(self, 'vm_frozen_since', None) is not None:
                    self.log("[system]", "virtualbox recovered.", "sysmsg")
                    self.vm_frozen_since = None
                    self.watchdog_action_level = 0
                    self.revert_disabled = False
            if getattr(self, 'consecutive_failures', 0) >= 10 and (time.time() - getattr(self, 'last_success_time', time.time())) >= 20:
                time_since_last_api_action = time.time() - getattr(self, 'last_api_watchdog_action_time', 0)
                if time_since_last_api_action > 120: self.api_watchdog_level = 0
                if getattr(self, 'api_watchdog_level', 0) == 0:
                    self.log("[system]", "[error] virtualbox api unresponsive! auto-reverting...", "sysmsg")
                    self.api_watchdog_level = 1
                    self.last_api_watchdog_action_time = time.time()
                    self.last_success_time = time.time()
                    self.consecutive_failures = 0
                    self.revert_disabled = True
                    self.trigger_command(("revert", "", "watchdog"))
                else:
                    self.log("[system]", "[error] virtualbox api still dead! killing tasks...", "sysmsg")
                    self.api_watchdog_level = 2
                    self.last_api_watchdog_action_time = time.time()
                    self.last_success_time = time.time()
                    self.consecutive_failures = 0
                    self._kill_vbox_tasks()
                    if self.config.get("enable_starting_scene", True): set_obs_scene(obs_scene_starting)
                    subprocess.Popen([vbox_manage_cmd, "startvm", vm_name, "--type", "gui"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(15)
                    set_obs_scene(obs_scene_main)
                    self.revert_disabled = False
                    self.api_watchdog_level = 0
            time.sleep(1.0)

    def start_app_threads(self):
        try:
            curr = time.time()
            if not hasattr(self, 'listener_thread') or not self.listener_thread.is_alive() or curr - getattr(self, 'listener_tick', curr) > 120:
                self.listener_tick = curr
                self.listener_id = getattr(self, 'listener_id', 0) + 1
                self.listener_thread = threading.Thread(target=self.chat_listener_loop, args=(self.listener_id,), daemon=True)
                self.listener_thread.start()
            if not hasattr(self, 'executor_thread') or not self.executor_thread.is_alive() or curr - getattr(self, 'executor_tick', curr) > 120:
                self.executor_tick = curr
                self.executor_id = getattr(self, 'executor_id', 0) + 1
                self.executor_thread = threading.Thread(target=self.executor_loop, args=(self.executor_id,), daemon=True)
                self.executor_thread.start()
            if not hasattr(self, 'error_watcher_thread') or not self.error_watcher_thread.is_alive():
                self.error_watcher_thread = threading.Thread(target=self.error_watcher_loop, daemon=True)
                self.error_watcher_thread.start()
            if not hasattr(self, 'action_thread') or not self.action_thread.is_alive():
                self.action_thread = threading.Thread(target=self.action_processor_loop, daemon=True)
                self.action_thread.start()
            if flask_available and (not hasattr(self, 'flask_thread') or not self.flask_thread.is_alive()):
                self.flask_thread = threading.Thread(target=start_flask, daemon=True)
                self.flask_thread.start()
        except Exception as e:
            console_log("ERROR", f"start threads crashed: {e}\n{traceback.format_exc()}")
            self.log("[system]", f"[error] start threads crashed: {e}", "err")

if __name__ == "__main__":
    try:
        main_ui_root = tk.Tk()
        main_gui_application = ChatPlaysApp(main_ui_root)
        main_ui_root.mainloop()
    except Exception as fatal_error:
        print("\n" + "="*60 + "\nscript crashed:\n" + "="*60)
        traceback.print_exc()
        print("="*60 + "\n")
        try:
            err_root = tk.Tk()
            err_root.withdraw()
            messagebox.showerror("error", f"crashed during startup.\n\nerror: {fatal_error}\n\ncheck black console for exact line.")
            err_root.destroy()
        except:
            pass
        input("press enter to exit...")
