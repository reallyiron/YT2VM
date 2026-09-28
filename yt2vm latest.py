import signal as _signal_module
import threading as _threading_module
_orig_signal = _signal_module.signal
def _safe_signal(sig, handler):
    if _threading_module.current_thread() is _threading_module.main_thread():
        return _orig_signal(sig, handler)
_signal_module.signal = _safe_signal

import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk
import tkinter.font as tkfont
import threading, time, sys, traceback, random, subprocess, os, re, json, platform, ctypes, collections, queue, shutil, gc
import urllib.request, urllib.error, urllib.parse
from ctypes import wintypes
sys.coinit_flags = 0

class _StderrFilter:
    SUPPRESS = ("ConnectionRefusedError", "websocket/_http.py", "obsws_python",
                "baseclient.py", "_open_socket", "sock.connect(address)",
                "WinError 10061", "During handling of the above")

    def __init__(self, orig):
        self.orig = orig
        self._muting = False
    def write(self, msg):
        m = str(msg)
        if "CoInitializeSecurity was already called" in m:
            return
        # obsws_python dumps a full traceback to stderr whenever OBS is closed.
        # Mute that block (we already log one clean line) but keep real errors.
        if any(tok in m for tok in self.SUPPRESS):
            self._muting = True
            return
        if self._muting:
            if m.strip() == "" or m.startswith((" ", "\t", "Traceback")):
                return
            self._muting = False
        self.orig.write(msg)
    def flush(self): self.orig.flush()
sys.stderr = _StderrFilter(sys.stderr)


# ── AUTO-INSTALL DEPENDENCIES ────────────────────────────────────────────────
# Installs what is missing on first run. Skip with --no-install, or by setting
# YT2VM_NO_INSTALL=1. It never reinstalls what is already importable, and it
# handles Arch/CachyOS "externally-managed-environment" by retrying correctly.
REQUIRED_PACKAGES = [
    ("pytchat", "pytchat", "reading YouTube live chat"),
    ("flask", "flask", "OBS overlay web server"),
]
OPTIONAL_PACKAGES = [
    ("obsws_python", "obsws-python", "OBS scene / media control"),
    ("customtkinter", "customtkinter", "modern rounded widgets"),
    ("ttkbootstrap", "ttkbootstrap", "themed ttk widgets"),
    ("yt_dlp", "yt-dlp", "music downloads"),
    ("serial", "pyserial", "Pico HID (Real PC tab)"),
    ("vncdotool", "vncdotool", "VMware input over VNC"),
]
if platform.system() == "Windows":
    REQUIRED_PACKAGES.append(("win32com", "pywin32", "VirtualBox native COM"))
    OPTIONAL_PACKAGES.append(("virtualbox", "virtualbox", "legacy pyvbox fallback"))
else:
    OPTIONAL_PACKAGES.append(("virtualbox", "virtualbox", "VirtualBox python API"))

INSTALL_FLAG = "deps_installed.flag"


def _missing_packages(pkgs):
    import importlib.util
    out = []
    for module, pipname, why in pkgs:
        try:
            if importlib.util.find_spec(module) is None:
                out.append((module, pipname, why))
        except Exception:
            out.append((module, pipname, why))
    return out


def _pip_install(pipnames):
    """Try a normal install, then the fallbacks distros need."""
    base = [sys.executable, "-m", "pip", "install", "--upgrade"]
    attempts = [base + pipnames,
                base + ["--user"] + pipnames,
                base + ["--break-system-packages"] + pipnames]
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if r.returncode == 0:
                return True, ""
            err = (r.stderr or "") + (r.stdout or "")
            if "externally-managed-environment" in err or "--break-system-packages" in err:
                continue
            if "No matching distribution" in err or "Could not find a version" in err:
                return False, err.strip().splitlines()[-1] if err.strip() else "no matching distribution"
        except Exception as e:
            return False, str(e)
    return False, "all install attempts failed"


def ensure_packages(force=False):
    if "--no-install" in sys.argv or os.environ.get("YT2VM_NO_INSTALL") == "1":
        return
    if not force and os.path.exists(INSTALL_FLAG):
        return
    need_req = _missing_packages(REQUIRED_PACKAGES)
    need_opt = _missing_packages(OPTIONAL_PACKAGES)
    if not need_req and not need_opt:
        try:
            with open(INSTALL_FLAG, "w") as f: f.write("ok")
        except Exception: pass
        return
    print("=" * 60)
    print("  first run - installing python packages")
    print("=" * 60)
    for _, pipname, why in need_req + need_opt:
        print(f"    {pipname:<18} {why}")
    print("  (skip this next time with:  python yt2vm.py --no-install)")
    print("=" * 60)
    failed = []
    # required first, one at a time so a single failure can't block the rest
    for module, pipname, why in need_req:
        ok, err = _pip_install([pipname])
        print(f"  [{'ok' if ok else 'FAILED'}] {pipname}" + ("" if ok else f"  -> {err[:90]}"))
        if not ok: failed.append((pipname, why, True))
    for module, pipname, why in need_opt:
        ok, err = _pip_install([pipname])
        print(f"  [{'ok' if ok else 'skip'}] {pipname}" + ("" if ok else f"  -> {err[:90]}"))
        if not ok: failed.append((pipname, why, False))
    hard = [f for f in failed if f[2]]
    if hard:
        print()
        print("  These are REQUIRED and did not install:")
        for pipname, why, _ in hard:
            print(f"    {pipname}  ({why})")
        print("  Install them manually, e.g.:")
        print(f"    {sys.executable} -m pip install " + " ".join(f[0] for f in hard))
        if platform.system() == "Linux":
            print("  On Arch/CachyOS you may also need:  sudo pacman -S tk")
    else:
        try:
            with open(INSTALL_FLAG, "w") as f: f.write("ok")
        except Exception: pass
    print("=" * 60)


ensure_packages() if "--no-install" not in sys.argv else None


def platform_report():
    """One-line summary of what this machine can actually drive."""
    sysname = platform.system()
    bits = [f"platform: {sysname}"]
    try:
        if os.path.exists(vbox_manage_cmd) or shutil.which("VBoxManage"):
            bits.append("VBoxManage: found")
        else:
            bits.append("VBoxManage: NOT FOUND")
    except Exception: pass
    try:
        vr = find_vmrun()
        bits.append("vmrun: found" if os.path.exists(vr) else "vmrun: not found")
    except Exception: pass
    if sysname == "Windows":
        bits.append("input: native COM")
    else:
        bits.append("input: vbox api / VBoxManage cli")
    return "  |  ".join(bits)

try: import pythoncom
except ImportError: pass

try:
    import virtualbox
    vbox_pkg = "virtualbox"
except ImportError:
    try:
        from vboxapi import VirtualBoxManager
        vbox_pkg = "vboxapi"
    except ImportError: vbox_pkg = None

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
            if cmd: self.bind("<Button-1>", lambda e: cmd())
            if abg: self.bind("<Enter>", lambda e: self.config(bg=abg, fg=afg or fg))
            self.bind("<Leave>", lambda e: self.config(bg=bg, fg=fg))
    tk.Button = MacLabelButton

try:
    import obsws_python as obs
    obs_available = True
except ImportError: obs_available = False

try:
    from flask import Flask, jsonify, render_template_string
    import logging as flask_logging
    flask_available = True
except ImportError: flask_available = False

try:
    import pytchat
    pytchat_available = True
except ImportError: pytchat_available = False

instance_id = 1
for arg in sys.argv:
    if arg == "--multistream": instance_id = 2
    elif arg.startswith("--multistream") and arg != "--multistream":
        try: instance_id = int(arg.replace("--multistream", "")) + 1
        except Exception: pass

is_multistream = instance_id > 1
flask_port = 5000 + instance_id - 1
version = "1.0.0_2026"

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
musiclogs_file = "musiclog.json"
heartbeat_file = f"heartbeat{suffix}.txt"
crashguard_file = f"crashguard{suffix}.txt"

refresh_rate = 100  
keyboard_layout = "US" 
available_layouts = ["US", "UK", "DANISH", "GERMAN", "FRENCH", "TURKISH", "NORWEGIAN", "SWEDISH"]
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
gui_log_queue = queue.Queue(maxsize=300)
log_lock = threading.Lock()


# ── DEBUG SYSTEM ─────────────────────────────────────────────────────────────
# Enable with --debug on the command line, YT2VM_DEBUG=1, or debug_mode in
# settings. Everything important reports through dbg(), and the full trail is
# written to debug_log.txt so a failure can be diagnosed after the fact.
DEBUG_FILE = f"debug_log{suffix}.txt"
# debug is ON by default now - a silent log helps nobody. use --quiet to stop it.
DEBUG_ON = ("--quiet" not in sys.argv) and (os.environ.get("YT2VM_DEBUG") != "0")
_dbg_lock = threading.Lock()
_dbg_ring = collections.deque(maxlen=800)


DBG_VISIBLE = {"vnc", "vmware", "backend", "vmfinder", "recovery"}
_dbg_sink = None


def dbg(category, msg, exc=None):
    """Structured debug line: time, thread, category, message.
    Lines in DBG_VISIBLE are also mirrored into the app's Event Log so the user
    can see what is happening without digging through a file."""
    try:
        if _dbg_sink is not None and str(category) in DBG_VISIBLE:
            _dbg_sink(f"[{category}] {msg}" + (f" ({type(exc).__name__}: {exc})" if exc else ""))
    except Exception:
        pass
    if not DEBUG_ON:
        return
    try:
        line = (f"[{time.strftime('%H:%M:%S')}] "
                f"[{threading.current_thread().name[:14]:<14}] "
                f"[{str(category)[:12]:<12}] {msg}")
        if exc is not None:
            line += f"\n    -> {type(exc).__name__}: {exc}"
            tb = traceback.format_exc()
            if tb and "NoneType: None" not in tb:
                line += "\n" + "".join("       " + l for l in tb.splitlines(True))
        with _dbg_lock:
            _dbg_ring.append(line)
            print(line, flush=True)
            try:
                with open(DEBUG_FILE, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass
    except Exception:
        pass


def dbg_run(category, cmd, timeout=15, **kw):
    """subprocess.run with the command, exit code, stdout and stderr logged."""
    dbg(category, f"RUN {cmd if isinstance(cmd, str) else ' '.join(str(c) for c in cmd)}")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
        el = (time.time() - t0) * 1000
        dbg(category, f"  rc={r.returncode} in {el:.0f}ms")
        if r.stdout and r.stdout.strip():
            for ln in r.stdout.strip().splitlines()[:12]:
                dbg(category, f"  out| {ln}")
        if r.stderr and r.stderr.strip():
            for ln in r.stderr.strip().splitlines()[:12]:
                dbg(category, f"  err| {ln}")
        return r
    except subprocess.TimeoutExpired:
        dbg(category, f"  TIMEOUT after {timeout}s")
        return None
    except Exception as e:
        dbg(category, "  EXCEPTION", e)
        return None


def safe_json_dump(filename, data):
    tmp_file = filename + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
        os.replace(tmp_file, filename)
    except Exception:
        try:
            with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
        except Exception: pass

def append_to_json_log(filename, user, command):
    try:
        with log_lock:
            entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "username": user, "command": command}
            logs = []
            if os.path.exists(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as f: logs = json.load(f)
                except Exception: pass
            logs.append(entry)
            if len(logs) > 1000: logs = logs[-1000:]
            safe_json_dump(filename, logs)
    except Exception: pass

def append_to_all_msgs_log(user, msg):
    try:
        with log_lock:
            entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "username": user, "message": msg}
            with open(allmsglogs_file, "a", encoding="utf-8") as f: f.write(json.dumps(entry) + "\n")
    except Exception: pass

def log_vote_action(action, user, vote_type, target, current_votes=0):
    try:
        with log_lock:
            entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action.lower(), "user": user, "vote": vote_type, "progress": f"{current_votes}/{target}" if current_votes else str(target)}
            logs = []
            if os.path.exists(voteslogs_file):
                try:
                    with open(voteslogs_file, "r", encoding="utf-8") as f: logs = json.load(f)
                except Exception: pass
            logs.append(entry)
            if len(logs) > 1000: logs = logs[-1000:]
            safe_json_dump(voteslogs_file, logs)
    except Exception: pass

def log_music_action(action, user, title, url=""):
    try:
        with log_lock:
            entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action, "user": user, "title": title, "url": url}
            logs = []
            if os.path.exists(musiclogs_file):
                try:
                    with open(musiclogs_file, "r", encoding="utf-8") as f: logs = json.load(f)
                except Exception: pass
            logs.append(entry)
            if len(logs) > 1000: logs = logs[-1000:]
            safe_json_dump(musiclogs_file, logs)
    except Exception: pass

def console_log(level, msg):
    timestamp = time.strftime("%H:%M:%S")
    date_stamp = time.strftime("%Y-%m-%d")
    log_line = f"[{timestamp}] [{level.lower()}] {msg.lower()}"
    print(log_line, flush=True)
    try: gui_log_queue.put_nowait((level, log_line))
    except queue.Full: pass
    try:
        with log_lock:
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"[{date_stamp} {timestamp}] [{level.lower()}] {msg.lower()}\n")
    except Exception: pass

possible_paths = [
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
    r"D:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    r"E:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage",
    "/usr/bin/VBoxManage", "/usr/local/bin/VBoxManage", "/opt/VirtualBox/VBoxManage",
    "VBoxManage"]

VMRUN_PATHS = [
    r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
    r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
    r"D:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
    r"E:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
    "/Applications/VMware Fusion.app/Contents/Library/vmrun",
    "/usr/bin/vmrun", "/usr/local/bin/vmrun", "/opt/vmware/bin/vmrun"]

def find_vmrun():
    for pth in VMRUN_PATHS:
        if os.path.exists(pth): return pth
    found = shutil.which("vmrun")
    return found or VMRUN_PATHS[0]
vbox_manage_cmd, _vbox_how = "VBoxManage", "not found"
_which = shutil.which("VBoxManage") or shutil.which("vboxmanage")
if _which:
    vbox_manage_cmd, _vbox_how = _which, "PATH"
else:
    for path in possible_paths:
        if os.path.exists(path):
            vbox_manage_cmd, _vbox_how = path, "known location"
            break

_VBOX_MISSING_WARNED = False


def run_vbox(args, timeout=10):
    """All VBoxManage calls funnel through here, so --debug traces every one.
    Returns None immediately when VirtualBox is not installed or the VMware
    backend is active, instead of raising FileNotFoundError on a timer."""
    global _VBOX_MISSING_WARNED
    if _active_backend() == "vmware":
        return None
    if resolve_vbox_path(vbox_manage_cmd)[1] == "not found":
        if not _VBOX_MISSING_WARNED:
            _VBOX_MISSING_WARNED = True
            dbg("vbox", "VBoxManage not installed - VirtualBox commands are disabled")
        return None
    global _VBOX_LOCKED
    if DEBUG_ON:
        r = dbg_run("vbox", [vbox_manage_cmd] + list(args), timeout=timeout)
    else:
        try:
            r = subprocess.run([vbox_manage_cmd] + args, capture_output=True, text=True, timeout=timeout)
        except Exception:
            r = None
    if r is not None:
        _VBOX_LOCKED = is_vbox_lock_error(r.stderr) or is_vbox_lock_error(r.stdout)
    return r


def is_vbox_lock_error(txt):
    """True if VBoxManage output means the VM session is locked / already in use
    by a (possibly hung or crashed) process."""
    t = str(txt or "").lower()
    return any(m in t for m in (
        "is already locked", "already locked by a session",
        "vbox_e_invalid_object_state", "0x80bb0007",
        "locked for a session", "session is locked",
        "the machine is not mutable", "vbox_e_object_in_use",
        "0x80bb000c", "a session for the machine",
        "cannot lock", "e_accessdenied while ", "already has a lock"))

VBOX_LAST_ERROR = ""
_VBOX_LOCKED = False
_SNAP_WARNED = set()


def _active_backend():
    """Which backend is selected, without needing the app instance."""
    global _RUNTIME_BACKEND
    try:
        if _RUNTIME_BACKEND: return _RUNTIME_BACKEND
    except NameError:
        pass
    try:
        if os.path.exists(settings_file):
            return str(json.load(open(settings_file)).get("backend", "virtualbox")).lower()
    except Exception:
        pass
    return "virtualbox"


_RUNTIME_BACKEND = ""


def resolve_vbox_path(preferred=""):
    """Locate VBoxManage: an explicit setting, then PATH, then known install
    directories. Returns (path, how_it_was_found)."""
    if preferred and (os.path.exists(preferred) or shutil.which(preferred)):
        return preferred, "configured"
    found = shutil.which("VBoxManage") or shutil.which("vboxmanage")
    if found:
        return found, "PATH"
    for pth in possible_paths:
        if os.path.exists(pth):
            return pth, "known location"
    return "VBoxManage", "not found"


def get_all_vbox_vms(vbox_path="VBoxManage", quiet=False):
    """List every VirtualBox VM.

    Previously this used a 2 second timeout and, on failure, returned two
    HARDCODED fake names - so a machine with no VirtualBox looked like it had
    VMs that did not exist. It now uses a realistic timeout (VBoxManage has to
    start VBoxSVC on first call, which can take several seconds), reports the
    real reason it failed, and returns an empty list rather than fiction."""
    global VBOX_LAST_ERROR
    vms = []
    if _active_backend() == "vmware":
        VBOX_LAST_ERROR = ""
        return []
    path, how = resolve_vbox_path(vbox_path)
    dbg("vmfinder", f"listing vms using {path!r} (found via {how})")
    if how == "not found":
        VBOX_LAST_ERROR = ("VBoxManage not found. Install VirtualBox, or set the path "
                           "on the VM Config page.")
        dbg("vmfinder", VBOX_LAST_ERROR)
        if not quiet: console_log("ERROR", VBOX_LAST_ERROR)
        return []
    try:
        res = subprocess.run([path, "list", "vms"], capture_output=True, text=True, timeout=20)
        dbg("vmfinder", f"rc={res.returncode} stdout={len(res.stdout or '')}b stderr={(res.stderr or '').strip()[:120]}")
        if res.returncode != 0:
            VBOX_LAST_ERROR = (res.stderr or "").strip() or f"VBoxManage exited {res.returncode}"
            if not quiet: console_log("ERROR", f"vm list failed: {VBOX_LAST_ERROR[:160]}")
            return []
        for line in (res.stdout or "").splitlines():
            if '"' in line:
                name = line.split('"')[1]
                if name: vms.append(name)
        VBOX_LAST_ERROR = "" if vms else "VirtualBox reported no VMs on this machine."
        dbg("vmfinder", f"found {len(vms)} vm(s): {vms}")
        if not vms and not quiet:
            console_log("SYSTEM", "no virtualbox vms found - create one in VirtualBox first.")
    except subprocess.TimeoutExpired:
        VBOX_LAST_ERROR = "VBoxManage timed out (VBoxSVC may be starting or hung)."
        dbg("vmfinder", VBOX_LAST_ERROR)
        if not quiet: console_log("ERROR", VBOX_LAST_ERROR)
    except FileNotFoundError:
        VBOX_LAST_ERROR = f"VBoxManage not executable at {path}"
        dbg("vmfinder", VBOX_LAST_ERROR)
        if not quiet: console_log("ERROR", VBOX_LAST_ERROR)
    except Exception as e:
        VBOX_LAST_ERROR = f"{type(e).__name__}: {e}"
        dbg("vmfinder", "vm list crashed", e)
        if not quiet: console_log("ERROR", f"vm list error: {e}")
    return vms

def get_vbox_snapshots(vbox_path, vm_name):
    """List VirtualBox snapshots.

    Guarded three ways, because this is polled on a timer: it does nothing when
    the VMware backend is active, nothing when VBoxManage is not installed, and
    it logs a given failure only once instead of spamming the log every poll."""
    global _SNAP_WARNED
    snaps = []
    if not vm_name:
        return snaps
    if _active_backend() == "vmware":
        return snaps
    path, how = resolve_vbox_path(vbox_path)
    if how == "not found":
        if "nopath" not in _SNAP_WARNED:
            _SNAP_WARNED.add("nopath")
            dbg("snapshots", "VBoxManage not installed - skipping snapshot lookups")
        return snaps
    try:
        res = subprocess.run([path, "snapshot", vm_name, "list"],
                             capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            err = (res.stderr or "").strip()
            if "does not have any snapshots" not in err.lower():
                key = f"rc:{vm_name}"
                if key not in _SNAP_WARNED:
                    _SNAP_WARNED.add(key)
                    dbg("snapshots", f"list failed for {vm_name}: {err[:140]}")
            return snaps
        for line in (res.stdout or "").splitlines():
            if "Name:" in line and "(UUID:" in line:
                part = line.split("Name:")[1].split("(UUID:")[0].strip()
                if part: snaps.append(part)
        _SNAP_WARNED.discard(f"err:{vm_name}")
        dbg("snapshots", f"{vm_name}: {len(snaps)} snapshot(s) {snaps}")
    except subprocess.TimeoutExpired:
        key = f"to:{vm_name}"
        if key not in _SNAP_WARNED:
            _SNAP_WARNED.add(key)
            dbg("snapshots", f"timeout listing snapshots for {vm_name}")
    except FileNotFoundError:
        if "nopath" not in _SNAP_WARNED:
            _SNAP_WARNED.add("nopath")
            dbg("snapshots", f"VBoxManage not found at {path} - skipping snapshot lookups")
    except Exception as e:
        key = f"err:{vm_name}"
        if key not in _SNAP_WARNED:
            _SNAP_WARNED.add(key)
            dbg("snapshots", f"error listing snapshots for {vm_name}: {type(e).__name__}: {e}")
    return snaps

_startup_backend = "virtualbox"
try:
    _tmp_cfg = json.load(open(settings_file)) if os.path.exists(settings_file) else {}
    _startup_backend = str(_tmp_cfg.get("backend", "virtualbox")).lower()
except Exception:
    pass
available_vms = get_all_vbox_vms(vbox_manage_cmd, quiet=True) if _startup_backend != "vmware" else []
vm_name = ""
if available_vms:
    vm_name = available_vms[instance_id - 1] if len(available_vms) >= instance_id else available_vms[0]
else:
    vm_name = "Windows10ChatVm"   # placeholder until one is picked in VM Config

default_blocked_terms = []

DANGEROUS_PAYLOAD = [
    "shutdown", "logoff", "poweroff", "slidetoshutdown", "format ", "diskpart",
    "bcdedit", "vssadmin", "cipher /w", "del /f", "del /q", "rd /s", "rmdir /s",
    "reg delete", "regdelete", "rundll32", "taskkill", "net user", "net localgroup",
    "wmic ", "powershell -e", "-encodedcommand", "invoke-expression", "iex(",
    "downloadstring", "certutil -urlcache", "bitsadmin /transfer", "mshta ",
    "attrib +h", "icacls", "takeown", "sc delete", "schtasks /create",
    "wscript", "cscript", "vssadmin delete", "cipher", "fsutil",
]
IP_GRABBER_TERMS = [
    "iplogger", "grabify", "ipgrabber", "ipinfo", "ifconfig.me", "icanhazip",
    "whatismyip", "whatismyipaddress", "ipify", "ip-api", "ipapi", "freegeoip",
    "geoip", "iplocation", "iptracker", "ip-tracker", "blasze", "yip.su", "2no.co",
    "ipstack", "ipdata", "showmyip", "myipaddress", "ip-lookup", "iplocator",
]
_LEET_MAP = {"0":"o","1":"i","2":"z","3":"e","4":"a","5":"s","6":"g","7":"t","8":"b",
             "9":"g","@":"a","$":"s","!":"i","|":"i","+":"t"}

def normalize_payload(text):
    """Collapse a string to bare letters so obfuscation can't sneak a blocked
    word past: lowercases, maps leetspeak, strips non-letters, collapses repeats.
    's-h.u.u.t_d0wn' and '$hutd0wn' both normalize to 'shutdown'."""
    out = []
    for ch in str(text).lower():
        ch = _LEET_MAP.get(ch, ch)
        if "a" <= ch <= "z": out.append(ch)
    res = []
    for ch in out:
        if not res or res[-1] != ch: res.append(ch)
    return "".join(res)

def payload_is_dangerous(text):
    """Return the matched term if this text would run something destructive."""
    raw = str(text).lower()
    for frag in DANGEROUS_PAYLOAD:
        if frag in raw: return frag
    norm = normalize_payload(text)
    for frag in DANGEROUS_PAYLOAD + IP_GRABBER_TERMS:
        nf = normalize_payload(frag)
        if nf and len(nf) >= 4 and nf in norm: return frag
    return None
banned_words = []
custom_commands = {}

default_keydata = {"VERSION": 4, "RAW":{"esc":[1],"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"-":[12],"=":[13],"backspace":[14],"tab":[15],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"[":[26],"]":[27],"enter":[28],"ctrl":[29],"lctrl":[29],"rctrl":[224,29],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],";":[39],"'":[40],"`":[41],"shift":[42],"lshift":[42],"\\":[43],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50],",":[51],".":[52],"/":[53],"rshift":[54],"alt":[56],"lalt":[56],"ralt":[224,56],"space":[57],"capslock":[58],"f1":[59],"f2":[60],"f3":[61],"f4":[62],"f5":[63],"f6":[64],"f7":[65],"f8":[66],"f9":[67],"f10":[68],"f11":[87],"f12":[88],"numlock":[69],"scrolllock":[70],"home":[224,71],"up":[224,72],"pageup":[224,73],"left":[224,75],"right":[224,77],"end":[224,79],"down":[224,80],"pagedown":[224,81],"insert":[224,82],"delete":[224,83],"del":[224,83],"win":[224,91],"lwin":[224,91],"rwin":[224,92],"cmd":[224,91],"super":[224,91],"menu":[224,93],"plus":[13],"minus":[12],"return":[28],"numpad0":[82],"numpad1":[79],"numpad2":[80],"numpad3":[81],"numpad4":[75],"numpad5":[76],"numpad6":[77],"numpad7":[71],"numpad8":[72],"numpad9":[73],"numpad_dot":[83],"numpad_enter":[224,28],"numpad_plus":[78],"numpad_minus":[74],"numpad_mul":[55],"numpad_div":[224,53],"printscreen":[224,55,224,183],"pause":[225,29,69,225,157,197],"vol_mute":[224,32],"vol_down":[224,46],"vol_up":[224,48],"media_next":[224,25],"media_prev":[224,16],"media_stop":[224,36],"media_play_pause":[224,34]},"LAYOUTS":{"US":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"-":[12],"=":[13],"[":[26],"]":[27],"\\":[43],";":[39],"'":[40],"`":[41],",":[51],".":[52],"/":[53]},"shift":{"!":[2],"@":[3],"#":[4],"$":[5],"%":[6],"^":[7],"&":[8],"*":[9],"(":[10],")":[11],"_":[12],"+":[13],"{":[26],"}":[27],"|":[43],":":[39],"\"":[40],"~":[41],"<":[51],">":[52],"?":[53]},"altgr":{}},"UK":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"-":[12],"=":[13],"[":[26],"]":[27],"#":[43],";":[39],"'":[40],"`":[41],",":[51],".":[52],"/":[53],"\\":[86]},"shift":{"!":[2],"\"":[3],"£":[4],"$":[5],"%":[6],"^":[7],"&":[8],"*":[9],"(":[10],")":[11],"_":[12],"+":[13],"{":[26],"}":[27],"~":[43],":":[39],"@":[40],"¬":[41],"<":[51],">":[52],"?":[53],"|":[86]},"altgr":{"€":[5],"\\":[86]}},"DANISH":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"+":[12],"´":[13],"å":[26],"¨":[27],"'":[43],"æ":[39],"ø":[40],"½":[41],",":[51],".":[52],"-":[53],"<":[86]},"shift":{"!":[2],"\"":[3],"#":[4],"¤":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"`":[13],"Å":[26],"^":[27],"*":[43],"Æ":[39],"Ø":[40],"§":[41],";":[51],":":[52],"_":[53],">":[86]},"altgr":{"@":[3],"£":[4],"$":[5],"{":[8],"[":[9],"]":[10],"}":[11],"\\":[12],"|":[86],"~":[27],"€":[18],"µ":[50]}},"GERMAN":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"z":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"y":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"ß":[12],"´":[13],"ü":[26],"+":[27],"#":[43],"ö":[39],"ä":[40],"^":[41],",":[51],".":[52],"-":[53],"<":[86]},"shift":{"!":[2],"\"":[3],"§":[4],"$":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"`":[13],"Ü":[26],"*":[27],"'":[43],"Ö":[39],"Ä":[40],"°":[41],";":[51],":":[52],"_":[53],">":[86]},"altgr":{"²":[3],"³":[4],"{":[8],"[":[9],"]":[10],"}":[11],"\\":[12],"@":[16],"€":[18],"~":[27],"|":[86],"µ":[50]}},"FRENCH":{"noshift":{"&":[2],"é":[3],"\"":[4],"'":[5],"(":[6],"-":[7],"è":[8],"_":[9],"ç":[10],"à":[11],")":[12],"=":[13],"a":[16],"z":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"^":[26],"$":[27],"q":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"m":[39],"ù":[40],"²":[41],"*":[43],"w":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],",":[50],";":[51],":":[52],"!":[53],"<":[86]," ":[57]},"shift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"°":[12],"+":[13],"¨":[26],"£":[27],"%":[40],"µ":[43],"?":[50],".":[51],"/":[52],"§":[53],">":[86]},"altgr":{"~":[3],"#":[4],"{":[5],"[":[6],"|":[7],"`":[8],"\\":[9],"^":[10],"@":[11],"]":[12],"}":[13],"€":[18]}},"TURKISH":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"ı":[23],"o":[24],"p":[25],"ğ":[26],"ü":[27],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"ş":[39],"i":[40],"\"":[41],",":[43],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50],"ö":[51],"ç":[52],".":[53],"<":[86]," ":[57],"*":[12],"-":[13]},"shift":{"!":[2],"'":[3],"^":[4],"+":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"_":[13],"Ğ":[26],"Ü":[27],"Ş":[39],"İ":[40],"é":[41],";":[43],"Ö":[51],"Ç":[52],":":[53],">":[86]},"altgr":{"@":[3],"#":[4],"$":[5],"{":[8],"[":[9],"]":[10],"}":[11],"\\":[12],"|":[13],"€":[18],"~":[41],"`":[43]}},"NORWEGIAN":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"+":[12],"\\":[13],"å":[26],"¨":[27],"@":[43],"ø":[39],"æ":[40],"|":[41],",":[51],".":[52],"-":[53],"<":[86]},"shift":{"!":[2],"\"":[3],"#":[4],"¤":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"`":[13],"Å":[26],"^":[27],"*":[43],"Ø":[39],"Æ":[40],"§":[41],";":[51],":":[52],"_":[53],">":[86]},"altgr":{"£":[4],"$":[5],"{":[8],"[":[9],"]":[10],"}":[11],"~":[27],"€":[18],"µ":[50]}},"SWEDISH":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"+":[12],"´":[13],"å":[26],"¨":[27],"'":[43],"ö":[39],"ä":[40],"§":[41],",":[51],".":[52],"-":[53],"<":[86]},"shift":{"!":[2],"\"":[3],"#":[4],"¤":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"`":[13],"Å":[26],"^":[27],"*":[43],"Ö":[39],"Ä":[40],"½":[41],";":[51],":":[52],"_":[53],">":[86]},"altgr":{"@":[3],"£":[4],"$":[5],"{":[8],"[":[9],"]":[10],"}":[11],"\\":[12],"~":[27],"|":[86],"€":[18],"µ":[50]}}}}

_needs_update = False
if os.path.exists(scancodes_file):
    try:
        with open(scancodes_file, "r", encoding="utf-8") as f: _loaded_data = json.load(f)
        if "LAYOUTS" not in _loaded_data or "RAW" not in _loaded_data or _loaded_data.get("VERSION") != default_keydata.get("VERSION"): _needs_update = True
    except Exception: _needs_update = True
else: _needs_update = True

if _needs_update:
    try:
        with open(scancodes_file, "w", encoding="utf-8") as f: json.dump(default_keydata, f, indent=4, ensure_ascii=False)
        _loaded_data = default_keydata.copy()
    except Exception: _loaded_data = default_keydata.copy()

scancodes = _loaded_data["RAW"]
_layouts = _loaded_data["LAYOUTS"]

def get_typed_codes(char, layout="US"):
    SHIFT = [[0x2A]]
    ALTGR = [[0xE0, 0x38]]
    target = _layouts.get(layout, _layouts["US"])
    active_no = target.get("noshift", {})
    active_sh = target.get("shift", {})
    active_al = target.get("altgr", {})
    if char in active_sh: return (SHIFT, active_sh[char])
    if char in active_al: return (ALTGR, active_al[char])
    if char in active_no: return ([], active_no[char])
    char_lower = char.lower()
    if char.isupper() and char_lower in active_no: return (SHIFT, active_no[char_lower])
    if char_lower != char and char_lower in active_no: return (SHIFT, active_no[char_lower])
    if char_lower in active_no: return ([], active_no[char_lower])
    us = _layouts["US"]
    if char in us["shift"]: return (SHIFT, us["shift"][char])
    if char in us["noshift"]: return ([], us["noshift"][char])
    if char.isupper() and char_lower in us["noshift"]: return (SHIFT, us["noshift"][char_lower])
    if char_lower in us["noshift"]: return ([], us["noshift"][char_lower])
    return ([], [0])

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
except Exception: pass

def save_stats():
    try:
        uptime = int(time.time() - script_start_time)
        with stats_lock:
            tmp_file = stats_file + ".tmp"
            with open(tmp_file, "w") as f: json.dump({"uptime": uptime, "commands": total_commands_executed, "failed": total_commands_failed, "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
            os.replace(tmp_file, stats_file)
    except Exception: pass

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
        with open("crash_log.txt", "w") as f: traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    except Exception: pass
    set_obs_scene(obs_scene_error)
sys.excepthook = handle_exception

def clean_text(text):
    if not isinstance(text, str): return str(text)
    return ''.join(c for c in text if c <= '\uFFFF')

def safe_int(val, default=0, lo=None, hi=None):
    """Chat is untrusted input - '!move left abc' must not raise."""
    try:
        n = int(str(val).strip())
    except Exception:
        try:
            n = int(float(str(val).strip()))
        except Exception:
            return default
    if lo is not None and n < lo: n = lo
    if hi is not None and n > hi: n = hi
    return n


def escape_html(text):
    if not isinstance(text, str): return str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

def add_to_history(user, msg, tag, is_mod=False, is_owner=False):
    global global_msg_id
    global_msg_id += 1
    safe_user = escape_html(user)
    safe_msg = escape_html(msg)
    msg_obj = {"id": global_msg_id, "u": safe_user, "m": safe_msg, "t": tag, "is_admin": is_mod, "is_owner": is_owner}
    with buffer_lock: messages_buffer.append(msg_obj)
    with history_lock: web_chat_history.append(msg_obj)

_obs_warned_at = 0
_obs_down_until = 0


def obs_reachable():
    """Probe the OBS websocket port before connecting. obsws_python prints a
    full traceback to stderr when the port is refused, so we avoid calling it
    at all when OBS is not running, and back off for a while."""
    global _obs_down_until, _obs_warned_at
    if time.time() < _obs_down_until:
        return False
    import socket
    try:
        with socket.create_connection((obs_host, int(obs_port)), timeout=0.6):
            return True
    except Exception:
        _obs_down_until = time.time() + 30
        if time.time() - _obs_warned_at > 120:
            _obs_warned_at = time.time()
            console_log("SYSTEM", f"obs not reachable on {obs_host}:{obs_port} - scene switching disabled until it is up.")
        dbg("obs", f"port {obs_host}:{obs_port} refused; backing off 30s")
        return False


def _obs_note_fail(e):
    """OBS not running is normal - log one short line, not a stack trace."""
    global _obs_warned_at
    msg = str(e)
    if "refused" in msg.lower() or "10061" in msg or "timed out" in msg.lower():
        if time.time() - _obs_warned_at > 60:
            _obs_warned_at = time.time()
            console_log("SYSTEM", f"obs not reachable on {obs_host}:{obs_port} (is OBS open with websocket enabled?)")
        dbg("obs", f"connect refused: {msg[:120]}")
    else:
        dbg("obs", "obs error", e)


def set_obs_scene(scene_name):
    try:
        if not obs_available: return
        def _switch():
            try:
                if not obs_reachable(): return
                cl = obs.ReqClient(host=obs_host, port=obs_port, password=obs_password, timeout=3) if obs_password else obs.ReqClient(host=obs_host, port=obs_port, timeout=3)
                cl.set_current_program_scene(scene_name)
                dbg("obs", f"scene -> {scene_name}")
            except Exception as e: _obs_note_fail(e)
        threading.Thread(target=_switch, daemon=True).start()
    except Exception: pass

if flask_available:
    obs_web_overlay_app = Flask(__name__)
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)
    @obs_web_overlay_app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    html_index = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Chat Controls</title><style>body{background:#09090b;color:#00E5FF;font-family:'Segoe UI',Consolas,monospace;text-align:center;padding:40px}h1{color:#10B981;font-size:36px;text-shadow:0 0 10px rgba(16,185,129,0.3);margin-bottom:5px}.grid{display:flex;flex-wrap:wrap;gap:20px;justify-content:center;max-width:800px;margin:40px auto}a{background:#18181b;border:1px solid #27272a;color:#fff;text-decoration:none;padding:20px;border-radius:12px;width:300px;transition:all 0.2s;box-shadow:0 4px 6px rgba(0,0,0,0.3);text-align:left}a:hover{transform:translateY(-5px);border-color:#00E5FF;box-shadow:0 8px 15px rgba(0,229,255,0.2)}.title{font-size:20px;font-weight:bold;margin-bottom:10px;color:#00E5FF}.desc{font-size:14px;color:#a1a1aa}</style></head><body><h1>[active] chat server active</h1><p style="color:#71717a;font-size:18px">Add one of these links to your OBS Browser Source:</p><div class="grid"><a href="/obsnew"><div class="title">Liquid Glass Chat (/obsnew)</div><div class="desc">Sleek gray bubbles with a glass background.</div></a><a href="/oldobsnew"><div class="title">Classic Dark Chat (/oldobsnew)</div><div class="desc">The OG dark background modern chat.</div></a><a href="/ultradebug"><div class="title">Ultra Debug (/ultradebug)</div><div class="desc">Shows core system status and queues.</div></a><a href="/stats"><div class="title">Live Stats (/stats)</div><div class="desc">Viewers, Likes, and Uptime widget.</div></a><a href="/obs"><div class="title">Legacy Chat (/obs)</div><div class="desc">The original transparent overlay.</div></a></div></body></html>"""
    html_template = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');@keyframes slideIn{from{transform:translateX(20px);opacity:0}to{transform:translateX(0);opacity:1}}html,body{background-color:rgba(0,0,0,0)!important;margin:0;padding:0;width:100vw;height:100vh;overflow:hidden}body{font-family:'Fira Code','Consolas',monospace;display:flex;flex-direction:column;padding:10px;text-shadow:2px 2px 0 #000;color:#ccc;font-size:16px;justify-content:flex-end}.header{position:absolute;top:10px;right:10px;text-align:right;display:flex;flex-direction:column;align-items:flex-end;z-index:10}div[id="vote-text"]{font-family:'Impact',sans-serif;font-size:24px;color:red;text-transform:uppercase;margin-bottom:5px;text-shadow:2px 2px 0 #000;background:rgba(0,0,0,0.85);padding:5px 12px;border:1px solid #444;border-radius:4px;display:none}.stats-container{display:flex;gap:15px;font-family:'Fira Code',monospace;font-weight:bold;font-size:20px;align-items:center;background:rgba(0,0,0,0.85);padding:5px 12px;border:1px solid #444;border-radius:4px}.stat-item{display:flex;align-items:center;gap:6px}.icon-eye{fill:#0af;width:22px;height:22px;filter:drop-shadow(0 0 2px #0af)}.icon-thumb{fill:#0f0;width:22px;height:22px;filter:drop-shadow(0 0 2px #0f0)}.stat-text{color:#fff;text-shadow:0 0 2px #fff}.chat-box{flex-grow:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:flex-end;padding-bottom:10px;z-index:5}.line{font-size:18px;font-weight:500;margin-bottom:3px;color:#fff;line-height:1.3;word-wrap:break-word;overflow-wrap:break-word;display:flex;align-items:flex-start;justify-content:flex-end;width:100%;animation:slideIn 0.2s ease-out forwards}.admin-name{color:#5e84f1;font-weight:700;text-shadow:0 0 3px #5e84f1}.owner-name{color:#ffd700;font-weight:700;text-shadow:0 0 3px #ffd700}.user-name{color:#e0e0e0;font-weight:700}.sys-text{color:#f0f;font-weight:700;text-shadow:0 0 3px #f0f}.sys-msg-text{color:#0f0;font-weight:bold}.err-text{color:#f33;font-weight:bold}.msg-text{color:#fff}.separator{margin-right:8px;color:#888;font-weight:bold}</style></head><body><div class="header"><div id="vote-text">no active votes</div><div class="stats-container"><div class="stat-item"><svg class="icon-eye" viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.61 11 7.61s9.27-3.22 11-7.61C21.27 7.61 17 4.5 12 4.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg><span id="viewers" class="stat-text">0</span></div><div class="stat-item"><svg class="icon-thumb" viewBox="0 0 24 24"><path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-1.91l-.01-.01L23 10z"/></svg><span id="likes" class="stat-text">0</span></div></div></div><div class="chat-box" id="chat"></div><script>let lastId=-1;let fetchingUpdates=!1;setInterval(function(){if(fetchingUpdates)return;fetchingUpdates=!0;fetch('/history?t='+Date.now()).then(r=>r.json()).then(data=>{if(data&&Array.isArray(data)){const c=document.getElementById('chat');if(!c)return;const fragment=document.createDocumentFragment();let added=!1;data.forEach(i=>{if(i.id>lastId){lastId=i.id;try{let nameClass="user-name";let msgClass="msg-text";if(i.is_owner){nameClass="owner-name";}else if(i.is_admin){nameClass="admin-name";}let u=i.u||"Unknown";let m=i.m||"";if(u==='[system]'||u==='system'){u="[system]";nameClass="sys-text";msgClass=m.includes("[err]")?"err-text":"sys-msg-text";}else if(u==='[console]'||u==='[announcement]'){nameClass="admin-name";}else{if(typeof u==='string'&&!u.startsWith('@'))u="@"+u;}const div=document.createElement('div');div.className='line';div.innerHTML=`<span class='${nameClass}'>${u}</span><span class="separator">:</span><span class='${msgClass}'>${m}</span>`;fragment.appendChild(div);added=!0;}catch(err){}}});if(added){c.appendChild(fragment);window.scrollTo(0,document.body.scrollHeight);while(c.children.length>50)c.removeChild(c.firstChild);}}fetchingUpdates=!1;}).catch(e=>{fetchingUpdates=!1;});},1000);let fetchingStatus=!1;setInterval(function(){if(fetchingStatus)return;fetchingStatus=!0;fetch('/status_update?t='+Date.now()).then(r=>r.json()).then(data=>{try{const v=document.getElementById('vote-text');const chatBox=document.getElementById('chat');const headerBox=document.querySelector('.header');if(chatBox){chatBox.style.display=data.chat_visible?'flex':'none';}if(headerBox){if(data.split_mode){headerBox.style.display='none';}else{headerBox.style.display='flex';if(v&&data.vote&&data.vote.active){v.innerHTML=(data.vote.text||"").replace('[vote] ','');v.style.display="block";}else if(v){v.style.display="none";}const viewEl=document.getElementById('viewers');const likeEl=document.getElementById('likes');if(viewEl)viewEl.innerText=data.viewers||"0";if(likeEl)likeEl.innerText=data.likes||"0";}}}catch(err){}fetchingStatus=!1;}).catch(e=>{fetchingStatus=!1;});},2000);</script></body></html>"""
    html_template_2 = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');html,body{background-color:rgba(0,0,0,0)!important;margin:0;padding:0;width:100vw;height:100vh;overflow:hidden}body{font-family:'Fira Code','Consolas',monospace;display:flex;flex-direction:column;align-items:flex-end;padding:3vw;box-sizing:border-box}.header{text-align:right;display:flex;flex-direction:column;align-items:flex-end}div[id="vote-text"]{font-family:'Impact',sans-serif;font-size:10vw;color:red;text-transform:uppercase;margin-bottom:2vw;text-shadow:0.5vw 0.5vw 0 #000;display:none;line-height:1}.stats-container{display:flex;gap:5vw;font-family:'Fira Code',monospace;font-weight:bold;font-size:8vw;align-items:center}.stat-item{display:flex;align-items:center;gap:2vw}.icon-eye{fill:#0af;width:9vw;height:9vw;filter:drop-shadow(0.4vw 0.4vw 0 #000)}.icon-thumb{fill:#0f0;width:9vw;height:9vw;filter:drop-shadow(0.4vw 0.4vw 0 #000)}.stat-text{color:#fff;text-shadow:0.4vw 0.4vw 0 #000}</style></head><body><div class="header"><div id="vote-text"></div><div class="stats-container"><div class="stat-item"><svg class="icon-eye" viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.61 11 7.61s9.27-3.22 11-7.61C21.27 7.61 17 4.5 12 4.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg><span id="viewers" class="stat-text">0</span></div><div class="stat-item"><svg class="icon-thumb" viewBox="0 0 24 24"><path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-1.91l-.01-.01L23 10z"/></svg><span id="likes" class="stat-text">0</span></div></div></div><script>let fetchingStatus2=!1;setInterval(function(){if(fetchingStatus2)return;fetchingStatus2=!0;fetch('/status_update?t='+Date.now()).then(r=>r.json()).then(data=>{try{const v=document.getElementById('vote-text');if(data.vote&&data.vote.active){v.innerHTML=(data.vote.text||"").replace('[vote] ','');v.style.display="block";}else if(v){v.style.display="none";}const viewEl=document.getElementById('viewers');const likeEl=document.getElementById('likes');if(viewEl)viewEl.innerText=data.viewers||"0";if(likeEl)likeEl.innerText=data.likes||"0";}catch(err){}fetchingStatus2=!1;}).catch(e=>{fetchingStatus2=!1;});},2000);</script></body></html>"""
    html_template_new = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');html,body{background-color:rgba(0,0,0,0)!important;margin:0;padding:0;width:100%;height:100%;overflow:hidden}body{font-family:'-apple-system','BlinkMacSystemFont','Inter',sans-serif;display:flex;flex-direction:column;padding:25px;justify-content:flex-end;box-sizing:border-box}.chat-box{display:flex;flex-direction:column;align-items:flex-end;gap:16px;width:100%}.msg-block{background:rgba(80,80,85,0.25);backdrop-filter:blur(25px) saturate(200%);-webkit-backdrop-filter:blur(25px) saturate(200%);padding:12px 18px;display:flex;align-items:flex-start;font-size:16px;border-radius:22px;box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 1px rgba(255,255,255,0.4);animation:popIn 0.35s cubic-bezier(0.175,0.885,0.32,1.2) forwards;max-width:90%;word-wrap:break-word;border:1px solid rgba(255,255,255,0.15);border-bottom:1px solid rgba(255,255,255,0.05)}.msg-block.cmd-border{box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 1px rgba(255,255,255,0.4),inset 4px 0 0 #00E5FF}.msg-block.chat-border{box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 1px rgba(255,255,255,0.4),inset 4px 0 0 #10B981}.msg-block.vote-border{box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 1px rgba(255,255,255,0.4),inset 4px 0 0 #F59E0B}.msg-block.err-border{box-shadow:0 8px 32px rgba(0,0,0,0.15),inset 0 1px 1px rgba(255,255,255,0.4),inset 4px 0 0 #EF4444}.badge{padding:4px 10px;font-weight:800;font-size:11px;border-radius:20px;margin-right:14px;flex-shrink:0;align-self:center;color:#fff;letter-spacing:0.8px;text-transform:uppercase;box-shadow:0 4px 10px rgba(0,0,0,0.2)}.badge.cmd{background:linear-gradient(135deg,#00E5FF,#0083B0)}.badge.chat{background:linear-gradient(135deg,#10B981,#047857)}.badge.vote{background:linear-gradient(135deg,#F59E0B,#B45309)}.badge.err{background:linear-gradient(135deg,#EF4444,#991B1B)}.msg-content{display:flex;flex-direction:column;gap:2px}.username{font-weight:700;font-size:14px;letter-spacing:0.3px;text-shadow:0 1px 4px rgba(0,0,0,0.3)}.username.cmd{color:#40C4FF}.username.chat{color:#34D399}.username.vote{color:#FBBF24}.username.err{color:#FF8A8A}.message{color:#fff;font-weight:500;line-height:1.4;font-size:16px;text-shadow:0 1px 3px rgba(0,0,0,0.4)}@keyframes popIn{from{transform:translateY(20px) scale(0.95);opacity:0;filter:blur(4px)}to{transform:translateY(0) scale(1);opacity:1;filter:blur(0)}}</style></head><body><div class="chat-box" id="chat"></div><script>let lastId=-1;let fetchingUpdates=!1;let hasConnected=!1;setInterval(function(){if(fetchingUpdates)return;fetchingUpdates=!0;fetch('/history?t='+Date.now()).then(r=>r.json()).then(data=>{try{if(data&&Array.isArray(data)){const c=document.getElementById('chat');if(c){if(!hasConnected){hasConnected=!0;const div=document.createElement('div');div.className='msg-block chat-border';div.innerHTML=`<div class="badge chat">SYS</div><div class="msg-content"><span class="username chat">system</span> <span class="message">ui connected successfully</span></div>`;c.appendChild(div);}const fragment=document.createDocumentFragment();let added=!1;data.forEach(i=>{if(i.id>lastId){lastId=i.id;try{let u=i.u||"Unknown";let m=i.m||"";if(u==='[system]'&&!m.includes('vote')&&!m.includes('[err]')&&!m.includes('waiting')&&!m.includes('ready')&&!m.includes('chat listener')&&!m.includes('running')&&!m.includes('[ban]')&&!m.includes('[warn]'))return;let isCmd=m.trim().startsWith('!');let badgeClass=isCmd?'cmd':'chat';let badgeText=isCmd?'CMD':'CHAT';let borderClass=isCmd?'cmd-border':'chat-border';let unameClass=isCmd?'username cmd':'username chat';let cleanU=u.replace(/^@+/,'');let displayU='@'+cleanU;if(u==='[console]'){displayU='CONSOLE';badgeText='SYS';}else if(u==='[announcement]'){displayU='ANNOUNCEMENT';badgeText='INFO';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}else if(u==='[system]'){displayU='SYSTEM';badgeText='SYS';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';if(m.includes('[vote]')){badgeText='VOTE';badgeClass='vote';borderClass='vote-border';unameClass='username vote';}else if(m.includes('[err]')||m.includes('[ban]')||m.includes('[warn]')){badgeText='ERR';badgeClass='err';borderClass='err-border';unameClass='username err';}else if(m.includes('running:')){badgeText='EXEC';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}else if(m.includes('[debug]')){badgeText='DBG';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}}const div=document.createElement('div');div.className=`msg-block ${borderClass}`;div.innerHTML=`<div class="badge ${badgeClass}">${badgeText}</div><div class="msg-content"><span class="${unameClass}">${displayU}</span> <span class="message">${m}</span></div>`;fragment.appendChild(div);added=!0;}catch(err){}}});if(added){c.appendChild(fragment);window.scrollTo(0,document.body.scrollHeight);while(c.children.length>15)c.removeChild(c.firstChild);}}}}finally{fetchingUpdates=!1;}}).catch(e=>{fetchingUpdates=!1;});},1000);</script></body></html>"""
    html_template_oldnew = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');html,body{background-color:rgba(0,0,0,0)!important;margin:0;padding:0;width:100%;height:100%;overflow:hidden}body{font-family:'Fira Code','Consolas',monospace;display:flex;flex-direction:column;padding:15px;justify-content:flex-end;box-sizing:border-box}.chat-box{display:flex;flex-direction:column;align-items:flex-end;gap:6px;width:100%}.msg-block{background-color:rgba(0,0,0,0.85);padding:6px 10px;display:flex;align-items:baseline;font-size:16px;border-radius:6px;box-shadow:2px 2px 4px rgba(0,0,0,0.5);animation:slideIn 0.2s ease-out forwards;margin-bottom:2px;max-width:95%;word-wrap:break-word}.msg-block.cmd-border{border-left:5px solid #00e5ff}.msg-block.chat-border{border-left:5px solid #00e676}.msg-block.vote-border{border-left:5px solid orange}.msg-block.err-border{border-left:5px solid #f33}.badge{padding:2px 6px;font-weight:800;color:#111;font-size:11px;border-radius:3px;margin-right:8px;flex-shrink:0;align-self:flex-start;margin-top:3px}.badge.cmd{background-color:#00e5ff}.badge.chat{background-color:#00e676}.badge.vote{background-color:orange}.badge.err{background-color:#f33;color:#fff}.msg-content{display:block;word-break:break-word}.username{font-weight:900;text-shadow:1px 1px 0 rgba(0,0,0,0.8);margin-right:5px}.username.cmd{color:#00e5ff}.username.chat{color:#00e676}.username.vote{color:orange}.username.err{color:#f33}.message{color:#fff;font-weight:600;text-shadow:1px 1px 0 rgba(0,0,0,0.8);line-height:1.4}@keyframes slideIn{from{transform:translateX(30px);opacity:0}to{transform:translateX(0);opacity:1}}</style></head><body><div class="chat-box" id="chat"></div><script>let lastId=-1;let fetchingUpdates=!1;let hasConnected=!1;setInterval(function(){if(fetchingUpdates)return;fetchingUpdates=!0;fetch('/history?t='+Date.now()).then(r=>r.json()).then(data=>{try{if(data&&Array.isArray(data)){const c=document.getElementById('chat');if(c){if(!hasConnected){hasConnected=!0;const div=document.createElement('div');div.className='msg-block cmd-border';div.innerHTML=`<div class="badge cmd">SYS</div><div class="msg-content"><span class="username cmd">system</span> <span class="message">connected</span></div>`;c.appendChild(div);}const fragment=document.createDocumentFragment();let added=!1;data.forEach(i=>{if(i.id>lastId){lastId=i.id;try{let u=i.u||"Unknown";let m=i.m||"";if(u==='[system]'&&!m.includes('vote')&&!m.includes('[debug]')&&!m.includes('[err]')&&!m.includes('waiting')&&!m.includes('ready')&&!m.includes('chat listener')&&!m.includes('running')&&!m.includes('[ban]')&&!m.includes('[warn]'))return;let isCmd=m.trim().startsWith('!');let badgeClass=isCmd?'cmd':'chat';let badgeText=isCmd?'CMD':'CHAT';let borderClass=isCmd?'cmd-border':'chat-border';let unameClass=isCmd?'username cmd':'username chat';let cleanU=u.replace(/^@+/,'');let displayU='@'+cleanU;if(u==='[console]'){displayU='CONSOLE';badgeText='SYS';}else if(u==='[announcement]'){displayU='ANNOUNCEMENT';badgeText='INFO';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}else if(u==='[system]'){displayU='SYSTEM';badgeText='SYS';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';if(m.includes('[vote]')){badgeText='VOTE';badgeClass='vote';borderClass='vote-border';unameClass='username vote';}else if(m.includes('[err]')||m.includes('[ban]')||m.includes('[warn]')){badgeText='ERR';badgeClass='err';borderClass='err-border';unameClass='username err';}else if(m.includes('running:')){badgeText='EXEC';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}else if(m.includes('[debug]')){badgeText='DBG';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}}const div=document.createElement('div');div.className=`msg-block ${borderClass}`;div.innerHTML=`<div class="badge ${badgeClass}">${badgeText}</div><div class="msg-content"><span class="${unameClass}">${displayU}</span> <span class="message">${m}</span></div>`;fragment.appendChild(div);added=!0;}catch(err){}}});if(added){c.appendChild(fragment);window.scrollTo(0,document.body.scrollHeight);while(c.children.length>20)c.removeChild(c.firstChild);}}}}finally{fetchingUpdates=!1;}}).catch(e=>{fetchingUpdates=!1;});},1000);</script></body></html>"""
    html_debugchat = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');html,body{background-color:rgba(0,0,0,0)!important;margin:0;padding:0;width:100%;height:100%;overflow:hidden}body{font-family:'Fira Code','Consolas',monospace;display:flex;flex-direction:column;padding:15px;justify-content:flex-end;box-sizing:border-box}.chat-box{display:flex;flex-direction:column;align-items:flex-end;gap:6px;width:100%}.msg-block{background-color:rgba(0,0,0,0.85);padding:6px 10px;display:flex;align-items:baseline;font-size:16px;border-radius:6px;box-shadow:2px 2px 4px rgba(0,0,0,0.5);animation:slideIn 0.2s ease-out forwards;margin-bottom:2px;max-width:95%;word-wrap:break-word}.msg-block.cmd-border{border-left:5px solid #00e5ff}.msg-block.chat-border{border-left:5px solid #00e676}.msg-block.vote-border{border-left:5px solid orange}.msg-block.err-border{border-left:5px solid #f33}.badge{padding:2px 6px;font-weight:800;color:#111;font-size:11px;border-radius:3px;margin-right:8px;flex-shrink:0;align-self:flex-start;margin-top:3px}.badge.cmd{background-color:#00e5ff}.badge.chat{background-color:#00e676}.badge.vote{background-color:orange}.badge.err{background-color:#f33;color:#fff}.msg-content{display:block;word-break:break-word}.username{font-weight:900;text-shadow:1px 1px 0 rgba(0,0,0,0.8);margin-right:5px}.username.cmd{color:#00e5ff}.username.chat{color:#00e676}.username.vote{color:orange}.username.err{color:#f33}.message{color:#fff;font-weight:600;text-shadow:1px 1px 0 rgba(0,0,0,0.8);line-height:1.4}@keyframes slideIn{from{transform:translateX(30px);opacity:0}to{transform:translateX(0);opacity:1}}</style></head><body><div class="chat-box" id="chat"></div><script>let lastId=-1;let fetchingUpdates=!1;setInterval(function(){if(fetchingUpdates)return;fetchingUpdates=!0;fetch('/history?t='+Date.now()).then(r=>r.json()).then(data=>{try{if(data&&Array.isArray(data)){const c=document.getElementById('chat');if(c){const fragment=document.createDocumentFragment();let added=!1;data.forEach(i=>{if(i.id>lastId){lastId=i.id;try{let u=i.u||"Unknown";let m=i.m||"";let isCmd=m.trim().startsWith('!');let badgeClass=isCmd?'cmd':'chat';let badgeText=isCmd?'CMD':'CHAT';let borderClass=isCmd?'cmd-border':'chat-border';let unameClass=isCmd?'username cmd':'username chat';let cleanU=u.replace(/^@+/,'');let displayU='@'+cleanU;if(u==='[console]'){displayU='CONSOLE';badgeText='SYS';}else if(u==='[announcement]'){displayU='ANNOUNCEMENT';badgeText='INFO';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}else if(u==='[system]'){displayU='SYSTEM';badgeText='SYS';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';if(m.includes('[vote]')){badgeText='VOTE';badgeClass='vote';borderClass='vote-border';unameClass='username vote';}else if(m.includes('[err]')||m.includes('[ban]')||m.includes('[warn]')){badgeText='ERR';badgeClass='err';borderClass='err-border';unameClass='username err';}else if(m.includes('[info]')){badgeText='INFO';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}else if(m.includes('running:')){badgeText='EXEC';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}else if(m.includes('[debug]')){badgeText='DBG';badgeClass='cmd';borderClass='cmd-border';unameClass='username cmd';}}const div=document.createElement('div');div.className=`msg-block ${borderClass}`;div.innerHTML=`<div class="badge ${badgeClass}">${badgeText}</div><div class="msg-content"><span class="${unameClass}">${displayU}</span> <span class="message">${m}</span></div>`;fragment.appendChild(div);added=!0;}catch(err){}}});if(added){c.appendChild(fragment);window.scrollTo(0,document.body.scrollHeight);while(c.children.length>20)c.removeChild(c.firstChild);}}}}finally{fetchingUpdates=!1;}}).catch(e=>{fetchingUpdates=!1;});},1000);</script></body></html>"""
    html_stats = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');html,body{background-color:rgba(0,0,0,0)!important;margin:0;padding:20px;overflow:hidden;font-family:'Fira Code',Consolas,monospace}.stats-widget{background:rgba(20,20,25,0.85);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:20px 30px;display:inline-block;box-shadow:0 10px 25px rgba(0,0,0,0.5)}.stat-row{display:flex;align-items:center;justify-content:space-between;margin:12px 0;gap:40px}.stat-label{color:#a1a1aa;font-weight:bold;font-size:16px;text-transform:uppercase;letter-spacing:1px}.stat-value{color:#fff;font-weight:bold;font-size:24px;text-shadow:0 0 10px rgba(255,255,255,0.2)}.stat-row.cmds .stat-value{color:#00E5FF;text-shadow:0 0 10px rgba(0,229,255,0.3)}.stat-row.views .stat-value{color:#3B82F6;text-shadow:0 0 10px rgba(59,130,246,0.3)}.stat-row.likes .stat-value{color:#10B981;text-shadow:0 0 10px rgba(16,185,129,0.3)}.stat-row.errs .stat-value{color:#EF4444;text-shadow:0 0 10px rgba(239,68,68,0.3)}.version-tag{font-size:12px;color:#52525b;text-align:right;margin-top:15px;font-weight:bold;border-top:1px solid #3f3f46;padding-top:10px}</style></head><body><div class="stats-widget"><div class="stat-row"><span class="stat-label">UPTIME</span><span class="stat-value" id="uptime">0d 0h 0m 0s</span></div><div class="stat-row views"><span class="stat-label">VIEWERS</span><span class="stat-value" id="viewers">0</span></div><div class="stat-row likes"><span class="stat-label">LIKES</span><span class="stat-label" id="likes">0</span></div><div class="stat-row cmds"><span class="stat-label">CMDS EXECUTED</span><span class="stat-value" id="cmds">0</span></div><div class="stat-row errs"><span class="stat-label">FAILED CMDS</span><span class="stat-value" id="failed">0</span></div><div class="version-tag">{{ version }}</div></div><script>setInterval(function(){fetch('/stats_data?t='+Date.now()).then(r=>r.json()).then(data=>{document.getElementById('uptime').innerText=data.uptime;document.getElementById('cmds').innerText=data.commands;document.getElementById('failed').innerText=data.failed;if(document.getElementById('viewers'))document.getElementById('viewers').innerText=data.viewers||"0";if(document.getElementById('likes'))document.getElementById('likes').innerText=data.likes||"0";}).catch(e=>{});},1000);</script></body></html>"""
    html_ultradebug = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@500;700&display=swap');html,body{background-color:#09090b!important;margin:0;padding:20px;overflow:hidden;font-family:'Fira Code',Consolas,monospace;color:#00FF41}.stats-widget{background:rgba(20,20,25,0.95);border:1px solid #00FF41;border-radius:12px;padding:20px 30px;box-shadow:0 0 15px rgba(0,255,65,0.2)}.stat-row{display:flex;align-items:center;justify-content:space-between;margin:12px 0;gap:40px;border-bottom:1px solid #18181b;padding-bottom:8px}.stat-label{color:#a1a1aa;font-weight:bold;font-size:16px;text-transform:uppercase}.stat-value{color:#00FF41;font-weight:bold;font-size:24px;text-shadow:0 0 8px rgba(0,255,65,0.5)}</style></head><body><div class="stats-widget"><div class="stat-row"><span class="stat-label">QUEUE SIZE</span><span class="stat-value" id="qsize">0</span></div><div class="stat-row"><span class="stat-label">COM LOCKED</span><span class="stat-value" id="comstate">FALSE</span></div><div class="stat-row"><span class="stat-label">ACTIVE THREADS</span><span class="stat-value" id="threads">0</span></div><div class="stat-row"><span class="stat-label">LAST REBUILD</span><span class="stat-value" id="rebuild">0s ago</span></div><div class="stat-row"><span class="stat-label">FAILED ACTIONS</span><span class="stat-value" style="color:#FF3333" id="failed">0</span></div></div><script>setInterval(function(){fetch('/debug_data?t='+Date.now()).then(r=>r.json()).then(data=>{document.getElementById('qsize').innerText=data.qsize;document.getElementById('comstate').innerText=data.comstate;document.getElementById('threads').innerText=data.threads;document.getElementById('rebuild').innerText=data.rebuild;document.getElementById('failed').innerText=data.failed;}).catch(e=>{});},500);</script></body></html>"""

    @obs_web_overlay_app.route('/')
    def index_page(): return render_template_string(html_index)
    @obs_web_overlay_app.route('/obs')
    def obs_overlay(): return render_template_string(html_template, padding=10)
    @obs_web_overlay_app.route('/obs2')
    def obs_overlay2(): return render_template_string(html_template_2)
    @obs_web_overlay_app.route('/obsnew')
    def obs_overlay_new(): return render_template_string(html_template_new)
    @obs_web_overlay_app.route('/oldobsnew')
    def obs_overlay_oldnew(): return render_template_string(html_template_oldnew)
    @obs_web_overlay_app.route('/debugchat')
    def obs_overlay_debugchat(): return render_template_string(html_debugchat)
    @obs_web_overlay_app.route('/ultradebug')
    def ultradebug_overlay(): return render_template_string(html_ultradebug)
    @obs_web_overlay_app.route('/stats')
    def stats_overlay(): return render_template_string(html_stats, version=version)
    @obs_web_overlay_app.route('/stats_data')
    def get_stats_data(): 
        uptime_sec = int(time.time() - script_start_time)
        d, r = divmod(uptime_sec, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)
        uptime_str = f"{d}d {h}h {m}m {s}s" if d > 0 else f"{h}h {m}m {s}s"
        return jsonify({"uptime": uptime_str, "commands": total_commands_executed, "failed": total_commands_failed, "viewers": current_viewers, "likes": current_likes})
    @obs_web_overlay_app.route('/updates')
    def get_updates(): 
        with buffer_lock:
            data = list(messages_buffer)
            messages_buffer.clear()
        return jsonify(data)
    @obs_web_overlay_app.route('/debug_data')
    def get_debug_data():
        qsize = 0
        comstate = "FALSE"
        threads = threading.active_count()
        rebuild_sec = 0
        if 'main_gui_application' in globals():
            qsize = main_gui_application.cmd_queue.qsize()
            comstate = "TRUE" if getattr(main_gui_application, 'shared_kb', None) else "FALSE"
            rebuild_sec = int(time.time() - getattr(main_gui_application, 'last_com_rebuild_time', time.time()))
        return jsonify({"qsize": qsize, "comstate": comstate, "threads": threads, "rebuild": f"{rebuild_sec}s ago", "failed": total_commands_failed})
    @obs_web_overlay_app.route('/history')
    def get_history(): 
        with history_lock: return jsonify(list(web_chat_history))
    @obs_web_overlay_app.route('/status_update')
    def get_status_update(): return jsonify({"status": current_status, "vote": current_vote_info, "viewers": current_viewers, "likes": current_likes, "chat_visible": overlay_chat_visible, "split_mode": split_overlay_mode})

    app_flash = {"text": "", "kind": "info", "n": 0, "dur": 6}
    FLASH_BANNER_APP = """<style>#ytpFlash{position:fixed;left:50%;top:20px;transform:translateX(-50%) translateY(-160%);z-index:2147483646;font-family:'Segoe UI',system-ui,sans-serif;font-weight:700;font-size:15px;color:#fff;padding:11px 20px;border-radius:13px;background:rgba(15,15,22,.92);border:1px solid rgba(0,229,255,.45);box-shadow:0 12px 40px rgba(0,0,0,.5);opacity:0;transition:transform .4s cubic-bezier(.2,.9,.3,1.3),opacity .4s;max-width:80vw;text-align:center}#ytpFlash.show{transform:translateX(-50%) translateY(0);opacity:1}#ytpFlash.good{border-color:rgba(16,185,129,.6)}#ytpFlash.warn{border-color:rgba(245,158,11,.6)}#ytpFlash.err{border-color:rgba(239,68,68,.6)}</style><div id=ytpFlash></div><script>(function(){var el=document.getElementById('ytpFlash'),last=-1,h=null;function p(){fetch('/flash.json?_='+Date.now()).then(function(r){return r.json();}).then(function(d){if(d&&d.n!==last&&d.text){last=d.n;el.textContent=d.text;el.className=d.kind||'info';void el.offsetWidth;el.classList.add('show');if(h)clearTimeout(h);h=setTimeout(function(){el.classList.remove('show');},(d.dur||6)*1000);}else if(d){last=Math.max(last,d.n||0);}}).catch(function(){}).finally(function(){setTimeout(p,1000);});}p();})();</script>"""
    @obs_web_overlay_app.route('/flash.json')
    def get_flash_json(): return jsonify(app_flash)
    for _tn in ("html_template", "html_template_2", "html_template_new", "html_template_oldnew", "html_debugchat", "html_stats", "html_ultradebug"):
        _tv = globals().get(_tn)
        if isinstance(_tv, str) and "</body>" in _tv and "ytpFlash" not in _tv:
            globals()[_tn] = _tv.replace("</body>", FLASH_BANNER_APP + "</body>", 1)

def start_flask():
    global flask_port
    if flask_available:
        try: 
            if 'flask.cli' in sys.modules: sys.modules['flask.cli'].show_server_banner = lambda *x: None
            if platform.system() == "Windows":
                try:
                    out = subprocess.check_output(["netstat", "-ano"], timeout=15).decode(errors="ignore")
                    for line in out.splitlines():
                        if "LISTENING" in line and f":{flask_port} " in line + " ":
                            pid = line.strip().split()[-1]
                            if pid.isdigit() and int(pid) > 0 and int(pid) != os.getpid():
                                subprocess.call(["taskkill", "/F", "/PID", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                time.sleep(0.5) 
                except Exception: pass
            for port in range(flask_port, flask_port + 10):
                try:
                    flask_port = port
                    _bind = '0.0.0.0' if os.environ.get("YT2VM_LAN") == "1" else '127.0.0.1'
                    obs_web_overlay_app.run(host=_bind, port=port, debug=False, use_reloader=False, threaded=True)
                    break
                except OSError: continue
        except Exception: pass

def list_serial_ports():
    ports = []
    try:
        from serial.tools import list_ports
        ports = [p.device for p in list_ports.comports()]
    except Exception:
        pass
    if not ports:
        if platform.system() == "Windows": ports = [f"COM{i}" for i in range(3, 12)]
        else: ports = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0"]
    return ports


class PicoController:
    """Sends line-based commands to a Pico 2 W acting as a USB HID device on a
    real physical machine. Protocol is simple newline-terminated text:
      TYPE <t> | SEND <t> | KEY <k> | COMBO a+b | KEYDOWN <k> | KEYUP <k>
      CLICK | RCLICK | MCLICK | MOVE dx dy | ABS x y | SCROLL n | DRAG dx dy
    Only dispatch() needs changing if your firmware speaks a different protocol."""
    def __init__(self, port="", baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.status = "not connected"

    def connect(self):
        try:
            import serial
        except Exception:
            self.status = "pyserial not installed (pip install pyserial)"
            return False
        try:
            if self.ser:
                try: self.ser.close()
                except Exception: pass
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            self.status = f"connected on {self.port}"
            return True
        except Exception as e:
            self.ser = None
            self.status = f"connect failed: {e}"
            return False

    def close(self):
        try:
            if self.ser: self.ser.close()
        except Exception: pass
        self.ser = None
        self.status = "not connected"

    def send_line(self, line):
        if not self.ser: return
        try:
            self.ser.write((line + "\n").encode("utf-8", "ignore"))
        except Exception as e:
            self.status = f"write error: {e}"

    def dispatch(self, cmd, arg):
        base = (cmd[1:] if cmd.startswith("!") else cmd).lower()
        m = {"type": "TYPE", "send": "SEND", "key": "KEY", "combo": "COMBO",
             "keydown": "KEYDOWN", "keyup": "KEYUP", "click": "CLICK", "lclick": "CLICK",
             "rclick": "RCLICK", "mclick": "MCLICK", "move": "MOVE", "abs": "ABS",
             "scroll": "SCROLL", "drag": "DRAG"}
        if base in m:
            self.send_line((m[base] + " " + arg).strip())


# Raw X11 keysym characters. vncdotool's named-key lookup is buggy for several
# keys, so the keysym is sent directly instead of the name.
VNC_KEYMAP = {
    "esc": chr(0xff1b), "escape": chr(0xff1b),
    "tab": chr(0xff09),
    "enter": chr(0xff0d), "return": chr(0xff0d),
    "space": " ",
    "backspace": chr(0xff08),
    "delete": chr(0xffff), "del": chr(0xffff),
    "insert": chr(0xff63), "ins": chr(0xff63),
    "home": chr(0xff50), "end": chr(0xff57),
    "pageup": chr(0xff55), "pgup": chr(0xff55),
    "pagedown": chr(0xff56), "pgdn": chr(0xff56),
    "ctrl": chr(0xffe3), "control": chr(0xffe3), "lctrl": chr(0xffe3), "rctrl": chr(0xffe4),
    "alt": chr(0xffe9), "lalt": chr(0xffe9), "ralt": chr(0xffea),
    "shift": chr(0xffe1), "lshift": chr(0xffe1), "rshift": chr(0xffe2),
    "capslock": chr(0xffe5),
    "win": chr(0xffeb), "super": chr(0xffeb), "windows": chr(0xffeb),
    "lwin": chr(0xffeb), "rwin": chr(0xffec), "cmd": chr(0xffeb), "menu": chr(0xff67),
    "up": chr(0xff52), "down": chr(0xff54), "left": chr(0xff51), "right": chr(0xff53),
    "printscreen": chr(0xff61), "pause": chr(0xff13),
}
for _i in range(1, 13): VNC_KEYMAP[f"f{_i}"] = chr(0xffbd + _i)
for _c in "abcdefghijklmnopqrstuvwxyz0123456789": VNC_KEYMAP[_c] = _c


def parse_combo_keys(args):
    """Accept 'win r', 'win+r' and 'winr' as the same combo. If a separator is
    present it is used directly; only a separator-less string falls back to a
    greedy longest-name match, so a properly delimited combo is never re-split."""
    text = (args or "").strip().lower()
    if not text:
        return []
    if " " in text or "+" in text:
        return [k for k in text.replace("+", " ").split() if k]
    known = sorted(VNC_KEYMAP.keys(), key=len, reverse=True)
    out, i = [], 0
    while i < len(text):
        for k in known:
            if text.startswith(k, i):
                out.append(k); i += len(k); break
        else:
            out.append(text[i:]); break
    return out


VNC_PASS_FILE = "vncpass.txt"

# ── VNC LAYOUT TRANSLATION ───────────────────────────────────────────────────
# VMware maps an incoming VNC keysym to a PHYSICAL KEY using a US layout, and
# the guest OS then interprets that key with ITS layout. So sending ':' to a
# Danish guest presses the US ':' key, which on a Danish keyboard is 'ae'.
# The fix is to send the keysym whose US key position produces the character we
# actually want under the guest's layout.
_VNC_XLAT_CACHE = {}


_LOCAL_IP_CACHE = {"ip": None, "at": 0}


def load_saved_vnc_pass():
    """Passwords the user has already told us about, newest first."""
    out = []
    try:
        if os.path.exists(VNC_PASS_FILE):
            with open(VNC_PASS_FILE, "r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.rstrip("\n")
                    if ln and ln not in out:
                        out.append(ln)
    except Exception:
        pass
    return out


def save_vnc_pass(pw):
    """Remember a working password so we never have to ask again."""
    if pw is None:
        return
    try:
        existing = load_saved_vnc_pass()
        if pw in existing:
            existing.remove(pw)
        existing.insert(0, pw)
        with open(VNC_PASS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(existing[:10]) + "\n")
        try:
            if os.name == "posix":
                os.chmod(VNC_PASS_FILE, 0o600)
        except Exception:
            pass
        dbg("vnc", f"saved working vnc password to {VNC_PASS_FILE} (owner-only)")
    except Exception as e:
        dbg("vnc", "could not save vnc password", e)


def get_local_ipv4(prefer_adapter="Ethernet", force=False):
    """Find this PC's LAN IPv4.

    On Windows it parses `ipconfig`, preferring 'Ethernet adapter Ethernet' and
    reading its IPv4 line, while skipping VMware/VirtualBox virtual adapters
    (which otherwise hand back a useless host-only 192.168.x.1). Falls back to a
    UDP-socket trick that works on every platform without sending anything."""
    if not force and _LOCAL_IP_CACHE["ip"] and time.time() - _LOCAL_IP_CACHE["at"] < 120:
        return _LOCAL_IP_CACHE["ip"]
    ip = None
    if platform.system() == "Windows":
        try:
            r = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=12)
            out = r.stdout or ""
            sections, current, buf = {}, None, []
            for line in out.splitlines():
                if line.strip() and not line.startswith(" "):
                    if current is not None:
                        sections[current] = buf
                    current = line.strip().rstrip(":")
                    buf = []
                elif current is not None:
                    buf.append(line)
            if current is not None:
                sections[current] = buf

            def ipv4_of(lines):
                import re as _re
                for ln in lines:
                    low = ln.lower()
                    if "ipv4" not in low or ("address" not in low and "adresse" not in low):
                        continue
                    m = _re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", ln.split(":")[-1])
                    if m:
                        return m.group(1)
                return None

            def is_virtual(name):
                n = name.lower()
                return any(v in n for v in ("vmnet", "vmware", "virtualbox", "hyper-v",
                                            "loopback", "bluetooth", "vethernet", "docker",
                                            "tap-", "tailscale", "zerotier", "wsl"))

            target = f"ethernet adapter {prefer_adapter}".lower()
            for name, lines in sections.items():
                if name.lower() == target and not is_virtual(name):
                    ip = ipv4_of(lines)
                    if ip:
                        dbg("net", f"local ip {ip} from '{name}'")
                        break
            if not ip:
                for name, lines in sections.items():
                    if name.lower().startswith("ethernet adapter") and not is_virtual(name):
                        cand = ipv4_of(lines)
                        if cand and not cand.startswith("169.254"):
                            ip = cand
                            dbg("net", f"local ip {ip} from '{name}'")
                            break
            if not ip:
                for name, lines in sections.items():
                    if is_virtual(name):
                        continue
                    cand = ipv4_of(lines)
                    if cand and not cand.startswith("169.254") and cand != "127.0.0.1":
                        ip = cand
                        dbg("net", f"local ip {ip} from '{name}'")
                        break
        except Exception as e:
            dbg("net", "ipconfig parse failed", e)
    if not ip:
        try:
            import socket
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.settimeout(1.0)
            sk.connect(("8.8.8.8", 80))
            ip = sk.getsockname()[0]
            sk.close()
            dbg("net", f"local ip {ip} via socket fallback")
        except Exception:
            ip = None
    _LOCAL_IP_CACHE["ip"] = ip
    _LOCAL_IP_CACHE["at"] = time.time()
    return ip


def _tcp_listening(host, port, timeout=0.4):
    import socket
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


# host-side VNC servers that squat on 5900 and intercept our connection
VNC_SQUATTER_PROCS = [
    "tvnserver.exe", "tvnviewer.exe", "winvnc.exe", "winvnc4.exe",
    "vncserver.exe", "vncserverui.exe", "vncviewer.exe",
    "x11vnc", "tigervncserver", "Xtightvnc",
]
VNC_SQUATTER_SERVICES = ["tvnserver", "uvnc_service", "vncserver", "RealVNC Server"]


def kill_vnc_squatters(reason=""):
    """Stop any host VNC server (TightVNC, UltraVNC, RealVNC...) holding our
    port. Otherwise the bot connects to the HOST's VNC server instead of the
    guest and every keystroke goes to the wrong machine."""
    killed = []
    try:
        if platform.system() == "Windows":
            for svc in VNC_SQUATTER_SERVICES:
                try:
                    r = subprocess.run(["sc", "stop", svc], capture_output=True, text=True, timeout=12)
                    if r.returncode == 0:
                        killed.append(f"service:{svc}")
                        dbg("vnc", f"stopped service {svc}")
                except Exception:
                    pass
            for proc in VNC_SQUATTER_PROCS:
                if not proc.lower().endswith(".exe"):
                    continue
                try:
                    r = subprocess.run(["taskkill", "/F", "/T", "/IM", proc],
                                       capture_output=True, text=True, timeout=12)
                    if r.returncode == 0:
                        killed.append(proc)
                        dbg("vnc", f"killed {proc}")
                except Exception:
                    pass
        else:
            for proc in VNC_SQUATTER_PROCS:
                name = proc[:-4] if proc.lower().endswith(".exe") else proc
                try:
                    r = subprocess.run(["pkill", "-f", name], capture_output=True, text=True, timeout=10)
                    if r.returncode == 0:
                        killed.append(name)
                        dbg("vnc", f"killed {name}")
                except Exception:
                    pass
    except Exception as e:
        dbg("vnc", "kill_vnc_squatters failed", e)
    if killed:
        console_log("SYSTEM", f"stopped host VNC server(s): {', '.join(killed)}"
                              + (f" ({reason})" if reason else ""))
        time.sleep(1.2)
    return killed


def pick_free_vnc_port(start=5900, end=5920, host="127.0.0.1"):
    """Find a port nothing else is listening on. TightVNC/RealVNC/UltraVNC on
    the HOST default to 5900, which collides with the VM's VNC server."""
    for port in range(int(start), int(end) + 1):
        if not _tcp_listening(host, port):
            return port
    return int(start)


def vnc_port_conflict(port, host="127.0.0.1"):
    """True when something is ALREADY listening before our VM has opened it."""
    return _tcp_listening(host, port)


def build_vnc_translation(layout):
    """char wanted on the guest -> (us_base_key, need_shift, need_altgr)

    VMware maps an incoming keysym to a physical key but does NOT apply the
    shift/AltGr that keysym implies - sending '*' pressed the right key without
    shift and produced '. So every character is resolved to the UNSHIFTED US key
    at the correct physical position, and we hold shift or AltGr ourselves."""
    layout = (layout or "US").upper()
    if layout in _VNC_XLAT_CACHE:
        return _VNC_XLAT_CACHE[layout]
    table = {}
    try:
        tgt = _layouts.get(layout)
        us = _layouts.get("US")
        if tgt and us:
            # physical key -> the UNSHIFTED us character that reaches it
            us_base = {}
            for ch, codes in (us.get("noshift") or {}).items():
                us_base[tuple(codes)] = ch
            for level, need_shift, need_altgr in (("noshift", False, False),
                                                  ("shift", True, False),
                                                  ("altgr", False, True)):
                for ch, codes in (tgt.get(level) or {}).items():
                    base = us_base.get(tuple(codes))
                    if base is None:
                        table[ch] = (None, False, False)   # no us key -> alt+numpad
                    else:
                        table[ch] = (base, need_shift, need_altgr)
    except Exception as e:
        dbg("vnc", f"could not build translation for {layout}", e)
    _VNC_XLAT_CACHE[layout] = table
    return table


_VNC_LAYOUT_CHARS = {}


def _layout_can_type(ch, layout):
    key = layout.upper()
    if key not in _VNC_LAYOUT_CHARS:
        chars = set()
        tgt = _layouts.get(key) or {}
        for level in ("noshift", "shift", "altgr"):
            chars.update((tgt.get(level) or {}).keys())
        _VNC_LAYOUT_CHARS[key] = chars
    return ch in _VNC_LAYOUT_CHARS[key]


def vnc_char_for(ch, layout):
    """Return (us_base_key, need_shift, need_altgr).
    base None means there is no reachable key - use Alt+numpad."""
    layout = (layout or "US").upper()
    # Turkish has two separate i letters: I is the capital of dotless 'i' (ı),
    # and the capital of ordinary 'i' is 'Ii'. Lowercasing naively lands on the
    # wrong key, so map the pair explicitly.
    if layout == "TURKISH":
        tr_pair = {"I": "\u0131", "\u0130": "i"}
        if ch in tr_pair:
            base, _s, altgr = vnc_char_for(tr_pair[ch], layout)
            if base is not None:
                return base, True, altgr
            return None, False, False
    # uppercase letters are shift + the lowercase key on every layout, and the
    # letter positions match US on QWERTY/QWERTZ/AZERTY alike once translated
    if ch.isalpha() and ch.isupper() and ch.lower() != ch:
        base, _s, altgr = vnc_char_for(ch.lower(), layout)
        if base is not None:
            return base, True, altgr
        return None, False, False
    t = build_vnc_translation(layout)
    if ch in t:
        return t[ch]
    if layout == "US":
        return ch, False, False
    if not _layout_can_type(ch, layout):
        return None, False, False
    return ch, False, False


class VMwareController:
    """VMware Workstation backend.

    Lifecycle runs through vmrun (start/stop/reset/snapshot). Input runs over
    VNC with vncdotool, because VMware exposes no scancode API like VirtualBox.
    VNC is keysym-based, so characters are sent as characters and VMware maps
    them using RemoteDisplay.vnc.keyMap in the .vmx (we set 'us' or 'dk')."""

    def __init__(self, vmrun_path="", vmx="", host="127.0.0.1", port=5900, password="", keymap="us"):
        self.vmrun_path = vmrun_path or find_vmrun()
        self.vmx = vmx
        self.host = host or "127.0.0.1"
        self.port = int(port or 5900)
        self.password = password or ""
        self.keymap = keymap if keymap in ("us", "dk") else "us"
        # the guest OS keyboard layout (DANISH, GERMAN...). This is what the
        # translation uses; the .vmx keyMap is always pinned to "us" so the
        # mapping stays predictable.
        self.guest_layout = "US"
        self.cfg = {}
        self.host_type = ""
        self.auto_kill_squatters = True
        self.client = None
        self.status = "not connected"
        self._mx, self._my = 0, 0
        self._last_ok = 0
        self.lock = threading.RLock()

    # ---- vmrun lifecycle ----
    def _host_type(self):
        """vmrun needs the product: 'fusion' on macOS, 'ws' for Workstation,
        'player' for VMware Player. Passing 'ws' on a Mac simply fails."""
        if getattr(self, "host_type", ""):
            return self.host_type
        if platform.system() == "Darwin":
            return "fusion"
        low = (self.vmrun_path or "").lower()
        if "player" in low:
            return "player"
        return "ws"

    def _vmrun(self, *args, timeout=90):
        try:
            return subprocess.run([self.vmrun_path, "-T", self._host_type()] + list(args),
                                  capture_output=True, text=True, timeout=timeout)
        except Exception as e:
            console_log("ERROR", f"vmrun failed: {e}")
            return None

    def available(self):
        return bool(self.vmrun_path and os.path.exists(self.vmrun_path))

    def list_running(self):
        r = self._vmrun("list", timeout=25)
        out = (r.stdout if r else "") or ""
        return [ln.strip() for ln in out.splitlines() if ln.strip().lower().endswith(".vmx")]

    def is_running(self):
        if not self.vmx: return False
        target = os.path.normcase(os.path.abspath(self.vmx))
        return any(os.path.normcase(os.path.abspath(p)) == target for p in self.list_running())

    def start(self, gui=True):
        self.ensure_vnc_in_vmx()
        r = self._vmrun("start", self.vmx, "gui" if gui else "nogui", timeout=180)
        return r is not None and r.returncode == 0

    def stop(self, hard=False):
        return self._vmrun("stop", self.vmx, "hard" if hard else "soft", timeout=90)

    def reset(self, hard=True):
        return self._vmrun("reset", self.vmx, "hard" if hard else "soft", timeout=90)

    def suspend(self):
        return self._vmrun("suspend", self.vmx, timeout=90)

    def list_snapshots(self):
        r = self._vmrun("listSnapshots", self.vmx, timeout=40)
        snaps = []
        if r and r.stdout:
            for ln in r.stdout.splitlines()[1:]:
                if ln.strip(): snaps.append(ln.strip())
        return snaps

    def take_snapshot(self, name):
        return self._vmrun("snapshot", self.vmx, name, timeout=180)

    def revert_snapshot(self, name):
        return self._vmrun("revertToSnapshot", self.vmx, name, timeout=180)

    def delete_snapshot(self, name):
        return self._vmrun("deleteSnapshot", self.vmx, name, timeout=120)

    # ---- .vmx VNC setup ----
    def read_vmx_vnc(self):
        """Return the VNC settings currently in the .vmx, so the UI can show
        what VMware will actually use rather than what we hoped we set."""
        info = {"enabled": None, "port": None, "keymap": None, "password": None, "key": None}
        try:
            for ln in open(self.vmx, "r", encoding="utf-8", errors="ignore"):
                if "=" not in ln: continue
                k, v = ln.split("=", 1)
                k = k.strip().lower(); v = v.strip().strip('"')
                if k == "remotedisplay.vnc.enabled": info["enabled"] = v
                elif k == "remotedisplay.vnc.port": info["port"] = v
                elif k == "remotedisplay.vnc.keymap": info["keymap"] = v
                elif k == "remotedisplay.vnc.password": info["password"] = v
                elif k == "remotedisplay.vnc.key": info["key"] = v
        except Exception:
            pass
        return info

    def resolve_port_conflict(self, auto=True):
        """If something else already owns our VNC port while the VM is OFF, that
        is another VNC server (commonly TightVNC on 5900). Move to a free port."""
        try:
            if self.is_running():
                return False, "vm is running - cannot check safely"
        except Exception:
            pass
        if not vnc_port_conflict(self.port, self.host):
            return False, ""
        msg = (f"port {self.port} is already in use by another VNC server on this PC "
               "(TightVNC/RealVNC/UltraVNC usually take 5900)")
        if not auto:
            return True, msg
        # first try to just stop the offender - keeping port 5900 is nicer than
        # relocating, and TightVNC is rarely needed while streaming a VM
        if self.auto_kill_squatters:
            killed = kill_vnc_squatters(f"it was holding port {self.port}")
            if killed and not vnc_port_conflict(self.port, self.host):
                return True, f"stopped {', '.join(killed)} - port {self.port} is free now"
        newp = pick_free_vnc_port(max(5901, int(self.port) + 1), 5920, self.host)
        old = self.port
        self.port = newp
        console_log("SYSTEM", f"{msg} - moving the VM's VNC to port {newp}.")
        dbg("vnc", f"port conflict on {old}, switched to {newp}")
        return True, f"{msg}. Moved this VM to port {newp}."

    def ensure_vnc_in_vmx(self):
        """Write the VNC settings VMware needs. The VM must be powered off.

        Importantly, when no password is set this REMOVES any existing
        RemoteDisplay.vnc.password AND RemoteDisplay.vnc.key lines. VMware
        stores the password in an encoded 'key' entry too, so leaving that
        behind means VMware keeps demanding a password you thought you deleted."""
        if not self.vmx or not os.path.exists(self.vmx):
            return False
        self.resolve_port_conflict(auto=True)
        pw = str(self.password or "")
        if len(pw) > 8:
            # VNC auth (DES) only uses the first 8 characters
            console_log("SYSTEM", "vnc passwords are limited to 8 characters - truncating.")
            pw = pw[:8]
            self.password = pw
        want = {
            "RemoteDisplay.vnc.enabled": '"TRUE"',
            "RemoteDisplay.vnc.port": f'"{self.port}"',
            # pinned to us: the script translates characters itself, so VMware
            # must NOT also remap them or everything gets mangled twice
            "RemoteDisplay.vnc.keyMap": '"us"',
        }
        if pw:
            want["RemoteDisplay.vnc.password"] = f'"{pw}"'
        # when there is no password, these must be GONE, not just blank
        drop = set() if pw else {"remotedisplay.vnc.password", "remotedisplay.vnc.key"}
        try:
            with open(self.vmx, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
            changed = False
            if drop:
                before = len(lines)
                lines = [ln for ln in lines
                         if ln.split("=")[0].strip().lower() not in drop]
                if len(lines) != before:
                    changed = True
                    console_log("SYSTEM", "removed the VNC password from the .vmx (no password set).")
            lower = [ln.split("=")[0].strip().lower() for ln in lines]
            for key, val in want.items():
                k = key.lower()
                if k in lower:
                    idx = lower.index(k)
                    newln = f'{key} = {val}'
                    if lines[idx].strip() != newln:
                        lines[idx] = newln; changed = True
                else:
                    lines.append(f'{key} = {val}'); changed = True
            if changed:
                bak = self.vmx + ".yt2vm.bak"
                if not os.path.exists(bak):
                    try: shutil.copyfile(self.vmx, bak)
                    except Exception: pass
                with open(self.vmx, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                console_log("SYSTEM", f"VNC written to {os.path.basename(self.vmx)}: port {self.port}, keymap {self.keymap}, password {'yes' if pw else 'none'}")
            dbg("vnc", f"vmx now has: {self.read_vmx_vnc()}")
            return True
        except Exception as e:
            console_log("ERROR", f"could not edit vmx: {e}")
            return False

    # ---- VNC input ----
    def config_get(self, key, default=None):
        try:
            return self.cfg.get(key, default)
        except Exception:
            return default

    def _clear_stuck_modifiers(self, client):
        """Release every modifier, in case a previous keyDown never got its keyUp."""
        for ks in (chr(0xFFE1), chr(0xFFE2), chr(0xFFE3), chr(0xFFE4),
                   chr(0xFFE9), chr(0xFFEA), chr(0xFE03), chr(0xFFEB), chr(0xFFEC)):
            try: client.keyUp(ks)
            except Exception: pass

    def _ask_vnc_password(self):
        """Ask the user for the VNC password once, on the UI thread, and return
        it (or None if they cancel). The answer is saved to vncpass.txt so this
        only ever happens once per password."""
        if getattr(self, "_asking_pw", False):
            return None
        self._asking_pw = True
        answer = {"pw": None}
        done = threading.Event()

        def _prompt():
            try:
                import tkinter as _tk
                from tkinter import simpledialog as _sd
                root = getattr(VMwareController, "_ui_root", None)
                pw = _sd.askstring(
                    "VMware VNC password",
                    f"VMware is asking for a VNC password on {self.host}:{self.port}.\n\n"
                    "Enter it here (max 8 characters). It will be saved so you are\n"
                    "not asked again. Leave empty and press OK to try no password.",
                    show="*", parent=root)
                answer["pw"] = ("" if pw is None else pw[:8]) if pw is not None else None
            except Exception as e:
                dbg("vnc", "password prompt failed", e)
                answer["pw"] = None
            finally:
                done.set()

        root = getattr(VMwareController, "_ui_root", None)
        try:
            if root is not None:
                root.after(0, _prompt)       # dialogs must run on the UI thread
                done.wait(120)
            else:
                _prompt()
        except Exception:
            pass
        self._asking_pw = False
        return answer["pw"]

    @staticmethod
    def _port_open(host, port, timeout=1.0):
        """Fast TCP probe. api.connect() blocks for a long time on a refused
        port, and doing that inside the executor thread stalls the whole bot -
        so the port is checked first and we fail fast instead."""
        import socket
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except Exception:
            return False

    def connect(self, timeout=6.0):
        """Connect to the guest's VNC server without ever blocking the caller
        indefinitely: probe the port, then run api.connect in a worker thread
        with a hard timeout."""
        t0 = time.time()
        try:
            from vncdotool import api
        except Exception:
            self.status = "vncdotool not installed (pip install vncdotool)"
            dbg("vnc", self.status)
            return False
        # VMware's VNC may bind to loopback OR to this PC's LAN address, so probe
        # both and use whichever actually answers.
        hosts = []
        for h in (self.host, "127.0.0.1", get_local_ipv4(), "localhost"):
            if h and h not in hosts:
                hosts.append(h)
        live = None
        for h in hosts:
            if self._port_open(h, self.port, 0.8):
                live = h
                break
        if live is None:
            self.client = None
            self.status = (f"nothing is listening on port {self.port} (tried {', '.join(hosts)}) - "
                           "VNC is not enabled in the .vmx, the VM is off, or the port is wrong")
            dbg("vnc", f"port probe FAILED on all hosts {hosts}:{self.port} ({(time.time()-t0)*1000:.0f}ms)")
            return False
        if live != self.host:
            dbg("vnc", f"vnc answered on {live} (not {self.host}) - switching to it")
            self.host = live
        # the port answers, but is it OUR vm? if the vm is powered off then this
        # is some other vnc server on the host (TightVNC etc) and connecting to
        # it would send keystrokes to the wrong machine entirely.
        try:
            if not self.is_running():
                self.client = None
                # the vm is off, so whatever answered is a host vnc server - kill it
                if self.auto_kill_squatters:
                    killed = kill_vnc_squatters(f"it answered on {self.host}:{self.port} while the VM was off")
                    if killed:
                        self.status = (f"stopped host VNC server ({', '.join(killed)}) that was holding "
                                       f"{self.host}:{self.port}. Start the VM and try again.")
                        dbg("vnc", "killed foreign vnc server that was squatting our port")
                        return False
                self.status = (f"something is listening on {self.host}:{self.port} but the VM is NOT "
                               "running - that is another VNC server on this PC (TightVNC?). "
                               "Use 'Kill TightVNC / host VNC' on the VMS tab.")
                dbg("vnc", "port answered but vm is off - refusing to connect to a foreign vnc server")
                return False
        except Exception:
            pass
        dbg("vnc", f"port {self.host}:{self.port} is open, connecting...")
        self.disconnect()

        # Try passwords in order: the configured one, then blank, then the common
        # VMware default, then anything the user has told us before. The first
        # one that works gets remembered.
        candidates = []
        def _add(p):
            key = "" if p is None else str(p)
            if key not in [("" if c is None else str(c)) for c in candidates]:
                candidates.append(p)
        if self.password: _add(str(self.password))
        _add(None)          # blank / no auth
        _add("1234")        # common default
        for saved in load_saved_vnc_pass(): _add(saved)

        last_err = None
        for pw in candidates:
            result = {}
            def _do(_pw=pw):
                try:
                    server = f"{self.host}::{self.port}"
                    result["client"] = api.connect(server, password=(str(_pw) if _pw else None))
                except Exception as e:
                    result["err"] = e
            th = threading.Thread(target=_do, daemon=True, name="vnc-connect")
            th.start()
            th.join(timeout)
            if th.is_alive():
                self.client = None
                self.status = f"vnc connect timed out after {timeout}s"
                dbg("vnc", self.status)
                return False
            if "err" not in result and result.get("client") is not None:
                self.client = result["client"]
                if pw:
                    self.password = str(pw)
                    save_vnc_pass(str(pw))
                dbg("vnc", f"authenticated with {'password' if pw else 'no password'}")
                break
            last_err = result.get("err")
            dbg("vnc", f"auth attempt with {'blank' if not pw else repr(pw)} failed: {str(last_err)[:80]}")
        else:
            # every candidate failed - ask the user, then retry with what they give us
            self.client = None
            asked = self._ask_vnc_password()
            if asked is not None:
                self.password = asked
                save_vnc_pass(asked)
                result = {}
                def _do2():
                    try:
                        result["client"] = api.connect(f"{self.host}::{self.port}",
                                                       password=(str(asked) if asked else None))
                    except Exception as e:
                        result["err"] = e
                th = threading.Thread(target=_do2, daemon=True, name="vnc-connect-retry")
                th.start(); th.join(timeout)
                if "err" not in result and result.get("client") is not None:
                    self.client = result["client"]
                    dbg("vnc", "authenticated with the password you entered")
                else:
                    self.status = f"vnc password rejected: {str(result.get('err', 'unknown'))[:100]}"
                    dbg("vnc", self.status)
                    return False
            else:
                result = {"err": last_err}
        if "err" in result:
            self.client = None
            e = result["err"]
            msg = str(e).lower()
            vmx_vnc = self.read_vmx_vnc() if self.vmx else {}
            if "password" in msg or "auth" in msg or "security" in msg or "vncauth" in msg:
                if vmx_vnc.get("password") or vmx_vnc.get("key"):
                    self.status = ("VNC password mismatch. The .vmx has a password set - "
                                   "either type it in the VMS tab, or power the VM OFF and press "
                                   "'Enable VNC in .vmx' with the password box empty to remove it.")
                else:
                    self.status = ("VNC server wants a password but the .vmx has none we can read "
                                   "(VMware may have stored an encoded one). Power the VM OFF and "
                                   "press 'Enable VNC in .vmx' to clear it.")
            else:
                self.status = f"vnc connect failed: {e}"
            dbg("vnc", self.status, e)
            return False
        self.client = result.get("client")
        if self.client is None:
            self.status = "vnc connect returned no client"
            dbg("vnc", self.status)
            return False
        try: self.client.timeout = 10
        except Exception: pass
        self._clear_stuck_modifiers(self.client)
        self._last_ok = time.time()
        self.status = f"connected {self.host}::{self.port}"
        dbg("vnc", f"CONNECTED in {(time.time()-t0)*1000:.0f}ms")
        return True

    def disconnect(self):
        try:
            if self.client: self.client.disconnect()
        except Exception: pass
        self.client = None

    def _need(self, fresh=False):
        """Keep ONE live session for the whole chain.

        Reconnecting per action was breaking multi-command chains: VMware resets
        the guest's keyboard state when a VNC client disconnects, so
        '!combo win+r !type notepad' opened Run and then lost the typing. Only
        reconnect when there is no client, when the caller forces it, or when the
        session has been idle long enough to have gone stale."""
        idle = time.time() - getattr(self, "_last_ok", 0)
        if self.client is None or fresh or idle > 120:
            self.connect()
        if self.client is None:
            try:
                from vncdotool import api  # noqa
                self.status = (self.status or "vnc not connected") + " (is VNC enabled in the .vmx and the VM running?)"
            except Exception:
                self.status = "vncdotool not installed - run: pip install vncdotool"
            console_log("ERROR", f"vmware input unavailable: {self.status}")
            return False
        return True

    def _alt_numpad(self, ch):
        """Type a character by holding Alt and entering its code on the numpad.
        Windows accepts this regardless of the guest's keyboard layout, which is
        the only way to reach keys that do not exist on a US keyboard (| < > on
        Danish live on the extra ISO key next to left shift)."""
        try:
            code = str(ord(ch))
            alt = chr(0xFFE9)                      # Alt_L
            kp = {str(d): chr(0xFFB0 + d) for d in range(10)}   # KP_0..KP_9
            self.client.keyDown(alt); self._flush()
            try:
                for digit in code:
                    self.client.keyPress(kp[digit]); self._flush()
                    time.sleep(0.02)
            finally:
                self.client.keyUp(alt); self._flush()
            dbg("vnc", f"typed {ch!r} via Alt+{code} (no key for it on a US keyboard)")
            return True
        except Exception as e:
            dbg("vnc", f"alt+numpad failed for {ch!r}", e)
            return False

    def _flush(self, hard=False):
        # vncdotool sends async. A tiny pause forces the queue out, but doing it
        # after EVERY key made a full network round-trip per character, which is
        # what made typing crawl on a slow PC. Only flush hard where ordering
        # actually matters (after a modifier press); otherwise skip it.
        if not hard:
            return
        try:
            if hasattr(self.client, "pause"): self.client.pause(0.01)
        except Exception:
            pass

    MAX_TYPE = 4000   # hard ceiling so one giant command can never wedge typing

    def type_text(self, text):
        if not self._need(): return
        # protect the box: an enormous string would take minutes and can brick a
        # slow host, so cap it and tell the user rather than freezing.
        if len(text) > self.MAX_TYPE:
            dbg("vmware", f"type request {len(text)} chars > {self.MAX_TYPE}, truncating")
            console_log("SYSTEM", f"typing truncated to {self.MAX_TYPE} chars (command too long)")
            text = text[:self.MAX_TYPE]
        lay = (getattr(self, "guest_layout", "") or keyboard_layout or "US").upper()
        lay = {"DK": "DANISH", "DA": "DANISH", "US": "US", "EN": "US",
               "DE": "GERMAN", "FR": "FRENCH", "UK": "UK", "GB": "UK",
               "TR": "TURKISH"}.get(lay, lay)
        SHIFT = chr(0xFFE1)
        ALT_R = chr(0xFFEA)
        ALT_L = chr(0xFFE9)
        CTRL_L = chr(0xFFE3)
        altgr_mode = str(self.config_get("altgr_mode", "alt_r")).lower()
        # per-character delay: 0 by default so a fast PC rips through it; users on
        # a slow VM can raise vmware_settle if the guest drops keys.
        try:
            per_char = max(0.0, float(self.config_get("vmware_settle", 1.0)) - 1.0) * 0.01
        except Exception:
            per_char = 0.0
        fails = 0
        with self.lock:
            for ch in text:
                try:
                    if ch == " ":
                        self.client.keyPress("space")
                    elif ch == chr(10):
                        self.client.keyPress("return")
                    elif ch == chr(9):
                        self.client.keyPress("tab")
                    else:
                        base, need_shift, need_altgr = vnc_char_for(ch, lay)
                        if base is None or (need_altgr and altgr_mode == "numpad"):
                            self._alt_numpad(ch)
                        elif not need_shift and not need_altgr:
                            # the common case: plain key, no modifier, no flush
                            self.client.keyPress(base)
                        else:
                            held = []
                            try:
                                if need_shift:
                                    self.client.keyDown(SHIFT); held.append(SHIFT)
                                if need_altgr:
                                    if altgr_mode == "ctrl_alt":
                                        self.client.keyDown(CTRL_L); held.append(CTRL_L)
                                        self.client.keyDown(ALT_L); held.append(ALT_L)
                                    else:
                                        self.client.keyDown(ALT_R); held.append(ALT_R)
                                    self._flush(hard=True)   # modifier must land first
                                self.client.keyPress(base)
                                self._flush(hard=True)       # key before release
                            finally:
                                for mod in reversed(held):
                                    try: self.client.keyUp(mod)
                                    except Exception: pass
                    if per_char: time.sleep(per_char)
                except Exception as e:
                    fails += 1
                    dbg("vmware", f"type char {ch!r} failed (continuing)", e)
                    try: self._clear_stuck_modifiers(self.client)
                    except Exception: pass
                    if fails > 8:
                        self.status = f"type error: {e}"
                        self.client = None
                        return
            try:
                self._clear_stuck_modifiers(self.client)
                self._flush(hard=True)
            except Exception:
                pass
            self._last_ok = time.time()
            dbg("vmware", f"typed {len(text)} chars over vnc"
                          + (f" ({fails} retried)" if fails else ""))

    def press_key(self, name):
        k = VNC_KEYMAP.get((name or "").lower().strip(), (name or "").lower().strip())
        with self.lock:
            if not self._need(): return
            try:
                self.client.keyDown(k); time.sleep(0.02); self.client.keyUp(k)
                self._flush()
                self._last_ok = time.time()
                dbg("vmware", f"pressed key {name!r} (keysym {hex(ord(k)) if len(k)==1 else k!r}) over vnc")
            except Exception as e:
                self.status = f"key error: {e}"; self.client = None
                dbg("vmware", "press_key failed - dropping session", e)

    def key_combo(self, combo):
        """Hold the chord down, then release in reverse order. vncdotool's
        dash-joined combo string is unreliable, so keys are held explicitly."""
        names = parse_combo_keys(combo)
        if not names: return
        mapped = [VNC_KEYMAP.get(k, k) for k in names]
        with self.lock:
            if not self._need(): return
            try:
                for k in mapped:
                    self.client.keyDown(k); self._flush(); time.sleep(0.03)
            finally:
                for k in reversed(mapped):
                    try: self.client.keyUp(k); self._flush(); time.sleep(0.03)
                    except Exception: pass
            self._last_ok = time.time()
            dbg("vmware", f"combo {names} sent over vnc")

    def click(self, button=1, count=1):
        """VNC encodes clicks relative to the last mouse position, so a click
        without a preceding move lands at (0,0). Always move first."""
        with self.lock:
            if not self._need(): return
            try:
                self.client.mouseMove(int(self._mx), int(self._my))
                self._flush()
                for _ in range(max(1, min(int(count), 20))):
                    self.client.mousePress(int(button))
                    self._flush()
                    time.sleep(0.03)
                dbg("vmware", f"click btn={button} x{count} at ({self._mx},{self._my})")
            except Exception as e:
                self.status = f"click error: {e}"
                dbg("vmware", "click failed", e)

    def test_connection(self):
        """Connect, report exactly what happened, and send a harmless keypress
        so you can confirm input really reaches the guest."""
        try:
            from vncdotool import api  # noqa
        except Exception:
            return False, "vncdotool is NOT installed. run: pip install vncdotool"
        if not self.vmx:
            return False, "no .vmx selected"
        if not os.path.exists(self.vmx):
            return False, f".vmx does not exist: {self.vmx}"
        try:
            txt = open(self.vmx, "r", encoding="utf-8", errors="ignore").read().lower()
            if "remotedisplay.vnc.enabled" not in txt or '"true"' not in txt.split("remotedisplay.vnc.enabled")[-1][:20]:
                return False, "VNC is not enabled in the .vmx - power the VM OFF and press 'Enable VNC in .vmx'"
        except Exception:
            pass
        if not self.is_running():
            return False, "the VM is not running - start it first"
        if not self.connect():
            return False, f"could not connect to {self.host}::{self.port} - {self.status}"
        try:
            with self.lock:
                self.client.keyDown(VNC_KEYMAP["shift"]); self._flush()
                time.sleep(0.05)
                self.client.keyUp(VNC_KEYMAP["shift"]); self._flush()
            return True, f"connected to {self.host}::{self.port} and sent a test keypress (shift). If the guest ignored it, check RemoteDisplay.vnc.keyMap in the .vmx."
        except Exception as e:
            return False, f"connected but sending failed: {e}"

    def move_abs(self, x, y):
        if not self._need(): return
        try:
            with self.lock:
                self.client.mouseMove(int(x), int(y))
                self._mx, self._my = int(x), int(y)
        except Exception as e:
            self.status = f"move error: {e}"

    def move_rel(self, dx, dy):
        self.move_abs(max(0, self._mx + int(dx)), max(0, self._my + int(dy)))

    def scroll(self, amount):
        if not self._need(): return
        btn = 4 if int(amount) > 0 else 5
        try:
            with self.lock:
                for _ in range(min(abs(int(amount)), 10)): self.client.mousePress(btn)
        except Exception as e:
            self.status = f"scroll error: {e}"

    def drag(self, dx, dy):
        if not self._need(): return
        try:
            with self.lock:
                self.client.mouseDown(1)
                self.client.mouseDrag(max(0, self._mx + int(dx)), max(0, self._my + int(dy)), step=10)
                self.client.mouseUp(1)
                self._mx += int(dx); self._my += int(dy)
        except Exception as e:
            self.status = f"drag error: {e}"


def find_vmx_files(root=None, max_depth=3):
    """Look for VMware VMs, starting with the default Documents\\Virtual Machines
    folder that VMware Workstation creates."""
    roots = []
    if root:
        roots = [root]
    else:
        home = os.path.expanduser("~")
        cands = [
            os.path.join(home, "Documents", "Virtual Machines"),
            os.path.join(home, "Documents", "Virtual Machines.localized"),
            os.path.join(home, "vmware"),
            os.path.join(home, "Virtual Machines"),
            os.path.join(home, "VMware"),
            os.path.join(home, ".vmware"),
        ]
        if platform.system() == "Linux":
            cands += [os.path.join(home, "vmware"), "/var/lib/vmware",
                      os.path.join(home, "Documents", "vmware")]
        elif platform.system() == "Darwin":
            cands += [os.path.join(home, "Virtual Machines.localized")]
        for cand in cands:
            if os.path.isdir(cand): roots.append(cand)
    found = []
    for r in roots:
        try:
            base_depth = r.rstrip(os.sep).count(os.sep)
            for dirpath, dirnames, filenames in os.walk(r):
                if dirpath.count(os.sep) - base_depth >= max_depth:
                    dirnames[:] = []
                    continue
                for fn in filenames:
                    if fn.lower().endswith(".vmx"):
                        found.append(os.path.join(dirpath, fn))
        except Exception:
            continue
    return sorted(set(found))


NAV_GROUPS = [
    ("MAIN",    ["Dashboard", "VM Config", "Commands", "Settings"]),
    ("CONTROL", ["Keys", "Mouse", "Macros", "Quick Type", "Win Apps"]),
    ("MACHINE", ["VMS", "Snapshots", "OS Voting", "Real PC", "System"]),
    ("STREAM",  ["OBS", "Overlays", "Media", "Music Queue", "Chat Tools", "Moderation"]),
    ("TOOLS",   ["Automation", "Event Log", "Replay", "Backup", "Appearance", "Extra Things", "Help", "Diagnostics"]),
]


class SidebarNav(tk.Frame):
    """Control-panel shell: grouped sidebar on the left, page area in the middle,
    live chat docked on the right, status bar along the bottom.

    Implements the slice of the ttk.Notebook API the app already uses
    (add / tabs / index / select / bind) so every existing page keeps working."""

    def __init__(self, master, app, **kw):
        super().__init__(master, bg="#0A0A0F", **kw)
        self.app = app
        self._pages = []           # [(frame, label)]
        self._buttons = {}         # label -> button widget
        self._current = None
        accent = getattr(app, "accent_main", "#00E5FF")

        # ---- sidebar ----
        self.side = tk.Frame(self, bg="#0C0C11", width=196)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        brand = tk.Frame(self.side, bg="#0C0C11"); brand.pack(fill="x", pady=(16, 10), padx=16)
        tk.Label(brand, text=getattr(app, "app_name", "YT2VM"), bg="#0C0C11", fg="#FFFFFF",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(brand, text="CONTROL PANEL", bg="#0C0C11", fg=accent,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(1, 0))
        sc = tk.Canvas(self.side, bg="#0C0C11", bd=0, highlightthickness=0)
        sc.pack(side="left", fill="both", expand=True)
        self._navwrap = tk.Frame(sc, bg="#0C0C11")
        sc.create_window((0, 0), window=self._navwrap, anchor="nw", width=196, tags="navwin")
        def _navcfg(e=None):
            try:
                sc.configure(scrollregion=sc.bbox("all"))
                sc.itemconfig("navwin", width=sc.winfo_width())
            except Exception: pass
        self._navwrap.bind("<Configure>", _navcfg)
        sc.bind("<Configure>", _navcfg)
        def _wheel(e):
            try:
                delta = int(-1 * (e.delta / 120)) if getattr(e, "delta", 0) else (-1 if getattr(e, "num", 0) == 4 else 1)
                sc.yview_scroll(delta * 2, "units")
            except Exception: pass
            return "break"
        self._nav_wheel = _wheel
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            sc.bind(seq, _wheel); self._navwrap.bind(seq, _wheel); self.side.bind(seq, _wheel)
        self._sc = sc
        self._group_frames = {}

        foot = tk.Frame(self.side, bg="#0C0C11")
        foot.pack(side="bottom", fill="x", pady=(6, 12), padx=12)
        self.theme_btn = tk.Label(foot, text="  Dark / Light", bg="#15151C", fg="#9A9AA6",
                                  font=("Segoe UI", 8, "bold"), anchor="w", padx=10, pady=6, cursor="hand2")
        self.theme_btn.pack(fill="x")
        self.theme_btn.bind("<Button-1>", lambda e: getattr(app, "toggle_dark_light", lambda: None)())
        self.guide_btn = tk.Label(foot, text="  User Guide", bg="#15151C", fg="#9A9AA6",
                                  font=("Segoe UI", 8, "bold"), anchor="w", padx=10, pady=6, cursor="hand2")
        self.guide_btn.pack(fill="x", pady=(6, 0))
        self.guide_btn.bind("<Button-1>", lambda e: getattr(app, "show_welcome_guide", lambda **k: None)(force=True))

        # ---- right: live chat ----
        self.chatpane = tk.Frame(self, bg="#0A0A0F", width=330)
        self.chatpane.pack(side="right", fill="y")
        self.chatpane.pack_propagate(False)
        ch = tk.Frame(self.chatpane, bg="#0F0F15"); ch.pack(fill="both", expand=True, padx=(0, 10), pady=10)
        hdr = tk.Frame(ch, bg="#0F0F15"); hdr.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(hdr, text="Live Chat", bg="#0F0F15", fg="#FFFFFF", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.chat_dot = tk.Label(hdr, text="offline", bg="#0F0F15", fg="#71717A", font=("Segoe UI", 8, "bold"))
        self.chat_dot.pack(side="right")
        self.chatbox = scrolledtext.ScrolledText(ch, font=("Consolas", 8), bg="#08080C", fg="#B8B8C4",
                                                 bd=0, highlightthickness=0, wrap="word")
        self.chatbox.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.chatbox.configure(state="disabled")
        self.chatbox.tag_config("usr", foreground="#E4E4EC")
        self.chatbox.tag_config("cmd", foreground=accent)
        self.chatbox.tag_config("sys", foreground="#10B981")
        self.chatbox.tag_config("err", foreground="#EF4444")
        self.chatbox.tag_config("mod", foreground="#8B5CF6")
        arow = tk.Frame(ch, bg="#0F0F15"); arow.pack(fill="x", padx=10, pady=(0, 10))
        self.autoscroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(arow, text="Auto-scroll", variable=self.autoscroll,
                        style="Toggle.TCheckbutton").pack(side="left")
        tk.Button(arow, text="Clear", font=("Segoe UI", 8, "bold"), bg="#1C1C24", fg="#A1A1AA",
                  bd=0, cursor="hand2", command=self.clear_chat).pack(side="right", ipadx=8)

        # ---- bottom status bar ----
        self.status = tk.Frame(self, bg="#0C0C11", height=26)
        self.status.pack(side="bottom", fill="x")
        self.status.pack_propagate(False)
        self.status_left = tk.Label(self.status, text="Ready", bg="#0C0C11", fg="#8A8A96", font=("Segoe UI", 8))
        self.status_left.pack(side="left", padx=14)
        self.status_right = tk.Label(self.status, text="Stopped", bg="#0C0C11", fg="#71717A", font=("Segoe UI", 8, "bold"))
        self.status_right.pack(side="right", padx=14)

        # ---- center page area ----
        self.content = tk.Frame(self, bg="#09090B")
        self.content.pack(side="left", fill="both", expand=True)

    # ---- Notebook-compatible API ----
    def add(self, frame, text="", **kw):
        label = (text or "").strip()
        self._pages.append((frame, label))
        group = "TOOLS"
        for gname, members in NAV_GROUPS:
            if label in members:
                group = gname; break
        if group not in self._group_frames:
            gf = tk.Frame(self._navwrap, bg="#0C0C11"); gf.pack(fill="x", pady=(10, 2))
            tk.Label(gf, text=group, bg="#0C0C11", fg="#4B4B57",
                     font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=18, pady=(0, 3))
            self._group_frames[group] = gf
        gf = self._group_frames[group]
        b = tk.Label(gf, text="   " + label, bg="#0C0C11", fg="#9A9AA6",
                     font=("Segoe UI", 9), anchor="w", padx=8, pady=5, cursor="hand2")
        b.pack(fill="x", padx=(8, 10))
        for _seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            b.bind(_seq, self._nav_wheel)
            gf.bind(_seq, self._nav_wheel)
        b.bind("<Button-1>", lambda e, f=frame: self.select(f))
        _hov = mix("#0C0C11", "#ffffff", 0.06)
        b.bind("<Enter>", lambda e, w=b, f=frame: w.configure(bg=_hov) if self._current is not f else None)
        b.bind("<Leave>", lambda e, w=b, f=frame: w.configure(
            bg=mix("#0C0C11", getattr(self.app, "accent_main", "#00E5FF"), 0.16) if self._current is f else "#0C0C11"))
        self._buttons[label] = (b, frame)
        if self._current is None:
            self.select(frame)
        return frame

    def tabs(self):
        return [str(f) for f, _ in self._pages]

    def index(self, tab):
        if tab in ("current", "end") or tab is None:
            for i, (f, _) in enumerate(self._pages):
                if f is self._current: return i
            return 0
        key = str(tab)
        for i, (f, _) in enumerate(self._pages):
            if str(f) == key: return i
        return 0

    def select(self, tab=None):
        if tab is None:
            return str(self._current) if self._current is not None else ""
        target = None
        key = str(tab)
        for f, _ in self._pages:
            if f is tab or str(f) == key:
                target = f; break
        if target is None: return ""
        if self._current is not None:
            try: self._current.pack_forget()
            except Exception: pass
        target.pack(in_=self.content, fill="both", expand=True)
        self._current = target
        accent = getattr(self.app, "accent_main", "#00E5FF")
        side_bg = "#0C0C11"
        try: side_bg = self.side.cget("bg")
        except Exception: pass
        active_bg = mix(side_bg, accent, 0.16)
        for lbl, (btn, frm) in self._buttons.items():
            on = frm is target
            try:
                btn.configure(bg=active_bg if on else side_bg, fg=accent if on else "#9A9AA6",
                              font=("Segoe UI", 9, "bold") if on else ("Segoe UI", 9))
            except Exception: pass
        return str(target)

    # ---- live chat feed ----
    def push_chat(self, user, msg, tag="usr"):
        try:
            self.chatbox.configure(state="normal")
            self.chatbox.insert("end", f"[{time.strftime('%H:%M:%S')}] ", "sys")
            self.chatbox.insert("end", f"{user}: ", tag)
            self.chatbox.insert("end", f"{msg}\n", "usr" if tag == "usr" else tag)
            lines = int(self.chatbox.index("end-1c").split(".")[0])
            if lines > 400:
                self.chatbox.delete("1.0", f"{lines-300}.0")
            if self.autoscroll.get(): self.chatbox.see("end")
            self.chatbox.configure(state="disabled")
        except Exception: pass

    def clear_chat(self):
        try:
            self.chatbox.configure(state="normal")
            self.chatbox.delete("1.0", "end")
            self.chatbox.configure(state="disabled")
        except Exception: pass

    def set_status(self, left=None, right=None, running=False):
        try:
            if left is not None: self.status_left.configure(text=left)
            if right is not None:
                self.status_right.configure(text=right, fg="#10B981" if running else "#71717A")
        except Exception: pass


def _hex_to_rgb(c):
    try:
        c = str(c).lstrip("#")
        if len(c) == 3: c = "".join(ch * 2 for ch in c)
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except Exception:
        return 24, 24, 27


def _rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))


def shade(color, factor):
    r, g, b = _hex_to_rgb(color)
    return _rgb_to_hex(r * factor, g * factor, b * factor)


def mix(c1, c2, t):
    """Blend two colours. t=0 -> c1, t=1 -> c2. Used to fake translucency,
    since tkinter widgets cannot actually be semi-transparent."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


def draw_glass(cv, x1, y1, x2, y2, radius, top, bottom, border=None, sheen=True, tag="glass"):
    """Draw a frosted-glass panel: a vertical gradient clipped to rounded
    corners, a bright sheen across the top, and a soft border.

    tkinter has no blur or alpha, so the 'glass' look is built from a real
    per-row gradient (corner inset computed from the circle equation) plus a
    highlight band, which reads as translucent against a dark background."""
    w, h = int(x2 - x1), int(y2 - y1)
    if w <= 2 or h <= 2:
        return
    r = max(0, min(int(radius), h // 2, w // 2))
    steps = max(1, h)
    for i in range(steps):
        y = y1 + i
        t = i / max(1, steps - 1)
        col = mix(top, bottom, t)
        # inset so the gradient follows the rounded corners
        inset = 0
        if i < r:
            dy = r - i
            inset = r - int((max(0.0, r * r - dy * dy)) ** 0.5)
        elif i > h - r - 1:
            dy = i - (h - r - 1)
            inset = r - int((max(0.0, r * r - dy * dy)) ** 0.5)
        cv.create_line(x1 + inset, y, x2 - inset, y, fill=col, tags=tag)
    if sheen:
        # bright top edge + soft highlight band = the glassy sheen
        hi = mix(top, "#ffffff", 0.30)
        cv.create_line(x1 + r, y1 + 1, x2 - r, y1 + 1, fill=hi, tags=tag)
        hi2 = mix(top, "#ffffff", 0.10)
        band = max(2, int(h * 0.18))
        for i in range(band):
            y = y1 + 2 + i
            t = i / max(1, band - 1)
            inset = 0
            if (y - y1) < r:
                dy = r - (y - y1)
                inset = r - int((max(0.0, r * r - dy * dy)) ** 0.5)
            cv.create_line(x1 + inset + 1, y, x2 - inset - 1, y,
                           fill=mix(hi2, top, t), tags=tag)
    if border:
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        cv.create_polygon(pts, smooth=True, splinesteps=24, fill="", outline=border, tags=tag)


class GlassCard(tk.Canvas):
    """A frosted-glass panel you can pack other widgets into."""

    def __init__(self, master, radius=16, tint=None, parent_bg=None, border=None, **kw):
        pbg = parent_bg
        if pbg is None:
            try: pbg = master.cget("bg")
            except Exception: pbg = "#09090B"
        super().__init__(master, bg=pbg, highlightthickness=0, bd=0, **kw)
        self._radius = radius
        self._tint = tint or "#1B1B26"
        self._border = border or mix(self._tint, "#ffffff", 0.12)
        self.body = tk.Frame(self, bg=self._tint)
        self._win = self.create_window(0, 0, window=self.body, anchor="nw")
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _e=None):
        self.delete("glass")
        w, h = max(self.winfo_width(), 4), max(self.winfo_height(), 4)
        top = mix(self._tint, "#ffffff", 0.10)
        bot = shade(self._tint, 0.82)
        draw_glass(self, 1, 1, w - 1, h - 1, self._radius, top, bot, self._border)
        pad = max(6, self._radius // 2)
        self.body.configure(bg=mix(self._tint, "#ffffff", 0.02))
        self.coords(self._win, pad, pad)
        self.itemconfig(self._win, width=max(1, w - pad * 2), height=max(1, h - pad * 2))
        self.tag_lower("glass")

    def set_tint(self, tint):
        self._tint = tint
        self._border = mix(tint, "#ffffff", 0.12)
        self._redraw()


class RoundedButton(tk.Canvas):
    """A real rounded-corner button. tkinter's Button is a hard rectangle, so
    this draws a rounded rectangle on a Canvas and behaves like a Button.

    Accepts the same keywords the app already passes to tk.Button, so it can be
    swapped in globally without touching the call sites."""

    def __init__(self, master=None, cnf=None, text="", command=None,
                 bg=None, background=None, fg=None, foreground=None,
                 font=("Segoe UI", 9, "bold"), activebackground=None,
                 activeforeground=None, bd=0, relief=None, cursor="hand2",
                 radius=10, state="normal", width=None, height=None,
                 highlightthickness=0, anchor=None, justify=None, padx=None,
                 pady=None, wraplength=None, image=None, compound=None,
                 disabledforeground=None, underline=None, takefocus=None, **kw):
        self._bg = bg or background or "#27272A"
        self._fg = fg or foreground or "#FFFFFF"
        self._hover = activebackground or self._shade(self._bg, 1.18)
        self._hover_fg = activeforeground or self._fg
        self._text = text
        self._command = command
        self._radius = radius
        self._font = font
        self._state = state
        self._pressed = False
        parent_bg = "#09090B"
        try:
            parent_bg = master.cget("bg")
        except Exception:
            try: parent_bg = master.cget("background")
            except Exception: pass
        try:
            f = tkfont.Font(font=font)
            tw, th = f.measure(text or ""), f.metrics("linespace")
        except Exception:
            tw, th = max(60, len(str(text)) * 8), 16
        w = width if isinstance(width, int) else tw + 28
        h = height if isinstance(height, int) else th + 14
        super().__init__(master, width=w, height=h, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor=cursor or "")
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    @staticmethod
    def _shade(hexcolor, factor):
        return shade(hexcolor, factor)

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        r = max(0, min(r, int((y2 - y1) / 2), int((x2 - x1) / 2)))
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, splinesteps=24, **kw)

    def _draw(self):
        self.delete("all")
        w = max(int(self.winfo_width()), 2)
        h = max(int(self.winfo_height()), 2)
        disabled = str(self._state) == "disabled"
        base = self._bg
        if disabled:
            base = shade(self._bg, 0.55)
        elif self._pressed:
            base = shade(self._bg, 0.86)
        elif self._hovering():
            base = mix(self._bg, "#ffffff", 0.14)
        top = mix(base, "#ffffff", 0.16)
        bot = shade(base, 0.80)
        border = mix(base, "#ffffff", 0.26 if self._hovering() else 0.14)
        # hover glow: a faint outer ring, so accent buttons feel lit
        if self._hovering() and not disabled:
            try:
                pbg = self.cget("bg")
                glow = mix(pbg, base, 0.55)
                self._round_outline(2, 2, w - 2, h - 2, self._radius + 2, glow)
            except Exception: pass
        draw_glass(self, 3, 2, w - 3, h - 2, self._radius, top, bot, border)
        txt_fg = self._fg if not self._hovering() else self._hover_fg
        if disabled: txt_fg = "#6B6B78"
        # subtle text shadow for depth
        self.create_text(w / 2 + 1, h / 2 + 1, text=self._text,
                         fill=shade(base, 0.6), font=self._font, justify="center")
        self.create_text(w / 2, h / 2, text=self._text, fill=txt_fg,
                         font=self._font, justify="center")

    def _round_outline(self, x1, y1, x2, y2, r, color):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, splinesteps=24, fill="", outline=color, width=2)

    def _hovering(self):
        return getattr(self, "_is_hover", False)

    def _on_enter(self, _e=None):
        self._is_hover = True; self._draw()

    def _on_leave(self, _e=None):
        self._is_hover = False; self._pressed = False; self._draw()

    def _on_press(self, _e=None):
        if str(self._state) == "disabled": return
        self._pressed = True; self._draw()

    def _on_release(self, _e=None):
        if str(self._state) == "disabled": return
        was = self._pressed
        self._pressed = False; self._draw()
        if was and callable(self._command):
            try: self._command()
            except Exception as ex:
                try: console_log("ERROR", f"button command failed: {ex}")
                except Exception: pass

    def configure(self, cnf=None, **kw):
        redraw = False
        for key in ("text", "bg", "background", "fg", "foreground", "state",
                    "activebackground", "activeforeground", "font", "command"):
            if key in kw:
                val = kw.pop(key)
                if key == "text": self._text = val
                elif key in ("bg", "background"): self._bg = val
                elif key in ("fg", "foreground"): self._fg = val
                elif key == "state": self._state = val
                elif key == "activebackground": self._hover = val
                elif key == "activeforeground": self._hover_fg = val
                elif key == "font": self._font = val
                elif key == "command": self._command = val
                redraw = True
        for junk in ("bd", "relief", "cursor", "highlightthickness", "padx", "pady", "anchor"):
            kw.pop(junk, None)
        if kw:
            try: super().configure(**kw)
            except Exception: pass
        if redraw: self._draw()

    config = configure

    def cget(self, key):
        if key == "text": return self._text
        if key in ("bg", "background"): return self._bg
        if key in ("fg", "foreground"): return self._fg
        if key == "state": return self._state
        try: return super().cget(key)
        except Exception: return ""

    def __setitem__(self, key, value):
        self.configure(**{key: value})


# ── OPTIONAL: CustomTkinter ──────────────────────────────────────────────────
# CustomTkinter draws nicer entries/combos/scrollbars/switches than stock tk.
# It is used ONLY where it is a clear win. Buttons stay on RoundedButton because
# CTkButton is a flat rounded rect - no gradient, sheen or hover glow - and it
# rejects the tk kwargs (bd, highlightthickness, insertbackground) used all over
# this file. If customtkinter is not installed, everything falls back to stock tk.
try:
    import customtkinter as ctk
    ctk_available = True
except Exception:
    ctk = None
    ctk_available = False

# ttkbootstrap restyles the ttk widgets (combobox, checkbutton, scrollbar,
# radiobutton) which stock ttk renders poorly on a dark background. It is used
# for those widgets only - our own canvas widgets keep the glass look.
try:
    import ttkbootstrap as tb
    tb_available = True
except Exception:
    tb = None
    tb_available = False

# our palettes -> closest ttkbootstrap theme
TB_THEME_MAP = {
    "original": "darkly", "better": "superhero", "god": "vapor",
    "glass": "darkly", "aurora": "vapor",
    "light": "flatly", "daylight": "litera",
}


def apply_bootstrap_theme(name):
    """Restyle ttk widgets with ttkbootstrap. Returns the Style or None."""
    if not tb_available:
        return None
    try:
        want = TB_THEME_MAP.get(name, "darkly")
        try:
            style = tb.Style()
            names = [str(n) for n in style.theme_names()]
        except Exception:
            style, names = None, []
        # prefer a modern (2.0) theme name; fall back to the legacy one
        modern = {"darkly": ["dark", "darkly"], "superhero": ["dark", "superhero"],
                  "vapor": ["dark", "vapor"], "flatly": ["light", "flatly"],
                  "litera": ["light", "litera"]}
        order = [c for c in modern.get(want, [want]) if not names or c in names] or [want]
        for cand in order:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    if style is not None: style.theme_use(cand)
                    else: style = tb.Style(theme=cand)
                dbg("ui", f"ttkbootstrap theme -> {cand}")
                return style
            except Exception:
                continue
        return style
    except Exception:
        return None

_CTK_DROP = ("bd", "borderwidth", "highlightthickness", "highlightbackground",
             "highlightcolor", "insertbackground", "relief", "activebackground",
             "activeforeground", "disabledforeground", "selectbackground",
             "selectforeground", "cursor", "bg", "background", "fg", "foreground",
             "font", "show", "justify", "state", "width", "textvariable", "values")


class CTkEntryCompat(ctk.CTkEntry if ctk_available else object):
    """CTkEntry that tolerates the tk.Entry keywords used throughout this file."""
    def __init__(self, master=None, **kw):
        show = kw.get("show")
        justify = kw.get("justify")
        font = kw.get("font")
        width = kw.get("width")
        txtvar = kw.get("textvariable")
        fg = kw.get("fg") or kw.get("foreground")
        bg = kw.get("bg") or kw.get("background")
        for k in list(kw):
            if k in _CTK_DROP: kw.pop(k, None)
        opts = {}
        if show: opts["show"] = show
        if justify: opts["justify"] = justify
        if font: opts["font"] = font
        if txtvar is not None: opts["textvariable"] = txtvar
        if isinstance(width, int) and width < 200: opts["width"] = max(60, width * 8)
        if fg: opts["text_color"] = fg
        if bg: opts["fg_color"] = bg
        opts["corner_radius"] = 8
        opts["border_width"] = 1
        try:
            super().__init__(master, **opts, **kw)
        except Exception:
            super().__init__(master)

    def configure(self, cnf=None, **kw):
        for k in list(kw):
            if k in ("bg", "background"): kw["fg_color"] = kw.pop(k)
            elif k in ("fg", "foreground"): kw["text_color"] = kw.pop(k)
            elif k in _CTK_DROP: kw.pop(k, None)
        try: super().configure(**kw)
        except Exception: pass

    config = configure


def enable_ctk(theme_dark=True, accent="#00E5FF"):
    """Switch the nicer widgets on. Safe to call when CTk is missing."""
    if not ctk_available:
        return False
    try:
        ctk.set_appearance_mode("dark" if theme_dark else "light")
        ctk.set_default_color_theme("dark-blue")
        try: ctk.set_widget_scaling(1.0)
        except Exception: pass
        tk.Entry = CTkEntryCompat
        return True
    except Exception:
        return False


if platform.system() != "Darwin":
    tk.Button = RoundedButton

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
            self.efail_count = 0
            self.last_efail_t = 0
            self.last_cmd_ok_t = time.time()
            self.last_escalation_t = 0
            self._maint_start_t = time.time()
            self.api_watchdog_level = 0
            self.last_api_watchdog_action_time = 0
            self.maintenance_lock = threading.Lock()
            self.maintenance_gen = 0
            self.revert_disabled = False
            self.main_heartbeat = time.time()
            self.recent_bot_messages = collections.deque(maxlen=50)
            self.config = self.load_settings()

            self.pico = None
            self.pico_enabled = False
            self.pico_target = self.config.get("pico_target", "vm")   # vm | pico | both
            self.relay_proc = None
            self._automation_started = False
            self.automations = self.config.get("automations", [])
            self.osvoting_enabled = self.config.get("osvoting_enabled", False)
            self.replay_buffer = collections.deque(maxlen=4000)
            self.replaying = False
            self.ui_theme = self.config.get("ui_theme", "original")
            self.relay_host = self.config.get("relay_host", "127.0.0.1")
            self.relay_port = int(self.config.get("relay_port", 8080))
            if self.config.get("accent_color"):
                pass  # applied below after accent_main is set
            
            self.cmd_queue = queue.Queue()
            self.music_queue = []
            self.banned_users = {}
            self.current_song = None
            self.song_paused = False
            self.ultra_speed = self.config.get("ultra_speed", False)
            self.vnc_port = self.config.get("vnc_port", "5900")
            self.vnc_password = self.config.get("vnc_password", "1234")
            self.vmrun_path = self.config.get("vmrun_path", "") or find_vmrun()
            global _RUNTIME_BACKEND
            self.backend = str(self.config.get("backend", "virtualbox") or "virtualbox").lower()
            self.com_mode = ""
            if self.config.get("use_customtkinter", False):
                if enable_ctk(theme_dark=self.THEMES.get(self.config.get("ui_theme", "original"), {}).get("dark", True)):
                    console_log("SYSTEM", "customtkinter widgets enabled.")
            if self.config.get("use_ttkbootstrap", True) and tb_available:
                if apply_bootstrap_theme(self.config.get("ui_theme", "original")) is not None:
                    console_log("SYSTEM", "ttkbootstrap theme applied to ttk widgets.")
            self.vmware = None
            self.vmx_path = self.config.get("vmx_path", "")
            self.vnc_keymap = self.config.get("vnc_keymap", "us")
            self.win_vbox = None
            self.win_session = None
            self.cli_input = False
            if self.backend not in ("virtualbox", "vmware"): self.backend = "virtualbox"
            _RUNTIME_BACKEND = self.backend
            
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
            self.root.geometry(f"1440x860+{max(0,x_cood-150)}+{max(0,y_cood-30)}")
            self.root.minsize(1100, 640)
            self.root.configure(bg="#09090B")
            self.accent_main = "#8B5CF6" if self.is_multistream else "#00E5FF"
            self.accent_hover = "#7C3AED" if self.is_multistream else "#00B3CC"

            self.root.option_add('*TCombobox*Listbox.background', '#18181B')
            self.root.option_add('*TCombobox*Listbox.foreground', 'white')
            self.root.option_add('*TCombobox*Listbox.selectBackground', self.accent_main)
            self.root.option_add('*TCombobox*Listbox.selectForeground', 'black')

            style = ttk.Style()
            if platform.system() == "Darwin" and "aqua" in style.theme_names(): style.theme_use("aqua")
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
            style.configure("TNotebook.Tab", background="#131318", foreground="#8A8A96", padding=[12, 7], font=("Segoe UI", 9, "bold"), borderwidth=0)
            style.map("TNotebook.Tab",
                      background=[("selected", self.accent_main), ("active", "#26262E")],
                      foreground=[("selected", "#000000"), ("active", "#FFFFFF")],
                      expand=[("selected", [1, 1, 1, 0])])
            style.configure("Vertical.TScrollbar", background="#27272A", troughcolor="#0F0F13",
                            bordercolor="#0F0F13", arrowcolor="#8A8A96", darkcolor="#27272A", lightcolor="#27272A")
            style.map("Vertical.TScrollbar", background=[("active", self.accent_main)])
            style.configure("Toggle.TCheckbutton", background="#18181B", foreground="#D4D4D8", font=("Segoe UI", 10), indicatorcolor="#27272A", padding=5)
            style.map("Toggle.TCheckbutton", indicatorcolor=[("selected", "#10B981")])
            
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
            self.timed_bans = {}
            self.user_last_cmd = {}
            self.user_cmd_hits = {}
            self.user_strikes = {}
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

            self.current_snapshot = ""
            if os.path.exists(snap_file):
                try:
                    with open(snap_file, "r") as f:
                        saved_snap = f.read().strip()
                        if saved_snap: self.current_snapshot = saved_snap
                except Exception: pass

            if not self.current_snapshot:
                if getattr(self, "backend", "virtualbox") == "vmware":
                    try: snaps_found = self._vmware().list_snapshots()
                    except Exception: snaps_found = []
                else:
                    snaps_found = get_vbox_snapshots(vbox_manage_cmd, vm_name)
                if snaps_found: self.current_snapshot = snaps_found[-1]

            self.vbox = None
            self.mgr = None

            if vbox_pkg == "virtualbox":
                try: self.vbox = virtualbox.VirtualBox()
                except Exception: pass
            elif vbox_pkg == "vboxapi":
                try:
                    self.mgr = VirtualBoxManager(None, None)
                    self.vbox = self.mgr.getVirtualBox()
                except Exception: pass

            try: set_obs_scene(obs_scene_main) 
            except Exception: pass
                
            global _dbg_sink
            _dbg_sink = lambda m: self.log("[debug]", m, "sysmsg")
            try: VMwareController._ui_root = self.root
            except Exception: pass
            if DEBUG_ON:
                console_log("SYSTEM", "DEBUG MODE ON - writing to " + DEBUG_FILE + "  (use --quiet to disable)")
                dbg("startup", platform_report())
                dbg("startup", f"vbox={vbox_manage_cmd} ({_vbox_how})  vms={available_vms}")
            self.build_unified_dashboard()
            self.start_terminal_thread()
            self.start_app_threads()
            if self.twenty_four_seven_mode and self.active_url: self.go_live()
            try: self.root.after(600, self.show_welcome_guide)
            except Exception: pass
            self.root.after(refresh_rate, self.process_ui_queue)
        except Exception as e:
            err_msg = f"[error] init crashed: {e}"
            print(err_msg + f"\n{traceback.format_exc()}")
            try: messagebox.showerror("error", err_msg)
            except: pass

    def _vm_is_running(self):
        if getattr(self, "backend", "virtualbox") == "vmware":
            try: return self._vmware().is_running()
            except Exception: return False
        try:
            res = subprocess.run([vbox_manage_cmd, "list", "runningvms"], capture_output=True, text=True, timeout=4)
            return f'"{vm_name}"' in (res.stdout or "")
        except Exception:
            return False

    def check_copyright(self, url):
        try:
            cmd = ["yt-dlp", "-J", url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            data = json.loads(result.stdout)
            dur = data.get("duration", 0)
            if dur > 1200:
                return False, "Song is over 20 minutes."
            uploader = str(data.get("uploader", "")).lower()
            channel = str(data.get("channel", "")).lower()
            license_str = str(data.get("license", "")).lower()
            if "nocopyrightsounds" in uploader or "nocopyrightsounds" in channel or "creative commons" in license_str:
                return True, data.get("title", "Unknown")
            return False, "Copyright detected."
        except Exception:
            return False, "Metadata fetch failed."

    def obs_media_action(self, action):
        try:
            cl = obs.ReqClient(host=obs_host, port=obs_port, password=obs_password, timeout=3)
            try: cl.trigger_media_input_action(inputName="Media", mediaAction=action)
            except Exception:
                try: cl.trigger_media_input_action(input_name="Media", mediaAction=action)
                except Exception: cl.trigger_media_input_action("Media", action)
        except Exception: pass

    def download_music_thread(self, url, user, is_owner=False, is_mod=False, bypass=False):
        if user in getattr(self, 'banned_users', {}) and time.time() < self.banned_users[user]:
            self.log("[music]", f"{user} is banned from music.", "sysmsg")
            return
        safe, msg = self.check_copyright(url)
        if not safe and not bypass and not is_owner:
            if "20 minutes" in msg:
                self.banned_users[user] = time.time() + 172800
                self.log("[music]", f"{user} banned for 48h (Storage limit).", "sysmsg")
            else:
                self.log("[music]", f"Blocked {url} for {user}: {msg}", "sysmsg")
            return
        title = msg if safe else "Bypassed URL"
        self.log("[music]", f"Downloading {title}...", "info")
        try:
            music_dir = self.config.get("music_dir", "")
            if not music_dir:
                music_dir = "D:/Music" if (platform.system() == "Windows" and os.path.isdir("D:/")) else os.path.join(os.path.expanduser("~"), "Music")
            try: os.makedirs(music_dir, exist_ok=True)
            except Exception: pass
            out_path = os.path.join(music_dir, "%(title)s.%(ext)s")
            mp3_path = None
            try:
                dl = subprocess.run(["yt-dlp", "-x", "--audio-format", "mp3", "--no-simulate", "--print", "after_move:filepath", "-o", out_path, url], capture_output=True, text=True, timeout=600)
                if dl.returncode == 0 and dl.stdout.strip():
                    for line in reversed(dl.stdout.strip().splitlines()):
                        line = line.strip()
                        if line.lower().endswith(".mp3") and os.path.exists(line):
                            mp3_path = line
                            break
            except Exception as e:
                self.log("[music]", f"Download error: {e}", "err")
                return
            if not mp3_path:
                guess = os.path.join(music_dir, f"{title}.mp3")
                if os.path.exists(guess): mp3_path = guess
                else:
                    self.log("[music]", f"[warn] downloaded but output path not found for {title}.", "err")
                    return
            item = {"title": title, "path": mp3_path, "user": user}
            if is_owner:
                self.music_queue.insert(0, item)
                self.current_song = None
                self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")
            else:
                self.music_queue.append(item)
            log_music_action("queue", user, title, url)
        except Exception as e:
            self.log("[music]", f"Download failed: {e}", "err")

    def tick_music_engine(self):
        while self.running:
            if not getattr(self, 'current_song', None) and getattr(self, 'music_queue', []):
                self.current_song = self.music_queue.pop(0)
                try:
                    if not obs_reachable(): return
                    cl = obs.ReqClient(host=obs_host, port=obs_port, password=obs_password, timeout=3)
                    try: cl.set_input_settings(inputName="Media", inputSettings={"local_file": self.current_song["path"]})
                    except Exception:
                        try: cl.set_input_settings(input_name="Media", inputSettings={"local_file": self.current_song["path"]})
                        except Exception: cl.set_input_settings("Media", {"local_file": self.current_song["path"]})
                    self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")
                    time.sleep(1)
                    self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
                    log_music_action("play", self.current_song["user"], self.current_song["title"])
                except Exception: pass
            time.sleep(1)

    def load_settings(self):
        _be = _active_backend()
        all_vms = get_all_vbox_vms(vbox_manage_cmd, quiet=True) if _be != "vmware" else []
        default_vm = all_vms[instance_id - 1] if (all_vms and len(all_vms) >= instance_id) else (all_vms[0] if all_vms else vm_name or "Windows10ChatVm")
        default_config = {
            "youtube_url": "", "vm_name": default_vm, "vbox_path": vbox_manage_cmd, "auto_start": False,
            "enable_chat": True, "strict_live_check": True, "keyboard_layout": "US", "command_prefix": "!",
            "stats_interval": 15, "typing_speed": 0.015, "key_delay": 0.015, "mouse_delay": 0.005,
            "enable_starting_scene": True, "app_name": "YT2VM", "ultra_speed": False, "osvoting_enabled": False, "ui_theme": "original", "auto_recover": True, "snippets": [], "sound_sources": [], "backend": "virtualbox", "allow_viewer_shell": False, "protect_vm": False, "rate_limit_enabled": True, "use_customtkinter": False, "use_ttkbootstrap": True, "viewer_cooldown": 1.5, "viewer_rate_limit": 7, "max_type_len": 200, "flask_bind_lan": False, "vmx_path": "", "vnc_keymap": "us", "vmware_settle": 1.0, "vnc_host": "127.0.0.1", "auto_kill_vnc": True, "altgr_mode": "alt_r", 
            "custom_commands": {}
        }
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r") as f: default_config.update(json.load(f))
            except Exception: pass
        return default_config

    def save_settings(self):
        try:
            tmp_file = settings_file + ".tmp"
            with open(tmp_file, "w") as f: json.dump(self.config, f, indent=4)
            os.replace(tmp_file, settings_file)
        except Exception: pass

    def trigger_command(self, action_tuple):
        if self.cmd_queue.qsize() > 5000:
            self.log("[system]", "[warn] command dropped: system overloaded", "err")
            self.force_session_refresh = True
            return
        self.cmd_queue.put(action_tuple)

    def trigger_command_chain(self, action_chain):
        if self.cmd_queue.qsize() > 5000:
            self.log("[system]", "[warn] macro dropped: system overloaded", "err")
            self.force_session_refresh = True
            return
            
        def process_macro():
            for action in action_chain:
                cmd_type, arg, user = action
                if cmd_type == "wait":
                    try:
                        w_time = min(float(arg), 3600.0) 
                        if w_time > 0: time.sleep(w_time)
                    except Exception: pass
                else:
                    self.cmd_queue.put(action)
                    # let the previous action land before queueing the next one
                    if getattr(self, "backend", "virtualbox") == "vmware":
                        time.sleep(0.12)

        threading.Thread(target=process_macro, daemon=True).start()

    def clear_commands(self):
        with self.cmd_queue.mutex:
            self.cmd_queue.queue.clear()

    def on_closing(self):
        self.running = False
        save_stats()
        try:
            if hasattr(self, 'shared_session') and self.shared_session:
                try:
                    if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                    else: self.shared_session.unlockMachine()
                except Exception: pass
        except Exception: pass
        self.root.update()
        time.sleep(0.2)
        os._exit(0)

    def start_terminal_thread(self):
        def listen_terminal():
            while self.running:
                try:
                    cmd = sys.stdin.readline().strip()
                    if cmd:
                        if not cmd.startswith(self.command_prefix) and not cmd.startswith("!"):
                            cmd = self.command_prefix + cmd
                        elif cmd.startswith("!") and not cmd.startswith(self.command_prefix):
                            cmd = self.command_prefix + cmd[1:]
                        self.root.after(0, self._handle_terminal_cmd, cmd)
                except Exception:
                    time.sleep(1)
        t = threading.Thread(target=listen_terminal, daemon=True)
        t.start()

    def _handle_terminal_cmd(self, cmd):
        self.log("[console]", cmd, "user", is_mod=True, is_owner=True)
        self.parse_command(cmd, "[console]", is_mod=True, is_owner=True)

    def extract_all_msgs(self):
        try:
            if not os.path.exists(allmsglogs_file):
                messagebox.showinfo("extract", "no messages logged yet.")
                return
            save_path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="extracted_messages.txt", title="save extracted messages", filetypes=[("text files", "*.txt")])
            if not save_path: return
            count = 0
            with open(save_path, "w", encoding="utf-8") as out_f:
                with open(allmsglogs_file, "r", encoding="utf-8") as in_f:
                    for line in in_f:
                        line = line.strip()
                        if not line or line in ["[", "]"]: continue
                        try:
                            entry = json.loads(line.rstrip(","))
                            out_f.write(f"[{entry.get('time', '')}] {entry.get('username', '')}: {entry.get('message', '')}\n")
                            count += 1
                        except: pass
            self.log("[system]", f"extracted {count} messages to {save_path}", "sysmsg")
            messagebox.showinfo("success", f"extracted {count} messages!")
        except Exception as e: self.log("[system]", f"[error] extract failed: {e}", "err")

    def spawn_multistream(self, suffix_id=""):
        try:
            self.log("[system]", f"[debug] spawning multi-stream instance {suffix_id}...", "sysmsg")
            script_path = os.path.abspath(sys.argv[0])
            base_dir, base_name = os.path.dirname(script_path), os.path.basename(script_path)
            name, ext = os.path.splitext(base_name)
            multi_script_path = os.path.join(base_dir, f"{name}_multi{suffix_id}{ext}")
            try:
                shutil.copyfile(script_path, multi_script_path)
                self.log("[system]", f"[debug] copied script to {multi_script_path}", "sysmsg")
            except Exception as e:
                self.log("[system]", f"[error] failed to copy script: {e}. using original.", "err")
                multi_script_path = script_path
            args = [sys.executable, multi_script_path, f"--multistream{suffix_id}"]
            if platform.system() == "Windows": subprocess.Popen(args, creationflags=0x00000010, close_fds=True)
            else: subprocess.Popen(args, start_new_session=True, close_fds=True)
            self.log("[system]", f"[debug] successfully spawned instance {suffix_id}!", "sysmsg")
        except Exception as e:
            err_msg = f"[error] spawn_multistream crashed: {e}"
            console_log("ERROR", err_msg + f"\n{traceback.format_exc()}")
            self.log("[system]", err_msg, "err")
            messagebox.showerror("error", err_msg)

    def build_unified_dashboard(self):
        try:
            self.tabview = SidebarNav(self.root, self)
            self.tabview.pack(fill="both", expand=True)
            self.tab_dash = ttk.Frame(self.tabview, style="TFrame")
            self.tab_vbox = ttk.Frame(self.tabview, style="TFrame")
            self.tab_cmds = ttk.Frame(self.tabview, style="TFrame")
            self.tab_sett = ttk.Frame(self.tabview, style="TFrame")
            self.tab_extra = ttk.Frame(self.tabview, style="TFrame")
            self.tab_music = ttk.Frame(self.tabview, style="TFrame")
            
            self.tabview.add(self.tab_dash, text="  Dashboard  ")
            self.tabview.add(self.tab_vbox, text="  VM Config  ")
            self.tabview.add(self.tab_cmds, text="  Commands  ")
            self.tabview.add(self.tab_sett, text="  Settings  ")
            self.tabview.add(self.tab_extra, text="  Extra Things  ")
            self.tabview.add(self.tab_music, text="  Music Queue  ")

            self.tab_osvote = ttk.Frame(self.tabview, style="TFrame")
            self.tab_realpc = ttk.Frame(self.tabview, style="TFrame")
            self.tab_auto = ttk.Frame(self.tabview, style="TFrame")
            self.tab_events = ttk.Frame(self.tabview, style="TFrame")
            self.tab_appear = ttk.Frame(self.tabview, style="TFrame")
            self.tab_obs = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_osvote, text="  OS Voting  ")
            self.tabview.add(self.tab_realpc, text="  Real PC  ")
            self.tabview.add(self.tab_auto, text="  Automation  ")
            self.tabview.add(self.tab_events, text="  Event Log  ")
            self.tabview.add(self.tab_appear, text="  Appearance  ")
            self.tabview.add(self.tab_obs, text="  OBS  ")

            self.tab_keys = ttk.Frame(self.tabview, style="TFrame")
            self.tab_mouse = ttk.Frame(self.tabview, style="TFrame")
            self.tab_macros = ttk.Frame(self.tabview, style="TFrame")
            self.tab_mod = ttk.Frame(self.tabview, style="TFrame")
            self.tab_snaps = ttk.Frame(self.tabview, style="TFrame")
            self.tab_overlays = ttk.Frame(self.tabview, style="TFrame")
            self.tab_chattools = ttk.Frame(self.tabview, style="TFrame")
            self.tab_system = ttk.Frame(self.tabview, style="TFrame")
            self.tab_replay = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_keys, text="  Keys  ")
            self.tabview.add(self.tab_mouse, text="  Mouse  ")
            self.tabview.add(self.tab_macros, text="  Macros  ")
            self.tabview.add(self.tab_mod, text="  Moderation  ")
            self.tabview.add(self.tab_snaps, text="  Snapshots  ")
            self.tabview.add(self.tab_overlays, text="  Overlays  ")
            self.tabview.add(self.tab_chattools, text="  Chat Tools  ")
            self.tabview.add(self.tab_system, text="  System  ")
            self.tabview.add(self.tab_replay, text="  Replay  ")
            self.tab_media = ttk.Frame(self.tabview, style="TFrame")
            self.tab_qtype = ttk.Frame(self.tabview, style="TFrame")
            self.tab_winapps = ttk.Frame(self.tabview, style="TFrame")
            self.tab_backup = ttk.Frame(self.tabview, style="TFrame")
            self.tab_help = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_media, text="  Media  ")
            self.tabview.add(self.tab_qtype, text="  Quick Type  ")
            self.tabview.add(self.tab_winapps, text="  Win Apps  ")
            self.tabview.add(self.tab_backup, text="  Backup  ")
            self.tabview.add(self.tab_help, text="  Help  ")
            self.tab_vms = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_vms, text="  VMS  ")
            self.tab_diag = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_diag, text="  Diagnostics  ")
            
            dash_top = tk.Frame(self.tab_dash, bg="#09090B")
            dash_top.pack(side="top", fill="x", padx=24, pady=(20, 0))
            tk.Label(dash_top, text="Welcome back", bg="#09090B", fg="#FFFFFF",
                     font=("Segoe UI", 20, "bold")).pack(anchor="w")
            tiles = tk.Frame(dash_top, bg="#09090B"); tiles.pack(fill="x", pady=(14, 4))
            self._tiles = {}
            self._tile_cards = []
            for i, (name, sub) in enumerate((("Bot Status", "Chat"), ("VM", "Machine"),
                                             ("Overlay Server", "Web"), ("Real PC", "Pico"))):
                card = GlassCard(tiles, radius=14, tint="#171B29", parent_bg="#09090B", height=78)
                card.grid(row=0, column=i, sticky="we", padx=(0 if i == 0 else 10, 0))
                inner = card.body
                tk.Label(inner, text=name.upper(), bg=inner.cget("bg"), fg="#8FA0BF",
                         font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=8, pady=(6, 0))
                v = tk.Label(inner, text="Stopped", bg=inner.cget("bg"), fg="#EF4444",
                             font=("Segoe UI", 12, "bold"))
                v.pack(anchor="w", padx=8, pady=(1, 4))
                self._tiles[name] = v
                self._tile_cards.append(card)
                tiles.columnconfigure(i, weight=1, uniform="tile")
            tk.Label(dash_top, text="Quick Actions", bg="#09090B", fg="#8A8A96",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(14, 6))
            qa = tk.Frame(dash_top, bg="#09090B"); qa.pack(fill="x", pady=(0, 4))
            for lbl, col, fn in (("Start VM", "#10B981", lambda: self._vm_action("startvm")),
                                 ("Stop VM", "#EF4444", lambda: self._vm_action("shutdown")),
                                 ("Restart VM", "#F59E0B", lambda: self._vm_action("restartvm")),
                                 ("Toggle Chat", "#27272A", self.toggle_pause_chat),
                                 ("Revert Snapshot", "#8B5CF6", lambda: self._vm_action("revert")),
                                 ("Minimize", "#27272A", lambda: self._minimize_window())):
                tk.Button(qa, text=lbl, font=("Segoe UI", 9, "bold"), bg=col,
                          fg=("black" if col not in ("#27272A", "#8B5CF6", "#EF4444") else "white"),
                          bd=0, cursor="hand2", command=fn).pack(side="left", padx=(0, 8), ipady=6, ipadx=14)
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
            def quick_cmd(c, a=""): self.trigger_command((c, a, "[console]"))
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
            
            self.lbl_music_playing = tk.Label(self.tab_music, text="NO MUSIC PLAYING", bg="#09090B", fg="#B026FF", font=("Consolas", 36, "bold"))
            self.lbl_music_playing.pack(pady=40)
            self.music_listbox = tk.Listbox(self.tab_music, bg="#18181B", fg="#00E5FF", font=("Consolas", 14), bd=0, highlightthickness=0)
            self.music_listbox.pack(fill="both", expand=True, padx=40, pady=20)
            def auto_resize_music_text(event):
                w = event.width
                new_size = max(12, min(48, int(w / 22)))
                self.lbl_music_playing.config(font=("Consolas", new_size, "bold"))
            self.tab_music.bind("<Configure>", auto_resize_music_text)

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
            # ── backend switch: VirtualBox <-> VMware ──
            tk.Label(vbox_content, text="Backend", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=0, column=0, sticky="e", pady=15, padx=(0, 20))
            be_frame = tk.Frame(vbox_content, bg="#18181B"); be_frame.grid(row=0, column=1, sticky="w", pady=15)
            self._cfg_backend_lbl = tk.Label(be_frame, text=getattr(self, "backend", "virtualbox").upper(),
                                             bg="#18181B", fg=("#8B5CF6" if getattr(self,"backend","virtualbox")=="vmware" else "#10B981"),
                                             font=("Consolas", 14, "bold"))
            self._cfg_backend_lbl.pack(side="left", padx=(0, 16))
            def _set_be(name):
                self.switch_backend(name)
                self._cfg_backend_lbl.config(text=name.upper(), fg=("#8B5CF6" if name=="vmware" else "#10B981"))
                refresh_vms()
            tk.Button(be_frame, text="Use VirtualBox", font=("Segoe UI", 10, "bold"), bg="#00E5FF", fg="black",
                      bd=0, cursor="hand2", command=lambda: _set_be("virtualbox")).pack(side="left", padx=4, ipady=5, ipadx=12)
            tk.Button(be_frame, text="Switch to VMware", font=("Segoe UI", 10, "bold"), bg="#8B5CF6", fg="white",
                      bd=0, cursor="hand2", command=lambda: _set_be("vmware")).pack(side="left", padx=4, ipady=5, ipadx=12)
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
                if not current_vm or current_vm.startswith("("): return
                if getattr(self, "backend", "virtualbox") == "vmware":
                    try: snaps = self._vmware().list_snapshots()
                    except Exception: snaps = []
                else:
                    snaps = get_vbox_snapshots(self.entry_vbox_new.get().strip() or vbox_manage_cmd, current_vm)
                if not snaps:
                    self.cb_snap_new['values'] = [""]
                    self.cb_snap_new.set("")
                else:
                    self.cb_snap_new['values'] = snaps
                    if self.current_snapshot in snaps: self.cb_snap_new.set(self.current_snapshot)
                    else: self.cb_snap_new.set(snaps[-1])
            tk.Button(snap_frame, text="Refresh", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=refresh_snaps).pack(side="left", ipady=5, ipadx=15)
            def refresh_vms():
                if getattr(self, "backend", "virtualbox") == "vmware":
                    vmxs = find_vmx_files()
                    names = [os.path.splitext(os.path.basename(v))[0] for v in vmxs]
                    self._vmx_map = dict(zip(names, vmxs))
                    self.cb_vm_new['values'] = names if names else ["(no .vmx found - use VMS tab to browse)"]
                    cur = os.path.splitext(os.path.basename(self.vmx_path))[0] if getattr(self, "vmx_path", "") else ""
                    if cur in names: self.cb_vm_new.set(cur)
                    elif names: self.cb_vm_new.set(names[0])
                    refresh_snaps()
                    return
                vms = get_all_vbox_vms(self.entry_vbox_new.get().strip() or vbox_manage_cmd)
                if vms:
                    self.cb_vm_new['values'] = vms
                    current_conf = self.config.get("vm_name")
                    if current_conf in vms: self.cb_vm_new.set(current_conf)
                    else: self.cb_vm_new.set(vms[0])
                elif VBOX_LAST_ERROR:
                    self.cb_vm_new['values'] = [f"(no VMs - {VBOX_LAST_ERROR[:40]})"]
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
            if self.config.get("keyboard_layout") in available_layouts: self.cb_layout_new.set(self.config["keyboard_layout"])
            else: self.cb_layout_new.set("US")
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
            tk.Label(sett_left, text="App Name", font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=8, column=0, sticky="e", pady=10, padx=(0, 20))
            self.cb_app_name = ttk.Combobox(sett_left, values=["YT2VM", "c2vm", "ycpv", "ytpvm"], width=30, state="readonly", font=("Segoe UI", 11))
            self.cb_app_name.grid(row=8, column=1, sticky="w", pady=10)
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
            btn_save_frame = tk.Frame(sett_content, bg="#18181B")
            btn_save_frame.pack(fill="x", pady=(20, 0))
            tk.Button(btn_save_frame, text="SAVE ALL SETTINGS", font=("Segoe UI", 11, "bold"), bg=self.accent_main, fg="black", activebackground=self.accent_hover, activeforeground="black", bd=0, cursor="hand2", command=self.save_general_settings).pack(ipady=8, ipadx=40)
            self.build_extra_tab()
            self.build_osvoting_tab()
            self.build_realpc_tab()
            self.build_automation_tab()
            self.build_eventlog_tab()
            self.build_appearance_tab()
            self.build_obs_tab()
            self.build_keys_tab()
            self.build_mouse_tab()
            self.build_macros_tab()
            self.build_moderation_tab()
            self.build_snapshots_tab()
            self.build_overlays_tab()
            self.build_chattools_tab()
            self.build_system_tab()
            self.build_replay_tab()
            self.build_media_tab()
            self.build_quicktype_tab()
            self.build_winapps_tab()
            self.build_backup_tab()
            self.build_help_tab()
            self.build_vms_tab()
            self.build_diagnostics_tab()
            self._bind_tab_scroll()
            self._bind_secret_replay()
            self._add_dashboard_buttons()
            if self.config.get("accent_color"):
                try: self.apply_accent(self.config["accent_color"])
                except Exception: pass
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
                tk.Button(extra_content, text="Spawn Multi-Stream 1 (Port 5001)", font=("Segoe UI", 11, "bold"), bg="#8B5CF6", fg="white", activebackground="#7C3AED", activeforeground="white", bd=0, cursor="hand2", command=lambda: self.spawn_multistream("")).pack(anchor="w", ipady=8, ipadx=20, pady=5)
                tk.Button(extra_content, text="Spawn Multi-Stream 2 (Port 5002)", font=("Segoe UI", 11, "bold"), bg="#8B5CF6", fg="white", activebackground="#7C3AED", activeforeground="white", bd=0, cursor="hand2", command=lambda: self.spawn_multistream("2")).pack(anchor="w", ipady=8, ipadx=20, pady=5)
                tk.Button(extra_content, text="Spawn Multi-Stream 3 (Port 5003)", font=("Segoe UI", 11, "bold"), bg="#8B5CF6", fg="white", activebackground="#7C3AED", activeforeground="white", bd=0, cursor="hand2", command=lambda: self.spawn_multistream("3")).pack(anchor="w", ipady=8, ipadx=20, pady=5)
                tk.Button(extra_content, text="Spawn Multi-Stream 4 (Port 5004)", font=("Segoe UI", 11, "bold"), bg="#8B5CF6", fg="white", activebackground="#7C3AED", activeforeground="white", bd=0, cursor="hand2", command=lambda: self.spawn_multistream("4")).pack(anchor="w", ipady=8, ipadx=20, pady=5)
                tk.Button(extra_content, text="Spawn Multi-Stream 5 (Port 5005)", font=("Segoe UI", 11, "bold"), bg="#8B5CF6", fg="white", activebackground="#7C3AED", activeforeground="white", bd=0, cursor="hand2", command=lambda: self.spawn_multistream("5")).pack(anchor="w", ipady=8, ipadx=20, pady=5)
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
            help_text = ("!type (!t) <text>\n   Types raw text into the VM.\n\n!key (!k) <key>\n   Presses a single key (e.g. !k enter)\n\n!combo (!c) <key>+<key>\n   Key combo (e.g. !c win+r)\n\n!click (!lc) [count]\n   Left clicks mouse.\n\n!rclick (!rc) [count]\n   Right clicks mouse.\n\n!move (!m) <dir> <amt>\n   Moves cursor by amount.\n\n!abs <x> <y>\n   Moves cursor to exact coords.\n\n!scroll <amt>\n   Scrolls mouse wheel.\n\n!drag (!d) <dx> <dy>\n   Clicks and drags mouse.\n\n!wait (!w) <seconds>\n   Pauses the action chain.\n\n!cmd <command>\n   Runs command in admin CMD.\n\n!run <command>\n   Runs command in Win+R dialog.\n\n!startvm\n   Boots the selected VM.\n\n!restartvm\n   Force restarts the VM.\n\n!shutdown\n   Power offs the VM.\n\n!revert\n   Restores target snapshot.\n\n!roll\n   Rolls a random number 1-100.\n\n!coinflip\n   Flips heads or tails.\n")
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
        if not name.startswith(self.command_prefix): name = self.command_prefix + name
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
            if isinstance(v, dict) and "value" in v: self.macro_listbox.insert('end', f"{k} -> {v['value']}")
            elif isinstance(v, str): self.macro_listbox.insert('end', f"{k} -> {v}")

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
                if current_vm_val not in vms and vm_name in vms: self.cb_vm_new.set(vm_name)
            active_vm = self.cb_vm_new.get()
            if active_vm:
                snaps = get_vbox_snapshots(self.entry_vbox_new.get().strip() or vbox_manage_cmd, active_vm)
                self.cb_snap_new['values'] = snaps if snaps else [""]
                if self.current_snapshot not in snaps and snaps:
                    self.current_snapshot = snaps[-1]
                    self.cb_snap_new.set(self.current_snapshot)
        except Exception: pass

    def update_say_admin(self):
        self.say_admin_only = self.say_admin_var.get()

    def switch_backend(self, name):
        """Switch backend from VM Config and persist it immediately."""
        global _RUNTIME_BACKEND
        name = "vmware" if str(name).lower() == "vmware" else "virtualbox"
        self.backend = name
        self.config["backend"] = name
        _RUNTIME_BACKEND = name
        self.save_settings()
        self._teardown_com_session()
        dbg("backend", f"switched to {name}")
        self.log("[system]", f"backend is now {name.upper()}.", "sysmsg")
        try:
            if hasattr(self, "backend_lbl"):
                self.backend_lbl.config(text=name.upper(), fg=("#8B5CF6" if name == "vmware" else "#10B981"))
        except Exception: pass
        if name == "vmware":
            threading.Thread(target=lambda: self._vmware().connect(), daemon=True).start()

    def save_vbox_settings(self):
        if getattr(self, "backend", "virtualbox") == "vmware":
            try:
                chosen = self.cb_vm_new.get()
                mp = getattr(self, "_vmx_map", {})
                if chosen in mp:
                    self.vmx_path = mp[chosen]
                    self.config["vmx_path"] = self.vmx_path
                    snap = self.cb_snap_new.get().strip()
                    if snap:
                        self.config["snapshot"] = snap; self.current_snapshot = snap
                    self.save_settings()
                    self.log("[system]", f"vmware vm saved: {chosen}", "sysmsg")
                    return
            except Exception as e:
                dbg("backend", "save vmware vm failed", e)
        self.config["vm_name"] = self.cb_vm_new.get()
        self.config["vbox_path"] = self.entry_vbox_new.get()
        self.current_snapshot = self.cb_snap_new.get()
        try:
            with open(snap_file, "w") as f: f.write(self.current_snapshot)
        except Exception: pass
        self.save_settings()
        global vm_name, vbox_manage_cmd
        vm_name = self.config["vm_name"]
        vbox_manage_cmd = self.config["vbox_path"]
        self.root.title(f"{self.config.get('app_name', 'YT2VM')} {version}: {vm_name}")
        self.btn_vm.configure(text=f"target: {vm_name}")
        console_log("SYSTEM", "vm settings saved!")

    def save_general_settings(self):
        self.config["auto_start"] = self.var_auto_new.get()
        self.config["enable_chat"] = self.var_chat_new.get()
        self.config["keyboard_layout"] = self.cb_layout_new.get()
        self.config["command_prefix"] = self.entry_prefix_new.get()
        self.config["enable_starting_scene"] = self.var_starting_scene.get()
        self.config["strict_live_check"] = self.var_strict_live.get()
        self.config["app_name"] = self.cb_app_name.get()
        self.config["ultra_speed"] = self.var_ultra_speed.get()
        try: self.config["stats_interval"] = float(self.entry_stats_int.get())
        except: self.config["stats_interval"] = 15
        try: self.config["typing_speed"] = float(self.entry_type_spd.get())
        except: self.config["typing_speed"] = 0.015
        try: self.config["key_delay"] = float(self.entry_key_del.get())
        except: self.config["key_delay"] = 0.015
        try: self.config["mouse_delay"] = float(self.entry_mouse_del.get())
        except: self.config["mouse_delay"] = 0.005
        self.save_settings()
        global keyboard_layout
        keyboard_layout = self.config["keyboard_layout"]
        self.command_prefix = self.config["command_prefix"]
        self.listening_to_chat = self.config["enable_chat"]
        self.twenty_four_seven_mode = self.config["auto_start"]
        self.app_name = self.config["app_name"]
        self.ultra_speed = self.config["ultra_speed"]
        self.root.title(f"{self.app_name} {version}: {vm_name}")
        console_log("SYSTEM", "general settings & timings saved!")

    def update_gui_console(self):
        try:
            while not gui_log_queue.empty():
                level, msg = gui_log_queue.get_nowait()
                self.console_text.configure(state='normal')
                if level in ["SYSTEM", "ERROR", "EXEC", "CHAT"]: self.console_text.insert(tk.END, msg + "\n", level)
                else: self.console_text.insert(tk.END, msg + "\n")
                self.console_text.see(tk.END)
                try:
                    line_count = int(self.console_text.index('end-1c').split('.')[0])
                    if line_count > 300: self.console_text.delete('1.0', f'{line_count - 250}.0')
                except Exception: pass
                self.console_text.configure(state='disabled')
        except Exception: pass

    def update_status_display(self, text, is_error=False):
        global current_status
        if not hasattr(self, '_last_status'): self._last_status = ""
        text_lower = text.lower()
        if self._last_status != text_lower:
            self._last_status = text_lower
            current_status = text_lower
            if hasattr(self, 'lbl_status'): self.lbl_status.configure(text=text_lower.upper(), fg="#EF4444" if is_error else "#10B981")
            gui_log_queue.put_nowait(("status", text_lower))

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

    def cycle_layout(self):
        global keyboard_layout
        try:
            current_index = available_layouts.index(keyboard_layout)
            next_index = (current_index + 1) % len(available_layouts)
        except ValueError: next_index = 0
        keyboard_layout = available_layouts[next_index]

    def _advance_vm_state(self):
        """Cycle to the next VM. Works for both backends and never indexes an
        empty list (that was the 'list index out of range' crash when VMware was
        selected, because the VirtualBox VM list is empty then)."""
        global vm_name, available_vms
        if getattr(self, "backend", "virtualbox") == "vmware":
            vmxs = find_vmx_files()
            if not vmxs:
                self.log("[system]", "[warn] no .vmx files found - pick one on the VMS tab.", "sysmsg")
                return
            cur = getattr(self, "vmx_path", "")
            try: idx = (vmxs.index(cur) + 1) % len(vmxs)
            except ValueError: idx = 0
            self.vmx_path = vmxs[idx]
            self.config["vmx_path"] = self.vmx_path
            vm_name = os.path.splitext(os.path.basename(self.vmx_path))[0]
            self.config["vm_name"] = vm_name
            try:
                snaps = self._vmware().list_snapshots()
                self.current_snapshot = snaps[-1] if snaps else ""
            except Exception:
                self.current_snapshot = ""
            self.save_settings()
            self.log("[system]", f"switched to vmware vm: {vm_name}", "sysmsg")
            return
        try:
            res = subprocess.run([vbox_manage_cmd, "list", "vms"], capture_output=True, text=True, timeout=15)
            fresh_vms = [line.split('"')[1] for line in res.stdout.splitlines() if '"' in line]
            if fresh_vms: available_vms = fresh_vms
        except Exception:
            pass
        if not available_vms:
            self.log("[system]", f"[warn] no VMs available to switch to. {VBOX_LAST_ERROR}", "sysmsg")
            return
        try:
            current_index = available_vms.index(vm_name)
            next_index = (current_index + 1) % len(available_vms)
        except ValueError:
            next_index = 0
        vm_name = available_vms[next_index]
        snaps = get_vbox_snapshots(vbox_manage_cmd, vm_name)
        self.current_snapshot = snaps[-1] if snaps else ""
        self.config["vm_name"] = vm_name
        self.save_settings()
        self.log("[system]", f"switched to vm: {vm_name}", "sysmsg")

    def _update_vm_label(self):
        try:
            self.root.title(f"{self.config.get('app_name', 'YT2VM')} {version}: {vm_name}")
            if hasattr(self, 'btn_vm'): self.btn_vm.configure(text=f"target: {vm_name}")
        except Exception: pass

    def cycle_vm(self):
        self._advance_vm_state()
        self._update_vm_label()

    def go_live(self):
        try:
            url = self.entry_url.get().strip()
            if url:
                if self.active_url != url: self.yt_bot_chat_id = None
                self.active_url = url
                self.force_connect = True
                self.config["youtube_url"] = url
                self.save_settings() 
        except Exception as e:
            self.log("[system]", f"[error] go live error: {e}", "err")
            console_log("ERROR", f"[error] go live error: {e}\n{traceback.format_exc()}")

    def resolve_live_video_id(self, url):
        if not hasattr(self, 'resolved_id_cache'): self.resolved_id_cache = {}
        if url in self.resolved_id_cache: return self.resolved_id_cache[url]
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
                if not check_url.startswith("http"): check_url = "https://www.youtube.com/" + check_url.lstrip("/")
                parsed = urllib.parse.urlparse(check_url)
                if not (parsed.netloc.endswith("youtube.com") or parsed.netloc.endswith("youtu.be")): return url
                if not check_url.endswith("live"): check_url = check_url.rstrip("/") + "/live"
                req = urllib.request.Request(check_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8').lower()
                if 'consent.youtube.com' in html or 'captcha' in html: return url
                match = re.search(r'rel="canonical" href="https://www.youtube.com/watch\?v=([^"]+)"', html)
                if not match: match = re.search(r'"videoid":"([a-zA-Z0-9_-]{11})"', html)
                if not match: match = re.search(r'watch\?v=([a-zA-Z0-9_-]{11})', html)
                if match: 
                    vid = match.group(1)
                    if len(vid) == 11:
                        self.resolved_id_cache[url] = vid
                        return vid
            except Exception as e: self.log("[system]", f"[error] resolve live video error: {e}", "err")
        return url
        
    def is_video_currently_live(self, vid):
        try:
            req = urllib.request.Request(f"https://www.youtube.com/watch?v={vid}", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8').lower()
            if 'live_stream_offline' in html: return False
            return True
        except Exception: return True

    def process_vote(self, user, vote_type, target=2):
        if getattr(self, 'vm_maintenance', False):
            self.log("[system]", "[warn] vm is processing commands. votes paused.", "sysmsg")
            return
        with self.vote_lock:
            if vote_type in self.active_votes:
                vote = self.active_votes[vote_type]
                if not isinstance(vote, dict):
                    vote = {"voters": set(), "target": target, "start_time": time.time()}
                    self.active_votes[vote_type] = vote
                if target < vote["target"]: vote["target"] = target
                if user not in vote["voters"]:
                    vote["voters"].add(user)
                    current_votes = len(vote["voters"])
                    self.log("[system]", f"[vote] [alert] {vote_type.lower()} progress: {current_votes}/{vote['target']}!", "sysmsg")
                    log_vote_action("vote_progress", user, vote_type, vote['target'], current_votes)
                    if current_votes >= vote["target"]:
                        self.log("[system]", f"[vote] [success] {vote_type.lower()} passed! executing now...", "sysmsg")
                        log_vote_action("vote_passed", user, vote_type, vote['target'], current_votes)
                        clean_cmd = vote_type
                        if clean_cmd.startswith(self.command_prefix): clean_cmd = clean_cmd[len(self.command_prefix):]
                        self.active_votes.clear()
                        if clean_cmd == "skipsong" or clean_cmd == "stopsong":
                            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")
                            self.current_song = None
                        elif clean_cmd == "pausesong":
                            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
                        elif clean_cmd == "resumesong":
                            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
                        elif clean_cmd == "votereplay":
                            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")
                            time.sleep(1)
                            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
                        elif clean_cmd in ("voteshuffle", "voterandom"):
                            random.shuffle(self.music_queue)
                            self.log("[system]", "[vote] music queue shuffled.", "sysmsg")
                        elif clean_cmd == "votedrop":
                            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")
                            self.current_song = None
                            self.log("[system]", "[vote] current song dropped.", "sysmsg")
                        elif clean_cmd == "forcefixvm":
                            self.clear_commands()
                            self.trigger_command(("forcefixvm", "", "vote_passed"))
                        else: self.trigger_command((clean_cmd, "", "vote_passed"))
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
                if not cmd.startswith(self.command_prefix) and not cmd.startswith("!"): cmd = self.command_prefix + cmd
                elif cmd.startswith("!") and not cmd.startswith(self.command_prefix): cmd = self.command_prefix + cmd[1:]
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
        try:
            nav = getattr(self, "tabview", None)
            if nav is not None and hasattr(nav, "push_chat"):
                low = str(message).lower()
                t = "sys"
                if user == "[system]":
                    t = "err" if ("[err" in low or "[error" in low or "[warn" in low) else "sys"
                elif is_owner or is_mod: t = "mod"
                elif str(message).strip().startswith(self.command_prefix): t = "cmd"
                else: t = "usr"
                nav.push_chat(user, message, t)
        except Exception: pass
    
    def set_status(self, text): 
        if isinstance(text, str): self.log_queue.put(("status", text.lower()))

    def process_ui_queue(self):
        try:
            self.main_heartbeat = time.time()
            self.update_gui_console()
            uptime_sec = int(time.time() - script_start_time)
            m, s = divmod(uptime_sec, 60)
            h, m = divmod(m, 60)
            try:
                nav = getattr(self, "tabview", None)
                if nav is not None and hasattr(nav, "set_status"):
                    running = self._vm_is_running() if time.time() - getattr(self, "_lastvmchk", 0) > 3 else getattr(self, "_lastvmstate", False)
                    if time.time() - getattr(self, "_lastvmchk", 0) > 3:
                        self._lastvmchk = time.time(); self._lastvmstate = running
                    be = getattr(self, "backend", "virtualbox")
                    nav.set_status(left=f"{be}  |  {vm_name}  |  {current_viewers} viewers  |  queue {self.cmd_queue.qsize()}",
                                   right=("Running" if running else "Stopped"), running=running)
                    if hasattr(nav, "chat_dot"):
                        alive = bool(getattr(self, "listening_to_chat", False)) and bool(getattr(self, "active_url", ""))
                        nav.chat_dot.configure(text="live" if alive else "offline", fg="#10B981" if alive else "#71717A")
            except Exception: pass
            try:
                if hasattr(self, "_tiles"):
                    vmrun = getattr(self, "_lastvmstate", False)
                    chat_on = bool(getattr(self, "listening_to_chat", False)) and bool(getattr(self, "active_url", ""))
                    pico_on = bool(getattr(self, "pico_enabled", False))
                    for nm, on in (("Bot Status", chat_on), ("VM", vmrun),
                                   ("Overlay Server", bool(getattr(self, "_flask_started", False))),
                                   ("Real PC", pico_on)):
                        lb = self._tiles.get(nm)
                        if lb is not None:
                            lb.configure(text="Running" if on else "Stopped", fg="#10B981" if on else "#EF4444")
            except Exception: pass
            if hasattr(self, 'lbl_uptime_val'):
                self.lbl_uptime_val.config(text=f"{h}h {m}m {s}s")
                self.lbl_cmds_val.config(text=f"{total_commands_executed} ({total_commands_failed} failed)")
                self.lbl_viewers_val.config(text=str(current_viewers))
                self.lbl_likes_val.config(text=str(current_likes))
            
            q_hash = str([x["title"] for x in getattr(self, 'music_queue', [])])
            if q_hash != getattr(self, 'last_q_hash', ""):
                self.last_q_hash = q_hash
                self.music_listbox.delete(0, "end")
                for idx, s in enumerate(self.music_queue):
                    self.music_listbox.insert("end", f"{idx+1}. {s['title']} ({s['user']})")
            if getattr(self, 'current_song', None):
                self.lbl_music_playing.config(text=f"PLAYING: {self.current_song['title']}")
            else:
                self.lbl_music_playing.config(text="NO MUSIC PLAYING")
                
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
                    if msg_type == "status": self.update_status_display(data, "broke" in data)
                except queue.Empty: break
                except Exception: pass
            with self.vote_lock:
                now = time.time()
                to_remove = []
                for vtype, data in self.active_votes.items():
                     if now - data["start_time"] > vote_timeout: to_remove.append(vtype)
                for vtype in to_remove: del self.active_votes[vtype]
                if self.active_votes:
                     parts = []
                     for vtype, data in self.active_votes.items(): parts.append(f"{vtype.lower()}: {len(data['voters'])}/{data['target']}")
                     text = " | ".join(parts).lower()
                     current_vote_info = {"active": True, "text": f"[vote] {text}"}
                else: current_vote_info = {"active": False, "text": "no active votes"}
        except Exception: pass
        finally:
            if self.running: self.root.after(refresh_rate, self.process_ui_queue)

    def save_session_data_threadsafe(self):
        try:
            url = self.active_url if self.active_url else ""
            mode = str(self.twenty_four_seven_mode)
            layout = str(keyboard_layout)
            with open(session_file, "w") as f: f.write(f"{url}|{mode}|{layout}")
        except: pass

    def _security_gate(self, clean_user, cmd, arg):
        """Protect the VM from viewers. Returns (allowed, reason).

        Handles: per-user cooldown, spam rate-limiting with auto-timeout,
        destructive-payload blocking (obfuscation-resistant), and keeping
        shell commands admin-only unless explicitly opened up."""
        now = time.time()
        # 0) MASTER UNLOCK: it is a sandbox VM the streamer controls, so command
        #    content is unrestricted by default. This turns OFF payload blocking
        #    and the shell lockout. Spam/rate limits stay so one viewer can't
        #    flood the queue - toggle those separately with 'rate_limit_enabled'.
        unlocked = not self.config.get("protect_vm", False)
        # shell access: allowed when unlocked, or when explicitly opened
        if cmd in ("!cmd", "!run") and not unlocked and not self.config.get("allow_viewer_shell", False):
            return False, "shell commands are mod-only"
        # 2) per-user cooldown
        cd = float(self.config.get("viewer_cooldown", 1.5) or 0)
        if cd > 0 and now - self.user_last_cmd.get(clean_user, 0) < cd:
            return False, "cooldown"
        self.user_last_cmd[clean_user] = now
        # 3) rolling-window spam limit -> strike -> auto timeout
        if self.config.get("rate_limit_enabled", True):
            win = 10.0
            lim = int(self.config.get("viewer_rate_limit", 7) or 7)
            hits = [t for t in self.user_cmd_hits.get(clean_user, []) if now - t < win]
            hits.append(now)
            self.user_cmd_hits[clean_user] = hits
            if len(hits) > lim:
                n = self.user_strikes.get(clean_user, 0) + 1
                self.user_strikes[clean_user] = n
                if n >= 3:
                    self.user_strikes[clean_user] = 0
                    self.timed_bans[clean_user] = now + 300
                    self.log("[system]", f"[ban] {clean_user} auto timed out 5m (spam)", "sysmsg")
                    return False, "spam - auto timeout"
                return False, "spam"
        # 4) destructive payload / ip-grabber blocking on anything that types
        if not unlocked and cmd in ("!type", "!send", "!cmd", "!run", "!key"):
            hit = payload_is_dangerous(f"{cmd} {arg}")
            if hit:
                n = self.user_strikes.get(clean_user, 0) + 1
                self.user_strikes[clean_user] = n
                return False, f"blocked term '{hit}'"
            # 5) spelled-out attacks: track a rolling per-user typed buffer so a
            #    banned word can't be assembled one !key at a time
            if cmd == "!key" and len(str(arg).strip()) == 1:
                buf, bts = getattr(self, "_typed_buf", {}).get(clean_user, ["", 0.0])
                if now - bts > 8.0: buf = ""
                buf = (buf + str(arg).strip())[-40:]
                if not hasattr(self, "_typed_buf"): self._typed_buf = {}
                self._typed_buf[clean_user] = [buf, now]
                hit = payload_is_dangerous(buf)
                if hit:
                    self._typed_buf[clean_user] = ["", now]
                    return False, f"blocked spelled term '{hit}'"
        # 6) length cap so one message can't flood the guest (skipped when unlocked)
        # a soft cap only when protection is on...
        if not unlocked and len(str(arg)) > int(self.config.get("max_type_len", 200)):
            return False, "message too long"
        # ...but a HARD cap always, so a 50k-char paste can never wedge the box
        if len(str(arg)) > 4000:
            return False, "command too long (max 4000 chars)"
        return True, ""

    def run_diagnostics(self):
        """Check every dependency and path, and report exactly what is wrong."""
        L = []
        def add(ok, label, detail=""):
            mark = "OK  " if ok is True else ("WARN" if ok is None else "FAIL")
            L.append(f"[{mark}] {label}" + (f"  -  {detail}" if detail else ""))
        add(True, "platform", f"{platform.system()} {platform.release()}  python {platform.python_version()}")
        add(True, "app", f"{self.app_name} {version}  instance {instance_id}  backend {getattr(self,'backend','virtualbox')}")
        L.append("")
        L.append("--- dependencies ---")
        import importlib.util
        for mod, pip, why in REQUIRED_PACKAGES + OPTIONAL_PACKAGES:
            found = False
            try: found = importlib.util.find_spec(mod) is not None
            except Exception: found = False
            req = any(m == mod for m, _, _ in REQUIRED_PACKAGES)
            add(True if found else (False if req else None), f"{pip:<16}", why if found else f"missing - pip install {pip}")
        L.append("")
        L.append("--- virtualbox ---")
        path, how = resolve_vbox_path(self.config.get("vbox_path", ""))
        add(how != "not found", f"VBoxManage", f"{path}  (via {how})")
        vms = get_all_vbox_vms(path, quiet=True)
        if vms:
            add(True, "VMs found", f"{len(vms)}: " + ", ".join(vms[:6]) + (" ..." if len(vms) > 6 else ""))
        else:
            add(False, "VMs found", VBOX_LAST_ERROR or "none")
        add(bool(vm_name), "target VM", vm_name or "(none selected)")
        try:
            add(True, "VM state", self._vm_state())
        except Exception as e:
            add(None, "VM state", str(e))
        add(True, "input mode", getattr(self, "com_mode", "") or ("cli" if getattr(self, "cli_input", False) else "api"))
        L.append("")
        L.append("--- vmware ---")
        vr = find_vmrun()
        add(os.path.exists(vr), "vmrun", vr if os.path.exists(vr) else "not found - set it on the VMS page")
        add(bool(self.vmx_path), "selected .vmx", self.vmx_path or "(none)")
        _lip = get_local_ipv4()
        add(bool(_lip), "this pc's ip", _lip or "not detected")
        try:
            _vp = int(self.vnc_port)
            if vnc_port_conflict(_vp) and not self._vmware().is_running():
                add(False, "VNC port", f"{_vp} is used by ANOTHER vnc server (TightVNC?) - press 'Fix VNC port conflict'")
            else:
                add(True, "VNC port", str(_vp))
        except Exception:
            pass
        found_vmx = find_vmx_files()
        add(True if found_vmx else None, "auto-discovered VMs", f"{len(found_vmx)} found" if found_vmx else "none in default folders")
        L.append("")
        L.append("--- stream ---")
        add(bool(self.active_url), "stream url", self.active_url or "(not set)")
        add(True, "chat listener", "on" if self.listening_to_chat else "off")
        add(True, "overlay server", f"port {flask_port}" if getattr(self, "_flask_started", False) else "not started")
        add(True, "queue depth", str(self.cmd_queue.qsize()))
        add(True, "commands", f"{total_commands_executed} run / {total_commands_failed} failed")
        L.append("")
        L.append("--- recovery ---")
        add(True, "auto recover", "on" if self.config.get("auto_recover", True) else "off")
        add(True, "escalation level", str(getattr(self, "watchdog_action_level", 0)))
        add(True, "E_FAIL count", str(getattr(self, "efail_count", 0)))
        add(True, "debug logging", f"ON -> {DEBUG_FILE}" if DEBUG_ON else "off (run with --debug)")
        return "\n".join(L)

    def build_diagnostics_tab(self):
        wrap = tk.Frame(self.tab_diag, bg="#09090B"); wrap.pack(fill="both", expand=True, padx=26, pady=18)
        top = tk.Frame(wrap, bg="#09090B"); top.pack(fill="x")
        tk.Label(top, text="DIAGNOSTICS", font=("Segoe UI", 15, "bold"), bg="#09090B", fg=self.accent_main).pack(side="left")
        tk.Button(top, text="Run checks", font=("Segoe UI", 9, "bold"), bg="#10B981", fg="black",
                  bd=0, cursor="hand2", command=self._refresh_diag).pack(side="right", ipady=4, ipadx=12)
        tk.Button(top, text="Copy report", font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white",
                  bd=0, cursor="hand2", command=self._copy_diag).pack(side="right", padx=6, ipady=4, ipadx=10)
        tk.Button(top, text="Open debug log", font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white",
                  bd=0, cursor="hand2", command=self._open_debug_log).pack(side="right", padx=6, ipady=4, ipadx=10)
        tk.Label(wrap, text="Run the app with  --debug  for a full command-by-command trace.",
                 font=("Segoe UI", 9), bg="#09090B", fg="#8A8A96").pack(anchor="w", pady=(4, 8))
        self.diag_text = scrolledtext.ScrolledText(wrap, font=("Consolas", 10), bg="#0B0B10", fg="#D4D4D8",
                                                   bd=0, highlightthickness=1, highlightbackground="#27272A")
        self.diag_text.pack(fill="both", expand=True)
        self.diag_text.tag_config("ok", foreground="#10B981")
        self.diag_text.tag_config("fail", foreground="#EF4444")
        self.diag_text.tag_config("warn", foreground="#F59E0B")
        self.diag_text.tag_config("hdr", foreground=self.accent_main)
        self._refresh_diag()

    def _refresh_diag(self):
        try:
            report = self.run_diagnostics()
        except Exception as e:
            report = f"diagnostics failed: {e}\n{traceback.format_exc()}"
        self.diag_text.configure(state="normal")
        self.diag_text.delete("1.0", "end")
        for line in report.splitlines():
            tag = ()
            if line.startswith("[OK"): tag = ("ok",)
            elif line.startswith("[FAIL"): tag = ("fail",)
            elif line.startswith("[WARN"): tag = ("warn",)
            elif line.startswith("---"): tag = ("hdr",)
            self.diag_text.insert("end", line + "\n", tag)
        self.diag_text.configure(state="disabled")

    def _copy_diag(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.run_diagnostics())
            self.log("[system]", "diagnostics copied to clipboard.", "sysmsg")
        except Exception: pass

    def _open_debug_log(self):
        try:
            if not os.path.exists(DEBUG_FILE):
                self.log("[system]", f"[warn] no debug log yet - run with --debug.", "sysmsg"); return
            if platform.system() == "Windows": os.startfile(DEBUG_FILE)
            elif platform.system() == "Darwin": subprocess.Popen(["open", DEBUG_FILE])
            else: subprocess.Popen(["xdg-open", DEBUG_FILE])
        except Exception as e:
            self.log("[system]", f"[error] open debug log: {e}", "err")

    def build_vms_tab(self):
        wrap = self.make_scrollable(self.tab_vms)
        tk.Label(wrap, text="VMS  -  BACKEND & VMWARE", font=("Segoe UI", 15, "bold"),
                 bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(24, 2))
        tk.Label(wrap, text="VirtualBox is the default. Switch to VMware Workstation to drive a .vmx over VNC.",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30, pady=(0, 16))

        bcard = tk.Frame(wrap, bg="#18181B"); bcard.pack(fill="x", padx=26, pady=(0, 14))
        tk.Label(bcard, text="ACTIVE BACKEND", bg="#18181B", fg="#A1A1AA", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        self.backend_lbl = tk.Label(bcard, text=getattr(self, "backend", "virtualbox").upper(),
                                    bg="#18181B", fg="#10B981", font=("Consolas", 20, "bold"))
        self.backend_lbl.pack(anchor="w", padx=16)
        brow = tk.Frame(bcard, bg="#18181B"); brow.pack(anchor="w", padx=12, pady=(8, 16))
        tk.Button(brow, text="Use VirtualBox", font=("Segoe UI", 10, "bold"), bg="#00E5FF", fg="black", bd=0,
                  cursor="hand2", command=lambda: self.set_backend("virtualbox")).pack(side="left", padx=4, ipady=6, ipadx=14)
        tk.Button(brow, text="Switch to VMware", font=("Segoe UI", 10, "bold"), bg="#8B5CF6", fg="white", bd=0,
                  cursor="hand2", command=lambda: self.set_backend("vmware")).pack(side="left", padx=4, ipady=6, ipadx=14)

        vcard = tk.Frame(wrap, bg="#18181B"); vcard.pack(fill="x", padx=26, pady=(0, 14))
        tk.Label(vcard, text="VMWARE SETUP", bg="#18181B", fg="#A1A1AA", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        prow = tk.Frame(vcard, bg="#18181B"); prow.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(prow, text="vmrun.exe", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 10, "bold"), width=11, anchor="e").pack(side="left")
        self.vmrun_entry = tk.Entry(prow, font=("Consolas", 10), bg="#09090B", fg="white", bd=0,
                                    highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.vmrun_entry.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        self.vmrun_entry.insert(0, self.config.get("vmrun_path", self.vmrun_path))
        tk.Button(prow, text="Browse", font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white", bd=0,
                  cursor="hand2", command=self._browse_vmrun).pack(side="left", ipady=4, ipadx=10)
        nrow = tk.Frame(vcard, bg="#18181B"); nrow.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(nrow, text="VNC port", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 10, "bold"), width=11, anchor="e").pack(side="left")
        self.vnc_port_entry = tk.Entry(nrow, width=8, font=("Consolas", 10), bg="#09090B", fg="white", bd=0,
                                       highlightthickness=1, highlightbackground="#27272A")
        self.vnc_port_entry.pack(side="left", padx=8, ipady=5); self.vnc_port_entry.insert(0, str(self.vnc_port))
        tk.Label(nrow, text="password", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(12, 0))
        self.vnc_pw_entry = tk.Entry(nrow, width=14, font=("Consolas", 10), bg="#09090B", fg="white", bd=0, show="*",
                                     highlightthickness=1, highlightbackground="#27272A")
        self.vnc_pw_entry.pack(side="left", padx=8, ipady=5); self.vnc_pw_entry.insert(0, str(self.vnc_password))
        tk.Label(nrow, text="host", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(12, 0))
        self.vnc_host_entry = tk.Entry(nrow, width=14, font=("Consolas", 10), bg="#09090B", fg="white", bd=0,
                                       highlightthickness=1, highlightbackground="#27272A")
        self.vnc_host_entry.pack(side="left", padx=8, ipady=5)
        self.vnc_host_entry.insert(0, self.config.get("vnc_host", "127.0.0.1"))
        tk.Label(nrow, text="keymap", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(12, 0))
        self.vnc_keymap_cb = ttk.Combobox(nrow, values=["us", "dk"], width=6, state="readonly", font=("Segoe UI", 10))
        self.vnc_keymap_cb.pack(side="left", padx=8); self.vnc_keymap_cb.set(self.vnc_keymap)
        srow = tk.Frame(vcard, bg="#18181B"); srow.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(srow, text="key delay", bg="#18181B", fg="#D4D4D8", font=("Segoe UI", 10, "bold"), width=11, anchor="e").pack(side="left")
        self.settle_entry = tk.Entry(srow, width=6, font=("Consolas", 10), bg="#09090B", fg="white", bd=0,
                                     highlightthickness=1, highlightbackground="#27272A")
        self.settle_entry.pack(side="left", padx=8, ipady=5)
        self.settle_entry.insert(0, str(self.config.get("vmware_settle", 1.0)))
        tk.Label(srow, text="x  (1.0 = normal, raise it if commands get skipped, lower it to go faster)",
                 bg="#18181B", fg="#71717A", font=("Segoe UI", 9)).pack(side="left")
        self.detected_ip_lbl = tk.Label(vcard, text="detecting local ip...", bg="#18181B", fg="#71717A", font=("Consolas", 9))
        self.detected_ip_lbl.pack(anchor="w", padx=16, pady=(0, 6))
        def _show_ip():
            ip = get_local_ipv4(force=True)
            try:
                self.detected_ip_lbl.config(
                    text=f"this pc: {ip or 'not detected'}   (vnc is tried on 127.0.0.1 and {ip or 'lan ip'})",
                    fg=("#10B981" if ip else "#F59E0B"))
            except Exception: pass
        threading.Thread(target=_show_ip, daemon=True).start()
        tk.Button(vcard, text="Save VMware settings", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0,
                  cursor="hand2", command=self._save_vmware_settings).pack(anchor="w", padx=16, pady=(4, 16), ipady=5, ipadx=14)

        lcard = tk.Frame(wrap, bg="#18181B"); lcard.pack(fill="both", expand=True, padx=26, pady=(0, 10))
        hrow = tk.Frame(lcard, bg="#18181B"); hrow.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(hrow, text="YOUR VIRTUAL MACHINES (.vmx)", bg="#18181B", fg="#A1A1AA", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(hrow, text="Rescan", font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white", bd=0,
                  cursor="hand2", command=lambda: self._scan_vms(None)).pack(side="right", ipady=4, ipadx=10)
        self.vms_hint = tk.Label(lcard, text="", bg="#18181B", fg="#52525b", font=("Segoe UI", 9), justify="left")
        self.vms_hint.pack(anchor="w", padx=16)
        self.vms_list_frame = tk.Frame(lcard, bg="#18181B"); self.vms_list_frame.pack(fill="both", expand=True, padx=12, pady=(6, 8))
        self.vms_selected_lbl = tk.Label(lcard, text="selected: (none)", bg="#18181B", fg="#00E5FF", font=("Consolas", 10))
        self.vms_selected_lbl.pack(anchor="w", padx=16, pady=(0, 6))
        tk.Button(lcard, text="This is not my VM folder  -  browse manually...", font=("Segoe UI", 10, "bold"),
                  bg="#F59E0B", fg="black", bd=0, cursor="hand2",
                  command=self._browse_vm_folder).pack(fill="x", padx=16, pady=(0, 14), ipady=7)

        ccard = tk.Frame(wrap, bg="#18181B"); ccard.pack(fill="x", padx=26, pady=(0, 24))
        tk.Label(ccard, text="VMWARE CONTROLS", bg="#18181B", fg="#A1A1AA", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(14, 6))
        self._grid_buttons(ccard, [
            ("Start VM", "#10B981", lambda: self._vmw_action("start")),
            ("Stop VM", "#EF4444", lambda: self._vmw_action("stop")),
            ("Reset VM", "#F59E0B", lambda: self._vmw_action("reset")),
            ("Suspend", "#27272A", lambda: self._vmw_action("suspend")),
            ("Connect VNC", "#8B5CF6", lambda: self._vmw_action("connect")),
            ("Enable VNC in .vmx", "#00E5FF", lambda: self._vmw_action("vnc_setup")),
            ("TEST VNC INPUT", "#F59E0B", lambda: self._vmw_action("test")),
            ("Remove VNC password", "#EF4444", lambda: self._vmw_action("clear_pw")),
            ("Forget saved VNC passwords", "#27272A", lambda: self._vmw_action("forget_pw")),
            ("Fix VNC port conflict", "#F59E0B", lambda: self._vmw_action("fix_port")),
            ("Kill TightVNC / host VNC", "#EF4444", lambda: self._vmw_action("kill_vnc")),
        ], cols=3).pack(fill="x", padx=12, pady=(0, 8))
        self.vmw_status = tk.Label(ccard, text="status: idle", bg="#18181B", fg="#A1A1AA", font=("Consolas", 10))
        self.vmw_status.pack(anchor="w", padx=16, pady=(0, 4))
        self.vnc_live = tk.Label(ccard, text="VNC INPUT: unknown", bg="#18181B", fg="#71717A", font=("Consolas", 11, "bold"))
        self.vnc_live.pack(anchor="w", padx=16, pady=(0, 16))
        self._vnc_tick()
        self._scan_vms(None)

    def _vnc_tick(self):
        """Show at a glance whether keystrokes can actually reach the guest."""
        try:
            if getattr(self, "backend", "virtualbox") != "vmware":
                self.vnc_live.config(text="VNC INPUT: n/a (backend is virtualbox)", fg="#71717A")
            else:
                vm = self._vmware()
                if vm.client is not None and (time.time() - getattr(vm, "_last_ok", 0)) < 60:
                    self.vnc_live.config(text=f"VNC INPUT: CONNECTED  ({vm.host}:{vm.port})", fg="#10B981")
                elif VMwareController._port_open(vm.host, vm.port, 0.4):
                    try: running = vm.is_running()
                    except Exception: running = True
                    if not running:
                        self.vnc_live.config(
                            text=f"VNC INPUT: PORT {vm.port} TAKEN BY ANOTHER VNC SERVER (TightVNC?) <- press 'Fix VNC port conflict'",
                            fg="#EF4444")
                    else:
                        self.vnc_live.config(text=f"VNC INPUT: port open, not connected yet  ({vm.host}:{vm.port})", fg="#F59E0B")
                else:
                    self.vnc_live.config(text=f"VNC INPUT: NO SERVER on {vm.host}:{vm.port}  <- enable VNC in .vmx while VM is OFF", fg="#EF4444")
        except Exception:
            pass
        if self.running:
            try: self.root.after(3000, self._vnc_tick)
            except Exception: pass

    def _vmware(self):
        if self.vmware is None:
            self.vmware = VMwareController(
                vmrun_path=self.config.get("vmrun_path", self.vmrun_path),
                vmx=self.vmx_path, port=self.vnc_port,
                host=self.config.get("vnc_host", "127.0.0.1"),
                password=self.vnc_password, keymap=self.vnc_keymap)
            self.vmware.auto_kill_squatters = bool(self.config.get("auto_kill_vnc", True))
        try:
            self.vmware.guest_layout = str(self.config.get("keyboard_layout", keyboard_layout) or "US").upper()
        except Exception: pass
        else:
            self.vmware.vmx = self.vmx_path
            self.vmware.vmrun_path = self.config.get("vmrun_path", self.vmrun_path)
            self.vmware.port = int(self.vnc_port)
            self.vmware.host = self.config.get("vnc_host", self.vmware.host or "127.0.0.1")
            self.vmware.auto_kill_squatters = bool(self.config.get("auto_kill_vnc", True))
            self.vmware.password = self.vnc_password
            self.vmware.keymap = self.vnc_keymap
        # the guest's real keyboard layout drives character translation, and it
        # must be refreshed on BOTH paths (new controller and reused one)
        try:
            self.vmware.guest_layout = str(self.config.get("keyboard_layout", keyboard_layout) or "US").upper()
            self.vmware.cfg = self.config
        except Exception:
            self.vmware.guest_layout = "US"
        return self.vmware

    def set_backend(self, name):
        name = "vmware" if str(name).lower() == "vmware" else "virtualbox"
        if name == "vmware" and not self.vmx_path:
            self.vmw_status.config(text="status: pick a .vmx below first", fg="#F59E0B")
            return
        dbg("backend", f"switching to {name} (vmx={self.vmx_path!r})")
        self.backend = name
        self.config["backend"] = name
        self.save_settings()
        self.backend_lbl.config(text=name.upper(), fg=("#8B5CF6" if name == "vmware" else "#10B981"))
        self._teardown_com_session()
        if name == "vmware":
            threading.Thread(target=lambda: self._vmware().connect(), daemon=True).start()
        self.log("[system]", f"backend switched to {name}.", "sysmsg")

    def _browse_vmrun(self):
        fp = filedialog.askopenfilename(title="select vmrun.exe", filetypes=[("vmrun", "vmrun.exe"), ("executable", "*.exe")])
        if fp:
            self.vmrun_entry.delete(0, "end"); self.vmrun_entry.insert(0, fp)
            self.config["vmrun_path"] = fp; self.save_settings()

    def _save_vmware_settings(self):
        self.config["vmrun_path"] = self.vmrun_entry.get().strip()
        self.vmrun_path = self.config["vmrun_path"]
        try: self.vnc_port = int(self.vnc_port_entry.get().strip() or 5900)
        except Exception: self.vnc_port = 5900
        self.vnc_password = self.vnc_pw_entry.get()
        self.vnc_keymap = self.vnc_keymap_cb.get() or "us"
        try:
            self.config["vnc_host"] = self.vnc_host_entry.get().strip() or "127.0.0.1"
            self.vnc_host = self.config["vnc_host"]
        except Exception: pass
        try: self.config["vmware_settle"] = max(0.0, min(float(self.settle_entry.get().strip() or 1.0), 5.0))
        except Exception: self.config["vmware_settle"] = 1.0
        self.config["vnc_port"] = self.vnc_port
        self.config["vnc_password"] = self.vnc_password
        self.config["vnc_keymap"] = self.vnc_keymap
        self.save_settings()
        self.vmw_status.config(text="status: settings saved", fg="#10B981")

    def _scan_vms(self, root):
        for w in self.vms_list_frame.winfo_children(): w.destroy()
        found = find_vmx_files(root)
        if root:
            self.vms_hint.config(text=f"scanned: {root}")
        else:
            _where = "Documents\\Virtual Machines" if platform.system() == "Windows" else ("~/Virtual Machines.localized" if platform.system() == "Darwin" else "~/vmware and ~/Documents")
            self.vms_hint.config(text=f"scanned VMware's default location ({_where})")
        if not found:
            tk.Label(self.vms_list_frame, text="No .vmx files found here.\nUse the orange button below to pick your VM folder.",
                     bg="#18181B", fg="#EF4444", font=("Segoe UI", 10), justify="left").pack(anchor="w", padx=6, pady=8)
            return
        for path in found[:40]:
            name = os.path.splitext(os.path.basename(path))[0]
            row = tk.Frame(self.vms_list_frame, bg="#09090B"); row.pack(fill="x", pady=2)
            sel = (os.path.normcase(path) == os.path.normcase(self.vmx_path or ""))
            tk.Label(row, text=("*  " if sel else "   ") + name, bg="#09090B",
                     fg=(self.accent_main if sel else "#D4D4D8"), font=("Consolas", 11)).pack(side="left", padx=10, pady=6)
            tk.Label(row, text=os.path.dirname(path), bg="#09090B", fg="#52525b", font=("Segoe UI", 8)).pack(side="left", padx=6)
            tk.Button(row, text="Select", font=("Segoe UI", 9, "bold"), bg="#8B5CF6", fg="white", bd=0, cursor="hand2",
                      command=lambda p=path: self._select_vmx(p)).pack(side="right", padx=8, pady=4, ipadx=8)

    def _select_vmx(self, path):
        self.vmx_path = path
        self.config["vmx_path"] = path
        self.save_settings()
        self.vms_selected_lbl.config(text=f"selected: {os.path.basename(path)}")
        self.vmw_status.config(text="status: vm selected - hit 'Enable VNC in .vmx' while it is powered off", fg="#00E5FF")
        self._scan_vms(None)

    def _browse_vm_folder(self):
        folder = filedialog.askdirectory(title="select the folder that holds your VMware VMs")
        if folder:
            self.config["vm_folder"] = folder; self.save_settings()
            self._scan_vms(folder)

    def _vmw_action(self, action):
        vm = self._vmware()
        if not self.vmx_path:
            self.vmw_status.config(text="status: no .vmx selected", fg="#EF4444"); return
        if not vm.available():
            self.vmw_status.config(text="status: vmrun.exe not found - set the path above", fg="#EF4444"); return
        def _go():
            try:
                if action == "start":
                    ok = vm.start()
                    msg = "vm started" if ok else "start failed (check vmrun path / .vmx)"
                elif action == "stop":
                    vm.stop(); msg = "stop sent"
                elif action == "reset":
                    vm.reset(); msg = "reset sent"
                elif action == "suspend":
                    vm.suspend(); msg = "suspend sent"
                elif action == "kill_vnc":
                    killed = kill_vnc_squatters("manual")
                    msg = (f"stopped: {', '.join(killed)}" if killed
                           else "no host VNC server was running (nothing to stop)")
                elif action == "fix_port":
                    if vm.is_running():
                        msg = "power the VM OFF first, then press this again"
                    else:
                        hit, why = vm.resolve_port_conflict(auto=True)
                        if hit:
                            self.vnc_port = vm.port
                            self.config["vnc_port"] = vm.port
                            self.save_settings()
                            try:
                                self.vnc_port_entry.delete(0, "end")
                                self.vnc_port_entry.insert(0, str(vm.port))
                            except Exception: pass
                            vm.ensure_vnc_in_vmx()
                            msg = why + " - .vmx updated, start the VM now"
                        else:
                            msg = f"no conflict: port {vm.port} is free for this VM"
                elif action == "forget_pw":
                    try:
                        if os.path.exists(VNC_PASS_FILE): os.remove(VNC_PASS_FILE)
                        msg = f"cleared {VNC_PASS_FILE}"
                    except Exception as e:
                        msg = f"could not clear: {e}"
                elif action == "clear_pw":
                    vm.password = ""
                    self.vnc_password = ""
                    self.config["vnc_password"] = ""
                    self.save_settings()
                    try: self.vnc_pw_entry.delete(0, "end")
                    except Exception: pass
                    if vm.is_running():
                        msg = "power the VM OFF first - the .vmx cannot be edited while it runs"
                    else:
                        vm.ensure_vnc_in_vmx()
                        msg = "vnc password removed from the .vmx - start the VM and test again"
                elif action == "vnc_setup":
                    ok = vm.ensure_vnc_in_vmx()
                    msg = f"vnc enabled in .vmx (port {vm.port}, keymap {vm.keymap})" if ok else "could not edit .vmx"
                elif action == "connect":
                    ok = vm.connect(); msg = vm.status
                elif action == "test":
                    ok, msg = vm.test_connection()
                    info = vm.read_vmx_vnc()
                    self.log("[system]", f"[vmx] enabled={info.get('enabled')} port={info.get('port')} "
                                          f"keymap={info.get('keymap')} password={'SET' if (info.get('password') or info.get('key')) else 'none'}", "sysmsg")
                    self.log("[system]", ("[vnc ok] " if ok else "[vnc fail] ") + msg, "sysmsg" if ok else "err")
                else:
                    msg = "unknown action"
                self.root.after(0, lambda: self.vmw_status.config(text=f"status: {msg}", fg="#10B981" if "fail" not in msg and "could not" not in msg else "#EF4444"))
            except Exception as e:
                self.root.after(0, lambda: self.vmw_status.config(text=f"status: {e}", fg="#EF4444"))
        threading.Thread(target=_go, daemon=True).start()

    def _handle_mod_command(self, cmd, arg, user, is_owner):
        """Mod/owner-only commands. Returns True if the command was handled.
        These are extra perks for the mod team - flashes, OBS scenes, VM control,
        bans/timeouts, and a few fun party effects. All gated to admins."""
        a = arg.strip()
        toks = a.split()
        target = toks[0].replace("@", "").lower().strip() if toks else ""
        rest = " ".join(toks[1:]).strip()
        def flash(t, k="info", d=6): self.send_flash(t, k, d)

        # ---- bans / timeouts ----
        if cmd == "!ban":
            if target:
                self.blacklisted_users.add(target)
                self.timed_bans.pop(target, None)
                flash(f"{target} was banned", "err", 6)
                self.log("[system]", f"[ban] {target} banned by {user}", "sysmsg")
            return True
        if cmd in ("!unban", "!unmute", "!pardon"):
            if target:
                self.blacklisted_users.discard(target)
                self.timed_bans.pop(target, None)
                flash(f"{target} was unbanned", "good", 5)
                self.log("[system]", f"[ban] {target} unbanned by {user}", "sysmsg")
            return True
        if cmd in ("!timeout", "!mute"):
            mins = 5.0
            if len(toks) > 1:
                try: mins = max(0.1, float(toks[1]))
                except Exception: mins = 5.0
            if target:
                self.timed_bans[target] = time.time() + mins * 60
                flash(f"{target} timed out {int(mins)}m", "warn", 6)
                self.log("[system]", f"[ban] {target} timed out {mins}m by {user}", "sysmsg")
            return True
        if cmd == "!blacklist":
            if target: self.blacklisted_users.add(target)
            return True
        if cmd == "!bans":
            n = len(self.blacklisted_users) + len(self.timed_bans)
            flash(f"{n} users banned/timed out", "info", 5)
            return True
        if cmd == "!warn":
            who = "@" + target if target else "chat"
            flash(f"{who}: {rest or 'behave!'}", "warn", 7)
            return True

        # ---- OBS / overlay ----
        if cmd == "!scene":
            if a:
                set_obs_scene(a)
                self.log("[system]", f"scene -> {a}", "sysmsg")
            return True
        if cmd == "!shout":
            if a: flash(a.upper(), "warn", 8)
            return True
        if cmd == "!alert":
            if a: flash(a, "err", 8)
            return True
        if cmd == "!pin":
            if a: flash(a, "info", 20)
            return True
        if cmd == "!announce":
            if a: self.log("[announcement]", a, "sysmsg")
            return True
        if cmd == "!nuke":
            with history_lock: web_chat_history.clear()
            flash("CHAT NUKED", "err", 5)
            return True

        # ---- useful mod utilities ----
        if cmd == "!whois":
            if target:
                banned = target in self.blacklisted_users
                t_left = int(max(0, self.timed_bans.get(target, 0) - time.time()))
                strikes = self.user_strikes.get(target, 0)
                info = f"{target}: {'BANNED' if banned else ('timeout ' + str(t_left) + 's' if t_left else 'ok')}, {strikes} strikes"
                flash(info, "info", 8)
                self.log("[system]", info, "sysmsg")
            return True
        if cmd == "!cooldown":
            try:
                v = max(0.0, float(target))
                self.config["viewer_cooldown"] = v; self.save_settings()
                flash(f"cooldown set to {v}s", "info", 5)
            except Exception: pass
            return True
        if cmd == "!slowmode":
            try:
                v = max(0.0, float(target)) if target else 5.0
                self.config["viewer_cooldown"] = v; self.save_settings()
                flash(f"slowmode {v}s", "warn", 6)
            except Exception: pass
            return True
        if cmd == "!queue":
            n = len(getattr(self, "music_queue", []))
            cur = (self.current_song or {}).get("title", "nothing")
            flash(f"playing: {cur} | {n} queued", "info", 7)
            return True
        if cmd == "!purge":
            self.clear_commands()
            flash("command queue purged", "warn", 5)
            return True
        if cmd == "!strikes":
            if target:
                self.user_strikes.pop(target, None)
                self.timed_bans.pop(target, None)
                flash(f"cleared strikes for {target}", "good", 5)
            return True
        if cmd == "!blockword":
            if a:
                DANGEROUS_PAYLOAD.append(a.lower())
                flash(f"blocked '{a}'", "warn", 5)
            return True
        if cmd in ("!unlock all", "!unlockall", "!protect"):
            if cmd == "!protect":
                self.config["protect_vm"] = not self.config.get("protect_vm", False)
            else:
                self.config["protect_vm"] = False
            self.save_settings()
            st = "PROTECTED (dangerous cmds blocked)" if self.config.get("protect_vm") else "UNLOCKED (everything allowed)"
            flash(f"VM is now {st}", "warn", 7)
            self.log("[system]", f"vm protection -> {st}", "sysmsg")
            return True
        if cmd in ("!killvnc", "!killtightvnc"):
            k = kill_vnc_squatters("mod command")
            flash(f"stopped host vnc: {', '.join(k)}" if k else "no host vnc running", "warn", 6)
            return True
        if cmd == "!altgr":
            mode = (target or "").lower()
            if mode not in ("alt_r", "ctrl_alt", "numpad"):
                flash(f"altgr mode is {self.config.get('altgr_mode','alt_r')} (alt_r / ctrl_alt / numpad)", "info", 8)
                return True
            self.config["altgr_mode"] = mode; self.save_settings()
            flash(f"altgr mode -> {mode}", "info", 6)
            return True
        if cmd == "!settle":
            try:
                v = max(0.0, min(float(target), 5.0))
                self.config["vmware_settle"] = v; self.save_settings()
                flash(f"vmware key delay {v}x", "info", 5)
            except Exception:
                flash(f"key delay is {self.config.get('vmware_settle', 1.0)}x", "info", 5)
            return True
        if cmd == "!ratelimit":
            self.config["rate_limit_enabled"] = not self.config.get("rate_limit_enabled", True)
            self.save_settings()
            flash(f"rate limit {'ON' if self.config['rate_limit_enabled'] else 'OFF'}", "info", 5)
            return True
        if cmd == "!allowshell":
            self.config["allow_viewer_shell"] = not self.config.get("allow_viewer_shell", False)
            self.save_settings()
            st = "ON (risky)" if self.config["allow_viewer_shell"] else "OFF"
            flash(f"viewer shell access {st}", "warn", 7)
            return True
        if cmd == "!vmswitch":
            if a:
                threading.Thread(target=lambda: self.switch_to_vm(a), daemon=True).start()
            return True
        if cmd == "!backend":
            flash(f"backend: {getattr(self, 'backend', 'virtualbox')}", "info", 5)
            return True
        if cmd == "!modhelp":
            flash("mod cmds: ban/timeout/whois/slowmode/purge/scene/flash/lockdown/vmstatus/snapshotnow", "info", 12)
            return True

        # ---- vm / system ----
        if cmd == "!skip":
            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")
            self.current_song = None
            flash("song skipped", "info", 4); return True
        if cmd in ("!killsvc", "!killglobal"):
            threading.Thread(target=self._kill_vbox_global, daemon=True).start()
            flash("restarting vbox interface", "warn", 5); return True
        if cmd in ("!closedialog", "!dismiss"):
            threading.Thread(target=self._dismiss_crash_dialogs, daemon=True).start()
            flash("closing crash dialogs", "warn", 4); return True
        if cmd == "!kill":
            threading.Thread(target=self._kill_vbox_tasks, daemon=True).start()
            self.log("[system]", "vbox tasks killed.", "sysmsg"); return True
        if cmd == "!rebuild":
            self.force_session_refresh = True
            self.log("[system]", "com rebuild queued.", "sysmsg"); return True
        if cmd == "!vmstatus":
            flash("VM: " + ("running" if self._vm_is_running() else "stopped"), "info", 5); return True
        if cmd == "!stats":
            flash(f"{current_viewers} viewers | {total_commands_executed} cmds run", "info", 6); return True
        if cmd == "!lockdown":
            self.chat_paused = True
            flash("LOCKDOWN - mods only", "warn", 6); return True
        if cmd == "!unlock":
            self.chat_paused = False
            flash("chat open again", "good", 5); return True
        if cmd == "!snapshotnow":
            self.trigger_command(("makesnapshot", "", "[console]"))
            flash("snapshot taken", "good", 4); return True
        if cmd == "!revertnow":
            self.trigger_command(("revert", "", "[console]"))
            flash("reverting VM", "warn", 5); return True
        if cmd == "!restartnow":
            self.trigger_command(("restartvm", "", "[console]"))
            flash("restarting VM", "warn", 5); return True
        if cmd == "!clearvotes":
            with self.vote_lock: self.active_votes.clear()
            flash("votes cleared", "info", 4); return True
        if cmd == "!title":
            if a:
                try: self.root.title(f"{self.app_name} {version}: {vm_name} - {a}")
                except Exception: pass
                self.log("[announcement]", a, "sysmsg")
            return True

        return False

    def parse_command(self, msg, user, is_mod=False, is_owner=False):
        global total_commands_executed
        self.last_command_time = time.time()
        if not msg.startswith(self.command_prefix): return
        first_word = msg.split()[0].lower()
        if first_word in self.custom_commands:
            macro_chain = self.custom_commands[first_word]
            self.parse_command(macro_chain.get("value", macro_chain) if isinstance(macro_chain, dict) else macro_chain, user, is_mod, is_owner)
            return
        clean_user = user.replace("@", "").lower().strip()
        if clean_user in self.blacklisted_users: return 
        if clean_user in getattr(self, 'timed_bans', {}):
            if time.time() < self.timed_bans[clean_user]: return
            else: del self.timed_bans[clean_user]
        for t in self.blocked_terms:
            if t in msg.lower(): return
        cmds = []
        if '|' in msg: cmds = msg.split('|')
        else:
            tokens = msg.split()
            curr = []
            for t in tokens:
                if t.startswith(self.command_prefix):
                    if curr: cmds.append(" ".join(curr))
                    curr = [t]
                else: curr.append(t)
            if curr: cmds.append(" ".join(curr))
        action_chain = []
        for c in cmds:
            parts = c.strip().split(maxsplit=1)
            if not parts: continue
            raw_cmd = parts[0].lower()
            if not raw_cmd.startswith(self.command_prefix): continue
            cmd = "!" + raw_cmd[len(self.command_prefix):]
            aliases = {"!c": "!combo", "!k": "!key", "!t": "!type", "!s": "!send", "!m": "!move", "!d": "!drag", "!w": "!wait", "!kd": "!keydown", "!ku": "!keyup", "!lc": "!click", "!rc": "!rclick"}
            if cmd in aliases: cmd = aliases[cmd]
            arg = parts[1].strip() if len(parts) > 1 else ""
            total_commands_executed += 1
            if clean_user in owners or clean_user == "reallyiron": is_owner = True
            is_admin = is_owner or is_mod or user == "[console]" or user == "[CONSOLE]" or clean_user in admins
            if is_admin and self._handle_mod_command(cmd, arg, user, is_owner):
                continue
            
            music_votes = {
                "!skipsong": 4, "!pausesong": 3, "!stopsong": 2, 
                "!resumesong": 3, "!voteshuffle": 4, "!votereplay": 3, 
                "!votedrop": 4, "!voterandom": 3
            }
            if cmd in music_votes:
                if is_owner or is_mod:
                    with self.vote_lock:
                        self.active_votes[cmd] = {"voters": {f"FORCE_{i}" for i in range(max(0, music_votes[cmd] - 1))}, "target": music_votes[cmd], "start_time": time.time()}
                self.process_vote(user, cmd, music_votes[cmd])
                continue

            if cmd == "!music" and arg:
                arg_parts = arg.split()
                url = arg_parts[0]
                bypass = len(arg_parts) > 1 and arg_parts[-1].lower() == "true" and is_mod
                threading.Thread(target=self.download_music_thread, args=(url, user, is_owner, is_mod, bypass), daemon=True).start()
                continue
                
            if cmd == "!testanticopyright" and is_owner and arg:
                safe, res_msg = self.check_copyright(arg.split()[0])
                self.log("[system]", f"Test Result: Safe={safe}, Msg={res_msg}", "sysmsg")
                continue
                
            if cmd in ["!volumeup", "!volumedown"]:
                if is_mod and arg.isdigit():
                    self.trigger_command((cmd, arg, user))
                continue
                
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
            if cmd == "!enablecv":
                 if is_owner: self.changevm_enabled = True
                 continue
            if cmd in self.disabled_commands and not is_admin: continue
            if not is_admin:
                _allow, _why = self._security_gate(clean_user, cmd, arg)
                if not _allow:
                    dbg("security", f"blocked {clean_user}: {cmd} -> {_why}")
                    if _why and not _why.startswith("cooldown"):
                        self.log("[system]", f"[warn] blocked {clean_user}: {_why}", "sysmsg")
                    continue
            if cmd == "!changevm" and not is_admin:
                if getattr(self, "osvoting_enabled", False) and self.changevm_enabled:
                    self.process_vote(user, f"{self.command_prefix}changevm", 3)
                continue
            if cmd in ["!votestop", "!clear", "!changevm", "!switchsnapshot", "!swichsnapshot", "!say", "!fixvm", "!forcefixvm", "!shutdown", "!remake2", "!makesnapshot", "!fixscript"]:
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
                        subprocess.Popen(args)
                        os._exit(0)
                else:
                    if cmd == "!forcefixvm": self.process_vote(user, f"{self.command_prefix}forcefixvm", 2)
                continue
            if cmd == "!restartvm":
                if is_admin: action_chain.append(("restartvm", "", user))
                else: self.process_vote(user, f"{self.command_prefix}restartvm", 2)
                continue
            if cmd == "!flash":
                if is_admin and arg:
                    self.send_flash(arg)
                continue
            if cmd == "!replay":
                if is_owner:
                    self.start_replay()
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
        if action_chain: self.trigger_command_chain(action_chain)

    def chat_listener_loop(self, thread_id=0):
        if not pytchat_available:
            while self.running and getattr(self, 'listener_id', 0) == thread_id: time.sleep(1)
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
                            dbg("chat", f"resolving {target_url!r}")
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
                                        else: self.log("[system]", "successfully connected to yt chat", "sysmsg")
                                else:
                                     time.sleep(retry_delay)
                                     retry_delay = min(retry_delay * 2, 60) 
                                     if is_connected:
                                         self.log("[system]", "disconnected from yt connecting to stream", "sysmsg")
                                         is_connected = False
                        except Exception as parse_err:
                            err_msg = str(parse_err)
                            _low = err_msg.lower()
                            _transient = any(k in _low for k in (
                                "timed out", "timeout", "readtimeout", "connecttimeout", "writetimeout",
                                "read operation", "connection", "temporarily", "remotedisconnected",
                                "remote_disconnected", "goaway", "reset by peer", "econnreset",
                                "429", "500", "502", "503", "504", "handshake", "eof occurred"))
                            if _transient:
                                if getattr(self, "_last_chat_warn", 0) != int(retry_delay) or time.time() - getattr(self, "_last_chat_warn_t", 0) > 15:
                                    self._last_chat_warn = int(retry_delay)
                                    self._last_chat_warn_t = time.time()
                                    self.log("[system]", f"[warn] youtube chat unreachable (timeout). retrying in {retry_delay}s...", "sysmsg")
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
                    if chat == "[DEBUG_MODE]": pass
                    elif chat and chat.is_alive():
                        if retry_delay > 2: retry_delay = 2
                        if time.time() - chat_start_time > 21600:
                            if hasattr(self, 'resolved_id_cache'): self.resolved_id_cache.clear()
                            if hasattr(chat, 'terminate'):
                                try: chat.terminate()
                                except: pass
                            chat = None
                            connected_url = None
                            chat_start_time = time.time()
                            self.last_msg_time = time.time()
                            continue
                        try: chat_data = chat.get()
                        except Exception:
                            chat_data = None
                            time.sleep(1)
                        if chat_data:
                            error_count = 0
                            if is_first_fetch:
                                is_first_fetch = False
                                for c in chat_data.items:
                                    if hasattr(c, 'id'): self.processed_msg_ids.add(c.id)
                                continue
                            new_items = [c for c in chat_data.items if hasattr(c, 'id') and c.id not in self.processed_msg_ids]
                            for c in new_items:
                                self.last_msg_time = time.time()
                                self.processed_msg_ids.add(c.id)
                                if not self.listening_to_chat: continue 
                                msg_lower = c.message.lower().strip()
                                clean_name = c.author.name.replace("@", "").lower().strip()
                                if clean_name == "nightbot": continue
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
                                            subprocess.run(["taskkill", "/F", "/FI", f"WINDOWTITLE eq *{vm_name}*",
                                                            "/IM", "VirtualBoxVM.exe", "/T"],
                                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                        self.clear_commands()
                                        self.trigger_command(("!startvm", "", c.author.name))
                                    else: self.process_vote(c.author.name, f"{self.command_prefix}forcefixvm", 2)
                                    continue
                                add_to_history(c.author.name, c.message, "user", is_mod, is_owner)
                                try: self.replay_buffer.append({"t": time.time(), "u": c.author.name, "m": c.message, "mod": is_mod, "owner": is_owner})
                                except Exception: pass
                                console_log("CHAT", f"[{c.author.name}]: {c.message}")
                                append_to_all_msgs_log(c.author.name, c.message)
                                if self.listening_to_chat:
                                    try: self.parse_command(c.message, c.author.name, is_mod, is_owner)
                                    except Exception as parse_ex:
                                        console_log("ERROR", f"parse_command error: {parse_ex}\n{traceback.format_exc()}")
                    elif chat is not None and chat != "[DEBUG_MODE]":
                        if is_connected:
                            self.log("[system]", "disconnected from yt connecting to stream", "sysmsg")
                            is_connected = False
                        if hasattr(chat, 'terminate'):
                            try: chat.terminate()
                            except: pass
                        chat = None
                        connected_url = None
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 60)
                except Exception as loop_err:
                    error_count += 1
                    console_log("ERROR", f"chat loop error: {loop_err}")
                    if error_count > 10:
                        chat = None
                        connected_url = None
                        error_count = 0
                    time.sleep(1)
            except Exception as outer_err:
                console_log("ERROR", f"listener outer error: {outer_err}\n{traceback.format_exc()}")
                time.sleep(2)
            time.sleep(0.5)

    def _dismiss_crash_dialogs_linux(self):
        """Linux/macOS equivalent: find an error window with wmctrl or xdotool,
        send Return (activates the default OK button), wait 2s, then kill the
        owning process if it is still up. Silently does nothing if neither tool
        is installed (pacman -S wmctrl xdotool)."""
        pats = ("error", "critical", "guru meditation", "not responding", "failed")
        def list_windows():
            out = []
            if shutil.which("wmctrl"):
                try:
                    r = subprocess.run(["wmctrl", "-l", "-p"], capture_output=True, text=True, timeout=8)
                    for ln in (r.stdout or "").splitlines():
                        parts = ln.split(None, 4)
                        if len(parts) >= 5:
                            wid, pid, title = parts[0], parts[2], parts[4]
                            t = title.lower()
                            if ("virtualbox" in t or "vbox" in t) and any(pp in t for pp in pats):
                                out.append((wid, pid, title))
                except Exception: pass
            elif shutil.which("xdotool"):
                try:
                    r = subprocess.run(["xdotool", "search", "--name", "(?i)virtualbox.*(error|critical)"],
                                       capture_output=True, text=True, timeout=8)
                    for wid in (r.stdout or "").split():
                        out.append((wid, "", "virtualbox error"))
                except Exception: pass
            return out
        found = list_windows()
        for wid, pid, title in found:
            console_log("SYSTEM", f"[anti-stuck] crash dialog detected: {title} - sending OK")
            if shutil.which("xdotool"):
                try:
                    subprocess.run(["xdotool", "windowactivate", "--sync", wid], timeout=6,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["xdotool", "key", "--window", wid, "Return"], timeout=6,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception: pass
            elif shutil.which("wmctrl"):
                try: subprocess.run(["wmctrl", "-i", "-c", wid], timeout=6)
                except Exception: pass
        if found:
            time.sleep(2.0)
            still = list_windows()
            for wid, pid, title in still:
                console_log("SYSTEM", f"[anti-stuck] dialog '{title}' still open - force killing pid {pid or '?'}")
                self.log("[system]", "[warn] crash dialog would not close - force killing it.", "sysmsg")
                if pid and pid.isdigit():
                    try: subprocess.run(["kill", "-9", pid], timeout=8,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception: pass
            try:
                if self._vm_state() == "aborted":
                    run_vbox(["discardstate", vm_name], timeout=20)
            except Exception: pass
        return len(found)

    def _dismiss_crash_dialogs(self):
        """Find a VirtualBox crash/error dialog, click its OK button, wait 2s,
        and force-kill the owning process if the window is still there.

        Matches things like 'VirtualBoxVM.exe - Application Error',
        'VirtualBox - Error', and the Windows 'has stopped working' box."""
        if platform.system() != "Windows":
            try: return self._dismiss_crash_dialogs_linux()
            except Exception: return 0
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return 0
        # exact/likely crash titles
        PATTERNS = ("application error", "virtualbox - error", "virtualboxvm.exe",
                    "has stopped working", "vboxsvc.exe", "runtime error",
                    "virtualbox error", "critical error", "vboxmanage", "guru meditation",
                    "not responding", "fatal error", "vboxheadless")
        # or: any window mentioning virtualbox/vbox together with an error-ish word
        VBOX_WORDS = ("virtualbox", "vbox")
        ERR_WORDS = ("error", "crash", "stopped", "fail", "exception", "terminate", "responding")
        BM_CLICK, WM_CLOSE, WM_COMMAND, IDOK = 0x00F5, 0x0010, 0x0111, 1
        u32 = ctypes.windll.user32
        handled = 0

        def window_titles():
            out = []
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def cb(hwnd, _l):
                try:
                    if not u32.IsWindowVisible(hwnd): return True
                    n = u32.GetWindowTextLengthW(hwnd)
                    if n <= 0: return True
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u32.GetWindowTextW(hwnd, buf, n + 1)
                    t = (buf.value or "").lower()
                    hit = any(p in t for p in PATTERNS)
                    if not hit and any(v in t for v in VBOX_WORDS) and any(w in t for w in ERR_WORDS):
                        hit = True
                    if hit:
                        # only touch real dialog/message boxes, never the VM window itself
                        cls = ctypes.create_unicode_buffer(64)
                        try: u32.GetClassNameW(hwnd, cls, 64)
                        except Exception: pass
                        cname = (cls.value or "").lower()
                        if cname in ("#32770", "") or "error" in t or "stopped" in t:
                            out.append((hwnd, buf.value))
                except Exception: pass
                return True
            try: u32.EnumWindows(EnumProc(cb), 0)
            except Exception: pass
            return out

        def click_ok(hwnd):
            # find an OK / Close button child and click it
            clicked = False
            EnumChild = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def cb(child, _l):
                nonlocal clicked
                try:
                    buf = ctypes.create_unicode_buffer(64)
                    u32.GetWindowTextW(child, buf, 64)
                    label = (buf.value or "").replace("&", "").strip().lower()
                    if label in ("ok", "close", "terminate", "cancel"):
                        u32.SendMessageW(child, BM_CLICK, 0, 0)
                        clicked = True
                        return False
                except Exception: pass
                return True
            try: u32.EnumChildWindows(hwnd, EnumChild(cb), 0)
            except Exception: pass
            if not clicked:
                # no OK button found: tell the dialog OK, then fake Enter/Space
                WM_KEYDOWN, WM_KEYUP, VK_RETURN, VK_SPACE = 0x0100, 0x0101, 0x0D, 0x20
                try:
                    u32.SendMessageW(hwnd, WM_COMMAND, IDOK, 0)
                    u32.SetForegroundWindow(hwnd)
                    for vk in (VK_RETURN, VK_SPACE):
                        u32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
                        u32.PostMessageW(hwnd, WM_KEYUP, vk, 0)
                    u32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                except Exception: pass
            return clicked

        found = window_titles()
        for hwnd, title in found:
            handled += 1
            console_log("SYSTEM", f"[anti-stuck] crash dialog detected: {title} - clicking OK")
            click_ok(hwnd)

        if found:
            time.sleep(2.0)   # give it a moment to close on its own
            still = [(h, t) for (h, t) in window_titles() if u32.IsWindow(h)]
            for hwnd, title in still:
                pid = wintypes.DWORD(0)
                try:
                    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                except Exception:
                    pid = wintypes.DWORD(0)
                console_log("SYSTEM", f"[anti-stuck] dialog '{title}' still open after 2s - force killing pid {pid.value}")
                self.log("[system]", "[warn] crash dialog would not close - force killing it.", "sysmsg")
                if pid.value:
                    try:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid.value)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                    except Exception: pass
                else:
                    try: u32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                    except Exception: pass
            # a crash box means the VM is dead - make sure state is clean
            try:
                if self._vm_state() == "aborted":
                    run_vbox(["discardstate", vm_name], timeout=20)
            except Exception: pass
        # WerFault holds these boxes open; clear it either way
        try:
            subprocess.run(["taskkill", "/F", "/IM", "WerFault.exe"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        except Exception: pass
        return handled

    def _crash_dialog_watcher(self):
        """Poll for VirtualBox crash dialogs so a stream never sits blocked
        behind an unclicked OK button."""
        while self.running:
            try:
                if self.config.get("auto_recover", True):
                    self._dismiss_crash_dialogs()
            except Exception:
                pass
            time.sleep(5)

    def _vbox_pids(self):
        """Find the PIDs of the VirtualBoxVM processes belonging to THIS vm.
        VBoxManage launches them as: VirtualBoxVM.exe --comment <vm_name> --startvm <uuid>
        so we match on the command line instead of the window title (a hung or
        headless VM often has no matching title, which is why taskkill silently
        killed nothing)."""
        pids = []
        if platform.system() != "Windows":
            # linux / macos: match the VM process by its command line
            try:
                r = subprocess.run(["pgrep", "-f", f"VirtualBoxVM.*{vm_name}"],
                                   capture_output=True, text=True, timeout=10)
                pids = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip().isdigit()]
            except Exception:
                pass
            return pids
        target = (vm_name or "").lower()
        try:
            ps = ('powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter '
                  "\\\"Name='VirtualBoxVM.exe'\\\" | Select-Object ProcessId,CommandLine | Format-List\"")
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-CimInstance Win32_Process -Filter \"Name='VirtualBoxVM.exe'\" "
                                "| Select-Object ProcessId,CommandLine | Format-List"],
                               capture_output=True, text=True, timeout=12)
            cur_pid, cur_cmd = None, ""
            for line in (r.stdout or "").splitlines():
                ls = line.strip()
                if ls.lower().startswith("processid"):
                    if cur_pid and target and target in cur_cmd.lower():
                        pids.append(cur_pid)
                    cur_pid = "".join(ch for ch in ls.split(":", 1)[-1] if ch.isdigit())
                    cur_cmd = ""
                elif ls.lower().startswith("commandline"):
                    cur_cmd = ls.split(":", 1)[-1]
                elif cur_cmd and ls:
                    cur_cmd += " " + ls
            if cur_pid and target and target in cur_cmd.lower():
                pids.append(cur_pid)
        except Exception:
            pass
        if not pids:
            try:
                r = subprocess.run(["wmic", "process", "where", "name='VirtualBoxVM.exe'",
                                    "get", "processid,commandline", "/format:list"],
                                   capture_output=True, text=True, timeout=12)
                block = {}
                for line in (r.stdout or "").splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        block[k.strip().lower()] = v.strip()
                    elif not line.strip() and block:
                        if target and target in block.get("commandline", "").lower() and block.get("processid", "").isdigit():
                            pids.append(block["processid"])
                        block = {}
                if block and target and target in block.get("commandline", "").lower() and block.get("processid", "").isdigit():
                    pids.append(block["processid"])
            except Exception:
                pass
        return [p for p in pids if p]

    def _kill_vbox_global(self):
        """Kill the VirtualBox global interface (VBoxSVC.exe / VBoxSDS.exe).
        This is the out-of-process COM server every API call goes through. When it
        wedges, E_FAIL never clears no matter how many times the VM is restarted,
        because the VM process was never the thing that was stuck. Killing it makes
        Windows spawn a fresh one on the next API call. NOTE: this is global - it
        drops the COM state for ALL VirtualBox VMs, so it only runs during recovery."""
        killed = 0
        try:
            with self.input_lock:
                self.shared_kb = None
                self.shared_mouse = None
                if getattr(self, 'shared_session', None):
                    try:
                        if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                        else: self.shared_session.unlockMachine()
                    except Exception: pass
                self.shared_session = None
            if platform.system() == "Windows":
                for proc in ("VBoxSVC.exe", "VBoxSDS.exe"):
                    try:
                        r = subprocess.run(["taskkill", "/F", "/T", "/IM", str(proc)],
                                           capture_output=True, text=True, timeout=15)
                        if r.returncode == 0: killed += 1
                    except Exception: pass
            else:
                for proc in ("VBoxSVC", "VBoxXPCOMIPCD", "VBoxSDS"):
                    try:
                        subprocess.run(["pkill", "-KILL", "-f", proc], timeout=10,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        killed += 1
                    except Exception: pass
            # drop every stale COM handle so the next call spawns a fresh server
            self.vbox = None
            self.mgr = None
            self.force_session_refresh = True
            self.efail_count = 0
            self.last_com_rebuild_time = time.time()
            time.sleep(2.5)
            # reconnect
            try:
                if vbox_pkg == "virtualbox":
                    self.vbox = virtualbox.VirtualBox()
                elif vbox_pkg == "vboxapi":
                    self.mgr = VirtualBoxManager(None, None)
                    self.vbox = self._vboxapi_get_vbox(self.mgr)
            except Exception as e:
                console_log("ERROR", f"vbox global reconnect failed (will retry): {e}")
            console_log("SYSTEM", f"[anti-stuck] killed virtualbox global interface ({killed} process group(s))")
            self.log("[system]", "[warn] virtualbox global interface restarted.", "sysmsg")
        except Exception as e:
            console_log("ERROR", f"kill vbox global failed: {e}")
        return killed

    def _kill_vbox_tasks(self):
        killed = 0
        try:
            # 1) ask VirtualBox to stop it cleanly first
            try: run_vbox(["controlvm", vm_name, "poweroff"], timeout=12)
            except Exception: pass
            if platform.system() == "Windows":
                # 0) clear any crash dialog first so the process can actually die
                self._dismiss_crash_dialogs()
                # 2) kill the exact PIDs for THIS vm (matched by command line)
                for pid in self._vbox_pids():
                    try:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(int(pid))],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                        killed += 1
                    except Exception: pass
                # 3) legacy window-title attempt (harmless if it matches nothing)
                if killed == 0:
                    try:
                        subprocess.run(["taskkill", "/F", "/T", "/FI",
                                        f"WINDOWTITLE eq *{vm_name}*", "/IM", "VirtualBoxVM.exe"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                    except Exception: pass
                # 4) still stuck -> VirtualBox's own emergency stop, then last-resort
                if killed == 0 and self._vm_is_running():
                    try: run_vbox(["startvm", vm_name, "--type", "emergencystop"], timeout=15)
                    except Exception: pass
                    if self._vm_is_running() and len(self._vbox_pids()) == 0:
                        try:
                            subprocess.run(["taskkill", "/F", "/T", "/IM", "VirtualBoxVM.exe"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                            killed += 1
                        except Exception: pass
            else:
                # linux / macos: target the VM process for THIS vm only
                for sig in ("-TERM", "-KILL"):
                    try:
                        subprocess.run(["pkill", sig, "-f", f"VirtualBoxVM.*{vm_name}"], timeout=10,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        killed += 1
                    except Exception: pass
                    time.sleep(0.4)
                    if not self._vm_is_running(): break
            if killed:
                console_log("SYSTEM", f"[anti-stuck] killed {killed} VirtualBoxVM process(es) for {vm_name}")
        except Exception as e:
            console_log("ERROR", f"kill vbox tasks failed: {e}")
        with self.input_lock:
            self.shared_kb = None
            self.shared_mouse = None
            if getattr(self, 'shared_session', None):
                try:
                    if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                    else: self.shared_session.unlockMachine()
                except Exception: pass
            self.shared_session = None
        self.efail_count = 0
        # clear a stale "locked/aborted" state left behind by the killed process
        try:
            if self._vm_state() == "aborted":
                run_vbox(["discardstate", vm_name], timeout=20)
        except Exception: pass
        time.sleep(1.5)

    def _start_vm_safely(self):
        if self.config.get("enable_starting_scene", True): set_obs_scene(obs_scene_starting)
        dbg("vm", f"starting {vm_name} via {vbox_manage_cmd}")
        self.log("[system]", f"[debug] executing startvm for {vm_name}...", "sysmsg")
        success = False
        for attempt in range(5):
            self.vm_start_time = time.time()
            if self._vm_is_running():
                success = True
                break
            try:
                res = subprocess.run([vbox_manage_cmd, "startvm", vm_name, "--type", "gui"], capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:
                self.log("[system]", "[warn] startvm command timed out. killing + retrying...", "sysmsg")
                self._kill_vbox_tasks()
                continue
            except Exception as e:
                self.log("[system]", f"[error] startvm exception: {e}", "err")
                self._kill_vbox_tasks()
                time.sleep(1.0)
                continue
            err_text = (res.stderr or "").strip()
            err_lower = err_text.lower()
            if "vboxhardening" in err_lower or "supr3hardened" in err_lower:
                self.log("[system]", "[error] virtualbox hardening error! reboot pc.", "err")
                console_log("ERROR", f"hardening error: {err_text}")
                break
            confirmed = False
            for _ in range(40):
                if self._vm_is_running():
                    confirmed = True
                    break
                time.sleep(0.5)
            if confirmed:
                time.sleep(1.5)
                if self._vm_is_running():
                    success = True
                    self.log("[system]", "[debug] vm confirmed running.", "sysmsg")
                    break
                else:
                    self.log("[system]", "[warn] vm started then vanished. cleaning up + retry...", "sysmsg")
            else:
                self.log("[system]", f"[warn] startvm reported code {res.returncode} but vm never appeared. retrying... {err_text[:100]}", "sysmsg")
            self._kill_vbox_tasks()
            try: subprocess.run([vbox_manage_cmd, "discardstate", vm_name], capture_output=True, text=True, timeout=15)
            except Exception: pass
            time.sleep(1.0)
        if not success:
            self.log("[system]", "[error] vm failed to start after all retries! escalating.", "err")
            set_obs_scene(obs_scene_error)
        self.vm_start_time = time.time()
        return success

    def _vmware_wait_running(self, want_running, timeout=90):
        """Poll vmrun until the VM's running state matches (or timeout).
        Returns True if the target state was reached."""
        vm = self._vmware()
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if vm.is_running() == want_running:
                    dbg("vmware", f"vm reached running={want_running} in {time.time()-t0:.0f}s")
                    return True
            except Exception as e:
                dbg("vmware", "is_running check failed", e)
            time.sleep(2)
        dbg("vmware", f"timeout waiting for running={want_running}")
        return False

    def _vmware_wait_ready(self, timeout=60):
        """After the VM process is up, wait until the guest actually accepts
        input - i.e. the VNC server is answering. That is the real 'done booting'
        signal, since vmrun reports 'running' the instant the process starts."""
        vm = self._vmware()
        t0 = time.time()
        # give the guest a head start to bring up its VNC server
        time.sleep(3)
        while time.time() - t0 < timeout:
            try:
                if vm.connect():
                    dbg("vmware", f"vnc ready (guest accepting input) in {time.time()-t0:.0f}s")
                    self.vm_start_time = time.time()
                    return True
            except Exception as e:
                dbg("vmware", "vnc not ready yet", e)
            time.sleep(2)
        dbg("vmware", "vnc did not become ready in time (vm may still be booting)")
        return False

    def _do_vm_maintenance(self, action, arg, user):
        """Run a viewer/console VM action. If VirtualBox reports the session is
        LOCKED (a hung or crashed process still holding the VM), close ALL
        VirtualBox processes and retry the exact same action once - so a locked
        VM self-heals instead of every start/revert/restart being refused."""
        global _VBOX_LOCKED
        if getattr(self, "backend", "virtualbox") == "vmware":
            return self._do_vm_maintenance_inner(action, arg, user)
        _VBOX_LOCKED = False
        ok = self._do_vm_maintenance_inner(action, arg, user)
        # a lock can surface either as a False result or via the run_vbox flag,
        # and also shows up as the machine state being stuck 'aborted'
        state = ""
        try: state = self._vm_state()
        except Exception: pass
        if _VBOX_LOCKED or (not ok and state in ("aborted", "unknown")) or state == "aborted":
            self.log("[system]", "[warn] VM session is LOCKED - killing all VirtualBox processes and retrying...", "sysmsg")
            dbg("recovery", f"lock detected on '{action}' (locked={_VBOX_LOCKED}, state={state}) - full kill + retry")
            try:
                self._kill_vbox_tasks()        # kill this VM's process
                self._kill_vbox_global()       # kill VBoxSVC / VBoxSDS (the lock holder)
                self._dismiss_crash_dialogs()  # clear any crash popup
            except Exception as e:
                dbg("recovery", "kill during lock recovery failed", e)
            time.sleep(2.0)
            # clear a stale saved/aborted state that would block a fresh start
            try:
                if self._vm_state() in ("aborted", "saved"):
                    run_vbox(["discardstate", vm_name], timeout=20)
            except Exception: pass
            _VBOX_LOCKED = False
            self.log("[system]", f"retrying '{action}' after unlock...", "sysmsg")
            ok = self._do_vm_maintenance_inner(action, arg, user)
        return ok

    def _do_vm_maintenance_inner(self, action, arg, user):
        action = action.lower()
        dbg("vm", f"maintenance '{action}' requested by {user}")
        if getattr(self, "backend", "virtualbox") == "vmware":
            if action.startswith(self.command_prefix): action = action[len(self.command_prefix):]
            if action.startswith("!"): action = action[1:]
            vm = self._vmware()
            self.vm_maintenance = True
            self._maint_start_t = time.time()
            try:
                if action == "startvm":
                    set_obs_scene(obs_scene_starting)
                    self.log("[system]", "starting vmware vm...", "sysmsg")
                    vm.start()
                    if self._vmware_wait_running(True, 90):
                        self._vmware_wait_ready()
                        set_obs_scene(obs_scene_main)
                        self.log("[system]", "vmware vm is up and ready.", "sysmsg")
                    else:
                        set_obs_scene(obs_scene_error)
                        self.log("[system]", "[error] vmware vm did not start in time.", "err")
                elif action in ("restartvm", "fixvm", "forcefixvm"):
                    set_obs_scene(obs_scene_starting)
                    self.log("[system]", "restarting vmware vm...", "sysmsg")
                    vm.reset()
                    time.sleep(3)
                    if self._vmware_wait_running(True, 90):
                        self._vmware_wait_ready()
                        set_obs_scene(obs_scene_main)
                        self.log("[system]", "vmware vm back up.", "sysmsg")
                elif action == "shutdown":
                    vm.stop()
                    self._vmware_wait_running(False, 40)
                    self.log("[system]", "vmware vm stopped.", "sysmsg")
                elif action in ("revert", "remake2"):
                    set_obs_scene(obs_scene_revert)
                    self.log("[system]", "reverting vmware snapshot...", "sysmsg")
                    snaps = vm.list_snapshots()
                    tgt = self.current_snapshot if self.current_snapshot in snaps else (snaps[-1] if snaps else "")
                    if tgt:
                        vm.revert_snapshot(tgt)
                        time.sleep(2)
                        vm.start()
                        if self._vmware_wait_running(True, 90):
                            self._vmware_wait_ready()
                            set_obs_scene(obs_scene_main)
                            self.log("[system]", f"reverted to '{tgt}', vm ready.", "sysmsg")
                        else:
                            set_obs_scene(obs_scene_error)
                    else:
                        self.log("[system]", "[warn] no vmware snapshot to revert to.", "sysmsg")
                        set_obs_scene(obs_scene_main)
                elif action == "makesnapshot":
                    name = arg.strip() or f"chatsnap_{int(time.time())}"
                    vm.take_snapshot(name)
                    self.log("[system]", f"vmware snapshot '{name}' taken.", "sysmsg")
                vm.connect()
                return True
            except Exception as e:
                dbg("vmware", f"maintenance '{action}' failed", e)
                console_log("ERROR", f"vmware maintenance '{action}' failed: {e}")
                return False
            finally:
                self.vm_maintenance = False
        if action.startswith(self.command_prefix): action = action[len(self.command_prefix):]
        if action.startswith("!"): action = action[1:]
        with self.maintenance_lock:
            self.maintenance_gen += 1
            self.vm_maintenance = True
            self._maint_start_t = time.time()
            with self.vote_lock: self.active_votes.clear()
            self.clear_commands()
            self._teardown_com_session()
            ok = True
            try:
                if action == "startvm":
                    ok = self._start_vm_safely()
                elif action in ("restartvm", "fixvm", "forcefixvm"):
                    self.log("[system]", f"[debug] {action} for {vm_name}...", "sysmsg")
                    if self.config.get("enable_starting_scene", True): set_obs_scene(obs_scene_starting)
                    self._kill_vbox_tasks()
                    run_vbox(["controlvm", vm_name, "poweroff"], timeout=20)
                    time.sleep(2)
                    ok = self._start_vm_safely()
                elif action == "shutdown":
                    self.log("[system]", f"[debug] shutting down {vm_name}...", "sysmsg")
                    r = run_vbox(["controlvm", vm_name, "acpipowerbutton"], timeout=15)
                    time.sleep(8)
                    if self._vm_is_running():
                        run_vbox(["controlvm", vm_name, "poweroff"], timeout=20)
                    ok = True
                elif action == "revert":
                    self.log("[system]", f"[debug] reverting {vm_name} to snapshot {self.current_snapshot}...", "sysmsg")
                    set_obs_scene(obs_scene_revert)
                    self._kill_vbox_tasks()
                    if self._vm_is_running():
                        run_vbox(["controlvm", vm_name, "poweroff"], timeout=20)
                        time.sleep(2)
                    for _ in range(3):
                        if self.current_snapshot:
                            r = run_vbox(["snapshot", vm_name, "restore", self.current_snapshot], timeout=45)
                        else:
                            r = run_vbox(["snapshot", vm_name, "restorecurrent"], timeout=45)
                        if r is not None and r.returncode == 0: break
                        self.log("[system]", "[warn] snapshot restore failed, retrying...", "sysmsg")
                        self._kill_vbox_tasks()
                        time.sleep(2)
                    ok = self._start_vm_safely()
                elif action == "changevm":
                    if not self.changevm_enabled:
                        self.log("[system]", "[warn] changevm is disabled.", "sysmsg")
                    else:
                        set_obs_scene(obs_scene_changevm)
                        self._kill_vbox_tasks()
                        if self._vm_is_running():
                            run_vbox(["controlvm", vm_name, "poweroff"], timeout=20)
                            time.sleep(2)
                        self._advance_vm_state()
                        self.root.after(0, self._update_vm_label)
                        if self.current_snapshot:
                            run_vbox(["snapshot", vm_name, "restore", self.current_snapshot], timeout=45)
                        ok = self._start_vm_safely()
                elif action == "makesnapshot":
                    snap_name = arg.strip() or f"chatsnap_{int(time.time())}"
                    r = run_vbox(["snapshot", vm_name, "take", snap_name], timeout=45)
                    if r is not None and r.returncode == 0:
                        self.current_snapshot = snap_name
                        try:
                            with open(snap_file, "w") as f: f.write(self.current_snapshot)
                        except Exception: pass
                        self.log("[system]", f"[debug] snapshot '{snap_name}' created.", "sysmsg")
                    ok = True
                elif action == "remake2":
                    set_obs_scene(obs_scene_revert)
                    self._kill_vbox_tasks()
                    if self._vm_is_running():
                        run_vbox(["controlvm", vm_name, "poweroff"], timeout=20)
                        time.sleep(2)
                    if self.current_snapshot:
                        run_vbox(["snapshot", vm_name, "restore", self.current_snapshot], timeout=45)
                    ok = self._start_vm_safely()
                else:
                    self.log("[system]", f"[warn] unknown maintenance action: {action}", "sysmsg")
            except Exception as e:
                ok = False
                console_log("ERROR", f"maintenance '{action}' crashed: {e}\n{traceback.format_exc()}")
                self.log("[system]", f"[error] maintenance {action} failed: {e}", "err")
            finally:
                if action != "shutdown":
                    if ok and self._vm_is_running():
                        set_obs_scene(obs_scene_main)
                        self.consecutive_failures = 0
                        self.last_success_time = time.time()
                    else:
                        self.log("[system]", f"[error] {action} did not leave a running vm! error scene set.", "err")
                        set_obs_scene(obs_scene_error)
                        self.consecutive_failures = getattr(self, 'consecutive_failures', 0) + 1
                self.vm_maintenance = False
            return ok

    def _teardown_com_session(self):
        with self.input_lock:
            self.shared_kb = None
            self.shared_mouse = None
            if getattr(self, "win_session", None) is not None:
                try: self.win_session.UnlockMachine()
                except Exception: pass
                self.win_session = None
                self.com_mode = ""
            if getattr(self, 'shared_session', None):
                try:
                    if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                    else: self.shared_session.unlockMachine()
                except Exception: pass
            self.shared_session = None

    def _vboxapi_get_vbox(self, mgr):
        """Get the IVirtualBox object. Older vboxapi exposes getVirtualBox(),
        newer builds only expose the .vbox attribute."""
        for getter in (lambda: mgr.vbox,
                       lambda: mgr.getVirtualBox(),
                       lambda: mgr.platform.getVirtualBox()):
            try:
                v = getter()
                if v is not None:
                    return v
            except Exception:
                continue
        raise RuntimeError("could not obtain IVirtualBox from vboxapi")

    def _vboxapi_session(self, machine):
        """Return (session, already_locked).

        vboxapi's session API is genuinely inconsistent between VirtualBox
        releases: getSessionObject may live on the VirtualBoxManager, on the
        inner .mgr, or on .platform, and it may take the vbox object, None, or
        no argument at all. Newer builds dropped some of these entirely, which
        is what causes:
            'VirtualBoxManager' object has no attribute 'getSessionObject'
        So try every documented form, plus openMachineSession() which creates
        AND locks the session in one call."""
        mgr = self.mgr
        inner = getattr(mgr, "mgr", None)
        plat = getattr(mgr, "platform", None)

        # 1) openMachineSession: returns an already-locked session
        for opener in (lambda: mgr.openMachineSession(machine, True),
                       lambda: mgr.openMachineSession(machine)):
            try:
                sess = opener()
                if sess is not None:
                    return sess, True
            except TypeError:
                continue
            except Exception:
                continue

        # 2) every known getSessionObject location / signature
        holders = [h for h in (mgr, inner, plat) if h is not None]
        for holder in holders:
            fn = getattr(holder, "getSessionObject", None)
            if fn is None:
                continue
            for call in (lambda f=fn: f(self.vbox), lambda f=fn: f(None), lambda f=fn: f()):
                try:
                    sess = call()
                    if sess is not None:
                        return sess, False
                except TypeError:
                    continue
                except Exception:
                    continue

        # 3) last resort: build an ISession straight from the COM/XPCOM platform
        for maker in (lambda: mgr.createSessionObject(),
                      lambda: plat.createSessionObject() if plat else None,
                      lambda: mgr.getSessionObjectNoWait() if hasattr(mgr, "getSessionObjectNoWait") else None):
            try:
                sess = maker()
                if sess is not None:
                    return sess, False
            except Exception:
                continue
        return None, False

    def _wincom_connect(self):
        """Talk to VirtualBox's NATIVE COM server via pywin32.

        This is the robust path on Windows: VirtualBox registers the COM objects
        'VirtualBox.VirtualBox' and 'VirtualBox.Session' as part of its own
        install, so the interface ALWAYS matches the installed VirtualBox. There
        are no pre-generated Python bindings to go stale, which is what breaks
        pyvbox after a VirtualBox update.
        Returns True when keyboard+mouse are live."""
        if platform.system() != "Windows":
            return False
        try:
            import pythoncom
            try: pythoncom.CoInitializeEx(0)
            except Exception:
                try: pythoncom.CoInitialize()
                except Exception: pass
        except Exception:
            pass
        try:
            import win32com.client
        except Exception:
            if not getattr(self, "_wincom_warned", False):
                self._wincom_warned = True
                console_log("ERROR", "pywin32 missing - install it with: pip install pywin32")
            return False
        try:
            try:
                if getattr(self, "win_session", None) is not None:
                    self.win_session.UnlockMachine()
            except Exception: pass
            self.win_session = None
            vbox = win32com.client.Dispatch("VirtualBox.VirtualBox")
            session = win32com.client.Dispatch("VirtualBox.Session")
            machine = vbox.FindMachine(vm_name)
            machine.LockMachine(session, 1)          # 1 = LockType_Shared
            console = session.Console
            if console is None:
                raise RuntimeError("console not ready")
            kb = console.Keyboard
            mouse = console.Mouse
            if kb is None or mouse is None:
                raise RuntimeError("keyboard/mouse not ready")
            self.win_vbox = vbox
            self.win_session = session
            self.shared_session = session
            self.shared_kb = kb
            self.shared_mouse = mouse
            self.com_mode = "wincom"
            self.cli_input = False
            self.vbox_binding_broken = False
            self._com_input_fails = 0
            self.efail_count = 0
            self.last_com_rebuild_time = time.time()
            dbg("com", "native COM connected (keyboard+mouse live)")
            if not getattr(self, "_wincom_announced", False):
                self._wincom_announced = True
                console_log("SYSTEM", "using VirtualBox native COM (pywin32) - always matches your installed VirtualBox.")
                self.log("[system]", "connected via virtualbox native com. keyboard + mouse active.", "sysmsg")
            return True
        except Exception as e:
            try:
                if getattr(self, "win_session", None) is not None:
                    self.win_session.UnlockMachine()
            except Exception: pass
            self.win_session = None
            _l = str(e).lower()
            if not ("not ready" in _l or "0x80bb0007" in _l or "invalid" in _l or "locked" in _l):
                if time.time() - getattr(self, "_last_wincom_err_t", 0) > 10:
                    self._last_wincom_err_t = time.time()
                    console_log("ERROR", f"native com connect failed: {e}")
            return False

    def _ensure_com_session(self):
        with self.input_lock:
            if self.shared_kb is not None and self.shared_mouse is not None and not getattr(self, 'force_session_refresh', False):
                return True
            if getattr(self, "backend", "virtualbox") == "vmware":
                return False
            dbg("com", "building input session")
            self.force_session_refresh = False
            session = None
            # Native COM first on Windows: it is version-matched to the installed
            # VirtualBox, so it survives VirtualBox updates that break pyvbox.
            if platform.system() == "Windows" and not getattr(self, "_wincom_disabled", False):
                if self._wincom_connect():
                    return True
            try:
                if self.shared_session:
                    try:
                        if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                        else: self.shared_session.unlockMachine()
                    except Exception: pass
                    self.shared_session = None
                if not self._vm_is_running():
                    self.shared_kb = None
                    self.shared_mouse = None
                    return False
                if vbox_pkg == "virtualbox":
                    if self.vbox is None: self.vbox = virtualbox.VirtualBox()
                    session = virtualbox.Session()
                    machine = self.vbox.find_machine(vm_name)
                    machine.lock_machine(session, virtualbox.library.LockType.shared)
                    self.shared_session = session
                    console = getattr(session, "console", None)
                    if console is None:
                        raise RuntimeError("console not ready")
                    self.shared_kb = console.keyboard
                    self.shared_mouse = console.mouse
                elif vbox_pkg == "vboxapi":
                    if self.vbox is None:
                        self.mgr = VirtualBoxManager(None, None)
                        self.vbox = self._vboxapi_get_vbox(self.mgr)
                    machine = self.vbox.findMachine(vm_name)
                    session, locked = self._vboxapi_session(machine)
                    if session is None:
                        raise RuntimeError("could not obtain a vboxapi session object")
                    if not locked:
                        machine.lockMachine(session, 1)
                    self.shared_session = session
                    console = getattr(session, "console", None)
                    if console is None:
                        raise RuntimeError("console not ready")
                    self.shared_kb = console.keyboard
                    self.shared_mouse = console.mouse
                else:
                    return False
                if self.shared_kb is None or self.shared_mouse is None:
                    raise RuntimeError("keyboard/mouse not ready")
                self.last_com_rebuild_time = time.time()
                return True
            except Exception as e:
                try:
                    if session is not None:
                        if vbox_pkg == "virtualbox": session.unlock_machine()
                        else: session.unlockMachine()
                except Exception: pass
                self.shared_kb = None
                self.shared_mouse = None
                self.shared_session = None
                _m = str(e).lower()
                _binding = ("find attribute" in _m or "ivirtualbox" in _m or "library_ext" in _m
                            or "getsessionobject" in _m or "virtualboxmanager" in _m
                            or "no attribute" in _m or "session object" in _m
                            or ("attribute" in _m and "object at" in _m))
                if _binding:
                    # pyvbox bindings no longer match the installed VirtualBox
                    # (happens after a VirtualBox update). Killing VBoxSVC won't fix
                    # a Python-side binding mismatch, so DON'T count this as an
                    # E_FAIL storm. Try the version-matched vboxapi; if that isn't
                    # available, fall back to VBoxManage CLI so typing still works.
                    if not getattr(self, "_tried_vboxapi", False):
                        self._tried_vboxapi = True
                        if self._try_vboxapi_fallback():
                            return False
                    if not getattr(self, "cli_input", False):
                        self.cli_input = True
                        self.vbox_binding_broken = True
                        console_log("ERROR", "VirtualBox was updated and the 'virtualbox' (pyvbox) python package no longer matches it.")
                        console_log("SYSTEM", "falling back to VBoxManage CLI for keyboard (mouse needs the API). fix fully with:  pip install --upgrade virtualbox   (or install the VirtualBox SDK's vboxapi)")
                        self.log("[system]", "[warn] pyvbox mismatch after VBox update - using CLI keyboard fallback. run: pip install --upgrade virtualbox", "err")
                    return False
                _locked = ("already locked" in _m or "0x80bb0007" in _m or "being locked" in _m
                           or "object_in_use" in _m or "0x80bb000c" in _m or "session is locked" in _m)
                if _locked and not getattr(self, "_lock_recovering", False):
                    self._lock_recovering = True
                    def _unlock():
                        try:
                            self.log("[system]", "[warn] COM session LOCKED - clearing VirtualBox processes...", "sysmsg")
                            self._kill_vbox_tasks(); self._kill_vbox_global(); self._dismiss_crash_dialogs()
                            time.sleep(2)
                            if self._vm_state() in ("aborted", "saved"):
                                run_vbox(["discardstate", vm_name], timeout=20)
                            self.force_session_refresh = True
                        except Exception as ue:
                            dbg("recovery", "unlock failed", ue)
                        finally:
                            self._lock_recovering = False
                    threading.Thread(target=_unlock, daemon=True).start()
                    return False
                _transient = ("subscriptable" in _m or "not ready" in _m or "console" in _m
                              or "0x80bb0007" in _m or "invalid_vm_state" in _m or "e_accessdenied" in _m
                              or "-2147418113" in _m or "not currently" in _m or "being locked" in _m
                              or "already locked" in _m)
                if _transient:
                    time.sleep(0.5)   # vm still booting / session settling — retry silently
                else:
                    if time.time() - getattr(self, "_last_com_err_t", 0) > 10:
                        self._last_com_err_t = time.time()
                        console_log("ERROR", f"com session build failed: {e}")
                return False

    def _cli_put_string(self, text):
        if text and len(text) > 4000:
            text = text[:4000]
        """VBoxManage can type a whole string directly - far more reliable than
        pushing hex scancodes one at a time when the API path is unavailable."""
        if not text: return True
        try:
            r = subprocess.run([vbox_manage_cmd, "controlvm", vm_name, "keyboardputstring", text],
                               capture_output=True, text=True, timeout=15)
            return r.returncode == 0
        except Exception:
            return False

    def _cli_put_scancodes(self, seq):
        # keyboard input via VBoxManage CLI - works even when the COM/pyvbox
        # bindings are broken after a VirtualBox update (no mouse support though)
        if not seq: return
        try:
            hexcodes = [format(int(b) & 0xFF, "02x") for b in seq]
            subprocess.run([vbox_manage_cmd, "controlvm", vm_name, "keyboardputscancode"] + hexcodes,
                           capture_output=True, text=True, timeout=6)
        except Exception:
            pass

    def _try_vboxapi_fallback(self):
        # vboxapi ships with VirtualBox itself, so it always matches the installed
        # version - switch to it when the pip 'virtualbox' package is out of sync
        global vbox_pkg
        try:
            from vboxapi import VirtualBoxManager as _VBM
            globals()["VirtualBoxManager"] = _VBM
            vbox_pkg = "vboxapi"
            self.vbox = None
            self.mgr = None
            self._vboxapi_ok = True
            self.shared_kb = None
            self.shared_mouse = None
            self.shared_session = None
            self.vbox_binding_broken = False
            self.cli_input = False
            self.force_session_refresh = True
            console_log("SYSTEM", "switched to vboxapi bindings (version-matched to your VirtualBox).")
            self.log("[system]", "using vboxapi bindings now.", "sysmsg")
            return True
        except Exception:
            return False

    def _raw_put(self, kb, chunk):
        if getattr(self, "com_mode", "") == "wincom":
            kb.PutScancodes([int(b) for b in chunk])
        elif vbox_pkg == "virtualbox":
            kb.put_scancodes(list(chunk))
        else:
            kb.putScancodes(list(chunk))

    def _send_scancodes(self, seq):
        if not seq: return
        if getattr(self, "cli_input", False):
            self._cli_put_scancodes(seq); return
        with self.input_lock:
            kb = self.shared_kb
            if kb is None:
                if getattr(self, "vbox_binding_broken", False):
                    self._cli_put_scancodes(seq)
                return
            try:
                # VirtualBox's PDM keyboard queue is small (it drops everything
                # past it with VERR_PDM_NO_QUEUE_ITEMS). Feed it in small chunks
                # and back off when it reports full, instead of losing the rest
                # of a long !type.
                seq = [int(b) for b in seq]
                CHUNK = 12
                i = 0
                while i < len(seq):
                    chunk = seq[i:i + CHUNK]
                    for attempt in range(14):
                        try:
                            self._raw_put(kb, chunk)
                            break
                        except Exception as ce:
                            cl = str(ce).lower()
                            if ("verr_pdm_no_queue_items" in cl or "no_queue" in cl
                                    or "could not send all scan codes" in cl or "-2135228411" in cl):
                                # queue full: let the guest drain, then retry
                                time.sleep(0.04 + attempt * 0.03)
                                if attempt >= 6 and CHUNK > 4:
                                    CHUNK = 4
                                    chunk = chunk[:4]
                                continue
                            raise
                    else:
                        self._queue_drops = getattr(self, "_queue_drops", 0) + 1
                        if time.time() - getattr(self, "_last_qwarn", 0) > 10:
                            self._last_qwarn = time.time()
                            self.log("[system]", "[warn] vm keyboard buffer is saturated - slowing typing down.", "sysmsg")
                        try:
                            self.config["typing_speed"] = min(float(self.config.get("typing_speed", 0.015)) + 0.01, 0.08)
                        except Exception: pass
                        break
                    i += len(chunk)
                    if len(seq) > CHUNK:
                        time.sleep(0.012)
                self._com_input_fails = 0
            except Exception as e:
                emsg = str(e)
                _l = emsg.lower()
                # A half-built pyvbox proxy raises from INSIDE put_scancodes
                # ("'NoneType' object is not subscriptable" / attribute errors).
                # That's a broken binding, not a wedged VM - killing VBoxSVC won't
                # help, so switch this session to the VBoxManage CLI and resend the
                # keystroke instead of losing it.
                if ("verr_pdm_no_queue_items" in _l or "could not send all scan codes" in _l
                        or "-2135228411" in _l):
                    return   # transient guest-side buffer pressure, not a COM fault
                _binding = ("subscriptable" in _l or "nonetype" in _l
                            or "no attribute" in _l or "attribute" in _l
                            or isinstance(e, (TypeError, AttributeError)))
                if _binding:
                    self._com_input_fails = getattr(self, "_com_input_fails", 0) + 1
                    # a broken pyvbox proxy -> rebuild on native COM instead of
                    # dropping to the CLI (native COM keeps mouse support too)
                    if platform.system() == "Windows" and getattr(self, "com_mode", "") != "wincom":
                        if self._wincom_connect():
                            try:
                                self.shared_kb.PutScancodes([int(b) for b in seq])
                                return
                            except Exception: pass
                    if self._com_input_fails >= 2 and not getattr(self, "cli_input", False):
                        self.cli_input = True
                        self.vbox_binding_broken = True
                        self.shared_kb = None
                        console_log("SYSTEM", "pyvbox keyboard proxy is broken - switching to VBoxManage CLI keyboard. fix fully with: pip install --upgrade virtualbox")
                        self.log("[system]", "[warn] switched to CLI keyboard (pyvbox mismatch). mouse needs 'pip install --upgrade virtualbox'.", "err")
                    self._cli_put_scancodes(seq)   # don't drop the keypress
                    return
                self._flag_com_error(emsg)
                raise

    def _press(self, seq):
        self._send_scancodes(list(seq))

    def _release(self, seq):
        rel = [(b if b in (0xE0, 0xE1, 224, 225) else (b | 0x80)) for b in seq]
        self._send_scancodes(rel)

    def _tap(self, seq):
        self._press(seq)
        self._release(seq)

    def _break(self, seq):
        return [(b if b in (0xE0, 0xE1, 224, 225) else (b | 0x80)) for b in seq]

    def _release_all_mods(self):
        # send break codes for every modifier so a dropped release can never
        # leave shift/ctrl/alt stuck down and garble everything typed after it
        try:
            self._send_scancodes([0xAA, 0xB6, 0x9D, 0xE0, 0x9D, 0xB8, 0xE0, 0xB8])
        except Exception:
            pass

    def _type_char(self, ch):
        # build the full make+break (incl. modifiers) for one character and send
        # it as ONE atomic put_scancodes call, so the guest can't drop part of it
        mods, codes = get_typed_codes(ch, keyboard_layout)
        seq = []
        for mseq in mods: seq += list(mseq)                     # modifier(s) down
        seq += list(codes)                                      # key down
        seq += self._break(codes)                               # key up
        for mseq in reversed(mods): seq += self._break(mseq)    # modifier(s) up
        self._send_scancodes(seq)

    def _mouse_event(self, dx, dy, dz, buttons):
        with self.input_lock:
            m = self.shared_mouse
            if m is None: return
            try:
                if getattr(self, "com_mode", "") == "wincom":
                    m.PutMouseEvent(int(dx), int(dy), int(dz), 0, int(buttons))
                elif vbox_pkg == "virtualbox": m.put_mouse_event(dx, dy, dz, 0, buttons)
                else: m.putMouseEvent(dx, dy, dz, 0, buttons)
            except Exception as e:
                emsg = str(e)
                _l = emsg.lower()
                if ("subscriptable" in _l or "nonetype" in _l or "no attribute" in _l
                        or isinstance(e, (TypeError, AttributeError))):
                    if not getattr(self, "_mouse_warned", False):
                        self._mouse_warned = True
                        self.log("[system]", "[warn] mouse needs the VirtualBox API - run: pip install --upgrade virtualbox", "err")
                    return
                self._flag_com_error(emsg)
                raise

    def _mouse_abs(self, x, y, buttons=0):
        with self.input_lock:
            m = self.shared_mouse
            if m is None: return
            try:
                if getattr(self, "com_mode", "") == "wincom":
                    m.PutMouseEventAbsolute(int(x), int(y), 0, 0, int(buttons))
                elif vbox_pkg == "virtualbox": m.put_mouse_event_absolute(x, y, 0, 0, buttons)
                else: m.putMouseEventAbsolute(x, y, 0, 0, buttons)
            except Exception as e:
                emsg = str(e)
                _l = emsg.lower()
                if ("subscriptable" in _l or "nonetype" in _l or "no attribute" in _l
                        or isinstance(e, (TypeError, AttributeError))):
                    if not getattr(self, "_mouse_warned", False):
                        self._mouse_warned = True
                        self.log("[system]", "[warn] mouse needs the VirtualBox API - run: pip install --upgrade virtualbox", "err")
                    return
                self._flag_com_error(emsg)
                raise

    def _vmware_exec(self, cmd, arg):
        """Drive a VMware guest over VNC (vncdotool) instead of VBox scancodes.
        Input problems are reported to the visible log, because a keystroke that
        quietly goes nowhere is the hardest kind of failure to diagnose."""
        vm = self._vmware()
        dbg("vmware", f"exec {cmd} {str(arg)[:50]!r}  (client={'up' if vm.client else 'down'})")
        # make sure we actually have an input channel before pretending to type
        if not vm._need():
            if time.time() - getattr(self, "_last_vnc_warn", 0) > 20:
                self._last_vnc_warn = time.time()
                self.log("[system]", f"[error] cannot send input to vmware: {vm.status}", "err")
            return
        base = (cmd[1:] if cmd.startswith("!") else cmd).lower()
        if base in ("type", "send"):
            vm.type_text(arg)
            if base == "send": vm.press_key("enter")
        elif base == "key": vm.press_key(arg)
        elif base == "combo": vm.key_combo(arg)
        elif base in ("click", "lclick"): vm.click(1, safe_int(arg, 1, 1, 20))
        elif base == "rclick": vm.click(3, safe_int(arg, 1, 1, 20))
        elif base == "mclick": vm.click(2, 1)
        elif base == "move":
            p = str(arg).split()
            if len(p) == 2:
                d, amt = p[0].lower(), safe_int(p[1], 10, -5000, 5000)
                dx = -amt if d == "left" else (amt if d == "right" else 0)
                dy = -amt if d == "up" else (amt if d == "down" else 0)
                vm.move_rel(dx, dy)
        elif base == "abs":
            p = str(arg).split()
            if len(p) == 2: vm.move_abs(safe_int(p[0], 0, 0, 10000), safe_int(p[1], 0, 0, 10000))
        elif base == "scroll":
            vm.scroll(safe_int(arg, -1, -20, 20))
        elif base == "drag":
            p = str(arg).split()
            if len(p) == 2: vm.drag(safe_int(p[0], 0, -5000, 5000), safe_int(p[1], 0, -5000, 5000))
        elif base == "run":
            vm.key_combo("win+r"); time.sleep(0.7); vm.type_text(arg); vm.press_key("enter")
        elif base == "cmd":
            vm.key_combo("win+r"); time.sleep(0.7); vm.type_text("cmd"); vm.press_key("enter")
            time.sleep(1.2); vm.type_text(arg); vm.press_key("enter")
        else:
            dbg("vmware", f"command '{base}' is not mapped for the vmware backend")
            return
        # VNC has no acknowledgement, so the guest needs a beat to catch up. Without
        # this, a chain like "!combo win+r !send cmd" fires the text before the Run
        # dialog exists and it is simply lost. Delays are sized per action: opening
        # a window needs far longer than nudging the mouse.
        try:
            mult = float(self.config.get("vmware_settle", 1.0))
        except Exception:
            mult = 1.0   # 0 is a valid value, so don't use 'or' here
        settle = {
            "combo": 0.85,   # win+r, ctrl+shift+esc etc. open a window
            "run": 1.20, "cmd": 1.50,
            "send": 0.70,    # ends with Enter, so something is about to happen
            "key": 0.30, "type": 0.25,
            "click": 0.20, "lclick": 0.20, "rclick": 0.20, "mclick": 0.20,
            "drag": 0.20, "scroll": 0.08, "move": 0.05, "abs": 0.05,
        }.get(base, 0.15)
        if base == "key" and str(arg).strip().lower() in ("enter", "return", "f5", "esc", "escape"):
            settle = 0.60   # these usually trigger something
        settle *= max(0.0, min(mult, 5.0))
        if settle > 0:
            dbg("vmware", f"settle {settle:.2f}s after '{base}'")
            time.sleep(settle)
        st = str(getattr(vm, "status", ""))
        if "error" in st.lower() or "fail" in st.lower() or "not " in st.lower():
            if time.time() - getattr(self, "_last_vnc_warn", 0) > 20:
                self._last_vnc_warn = time.time()
                self.log("[system]", f"[warn] vmware input: {st}", "err")

    def _run_watched(self, cmd, arg, user, timeout=45):
        """Run one command with a hard timeout. On a slow PC a long VNC type can
        take a while, but it must never hang the executor forever - if it blows
        the timeout we drop the stale VNC client so the next command reconnects
        cleanly instead of the whole bot freezing."""
        done = threading.Event()

        def _work():
            try:
                self.run_cmd_worker(cmd, arg, user)
            except Exception as e:
                dbg("exec", f"watched cmd '{cmd}' crashed", e)
            finally:
                done.set()

        th = threading.Thread(target=_work, daemon=True, name="cmd-worker")
        th.start()
        if not done.wait(timeout):
            dbg("exec", f"command '{cmd} {str(arg)[:30]}' exceeded {timeout}s - dropping vnc session")
            self.log("[system]", f"[warn] '{cmd}' took too long; recovering.", "sysmsg")
            try:
                if getattr(self, "vmware", None) and self.vmware.client:
                    self.vmware.disconnect()
            except Exception:
                pass

    def run_cmd_worker(self, cmd, arg, user):
        global total_commands_failed
        display_cmd = f"{cmd} {arg}".strip()
        if getattr(self, "backend", "virtualbox") == "vmware":
            try:
                self._vmware_exec(cmd, arg)
                self.last_cmd_ok_t = time.time()
            except Exception as e:
                total_commands_failed += 1
                if time.time() - getattr(self, "_last_vmw_err_t", 0) > 8:
                    self._last_vmw_err_t = time.time()
                    console_log("ERROR", f"vmware cmd '{display_cmd}' failed: {e}")
            return
        _tgt = getattr(self, "pico_target", "vm")
        if getattr(self, "pico_enabled", False) and self.pico and getattr(self.pico, "ser", None) and _tgt in ("pico", "both"):
            try: self.pico.dispatch(cmd, arg)
            except Exception as _pe: console_log("ERROR", f"pico dispatch failed: {_pe}")
            if _tgt == "pico":
                return
        try:
            key_delay = float(self.config.get("key_delay", 0.015)) if not self.ultra_speed else 0
            type_delay = float(self.config.get("typing_speed", 0.015)) if not self.ultra_speed else 0
            mouse_delay = float(self.config.get("mouse_delay", 0.005)) if not self.ultra_speed else 0
            base = cmd[1:] if cmd.startswith("!") else cmd

            if base in ("type", "send"):
                if len(arg) > 4000:
                    arg = arg[:4000]
                    self.log("[system]", "[warn] input truncated to 4000 chars.", "sysmsg")
                _td = max(type_delay if not self.ultra_speed else 0.0, 0.006)
                if getattr(self, "cli_input", False) and arg:
                    if self._cli_put_string(arg):
                        if base == "send":
                            time.sleep(0.05); self._cli_put_scancodes(scancodes["enter"])
                            self._cli_put_scancodes(self._break(scancodes["enter"]))
                        return
                self._release_all_mods()
                for ch in arg:
                    self._type_char(ch)
                    time.sleep(_td)
                self._release_all_mods()
                if base == "send":
                    time.sleep(max(key_delay, 0.02))
                    self._tap(scancodes["enter"])
            elif base == "key":
                seq = scancodes.get(arg.lower().strip())
                if seq: self._tap(seq)
            elif base == "keydown":
                seq = scancodes.get(arg.lower().strip())
                if seq: self._press(seq)
            elif base == "keyup":
                seq = scancodes.get(arg.lower().strip())
                if seq: self._release(seq)
            elif base == "combo":
                keys = [k.strip().lower() for k in arg.replace(" ", "+").split("+") if k.strip()]
                seqs = [scancodes.get(k) for k in keys if scancodes.get(k)]
                for s in seqs: self._press(s)
                if key_delay: time.sleep(key_delay)
                for s in reversed(seqs): self._release(s)
            elif base in ("click", "lclick"):
                count = int(arg) if arg.strip().isdigit() else 1
                for _ in range(max(1, min(count, 20))):
                    self._mouse_event(0, 0, 0, 1); time.sleep(0.02); self._mouse_event(0, 0, 0, 0)
                    if mouse_delay: time.sleep(mouse_delay)
            elif base == "rclick":
                count = int(arg) if arg.strip().isdigit() else 1
                for _ in range(max(1, min(count, 20))):
                    self._mouse_event(0, 0, 0, 2); time.sleep(0.02); self._mouse_event(0, 0, 0, 0)
                    if mouse_delay: time.sleep(mouse_delay)
            elif base == "mclick":
                self._mouse_event(0, 0, 0, 4); time.sleep(0.02); self._mouse_event(0, 0, 0, 0)
            elif base == "move":
                p = arg.split()
                if len(p) == 2:
                    d, amt = p[0].lower(), int(p[1])
                    dx = dy = 0
                    if d == "left": dx = -amt
                    elif d == "right": dx = amt
                    elif d == "up": dy = -amt
                    elif d == "down": dy = amt
                    self._mouse_event(dx, dy, 0, 0)
                elif len(p) == 2:
                    self._mouse_event(int(p[0]), int(p[1]), 0, 0)
            elif base == "abs":
                p = arg.split()
                if len(p) == 2: self._mouse_abs(int(p[0]), int(p[1]), 0)
            elif base == "scroll":
                try: amt = int(arg)
                except Exception: amt = -1
                self._mouse_event(0, 0, amt, 0)
            elif base == "drag":
                p = arg.split()
                if len(p) == 2:
                    dx, dy = int(p[0]), int(p[1])
                    self._mouse_event(0, 0, 0, 1); time.sleep(0.05)
                    steps = 10
                    for i in range(steps):
                        self._mouse_event(dx // steps, dy // steps, 0, 1); time.sleep(0.01)
                    self._mouse_event(0, 0, 0, 0)
            elif base == "run":
                self._release_all_mods()
                lw = scancodes["lwin"]; rk = scancodes["r"]
                self._send_scancodes(list(lw) + list(rk) + self._break(rk) + self._break(lw))
                time.sleep(0.7)
                _td = max(type_delay if not self.ultra_speed else 0.0, 0.006)
                for ch in arg:
                    self._type_char(ch); time.sleep(_td)
                self._release_all_mods()
                time.sleep(0.2); self._tap(scancodes["enter"])
            elif base == "cmd":
                self._release_all_mods()
                lw = scancodes["lwin"]; rk = scancodes["r"]
                self._send_scancodes(list(lw) + list(rk) + self._break(rk) + self._break(lw))
                time.sleep(0.7)
                _td = max(type_delay if not self.ultra_speed else 0.0, 0.006)
                for ch in "cmd":
                    self._type_char(ch); time.sleep(_td)
                self._tap(scancodes["enter"]); time.sleep(1.0)
                for ch in arg:
                    self._type_char(ch); time.sleep(_td)
                self._release_all_mods()
                time.sleep(0.2); self._tap(scancodes["enter"])
            elif base == "roll":
                self.log("[system]", f"{user} rolled {random.randint(1, 100)}!", "sysmsg")
            elif base == "coinflip":
                self.log("[system]", f"{user} flipped {random.choice(['heads', 'tails'])}!", "sysmsg")
            elif base in ("volumeup", "volumedown"):
                seq = scancodes["vol_up"] if base == "volumeup" else scancodes["vol_down"]
                reps = int(arg) if arg.strip().isdigit() else 1
                for _ in range(max(1, min(reps, 50))): self._tap(seq)
            self.last_cmd_ok_t = time.time()
            if getattr(self, "efail_count", 0): self.efail_count = 0
            if getattr(self, "consecutive_failures", 0): self.consecutive_failures = 0
            if getattr(self, "watchdog_action_level", 0): self.watchdog_action_level = 0
        except Exception as e:
            total_commands_failed += 1
            self._flag_com_error(e)
            if time.time() - getattr(self, "_last_cmd_err_t", 0) > 8:
                self._last_cmd_err_t = time.time()
                console_log("ERROR", f"cmd '{display_cmd}' failed: {e}")

    def executor_loop(self, thread_id=0):
        maintenance_actions = {"startvm", "revert", "restartvm", "shutdown", "changevm", "fixvm", "forcefixvm", "makesnapshot", "remake2"}
        while self.running and getattr(self, 'executor_id', 0) == thread_id:
            self.executor_tick = time.time()
            try:
                try:
                    action = self.cmd_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if not action or len(action) < 3: continue
                cmd, arg, user = action[0], action[1], action[2]
                self._exec_current = f"{cmd} {str(arg)[:40]}"
                self._exec_started = time.time()
                dbg("exec", f"START {cmd} {str(arg)[:60]!r} from {user} (queue={self.cmd_queue.qsize()})")
                base = cmd.lower()
                if base.startswith(self.command_prefix): base = base[len(self.command_prefix):]
                if base.startswith("!"): base = base[1:]
                if base in maintenance_actions:
                    self._do_vm_maintenance(base, arg, user)
                    continue
                if getattr(self, 'vm_maintenance', False):
                    continue
                if getattr(self, "pico_enabled", False) and getattr(self, "pico_target", "vm") == "pico":
                    if self.pico and getattr(self.pico, "ser", None):
                        self.run_cmd_worker(cmd, arg, user)
                    continue
                if getattr(self, "backend", "virtualbox") == "vmware":
                    self._run_watched(cmd, arg, user)
                    continue
                if not self._vm_is_running():
                    continue
                if getattr(self, "cli_input", False):
                    self.run_cmd_worker(cmd, arg, user)
                    continue
                if not self._ensure_com_session():
                    self.force_session_refresh = True
                    time.sleep(0.2)
                    continue
                self.run_cmd_worker(cmd, arg, user)
                dbg("exec", f"DONE  {cmd} in {(time.time()-self._exec_started)*1000:.0f}ms")
                self._exec_current = ""
            except Exception as e:
                dbg("exec", f"CRASH in {self._exec_current!r}", e)
                console_log("ERROR", f"executor loop error: {e}\n{traceback.format_exc()}")
                self.force_session_refresh = True
                time.sleep(0.5)

    def error_watcher_loop(self):
        while self.running:
            try:
                time.sleep(5)
                if getattr(self, 'vm_maintenance', False):
                    continue
                now = time.time()
                if now - getattr(self, 'executor_tick', now) > 30:
                    self.executor_id += 1
                    t = threading.Thread(target=self.executor_loop, args=(self.executor_id,), daemon=True)
                    t.start()
                    self.executor_thread = t
                    _stuck = getattr(self, "_exec_current", "") or "(idle)"
                    _for = time.time() - getattr(self, "_exec_started", time.time())
                    console_log("SYSTEM", f"executor stalled on {_stuck!r} for {_for:.0f}s; restarted. "
                                          f"(backend={getattr(self,'backend','virtualbox')})")
                    dbg("exec", f"STALL on {_stuck!r} after {_for:.0f}s - restarting executor")
                if now - getattr(self, 'listener_tick', now) > 90:
                    self.listener_id += 1
                    t = threading.Thread(target=self.chat_listener_loop, args=(self.listener_id,), daemon=True)
                    t.start()
                    self.listener_thread = t
                    console_log("SYSTEM", "listener thread was stalled; restarted.")
                if getattr(self, 'consecutive_failures', 0) >= 3:
                    self.force_session_refresh = True
                if self.twenty_four_seven_mode and self.active_url and not getattr(self, 'vm_maintenance', False):
                    if not self._vm_is_running():
                        if now - getattr(self, 'vm_start_time', 0) > 30:
                            console_log("SYSTEM", "24/7 mode: vm is down, auto-starting.")
                            self.trigger_command(("startvm", "", "[watchdog]"))
                            self.vm_start_time = now
            except Exception as e:
                console_log("ERROR", f"error watcher crashed: {e}")
                time.sleep(5)

    def _relaunch_self(self, reason=""):
        try:
            console_log("ERROR", f"self-relaunch triggered: {reason}")
            script_path = os.path.abspath(sys.argv[0])
            keep = [a for a in sys.argv[1:] if a.startswith("--multistream") or a == "--no-install" or a == "--quiet"]
            args = [sys.executable, script_path] + keep
            # tell the fresh instance it is a crash relaunch, so it starts
            # minimized and does not pop over the stream
            if "--relaunched" not in args: args.append("--relaunched")
            if platform.system() == "Windows": subprocess.Popen(args, creationflags=0x00000010, close_fds=True)
            else: subprocess.Popen(args, start_new_session=True, close_fds=True)
        except Exception: pass
        os._exit(1)

    def hard_watchdog_loop(self):
        while self.running:
            try:
                hb = getattr(self, 'main_heartbeat', time.time())
                if time.time() - hb > 180:
                    self._relaunch_self("main ui thread frozen >180s")
                try:
                    with open(heartbeat_file, "w") as f: f.write(str(int(time.time())))
                except Exception: pass
            except Exception: pass
            time.sleep(5)

    def start_stats_thread(self):
        if getattr(self, '_stats_thread_started', False): return
        self._stats_thread_started = True
        threading.Thread(target=self.stats_loop, daemon=True).start()

    def stats_loop(self):
        global current_viewers, current_likes
        while self.running:
            try:
                interval = float(self.config.get("stats_interval", 15))
            except Exception:
                interval = 15
            try:
                url = getattr(self, "active_url", None)
                if url and url != "[DEBUG_MODE]":
                    vid = self.resolve_live_video_id(url)
                    if vid and len(vid) == 11:
                        req = urllib.request.Request(f"https://www.youtube.com/watch?v={vid}", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                        with urllib.request.urlopen(req, timeout=10) as response:
                            html = response.read().decode('utf-8', 'ignore')
                        vm = re.search(r'"originalViewCount":"(\d+)"', html) or re.search(r'\{"viewCount":\{"runs":\[\{"text":"([\d,\.]+)"', html) or re.search(r'"viewCount":"(\d+)"', html)
                        if vm: current_viewers = vm.group(1).replace(",", "")
                        lm = re.search(r'"likeCount":"(\d+)"', html) or re.search(r'"defaultText":\{"accessibility":\{"accessibilityData":\{"label":"([\d,\.]+) likes', html)
                        if lm: current_likes = lm.group(1).replace(",", "")
            except Exception:
                pass
            time.sleep(max(5, interval))

    def _add_dashboard_buttons(self):
        strip = tk.Frame(self.tab_dash, bg="#09090B")
        strip.pack(side="bottom", fill="x", padx=20, pady=(0, 12))
        def mk(txt, col, cmd):
            return tk.Button(strip, text=txt, font=("Segoe UI", 10, "bold"), bg=col, fg="white",
                             activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=cmd)
        mk("Pause VM", "#27272A", self.pause_vm).pack(side="left", expand=True, fill="x", padx=4, ipady=5)
        mk("Resume VM", "#27272A", self.resume_vm).pack(side="left", expand=True, fill="x", padx=4, ipady=5)
        mk("Quick Snapshot", "#F59E0B", self.quick_snapshot).pack(side="left", expand=True, fill="x", padx=4, ipady=5)
        mk("Toggle Pause Chat", "#F59E0B", self.toggle_pause_chat).pack(side="left", expand=True, fill="x", padx=4, ipady=5)

    def pause_vm(self):
        threading.Thread(target=lambda: run_vbox(["controlvm", vm_name, "pause"], timeout=15), daemon=True).start()
        self.log("[system]", "vm paused.", "sysmsg")

    def resume_vm(self):
        threading.Thread(target=lambda: run_vbox(["controlvm", vm_name, "resume"], timeout=15), daemon=True).start()
        self.log("[system]", "vm resumed.", "sysmsg")

    def quick_snapshot(self):
        self.trigger_command(("makesnapshot", "", "[console]"))
        self.log("[system]", "quick snapshot requested.", "sysmsg")

    def toggle_pause_chat(self):
        self.chat_paused = not getattr(self, "chat_paused", False)
        self.log("[system]", f"chat {'paused' if self.chat_paused else 'unpaused'}.", "sysmsg")

    def build_osvoting_tab(self):
        wrap = tk.Frame(self.tab_osvote, bg="#09090B"); wrap.pack(fill="both", expand=True, padx=40, pady=30)
        top = tk.Frame(wrap, bg="#09090B"); top.pack(fill="x")
        tk.Label(top, text="OS / VM VOTING", font=("Segoe UI", 13, "bold"), bg="#09090B", fg=self.accent_main).pack(side="left")
        self.osvote_var = tk.BooleanVar(value=self.osvoting_enabled)
        ttk.Checkbutton(top, text="Enable viewer voting", variable=self.osvote_var, command=self.toggle_osvoting, style="Toggle.TCheckbutton").pack(side="right")
        tk.Label(wrap, text="When ON, viewers can vote !changevm to switch OS. Mods can force-switch to any VM below.",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", pady=(2, 18))
        self.osvote_list = tk.Frame(wrap, bg="#09090B"); self.osvote_list.pack(fill="both", expand=True)
        tk.Button(wrap, text="Refresh VM list", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white",
                  bd=0, cursor="hand2", command=self._refresh_osvote).pack(anchor="w", pady=(12, 0), ipady=5, ipadx=12)
        self._refresh_osvote()

    def toggle_osvoting(self):
        self.osvoting_enabled = self.osvote_var.get()
        self.config["osvoting_enabled"] = self.osvoting_enabled
        self.save_settings()
        self.log("[system]", f"os voting {'enabled' if self.osvoting_enabled else 'disabled'}.", "sysmsg")

    def _refresh_osvote(self):
        for w in self.osvote_list.winfo_children(): w.destroy()
        for name in get_all_vbox_vms(vbox_manage_cmd):
            row = tk.Frame(self.osvote_list, bg="#18181B"); row.pack(fill="x", pady=3)
            mark = "  <- current" if name == vm_name else ""
            tk.Label(row, text=name + mark, font=("Consolas", 12), bg="#18181B",
                     fg=(self.accent_main if name == vm_name else "#D4D4D8")).pack(side="left", padx=12, pady=8)
            tk.Button(row, text="Force switch", font=("Segoe UI", 9, "bold"), bg="#8B5CF6", fg="white",
                      bd=0, cursor="hand2", command=lambda n=name: self.switch_to_vm(n)).pack(side="right", padx=10, pady=6, ipadx=8)

    def switch_to_vm(self, name):
        def _go():
            global vm_name
            try:
                vm_name = name
                self.config["vm_name"] = name
                self.save_settings()
                snaps = get_vbox_snapshots(vbox_manage_cmd, name)
                self.current_snapshot = snaps[-1] if snaps else ""
                self.root.after(0, self._update_vm_label)
                self._do_vm_maintenance("remake2", "", "[console]")
                self.root.after(0, self._refresh_osvote)
            except Exception as e:
                console_log("ERROR", f"switch_to_vm failed: {e}")
        threading.Thread(target=_go, daemon=True).start()
        self.log("[system]", f"switching to {name}...", "sysmsg")

    def build_realpc_tab(self):
        wrap = tk.Frame(self.tab_realpc, bg="#09090B"); wrap.pack(fill="both", expand=True, padx=40, pady=30)
        tk.Label(wrap, text="REAL PC - PICO HID CONTROL", font=("Segoe UI", 13, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w")
        tk.Label(wrap, text="Route chat commands to a physical machine through your Pico 2 W over USB serial.",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", pady=(2, 18))
        row1 = tk.Frame(wrap, bg="#09090B"); row1.pack(fill="x", pady=6)
        tk.Label(row1, text="Serial port", font=("Segoe UI", 11, "bold"), bg="#09090B", fg="#D4D4D8", width=12, anchor="e").pack(side="left", padx=(0, 12))
        self.pico_port_cb = ttk.Combobox(row1, values=list_serial_ports(), width=24, font=("Consolas", 11))
        self.pico_port_cb.pack(side="left")
        self.pico_port_cb.set(self.config.get("pico_port", (list_serial_ports() or [""])[0]))
        row2 = tk.Frame(wrap, bg="#09090B"); row2.pack(fill="x", pady=6)
        tk.Label(row2, text="Target", font=("Segoe UI", 11, "bold"), bg="#09090B", fg="#D4D4D8", width=12, anchor="e").pack(side="left", padx=(0, 12))
        self.pico_target_var = tk.StringVar(value=self.pico_target)
        for val, lbl in (("vm", "VM only"), ("pico", "Real PC only"), ("both", "Both")):
            ttk.Radiobutton(row2, text=lbl, value=val, variable=self.pico_target_var,
                            command=self._apply_pico_target, style="Toggle.TCheckbutton").pack(side="left", padx=8)
        row3 = tk.Frame(wrap, bg="#09090B"); row3.pack(fill="x", pady=14)
        tk.Button(row3, text="Connect", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2",
                  command=self.pico_connect).pack(side="left", ipady=6, ipadx=16)
        tk.Button(row3, text="Disconnect", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                  command=self.pico_disconnect).pack(side="left", padx=8, ipady=6, ipadx=12)
        tk.Button(row3, text="Test (types 'hi')", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                  command=self.pico_test).pack(side="left", padx=4, ipady=6, ipadx=12)
        self.pico_status_lbl = tk.Label(wrap, text="status: not connected", font=("Consolas", 11), bg="#09090B", fg="#A1A1AA")
        self.pico_status_lbl.pack(anchor="w", pady=(6, 0))
        tk.Label(wrap, text="Firmware protocol (lines): TYPE <t> | SEND <t> | KEY <k> | COMBO a+b | CLICK | RCLICK | MOVE dx dy | SCROLL n",
                 font=("Consolas", 9), bg="#09090B", fg="#52525b", wraplength=760, justify="left").pack(anchor="w", pady=(18, 0))

    def _apply_pico_target(self):
        self.pico_target = self.pico_target_var.get()
        self.pico_enabled = self.pico_target in ("pico", "both") and self.pico is not None and getattr(self.pico, "ser", None) is not None
        self.config["pico_target"] = self.pico_target
        self.save_settings()

    def pico_connect(self):
        port = self.pico_port_cb.get().strip()
        self.config["pico_port"] = port
        self.save_settings()
        self.pico = PicoController(port)
        ok = self.pico.connect()
        self.pico_target = self.pico_target_var.get()
        self.pico_enabled = ok and self.pico_target in ("pico", "both")
        self.pico_status_lbl.config(text="status: " + self.pico.status, fg=("#10B981" if ok else "#EF4444"))

    def pico_disconnect(self):
        if self.pico: self.pico.close()
        self.pico_enabled = False
        self.pico_status_lbl.config(text="status: not connected", fg="#A1A1AA")

    def pico_test(self):
        if self.pico and getattr(self.pico, "ser", None):
            self.pico.send_line("TYPE hi")
            self.log("[system]", "sent test 'hi' to Pico.", "sysmsg")
        else:
            self.pico_status_lbl.config(text="status: connect first", fg="#EF4444")

    def build_automation_tab(self):
        wrap = tk.Frame(self.tab_auto, bg="#09090B"); wrap.pack(fill="both", expand=True, padx=40, pady=30)
        tk.Label(wrap, text="AUTOMATION - TIMED COMMANDS", font=("Segoe UI", 13, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w")
        tk.Label(wrap, text="Run a command automatically every N seconds (periodic !say, keep-alive key, scheduled revert...).",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", pady=(2, 16))
        form = tk.Frame(wrap, bg="#09090B"); form.pack(fill="x")
        tk.Label(form, text="Every (s)", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.auto_int = tk.Entry(form, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, width=8,
                                 highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981")
        self.auto_int.pack(side="left", padx=(6, 14), ipady=5)
        tk.Label(form, text="Command", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.auto_cmd = tk.Entry(form, font=("Consolas", 11), bg="#18181B", fg="white", bd=0,
                                 highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981")
        self.auto_cmd.pack(side="left", padx=(6, 14), ipady=5, fill="x", expand=True)
        tk.Button(form, text="Add", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2",
                  command=self.add_automation).pack(side="left", ipady=5, ipadx=14)
        self.auto_listbox = tk.Listbox(wrap, bg="#18181B", fg="#00E5FF", font=("Consolas", 12), bd=0, highlightthickness=0)
        self.auto_listbox.pack(fill="both", expand=True, pady=16)
        arow2 = tk.Frame(wrap, bg="#09090B"); arow2.pack(fill="x", pady=(8, 0))
        tk.Button(arow2, text="Delete selected", font=("Segoe UI", 10, "bold"), bg="#EF4444", fg="white", bd=0, cursor="hand2",
                  command=self.del_automation).pack(side="left", ipady=5, ipadx=12)
        tk.Button(arow2, text="Run selected now", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2",
                  command=self._run_automation_now).pack(side="left", padx=8, ipady=5, ipadx=12)
        tk.Button(arow2, text="Clear all", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                  command=self._clear_automations).pack(side="left", padx=4, ipady=5, ipadx=12)
        tk.Label(wrap, text="Quick presets:", bg="#09090B", fg="#A1A1AA", font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 2))
        prow = tk.Frame(wrap, bg="#09090B"); prow.pack(anchor="w")
        presets = [("Keep-alive key /60s", 60, "!key f15"), ("Auto snapshot /600s", 600, "makesnapshot auto"),
                   ("Follow reminder /300s", 300, "!say Type !help for commands"), ("Auto revert /900s", 900, "revert")]
        for lbl, iv, cmd in presets:
            tk.Button(prow, text=lbl, font=("Segoe UI", 9, "bold"), bg="#8B5CF6", fg="white", bd=0, cursor="hand2",
                      command=lambda i=iv, c=cmd: self._add_automation_preset(i, c)).pack(side="left", padx=4, pady=4, ipady=4, ipadx=6)
        self._refresh_auto_list()

    def _refresh_auto_list(self):
        self.auto_listbox.delete(0, "end")
        for a in self.automations:
            self.auto_listbox.insert("end", f"every {a['interval']}s  ->  {a['cmd']}")

    def add_automation(self):
        try: iv = float(self.auto_int.get().strip())
        except Exception: return
        cmd = self.auto_cmd.get().strip()
        if not cmd or iv <= 0: return
        self.automations.append({"interval": iv, "cmd": cmd, "last": 0})
        self.config["automations"] = self.automations
        self.save_settings()
        self._refresh_auto_list()
        self.auto_cmd.delete(0, "end")

    def del_automation(self):
        sel = self.auto_listbox.curselection()
        if not sel: return
        del self.automations[sel[0]]
        self.config["automations"] = self.automations
        self.save_settings()
        self._refresh_auto_list()

    def automation_loop(self):
        while self.running:
            now = time.time()
            for a in list(self.automations):
                try:
                    if now - a.get("last", 0) >= a["interval"]:
                        a["last"] = now
                        self.parse_command(a["cmd"], "[console]", is_mod=True, is_owner=True)
                except Exception: pass
            time.sleep(1)

    def _run_automation_now(self):
        sel = self.auto_listbox.curselection()
        if not sel: return
        a = self.automations[sel[0]]
        self.parse_command(a["cmd"], "[console]", is_mod=True, is_owner=True)

    def _clear_automations(self):
        self.automations = []
        self.config["automations"] = self.automations
        self.save_settings()
        self._refresh_auto_list()

    def _add_automation_preset(self, interval, cmd):
        self.automations.append({"interval": interval, "cmd": cmd, "last": 0})
        self.config["automations"] = self.automations
        self.save_settings()
        self._refresh_auto_list()

    def build_eventlog_tab(self):
        wrap = tk.Frame(self.tab_events, bg="#09090B"); wrap.pack(fill="both", expand=True, padx=30, pady=16)
        bar = tk.Frame(wrap, bg="#09090B"); bar.pack(fill="x")
        tk.Label(bar, text="EVENT LOG", font=("Segoe UI", 13, "bold"), bg="#09090B", fg=self.accent_main).pack(side="left")
        self._eventlog_src = modlogs_file
        self._eventlog_auto = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Auto-refresh", variable=self._eventlog_auto, style="Toggle.TCheckbutton").pack(side="right", padx=(6, 0))
        for lbl, fn in (("Live Console", "__console__"), ("Mod/Owner", modlogs_file), ("Votes", voteslogs_file), ("Music", musiclogs_file), ("All msgs", allmsglogs_file)):
            tk.Button(bar, text=lbl, font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                      command=lambda f=fn: self._load_log(f)).pack(side="right", padx=3, ipady=4, ipadx=7)
        sbar = tk.Frame(wrap, bg="#09090B"); sbar.pack(fill="x", pady=(8, 0))
        tk.Label(sbar, text="Filter:", bg="#09090B", fg="#A1A1AA", font=("Segoe UI", 9)).pack(side="left")
        self._eventlog_filter = tk.Entry(sbar, font=("Consolas", 10), bg="#18181B", fg="white", bd=0,
                                         highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self._eventlog_filter.pack(side="left", fill="x", expand=True, padx=8, ipady=3)
        self._eventlog_filter.bind("<KeyRelease>", lambda e: self._load_log(self._eventlog_src))
        tk.Button(sbar, text="Refresh", font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                  command=lambda: self._load_log(self._eventlog_src)).pack(side="left", padx=3, ipady=4, ipadx=8)
        self.event_text = scrolledtext.ScrolledText(wrap, font=("Consolas", 10), bg="#09090B", fg="#D4D4D8", bd=0,
                                                     highlightthickness=1, highlightbackground="#27272A")
        self.event_text.pack(fill="both", expand=True, pady=(10, 0))
        self.event_text.tag_config("cmd", foreground="#00E5FF")
        self.event_text.tag_config("err", foreground="#EF4444")
        self.event_text.tag_config("mod", foreground="#10B981")
        self.event_text.tag_config("dim", foreground="#71717a")
        self._load_log(modlogs_file)
        self._eventlog_tick()

    def _eventlog_tick(self):
        try:
            if getattr(self, "_eventlog_auto", None) and self._eventlog_auto.get():
                self._load_log(self._eventlog_src)
        except Exception: pass
        if self.running:
            self.root.after(2500, self._eventlog_tick)

    def _load_log(self, path):
        self._eventlog_src = path
        flt = ""
        try: flt = self._eventlog_filter.get().strip().lower()
        except Exception: pass
        self.event_text.configure(state="normal")
        self.event_text.delete("1.0", "end")
        def emit(line, tag=None):
            if flt and flt not in line.lower(): return
            self.event_text.insert("end", line + "\n", tag or ())
        try:
            if path == "__console__":
                for m in list(getattr(self, "recent_bot_messages", []))[-400:]:
                    tag = "err" if "[err" in m.lower() or "[error" in m.lower() else ("cmd" if "running" in m.lower() else "dim")
                    emit(m, tag)
            elif not os.path.exists(path):
                emit("(no entries yet)", "dim")
            elif path == allmsglogs_file:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f.readlines()[-500:]:
                        try:
                            e = json.loads(line.strip().rstrip(","))
                            msg = e.get("message", "")
                            emit(f"[{e.get('time','')}] {e.get('username','')}: {msg}", "cmd" if msg.startswith("!") else None)
                        except Exception: pass
            else:
                with open(path, "r", encoding="utf-8") as f: data = json.load(f)
                for e in data[-500:]:
                    t = e.get("time", "")
                    if "command" in e:
                        emit(f"[{t}] {e.get('username','')}  ->  {e.get('command','')}", "cmd")
                    elif "vote" in e:
                        emit(f"[{t}] {e.get('action','')}  {e.get('user','')}  {e.get('vote','')}  {e.get('progress','')}", "mod")
                    elif "title" in e:
                        emit(f"[{t}] {e.get('action','')}  {e.get('user','')}  {e.get('title','')}", None)
                    else:
                        emit(f"[{t}] " + json.dumps({k: v for k, v in e.items() if k != 'time'}), "dim")
        except Exception as e:
            emit(f"(error reading log: {e})", "err")
        self.event_text.see("end")
        self.event_text.configure(state="disabled")

    def build_appearance_tab(self):
        wrap = self.make_scrollable(self.tab_appear)
        tk.Label(wrap, text="APPEARANCE", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=40, pady=(26, 2))
        tk.Label(wrap, text="Full UI themes repaint the whole app. Accent colors tint highlights.",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=40, pady=(0, 16))
        tk.Label(wrap, text="UI THEME", font=("Segoe UI", 11, "bold"), bg="#09090B", fg="#10B981").pack(anchor="w", padx=40)
        trow = tk.Frame(wrap, bg="#09090B"); trow.pack(anchor="w", padx=40, pady=(6, 20))
        themes = (("Original", "original", "#18181B", "#00E5FF"),
                  ("Better", "better", "#151823", "#8B5CF6"),
                  ("God", "god", "#151024", "#A78BFA"),
                  ("Liquid Glass", "glass", "#141A28", "#38BDF8"),
                  ("Aurora", "aurora", "#151228", "#C084FC"),
                  ("Light", "light", "#FFFFFF", "#2563EB"),
                  ("Daylight", "daylight", "#FBFCFE", "#0EA5E9"))
        for name, key, card, acc in themes:
            b = tk.Frame(trow, bg=card, bd=0); b.pack(side="left", padx=8)
            tk.Label(b, text=name, font=("Segoe UI", 13, "bold"), bg=card, fg=acc).pack(padx=26, pady=(16, 2))
            tk.Label(b, text={"original": "clean & dark", "better": "richer, softer", "god": "premium violet",
                              "glass": "frosted, layered", "aurora": "violet glass",
                              "light": "bright & clean", "daylight": "soft daylight"}[key],
                     font=("Segoe UI", 9), bg=card, fg="#A1A1AA").pack(padx=26, pady=(0, 10))
            tk.Button(b, text="Apply", font=("Segoe UI", 9, "bold"), bg=acc, fg="black", bd=0, cursor="hand2",
                      command=lambda k=key: self.apply_theme(k)).pack(padx=26, pady=(0, 16), ipadx=18, ipady=3)
        tk.Button(wrap, text="Toggle Dark / Light", font=("Segoe UI", 10, "bold"), bg="#8B5CF6", fg="white",
                  bd=0, cursor="hand2", command=self.toggle_dark_light).pack(anchor="w", padx=40, pady=(0, 18), ipady=6, ipadx=16)
        _ctk_row = tk.Frame(wrap, bg="#09090B"); _ctk_row.pack(anchor="w", padx=40, pady=(0, 18))
        tk.Button(_ctk_row, text=("CustomTkinter: ON" if self.config.get("use_customtkinter") else "CustomTkinter: OFF"),
                  font=("Segoe UI", 10, "bold"), bg=("#10B981" if self.config.get("use_customtkinter") else "#27272A"),
                  fg=("black" if self.config.get("use_customtkinter") else "white"), bd=0, cursor="hand2",
                  command=self.toggle_ctk).pack(side="left", ipady=6, ipadx=16)
        tk.Label(_ctk_row, text=("  installed" if ctk_available else "  not installed - pip install customtkinter"),
                 bg="#09090B", fg=("#10B981" if ctk_available else "#F59E0B"), font=("Segoe UI", 9)).pack(side="left", padx=8)
        _tb_row = tk.Frame(wrap, bg="#09090B"); _tb_row.pack(anchor="w", padx=40, pady=(0, 18))
        tk.Button(_tb_row, text=("ttkbootstrap: ON" if self.config.get("use_ttkbootstrap", True) else "ttkbootstrap: OFF"),
                  font=("Segoe UI", 10, "bold"), bg=("#10B981" if self.config.get("use_ttkbootstrap", True) else "#27272A"),
                  fg=("black" if self.config.get("use_ttkbootstrap", True) else "white"), bd=0, cursor="hand2",
                  command=self.toggle_ttkbootstrap).pack(side="left", ipady=6, ipadx=16)
        tk.Label(_tb_row, text=("  installed" if tb_available else "  not installed - pip install ttkbootstrap"),
                 bg="#09090B", fg=("#10B981" if tb_available else "#F59E0B"), font=("Segoe UI", 9)).pack(side="left", padx=8)
        tk.Label(wrap, text="ACCENT COLOR", font=("Segoe UI", 11, "bold"), bg="#09090B", fg="#10B981").pack(anchor="w", padx=40)
        sw = tk.Frame(wrap, bg="#09090B"); sw.pack(anchor="w", padx=40, pady=(6, 30))
        for name, col in (("Cyan", "#00E5FF"), ("Violet", "#8B5CF6"), ("Green", "#10B981"),
                          ("Amber", "#F59E0B"), ("Rose", "#EF4444"), ("Blue", "#3B82F6"),
                          ("Pink", "#EC4899"), ("Teal", "#14B8A6")):
            tk.Button(sw, text=name, font=("Segoe UI", 10, "bold"), bg=col, fg="black", bd=0, cursor="hand2",
                      command=lambda c=col: self.apply_accent(c)).pack(side="left", padx=5, ipady=8, ipadx=12)

    def apply_accent(self, col):
        self.accent_main = col
        self.config["accent_color"] = col
        self.save_settings()
        try:
            style = ttk.Style()
            style.map("TNotebook.Tab", background=[("selected", col)], foreground=[("selected", "#000000")])
        except Exception: pass

    def build_obs_tab(self):
        wrap = tk.Frame(self.tab_obs, bg="#09090B"); wrap.pack(fill="both", expand=True, padx=40, pady=26)
        tk.Label(wrap, text="OBS CONNECTION", font=("Segoe UI", 13, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w")
        grid = tk.Frame(wrap, bg="#09090B"); grid.pack(anchor="w", pady=(10, 6))
        self._obs_entries = {}
        for i, (lbl, val) in enumerate((("Host", obs_host), ("Port", obs_port), ("Password", obs_password))):
            tk.Label(grid, text=lbl, bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold"), width=9, anchor="e").grid(row=i, column=0, padx=(0, 10), pady=4)
            e = tk.Entry(grid, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, width=26,
                         highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main,
                         show=("*" if lbl == "Password" else ""))
            e.grid(row=i, column=1, pady=4, ipady=5); e.insert(0, str(val))
            self._obs_entries[lbl] = e
        tk.Button(wrap, text="Save OBS settings", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2",
                  command=self.save_obs).pack(anchor="w", pady=(6, 14), ipady=6, ipadx=14)
        tk.Label(wrap, text="Switch scene:", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        srow = tk.Frame(wrap, bg="#09090B"); srow.pack(anchor="w", pady=(4, 10))
        for lbl, scene in (("Main", obs_scene_main), ("Revert", obs_scene_revert), ("Starting", obs_scene_starting),
                           ("Change", obs_scene_changevm), ("Error", obs_scene_error)):
            tk.Button(srow, text=lbl, font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                      command=lambda s=scene: set_obs_scene(s)).pack(side="left", padx=4, ipady=5, ipadx=10)
        tk.Label(wrap, text="Music:", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(6, 0))
        mrow = tk.Frame(wrap, bg="#09090B"); mrow.pack(anchor="w", pady=(4, 12))
        for lbl, act in (("Play", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"), ("Pause", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE"),
                         ("Stop", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP"), ("Restart", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")):
            tk.Button(mrow, text=lbl, font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                      command=lambda a=act: self.obs_media_action(a)).pack(side="left", padx=4, ipady=5, ipadx=10)
        tk.Button(mrow, text="Skip song", font=("Segoe UI", 9, "bold"), bg="#8B5CF6", fg="white", bd=0, cursor="hand2",
                  command=self._skip_song).pack(side="left", padx=8, ipady=5, ipadx=10)
        tk.Label(wrap, text="IRONCONTROL RELAY", font=("Segoe UI", 13, "bold"), bg="#09090B", fg="#8B5CF6").pack(anchor="w", pady=(6, 8))
        rrow = tk.Frame(wrap, bg="#09090B"); rrow.pack(anchor="w")
        tk.Button(rrow, text="Launch Relay", font=("Segoe UI", 10, "bold"), bg="#8B5CF6", fg="white", bd=0, cursor="hand2",
                  command=self.launch_relay).pack(side="left", ipady=6, ipadx=14)
        tk.Button(rrow, text="Control panel", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                  command=lambda: self._open_relay("/control")).pack(side="left", padx=8, ipady=6, ipadx=10)
        tk.Button(rrow, text="LAN clients", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                  command=lambda: self._open_relay("/clients")).pack(side="left", padx=4, ipady=6, ipadx=10)
        frow = tk.Frame(wrap, bg="#09090B"); frow.pack(anchor="w", pady=(14, 0), fill="x")
        tk.Label(frow, text="Flash:", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.flash_entry = tk.Entry(frow, font=("Consolas", 11), bg="#18181B", fg="white", bd=0,
                                    highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.flash_entry.pack(side="left", padx=8, ipady=5, fill="x", expand=True)
        tk.Button(frow, text="Send", font=("Segoe UI", 10, "bold"), bg=self.accent_main, fg="black", bd=0, cursor="hand2",
                  command=self.send_flash_ui).pack(side="left", padx=(8, 0), ipady=5, ipadx=14)

    def _skip_song(self):
        self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")
        self.current_song = None
        self.log("[system]", "song skipped.", "sysmsg")

    def save_obs(self):
        global obs_host, obs_port, obs_password
        try:
            obs_host = self._obs_entries["Host"].get().strip()
            obs_port = int(self._obs_entries["Port"].get().strip())
            obs_password = self._obs_entries["Password"].get()
            self.config["obs_host"] = obs_host
            self.config["obs_port"] = obs_port
            self.save_settings()
            self.log("[system]", "obs settings saved.", "sysmsg")
        except Exception as e:
            self.log("[system]", f"[error] obs save: {e}", "err")

    def launch_relay(self):
        try:
            base = os.path.dirname(os.path.abspath(sys.argv[0]))
            target = None
            for cand in ("relay_plus.py", "relay_local.py"):
                if os.path.exists(os.path.join(base, cand)):
                    target = os.path.join(base, cand); break
            if not target:
                self.log("[system]", "[warn] relay_plus.py / relay_local.py not found next to this script.", "err")
                return
            args = [sys.executable, target]
            vid = getattr(self, "active_url", "")
            if vid: args.append(vid)
            if platform.system() == "Windows":
                self.relay_proc = subprocess.Popen(args, creationflags=0x00000010, close_fds=True)
            else:
                self.relay_proc = subprocess.Popen(args, start_new_session=True, close_fds=True)
            self.log("[system]", f"relay launched ({os.path.basename(target)}).", "sysmsg")
        except Exception as e:
            self.log("[system]", f"[error] launch relay: {e}", "err")

    def _open_relay(self, path):
        try:
            import webbrowser
            webbrowser.open(f"http://{self.config.get('relay_host','127.0.0.1')}:{int(self.config.get('relay_port',8080))}{path}")
        except Exception: pass

    def send_flash_ui(self):
        txt = self.flash_entry.get().strip()
        if not txt: return
        self.send_flash(txt)
        self.flash_entry.delete(0, "end")

    def send_flash(self, text, kind="info", dur=6):
        try:
            app_flash.update({"text": text, "kind": kind, "dur": dur, "n": app_flash.get("n", 0) + 1})
        except Exception: pass
        def _post():
            try:
                host = self.config.get("relay_host", "127.0.0.1")
                port = int(self.config.get("relay_port", 8080))
                data = json.dumps({"text": text, "kind": kind, "dur": dur}).encode()
                req = urllib.request.Request(f"http://{host}:{port}/api/flash", data=data,
                                             headers={"Content-Type": "application/json"}, method="POST")
                urllib.request.urlopen(req, timeout=3)
            except Exception: pass
        threading.Thread(target=_post, daemon=True).start()
        self.log("[system]", f"flashed: {text}", "sysmsg")

    def _bind_secret_replay(self):
        # secret: 5 quick clicks on the status label triggers a full replay
        self._secret_clicks = []
        def _hit(_e=None):
            now = time.time()
            self._secret_clicks = [t for t in self._secret_clicks if now - t < 2.0] + [now]
            if len(self._secret_clicks) >= 5:
                self._secret_clicks = []
                try: self.tabview.select(self.tab_replay)
                except Exception: pass
                self.start_replay()
        try:
            if hasattr(self, "lbl_status"): self.lbl_status.bind("<Button-1>", _hit)
        except Exception: pass

    # ── UI helpers ───────────────────────────────────────────────────────────
    def make_scrollable(self, parent):
        canvas = tk.Canvas(parent, bg="#09090B", bd=0, highlightthickness=0)
        vs = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#09090B")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.configure(yscrollcommand=vs.set)
        canvas.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        def _wheel(e):
            try: canvas.yview_scroll(int(-1 * (e.delta / 120)) if e.delta else (-1 if e.num == 4 else 1), "units")
            except Exception: pass
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind_all_target = None
            inner.bind(seq, _wheel); canvas.bind(seq, _wheel)
        return inner

    def _grid_buttons(self, parent, items, cols=4, pady=4):
        frame = tk.Frame(parent, bg="#09090B")
        for i, (lbl, col, cmd) in enumerate(items):
            r, c = divmod(i, cols)
            tk.Button(frame, text=lbl, font=("Segoe UI", 9, "bold"), bg=col, fg=("black" if col not in ("#27272A", "#3F3F46") else "white"),
                      activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2",
                      command=cmd).grid(row=r, column=c, sticky="we", padx=4, pady=pady, ipady=6)
        for c in range(cols):
            frame.columnconfigure(c, weight=1, uniform="btns")
        return frame

    def _bind_tab_scroll(self):
        def _scroll(e):
            try:
                tabs = self.tabview.tabs()
                if not tabs: return
                cur = self.tabview.index(self.tabview.select())
                nxt = cur + (1 if (getattr(e, "delta", 0) < 0 or getattr(e, "num", 0) == 5) else -1)
                nxt = max(0, min(len(tabs) - 1, nxt))
                self.tabview.select(tabs[nxt])
            except Exception: pass
        try:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.tabview.side.bind(seq, _scroll)
        except Exception: pass

    # ── THEME ENGINE ─────────────────────────────────────────────────────────
    THEMES = {
        "original": {"bg": "#09090B", "card": "#18181B", "border": "#27272A", "text": "#D4D4D8",
                     "side": "#0C0C11", "panel": "#0F0F15", "muted": "#8A8A96", "dark": True},
        "better":   {"bg": "#0B0D14", "card": "#151823", "border": "#232838", "text": "#E6E9F2",
                     "side": "#0D1018", "panel": "#11141D", "muted": "#8D93A6", "dark": True},
        "god":      {"bg": "#08060F", "card": "#151024", "border": "#2B2145", "text": "#F2EEFF",
                     "side": "#0B0818", "panel": "#120E20", "muted": "#9A8FB8", "dark": True},
        "light":    {"bg": "#F1F3F8", "card": "#FFFFFF", "border": "#DDE1EA", "text": "#16181F",
                     "side": "#FFFFFF", "panel": "#F7F8FC", "muted": "#5C6270", "dark": False},
        "glass":    {"bg": "#070A12", "card": "#141A28", "border": "#2A3550", "text": "#EAF0FF",
                     "side": "#0A0F1A", "panel": "#111827", "muted": "#8FA0BF", "dark": True},
        "aurora":   {"bg": "#06080F", "card": "#151228", "border": "#332A55", "text": "#F0EBFF",
                     "side": "#0A0817", "panel": "#120F22", "muted": "#9C8FC4", "dark": True},
        "daylight": {"bg": "#EDEFF5", "card": "#FBFCFE", "border": "#D5DAE5", "text": "#101319",
                     "side": "#F7F8FC", "panel": "#FFFFFF", "muted": "#565C6B", "dark": False},
    }

    def apply_theme(self, name):
        """Repaint the whole app - background, cards, borders, text, sidebar,
        chat panel and status bar - for the chosen palette (dark or light)."""
        pal = self.THEMES.get(name, self.THEMES["original"])
        old = getattr(self, "_theme_palette", self.THEMES["original"])
        remap = {}
        for role in ("bg", "card", "border", "text", "side", "panel", "muted"):
            if role in old and role in pal:
                remap[old[role]] = pal[role]
        for role, val in self.THEMES["original"].items():
            if isinstance(val, str) and role in pal:
                remap.setdefault(val, pal[role])
        # chrome colours used by the sidebar shell
        for extra_old, role in (("#0C0C11", "side"), ("#0F0F15", "panel"), ("#08080C", "panel"),
                                ("#15151C", "card"), ("#1A1A24", "card"), ("#1C1C24", "card"),
                                ("#0A0A0F", "bg"), ("#9A9AA6", "muted"), ("#8A8A96", "muted"),
                                ("#A1A1AA", "muted"), ("#D4D4D8", "text"), ("#E4E4EC", "text")):
            remap.setdefault(extra_old, pal.get(role, pal["bg"]))
        if not pal.get("dark", True):
            remap.setdefault("#FFFFFF", pal["text"])
            remap.setdefault("white", pal["text"])

        def walk(w):
            for opt in ("bg", "background", "fg", "foreground", "activebackground",
                        "highlightbackground", "insertbackground", "troughcolor"):
                try:
                    cur = str(w.cget(opt))
                    if cur in remap and remap[cur] != cur:
                        w.configure(**{opt: remap[cur]})
                except Exception: pass
            for ch in w.winfo_children():
                walk(ch)

        try: self.root.configure(bg=pal["bg"])
        except Exception: pass
        walk(self.root)
        try:
            style = ttk.Style()
            style.configure(".", background=pal["bg"], foreground=pal["text"])
            style.configure("TFrame", background=pal["bg"])
            style.configure("Card.TFrame", background=pal["card"])
            style.configure("TLabel", background=pal["bg"], foreground=pal["text"])
            style.configure("Header.TLabel", background=pal["bg"], foreground=pal["text"])
            style.configure("TNotebook", background=pal["bg"])
            style.configure("TNotebook.Tab", background=pal["card"], foreground=pal["muted"])
            style.map("TNotebook.Tab", background=[("selected", self.accent_main)],
                      foreground=[("selected", "#000000" if pal.get("dark", True) else "#FFFFFF")])
            style.configure("Toggle.TCheckbutton", background=pal["card"], foreground=pal["text"])
            style.configure("Vertical.TScrollbar", background=pal["border"], troughcolor=pal["bg"],
                            bordercolor=pal["bg"], arrowcolor=pal["muted"],
                            darkcolor=pal["border"], lightcolor=pal["border"])
            style.configure("TCombobox", fieldbackground=pal["bg"], background=pal["card"], foreground=pal["text"])
            self.root.option_add('*TCombobox*Listbox.background', pal["card"])
            self.root.option_add('*TCombobox*Listbox.foreground', pal["text"])
        except Exception: pass
        # re-tint the sidebar selection so the active page still reads correctly
        try:
            nav = getattr(self, "tabview", None)
            if nav is not None and hasattr(nav, "select") and nav._current is not None:
                nav.select(nav._current)
        except Exception: pass
        if self.config.get("use_ttkbootstrap", True):
            apply_bootstrap_theme(name)
        if self.config.get("use_customtkinter", False) and ctk_available:
            try: ctk.set_appearance_mode("dark" if pal.get("dark", True) else "light")
            except Exception: pass
        self._theme_palette = pal
        self.ui_theme = name
        self.config["ui_theme"] = name
        self.save_settings()
        self.log("[system]", f"theme set to {name}.", "sysmsg")

    def toggle_ctk(self):
        if not ctk_available:
            self.log("[system]", "[warn] customtkinter not installed. run: pip install customtkinter", "err")
            return
        new = not self.config.get("use_customtkinter", False)
        self.config["use_customtkinter"] = new
        self.save_settings()
        self.log("[system]", f"customtkinter {'enabled' if new else 'disabled'} - restart to apply.", "sysmsg")

    def toggle_ttkbootstrap(self):
        if not tb_available:
            self.log("[system]", "[warn] ttkbootstrap not installed. run: pip install ttkbootstrap", "err")
            return
        new = not self.config.get("use_ttkbootstrap", True)
        self.config["use_ttkbootstrap"] = new
        self.save_settings()
        if new: apply_bootstrap_theme(getattr(self, "ui_theme", "original"))
        self.log("[system]", f"ttkbootstrap {'enabled' if new else 'disabled'} - restart to fully apply.", "sysmsg")

    def toggle_dark_light(self):
        cur = getattr(self, "ui_theme", "original")
        is_dark = self.THEMES.get(cur, {}).get("dark", True)
        self.apply_theme("light" if is_dark else "original")

    # ── KEYS ─────────────────────────────────────────────────────────────────
    def _minimize_window(self):
        try:
            self.root.iconify()
        except Exception:
            pass

    def _vm_action(self, action, arg=""):
        """Dashboard/console VM control. Runs the maintenance action directly in
        a thread so it works for BOTH backends and reports what actually happened,
        instead of pushing into the chat queue where a silent failure hides it."""
        be = getattr(self, "backend", "virtualbox")
        dbg("vm", f"console requested '{action}' (backend={be})")
        self.log("[system]", f"{action} requested ({be})...", "sysmsg")
        if be == "vmware":
            vm = self._vmware()
            if not vm.available():
                self.log("[system]", "[error] vmrun.exe not found - set its path on the VMS tab.", "err")
                return
            if not self.vmx_path:
                self.log("[system]", "[error] no .vmx selected - pick one on the VMS or VM Config tab.", "err")
                return
        threading.Thread(target=lambda: self._do_vm_maintenance(action, arg, "[console]"), daemon=True).start()

    def _send_cmd(self, cmd, arg=""):
        self.trigger_command((cmd, arg, "[console]"))

    def _send_chain(self, chain):
        self.trigger_command_chain([(c, a, "[console]") for c, a in chain])

    def build_keys_tab(self):
        wrap = self.make_scrollable(self.tab_keys)
        tk.Label(wrap, text="KEYBOARD", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 10))
        srow = tk.Frame(wrap, bg="#09090B"); srow.pack(fill="x", padx=30, pady=(0, 14))
        self.keys_text = tk.Entry(srow, font=("Consolas", 12), bg="#18181B", fg="white", bd=0,
                                  highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.keys_text.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(srow, text="Type", font=("Segoe UI", 10, "bold"), bg=self.accent_main, fg="black", bd=0, cursor="hand2",
                  command=lambda: self._send_cmd("!type", self.keys_text.get())).pack(side="left", padx=(8, 0), ipady=5, ipadx=12)
        tk.Button(srow, text="Send (+Enter)", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2",
                  command=lambda: self._send_cmd("!send", self.keys_text.get())).pack(side="left", padx=(6, 0), ipady=5, ipadx=12)
        common = ["enter", "esc", "tab", "space", "backspace", "delete", "up", "down", "left", "right",
                  "home", "end", "pageup", "pagedown", "insert", "capslock"]
        tk.Label(wrap, text="Keys", font=("Segoe UI", 10, "bold"), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30)
        self._grid_buttons(wrap, [(k, "#27272A", lambda kk=k: self._send_cmd("!key", kk)) for k in common], cols=8).pack(fill="x", padx=26, pady=(4, 12))
        fkeys = [f"f{i}" for i in range(1, 13)]
        self._grid_buttons(wrap, [(k, "#27272A", lambda kk=k: self._send_cmd("!key", kk)) for k in fkeys], cols=12).pack(fill="x", padx=26, pady=(0, 12))
        tk.Label(wrap, text="Combos", font=("Segoe UI", 10, "bold"), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30)
        combos = [("Win+R", "win+r"), ("Win+D", "win+d"), ("Win+E", "win+e"), ("Alt+Tab", "alt+tab"),
                  ("Alt+F4", "alt+f4"), ("Ctrl+C", "ctrl+c"), ("Ctrl+V", "ctrl+v"), ("Ctrl+A", "ctrl+a"),
                  ("Ctrl+Z", "ctrl+z"), ("Ctrl+Shift+Esc", "ctrl+shift+esc"), ("Ctrl+Alt+Del", "ctrl+alt+delete"), ("Win", "win")]
        self._grid_buttons(wrap, [(lbl, "#8B5CF6", lambda cc=c: self._send_cmd("!combo", cc)) for lbl, c in combos], cols=4).pack(fill="x", padx=26, pady=(4, 24))

    # ── MOUSE ────────────────────────────────────────────────────────────────
    def build_mouse_tab(self):
        wrap = self.make_scrollable(self.tab_mouse)
        tk.Label(wrap, text="MOUSE", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 12))
        self._grid_buttons(wrap, [
            ("Move Up", "#27272A", lambda: self._send_cmd("!move", "up 60")),
            ("Move Down", "#27272A", lambda: self._send_cmd("!move", "down 60")),
            ("Move Left", "#27272A", lambda: self._send_cmd("!move", "left 60")),
            ("Move Right", "#27272A", lambda: self._send_cmd("!move", "right 60")),
        ], cols=4).pack(fill="x", padx=26, pady=(0, 10))
        self._grid_buttons(wrap, [
            ("Left Click", "#00E5FF", lambda: self._send_cmd("!click")),
            ("Right Click", "#8B5CF6", lambda: self._send_cmd("!rclick")),
            ("Middle Click", "#10B981", lambda: self._send_cmd("!mclick")),
            ("Double Click", "#00E5FF", lambda: self._send_cmd("!click", "2")),
            ("Scroll Up", "#27272A", lambda: self._send_cmd("!scroll", "3")),
            ("Scroll Down", "#27272A", lambda: self._send_cmd("!scroll", "-3")),
        ], cols=3).pack(fill="x", padx=26, pady=(0, 14))
        arow = tk.Frame(wrap, bg="#09090B"); arow.pack(fill="x", padx=30, pady=(0, 20))
        tk.Label(arow, text="Go to  X", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.abs_x = tk.Entry(arow, width=7, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A"); self.abs_x.pack(side="left", padx=6, ipady=4)
        tk.Label(arow, text="Y", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.abs_y = tk.Entry(arow, width=7, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A"); self.abs_y.pack(side="left", padx=6, ipady=4)
        tk.Button(arow, text="Go", font=("Segoe UI", 10, "bold"), bg=self.accent_main, fg="black", bd=0, cursor="hand2",
                  command=lambda: self._send_cmd("!abs", f"{self.abs_x.get()} {self.abs_y.get()}")).pack(side="left", padx=8, ipady=4, ipadx=14)

    # ── MACROS ───────────────────────────────────────────────────────────────
    def build_macros_tab(self):
        wrap = self.make_scrollable(self.tab_macros)
        tk.Label(wrap, text="QUICK MACROS", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 4))
        tk.Label(wrap, text="One-click command sequences. Build custom ones in the Commands tab.",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30, pady=(0, 14))
        self._grid_buttons(wrap, [
            ("Open Run", "#8B5CF6", lambda: self._send_cmd("!combo", "win+r")),
            ("Open Notepad", "#8B5CF6", lambda: self._send_chain([("!combo", "win+r"), ("!wait", "0.6"), ("!send", "notepad")])),
            ("Open Browser", "#8B5CF6", lambda: self._send_chain([("!combo", "win+r"), ("!wait", "0.6"), ("!send", "https://youtube.com")])),
            ("Minimize All", "#27272A", lambda: self._send_cmd("!combo", "win+d")),
            ("Task Manager", "#27272A", lambda: self._send_cmd("!combo", "ctrl+shift+esc")),
            ("File Explorer", "#27272A", lambda: self._send_cmd("!combo", "win+e")),
            ("Select All", "#27272A", lambda: self._send_cmd("!combo", "ctrl+a")),
            ("Screenshot", "#10B981", lambda: self._send_cmd("!key", "printscreen")),
        ], cols=4).pack(fill="x", padx=26, pady=(0, 20))

    # ── MODERATION ───────────────────────────────────────────────────────────
    def build_moderation_tab(self):
        wrap = self.make_scrollable(self.tab_mod)
        tk.Label(wrap, text="MODERATION", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 12))
        urow = tk.Frame(wrap, bg="#09090B"); urow.pack(fill="x", padx=30, pady=(0, 12))
        tk.Label(urow, text="User", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.mod_user = tk.Entry(urow, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.mod_user.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        self._grid_buttons(wrap, [
            ("Blacklist", "#EF4444", lambda: self._mod_blacklist(True)),
            ("Un-blacklist", "#10B981", lambda: self._mod_blacklist(False)),
            ("Pause Chat", "#F59E0B", lambda: self._send_cmd("__pausechat__") if False else self.toggle_pause_chat()),
            ("Clear Votes", "#27272A", self._mod_clear_votes),
        ], cols=4).pack(fill="x", padx=26, pady=(0, 10))
        self.mod_status = tk.Label(wrap, text="", font=("Consolas", 10), bg="#09090B", fg="#A1A1AA"); self.mod_status.pack(anchor="w", padx=30, pady=(4, 8))
        tk.Label(wrap, text="Blacklisted users", font=("Segoe UI", 10, "bold"), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30)
        self.mod_list = tk.Listbox(wrap, bg="#18181B", fg="#EF4444", font=("Consolas", 11), bd=0, highlightthickness=0, height=8)
        self.mod_list.pack(fill="x", padx=30, pady=(4, 20))
        self._refresh_mod_list()

    def _mod_blacklist(self, add):
        u = self.mod_user.get().replace("@", "").lower().strip()
        if not u: return
        if add: self.blacklisted_users.add(u)
        else: self.blacklisted_users.discard(u)
        self.mod_status.config(text=f"{'blacklisted' if add else 'un-blacklisted'} {u}")
        self._refresh_mod_list()

    def _mod_clear_votes(self):
        with self.vote_lock: self.active_votes.clear()
        self.mod_status.config(text="all votes cleared")

    def _refresh_mod_list(self):
        self.mod_list.delete(0, "end")
        for u in sorted(self.blacklisted_users): self.mod_list.insert("end", u)

    # ── SNAPSHOTS ────────────────────────────────────────────────────────────
    def build_snapshots_tab(self):
        wrap = self.make_scrollable(self.tab_snaps)
        tk.Label(wrap, text="SNAPSHOTS", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 12))
        row = tk.Frame(wrap, bg="#09090B"); row.pack(fill="x", padx=30, pady=(0, 10))
        self.snap_cb = ttk.Combobox(row, width=34, font=("Segoe UI", 11)); self.snap_cb.pack(side="left")
        tk.Button(row, text="Refresh", font=("Segoe UI", 9, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                  command=self._refresh_snaps_tab).pack(side="left", padx=6, ipady=4, ipadx=10)
        self._grid_buttons(wrap, [
            ("Restore selected", "#EF4444", self._snap_restore),
            ("Set as target", "#8B5CF6", self._snap_set_target),
            ("Delete selected", "#27272A", self._snap_delete),
        ], cols=3).pack(fill="x", padx=26, pady=(0, 10))
        crow = tk.Frame(wrap, bg="#09090B"); crow.pack(fill="x", padx=30, pady=(0, 20))
        self.snap_new = tk.Entry(crow, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981")
        self.snap_new.pack(side="left", fill="x", expand=True, ipady=5)
        tk.Button(crow, text="Create snapshot", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2",
                  command=lambda: self._send_cmd("makesnapshot", self.snap_new.get())).pack(side="left", padx=8, ipady=5, ipadx=12)
        self._refresh_snaps_tab()

    def _refresh_snaps_tab(self):
        snaps = get_vbox_snapshots(vbox_manage_cmd, vm_name)
        self.snap_cb["values"] = snaps or [""]
        if self.current_snapshot in snaps: self.snap_cb.set(self.current_snapshot)
        elif snaps: self.snap_cb.set(snaps[-1])

    def _snap_set_target(self):
        s = self.snap_cb.get().strip()
        if not s: return
        self.current_snapshot = s
        try:
            with open(snap_file, "w") as f: f.write(s)
        except Exception: pass
        self.save_settings()
        self.log("[system]", f"target snapshot set to {s}.", "sysmsg")

    def _snap_restore(self):
        s = self.snap_cb.get().strip()
        if not s: return
        self.current_snapshot = s
        self._send_cmd("revert")

    def _snap_delete(self):
        s = self.snap_cb.get().strip()
        if not s: return
        threading.Thread(target=lambda: run_vbox(["snapshot", vm_name, "delete", s], timeout=45), daemon=True).start()
        self.log("[system]", f"deleting snapshot {s}...", "sysmsg")
        self.root.after(3000, self._refresh_snaps_tab)

    # ── OVERLAYS ─────────────────────────────────────────────────────────────
    def build_overlays_tab(self):
        wrap = self.make_scrollable(self.tab_overlays)
        tk.Label(wrap, text="OBS OVERLAYS", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 4))
        tk.Label(wrap, text=f"Local server on port {flask_port}. Add these as OBS Browser Sources.",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30, pady=(0, 14))
        overlays = [("Liquid Glass", "/obsnew"), ("Classic Dark", "/oldobsnew"), ("Legacy", "/obs"),
                    ("Big Stats", "/obs2"), ("Live Stats", "/stats"), ("Ultra Debug", "/ultradebug"),
                    ("Debug Chat", "/debugchat"), ("Index", "/")]
        self._grid_buttons(wrap, [(lbl, "#8B5CF6", lambda p=path: self._open_local(p)) for lbl, path in overlays], cols=4).pack(fill="x", padx=26, pady=(0, 14))
        tk.Label(wrap, text="Overlay controls", font=("Segoe UI", 10, "bold"), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30)
        self._grid_buttons(wrap, [
            ("Toggle Chat Visible", "#27272A", self.toggle_overlay_chat),
            ("Toggle Split Mode", "#27272A", self.toggle_split_overlay),
            ("Copy Glass URL", "#10B981", lambda: self._copy(f"http://localhost:{flask_port}/obsnew")),
            ("Copy Stats URL", "#10B981", lambda: self._copy(f"http://localhost:{flask_port}/stats")),
        ], cols=2).pack(fill="x", padx=26, pady=(4, 20))

    def _open_local(self, path):
        try:
            import webbrowser; webbrowser.open(f"http://localhost:{flask_port}{path}")
        except Exception: pass

    def _copy(self, text):
        try:
            self.root.clipboard_clear(); self.root.clipboard_append(text)
            self.log("[system]", f"copied: {text}", "sysmsg")
        except Exception: pass

    # ── CHAT TOOLS ───────────────────────────────────────────────────────────
    def build_chattools_tab(self):
        wrap = self.make_scrollable(self.tab_chattools)
        tk.Label(wrap, text="CHAT TOOLS", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 12))
        arow = tk.Frame(wrap, bg="#09090B"); arow.pack(fill="x", padx=30, pady=(0, 10))
        tk.Label(arow, text="Announce", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.announce_e = tk.Entry(arow, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.announce_e.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        tk.Button(arow, text="Send", font=("Segoe UI", 10, "bold"), bg=self.accent_main, fg="black", bd=0, cursor="hand2",
                  command=lambda: self.log("[announcement]", self.announce_e.get(), "sysmsg")).pack(side="left", ipady=5, ipadx=12)
        frow = tk.Frame(wrap, bg="#09090B"); frow.pack(fill="x", padx=30, pady=(0, 10))
        tk.Label(frow, text="Flash", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.chat_flash_e = tk.Entry(frow, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.chat_flash_e.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        tk.Button(frow, text="Flash", font=("Segoe UI", 10, "bold"), bg="#8B5CF6", fg="white", bd=0, cursor="hand2",
                  command=lambda: self.send_flash(self.chat_flash_e.get())).pack(side="left", ipady=5, ipadx=12)
        irow = tk.Frame(wrap, bg="#09090B"); irow.pack(fill="x", padx=30, pady=(0, 10))
        tk.Label(irow, text="Test msg", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.inject_e = tk.Entry(irow, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.inject_e.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        tk.Button(irow, text="Inject", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2",
                  command=self._inject_test).pack(side="left", ipady=5, ipadx=12)
        self._grid_buttons(wrap, [
            ("Clear Chat History", "#EF4444", self._clear_chat_history),
            ("Export All Messages", "#8B5CF6", self.extract_all_msgs),
            ("Pause Chat", "#F59E0B", self.toggle_pause_chat),
        ], cols=3).pack(fill="x", padx=26, pady=(6, 20))

    def _inject_test(self):
        txt = self.inject_e.get().strip()
        if not txt: return
        self.log("[console]", txt, "user", is_mod=True, is_owner=True)
        self.parse_command(txt, "[console]", is_mod=True, is_owner=True)

    def _clear_chat_history(self):
        global web_chat_history
        with history_lock: web_chat_history.clear()
        self.log("[system]", "chat history cleared.", "sysmsg")

    # ── SYSTEM ───────────────────────────────────────────────────────────────
    def build_system_tab(self):
        wrap = self.make_scrollable(self.tab_system)
        tk.Label(wrap, text="SYSTEM & DIAGNOSTICS", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 12))
        self.sys_diag = tk.Label(wrap, text="", font=("Consolas", 11), bg="#18181B", fg="#10B981", justify="left", anchor="w")
        self.sys_diag.pack(fill="x", padx=30, pady=(0, 14), ipady=10, ipadx=10)
        self._grid_buttons(wrap, [
            ("Rebuild COM", "#3B82F6", lambda: setattr(self, "force_session_refresh", True)),
            ("Kill VBox Tasks", "#EF4444", lambda: threading.Thread(target=self._kill_vbox_tasks, daemon=True).start()),
            ("Kill VBox Global Iface", "#EF4444", lambda: threading.Thread(target=self._kill_vbox_global, daemon=True).start()),
            ("Close Crash Dialogs", "#F59E0B", lambda: threading.Thread(target=self._dismiss_crash_dialogs, daemon=True).start()),
            ("Force Fix VM", "#F59E0B", lambda: self._send_cmd("forcefixvm")),
            ("Clear Cmd Queue", "#27272A", self.clear_commands),
            ("Garbage Collect", "#27272A", lambda: __import__("gc").collect()),
            ("Restart App", "#8B5CF6", self._restart_app),
        ], cols=3).pack(fill="x", padx=26, pady=(0, 20))
        self._sys_diag_tick()

    def _sys_diag_tick(self):
        try:
            up = int(time.time() - script_start_time); h, r = divmod(up, 3600); m, s = divmod(r, 60)
            com = "yes" if getattr(self, "shared_kb", None) else "no"
            txt = (f"uptime      {h}h {m}m {s}s\n"
                   f"queue size  {self.cmd_queue.qsize()}\n"
                   f"threads     {threading.active_count()}\n"
                   f"com locked  {com}\n"
                   f"vm running  {'yes' if self._vm_is_running() else 'no'}\n"
                   f"replay msgs {len(getattr(self, 'replay_buffer', []))}")
            if hasattr(self, "sys_diag"): self.sys_diag.config(text=txt)
        except Exception: pass
        if self.running:
            self.root.after(2000, self._sys_diag_tick)

    def _restart_app(self):
        try:
            self.save_settings(); time.sleep(0.3)
            args = [sys.executable, os.path.abspath(sys.argv[0])] + [a for a in sys.argv[1:] if a.startswith("--multistream")]
            subprocess.Popen(args)
            os._exit(0)
        except Exception as e:
            self.log("[system]", f"[error] restart: {e}", "err")

    # ── PRESETS ──────────────────────────────────────────────────────────────






    def build_replay_tab(self):
        wrap = self.make_scrollable(self.tab_replay)
        tk.Label(wrap, text="REPLAY", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 4))
        tk.Label(wrap, text="Re-plays recorded chat to the overlays with the ORIGINAL timing between messages\n(not one per second). Commands are shown, never re-executed.",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA", justify="left").pack(anchor="w", padx=30, pady=(0, 14))
        row = tk.Frame(wrap, bg="#09090B"); row.pack(fill="x", padx=30, pady=(0, 10))
        tk.Label(row, text="Speed x", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.replay_speed = tk.Entry(row, width=6, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A"); self.replay_speed.pack(side="left", padx=6, ipady=4); self.replay_speed.insert(0, "1")
        tk.Label(row, text="Max gap (s)", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(12, 0))
        self.replay_maxgap = tk.Entry(row, width=6, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A"); self.replay_maxgap.pack(side="left", padx=6, ipady=4); self.replay_maxgap.insert(0, "8")
        self.replay_status = tk.Label(wrap, text="idle", font=("Consolas", 11), bg="#09090B", fg="#A1A1AA"); self.replay_status.pack(anchor="w", padx=30, pady=(6, 8))
        self._grid_buttons(wrap, [
            ("Start Replay", "#10B981", self.start_replay),
            ("Stop Replay", "#EF4444", self.stop_replay),
            ("Clear Buffer", "#27272A", lambda: (self.replay_buffer.clear(), self._replay_update())),
        ], cols=3).pack(fill="x", padx=26, pady=(0, 20))
        self._replay_update()

    def _replay_update(self):
        try:
            self.replay_status.config(text=("replaying..." if self.replaying else f"{len(self.replay_buffer)} messages buffered"))
        except Exception: pass

    def start_replay(self):
        if self.replaying:
            return
        if not self.replay_buffer:
            self.replay_status.config(text="nothing to replay yet"); return
        try: speed = max(0.1, float(self.replay_speed.get()))
        except Exception: speed = 1.0
        try: maxgap = max(0.0, float(self.replay_maxgap.get()))
        except Exception: maxgap = 8.0
        self.replaying = True
        self._replay_update()
        threading.Thread(target=self._replay_loop, args=(speed, maxgap), daemon=True).start()

    def stop_replay(self):
        self.replaying = False
        self._replay_update()

    def _replay_loop(self, speed, maxgap):
        try:
            snap = list(self.replay_buffer)
            prev_t = None
            for item in snap:
                if not self.replaying or not self.running:
                    break
                if prev_t is not None:
                    gap = (item["t"] - prev_t) / speed
                    if gap > 0:
                        time.sleep(min(gap, maxgap))
                prev_t = item["t"]
                add_to_history("[replay] " + item.get("u", "?"), item.get("m", ""), "user", item.get("mod", False), item.get("owner", False))
        except Exception as e:
            console_log("ERROR", f"replay loop error: {e}")
        finally:
            self.replaying = False
            try: self.root.after(0, self._replay_update)
            except Exception: pass

    def _flag_com_error(self, emsg):
        e = str(emsg).lower()
        if ("verr_pdm_no_queue_items" in e or "could not send all scan codes" in e
                or "-2135228411" in e):
            return
        if ("-2147467259" in e or "0x80004005" in e or "e_fail" in e or "subscriptable" in e
                or "not ready" in e or "console" in e or "0x80bb0007" in e or "invalid_vm_state" in e
                or "aborted" in e or "-2147418113" in e):
            self.force_session_refresh = True
            self.efail_count = getattr(self, "efail_count", 0) + 1
            self.last_efail_t = time.time()

    def _vm_state(self):
        if getattr(self, "backend", "virtualbox") == "vmware":
            try: return "running" if self._vmware().is_running() else "poweroff"
            except Exception: return "unknown"
        try:
            r = subprocess.run([vbox_manage_cmd, "showvminfo", vm_name, "--machinereadable"],
                               capture_output=True, text=True, timeout=5)
            for line in (r.stdout or "").splitlines():
                if line.startswith("VMState="):
                    return line.split("=", 1)[1].strip().strip('"').lower()
        except Exception:
            pass
        return "unknown"

    def _escalate_recovery(self, reason):
        now = time.time()
        if now - getattr(self, "last_escalation_t", 0) < 20:   # cooldown so it can't thrash
            return
        self.last_escalation_t = now
        self.watchdog_action_level = min(getattr(self, "watchdog_action_level", 0) + 1, 5)
        lvl = self.watchdog_action_level
        dbg("recovery", f"ESCALATE level {lvl}: {reason} (efail={getattr(self,'efail_count',0)}, queue={self.cmd_queue.qsize()})")
        console_log("SYSTEM", f"[anti-stuck] escalation L{lvl}: {reason}")
        self.log("[system]", f"[warn] auto-recovery L{lvl}: {reason}", "sysmsg")
        try:
            if lvl == 1:
                self.force_session_refresh = True
            elif lvl == 2:
                self._teardown_com_session()
                self.force_session_refresh = True
            elif lvl == 3:
                # the session is wedged: kill the actual VirtualBoxVM process for
                # this vm, then bring it back up (a plain restartvm can't fix a
                # process that has stopped answering COM calls)
                def _kill_restart():
                    self._kill_vbox_tasks()
                    self._kill_vbox_global()
                    self._do_vm_maintenance("startvm", "", "[watchdog]")
                threading.Thread(target=_kill_restart, daemon=True).start()
            elif lvl == 4:
                if not getattr(self, "revert_disabled", False):
                    def _kill_revert():
                        self._kill_vbox_tasks()
                        self._do_vm_maintenance("revert", "", "[watchdog]")
                    threading.Thread(target=_kill_revert, daemon=True).start()
                else:
                    threading.Thread(target=lambda: self._do_vm_maintenance("restartvm", "", "[watchdog]"), daemon=True).start()
            elif lvl >= 5:
                try: self._kill_vbox_tasks()
                except Exception: pass
                self._relaunch_self("auto-recovery exhausted lower levels")
        except Exception as e:
            console_log("ERROR", f"escalation failed: {e}")

    def vm_health_watchdog(self):
        """Self-healing loop so the stream keeps running unattended. Detects a
        stuck/frozen VM, E_FAIL storms, dead COM sessions, and wrong power states,
        then recovers automatically with a cooldown-gated escalation ladder."""
        while self.running:
            try:
                time.sleep(4)
                if not self.config.get("auto_recover", True):
                    continue
                if getattr(self, "backend", "virtualbox") == "vmware":
                    continue
                now = time.time()
                # stuck-maintenance guard: never let vm_maintenance hang forever
                if getattr(self, "vm_maintenance", False):
                    if now - getattr(self, "_maint_start_t", now) > 200:
                        console_log("SYSTEM", "[anti-stuck] maintenance stuck >200s, clearing flag.")
                        self.vm_maintenance = False
                    continue
                state = self._vm_state()
                # crashed VM -> auto fix
                if state == "aborted":
                    self.log("[system]", "[warn] vm aborted/crashed, killing + restarting...", "sysmsg")
                    self._dismiss_crash_dialogs()
                    def _fix_aborted():
                        self._kill_vbox_tasks()
                        self._do_vm_maintenance("startvm", "", "[watchdog]")
                    threading.Thread(target=_fix_aborted, daemon=True).start()
                    self.vm_start_time = now
                    continue
                # unexpectedly paused -> resume
                if state == "paused":
                    run_vbox(["controlvm", vm_name, "resume"], timeout=10)
                    continue
                # off/saved but should be live -> start (24/7)
                if state in ("poweroff", "saved") and self.twenty_four_seven_mode and self.active_url:
                    if now - getattr(self, "vm_start_time", 0) > 20:
                        self.log("[system]", "[warn] vm down in 24/7 mode, auto-starting...", "sysmsg")
                        self.trigger_command(("startvm", "", "[watchdog]"))
                        self.vm_start_time = now
                    continue
                # only watch COM health while the vm is actually running
                if state != "running" and not self._vm_is_running():
                    self.watchdog_action_level = 0
                    continue
                # a crashed VM often pops the WerFault "Application Error" box and
                # then just sits there erroring - clear it as soon as we see trouble
                if getattr(self, "efail_count", 0) >= 4 or state == "aborted":
                    self._dismiss_crash_dialogs()
                # E_FAIL storm -> escalate
                if getattr(self, "efail_count", 0) >= 8:
                    # heavy storm, or COM has been unbuildable for a while while the
                    # vm claims to be running: the process is wedged, skip the gentle
                    # levels and go straight to killing it
                    if self.efail_count >= 20 or (self.shared_kb is None and now - getattr(self, "last_cmd_ok_t", now) > 45):
                        self.watchdog_action_level = max(getattr(self, "watchdog_action_level", 0), 2)
                        self.last_escalation_t = 0
                    self._escalate_recovery(f"E_FAIL storm ({self.efail_count})")
                    self.efail_count = 0
                    continue
                # commands piling up but nothing executing -> escalate
                if self.cmd_queue.qsize() > 3 and now - getattr(self, "last_cmd_ok_t", now) > 25:
                    self._escalate_recovery("commands queued but not executing")
                    continue
                # COM session should exist while running; if it keeps failing to build -> nudge
                if self.shared_kb is None and self.cmd_queue.qsize() > 0:
                    self.force_session_refresh = True
                # recovered cleanly -> stand down the ladder
                if getattr(self, "efail_count", 0) == 0 and now - getattr(self, "last_cmd_ok_t", now) < 15:
                    if getattr(self, "watchdog_action_level", 0) != 0 and now - getattr(self, "last_escalation_t", 0) > 30:
                        self.watchdog_action_level = 0
                        self.consecutive_failures = 0
            except Exception as e:
                console_log("ERROR", f"health watchdog error: {e}")
                time.sleep(4)

    def build_media_tab(self):
        wrap = self.make_scrollable(self.tab_media)
        tk.Label(wrap, text="MEDIA / MUSIC", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 12))
        arow = tk.Frame(wrap, bg="#09090B"); arow.pack(fill="x", padx=30, pady=(0, 12))
        tk.Label(arow, text="Add URL", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.media_url = tk.Entry(arow, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.media_url.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        tk.Button(arow, text="Add to queue", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2", command=self._media_add).pack(side="left", ipady=5, ipadx=10)
        self._grid_buttons(wrap, [
            ("Play", "#10B981", lambda: self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")),
            ("Pause", "#F59E0B", lambda: self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")),
            ("Stop", "#EF4444", lambda: self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")),
            ("Restart", "#00E5FF", lambda: self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")),
            ("Skip", "#8B5CF6", self._skip_song),
            ("Clear Queue", "#27272A", lambda: (self.music_queue.clear(), self.log("[system]", "music queue cleared.", "sysmsg"))),
        ], cols=3).pack(fill="x", padx=26, pady=(0, 12))
        self._grid_buttons(wrap, [
            ("VM Vol +", "#27272A", lambda: self._send_cmd("!volumeup", "2")),
            ("VM Vol -", "#27272A", lambda: self._send_cmd("!volumedown", "2")),
            ("VM Mute", "#27272A", lambda: self._send_cmd("!key", "vol_mute")),
        ], cols=3).pack(fill="x", padx=26, pady=(0, 20))

    def _media_add(self):
        url = self.media_url.get().strip()
        if url:
            threading.Thread(target=self.download_music_thread, args=(url, "[console]", True, True, True), daemon=True).start()
            self.media_url.delete(0, "end")

    def build_quicktype_tab(self):
        wrap = self.make_scrollable(self.tab_qtype)
        tk.Label(wrap, text="QUICK TYPE", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 4))
        tk.Label(wrap, text="Type a whole block into the VM, or save reusable snippets.",
                 font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30, pady=(0, 12))
        self.qtype_text = scrolledtext.ScrolledText(wrap, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, height=5,
                                                    highlightthickness=1, highlightbackground="#27272A", insertbackground="white")
        self.qtype_text.pack(fill="x", padx=30, pady=(0, 8))
        self._grid_buttons(wrap, [
            ("Type block", self.accent_main, lambda: self._qtype_send(False)),
            ("Type block + Enter", "#10B981", lambda: self._qtype_send(True)),
        ], cols=2).pack(fill="x", padx=26, pady=(0, 14))
        srow = tk.Frame(wrap, bg="#09090B"); srow.pack(fill="x", padx=30, pady=(0, 8))
        tk.Label(srow, text="New snippet", bg="#09090B", fg="#D4D4D8", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.snip_entry = tk.Entry(srow, font=("Consolas", 11), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981")
        self.snip_entry.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        tk.Button(srow, text="Save", font=("Segoe UI", 10, "bold"), bg="#10B981", fg="black", bd=0, cursor="hand2", command=self._snip_add).pack(side="left", ipady=5, ipadx=12)
        self.snip_wrap = tk.Frame(wrap, bg="#09090B"); self.snip_wrap.pack(fill="x", padx=26, pady=(6, 20))
        self._refresh_snippets()

    def _qtype_send(self, enter=False):
        txt = self.qtype_text.get("1.0", "end").rstrip("\n")
        if not txt: return
        lines = txt.split("\n")
        chain = []
        for i, ln in enumerate(lines):
            if ln: chain.append(("!type", ln))
            if i < len(lines) - 1: chain.append(("!key", "enter"))
        if enter: chain.append(("!key", "enter"))
        self._send_chain(chain)

    def _snip_add(self):
        v = self.snip_entry.get().strip()
        if not v: return
        snips = self.config.get("snippets", [])
        snips.append(v); self.config["snippets"] = snips; self.save_settings()
        self.snip_entry.delete(0, "end"); self._refresh_snippets()

    def _refresh_snippets(self):
        for w in self.snip_wrap.winfo_children(): w.destroy()
        for i, sn in enumerate(self.config.get("snippets", [])):
            row = tk.Frame(self.snip_wrap, bg="#18181B"); row.pack(fill="x", pady=2)
            tk.Button(row, text="Type", font=("Segoe UI", 9, "bold"), bg=self.accent_main, fg="black", bd=0, cursor="hand2",
                      command=lambda t=sn: self._send_cmd("!type", t)).pack(side="left", padx=(6, 8), pady=4, ipadx=8)
            tk.Label(row, text=(sn[:60] + ("..." if len(sn) > 60 else "")), bg="#18181B", fg="#D4D4D8", font=("Consolas", 10)).pack(side="left")
            tk.Button(row, text="x", font=("Segoe UI", 9, "bold"), bg="#EF4444", fg="white", bd=0, cursor="hand2",
                      command=lambda idx=i: self._snip_del(idx)).pack(side="right", padx=6)

    def _snip_del(self, idx):
        snips = self.config.get("snippets", [])
        if 0 <= idx < len(snips):
            del snips[idx]; self.config["snippets"] = snips; self.save_settings(); self._refresh_snippets()

    def build_winapps_tab(self):
        wrap = self.make_scrollable(self.tab_winapps)
        tk.Label(wrap, text="WINDOWS APPS", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 4))
        tk.Label(wrap, text="Launches via Win+R inside the VM.", font=("Segoe UI", 10), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30, pady=(0, 12))
        apps = [("Notepad", "notepad"), ("Calculator", "calc"), ("Paint", "mspaint"), ("Explorer", "explorer"),
                ("Command Prompt", "cmd"), ("Task Manager", "taskmgr"), ("Control Panel", "control"), ("Registry", "regedit"),
                ("WordPad", "write"), ("Snipping Tool", "snippingtool"), ("Edge", "msedge"), ("Chrome", "chrome"),
                ("Settings", "ms-settings:"), ("Char Map", "charmap"), ("Services", "services.msc"), ("Device Mgr", "devmgmt.msc")]
        self._grid_buttons(wrap, [(lbl, "#8B5CF6", lambda c=cmd: self._launch_app(c)) for lbl, cmd in apps], cols=4).pack(fill="x", padx=26, pady=(0, 12))
        tk.Button(wrap, text="Open Run dialog", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", bd=0, cursor="hand2",
                  command=lambda: self._send_cmd("!combo", "win+r")).pack(anchor="w", padx=30, pady=(0, 20), ipady=5, ipadx=14)

    def _launch_app(self, cmd):
        self._send_chain([("!combo", "win+r"), ("!wait", "0.6"), ("!send", cmd)])










    def build_backup_tab(self):
        wrap = self.make_scrollable(self.tab_backup)
        tk.Label(wrap, text="BACKUP & EXPORT", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(anchor="w", padx=30, pady=(22, 12))
        self._grid_buttons(wrap, [
            ("Export All Messages", "#8B5CF6", self.extract_all_msgs),
            ("Backup Config", "#10B981", self._backup_config),
            ("Save Snapshot List", "#00E5FF", self._save_snaplist),
            ("Open Script Folder", "#27272A", self._open_folder),
            ("Clear Server Log", "#EF4444", self._clear_server_log),
            ("Reload Settings", "#27272A", self._reload_settings),
        ], cols=3).pack(fill="x", padx=26, pady=(0, 12))
        self.backup_status = tk.Label(wrap, text="", font=("Consolas", 10), bg="#09090B", fg="#A1A1AA"); self.backup_status.pack(anchor="w", padx=30, pady=(4, 20))

    def _backup_config(self):
        try:
            name = f"settings_backup_{time.strftime('%Y%m%d_%H%M%S')}.json"
            with open(name, "w", encoding="utf-8") as f: json.dump(self.config, f, indent=2)
            self.backup_status.config(text=f"saved {name}")
        except Exception as e:
            self.backup_status.config(text=f"error: {e}")

    def _save_snaplist(self):
        try:
            snaps = get_vbox_snapshots(vbox_manage_cmd, vm_name)
            name = f"snapshots_{vm_name}.txt"
            with open(name, "w", encoding="utf-8") as f: f.write("\n".join(snaps))
            self.backup_status.config(text=f"saved {name} ({len(snaps)} snapshots)")
        except Exception as e:
            self.backup_status.config(text=f"error: {e}")

    def _open_folder(self):
        try:
            folder = os.path.dirname(os.path.abspath(sys.argv[0])) or "."
            if platform.system() == "Windows": os.startfile(folder)
            elif platform.system() == "Darwin": subprocess.Popen(["open", folder])
            else: subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            self.backup_status.config(text=f"error: {e}")

    def _clear_server_log(self):
        try:
            open(log_file, "w").close()
            self.backup_status.config(text="server log cleared")
        except Exception as e:
            self.backup_status.config(text=f"error: {e}")

    def _reload_settings(self):
        self.config = self.load_settings()
        self.backup_status.config(text="settings reloaded (restart for full effect)")

    GUIDE_FLAG_FILE = "guide_seen.flag"

    def show_welcome_guide(self, force=False):
        """Chaptered user guide. Opens on first launch, and any time from the
        Help page or the sidebar."""
        if not force and os.path.exists(self.GUIDE_FLAG_FILE):
            return
        pal = getattr(self, "_theme_palette", self.THEMES["original"])
        BG, BG2, BG3 = pal["bg"], pal["card"], pal["panel"]
        TEXT, DIM, ACC = pal["text"], pal["muted"], self.accent_main
        W, H = 860, 600
        dlg = tk.Toplevel(self.root)
        dlg.title(f"{self.app_name} - User Guide")
        dlg.configure(bg=BG)
        try:
            dlg.grab_set()
            self.root.update_idletasks()
            rx = self.root.winfo_x() + (self.root.winfo_width() - W) // 2
            ry = self.root.winfo_y() + (self.root.winfo_height() - H) // 2
            dlg.geometry(f"{W}x{H}+{max(0, rx)}+{max(0, ry)}")
        except Exception:
            dlg.geometry(f"{W}x{H}")

        hdr = tk.Frame(dlg, bg=ACC, height=54); hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"{self.app_name} Control Panel  -  User Guide", bg=ACC, fg="#000000",
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=18, pady=10)
        tk.Label(hdr, text=f"v{version}", bg=ACC, fg="#000000", font=("Segoe UI", 9)).pack(side="right", padx=18)

        body = tk.Frame(dlg, bg=BG); body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=BG2, width=215); side.pack(side="left", fill="y"); side.pack_propagate(False)
        tk.Label(side, text="CHAPTERS", bg=BG2, fg=DIM, font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        sb_canvas = tk.Canvas(side, bg=BG2, highlightthickness=0, bd=0)
        sb_scroll = ttk.Scrollbar(side, orient="vertical", command=sb_canvas.yview)
        sb_canvas.configure(yscrollcommand=sb_scroll.set)
        sb_scroll.pack(side="right", fill="y"); sb_canvas.pack(side="left", fill="both", expand=True)
        navf = tk.Frame(sb_canvas, bg=BG2)
        navwin = sb_canvas.create_window((0, 0), window=navf, anchor="nw")
        navf.bind("<Configure>", lambda e: sb_canvas.configure(scrollregion=sb_canvas.bbox("all")))
        sb_canvas.bind("<Configure>", lambda e: sb_canvas.itemconfig(navwin, width=e.width))

        right = tk.Frame(body, bg=BG); right.pack(side="left", fill="both", expand=True)
        tf = tk.Frame(right, bg=pal["border"], bd=1); tf.pack(fill="both", expand=True, padx=10, pady=10)
        txt = tk.Text(tf, bg=BG3, fg=TEXT, font=("Segoe UI", 10), wrap="word", relief="flat",
                      bd=0, padx=16, pady=12, state="disabled", cursor="arrow")
        ts = ttk.Scrollbar(tf, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ts.set); ts.pack(side="right", fill="y"); txt.pack(fill="both", expand=True)
        txt.tag_configure("h1", font=("Segoe UI", 15, "bold"), foreground=ACC, spacing1=4, spacing3=8)
        txt.tag_configure("h2", font=("Segoe UI", 11, "bold"), foreground="#F59E0B", spacing1=12, spacing3=3)
        txt.tag_configure("body", font=("Segoe UI", 10), foreground=TEXT, spacing1=2, lmargin1=4, lmargin2=4)
        txt.tag_configure("code", font=("Consolas", 9), foreground="#10B981", background=BG2, spacing1=1, lmargin1=16, lmargin2=16)
        txt.tag_configure("tip", font=("Segoe UI", 9, "italic"), foreground=DIM, spacing1=3, lmargin1=4)

        CHAPTERS = [
            ("Getting Started", [
                ("h1", "Getting Started"),
                ("body", f"Welcome to {self.app_name}. Your chat drives a virtual machine live on stream."),
                ("h2", "First-time setup"),
                ("body", "1.  Paste your YouTube stream link or channel into the Dashboard."),
                ("body", "    A full URL, a bare video ID, or an @channel all work."),
                ("code", "  youtube.com/watch?v=abc123XYZ    or    @yourchannel"),
                ("body", "2.  Pick your VM on the VM Config page (press Refresh if the list is empty)."),
                ("body", "3.  Press  Connect Chat  on the Dashboard."),
                ("h2", "Quick Actions"),
                ("body", "The Dashboard has Start VM, Stop VM, Restart VM, Toggle Chat and Revert Snapshot."),
                ("h2", "24/7 mode"),
                ("body", "Settings -> 'Auto-start VM on launch'. If the VM crashes or powers off, the watchdog brings it back automatically."),
                ("tip", "Tip: the status bar at the bottom always shows backend, VM, viewers and queue depth."),
            ]),
            ("Chat Commands", [
                ("h1", "Chat Commands"),
                ("body", "Viewers type these in your live chat. Every command starts with your prefix (default '!')."),
                ("h2", "Keyboard"),
                ("code", "  !type hello          types 'hello' into the VM"),
                ("code", "  !send notepad        types text, then presses Enter"),
                ("code", "  !key enter           presses one key"),
                ("code", "  !combo win+r         presses Win and R together"),
                ("code", "  !keydown shift       holds a key"),
                ("code", "  !keyup shift         releases a held key"),
                ("h2", "Mouse"),
                ("code", "  !click / !rclick / !mclick     mouse buttons"),
                ("code", "  !move right 60                 move the cursor"),
                ("code", "  !abs 500 300                   jump to x=500 y=300"),
                ("code", "  !scroll 3                      scroll (negative = down)"),
                ("code", "  !drag 100 200                  click and drag"),
                ("h2", "Chaining"),
                ("body", "Several commands can go in ONE message, separated by spaces:"),
                ("code", "  !combo win+r !wait 1 !send notepad"),
                ("tip", "Tip: pipes work too, but they are optional - spaces are enough."),
                ("h2", "Votes"),
                ("code", "  !revert / !restartvm      viewers vote, mods act instantly"),
                ("code", "  !skipsong !pausesong      music votes"),
                ("code", "  !changevm                 vote to switch OS (if enabled)"),
            ]),
            ("Mod Commands", [
                ("h1", "Mod Commands"),
                ("body", "Only moderators and the stream owner can run these."),
                ("h2", "Moderation"),
                ("code", "  !ban <user>              block a user from commands"),
                ("code", "  !unban <user>            lift a ban"),
                ("code", "  !timeout <user> <mins>   temporary ban"),
                ("code", "  !whois <user>            ban status and strike count"),
                ("code", "  !strikes <user>          clear their strikes"),
                ("code", "  !slowmode <sec>          set the viewer cooldown"),
                ("code", "  !lockdown / !unlock      mods-only chat toggle"),
                ("h2", "Stream"),
                ("code", "  !flash <msg>             flash a message on the overlays"),
                ("code", "  !shout / !alert / !pin   styled overlay flashes"),
                ("code", "  !scene <name>            switch OBS scene"),
                ("code", "  !announce <msg>          announcement in chat"),
                ("h2", "System"),
                ("code", "  !vmstatus / !stats       quick status"),
                ("code", "  !snapshotnow             take a snapshot"),
                ("code", "  !revertnow / !restartnow instant VM actions"),
                ("code", "  !purge                   clear the command queue"),
                ("code", "  !kill / !rebuild         kill VM procs / rebuild COM"),
                ("code", "  !closedialog             close VirtualBox crash popups"),
                ("code", "  !allowshell              toggle viewer !cmd/!run access"),
            ]),
            ("VMs and Backends", [
                ("h1", "VMs and Backends"),
                ("body", "The VMS page picks which virtualization backend drives the guest."),
                ("h2", "VirtualBox (default)"),
                ("body", "Input goes through VirtualBox's native COM interface, which always matches your installed version. Keyboard and mouse both work."),
                ("h2", "VMware Workstation"),
                ("body", "1.  Set the path to vmrun (auto-detected on most systems)."),
                ("body", "2.  Pick your .vmx - the VMS page scans Documents/Virtual Machines automatically."),
                ("body", "3.  If your VMs live elsewhere, use 'This is not my VM folder' to browse."),
                ("body", "4.  With the VM powered OFF, press 'Enable VNC in .vmx'."),
                ("body", "5.  Press 'Switch to VMware'."),
                ("code", "  pip install vncdotool        required for VMware input"),
                ("tip", "Tip: vmrun cannot inject keystrokes, so VMware input runs over VNC."),
                ("tip", "Tip: set keymap 'dk' or 'us' to match your guest's keyboard."),
                ("h2", "Snapshots"),
                ("body", "The Snapshots page lists, creates, restores and deletes snapshots for the active VM."),
            ]),
            ("Overlays and OBS", [
                ("h1", "Overlays and OBS"),
                ("body", "Add these as Browser Sources in OBS. The Overlays page can copy each URL."),
                ("code", "  /obsnew        liquid glass chat"),
                ("code", "  /oldobsnew     classic dark chat"),
                ("code", "  /stats         uptime, viewers, likes, commands"),
                ("code", "  /ultradebug    queue, COM state, threads"),
                ("h2", "OBS connection"),
                ("body", "Set host, port and password on the OBS page, then use the scene buttons to test."),
                ("h2", "Flash messages"),
                ("body", "Type into the Flash box on the OBS or Chat Tools page, and it appears on every overlay at once."),
                ("tip", "Tip: overlays bind to localhost by default. Set YT2VM_LAN=1 to expose them to your network."),
            ]),
            ("Safety and Recovery", [
                ("h1", "Safety and Recovery"),
                ("body", "The bot protects both the guest and the stream automatically."),
                ("h2", "Viewer protection"),
                ("body", "Destructive payloads are blocked even when obfuscated - 'shutdown', 'sh-u.t_d0wn' and '$hutd0wn' are all caught. IP-grabber links are blocked too."),
                ("body", "Shell commands (!cmd, !run) are mod-only unless you enable them."),
                ("body", "Per-user cooldown and spam limits apply, with an auto timeout after repeat strikes."),
                ("h2", "Auto-recovery"),
                ("body", "A watchdog escalates through refresh, rebuild, kill+restart, revert, then relaunch, with cooldowns so it never thrashes."),
                ("body", "VirtualBox crash dialogs are detected, OK is clicked, and the process is force-killed if it will not close."),
                ("tip", "Tip: turn this off with auto_recover in settings if you prefer manual control."),
            ]),
            ("Tools", [
                ("h1", "Tools"),
                ("body", "Extras that make long streams easier."),
                ("h2", "Automation"),
                ("body", "Run any command on a timer - keep-alive keys, periodic announcements, scheduled reverts."),
                ("h2", "Replay"),
                ("body", "Records chat with real timestamps and replays it preserving the ORIGINAL gaps between messages. Commands are shown, never re-executed."),
                ("tip", "Tip: five quick clicks on the status label starts a replay instantly."),
                ("h2", "Quick Type and Macros"),
                ("body", "Type whole blocks into the VM, save reusable snippets, and launch Windows apps in one click."),
                ("h2", "Appearance"),
                ("body", "Five themes - Original, Better, God, Light and Daylight - plus eight accent colours."),
                ("h2", "Backup"),
                ("body", "Export chat logs, back up your config, and save the snapshot list."),
            ]),
        ]

        btns = []
        def show_chapter(idx):
            _, sections = CHAPTERS[idx]
            txt.configure(state="normal"); txt.delete("1.0", "end")
            for tag, content in sections:
                txt.insert("end", content + "\n", tag)
            txt.configure(state="disabled"); txt.yview_moveto(0)
            for i, b in enumerate(btns):
                try: b.configure(bg=ACC if i == idx else BG2, fg="#000000" if i == idx else TEXT)
                except Exception: pass

        for i, (title, _) in enumerate(CHAPTERS):
            b = tk.Label(navf, text="  " + title, bg=BG2, fg=TEXT, anchor="w",
                         font=("Segoe UI", 9), padx=12, pady=7, cursor="hand2")
            b.pack(fill="x", pady=1)
            b.bind("<Button-1>", lambda e, idx=i: show_chapter(idx))
            btns.append(b)
        show_chapter(0)

        footer = tk.Frame(dlg, bg=BG2, pady=8); footer.pack(fill="x", side="bottom")
        dont = tk.BooleanVar(value=False)
        ttk.Checkbutton(footer, text="Don't show this guide on startup", variable=dont,
                        style="Toggle.TCheckbutton").pack(side="left", padx=16)
        def close_guide():
            if dont.get():
                try:
                    with open(self.GUIDE_FLAG_FILE, "w") as f: f.write("seen")
                except Exception: pass
            try: dlg.destroy()
            except Exception: pass
        tk.Button(footer, text="Got it, close guide", font=("Segoe UI", 10, "bold"),
                  bg="#10B981", fg="black", bd=0, cursor="hand2",
                  command=close_guide).pack(side="right", padx=16, ipady=4, ipadx=12)
        dlg.protocol("WM_DELETE_WINDOW", close_guide)
        dlg.bind("<Escape>", lambda e: close_guide())
        txt.bind("<MouseWheel>", lambda e: txt.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def build_help_tab(self):
        wrap = tk.Frame(self.tab_help, bg="#09090B"); wrap.pack(fill="both", expand=True, padx=30, pady=20)
        bar = tk.Frame(wrap, bg="#09090B"); bar.pack(fill="x")
        tk.Label(bar, text="COMMAND REFERENCE", font=("Segoe UI", 14, "bold"), bg="#09090B", fg=self.accent_main).pack(side="left")
        tk.Label(bar, text="Filter:", bg="#09090B", fg="#A1A1AA", font=("Segoe UI", 9)).pack(side="left", padx=(20, 4))
        self.help_filter = tk.Entry(bar, font=("Consolas", 10), bg="#18181B", fg="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor=self.accent_main)
        self.help_filter.pack(side="left", fill="x", expand=True, ipady=3)
        self.help_filter.bind("<KeyRelease>", lambda e: self._render_help())
        tk.Button(bar, text="Open User Guide", font=("Segoe UI", 9, "bold"), bg=self.accent_main, fg="black",
                  bd=0, cursor="hand2", command=lambda: self.show_welcome_guide(force=True)).pack(side="right", padx=(10, 0), ipady=4, ipadx=10)
        self.help_text = scrolledtext.ScrolledText(wrap, font=("Consolas", 10), bg="#09090B", fg="#D4D4D8", bd=0, highlightthickness=1, highlightbackground="#27272A")
        self.help_text.pack(fill="both", expand=True, pady=(10, 0))
        self._help_lines = [
            ("VIEWER", "!type <text>", "type text into the VM"),
            ("VIEWER", "!send <text>", "type text then press Enter"),
            ("VIEWER", "!key <key>", "press a single key (enter, esc, f5...)"),
            ("VIEWER", "!combo a+b", "key combo (win+r, ctrl+c...)"),
            ("VIEWER", "!click / !rclick / !mclick [n]", "mouse clicks"),
            ("VIEWER", "!move <dir> <amt>", "move cursor"),
            ("VIEWER", "!abs <x> <y>", "move cursor to coords"),
            ("VIEWER", "!scroll <amt>", "scroll wheel"),
            ("VIEWER", "!drag <dx> <dy>", "click-drag mouse"),
            ("VIEWER", "!cmd / !run <text>", "run in cmd / Win+R"),
            ("VIEWER", "!startvm", "boot the VM"),
            ("VIEWER", "!music <url> [true]", "queue a song"),
            ("VIEWER", "!roll / !coinflip", "random number / coin"),
            ("VIEWER", "!skipsong / !pausesong ...", "start a music vote"),
            ("VIEWER", "!revert / !restartvm", "start a vote (mods bypass)"),
            ("VIEWER", "!changevm", "vote to switch OS (if enabled)"),
            ("MOD", "!ban / !unban <user>", "blacklist / un-blacklist"),
            ("MOD", "!timeout / !mute <user> <mins>", "timed ban"),
            ("MOD", "!warn <user> <msg>", "warn flash"),
            ("MOD", "!scene <name>", "switch OBS scene"),
            ("MOD", "!shout / !alert / !pin <msg>", "flash overlays"),
            ("MOD", "!announce / !nuke", "announce / clear chat"),
            ("MOD", "!flash <msg>", "flash overlays"),
            ("MOD", "!hydrate !clip !brb !back", "hype flashes"),
            ("MOD", "!applause !hype !f !8ball", "fun flashes"),
            ("MOD", "!countdown <n> / !disco", "countdown / party"),
            ("MOD", "!coin / !bigroll", "coin / big roll flash"),
            ("MOD", "!skip / !kill / !rebuild", "skip song / kill vbox / rebuild COM"),
            ("MOD", "!vmstatus / !stats", "status flashes"),
            ("MOD", "!lockdown / !unlock", "mods-only chat toggle"),
            ("MOD", "!snapshotnow / !revertnow / !restartnow", "instant VM actions"),
            ("MOD", "!clearvotes / !title <text>", "clear votes / set title"),
            ("OWNER", "!replay", "replay chat with original timing"),
            ("OWNER", "!pausechat / !enablechat", "freeze / open chat"),
        ]
        self._render_help()

    def _render_help(self):
        flt = ""
        try: flt = self.help_filter.get().strip().lower()
        except Exception: pass
        self.help_text.configure(state="normal")
        self.help_text.delete("1.0", "end")
        cur = None
        for role, cmd, desc in self._help_lines:
            line = f"{cmd}   -   {desc}"
            if flt and flt not in line.lower() and flt not in role.lower(): continue
            if role != cur:
                cur = role
                self.help_text.insert("end", f"\n[{role}]\n")
            self.help_text.insert("end", f"  {cmd:<38} {desc}\n")
        self.help_text.configure(state="disabled")

    def start_app_threads(self):
        try:
            if not getattr(self, '_flask_started', False):
                self._flask_started = True
                threading.Thread(target=start_flask, daemon=True).start()
            if not getattr(self, '_music_started', False):
                self._music_started = True
                threading.Thread(target=self.tick_music_engine, daemon=True).start()
            if not getattr(self, '_watcher_started', False):
                self._watcher_started = True
                threading.Thread(target=self.error_watcher_loop, daemon=True).start()
            if not getattr(self, '_hardwatchdog_started', False):
                self._hardwatchdog_started = True
                threading.Thread(target=self.hard_watchdog_loop, daemon=True).start()
            if not getattr(self, '_automation_started', False):
                self._automation_started = True
                threading.Thread(target=self.automation_loop, daemon=True).start()
            if not getattr(self, '_health_started', False):
                self._health_started = True
                threading.Thread(target=self.vm_health_watchdog, daemon=True).start()
            if not getattr(self, '_dialogwatch_started', False):
                self._dialogwatch_started = True
                threading.Thread(target=self._crash_dialog_watcher, daemon=True).start()
            lt = getattr(self, 'listener_thread', None)
            if lt is None or not lt.is_alive():
                self.listener_id += 1
                t = threading.Thread(target=self.chat_listener_loop, args=(self.listener_id,), daemon=True)
                t.start()
                self.listener_thread = t
            et = getattr(self, 'executor_thread', None)
            if et is None or not et.is_alive():
                self.executor_id += 1
                t = threading.Thread(target=self.executor_loop, args=(self.executor_id,), daemon=True)
                t.start()
                self.executor_thread = t
        except Exception as e:
            console_log("ERROR", f"start_app_threads error: {e}\n{traceback.format_exc()}")


def _should_respawn():
    try:
        now = time.time()
        times = []
        if os.path.exists(crashguard_file):
            with open(crashguard_file) as f:
                times = [float(x) for x in f.read().split() if x.strip()]
        times = [t for t in times if now - t < 60]
        times.append(now)
        with open(crashguard_file, "w") as f: f.write(" ".join(str(t) for t in times))
        return len(times) <= 5
    except Exception:
        return True


if __name__ == "__main__":
    try:
        main_ui_root = tk.Tk()
        main_gui_application = ChatPlaysApp(main_ui_root)
        # when this instance was started by a crash relaunch, minimize it so it
        # never pops over the stream. also minimize if the user asked for it.
        if ("--relaunched" in sys.argv or "--minimized" in sys.argv
                or os.environ.get("YT2VM_MINIMIZED") == "1"):
            def _minimize_after_start():
                try:
                    main_ui_root.iconify()
                    if "--relaunched" in sys.argv:
                        console_log("SYSTEM", "recovered from a crash - running minimized so the stream is not interrupted.")
                except Exception:
                    pass
            # do it after the window has actually mapped, or iconify is ignored
            main_ui_root.after(400, _minimize_after_start)
        main_ui_root.mainloop()
    except Exception as fatal_error:
        traceback.print_exc()
        try:
            with open("crash_log.txt", "w") as f: traceback.print_exc(file=f)
        except Exception: pass
        try: set_obs_scene(obs_scene_error)
        except Exception: pass
        if _should_respawn():
            try:
                script_path = os.path.abspath(sys.argv[0])
                args = [sys.executable, script_path] + [a for a in sys.argv[1:] if a.startswith("--multistream")]
                if platform.system() == "Windows": subprocess.Popen(args, creationflags=0x00000010, close_fds=True)
                else: subprocess.Popen(args, start_new_session=True, close_fds=True)
            except Exception: pass
            os._exit(1)
        else:
            try:
                err_root = tk.Tk(); err_root.withdraw()
                messagebox.showerror("error", f"crashed repeatedly ({fatal_error}). not respawning to avoid a boot loop.")
                err_root.destroy()
            except Exception: pass
            input("press enter to exit...")
