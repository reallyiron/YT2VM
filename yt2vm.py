import signal as _signal_module
import threading as _threading_module
import sys as _sys_early
import os as _os_early

IN_IDLE = bool("idlelib" in _sys_early.modules or "idlelib.run" in _sys_early.modules
               or _os_early.environ.get("YT2VM_IDLE") == "1")

try:
    with open("boot_log.txt", "a", encoding="utf-8") as _bf:
        import time as _t_early
        _bf.write(f"[{_t_early.strftime('%Y-%m-%d %H:%M:%S')}] boot start (idle={IN_IDLE}, argv={_sys_early.argv})\n")
except Exception:
    pass

_orig_signal = _signal_module.signal
def _safe_signal(sig, handler):
    try:
        if _threading_module.current_thread() is _threading_module.main_thread():
            return _orig_signal(sig, handler)
    except Exception:
        pass
_signal_module.signal = _safe_signal

import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk
import tkinter.font as tkfont
import threading, time, sys, traceback, random, subprocess, os, re, json, platform, ctypes, collections, queue, shutil, gc
import math
import asyncio
import hashlib
import urllib.request, urllib.error, urllib.parse
from ctypes import wintypes


def _hide_console():
    if globals().get("_HIDE_DISABLED"):
        return
    if platform.system() != "Windows":
        return
    if IN_IDLE:
        return
    if "--console" in sys.argv or os.environ.get("YT2VM_CONSOLE") == "1":
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


_HIDE_DISABLED = True
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




_rqp = [
    ("pytchat", "pytchat", "reading YouTube live chat"),
    ("flask", "flask", "OBS overlay web server"),
]
_opp = [
    ("obsws_python", "obsws-python", "OBS scene / media control"),
    ("customtkinter", "customtkinter", "modern rounded widgets"),
    ("ttkbootstrap", "ttkbootstrap", "themed ttk widgets"),
    ("yt_dlp", "yt-dlp", "music downloads"),
    ("serial", "pyserial", "Pico HID (Real PC tab)"),
    ("vncdotool", "vncdotool", "VMware input over VNC"),
]
if platform.system() == "Windows":
    _rqp.append(("win32com", "pywin32", "VirtualBox native COM"))
    _opp.append(("virtualbox", "virtualbox", "legacy pyvbox fallback"))
else:
    _opp.append(("virtualbox", "virtualbox", "VirtualBox python API"))

_if = "deps_installed.flag"

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
    if IN_IDLE:
        try:
            miss = _missing_packages(_rqp)
            if miss:
                print("MISSING PACKAGES (run this once in Command Prompt, NOT IDLE):")
                print("  pip install " + " ".join(m[1] for m in miss))
        except Exception:
            pass
        return
    if not force and os.path.exists(_if):
        return
    need_req = _missing_packages(_rqp)
    need_opt = _missing_packages(_opp)
    if not need_req and not need_opt:
        try:
            with open(_if, "w") as f: f.write("ok")
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
            with open(_if, "w") as f: f.write("ok")
        except Exception: pass
    print("=" * 60)

ensure_packages() if "--no-install" not in sys.argv else None
try:
    if os.cpu_count() and os.cpu_count() <= 2:
        os.environ.setdefault("YT2VM_SUGGEST_LOWPOWER", "1")
except Exception:
    pass

def platform_report():
    sysname = platform.system()
    bits = [f"platform: {sysname}"]
    try:
        if os.path.exists(vbox_manage_cmd) or shutil.which("VBoxManage"):
            bits.append("VBoxManage: found")
        else:
            bits.append("VBoxManage: NOT FOUND")
    except Exception as _ex:
        _trace(_ex_where(), _ex)
    try:
        vr = find_vmrun()
        bits.append("vmrun: found" if os.path.exists(vr) else "vmrun: not found")
    except Exception as _ex:
        _trace(_ex_where(), _ex)
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

CRASH_LOG = f"crash_log{suffix}.txt"
SESSION_LOG = f"session_log{suffix}.txt"
CRASH_LINE_LOG = f"crashed_at_line{suffix}.txt"
_log_lock = _threading_module.Lock()


def write_log(where, text):
    try:
        with _log_lock:
            with open(where, "a", encoding="utf-8") as f:
                f.write(text)
    except Exception:
        pass


_OUT_LOG = f"output_log{suffix}.txt"
_OUT_MAX = 8 * 1024 * 1024
_OUT_VERBOSE = ("--debug" in sys.argv) or ("--verbose" in sys.argv) or (os.environ.get("YT2VM_VERBOSE") == "1")
_OUT_PRINT = ("--no-print" not in sys.argv) and (os.environ.get("YT2VM_PRINT") != "0")
_out_q = queue.Queue(maxsize=50000)
_out_state = {"dropped": 0, "lines": 0, "started": False, "busy": False}
_out_thread_re = re.compile(r"^Thread-\d+ \((.+)\)$")
_MAINLOOP_LIVE = [False]
_ui_block_seen = {}

try:
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def _out_thread_name():
    try:
        n = threading.current_thread().name
        m = _out_thread_re.match(n)
        return m.group(1) if m else n
    except Exception:
        return "?"


def plog(tag, msg, verbose=False):
    if verbose and not _OUT_VERBOSE:
        return
    try:
        t = time.time()
        stamp = time.strftime("%H:%M:%S", time.localtime(t)) + f".{int((t % 1) * 1000):03d}"
        lines = str(msg).splitlines() or [""]
        head = f"[{stamp}] [{_out_thread_name()[:18]:<18}] [{str(tag)[:10]:<10}] "
        pad = "\n" + " " * len(head)
        _out_q.put_nowait(head + lines[0] + "".join(pad + ln for ln in lines[1:]))
    except queue.Full:
        _out_state["dropped"] += 1
    except Exception:
        pass


def _out_write(blob):
    if _OUT_PRINT:
        try:
            so = sys.stdout
            if so is not None:
                try:
                    so.write(blob)
                except UnicodeEncodeError:
                    enc = getattr(so, "encoding", None) or "ascii"
                    so.write(blob.encode(enc, "replace").decode(enc, "replace"))
                so.flush()
        except Exception:
            pass
    try:
        if os.path.exists(_OUT_LOG) and os.path.getsize(_OUT_LOG) > _OUT_MAX:
            old = _OUT_LOG[:-4] + ".old.txt"
            try:
                if os.path.exists(old):
                    os.remove(old)
            except Exception:
                pass
            os.replace(_OUT_LOG, old)
        with open(_OUT_LOG, "a", encoding="utf-8") as f:
            f.write(blob)
    except Exception:
        pass


def _out_pump():
    while True:
        try:
            batch = [_out_q.get()]
            _out_state["busy"] = True
            try:
                while len(batch) < 1000:
                    batch.append(_out_q.get_nowait())
            except queue.Empty:
                pass
            if _out_state["dropped"]:
                batch.append(f"[log] {_out_state['dropped']} log lines were dropped because the log queue was full")
                _out_state["dropped"] = 0
            _out_state["lines"] += len(batch)
            _out_write("\n".join(batch) + "\n")
        except Exception:
            time.sleep(0.2)
        finally:
            _out_state["busy"] = False


def out_flush(timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if _out_q.empty() and not _out_state["busy"]:
            return True
        time.sleep(0.05)
    return False


_plog_last = {}


def plog_throttled(key, tag, msg, every=60.0, on_change=True):
    try:
        now = time.time()
        prev = _plog_last.get(key)
        if prev is not None and now - prev[0] < every and (prev[1] == msg or not on_change):
            return
        _plog_last[key] = (now, msg)
        plog(tag, msg)
    except Exception:
        pass


def _out_start():
    if _out_state["started"]:
        return
    _out_state["started"] = True
    threading.Thread(target=_out_pump, daemon=True, name="log-pump").start()


_out_start()


def _warn_if_ui_thread(what):
    try:
        if not _MAINLOOP_LIVE[0] or threading.current_thread() is not threading.main_thread():
            return
        st = traceback.extract_stack()[:-2]
        caller = f"{st[-1].name}:{st[-1].lineno}" if st else "?"
        key = f"{what}@{caller}"
        n = _ui_block_seen.get(key, 0) + 1
        _ui_block_seen[key] = n
        if n in (1, 10, 100) or n % 1000 == 0:
            plog("UI-BLOCK", f"{what} ran on the UI thread from {caller} (x{n}) - the window cannot repaint while this runs")
    except Exception:
        pass


def _disable_quickedit():
    if platform.system() != "Windows":
        return "n/a (not windows)"
    try:
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-10)
        mode = wintypes.DWORD()
        if not k32.GetConsoleMode(h, ctypes.byref(mode)):
            return "no console attached"
        if not (mode.value & 0x0040):
            return "already off"
        k32.SetConsoleMode(h, (mode.value | 0x0080) & ~0x0040)
        return "turned off (clicking the console can no longer pause the app)"
    except Exception as e:
        return f"could not change it: {e}"


def _rss_mb():
    try:
        if platform.system() == "Windows":
            class _PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = _PMC()
            pmc.cb = ctypes.sizeof(_PMC)
            gp = ctypes.windll.kernel32.GetCurrentProcess
            gp.restype = wintypes.HANDLE
            fn = ctypes.windll.psapi.GetProcessMemoryInfo
            fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
            if fn(gp(), ctypes.byref(pmc), pmc.cb):
                return pmc.WorkingSetSize / 1048576.0
            return -1.0
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1048576.0
    except Exception:
        return -1.0


def _dump_all_stacks(reason, to_crash_log=True):
    lines = [f"{'='*70}", f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] STACK DUMP - {reason}", f"{'='*70}"]
    try:
        frames = sys._current_frames()
        for th in threading.enumerate():
            fr = frames.get(th.ident)
            if fr is None:
                continue
            lines.append(f"--- thread '{th.name}' (daemon={th.daemon}) ---")
            for fs in traceback.extract_stack(fr)[-14:]:
                lines.append(f"    {os.path.basename(fs.filename)}:{fs.lineno} in {fs.name}()  {(fs.line or '').strip()[:110]}")
    except Exception as e:
        lines.append(f"(could not read stacks: {e})")
    blob = "\n".join(lines)
    if to_crash_log:
        write_log(CRASH_LOG, "\n" + blob + "\n\n")
    plog("STACKS", blob)
    return blob


def _spawn(name, target, args=(), daemon=True):
    def _runner():
        plog("THREAD", f"started '{name}'", verbose=True)
        try:
            target(*args)
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as e:
            plog("THREAD", f"'{name}' died: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            raise
        else:
            plog("THREAD", f"'{name}' exited", verbose=True)
    th = threading.Thread(target=_runner, daemon=daemon, name=name)
    th.start()
    return th


import linecache as _linecache


def _ex_where():
    try:
        import inspect
        fr = inspect.currentframe().f_back.f_back
        return f"{fr.f_code.co_name}:{fr.f_lineno}"
    except Exception:
        return "?"


_trace_lock = _threading_module.Lock()
_trace_on = ("--trace" in sys.argv) or ("--debug" in sys.argv) or (os.environ.get("YT2VM_TRACE") == "1")
_TRACE_LOG = f"trace_log{suffix}.txt"
_trace_counts = {}


def _trace(where, exc):
    """Record a swallowed exception. Off by default (adds overhead); enable with
    --trace or YT2VM_TRACE=1. Even off, it still counts them so a hot silent
    failure can be spotted."""
    try:
        key = f"{where}:{type(exc).__name__}"
        n = _trace_counts.get(key, 0) + 1
        _trace_counts[key] = n
        if n in (1, 10, 100, 1000) or n % 10000 == 0 or _OUT_VERBOSE:
            plog("SWALLOWED", f"{key} (x{n}): {str(exc)[:200]}")
        if not _trace_on:
            return
        with _trace_lock:
            with open(_TRACE_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {where}  {type(exc).__name__}: {exc}\n")
    except Exception:
        pass


def log_event(tag, msg):
    """Timestamped line to the rolling session log (and console if enabled)."""
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{tag}] {msg}\n"
    write_log(SESSION_LOG, line)
    plog(tag, msg)


def _crash_line(tb=None):
    """Pull 'file:line in function' for the DEEPEST frame inside yt2vm itself,
    so the log points at OUR code, not deep inside a library."""
    try:
        frames = traceback.extract_tb(tb) if tb is not None else traceback.extract_stack()
        mine = [f for f in frames if "yt2vm" in (f.filename or "").lower()]
        pick = (mine or frames)[-1]
        fn = os.path.basename(pick.filename)
        return f"{fn}:{pick.lineno} in {pick.name}()"
    except Exception:
        return "unknown line"


def log_crash(context, exc=None):
    try:
        where = _crash_line(getattr(exc, "__traceback__", None) if exc is not None else None)
        head = (f"\n{'='*70}\n"
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SCRIPT CRASHED AT LINE: {where}\n"
                f"   context : {context}\n"
                f"   error   : {type(exc).__name__ if exc else '?'}: {exc}\n"
                f"{'='*70}\n")
        body = traceback.format_exc()
        if exc is not None and (not body or "NoneType: None" in body):
            body = f"{type(exc).__name__}: {exc}\n"
        blob = head + body + "\n"
        write_log(CRASH_LOG, blob)
        write_log(CRASH_LINE_LOG, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SCRIPT CRASHED AT LINE: {where}  ({type(exc).__name__ if exc else 'error'}: {exc}) [{context}]\n")
        log_event("CRASH", f"SCRIPT CRASHED AT LINE: {where}  ({context}: {exc})")
        plog("CRASH", blob.strip())
    except Exception:
        pass


def _sys_excepthook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        try: sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        return
    try:
        _w = _crash_line(exc_tb)
        blob = (f"\n{'='*70}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] SCRIPT CRASHED AT LINE: {_w}\n{'='*70}\n"
                + "".join(traceback.format_exception(exc_type, exc_value, exc_tb)) + "\n")
        log_event("CRASH", f"SCRIPT CRASHED AT LINE: {_w} ({exc_type.__name__})")
        write_log(CRASH_LINE_LOG, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SCRIPT CRASHED AT LINE: {_w}  ({exc_type.__name__}: {exc_value})\n")
        write_log(CRASH_LOG, blob)
        plog("CRASH", blob.strip())
        out_flush(1.5)
    except Exception:
        pass
    try: sys.__excepthook__(exc_type, exc_value, exc_tb)
    except Exception as _ex:
        _trace(_ex_where(), _ex)


sys.excepthook = _sys_excepthook


def _thread_excepthook(args):
    if args.exc_type is not None and issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
        return
    try:
        _w = _crash_line(args.exc_traceback)
        _tn = getattr(args.thread, 'name', '?')
        blob = (f"\n{'='*70}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] SCRIPT CRASHED AT LINE: {_w}  (thread {_tn})\n{'='*70}\n"
                + "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)) + "\n")
        log_event("CRASH", f"SCRIPT CRASHED AT LINE: {_w} (thread {_tn})")
        write_log(CRASH_LINE_LOG, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SCRIPT CRASHED AT LINE: {_w}  ({args.exc_type.__name__}: {args.exc_value}) [thread {_tn}]\n")
        write_log(CRASH_LOG, blob)
        plog("CRASH", blob.strip())
    except Exception:
        pass


try:
    _threading_module.excepthook = _thread_excepthook
except Exception:
    pass

def _sigint_handler(signum, frame):
    log_event("SHUTDOWN", f"signal {signum} received - shutting down cleanly")
    try: _jlog_flush()
    except Exception: pass
    out_flush(1.0)
    os._exit(0)


if not IN_IDLE:
    try:
        import signal as _signal
        _signal.signal(_signal.SIGINT, _sigint_handler)
        if hasattr(_signal, "SIGTERM"):
            _signal.signal(_signal.SIGTERM, _sigint_handler)
    except Exception:
        pass

log_event("START", f"yt2vm launching (instance {instance_id}, pid {os.getpid()})")
plog("START", f"yt2vm {version}  instance {instance_id}  pid {os.getpid()}")
plog("START", f"python {sys.version.split()[0]} at {sys.executable}")
plog("START", f"platform {platform.platform()}  cpus={os.cpu_count()}  idle={IN_IDLE}")
plog("START", f"cwd {os.getcwd()}")
plog("START", f"argv {sys.argv}")
plog("START", f"logs -> {_OUT_LOG} (everything printed), {SESSION_LOG}, {CRASH_LOG}, {CRASH_LINE_LOG}, boot_log.txt")
plog("START", f"verbose={_OUT_VERBOSE} (--debug for per-command/per-tick detail, --no-print to silence the console)")
if "--quickedit" not in sys.argv:
    plog("START", f"console quick-edit mode: {_disable_quickedit()}")
def _appdir():
    try:
        d = os.path.dirname(os.path.abspath(sys.argv[0]))
        return d if d and os.path.isdir(d) else os.getcwd()
    except Exception:
        return os.getcwd()

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




_dbf = f"debug_log{suffix}.txt"

DEBUG_ON = ("--quiet" not in sys.argv) and (os.environ.get("YT2VM_DEBUG") != "0")
_dbg_lock = threading.Lock()
_dbg_ring = collections.deque(maxlen=800)

_dv = {"vnc", "vmware", "backend", "vmfinder", "recovery"}
_ds = None

def dbg(category, msg, exc=None):
    try:
        if _ds is not None and str(category) in _dv:
            _ds(f"[{category}] {msg}" + (f" ({type(exc).__name__}: {exc})" if exc else ""))
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
            plog(str(category)[:10], msg + (f"  -> {type(exc).__name__}: {exc}" if exc is not None else ""))
            try:
                with open(_dbf, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass
    except Exception:
        pass

def dbg_run(category, cmd, timeout=15, **kw):
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
        except Exception as _ex:
            _trace(_ex_where(), _ex)

_jlog_pending = {}
_jlog_lock = threading.Lock()
_jlog_state = {"started": False}


def _jlog_flush():
    with _jlog_lock:
        work = dict(_jlog_pending)
        _jlog_pending.clear()
    for fn, entries in work.items():
        try:
            with log_lock:
                logs = []
                if os.path.exists(fn):
                    try:
                        with open(fn, "r", encoding="utf-8") as f:
                            logs = json.load(f)
                        if not isinstance(logs, list):
                            logs = []
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
                logs.extend(entries)
                if len(logs) > 1000:
                    logs = logs[-1000:]
                safe_json_dump(fn, logs)
        except Exception as _ex:
            _trace(_ex_where(), _ex)


def _jlog_loop():
    while True:
        time.sleep(2.0)
        try:
            _jlog_flush()
        except Exception as _ex:
            _trace(_ex_where(), _ex)


def _jlog_add(filename, entry):
    with _jlog_lock:
        lst = _jlog_pending.setdefault(filename, [])
        lst.append(entry)
        if len(lst) > 2000:
            del lst[:-1000]
    if not _jlog_state["started"]:
        _jlog_state["started"] = True
        threading.Thread(target=_jlog_loop, daemon=True, name="json-log-writer").start()


def append_to_json_log(filename, user, command):
    _jlog_add(filename, {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "username": user, "command": command})

def append_to_all_msgs_log(user, msg):
    try:
        with log_lock:
            entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "username": user, "message": msg}
            with open(allmsglogs_file, "a", encoding="utf-8") as f: f.write(json.dumps(entry) + "\n")
    except Exception as _ex:
        _trace(_ex_where(), _ex)

def log_vote_action(action, user, vote_type, target, current_votes=0):
    _jlog_add(voteslogs_file, {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action.lower(), "user": user,
                               "vote": vote_type, "progress": f"{current_votes}/{target}" if current_votes else str(target)})


def log_music_action(action, user, title, url=""):
    _jlog_add(musiclogs_file, {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": action, "user": user, "title": title, "url": url})


def console_log(level, msg):
    timestamp = time.strftime("%H:%M:%S")
    date_stamp = time.strftime("%Y-%m-%d")
    log_line = f"[{timestamp}] [{level.lower()}] {msg.lower()}"
    log_event(level.upper(), msg)
    try: gui_log_queue.put_nowait((level, log_line))
    except queue.Full: pass
    try:
        with log_lock:
            with open(log_file, "a", encoding="utf-8") as f: f.write(f"[{date_stamp} {timestamp}] [{level.lower()}] {msg.lower()}\n")
    except Exception as _ex:
        _trace(_ex_where(), _ex)

_pp = [
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
    r"D:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    r"E:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage",
    "/usr/bin/VBoxManage", "/usr/local/bin/VBoxManage", "/opt/VirtualBox/VBoxManage",
    "VBoxManage"]

_vrp = [
    r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
    r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
    r"D:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
    r"E:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
    "/Applications/VMware Fusion.app/Contents/Library/vmrun",
    "/usr/bin/vmrun", "/usr/local/bin/vmrun", "/opt/vmware/bin/vmrun"]

def find_vmrun():
    for pth in _vrp:
        if os.path.exists(pth): return pth
    found = shutil.which("vmrun")
    return found or _vrp[0]
vbox_manage_cmd, _vbox_how = "VBoxManage", "not found"
_which = shutil.which("VBoxManage") or shutil.which("vboxmanage")
if _which:
    vbox_manage_cmd, _vbox_how = _which, "PATH"
else:
    for path in _pp:
        if os.path.exists(path):
            vbox_manage_cmd, _vbox_how = path, "known location"
            break

_vmw = False

def run_vbox(args, timeout=10):
    global _vmw
    if _active_backend() == "vmware":
        return None
    if resolve_vbox_path(vbox_manage_cmd)[1] == "not found":
        if not _vmw:
            _vmw = True
            dbg("vbox", "VBoxManage not installed - VirtualBox commands are disabled")
        return None
    global _vlk
    _desc = " ".join(str(a) for a in args)[:140]
    _warn_if_ui_thread(f"VBoxManage {_desc[:40]}")
    _t0 = time.time()
    if DEBUG_ON:
        r = dbg_run("vbox", [vbox_manage_cmd] + list(args), timeout=timeout)
    else:
        try:
            r = subprocess.run([vbox_manage_cmd] + list(args), capture_output=True, text=True, timeout=timeout)
        except Exception as _e:
            plog("VBOX", f"VBoxManage {_desc} failed to run: {type(_e).__name__}: {_e}")
            r = None
    _el = time.time() - _t0
    if r is None:
        plog("VBOX", f"VBoxManage {_desc} gave no result after {_el:.1f}s (timeout {timeout}s or not runnable)")
    elif _el > 5:
        plog("VBOX", f"SLOW VBoxManage {_desc} took {_el:.1f}s rc={r.returncode}")
    elif r.returncode != 0:
        plog("VBOX", f"VBoxManage {_desc} rc={r.returncode} {_el*1000:.0f}ms err={(r.stderr or '').strip()[:160]!r}")
    else:
        plog("VBOX", f"VBoxManage {_desc} ok {_el*1000:.0f}ms", verbose=True)
    if r is not None:
        _vlk = is_vbox_lock_error(r.stderr) or is_vbox_lock_error(r.stdout)
    return r

def is_vbox_lock_error(txt):
    t = str(txt or "").lower()
    return any(m in t for m in (
        "is already locked", "already locked by a session",
        "vbox_e_invalid_object_state", "0x80bb0007",
        "locked for a session", "session is locked",
        "the machine is not mutable", "vbox_e_object_in_use",
        "0x80bb000c", "a session for the machine",
        "cannot lock", "e_accessdenied while ", "already has a lock"))

_vle = ""
_vlk = False
_sw = set()

def _active_backend():
    global _rb
    try:
        if _rb: return _rb
    except NameError:
        pass
    try:
        if os.path.exists(settings_file):
            return str(json.load(open(settings_file)).get("backend", "virtualbox")).lower()
    except Exception:
        pass
    return "virtualbox"

_rb = ""

def resolve_vbox_path(preferred=""):
    if preferred and (os.path.exists(preferred) or shutil.which(preferred)):
        return preferred, "configured"
    found = shutil.which("VBoxManage") or shutil.which("vboxmanage")
    if found:
        return found, "PATH"
    for pth in _pp:
        if os.path.exists(pth):
            return pth, "known location"
    return "VBoxManage", "not found"

def get_all_vbox_vms(vbox_path="VBoxManage", quiet=False):
    global _vle
    vms = []
    if _active_backend() == "vmware":
        _vle = ""
        return []
    path, how = resolve_vbox_path(vbox_path)
    _warn_if_ui_thread("VBoxManage list vms")
    dbg("vmfinder", f"listing vms using {path!r} (found via {how})")
    if how == "not found":
        _vle = ("VBoxManage not found. Install VirtualBox, or set the path "
                           "on the VM Config page.")
        dbg("vmfinder", _vle)
        if not quiet: console_log("ERROR", _vle)
        return []
    try:
        res = subprocess.run([path, "list", "vms"], capture_output=True, text=True, timeout=20)
        dbg("vmfinder", f"rc={res.returncode} stdout={len(res.stdout or '')}b stderr={(res.stderr or '').strip()[:120]}")
        if res.returncode != 0:
            _vle = (res.stderr or "").strip() or f"VBoxManage exited {res.returncode}"
            if not quiet: console_log("ERROR", f"vm list failed: {_vle[:160]}")
            return []
        for line in (res.stdout or "").splitlines():
            if '"' in line:
                name = line.split('"')[1]
                if name: vms.append(name)
        _vle = "" if vms else "VirtualBox reported no VMs on this machine."
        dbg("vmfinder", f"found {len(vms)} vm(s): {vms}")
        if not vms and not quiet:
            console_log("SYSTEM", "no virtualbox vms found - create one in VirtualBox first.")
    except subprocess.TimeoutExpired:
        _vle = "VBoxManage timed out (VBoxSVC may be starting or hung)."
        dbg("vmfinder", _vle)
        if not quiet: console_log("ERROR", _vle)
    except FileNotFoundError:
        _vle = f"VBoxManage not executable at {path}"
        dbg("vmfinder", _vle)
        if not quiet: console_log("ERROR", _vle)
    except Exception as e:
        _vle = f"{type(e).__name__}: {e}"
        dbg("vmfinder", "vm list crashed", e)
        if not quiet: console_log("ERROR", f"vm list error: {e}")
    return vms

def get_vbox_snapshots(vbox_path, vm_name):
    global _sw
    snaps = []
    if not vm_name:
        return snaps
    if _active_backend() == "vmware":
        return snaps
    path, how = resolve_vbox_path(vbox_path)
    if how == "not found":
        if "nopath" not in _sw:
            _sw.add("nopath")
            dbg("snapshots", "VBoxManage not installed - skipping snapshot lookups")
        return snaps
    _warn_if_ui_thread("VBoxManage snapshot list")
    try:
        res = subprocess.run([path, "snapshot", vm_name, "list"],
                             capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            err = (res.stderr or "").strip()
            if "does not have any snapshots" not in err.lower():
                key = f"rc:{vm_name}"
                if key not in _sw:
                    _sw.add(key)
                    dbg("snapshots", f"list failed for {vm_name}: {err[:140]}")
            return snaps
        for line in (res.stdout or "").splitlines():
            if "Name:" in line and "(UUID:" in line:
                part = line.split("Name:")[1].split("(UUID:")[0].strip()
                if part: snaps.append(part)
        _sw.discard(f"err:{vm_name}")
        dbg("snapshots", f"{vm_name}: {len(snaps)} snapshot(s) {snaps}")
    except subprocess.TimeoutExpired:
        key = f"to:{vm_name}"
        if key not in _sw:
            _sw.add(key)
            dbg("snapshots", f"timeout listing snapshots for {vm_name}")
    except FileNotFoundError:
        if "nopath" not in _sw:
            _sw.add("nopath")
            dbg("snapshots", f"VBoxManage not found at {path} - skipping snapshot lookups")
    except Exception as e:
        key = f"err:{vm_name}"
        if key not in _sw:
            _sw.add(key)
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
    vm_name = "Windows10ChatVm"

_dbt = []

_dpl = [
    "shutdown", "logoff", "poweroff", "slidetoshutdown", "format ", "diskpart",
    "bcdedit", "vssadmin", "cipher /w", "del /f", "del /q", "rd /s", "rmdir /s",
    "reg delete", "regdelete", "rundll32", "taskkill", "net user", "net localgroup",
    "wmic ", "powershell -e", "-encodedcommand", "invoke-expression", "iex(",
    "downloadstring", "certutil -urlcache", "bitsadmin /transfer", "mshta ",
    "attrib +h", "icacls", "takeown", "sc delete", "schtasks /create",
    "wscript", "cscript", "vssadmin delete", "cipher", "fsutil",
]
_igt = [
    "iplogger", "grabify", "ipgrabber", "ipinfo", "ifconfig.me", "icanhazip",
    "whatismyip", "whatismyipaddress", "ipify", "ip-api", "ipapi", "freegeoip",
    "geoip", "iplocation", "iptracker", "ip-tracker", "blasze", "yip.su", "2no.co",
    "ipstack", "ipdata", "showmyip", "myipaddress", "ip-lookup", "iplocator",
]
_LEET_MAP = {"0":"o","1":"i","2":"z","3":"e","4":"a","5":"s","6":"g","7":"t","8":"b",
             "9":"g","@":"a","$":"s","!":"i","|":"i","+":"t"}

def normalize_payload(text):
    out = []
    for ch in str(text).lower():
        ch = _LEET_MAP.get(ch, ch)
        if "a" <= ch <= "z": out.append(ch)
    res = []
    for ch in out:
        if not res or res[-1] != ch: res.append(ch)
    return "".join(res)

class FairCommandQueue:

    def __init__(self, cfg=None):
        self._cv = threading.Condition()
        self._prio = collections.deque()
        self._users = collections.OrderedDict()
        self._cur = None
        self._n = 0
        self._cfg = cfg or (lambda k, d: d)
        self.stats = {"jobs": 0, "stale": 0, "capped": 0, "overflow": 0}
        self._note_t = {}

    def _limit(self, key, default, lo, hi):
        try:
            v = float(self._cfg(key, default))
        except Exception:
            v = default
        return max(lo, min(hi, v))

    def _note(self, kind, user):
        now = time.time()
        if now - self._note_t.get(kind, 0) < 10:
            return
        self._note_t[kind] = now
        n = self.stats[kind]
        if kind == "capped":
            plog("QUEUE", f"{user} has too many commands waiting - dropped their oldest so their newest runs (total dropped this way: {n})")
        elif kind == "stale":
            plog("QUEUE", f"dropped a command from {user} that waited longer than {self._limit('queue_max_age', 30, 3, 3600):.0f}s (total: {n})")
        else:
            plog("QUEUE", f"queue full - dropped the oldest command from {user}, the viewer with the most waiting (total: {n})")

    def _viewer_jobs(self):
        return sum(len(dq) for dq in self._users.values())

    def put(self, item, block=True, timeout=None):
        user = item[2] if isinstance(item, (tuple, list)) and len(item) > 2 else "?"
        self.put_job([item], user, prio=True)

    def put_nowait(self, item):
        self.put(item)

    def put_job(self, items, user, prio=False):
        items = [x for x in items if x]
        if not items:
            return
        job = {"items": collections.deque(items), "user": str(user), "t": time.time()}
        with self._cv:
            if prio:
                self._prio.append(job)
            else:
                key = str(user).lower()
                dq = self._users.get(key)
                if dq is None:
                    dq = self._users[key] = collections.deque()
                cap = int(self._limit("queue_per_user", 2, 1, 20))
                while len(dq) >= cap:
                    old = dq.popleft()
                    self._n -= len(old["items"])
                    self.stats["capped"] += 1
                    self._note("capped", user)
                dq.append(job)
                maxjobs = int(self._limit("queue_max_jobs", 150, 10, 5000))
                while self._viewer_jobs() + 1 > maxjobs and self._users:
                    big = max(self._users, key=lambda u: len(self._users[u]))
                    old = self._users[big].popleft()
                    self._n -= len(old["items"])
                    if not self._users[big]:
                        del self._users[big]
                    self.stats["overflow"] += 1
                    self._note("overflow", old["user"])
            self._n += len(items)
            self.stats["jobs"] += 1
            self._cv.notify()

    def _next_job(self):
        if self._prio:
            return self._prio.popleft()
        max_age = self._limit("queue_max_age", 30, 3, 3600)
        now = time.time()
        while self._users:
            key = next(iter(self._users))
            dq = self._users[key]
            job = dq.popleft() if dq else None
            if dq:
                self._users.move_to_end(key)
            else:
                del self._users[key]
            if job is None:
                continue
            if now - job["t"] > max_age:
                self._n -= len(job["items"])
                self.stats["stale"] += 1
                self._note("stale", job["user"])
                continue
            return job
        return None

    def get(self, block=True, timeout=None):
        end = None if timeout is None else time.time() + timeout
        with self._cv:
            while True:
                if self._cur is not None and not self._cur["items"]:
                    self._cur = None
                if self._cur is None:
                    self._cur = self._next_job()
                if self._cur is not None and self._cur["items"]:
                    self._n -= 1
                    return self._cur["items"].popleft()
                if not block:
                    raise queue.Empty
                rem = None if end is None else end - time.time()
                if rem is not None and rem <= 0:
                    raise queue.Empty
                self._cv.wait(rem)

    def get_nowait(self):
        return self.get(False)

    def qsize(self):
        with self._cv:
            return max(0, self._n)

    def empty(self):
        return self.qsize() == 0

    def clear(self):
        with self._cv:
            n = max(0, self._n)
            self._prio.clear()
            self._users.clear()
            self._cur = None
            self._n = 0
            return n

    def waiting_viewers(self):
        with self._cv:
            return len(self._users)


class _RecentIds:

    def __init__(self, cap=20000):
        self._s = set()
        self._d = collections.deque()
        self.cap = cap

    def add(self, x):
        if x in self._s:
            return
        self._s.add(x)
        self._d.append(x)
        while len(self._d) > self.cap:
            self._s.discard(self._d.popleft())

    def __contains__(self, x):
        return x in self._s

    def __len__(self):
        return len(self._s)

    def clear(self):
        self._s.clear()
        self._d.clear()


_KNOWN_CMDS = frozenset("""abs alert allowshell altgr announce autoclose backend ban bans blacklist blockword c changevm clear
clearvotes click closedialog cmd coinflip combo cooldown d dismiss drag enablechat enablecv errors fixscript fixvm flash
forcefixvm k kd key keydown keyup kill killglobal killsvc killtightvnc killvnc ku lc lockdown lowpower m makesnapshot
mclick modhelp move music mute nuke pardon pausechat pausesong pin ping protect purge queue ratelimit rc rclick rebuild
remake2 replay restartnow restartvm resumesong revert revertnow roll run s say scene scroll send settle shout shutdown
skip skipsong slowmode snapshotnow startvm stats stopsong strikes swichsnapshot switchsnapshot t testanticopyright
timeout title trace type unban unlock unlockall unmute uptime vmstatus vmswitch volumedown volumeup votedrop voterandom
votereplay voteshuffle votestop w wait warn whois lclick tob64 eb64 unblock unb64 plugins plugin
help lock screen screenshot""".split())


_B64_ALPHA_RUN = re.compile(r"[A-Za-z0-9+/]{64,}={0,2}")
_B64_PS_HOST = re.compile(r"\b(powershell|pwsh)(\.exe)?\b")
_B64_PS_ENC = re.compile(r"(?:^|\s)[-/](?:e|ec|en|enc|enco|encod|encode|encoded|encodedc|encodedco|encodedcom|encodedcomm|"
                         r"encodedcomma|encodedcomman|encodedcommand|encodedarguments|ea)\s+[a-z0-9+/]{8,}={0,2}")
_B64_RULES = (
    (re.compile(r"frombase64"), "FromBase64String decode"),
    (re.compile(r"b64decode|a2b_base64|decodebytes|decodestring|standard_b64decode|urlsafe_b64decode"), "python base64 decode"),
    (re.compile(r"import\W{0,4}base64|from\W{0,4}base64\W{0,4}import|__import__\W{0,4}base64"), "python base64 import"),
    (re.compile(r"codecs\W{0,4}decode.{0,40}base64|['\"]base64['\"]\W{0,4}\)\W{0,4}decode"), "python codecs base64"),
    (re.compile(r"certutil(?:\.exe)?\W{0,4}[-/](?:decode|decodehex|urlcache)"), "certutil -decode"),
    (re.compile(r"\bbase64\s+(?:-d|--decode|-D|-di)\b"), "base64 --decode"),
    (re.compile(r"openssl\s+(?:enc\s+)?(?:-a\s+)?(?:-d\s+)?base64|openssl\s+enc\s+-d\s+-base64"), "openssl base64"),
    (re.compile(r"data:[a-z0-9.+-]+/[a-z0-9.+-]+;base64,"), "base64 data URI"),
    (re.compile(r"\batob\s*\("), "javascript atob"),
    (re.compile(r"convert\W{0,4}::\W{0,4}from"), "[Convert]:: decode"),
)


def _b64_scan(text):
    raw = str(text or "")
    if len(raw) < 8:
        return None
    norm = raw.replace("^", "").replace("`", "")
    low = norm.lower()
    squash = re.sub(r"[\s'\"+(),&{}\[\]$;]", "", low)
    if _B64_PS_HOST.search(low) or _B64_PS_HOST.search(squash):
        if _B64_PS_ENC.search(" " + re.sub(r"['\"]", "", low)):
            return "PowerShell -EncodedCommand"
    for rx, why in _B64_RULES:
        if rx.search(low) or rx.search(squash):
            return why
    for m in _B64_ALPHA_RUN.finditer(norm):
        run = m.group(0).rstrip("=")
        kinds = sum(1 for test in (str.isupper, str.islower, str.isdigit) if any(test(c) for c in run))
        uniq = len(set(run))
        if len(run) >= 64 and kinds >= 2 and uniq >= 18:
            return f"{len(run)}-character base64 blob"
    return None


def _token_file():
    return os.path.splitext(settings_file)[0] + "_discord_token.json"


def _dpapi(data, protect):
    from ctypes import wintypes as _wt
    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", _wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0x01, ctypes.byref(blob_out)):
        raise OSError(f"DPAPI {'protect' if protect else 'unprotect'} failed ({ctypes.GetLastError()})")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))


def _clean_token(token):
    t = str(token or "").strip().strip("\"'").strip()
    if t.lower().startswith("bot "):
        t = t[4:].strip()
    return t


def discord_token_save(token):
    import base64 as _b
    token = _clean_token(token)
    doc = {"v": 1}
    if token:
        if platform.system() == "Windows":
            try:
                doc["dpapi"] = _b.b64encode(_dpapi(token.encode("utf-8"), True)).decode("ascii")
            except Exception as e:
                plog("DISCORD", f"DPAPI unavailable ({e}) - token stored without encryption")
                doc["plain"] = token
        else:
            doc["plain"] = token
    path = _token_file()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    return "dpapi" in doc


def discord_token_load():
    import base64 as _b
    try:
        with open(_token_file(), "r") as f:
            doc = json.load(f)
    except Exception:
        return ""
    if doc.get("dpapi"):
        try:
            return _dpapi(_b.b64decode(doc["dpapi"]), False).decode("utf-8")
        except Exception as e:
            plog("DISCORD", f"saved token could not be decrypted ({e}) - paste it again")
            return ""
    return str(doc.get("plain", ""))


def _dc_name(user):
    base = re.sub(r"[^a-z0-9_.]", "", str(getattr(user, "name", "") or "").lower())
    return "dc_" + (base or str(getattr(user, "id", "user")))


class DiscordBridge:

    SETTLE = 0.9
    MAX_BATCH_WAIT = 4.0
    SHOT_GAP = 2.5
    LOG_GAP = 2.0

    def __init__(self, app):
        self.app = app
        self.thread = None
        self.loop = None
        self.client = None
        self.state = "stopped"
        self.detail = ""
        self.mode = "crossplay"
        self.user_tag = ""
        self.guilds = []
        self.inbox = queue.Queue(maxsize=2000)
        self._pressed = collections.deque(maxlen=300)
        self._announce = collections.deque(maxlen=60)
        self._logq = collections.deque(maxlen=3000)
        self._stop = threading.Event()
        self._gen = 0
        self._msgs = collections.OrderedDict()
        self._first_press = 0.0
        self._last_press = 0.0
        self._last_shot = 0.0
        self._last_log = 0.0
        self._warned = {}
        self._empty_seen = 0
        self.stats = {"in": 0, "cmds": 0, "sent": 0, "shots": 0, "blocked": 0, "errors": 0}
        self.events = collections.deque(maxlen=200)
        self.dirty = True
        self.guilds_dirty = True
        self._ingest_thread = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    @property
    def online(self):
        return self.running and self.state == "online"

    def cfg(self, key, default=None):
        return self.app.config.get(key, default)

    def _id(self, key):
        try:
            return int(str(self.cfg(key, "") or "0").strip() or 0)
        except Exception:
            return 0

    def event(self, text):
        self.events.append((time.strftime("%H:%M:%S"), str(text)))
        self.dirty = True

    def _set_state(self, state, detail=""):
        changed = (state, detail) != (self.state, self.detail)
        self.state, self.detail = state, detail
        self.dirty = True
        if changed:
            plog("DISCORD", f"{state}" + (f" - {detail}" if detail else ""))
            self.event(f"{state}" + (f": {detail}" if detail else ""))

    def _warn_once(self, key, text, every=60):
        now = time.time()
        if now - self._warned.get(key, 0) < every:
            return
        self._warned[key] = now
        self.event(text)
        plog("DISCORD", text)

    def start(self, token, mode="crossplay"):
        self.mode = mode if mode in ("crossplay", "discord") else "crossplay"
        self.dirty = True
        self._want = True
        if self.running:
            if self._stop.is_set():
                old = self.thread
                def _restart(old=old, token=token, mode=mode):
                    try:
                        old.join(timeout=20)
                    except Exception:
                        pass
                    if getattr(self, "_want", False) and not self.running:
                        self.start(token, mode)
                threading.Thread(target=_restart, daemon=True, name="discord-restart").start()
                self.event("restarting - waiting for the old connection to close")
                return
            self.event(f"mode set to {self.mode_label()}")
            return
        token = _clean_token(token)
        if not token:
            self._set_state("error", "paste the bot token first")
            return
        self._stop.clear()
        self._gen += 1
        gen = self._gen
        self.thread = threading.Thread(target=self._thread_main, args=(token, gen), daemon=True, name="discord-bot")
        self.thread.start()
        if self._ingest_thread is None or not self._ingest_thread.is_alive():
            self._ingest_thread = threading.Thread(target=self._ingest_loop, daemon=True, name="discord-ingest")
            self._ingest_thread.start()

    def stop(self):
        self._want = False
        self._stop.set()
        self._gen += 1
        loop, client = self.loop, self.client
        if loop is not None and client is not None:
            try:
                asyncio.run_coroutine_threadsafe(client.close(), loop)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        self.dirty = True

    def mode_label(self):
        return "Discord + YouTube crossplay" if self.mode == "crossplay" else "Discord only"

    def _import(self):
        try:
            import discord
            return discord
        except Exception:
            pass
        self._set_state("installing", "installing discord.py (first time only) ...")
        ok, err = _pip_install(["discord.py"])
        try:
            import importlib
            importlib.invalidate_caches()
            import discord
            self.event("discord.py installed")
            return discord
        except Exception as e:
            self._set_state("error", f"discord.py could not be installed: {(err or str(e))[:160]}")
            return None

    def _thread_main(self, token, gen):
        discord = self._import()
        if discord is None:
            return
        errs = getattr(discord, "errors", discord)
        login_fail = getattr(errs, "LoginFailure", None) or getattr(discord, "LoginFailure", Exception)
        intents_fail = getattr(errs, "PrivilegedIntentsRequired", None) or getattr(discord, "PrivilegedIntentsRequired", None)
        delay = 5
        while not self._stop.is_set() and gen == self._gen:
            self._set_state("connecting", "logging in")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            client = None
            fatal = None
            err = "connection closed"
            try:
                client = self._make_client(discord)
                self.loop, self.client = loop, client
                loop.run_until_complete(self._runner(client, token))
            except login_fail:
                fatal = "Discord rejected the token. Copy a fresh one from the Developer Portal (Bot > Reset Token)."
            except Exception as e:
                if intents_fail is not None and isinstance(e, intents_fail):
                    fatal = "Turn on MESSAGE CONTENT INTENT in the Developer Portal (Bot > Privileged Gateway Intents), then press Enable again."
                else:
                    err = f"{type(e).__name__}: {str(e)[:140]}"
                    self.stats["errors"] += 1
            finally:
                try:
                    if client is not None and not client.is_closed():
                        loop.run_until_complete(client.close())
                except Exception:
                    pass
                try:
                    pend = [t for t in asyncio.all_tasks(loop) if not t.done()]
                    for t in pend:
                        t.cancel()
                    if pend:
                        loop.run_until_complete(asyncio.gather(*pend, return_exceptions=True))
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    pass
                self.loop, self.client = None, None
            if fatal:
                self._set_state("error", fatal)
                return
            if self._stop.is_set() or gen != self._gen:
                break
            self._set_state("error", f"disconnected ({err}) - retrying in {delay}s")
            self._stop.wait(delay)
            delay = min(delay * 2, 120)
        if gen == self._gen or self._stop.is_set():
            self._set_state("stopped", "")

    async def _runner(self, client, token):
        flusher = asyncio.ensure_future(self._flush_loop(client))
        try:
            await client.start(token)
        finally:
            flusher.cancel()

    def _make_client(self, discord):
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        bridge = self

        @client.event
        async def on_ready():
            bridge.user_tag = str(client.user)
            bridge._scan(client)
            bridge._set_state("online", f"logged in as {bridge.user_tag}")

        @client.event
        async def on_message(message):
            try:
                bridge._on_message(client, message)
            except Exception as e:
                bridge.stats["errors"] += 1
                _trace(_ex_where(), e)

        for name in ("on_guild_join", "on_guild_remove", "on_guild_channel_create",
                     "on_guild_channel_delete", "on_guild_channel_update", "on_guild_update"):
            async def _rescan(*a, **k):
                bridge._scan(client)
            _rescan.__name__ = name
            client.event(_rescan)
        return client

    def _scan(self, client):
        out = []
        try:
            for g in sorted(client.guilds, key=lambda x: str(x.name).lower()):
                me = getattr(g, "me", None)
                chans = []
                for c in getattr(g, "text_channels", []):
                    ok = True
                    try:
                        if me is not None:
                            p = c.permissions_for(me)
                            ok = bool(p.view_channel and p.send_messages)
                    except Exception:
                        ok = True
                    chans.append((int(c.id), str(c.name), ok))
                out.append((int(g.id), str(g.name), chans))
        except Exception as e:
            _trace(_ex_where(), e)
        self.guilds = out
        self.guilds_dirty = True
        self.dirty = True

    def channel_name(self, cid):
        for gid, gname, chans in self.guilds:
            for c, n, ok in chans:
                if c == cid:
                    return f"{gname} / #{n}"
        return ""

    def _on_message(self, client, message):
        author = message.author
        if getattr(author, "bot", False) or (client.user is not None and author.id == client.user.id):
            return
        play = self._id("discord_channel_id")
        if not play or int(message.channel.id) != play:
            return
        content = str(message.content or "")
        try:
            for mem in getattr(message, "mentions", []) or []:
                content = re.sub(rf"<@!?{int(mem.id)}>", _dc_name(mem), content)
        except Exception:
            pass
        if not content.strip():
            if not getattr(message, "attachments", None) and not getattr(message, "embeds", None):
                self._empty_seen += 1
                if self._empty_seen >= 3:
                    self._warn_once("intent", "messages arrive empty - turn on MESSAGE CONTENT INTENT for the bot in the Developer Portal", 300)
            return
        self._empty_seen = 0
        name = _dc_name(author)
        display = str(getattr(author, "display_name", "") or getattr(author, "name", name))
        guild = message.guild
        owner_ids = set()
        for tok in re.split(r"[\s,;]+", str(self.cfg("discord_owner_ids", "") or "")):
            if tok.strip().isdigit():
                owner_ids.add(int(tok.strip()))
        is_owner = int(author.id) in owner_ids or (guild is not None and int(getattr(guild, "owner_id", 0) or 0) == int(author.id))
        perms = getattr(author, "guild_permissions", None)
        is_mod = bool(is_owner or (perms is not None and (perms.administrator or perms.manage_messages or perms.manage_guild)))
        self.stats["in"] += 1
        self._msgs[int(message.id)] = message
        while len(self._msgs) > 300:
            self._msgs.popitem(last=False)
        shown = content
        if self.cfg("b64_filter", True) and _b64_scan(content):
            shown = f"[blocked by base64 filter - {len(content)} chars hidden]"
        self.log_line(f"{display} ({name}){' [owner]' if is_owner else (' [mod]' if is_mod else '')}: {shown}")
        try:
            self.inbox.put_nowait((name, content, is_mod, is_owner, int(message.id), display))
        except queue.Full:
            self._warn_once("inbox", "too many Discord messages at once - some were dropped", 30)

    def _ingest_loop(self):
        while True:
            try:
                item = self.inbox.get(timeout=1.0)
            except queue.Empty:
                if self._stop.is_set() and not self.running:
                    if self.inbox.empty():
                        return
                continue
            name, content, is_mod, is_owner, mid, display = item
            try:
                res = self.app._ingest_chat(name, content, is_mod, is_owner, source="discord", ref=mid, display=display)
                if res == "cmd":
                    self.stats["cmds"] += 1
            except Exception as e:
                self.stats["errors"] += 1
                log_crash("discord ingest", e)

    _VERB = {"type": "typed", "send": "sent", "key": "pressed", "combo": "pressed combo",
             "keydown": "held", "keyup": "released", "click": "clicked", "rclick": "right-clicked",
             "mclick": "middle-clicked", "move": "moved the mouse", "abs": "moved the mouse",
             "scroll": "scrolled", "drag": "dragged the mouse", "run": "ran", "cmd": "ran in CMD",
             "roll": "rolled the dice", "coinflip": "flipped a coin", "startvm": "started the VM"}
    _NOARG = {"click", "rclick", "mclick", "roll", "coinflip", "scroll", "move", "abs", "drag"}

    def pressed(self, cmd, arg, user):
        now = time.time()
        if not self._pressed:
            self._first_press = now
        self._last_press = now
        who = str(user)[3:] if str(user).startswith("dc_") else str(user)
        base = str(cmd).lower().lstrip("!")
        verb = self._VERB.get(base, "ran")
        a = str(arg or "").replace("`", "'").replace("\n", " ").strip()
        if base in self._NOARG or not a:
            line = f"{who} {verb}"
        elif len(a) > 120:
            line = f"{who} {verb}: `!{base}` (too long for Discord to show here, but your command will be run)"
        else:
            line = f"{who} {verb} `{a}`"
        self._pressed.append(line)
        self.log_line(f"executed !{base} {a} for {user}")

    def screenshot_now(self, requester):
        loop = self.loop
        if loop is None or self.client is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._do_screenshot(requester), loop)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    async def _do_screenshot(self, requester):
        ch = self._chan(self.client, "discord_channel_id")
        if ch is None:
            return
        who = str(requester)[3:] if str(requester).startswith("dc_") else str(requester)
        loop = asyncio.get_running_loop()
        for attempt in (1, 2):
            path, why = None, ""
            try:
                path, why = await loop.run_in_executor(None, self.app._capture_vm_png)
            except Exception as e:
                path, why = None, f"{type(e).__name__}"
            if not path:
                if why in ("VM is not running", "VNC not connected", "VNC capture unavailable"):
                    await self._send(ch, f"Can't take a screenshot: {why}.")
                    return
                await asyncio.sleep(0.6)
                continue
            ok = await self._send(ch, f"Screenshot (asked by {who})", path)
            try:
                os.remove(path)
            except Exception:
                pass
            if ok:
                self.stats["shots"] += 1
                return
            await asyncio.sleep(0.6)
        await self._send(ch, "Uploading image didnt work tried 2 times Still not working")

    def announce(self, text):
        self._announce.append(str(text))

    def maint_announce(self, text, shot=False):
        if not shot:
            self.announce(text)
            return
        loop = self.loop
        if loop is None or self.client is None:
            self.announce(text)
            return
        try:
            asyncio.run_coroutine_threadsafe(self._announce_shot(str(text)), loop)
        except Exception:
            self.announce(text)

    async def _announce_shot(self, text):
        ch = self._chan(self.client, "discord_channel_id")
        if ch is None:
            return
        path, why = None, ""
        if self.cfg("discord_screens", True):
            loop = asyncio.get_running_loop()
            try:
                path, why = await loop.run_in_executor(None, self.app._capture_vm_png)
            except Exception as e:
                path, why = None, f"{type(e).__name__}"
        if not path and why:
            text += f"\n_(no screenshot: {why})_"
        await self._send(ch, text[:1990], path)
        if path:
            try:
                os.remove(path)
            except Exception:
                pass

    def log_line(self, text):
        if not self.cfg("discord_log_all", True) and not str(text).startswith("[!]"):
            return
        self._logq.append(f"[{time.strftime('%H:%M:%S')}] {text}")

    def delete_message(self, mid):
        msg = self._msgs.get(int(mid or 0))
        loop = self.loop
        if msg is None or loop is None:
            return
        async def _del():
            try:
                await msg.delete()
                self.event(f"deleted the blocked message from {_dc_name(msg.author)}")
            except Exception as e:
                self._warn_once("delete", f"could not delete the blocked message ({type(e).__name__}) - give the bot Manage Messages", 120)
        try:
            asyncio.run_coroutine_threadsafe(_del(), loop)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def on_blocked(self, user, why, ref=None):
        self.stats["blocked"] += 1
        self.announce(f"Blocked {user}: base64 filter ({why}). That account can't send commands anymore.")
        self.log_line(f"[!] base64 filter blocked {user}: {why}")
        self.event(f"base64 filter blocked {user} ({why})")
        if ref:
            self.delete_message(ref)

    async def _flush_loop(self, client):
        try:
            await client.wait_until_ready()
        except Exception:
            return
        while not client.is_closed():
            await asyncio.sleep(0.4)
            try:
                await self._flush_once(client)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.stats["errors"] += 1
                self._warn_once("flush", f"send failed: {type(e).__name__}: {str(e)[:120]}", 30)

    def _chan(self, client, key):
        cid = self._id(key)
        if not cid:
            return None
        ch = client.get_channel(cid)
        if ch is None:
            self._warn_once("chan" + key, f"channel {cid} not found - pick it again on the Discord page", 120)
        return ch

    async def _send(self, ch, content=None, path=None):
        discord = sys.modules.get("discord")
        kw = {}
        try:
            kw["allowed_mentions"] = discord.AllowedMentions.none()
        except Exception:
            pass
        if path:
            kw["file"] = discord.File(path, filename="vm.png")
        try:
            await ch.send(content=content, **kw)
            self.stats["sent"] += 1
            return True
        except Exception as e:
            nm = type(e).__name__
            if nm == "Forbidden":
                self._warn_once("forbid" + str(getattr(ch, "id", "")), f"no permission to post in #{getattr(ch, 'name', '?')} - give the bot Send Messages and Attach Files", 120)
            else:
                self._warn_once("send" + nm, f"send failed: {nm}: {str(e)[:120]}", 30)
            self.stats["errors"] += 1
            return False

    @staticmethod
    def _chunks(lines, limit=1900):
        out, cur = [], ""
        for ln in lines:
            ln = ln if len(ln) <= limit else ln[:limit - 3] + "..."
            if cur and len(cur) + 1 + len(ln) > limit:
                out.append(cur)
                cur = ln
            else:
                cur = (cur + "\n" + ln) if cur else ln
        if cur:
            out.append(cur)
        return out

    async def _flush_once(self, client):
        now = time.time()
        if self._announce:
            ch = self._chan(client, "discord_channel_id")
            lines = []
            while self._announce:
                lines.append(self._announce.popleft())
            if ch is not None:
                for part in self._chunks(lines):
                    await self._send(ch, part)
        if self._pressed and now - self._last_shot >= self.SHOT_GAP and (
                now - self._last_press >= self.SETTLE or now - self._first_press >= self.MAX_BATCH_WAIT):
            ch = self._chan(client, "discord_channel_id")
            lines = []
            while self._pressed:
                lines.append(self._pressed.popleft())
            self._last_shot = time.time()
            if ch is not None:
                shown, used, budget = [], 0, 1850
                for ln in lines:
                    if used + len(ln) + 1 > budget:
                        break
                    shown.append(ln)
                    used += len(ln) + 1
                text = "\n".join(shown)
                hidden = len(lines) - len(shown)
                if hidden > 0:
                    text += f"\n+{hidden} more"
                path, why = None, ""
                if self.cfg("discord_screens", True):
                    loop = asyncio.get_running_loop()
                    try:
                        path, why = await loop.run_in_executor(None, self.app._capture_vm_png)
                    except Exception as e:
                        path, why = None, f"{type(e).__name__}"
                    if path:
                        self.stats["shots"] += 1
                    elif why:
                        text += f"\n_(no screenshot: {why})_"
                await self._send(ch, text[:1990], path)
                if path:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
        if self._logq and now - self._last_log >= self.LOG_GAP:
            self._last_log = now
            ch = self._chan(client, "discord_log_channel_id")
            if ch is None:
                if not self._id("discord_log_channel_id"):
                    self._logq.clear()
                return
            lines = []
            while self._logq and len(lines) < 60:
                lines.append(self._logq.popleft())
            parts = self._chunks(lines)
            for part in parts[:2]:
                await self._send(ch, part)
            for part in reversed(parts[2:]):
                for ln in reversed(part.split("\n")):
                    self._logq.appendleft(ln)



async def _noop_rescan(bridge, client):
    bridge._scan(client)

def payload_is_dangerous(text):
    raw = str(text).lower()
    for frag in _dpl:
        if frag in raw: return frag
    norm = normalize_payload(text)
    for frag in _dpl + _igt:
        nf = normalize_payload(frag)
        if nf and len(nf) >= 4 and nf in norm: return frag
    return None
banned_words = []
custom_commands = {}

_dkd = {"VERSION":5,"RAW":{"esc":[1],"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"-":[12],"=":[13],"backspace":[14],"tab":[15],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"[":[26],"]":[27],"enter":[28],"ctrl":[29],"lctrl":[29],"rctrl":[224,29],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],";":[39],"'":[40],"`":[41],"shift":[42],"lshift":[42],"\\":[43],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50],",":[51],".":[52],"/":[53],"rshift":[54],"alt":[56],"lalt":[56],"ralt":[224,56],"space":[57],"capslock":[58],"f1":[59],"f2":[60],"f3":[61],"f4":[62],"f5":[63],"f6":[64],"f7":[65],"f8":[66],"f9":[67],"f10":[68],"f11":[87],"f12":[88],"numlock":[69],"scrolllock":[70],"home":[224,71],"up":[224,72],"pageup":[224,73],"left":[224,75],"right":[224,77],"end":[224,79],"down":[224,80],"pagedown":[224,81],"insert":[224,82],"delete":[224,83],"del":[224,83],"win":[224,91],"lwin":[224,91],"rwin":[224,92],"cmd":[224,91],"super":[224,91],"menu":[224,93],"plus":[13],"minus":[12],"return":[28],"numpad0":[82],"numpad1":[79],"numpad2":[80],"numpad3":[81],"numpad4":[75],"numpad5":[76],"numpad6":[77],"numpad7":[71],"numpad8":[72],"numpad9":[73],"numpad_dot":[83],"numpad_enter":[224,28],"numpad_plus":[78],"numpad_minus":[74],"numpad_mul":[55],"numpad_div":[224,53],"printscreen":[224,55,224,183],"pause":[225,29,69,225,157,197],"vol_mute":[224,32],"vol_down":[224,46],"vol_up":[224,48],"media_next":[224,25],"media_prev":[224,16],"media_stop":[224,36],"media_play_pause":[224,34]},"LAYOUTS":{"US":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"-":[12],"=":[13],"[":[26],"]":[27],"\\":[43],";":[39],"'":[40],"`":[41],",":[51],".":[52],"/":[53]},"shift":{"!":[2],"@":[3],"#":[4],"$":[5],"%":[6],"^":[7],"&":[8],"*":[9],"(":[10],")":[11],"_":[12],"+":[13],"{":[26],"}":[27],"|":[43],":":[39],"\"":[40],"~":[41],"<":[51],">":[52],"?":[53]},"altgr":{}},"UK":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"-":[12],"=":[13],"[":[26],"]":[27],"#":[43],";":[39],"'":[40],"`":[41],",":[51],".":[52],"/":[53],"\\":[86]},"shift":{"!":[2],"\"":[3],"£":[4],"$":[5],"%":[6],"^":[7],"&":[8],"*":[9],"(":[10],")":[11],"_":[12],"+":[13],"{":[26],"}":[27],"~":[43],":":[39],"@":[40],"¬":[41],"<":[51],">":[52],"?":[53],"|":[86]},"altgr":{"€":[5]}},"DANISH":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"+":[12],"´":[13],"å":[26],"¨":[27],"'":[43],"æ":[39],"ø":[40],"½":[41],",":[51],".":[52],"-":[53],"<":[86]},"shift":{"!":[2],"\"":[3],"#":[4],"¤":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"`":[13],"Å":[26],"^":[27],"*":[43],"Æ":[39],"Ø":[40],"§":[41],";":[51],":":[52],"_":[53],">":[86]},"altgr":{"@":[3],"£":[4],"$":[5],"{":[8],"[":[9],"]":[10],"}":[11],"\\":[86],"|":[13],"~":[27],"€":[18],"µ":[50]}},"GERMAN":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"z":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"y":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"ß":[12],"´":[13],"ü":[26],"+":[27],"#":[43],"ö":[39],"ä":[40],"^":[41],",":[51],".":[52],"-":[53],"<":[86]},"shift":{"!":[2],"\"":[3],"§":[4],"$":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"`":[13],"Ü":[26],"*":[27],"'":[43],"Ö":[39],"Ä":[40],"°":[41],";":[51],":":[52],"_":[53],">":[86]},"altgr":{"²":[3],"³":[4],"{":[8],"[":[9],"]":[10],"}":[11],"\\":[12],"@":[16],"€":[18],"~":[27],"|":[86],"µ":[50]}},"FRENCH":{"noshift":{"&":[2],"é":[3],"\"":[4],"'":[5],"(":[6],"-":[7],"è":[8],"_":[9],"ç":[10],"à":[11],")":[12],"=":[13],"a":[16],"z":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"^":[26],"$":[27],"q":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"m":[39],"ù":[40],"²":[41],"*":[43],"w":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],",":[50],";":[51],":":[52],"!":[53],"<":[86]," ":[57]},"shift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"°":[12],"+":[13],"¨":[26],"£":[27],"%":[40],"µ":[43],"?":[50],".":[51],"/":[52],"§":[53],">":[86]},"altgr":{"~":[3],"#":[4],"{":[5],"[":[6],"|":[7],"`":[8],"\\":[9],"^":[10],"@":[11],"]":[12],"}":[13],"€":[18]}},"TURKISH":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"ı":[23],"o":[24],"p":[25],"ğ":[26],"ü":[27],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"ş":[39],"i":[40],"\"":[41],",":[43],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50],"ö":[51],"ç":[52],".":[53],"<":[86]," ":[57],"*":[12],"-":[13]},"shift":{"!":[2],"'":[3],"^":[4],"+":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"_":[13],"Ğ":[26],"Ü":[27],"Ş":[39],"İ":[40],"é":[41],";":[43],"Ö":[51],"Ç":[52],":":[53],">":[86],"I":[23]},"altgr":{"@":[16],"#":[4],"$":[5],"{":[8],"[":[9],"]":[10],"}":[11],"\\":[12],"|":[13],"€":[18],"~":[27],"`":[43],"´":[39],"¨":[26]}},"NORWEGIAN":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"+":[12],"\\":[13],"å":[26],"¨":[27],"ø":[39],"æ":[40],"|":[41],",":[51],".":[52],"-":[53],"<":[86],"'":[43]},"shift":{"!":[2],"\"":[3],"#":[4],"¤":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"`":[13],"Å":[26],"^":[27],"*":[43],"Ø":[39],"Æ":[40],"§":[41],";":[51],":":[52],"_":[53],">":[86]},"altgr":{"£":[4],"$":[5],"{":[8],"[":[9],"]":[10],"}":[11],"~":[27],"€":[18],"µ":[50],"@":[3],"´":[13]}},"SWEDISH":{"noshift":{"1":[2],"2":[3],"3":[4],"4":[5],"5":[6],"6":[7],"7":[8],"8":[9],"9":[10],"0":[11],"q":[16],"w":[17],"e":[18],"r":[19],"t":[20],"y":[21],"u":[22],"i":[23],"o":[24],"p":[25],"a":[30],"s":[31],"d":[32],"f":[33],"g":[34],"h":[35],"j":[36],"k":[37],"l":[38],"z":[44],"x":[45],"c":[46],"v":[47],"b":[48],"n":[49],"m":[50]," ":[57],"+":[12],"´":[13],"å":[26],"¨":[27],"'":[43],"ö":[39],"ä":[40],"§":[41],",":[51],".":[52],"-":[53],"<":[86]},"shift":{"!":[2],"\"":[3],"#":[4],"¤":[5],"%":[6],"&":[7],"/":[8],"(":[9],")":[10],"=":[11],"?":[12],"`":[13],"Å":[26],"^":[27],"*":[43],"Ö":[39],"Ä":[40],"½":[41],";":[51],":":[52],"_":[53],">":[86]},"altgr":{"@":[3],"£":[4],"$":[5],"{":[8],"[":[9],"]":[10],"}":[11],"\\":[12],"~":[27],"|":[86],"€":[18],"µ":[50]}}}}

_needs_update = False
if os.path.exists(scancodes_file):
    try:
        with open(scancodes_file, "r", encoding="utf-8") as f: _loaded_data = json.load(f)
        if "LAYOUTS" not in _loaded_data or "RAW" not in _loaded_data or _loaded_data.get("VERSION") != _dkd.get("VERSION"): _needs_update = True
    except Exception: _needs_update = True
else: _needs_update = True

if _needs_update:
    try:
        with open(scancodes_file, "w", encoding="utf-8") as f: json.dump(_dkd, f, indent=4, ensure_ascii=False)
        _loaded_data = _dkd.copy()
    except Exception: _loaded_data = _dkd.copy()

scancodes = _loaded_data["RAW"]
_layouts = _loaded_data["LAYOUTS"]

_DEAD_KEYS = {"DANISH": "\u00b4`\u00a8^~", "NORWEGIAN": "\u00b4`\u00a8^~", "SWEDISH": "\u00b4`\u00a8^~",
              "GERMAN": "^\u00b4`", "FRENCH": "\u00a8~`", "TURKISH": "^\u00a8~`\u00b4"}


def is_dead_key(char, layout):
    if char not in _DEAD_KEYS.get(str(layout or "").upper(), ""):
        return False
    t = _layouts.get(str(layout or "").upper()) or {}
    if str(layout).upper() == "FRENCH" and char == "^":
        return False
    return any(char in (t.get(lv) or {}) for lv in ("noshift", "shift", "altgr"))


def _wait_seconds(arg, default=0.5, cap=30.0):
    s = str(arg or "").strip().lower().replace(" ", "")
    if not s:
        return default
    try:
        if s.endswith("ms"):
            v = float(s[:-2]) / 1000.0
        elif s.endswith("sec"):
            v = float(s[:-3])
        elif s.endswith("secs"):
            v = float(s[:-4])
        elif s.endswith("s"):
            v = float(s[:-1])
        elif s.endswith("m"):
            v = float(s[:-1]) * 60.0
        elif s.endswith("min"):
            v = float(s[:-3]) * 60.0
        else:
            v = float(s)
    except Exception:
        return default
    return max(0.0, min(v, cap))


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
except Exception as _ex:
    _trace(_ex_where(), _ex)

def save_stats():
    try:
        uptime = int(time.time() - script_start_time)
        with stats_lock:
            tmp_file = stats_file + ".tmp"
            with open(tmp_file, "w") as f: json.dump({"uptime": uptime, "commands": total_commands_executed, "failed": total_commands_failed, "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
            os.replace(tmp_file, stats_file)
    except Exception as _ex:
        _trace(_ex_where(), _ex)

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
    except Exception as _ex:
        _trace(_ex_where(), _ex)
    set_obs_scene(obs_scene_error)
sys.excepthook = handle_exception

def clean_text(text):
    if not isinstance(text, str): return str(text)
    return ''.join(c for c in text if c <= '\uFFFF')

def safe_int(val, default=0, lo=None, hi=None):
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
                plog("OBS", f"scene switched -> {scene_name}")
                dbg("obs", f"scene -> {scene_name}")
            except Exception as e: _obs_note_fail(e)
        plog("OBS", f"scene switch requested -> {scene_name}", verbose=True)
        threading.Thread(target=_switch, daemon=True, name="obs-scene").start()
    except Exception as _ex:
        _trace(_ex_where(), _ex)

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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            for port in range(flask_port, flask_port + 10):
                try:
                    flask_port = port
                    _bind = '0.0.0.0' if os.environ.get("YT2VM_LAN") == "1" else '127.0.0.1'
                    obs_web_overlay_app.run(host=_bind, port=port, debug=False, use_reloader=False, threaded=True)
                    break
                except OSError: continue
        except Exception as _ex:
            _trace(_ex_where(), _ex)

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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
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
        except Exception as _ex:
            _trace(_ex_where(), _ex)
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



_vkm = {
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
for _i in range(1, 13): _vkm[f"f{_i}"] = chr(0xffbd + _i)
for _c in "abcdefghijklmnopqrstuvwxyz0123456789": _vkm[_c] = _c

def parse_combo_keys(args):
    text = (args or "").strip().lower()
    if not text:
        return []
    if " " in text or "+" in text:
        return [k for k in text.replace("+", " ").split() if k]
    known = sorted(_vkm.keys(), key=len, reverse=True)
    out, i = [], 0
    while i < len(text):
        for k in known:
            if text.startswith(k, i):
                out.append(k); i += len(k); break
        else:
            out.append(text[i:]); break
    return out

_vpf = "vncpass.txt"





_vxc = {}

_lic = {"ip": None, "at": 0}

def load_saved_vnc_pass():
    out = []
    try:
        if os.path.exists(_vpf):
            with open(_vpf, "r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.rstrip("\n")
                    if ln and ln not in out:
                        out.append(ln)
    except Exception:
        pass
    return out

def save_vnc_pass(pw):
    if pw is None:
        return
    try:
        existing = load_saved_vnc_pass()
        if pw in existing:
            existing.remove(pw)
        existing.insert(0, pw)
        with open(_vpf, "w", encoding="utf-8") as f:
            f.write("\n".join(existing[:10]) + "\n")
        try:
            if os.name == "posix":
                os.chmod(_vpf, 0o600)
        except Exception:
            pass
        dbg("vnc", f"saved working vnc password to {_vpf} (owner-only)")
    except Exception as e:
        dbg("vnc", "could not save vnc password", e)

def get_local_ipv4(prefer_adapter="Ethernet", force=False):
    if not force and _lic["ip"] and time.time() - _lic["at"] < 120:
        return _lic["ip"]
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
    _lic["ip"] = ip
    _lic["at"] = time.time()
    return ip

def _tcp_listening(host, port, timeout=0.4):
    import socket
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


_vsp = [
    "tvnserver.exe", "tvnviewer.exe", "winvnc.exe", "winvnc4.exe",
    "vncserver.exe", "vncserverui.exe", "vncviewer.exe",
    "x11vnc", "tigervncserver", "Xtightvnc",
]
_vss = ["tvnserver", "uvnc_service", "vncserver", "RealVNC Server"]

def kill_vnc_squatters(reason=""):
    killed = []
    try:
        if platform.system() == "Windows":
            for svc in _vss:
                try:
                    r = subprocess.run(["sc", "stop", svc], capture_output=True, text=True, timeout=12)
                    if r.returncode == 0:
                        killed.append(f"service:{svc}")
                        dbg("vnc", f"stopped service {svc}")
                except Exception:
                    pass
            for proc in _vsp:
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
            for proc in _vsp:
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
    for port in range(int(start), int(end) + 1):
        if not _tcp_listening(host, port):
            return port
    return int(start)

def vnc_port_conflict(port, host="127.0.0.1"):
    return _tcp_listening(host, port)

def build_vnc_translation(layout):
    layout = (layout or "US").upper()
    if layout in _vxc:
        return _vxc[layout]
    table = {}
    try:
        tgt = _layouts.get(layout)
        us = _layouts.get("US")
        if tgt and us:

            us_base = {}
            for ch, codes in (us.get("noshift") or {}).items():
                us_base[tuple(codes)] = ch
            for level, need_shift, need_altgr in (("noshift", False, False),
                                                  ("shift", True, False),
                                                  ("altgr", False, True)):
                for ch, codes in (tgt.get(level) or {}).items():
                    base = us_base.get(tuple(codes))
                    if base is None:
                        table[ch] = (None, False, False)
                    else:
                        table[ch] = (base, need_shift, need_altgr)
    except Exception as e:
        dbg("vnc", f"could not build translation for {layout}", e)
    _vxc[layout] = table
    return table

_vlc = {}

def _layout_can_type(ch, layout):
    key = layout.upper()
    if key not in _vlc:
        chars = set()
        tgt = _layouts.get(key) or {}
        for level in ("noshift", "shift", "altgr"):
            chars.update((tgt.get(level) or {}).keys())
        _vlc[key] = chars
    return ch in _vlc[key]

def vnc_char_for(ch, layout):
    layout = (layout or "US").upper()


    if layout == "TURKISH":
        tr_pair = {"I": "\u0131", "\u0130": "i"}
        if ch in tr_pair:
            base, _s, altgr = vnc_char_for(tr_pair[ch], layout)
            if base is not None:
                return base, True, altgr
            return None, False, False

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

    def __init__(self, vmrun_path="", vmx="", host="127.0.0.1", port=5900, password="", keymap="us"):
        self.vmrun_path = vmrun_path or find_vmrun()
        self.vmx = vmx
        self.host = host or "127.0.0.1"
        self.port = int(port or 5900)
        self.password = password or ""
        self.keymap = keymap if keymap in ("us", "dk") else "us"


        self.guest_layout = "US"
        self.cfg = {}
        self.host_type = ""
        self.auto_kill_squatters = True
        self.client = None
        self.status = "not connected"
        self._mx, self._my = 0, 0
        self._last_ok = 0
        self.lock = threading.RLock()

    def _host_type(self):
        if getattr(self, "host_type", ""):
            return self.host_type
        if platform.system() == "Darwin":
            return "fusion"
        low = (self.vmrun_path or "").lower()
        if "player" in low:
            return "player"
        return "ws"

    def _vmrun(self, *args, timeout=90):
        _desc = " ".join(str(a) for a in args[:1]) + (" " + os.path.basename(str(args[1])) if len(args) > 1 else "")
        _warn_if_ui_thread(f"vmrun {_desc}")
        _t0 = time.time()
        try:
            r = subprocess.run([self.vmrun_path, "-T", self._host_type()] + list(args),
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            plog("VMRUN", f"vmrun {_desc} TIMED OUT after {timeout}s - VMware is hung or busy")
            console_log("ERROR", f"vmrun {_desc} timed out after {timeout}s")
            return None
        except Exception as e:
            console_log("ERROR", f"vmrun failed: {e}")
            return None
        _el = time.time() - _t0
        if _el > 5:
            plog("VMRUN", f"SLOW vmrun {_desc} took {_el:.1f}s rc={r.returncode}")
        elif r.returncode != 0:
            plog("VMRUN", f"vmrun {_desc} rc={r.returncode} {_el*1000:.0f}ms {((r.stdout or '') + (r.stderr or '')).strip()[:160]!r}")
        else:
            plog("VMRUN", f"vmrun {_desc} ok {_el*1000:.0f}ms", verbose=True)
        return r

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

    def read_vmx_vnc(self):
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
        if not self.vmx or not os.path.exists(self.vmx):
            return False
        self.resolve_port_conflict(auto=True)
        pw = str(self.password or "")
        if len(pw) > 8:

            console_log("SYSTEM", "vnc passwords are limited to 8 characters - truncating.")
            pw = pw[:8]
            self.password = pw
        want = {
            "RemoteDisplay.vnc.enabled": '"TRUE"',
            "RemoteDisplay.vnc.port": f'"{self.port}"',

            "RemoteDisplay.vnc.keyMap": '"us"',
        }
        if pw:
            want["RemoteDisplay.vnc.password"] = f'"{pw}"'

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
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
                with open(self.vmx, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                console_log("SYSTEM", f"VNC written to {os.path.basename(self.vmx)}: port {self.port}, keymap {self.keymap}, password {'yes' if pw else 'none'}")
            dbg("vnc", f"vmx now has: {self.read_vmx_vnc()}")
            return True
        except Exception as e:
            console_log("ERROR", f"could not edit vmx: {e}")
            return False

    def config_get(self, key, default=None):
        try:
            return self.cfg.get(key, default)
        except Exception:
            return default

    def _clear_stuck_modifiers(self, client):
        for ks in (chr(0xFFE1), chr(0xFFE2), chr(0xFFE3), chr(0xFFE4),
                   chr(0xFFE9), chr(0xFFEA), chr(0xFE03), chr(0xFFEB), chr(0xFFEC)):
            try: client.keyUp(ks)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _ask_vnc_password(self):
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
                root.after(0, _prompt)
                done.wait(120)
            else:
                _prompt()
        except Exception:
            pass
        self._asking_pw = False
        return answer["pw"]

    @staticmethod
    def _port_open(host, port, timeout=1.0):
        import socket
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except Exception:
            return False

    def connect(self, timeout=6.0):
        t0 = time.time()
        try:
            from vncdotool import api
        except Exception:
            self.status = "vncdotool not installed (pip install vncdotool)"
            dbg("vnc", self.status)
            return False

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


        try:
            if not self.is_running():
                self.client = None

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



        candidates = []
        def _add(p):
            key = "" if p is None else str(p)
            if key not in [("" if c is None else str(c)) for c in candidates]:
                candidates.append(p)
        if self.password: _add(str(self.password))
        _add(None)
        _add("1234")
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
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self._clear_stuck_modifiers(self.client)
        self._last_ok = time.time()
        self.status = f"connected {self.host}::{self.port}"
        dbg("vnc", f"CONNECTED in {(time.time()-t0)*1000:.0f}ms")
        return True

    def disconnect(self):
        try:
            if self.client: self.client.disconnect()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self.client = None

    def _need(self, fresh=False):
        idle = time.time() - getattr(self, "_last_ok", 0)
        if self.client is None or fresh or idle > 120:
            self.connect()
        if self.client is None:
            try:
                from vncdotool import api
                self.status = (self.status or "vnc not connected") + " (is VNC enabled in the .vmx and the VM running?)"
            except Exception:
                self.status = "vncdotool not installed - run: pip install vncdotool"
            console_log("ERROR", f"vmware input unavailable: {self.status}")
            return False
        return True

    def _alt_numpad(self, ch):
        try:
            code = str(ord(ch))
            alt = chr(0xFFE9)
            kp = {str(d): chr(0xFFB0 + d) for d in range(10)}
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



        if not hard:
            return
        try:
            if hasattr(self.client, "pause"): self.client.pause(0.01)
        except Exception:
            pass

    MAX_TYPE = 4000

    def type_text(self, text):
        if not self._need(): return

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
                                    self._flush(hard=True)
                                self.client.keyPress(base)
                                self._flush(hard=True)
                            finally:
                                for mod in reversed(held):
                                    try: self.client.keyUp(mod)
                                    except Exception as _ex:
                                        _trace(_ex_where(), _ex)
                    if ch not in (" ", chr(10), chr(9)) and is_dead_key(ch, lay):
                        self.client.keyPress("space")
                    if per_char: time.sleep(per_char)
                except Exception as e:
                    fails += 1
                    dbg("vmware", f"type char {ch!r} failed (continuing)", e)
                    try: self._clear_stuck_modifiers(self.client)
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
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
        k = _vkm.get((name or "").lower().strip(), (name or "").lower().strip())
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
        names = parse_combo_keys(combo)
        if not names: return
        mapped = [_vkm.get(k, k) for k in names]
        with self.lock:
            if not self._need(): return
            try:
                for k in mapped:
                    self.client.keyDown(k); self._flush(); time.sleep(0.03)
            finally:
                for k in reversed(mapped):
                    try: self.client.keyUp(k); self._flush(); time.sleep(0.03)
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
            self._last_ok = time.time()
            dbg("vmware", f"combo {names} sent over vnc")

    def click(self, button=1, count=1):
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
        try:
            from vncdotool import api
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
                self.client.keyDown(_vkm["shift"]); self._flush()
                time.sleep(0.05)
                self.client.keyUp(_vkm["shift"]); self._flush()
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

_ng = [
    ("MAIN",    ["Dashboard", "VM Config", "Commands", "Settings"]),
    ("CONTROL", ["Keys", "Mouse", "Macros", "Quick Type", "Win Apps"]),
    ("MACHINE", ["VMS", "Snapshots", "OS Voting", "Real PC", "System"]),
    ("STREAM",  ["OBS", "Discord", "Overlays", "Media", "Music Queue", "Chat Tools", "Moderation"]),
    ("TOOLS",   ["Plugins", "Plugin Market", "Plugin Docs", "Automation", "Event Log", "Replay", "Backup", "Appearance", "Extra Things", "Help", "Diagnostics"]),
]

_NG_ICON = {"MAIN": "main", "CONTROL": "control", "MACHINE": "machine", "STREAM": "stream", "TOOLS": "tools"}
_NAV_ROW_ICONS = {"Discord": "bridge"}
_LOGO_CACHE = {}


def _user_logo(size):
    size = int(size)
    if size in _LOGO_CACHE:
        return _LOGO_CACHE[size]
    img = None
    for path in (os.path.join(_appdir(), "discord_logo.png"), os.path.abspath("discord_logo.png")):
        try:
            if os.path.isfile(path):
                raw = tk.PhotoImage(file=path)
                f = max(1, int(round(max(raw.width(), raw.height()) / float(size))))
                img = raw.subsample(f, f) if f > 1 else raw
                break
        except Exception as _ex:
            _trace(_ex_where(), _ex)
    _LOGO_CACHE[size] = img
    return img

_PAGE_BLURB = {
    "Dashboard": "Live overview of chat, the machine and the stream.",
    "VM Config": "Pick the backend, the target VM and the snapshot chat reverts to.",
    "Commands": "Built-in chat commands and your own macros.",
    "Settings": "Prefix, layout, timings and how much load chat is allowed to put on the VM.",
    "Keys": "Send keys, text and combos straight into the VM.",
    "Mouse": "Move, click and scroll inside the VM.",
    "Macros": "One-click command sequences.",
    "Quick Type": "Type whole blocks into the VM and keep reusable snippets.",
    "Win Apps": "Launch Windows apps inside the VM through Win+R.",
    "VMS": "Switch between VirtualBox and VMware and set up VNC input.",
    "Snapshots": "Create, restore and delete snapshots for the active VM.",
    "OS Voting": "Let chat vote on which OS runs next.",
    "Real PC": "Route chat input to a physical machine through the Pico.",
    "System": "Live internals, the recovery buttons and app updates.",
    "OBS": "Scenes, media playback, the relay and overlay flashes.",
    "Overlays": "Browser sources for OBS, served from this app.",
    "Media": "Music queue controls and VM volume.",
    "Music Queue": "What is playing and what is up next.",
    "Chat Tools": "Announcements, flashes and test messages.",
    "Moderation": "Blacklist viewers and manage votes.",
    "Discord": "Run the same chat-plays commands from a Discord server, alongside or instead of YouTube.",
    "Automation": "Commands that run on a timer.",
    "Event Log": "Mod actions, votes, music and the raw chat log.",
    "Replay": "Re-play recorded chat to the overlays with the original timing.",
    "Backup": "Export logs and back up your configuration.",
    "Appearance": "Theme, accent colour and text size.",
    "Extra Things": "Run extra instances for multi-streaming.",
    "Help": "Every chat command and who can use it.",
    "Diagnostics": "Dependency, backend and recovery checks in one report.",
    "Plugins": "Enable, reload and configure installed plugins.",
    "Plugin Market": "Browse and install plugins from the market.",
    "Plugin Docs": "How to use, write and release plugins - built into the app.",
}


def _ease_out_cubic(p):
    return 1.0 - (1.0 - p) ** 3


def _ease_in_cubic(p):
    return p * p * p


def _ease_in_out(p):
    return 4 * p * p * p if p < 0.5 else 1 - ((-2 * p + 2) ** 3) / 2


def _ease_out_back(p):
    c1 = 1.45
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def _ease_linear(p):
    return p


class _Motion:

    LEVELS = {"off": 0, "reduced": 1, "full": 2}

    def __init__(self):
        self.root = None
        self.level = 2
        self.tw = {}
        self.loops = {}
        self.val = {}
        self.col = {}
        self._after = None
        self._last_loop = 0.0
        self.frames = 0
        self.worst_ms = 0.0
        self._fps_n = 0
        self._fps_t = time.perf_counter()
        self.fps = 0.0
        self._slow_logged = 0.0
        self.errors = 0
        self._in_frame = False
        self.chains_blocked = 0

    @property
    def on(self):
        return self.root is not None and self.level > 0

    @property
    def ambient(self):
        return self.root is not None and self.level >= 2

    def attach(self, root, level="full"):
        self.root = root
        self.set_level(level)

    def set_level(self, level):
        lv = self.LEVELS.get(str(level), 2) if not isinstance(level, int) else max(0, min(2, level))
        self.level = lv
        if lv == 0:
            for key in list(self.tw):
                self.finish(key)
        if lv < 2:
            for key, lp in list(self.loops.items()):
                self._call(lp[0], 0.0)
        self._kick()

    def _call(self, fn, *a):
        try:
            fn(*a)
            return True
        except tk.TclError:
            return False
        except Exception as _ex:
            self.errors += 1
            _trace(_ex_where(), _ex)
            return False

    def tween(self, key, dur, fn, b=1.0, a=None, ease=_ease_out_cubic, done=None, delay=0, slow=False, scale=True):
        if a is None:
            a = self.val.get(key, 0.0 if b else 1.0)
        old = self.tw.pop(key, None)
        if not self.on or dur <= 0:
            self.val[key] = b
            ok = self._call(fn, b)
            if done is not None and ok:
                self._call(done)
            return
        if self.level == 1 and scale:
            dur *= 0.55
            delay *= 0.5
        now = time.perf_counter()
        self.tw[key] = [now + delay / 1000.0, dur / 1000.0, fn, float(a), float(b), ease, done, slow]
        if delay <= 0:
            self.val[key] = float(a)
        self._kick()

    def color(self, key, dur, setter, to, frm=None, ease=_ease_out_cubic, done=None, delay=0):
        start = frm or self.col.get(key) or to
        if _hx(start) == _hx(to) and key not in self.tw:
            self.col[key] = to
            self._call(setter, to)
            if done is not None:
                self._call(done)
            return
        def _step(p, s=start, t=to):
            c = mix(s, t, max(0.0, min(1.0, p)))
            self.col[key] = c
            setter(c)
        self.tween(key, dur, _step, 1.0, 0.0, ease, done, delay)

    def busy(self, key):
        return key in self.tw

    def cancel(self, key):
        self.tw.pop(key, None)

    def finish(self, key):
        tw = self.tw.pop(key, None)
        if tw is None:
            return
        self.val[key] = tw[4]
        if self._call(tw[2], tw[4]) and tw[6] is not None:
            self._call(tw[6])

    def loop(self, key, fn, period_ms, fps=30):
        if key in self.loops:
            self.loops[key][1] = period_ms / 1000.0
            return
        self.loops[key] = [fn, period_ms / 1000.0, time.perf_counter(), 1.0 / max(1, fps), 0.0]
        if not self.ambient:
            self._call(fn, 0.0)
        self._kick()

    def unloop(self, key, rest=True):
        lp = self.loops.pop(key, None)
        if lp is not None and rest:
            self._call(lp[0], 0.0)

    def looping(self, key):
        return key in self.loops

    def _kick(self):
        if self._in_frame:
            return
        if self.root is None or self._after is not None:
            return
        if not self.tw and not (self.loops and self.ambient):
            return
        try:
            self._after = self.root.after(16, self._frame)
        except Exception:
            self._after = None

    def _frame(self):
        self._after = None
        if self.root is None:
            return
        self._in_frame = True
        try:
            self._frame_body()
        finally:
            self._in_frame = False

    def _frame_body(self):
        t0 = time.perf_counter()
        try:
            iconic = str(self.root.state()) == "iconic"
        except Exception:
            iconic = False
        if iconic:
            for key in list(self.tw):
                self.finish(key)
            if self._after is not None:
                return
            try:
                self._after = self.root.after(400, self._frame) if (self.loops and self.ambient) else None
            except Exception:
                self._after = None
            return
        fast = False
        for key, tw in list(self.tw.items()):
            start, dur, fn, a, b, ease, done, slow = tw
            if t0 < start:
                fast = fast or not slow
                continue
            p = 1.0 if dur <= 0 else min(1.0, (t0 - start) / dur)
            try:
                e = ease(p)
            except Exception:
                e = p
            v = a + (b - a) * e
            self.val[key] = v
            ok = self._call(fn, v)
            if p >= 1.0 or not ok:
                if self.tw.get(key) is tw:
                    del self.tw[key]
                if ok and done is not None:
                    self._call(done)
            elif not slow:
                fast = True
        if self.loops and self.ambient:
            for key, lp in list(self.loops.items()):
                fn, period, born, step, last = lp
                if t0 - last < step:
                    continue
                lp[4] = t0
                ph = ((t0 - born) / period) % 1.0 if period > 0 else 0.0
                if not self._call(fn, ph):
                    self.loops.pop(key, None)
        el = (time.perf_counter() - t0) * 1000.0
        self.frames += 1
        self._fps_n += 1
        if el > self.worst_ms:
            self.worst_ms = el
        if t0 - self._fps_t >= 1.0:
            self.fps = self._fps_n / (t0 - self._fps_t)
            self._fps_n = 0
            self._fps_t = t0
        if el > 30 and t0 - self._slow_logged > 10:
            self._slow_logged = t0
            plog("MOTION-SLOW", f"animation frame took {el:.0f}ms  tweens={len(self.tw)} loops={len(self.loops)} "
                                f"[{', '.join(str(k)[:28] for k in list(self.tw)[:6])}]")
        if self._after is not None:
            self.chains_blocked += 1
            return
        if self.tw or (self.loops and self.ambient):
            delay = 16 if fast else 33
            delay = max(4, delay - int(el))
            try:
                self._after = self.root.after(delay, self._frame)
            except Exception:
                self._after = None

    def stats(self):
        names = {0: "off", 1: "reduced", 2: "full"}
        return f"{names.get(self.level, '?')} tweens={len(self.tw)} loops={len(self.loops)} fps={self.fps:.0f} worst={self.worst_ms:.0f}ms"


MOTION = _Motion()


def _clip_poly(pts, x1, y1, x2, y2):
    def clip(poly, inside, cross):
        out = []
        if not poly:
            return out
        prev = poly[-1]
        for cur in poly:
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
            prev = cur
        return out
    def xcross(xv):
        return lambda p, q: (xv, p[1] + (q[1] - p[1]) * (xv - p[0]) / ((q[0] - p[0]) or 1e-9))
    def ycross(yv):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (yv - p[1]) / ((q[1] - p[1]) or 1e-9), yv)
    poly = list(pts)
    poly = clip(poly, lambda p: p[0] >= x1, xcross(x1))
    poly = clip(poly, lambda p: p[0] <= x2, xcross(x2))
    poly = clip(poly, lambda p: p[1] >= y1, ycross(y1))
    poly = clip(poly, lambda p: p[1] <= y2, ycross(y2))
    return poly


def _breath(ph):
    return (1.0 - math.cos(2 * math.pi * ph)) / 2.0


def _mo_inside(w, e):
    try:
        x, y = e.x_root, e.y_root
        wx, wy = w.winfo_rootx(), w.winfo_rooty()
        return wx <= x < wx + w.winfo_width() and wy <= y < wy + w.winfo_height()
    except Exception:
        return False


def _mo_border_glow(fr):
    key = ("bglow", str(fr))
    def paint(c):
        fr.configure(highlightbackground=c, highlightcolor=c)
    def enter(e=None):
        t = _STUDIO["tok"]
        try:
            if not t or int(fr.cget("highlightthickness")) <= 0:
                return
        except Exception:
            return
        MOTION.color(key, 170, paint, mix(t["line"], t["accent"], 0.5), frm=None if MOTION.busy(key) else t["line"])
    def leave(e=None):
        t = _STUDIO["tok"]
        if not t or (e is not None and _mo_inside(fr, e)):
            return
        try:
            if int(fr.cget("highlightthickness")) <= 0:
                return
        except Exception:
            return
        MOTION.color(key, 280, paint, t["line"])
    fr.bind("<Enter>", enter, add="+")
    fr.bind("<Leave>", leave, add="+")


def _mo_hover_glow(outer, key, rest_role="line"):
    def paint(c):
        outer.configure(bg=c)
    def enter(e=None):
        t = _STUDIO["tok"]
        if not t or getattr(outer, "_mo_lock", False):
            return
        MOTION.color(key, 160, paint, mix(t[rest_role], t["accent"], 0.55), frm=t[rest_role] if not MOTION.busy(key) else None)
    def leave(e=None):
        t = _STUDIO["tok"]
        if not t or getattr(outer, "_mo_lock", False):
            return
        if e is not None and _mo_inside(outer, e):
            return
        MOTION.color(key, 260, paint, t[rest_role])
    outer.bind("<Enter>", enter, add="+")
    outer.bind("<Leave>", leave, add="+")


def _rrect(cv, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, splinesteps=12, **kw)


def _draw_icon(cv, name, cx, cy, s, col, bg, w=1.7, tag="icon"):
    u = s / 20.0
    x0, y0 = cx - s / 2.0, cy - s / 2.0
    def P(x, y):
        return x0 + x * u, y0 + y * u
    def line(*pts, width=None):
        flat = []
        for i in range(0, len(pts), 2):
            flat += list(P(pts[i], pts[i + 1]))
        cv.create_line(*flat, fill=col, width=width or w, capstyle="round", joinstyle="round", tags=tag)
    def dot(x, y, r):
        a, b = P(x - r, y - r)
        c, d = P(x + r, y + r)
        cv.create_oval(a, b, c, d, fill=col, outline="", tags=tag)
    def box(x1, y1, x2, y2, r=1.6, fill=""):
        a, b = P(x1, y1)
        c, d = P(x2, y2)
        _rrect(cv, a, b, c, d, r * u, fill=fill, outline=col, width=w, tags=tag)
    if name == "main":
        box(2.5, 2.5, 9, 9); box(11, 2.5, 17.5, 9); box(2.5, 11, 9, 17.5); box(11, 11, 17.5, 17.5)
    elif name == "control":
        box(1.5, 4.5, 18.5, 15.5, 2.2)
        for x in (5.5, 8.5, 11.5, 14.5):
            dot(x, 8.4, 0.95)
        line(6.5, 12, 13.5, 12)
    elif name == "machine":
        box(2, 3, 18, 13.5, 1.8)
        line(10, 13.8, 10, 16.8)
        line(6.5, 17, 13.5, 17)
    elif name == "stream":
        dot(10, 10, 1.9)
        for (a, b, c, d) in ((5.4, 5.4, 14.6, 14.6), (1.8, 1.8, 18.2, 18.2)):
            p1, p2 = P(a, b), P(c, d)
            for start in (-42, 138):
                cv.create_arc(p1[0], p1[1], p2[0], p2[1], start=start, extent=84, style="arc",
                              outline=col, width=w, tags=tag)
    elif name == "tools":
        for y, kx in ((5, 13), (10, 6.5), (15, 11)):
            line(2.5, y, 17.5, y)
            a, b = P(kx - 2.2, y - 2.2)
            c, d = P(kx + 2.2, y + 2.2)
            cv.create_oval(a, b, c, d, fill=bg, outline=col, width=w, tags=tag)
    elif name == "search":
        a, b = P(2.5, 2.5)
        c, d = P(13.5, 13.5)
        cv.create_oval(a, b, c, d, outline=col, width=w, tags=tag)
        line(12, 12, 17.5, 17.5)
    elif name == "sun":
        a, b = P(6.4, 6.4)
        c, d = P(13.6, 13.6)
        cv.create_oval(a, b, c, d, outline=col, width=w, tags=tag)
        import math as _m
        for k in range(8):
            ang = k * _m.pi / 4
            line(10 + 5.6 * _m.cos(ang), 10 + 5.6 * _m.sin(ang), 10 + 7.8 * _m.cos(ang), 10 + 7.8 * _m.sin(ang))
    elif name == "moon":
        a, b = P(3, 3)
        c, d = P(17, 17)
        cv.create_oval(a, b, c, d, fill=col, outline="", tags=tag)
        a, b = P(7, 0.8)
        c, d = P(20, 13.8)
        cv.create_oval(a, b, c, d, fill=bg, outline="", tags=tag)
    elif name == "guide":
        a, b = P(2, 2)
        c, d = P(18, 18)
        cv.create_oval(a, b, c, d, outline=col, width=w, tags=tag)
        line(7.4, 7.6, 8.2, 5.9, 10, 5.3, 11.9, 5.9, 12.6, 7.6, 11.6, 9.4, 10, 10.6, 10, 12)
        dot(10, 14.6, 1.0)
    elif name == "chat":
        box(2, 3, 18, 13.8, 2.4)
        line(6, 13.8, 4.8, 17.6, 10, 13.8)
    elif name == "note":
        line(8, 15, 8, 3.5, 16, 2, 16, 13.5)
        line(8, 7, 16, 5.5)
        a, b = P(3, 12.5)
        c, d = P(8.6, 17.5)
        cv.create_oval(a, b, c, d, fill=col, outline="", tags=tag)
        a, b = P(11, 11)
        c, d = P(16.6, 16)
        cv.create_oval(a, b, c, d, fill=col, outline="", tags=tag)
    elif name == "bolt":
        line(11.5, 2, 5.5, 11, 10, 11, 8.5, 18, 14.5, 9, 10, 9, 11.5, 2)
    elif name == "bridge":
        box(2, 2.5, 18, 14, 3.0)
        line(6.2, 14, 5.0, 17.6, 9.8, 14)
        line(5.4, 8.3, 9.0, 8.3)
        line(7.2, 6.5, 7.2, 10.1)
        dot(12.6, 7.2, 1.05)
        dot(14.6, 9.4, 1.05)


class SidebarNav(tk.Frame):

    GROUP_TITLES = {"MAIN": "Main", "CONTROL": "Control", "MACHINE": "Machine", "STREAM": "Stream", "TOOLS": "Tools"}
    NAME_COLORS_DARK = ("#7AA2F7", "#9ECE6A", "#E0AF68", "#BB9AF7", "#7DCFFF", "#F7768E", "#73DACA", "#FF9E64")

    def __init__(self, master, app, **kw):
        tok = _STUDIO["tok"] or _studio_resolve("original")
        super().__init__(master, bg=tok["bg"], **kw)
        self.app = app
        self._pages = []
        self._buttons = {}
        self._items = {}
        self._current = None
        self._group = None
        self._last_in_group = {}
        self._toasts = []
        self._tally = {}
        self._rail_btns = {}
        self._rail_hover = None
        self._pulse = False
        self._chat_count = 0
        self._chat_alive = False
        self._chat_hidden = bool(app.config.get("ui_chat_hidden", False))
        self._chat_auto = False
        self._rail_act = {}
        self._rail_hov = {}
        self._ind_y = None
        self._ind_h = None
        self._ind_label = None
        self._ind_group = None
        self._fl_i = 0
        s = float(getattr(app, "_ui_scale", 1.0) or 1.0)
        self._s = s

        self.rail = tk.Frame(self, width=int(64 * s))
        self.rail._studio_skip_tree = True
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)
        self.logo = tk.Canvas(self.rail, width=int(64 * s), height=int(64 * s), bd=0, highlightthickness=0)
        self.logo.pack(side="top", pady=(int(12 * s), int(14 * s)))
        self.logo.bind("<Enter>", lambda e: self.shine())
        for gname, _members in _ng:
            cv = tk.Canvas(self.rail, width=int(64 * s), height=int(44 * s), bd=0, highlightthickness=0, cursor="hand2")
            cv.pack(side="top", pady=int(2 * s))
            cv.bind("<Button-1>", lambda e, g=gname: self.show_group(g, jump=True))
            cv.bind("<Enter>", lambda e, g=gname: self._rail_enter(g))
            cv.bind("<Leave>", lambda e, g=gname: self._rail_leave(g))
            self._rail_btns[gname] = cv
        self.rail_foot = tk.Frame(self.rail)
        self.rail_foot.pack(side="bottom", pady=(0, int(14 * s)))
        self._rail_extra = {}
        for key, tip, fn in (("theme", "Switch light / dark", lambda: getattr(app, "toggle_dark_light", lambda: None)()),
                             ("guide", "User guide", lambda: getattr(app, "show_welcome_guide", lambda **k: None)(force=True))):
            cv = tk.Canvas(self.rail_foot, width=int(64 * s), height=int(40 * s), bd=0, highlightthickness=0, cursor="hand2")
            cv.pack(side="top", pady=int(2 * s))
            cv.bind("<Button-1>", lambda e, f=fn: f())
            cv.bind("<Enter>", lambda e, k=key, t=tip: self._rail_enter(k, t))
            cv.bind("<Leave>", lambda e, k=key: self._rail_leave(k))
            self._rail_extra[key] = cv
        self.rail_rule = tk.Frame(self, width=1)
        self.rail_rule._studio_skip_tree = True
        self.rail_rule.pack(side="left", fill="y")
        self.tip = tk.Label(self, text="", padx=9, pady=4)
        self.tip._studio_skip_tree = True

        self.side = tk.Frame(self, width=int(212 * s))
        self.side._studio_skip_tree = True
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        self.brand = tk.Frame(self.side)
        self.brand.pack(fill="x", padx=20, pady=(int(20 * s), int(14 * s)))
        self.brand_name = tk.Label(self.brand, text=getattr(app, "app_name", "YT2VM"), anchor="w")
        self.brand_name.pack(anchor="w")
        self.brand_sub = tk.Label(self.brand, text=f"Control desk  {version}", anchor="w")
        self.brand_sub.pack(anchor="w", pady=(1, 0))

        self.search_wrap = tk.Frame(self.side, cursor="hand2", highlightthickness=1, bd=0)
        self.search_wrap.pack(fill="x", padx=14, pady=(0, int(18 * s)))
        self.search_icon = tk.Canvas(self.search_wrap, width=int(18 * s), height=int(18 * s), bd=0, highlightthickness=0, cursor="hand2")
        self.search_icon.pack(side="left", padx=(10, 6), pady=int(7 * s))
        self.search_lbl = tk.Label(self.search_wrap, text="Search", anchor="w", cursor="hand2")
        self.search_lbl.pack(side="left", fill="x", expand=True)
        self.search_kbd = tk.Label(self.search_wrap, text="Ctrl K", padx=5, pady=0, cursor="hand2")
        self.search_kbd.pack(side="right", padx=(4, 8))
        for w in (self.search_wrap, self.search_icon, self.search_lbl, self.search_kbd):
            w.bind("<Button-1>", lambda e: self.focus_search(e))
            w.bind("<Enter>", lambda e: self._search_hover(True))
            w.bind("<Leave>", lambda e: self._search_hover(False))

        self.group_head = tk.Frame(self.side)
        self.group_head.pack(fill="x", padx=20, pady=(0, 6))
        self.group_title = tk.Label(self.group_head, text="", anchor="w")
        self.group_title.pack(side="left")
        self.group_count = tk.Label(self.group_head, text="", anchor="e")
        self.group_count.pack(side="right")

        self.activity = tk.Frame(self.side, highlightthickness=1, bd=0)
        self.activity.pack(side="bottom", fill="x", padx=14, pady=(8, 14))
        self.act_head = tk.Frame(self.activity)
        self.act_head.pack(fill="x", padx=12, pady=(10, 2))
        self.act_dot = tk.Label(self.act_head, text="\u25cf", padx=0)
        self.act_dot.pack(side="left")
        self.act_title = tk.Label(self.act_head, text="Executor idle", anchor="w")
        self.act_title.pack(side="left", padx=(6, 0))
        self.act_cmd = tk.Label(self.activity, text="Nothing running", anchor="w", justify="left")
        self.act_cmd.pack(fill="x", padx=12)
        self.act_bar = tk.Canvas(self.activity, height=2, bd=0, highlightthickness=0)
        self.act_bar.pack(fill="x", padx=12, pady=(6, 0))
        self.act_sub = tk.Label(self.activity, text="Queue 0", anchor="w")
        self.act_sub.pack(fill="x", padx=12, pady=(2, 10))

        self._navwrap = tk.Frame(self.side)
        self._navwrap.pack(fill="both", expand=True)
        self._group_frames = {}
        self._group_heads = {}
        self._group_order = []
        for gname, _members in _ng:
            gf = tk.Frame(self._navwrap)
            self._group_frames[gname] = gf
            self._group_order.append(gname)
        self._sc = self._navwrap
        self._ind = tk.Frame(self._navwrap, width=3)
        self._ind._studio_skip_tree = True

        self.side_rule = tk.Frame(self, width=1)
        self.side_rule._studio_skip_tree = True
        self.side_rule.pack(side="left", fill="y")

        self.chatpane = tk.Frame(self, width=int(318 * s))
        self.chatpane._studio_skip_tree = True
        self.chatpane.pack_propagate(False)
        self.chat_rule = tk.Frame(self.chatpane, width=1)
        self.chat_rule.pack(side="left", fill="y")
        self.chat_card = tk.Frame(self.chatpane)
        self.chat_card.place(relx=1.0, y=0, anchor="ne", width=int(318 * s) - 1, relheight=1.0)
        hdr = tk.Frame(self.chat_card)
        hdr.pack(fill="x", padx=18, pady=(int(20 * s), 2))
        self.chat_hdr = hdr
        self.chat_title = tk.Label(hdr, text="Live chat", anchor="w")
        self.chat_title.pack(side="left")
        self.chat_state = tk.Frame(hdr, highlightthickness=1, bd=0)
        self.chat_state.pack(side="right")
        self.chat_state_dot = tk.Label(self.chat_state, text="\u25cf", padx=0)
        self.chat_state_dot.pack(side="left", padx=(8, 0))
        self.chat_dot = tk.Label(self.chat_state, text="offline")
        self.chat_dot.pack(side="left", padx=(4, 9), pady=1)
        self.chat_sub = tk.Label(self.chat_card, text="No messages yet", anchor="w")
        self.chat_sub.pack(fill="x", padx=18, pady=(0, 10))
        self.chat_sep = tk.Frame(self.chat_card, height=1)
        self.chat_sep.pack(fill="x")
        self.chat_body = tk.Frame(self.chat_card)
        self.chat_body.pack(fill="both", expand=True)
        self.chatbox = scrolledtext.ScrolledText(self.chat_body, bd=0, highlightthickness=0, wrap="word",
                                                 padx=16, pady=12, spacing1=3, spacing3=6, cursor="arrow")
        self.chatbox.pack(fill="both", expand=True)
        self.chatbox.configure(state="disabled")
        self.chat_empty = tk.Frame(self.chat_body)
        self.chat_empty_icon = tk.Canvas(self.chat_empty, width=int(40 * s), height=int(40 * s), bd=0, highlightthickness=0)
        self.chat_empty_icon.pack(pady=(0, 10))
        self.chat_empty_t = tk.Label(self.chat_empty, text="Waiting for chat")
        self.chat_empty_t.pack()
        self.chat_empty_s = tk.Label(self.chat_empty, text="Viewer messages show up here as\nsoon as the chat bot is connected.", justify="center")
        self.chat_empty_s.pack(pady=(4, 0))
        self.chat_empty.place(relx=0.5, rely=0.42, anchor="center")
        MOTION.loop("chatempty", self._chat_empty_frame, 2600, fps=30)
        self.chat_foot_sep = tk.Frame(self.chat_card, height=1)
        self.chat_foot_sep.pack(fill="x")
        arow = tk.Frame(self.chat_card)
        arow.pack(fill="x", padx=14, pady=(10, 12))
        self.chat_foot = arow
        self.autoscroll = tk.BooleanVar(value=True)
        self.autoscroll_cb = ttk.Checkbutton(arow, text="Follow new messages", variable=self.autoscroll,
                                             style="Studio.Pane.TCheckbutton")
        self.autoscroll_cb.pack(side="left")
        self.clear_btn = tk.Button(arow, text="Clear", bg="#27272A", fg="white", bd=0, cursor="hand2", command=self.clear_chat)
        self.clear_btn.pack(side="right")

        self.status = tk.Frame(self, height=int(28 * s))
        self.status._studio_skip_tree = True
        self.status.pack_propagate(False)
        self.status_rule = tk.Frame(self.status, height=1)
        self.status_rule.pack(side="top", fill="x")
        self.status_left = tk.Label(self.status, text="Ready")
        self.status_left.pack(side="left", padx=16)
        self.chat_toggle = tk.Label(self.status, text="Hide chat", cursor="hand2", padx=8)
        self.chat_toggle.pack(side="right", padx=(0, 10))
        self.chat_toggle.bind("<Button-1>", lambda e: self.toggle_chat_pane())
        self.status_right = tk.Label(self.status, text="")
        self.status_right.pack(side="right", padx=(16, 6))
        self.status_hint = tk.Label(self.status, text="Ctrl K  palette     Ctrl Tab  next page     Ctrl L  console     Ctrl J  chat")
        self.status_hint.pack(side="left", padx=16)

        self.main = tk.Frame(self)
        self.main._studio_skip = True
        self.header = tk.Frame(self.main, height=int((92 + 6 * max(0, int(_STUDIO.get("delta", 0)))) * s))
        self.header._studio_skip_tree = True
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)
        self.hdr_top = tk.Frame(self.header)
        self.hdr_top.pack(side="top", fill="x", padx=(30, 24), pady=(int(14 * s), 0))
        self.tally_bar = tk.Frame(self.hdr_top)
        self.tally_bar.pack(side="right", anchor="s", pady=(0, 2))
        self.hdr_left = tk.Frame(self.hdr_top)
        self.hdr_left.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.crumb = tk.Label(self.hdr_left, text="", anchor="w")
        self.crumb.pack(anchor="w")
        self.page_title = tk.Label(self.hdr_left, text="", anchor="w")
        self.page_title.pack(anchor="w")
        self.page_desc = tk.Label(self.header, text="", anchor="w")
        self.page_desc.pack(side="top", anchor="w", fill="x", padx=(31, 24), pady=(1, 0))
        self._desc_full = ""
        self.header.bind("<Configure>", lambda e: self._fit_desc())
        for key, txt in (("chat", "OFF AIR"), ("vm", "VM stopped"), ("obs", "OBS offline"), ("queue", "Queue 0"), ("viewers", "0 viewers")):
            pill = tk.Frame(self.tally_bar, highlightthickness=1, bd=0)
            pill.pack(side="left", padx=(8, 0))
            dot = tk.Label(pill, text="\u25cf", padx=0)
            if key in ("chat", "vm", "obs"):
                dot.pack(side="left", padx=(10, 0), pady=4)
            lbl = tk.Label(pill, text=txt)
            lbl.pack(side="left", padx=(6 if key in ("chat", "vm", "obs") else 11, 11), pady=4)
            self._tally[key] = [pill, dot, lbl, "off"]
        self.header_rule = tk.Frame(self.main, height=1)
        self.header_rule._studio_skip_tree = True
        self.header_rule.pack(side="top", fill="x")
        self.content = tk.Frame(self.main)
        self.content._studio_skip = True
        self.content.pack(side="top", fill="both", expand=True)

        self._layout()
        self.palette = CommandPalette(self, app)
        self.bind("<Configure>", self._on_resize, add="+")
        self.apply_tokens()

    def _layout(self, animate=False):
        want = not self._chat_hidden and not self._chat_auto
        full = int(318 * self._s)
        try:
            self.chat_toggle.configure(text="Hide chat" if want else "Show chat")
        except Exception:
            pass
        shown = bool(self.chatpane.winfo_manager())
        def setw(v):
            self.chatpane.configure(width=max(1, int(full * max(0.0, min(1.0, v)))))
        if animate and MOTION.on and want != shown:
            if want:
                self.chatpane.configure(width=1)
                for w in (self.status, self.main):
                    try: w.pack_forget()
                    except Exception: pass
                self.chatpane.pack(side="right", fill="y")
                self.status.pack(side="bottom", fill="x")
                self.main.pack(side="left", fill="both", expand=True)
                self.status.lift()
                MOTION.tween("chatpane", 300, setw, 1.0, a=MOTION.val.get("chatpane", 0.0) if MOTION.busy("chatpane") else 0.0)
            else:
                def _gone():
                    if self._chat_hidden or self._chat_auto:
                        self._layout(False)
                MOTION.tween("chatpane", 230, setw, 0.0, a=MOTION.val.get("chatpane", 1.0) if MOTION.busy("chatpane") else 1.0,
                             ease=_ease_in_cubic, done=_gone)
            return
        MOTION.cancel("chatpane")
        MOTION.val["chatpane"] = 1.0 if want else 0.0
        try: self.chatpane.configure(width=full)
        except Exception: pass
        for w in (self.chatpane, self.status, self.main):
            try: w.pack_forget()
            except Exception: pass
        if want:
            self.chatpane.pack(side="right", fill="y")
        self.status.pack(side="bottom", fill="x")
        self.main.pack(side="left", fill="both", expand=True)
        try: self.status.lift()
        except Exception: pass

    def _on_resize(self, e=None):
        try:
            w = self.winfo_width()
        except Exception:
            return
        narrow = w < int(1240 * self._s)
        if narrow != self._chat_auto and not self._chat_hidden:
            self._chat_auto = narrow
            self._layout()
            plog("UI", f"window {w}px wide - chat pane {'tucked away' if narrow else 'shown'}", verbose=True)
        elif self._chat_hidden:
            self._chat_auto = narrow

    def toggle_chat_pane(self, _e=None):
        if self._chat_auto and not self._chat_hidden:
            self._chat_auto = False
            self._chat_hidden = False
        else:
            self._chat_hidden = not self._chat_hidden
        try:
            self.app.config["ui_chat_hidden"] = self._chat_hidden
            self.app.save_settings()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self._layout(animate=True)
        return "break"

    def _search_hover(self, on):
        t = _STUDIO["tok"] or _studio_resolve("original")
        def paint(c):
            self.search_wrap.configure(highlightbackground=c, highlightcolor=c)
        MOTION.color("search_hover", 120 if on else 240, paint, t["muted"] if on else t["line"])

    def focus_search(self, _e=None):
        try:
            self.palette.open(from_click=_e is not None and str(getattr(_e, "type", "")) in ("ButtonPress", "4"))
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        return "break"

    def _rail_fade(self, key, to, dur):
        def fn(v, k=key):
            self._rail_hov[k] = max(0.0, min(1.0, v))
            if k in self._rail_btns:
                self._paint_rail_btn(k)
            else:
                self._paint_rail_extra(k)
        MOTION.tween(("railh", key), dur, fn, to, a=self._rail_hov.get(key, 0.0))

    def _rail_enter(self, key, tip=None):
        self._rail_hover = key
        self._rail_fade(key, 1.0, 120)
        cv = self._rail_btns.get(key) or self._rail_extra.get(key)
        text = tip or self.GROUP_TITLES.get(key, key)
        if cv is None:
            return
        try:
            t = _STUDIO["tok"] or _studio_resolve("original")
            self.tip.configure(text=text, bg=t["raised"], fg=t["hi"], font=_sf("ui", 9, "semi"))
            y = cv.winfo_rooty() - self.winfo_rooty() + cv.winfo_height() // 2
            x0 = self.rail.winfo_width()
            self.tip.place(x=x0 + 2, y=y, anchor="w")
            self.tip.lift()
            def step(v, x0=x0):
                tt = _STUDIO["tok"] or t
                self.tip.place_configure(x=int(x0 + 2 + 7 * v))
                self.tip.configure(fg=mix(tt["raised"], tt["hi"], max(0.0, min(1.0, v))))
            MOTION.tween("railtip", 170, step, 1.0, a=0.0, ease=_ease_out_back)
        except Exception:
            pass

    def _rail_leave(self, key):
        if self._rail_hover == key:
            self._rail_hover = None
        MOTION.cancel("railtip")
        try: self.tip.place_forget()
        except Exception: pass
        self._rail_fade(key, 0.0, 240)

    def shine(self):
        if MOTION.busy("logo_shine"):
            return
        MOTION.tween("logo_shine", 950, lambda v: self._paint_logo(v), 1.0, a=0.0, ease=_ease_in_out,
                     done=lambda: self._paint_logo())

    def _paint_logo(self, shine=None):
        t = _STUDIO["tok"] or _studio_resolve("original")
        rail = t.get("rail", t["side"])
        s = self._s
        cv = self.logo
        cv.delete("all")
        cv.configure(bg=rail)
        sz = int(36 * s)
        ox = (int(64 * s) - sz) / 2.0
        oy = (int(64 * s) - sz) / 2.0
        _rrect(cv, ox, oy, ox + sz, oy + sz, 9 * s, fill=t["accent"], outline="")
        if shine is not None and 0.0 < shine < 1.0:
            bw = 9 * s
            x0 = ox - sz + shine * (2.4 * sz)
            pts = [(x0, oy + sz + 4), (x0 + bw, oy + sz + 4), (x0 + bw + sz * 0.8, oy - 4), (x0 + sz * 0.8, oy - 4)]
            poly = _clip_poly(pts, ox + 3 * s, oy + 3 * s, ox + sz - 3 * s, oy + sz - 3 * s)
            if len(poly) >= 3:
                cv.create_polygon(*[c for pt in poly for c in pt], fill=mix(t["accent"], "#FFFFFF", 0.42), outline="")
        c = t["on_accent"]
        cx = ox + sz / 2.0
        cv.create_line(cx - 7 * s, oy + 10 * s, cx, oy + 18 * s, cx + 7 * s, oy + 10 * s,
                       fill=c, width=2.6 * s, capstyle="round", joinstyle="round")
        cv.create_line(cx, oy + 18 * s, cx, oy + 27 * s, fill=c, width=2.6 * s, capstyle="round")

    def _paint_rail_btn(self, g):
        cv = self._rail_btns.get(g)
        if cv is None:
            return
        t = _STUDIO["tok"] or _studio_resolve("original")
        rail = t.get("rail", t["side"])
        s = self._s
        W, H = int(64 * s), int(44 * s)
        act = max(0.0, min(1.0, self._rail_act.get(g, 0.0)))
        over = self._rail_act.get(g, 0.0)
        hov = max(0.0, min(1.0, self._rail_hov.get(g, 0.0)))
        cv.delete("all")
        cv.configure(bg=rail)
        bg = mix(mix(rail, t["raised"], hov), t["accent_tint"], act)
        if act > 0.01 or hov > 0.01:
            grow = 1.0 + 0.10 * max(0.0, over - 1.0) * 6
            ins = 12 * s / grow
            _rrect(cv, ins, 3 * s, W - ins, H - 3 * s, 10 * s, fill=bg, outline="")
        if act > 0.01:
            bh = (H - 24 * s) * max(0.0, over)
            cy = H / 2.0
            cv.create_rectangle(0, cy - bh / 2.0, 3 * s, cy + bh / 2.0, fill=t["accent"], outline="")
        col = mix(mix(t["muted"], t["hi"], hov), t["accent_text"], act)
        _draw_icon(cv, _NG_ICON.get(g, "main"), W / 2.0, H / 2.0, 19 * s, col, bg if (act > 0.01 or hov > 0.01) else rail, w=1.6 * s)

    def _paint_rail_extra(self, k):
        cv = self._rail_extra.get(k)
        if cv is None:
            return
        t = _STUDIO["tok"] or _studio_resolve("original")
        rail = t.get("rail", t["side"])
        s = self._s
        W, H = int(64 * s), int(40 * s)
        hov = max(0.0, min(1.0, self._rail_hov.get(k, 0.0)))
        cv.delete("all")
        cv.configure(bg=rail)
        ibg = rail
        if hov > 0.01:
            ibg = mix(rail, t["raised"], hov)
            _rrect(cv, 14 * s, 2 * s, W - 14 * s, H - 2 * s, 9 * s, fill=ibg, outline="")
        icon = "guide" if k == "guide" else ("sun" if t["dark"] else "moon")
        _draw_icon(cv, icon, W / 2.0, H / 2.0, 17 * s, mix(t["faint"], t["hi"], hov), ibg, w=1.5 * s)

    def _paint_rail(self):
        try:
            if not MOTION.busy("logo_shine"):
                self._paint_logo()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        for g in self._rail_btns:
            try: self._paint_rail_btn(g)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        for k in self._rail_extra:
            try: self._paint_rail_extra(k)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def show_group(self, group, jump=False):
        if group not in self._group_frames:
            return
        if group != self._group:
            first = self._group is None
            for g, gf in self._group_frames.items():
                if g != group:
                    gf.pack_forget()
            self._group_frames[group].pack(fill="x")
            self._group = group
            try:
                self.group_title.configure(text=self.GROUP_TITLES.get(group, group.title()))
            except Exception:
                pass
            for g in self._rail_btns:
                target = 1.0 if g == group else 0.0
                cur = self._rail_act.get(g, 0.0)
                if abs(cur - target) < 0.001:
                    continue
                def fn(v, gg=g):
                    self._rail_act[gg] = v
                    self._paint_rail_btn(gg)
                MOTION.tween(("raila", g), 340 if target else 220, fn, target, a=cur,
                             ease=_ease_out_back if target else _ease_out_cubic)
            if not first and MOTION.on:
                self._cascade(group)
        try:
            n = sum(1 for it in self._items.values() if it[3] == group)
            self.group_count.configure(text=f"{n} page{'s' if n != 1 else ''}")
        except Exception:
            pass
        if jump:
            target = self._last_in_group.get(group)
            if target is None:
                for f, l in self._pages:
                    it = self._items.get(l)
                    if it and it[3] == group:
                        target = f
                        break
            if target is not None and target is not self._current:
                self.select(target)

    def _cascade(self, group):
        t = _STUDIO["tok"] or _studio_resolve("original")
        gf = self._group_frames.get(group)
        if gf is None:
            return
        def ttl(v):
            tt = _STUDIO["tok"] or t
            vv = max(0.0, min(1.0, v))
            self.group_title.configure(fg=mix(tt["side"], tt["hi"], vv))
            self.group_count.configure(fg=mix(tt["side"], tt["faint"], vv))
            self.group_title.pack_configure(padx=(int(10 * (1 - vv)), 0))
        MOTION.tween("navgroup", 260, ttl, 1.0, a=0.0)
        for i, row in enumerate(gf.pack_slaves()):
            lab = getattr(row, "_nav_label", None)
            it = self._items.get(lab)
            if it is None:
                continue
            row._mo_cascade = True
            try:
                row.pack_configure(padx=(30, 12))
                it[2].configure(fg=t["side"])
            except Exception:
                pass
            def step(v, row=row, lbl=it[2], lab=lab):
                tt = _STUDIO["tok"] or t
                fg = self._item_target(lab)[1]
                row.pack_configure(padx=(int(round(10 + 20 * (1 - v))), 12))
                lbl.configure(fg=mix(tt["side"], fg, max(0.0, min(1.0, v))))
            def done(row=row, lab=lab):
                row._mo_cascade = False
                try: row.pack_configure(padx=(10, 12))
                except Exception: pass
                self._paint_item(lab, instant=True)
            MOTION.tween(("casc", lab), 340, step, 1.0, a=0.0, delay=i * 34, done=done)

    def _move_indicator(self, animate=True):
        t = _STUDIO["tok"] or _studio_resolve("original")
        lab = self.label_of(self._current) if self._current is not None else ""
        it = self._items.get(lab)
        try:
            self._ind.configure(bg=t["accent"])
        except Exception:
            pass
        if not it or it[3] != self._group:
            try: self._ind.place_forget()
            except Exception: pass
            self._ind_label = None
            return
        row = it[0]
        try:
            self._navwrap.update_idletasks()
            y = row.winfo_y() + row.master.winfo_y() + 8
            h = max(6, row.winfo_height() - 16)
        except Exception:
            return
        x = 10
        same = (self._ind_label is not None and self._ind_group == self._group and self._ind_y is not None)
        if self._ind_label == lab and same and not MOTION.busy("navind"):
            self._ind.place(x=x, y=y, width=3, height=h)
            self._ind_y, self._ind_h = y, h
            return
        prev_y = self._ind_y if self._ind_y is not None else y
        self._ind_label, self._ind_group = lab, self._group
        if not animate or not MOTION.on:
            MOTION.cancel("navind")
            self._ind.place(x=x, y=y, width=3, height=h)
            self._ind_y, self._ind_h = y, h
            return
        if same:
            y0 = prev_y
            dist = abs(y - y0)
            def step(v, y0=y0, y1=y, h=h, dist=dist):
                vv = max(0.0, min(1.0, v))
                cy = y0 + (y1 - y0) * v
                hh = h + dist * 0.45 * math.sin(math.pi * vv)
                self._ind_y = cy
                self._ind.place(x=x, y=int(cy - (hh - h) / 2.0), width=3, height=max(2, int(hh)))
            MOTION.tween("navind", 320, step, 1.0, a=0.0, ease=_ease_in_out)
        else:
            self._ind.place_forget()
            def step(v, y1=y, h=h):
                hh = max(1.0, h * max(0.0, v))
                self._ind_y = y1
                self._ind.place(x=x, y=int(y1 + (h - hh) / 2.0), width=3, height=int(hh))
            MOTION.tween("navind", 380, step, 1.0, a=0.0, ease=_ease_out_back, delay=140)
        self._ind_y, self._ind_h = y, h

    def _query(self):
        return ""

    def _filter(self):
        return None

    def add(self, frame, text="", **kw):
        label = (text or "").strip()
        self._pages.append((frame, label))
        group = "TOOLS"
        for gname, members in _ng:
            if label in members:
                group = gname; break
        gf = self._group_frames.get(group)
        if gf is None:
            gf = tk.Frame(self._navwrap)
            self._group_frames[group] = gf
            self._group_order.append(group)
        row = tk.Frame(gf, cursor="hand2")
        row._nav_label = label
        bar = tk.Frame(row, width=3)
        bar.pack(side="left", fill="y", pady=7)
        row._icon = None
        if label in _NAV_ROW_ICONS:
            isz = int(18 * self._s)
            ic = tk.Canvas(row, width=isz, height=isz, bd=0, highlightthickness=0, cursor="hand2")
            ic.pack(side="left", padx=(9, 0))
            ic._glyph = _NAV_ROW_ICONS[label]
            row._icon = ic
            ic.bind("<Button-1>", lambda e, f=frame: self.select(f))
            ic.bind("<Enter>", lambda e, l=label: self._hover(l, True))
            ic.bind("<Leave>", lambda e, l=label: self._hover(l, False))
        lbl = tk.Label(row, text=label, anchor="w", padx=(7 if label in _NAV_ROW_ICONS else 11), pady=7, cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True)
        badge = tk.Label(row, text="", padx=6, cursor="hand2")
        members = next((m for g, m in _ng if g == group), [])
        rank = members.index(label) if label in members else 999
        row._nav_rank = rank
        before = None
        for other in gf.pack_slaves():
            if getattr(other, "_nav_rank", 999) > rank:
                before = other
                break
        if before is not None:
            row.pack(fill="x", padx=(10, 12), pady=1, before=before)
        else:
            row.pack(fill="x", padx=(10, 12), pady=1)
        for w in (row, lbl, bar, badge):
            w.bind("<Button-1>", lambda e, f=frame: self.select(f))
            w.bind("<Enter>", lambda e, l=label: self._hover(l, True))
            w.bind("<Leave>", lambda e, l=label: self._hover(l, False))
        self._items[label] = [row, bar, lbl, group, frame, badge, None, None]
        self._buttons[label] = (lbl, frame)
        self._paint_item(label)
        if self._current is None:
            self.select(frame)
        return frame

    def frame_for(self, label):
        want = str(label).strip()
        for f, l in self._pages:
            if l.strip() == want:
                return f
        return None

    def remove(self, frame):
        label = self.label_of(frame)
        self._pages = [(f, l) for (f, l) in self._pages if f is not frame]
        it = self._items.pop(label, None)
        self._buttons.pop(label, None)
        if it is not None:
            try: it[0].destroy()
            except Exception: pass
        if self._current is frame:
            self._current = None
            if self._pages:
                self.select(self._pages[0][0])
        try: frame.destroy()
        except Exception: pass

    def set_row_visible(self, label, visible):
        it = self._items.get(label)
        if not it:
            return
        row = it[0]
        try:
            if not visible:
                row.pack_forget()
                if self._current is it[4]:
                    for f, l in self._pages:
                        other = self._items.get(l)
                        if f is not it[4] and other is not None and other[0].winfo_manager():
                            self.select(f)
                            break
            else:
                gf = row.master
                rank = getattr(row, "_nav_rank", 999)
                before = None
                for other in gf.pack_slaves():
                    if getattr(other, "_nav_rank", 999) > rank:
                        before = other
                        break
                if before is not None:
                    row.pack(fill="x", padx=(10, 12), pady=1, before=before)
                else:
                    row.pack(fill="x", padx=(10, 12), pady=1)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def set_badge(self, label, text):
        it = self._items.get(label)
        if not it:
            return
        badge = it[5]
        try:
            if str(badge.cget("text")) == str(text or ""):
                return
            badge.configure(text=text or "")
            if text:
                badge.pack(side="right", padx=(0, 8))
            else:
                badge.pack_forget()
            self._paint_item(label, instant=True)
            if text and MOTION.on:
                t = _STUDIO["tok"] or _studio_resolve("original")
                def paint(c, b=badge):
                    b.configure(bg=c)
                rest = mix(it[6] or t["side"], t["hi"], 0.08)
                MOTION.color(("badge", label), 900, paint, rest, frm=t["accent"])
                MOTION.color(("badgefg", label), 900, lambda c, b=badge: b.configure(fg=c), t["text"], frm=t["on_accent"])
        except Exception:
            pass

    def _hover(self, label, on):
        if self._items.get(label):
            self._paint_item(label, hover=on)

    def _item_target(self, label, hover=None):
        it = self._items.get(label)
        t = _STUDIO["tok"] or _studio_resolve("original")
        if hover is None:
            hover = getattr(it[0], "_mo_hover", False) if it else False
        active = bool(it) and it[4] is self._current
        side = t["side"]
        if active:
            return mix(side, t["accent"], 0.12), t["hi"], _sf("ui", 10, "semi"), True
        if hover:
            return mix(side, t["hi"], 0.05), t["hi"], _sf("ui", 10), False
        return side, t["muted"], _sf("ui", 10), False

    def _paint_item(self, label, hover=None, instant=False):
        it = self._items.get(label)
        if not it:
            return
        row, bar, lbl, badge = it[0], it[1], it[2], it[5]
        if hover is not None:
            row._mo_hover = bool(hover)
        bg, fg, font, active = self._item_target(label)
        try:
            lbl.configure(font=font)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        def apply(bgc, fgc):
            tt = _STUDIO["tok"] or _studio_resolve("original")
            row.configure(bg=bgc)
            bar.configure(bg=bgc)
            lbl.configure(bg=bgc)
            ic = getattr(row, "_icon", None)
            if ic is not None:
                ic.configure(bg=bgc)
                ic.delete("all")
                isz = int(ic.cget("width"))
                img = _user_logo(isz)
                if img is not None:
                    ic.create_image(isz / 2.0, isz / 2.0, image=img)
                else:
                    _draw_icon(ic, ic._glyph, isz / 2.0, isz / 2.0, isz * 0.9, fgc, bgc, w=1.4 * self._s)
            if not getattr(row, "_mo_cascade", False):
                lbl.configure(fg=fgc)
            if not MOTION.busy(("badge", label)):
                badge.configure(bg=mix(bgc, tt["hi"], 0.08), fg=tt["text"], font=_sf("ui", 8, "semi"))
            it[6], it[7] = bgc, fgc
        if instant or not MOTION.on or it[6] is None:
            MOTION.cancel(("navi", label))
            try: apply(bg, fg)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            return
        b0, f0 = it[6], it[7]
        if _hx(b0) == _hx(bg) and _hx(f0) == _hx(fg) and not MOTION.busy(("navi", label)):
            return
        dur = 90 if (hover and not active) else (230 if active else 200)
        def step(p, b0=b0, f0=f0, b1=bg, f1=fg):
            pp = max(0.0, min(1.0, p))
            apply(mix(b0, b1, pp), mix(f0, f1, pp))
        MOTION.tween(("navi", label), dur, step, 1.0, a=0.0)

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

    def label_of(self, frame):
        for f, l in self._pages:
            if f is frame:
                return l
        return ""

    def group_of(self, label):
        it = self._items.get(label)
        return it[3] if it else "TOOLS"

    def select(self, tab=None):
        if tab is None:
            return str(self._current) if self._current is not None else ""
        target = None
        key = str(tab)
        for f, _ in self._pages:
            if f is tab or str(f) == key:
                target = f; break
        if target is None: return ""
        prev = self._current
        animate = MOTION.on and prev is not None and prev is not target
        if prev is not None and prev is not target:
            try:
                prev.place_forget()
                prev.pack_forget()
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        try:
            if prev is not target or not target.winfo_manager():
                target.place(in_=self.content, x=0, y=(22 if animate else 0), relwidth=1.0, relheight=1.0)
            self.status.lift()
        except Exception as e:
            try: console_log("ERROR", f"could not show tab: {e}")
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        self._current = target
        name = self.label_of(target)
        group = self.group_of(name)
        self._last_in_group[group] = target
        self.show_group(group)
        for lbl in list(self._items):
            self._paint_item(lbl)
        try:
            self.page_title.configure(text=name)
            self.crumb.configure(text=self.GROUP_TITLES.get(group, group.title()))
            self._desc_full = getattr(self.app, "_page_desc", {}).get(name) or _PAGE_BLURB.get(name, "")
            self._fit_desc()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if animate:
            self._page_anim(target)
        else:
            MOTION.cancel("page")
        try: self.after_idle(self._move_indicator)
        except Exception: pass
        if prev is not target:
            plog("NAV", f"page -> {name}", verbose=True)
            try: self.app._on_page_shown(target)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        return str(target)

    def _page_anim(self, target):
        def step(v, f=target):
            t = _STUDIO["tok"] or _studio_resolve("original")
            vv = max(0.0, min(1.0, v))
            f.place_configure(y=int(round(22 * (1.0 - v))))
            bg = t["bg"]
            self.page_title.configure(fg=mix(bg, t["hi"], vv))
            self.page_title.pack_configure(padx=(int(round(14 * (1.0 - vv))), 0))
            self.crumb.configure(fg=mix(bg, t["accent_text"], vv))
            self.page_desc.configure(fg=mix(bg, t["muted"], min(1.0, vv * 1.15)))
        MOTION.tween("page", 360, step, 1.0, a=0.0, ease=_ease_out_cubic)

    def _fit_desc(self):
        try:
            full = self._desc_full or ""
            avail = self.header.winfo_width() - 60
            if avail < 40:
                self.page_desc.configure(text=full)
                return
            f = tkfont.Font(root=self, font=self.page_desc.cget("font"))
            if f.measure(full) <= avail:
                self.page_desc.configure(text=full)
                return
            lo, hi = 0, len(full)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if f.measure(full[:mid].rstrip() + "...") <= avail:
                    lo = mid
                else:
                    hi = mid - 1
            self.page_desc.configure(text=full[:lo].rstrip() + "...")
        except Exception:
            pass

    def step(self, delta):
        if not self._pages:
            return
        idx = self.index("current")
        self.select(self._pages[(idx + delta) % len(self._pages)][0])

    def apply_tokens(self):
        t = _STUDIO["tok"] or _studio_resolve("original")
        side, panel, rail = t["side"], t["panel"], t.get("rail", t["side"])
        try:
            self.configure(bg=t["bg"])
            self.rail.configure(bg=rail)
            self.rail_foot.configure(bg=rail)
            self.rail_rule.configure(bg=t["line"])
            self.side_rule.configure(bg=t["line"])
            for w in (self.side, self.brand, self._navwrap, self.group_head):
                w.configure(bg=side)
            self.brand_name.configure(bg=side, fg=t["hi"], font=_sf("display", 17))
            self.brand_sub.configure(bg=side, fg=t["faint"], font=_sf("ui", 8))
            sbg = t["input"]
            self.search_wrap.configure(bg=sbg, highlightbackground=t["line"], highlightcolor=t["line"])
            self.search_icon.configure(bg=sbg)
            self.search_icon.delete("all")
            _draw_icon(self.search_icon, "search", int(9 * self._s), int(9 * self._s), 14 * self._s, t["faint"], sbg, w=1.4 * self._s)
            self.search_lbl.configure(bg=sbg, fg=t["faint"], font=_sf("ui", 9))
            self.search_kbd.configure(bg=t["raised"], fg=t["muted"], font=_sf("mono", 8))
            self.group_title.configure(bg=side, fg=t["hi"], font=_sf("display", 12))
            self.group_count.configure(bg=side, fg=t["faint"], font=_sf("ui", 8))
            for g, gf in self._group_frames.items():
                gf.configure(bg=side)
            self.activity.configure(bg=t["card"], highlightbackground=t["line"], highlightcolor=t["line"])
            self.act_head.configure(bg=t["card"])
            self.act_title.configure(bg=t["card"], fg=t["muted"], font=_sf("ui", 8, "semi"))
            self.act_dot.configure(bg=t["card"], font=_sf("ui", 7))
            self.act_cmd.configure(bg=t["card"], fg=t["hi"], font=_sf("mono", 9), wraplength=int(170 * self._s))
            self.act_sub.configure(bg=t["card"], fg=t["faint"], font=_sf("ui", 8))
            self._paint_activity()
            for w in (self.chatpane, self.chat_card, self.chat_hdr, self.chat_foot, self.chat_body, self.chat_empty):
                w.configure(bg=panel)
            for w in (self.chat_rule, self.chat_sep, self.chat_foot_sep):
                w.configure(bg=t["line"])
            self.chat_title.configure(bg=panel, fg=t["hi"], font=_sf("display", 14))
            self.chat_sub.configure(bg=panel, fg=t["faint"], font=_sf("ui", 9))
            self.chat_empty_icon.configure(bg=panel)
            self.chat_empty_icon.delete("all")
            _draw_icon(self.chat_empty_icon, "chat", int(20 * self._s), int(20 * self._s), 30 * self._s, t["faint"], panel, w=1.6 * self._s)
            self.chat_empty_t.configure(bg=panel, fg=t["text"], font=_sf("ui", 10, "semi"))
            self.chat_empty_s.configure(bg=panel, fg=t["faint"], font=_sf("ui", 9))
            self._paint_chat_state()
            self.chatbox.frame.configure(bg=panel)
            self.chatbox.configure(bg=panel, fg=t["text"], font=_sf("ui", 10), selectbackground=t["sel"],
                                   selectforeground=t["hi"], insertbackground=t["hi"], inactiveselectbackground=t["sel"])
            self.chatbox.tag_config("ts", foreground=t["faint"], font=_sf("mono", 8))
            self.chatbox.tag_config("n_usr", foreground=t["hi"], font=_sf("ui", 10, "semi"))
            self.chatbox.tag_config("n_cmd", foreground=t["accent_text"], font=_sf("ui", 10, "semi"))
            self.chatbox.tag_config("n_sys", foreground=t["ok"], font=_sf("ui", 10, "semi"))
            self.chatbox.tag_config("n_err", foreground=t["bad"], font=_sf("ui", 10, "semi"))
            self.chatbox.tag_config("n_mod", foreground=t["violet"], font=_sf("ui", 10, "semi"))
            for i, c in enumerate(self.NAME_COLORS_DARK):
                col = c if t["dark"] else mix(c, "#000000", 0.42)
                self.chatbox.tag_config(f"nc{i}", foreground=col, font=_sf("ui", 10, "semi"))
            self.chatbox.tag_config("m_usr", foreground=t["text"])
            self.chatbox.tag_config("m_cmd", foreground=mix(t["accent_text"], t["text"], 0.35), font=_sf("mono", 9))
            self.chatbox.tag_config("m_sys", foreground=t["muted"])
            self.chatbox.tag_config("m_err", foreground=t["bad_soft"])
            self.chatbox.tag_config("m_mod", foreground=t["text"])
            self.chatbox.tag_config("b_mod", foreground=t["violet"], background=t["violet_tint"], font=_sf("ui", 7, "semi"))
            self.chatbox.tag_config("b_own", foreground=t["on_accent"], background=t["accent"], font=_sf("ui", 7, "semi"))
            self.chatbox.tag_config("b_sys", foreground=t["muted"], background=t["raised"], font=_sf("ui", 7, "semi"))
            self.chatbox.tag_config("line", lmargin1=0, lmargin2=int(12 * self._s))
            for tg in ("usr", "cmd", "sys", "err", "mod"):
                self.chatbox.tag_config(tg, foreground={"usr": t["text"], "cmd": t["accent_text"], "sys": t["ok"],
                                                          "err": t["bad"], "mod": t["violet"]}[tg])
            try:
                self.app._style_ttk_check(self.autoscroll_cb, panel)
                self.app._style_scrollbar(self.chatbox.vbar, panel)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            try: self.clear_btn.studio_style(panel, _sf("ui", 9, "semi"))
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            self.status.configure(bg=rail)
            self.status_rule.configure(bg=t["line"])
            self.status_left.configure(bg=rail, fg=t["muted"], font=_sf("ui", 8))
            self.status_right.configure(bg=rail, fg=t["muted"], font=_sf("ui", 8))
            self.status_hint.configure(bg=rail, fg=t["faint"], font=_sf("ui", 8))
            self.chat_toggle.configure(bg=rail, fg=t["accent_text"], font=_sf("ui", 8, "semi"))
            self.main.configure(bg=t["bg"])
            self.header.configure(bg=t["bg"], height=int((92 + 6 * max(0, int(_STUDIO.get("delta", 0)))) * self._s))
            self.hdr_left.configure(bg=t["bg"])
            self.hdr_top.configure(bg=t["bg"])
            self.header_rule.configure(bg=t["line"])
            self.content.configure(bg=t["bg"])
            self.crumb.configure(bg=t["bg"], fg=t["accent_text"], font=_sf("ui", 8, "semi"))
            self.page_title.configure(bg=t["bg"], fg=t["hi"], font=_sf("display", 21))
            self.page_desc.configure(bg=t["bg"], fg=t["muted"], font=_sf("ui", 9))
            self.tally_bar.configure(bg=t["bg"])
            for key in self._tally:
                self._paint_tally(key)
            for lbl in list(self._items):
                self._paint_item(lbl, instant=True)
            for tw in list(self._toasts):
                self._paint_toast(tw)
            self._paint_rail()
            self.act_bar.configure(bg=t["card"])
            self._ind.configure(bg=t["accent"])
            self.after_idle(lambda: self._move_indicator(False))
            self.palette.apply_tokens()
            self._fit_desc()
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def set_activity(self, current, queued, waiting=0):
        cur = (current or "").strip()
        key = (cur, queued, waiting)
        if getattr(self, "_act_key", None) == key:
            return
        self._act_key = key
        try:
            old_cmd = str(self.act_cmd.cget("text"))
            if cur:
                self.act_title.configure(text="Executing")
                show = cur if len(cur) <= 60 else cur[:57] + "..."
                self.act_cmd.configure(text=show)
            else:
                self.act_title.configure(text="Executor idle")
                self.act_cmd.configure(text="Nothing running")
            self.act_sub.configure(text=f"Queue {queued}" + (f"  /  {waiting} viewer{'s' if waiting != 1 else ''} waiting" if waiting else ""))
            self._paint_activity()
            t = _STUDIO["tok"] or _studio_resolve("original")
            if str(self.act_cmd.cget("text")) != old_cmd:
                MOTION.color("actcmd", 260, lambda c: self.act_cmd.configure(fg=c), t["hi"] if cur else t["faint"], frm=t["card"])
            if cur and not MOTION.looping("exec"):
                MOTION.loop("exec", self._exec_frame, 1400, fps=40)
            elif not cur and MOTION.looping("exec"):
                MOTION.unloop("exec")
        except Exception:
            pass

    def _exec_frame(self, ph):
        t = _STUDIO["tok"] or _studio_resolve("original")
        cv = self.act_bar
        cv.delete("all")
        busy = bool(getattr(self, "_act_key", ("",))[0])
        w = cv.winfo_width()
        if not busy or w < 10:
            self.act_dot.configure(fg=t["ok"] if busy else t["faint"])
            return
        cv.create_rectangle(0, 0, w, 2, fill=t["raised"], outline="")
        seg = w * 0.38
        x = -seg + _ease_in_out(ph) * (w + seg)
        for i in range(6):
            a = x + seg * i / 6.0
            b = x + seg * (i + 1) / 6.0
            k = 1.0 - abs(i - 2.5) / 3.0
            cv.create_rectangle(max(0, a), 0, min(w, b), 2, fill=mix(t["raised"], t["ok"], max(0.0, k)), outline="")
        self.act_dot.configure(fg=mix(t["ok"], t["card"], 0.55 * _breath(ph)))

    def _paint_activity(self):
        t = _STUDIO["tok"] or _studio_resolve("original")
        busy = bool(getattr(self, "_act_key", ("",))[0])
        try:
            self.act_dot.configure(fg=(t["ok"] if busy else t["faint"]))
            self.act_cmd.configure(fg=(t["hi"] if busy else t["faint"]))
        except Exception:
            pass

    def set_chat_state(self, alive):
        alive = bool(alive)
        if alive == self._chat_alive and getattr(self, "_chat_state_painted", False):
            return
        was = getattr(self, "_chat_state_painted", False)
        self._chat_alive = alive
        self._chat_state_painted = True
        self._paint_chat_state()
        if was and MOTION.on:
            t = _STUDIO["tok"] or _studio_resolve("original")
            bg = t["ok_tint"] if alive else t["panel"]
            def paint(c):
                self.chat_state.configure(bg=c)
                self.chat_state_dot.configure(bg=c)
                self.chat_dot.configure(bg=c)
            MOTION.color("chatstate", 800, paint, bg, frm=mix(bg, t["ok"] if alive else t["hi"], 0.45))

    def _chat_live_frame(self, ph):
        if not self._chat_alive:
            return
        t = _STUDIO["tok"] or _studio_resolve("original")
        try:
            self.chat_state_dot.configure(fg=mix(t["ok"], t["ok_tint"], 0.75 * _breath(ph)))
        except Exception:
            pass

    def _paint_chat_state(self):
        t = _STUDIO["tok"] or _studio_resolve("original")
        panel = t["panel"]
        alive = self._chat_alive
        if alive:
            MOTION.loop("chatlive", self._chat_live_frame, 1700, fps=30)
        else:
            MOTION.unloop("chatlive", rest=False)
        bg = t["ok_tint"] if alive else panel
        edge = t["ok_edge"] if alive else t["line"]
        try:
            self.chat_state.configure(bg=bg, highlightbackground=edge, highlightcolor=edge)
            self.chat_state_dot.configure(bg=bg, fg=t["ok"] if alive else t["faint"], font=_sf("ui", 7))
            self.chat_dot.configure(bg=bg, fg=t["ok_soft"] if alive else t["faint"], font=_sf("ui", 8, "semi"),
                                    text="connected" if alive else "offline")
        except Exception:
            pass

    def set_tally(self, key, text, state):
        it = self._tally.get(key)
        if not it:
            return
        if key == "chat":
            text = str(text).upper()
        if it[2].cget("text") != text or it[3] != state:
            changed = it[3] != state
            it[3] = state
            it[2].configure(text=text)
            self._paint_tally(key)
            if changed and MOTION.on:
                t = _STUDIO["tok"] or _studio_resolve("original")
                bg = self._tally_colors(state)[0]
                pill, dot, lbl = it[0], it[1], it[2]
                def paint(c, pill=pill, dot=dot, lbl=lbl):
                    pill.configure(bg=c)
                    dot.configure(bg=c)
                    lbl.configure(bg=c)
                MOTION.color(("tally", key), 700, paint, bg, frm=mix(bg, t["hi"], 0.4))
            if key == "chat":
                if state == "onair":
                    MOTION.loop("onair", self._onair_frame, 1900, fps=30)
                else:
                    MOTION.unloop("onair", rest=False)

    def _onair_frame(self, ph):
        it = self._tally.get("chat")
        if not it or it[3] != "onair" or MOTION.busy(("tally", "chat")):
            return
        t = _STUDIO["tok"] or _studio_resolve("original")
        s = _breath(ph)
        bg = mix(t["bad"], mix(t["bad"], "#FFFFFF", 0.22), s)
        pill, dot, lbl = it[0], it[1], it[2]
        pill.configure(bg=bg, highlightbackground=bg, highlightcolor=bg)
        dot.configure(bg=bg, fg=mix("#FFFFFF", mix(t["bad"], "#FFFFFF", 0.35), 1.0 - s))
        lbl.configure(bg=bg)

    def pulse(self):
        if MOTION.ambient:
            return
        self._pulse = not self._pulse
        it = self._tally.get("chat")
        if it and it[3] == "onair":
            t = _STUDIO["tok"] or _studio_resolve("original")
            try:
                it[1].configure(fg="#FFFFFF" if self._pulse else mix(t["bad"], "#FFFFFF", 0.45))
            except Exception:
                pass

    def _tally_colors(self, state):
        t = _STUDIO["tok"] or _studio_resolve("original")
        if state == "onair":
            return t["bad"], t["bad"], "#FFFFFF", "#FFFFFF"
        if state == "ok":
            return t["card"], t["line"], t["ok"], t["text"]
        if state == "warn":
            return t["warn_tint"], t["warn_edge"], t["warn"], t["hi"]
        if state == "bad":
            return t["bad_tint"], t["bad_edge"], t["bad"], t["hi"]
        if state == "neutral":
            return t["card"], t["line"], t["faint"], t["text"]
        return t["bg"], t["line"], t["faint"], t["muted"]

    def _paint_tally(self, key):
        t = _STUDIO["tok"] or _studio_resolve("original")
        pill, dot, lbl, state = self._tally[key]
        font = _sf("display", 10)
        if state == "onair":
            bg, edge, dotc, fg = t["bad"], t["bad"], "#FFFFFF", "#FFFFFF"
        elif state == "ok":
            bg, edge, dotc, fg = t["card"], t["line"], t["ok"], t["text"]
        elif state == "warn":
            bg, edge, dotc, fg = t["warn_tint"], t["warn_edge"], t["warn"], t["hi"]
        elif state == "bad":
            bg, edge, dotc, fg = t["bad_tint"], t["bad_edge"], t["bad"], t["hi"]
        elif state == "neutral":
            bg, edge, dotc, fg = t["card"], t["line"], t["faint"], t["text"]
        else:
            bg, edge, dotc, fg = t["bg"], t["line"], t["faint"], t["muted"]
        try:
            pill.configure(bg=bg, highlightbackground=edge, highlightcolor=edge)
            dot.configure(bg=bg, fg=dotc, font=_sf("ui", 7))
            lbl.configure(bg=bg, fg=fg, font=font)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def toast(self, text, kind="info", ms=None):
        try:
            if not self.app.config.get("ui_toasts", True):
                return
            now = time.time()
            for tw in self._toasts:
                if getattr(tw, "_text", "") == text and now - getattr(tw, "_born", 0) < 6:
                    return
            while len(self._toasts) >= 4:
                self._drop_toast(self._toasts[0])
            box = tk.Frame(self, highlightthickness=1, bd=0, cursor="hand2")
            box._studio_skip_tree = True
            box._text, box._born, box._kind = text, now, kind
            bar = tk.Frame(box, width=3)
            bar.pack(side="left", fill="y")
            ttl = {"bad": "Error", "warn": "Warning", "ok": "Done"}.get(kind, "Notice")
            inner = tk.Frame(box)
            inner.pack(side="left", fill="both", expand=True, padx=(12, 14), pady=(9, 10))
            head = tk.Label(inner, text=ttl, anchor="w")
            head.pack(fill="x")
            msg = tk.Label(inner, text=text, justify="left", anchor="w", wraplength=320)
            msg.pack(fill="x", pady=(1, 0))
            prog = tk.Frame(box, height=2)
            box._prog = prog
            box._parts = (bar, msg, head, inner)
            box._y = None
            box._off = 420.0 if MOTION.on else 0.0
            box._frac = 1.0
            box._life = ms or (8000 if kind == "bad" else 4500)
            for w in (box, bar, msg, head, inner, prog):
                w.bind("<Button-1>", lambda e, b=box: self._drop_toast(b))
            self._toasts.append(box)
            self._paint_toast(box)
            self._place_toasts()
            if MOTION.on:
                prog.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0, height=2)
                MOTION.tween(("toastx", str(box)), 460, lambda v, b=box: self._toast_x(b, 420.0 * (1.0 - v)), 1.0, a=0.0,
                             ease=_ease_out_back)
                self._toast_timer(box)
                def _enter(e=None, b=box):
                    MOTION.cancel(("toastlife", str(b)))
                def _leave(e=None, b=box):
                    if e is not None and _mo_inside(b, e):
                        return
                    if b in self._toasts:
                        self._toast_timer(b)
                box.bind("<Enter>", _enter)
                box.bind("<Leave>", _leave)
            else:
                box._after_id = self.after(box._life, lambda b=box: self._drop_toast(b))
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _toast_x(self, box, off):
        box._off = off
        box.place_configure(x=int(-22 + off))

    def _toast_timer(self, box):
        frac = max(0.02, getattr(box, "_frac", 1.0))
        def step(v, b=box):
            b._frac = v
            b._prog.place_configure(relwidth=max(0.0, v))
        MOTION.tween(("toastlife", str(box)), box._life * frac, step, 0.0, a=frac, ease=_ease_linear,
                     done=lambda b=box: self._drop_toast(b), slow=True, scale=False)

    def _paint_toast(self, box):
        t = _STUDIO["tok"] or _studio_resolve("original")
        col = {"bad": t["bad"], "warn": t["warn"], "ok": t["ok"]}.get(box._kind, t["accent"])
        bar, msg, head, inner = box._parts
        box.configure(bg=t["raised"], highlightbackground=mix(t["line"], col, 0.35), highlightcolor=t["line"])
        bar.configure(bg=col)
        inner.configure(bg=t["raised"])
        try: box._prog.configure(bg=mix(t["raised"], col, 0.75))
        except Exception: pass
        head.configure(bg=t["raised"], fg=col if t["dark"] else mix(col, "#000000", 0.25), font=_sf("ui", 8, "semi"))
        msg.configure(bg=t["raised"], fg=t["hi"], font=_sf("ui", 10))

    def _place_toasts(self):
        try: y = self.header.winfo_reqheight() + 14
        except Exception: y = 80
        for box in reversed(self._toasts):
            try:
                box.update_idletasks()
                if box._y is None or not MOTION.on:
                    box._y = y
                    box.place(in_=self.main, relx=1.0, rely=0.0, x=int(-22 + box._off), y=y, anchor="ne")
                elif abs(box._y - y) > 0.5:
                    def step(v, b=box):
                        b._y = v
                        b.place_configure(y=int(round(v)))
                    MOTION.tween(("toasty", str(box)), 300, step, float(y), a=float(box._y), ease=_ease_out_cubic)
                box.lift()
                y += box.winfo_reqheight() + 8
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        try:
            if self.palette.is_open:
                self.palette.frame.lift()
        except Exception:
            pass

    def _drop_toast(self, box):
        if box not in self._toasts:
            return
        self._toasts.remove(box)
        aid = getattr(box, "_after_id", None)
        if aid:
            box._after_id = None
            try: self.after_cancel(aid)
            except Exception: pass
        MOTION.cancel(("toastlife", str(box)))
        MOTION.cancel(("toasty", str(box)))
        def kill(b=box):
            MOTION.cancel(("toastx", str(b)))
            try: b.destroy()
            except Exception: pass
        if MOTION.on:
            MOTION.tween(("toastx", str(box)), 240, lambda v, b=box: self._toast_x(b, 440.0 * v), 1.0,
                         a=0.0, ease=_ease_in_cubic, done=kill)
        else:
            kill()
        self._place_toasts()

    def _name_tag(self, user):
        import zlib
        return f"nc{zlib.crc32(str(user).lower().encode('utf-8', 'ignore')) % len(self.NAME_COLORS_DARK)}"

    def push_chat(self, user, msg, tag="usr", badge=None):
        try:
            tag = tag if tag in ("usr", "cmd", "sys", "err", "mod") else "usr"
            if self._chat_count == 0:
                MOTION.unloop("chatempty", rest=False)
                try: self.chat_empty.place_forget()
                except Exception: pass
            self._chat_count += 1
            self.chatbox.configure(state="normal")
            line_start = self.chatbox.index("end-1c")
            self.chatbox.insert("end", time.strftime("%H:%M") + "  ", ("ts", "line"))
            if badge:
                btag = {"MOD": "b_mod", "OWNER": "b_own"}.get(badge, "b_sys")
                self.chatbox.insert("end", f" {badge} ", (btag, "line"))
                self.chatbox.insert("end", " ", ("line",))
            name = str(user).lstrip("@")
            ntag = self._name_tag(name) if tag in ("usr", "cmd") else "n_" + tag
            self.chatbox.insert("end", f"{name}", (ntag, "line"))
            self.chatbox.insert("end", "  ", ("line",))
            self.chatbox.insert("end", f"{msg}\n", ("m_" + tag, "line"))
            lines = int(self.chatbox.index("end-1c").split(".")[0])
            if lines > 400:
                self.chatbox.delete("1.0", f"{lines-300}.0")
            self._flash_line(line_start)
            if self.autoscroll.get(): self.chatbox.see("end")
            self.chatbox.configure(state="disabled")
            self.chat_sub.configure(text=f"{self._chat_count} message{'s' if self._chat_count != 1 else ''} this session")
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _flash_line(self, start):
        if not MOTION.on:
            return
        self._fl_i = (self._fl_i + 1) % 14
        tag = f"fl{self._fl_i}"
        cb = self.chatbox
        try:
            cb.tag_remove(tag, "1.0", "end")
            cb.tag_add(tag, start, "end-1c")
            cb.tag_lower(tag)
        except Exception:
            return
        def step(v, tag=tag):
            t = _STUDIO["tok"] or _studio_resolve("original")
            cb.tag_config(tag, background=mix(mix(t["panel"], t["accent"], 0.22), t["panel"], max(0.0, min(1.0, v))))
        def done(tag=tag):
            cb.tag_remove(tag, "1.0", "end")
        MOTION.tween(("chatfl", tag), 1300, step, 1.0, a=0.0, ease=_ease_in_out, done=done)

    def _chat_empty_frame(self, ph):
        if self._chat_count:
            return
        t = _STUDIO["tok"] or _studio_resolve("original")
        dy = -5.0 * math.sin(2 * math.pi * ph)
        try:
            if self.chat_empty.winfo_ismapped():
                self.chat_empty.place_configure(y=int(round(dy)))
                cv = self.chat_empty_icon
                cv.delete("all")
                panel = t["panel"]
                col = mix(t["faint"], t["accent_text"], 0.5 * _breath(ph))
                _draw_icon(cv, "chat", int(20 * self._s), int(20 * self._s), 30 * self._s, col, panel, w=1.6 * self._s)
                k = int(ph * 3 * 3) % 3
                for i in range(3):
                    r = 1.6 * self._s
                    cx = (13 + i * 7) * self._s
                    cy = 17 * self._s
                    cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=col if i == k else mix(panel, col, 0.35), outline="")
        except Exception:
            pass

    def clear_chat(self):
        try:
            self.chatbox.configure(state="normal")
            self.chatbox.delete("1.0", "end")
            self.chatbox.configure(state="disabled")
            self._chat_count = 0
            self.chat_sub.configure(text="No messages yet")
            self.chat_empty.place(relx=0.5, rely=0.42, anchor="center")
            MOTION.loop("chatempty", self._chat_empty_frame, 2600, fps=30)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def set_status(self, left=None, right=None, running=False):
        try:
            if left is not None and self.status_left.cget("text") != left:
                self.status_left.configure(text=left)
            if right is not None and self.status_right.cget("text") != right:
                self.status_right.configure(text=right)
        except Exception as _ex:
            _trace(_ex_where(), _ex)


class CommandPalette:

    MAX_ROWS = 9

    def __init__(self, nav, app):
        self.nav = nav
        self.app = app
        self.is_open = False
        self._rows = []
        self._results = []
        self._sel = 0
        s = nav._s
        self.frame = tk.Frame(nav, highlightthickness=1, bd=0)
        self.frame._studio_skip_tree = True
        top = tk.Frame(self.frame)
        top.pack(fill="x")
        self.top = top
        self.icon = tk.Canvas(top, width=int(22 * s), height=int(22 * s), bd=0, highlightthickness=0)
        self.icon.pack(side="left", padx=(16, 8), pady=int(14 * s))
        self.var = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.var, bd=0, relief="flat", highlightthickness=0)
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.esc = tk.Label(top, text="Esc", padx=6)
        self.esc.pack(side="right", padx=(8, 14))
        self.rule = tk.Frame(self.frame, height=1)
        self.rule.pack(fill="x")
        self.list = tk.Frame(self.frame)
        self.list.pack(fill="both", expand=True, pady=6)
        for i in range(self.MAX_ROWS):
            row = tk.Frame(self.list, cursor="hand2")
            kind = tk.Label(row, text="", width=6, anchor="w", cursor="hand2")
            kind.pack(side="left", padx=(14, 4), pady=6)
            title = tk.Label(row, text="", anchor="w", cursor="hand2")
            title.pack(side="left", fill="x", expand=True)
            sub = tk.Label(row, text="", anchor="e", cursor="hand2")
            sub.pack(side="right", padx=(8, 16))
            for w in (row, kind, title, sub):
                w.bind("<Enter>", lambda e, k=i: self._hover(k))
                w.bind("<Button-1>", lambda e, k=i: self._click(k))
            self._rows.append((row, kind, title, sub))
        self.empty = tk.Label(self.list, text="No matches", pady=14)
        self.rule2 = tk.Frame(self.frame, height=1)
        self.rule2.pack(fill="x")
        self.foot = tk.Label(self.frame, text="Enter to run    Up / Down to move    Start with ! to send a command to the VM", anchor="w", padx=16, pady=7)
        self.foot.pack(fill="x")
        self.var.trace_add("write", lambda *a: self.refresh())
        self.entry.bind("<Down>", lambda e: self._move(1))
        self.entry.bind("<Up>", lambda e: self._move(-1))
        self.entry.bind("<Tab>", lambda e: self._move(1))
        self.entry.bind("<Return>", lambda e: self._run())
        self.entry.bind("<KP_Enter>", lambda e: self._run())
        self.entry.bind("<Escape>", lambda e: self.close())
        try:
            nav.winfo_toplevel().bind_all("<ButtonPress-1>", self._outside, add="+")
        except Exception:
            pass

    def _outside(self, e):
        if not self.is_open:
            return
        if getattr(self, "_skip_click", False):
            self._skip_click = False
            return
        try:
            w = e.widget
            while w is not None:
                if w is self.frame:
                    return
                w = getattr(w, "master", None)
        except Exception:
            pass
        self.close()

    def apply_tokens(self):
        t = _STUDIO["tok"] or _studio_resolve("original")
        bg = t["raised"] if t["dark"] else t["card"]
        self._bg = bg
        try:
            self.frame.configure(bg=bg, highlightbackground=mix(t["line"], t["hi"], 0.12), highlightcolor=t["line"])
            for w in (self.top, self.list):
                w.configure(bg=bg)
            self.icon.configure(bg=bg)
            self.icon.delete("all")
            _draw_icon(self.icon, "search", int(11 * self.nav._s), int(11 * self.nav._s), 17 * self.nav._s, t["muted"], bg, w=1.6 * self.nav._s)
            self.entry.configure(bg=bg, fg=t["hi"], insertbackground=t["accent"], font=_sf("ui", 13),
                                 selectbackground=t["sel"], selectforeground=t["hi"])
            self.esc.configure(bg=mix(bg, t["hi"], 0.08), fg=t["muted"], font=_sf("mono", 8))
            self.rule.configure(bg=t["line"])
            self.rule2.configure(bg=t["line"])
            self.foot.configure(bg=mix(bg, "#000000", 0.12 if t["dark"] else 0.03), fg=t["faint"], font=_sf("ui", 8))
            self.empty.configure(bg=bg, fg=t["faint"], font=_sf("ui", 10))
            self._paint_rows()
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _items(self):
        out = []
        for f, label in self.nav._pages:
            grp = self.nav.GROUP_TITLES.get(self.nav.group_of(label), "")
            out.append(("Page", label, grp, (lambda fr=f: self.nav.select(fr)), label + " " + grp))
        try:
            for title, sub, fn in self.app._palette_actions():
                out.append(("Action", title, sub, fn, title + " " + sub))
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        return out

    @staticmethod
    def _score(q, hay, title):
        h = hay.lower()
        tl = title.lower()
        if not q:
            return 1
        if tl.startswith(q):
            return 100 - len(tl) * 0.1
        if q in tl:
            return 80 - tl.index(q)
        if q in h:
            return 60
        words = [w for w in q.split() if w]
        if words and all(w in h for w in words):
            return 50
        i = 0
        for ch in h:
            if i < len(q) and ch == q[i]:
                i += 1
        return 20 if i == len(q) else 0

    def refresh(self):
        raw = self.var.get().strip()
        q = raw.lower()
        res = []
        pfx = getattr(self.app, "command_prefix", "!") or "!"
        if raw.startswith("!") or (pfx != "!" and raw.startswith(pfx)):
            cmd = raw
            res.append(("Run", raw, "Send to the VM as owner", (lambda c=cmd: self.app._palette_run(c)), 1000))
        scored = []
        for kind, title, sub, fn, hay in self._items():
            sc = self._score(q.lstrip("!"), hay, title) if not res else 0
            if sc > 0:
                scored.append((kind, title, sub, fn, sc + (5 if kind == "Page" else 0)))
        scored.sort(key=lambda r: -r[4])
        res.extend(scored)
        self._results = res[:self.MAX_ROWS]
        self._sel = 0
        self._paint_rows()

    def _paint_rows(self, instant=False):
        t = _STUDIO["tok"] or _studio_resolve("original")
        bg = getattr(self, "_bg", t["raised"])
        selbg = mix(bg, t["accent"], 0.16)
        for i, (row, kind, title, sub) in enumerate(self._rows):
            if i < len(self._results):
                k, ti, su, _fn, _sc = self._results[i]
                on = i == self._sel
                rb = selbg if on else bg
                kc = {"Page": t["info"], "Action": t["accent_text"], "Run": t["ok"]}.get(k, t["muted"])
                try:
                    kind.configure(text=k.upper(), fg=kc, font=_sf("ui", 7, "semi"))
                    title.configure(text=ti if len(ti) < 70 else ti[:67] + "...", fg=t["hi"], font=_sf("ui", 11, "semi" if on else "normal"))
                    sub.configure(text=su, fg=t["muted"] if on else t["faint"], font=_sf("ui", 9))
                    def paint(c, ws=(row, kind, title, sub)):
                        for w in ws:
                            w.configure(bg=c)
                    if instant or not MOTION.on or getattr(row, "_mo_bg", None) is None:
                        MOTION.cancel(("palrow", i))
                        MOTION.col[("palrow", i)] = rb
                        paint(rb)
                    else:
                        MOTION.color(("palrow", i), 120 if on else 200, paint, rb)
                    row._mo_bg = rb
                    if not row.winfo_manager():
                        row.pack(fill="x", padx=6)
                except Exception:
                    pass
            else:
                try: row.pack_forget()
                except Exception: pass
        try:
            if not self._results:
                self.empty.pack(fill="x")
            else:
                self.empty.pack_forget()
        except Exception:
            pass

    def _hover(self, i):
        if i < len(self._results) and i != self._sel:
            self._sel = i
            self._paint_rows()

    def _click(self, i):
        if i < len(self._results):
            self._sel = i
            self._run()

    def _move(self, d):
        if self._results:
            self._sel = (self._sel + d) % len(self._results)
            self._paint_rows()
        return "break"

    def _run(self):
        if not self._results:
            return "break"
        k, title, _sub, fn, _sc = self._results[self._sel]
        self.close()
        plog("PALETTE", f"{k.lower()}: {title}")
        try:
            fn()
        except Exception as e:
            log_crash(f"palette {title}", e)
        return "break"

    def open(self, from_click=False):
        self._skip_click = bool(from_click)
        if self.is_open:
            self.entry.select_range(0, "end")
            self.entry.focus_set()
            return
        self.is_open = True
        self._opened_at = time.time()
        self.apply_tokens()
        self.var.set("")
        self.refresh()
        w = int(600 * self.nav._s)
        y1 = int(92 * self.nav._s)
        MOTION.cancel("palette")
        for r in self._rows:
            r[0]._mo_bg = None
        self._paint_rows(instant=True)
        try:
            self.frame.place(in_=self.nav, relx=0.5, y=(y1 - 16 if MOTION.on else y1), anchor="n", width=w)
            self.frame.lift()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if MOTION.on:
            def step(v, y1=y1, w=w):
                self.frame.place_configure(y=int(round(y1 - 16 * (1.0 - v))), width=int(w * (0.96 + 0.04 * min(1.0, v))))
            MOTION.tween("palette", 260, step, 1.0, a=0.0, ease=_ease_out_back)
            t = _STUDIO["tok"] or _studio_resolve("original")
            for i, (row, kind, title, sub) in enumerate(self._rows):
                if i >= len(self._results):
                    break
                try:
                    _bg0 = getattr(self, "_bg", t["raised"])
                    title.configure(fg=_bg0)
                    sub.configure(fg=_bg0)
                except Exception:
                    pass
                def fade(v, title=title, sub=sub, i=i):
                    tt = _STUDIO["tok"] or t
                    bg = getattr(self, "_bg", tt["raised"])
                    vv = max(0.0, min(1.0, v))
                    title.configure(fg=mix(bg, tt["hi"], vv))
                    sub.configure(fg=mix(bg, tt["muted"] if i == self._sel else tt["faint"], vv))
                MOTION.tween(("palfade", i), 220, fade, 1.0, a=0.0, delay=40 + i * 22)
        self.entry.focus_set()

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        try:
            if self.nav.focus_get() is self.entry:
                self.nav.winfo_toplevel().focus_set()
        except Exception:
            pass
        for i in range(self.MAX_ROWS):
            MOTION.cancel(("palfade", i))
        if MOTION.on and self.frame.winfo_manager():
            y1 = int(92 * self.nav._s)
            def step(v, y1=y1):
                self.frame.place_configure(y=int(round(y1 - 12 * v)))
            def gone():
                if not self.is_open:
                    try: self.frame.place_forget()
                    except Exception: pass
            MOTION.tween("palette", 130, step, 1.0, a=0.0, ease=_ease_in_cubic, done=gone)
            return
        try: self.frame.place_forget()
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
    r1, g1, b1 = _hex_to_rgb(_hx(c1))
    r2, g2, b2 = _hex_to_rgb(_hx(c2))
    return _rgb_to_hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


_STUDIO = {"tok": None, "on": False, "accent_seen": set(), "delta": 0, "gen": 0}

_STUDIO_BASE = {
    "original": dict(name="Studio", desc="Graphite desk, amber tally accents. The default.", dark=True,
                     bg="#111418", side="#0D1014", panel="#13171C", card="#181D23", raised="#222930",
                     line="#29313B", input="#0C0F12", hi="#F2F4F7", text="#D3D8DF", muted="#8C95A3",
                     faint="#5E6673", ok="#3DBE7E", bad="#E5484D", warn="#E9A23B", violet="#A08CF2",
                     info="#5AA9E6", accent="#F2A53A"),
    "light": dict(name="Studio light", desc="The same desk in daylight.", dark=False,
                  bg="#F1F2F4", side="#E7E9ED", panel="#FAFAFB", card="#FFFFFF", raised="#E8EBEF",
                  line="#D4D9E0", input="#FFFFFF", hi="#0E1116", text="#2B313B", muted="#5E6673",
                  faint="#8D95A1", ok="#1E9A62", bad="#D3343A", warn="#B5730A", violet="#6A55D8",
                  info="#2F7FC1", accent="#E59A2F"),
    "zinc": dict(name="Zinc", desc="The previous neutral black look.", dark=True,
                 bg="#09090B", side="#0C0C11", panel="#0F0F15", card="#18181B", raised="#27272A",
                 line="#27272A", input="#09090B", hi="#FAFAFA", text="#D4D4D8", muted="#A1A1AA",
                 faint="#71717A", ok="#10B981", bad="#EF4444", warn="#F59E0B", violet="#8B5CF6",
                 info="#3B82F6", accent="#00E5FF"),
    "better": dict(name="Midnight", desc="Deep navy, softer contrast.", dark=True,
                   bg="#0B0D14", side="#0D1018", panel="#11141D", card="#151823", raised="#1F2433",
                   line="#232838", input="#090B11", hi="#F3F5FA", text="#E0E4EE", muted="#8D93A6",
                   faint="#5C6275", ok="#34C38F", bad="#F0606A", warn="#F2B33D", violet="#9B8CFF",
                   info="#5B9DFF", accent="#7AA2FF"),
    "god": dict(name="Violet", desc="Dark plum with a violet accent.", dark=True,
                bg="#0C0914", side="#0B0818", panel="#120E20", card="#171127", raised="#231B38",
                line="#2B2145", input="#0A0712", hi="#F6F2FF", text="#E4DDF7", muted="#9A8FB8",
                faint="#655B82", ok="#3CC98E", bad="#F0607A", warn="#F0B04A", violet="#B79CFF",
                info="#7FA8FF", accent="#B79CFF"),
    "glass": dict(name="Glass", desc="Cool blue steel.", dark=True,
                  bg="#0A0E16", side="#0A0F1A", panel="#111827", card="#141A28", raised="#1E2638",
                  line="#2A3550", input="#080C14", hi="#F2F6FF", text="#DCE4F5", muted="#8FA0BF",
                  faint="#5A6884", ok="#3CC79A", bad="#F2646E", warn="#F2B34A", violet="#A38CFF",
                  info="#38BDF8", accent="#38BDF8"),
    "aurora": dict(name="Aurora", desc="Ink with a green signal accent.", dark=True,
                   bg="#0A0D10", side="#080B0E", panel="#0F1418", card="#131A1F", raised="#1C252C",
                   line="#26323A", input="#080B0D", hi="#EEF6F3", text="#D2E0DB", muted="#86A098",
                   faint="#566962", ok="#3DD68C", bad="#F0646C", warn="#E8B04A", violet="#A08CF2",
                   info="#5AB8E6", accent="#3DD6A4"),
    "daylight": dict(name="Daylight", desc="Bright paper with a blue accent.", dark=False,
                     bg="#EDEFF5", side="#F7F8FC", panel="#FFFFFF", card="#FBFCFE", raised="#E6E9F0",
                     line="#D5DAE5", input="#FFFFFF", hi="#0A0D12", text="#20252E", muted="#565C6B",
                     faint="#8A91A0", ok="#17935B", bad="#CF3036", warn="#A86A08", violet="#6B54D6",
                     info="#1F6FC2", accent="#2F7FD8"),
}
_STUDIO_ORDER = ("original", "light", "zinc", "better", "god", "glass", "aurora", "daylight")

_ACRONYMS = {"OBS", "VM", "VMS", "VNC", "IP", "URL", "PC", "UI", "COM", "API", "HID", "OS", "CPU", "YT", "ID",
             "LAN", "USB", "SDR", "HTML", "JSON", "CLI", "GPU", "RAM", "AI", "TOS", "FAQ", "DNS", "TCP", "HTTP",
             "IRL", "SSH", "QR", "RGB", "UK", "US", "DPI", "CSV", "PID", "MS", "XP", "UAC", "BIOS", "SMP"}
_SPECIAL_WORDS = {"VIRTUALBOX": "VirtualBox", "VMWARE": "VMware", "YOUTUBE": "YouTube", "VBOXMANAGE": "VBoxManage",
                  "TIGHTVNC": "TightVNC", "PICO": "Pico", "WINDOWS": "Windows", "LINUX": "Linux",
                  "TWITCH": "Twitch", "CUSTOMTKINTER": "CustomTkinter", "TTKBOOTSTRAP": "ttkbootstrap",
                  "VMRUN": "vmrun", "WEBSOCKET": "WebSocket", "PYTCHAT": "pytchat", "IRONCONTROL": "IRONCONTROL",
                  "YT2VM": "YT2VM"}
_CAPS_RE = re.compile(r"^[A-Z0-9 &/\-'()+.!?,]+$")


def _hx(c):
    c = str(c or "").strip().lower()
    if c in ("white",): return "#ffffff"
    if c in ("black",): return "#000000"
    if len(c) == 4 and c.startswith("#"):
        return "#" + "".join(ch * 2 for ch in c[1:])
    return c


def _lum(c):
    r, g, b = _hex_to_rgb(_hx(c))
    def ch(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _sentence_case(text):
    try:
        words = str(text).split(" ")
        out, first = [], True
        for w in words:
            if not w:
                out.append(w)
                continue
            core = re.sub(r"[^A-Za-z0-9]", "", w).upper()
            if core in _SPECIAL_WORDS:
                out.append(w.upper().replace(core, _SPECIAL_WORDS[core]))
            elif core in _ACRONYMS:
                out.append(w.upper())
            else:
                lw = w.lower()
                if first:
                    i = next((k for k, ch in enumerate(lw) if ch.isalpha()), None)
                    if i is not None:
                        lw = lw[:i] + lw[i].upper() + lw[i + 1:]
                out.append(lw)
            if core:
                first = False
        return " ".join(out)
    except Exception:
        return text


def _is_caps_label(t):
    t = str(t or "").strip()
    if len(t) < 3 or t.endswith("...") or "\n" in t:
        return False
    if not _CAPS_RE.match(t) or sum(ch.isalpha() for ch in t) < 3:
        return False
    if t.replace(" ", "") in _ACRONYMS or t in _SPECIAL_WORDS:
        return False
    return t.upper() == t


def _studio_resolve(name, accent=None):
    base = dict(_STUDIO_BASE.get(name) or _STUDIO_BASE["original"])
    if accent:
        base["accent"] = accent
    dark = base["dark"]
    acc = base["accent"]
    base["accent_hover"] = mix(acc, "#ffffff", 0.14) if dark else mix(acc, "#000000", 0.10)
    base["on_accent"] = "#16120B" if _lum(acc) > 0.36 else "#FFFFFF"
    base["accent_text"] = acc if dark or _lum(acc) < 0.3 else mix(acc, "#000000", 0.32)
    base["sel"] = mix(base["card"], acc, 0.38 if dark else 0.28)
    for role in ("ok", "bad", "warn", "violet", "info", "accent"):
        base[role + "_tint"] = mix(base["card"], base[role], 0.18 if dark else 0.12)
        base[role + "_edge"] = mix(base["card"], base[role], 0.42 if dark else 0.38)
        base[role + "_soft"] = mix(base[role], base["hi"], 0.30) if dark else mix(base[role], "#000000", 0.18)
    base["raised_hover"] = mix(base["raised"], base["hi"], 0.07)
    base["rail"] = mix(base["side"], "#000000", 0.30) if dark else mix(base["side"], "#000000", 0.04)
    base["border"] = base["line"]
    base["key"] = name if name in _STUDIO_BASE else "original"
    return base


_BG_ROLES = {
    "#09090b": "bg", "#0a0a0f": "bg", "#000000": "bg", "#0b0b10": "bg",
    "#08080c": "input", "#0f0f13": "panel", "#131318": "panel", "#0c0c11": "side", "#0f0f15": "panel",
    "#18181b": "card", "#15151c": "card", "#1a1a24": "card", "#171b29": "card", "#1b1b26": "card",
    "#1c1c24": "raised", "#27272a": "line", "#3f3f46": "raised", "#52525b": "raised", "#26262e": "raised",
    "#10b981": "ok", "#059669": "ok", "#22c55e": "ok", "#ef4444": "bad", "#dc2626": "bad",
    "#f59e0b": "warn", "#fbbf24": "warn", "#8b5cf6": "violet", "#7c3aed": "violet", "#a78bfa": "violet",
    "#3b82f6": "info", "#2563eb": "info", "#00e5ff": "accent", "#00b3cc": "accent",
    "#ec4899": "violet", "#14b8a6": "ok", "#b026ff": "violet",
}
_FG_ROLES = {
    "#ffffff": "hi", "#f4f4f5": "hi", "#fafafa": "hi", "#e4e4ec": "hi", "#f2eeff": "hi", "#e4e4e7": "hi",
    "#d4d4d8": "text", "#b8b8c4": "text", "#e6e9f2": "text", "#cbd5e1": "text",
    "#a1a1aa": "muted", "#8a8a96": "muted", "#9a9aa6": "muted", "#8fa0bf": "muted", "#94a3b8": "muted",
    "#71717a": "faint", "#52525b": "faint", "#4b4b57": "faint", "#6b6b78": "faint", "#3f3f46": "faint",
    "#10b981": "ok", "#059669": "ok", "#22c55e": "ok", "#34d399": "ok", "#14b8a6": "ok",
    "#ef4444": "bad", "#dc2626": "bad", "#f87171": "bad",
    "#f59e0b": "warn", "#fbbf24": "warn", "#f97316": "warn",
    "#8b5cf6": "violet", "#a78bfa": "violet", "#7c3aed": "violet", "#b026ff": "violet", "#c084fc": "violet", "#ec4899": "violet",
    "#3b82f6": "info", "#2563eb": "info", "#38bdf8": "info", "#0ea5e9": "info", "#60a5fa": "info",
    "#00e5ff": "accent", "#00b3cc": "accent", "#000000": "on_accent",
}
_SATURATED = ("ok", "bad", "warn", "violet", "info", "accent")


def _studio_fg_role(val):
    v = _hx(val)
    if not v:
        return None
    if v in _STUDIO["accent_seen"]:
        return "accent"
    return _FG_ROLES.get(v)


def _studio_bg_role(val, cls=""):
    v = _hx(val)
    if not v:
        return None
    if v in ("systembuttonface", "#d9d9d9", "#f0f0f0", "systemwindow", "#ececec", "systemwindowbody"):
        return "parent"
    if v in _STUDIO["accent_seen"]:
        role = "accent"
    else:
        role = _BG_ROLES.get(v)
    if role is None:
        return None
    if cls != "Frame" and role == "line":
        role = "raised"
    if cls not in ("Button",) and role in _SATURATED:
        role = role + "_tint"
    return role


def _studio_color(role, fallback=None):
    tok = _STUDIO["tok"]
    if not tok or not role:
        return fallback
    if role == "accent":
        return tok["accent_text"]
    return tok.get(role, fallback)


def _studio_variant(val):
    v = _hx(val)
    tok = _STUDIO["tok"]
    if tok and v == _hx(tok["accent"]):
        return "primary"
    if v in ("#00e5ff", "#00b3cc"):
        return "soft"
    if v in _STUDIO["accent_seen"]:
        return "primary"
    role = _BG_ROLES.get(v)
    if role == "ok": return "go"
    if role == "bad": return "danger"
    if role == "warn": return "warn"
    return "neutral"


def _studio_button_colors(variant):
    tok = _STUDIO["tok"]
    if not tok:
        return None
    if variant == "primary":
        return dict(bg=tok["accent"], fg=tok["on_accent"], border=tok["accent"], hover=tok["accent_hover"])
    sem = {"go": "ok", "danger": "bad", "warn": "warn", "soft": "accent"}.get(variant)
    if sem:
        return dict(bg=tok[sem + "_tint"], fg=tok[sem + "_soft"], border=tok[sem + "_edge"],
                    hover=mix(tok[sem + "_tint"], tok[sem], 0.16))
    return dict(bg=tok["raised"], fg=tok["text"], border=tok["line"], hover=tok["raised_hover"])


_SF = {"ui": "Segoe UI", "ui_semi": None, "display": None, "display_bold": True, "mono": "Consolas", "picked": False}


def _studio_pick_fonts(root):
    if _SF["picked"]:
        return
    try:
        fams = {f.lower(): f for f in tkfont.families(root)}
    except Exception:
        fams = {}
    def first(*names):
        for n in names:
            if n.lower() in fams:
                return fams[n.lower()]
        return None
    _SF["ui"] = first("Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", "Helvetica", "Arial") or "TkDefaultFont"
    _SF["ui_semi"] = first("Segoe UI Semibold")
    d = first("Bahnschrift SemiBold")
    if d:
        _SF["display"], _SF["display_bold"] = d, False
    else:
        d = first("Bahnschrift")
        _SF["display"], _SF["display_bold"] = (d or _SF["ui"]), True
    _SF["mono"] = first("Cascadia Mono", "Cascadia Code", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Courier New") or "TkFixedFont"
    _SF["picked"] = True
    plog("UI", f"fonts: ui={_SF['ui']} semibold={_SF['ui_semi'] or '(bold)'} display={_SF['display']} mono={_SF['mono']}")


def _sf(kind="ui", size=10, weight="normal"):
    size = max(7, int(size) + int(_STUDIO.get("delta", 0)))
    if kind == "display":
        fam = _SF["display"] or _SF["ui"]
        return (fam, size, "bold") if _SF["display_bold"] else (fam, size)
    if kind == "mono":
        return (_SF["mono"], size, "bold") if weight == "bold" else (_SF["mono"], size)
    if weight == "semi" and _SF["ui_semi"]:
        return (_SF["ui_semi"], size)
    if weight in ("semi", "bold"):
        return (_SF["ui"], size, "bold")
    return (_SF["ui"], size)


def _win_dpi_aware():
    if platform.system() != "Windows" or "--no-dpi" in sys.argv:
        return "skipped"
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return "per-monitor aware"
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return "system aware"
        except Exception as e:
            return f"failed: {e}"


def _win_titlebar(root, dark):
    if platform.system() != "Windows":
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        val = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except Exception as e:
        plog("UI", f"could not set title bar color: {e}")


class _StudioScrollbar(ttk.Scrollbar):
    _DROP = ("bg", "background", "troughcolor", "activebackground", "highlightthickness", "highlightbackground",
             "highlightcolor", "bd", "borderwidth", "relief", "width", "elementborderwidth", "jump",
             "repeatdelay", "repeatinterval", "activerelief")

    def __init__(self, master=None, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
        for k in self._DROP:
            kw.pop(k, None)
        super().__init__(master, **kw)

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, str):
            return "" if cnf in self._DROP else super().configure(cnf)
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
        for k in self._DROP:
            kw.pop(k, None)
        if not kw:
            return None
        return super().configure(**kw)

    config = configure

    def __setitem__(self, key, value):
        if key in self._DROP:
            return
        super().__setitem__(key, value)

    def cget(self, key):
        if key in self._DROP:
            return ""
        return super().cget(key)

    def set(self, first, last):
        super().set(first, last)
        st = getattr(self, "_st_styles", None)
        if st:
            try:
                idle = float(first) <= 0.0 and float(last) >= 1.0
                want = st[1] if idle else st[0]
                if getattr(self, "_st_cur", None) != want:
                    self._st_cur = want
                    ttk.Scrollbar.configure(self, style=want)
            except Exception:
                pass


_TkLabelBase = tk.Label


class _StudioLabel(_TkLabelBase):
    def configure(self, cnf=None, **kw):
        if _STUDIO["on"] and _STUDIO["tok"] and kw:
            for k in ("fg", "foreground"):
                if k in kw:
                    r = _studio_fg_role(kw[k])
                    if r == "on_accent":
                        r = "hi"
                    if r:
                        kw[k] = _studio_color(r, kw[k])
            for k in ("bg", "background"):
                if k in kw:
                    r = _studio_bg_role(kw[k], "Label")
                    if r:
                        kw[k] = _studio_color(r, kw[k])
        return _TkLabelBase.configure(self, cnf, **kw)

    config = configure


tk.Label = _StudioLabel
tk.Scrollbar = _StudioScrollbar
try:
    scrolledtext.Scrollbar = _StudioScrollbar
except Exception:
    pass

def draw_glass(cv, x1, y1, x2, y2, radius, top, bottom, border=None, sheen=True, tag="glass"):
    w, h = int(x2 - x1), int(y2 - y1)
    if w <= 2 or h <= 2:
        return
    r = max(0, min(int(radius), h // 2, w // 2))
    steps = max(1, h)
    for i in range(steps):
        y = y1 + i
        t = i / max(1, steps - 1)
        col = mix(top, bottom, t)

        inset = 0
        if i < r:
            dy = r - i
            inset = r - int((max(0.0, r * r - dy * dy)) ** 0.5)
        elif i > h - r - 1:
            dy = i - (h - r - 1)
            inset = r - int((max(0.0, r * r - dy * dy)) ** 0.5)
        cv.create_line(x1 + inset, y, x2 - inset, y, fill=col, tags=tag)
    if sheen:

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
        r = max(0, min(int(self._radius), 10, h // 2, w // 2))
        x1, y1, x2, y2 = 0, 0, w - 1, h - 1
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, splinesteps=16, fill=self._tint, outline=self._border, tags="glass")
        pad = max(8, r)
        self.body.configure(bg=self._tint)
        self.coords(self._win, pad, pad)
        self.itemconfig(self._win, width=max(1, w - pad * 2), height=max(1, h - pad * 2))
        self.tag_lower("glass")

    def set_tint(self, tint, border=None):
        self._tint = tint
        self._border = border or mix(tint, "#ffffff", 0.12)
        self._redraw()

class RoundedButton(tk.Canvas):

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
        self._hv = 0.0
        self._pv = 0.0
        self._rip = None
        parent_bg = "#09090B"
        try:
            parent_bg = master.cget("bg")
        except Exception:
            try: parent_bg = master.cget("background")
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        try:
            f = tkfont.Font(font=font)
            tw, th = f.measure(text or ""), f.metrics("linespace")
        except Exception:
            tw, th = max(60, len(str(text)) * 8), 16
        self._auto_w = not isinstance(width, int)
        self._auto_h = not isinstance(height, int)
        self._border = None
        self._variant = None
        w = width if isinstance(width, int) else tw + 28
        h = height if isinstance(height, int) else th + 14
        super().__init__(master, width=w, height=h, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor=cursor or "")
        if _STUDIO["on"] and _STUDIO["tok"]:
            self.studio_style(parent_bg)
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
        border = self._border or base
        fg = self._fg
        hov = getattr(self, "_hover_bg", None)
        if disabled:
            try: pbg = super().cget("bg")
            except Exception: pbg = base
            base = mix(base, pbg, 0.45)
            border = mix(border, pbg, 0.45)
            fg = mix(fg, pbg, 0.5)
        else:
            hv = max(0.0, min(1.0, self._hv if MOTION.on else (1.0 if self._hovering() else 0.0)))
            pv = max(0.0, min(1.0, self._pv if MOTION.on else (1.0 if self._pressed else 0.0)))
            if hv > 0:
                base = mix(base, hov or mix(self._bg, "#ffffff", 0.10), hv)
                border = mix(border, mix(border, "#ffffff", 0.16), hv)
                if self._variant is None and self._hover_fg and hv > 0.5:
                    fg = self._hover_fg
            if pv > 0:
                base = mix(base, "#000000", 0.14 * pv)
        r = max(2, min(int(self._radius), 6))
        self._round_rect(1, 1, w - 2, h - 2, r, fill=base, outline=border)
        rip = self._rip
        if rip is not None and not disabled:
            rx, ry, rp = rip
            far = max(math.hypot(rx - cx, ry - cy) for cx in (0, w) for cy in (0, h))
            rr = 6 + far * rp
            lift = mix(base, "#FFFFFF", 0.20 * (1.0 - rp)) if _lum(base) < 0.55 else mix(base, "#000000", 0.12 * (1.0 - rp))
            pts = []
            for k in range(28):
                a = 2 * math.pi * k / 28.0
                pts.append((rx + rr * math.cos(a), ry + rr * math.sin(a)))
            poly = _clip_poly(pts, 2, 2, w - 3, h - 3)
            if len(poly) >= 3:
                self.create_polygon(*[c for pt in poly for c in pt], fill=lift, outline="")
            self._round_outline(1, 1, w - 2, h - 2, r, border)
        self.create_text(w / 2, h / 2 + (1 if self._pressed else 0), text=self._text, fill=fg,
                         font=self._font, justify="center")

    def studio_style(self, parent_bg=None, font=None):
        if parent_bg:
            try: super().configure(bg=parent_bg)
            except Exception: pass
        if self._variant is None:
            self._variant = _studio_variant(self._bg)
            if _is_caps_label(self._text):
                self._text = _sentence_case(self._text)
        cols = _studio_button_colors(self._variant)
        if cols:
            self._bg, self._fg, self._border, self._hover_bg = cols["bg"], cols["fg"], cols["border"], cols["hover"]
            self._hover_fg = cols["fg"]
        if font is not None:
            self._font = font
        self._resize_auto()
        self._draw()

    def _resize_auto(self):
        if not (self._auto_w or self._auto_h):
            return
        try:
            f = tkfont.Font(root=self, font=self._font)
            tw, th = f.measure(self._text or ""), f.metrics("linespace")
            kw = {}
            if self._auto_w: kw["width"] = tw + 26
            if self._auto_h: kw["height"] = th + 12
            super().configure(**kw)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _round_outline(self, x1, y1, x2, y2, r, color, width=1):
        r = max(0, min(r, int((y2 - y1) / 2), int((x2 - x1) / 2)))
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, splinesteps=24, fill="", outline=color, width=width)

    def _anim(self, attr, to, dur, ease=_ease_out_cubic):
        key = ("btn", str(self), attr)
        def step(v, attr=attr):
            setattr(self, attr, v)
            self._draw()
        MOTION.tween(key, dur, step, to, a=getattr(self, attr, 0.0), ease=ease)

    def _hovering(self):
        return getattr(self, "_is_hover", False)

    def _on_enter(self, _e=None):
        self._is_hover = True
        if MOTION.on and str(self._state) != "disabled":
            self._anim("_hv", 1.0, 130)
        else:
            self._hv = 1.0
            self._draw()

    def _on_leave(self, _e=None):
        self._is_hover = False
        was = self._pressed
        self._pressed = False
        if MOTION.on:
            self._anim("_hv", 0.0, 260)
            if was:
                self._anim("_pv", 0.0, 200)
        else:
            self._hv = 0.0
            self._pv = 0.0
            self._draw()

    def _on_press(self, _e=None):
        if str(self._state) == "disabled": return
        self._pressed = True
        if MOTION.on:
            self._anim("_pv", 1.0, 70)
        else:
            self._pv = 1.0
            self._draw()

    def _ripple(self, x, y):
        key = ("btn", str(self), "rip")
        def step(v, x=x, y=y):
            self._rip = (x, y, v)
            self._draw()
        def done():
            self._rip = None
            self._draw()
        MOTION.tween(key, 520, step, 1.0, a=0.0, ease=_ease_out_cubic, done=done)

    def _on_release(self, _e=None):
        if str(self._state) == "disabled": return
        was = self._pressed
        self._pressed = False
        if MOTION.on:
            self._anim("_pv", 0.0, 240)
            if was and _e is not None and MOTION.ambient:
                self._ripple(getattr(_e, "x", self.winfo_width() // 2), getattr(_e, "y", self.winfo_height() // 2))
        else:
            self._pv = 0.0
            self._draw()
        if was and callable(self._command):
            try: self._command()
            except Exception as ex:
                try: console_log("ERROR", f"button command failed: {ex}")
                except Exception as _ex:
                    _trace(_ex_where(), _ex)

    def configure(self, cnf=None, **kw):
        redraw = False
        restyle = False
        for key in ("text", "bg", "background", "fg", "foreground", "state",
                    "activebackground", "activeforeground", "font", "command"):
            if key in kw:
                val = kw.pop(key)
                if key == "text":
                    self._text = _sentence_case(val) if (self._variant is not None and _is_caps_label(val)) else val
                    if self._variant is not None: self._resize_auto()
                elif key in ("bg", "background"):
                    if self._variant is not None and _STUDIO["on"]:
                        self._variant = _studio_variant(val)
                        restyle = True
                    else:
                        self._bg = val
                elif key in ("fg", "foreground"):
                    if self._variant is None or not _STUDIO["on"]:
                        self._fg = val
                elif key == "state":
                    self._state = val
                    if str(val) == "disabled":
                        self._hv = 0.0
                        self._pv = 0.0
                        self._rip = None
                elif key == "activebackground": self._hover = val
                elif key == "activeforeground":
                    if self._variant is None: self._hover_fg = val
                elif key == "font":
                    if self._variant is None: self._font = val
                elif key == "command": self._command = val
                redraw = True
        if restyle:
            cols = _studio_button_colors(self._variant)
            if cols:
                self._bg, self._fg, self._border, self._hover_bg = cols["bg"], cols["fg"], cols["border"], cols["hover"]
                self._hover_fg = cols["fg"]
        for junk in ("bd", "relief", "cursor", "highlightthickness", "padx", "pady", "anchor"):
            kw.pop(junk, None)
        if kw:
            try: super().configure(**kw)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
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





try:
    import customtkinter as ctk
    ctk_available = True
except Exception:
    ctk = None
    ctk_available = False



try:
    import ttkbootstrap as tb
    tb_available = True
except Exception:
    tb = None
    tb_available = False

_ttm = {
    "original": "darkly", "better": "superhero", "god": "vapor",
    "glass": "darkly", "aurora": "vapor",
    "light": "flatly", "daylight": "litera",
}

def apply_bootstrap_theme(name):
    if not tb_available:
        return None
    try:
        want = _ttm.get(name, "darkly")
        try:
            style = tb.Style()
            names = [str(n) for n in style.theme_names()]
        except Exception:
            style, names = None, []

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
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    config = configure

def enable_ctk(theme_dark=True, accent="#00E5FF"):
    if not ctk_available:
        return False
    try:
        ctk.set_appearance_mode("dark" if theme_dark else "light")
        ctk.set_default_color_theme("dark-blue")
        try: ctk.set_widget_scaling(1.0)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        tk.Entry = CTkEntryCompat
        return True
    except Exception:
        return False

if platform.system() != "Darwin":
    tk.Button = RoundedButton

# ---------------------------------------------------------------------------
# plugins
# ---------------------------------------------------------------------------
# A plugin is a folder inside  plugins/  (next to yt2vm.py) holding a
# plugin.json manifest and a python entry file (plugin.py by default) that
# defines  setup(api)  and optionally  teardown(api).  See docs/plugins.md.

PLUGIN_API_VERSION = 2
PLUGIN_DIR_NAME = "plugins"
PLUGIN_SINGLE_EXTS = (".py", ".y2vp")
# The one plugin market: the YT2VM market server. The Plugin Market page installs from <server>/index.json and
# the Submit button uploads to <server>/api/submit. Empty = no market in this build.
# YT2VM_MARKET_SERVER overrides it, for testing a server before it goes live.
PLUGIN_MARKET_SERVER = "https://plugins.reallyiron.net"


def market_server_url():
    return str(os.environ.get("YT2VM_MARKET_SERVER") or PLUGIN_MARKET_SERVER or "").strip().rstrip("/")
_PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,39}$")
_PLUGIN_CMD_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_PLUGIN_EVENTS = ("ready", "chat", "command", "shutdown")
# the viewer action commands ctx.run() may queue (same list parse_command lets viewers chain)
_PLUGIN_ACTION_CMDS = ("!run", "!startvm", "!type", "!send", "!key", "!combo", "!keydown", "!keyup", "!move", "!abs",
                       "!click", "!rclick", "!mclick", "!scroll", "!drag", "!wait", "!cmd", "!roll", "!coinflip")
_PLUGIN_ALIASES = {"!c": "!combo", "!k": "!key", "!t": "!type", "!m": "!move", "!d": "!drag", "!w": "!wait",
                   "!kd": "!keydown", "!ku": "!keyup", "!lc": "!click", "!rc": "!rclick"}


def plugins_dir():
    d = os.path.join(_appdir(), PLUGIN_DIR_NAME)
    try: os.makedirs(d, exist_ok=True)
    except Exception as _ex:
        _trace(_ex_where(), _ex)
    return d


def _version_tuple(v):
    out = []
    for part in re.split(r"[.\-+_]", str(v or "0")):
        m = re.match(r"\d+", part)
        out.append(int(m.group()) if m else 0)
    while len(out) < 3: out.append(0)
    return tuple(out)


def read_plugin_manifest(folder):
    path = os.path.join(folder, "plugin.json")
    with open(path, "r", encoding="utf-8") as f:
        man = json.load(f)
    if not isinstance(man, dict):
        raise ValueError("plugin.json must be an object")
    pid = str(man.get("id", "")).strip().lower()
    if not _PLUGIN_ID_RE.match(pid):
        raise ValueError(f"bad plugin id {pid!r} (lowercase letters, digits, - and _, 2-40 chars)")
    entry = str(man.get("entry", "plugin.py"))
    if os.path.isabs(entry) or ".." in entry.replace("\\", "/").split("/"):
        raise ValueError(f"bad entry path {entry!r}")
    man["id"] = pid
    man["entry"] = entry
    man.setdefault("name", pid)
    man.setdefault("version", "0.0.0")
    man.setdefault("author", "unknown")
    man.setdefault("description", "")
    man["api"] = int(man.get("api", PLUGIN_API_VERSION) or PLUGIN_API_VERSION)
    return man


def _btn_text(c):
    t = getattr(c, "_text", None)
    if t is not None:
        return str(t)
    try:
        return str(c.cget("text"))
    except Exception:
        return ""


def _hide_widget(c):
    mgr = ""
    info = None
    try:
        mgr = c.winfo_manager()
        if mgr == "pack":
            info = c.pack_info()
            c.pack_forget()
        elif mgr == "grid":
            info = c.grid_info()
            c.grid_forget()
        elif mgr == "place":
            info = c.place_info()
            c.place_forget()
    except Exception:
        pass
    return (mgr, info)


def _show_widget(c, saved):
    mgr, info = saved
    if not info:
        return
    clean = {k: v for k, v in dict(info).items() if k != "in"}
    try:
        if mgr == "pack":
            c.pack(**clean)
        elif mgr == "grid":
            c.grid(**clean)
        elif mgr == "place":
            c.place(**clean)
    except Exception:
        pass


class PluginContext:
    """What a command handler receives. Built per command call."""

    def __init__(self, plugin, cmd, arg, user, is_mod, is_owner, source):
        self._plugin = plugin
        self.command = cmd
        self.arg = arg
        self.args = arg.split() if arg else []
        self.user = user
        self.clean_user = str(user).replace("@", "").lower().strip()
        self.is_mod = bool(is_mod)
        self.is_owner = bool(is_owner)
        self.is_admin = bool(is_mod or is_owner)
        self.source = source

    def reply(self, text):
        self._plugin.api.say(text)
        if self.source == "discord":
            app = self._plugin.manager.app
            br = getattr(app, "discord", None)
            if br is not None and br.running:
                try:
                    br.announce(f"[{self._plugin.name}] {text}")
                except Exception:
                    pass

    def run(self, chain):
        """Queue VM actions (!type, !key, !combo, ...) on behalf of the user who ran the command.
        Only viewer action commands are accepted, and the normal payload filter applies to non-admins."""
        return self._plugin.manager.run_as_user(self, chain)


class PluginAPI:
    """The object passed to setup(api). Everything a plugin registers through it is
    removed automatically when the plugin is disabled, reloaded or uninstalled."""

    def __init__(self, manager, plugin):
        self._mgr = manager
        self._plugin = plugin
        self.app = manager.app
        self.id = plugin.id
        self.manifest = plugin.manifest
        self.path = plugin.folder
        self.api_version = PLUGIN_API_VERSION
        self.app_version = version

    # -- registration ------------------------------------------------------
    def command(self, name, help="", mod_only=False, owner_only=False):
        def deco(fn):
            self._mgr._register_command(self._plugin, name, fn, help, mod_only, owner_only)
            return fn
        return deco

    def on(self, event, fn=None):
        if fn is None:
            return lambda f: (self._mgr._register_event(self._plugin, event, f), f)[1]
        self._mgr._register_event(self._plugin, event, fn)
        return fn

    def every(self, seconds, fn=None):
        if fn is None:
            return lambda f: (self._mgr._register_timer(self._plugin, seconds, f), f)[1]
        self._mgr._register_timer(self._plugin, seconds, fn)
        return fn

    def add_panel(self, build_fn, title=None):
        """build_fn(parent) is called on the UI thread to draw controls on the Plugins page."""
        self._plugin.panels.append((title or self._plugin.name, build_fn))
        self._mgr._changed()

    # -- tabs & buttons (API v2) -------------------------------------------
    def _ui_ready(self):
        return getattr(self.app, "tabview", None) is not None

    def _do_ui(self, fn):
        if self._ui_ready():
            return self.app.ui(fn)
        self._mgr._defer(self._plugin, fn)
        return None

    def add_tab(self, title, build_fn=None, group="TOOLS"):
        """Add a new sidebar tab. build_fn(frame) draws its contents. Removed automatically on unload."""
        title = str(title).strip() or self._plugin.name
        def _mk():
            nav = getattr(self.app, "tabview", None)
            if nav is None:
                return None
            frame = ttk.Frame(nav, style="TFrame")
            if build_fn:
                try:
                    build_fn(frame)
                except Exception as e:
                    log_crash(f"plugin {self.id} add_tab", e)
            nav.add(frame, text="  " + title + "  ")
            self._plugin.ui_tabs.append((title, frame))
            try:
                self.app._studio_restyle(target=frame)
            except Exception:
                pass
            return frame
        return self._do_ui(_mk)

    def remove_tab(self, title):
        """Remove a tab this plugin added, by its title."""
        want = str(title).strip()
        def _mk():
            nav = getattr(self.app, "tabview", None)
            if nav is None:
                return
            for item in list(self._plugin.ui_tabs):
                t, frame = item
                if t == want:
                    try:
                        nav.remove(frame)
                    except Exception:
                        pass
                    self._plugin.ui_tabs.remove(item)
        self._do_ui(_mk)

    def add_button(self, page, text, fn, variant="neutral"):
        """Add a button to a page (a frame from add_tab/page(), or a tab title). Removed automatically on unload."""
        def _cb():
            try:
                fn()
            except Exception as e:
                log_crash(f"plugin {self.id} button {text!r}", e)
        def _mk():
            nav = getattr(self.app, "tabview", None)
            if nav is None:
                return None
            if hasattr(page, "winfo_children"):
                target = page
            else:
                target = nav.frame_for("  " + str(page) + "  ") or nav.frame_for(str(page))
            if target is None:
                plog("PLUGIN", f"{self.id}: add_button could not find page {page!r}")
                return None
            b = self.app._st_button(target, str(text), _cb, variant, 10)
            b.pack(anchor="w", padx=16, pady=6, ipady=3, ipadx=10)
            self._plugin.ui_buttons.append(b)
            return b
        return self._do_ui(_mk)

    def hide_tab(self, title):
        """Hide a built-in (or any) tab by its title. Restored automatically on unload."""
        key = str(title).strip()
        def _mk():
            nav = getattr(self.app, "tabview", None)
            if nav is None:
                return
            nav.set_row_visible(key, False)
            if key not in self._plugin.hidden_tabs:
                self._plugin.hidden_tabs.append(key)
        self._do_ui(_mk)

    def hide_button(self, text, page=None):
        """Hide a button by its text, on one page or anywhere. Restored automatically on unload."""
        want = str(text).strip().lower()
        def _mk():
            nav = getattr(self.app, "tabview", None)
            if nav is None:
                return
            if page is None:
                frames = [f for f, _l in nav._pages]
            elif hasattr(page, "winfo_children"):
                frames = [page]
            else:
                tgt = nav.frame_for("  " + str(page) + "  ") or nav.frame_for(str(page))
                frames = [tgt] if tgt is not None else []
            found = []
            def walk(w):
                for c in w.winfo_children():
                    try:
                        if isinstance(c, (tk.Button, RoundedButton)) and _btn_text(c).strip().lower() == want:
                            found.append(c)
                    except Exception:
                        pass
                    walk(c)
            for fr in frames:
                walk(fr)
            for c in found:
                self._plugin.hidden_buttons.append((c, _hide_widget(c)))
        self._do_ui(_mk)

    def pages(self):
        """List all tab titles currently in the sidebar."""
        nav = getattr(self.app, "tabview", None)
        if nav is None:
            return []
        return [l.strip() for _f, l in nav._pages]

    def page(self, title):
        """Return the frame for a tab title (to add buttons to), or None."""
        nav = getattr(self.app, "tabview", None)
        if nav is None:
            return None
        return nav.frame_for("  " + str(title) + "  ") or nav.frame_for(str(title))

    # -- actions -----------------------------------------------------------
    def say(self, text):
        self.app.log(f"[{self._plugin.name}]", str(text), "sysmsg")

    def log(self, text):
        plog("PLUGIN", f"{self.id}: {text}")

    def toast(self, text, kind="info"):
        self.app.toast(str(text), kind)

    def flash(self, text, kind="info", dur=6):
        self.app.send_flash(str(text), kind, dur)

    def run(self, chain):
        """Run any command chain as the console (owner rights). Never pass raw viewer text here."""
        self.app._manual_cmd(str(chain))

    def ui(self, fn, *a, **k):
        self.app.ui(fn, *a, **k)

    # -- settings ----------------------------------------------------------
    def _store(self):
        allp = self.app.config.setdefault("plugin_settings", {})
        return allp.setdefault(self.id, {})

    def get(self, key, default=None):
        return self._store().get(key, default)

    def set(self, key, value):
        self._store()[key] = value
        self.app.save_settings()

    @property
    def settings(self):
        return dict(self._store())


class LoadedPlugin:
    def __init__(self, manager, folder, manifest, single_file=None):
        self.manager = manager
        self.folder = folder
        self.manifest = manifest
        self.single_file = single_file
        self.id = manifest["id"]
        self.name = manifest.get("name", self.id)
        self.module = None
        self.api = None
        self.loaded = False
        self.error = ""
        self.commands = {}
        self.events = collections.defaultdict(list)
        self.timers = []
        self.panels = []
        self.ui_tabs = []
        self.ui_buttons = []
        self.hidden_tabs = []
        self.hidden_buttons = []


class PluginManager:
    def __init__(self, app):
        self.app = app
        self.plugins = {}
        self._lock = threading.RLock()
        self._q = queue.Queue(maxsize=2000)
        self._listeners = []
        self._worker = None
        self._dropped = 0
        self._deferred_ui = []

    # -- state -------------------------------------------------------------
    def _enabled_map(self):
        return self.app.config.setdefault("plugins_enabled", {})

    def is_enabled(self, pid):
        return bool(self._enabled_map().get(pid, True))

    def set_enabled(self, pid, on):
        self._enabled_map()[pid] = bool(on)
        self.app.save_settings()
        if on: self.load(pid)
        else: self.unload(pid)

    def add_listener(self, fn):
        self._listeners.append(fn)

    def _changed(self):
        for fn in list(self._listeners):
            try: self.app.ui(fn)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def command_names(self):
        with self._lock:
            return {c for p in self.plugins.values() if p.loaded for c in p.commands}

    def help_lines(self):
        pre = (self.app.command_prefix or "!")
        out = []
        with self._lock:
            for p in sorted(self.plugins.values(), key=lambda x: x.name.lower()):
                if not p.loaded:
                    continue
                for n, s in sorted(p.commands.items()):
                    tag = " (owner)" if s["owner_only"] else (" (mods)" if s["mod_only"] else "")
                    desc = (s["help"] or f"from {p.name}") + tag
                    out.append((f"{pre}{n}", desc))
        return out

    def _defer(self, plugin, fn):
        self._deferred_ui.append((plugin, fn))

    def apply_deferred_ui(self):
        pending, self._deferred_ui = self._deferred_ui, []
        for plugin, fn in pending:
            if not plugin.loaded:
                continue
            try:
                self.app.ui(fn)
            except Exception as e:
                log_crash(f"plugin {plugin.id} deferred ui", e)

    def _revert_ui(self, p):
        app = self.app
        tabs = list(p.ui_tabs)
        buttons = list(p.ui_buttons)
        hidden_tabs = list(p.hidden_tabs)
        hidden_buttons = list(p.hidden_buttons)
        p.ui_tabs = []
        p.ui_buttons = []
        p.hidden_tabs = []
        p.hidden_buttons = []
        self._deferred_ui = [(pl, fn) for (pl, fn) in self._deferred_ui if pl is not p]
        def _go():
            nav = getattr(app, "tabview", None)
            for _t, frame in tabs:
                if nav is not None:
                    try:
                        nav.remove(frame)
                    except Exception:
                        pass
            for b in buttons:
                try:
                    b.destroy()
                except Exception:
                    pass
            if nav is not None:
                for key in hidden_tabs:
                    try:
                        nav.set_row_visible(key, True)
                    except Exception:
                        pass
            for c, saved in hidden_buttons:
                _show_widget(c, saved)
        app.ui(_go)

    def all_commands(self):
        with self._lock:
            return [(p, n, c) for p in self.plugins.values() if p.loaded for n, c in sorted(p.commands.items())]

    # -- discovery / loading ----------------------------------------------
    def discover(self):
        root = plugins_dir()
        found = {}
        for name in sorted(os.listdir(root)):
            full = os.path.join(root, name)
            if name.startswith((".", "_")):
                continue
            if os.path.isdir(full):
                if not os.path.isfile(os.path.join(full, "plugin.json")):
                    continue
                try:
                    man = read_plugin_manifest(full)
                except Exception as e:
                    plog("PLUGIN", f"skipping {name}: {e}")
                    continue
                if man["id"] in found:
                    plog("PLUGIN", f"duplicate plugin id {man['id']} in {name} - skipped")
                    continue
                found[man["id"]] = (full, man, None)
            elif os.path.isfile(full) and os.path.splitext(name)[1].lower() in PLUGIN_SINGLE_EXTS:
                pid = os.path.splitext(name)[0].strip().lower()
                if not _PLUGIN_ID_RE.match(pid):
                    plog("PLUGIN", f"skipping {name}: bad plugin id {pid!r}")
                    continue
                if pid in found:
                    plog("PLUGIN", f"duplicate plugin id {pid} ({name}) - skipped")
                    continue
                man = {"id": pid, "name": pid, "version": "0.0.0", "author": "unknown",
                       "description": "", "api": PLUGIN_API_VERSION, "entry": name, "single_file": True}
                found[pid] = (root, man, full)
        with self._lock:
            for pid in list(self.plugins):
                if pid not in found:
                    self.unload(pid)
                    self.plugins.pop(pid, None)
            for pid, (folder, man, single) in found.items():
                cur = self.plugins.get(pid)
                if cur is None or cur.folder != folder or cur.single_file != single or not cur.loaded:
                    if cur is not None: self.unload(pid)
                    self.plugins[pid] = LoadedPlugin(self, folder, man, single_file=single)
                else:
                    cur.manifest = man
        return found

    def load_all(self):
        self._start_worker()
        self.discover()
        for pid in list(self.plugins):
            if self.is_enabled(pid):
                self.load(pid)
        n = sum(1 for p in self.plugins.values() if p.loaded)
        plog("PLUGIN", f"{n}/{len(self.plugins)} plugin(s) loaded from {plugins_dir()}")
        self._changed()

    def load(self, pid):
        import importlib.util, importlib.machinery
        with self._lock:
            p = self.plugins.get(pid)
            if p is None:
                self.discover()
                p = self.plugins.get(pid)
            if p is None:
                return False
            if p.loaded:
                return True
            if p.single_file:
                entry = p.single_file
            else:
                try:
                    p.manifest = read_plugin_manifest(p.folder)
                    p.name = p.manifest.get("name", pid)
                except Exception as e:
                    p.error = f"manifest: {e}"
                    self._changed()
                    return False
                entry = os.path.join(p.folder, p.manifest["entry"])
            if p.manifest["api"] > PLUGIN_API_VERSION:
                p.error = f"needs plugin API {p.manifest['api']} (this app has {PLUGIN_API_VERSION}) - update YT2VM"
                self._changed()
                return False
            p.commands.clear(); p.events.clear(); p.timers.clear(); p.panels.clear()
            p.ui_tabs = []; p.ui_buttons = []; p.hidden_tabs = []; p.hidden_buttons = []
            p.error = ""
            p.api = PluginAPI(self, p)
            try:
                modname = f"yt2vm_plugin_{pid.replace('-', '_')}"
                loader = importlib.machinery.SourceFileLoader(modname, entry)
                spec = importlib.util.spec_from_loader(modname, loader)
                mod = importlib.util.module_from_spec(spec)
                loader.exec_module(mod)
                p.module = mod
                for attr, key in (("PLUGIN_NAME", "name"), ("PLUGIN_VERSION", "version"),
                                  ("PLUGIN_AUTHOR", "author"), ("PLUGIN_DESCRIPTION", "description")):
                    if hasattr(mod, attr):
                        p.manifest[key] = str(getattr(mod, attr))
                p.name = p.manifest.get("name", pid)
                if not hasattr(mod, "setup"):
                    raise AttributeError("plugin has no setup(api) function")
                mod.setup(p.api)
                p.loaded = True
                plog("PLUGIN", f"loaded {pid} {p.manifest.get('version')} ({len(p.commands)} command(s))")
            except Exception as e:
                p.error = f"{type(e).__name__}: {e}"
                p.loaded = False
                p.commands.clear(); p.events.clear(); p.timers.clear(); p.panels.clear()
                log_crash(f"plugin {pid} setup", e)
                console_log("ERROR", f"plugin {pid} failed to load: {e}")
        self._changed()
        if p.loaded and getattr(self.app, "_plugins_ready", False):
            self._dispatch_one(p, "ready", ())
        return p.loaded

    def unload(self, pid):
        with self._lock:
            p = self.plugins.get(pid)
            if p is None or not p.loaded:
                return
            mod = p.module
            p.loaded = False
            try:
                if mod is not None and hasattr(mod, "teardown"):
                    mod.teardown(p.api)
            except Exception as e:
                log_crash(f"plugin {pid} teardown", e)
            try:
                self._revert_ui(p)
            except Exception as e:
                log_crash(f"plugin {pid} ui revert", e)
            p.commands.clear(); p.events.clear(); p.timers.clear(); p.panels.clear()
            p.module = None
            plog("PLUGIN", f"unloaded {pid}")
        self._changed()

    def reload(self, pid):
        self.unload(pid)
        self.discover()
        return self.load(pid) if self.is_enabled(pid) else False

    def reload_all(self):
        for pid in list(self.plugins):
            self.unload(pid)
        self.load_all()

    def shutdown(self):
        self.emit("shutdown")
        for pid in list(self.plugins):
            try: self.unload(pid)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    # -- registration (called through PluginAPI) ---------------------------
    def _register_command(self, p, name, fn, help, mod_only, owner_only):
        name = str(name).lower().lstrip("!")
        if not _PLUGIN_CMD_RE.match(name):
            raise ValueError(f"bad command name {name!r}")
        if name in _KNOWN_CMDS or name in ("plugins", "plugin"):
            raise ValueError(f"!{name} is a built-in command")
        for other in self.plugins.values():
            if other is not p and other.loaded and name in other.commands:
                raise ValueError(f"!{name} is already registered by plugin {other.id}")
        p.commands[name] = {"fn": fn, "help": str(help or ""), "mod_only": bool(mod_only or owner_only),
                            "owner_only": bool(owner_only)}

    def _register_event(self, p, event, fn):
        if event not in _PLUGIN_EVENTS:
            raise ValueError(f"unknown event {event!r} (use one of {', '.join(_PLUGIN_EVENTS)})")
        p.events[event].append(fn)

    def _register_timer(self, p, seconds, fn):
        seconds = max(1.0, float(seconds))
        p.timers.append({"every": seconds, "fn": fn, "next": time.time() + seconds})

    # -- worker ------------------------------------------------------------
    def _start_worker(self):
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = _spawn("plugins", self._worker_loop)

    def _submit(self, p, fn, args, what):
        try:
            self._q.put_nowait((p, fn, args, what))
        except queue.Full:
            self._dropped += 1
            plog_throttled("plugin-q", "PLUGIN", f"plugin queue full - dropped {self._dropped} call(s)")

    def _call(self, p, fn, args, what):
        if not p.loaded:
            return
        t0 = time.time()
        try:
            fn(*args)
        except Exception as e:
            log_crash(f"plugin {p.id} {what}", e)
            console_log("ERROR", f"plugin {p.id} {what} failed: {type(e).__name__}: {e}")
        el = time.time() - t0
        if el > 2:
            plog("PLUGIN", f"{p.id} {what} took {el:.1f}s - keep plugin callbacks short or use a thread")

    def _worker_loop(self):
        while self.app.running:
            try:
                item = self._q.get(timeout=0.25)
            except queue.Empty:
                item = None
            if item is not None:
                self._call(*item)
            now = time.time()
            with self._lock:
                due = [(p, t) for p in self.plugins.values() if p.loaded for t in p.timers if now >= t["next"]]
            for p, t in due:
                t["next"] = now + t["every"]
                self._call(p, t["fn"], (), "timer")

    def _dispatch_one(self, p, event, args):
        for fn in list(p.events.get(event, ())):
            self._submit(p, fn, args, f"on({event})")

    def emit(self, event, *args):
        with self._lock:
            targets = [p for p in self.plugins.values() if p.loaded and p.events.get(event)]
        for p in targets:
            self._dispatch_one(p, event, args)

    # -- chat hooks ----------------------------------------------------------
    def handle_command(self, cmd, arg, user, is_mod, is_owner, source):
        name = cmd.lstrip("!").lower()
        with self._lock:
            hit = None
            for p in self.plugins.values():
                if p.loaded and name in p.commands:
                    hit = (p, p.commands[name]); break
        if hit is None:
            return False
        p, spec = hit
        if spec["owner_only"] and not is_owner:
            return True
        if spec["mod_only"] and not (is_mod or is_owner):
            return True
        ctx = PluginContext(p, name, arg, user, is_mod, is_owner, source)
        self._submit(p, spec["fn"], (ctx,), f"!{name}")
        return True

    def run_as_user(self, ctx, chain):
        app = self.app
        steps = app._split_chain(str(chain), trusted=True)
        out = []
        for seg, _t in steps:
            parts = seg.strip().split(maxsplit=1)
            if not parts:
                continue
            raw = parts[0].lower()
            pre = app.command_prefix or "!"
            if raw.startswith(pre):
                raw = raw[len(pre):]
            c = _PLUGIN_ALIASES.get("!" + raw, "!" + raw)
            a = parts[1].strip() if len(parts) > 1 else ""
            if c not in _PLUGIN_ACTION_CMDS:
                plog("PLUGIN", f"{ctx._plugin.id}: ctx.run skipped {c} (not a viewer action command)")
                continue
            if not ctx.is_admin:
                ok, why = app._security_gate(ctx.clean_user, c, a, chain_step=True)
                if not ok:
                    plog("PLUGIN", f"{ctx._plugin.id}: ctx.run blocked {c} ({why})")
                    continue
            out.append((c, a, ctx.user))
        if out:
            app.trigger_command_chain(out, priority=ctx.is_admin)
        return len(out)


# ---------------------------------------------------------------------------
# plugin market
# ---------------------------------------------------------------------------
# A market is a JSON index (see docs/plugin-market.md). Every file listed for a
# plugin carries a sha256; nothing is written to plugins/ unless all of them match.

_MARKET_MAX_FILE = 4 * 1024 * 1024
_MARKET_UA = f"YT2VM/{version} plugin-market"


def _market_fetch(url, limit=_MARKET_MAX_FILE, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": _MARKET_UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{url} is larger than {limit // 1024} KB")
    return data


def market_fetch_index(url):
    raw = _market_fetch(url)
    idx = json.loads(raw.decode("utf-8"))
    if not isinstance(idx, dict) or not isinstance(idx.get("plugins"), list):
        raise ValueError("index has no \"plugins\" list")
    out = []
    for e in idx["plugins"]:
        try:
            pid = str(e.get("id", "")).lower()
            if not _PLUGIN_ID_RE.match(pid):
                raise ValueError(f"bad id {pid!r}")
            files = e.get("files") or []
            if not files or not all(isinstance(f, dict) and f.get("path") and f.get("sha256") for f in files):
                raise ValueError("every file needs a path and sha256")
            ent = dict(e)
            ent["id"] = pid
            ent["_source"] = url
            ent["_base"] = urllib.parse.urljoin(url, str(e.get("base_url") or f"plugins/{pid}/"))
            out.append(ent)
        except Exception as ex:
            plog("MARKET", f"{url}: skipped entry {e.get('id', '?') if isinstance(e, dict) else '?'}: {ex}")
    return {"name": str(idx.get("name") or url), "url": url, "plugins": out}


def _market_safe_rel(path):
    p = str(path).replace("\\", "/")
    if not p or p.startswith("/") or os.path.isabs(path) or ":" in p or any(part in ("", ".", "..") for part in p.split("/")):
        raise ValueError(f"unsafe file path {path!r}")
    return p


def market_install(entry, progress=None):
    """Download every file of a market entry, verify sha256, then swap it into plugins/<id>.
    A data/ folder from an existing install is carried over."""
    pid = entry["id"]
    root = plugins_dir()
    dest = os.path.join(root, pid)
    tmp = os.path.join(root, f".{pid}.installing")
    if os.path.isdir(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        files = entry["files"]
        for i, f in enumerate(files):
            rel = _market_safe_rel(f["path"])
            url = f.get("url") or urllib.parse.urljoin(entry["_base"], urllib.parse.quote(rel))
            if progress: progress(f"downloading {rel} ({i + 1}/{len(files)})")
            data = _market_fetch(url)
            got = hashlib.sha256(data).hexdigest()
            if got.lower() != str(f["sha256"]).lower():
                raise ValueError(f"checksum mismatch for {rel} - refusing to install")
            out = os.path.join(tmp, *rel.split("/"))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(data)
        man = read_plugin_manifest(tmp)
        if man["id"] != pid:
            raise ValueError(f"plugin.json id {man['id']!r} does not match market id {pid!r}")
        if os.path.isdir(os.path.join(dest, "data")):
            shutil.move(os.path.join(dest, "data"), os.path.join(tmp, "data"))
        if os.path.isdir(dest):
            old = os.path.join(root, f".{pid}.old")
            shutil.rmtree(old, ignore_errors=True)
            os.replace(dest, old)
            shutil.rmtree(old, ignore_errors=True)
        os.replace(tmp, dest)
        with open(os.path.join(dest, ".market.json"), "w", encoding="utf-8") as fh:
            json.dump({"source": entry.get("_source"), "version": entry.get("version"), "installed": time.time()}, fh)
        return man
    finally:
        if os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)


def market_submit(server, folder, owner_key="", note=""):
    """Upload a plugin folder to the market server (POST /api/submit). Returns the server's JSON reply.
    Raises ValueError with the server's error list when the upload is refused."""
    server = str(server or "").strip().rstrip("/")
    if not server.lower().startswith(("https://", "http://")):
        raise ValueError(["this build of YT2VM has no plugin market configured"])
    read_plugin_manifest(folder)
    files, total = {}, 0
    for item in _market_plugin_files(folder):
        full = os.path.join(folder, *item["path"].split("/"))
        with open(full, "rb") as fh:
            raw = fh.read()
        try:
            files[item["path"]] = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError([f"{item['path']} is not a text file - only text files can be published"])
        total += len(raw)
    if total > 600 * 1024:
        raise ValueError(["the plugin is larger than 600 KB - host it in your own market folder instead"])
    body = json.dumps({"files": files, "owner_key": owner_key or "", "note": str(note or "")[:2000]}).encode("utf-8")
    req = urllib.request.Request(server + "/api/submit", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": _MARKET_UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read(1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            errs = json.loads(e.read(1024 * 1024).decode("utf-8")).get("errors") or [f"HTTP {e.code}"]
        except Exception:
            errs = [f"the server answered HTTP {e.code}"]
        raise ValueError(errs)
    except urllib.error.URLError as e:
        raise ValueError([f"could not reach {server}: {e.reason}"])


def market_uninstall(pid):
    if not _PLUGIN_ID_RE.match(str(pid)):
        raise ValueError(f"bad plugin id {pid!r}")
    root = os.path.abspath(plugins_dir())
    dest = os.path.join(root, pid)
    if os.path.isdir(dest) and os.path.dirname(os.path.abspath(dest)) == root:
        shutil.rmtree(dest)
        return
    for ext in PLUGIN_SINGLE_EXTS:
        f = os.path.join(root, pid + ext)
        if os.path.isfile(f):
            os.remove(f)


def _market_plugin_files(folder):
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in ("data", "__pycache__"))
        for fn in sorted(filenames):
            if fn.startswith(".") or fn.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, fn)
            with open(full, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            out.append({"path": os.path.relpath(full, folder).replace(os.sep, "/"), "sha256": digest})
    return out


_PLUGIN_TEMPLATE_PY = '''import tkinter as tk


def setup(api):
    # !{cmd} - try it from the Dashboard console, then change it into something useful
    @api.command("{cmd}", help="Starter command from the {name} plugin")
    def {cmd}(ctx):
        count = api.get("count", 0) + 1
        api.set("count", count)
        ctx.reply(f"Hi {{ctx.user}}! !{cmd} has run {{count}} time(s).")

    # runs for every chat message (YouTube and Discord)
    @api.on("chat")
    def on_chat(user, message, is_mod, is_owner, source):
        pass

    # a small panel on the Plugins page
    def panel(parent):
        tk.Label(parent, text="Edit plugin.py in this folder, then click Reload.",
                 bg=parent["bg"], fg="#8C95A3").pack(anchor="w")
    api.add_panel(panel)


def teardown(api):
    pass
'''


def plugin_scaffold(pid, name="", author=""):
    pid = str(pid).strip().lower()
    if not _PLUGIN_ID_RE.match(pid):
        raise ValueError("ids use lowercase letters, digits, - and _ (2-40 characters)")
    folder = os.path.join(plugins_dir(), pid)
    if os.path.exists(folder):
        raise ValueError(f"plugins/{pid} already exists")
    cmd = re.sub(r"[^a-z0-9_]", "_", pid)
    if not cmd[0].isalpha():
        cmd = "p" + cmd
    cmd = cmd[:32]
    if cmd in _KNOWN_CMDS or cmd in ("plugins", "plugin"):
        cmd = (cmd + "_cmd")[:32]
    name = name or pid.replace("-", " ").replace("_", " ").title()
    os.makedirs(folder)
    man = {"id": pid, "name": name, "version": "0.1.0", "author": author or "you",
           "description": "Describe what your plugin does.", "api": PLUGIN_API_VERSION, "entry": "plugin.py",
           "commands": [cmd]}
    with open(os.path.join(folder, "plugin.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(man, fh, indent=4)
        fh.write("\n")
    with open(os.path.join(folder, "plugin.py"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_PLUGIN_TEMPLATE_PY.replace("{cmd}", cmd).replace("{name}", name)
                 .replace("{{", "{").replace("}}", "}"))
    return folder, cmd


# The plugin docs, shown on the Plugin Docs page. docs/*.md are generated from
# these with  python docs/sync_docs.py  so the app and GitHub always match.
PLUGIN_DOCS = (
    ("plugins", "Plugins guide", r"""# Plugins

Plugins add things to YT2VM without editing `yt2vm.py`: new chat commands, reactions to chat messages, timers, and small settings panels in the GUI.

Everything here works with nothing but `yt2vm.py`. The app creates the `plugins` folder itself, these docs are built into the app (**Tools → Plugin Docs**), and you can create, test and publish a plugin from the GUI, with no GitHub account.

- [Installing and managing plugins](#installing-and-managing-plugins)
- [Your first plugin](#your-first-plugin)
- [plugin.json](#pluginjson)
- [API reference](#api-reference)
- [Threads and the UI](#threads-and-the-ui)
- [Releasing a plugin](#releasing-a-plugin)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

How the plugin market works is covered in the [Plugin market guide](plugin-market.md).

---

## Installing and managing plugins

Plugins live in a `plugins` folder next to `yt2vm.py`. The app creates it on first start. Each plugin is its own folder:

```
yt2vm.py
plugins/
  hello/
    plugin.json
    plugin.py
  chat-stats/
    plugin.json
    plugin.py
    data/          <- the plugin's own files (kept when you update it)
```

There are four ways to get a plugin:

1. **Plugin Market page** (Tools → Plugin Market): click **Install**.
2. **New plugin button** (Tools → Plugins): creates a working starter plugin for you to edit.
3. **By hand:** copy a plugin folder into `plugins`, then click **Reload all** on the Plugins page (or restart the app).
4. **From chat or the console** (owner only): drop the folder in, then run `!plugin reload`.

The **Plugins** page (Tools → Plugins) lists every installed plugin with its status (`Running`, `Disabled` or `Error`), the commands it adds, and these buttons:

| Button | What it does |
|---|---|
| Enable / Disable | Turns the plugin on or off. The choice is saved in `settings.json` under `plugins_enabled`. |
| Reload | Re-reads the plugin's files from disk. Use it while you're writing a plugin. |
| Open folder | Opens the plugin's folder. |
| Submit | Uploads the plugin to the plugin market for review. Only shown for plugins you made: plugins installed from the market belong to their author. See [Releasing a plugin](#releasing-a-plugin). |
| Uninstall | Deletes the plugin's folder, after you confirm. |

Plugin panels (settings, leaderboards and so on) appear inside each plugin's card.

### Owner chat commands

| Command | Effect |
|---|---|
| `!plugins` | Lists installed plugins. |
| `!plugin reload` | Reloads all plugins. |
| `!plugin reload <id>` | Reloads one plugin. |
| `!plugin enable <id>` / `!plugin disable <id>` | Turns one plugin on or off. |

The command palette (Ctrl K) also has **Open plugins**, **Open the plugin market**, **Open the plugin docs**, **Create a new plugin** and **Reload all plugins**.

---

## Your first plugin

The quickest start: on **Tools → Plugins**, click **New plugin**, type an id such as `greeter`, and the app writes a working plugin into `plugins/greeter/`, loads it, and opens its folder. Type `!greeter` in the Dashboard console to try it.

To make one by hand, create a folder `plugins/greeter/` with two files.

**plugins/greeter/plugin.json**

```json
{
    "id": "greeter",
    "name": "Greeter",
    "version": "1.0.0",
    "author": "you",
    "description": "Says hi.",
    "api": 1
}
```

**plugins/greeter/plugin.py**

```python
def setup(api):
    @api.command("hi", help="Say hi")
    def hi(ctx):
        ctx.reply(f"Hi {ctx.user}!")
```

Click **Reload all** on the Plugins page and type `!hi` in the Dashboard console. You should see `[Greeter]: Hi [console]!`.

Here is a bigger example that uses every part of the API:

```python
import tkinter as tk


def setup(api):
    # a chat command anyone can use
    @api.command("dance", help="Make the VM dance")
    def dance(ctx):
        ctx.run("!key left | !key right | !key left | !key right")
        ctx.reply(f"{ctx.user} started a dance")

    # a command only mods and owners can use
    @api.command("panic", help="Revert the VM", mod_only=True)
    def panic(ctx):
        api.run("!revert")            # runs with console rights, see "Security" below

    # react to every chat message (YouTube and Discord)
    @api.on("chat")
    def on_chat(user, message, is_mod, is_owner, source):
        if "gg" in message.lower():
            api.say(f"gg {user}")

    # run something every 5 minutes
    @api.every(300)
    def reminder():
        api.flash("Remember to follow!", "info", 6)

    # settings that persist in settings.json
    if api.get("first_run", True):
        api.log("first run!")
        api.set("first_run", False)

    # a small panel on the Plugins page
    def panel(parent):
        tk.Label(parent, text="Hello from my plugin", bg=parent["bg"], fg="#D3D8DF").pack(anchor="w")
    api.add_panel(panel, "Status")


def teardown(api):
    # optional: called on disable, reload, uninstall and app exit
    pass
```

### Single-file plugins (.py / .y2vp)

You don't need a folder or a `plugin.json` for a quick plugin. Drop a single file straight into `plugins/`:

```
plugins/
  greeter.py        <- a single-file plugin, id "greeter"
  mymacros.y2vp     <- also a plugin (.y2vp = "yt2vm plugin"), id "mymacros"
```

A `.y2vp` file is just Python with the YT2VM plugin API available (same as `.py`); the different extension only keeps your plugins easy to spot. The plugin's **id** is the file name without the extension, so it must be lowercase letters, digits, `-` and `_`. The file needs a `setup(api)` function, exactly like `plugin.py`. There is no `plugin.json`, so set these at the top of the file if you want them:

```python
PLUGIN_NAME = "My Macros"
PLUGIN_VERSION = "1.0.0"
PLUGIN_AUTHOR = "you"
PLUGIN_DESCRIPTION = "A couple of handy macros."

def setup(api):
    @api.command("np", help="open notepad")
    def np(ctx):
        ctx.run("!combo win+r | !wait 1 | !send notepad")

def teardown(api):
    pass
```

Single-file plugins get the whole API, including tabs and buttons. They can't be submitted to the market (put them in a folder with a `plugin.json` first), but everything else works the same. Click **Reload all** on the Plugins page after adding one.

The market's starter plugins are short, working examples. Install them from the Plugin Market page and click **Open folder** on the Plugins page to read them:

| Plugin | Shows how to |
|---|---|
| `hello` | register a command, store a setting, build a settings panel |
| `chat-stats` | use the `chat` event, run a timer, keep files in `data/`, use `teardown` |
| `shortcuts` | register many commands in a loop and queue VM input with `ctx.run` |
| `announcer` | build a timer-driven feature with an editable panel |

---

## plugin.json

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Unique id: lowercase letters, digits, `-` and `_`, 2–40 characters. Never change it after release, because the market uses it to match updates. |
| `name` | yes for the market | Display name. Defaults to `id`. |
| `version` | yes for the market | Version such as `1.2.0`. The market compares versions to offer updates. |
| `author` | yes for the market | Shown in the GUI. |
| `description` | yes for the market | One or two sentences, shown in the GUI. |
| `api` | no | Plugin API version the plugin needs. Defaults to `1`. Set it to `2` if you use tabs/buttons (`add_tab`, `add_button`, `hide_tab`, `hide_button`). If it is higher than the app supports, the plugin doesn't load and shows an error telling the user to update YT2VM. |
| `entry` | no | Python file to load. Defaults to `plugin.py`. Must be inside the plugin folder. |
| `tags`, `commands`, `homepage` | no | Shown on the market card. |

---

## API reference

### setup(api) and teardown(api)

`setup(api)` is required. It runs once when the plugin loads and should register everything the plugin needs. If it raises an exception, the plugin shows **Error** and nothing it registered stays active.

`teardown(api)` is optional. It runs when the plugin is disabled, reloaded or uninstalled, and when the app closes. YT2VM removes the plugin's commands, events, timers and panels automatically, so use `teardown` only for the plugin's own cleanup, such as saving files or stopping threads it started.

### Registering things

| Call | Description |
|---|---|
| `@api.command(name, help="", mod_only=False, owner_only=False)` | Adds `!name`. The handler receives a `ctx` (see below). Names are lowercase letters, digits and `_`, at most 32 characters, and can't replace a built-in command or one from another plugin. The command uses the user's configured prefix, so `!name` becomes `?name` if the prefix is `?`. |
| `@api.on(event)` | Subscribes to an event (see below). Also works as `api.on(event, fn)`. |
| `@api.every(seconds)` | Calls `fn()` every `seconds` (minimum 1). Also works as `api.every(seconds, fn)`. |
| `api.add_panel(build_fn, title=None)` | `build_fn(parent)` is called on the UI thread whenever the Plugins page redraws. Put your Tk widgets inside `parent`. Use `parent["bg"]` as the background so the panel matches the theme. |
| `api.add_tab(title, build_fn=None, group="TOOLS")` | **(API 2)** Adds a new sidebar tab. `build_fn(frame)` draws its contents (runs on the UI thread). The tab is removed automatically when the plugin unloads. Returns the tab's frame. |
| `api.add_button(page, text, fn, variant="neutral")` | **(API 2)** Adds a button to a page. `page` is a frame (from `add_tab` or `api.page(title)`) or a tab title. `fn()` runs when clicked. Removed automatically on unload. `variant` is `neutral`, `go`, `primary` or `danger`. |
| `api.hide_tab(title)` | **(API 2)** Hides any tab by its title (built-in or added). Restored automatically on unload. |
| `api.hide_button(text, page=None)` | **(API 2)** Hides buttons whose text matches, on one page (frame or title) or everywhere. Restored automatically on unload. |
| `api.remove_tab(title)` | **(API 2)** Removes a tab this plugin added. |
| `api.pages()` / `api.page(title)` | **(API 2)** List all tab titles / get one tab's frame (or `None`) so you can add buttons to it. |

Viewer commands go through the same protections as built-in ones before they reach your handler: blacklist, timed bans, cooldown, rate limit, chat pause and disabled commands. Built-in commands always take priority over plugin commands.

### Events

| Event | Handler signature | When |
|---|---|---|
| `ready` | `fn()` | After the app finishes starting, or right after loading if the app is already running. |
| `chat` | `fn(user, message, is_mod, is_owner, source)` | For every chat message. `source` is `"youtube"` or `"discord"`. |
| `command` | `fn(user, cmd, arg)` | For every command that gets past the security checks, including built-in ones and those of plugins. `cmd` includes the `!`. Commands typed in the Dashboard console, run by automations, or queued with `api.run` arrive with `user` set to `"[console]"`. Check `user.startswith("[")` to skip them, for example when you only care about viewers. |
| `shutdown` | `fn()` | When the window closes. |

### The ctx object

| Attribute / method | Description |
|---|---|
| `ctx.user` | Display name of the person who ran the command, or `"[console]"` for the Dashboard console and automations. |
| `ctx.clean_user` | Lowercase name without `@`, which is the form used for bans and stats. |
| `ctx.command` | Command name without the prefix. |
| `ctx.arg` / `ctx.args` | Everything after the command, as one string and split on spaces. |
| `ctx.is_mod`, `ctx.is_owner`, `ctx.is_admin` | Permission flags. |
| `ctx.source` | `"youtube"` or `"discord"`. Commands from the console and from automations report `"youtube"`. |
| `ctx.reply(text)` | Posts `[Plugin Name]: text` to the console and overlay chat. If the command came from Discord, it is also posted back to the Discord command channel. |
| `ctx.run(chain)` | Queues VM input **on behalf of the user**. Only viewer action commands are accepted: `!type !send !key !combo !keydown !keyup !move !abs !click !rclick !mclick !scroll !drag !wait !cmd !run !startvm !roll !coinflip` and their short aliases. For non-admins the normal payload filter applies. Returns the number of steps queued. |

### Everything else on api

| Member | Description |
|---|---|
| `api.say(text)` | Posts `[Plugin Name]: text` to the console and overlay chat. |
| `api.log(text)` | Writes to `output_log.txt` only. |
| `api.toast(text, kind="info")` | Shows a toast in the GUI. `kind` is `info`, `ok` or `bad`. |
| `api.flash(text, kind="info", dur=6)` | Shows a flash message on the OBS overlay for `dur` seconds. `kind` is `info`, `good`, `warn` or `err` and sets the banner's colour. |
| `api.run(chain)` | Runs any command chain **as the console, with owner rights**. It is queued: the call returns at once and the commands run shortly after, as user `"[console]"`, so they also fire the `command` event. |
| `api.get(key, default=None)` / `api.set(key, value)` | Per-plugin settings saved in `settings.json` under `plugin_settings.<id>`. Values must be JSON-serialisable. |
| `api.settings` | A copy of all of this plugin's settings. |
| `api.ui(fn, *args)` | Runs `fn` on the Tk UI thread. |
| `api.id`, `api.manifest`, `api.path` | The plugin's id, its parsed `plugin.json`, and its folder. Keep your own files in `os.path.join(api.path, "data")`, which survives market updates. |
| `api.api_version`, `api.app_version` | Plugin API version (currently `2`) and the YT2VM version string. |
| `api.app` | The `ChatPlaysApp` object itself. It is powerful but internal and can change between releases, so prefer the API above. |

---

## Threads and the UI

- Command handlers, event handlers and timers all run on one background thread named `plugins`, in order. A slow handler delays every other plugin, so do long work (network calls, big files) in your own `threading.Thread`. If a callback takes more than 2 seconds, a warning is written to the log.
- **Never touch Tk widgets from a handler or timer.** Wrap UI updates in `api.ui(fn)`. Panel `build_fn`s already run on the UI thread, and so do callbacks from widgets such as button commands and `widget.after(...)`.
- An exception in a callback is written to `crash_log.txt` and the console. It doesn't stop the plugin or the app.

---

## Releasing a plugin

You release a plugin by clicking **Submit** on its card. The app uploads it to the plugin market, the market's admin reviews the code, and once approved it appears on everyone's Plugin Market page. You need no GitHub account and no website.

### 1. Get it ready

- Pick an `id` you will keep forever, and fill in `name`, `author`, `description` and `version` in `plugin.json`. The market requires all four. Adding `tags`, `commands` and `homepage` makes the market card more useful.
- Use version numbers like `1.0.0`. Raise the last number for fixes (`1.0.1`), the middle one for new features (`1.1.0`), and the first one for changes that break existing settings (`2.0.0`). The market only accepts a version higher than the published one.
- Set `api` to the plugin API version you tested with (currently `2`; use `1` if you only use commands, events, timers and panels).
- Don't put passwords, tokens or anything personal in the plugin folder. Every file in it except `data/` and dotfiles gets uploaded. Only text files can be published, up to 25 files and 600 KB in total.

### 2. Test it

- Click **Reload** on the plugin's card and check that it shows **Running**, not **Error**.
- Try every command from the Dashboard console. Also try them as a viewer, through chat or with the Chat Tools test message, to check `mod_only` and the payload filter.
- Disable and enable it, then restart the app, to check that `teardown` and saved settings work.
- Read `crash_log.txt` for anything with your plugin's id in it.

### 3. Submit it

1. On **Tools → Plugins**, click **Submit** on your plugin's card. You can add a note for the reviewer.
2. The market checks the files right away. If something is wrong, such as a syntax error, a missing field or a version that isn't higher, you get a list of problems. Fix them and submit again.
3. The first time you submit a plugin id, the market reserves it for you and returns an **owner key**. The app saves it in `settings.json`, under `plugin_owner_keys`, and shows it once. Back it up, because without it you can't publish updates to that id, for example from another PC.
4. Your plugin is now waiting for review. While it waits you can fix it and submit the same version again.
5. Once the admin approves it, it appears on the Plugin Market page for everyone.

### 4. Ship updates

1. Raise `version` in `plugin.json`.
2. Click **Submit** again. Your saved owner key is sent along automatically.

Once the update is approved, users see **Update x → y** on the Plugin Market page. Updating keeps their `data/` folder and their settings.

---

## Security

**A plugin is ordinary Python code running inside YT2VM with full access to your PC.** It can read files, start programs and use the network. Every plugin in the market is reviewed before it's published, but only install plugins you're comfortable running, and plugins you got elsewhere only if you've read their code or trust the author.

When you write a plugin:

- Use `ctx.run(...)` for anything a viewer triggers. It keeps the viewer's own permissions and goes through the payload filter.
- Use `api.run(...)` only with text you wrote yourself, never with text that came from chat. It runs with owner rights, so passing viewer text to it would give viewers owner powers.
- Use `mod_only=True` or `owner_only=True` for anything destructive.

Plugins that ignore these rules, hide what they do, or contact unexpected servers won't be approved.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| The plugin doesn't appear at all | `plugin.json` is missing, is invalid JSON, or has a bad `id`. The reason is in `output_log.txt` (search for `PLUGIN`). Folders starting with `.` or `_` are ignored. |
| Status is **Error** | The message is shown on the card. The full traceback is in `crash_log.txt`. |
| "`!x is a built-in command`" | Choose another command name. |
| "already registered by plugin …" | Two plugins use the same command name. Disable one of them. |
| The command does nothing for viewers | Check whether it is `mod_only`, whether chat is paused, and whether the viewer is on cooldown. |
| Changes don't show up | Click **Reload** on the plugin's card. |
| Submit says the id belongs to someone else | Another author already reserved that id, or your owner key is missing or wrong. Pick another id, or copy your key back into `plugin_owner_keys` in `settings.json`. |
| Submit says the version was already submitted | Raise `version` in `plugin.json`. |"""),
    ("plugin-market", "Plugin market guide", r"""# Plugin market

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

If your plugin is rejected, fix the problem, raise the version and submit again."""),
)


# ---------------------------------------------------------------------------
# updater
# ---------------------------------------------------------------------------
# Updates come only from GitHub Releases: publishing a release tagged v<version> makes every copy of
# YT2VM offer that version. The new yt2vm.py is fetched from the tag, checked (it must compile, be
# this app, and carry the same version as the tag), the old file is kept as yt2vm.py.bak-<old>, and
# nothing restarts until the user says so. YT2VM_UPDATE_API / YT2VM_UPDATE_RAW override the URLs for testing.

UPDATE_REPO = "reallyiron/YT2VM"
UPDATE_CHECK_HOURS = 6
_UPDATE_MAX_BYTES = 16 * 1024 * 1024


def _update_urls():
    api = os.environ.get("YT2VM_UPDATE_API") or f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
    raw = os.environ.get("YT2VM_UPDATE_RAW") or f"https://raw.githubusercontent.com/{UPDATE_REPO}/{{tag}}/yt2vm.py"
    return api, raw


def update_supported():
    """(True, "") when this copy can update itself, otherwise (False, why)."""
    if getattr(sys, "frozen", False):
        return False, "this is a packaged .exe build - download new versions by hand"
    target = os.path.abspath(sys.argv[0])
    if not target.lower().endswith(".py") or not os.path.isfile(target):
        return False, "YT2VM isn't running from its .py file"
    if not os.access(target, os.W_OK) or not os.access(os.path.dirname(target), os.W_OK):
        return False, f"no permission to write {target}"
    return True, ""


def update_check():
    """Latest GitHub release. Returns {"tag", "version", "notes", "page", "newer"}; raises on network errors."""
    api, raw = _update_urls()
    req = urllib.request.Request(api, headers={"User-Agent": f"YT2VM/{version} updater",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        rel = json.loads(r.read(1024 * 1024).decode("utf-8"))
    tag = str(rel.get("tag_name") or "").strip()
    if not tag or rel.get("draft") or rel.get("prerelease"):
        return {"tag": "", "version": version, "notes": "", "page": "", "newer": False}
    ver = tag[1:] if tag[:1] in ("v", "V") else tag
    return {"tag": tag, "version": ver, "notes": str(rel.get("body") or "").strip(),
            "page": str(rel.get("html_url") or ""), "raw": raw.replace("{tag}", urllib.parse.quote(tag)),
            "newer": _version_tuple(ver) > _version_tuple(version)}


def update_download(info):
    """Fetch yt2vm.py for a release and check it before anything is replaced. Returns the file's bytes."""
    data = _market_fetch(info["raw"], limit=_UPDATE_MAX_BYTES, timeout=60)
    try:
        src = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("the downloaded file isn't text")
    if "class ChatPlaysApp" not in src or "def update_check" not in src:
        raise ValueError("the downloaded file isn't YT2VM")
    try:
        compile(src, "yt2vm.py", "exec")                        # syntax check only - nothing is run
    except SyntaxError as e:
        raise ValueError(f"the downloaded file has a syntax error on line {e.lineno}")
    m = re.search(r'^version = "([^"]+)"', src, re.M)
    if not m or _version_tuple(m.group(1)) != _version_tuple(info["version"]):
        raise ValueError(f"release {info['tag']} contains yt2vm.py version {m.group(1) if m else '?'} - "
                         "the release tag and the version in the file must match")
    return data


def update_install(data):
    """Replace the running yt2vm.py with data. Keeps the old file as yt2vm.py.bak-<version>. Returns the backup path."""
    ok, why = update_supported()
    if not ok:
        raise ValueError(why)
    target = os.path.abspath(sys.argv[0])
    backup = f"{target}.bak-{re.sub(r'[^0-9A-Za-z._-]', '_', version)}"
    shutil.copy2(target, backup)
    tmp = target + ".update"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, target)
    return backup


class ChatPlaysApp:
    def __init__(self, root):
        self.running = True
        self.root = root
        self.config = {}
        self._init_t0 = time.time()
        self._ui_q = queue.Queue(maxsize=5000)
        self._ui_dropped = 0
        self._ui_after_id = None
        self._ui_tick_count = 0
        self._ui_next_due = 0
        self._ui_sections = []
        self._ui_worst_ms = 0.0
        self._pending_after = -1
        self._bg_busy = set()
        plog("INIT", "building ChatPlaysApp...")
        try:
            self.root = root
            try:
                def _tk_err(exc, val, tb):
                    if issubclass(exc, (KeyboardInterrupt, SystemExit)):
                        self.running = False
                        return
                    blob = ("".join(traceback.format_exception(exc, val, tb)))
                    log_crash("tkinter callback", val)
                    console_log("ERROR", f"ui callback crashed: {val}")
                self.root.report_callback_exception = _tk_err
            except Exception as _ex:
                _trace(_ex_where(), _ex)
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
            self.plugins = PluginManager(self)

            self.pico = None
            self.pico_enabled = False
            self.pico_target = self.config.get("pico_target", "vm")
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
                pass

            self.cmd_queue = FairCommandQueue(lambda k, d: self.config.get(k, d))
            self.music_queue = []
            self.banned_users = {}
            self.current_song = None
            self.song_paused = False
            self.ultra_speed = self.config.get("ultra_speed", False)
            self.vnc_port = self.config.get("vnc_port", "5900")
            self.vnc_password = self.config.get("vnc_password", "1234")
            self.vmrun_path = self.config.get("vmrun_path", "") or find_vmrun()
            self.backend = str(self.config.get("backend", "virtualbox") or "virtualbox").lower()
            self.com_mode = ""
            if self.config.get("use_customtkinter", False):
                if enable_ctk(theme_dark=self.THEMES.get(self.config.get("ui_theme", "original"), {}).get("dark", True)):
                    console_log("SYSTEM", "customtkinter widgets enabled.")
            self.vmware = None
            self.vmx_path = self.config.get("vmx_path", "")
            self.vnc_keymap = self.config.get("vnc_keymap", "us")
            self.win_vbox = None
            self.win_session = None
            self.cli_input = False
            if self.backend not in ("virtualbox", "vmware"): self.backend = "virtualbox"
            _rb = self.backend

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
            _sw, _sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            _gw, _gh = min(1520, max(1100, _sw - 80)), min(900, max(640, _sh - 90))
            self.root.geometry(f"{_gw}x{_gh}+{max(0, (_sw - _gw) // 2)}+{max(0, (_sh - _gh) // 2 - 20)}")
            self.root.minsize(1100, 640)
            self._studio_init()

            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            self.log_queue = queue.Queue(maxsize=300)
            self.connect_queue = queue.Queue()
            self.running = True
            self.active_url = self.config.get("youtube_url", "")
            self.listening_to_chat = self.config.get("enable_chat", True)
            self.disabled_commands = set()
            self.say_admin_only = True
            self.blocked_terms = list(_dbt)
            self.twenty_four_seven_mode = self.config.get("auto_start", False)
            self.blacklisted_users = set()
            self.b64_offenders = self._load_offenders()
            self._tls = threading.local()
            self._discord_token_cache = ""
            self.discord = DiscordBridge(self)
            self.timed_bans = {}
            self.user_last_cmd = {}
            self.user_cmd_hits = {}
            self.user_strikes = {}
            self.active_votes = {}
            self.vote_lock = threading.Lock()
            self.processed_msg_ids = _RecentIds(20000)
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)

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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            elif vbox_pkg == "vboxapi":
                try:
                    self.mgr = VirtualBoxManager(None, None)
                    self.vbox = self.mgr.getVirtualBox()
                except Exception as _ex:
                    _trace(_ex_where(), _ex)

            try: set_obs_scene(obs_scene_main)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

            global _ds
            _ds = lambda m: self.log("[debug]", m, "sysmsg")
            try: VMwareController._ui_root = self.root
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            if DEBUG_ON:
                console_log("SYSTEM", "DEBUG MODE ON - writing to " + _dbf + "  (use --quiet to disable)")
                dbg("startup", platform_report())
                dbg("startup", f"vbox={vbox_manage_cmd} ({_vbox_how})  vms={available_vms}")
            try: self.plugins.load_all()
            except Exception as _ex:
                log_crash("plugins load_all", _ex)
            self.build_unified_dashboard()
            try: self.plugins.apply_deferred_ui()
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            self.start_terminal_thread()
            self.start_app_threads()
            if self.twenty_four_seven_mode and self.active_url: self.go_live()
            try:
                if self.config.get("discord_enabled") and self.config.get("discord_mode") != "disabled":
                    _tok = getattr(self, "_discord_token_cache", "") or discord_token_load()
                    if _tok:
                        self.discord.start(_tok, self.config.get("discord_mode", "crossplay"))
                        plog("DISCORD", "auto-starting bot (was enabled last session)")
                    else:
                        plog("DISCORD", "was enabled but no saved token - open the Discord page to paste it")
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            self._plugins_ready = True
            self.plugins.emit("ready")
            self._update_schedule(first=True)
            try: self.root.after(600, self.show_welcome_guide)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            self._schedule_ui_tick()
            plog("INIT", f"ChatPlaysApp ready in {time.time()-self._init_t0:.2f}s  backend={getattr(self,'backend','?')}  vm={vm_name}  "
                         f"chat_url={'set' if getattr(self,'active_url','') else 'none'}  24/7={getattr(self,'twenty_four_seven_mode',False)}")
        except Exception as e:
            err_msg = f"[error] init crashed: {e}"
            log_crash("ChatPlaysApp.__init__", e)
            print(err_msg + f"\n{traceback.format_exc()}")
            try: messagebox.showerror("error", err_msg + "\n\nsee " + CRASH_LOG)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def ui(self, fn, *a, **k):
        if threading.current_thread() is threading.main_thread():
            try:
                return fn(*a, **k)
            except Exception as e:
                log_crash(f"ui call {getattr(fn, '__name__', '?')}", e)
                return None
        q = getattr(self, "_ui_q", None)
        if q is None:
            return None
        try:
            q.put_nowait((fn, a, k, time.time()))
        except queue.Full:
            self._ui_dropped = getattr(self, "_ui_dropped", 0) + 1
            if self._ui_dropped in (1, 100) or self._ui_dropped % 1000 == 0:
                plog("UI", f"ui call queue full - dropped {self._ui_dropped} widget updates (UI thread is not keeping up)")
        return None

    def _drain_ui_calls(self, budget=0.05):
        q = getattr(self, "_ui_q", None)
        if q is None:
            return 0
        end = time.time() + budget
        n = 0
        while time.time() < end:
            try:
                fn, a, k, ts = q.get_nowait()
            except queue.Empty:
                break
            n += 1
            t0 = time.time()
            try:
                fn(*a, **k)
            except Exception as e:
                _trace(_ex_where(), e)
            el = time.time() - t0
            if el > 0.2:
                plog("UI-SLOW", f"queued ui call {getattr(fn, '__qualname__', getattr(fn, '__name__', '?'))} took {el*1000:.0f}ms")
        left = q.qsize()
        if left > 500 and (time.time() - getattr(self, "_ui_backlog_warn", 0)) > 10:
            self._ui_backlog_warn = time.time()
            plog("UI", f"ui call backlog: {left} pending widget updates")
        return n

    def _run_bg(self, key, fn, *a):
        busy = self._bg_busy
        if key in busy:
            return False
        busy.add(key)
        def _go():
            t0 = time.time()
            try:
                fn(*a)
            except Exception as e:
                plog("BG", f"background job '{key}' failed: {type(e).__name__}: {e}")
                _trace(_ex_where(), e)
            finally:
                busy.discard(key)
                el = time.time() - t0
                if el > 8:
                    plog("BG", f"background job '{key}' took {el:.1f}s")
                else:
                    plog("BG", f"background job '{key}' done in {el*1000:.0f}ms", verbose=True)
        threading.Thread(target=_go, daemon=True, name=f"bg-{key}").start()
        return True

    def _discord_exclusive(self):
        br = getattr(self, "discord", None)
        return bool(br is not None and br.running and br.mode == "discord")

    def _b64_filter_on(self):
        return bool(self.config.get("b64_filter", True))

    def _display_text(self, message):
        if self._b64_filter_on() and _b64_scan(message):
            return "[blocked by base64 filter]"
        return message

    def _ingest_chat(self, user, message, is_mod=False, is_owner=False, source="discord", ref=None, display=None):
        if not self.listening_to_chat:
            return None
        shown = display or user
        text = self._display_text(message)
        add_to_history(f"[{source}] {shown}", text, "user", is_mod, is_owner)
        if not str(shown).startswith("["):
            self._chat_pane_msg(f"{shown}", text, is_mod, is_owner)
        try:
            self.replay_buffer.append({"t": time.time(), "u": f"[{source}] {shown}", "m": text, "mod": is_mod, "owner": is_owner})
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        console_log("CHAT", f"[{source}] [{shown}]{' (owner)' if is_owner else (' (mod)' if is_mod else '')}: {text}")
        append_to_all_msgs_log(f"[{source}] {shown}", text)
        self._plugin_chat(shown, message, is_mod, is_owner, source)
        clean_user = str(user).replace("@", "").lower().strip()
        if str(message).startswith(self.command_prefix):
            if self._guard_payload(clean_user, message, is_owner, source=source, ref=ref):
                return "blocked"
            self._tls.src = (source, ref)
            try:
                self.parse_command(message, user, is_mod, is_owner)
            except Exception as parse_ex:
                console_log("ERROR", f"parse_command error ({source}): {parse_ex}\n{traceback.format_exc()}")
            finally:
                self._tls.src = None
            return "cmd"
        return "msg"

    def _is_owner_name(self, clean_user, is_owner=False):
        return bool(is_owner or clean_user in owners or clean_user == "reallyiron"
                    or clean_user in ("[console]", "[system]"))

    def _guard_payload(self, clean_user, message, is_owner, source="youtube", ref=None):
        if not self._b64_filter_on():
            return False
        why = _b64_scan(message)
        if not why:
            return False
        trusted = self._is_owner_name(clean_user, is_owner)
        plog("SECURITY", f"base64 filter blocked {source}:{clean_user} - {why}" + (" (owner - not added to the block list)" if trusted else ""))
        if trusted:
            self.log("[system]", f"[warn] base64 filter blocked a command from {clean_user} ({why}). !tob64 turns the filter off.", "sysmsg")
        else:
            if clean_user not in self.b64_offenders:
                self.b64_offenders.add(clean_user)
                self._save_offenders()
            self.log("[system]", f"[error] base64 blocked from {clean_user} ({why}). they can no longer send commands.", "err")
            br = getattr(self, "discord", None)
            if source == "discord" and br is not None:
                br.on_blocked(clean_user, why, ref=ref)
        self.ui(self._sync_security_marks)
        return True

    def _offenders_file(self):
        return os.path.splitext(settings_file)[0] + "_blocked.json"

    def _load_offenders(self):
        try:
            with open(self._offenders_file(), "r") as f:
                data = json.load(f)
            return set(str(x).lower() for x in data)
        except Exception:
            return set()

    def _save_offenders(self):
        try:
            tmp = self._offenders_file() + ".tmp"
            with open(tmp, "w") as f:
                json.dump(sorted(self.b64_offenders), f)
            os.replace(tmp, self._offenders_file())
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _capture_vm_png(self):
        out = os.path.abspath(f"_vm_shot_{os.getpid()}.png")
        be = getattr(self, "backend", "virtualbox")
        try:
            if be == "vmware":
                vmw = self._vmware()
                if not getattr(vmw, "_need", lambda: False)():
                    return None, "VNC not connected"
                client = vmw.client
                if client is None or not hasattr(client, "captureScreen"):
                    return None, "VNC capture unavailable"
                with vmw.lock:
                    client.captureScreen(out)
                if os.path.exists(out) and os.path.getsize(out) > 0:
                    return out, ""
                return None, "capture produced no image"
            if not self._vm_is_running():
                return None, "VM is not running"
            r = run_vbox(["controlvm", vm_name, "screenshotpng", out], timeout=12)
            if r is not None and r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 0:
                return out, ""
            detail = ""
            if r is not None:
                detail = ((r.stderr or "") + (r.stdout or "")).strip()[:80]
            return None, detail or "VBoxManage screenshotpng failed"
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:80]}"

    def _discord_press(self, cmd, arg, user):
        br = getattr(self, "discord", None)
        if br is not None and br.running and str(user).startswith("dc_"):
            try:
                br.pressed(cmd, arg, user)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _discord_announce(self, text):
        br = getattr(self, "discord", None)
        if br is not None and br.running:
            try:
                br.announce(text)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    _MAINT_MSGS = {
        "revert": ("Reverting!", "Revert done!", "Revert failed."),
        "restartvm": ("Restarting the VM!", "VM restarted!", "Restart failed."),
        "startvm": ("Starting the VM!", "VM started!", "Couldn't start the VM."),
        "shutdown": ("Shutting down the VM!", "VM shut down.", "Shutdown failed."),
        "changevm": ("Switching VM!", "VM switched!", "Couldn't switch the VM."),
        "fixvm": ("Fixing the VM!", "VM fixed!", "Fix failed."),
        "forcefixvm": ("Force-fixing the VM!", "VM fixed!", "Fix failed."),
        "makesnapshot": ("Taking a snapshot!", "Snapshot saved!", "Snapshot failed."),
        "remake2": ("Rebuilding the snapshot!", "Snapshot rebuilt!", "Rebuild failed."),
    }

    def _maint_messages(self, base):
        return self._MAINT_MSGS.get(base, (f"Running {base}!", f"{base} done!", f"{base} failed."))

    def _discord_maint(self, text, shot=False):
        br = getattr(self, "discord", None)
        if br is not None and br.running:
            try:
                br.maint_announce(text, shot)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _cmd_screenshot(self, user):
        now = time.time()
        if now - getattr(self, "_last_shot_req", 0.0) < 3.0:
            return
        self._last_shot_req = now
        br = getattr(self, "discord", None)
        if br is not None and br.running:
            br.screenshot_now(user)
        else:
            self.log("[system]", "screenshot requested, but the Discord bot is offline.", "sysmsg")

    _HELP_VIEWER = [
        ("!type <text>", "type text into the VM"),
        ("!send <text>", "type text, then press Enter"),
        ("!key <key>", "press one key (enter, tab, f5, esc ...)"),
        ("!combo <a+b>", "press keys together (win+r, ctrl+c)"),
        ("!keydown <key> / !keyup <key>", "hold a key down / release it"),
        ("!click / !rclick / !mclick", "left / right / middle mouse click"),
        ("!move <x> <y> / !abs <x> <y>", "move the mouse by, or to, x y"),
        ("!scroll <n> / !drag <x> <y>", "scroll the wheel / drag the mouse"),
        ("!wait <time>", "pause in a chain - !wait 2, !wait 2s, !wait 500ms"),
        ("!run <cmd> / !cmd <cmd>", "run a program / run a line in CMD"),
        ("!screenshot / !screen / !s", "post a screenshot of the VM to Discord"),
        ("!roll / !coinflip", "roll a dice / flip a coin"),
        ("!revert", "vote to revert the VM (mods revert instantly)"),
        ("!music <url>", "queue a song"),
        ("!skipsong / !pausesong / !resumesong", "vote song controls"),
        ("chaining", "join commands with | : !combo win+r | !wait 1 | !send notepad"),
        ("!help", "show this list"),
    ]
    _HELP_MOD = [
        ("!ban @user / !unban @user", "ban or unban a user from using commands"),
        ("!timeout @user <min>", "mute a user for some minutes"),
        ("!lock / !unlock", "lock commands to mods only / re-open to everyone"),
        ("!purge", "clear the command queue"),
        ("!slowmode <sec>", "set the viewer cooldown"),
        ("!whois @user / !strikes @user", "show / clear a user's status"),
        ("!clearvotes", "clear the active votes"),
        ("!revertnow / !restartnow / !snapshotnow", "run VM maintenance right now"),
        ("!vmstatus / !stats / !queue", "status info"),
        ("!flash <text> / !announce <text>", "show a message on stream"),
        ("!protect", "toggle blocking dangerous VM commands"),
    ]
    _HELP_OWNER = [
        ("!tob64 / !eb64", "turn the base64 filter off / on"),
        ("!unblock @user", "remove a user from the base64 block list"),
        ("!pausechat / !enablechat", "owner-only chat pause"),
        ("!plugins ...", "manage plugins (list / reload / enable / disable)"),
    ]

    def _send_help(self, user, is_mod, is_admin, is_owner, src):
        sections = [("Commands", self._HELP_VIEWER)]
        if is_admin:
            sections.append(("Mod commands", self._HELP_MOD))
        if is_owner:
            sections.append(("Owner commands", self._HELP_OWNER))
        pm = getattr(self, "plugins", None)
        if pm is not None:
            try:
                pcmds = pm.help_lines()
            except Exception:
                pcmds = []
            if pcmds:
                sections.append(("Plugin commands", list(pcmds)))
        br = getattr(self, "discord", None)
        if src == "discord" and br is not None and br.running:
            for title, items in sections:
                br.announce(f"**{title}**")
                for c, d in items:
                    br.announce(f"`{c}` - {d}")
        else:
            self.send_flash("commands listed in the log below", "info", 5)
            for title, items in sections:
                self.log("[help]", title, "sysmsg")
                for c, d in items:
                    self.log("[help]", f"{c}  -  {d}", "sysmsg")

    def toggle_crossplay(self):
        br = self.discord
        if br.running:
            br.stop()
            self.config["discord_enabled"] = False
            self.save_settings()
            self.toast("Discord bot stopped.", "ok")
            self._refresh_discord_page()
            return
        token = ""
        try:
            token = self.discord_token_entry.get().strip()
        except Exception:
            pass
        if token and token != self._discord_token_mask():
            saved_enc = discord_token_save(token)
            self._discord_token_cache = token
            plog("DISCORD", "token saved" + (" (encrypted with DPAPI)" if saved_enc else " (plaintext - not on Windows)"))
        else:
            token = getattr(self, "_discord_token_cache", "") or discord_token_load()
        if not token:
            self.toast("Paste your bot token first.", "bad")
            self._set_discord_hint("Paste the bot token from the Developer Portal, then press the button again.", "bad")
            return
        mode = getattr(self, "_discord_mode_var", None)
        mode = mode.get() if mode is not None else "crossplay"
        self.config["discord_enabled"] = True
        self.config["discord_mode"] = mode
        self.save_settings()
        br.start(token, mode)
        if mode == "crossplay":
            url = str(self.config.get("youtube_url", "") or "").strip()
            if url and not (getattr(self, "listening_to_chat", False) and getattr(self, "active_url", "")):
                try:
                    self.go_live()
                    plog("DISCORD", "crossplay - also connecting YouTube chat")
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
        self.toast(f"Starting Discord bot ({br.mode_label()}).", "ok")
        self._refresh_discord_page()

    def _discord_token_mask(self):
        return "\u2022" * 24

    def save_discord_token(self):
        try:
            token = self.discord_token_entry.get().strip()
        except Exception:
            return
        if token == self._discord_token_mask():
            return
        if not token:
            discord_token_save("")
            self._discord_token_cache = ""
            self._set_discord_hint("Saved token removed.", "ok")
            self.toast("Bot token removed.", "ok")
            return
        enc = discord_token_save(token)
        self._discord_token_cache = token
        self._set_discord_hint("Token saved" + (" and encrypted with Windows DPAPI." if enc else " (stored in plain text - Windows encrypts it automatically)."), "ok")
        self.toast("Bot token saved.", "ok")

    def _set_discord_hint(self, text, kind="muted"):
        if not hasattr(self, "_discord_hint"):
            return
        col = {"ok": "ok", "bad": "bad", "warn": "warn"}.get(kind, "muted")
        try:
            self._discord_hint.configure(text=text, fg=_studio_color(col, "#A1A1AA"))
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _vm_is_running(self):
        _c = getattr(self, "_vmrun_cache", None)
        if _c and time.time() - _c[0] < 3:
            return _c[1]
        if threading.current_thread() is threading.main_thread():
            self._run_bg("vm-state", self._vm_is_running_blocking)
            return _c[1] if _c else False
        return self._vm_is_running_blocking()

    def _vm_is_running_blocking(self):
        prev = getattr(self, "_vmrun_cache", None)
        t0 = time.time()
        if getattr(self, "backend", "virtualbox") == "vmware":
            try:
                r = self._vmware().is_running()
            except Exception as e:
                plog_throttled("vmstate", "VM", f"vmware is_running check failed: {e}")
                r = False
        else:
            try:
                res = subprocess.run([vbox_manage_cmd, "list", "runningvms"], capture_output=True, text=True, timeout=4)
                r = f'"{vm_name}"' in (res.stdout or "")
            except subprocess.TimeoutExpired:
                plog_throttled("vmstate", "VM", "VBoxManage list runningvms timed out (4s) - VBoxSVC busy or hung", 20)
                return prev[1] if prev else False
            except Exception as e:
                plog_throttled("vmstate", "VM", f"VBoxManage list runningvms failed: {type(e).__name__}: {e}")
                return False
        self._vmrun_cache = (time.time(), r)
        el = time.time() - t0
        if prev is None or prev[1] != r:
            plog("VM", f"vm '{vm_name}' state -> {'RUNNING' if r else 'STOPPED'} (checked in {el*1000:.0f}ms via {getattr(self, 'backend', 'virtualbox')})")
        elif el > 3:
            plog("VM", f"vm state check was slow: {el:.1f}s")
        return r

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
        if threading.current_thread() is threading.main_thread():
            threading.Thread(target=self.obs_media_action, args=(action,), daemon=True, name="obs-media").start()
            return
        plog("OBS", f"media action {action.replace('OBS_WEBSOCKET_MEDIA_INPUT_ACTION_', '')}")
        try:
            if not obs_available or not obs_reachable():
                plog("OBS", "media action skipped - OBS websocket not reachable")
                return
            cl = obs.ReqClient(host=obs_host, port=obs_port, password=obs_password, timeout=3)
            try: cl.trigger_media_input_action(inputName="Media", mediaAction=action)
            except Exception:
                try: cl.trigger_media_input_action(input_name="Media", mediaAction=action)
                except Exception: cl.trigger_media_input_action("Media", action)
        except Exception as _ex:
            plog("OBS", f"media action failed: {type(_ex).__name__}: {_ex}")
            _trace(_ex_where(), _ex)

    def queue_music(self, url, user, is_owner=False, is_mod=False, bypass=False):
        q = getattr(self, "_music_q", None)
        if q is None:
            q = self._music_q = collections.deque()
            self._music_lock = threading.Lock()
            self._music_evt = threading.Event()
            def _worker():
                while self.running:
                    self._music_evt.wait(2.0)
                    while True:
                        with self._music_lock:
                            job = q.popleft() if q else None
                            if not q:
                                self._music_evt.clear()
                        if job is None:
                            break
                        self._music_busy = job[1]
                        t0 = time.time()
                        try:
                            self.download_music_thread(*job)
                        except Exception as e:
                            plog("MUSIC", f"download for {job[1]} crashed: {type(e).__name__}: {e}")
                        self._music_busy = None
                        plog("MUSIC", f"download for {job[1]} finished in {time.time()-t0:.0f}s ({len(q)} waiting)")
            threading.Thread(target=_worker, daemon=True, name="music-downloader").start()
        privileged = is_owner or is_mod or user == "[console]"
        key = str(user).lower()
        with self._music_lock:
            mine = sum(1 for j in q if str(j[1]).lower() == key) + (1 if str(getattr(self, "_music_busy", "") or "").lower() == key else 0)
            if not privileged and mine >= 1:
                why = "you already have a song downloading or waiting"
            elif not privileged and len(q) >= int(self.config.get("music_queue_max", 8) or 8):
                why = "the download line is full, try again in a minute"
            else:
                why = None
                q.append((url, user, is_owner, is_mod, bypass))
                n = len(q)
        if why:
            ws = getattr(self, "_warn_seen", None)
            if ws is None:
                ws = self._warn_seen = {}
            if time.time() - ws.get((key, "music"), 0) > 30:
                ws[(key, "music")] = time.time()
                self.log("[music]", f"{user}: {why}.", "sysmsg")
            plog("MUSIC", f"request from {user} refused: {why}")
            return
        plog("MUSIC", f"request from {user} queued ({n} waiting)")
        self._music_evt.set()

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
            except Exception as _ex:
                _trace(_ex_where(), _ex)
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            time.sleep(1)

    def load_settings(self):
        _be = _active_backend()
        all_vms = get_all_vbox_vms(vbox_manage_cmd, quiet=True) if _be != "vmware" else []
        default_vm = all_vms[instance_id - 1] if (all_vms and len(all_vms) >= instance_id) else (all_vms[0] if all_vms else vm_name or "Windows10ChatVm")
        default_config = {
            "youtube_url": "", "vm_name": default_vm, "vbox_path": vbox_manage_cmd, "auto_start": False,
            "enable_chat": True, "strict_live_check": True, "keyboard_layout": "US", "command_prefix": "!",
            "stats_interval": 15, "typing_speed": 0.015, "key_delay": 0.015, "mouse_delay": 0.005,
            "enable_starting_scene": True, "app_name": "YT2VM", "ultra_speed": False, "osvoting_enabled": False, "ui_theme": "original", "auto_recover": True, "low_power": False, "snippets": [], "sound_sources": [], "backend": "virtualbox", "allow_viewer_shell": False, "protect_vm": False, "rate_limit_enabled": True, "use_customtkinter": False, "use_ttkbootstrap": True, "viewer_cooldown": 1.5, "viewer_rate_limit": 7, "max_type_len": 200, "flask_bind_lan": False, "vmx_path": "", "vnc_keymap": "us", "vmware_settle": 1.0, "vnc_host": "127.0.0.1", "auto_kill_vnc": True, "altgr_mode": "alt_r",
            "custom_commands": {},
            "b64_filter": True, "discord_enabled": False, "discord_mode": "crossplay",
            "discord_guild_id": "", "discord_channel_id": "", "discord_log_channel_id": "",
            "discord_owner_ids": "", "discord_screens": True, "discord_log_all": True,
            "plugins_enabled": {}, "plugin_settings": {}, "plugin_market_autoload": True, "plugin_owner_keys": {}, "update_mode": "ask"
        }
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r") as f: default_config.update(json.load(f))
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        return default_config

    _settings_lock = threading.Lock()

    def save_settings(self):
        try:
            with self._settings_lock:
                tmp_file = settings_file + ".tmp"
                with open(tmp_file, "w") as f: json.dump(self.config, f, indent=4)
                os.replace(tmp_file, settings_file)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def trigger_command(self, action_tuple):
        if self.cmd_queue.qsize() > 5000:
            plog("QUEUE", f"DROPPED {action_tuple!r:.120} - queue over 5000")
            self.log("[system]", "[warn] command dropped: system overloaded", "err")
            self.force_session_refresh = True
            return
        self.cmd_queue.put(action_tuple)
        try:
            plog("QUEUE", f"+ {str(action_tuple[0])} {str(action_tuple[1])[:60]!r} from {action_tuple[2]}  (queue={self.cmd_queue.qsize()})")
        except Exception:
            plog("QUEUE", f"+ {action_tuple!r:.120}")

    def trigger_command_chain(self, action_chain, priority=True):
        if self.cmd_queue.qsize() > 5000:
            self.log("[system]", "[warn] macro dropped: system overloaded", "err")
            self.force_session_refresh = True
            return
        items = []
        owner = None
        for action in action_chain:
            try:
                cmd_type, arg, user = action
            except Exception:
                continue
            owner = owner or user
            base = str(cmd_type).lower()
            if base.startswith(self.command_prefix): base = base[len(self.command_prefix):]
            base = base.lstrip("!")
            if base in ("wait", "w"):
                w = _wait_seconds(arg)
                items.append(("__wait__", str(w), user))
            else:
                items.append(action)
        n = len(items)
        if not n:
            return
        if hasattr(self.cmd_queue, "put_job"):
            self.cmd_queue.put_job(items, owner, prio=priority)
        else:
            for it in items:
                self.cmd_queue.put(it)
        if n > 1:
            plog("QUEUE", f"chain queued: {n} step(s) in order from {owner}{' (priority)' if priority else ''}  (queue={self.cmd_queue.qsize()})")
        else:
            try: plog("QUEUE", f"+ {action_chain[0][0]} {str(action_chain[0][1])[:60]!r} from {action_chain[0][2]}  (queue={self.cmd_queue.qsize()})")
            except Exception: pass

    def clear_commands(self):
        if hasattr(self.cmd_queue, "clear"):
            n = self.cmd_queue.clear()
        else:
            with self.cmd_queue.mutex:
                n = len(self.cmd_queue.queue)
                self.cmd_queue.queue.clear()
        plog("QUEUE", f"command queue cleared ({n} dropped)")

    def on_closing(self):
        plog("SHUTDOWN", "window closed by user - saving and exiting")
        try: _jlog_flush()
        except Exception: pass
        try: self.plugins.shutdown()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self.running = False
        try:
            if getattr(self, "discord", None) is not None:
                self.discord.stop()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        save_stats()
        try:
            if hasattr(self, 'shared_session') and self.shared_session:
                try:
                    if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                    else: self.shared_session.unlockMachine()
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self.root.update()
        out_flush(1.0)
        os._exit(0)

    def start_terminal_thread(self):
        def listen_terminal():
            eofs = 0
            while self.running:
                try:
                    if sys.stdin is None:
                        plog("TERMINAL", "no stdin attached - terminal commands disabled")
                        return
                    raw = sys.stdin.readline()
                    if raw == "":
                        eofs += 1
                        if eofs >= 5:
                            plog("TERMINAL", "stdin is closed (EOF) - terminal command listener stopped")
                            return
                        time.sleep(1)
                        continue
                    eofs = 0
                    cmd = raw.strip()
                    if cmd:
                        if not cmd.startswith(self.command_prefix) and not cmd.startswith("!"):
                            cmd = self.command_prefix + cmd
                        elif cmd.startswith("!") and not cmd.startswith(self.command_prefix):
                            cmd = self.command_prefix + cmd[1:]
                        plog("TERMINAL", f"typed: {cmd}")
                        self.ui(self._handle_terminal_cmd, cmd)
                except Exception as e:
                    plog("TERMINAL", f"stdin read error: {e}")
                    time.sleep(1)
        t = threading.Thread(target=listen_terminal, daemon=True, name="terminal")
        t.start()

    def _handle_terminal_cmd(self, cmd):
        self.log("[console]", cmd, "user", is_mod=True, is_owner=True)
        self._manual_cmd(cmd)

    def _manual_cmd(self, cmd):
        q = getattr(self, "_manual_q", None)
        if q is None:
            q = self._manual_q = queue.Queue()
            def _worker():
                while self.running:
                    try:
                        c = q.get(timeout=1)
                    except queue.Empty:
                        continue
                    t0 = time.time()
                    try:
                        self.parse_command(c, "[console]", is_mod=True, is_owner=True)
                    except Exception as e:
                        log_crash(f"manual command {c!r}", e)
                    el = time.time() - t0
                    if el > 2:
                        plog("CMD", f"manual command {c!r} took {el:.1f}s to parse")
            threading.Thread(target=_worker, daemon=True, name="manual-cmd").start()
        plog("CMD", f"manual command: {cmd}")
        q.put(cmd)

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
                        except Exception as _ex:
                            _trace(_ex_where(), _ex)
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
            self.tab_discord = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_discord, text="  Discord  ")
            self.tab_plugins = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_plugins, text="  Plugins  ")
            self.tab_market = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_market, text="  Plugin Market  ")
            self.tab_plugindocs = ttk.Frame(self.tabview, style="TFrame")
            self.tabview.add(self.tab_plugindocs, text="  Plugin Docs  ")

            t = self._tok
            def _f(parent, role="bg", **kw):
                fr = tk.Frame(parent, bg=t[role], **kw)
                fr._st = {"bg": role}
                return fr
            S = getattr(self, "_ui_scale", 1.0)
            self._dash_hist = {k: collections.deque(maxlen=150) for k in ("viewers", "queue", "cpm")}
            self._dash_cmdlog = collections.deque(maxlen=400)
            self._repaint_hooks = getattr(self, "_repaint_hooks", [])

            metrics = _f(self.tab_dash)
            metrics.pack(side="top", fill="x", padx=24, pady=(20, 0))
            self._metric = {}
            for i, (key, title, sub) in enumerate((("viewers", "Viewers", "0 likes"),
                                                   ("queue", "Command queue", "Nobody waiting"),
                                                   ("cpm", "Commands / min", "0 run  /  0 failed"),
                                                   ("uptime", "Uptime", "Success rate 100%"))):
                outer, card = self._st_card(metrics)
                outer.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
                metrics.columnconfigure(i, weight=1, uniform="metric")
                top = _f(card, "card")
                top.pack(fill="x", padx=16, pady=(13, 0))
                self._st_label(top, title, fg="muted", font=("ui", 9, "semi")).pack(side="left")
                trend = self._st_label(top, "", fg="faint", font=("ui", 8))
                trend.pack(side="right")
                val = self._st_label(card, "0", fg="hi", font=("display", 23), anchor="w")
                val.pack(fill="x", padx=16, pady=(2, 0))
                sl = self._st_label(card, sub, fg="faint", font=("ui", 8), anchor="w")
                sl.pack(fill="x", padx=16)
                cv = tk.Canvas(card, height=int(34 * S), bd=0, highlightthickness=0, bg=t["card"])
                cv._studio_skip = True
                cv.pack(fill="x", padx=0, pady=(8, 0))
                cv.bind("<Configure>", lambda e: self._draw_sparks())
                self._metric[key] = {"val": val, "sub": sl, "cv": cv, "trend": trend}
            self.lbl_viewers_val = self._metric["viewers"]["val"]
            self.lbl_likes_val = self._metric["viewers"]["sub"]
            self.lbl_uptime_val = self._metric["uptime"]["val"]
            self.lbl_cmds_val = self._metric["cpm"]["sub"]

            hoo, health = self._st_card(self.tab_dash)
            hoo.pack(side="top", fill="x", padx=24, pady=(12, 0))
            hrow = _f(health, "card")
            hrow.pack(fill="x")
            self._tiles = {}
            self._tile_dots = {}
            self._tile_cards = [hoo]
            cells = (("Bot Status", "Chat bot"), ("VM", "Virtual machine"), ("Discord", "Discord"), ("OBS", "OBS"),
                     ("Overlay Server", "Overlay server"), ("Real PC", "Real PC"))
            for i, (key, nice) in enumerate(cells):
                if i:
                    sep = _f(hrow, "line", width=1)
                    sep.grid(row=0, column=i * 2 - 1, sticky="ns", pady=10)
                cell = _f(hrow, "card")
                cell.grid(row=0, column=i * 2, sticky="we", padx=16, pady=10)
                hrow.columnconfigure(i * 2, weight=1, uniform="health")
                dot = self._st_label(cell, "\u25cf", fg="faint", font=("ui", 9))
                dot.pack(side="left", padx=(0, 8))
                txt = _f(cell, "card")
                txt.pack(side="left", fill="x")
                self._st_label(txt, nice, fg="muted", font=("ui", 8), anchor="w").pack(anchor="w")
                v = self._st_label(txt, "Stopped", fg="text", font=("ui", 10, "semi"), anchor="w")
                v.pack(anchor="w")
                self._tiles[key] = v
                self._tile_dots[key] = dot

            body = _f(self.tab_dash)
            body.pack(side="top", fill="both", expand=True, padx=24, pady=(12, 18))
            left_host = _f(body, width=int(352 * S))
            left_host.pack(side="left", fill="y")
            left_host.pack_propagate(False)
            dash_left = self.make_scrollable(left_host)
            dash_right = _f(body)
            dash_right.pack(side="left", fill="both", expand=True, padx=(14, 0))

            o1, conn_card = self._st_card(dash_left, "Stream")
            o1.pack(fill="x", pady=(0, 12), padx=(0, 10))
            self._st_label(conn_card, "YouTube link, @handle or video ID", fg="muted", font=("ui", 9)).pack(anchor="w", padx=16)
            self.entry_url = tk.Entry(conn_card, font=_sf("ui", 10), bg=t["input"], fg=t["hi"], insertbackground=t["hi"], bd=0,
                                      highlightthickness=1, highlightbackground=t["line"], highlightcolor=t["accent"])
            self.entry_url.pack(fill="x", padx=16, pady=(6, 10), ipady=7)
            self.entry_url.insert(0, self.config.get("youtube_url", "@yourchannel"))
            self.entry_url.bind("<Return>", lambda e: self.go_live())
            self.btn_connect = self._st_button(conn_card, "Connect chat", self.go_live, "primary")
            self.btn_connect.pack(fill="x", padx=16, pady=(0, 10))
            srow = _f(conn_card, "card")
            srow.pack(fill="x", padx=16, pady=(0, 14))
            self._stream_dot = self._st_label(srow, "\u25cf", fg="faint", font=("ui", 8))
            self._stream_dot.pack(side="left")
            self._stream_state = self._st_label(srow, "Not connected", fg="faint", font=("ui", 9), anchor="w")
            self._stream_state.pack(side="left", padx=(6, 0))

            o2, status_card = self._st_card(dash_left, "Machine")
            o2.pack(fill="x", pady=(0, 12), padx=(0, 10))
            self.lbl_status = self._st_label(status_card, "Booting", fg="ok", font=("display", 15), anchor="w")
            self.lbl_status.pack(fill="x", padx=16)
            self._st_label(status_card, "Target VM  /  click to cycle", fg="faint", font=("ui", 8), anchor="w").pack(fill="x", padx=16, pady=(8, 0))
            self.btn_vm = self._st_button(status_card, f"{vm_name}", self.cycle_vm, "neutral", 9)
            self.btn_vm.pack(fill="x", padx=16, pady=(4, 10))
            grid = _f(status_card, "card")
            grid.pack(fill="x", padx=12, pady=(0, 14))
            for c in range(2):
                grid.columnconfigure(c, weight=1, uniform="mach")
            for i, (lbl, fn, var) in enumerate((
                    ("Start VM", lambda: self._vm_action("startvm"), "go"),
                    ("Shut down", lambda: self._vm_action("shutdown"), "neutral"),
                    ("Restart", lambda: self._vm_action("restartvm"), "neutral"),
                    ("Revert snapshot", lambda: self._vm_action("revert"), "danger"),
                    ("Pause", self.pause_vm, "neutral"),
                    ("Resume", self.resume_vm, "neutral"),
                    ("Quick snapshot", self.quick_snapshot, "neutral"),
                    ("Rebuild COM", lambda: setattr(self, 'force_session_refresh', True), "neutral"))):
                self._st_button(grid, lbl, fn, var, 9).grid(row=i // 2, column=i % 2, sticky="we", padx=4, pady=4)

            o3, tools_card = self._st_card(dash_left, "Chat control")
            o3.pack(fill="x", pady=(0, 6), padx=(0, 10))
            tg = _f(tools_card, "card")
            tg.pack(fill="x", padx=12, pady=(0, 14))
            for c in range(2):
                tg.columnconfigure(c, weight=1, uniform="tools")
            for i, (lbl, fn) in enumerate((("Toggle chat", self.toggle_pause_chat),
                                           ("Low power", self._toggle_low_power),
                                           ("Export messages", self.extract_all_msgs),
                                           ("Minimize", self._minimize_window))):
                self._st_button(tg, lbl, fn, "neutral", 9).grid(row=i // 2, column=i % 2, sticky="we", padx=4, pady=4)

            co, ccard = self._st_card(dash_right)
            co.pack(fill="both", expand=True)
            chead = _f(ccard, "card")
            chead.pack(fill="x", padx=16, pady=(12, 10))
            self._st_label(chead, "Console", fg="hi", font=("display", 13)).pack(side="left")
            self._st_button(chead, "Clear", self._clear_console, "neutral", 9).pack(side="right")
            chips = _f(chead, "card")
            chips.pack(side="right", padx=(0, 10))
            self._console_filter = "all"
            self._console_chips = {}
            for key, txt in (("all", "All"), ("chat", "Chat"), ("system", "System"), ("errors", "Errors")):
                ch = tk.Label(chips, text=txt, padx=10, pady=3, cursor="hand2")
                ch._studio_skip = True
                ch.pack(side="left", padx=(4, 0))
                ch.bind("<Button-1>", lambda e, k=key: self._set_console_filter(k))
                self._console_chips[key] = ch
            self._repaint_hooks.append(self._paint_console_chips)
            crule = _f(ccard, "line", height=1)
            crule.pack(fill="x")
            cmd_frame = _f(ccard, "card")
            cmd_frame.pack(side="bottom", fill="x", padx=12, pady=12)
            crule2 = _f(ccard, "line", height=1)
            crule2.pack(side="bottom", fill="x")
            console_border = _f(ccard, "input")
            console_border.pack(fill="both", expand=True)
            self.console_text = scrolledtext.ScrolledText(console_border, font=_sf("mono", 10), bg=t["input"], fg=t["text"], bd=0,
                                                          highlightthickness=0, insertbackground=t["hi"], padx=16, pady=12,
                                                          spacing1=1, spacing3=3, wrap="word", height=6, width=40)
            self.console_text._st = {"bg": "input", "fg": "text", "font": ("mono", 9)}
            self.console_text.pack(fill="both", expand=True)
            self.console_text.configure(state='disabled')
            self.console_text.tag_config("SYSTEM", foreground="#10B981")
            self.console_text.tag_config("ERROR", foreground="#EF4444", font=("Consolas", 10, "bold"))
            self.console_text.tag_config("EXEC", foreground="#A78BFA")
            self.console_text.tag_config("CHAT", foreground="#A1A1AA")
            self.console_text.tag_config("OTHER", foreground="#D4D4D8")
            cmd_box = _f(cmd_frame, "line")
            cmd_box.pack(side="left", fill="x", expand=True)
            cmd_inner = _f(cmd_box, "input")
            cmd_inner.pack(fill="both", expand=True, padx=1, pady=1)
            self._st_label(cmd_inner, ">", bg="input", fg="accent", font=("mono", 12, "bold")).pack(side="left", padx=(12, 4))
            self.entry_cmd = tk.Entry(cmd_inner, font=_sf("mono", 11), bg=t["input"], fg=t["hi"], insertbackground=t["hi"],
                                      bd=0, highlightthickness=0)
            self.entry_cmd._st = {"bg": "input", "fg": "hi", "font": ("mono", 11), "plain": True}
            self.entry_cmd.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
            self.entry_cmd.bind("<Return>", self.on_manual_cmd)
            self.entry_cmd.bind("<Up>", lambda e: self._cmd_history(-1))
            self.entry_cmd.bind("<Down>", lambda e: self._cmd_history(1))
            self._cmd_hist = []
            self._cmd_hist_i = 0
            self._cmd_hint = self._st_label(cmd_inner, "!type hello    Up / Down for history", bg="input", fg="faint", font=("mono", 10), anchor="w")
            self._cmd_hint.bind("<Button-1>", lambda e: self.entry_cmd.focus_set())
            def _hint(e=None):
                try:
                    if self.entry_cmd.get() or self.root.focus_get() is self.entry_cmd:
                        self._cmd_hint.place_forget()
                    else:
                        self._cmd_hint.place(in_=self.entry_cmd, x=2, rely=0.5, anchor="w")
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            self._cmd_hint_update = _hint
            for ev in ("<FocusIn>", "<FocusOut>", "<KeyRelease>"):
                self.entry_cmd.bind(ev, _hint, add="+")
            self.root.after(300, _hint)
            self._st_button(cmd_frame, "Run", self.on_manual_cmd, "primary").pack(side="right", padx=(10, 0), fill="y")
            mwrap = _f(self.tab_music)
            mwrap.pack(fill="both", expand=True, padx=24, pady=20)
            mo, mnow = self._st_card(mwrap)
            mo.pack(fill="x")
            mrow = _f(mnow, "card")
            mrow.pack(fill="x", padx=18, pady=18)
            self._music_art = tk.Canvas(mrow, width=int(64 * S), height=int(64 * S), bd=0, highlightthickness=0, bg=t["card"])
            self._music_art._studio_skip = True
            self._music_art.pack(side="left")
            mtxt = _f(mrow, "card")
            mtxt.pack(side="left", fill="x", expand=True, padx=(16, 10))
            self._st_label(mtxt, "Now playing", fg="muted", font=("ui", 9, "semi"), anchor="w").pack(anchor="w")
            self.lbl_music_playing = self._st_label(mtxt, "Nothing playing", fg="hi", font=("display", 18), anchor="w")
            self.lbl_music_playing.pack(anchor="w", fill="x")
            self.lbl_music_by = self._st_label(mtxt, "Viewers queue songs with !music <url>", fg="faint", font=("ui", 9), anchor="w")
            self.lbl_music_by.pack(anchor="w")
            mctl = _f(mrow, "card")
            mctl.pack(side="right")
            for _txt, _fn, _var in (("Play", lambda: self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY"), "neutral"),
                                    ("Pause", lambda: self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE"), "neutral"),
                                    ("Skip", self._skip_song, "soft")):
                self._st_button(mctl, _txt, _fn, _var, 9).pack(side="left", padx=(6, 0))
            mo2, mnext = self._st_card(mwrap, "Up next")
            mo2.pack(fill="both", expand=True, pady=(12, 0))
            mlist = _f(mnext, "card")
            mlist.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.music_listbox = tk.Listbox(mlist, bg=t["card"], fg=t["text"], font=_sf("ui", 11), bd=0, highlightthickness=0,
                                            activestyle="none")
            self.music_listbox._st = {"bg": "card", "fg": "text", "font": ("ui", 11)}
            self.music_listbox.pack(fill="both", expand=True, padx=6)
            self._music_empty = self._st_label(mlist, "The queue is empty", fg="faint", font=("ui", 10))
            self._music_empty.place(relx=0.5, rely=0.4, anchor="center")
            def _paint_art(ph=None):
                cv = self._music_art
                tk_ = self._tok
                cv.delete("all")
                cv.configure(bg=tk_["card"])
                w = int(64 * S)
                playing = bool(getattr(self, "current_song", None))
                glow = 0.0 if ph is None else _breath(ph * 2 % 1.0)
                _rrect(cv, 1, 1, w - 1, w - 1, 12 * S, fill=tk_["accent_tint"],
                       outline=mix(tk_["accent_edge"], tk_["accent"], 0.6 * glow))
                if playing and ph is not None and MOTION.ambient:
                    n = 5
                    bw = 5 * S
                    gap = 3.5 * S
                    total = n * bw + (n - 1) * gap
                    x0 = (w - total) / 2.0
                    base = w - 16 * S
                    maxh = w - 32 * S
                    for i in range(n):
                        a = abs(math.sin(2 * math.pi * (ph * (1.0 + i * 0.37) + i * 0.21)))
                        b = abs(math.sin(2 * math.pi * (ph * (2.1 - i * 0.23) + i * 0.53)))
                        hh = maxh * (0.18 + 0.82 * (0.6 * a + 0.4 * b))
                        x = x0 + i * (bw + gap)
                        _rrect(cv, x, base - hh, x + bw, base, 2 * S, fill=mix(tk_["accent_text"], tk_["hi"], 0.15 * (i % 2)), outline="")
                else:
                    _draw_icon(cv, "note", w / 2.0, w / 2.0, 30 * S, tk_["accent_text"], tk_["accent_tint"], w=2.0 * S)
            self._paint_music_art = _paint_art
            def _eq(ph):
                if getattr(self.tabview, "_current", None) is self.tab_music:
                    _paint_art(ph)
            self._music_eq = _eq
            self._repaint_hooks.append(_paint_art)

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
                elif _vle:
                    self.cb_vm_new['values'] = [f"(no VMs - {_vle[:40]})"]
                refresh_snaps()
            tk.Button(vm_frame, text="Refresh", font=("Segoe UI", 10, "bold"), bg="#27272A", fg="white", activebackground="#3F3F46", activeforeground="white", bd=0, cursor="hand2", command=refresh_vms).pack(side="left", ipady=5, ipadx=15)
            refresh_vms()
            self.cb_vm_new.bind("<<ComboboxSelected>>", refresh_snaps)
            tk.Button(vbox_content, text="Save VM Configuration", font=("Segoe UI", 11, "bold"), bg="#10B981", fg="#000000", activebackground="#059669", activeforeground="#000000", bd=0, cursor="hand2", command=self.save_vbox_settings).grid(row=8, column=1, sticky="w", pady=40, ipady=8, ipadx=20)
            try: self.build_commands_tab()
            except Exception as _e: log_crash('tab build_commands_tab', _e)
            sett_wrapper = self.make_scrollable(self.tab_sett)
            sett_card_border = tk.Frame(sett_wrapper, bg="#27272A")
            sett_card_border.pack(pady=24, padx=28, fill="x")
            sett_content = tk.Frame(sett_card_border, bg="#18181B", padx=20, pady=20)
            sett_content.pack(fill="both", expand=True, padx=1, pady=1)
            sett_cols = tk.Frame(sett_content, bg="#18181B")
            sett_cols.pack(fill="both", expand=True)
            sett_left = tk.Frame(sett_cols, bg="#18181B")
            sett_left.pack(side="top", fill="x", anchor="w")
            sett_right = tk.Frame(sett_cols, bg="#18181B")
            sett_right.pack(side="top", fill="x", anchor="w", pady=(26, 0))
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
            tk.Label(sett_right, text="CHAT LOAD", font=("Segoe UI", 12, "bold"), bg="#18181B", fg=self.accent_main).grid(row=6, column=0, columnspan=2, sticky="w", pady=(26, 4))
            self._load_entries = {}
            for _r, (_key, _lbl, _dflt) in enumerate((("viewer_cooldown", "Viewer cooldown (s)", 1.5),
                                                       ("queue_per_user", "Commands waiting per viewer", 2),
                                                       ("queue_max_age", "Drop commands older than (s)", 30),
                                                       ("music_queue_max", "Songs waiting to download", 8)), start=7):
                tk.Label(sett_right, text=_lbl, font=("Segoe UI", 11, "bold"), bg="#18181B", fg="#D4D4D8").grid(row=_r, column=0, sticky="e", pady=10, padx=(0, 20))
                _e = tk.Entry(sett_right, width=15, font=("Consolas", 12), bg="#09090B", fg="white", insertbackground="white", bd=0, highlightthickness=1, highlightbackground="#27272A", highlightcolor="#10B981", justify="center")
                _e.grid(row=_r, column=1, sticky="w", pady=10, ipady=5)
                _e.insert(0, str(self.config.get(_key, _dflt)))
                self._load_entries[_key] = (_e, _dflt)
            tk.Label(sett_right, text="With a busy chat each viewer gets a turn in order. A viewer's newest commands replace their oldest waiting ones, and anything that waits too long is skipped. Mods and you always go first.",
                     font=("Segoe UI", 9), bg="#18181B", fg="#A1A1AA", justify="left", wraplength=520).grid(row=11, column=0, columnspan=2, sticky="w", pady=(4, 0))
            btn_save_frame = tk.Frame(sett_content, bg="#18181B")
            btn_save_frame.pack(fill="x", pady=(20, 0))
            tk.Button(btn_save_frame, text="SAVE ALL SETTINGS", font=("Segoe UI", 11, "bold"), bg=self.accent_main, fg="black", activebackground=self.accent_hover, activeforeground="black", bd=0, cursor="hand2", command=self.save_general_settings).pack(ipady=8, ipadx=40)
            for _tab in ("build_extra_tab", "build_osvoting_tab", "build_realpc_tab", "build_automation_tab", "build_eventlog_tab", "build_appearance_tab", "build_obs_tab", "build_keys_tab", "build_mouse_tab", "build_macros_tab", "build_moderation_tab", "build_snapshots_tab", "build_overlays_tab", "build_chattools_tab", "build_system_tab", "build_replay_tab", "build_media_tab", "build_quicktype_tab", "build_winapps_tab", "build_backup_tab", "build_help_tab", "build_vms_tab", "build_diagnostics_tab", "build_discord_tab", "build_plugins_tab", "build_market_tab", "build_plugindocs_tab"):
                self._build_tab(_tab)
            self._bind_secret_replay()
            self._promote_page_titles()
            self._studio_finish()
        except Exception as e:
            self.log("[system]", f"[error] ui build error: {e}", "err")
            console_log("ERROR", f"[error] ui build error: {e}\n{traceback.format_exc()}")

    def _studio_init(self):
        _studio_pick_fonts(self.root)
        try:
            self._ui_scale = max(1.0, min(2.5, float(self.root.winfo_fpixels("1i")) / 96.0))
        except Exception:
            self._ui_scale = 1.0
        _STUDIO["delta"] = int(self.config.get("ui_text_size", 0) or 0)
        self._st_orig = {}
        self._scroll_canvases = set()
        default_acc = "#8B5CF6" if self.is_multistream else None
        acc = self.config.get("accent_color") or default_acc
        name = self.config.get("ui_theme", "original")
        if name not in _STUDIO_BASE:
            name = "original"
        self.ui_theme = name
        tok = _studio_resolve(name, acc)
        _STUDIO["tok"] = tok
        _STUDIO["on"] = True
        self._tok = tok
        self.accent_main = tok["accent"]
        self.accent_hover = tok["accent_hover"]
        _STUDIO["accent_seen"].update({_hx(tok["accent"]), "#00e5ff", "#00b3cc"})
        self._theme_palette = tok
        try:
            self.root.configure(bg=tok["bg"])
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self._style_ttk()
        try:
            self.root.bind_all("<MouseWheel>", self._wheel_router, add="+")
            self.root.bind_all("<Button-4>", self._wheel_router, add="+")
            self.root.bind_all("<Button-5>", self._wheel_router, add="+")
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        plog("UI", f"studio ui: theme={name} accent={tok['accent']} scale={self._ui_scale:.2f} text_size={_STUDIO['delta']:+d}")

    def _style_ttk(self):
        t = self._tok
        try:
            style = ttk.Style()
            names = list(style.theme_names())
            if platform.system() != "Darwin" and "clam" in names and style.theme_use() != "clam":
                style.theme_use("clam")
            style.configure(".", background=t["bg"], foreground=t["text"], fieldbackground=t["input"],
                            bordercolor=t["line"], lightcolor=t["card"], darkcolor=t["card"], troughcolor=t["bg"],
                            selectbackground=t["sel"], selectforeground=t["hi"], insertcolor=t["hi"],
                            focuscolor=t["accent"], font=_sf("ui", 10))
            style.configure("TFrame", background=t["bg"])
            style.configure("Card.TFrame", background=t["card"])
            style.configure("TLabel", background=t["bg"], foreground=t["text"], font=_sf("ui", 10))
            style.configure("Header.TLabel", background=t["bg"], foreground=t["hi"], font=_sf("display", 15))
            style.configure("TCombobox", fieldbackground=t["input"], background=t["raised"], foreground=t["hi"],
                            arrowcolor=t["muted"], bordercolor=t["line"], lightcolor=t["input"], darkcolor=t["input"],
                            selectbackground=t["input"], selectforeground=t["hi"], padding=(8, 5), arrowsize=13,
                            insertcolor=t["hi"])
            style.map("TCombobox",
                      fieldbackground=[("readonly", t["input"]), ("disabled", t["card"])],
                      foreground=[("readonly", t["hi"]), ("disabled", t["faint"])],
                      background=[("active", t["raised_hover"]), ("pressed", t["raised_hover"])],
                      bordercolor=[("focus", t["accent"]), ("active", t["muted"])],
                      arrowcolor=[("active", t["hi"])],
                      selectbackground=[("focus", t["input"])], selectforeground=[("focus", t["hi"])])
            for orient in ("Vertical", "Horizontal"):
                sn = f"{orient}.TScrollbar"
                try:
                    style.layout(sn, [(f"{orient}.Scrollbar.trough", {"sticky": "ns" if orient == "Vertical" else "we",
                                       "children": [(f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                style.configure(sn, background=t["raised"], troughcolor=t["bg"], bordercolor=t["bg"],
                                lightcolor=t["raised"], darkcolor=t["raised"], arrowcolor=t["muted"],
                                gripcount=0, arrowsize=int(9 * self._ui_scale), relief="flat")
                style.map(sn, background=[("pressed", t["muted"]), ("active", t["raised_hover"])],
                          lightcolor=[("active", t["raised_hover"])], darkcolor=[("active", t["raised_hover"])])
            style.configure("TButton", background=t["raised"], foreground=t["text"], bordercolor=t["line"],
                            lightcolor=t["raised"], darkcolor=t["raised"], padding=(12, 6), font=_sf("ui", 10, "semi"))
            style.map("TButton", background=[("active", t["raised_hover"])], foreground=[("active", t["hi"])])
            style.configure("TEntry", fieldbackground=t["input"], foreground=t["hi"], bordercolor=t["line"],
                            lightcolor=t["input"], darkcolor=t["input"], insertcolor=t["hi"], padding=6)
            style.map("TEntry", bordercolor=[("focus", t["accent"])])
            style.configure("TSpinbox", fieldbackground=t["input"], foreground=t["hi"], bordercolor=t["line"],
                            background=t["raised"], arrowcolor=t["muted"], lightcolor=t["input"], darkcolor=t["input"])
            style.configure("Treeview", background=t["input"], fieldbackground=t["input"], foreground=t["text"],
                            bordercolor=t["line"], rowheight=int(26 * self._ui_scale), font=_sf("ui", 10))
            style.configure("Treeview.Heading", background=t["card"], foreground=t["muted"], relief="flat",
                            bordercolor=t["line"], font=_sf("ui", 9, "semi"))
            style.map("Treeview", background=[("selected", t["sel"])], foreground=[("selected", t["hi"])])
            style.configure("TProgressbar", troughcolor=t["input"], background=t["accent"], bordercolor=t["line"],
                            lightcolor=t["accent"], darkcolor=t["accent"], thickness=6)
            style.configure("TNotebook", background=t["bg"], borderwidth=0)
            style.configure("TNotebook.Tab", background=t["card"], foreground=t["muted"], padding=[12, 6],
                            font=_sf("ui", 9, "semi"), borderwidth=0)
            style.map("TNotebook.Tab", background=[("selected", t["raised"])], foreground=[("selected", t["hi"])])
            for base in ("TCheckbutton", "TRadiobutton", "Toggle.TCheckbutton"):
                style.configure(base, background=t["bg"], foreground=t["text"], font=_sf("ui", 10),
                                indicatorbackground=t["input"], indicatorforeground=t["on_accent"],
                                upperbordercolor=t["line"], lowerbordercolor=t["line"], indicatormargin=(0, 0, 8, 0),
                                focuscolor=t["bg"])
                style.map(base, indicatorbackground=[("selected", t["accent"]), ("active", t["raised"])],
                          background=[("active", t["bg"])], foreground=[("active", t["hi"])],
                          upperbordercolor=[("selected", t["accent"])], lowerbordercolor=[("selected", t["accent"])])
            self._ttk_bg_styles = {}
            try:
                self._make_indicators()
            except Exception as e:
                plog("UI", f"indicator images failed: {e}")
            for opt, val in (("background", t["card"]), ("foreground", t["text"]), ("selectBackground", t["sel"]),
                             ("selectForeground", t["hi"]), ("font", _sf("ui", 10))):
                self.root.option_add(f"*TCombobox*Listbox.{opt}", val)
        except Exception as e:
            plog("UI", f"ttk styling failed: {type(e).__name__}: {e}")

    def _style_ttk_check(self, w, bg):
        t = self._tok
        try:
            cls = w.winfo_class()
        except Exception:
            return
        if cls not in ("TCheckbutton", "TRadiobutton", "TLabel"):
            return
        if cls in ("TCheckbutton", "TRadiobutton", "TLabel"):
            try:
                txt = str(w.cget("text"))
                if _is_caps_label(txt.split(" (")[0]) and len(txt.split(" (")[0]) > 3:
                    head, _, tail = txt.partition(" (")
                    w.configure(text=_sentence_case(head) + ((" (" + tail) if tail else ""))
            except Exception:
                pass
        key = (cls, _hx(bg))
        cache = getattr(self, "_ttk_bg_styles", None)
        if cache is None:
            cache = self._ttk_bg_styles = {}
        name = cache.get(key)
        style = ttk.Style()
        if name is None:
            name = f"st{len(cache)}.{cls}"
            cache[key] = name
        if cls == "TLabel":
            try: orig = str(w.cget("style"))
            except Exception: orig = ""
            hdr = "Header" in orig or getattr(w, "_st_header", False)
            if hdr:
                w._st_header = True
                name = name.replace(".TLabel", "H.TLabel")
            style.configure(name, background=bg, foreground=t["hi"] if hdr else t["text"],
                            font=_sf("display", 15) if hdr else _sf("ui", 10))
        else:
            style.configure(name, background=bg, foreground=t["text"], font=_sf("ui", 10),
                            indicatorbackground=t["input"], indicatorforeground=t["on_accent"],
                            upperbordercolor=t["line"], lowerbordercolor=t["line"], indicatormargin=(0, 0, 8, 0),
                            focuscolor=bg, padding=(0, 3, 4, 3))
            style.map(name, indicatorbackground=[("selected", t["accent"]), ("active", t["raised"])],
                      background=[("active", bg)], foreground=[("active", t["hi"])],
                      upperbordercolor=[("selected", t["accent"])], lowerbordercolor=[("selected", t["accent"])])
        try:
            w.configure(style=name)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _style_scrollbar(self, sb, bg):
        t = self._tok
        try:
            orient = str(sb.cget("orient"))
        except Exception:
            orient = "vertical"
        base = "Vertical.TScrollbar" if orient == "vertical" else "Horizontal.TScrollbar"
        cache = getattr(self, "_ttk_bg_styles", None)
        if cache is None:
            cache = self._ttk_bg_styles = {}
        key = ("sb", orient, _hx(bg))
        names = cache.get(key)
        style = ttk.Style()
        if names is None:
            n = len(cache)
            names = (f"sb{n}.{base}", f"sbi{n}.{base}")
            cache[key] = names
            style.configure(names[0], troughcolor=bg, bordercolor=bg, background=t["raised"], lightcolor=t["raised"],
                            darkcolor=t["raised"], gripcount=0, arrowsize=int(9 * self._ui_scale))
            style.map(names[0], background=[("pressed", t["muted"]), ("active", t["raised_hover"])],
                      lightcolor=[("active", t["raised_hover"])], darkcolor=[("active", t["raised_hover"])])
            style.configure(names[1], troughcolor=bg, bordercolor=bg, background=bg, lightcolor=bg, darkcolor=bg,
                            gripcount=0, arrowsize=int(9 * self._ui_scale))
            style.map(names[1], background=[("pressed", bg), ("active", bg)],
                      lightcolor=[("active", bg)], darkcolor=[("active", bg)])
        sb._st_styles = names
        sb._st_cur = None
        try:
            first, last = sb.get()[:2]
            idle = float(first) <= 0.0 and float(last) >= 1.0
            want = names[1] if idle else names[0]
            sb._st_cur = want
            ttk.Scrollbar.configure(sb, style=want)
        except Exception:
            try: ttk.Scrollbar.configure(sb, style=names[0])
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _make_indicators(self):
        t = self._tok
        s = max(13, int(round(14 * self._ui_scale)))
        def inside_rr(px, py, x0, y0, x1, y1, r):
            cx = min(max(px, x0 + r), x1 - r)
            cy = min(max(py, y0 + r), y1 - r)
            return (px - cx) ** 2 + (py - cy) ** 2 <= r * r + 0.01 if (px < x0 + r or px > x1 - r) and (py < y0 + r or py > y1 - r) else (x0 <= px <= x1 and y0 <= py <= y1)
        def seg_d(px, py, ax, ay, bx, by):
            dx, dy = bx - ax, by - ay
            L = dx * dx + dy * dy
            u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L)) if L else 0.0
            qx, qy = ax + u * dx, ay + u * dy
            return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5
        def build(kind, on, hover):
            im = tk.PhotoImage(master=self.root, width=s, height=s)
            edge = t["accent"] if on else (t["muted"] if hover else mix(t["line"], t["muted"], 0.45))
            fill = t["accent"] if on else t["input"]
            mark = t["on_accent"]
            pts = []
            for y in range(s):
                for x in range(s):
                    px, py = x + 0.5, y + 0.5
                    if kind == "chk":
                        outer = inside_rr(px, py, 0.5, 0.5, s - 0.5, s - 0.5, 3.0)
                        inner = inside_rr(px, py, 1.5, 1.5, s - 1.5, s - 1.5, 2.0)
                    else:
                        c = s / 2.0
                        dd = ((px - c) ** 2 + (py - c) ** 2) ** 0.5
                        outer = dd <= c - 0.3
                        inner = dd <= c - 1.3
                    if not outer:
                        continue
                    col = fill if inner else edge
                    if on and inner:
                        if kind == "chk":
                            d = min(seg_d(px, py, s * 0.26, s * 0.52, s * 0.43, s * 0.70),
                                    seg_d(px, py, s * 0.43, s * 0.70, s * 0.76, s * 0.31))
                            if d <= 0.95:
                                col = mark
                        else:
                            c = s / 2.0
                            if ((px - c) ** 2 + (py - c) ** 2) ** 0.5 <= s * 0.2:
                                col = mark
                    pts.append((x, y, col))
            for x, y, col in pts:
                im.put(col, to=(x, y))
            return im
        gen = getattr(self, "_ind_gen", 0) + 1
        self._ind_gen = gen
        imgs = {}
        for kind in ("chk", "rad"):
            imgs[kind] = (build(kind, False, False), build(kind, False, True), build(kind, True, False))
        self._ind_imgs = imgs
        style = ttk.Style()
        for kind, cls in (("chk", "Checkbutton"), ("rad", "Radiobutton")):
            off, hov, on = imgs[kind]
            el = f"st{gen}{kind}.indicator"
            try:
                style.element_create(el, "image", off, ("selected", on), ("active", hov), width=s + 9, sticky="w")
                lay = [(f"{cls}.padding", {"sticky": "nswe", "children": [
                    (el, {"side": "left", "sticky": ""}),
                    (f"{cls}.focus", {"side": "left", "sticky": "w", "children": [(f"{cls}.label", {"sticky": "nswe"})]})]})]
                style.layout(f"T{cls}", lay)
                if cls == "Checkbutton":
                    style.layout("Toggle.TCheckbutton", lay)
            except Exception as e:
                plog("UI", f"custom {cls.lower()} indicator failed: {e}")

    _ST_OPTS = ("background", "foreground", "font", "text", "highlightthickness", "padx", "pady")

    def _st_capture(self, w):
        o = {"_cls": w.winfo_class()}
        for opt in self._ST_OPTS:
            try:
                o[opt] = str(w.cget(opt))
            except Exception:
                pass
        t = getattr(self, "_tok", None)
        if t:
            if "background" in o:
                bgv = _hx(o["background"])
                for role in ("bg", "side", "panel", "card", "input", "raised", "line", "accent_tint", "ok_tint",
                             "bad_tint", "warn_tint", "violet_tint", "info_tint", "raised_hover", "sel"):
                    if _hx(t.get(role, "")) == bgv:
                        o["_tokbg"] = role
                        break
            if "foreground" in o:
                for role in ("hi", "text", "muted", "faint", "ok", "bad", "warn", "violet", "info"):
                    if _hx(t[role]) == _hx(o["foreground"]):
                        o["_tokfg"] = role
                        break
                if "_tokfg" not in o and _hx(o["foreground"]) == _hx(t.get("accent_text", "")):
                    o["_tokfg"] = "accent"
        if o["_cls"] == "Text":
            tags = {}
            try:
                for tg in w.tag_names():
                    if tg == "sel":
                        continue
                    tags[tg] = (str(w.tag_cget(tg, "foreground")), str(w.tag_cget(tg, "background")), str(w.tag_cget(tg, "font")))
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            o["_tags"] = tags
        return o

    def _st_font(self, o, cls, ex):
        f = o.get("font")
        if not f:
            return None, None
        try:
            parts = self.root.tk.splitlist(f)
        except Exception:
            return None, None
        if len(parts) < 2:
            return None, None
        fam = str(parts[0]).lower()
        try:
            size = abs(int(parts[1]))
        except Exception:
            return None, None
        bold = any(str(x).lower() == "bold" for x in parts[2:])
        mono = any(k in fam for k in ("consolas", "courier", "mono", "cascadia"))
        return (fam, size, bold, mono), None

    def _st_widget(self, x, pbg, force):
        key = str(x)
        o = self._st_orig.get(key)
        if o is not None and not force:
            return o.get("_bg") or pbg
        if o is None:
            o = self._st_capture(x)
            self._st_orig[key] = o
        t = self._tok
        ex = getattr(x, "_st", None) or {}
        cls = o["_cls"]
        if isinstance(x, RoundedButton):
            size = 10
            if ex.get("font"):
                font = _sf(*ex["font"])
            else:
                try:
                    fparts = self.root.tk.splitlist(str(x._font)) if not isinstance(x._font, tuple) else x._font
                    size = abs(int(fparts[1]))
                except Exception:
                    size = 10
                font = _sf("ui", 9 if size <= 9 else (10 if size <= 11 else 11), "semi")
            if ex.get("variant"):
                x._variant = ex["variant"]
            x.studio_style(pbg, font)
            o["_bg"] = pbg
            return pbg
        if isinstance(x, GlassCard):
            x.configure(bg=pbg)
            x.set_tint(t[ex.get("bg", "card")], t["line"])
            o["_bg"] = t[ex.get("bg", "card")]
            return pbg
        if cls.startswith("T") and cls[1:2].isupper():
            if cls == "TScrollbar":
                self._style_scrollbar(x, pbg)
                return pbg
            if cls == "TFrame":
                return t["bg"] if not ex.get("bg") else t[ex["bg"]]
            if cls in ("TCheckbutton", "TRadiobutton", "TLabel"):
                self._style_ttk_check(x, pbg)
            return pbg
        kw = {}
        bg_role = ex.get("bg")
        if bg_role is None and cls == "Frame":
            try:
                for k in x.winfo_children():
                    if isinstance(k, tk.Text) and getattr(k, "frame", None) is x:
                        bg_role = (getattr(k, "_st", None) or {}).get("bg", "input")
                        break
            except Exception:
                pass
        if bg_role is None and "background" in o:
            bg_role = _studio_bg_role(o["background"], cls)
            if bg_role is None and o.get("_tokbg"):
                bg_role = o["_tokbg"]
            if bg_role is None and cls in ("Label", "Checkbutton", "Radiobutton", "Message", "Canvas", "Scale"):
                bg_role = "parent"
            elif cls in ("Label", "Checkbutton", "Radiobutton", "Message", "Scale") and bg_role in ("bg", "card", "panel", "side", "input"):
                bg_role = "parent"
        newbg = None
        if bg_role == "parent":
            newbg = pbg
        elif bg_role:
            newbg = t.get(bg_role)
        if cls in ("Entry", "Spinbox", "Text", "Listbox") and not ex.get("bg"):
            newbg = t["input"] if cls != "Text" or bg_role not in ("panel",) else t["panel"]
        if newbg:
            kw["background"] = newbg
        fg_role = ex.get("fg") or (_studio_fg_role(o.get("foreground")) if "foreground" in o else None) or o.get("_tokfg")
        if fg_role == "on_accent" and bg_role != "accent":
            fg_role = "hi"
        if cls in ("Entry", "Spinbox") and not ex.get("fg"):
            fg_role = "hi"
        if cls in ("Text", "Listbox") and not ex.get("fg"):
            fg_role = fg_role if fg_role in ("ok", "bad", "warn", "violet", "info", "accent") else "text"
        if fg_role and "foreground" in o:
            kw["foreground"] = _studio_color(fg_role)
        finfo, _ = self._st_font(o, cls, ex) if not ex.get("font") else (None, None)
        text = o.get("text", "")
        if ex.get("font"):
            kw["font"] = _sf(*ex["font"])
        elif finfo:
            fam, size, bold, mono = finfo
            if cls == "Label" and bold and size >= 13 and size < 26 and not mono:
                kw["font"] = _sf("display", 16 if size <= 14 else (19 if size <= 18 else 22))
                if fg_role in (None, "accent", "hi", "text", "ok", "muted", "violet", "info", "warn"):
                    kw["foreground"] = t["hi"]
            elif cls == "Label" and bold and _is_caps_label(text) and size <= 12 and not mono:
                kw["font"] = _sf("ui", 9 if size <= 9 else 10, "semi")
                if fg_role in (None, "accent", "ok", "muted", "text", "hi", "violet"):
                    kw["foreground"] = t["muted"]
            elif mono:
                kw["font"] = _sf("mono", max(8, size), "bold" if bold else "normal")
            elif cls == "Label" and bold and size >= 11 and size < 13:
                kw["font"] = _sf("ui", 10, "semi")
                if fg_role in (None, "hi", "text"):
                    kw["foreground"] = t["text"]
            elif size < 26:
                kw["font"] = _sf("ui", max(8, size), "semi" if bold else "normal")
        if cls in ("Label", "Checkbutton", "Radiobutton", "Message") and text and _is_caps_label(text):
            kw["text"] = _sentence_case(text)
        if cls in ("Entry", "Spinbox"):
            kw.update(insertbackground=t["hi"], relief="flat", bd=0, highlightthickness=0 if ex.get("plain") else 1,
                      highlightbackground=t["line"], highlightcolor=t["accent"], selectbackground=t["sel"],
                      selectforeground=t["hi"], disabledbackground=t["card"], disabledforeground=t["faint"],
                      readonlybackground=t["input"])
            if cls == "Spinbox":
                kw.update(buttonbackground=t["raised"])
        elif cls == "Text":
            kw.update(insertbackground=t["hi"], relief="flat", bd=0, selectbackground=t["sel"],
                      selectforeground=t["hi"], inactiveselectbackground=t["sel"],
                      highlightthickness=1 if o.get("highlightthickness") not in ("0", "") else 0,
                      highlightbackground=t["line"], highlightcolor=t["line"])
            try:
                if int(float(o.get("padx", "0") or 0)) < 8: kw["padx"] = 10
                if int(float(o.get("pady", "0") or 0)) < 6: kw["pady"] = 8
            except Exception:
                pass
            for tg, (tfg, tbg, tfont) in (o.get("_tags") or {}).items():
                try:
                    r = _studio_fg_role(tfg) if tfg else None
                    if r:
                        x.tag_config(tg, foreground=_studio_color(r))
                    rb = _studio_bg_role(tbg, "Label") if tbg else None
                    if rb:
                        x.tag_config(tg, background=_studio_color(rb))
                    if tfont:
                        tp = self.root.tk.splitlist(tfont)
                        if len(tp) >= 2:
                            fam = str(tp[0]).lower()
                            m = any(k in fam for k in ("consolas", "courier", "mono", "cascadia"))
                            b = any(str(q).lower() == "bold" for q in tp[2:])
                            x.tag_config(tg, font=_sf("mono" if m else "ui", abs(int(tp[1])), "bold" if (b and m) else ("semi" if b else "normal")))
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            try:
                fr = getattr(x, "frame", None)
                if fr is not None:
                    fr.configure(bg=newbg or t["input"])
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        elif cls == "Listbox":
            kw.update(selectbackground=t["sel"], selectforeground=t["hi"], highlightthickness=1,
                      highlightbackground=t["line"], highlightcolor=t["line"], relief="flat", bd=0, activestyle="none")
        elif cls in ("Checkbutton", "Radiobutton"):
            kw.update(activebackground=newbg or pbg, activeforeground=t["hi"], selectcolor=t["input"],
                      highlightthickness=0, bd=0)
        elif cls == "Scale":
            kw.update(troughcolor=t["input"], highlightthickness=0, activebackground=t["accent"], bd=0)
        elif cls in ("Menubutton",):
            kw.update(activebackground=t["raised_hover"], activeforeground=t["hi"], relief="flat", highlightthickness=0)
        elif cls == "Canvas":
            kw.pop("foreground", None)
        elif cls in ("Frame", "Toplevel", "Labelframe"):
            kw.pop("foreground", None) if cls != "Labelframe" else None
            if (cls == "Frame" and not ex and newbg and _hx(newbg) == _hx(t["card"])
                    and _hx(pbg) in (_hx(t["bg"]), _hx(t["panel"]))):
                kw.update(highlightthickness=1, highlightbackground=t["line"], highlightcolor=t["line"])
                if not getattr(x, "_mo_glow", False):
                    x._mo_glow = True
                    _mo_border_glow(x)
        try:
            x.configure(**kw)
        except Exception:
            for k, v in kw.items():
                try: x.configure(**{k: v})
                except Exception: pass
        o["_bg"] = newbg or (pbg if cls in ("Label", "Checkbutton", "Radiobutton") else None)
        if cls in ("Frame", "Toplevel", "Labelframe", "Canvas"):
            try: o["_bg"] = str(x.cget("background"))
            except Exception: pass
        return o["_bg"] or pbg

    def _st_walk(self, root_w, parent_bg, force=False):
        n = 0
        stack = [(root_w, parent_bg)]
        while stack:
            w, pbg = stack.pop()
            if getattr(w, "_studio_skip_tree", False):
                continue
            try:
                if type(w).__module__.startswith("customtkinter"):
                    continue
            except Exception:
                pass
            mybg = pbg
            if not getattr(w, "_studio_skip", False):
                try:
                    mybg = self._st_widget(w, pbg, force) or pbg
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                n += 1
            else:
                try: mybg = str(w.cget("bg"))
                except Exception: pass
            try:
                kids = w.winfo_children()
            except Exception:
                kids = []
            for k in kids:
                stack.append((k, mybg))
        return n

    def _studio_restyle(self, force=False, target=None):
        t0 = time.time()
        n = self._st_walk(target or self.root, self._tok["bg"], force)
        el = time.time() - t0
        if force or el > 0.15:
            plog("UI", f"styled {n} widgets in {el*1000:.0f}ms")
        return n

    def _on_page_shown(self, page):
        if getattr(self, "_studio_ready", False):
            self._st_walk(page, self._tok["bg"], False)
        if page is getattr(self, "tab_dash", None):
            self._dash_enter()
        else:
            MOTION.unloop("sparkpulse", rest=False)
            MOTION.unloop("health", rest=True)
            for _c in getattr(self, "_metric", {}).values():
                try: _c["cv"].delete("pulse")
                except Exception: pass

    def _register_scroll(self, canvas):
        try:
            self._scroll_canvases.add(str(canvas))
        except Exception:
            pass

    def _smooth_scroll(self, cv, d):
        try:
            sr = [float(x) for x in str(cv.cget("scrollregion")).split()]
            total = (sr[3] - sr[1]) if len(sr) == 4 else 0.0
            view = float(cv.winfo_height())
        except Exception:
            total = 0.0
            view = 0.0
        if not MOTION.on or total <= view or total <= 0:
            cv.yview_scroll(d * 3, "units")
            return
        key = ("scroll", str(cv))
        first = float(cv.yview()[0])
        pend = getattr(self, "_scroll_targets", {})
        self._scroll_targets = pend
        base = pend.get(key, first) if MOTION.busy(key) else first
        step_px = 64.0 * abs(d)
        target = base + (step_px if d > 0 else -step_px) / total
        target = max(0.0, min(1.0 - view / total, target))
        pend[key] = target
        MOTION.tween(key, 220, lambda v, c=cv: c.yview_moveto(v), target, a=first, ease=_ease_out_cubic)

    def _wheel_router(self, e):
        try:
            w = self.root.winfo_containing(e.x_root, e.y_root)
        except Exception:
            return None
        hops = 0
        while w is not None and hops < 60:
            hops += 1
            try:
                cls = w.winfo_class()
            except Exception:
                return None
            if cls in ("Text", "Listbox", "Treeview", "TCombobox", "Entry", "Spinbox"):
                return None
            if str(w) in self._scroll_canvases:
                try:
                    first, last = w.yview()
                    if first <= 0.0 and last >= 1.0:
                        return None
                    if getattr(e, "num", 0) == 4:
                        d = -1
                    elif getattr(e, "num", 0) == 5:
                        d = 1
                    else:
                        d = -1 if e.delta > 0 else 1
                        d *= max(1, abs(int(e.delta)) // 120)
                    self._smooth_scroll(w, d)
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                return "break"
            w = getattr(w, "master", None)
        return None

    def _studio_keys(self):
        nav = getattr(self, "tabview", None)
        if nav is None:
            return
        try:
            self.root.bind_all("<Control-k>", nav.focus_search)
            self.root.bind_all("<Control-K>", nav.focus_search)
            self.root.bind_all("<Control-p>", nav.focus_search)
            self.root.bind_all("<Control-j>", nav.toggle_chat_pane)
            self.root.bind_all("<Control-J>", nav.toggle_chat_pane)
            self.root.bind_all("<Control-Tab>", lambda e: (nav.step(1), "break")[1])
            _orig_next = str(self.root.bind_all("<<NextWindow>>") or "")
            def _next_window(e):
                try:
                    st = int(e.state) if str(e.state).isdigit() else 0
                except Exception:
                    st = 0
                if st & 0x4:
                    nav.step(1)
                    return "break"
                if _orig_next:
                    try:
                        self.root.tk.eval(_orig_next.replace("%W", str(e.widget)))
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
                return "break"
            self.root.bind_all("<<NextWindow>>", _next_window)
            self.root.bind_all("<Control-Shift-Tab>", lambda e: (nav.step(-1), "break")[1])
            try: self.root.bind_all("<Control-ISO_Left_Tab>", lambda e: (nav.step(-1), "break")[1])
            except Exception: pass
            def _focus_cmd(e=None):
                try:
                    nav.palette.close()
                    nav.select(self.tab_dash)
                    self.root.after(40, self.entry_cmd.focus_set)
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                return "break"
            self.root.bind_all("<Control-l>", _focus_cmd)
            self.root.bind_all("<Control-L>", _focus_cmd)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _run_repaint_hooks(self):
        for fn in list(getattr(self, "_repaint_hooks", [])):
            try:
                fn()
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        try: self._draw_sparks()
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _promote_page_titles(self):
        self._page_desc = {}
        nav = getattr(self, "tabview", None)
        if nav is None:
            return
        hidden = 0
        for frame, label in nav._pages:
            try:
                stack = [frame]
                order = []
                while stack and len(order) < 60:
                    w = stack.pop(0)
                    order.append(w)
                    stack = list(w.winfo_children()) + stack
                title = None
                for w in order:
                    if w.winfo_class() != "Label":
                        continue
                    try:
                        parts = self.root.tk.splitlist(str(w.cget("font")))
                        size = abs(int(parts[1])) if len(parts) > 1 else 0
                        bold = any(str(x).lower() == "bold" for x in parts[2:])
                    except Exception:
                        continue
                    txt = str(w.cget("text")).strip()
                    if bold and 13 <= size <= 16 and txt and txt.upper() == txt and sum(c.isalpha() for c in txt) >= 3:
                        title = w
                    break
                if title is None:
                    continue
                parent = title.master
                mgr = title.winfo_manager()
                desc = None
                if mgr == "pack":
                    sl = parent.pack_slaves()
                    if title in sl:
                        i = sl.index(title)
                        if i + 1 < len(sl) and sl[i + 1].winfo_class() == "Label":
                            nx = sl[i + 1]
                            try:
                                np_ = self.root.tk.splitlist(str(nx.cget("font")))
                                nsize = abs(int(np_[1])) if len(np_) > 1 else 0
                                nbold = any(str(x).lower() == "bold" for x in np_[2:])
                            except Exception:
                                nsize, nbold = 0, True
                            ntxt = str(nx.cget("text")).strip()
                            if nsize <= 10 and not nbold and len(ntxt) > 20:
                                desc = nx
                    first = sl and sl[0] is title
                    title.pack_forget()
                    if desc is not None:
                        self._page_desc[label] = " ".join(str(desc.cget("text")).split())
                        desc.pack_forget()
                    if first:
                        rest = parent.pack_slaves()
                        if rest:
                            sp = tk.Frame(parent, height=10, bg=str(parent.cget("bg")) if parent.winfo_class() == "Frame" else "#09090B")
                            sp.pack(fill="x", before=rest[0])
                elif mgr == "grid":
                    title.grid_remove()
                hidden += 1
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        plog("UI", f"moved {hidden} in-page titles into the page header ({len(self._page_desc)} descriptions)", verbose=True)

    def _motion_level_name(self):
        if self.config.get("low_power", False):
            return "off"
        lv = str(self.config.get("ui_motion", "full")).lower()
        return lv if lv in ("full", "reduced", "off") else "full"

    def _apply_motion_level(self):
        MOTION.set_level(self._motion_level_name())
        plog("UI", f"motion -> {MOTION.stats()}")
        if MOTION.ambient and getattr(self.tabview, "_current", None) is getattr(self, "tab_dash", None):
            self._dash_enter()
        self._refresh_appearance_marks()

    def set_motion(self, level):
        level = level if level in ("full", "reduced", "off") else "full"
        self.config["ui_motion"] = level
        self.save_settings()
        self._apply_motion_level()
        note = "  Low power mode is on, so it stays off until you turn that off." if self.config.get("low_power", False) and level != "off" else ""
        self.toast(f"Motion set to {level}.{note}", "ok")

    def _mo_focus_rest(self, w):
        gen = _STUDIO.get("gen", 0)
        if getattr(w, "_mo_gen", None) != gen or not hasattr(w, "_mo_hc"):
            w._mo_hc = str(w.cget("highlightcolor"))
            w._mo_hb = str(w.cget("highlightbackground"))
            w._mo_gen = gen
        return w._mo_hc, w._mo_hb

    def _mo_focus_in(self, e):
        w = e.widget
        try:
            if not MOTION.on or int(w.cget("highlightthickness")) <= 0:
                return
            key = ("focus", str(w))
            if not MOTION.busy(key):
                hc, hb = self._mo_focus_rest(w)
            else:
                hc, hb = w._mo_hc, w._mo_hb
            if _hx(hc) == _hx(hb):
                return
            MOTION.color(key, 280, lambda c, w=w: w.configure(highlightcolor=c), hc, frm=hb)
        except Exception:
            pass

    def _mo_focus_out(self, e):
        w = e.widget
        try:
            if not MOTION.on or int(w.cget("highlightthickness")) <= 0 or not hasattr(w, "_mo_hc"):
                return
            hc, hb = w._mo_hc, w._mo_hb
            if _hx(hc) == _hx(hb):
                return
            def done(w=w, hc=hc):
                w.configure(highlightcolor=hc)
            MOTION.color(("focus", str(w)), 320, lambda c, w=w: w.configure(highlightbackground=c), hb, frm=hc, done=done)
        except Exception:
            pass

    def _motion_start(self):
        MOTION.attach(self.root, self._motion_level_name())
        for cls in ("Entry", "Text", "Spinbox"):
            try:
                self.root.bind_class(cls, "<FocusIn>", self._mo_focus_in, add="+")
                self.root.bind_class(cls, "<FocusOut>", self._mo_focus_out, add="+")
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        plog("UI", f"motion engine attached - {MOTION.stats()}")
        def first_frame():
            if MOTION.ambient:
                try:
                    self.root.attributes("-alpha", 0.0)
                    MOTION.tween("startup", 520, lambda v: self.root.attributes("-alpha", max(0.0, min(1.0, v))), 1.0, a=0.0,
                                 ease=_ease_out_cubic, done=lambda: self.root.attributes("-alpha", 1.0))
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                try:
                    self.tabview.shine()
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            if getattr(self.tabview, "_current", None) is getattr(self, "tab_dash", None):
                self._dash_enter()
        def safety():
            try: self.root.attributes("-alpha", 1.0)
            except Exception: pass
        try:
            self.root.after(60, first_frame)
            self.root.after(3000, safety)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _dip(self, fn):
        try:
            viewable = bool(self.root.winfo_viewable())
        except Exception:
            viewable = False
        if not MOTION.ambient or not viewable:
            fn()
            return
        self._dip_fn = fn
        if getattr(self, "_dip_active", False):
            return
        self._dip_active = True
        try:
            had = self.root.focus_get()
        except Exception:
            had = None
        try:
            ov = tk.Toplevel(self.root)
            ov._studio_skip_tree = True
            ov.withdraw()
            ov.overrideredirect(True)
            ov.configure(bg=self._tok["bg"])
            ov.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}")
            try: ov.attributes("-alpha", 0.0)
            except Exception: pass
            try: ov.attributes("-disabled", True)
            except Exception: pass
            ov.deiconify()
            ov.lift()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
            self._dip_active = False
            fn()
            return
        state = {"done": False, "ran": False}
        def kill():
            if state["done"]:
                return
            state["done"] = True
            self._dip_active = False
            if not state["ran"]:
                state["ran"] = True
                try: self._dip_fn()
                except Exception as _ex2:
                    log_crash("theme change", _ex2)
            try: ov.destroy()
            except Exception: pass
            try:
                if had is not None:
                    had.focus_set()
            except Exception:
                pass
        def alpha(v):
            ov.attributes("-alpha", max(0.0, min(1.0, v)))
        def run():
            state["ran"] = True
            try:
                self._dip_fn()
            except Exception as _ex:
                log_crash("theme change", _ex)
            try:
                ov.configure(bg=self._tok["bg"])
            except Exception:
                pass
            MOTION.tween("dip", 300, alpha, 0.0, a=1.0, ease=_ease_in_out, done=kill)
        def mid():
            try:
                ov.update_idletasks()
                self.root.after(1, run)
            except Exception:
                run()
        MOTION.tween("dip", 150, alpha, 1.0, a=0.0, ease=_ease_in_out, done=mid)
        self.root.after(4000, kill)

    def _studio_finish(self):
        self._studio_ready = True
        self._studio_restyle(force=True)
        self._refresh_appearance_marks()
        try: self.tabview.apply_tokens()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        try: self.tabview.select(self.tabview._current)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self._run_repaint_hooks()
        self._motion_start()
        self._studio_keys()
        try: self.root.after(150, lambda: _win_titlebar(self.root, self._tok["dark"]))
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def toast(self, text, kind="info"):
        nav = getattr(self, "tabview", None)
        if nav is not None and hasattr(nav, "toast"):
            self.ui(nav.toast, text, kind)

    def _st_card(self, parent, title=None, pad=16):
        t = self._tok
        outer = tk.Frame(parent, bg=t["line"])
        outer._st = {"bg": "line"}
        card = tk.Frame(outer, bg=t["card"])
        card._st = {"bg": "card"}
        card.pack(fill="both", expand=True, padx=1, pady=1)
        _mo_hover_glow(outer, ("card", str(outer)))
        if title:
            h = tk.Label(card, text=title, bg=t["card"], fg=t["hi"], font=_sf("display", 13), anchor="w")
            h._st = {"bg": "card", "fg": "hi", "font": ("display", 13)}
            h.pack(fill="x", padx=pad, pady=(pad - 2, 8))
        return outer, card

    def _st_label(self, parent, text, bg="card", fg="text", font=("ui", 10), **kw):
        t = self._tok
        l = tk.Label(parent, text=text, bg=t[bg], fg=_studio_color(fg), font=_sf(*font), **kw)
        l._st = {"bg": bg, "fg": fg, "font": font}
        return l

    def _st_button(self, parent, text, command, variant="neutral", size=10):
        b = tk.Button(parent, text=text, command=command, bg="#27272A", fg="white", bd=0, cursor="hand2",
                      font=_sf("ui", size, "semi"))
        b._st = {"variant": variant, "font": ("ui", size, "semi")}
        b._variant = variant
        try: b.studio_style(None, _sf("ui", size, "semi"))
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        return b

    def _build_tab(self, name):
        t0 = time.time()
        try:
            getattr(self, name)()
        except Exception as _e:
            log_crash(f"tab {name}", _e)
            plog("INIT", f"tab {name} FAILED: {type(_e).__name__}: {_e}")
            return
        el = time.time() - t0
        plog("INIT", f"tab {name} built in {el*1000:.0f}ms" + ("  (slow)" if el > 0.5 else ""), verbose=el <= 0.5)

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
            if _active_backend() == "vmware":
                return
            path = self.entry_vbox_new.get().strip() or vbox_manage_cmd
            active_vm = self.cb_vm_new.get()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
            return
        def _work():
            vms = get_all_vbox_vms(path, quiet=True)
            snaps = get_vbox_snapshots(path, active_vm) if active_vm else []
            self.ui(self._apply_vbox_refresh, vms, active_vm, snaps)
        self._run_bg("vbox-refresh", _work)

    def _apply_vbox_refresh(self, vms, active_vm, snaps):
        try:
            if vms:
                current_vm_val = self.cb_vm_new.get()
                if list(self.cb_vm_new['values'] or ()) != list(vms):
                    self.cb_vm_new['values'] = vms
                    plog("VBOX", f"vm list refreshed: {vms}", verbose=True)
                if current_vm_val not in vms and vm_name in vms: self.cb_vm_new.set(vm_name)
            if active_vm and active_vm == self.cb_vm_new.get():
                self.cb_snap_new['values'] = snaps if snaps else [""]
                if self.current_snapshot not in snaps and snaps:
                    self.current_snapshot = snaps[-1]
                    self.cb_snap_new.set(self.current_snapshot)
                    plog("VBOX", f"snapshot target auto-set to {self.current_snapshot!r}")
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def update_say_admin(self):
        self.say_admin_only = self.say_admin_var.get()

    def switch_backend(self, name):
        global _rb
        name = "vmware" if str(name).lower() == "vmware" else "virtualbox"
        plog("BACKEND", f"switching backend -> {name}")
        self.backend = name
        self.config["backend"] = name
        _rb = name
        self.save_settings()
        self._teardown_com_session()
        dbg("backend", f"switched to {name}")
        self.log("[system]", f"backend is now {name.upper()}.", "sysmsg")
        try:
            if hasattr(self, "backend_lbl"):
                self.backend_lbl.config(text=name.upper(), fg=("#8B5CF6" if name == "vmware" else "#10B981"))
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if name == "vmware":
            threading.Thread(target=lambda: self._vmware().connect(), daemon=True, name="vnc-connect-switch").start()

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
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self.save_settings()
        global vm_name, vbox_manage_cmd
        vm_name = self.config["vm_name"]
        vbox_manage_cmd = self.config["vbox_path"]
        self.root.title(f"{self.config.get('app_name', 'YT2VM')} {version}: {vm_name}")
        self.btn_vm.configure(text=f"{vm_name}")
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
        for _key, (_e, _dflt) in getattr(self, "_load_entries", {}).items():
            try:
                _v = float(_e.get())
                if _key in ("queue_per_user", "music_queue_max"): _v = int(max(1, _v))
                elif _v < 0: raise ValueError
                self.config[_key] = _v
            except Exception:
                self.config[_key] = _dflt
        plog("SETTINGS", "chat load: " + ", ".join(f"{k}={self.config.get(k)}" for k in ("viewer_cooldown", "queue_per_user", "queue_max_age", "music_queue_max")))
        self.save_settings()
        global keyboard_layout
        keyboard_layout = self.config["keyboard_layout"]
        self.command_prefix = self.config["command_prefix"]
        self.listening_to_chat = self.config["enable_chat"]
        self.twenty_four_seven_mode = self.config["auto_start"]
        self.app_name = self.config["app_name"]
        try: self.tabview.brand_name.configure(text=self.app_name)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self.ultra_speed = self.config["ultra_speed"]
        self.root.title(f"{self.app_name} {version}: {vm_name}")
        console_log("SYSTEM", "general settings & timings saved!")

    def update_gui_console(self):
        batch = []
        try:
            while len(batch) < 150:
                batch.append(gui_log_queue.get_nowait())
        except queue.Empty:
            pass
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if not batch or not hasattr(self, "console_text"):
            return
        try:
            self.console_text.configure(state='normal')
            for level, msg in batch:
                msg = str(msg)
                if level == "CHAT" and "] [debug] " in msg[:40]:
                    tag = "DEBUG"
                elif level in ("SYSTEM", "ERROR", "EXEC", "CHAT"):
                    tag = level
                else:
                    tag = "OTHER"
                self.console_text.insert(tk.END, msg + "\n", tag)
            try:
                line_count = int(self.console_text.index('end-1c').split('.')[0])
                if line_count > 300: self.console_text.delete('1.0', f'{line_count - 250}.0')
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            self.console_text.see(tk.END)
            self.console_text.configure(state='disabled')
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def update_status_display(self, text, is_error=False):
        global current_status
        if not hasattr(self, '_last_status'): self._last_status = ""
        text_lower = text.lower()
        if self._last_status != text_lower:
            self._last_status = text_lower
            current_status = text_lower
            if hasattr(self, 'lbl_status'):
                _fg = _studio_color("bad" if is_error else "ok", "#10B981")
                self.lbl_status.configure(text=_sentence_case(text_lower), fg=_fg)
                if MOTION.on and threading.current_thread() is threading.main_thread():
                    MOTION.color("mstatus", 600, lambda c: self.lbl_status.configure(fg=c), _fg, frm=self._tok["card"])
            plog("STATUS", text_lower)
            try: gui_log_queue.put_nowait(("status", text_lower))
            except queue.Full: pass

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
            self.log("[system]", f"[warn] no VMs available to switch to. {_vle}", "sysmsg")
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
            if hasattr(self, 'btn_vm'): self.btn_vm.configure(text=f"{vm_name}")
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def cycle_vm(self):
        plog("VM", "cycle vm button pressed")
        def _work():
            self._advance_vm_state()
            self.ui(self._update_vm_label)
        self._run_bg("cycle-vm", _work)

    def go_live(self):
        try:
            url = self.entry_url.get().strip()
            plog("CHAT", f"go live pressed: url={url!r}")
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
            plog("VOTE", f"{user} voted {vote_type} but votes are paused (vm maintenance)")
            self.log("[system]", "[warn] vm is processing commands. votes paused.", "sysmsg")
            return
        msgs = []
        passed = None
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
                    msgs.append(f"[vote] [alert] {vote_type.lower()} progress: {current_votes}/{vote['target']}!")
                    log_vote_action("vote_progress", user, vote_type, vote['target'], current_votes)
                    plog("VOTE", f"{user} -> {vote_type} {current_votes}/{vote['target']}")
                    if current_votes >= vote["target"]:
                        msgs.append(f"[vote] [success] {vote_type.lower()} passed! executing now...")
                        log_vote_action("vote_passed", user, vote_type, vote['target'], current_votes)
                        passed = vote_type
                        self.active_votes.clear()
                else:
                    plog("VOTE", f"{user} already voted {vote_type}", verbose=True)
            elif len(self.active_votes) < 3:
                msgs.append(f"[vote] [started] {vote_type.lower()} vote started by {user}! progress: 1/{target}.")
                self.active_votes[vote_type] = {"voters": {user}, "target": target, "start_time": time.time()}
                log_vote_action("vote_started", user, vote_type, target, 1)
                plog("VOTE", f"{user} started {vote_type} vote (needs {target})")
            else:
                plog("VOTE", f"{user} tried to start {vote_type} but 3 votes are already running")
        for m in msgs:
            self.log("[system]", m, "sysmsg")
        for m in msgs:
            clean = re.sub(r"\[(vote|alert|started|success)\]\s*", "", m, flags=re.I).strip()
            if clean:
                self._discord_announce(clean[:1].upper() + clean[1:])
        if passed is None:
            return
        clean_cmd = passed
        if clean_cmd.startswith(self.command_prefix): clean_cmd = clean_cmd[len(self.command_prefix):]
        plog("VOTE", f"vote PASSED: {clean_cmd} - executing")
        self._discord_announce(f"Vote passed: {clean_cmd}. Running it now.")
        if clean_cmd == "skipsong" or clean_cmd == "stopsong":
            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_STOP")
            self.current_song = None
        elif clean_cmd == "pausesong":
            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
        elif clean_cmd == "resumesong":
            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
        elif clean_cmd == "votereplay":
            self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")
            def _replay_play():
                time.sleep(1)
                self.obs_media_action("OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
            threading.Thread(target=_replay_play, daemon=True, name="vote-replay").start()
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

    def on_manual_cmd(self, event=None):
        try:
            cmd = self.entry_cmd.get().strip()
            if cmd:
                if not cmd.startswith(self.command_prefix) and not cmd.startswith("!"): cmd = self.command_prefix + cmd
                elif cmd.startswith("!") and not cmd.startswith(self.command_prefix): cmd = self.command_prefix + cmd[1:]
                self.log("[console]", cmd, "user", is_mod=True, is_owner=True)
                self._manual_cmd(cmd)
                self.entry_cmd.delete(0, 'end')
                hist = getattr(self, "_cmd_hist", None)
                if hist is not None:
                    if not hist or hist[-1] != cmd:
                        hist.append(cmd)
                    del hist[:-50]
                    self._cmd_hist_i = len(hist)
        except Exception as e:
            self.log("[system]", f"[error] manual cmd error: {e}", "err")
            console_log("ERROR", f"[error] manual cmd error: {e}\n{traceback.format_exc()}")

    def _cmd_history(self, d):
        hist = getattr(self, "_cmd_hist", [])
        if not hist:
            return "break"
        i = max(0, min(len(hist), getattr(self, "_cmd_hist_i", len(hist)) + d))
        self._cmd_hist_i = i
        try:
            self.entry_cmd.delete(0, "end")
            if i < len(hist):
                self.entry_cmd.insert(0, hist[i])
                self.entry_cmd.icursor("end")
            self._cmd_hint_update()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        return "break"

    def _palette_run(self, cmd):
        cmd = str(cmd).strip()
        if not cmd:
            return
        if cmd.startswith("!") and not cmd.startswith(self.command_prefix):
            cmd = self.command_prefix + cmd[1:]
        self.log("[console]", cmd, "user", is_mod=True, is_owner=True)
        self._manual_cmd(cmd)

    def _palette_actions(self):
        acts = [
            ("Connect chat", "Use the stream link on the Dashboard", self.go_live),
            ("Pause or resume chat commands", "Chat", self.toggle_pause_chat),
            ("Enable or stop the Discord bot", "Discord", self.toggle_crossplay),
            ("Toggle the base64 filter", "Security", self._palette_toggle_b64),
            ("Start VM", "Machine", lambda: self._vm_action("startvm")),
            ("Shut down VM", "Machine", lambda: self._vm_action("shutdown")),
            ("Restart VM", "Machine", lambda: self._vm_action("restartvm")),
            ("Revert to snapshot", "Machine", lambda: self._vm_action("revert")),
            ("Take a quick snapshot", "Machine", self.quick_snapshot),
            ("Pause VM", "Machine", self.pause_vm),
            ("Resume VM", "Machine", self.resume_vm),
            ("Cycle target VM", "Machine", self.cycle_vm),
            ("Rebuild COM session", "Recovery", lambda: setattr(self, "force_session_refresh", True)),
            ("Clear command queue", "Recovery", self.clear_commands),
            ("Close VirtualBox crash dialogs", "Recovery", lambda: threading.Thread(target=self._dismiss_crash_dialogs, daemon=True).start()),
            ("Toggle low power mode", "Performance", self._toggle_low_power),
            ("Switch light / dark", "Appearance", self.toggle_dark_light),
            ("Show or hide the chat pane", "Layout", lambda: self.tabview.toggle_chat_pane()),
            ("Focus the console", "Dashboard", lambda: (self.tabview.select(self.tab_dash), self.root.after(40, self.entry_cmd.focus_set))),
            ("Clear the console", "Dashboard", self._clear_console),
            ("Export chat messages", "Backup", self.extract_all_msgs),
            ("Open the output log", "Logs", lambda: self._open_file(_OUT_LOG)),
            ("Open the crash log", "Logs", lambda: self._open_file(CRASH_LOG)),
            ("Open the user guide", "Help", lambda: self.show_welcome_guide(force=True)),
            ("Minimize window", "Window", self._minimize_window),
            ("Open plugins", "Plugins", lambda: self.tabview.select(self.tab_plugins)),
            ("Open the plugin market", "Plugins", lambda: self.tabview.select(self.tab_market)),
            ("Open the plugin docs", "Plugins", self.plugin_docs_open),
            ("Create a new plugin", "Plugins", self._plugin_new),
            ("Check for updates", "App", self.update_check_now),
            ("Reload all plugins", "Plugins", lambda: self._run_bg("plugins-reload", self.plugins.reload_all)),
        ]
        for key, base in _STUDIO_BASE.items():
            acts.append((f"Theme: {base['name']}", "Appearance", lambda k=key: self.apply_theme(k)))
        for lv in ("full", "reduced", "off"):
            acts.append((f"Motion: {lv}", "Appearance", lambda lv=lv: self.set_motion(lv)))
        return acts

    def _clear_console(self):
        try:
            self.console_text.configure(state="normal")
            self.console_text.delete("1.0", "end")
            self.console_text.configure(state="disabled")
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _set_console_filter(self, key):
        self._console_filter = key
        show = {"all": None, "chat": {"CHAT"}, "system": {"SYSTEM", "EXEC", "OTHER", "DEBUG"}, "errors": {"ERROR"}}.get(key)
        try:
            for tg in ("SYSTEM", "ERROR", "EXEC", "CHAT", "OTHER", "DEBUG"):
                self.console_text.tag_config(tg, elide=bool(show is not None and tg not in show))
            self.console_text.see("end")
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self._paint_console_chips(animate=True)

    def _paint_console_chips(self, animate=False):
        t = self._tok
        for key, ch in getattr(self, "_console_chips", {}).items():
            on = key == getattr(self, "_console_filter", "all")
            bg = t["accent_tint"] if on else t["card"]
            fg = t["accent_text"] if on else t["muted"]
            try:
                ch.configure(font=_sf("ui", 9, "semi"))
                if animate and MOTION.on:
                    MOTION.color(("chip", key), 220, lambda c, ch=ch: ch.configure(bg=c), bg)
                    MOTION.color(("chipfg", key), 220, lambda c, ch=ch: ch.configure(fg=c), fg)
                else:
                    MOTION.cancel(("chip", key)); MOTION.cancel(("chipfg", key))
                    MOTION.col[("chip", key)] = bg
                    MOTION.col[("chipfg", key)] = fg
                    ch.configure(bg=bg, fg=fg)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _chat_pane_msg(self, user, message, is_mod=False, is_owner=False):
        nav = getattr(self, "tabview", None)
        if nav is None or not hasattr(nav, "push_chat"):
            return
        m = str(message)
        tag = "cmd" if m.strip().startswith(self.command_prefix) else "usr"
        badge = "OWNER" if is_owner else ("MOD" if is_mod else None)
        self.ui(nav.push_chat, user, m, tag, badge)

    def _count(self, key, lbl, n, fmt="{:,}", flash=False):
        cnt = self.__dict__.setdefault("_cnt", {})
        cur = cnt.get(key)
        cnt[key] = n
        mk = ("count", key)
        if cur is None or not MOTION.on:
            MOTION.cancel(mk)
            MOTION.val[mk] = float(n)
            txt = fmt.format(n)
            if lbl.cget("text") != txt:
                lbl.configure(text=txt)
            return
        if cur == n:
            return
        start = MOTION.val.get(mk, float(cur))
        MOTION.tween(mk, 700, lambda v, l=lbl: l.configure(text=fmt.format(int(round(v)))), float(n), a=start,
                     ease=_ease_out_cubic)
        if flash:
            t = self._tok
            MOTION.color(("countfx", key), 1100, lambda c, l=lbl: l.configure(fg=c), t["hi"],
                         frm=t["ok"] if n > cur else t["bad"])

    def _dash_enter(self):
        if not hasattr(self, "_metric"):
            return
        if MOTION.on:
            def rev(v):
                self._spark_rev = max(0.0, min(1.0, v))
                self._draw_sparks()
            MOTION.tween("sparkrev", 1000, rev, 1.0, a=0.0, ease=_ease_in_out, delay=120)
            cnt = self.__dict__.setdefault("_cnt", {})
            for i, key in enumerate(("viewers", "queue", "cpm")):
                n = cnt.get(key)
                if n:
                    lbl = self._metric[key]["val"]
                    lbl.configure(text="0")
                    MOTION.tween(("count", key), 800, lambda v, l=lbl: l.configure(text="{:,}".format(int(round(v)))),
                                 float(n), a=0.0, ease=_ease_out_cubic, delay=80 + i * 70)
            self._ok_shown = 0.0
            MOTION.tween("okbar", 900, self._okbar_step, self._ok_target(), a=0.0, ease=_ease_out_cubic, delay=300)
        MOTION.loop("sparkpulse", self._spark_pulse, 1600, fps=30)
        MOTION.loop("health", self._health_frame, 2400, fps=24)

    def _ok_target(self):
        tot = max(1, total_commands_executed)
        return max(0.0, 1.0 - total_commands_failed / float(tot))

    def _okbar_step(self, v):
        self._ok_shown = v
        self._draw_okbar()

    def _draw_okbar(self):
        t = self._tok
        cv = self._metric["uptime"]["cv"]
        cv.delete("all")
        cv.configure(bg=t["card"])
        w, h = cv.winfo_width(), cv.winfo_height()
        if w <= 40:
            return
        ok = max(0.0, min(1.0, getattr(self, "_ok_shown", self._ok_target())))
        tgt = self._ok_target()
        y = h / 2.0 + 4
        x1, x2 = 16, w - 16
        _rrect(cv, x1, y - 3, x2, y + 3, 3, fill=t["raised"], outline="")
        if ok > 0:
            col = t["ok"] if tgt > 0.9 else (t["warn"] if tgt > 0.6 else t["bad"])
            _rrect(cv, x1, y - 3, x1 + max(6, (x2 - x1) * ok), y + 3, 3, fill=col, outline="")
            cv.create_oval(x1 + max(6, (x2 - x1) * ok) - 3, y - 3, x1 + max(6, (x2 - x1) * ok) + 3, y + 3,
                           fill=mix(col, "#FFFFFF", 0.35), outline="")

    def _spark_pulse(self, ph):
        t = self._tok
        if getattr(self.tabview, "_current", None) is not getattr(self, "tab_dash", None):
            return
        for key, tip in list(getattr(self, "_spark_tips", {}).items()):
            cv = self._metric[key]["cv"]
            try:
                cv.delete("pulse")
                if tip is None or MOTION.busy("sparkrev"):
                    continue
                x, y, col = tip
                r = 3 + 9 * ph
                cv.create_oval(x - r, y - r, x + r, y + r, outline=mix(col, t["card"], ph), width=1.6, tags="pulse")
            except Exception:
                pass

    def _health_frame(self, ph):
        t = self._tok
        on_dash = getattr(self.tabview, "_current", None) is getattr(self, "tab_dash", None)
        for i, (nm, dt) in enumerate(getattr(self, "_tile_dots", {}).items()):
            on = getattr(self, "_tile_state", {}).get(nm, False)
            if MOTION.busy(("tiledot", nm)):
                continue
            try:
                if on and on_dash and MOTION.ambient:
                    dt.configure(fg=mix(t["ok"], t["ok_tint"], 0.7 * _breath((ph + i * 0.17) % 1.0)))
                else:
                    dt.configure(fg=t["ok"] if on else t["faint"])
            except Exception:
                pass

    def _draw_sparks(self):
        t = self._tok
        hist = getattr(self, "_dash_hist", None)
        if not hist or not hasattr(self, "_metric"):
            return
        rev = max(0.0, min(1.0, getattr(self, "_spark_rev", 1.0)))
        self._spark_tips = {}
        for key, col in (("viewers", t["info"]), ("queue", t["warn"] if (hist["queue"] and hist["queue"][-1] > 25) else t["accent"]),
                         ("cpm", t["ok"])):
            cv = self._metric[key]["cv"]
            try:
                cv.delete("all")
                cv.configure(bg=t["card"])
                w, h = cv.winfo_width(), cv.winfo_height()
                if w < 20 or h < 10:
                    continue
                data = list(hist[key])
                n = len(data)
                base = h - 2
                cv.create_line(0, base, w, base, fill=t["line"])
                if n < 2:
                    self._spark_tips[key] = None
                    continue
                hi = max(max(data), 1.0)
                lo = 0.0
                pts = []
                for i, v in enumerate(data):
                    x = 1 + (i / float(n - 1)) * (w - 16)
                    y = base - (float(v) - lo) / (hi - lo) * (h - 13)
                    pts += [x, y]
                if rev < 1.0:
                    xmax = 1 + rev * (w - 16)
                    keep = [i for i in range(0, len(pts), 2) if pts[i] <= xmax]
                    if len(keep) < 2:
                        self._spark_tips[key] = None
                        continue
                    pts = [c for i in keep for c in (pts[i], pts[i + 1])]
                poly = [pts[0], base] + pts + [pts[-2], base]
                cv.create_polygon(*poly, fill=mix(t["card"], col, 0.16), outline="")
                cv.create_line(*pts, fill=col, width=1.6, smooth=True)
                cv.create_oval(pts[-2] - 2.5, pts[-1] - 2.5, pts[-2] + 2.5, pts[-1] + 2.5, fill=col, outline="")
                self._spark_tips[key] = (pts[-2], pts[-1], col)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        try:
            tgt = self._ok_target()
            if not MOTION.busy("okbar"):
                cur = getattr(self, "_ok_shown", None)
                if cur is None or not MOTION.on:
                    self._ok_shown = tgt
                elif abs(cur - tgt) > 0.001:
                    MOTION.tween("okbar", 600, self._okbar_step, tgt, a=cur)
                    return
            self._draw_okbar()
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _dash_tick(self, h, m, s):
        hist = getattr(self, "_dash_hist", None)
        if hist is None:
            return
        now = time.time()
        qn = self.cmd_queue.qsize()
        try: waiting = self.cmd_queue.waiting_viewers()
        except Exception: waiting = 0
        try: viewers = float(str(current_viewers).replace(",", "") or 0)
        except Exception: viewers = 0.0
        self._dash_cmdlog.append((now, total_commands_executed))
        old = None
        for ts, n in self._dash_cmdlog:
            if now - ts <= 60:
                old = (ts, n)
                break
        cpm = 0
        if old is not None and now - old[0] > 0.5:
            cpm = int(round((total_commands_executed - old[1]) * 60.0 / max(1.0, min(60.0, now - old[0])))) if now - old[0] >= 10 else total_commands_executed - old[1]
        last = getattr(self, "_dash_last_sample", 0)
        if now - last >= 2.0:
            self._dash_last_sample = now
            hist["viewers"].append(viewers)
            hist["queue"].append(qn)
            hist["cpm"].append(cpm)
        mt = self._metric
        def setl(lbl, txt, fg=None):
            try:
                if lbl.cget("text") != txt:
                    lbl.configure(text=txt)
                if fg is not None:
                    lbl.configure(fg=fg)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        t = self._tok
        self._count("viewers", mt["viewers"]["val"], int(viewers), flash=True)
        setl(mt["viewers"]["sub"], f"{current_likes} likes")
        self._count("queue", mt["queue"]["val"], int(qn))
        if not MOTION.busy(("countfx", "queue")):
            setl(mt["queue"]["val"], mt["queue"]["val"].cget("text"), t["warn"] if qn > 25 else t["hi"])
        setl(mt["queue"]["sub"], f"{waiting} viewer{'s' if waiting != 1 else ''} waiting" if waiting else "Nobody waiting")
        self._count("cpm", mt["cpm"]["val"], int(cpm))
        setl(mt["cpm"]["sub"], f"{total_commands_executed:,} run  /  {total_commands_failed:,} failed")
        d, hh = divmod(h, 24)
        setl(mt["uptime"]["val"], (f"{d}d {hh}h {m:02d}m" if d else f"{h}h {m:02d}m"))
        tot = max(1, total_commands_executed)
        setl(mt["uptime"]["sub"], f"Success rate {100.0 * (1 - total_commands_failed / float(tot)):.1f}%")
        vh = list(hist["viewers"])
        if len(vh) >= 2:
            dv = vh[-1] - vh[max(0, len(vh) - 30)]
            setl(mt["viewers"]["trend"], ("+" if dv > 0 else "") + f"{int(dv)} in 1m" if dv else "steady")
        setl(mt["queue"]["trend"], "busy" if qn > 25 else "")
        setl(mt["cpm"]["trend"], "")
        setl(mt["uptime"]["trend"], "")
        alive = bool(getattr(self, "listening_to_chat", False)) and bool(getattr(self, "active_url", ""))
        try:
            _st_txt = (f"Listening to {self.active_url}" if alive else ("Chat listener off" if getattr(self, "active_url", "") else "Not connected"))
            _st_fg = t["ok_soft"] if alive else t["faint"]
            if self._stream_state.cget("text") != _st_txt and MOTION.on:
                self._stream_state.configure(text=_st_txt)
                MOTION.color("streamstate", 500, lambda c: self._stream_state.configure(fg=c), _st_fg, frm=t["card"])
            elif not MOTION.busy("streamstate"):
                setl(self._stream_state, _st_txt, _st_fg)
            self._stream_dot.configure(fg=t["ok"] if alive else t["faint"])
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if getattr(self.tabview, "_current", None) is self.tab_dash:
            self._draw_sparks()

    def log(self, user, message, tag="sysmsg", is_mod=False, is_owner=False):
        if not isinstance(message, str): message = str(message)
        if not isinstance(user, str): user = str(user)
        if user == "[system]" or user.lower() == "system" or user == "[SYSTEM]":
            user = "[system]"
            is_mod = True
            is_owner = True
            self.recent_bot_messages.append(message)
        if user == "[debug]":
            try: gui_log_queue.put_nowait(("CHAT", f"[{time.strftime('%H:%M:%S')}] [debug] {message.lower()}"))
            except queue.Full: pass
            return
        plog("SYS" if user == "[system]" else "LOG", f"{user}: {message}" if user != "[system]" else message)
        if user == "[system]":
            low = message.lower()
            kind = None
            if "[warn] blocked" in low or "[ban]" in low or "[music]" in low: kind = None
            elif "[error" in low: kind = "bad"
            elif "[warn" in low: kind = "warn"
            elif "passed" in low or "connected to yt chat" in low: kind = "ok"
            if kind:
                clean = re.sub(r"\[(error|warn|vote|alert|success|started)\]\s*", "", message, flags=re.I).strip()
                self.toast(clean[:1].upper() + clean[1:], kind)
        add_to_history(user, message, tag, is_mod, is_owner)
        try:
            nav = getattr(self, "tabview", None)
            if nav is not None and hasattr(nav, "push_chat"):
                if user == "[console]":
                    t = "cmd" if str(message).strip().startswith(self.command_prefix) else "usr"
                    self.ui(nav.push_chat, "Console", message, t, "OWNER")
                elif user == "[announcement]":
                    self.ui(nav.push_chat, "Announcement", message, "sys", "INFO")
                elif not user.startswith("["):
                    self._chat_pane_msg(user, message, is_mod, is_owner)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def set_status(self, text):
        if isinstance(text, str):
            try: self.log_queue.put_nowait(("status", text.lower()))
            except queue.Full: plog("STATUS", f"status queue full, dropped: {text.lower()}")

    def _schedule_ui_tick(self):
        if not self.running:
            return
        try:
            prev = getattr(self, "_ui_after_id", None)
            if prev is not None:
                try: self.root.after_cancel(prev)
                except Exception: pass
            delay = 250 if self.config.get('low_power', False) else refresh_rate
            self._ui_next_due = time.time() + delay / 1000.0
            self._ui_after_id = self.root.after(delay, self.process_ui_queue)
        except (RuntimeError, tk.TclError) as e:
            plog("UI", f"could not schedule the next ui tick: {e}")

    def _ui_sec(self, name, t0):
        el = time.time() - t0
        if el > 0.05:
            self._ui_sections.append(f"{name}={el*1000:.0f}ms")
        return time.time()

    def process_ui_queue(self):
        self._ui_after_id = None
        t_start = time.time()
        if not _MAINLOOP_LIVE[0]:
            _MAINLOOP_LIVE[0] = True
            plog("UI", f"mainloop is live - first ui tick {t_start - script_start_time:.2f}s after launch")
        due = getattr(self, "_ui_next_due", 0)
        if due and t_start - due > 1.0:
            plog("UI-LAG", f"ui tick ran {t_start - due:.2f}s late - something held the UI thread (see UI-SLOW / UI-BLOCK lines above)")
        self._ui_tick_count = getattr(self, "_ui_tick_count", 0) + 1
        self._ui_sections = []
        try:
            self._process_ui_queue_body()
        except (KeyboardInterrupt, SystemExit):
            self.running = False
            return
        except Exception as _uie:
            log_crash("process_ui_queue", _uie)
        finally:
            el = time.time() - t_start
            if el * 1000 > getattr(self, "_ui_worst_ms", 0):
                self._ui_worst_ms = el * 1000
            if el > 0.25:
                plog("UI-SLOW", f"ui tick #{self._ui_tick_count} took {el*1000:.0f}ms  [{', '.join(self._ui_sections) or 'no single section over 50ms'}]")
            try:
                self._schedule_ui_tick()
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _process_ui_queue_body(self):
        global current_vote_info
        self.main_heartbeat = time.time()
        t = time.time()
        self._drain_ui_calls()
        t = self._ui_sec("ui_calls", t)
        self.update_gui_console()
        t = self._ui_sec("console", t)
        for _ in range(200):
            try:
                mt, dd = self.log_queue.get_nowait()
            except queue.Empty:
                break
            except Exception as _ex:
                _trace(_ex_where(), _ex)
                break
            try:
                if mt == "status": self.update_status_display(dd, "broke" in dd)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        t = self._ui_sec("status", t)
        _now = time.time()
        _lp = self.config.get("low_power", False)
        if (_now - getattr(self, "_last_slow_ui", 0)) < (2.0 if _lp else 1.0):
            return
        self._last_slow_ui = _now
        uptime_sec = int(_now - script_start_time)
        m, s = divmod(uptime_sec, 60)
        h, m = divmod(m, 60)
        try:
            nav = getattr(self, "tabview", None)
            if nav is not None and hasattr(nav, "set_status"):
                running = self._vm_is_running()
                self._lastvmchk = time.time(); self._lastvmstate = running
                be = getattr(self, "backend", "virtualbox")
                qn = self.cmd_queue.qsize()
                nav.set_status(left=f"{'VMware' if be == 'vmware' else 'VirtualBox'}  /  {vm_name}",
                               right=f"Up {h}h {m:02d}m", running=running)
                alive = bool(getattr(self, "listening_to_chat", False)) and bool(getattr(self, "active_url", ""))
                if hasattr(nav, "set_chat_state"):
                    nav.set_chat_state(alive)
                if hasattr(nav, "set_activity"):
                    try: _wv = self.cmd_queue.waiting_viewers()
                    except Exception: _wv = 0
                    nav.set_activity(getattr(self, "_exec_current", ""), qn, _wv)
                if hasattr(nav, "pulse"):
                    nav.pulse()
                if hasattr(nav, "set_badge"):
                    _mq = len(getattr(self, "music_queue", []) or [])
                    nav.set_badge("Music Queue", str(_mq) if _mq else "")
                    nav.set_badge("Automation", str(len(self.automations)) if getattr(self, "automations", None) else "")
                if hasattr(nav, "set_tally"):
                    nav.set_tally("chat", "On air" if alive else "Off air", "onair" if alive else "off")
                    nav.set_tally("vm", "VM running" if running else "VM stopped", "ok" if running else "off")
                    obs_ok = getattr(self, "_obs_ok", None)
                    nav.set_tally("obs", "OBS linked" if obs_ok else "OBS offline", "ok" if obs_ok else "off")
                    nav.set_tally("queue", f"Queue {qn}", "warn" if qn > 25 else "neutral")
                    nav.set_tally("viewers", f"{current_viewers} viewers", "neutral")
                if time.time() - getattr(self, "_last_obs_probe", 0) > 10:
                    self._last_obs_probe = time.time()
                    self._run_bg("obs-probe", lambda: setattr(self, "_obs_ok", bool(obs_available and obs_reachable())))
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        t = self._ui_sec("statusbar", t)
        try:
            if hasattr(self, "_tiles"):
                vmrun = getattr(self, "_lastvmstate", False)
                chat_on = bool(getattr(self, "listening_to_chat", False)) and bool(getattr(self, "active_url", ""))
                pico_on = bool(getattr(self, "pico_enabled", False))
                obs_on = bool(getattr(self, "_obs_ok", False))
                _dc = getattr(self, "discord", None)
                dc_on = bool(_dc and _dc.online)
                for nm, on, txt_on, txt_off in (("Bot Status", chat_on, "Listening", "Stopped"), ("VM", vmrun, "Running", "Stopped"),
                                                ("Discord", dc_on, "Online", ("Connecting" if (_dc and _dc.running) else "Off")),
                                                ("OBS", obs_on, "Linked", "Offline"),
                                                ("Overlay Server", bool(getattr(self, "_flask_started", False)), f"Port {flask_port}", "Stopped"),
                                                ("Real PC", pico_on, "Connected", "Not connected")):
                    lb = self._tiles.get(nm)
                    tstate = self.__dict__.setdefault("_tile_state", {})
                    was = tstate.get(nm)
                    tstate[nm] = on
                    _tt = self._tok
                    if lb is not None:
                        want = txt_on if on else txt_off
                        if lb.cget("text") != want:
                            lb.configure(text=want)
                        if was is not None and was != on and MOTION.on:
                            MOTION.color(("tiletxt", nm), 700, lambda c, l=lb: l.configure(fg=c),
                                         _tt["hi"] if on else _tt["muted"], frm=_tt["card"])
                        elif not MOTION.busy(("tiletxt", nm)):
                            lb.configure(fg=_studio_color("hi" if on else "muted", "#10B981"))
                    dt = getattr(self, "_tile_dots", {}).get(nm)
                    if dt is not None:
                        if was is not None and was != on and MOTION.on:
                            MOTION.color(("tiledot", nm), 900, lambda c, d=dt: d.configure(fg=c),
                                         _tt["ok"] if on else _tt["faint"], frm=_tt["hi"] if on else _tt["bad"])
                        elif not MOTION.looping("health") or not MOTION.ambient:
                            dt.configure(fg=_studio_color("ok" if on else "faint", "#10B981"))
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        try:
            self._dash_tick(h, m, s)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        t = self._ui_sec("tiles", t)

        q_hash = str([x["title"] for x in getattr(self, 'music_queue', [])])
        if q_hash != getattr(self, 'last_q_hash', "") and hasattr(self, "music_listbox"):
            self.last_q_hash = q_hash
            try:
                self.music_listbox.delete(0, "end")
                for idx, s2 in enumerate(self.music_queue):
                    self.music_listbox.insert("end", f"{idx+1}. {s2['title']} ({s2['user']})")
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        if hasattr(self, "lbl_music_playing"):
            try:
                cs = getattr(self, 'current_song', None)
                want = (str(cs.get('title', '?')) if cs else "Nothing playing")
                by = (f"Requested by {cs.get('user', '?')}" if cs else "Viewers queue songs with !music <url>")
                if self.lbl_music_playing.cget("text") != want:
                    self.lbl_music_playing.config(text=want)
                    if MOTION.on:
                        _t = self._tok
                        MOTION.color("nowplaying", 600, lambda c: self.lbl_music_playing.configure(fg=c), _t["hi"], frm=_t["card"])
                        MOTION.tween("nowplaying_x", 520, lambda v: self.lbl_music_playing.pack_configure(padx=(int(18 * (1 - v)), 0)),
                                     1.0, a=0.0, ease=_ease_out_back)
                if cs and hasattr(self, "_music_eq"):
                    MOTION.loop("musiceq", self._music_eq, 2400, fps=24)
                elif MOTION.looping("musiceq"):
                    MOTION.unloop("musiceq", rest=False)
                    try: self._paint_music_art()
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
                if hasattr(self, "lbl_music_by") and self.lbl_music_by.cget("text") != by:
                    self.lbl_music_by.config(text=by)
                if hasattr(self, "_music_empty"):
                    if getattr(self, "music_queue", None):
                        self._music_empty.place_forget()
                    elif not self._music_empty.winfo_manager():
                        self._music_empty.place(relx=0.5, rely=0.4, anchor="center")
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        t = self._ui_sec("music", t)

        if getattr(self, "_studio_ready", False) and time.time() - getattr(self, "_last_st_pass", 0) > 1.5:
            self._last_st_pass = time.time()
            try:
                cur = getattr(self.tabview, "_current", None)
                if cur is not None:
                    self._st_walk(cur, self._tok["bg"], False)
                for tl in self.root.winfo_children():
                    if isinstance(tl, tk.Toplevel):
                        self._st_walk(tl, self._tok["bg"], False)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        t = self._ui_sec("restyle", t)
        if time.time() - getattr(self, "_last_after_count", 0) > 10:
            self._last_after_count = time.time()
            try:
                self._pending_after = len(self.root.tk.call("after", "info"))
                if self._pending_after > 60:
                    plog("UI", f"WARNING {self._pending_after} pending Tk timers - a tick is scheduling itself more than once")
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        if time.time() - self.last_gc_time > 60:
            self.last_gc_time = time.time()
            _g0 = time.time()
            freed = gc.collect()
            plog("GC", f"gc.collect freed {freed} objects in {(time.time()-_g0)*1000:.0f}ms", verbose=True)
            try:
                top = sorted(_trace_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]
                if top:
                    log_event("TRACE", "top silent errors: " + ", ".join(f"{k}={v}" for k, v in top))
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        t = self._ui_sec("gc", t)
        if time.time() - getattr(self, 'last_vbox_refresh', 0) > (30 if self.config.get('low_power', False) else 10):
            self.last_vbox_refresh = time.time()
            self.auto_refresh_vbox_ui()
        if time.time() - getattr(self, 'last_thread_check', 0) > 15:
            self.last_thread_check = time.time()
            self.start_app_threads()
        t = self._ui_sec("threads", t)
        if self.vote_lock.acquire(blocking=False):
            try:
                now = time.time()
                to_remove = []
                for vtype, data in self.active_votes.items():
                    if now - data["start_time"] > vote_timeout: to_remove.append(vtype)
                for vtype in to_remove:
                    del self.active_votes[vtype]
                    plog("VOTE", f"vote {vtype} expired after {vote_timeout}s")
                if self.active_votes:
                    parts = []
                    for vtype, data in self.active_votes.items(): parts.append(f"{vtype.lower()}: {len(data['voters'])}/{data['target']}")
                    text = " | ".join(parts).lower()
                    current_vote_info = {"active": True, "text": f"[vote] {text}"}
                else: current_vote_info = {"active": False, "text": "no active votes"}
            finally:
                self.vote_lock.release()
        self._ui_sec("votes", t)

    def save_session_data_threadsafe(self):
        try:
            url = self.active_url if self.active_url else ""
            mode = str(self.twenty_four_seven_mode)
            layout = str(keyboard_layout)
            with open(session_file, "w") as f: f.write(f"{url}|{mode}|{layout}")
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _security_gate(self, clean_user, cmd, arg, chain_step=False, trusted=False):
        now = time.time()
        if trusted and chain_step:
            return True, ""
        if chain_step:
            if self.config.get("protect_vm", False) and cmd in ("!type", "!send", "!cmd", "!run", "!key"):
                hit = payload_is_dangerous(f"{cmd} {arg}")
                if hit:
                    return False, f"blocked term '{hit}'"
                if len(str(arg)) > int(self.config.get("max_type_len", 200)):
                    return False, "message too long"
            if len(str(arg)) > 4000:
                return False, "command too long (max 4000 chars)"
            return True, ""



        unlocked = not self.config.get("protect_vm", False)

        if cmd in ("!cmd", "!run") and not unlocked and not trusted and not self.config.get("allow_viewer_shell", False):
            return False, "shell commands are mod-only"

        cd = float(self.config.get("viewer_cooldown", 1.5) or 0)
        if cd > 0 and now - self.user_last_cmd.get(clean_user, 0) < cd:
            return False, "cooldown"
        self.user_last_cmd[clean_user] = now

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

        if not unlocked and not trusted and cmd in ("!type", "!send", "!cmd", "!run", "!key"):
            hit = payload_is_dangerous(f"{cmd} {arg}")
            if hit:
                n = self.user_strikes.get(clean_user, 0) + 1
                self.user_strikes[clean_user] = n
                return False, f"blocked term '{hit}'"

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

        if not unlocked and not trusted and len(str(arg)) > int(self.config.get("max_type_len", 200)):
            return False, "message too long"

        if len(str(arg)) > 4000:
            return False, "command too long (max 4000 chars)"
        return True, ""

    def _trace_report(self, n=15):
        items = sorted(_trace_counts.items(), key=lambda kv: kv[1], reverse=True)
        lines = ["--- most frequent swallowed exceptions (where:type -> count) ---"]
        if not items:
            lines.append("  (none yet - nothing has silently failed)")
        for k, v in items[:n]:
            lines.append(f"  {v:>6}x  {k}")
        return "\n".join(lines)

    def run_diagnostics(self):
        L = []
        def add(ok, label, detail=""):
            mark = "OK  " if ok is True else ("WARN" if ok is None else "FAIL")
            L.append(f"[{mark}] {label}" + (f"  -  {detail}" if detail else ""))
        add(True, "platform", f"{platform.system()} {platform.release()}  python {platform.python_version()}")
        add(True, "app", f"{self.app_name} {version}  instance {instance_id}  backend {getattr(self,'backend','virtualbox')}")
        L.append("")
        L.append("--- dependencies ---")
        import importlib.util
        for mod, pip, why in _rqp + _opp:
            found = False
            try: found = importlib.util.find_spec(mod) is not None
            except Exception: found = False
            req = any(m == mod for m, _, _ in _rqp)
            add(True if found else (False if req else None), f"{pip:<16}", why if found else f"missing - pip install {pip}")
        import importlib.util as _ilu
        _dc = False
        try: _dc = _ilu.find_spec("discord") is not None
        except Exception: _dc = False
        add(_dc if _dc else None, f"{'discord.py':<16}", "Discord crossplay bot" if _dc else "installs automatically when you enable the bot")
        L.append("")
        L.append("--- discord ---")
        _br = getattr(self, "discord", None)
        add(bool(_br and _br.online) if (_br and _br.running) else None, "bot",
            (_br.state + (f" ({_br.user_tag})" if _br.user_tag else "")) if _br else "stopped")
        add(None if not self.config.get("discord_enabled") else True, "enabled",
            "yes, mode=" + str(self.config.get("discord_mode", "crossplay")) if self.config.get("discord_enabled") else "no")
        add(bool(self._did("discord_channel_id")), "command channel",
            (self.discord.channel_name(self._did("discord_channel_id")) or str(self._did("discord_channel_id"))) if self._did("discord_channel_id") else "not picked")
        add(bool(discord_token_load()), "saved token", "present" if discord_token_load() else "none - paste it on the Discord page")
        add(self._b64_filter_on(), "base64 filter", ("on" + (f", {len(self.b64_offenders)} blocked" if self.b64_offenders else "")) if self._b64_filter_on() else "OFF")
        L.append("")
        L.append("--- virtualbox ---")
        path, how = resolve_vbox_path(self.config.get("vbox_path", ""))
        add(how != "not found", f"VBoxManage", f"{path}  (via {how})")
        vms = get_all_vbox_vms(path, quiet=True)
        if vms:
            add(True, "VMs found", f"{len(vms)}: " + ", ".join(vms[:6]) + (" ..." if len(vms) > 6 else ""))
        else:
            add(False, "VMs found", _vle or "none")
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
        add(True, "debug logging", f"ON -> {_dbf}" if DEBUG_ON else "off (run with --debug)")
        add(True, "trace logging", "ON" if _trace_on else "off (run with --trace)")
        L.append("")
        L.append(self._trace_report())
        return "\n".join(L)

    def _discord_logo(self, cv, size):
        t = self._tok
        cv.delete("all")
        bg = t["bg"]
        cv.configure(bg=bg)
        c = int(size)
        br = getattr(self, "discord", None)
        online = bool(br and br.online)
        img = _user_logo(int(c * 0.78))
        tint = t["ok_tint"] if online else t["accent_tint"]
        edge = t["ok_edge"] if online else t["accent_edge"]
        _rrect(cv, 1, 1, c - 1, c - 1, c * 0.24, fill=tint, outline=edge)
        if img is not None:
            cv.create_image(c / 2.0, c / 2.0, image=img)
        else:
            _draw_icon(cv, "bridge", c / 2.0, c / 2.0, c * 0.6, t["ok"] if online else t["accent_text"], tint, w=2.0 * c / 54.0)

    def build_discord_tab(self):
        t = self._tok
        S = getattr(self, "_ui_scale", 1.0)
        wrap = self.make_scrollable(self.tab_discord)
        pad = 26

        def card(parent, pack=True):
            o = tk.Frame(parent, bg=t["line"]); o._st = {"bg": "line"}
            c = tk.Frame(o, bg=t["card"]); c._st = {"bg": "card"}
            c.pack(fill="both", expand=True, padx=1, pady=1)
            if pack:
                o.pack(fill="x", padx=pad, pady=(0, 14))
            return o, c

        head = tk.Frame(wrap, bg=t["bg"]); head._st = {"bg": "bg"}
        head.pack(fill="x", padx=pad, pady=(20, 14))
        logo = tk.Canvas(head, width=int(54 * S), height=int(54 * S), bd=0, highlightthickness=0, bg=t["bg"])
        logo._studio_skip = True
        logo.pack(side="left")
        self._discord_logo_cv = logo
        htx = tk.Frame(head, bg=t["bg"]); htx._st = {"bg": "bg"}
        htx.pack(side="left", padx=(14, 0), fill="x", expand=True)
        self._st_label(htx, "Discord bridge", bg="bg", fg="hi", font=("display", 17), anchor="w").pack(anchor="w")
        self._discord_state_lbl = self._st_label(htx, "Stopped", bg="bg", fg="muted", font=("ui", 10), anchor="w")
        self._discord_state_lbl.pack(anchor="w", pady=(2, 0))

        _o, setup = card(wrap)
        inner = tk.Frame(setup, bg=t["card"]); inner._st = {"bg": "card"}
        inner.pack(fill="x", padx=16, pady=16)
        self._st_label(inner, "Bot token", bg="card", fg="hi", font=("ui", 10, "semi"), anchor="w").pack(anchor="w")
        self._st_label(inner, "From the Discord Developer Portal > your app > Bot > Reset Token. It is saved (encrypted on Windows) so it survives a crash or restart.",
                       bg="card", fg="faint", font=("ui", 9), anchor="w", justify="left", wraplength=int(620 * S)).pack(anchor="w", pady=(1, 8))
        trow = tk.Frame(inner, bg=t["card"]); trow._st = {"bg": "card"}
        trow.pack(fill="x")
        self.discord_token_entry = tk.Entry(trow, font=_sf("mono", 11), bg=t["input"], fg=t["hi"], insertbackground=t["hi"],
                                            bd=0, show="\u2022", highlightthickness=1, highlightbackground=t["line"], highlightcolor=t["accent"])
        self.discord_token_entry.pack(side="left", fill="x", expand=True, ipady=7)
        if discord_token_load():
            self.discord_token_entry.insert(0, self._discord_token_mask())
            self._discord_token_cache = discord_token_load()
        self._discord_show_var = tk.BooleanVar(value=False)
        def _toggle_show():
            self.discord_token_entry.configure(show="" if self._discord_show_var.get() else "\u2022")
        ttk.Checkbutton(trow, text="Show", variable=self._discord_show_var, command=_toggle_show).pack(side="left", padx=(10, 0))
        self._st_button(trow, "Save token", self.save_discord_token, "neutral", 9).pack(side="left", padx=(10, 0))
        self._discord_hint = self._st_label(inner, "", bg="card", fg="muted", font=("ui", 9), anchor="w", justify="left", wraplength=int(620 * S))
        self._discord_hint.pack(anchor="w", pady=(8, 0))

        _o2, modec = card(wrap)
        mi = tk.Frame(modec, bg=t["card"]); mi._st = {"bg": "card"}
        mi.pack(fill="x", padx=16, pady=16)
        self._st_label(mi, "Mode", bg="card", fg="hi", font=("ui", 10, "semi"), anchor="w").pack(anchor="w", pady=(0, 6))
        self._discord_mode_var = tk.StringVar(value=self.config.get("discord_mode", "crossplay"))
        for val, title, sub in (
                ("crossplay", "Discord + YouTube crossplay", "Both chats drive the VM at once. Votes and commands are shared."),
                ("discord", "Discord only", "Only Discord can run commands. YouTube chat still shows, but its commands are ignored.")):
            row = tk.Frame(mi, bg=t["card"]); row._st = {"bg": "card"}
            row.pack(fill="x", pady=2)
            rb = ttk.Radiobutton(row, text="", value=val, variable=self._discord_mode_var,
                                 command=self._on_discord_mode)
            rb.pack(side="left")
            txt = tk.Frame(row, bg=t["card"], cursor="hand2"); txt._st = {"bg": "card"}
            txt.pack(side="left", fill="x", expand=True)
            self._st_label(txt, title, bg="card", fg="text", font=("ui", 10, "semi"), anchor="w").pack(anchor="w")
            self._st_label(txt, sub, bg="card", fg="faint", font=("ui", 9), anchor="w").pack(anchor="w")
            for w in (txt,) + tuple(txt.winfo_children()):
                w.bind("<Button-1>", lambda e, v=val: (self._discord_mode_var.set(v), self._on_discord_mode()))

        self.btn_crossplay = self._st_button(mi, "Enable Discord & YouTube crossplay", self.toggle_crossplay, "primary", 11)
        self.btn_crossplay.pack(fill="x", pady=(12, 0), ipady=4)

        _o3, chans = card(wrap)
        ci = tk.Frame(chans, bg=t["card"]); ci._st = {"bg": "card"}
        ci.pack(fill="x", padx=16, pady=16)
        hc = tk.Frame(ci, bg=t["card"]); hc._st = {"bg": "card"}
        hc.pack(fill="x")
        self._st_label(hc, "Server & channels", bg="card", fg="hi", font=("ui", 10, "semi"), anchor="w").pack(side="left")
        self._st_button(hc, "Refresh", self._discord_rescan, "neutral", 9).pack(side="right")
        self._st_label(ci, "Pick these after the bot is online. The command channel is where viewers type; the log channel is optional.",
                       bg="card", fg="faint", font=("ui", 9), anchor="w", justify="left", wraplength=int(620 * S)).pack(anchor="w", pady=(1, 10))

        grid = tk.Frame(ci, bg=t["card"]); grid._st = {"bg": "card"}
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        self._discord_combos = {}
        rowdefs = [("Server", "guild"), ("Command channel", "channel"), ("Log channel (optional)", "log")]
        for i, (lbl, key) in enumerate(rowdefs):
            self._st_label(grid, lbl, bg="card", fg="muted", font=("ui", 9), anchor="e", width=20).grid(row=i, column=0, sticky="e", padx=(0, 12), pady=5)
            cb = ttk.Combobox(grid, state="readonly", font=("Segoe UI", 10))
            cb.grid(row=i, column=1, sticky="we", pady=5, ipady=3)
            cb.bind("<<ComboboxSelected>>", lambda e, k=key: self._on_discord_pick(k))
            self._discord_combos[key] = cb

        orow = tk.Frame(ci, bg=t["card"]); orow._st = {"bg": "card"}
        orow.pack(fill="x", pady=(10, 0))
        self._st_label(orow, "Extra owner IDs", bg="card", fg="muted", font=("ui", 9), anchor="e", width=20).pack(side="left", padx=(0, 12))
        self.discord_owner_entry = tk.Entry(orow, font=_sf("mono", 10), bg=t["input"], fg=t["hi"], insertbackground=t["hi"],
                                            bd=0, highlightthickness=1, highlightbackground=t["line"], highlightcolor=t["accent"])
        self.discord_owner_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.discord_owner_entry.insert(0, str(self.config.get("discord_owner_ids", "")))
        self.discord_owner_entry.bind("<FocusOut>", lambda e: self._save_discord_owners())
        self.discord_owner_entry.bind("<Return>", lambda e: self._save_discord_owners())
        self._st_label(ci, "Server admins already count as mods. Add user IDs here (comma-separated) to grant owner rights to specific people.",
                       bg="card", fg="faint", font=("ui", 8), anchor="w", justify="left", wraplength=int(620 * S)).pack(anchor="w", pady=(4, 0))

        togrow = tk.Frame(ci, bg=t["card"]); togrow._st = {"bg": "card"}
        togrow.pack(fill="x", pady=(12, 0))
        self._discord_screens_var = tk.BooleanVar(value=bool(self.config.get("discord_screens", True)))
        self._discord_logall_var = tk.BooleanVar(value=bool(self.config.get("discord_log_all", True)))
        ttk.Checkbutton(togrow, text="Post a VM screenshot with each 'Pressed:' batch", variable=self._discord_screens_var,
                        command=lambda: self._save_discord_toggle("discord_screens", self._discord_screens_var)).pack(anchor="w", pady=2)
        ttk.Checkbutton(togrow, text="Log every command and message to the log channel", variable=self._discord_logall_var,
                        command=lambda: self._save_discord_toggle("discord_log_all", self._discord_logall_var)).pack(anchor="w", pady=2)

        _o4, secc = card(wrap)
        si = tk.Frame(secc, bg=t["card"]); si._st = {"bg": "card"}
        si.pack(fill="x", padx=16, pady=16)
        srow = tk.Frame(si, bg=t["card"]); srow._st = {"bg": "card"}
        srow.pack(fill="x")
        self._st_label(srow, "Base64 filter", bg="card", fg="hi", font=("ui", 10, "semi"), anchor="w").pack(side="left")
        self._b64_pill = tk.Label(srow, text="ON", padx=10, pady=2)
        self._b64_pill._studio_skip = True
        self._b64_pill.pack(side="right")
        self._st_label(si, "Blocks PowerShell / cmd / Python base64 payloads on both YouTube and Discord, and stops that sender from issuing any more commands. "
                           "Chat toggles: !tob64 turns it off, !eb64 turns it back on. !unblock <user> clears one sender.",
                       bg="card", fg="faint", font=("ui", 9), anchor="w", justify="left", wraplength=int(620 * S)).pack(anchor="w", pady=(2, 10))
        self._b64_var = tk.BooleanVar(value=self._b64_filter_on())
        ttk.Checkbutton(si, text="Block base64 command payloads", variable=self._b64_var,
                        command=self._toggle_b64_ui).pack(anchor="w")
        self._b64_block_lbl = self._st_label(si, "", bg="card", fg="muted", font=("ui", 9), anchor="w")
        self._b64_block_lbl.pack(anchor="w", pady=(8, 0))
        self._st_button(si, "Clear the base64 block list", self._clear_offenders, "neutral", 9).pack(anchor="w", pady=(6, 0))

        _o5, statc = card(wrap)
        sti = tk.Frame(statc, bg=t["card"]); sti._st = {"bg": "card"}
        sti.pack(fill="x", padx=16, pady=16)
        self._st_label(sti, "Live status", bg="card", fg="hi", font=("ui", 10, "semi"), anchor="w").pack(anchor="w", pady=(0, 8))
        self._discord_stat_grid = tk.Frame(sti, bg=t["card"]); self._discord_stat_grid._st = {"bg": "card"}
        self._discord_stat_grid.pack(fill="x")
        self._discord_stat_lbls = {}
        cells = [("Bot", "bot"), ("Messages", "in"), ("Commands", "cmds"), ("Screens", "shots"), ("Blocked", "blocked"), ("Errors", "errors")]
        for i, (title, key) in enumerate(cells):
            cell = tk.Frame(self._discord_stat_grid, bg=t["card"]); cell._st = {"bg": "card"}
            cell.grid(row=0, column=i, sticky="w", padx=(0 if i == 0 else 22, 0))
            self._st_label(cell, title, bg="card", fg="faint", font=("ui", 8), anchor="w").pack(anchor="w")
            v = self._st_label(cell, "-", bg="card", fg="hi", font=("display", 15), anchor="w")
            v.pack(anchor="w")
            self._discord_stat_lbls[key] = v
        self._st_label(sti, "Recent events", bg="card", fg="muted", font=("ui", 9), anchor="w").pack(anchor="w", pady=(12, 2))
        self.discord_events = scrolledtext.ScrolledText(sti, font=_sf("mono", 9), bg=t["input"], fg=t["text"], bd=0,
                                                        highlightthickness=0, height=7, wrap="word", padx=10, pady=8)
        self.discord_events._st = {"bg": "input", "fg": "text", "font": ("mono", 9)}
        self.discord_events.pack(fill="x")
        self.discord_events.configure(state="disabled")

        self._discord_built = True
        self._refresh_discord_page()
        self._fill_discord_combos(force=True)
        if not getattr(self, "_discord_poll_on", False):
            self._discord_poll_on = True
            self.root.after(700, self._discord_poll)

    def _on_discord_mode(self):
        mode = self._discord_mode_var.get()
        self.config["discord_mode"] = mode
        self.save_settings()
        br = getattr(self, "discord", None)
        if br is not None:
            br.mode = mode
            if br.running:
                br.event(f"mode set to {br.mode_label()}")
        self._refresh_discord_page()

    def _save_discord_owners(self):
        try:
            self.config["discord_owner_ids"] = self.discord_owner_entry.get().strip()
            self.save_settings()
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _save_discord_toggle(self, key, var):
        self.config[key] = bool(var.get())
        self.save_settings()

    def _discord_rescan(self):
        br = getattr(self, "discord", None)
        if br is None or not br.online:
            self._set_discord_hint("Start the bot first, then press Refresh.", "warn")
            return
        loop, client = br.loop, br.client
        if loop is not None and client is not None:
            try:
                asyncio.run_coroutine_threadsafe(_noop_rescan(br, client), loop)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        self._fill_discord_combos(force=True)

    def _fill_discord_combos(self, force=False):
        br = getattr(self, "discord", None)
        if br is None or not getattr(self, "_discord_built", False):
            return
        if not force and not br.guilds_dirty:
            return
        br.guilds_dirty = False
        guilds = list(br.guilds)
        gmap = {}
        gvals = []
        for gid, gname, chans in guilds:
            label = f"{gname}  ({gid})"
            gvals.append(label)
            gmap[label] = gid
        self._discord_gmap = gmap
        cb = self._discord_combos["guild"]
        cb.configure(values=gvals or ["(bot offline - start it, then Refresh)"])
        cur_gid = self._did("discord_guild_id")
        sel_label = next((l for l, g in gmap.items() if g == cur_gid), "")
        if sel_label:
            cb.set(sel_label)
        elif cur_gid and not gvals:
            cb.set(f"saved server {cur_gid}")
        elif gvals and not cb.get():
            cb.set(gvals[0])
            self._discord_set_guild(gmap[gvals[0]])
        self._fill_channel_combos()

    def _fill_channel_combos(self):
        br = getattr(self, "discord", None)
        gid = self._did("discord_guild_id")
        chans = []
        for g, gname, cs in (br.guilds if br else []):
            if g == gid:
                chans = cs
                break
        cvals, cmap = [], {}
        for cid, cname, ok in chans:
            label = f"#{cname}" + ("" if ok else "  (no access)")
            cvals.append(label)
            cmap[label] = cid
        self._discord_cmap = cmap
        for key, cfgkey, allow_none in (("channel", "discord_channel_id", False), ("log", "discord_log_channel_id", True)):
            cb = self._discord_combos[key]
            vals = (["(none)"] if allow_none else []) + cvals
            cb.configure(values=vals or ["(no channels)"])
            cur = self._did(cfgkey)
            label = next((l for l, c in cmap.items() if c == cur), "")
            if label:
                cb.set(label)
            elif cur and not cvals:
                cb.set(f"saved channel {cur}")
            elif allow_none and not cur:
                cb.set("(none)")
            elif not cb.get() and vals:
                cb.set(vals[0])

    def _on_discord_pick(self, key):
        cb = self._discord_combos[key]
        val = cb.get()
        if key == "guild":
            gid = getattr(self, "_discord_gmap", {}).get(val, 0)
            if not gid:
                return
            self._discord_set_guild(gid)
            self._fill_channel_combos()
            return
        cfgkey = "discord_channel_id" if key == "channel" else "discord_log_channel_id"
        if val == "(none)" and key == "log":
            self.config[cfgkey] = ""
        else:
            cid = getattr(self, "_discord_cmap", {}).get(val, 0)
            if not cid:
                return
            self.config[cfgkey] = str(cid)
        self.save_settings()
        self._refresh_discord_page()

    def _discord_set_guild(self, gid):
        new = str(gid) if gid else ""
        if new == str(self.config.get("discord_guild_id", "") or ""):
            return
        self.config["discord_guild_id"] = new
        self.config["discord_channel_id"] = ""
        self.config["discord_log_channel_id"] = ""
        self.save_settings()

    def _did(self, key):
        try:
            return int(str(self.config.get(key, "") or "0").strip() or 0)
        except Exception:
            return 0

    def _toggle_b64_ui(self):
        self.config["b64_filter"] = bool(self._b64_var.get())
        self.save_settings()
        self._sync_security_marks()
        self.toast("Base64 filter " + ("on." if self._b64_var.get() else "off."), "ok" if self._b64_var.get() else "warn")

    def _palette_toggle_b64(self):
        self.config["b64_filter"] = not self._b64_filter_on()
        self.save_settings()
        self._sync_security_marks()
        self.toast("Base64 filter " + ("on." if self._b64_filter_on() else "off."), "ok" if self._b64_filter_on() else "warn")

    def _clear_offenders(self):
        n = len(self.b64_offenders)
        self.b64_offenders = set()
        self._save_offenders()
        self._sync_security_marks()
        self.toast(f"Cleared {n} blocked sender{'s' if n != 1 else ''}.", "ok")

    def _sync_security_marks(self):
        on = self._b64_filter_on()
        if hasattr(self, "_b64_var"):
            try: self._b64_var.set(on)
            except Exception: pass
        t = self._tok
        if hasattr(self, "_b64_pill"):
            try:
                self._b64_pill.configure(text="ON" if on else "OFF",
                                         bg=t["ok_tint"] if on else t["bad_tint"],
                                         fg=t["ok_soft"] if on else t["bad_soft"],
                                         font=_sf("ui", 8, "semi"))
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        if hasattr(self, "_b64_block_lbl"):
            n = len(getattr(self, "b64_offenders", ()))
            try:
                self._b64_block_lbl.configure(text=(f"{n} sender{'s' if n != 1 else ''} currently blocked." if n else "No senders blocked."))
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _refresh_discord_page(self):
        if not getattr(self, "_discord_built", False):
            return
        t = self._tok
        br = getattr(self, "discord", None)
        try:
            self._discord_logo(self._discord_logo_cv, int(54 * getattr(self, "_ui_scale", 1.0)))
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        running = bool(br and br.running)
        if hasattr(self, "btn_crossplay"):
            mode = self._discord_mode_var.get() if hasattr(self, "_discord_mode_var") else "crossplay"
            if running:
                label = "Stop the Discord bot"
                var = "danger"
            else:
                label = "Enable Discord & YouTube crossplay" if mode == "crossplay" else "Enable Discord bot"
                var = "primary"
            self.btn_crossplay.configure(text=label)
            self.btn_crossplay._variant = var
            try: self.btn_crossplay.studio_style(None, _sf("ui", 11, "semi"))
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        self._sync_security_marks()
        state = (br.state if br else "stopped")
        detail = (br.detail if br else "")
        colors = {"online": "ok", "connecting": "warn", "installing": "warn", "error": "bad", "stopped": "muted"}
        if hasattr(self, "_discord_state_lbl"):
            txt = {"online": "Online", "connecting": "Connecting", "installing": "Installing discord.py",
                   "error": "Problem", "stopped": "Stopped"}.get(state, state.title())
            if br and br.online:
                ch = br.channel_name(self._did("discord_channel_id"))
                txt = f"Online as {br.user_tag}" + (f"  -  commands from {ch}" if ch else "  -  pick a command channel below")
            elif detail:
                txt = f"{txt} - {detail}"
            self._discord_state_lbl.configure(text=txt, fg=_studio_color(colors.get(state, "muted"), "#A1A1AA"))

    def _discord_poll(self):
        if not getattr(self, "running", True):
            return
        br = getattr(self, "discord", None)
        try:
            if br is not None and getattr(self, "_discord_built", False):
                if br.guilds_dirty:
                    self._fill_discord_combos()
                if br.dirty:
                    br.dirty = False
                    self._refresh_discord_page()
                    if hasattr(self, "_discord_stat_lbls"):
                        st = br.stats
                        self._discord_stat_lbls["bot"].configure(
                            text={"online": "online", "connecting": "...", "installing": "setup", "error": "error", "stopped": "off"}.get(br.state, br.state),
                            fg=_studio_color({"online": "ok", "error": "bad"}.get(br.state, "muted"), "#A1A1AA"))
                        for key in ("in", "cmds", "shots", "blocked", "errors"):
                            self._discord_stat_lbls[key].configure(text=str(st.get(key, 0)))
                    ev = list(br.events)[-40:]
                    cur = getattr(self, "_discord_ev_n", -1)
                    if len(ev) != cur:
                        self._discord_ev_n = len(ev)
                        self.discord_events.configure(state="normal")
                        self.discord_events.delete("1.0", "end")
                        for ts, line in ev:
                            self.discord_events.insert("end", f"{ts}  {line}\n")
                        self.discord_events.see("end")
                        self.discord_events.configure(state="disabled")
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        try:
            self.root.after(700, self._discord_poll)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _plugin_chat(self, user, message, is_mod, is_owner, source):
        pm = getattr(self, "plugins", None)
        if pm is not None:
            pm.emit("chat", user, str(message), bool(is_mod), bool(is_owner), source)

    def _plugin_owner_cmd(self, arg):
        pm = self.plugins
        parts = arg.split()
        if not parts:
            names = [f"{p.id}{'' if p.loaded else ' (off)'}" for p in pm.plugins.values()]
            self.log("[plugins]", "installed: " + (", ".join(names) or "none"), "sysmsg")
            return
        act, pid = parts[0].lower(), (parts[1].lower() if len(parts) > 1 else "")
        if act == "reload" and not pid:
            pm.reload_all()
        elif act in ("reload", "enable", "disable") and pid in pm.plugins:
            if act == "reload": pm.reload(pid)
            else: pm.set_enabled(pid, act == "enable")
        else:
            self.log("[plugins]", "usage: !plugin [reload|enable|disable] <id>   (reload with no id reloads all)", "sysmsg")
            return
        self.log("[plugins]", f"{act} {pid or 'all'}: done", "sysmsg")

    # -- Plugins page ------------------------------------------------------
    def build_plugins_tab(self):
        wrap = self.make_scrollable(self.tab_plugins)
        t = self._tok
        head = tk.Frame(wrap, bg=t["bg"]); head._st = {"bg": "bg"}
        head.pack(fill="x", padx=26, pady=(22, 10))
        self._st_label(head, "Installed plugins", bg="bg", fg="hi", font=("display", 15)).pack(side="left")
        for txt, fn, var in (("Plugin market", lambda: self.tabview.select(self.tab_market), "primary"),
                             ("New plugin", self._plugin_new, "neutral"),
                             ("Docs", self.plugin_docs_open, "neutral"),
                             ("Open folder", lambda: self._open_file(plugins_dir()), "neutral"),
                             ("Reload all", lambda: self._run_bg("plugins-reload", self.plugins.reload_all), "neutral")):
            self._st_button(head, txt, fn, var, 9).pack(side="right", padx=(8, 0), ipady=3, ipadx=8)
        self._st_label(wrap, "Plugins add chat commands, timers and panels. They live in the plugins folder next to "
                             "yt2vm.py and run with the same access as the app, so only install ones you trust.",
                       bg="bg", fg="muted", font=("ui", 9), anchor="w", justify="left", wraplength=820).pack(fill="x", padx=26, pady=(0, 12))
        self._plugins_list = tk.Frame(wrap, bg=t["bg"]); self._plugins_list._st = {"bg": "bg"}
        self._plugins_list.pack(fill="x", padx=26, pady=(0, 24))
        self.plugins.add_listener(self._render_plugins)
        self._render_plugins()

    def _render_plugins(self):
        host = getattr(self, "_plugins_list", None)
        if host is None:
            return
        for w in host.winfo_children():
            w.destroy()
        pm = self.plugins
        items = sorted(pm.plugins.values(), key=lambda p: p.name.lower())
        if not items:
            o, c = self._st_card(host)
            o.pack(fill="x")
            self._st_label(c, "No plugins installed yet.", fg="hi", font=("ui", 11, "semi"), anchor="w").pack(fill="x", padx=16, pady=(14, 2))
            self._st_label(c, "Grab one from the Plugin market, or drop a folder with plugin.json + plugin.py into the plugins folder "
                              "and press Reload all. docs/plugins.md shows how to write your own.",
                           fg="muted", font=("ui", 9), anchor="w", justify="left", wraplength=760).pack(fill="x", padx=16, pady=(0, 14))
        for p in items:
            self._plugin_card(host, p)
        try: self._studio_restyle(target=host)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _plugin_card(self, host, p):
        m = p.manifest
        on = self.plugins.is_enabled(p.id)
        o, c = self._st_card(host)
        o.pack(fill="x", pady=(0, 12))
        top = tk.Frame(c, bg=self._tok["card"]); top._st = {"bg": "card"}
        top.pack(fill="x", padx=16, pady=(14, 0))
        self._st_label(top, p.name, fg="hi", font=("ui", 12, "semi")).pack(side="left")
        self._st_label(top, f"  v{m.get('version')}  by {m.get('author')}", fg="faint", font=("ui", 9)).pack(side="left", pady=(3, 0))
        if p.error: state, col = "Error", "bad"
        elif p.loaded: state, col = "Running", "ok"
        elif on: state, col = "Not loaded - click Reload", "warn"
        else: state, col = "Disabled", "faint"
        self._st_label(top, "● " + state, fg=col, font=("ui", 9, "semi")).pack(side="right")
        if m.get("description"):
            self._st_label(c, m["description"], fg="muted", font=("ui", 9), anchor="w", justify="left",
                           wraplength=760).pack(fill="x", padx=16, pady=(4, 0))
        if p.error:
            self._st_label(c, p.error, fg="bad", font=("mono", 9), anchor="w", justify="left",
                           wraplength=760).pack(fill="x", padx=16, pady=(6, 0))
        if p.commands:
            pre = self.command_prefix or "!"
            cmds = "   ".join(f"{pre}{n}" + (" (mods)" if s["mod_only"] else "") for n, s in sorted(p.commands.items()))
            self._st_label(c, "Commands:  " + cmds, fg="text", font=("mono", 9), anchor="w", justify="left",
                           wraplength=760).pack(fill="x", padx=16, pady=(6, 0))
        row = tk.Frame(c, bg=self._tok["card"]); row._st = {"bg": "card"}
        row.pack(fill="x", padx=12, pady=(10, 14))
        self._st_button(row, "Disable" if on else "Enable",
                        lambda: self._run_bg(f"plugin-{p.id}", self.plugins.set_enabled, p.id, not on),
                        "neutral" if on else "go", 9).pack(side="left", padx=4, ipadx=8)
        self._st_button(row, "Reload", lambda: self._run_bg(f"plugin-{p.id}", self.plugins.reload, p.id),
                        "neutral", 9).pack(side="left", padx=4, ipadx=8)
        self._st_button(row, "Open folder", lambda: self._open_file(p.folder), "neutral", 9).pack(side="left", padx=4, ipadx=8)
        if self._plugin_submittable(p)[0]:
            self._st_button(row, "Submit", lambda: self._plugin_submit(p.id), "neutral", 9).pack(side="left", padx=4, ipadx=8)
        self._st_button(row, "Uninstall", lambda: self._plugin_uninstall(p.id), "danger", 9).pack(side="right", padx=4, ipadx=8)
        for title, build in list(p.panels):
            box = tk.Frame(c, bg=self._tok["card"]); box._st = {"bg": "card"}
            box.pack(fill="x", padx=16, pady=(0, 14))
            if title and title != p.name:
                self._st_label(box, title, fg="muted", font=("ui", 9, "semi"), anchor="w").pack(fill="x", pady=(0, 4))
            try:
                build(box)
            except Exception as e:
                log_crash(f"plugin {p.id} panel", e)
                self._st_label(box, f"panel failed: {e}", fg="bad", font=("mono", 9), anchor="w").pack(fill="x")

    def _plugin_uninstall(self, pid):
        p = self.plugins.plugins.get(pid)
        if p is None:
            return
        where = p.single_file or p.folder
        if not messagebox.askyesno("Uninstall plugin", f"Remove {p.name} and delete it?\n\n{where}"):
            return
        def work():
            self.plugins.unload(pid)
            root = os.path.abspath(plugins_dir())
            if p.single_file and os.path.isfile(p.single_file) and os.path.dirname(os.path.abspath(p.single_file)) == root:
                try: os.remove(p.single_file)
                except Exception as _ex: _trace(_ex_where(), _ex)
            else:
                folder = os.path.abspath(p.folder)
                if os.path.dirname(folder) == root and folder != root:
                    shutil.rmtree(folder, ignore_errors=True)
            self.plugins.discover()
            self.plugins._changed()
            self._market_changed()
            self.toast(f"Uninstalled {p.name}", "info")
        self._run_bg(f"plugin-{pid}", work)

    # -- Plugin Market page ------------------------------------------------
    def build_market_tab(self):
        wrap = self.make_scrollable(self.tab_market)
        t = self._tok
        self._market_items = []
        self._market_busy = False
        head = tk.Frame(wrap, bg=t["bg"]); head._st = {"bg": "bg"}
        head.pack(fill="x", padx=26, pady=(22, 10))
        self._st_label(head, "Plugin market", bg="bg", fg="hi", font=("display", 15)).pack(side="left")
        self._st_button(head, "Refresh", self._market_refresh, "primary", 9).pack(side="right", ipady=3, ipadx=10)
        self._st_button(head, "Docs", lambda: self.plugin_docs_open("plugin-market"), "neutral", 9).pack(side="right", padx=(0, 8), ipady=3, ipadx=8)

        server = market_server_url()
        if server:
            self._st_label(wrap, f"Every plugin here was reviewed before it was published.  Market: {server}", bg="bg",
                           fg="muted", font=("ui", 9), anchor="w").pack(fill="x", padx=26, pady=(0, 12))
        else:
            so, sc = self._st_card(wrap)
            so.pack(fill="x", padx=26, pady=(0, 12))
            self._st_label(sc, "The plugin market isn't available in this build yet.", fg="hi", font=("ui", 11, "semi"),
                           anchor="w").pack(fill="x", padx=16, pady=(14, 2))
            self._st_label(sc, "You can still install plugins by copying their folder into the plugins folder and pressing "
                               "Reload all on the Plugins page.", fg="muted", font=("ui", 9), anchor="w", justify="left",
                           wraplength=760).pack(fill="x", padx=16, pady=(0, 14))

        frow = tk.Frame(wrap, bg=t["bg"]); frow._st = {"bg": "bg"}
        frow.pack(fill="x", padx=26, pady=(0, 8))
        self._st_label(frow, "Search", bg="bg", fg="muted", font=("ui", 9)).pack(side="left")
        self.market_filter = tk.Entry(frow, font=_sf("ui", 10), bg=t["input"], fg=t["hi"], insertbackground=t["hi"], bd=0,
                                      highlightthickness=1, highlightbackground=t["line"], highlightcolor=t["accent"])
        self.market_filter._st = {"bg": "input", "fg": "hi"}
        self.market_filter.pack(side="left", fill="x", expand=True, padx=(8, 12), ipady=5)
        self.market_filter.bind("<KeyRelease>", lambda e: self._render_market())
        self.market_status = self._st_label(frow, "Press Refresh to load the market.", bg="bg", fg="faint", font=("ui", 9))
        self.market_status.pack(side="right")

        self._market_list = tk.Frame(wrap, bg=t["bg"]); self._market_list._st = {"bg": "bg"}
        self._market_list.pack(fill="x", padx=26, pady=(0, 24))
        self.plugins.add_listener(self._market_changed)
        if self.config.get("plugin_market_autoload", True):
            self.root.after(1500, self._market_refresh)

    def _market_set_status(self, text, fg="faint"):
        lbl = getattr(self, "market_status", None)
        if lbl is not None:
            self.ui(lambda: lbl.configure(text=text, fg=_studio_color(fg)))

    def _market_refresh(self):
        if getattr(self, "_market_busy", False):
            return
        server = market_server_url()
        if not server:
            self._market_set_status("No market in this build.")
            return
        self._market_busy = True
        self._market_set_status("Loading...")
        def work():
            url = server + "/index.json"
            try:
                self._market_items = market_fetch_index(url)["plugins"]
                self._market_set_status(f"{len(self._market_items)} plugin(s)")
            except Exception as ex:
                plog("MARKET", f"index {url} failed: {ex}")
                self._market_set_status("Couldn't reach the market - check your connection and press Refresh.", "bad")
                self.toast(f"Plugin market: {str(ex)[:120]}", "bad")
            finally:
                self._market_busy = False
            self.ui(self._render_market)
        threading.Thread(target=work, daemon=True, name="market-refresh").start()

    def _market_changed(self):
        if getattr(self, "_market_list", None) is not None:
            self.ui(self._render_market)

    def _render_market(self):
        host = getattr(self, "_market_list", None)
        if host is None:
            return
        for w in host.winfo_children():
            w.destroy()
        flt = ""
        try: flt = self.market_filter.get().strip().lower()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        shown = 0
        for e in self._market_items:
            blob = " ".join(str(e.get(k, "")) for k in ("id", "name", "author", "description")) + " " + " ".join(e.get("tags") or [])
            if flt and flt not in blob.lower():
                continue
            self._market_card(host, e)
            shown += 1
        if not shown and self._market_items:
            self._st_label(host, "Nothing matches that search.", bg="bg", fg="faint", font=("ui", 10)).pack(anchor="w", pady=8)
        try: self._studio_restyle(target=host)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _market_card(self, host, e):
        t = self._tok
        inst = self.plugins.plugins.get(e["id"])
        o, c = self._st_card(host)
        o.pack(fill="x", pady=(0, 12))
        top = tk.Frame(c, bg=t["card"]); top._st = {"bg": "card"}
        top.pack(fill="x", padx=16, pady=(14, 0))
        self._st_label(top, e.get("name") or e["id"], fg="hi", font=("ui", 12, "semi")).pack(side="left")
        self._st_label(top, f"  v{e.get('version', '?')}  by {e.get('author', 'unknown')}", fg="faint", font=("ui", 9)).pack(side="left", pady=(3, 0))
        if e.get("description"):
            self._st_label(c, e["description"], fg="muted", font=("ui", 9), anchor="w", justify="left",
                           wraplength=760).pack(fill="x", padx=16, pady=(4, 0))
        meta = []
        if e.get("tags"): meta.append("  ".join("#" + str(x) for x in e["tags"]))
        if e.get("commands"): meta.append("adds " + " ".join("!" + str(x).lstrip("!") for x in e["commands"]))
        if meta: self._st_label(c, "   ·   ".join(meta), fg="faint", font=("ui", 8), anchor="w", justify="left",
                       wraplength=760).pack(fill="x", padx=16, pady=(6, 0))
        row = tk.Frame(c, bg=t["card"]); row._st = {"bg": "card"}
        row.pack(fill="x", padx=12, pady=(10, 14))
        if inst is None:
            self._st_button(row, "Install", lambda: self._market_install(e), "primary", 9).pack(side="left", padx=4, ipadx=10)
        else:
            have = inst.manifest.get("version", "0")
            if _version_tuple(e.get("version")) > _version_tuple(have):
                self._st_button(row, f"Update {have} → {e.get('version')}", lambda: self._market_install(e), "primary", 9).pack(side="left", padx=4, ipadx=10)
            else:
                self._st_label(row, f"✓ Installed (v{have})", fg="ok", font=("ui", 9, "semi")).pack(side="left", padx=6)
                self._st_button(row, "Reinstall", lambda: self._market_install(e), "neutral", 9).pack(side="left", padx=4, ipadx=8)
            self._st_button(row, "Uninstall", lambda: self._plugin_uninstall(e["id"]), "danger", 9).pack(side="right", padx=4, ipadx=8)
        if e.get("homepage"):
            self._st_button(row, "Homepage", lambda: self._market_open_home(e["homepage"]), "neutral", 9).pack(side="left", padx=4, ipadx=8)

    def _market_open_home(self, url):
        if str(url).lower().startswith(("https://", "http://")):
            import webbrowser
            webbrowser.open(url)

    def _market_install(self, e):
        name = e.get("name") or e["id"]
        self._market_set_status(f"Installing {name}...")
        def work():
            try:
                self.plugins.unload(e["id"])
                market_install(e, progress=lambda s: self._market_set_status(s))
                self.plugins._enabled_map()[e["id"]] = True
                self.save_settings()
                self.plugins.discover()
                ok = self.plugins.load(e["id"])
                self._market_set_status(f"Installed {name}" if ok else f"{name} installed but failed to load - see Plugins page",
                                        "ok" if ok else "bad")
                self.toast(f"Installed {name}" if ok else f"{name} failed to load", "ok" if ok else "bad")
            except Exception as ex:
                log_crash(f"market install {e['id']}", ex)
                self._market_set_status(f"Install failed: {ex}", "bad")
                self.toast(f"Install failed: {ex}", "bad")
                self.plugins.discover()
                if self.plugins.is_enabled(e["id"]):
                    self.plugins.load(e["id"])
            self._market_changed()
        threading.Thread(target=work, daemon=True, name=f"market-install-{e['id']}").start()

    def _plugin_new(self):
        from tkinter import simpledialog
        pid = simpledialog.askstring("New plugin", "Plugin id (lowercase letters, digits, - and _):", parent=self.root)
        if not pid:
            return
        try:
            folder, cmd = plugin_scaffold(pid)
        except Exception as e:
            messagebox.showerror("New plugin", str(e))
            return
        def work():
            self.plugins.discover()
            ok = self.plugins.load(pid.strip().lower())
            pre = self.command_prefix or "!"
            self.toast(f"Created plugins/{os.path.basename(folder)} - try {pre}{cmd}" if ok else "Plugin created but failed to load",
                       "ok" if ok else "bad")
            self.ui(self._open_file, folder)
        self._run_bg("plugin-new", work)

    def _plugin_submittable(self, p):
        """(True, "") when this plugin may be submitted from here; otherwise (False, reason).
        Plugins installed from the market belong to their author - only the holder of the owner key can submit them."""
        if p.single_file:
            return False, ("Single-file plugins (.py / .y2vp) can't be submitted to the market. "
                           "Put it in its own folder with a plugin.json first, then submit that.")
        if os.path.isfile(os.path.join(p.folder, ".market.json")):
            server = market_server_url()
            if not self.config.get("plugin_owner_keys", {}).get(server, {}).get(p.id):
                return False, (f"{p.name} was installed from the plugin market, so it belongs to its author. "
                               "Only the author can submit new versions of it.")
        return True, ""

    def _plugin_submit(self, pid):
        p = self.plugins.plugins.get(pid)
        if p is None:
            return
        ok, why = self._plugin_submittable(p)
        if not ok:
            messagebox.showinfo("Submit plugin", why)
            return
        server = market_server_url()
        if not server:
            messagebox.showinfo("Submit plugin", "This build of YT2VM has no plugin market yet, so there is nowhere to submit to.")
            return
        keys = self.config.setdefault("plugin_owner_keys", {}).setdefault(server, {})
        from tkinter import simpledialog
        note = simpledialog.askstring(
            "Submit plugin",
            f"Upload {p.name} {p.manifest.get('version')} to\n{server}\n\n"
            + ("This is an update to your plugin." if keys.get(pid) else "This id is new on the market - it will be reserved for you.")
            + "\n\nNote for the reviewer (optional):", parent=self.root)
        if note is None:
            return
        def work():
            try:
                res = market_submit(server, p.folder, keys.get(pid, ""), note)
            except ValueError as e:
                errs = e.args[0] if e.args and isinstance(e.args[0], list) else [str(e)]
                self.ui(messagebox.showerror, "Submit plugin", "The server refused the upload:\n\n- " + "\n- ".join(map(str, errs)))
                return
            except Exception as e:
                log_crash(f"submit {pid}", e)
                self.ui(messagebox.showerror, "Submit plugin", f"Upload failed: {e}")
                return
            msg = f"{p.name} {res.get('version')} was uploaded."
            msg += ("\n\nIt is waiting for review - it shows up in the market once an admin approves it."
                    if res.get("status") == "pending" else "\n\nIt is published now.")
            if res.get("owner_key"):
                keys[pid] = res["owner_key"]
                self.save_settings()
                msg += ("\n\nYour owner key for this plugin is saved in settings.json. You need it to publish updates, "
                        "so back it up:\n\n" + res["owner_key"])
            plog("MARKET", f"submitted {pid} {res.get('version')} to {server}: {res.get('status')}")
            self.toast(f"Submitted {p.name} {res.get('version')}", "ok")
            self.ui(messagebox.showinfo, "Submit plugin", msg)
        self._run_bg(f"plugin-submit-{pid}", work)

    # -- Plugin Docs page --------------------------------------------------
    def plugin_docs_open(self, doc_key=None, anchor=None):
        self.tabview.select(self.tab_plugindocs)
        if doc_key:
            self.root.after(60, lambda: self._docs_jump(f"{doc_key}#{anchor}" if anchor else f"{doc_key}#"))

    def build_plugindocs_tab(self):
        t = self._tok
        wrap = tk.Frame(self.tab_plugindocs, bg=t["bg"]); wrap._st = {"bg": "bg"}
        wrap.pack(fill="both", expand=True, padx=26, pady=(22, 18))
        head = tk.Frame(wrap, bg=t["bg"]); head._st = {"bg": "bg"}
        head.pack(fill="x", pady=(0, 10))
        self._st_label(head, "Plugin docs", bg="bg", fg="hi", font=("display", 15)).pack(side="left")
        for txt, fn, var in (("New plugin", self._plugin_new, "primary"),
                             ("Plugins", lambda: self.tabview.select(self.tab_plugins), "neutral"),
                             ("Plugin market", lambda: self.tabview.select(self.tab_market), "neutral")):
            self._st_button(head, txt, fn, var, 9).pack(side="right", padx=(8, 0), ipady=3, ipadx=8)
        self.docs_find = tk.Entry(head, width=26, font=_sf("ui", 10), bg=t["input"], fg=t["hi"], insertbackground=t["hi"], bd=0,
                                  highlightthickness=1, highlightbackground=t["line"], highlightcolor=t["accent"])
        self.docs_find._st = {"bg": "input", "fg": "hi"}
        self.docs_find.pack(side="right", padx=(8, 4), ipady=5)
        self.docs_find.bind("<Return>", lambda e: self._docs_search())
        self._st_label(head, "Find (Enter)", bg="bg", fg="faint", font=("ui", 9)).pack(side="right")

        body = tk.Frame(wrap, bg=t["bg"]); body._st = {"bg": "bg"}
        body.pack(fill="both", expand=True)
        self.docs_nav = tk.Listbox(body, width=30, activestyle="none", bd=0, highlightthickness=1, exportselection=False,
                                   font=_sf("ui", 10))
        self.docs_nav._studio_skip = True
        self.docs_nav.pack(side="left", fill="y", padx=(0, 12))
        self.docs_nav.bind("<<ListboxSelect>>", lambda e: self._docs_nav_pick())
        tw = tk.Frame(body, bg=t["line"]); tw._st = {"bg": "line"}
        tw.pack(side="left", fill="both", expand=True)
        self.docs_text = tk.Text(tw, wrap="word", bd=0, highlightthickness=0, padx=22, pady=16, cursor="arrow",
                                 font=_sf("ui", 10), spacing1=2, spacing3=4)
        self.docs_text._studio_skip = True
        sb = ttk.Scrollbar(tw, orient="vertical", command=self.docs_text.yview)
        self.docs_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.docs_text.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        self.docs_text.bind("<Key>", lambda e: None if (e.state & 0x4 and e.keysym.lower() in ("c", "a")) else "break")
        self._docs_nav_marks = []
        self._docs_render()
        self._docs_paint()
        self._repaint_hooks = getattr(self, "_repaint_hooks", [])
        self._repaint_hooks.append(self._docs_paint)

    def _docs_paint(self):
        tx = getattr(self, "docs_text", None)
        if tx is None:
            return
        t = self._tok
        mono = _sf("mono", 9)
        tx.configure(bg=t["card"], fg=t["text"], insertbackground=t["hi"], selectbackground=t["raised"], selectforeground=t["hi"])
        self.docs_nav.configure(bg=t["panel"], fg=t["text"], selectbackground=t["raised"], selectforeground=t["hi"],
                                highlightbackground=t["line"], highlightcolor=t["line"])
        tx.tag_configure("h1", font=_sf("display", 20), foreground=t["hi"], spacing1=6, spacing3=10)
        tx.tag_configure("h2", font=_sf("display", 15), foreground=t["hi"], spacing1=18, spacing3=6)
        tx.tag_configure("h3", font=_sf("ui", 11, "bold"), foreground=t["hi"], spacing1=12, spacing3=4)
        tx.tag_configure("bold", font=_sf("ui", 10, "bold"), foreground=t["hi"])
        tx.tag_configure("code", font=mono, foreground=t["accent"], background=t["input"])
        tx.tag_configure("pre", font=mono, foreground=t["text"], background=t["input"], lmargin1=14, lmargin2=14,
                         spacing1=0, spacing3=0)
        tx.tag_configure("bullet", lmargin1=10, lmargin2=26)
        tx.tag_configure("bullet2", lmargin1=30, lmargin2=46)
        tx.tag_configure("quote", foreground=t["muted"], lmargin1=14, lmargin2=14)
        tx.tag_configure("tkey", lmargin1=10, lmargin2=10, spacing1=6)
        tx.tag_configure("tcell", foreground=t["muted"], lmargin1=28, lmargin2=28, spacing3=2)
        tx.tag_configure("tlabel", foreground=t["faint"])
        tx.tag_configure("rule", font=_sf("ui", 4))
        tx.tag_configure("link", foreground=t["info"], underline=True)
        tx.tag_configure("hit", background=t["warn"], foreground=t["bg"])
        tx.tag_raise("hit")

    def _docs_inline(self, text, tags):
        tx = self.docs_text
        pat = re.compile(r"(`[^`]+`)|(\*\*[^*]+\*\*)|(\[[^\]]+\]\([^)\s]+\))|(<https?://[^>\s]+>)")
        pos = 0
        for m in pat.finditer(text):
            if m.start() > pos:
                tx.insert("end", text[pos:m.start()], tags)
            tok = m.group(0)
            if m.group(1):
                tx.insert("end", tok[1:-1], tags + ("code",))
            elif m.group(2):
                tx.insert("end", tok[2:-2], tags + ("bold",))
            else:
                if m.group(3):
                    label, target = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", tok).groups()
                else:
                    label = target = tok[1:-1]
                self._docs_link_n += 1
                lt = f"lnk{self._docs_link_n}"
                tx.insert("end", label, tags + ("link", lt))
                tx.tag_bind(lt, "<Button-1>", lambda e, tg=target: self._docs_follow(tg))
                tx.tag_bind(lt, "<Enter>", lambda e: tx.configure(cursor="hand2"))
                tx.tag_bind(lt, "<Leave>", lambda e: tx.configure(cursor="arrow"))
            pos = m.end()
        if pos < len(text):
            tx.insert("end", text[pos:], tags)

    @staticmethod
    def _docs_slug(text):
        return re.sub(r"[^\w\- ]", "", re.sub(r"[`*]", "", text).lower()).strip().replace(" ", "-")

    def _docs_render(self):
        tx = self.docs_text
        tx.configure(state="normal")
        tx.delete("1.0", "end")
        self.docs_nav.delete(0, "end")
        self._docs_nav_marks = []
        self._docs_link_n = 0
        for key, title, md in PLUGIN_DOCS:
            self._docs_key = key
            tx.mark_set(f"{key}#", "end-1c"); tx.mark_gravity(f"{key}#", "left")
            self.docs_nav.insert("end", title)
            self._docs_nav_marks.append(f"{key}#")
            lines = md.strip("\n").splitlines()
            i, in_code = 0, False
            while i < len(lines):
                line = lines[i]
                if line.startswith("```"):
                    in_code = not in_code
                    if not in_code:
                        tx.insert("end", "\n")
                    i += 1; continue
                if in_code:
                    tx.insert("end", line + "\n", ("pre",)); i += 1; continue
                h = re.match(r"(#{1,3}) (.*)", line)
                if h:
                    lvl, text = len(h.group(1)), h.group(2).strip()
                    mk = f"{key}#{self._docs_slug(text)}"
                    tx.mark_set(mk, "end-1c"); tx.mark_gravity(mk, "left")
                    self._docs_inline(text, (f"h{lvl}",)); tx.insert("end", "\n", (f"h{lvl}",))
                    if lvl == 2:
                        self.docs_nav.insert("end", "    " + re.sub(r"[`*]", "", text))
                        self._docs_nav_marks.append(mk)
                    i += 1; continue
                if line.startswith("|"):
                    rows = []
                    while i < len(lines) and lines[i].startswith("|"):
                        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                        if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                            rows.append(cells)
                        i += 1
                    head, rest = rows[0], rows[1:]
                    for r in rest:
                        self._docs_inline(r[0], ("tkey", "bold")); tx.insert("end", "\n", ("tkey",))
                        for j, c in enumerate(r[1:], 1):
                            if len(head) > 2 and j < len(head):
                                tx.insert("end", f"{head[j]}: ", ("tcell", "tlabel"))
                            self._docs_inline(c, ("tcell",)); tx.insert("end", "\n", ("tcell",))
                    tx.insert("end", "\n")
                    continue
                b = re.match(r"(\s*)([-*]|\d+\.) (.*)", line)
                if b:
                    tag = "bullet2" if len(b.group(1)) >= 2 else "bullet"
                    mark = "•  " if b.group(2) in ("-", "*") else b.group(2) + "  "
                    tx.insert("end", mark, (tag,)); self._docs_inline(b.group(3), (tag,)); tx.insert("end", "\n", (tag,))
                    i += 1; continue
                if line.startswith(">"):
                    self._docs_inline(line.lstrip("> "), ("quote",)); tx.insert("end", "\n", ("quote",))
                    i += 1; continue
                if line.strip() == "---":
                    tx.insert("end", "\n", ("rule",)); i += 1; continue
                if line.strip():
                    self._docs_inline(line.strip(), ())
                tx.insert("end", "\n")
                i += 1
            tx.insert("end", "\n\n")
        tx.configure(state="disabled")

    def _docs_jump(self, mark):
        tx = getattr(self, "docs_text", None)
        if tx is None:
            return False
        if mark not in tx.mark_names():
            return False
        tx.yview(mark)
        return True

    def _docs_follow(self, target):
        target = str(target)
        if target.lower().startswith(("http://", "https://")):
            self._market_open_home(target)
            return
        if target.startswith("#"):
            key = "plugins"
            try:
                top = self.docs_text.index("@0,0")
                for k, _t, _m in PLUGIN_DOCS:
                    if self.docs_text.compare(f"{k}#", "<=", top):
                        key = k
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            self._docs_jump(f"{key}{target}")
            return
        page, _, anchor = target.partition("#")
        page = os.path.basename(page)
        if page.endswith(".md"):
            self._docs_jump(f"{page[:-3]}#{anchor}")

    def _docs_nav_pick(self):
        sel = self.docs_nav.curselection()
        if sel and sel[0] < len(self._docs_nav_marks):
            self._docs_jump(self._docs_nav_marks[sel[0]])

    def _docs_search(self):
        tx = self.docs_text
        q = self.docs_find.get().strip()
        tx.tag_remove("hit", "1.0", "end")
        if not q:
            return
        start = getattr(self, "_docs_hit_end", "1.0")
        pos = tx.search(q, start, stopindex="end", nocase=True) or tx.search(q, "1.0", stopindex="end", nocase=True)
        if not pos:
            self.toast(f"No match for \"{q}\"", "bad")
            return
        end = f"{pos}+{len(q)}c"
        tx.tag_add("hit", pos, end)
        self._docs_hit_end = end
        tx.see(pos)

    def build_diagnostics_tab(self):
        wrap = tk.Frame(self.tab_diag, bg="#09090B"); wrap.pack(fill="both", expand=True, padx=26, pady=18)
        top = tk.Frame(wrap, bg="#09090B"); top.pack(fill="x")
        tk.Label(top, text="DIAGNOSTICS", font=("Segoe UI", 15, "bold"), bg="#09090B", fg=self.accent_main).pack(side="left")
        brow = tk.Frame(wrap, bg="#09090B"); brow.pack(fill="x")
        for _i, (_txt, _col, _fn) in enumerate((("Run checks", "#10B981", self._refresh_diag),
                                ("Copy report", "#27272A", self._copy_diag),
                                ("Open session log", "#27272A", lambda: self._open_file(SESSION_LOG)),
                                ("Open crash log", "#EF4444", lambda: self._open_file(CRASH_LOG)),
                                ("Open debug log", "#27272A", self._open_debug_log),
                                ("Show / hide console", "#27272A", lambda: self._toggle_console()))):
            tk.Button(brow, text=_txt, font=("Segoe UI", 9, "bold"), bg=_col, fg="white", bd=0, cursor="hand2",
                      command=_fn).grid(row=_i // 3, column=_i % 3, sticky="we", padx=(0, 8), pady=(0, 6))
        for _c in range(3):
            brow.columnconfigure(_c, weight=1, uniform="diagbtn")
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
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _open_file(self, path):
        try:
            if not os.path.exists(path):
                self.log("[system]", f"[warn] {path} does not exist yet.", "sysmsg"); return
            if platform.system() == "Windows": os.startfile(path)
            elif platform.system() == "Darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log("[system]", f"[error] open {path}: {e}", "err")

    def _open_debug_log(self):
        try:
            if not os.path.exists(_dbf):
                self.log("[system]", f"[warn] no debug log yet - run with --debug.", "sysmsg"); return
            if platform.system() == "Windows": os.startfile(_dbf)
            elif platform.system() == "Darwin": subprocess.Popen(["open", _dbf])
            else: subprocess.Popen(["xdg-open", _dbf])
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
            plog("NET", f"local ipv4 detected: {ip or 'none'}")
            self.ui(lambda: self.detected_ip_lbl.config(
                text=f"this pc: {ip or 'not detected'}   (vnc is tried on 127.0.0.1 and {ip or 'lan ip'})",
                fg=("#10B981" if ip else "#F59E0B")))
        threading.Thread(target=_show_ip, daemon=True, name="detect-ip").start()
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
        try:
            res = getattr(self, "_vnc_status_result", None)
            if res is not None:
                self._vnc_status_result = None
                if res != getattr(self, "_vnc_status_shown", None):
                    self._vnc_status_shown = res
                    self.vnc_live.config(text=res[0], fg=res[1])
                    plog("VNC", res[0].replace("VNC INPUT: ", "vnc input: "))
            if getattr(self, "backend", "virtualbox") != "vmware":
                self._vnc_status_result = ("VNC INPUT: n/a (backend is virtualbox)", "#71717A")
            else:
                self._run_bg("vnc-status", self._vnc_status_work)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if self.running:
            try: self.root.after(6000 if self.config.get('low_power', False) else 3000, self._vnc_tick)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _vnc_status_work(self):
        vm = self._vmware()
        if vm.client is not None and (time.time() - getattr(vm, "_last_ok", 0)) < 60:
            res = (f"VNC INPUT: CONNECTED  ({vm.host}:{vm.port})", "#10B981")
        elif VMwareController._port_open(vm.host, vm.port, 0.4):
            try: running = self._vm_is_running()
            except Exception: running = True
            if not running:
                res = (f"VNC INPUT: PORT {vm.port} TAKEN BY ANOTHER VNC SERVER (TightVNC?) <- press 'Fix VNC port conflict'", "#EF4444")
            else:
                res = (f"VNC INPUT: port open, not connected yet  ({vm.host}:{vm.port})", "#F59E0B")
        else:
            res = (f"VNC INPUT: NO SERVER on {vm.host}:{vm.port}  <- enable VNC in .vmx while VM is OFF", "#EF4444")
        self._vnc_status_result = res

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
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        else:
            self.vmware.vmx = self.vmx_path
            self.vmware.vmrun_path = self.config.get("vmrun_path", self.vmrun_path)
            self.vmware.port = int(self.vnc_port)
            self.vmware.host = self.config.get("vnc_host", self.vmware.host or "127.0.0.1")
            self.vmware.auto_kill_squatters = bool(self.config.get("auto_kill_vnc", True))
            self.vmware.password = self.vnc_password
            self.vmware.keymap = self.vnc_keymap

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
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        try: self.config["vmware_settle"] = max(0.0, min(float(self.settle_entry.get().strip() or 1.0), 5.0))
        except Exception: self.config["vmware_settle"] = 1.0
        self.config["vnc_port"] = self.vnc_port
        self.config["vnc_password"] = self.vnc_password
        self.config["vnc_keymap"] = self.vnc_keymap
        self.save_settings()
        self.vmw_status.config(text="status: settings saved", fg="#10B981")

    def _scan_vms(self, root):
        def _work():
            t0 = time.time()
            found = find_vmx_files(root)
            plog("VMWARE", f"scanned for .vmx files in {root or 'default locations'}: {len(found)} found in {(time.time()-t0)*1000:.0f}ms")
            self.ui(self._render_vms, root, found)
        if not self._run_bg("scan-vmx", _work):
            plog("VMWARE", "vmx scan already running")

    def _render_vms(self, root, found):
        for w in self.vms_list_frame.winfo_children(): w.destroy()
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
                            except Exception as _ex:
                                _trace(_ex_where(), _ex)
                            vm.ensure_vnc_in_vmx()
                            msg = why + " - .vmx updated, start the VM now"
                        else:
                            msg = f"no conflict: port {vm.port} is free for this VM"
                elif action == "forget_pw":
                    try:
                        if os.path.exists(_vpf): os.remove(_vpf)
                        msg = f"cleared {_vpf}"
                    except Exception as e:
                        msg = f"could not clear: {e}"
                elif action == "clear_pw":
                    vm.password = ""
                    self.vnc_password = ""
                    self.config["vnc_password"] = ""
                    self.save_settings()
                    try: self.vnc_pw_entry.delete(0, "end")
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
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
                plog("VMWARE", f"action {action}: {msg}")
                self.ui(lambda: self.vmw_status.config(text=f"status: {msg}", fg="#10B981" if "fail" not in msg and "could not" not in msg else "#EF4444"))
            except Exception as e:
                _emsg = str(e)
                plog("VMWARE", f"action {action} crashed: {type(e).__name__}: {e}")
                self.ui(lambda m=_emsg: self.vmw_status.config(text=f"status: {m}", fg="#EF4444"))
        plog("VMWARE", f"action requested: {action}")
        threading.Thread(target=_go, daemon=True, name=f"vmw-{action}").start()

    def _handle_mod_command(self, cmd, arg, user, is_owner):
        a = arg.strip()
        toks = a.split()
        target = toks[0].replace("@", "").lower().strip() if toks else ""
        rest = " ".join(toks[1:]).strip()
        def flash(t, k="info", d=6): self.send_flash(t, k, d)

        if cmd in ("!tob64", "!eb64"):
            if not is_owner:
                self.log("[system]", f"[warn] {user}: only the owner can switch the base64 filter.", "sysmsg")
                return True
            want_off = cmd == "!tob64"
            self.config["b64_filter"] = not want_off
            self.save_settings()
            if want_off:
                flash("base64 filter OFF", "err", 5)
                self.log("[system]", f"[warn] base64 filter turned OFF by {user}. !eb64 turns it back on.", "sysmsg")
            else:
                flash("base64 filter ON", "good", 5)
                self.log("[system]", f"base64 filter turned ON by {user}.", "sysmsg")
            self.ui(self._sync_security_marks)
            return True
        if cmd in ("!unblock", "!unb64"):
            if target and target in getattr(self, "b64_offenders", set()):
                self.b64_offenders.discard(target)
                self._save_offenders()
                flash(f"{target} un-blocked", "good", 5)
                self.log("[system]", f"{target} removed from the base64 block list by {user}.", "sysmsg")
                self.ui(self._sync_security_marks)
            elif target:
                self.log("[system]", f"{target} is not on the base64 block list.", "sysmsg")
            return True
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
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            return True
        if cmd == "!slowmode":
            try:
                v = max(0.0, float(target)) if target else 5.0
                self.config["viewer_cooldown"] = v; self.save_settings()
                flash(f"slowmode {v}s", "warn", 6)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
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
                _dpl.append(a.lower())
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
        if cmd == "!autoclose":
            v = not self.config.get("auto_close_crash_dialogs", True)
            self.config["auto_close_crash_dialogs"] = v; self.save_settings()
            flash(f"auto-close crash dialogs {'ON' if v else 'OFF'}", "info", 6)
            return True
        if cmd in ("!trace", "!errors"):
            for line in self._trace_report(10).split("\n"):
                self.log("[system]", line, "sysmsg")
            return True
        if cmd == "!lowpower":
            v = not self.config.get("low_power", False)
            self.config["low_power"] = v; self.save_settings()
            self.ui(self._apply_motion_level)
            flash(f"low power {'ON' if v else 'OFF'}", "info", 5)
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
        if cmd in ("!lockdown", "!lock"):
            self.chat_paused = True
            flash("LOCKED - mods only", "warn", 6)
            self.log("[system]", f"commands locked by {user} - mods only. !unlock re-opens.", "sysmsg")
            return True
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
                self.ui(lambda _a=a: self.root.title(f"{self.app_name} {version}: {vm_name} - {_a}"))
                self.log("[announcement]", a, "sysmsg")
            return True

        return False

    def _split_chain(self, msg, depth=0, trusted=False):
        p = self.command_prefix or "!"
        known = set(_KNOWN_CMDS)
        pm = getattr(self, "plugins", None)
        if pm is not None: known.update(pm.command_names())
        for k in self.custom_commands:
            if str(k).startswith(p):
                known.add(str(k)[len(p):].lower())
        pat = re.compile(r"(?:(?<=^)|(?<=\s)|(?<=\|))" + re.escape(p) + r"([A-Za-z][A-Za-z0-9_]*)(?=\s|\||$)")
        if trusted and not msg.lstrip().startswith(p):
            fixed = []
            for piece in msg.split("|"):
                w = piece.strip().split(maxsplit=1)
                if w and not w[0].startswith(p) and w[0].lower() in known:
                    lead = piece[:len(piece) - len(piece.lstrip())]
                    piece = lead + p + piece.lstrip()
                fixed.append(piece)
            msg = "|".join(fixed)
        starts = [m.start() for m in pat.finditer(msg) if m.group(1).lower() in known]
        segs = []
        for i, st in enumerate(starts):
            en = starts[i + 1] if i + 1 < len(starts) else len(msg)
            seg = msg[st:en]
            if i + 1 < len(starts):
                seg = seg.rstrip()
                if seg.endswith("|"):
                    seg = seg[:-1].rstrip()
            segs.append(seg)
        out = []
        for seg in segs:
            first = seg.split(maxsplit=1)[0].lower() if seg.split() else ""
            if first in self.custom_commands and depth < 4:
                mc = self.custom_commands[first]
                body = mc.get("value", "") if isinstance(mc, dict) else mc
                if isinstance(body, (list, tuple)):
                    body = " | ".join(str(x) for x in body)
                inner = self._split_chain(str(body), depth + 1, trusted=True)
                plog("CHAIN", f"macro {first} expanded to {len(inner)} step(s)")
                out.extend((s2, True) for s2, _t in inner)
            elif first in self.custom_commands:
                plog("CHAIN", f"macro {first} nested too deep - skipped")
            else:
                out.append((seg, trusted))
        return out

    def parse_command(self, msg, user, is_mod=False, is_owner=False):
        global total_commands_executed
        self.last_command_time = time.time()
        if not isinstance(msg, str):
            msg = str(msg or "")
        if not msg.startswith(self.command_prefix): return
        clean_user = user.replace("@", "").lower().strip()
        if clean_user in self.blacklisted_users: return
        if clean_user in getattr(self, "b64_offenders", set()) and not self._is_owner_name(clean_user, is_owner):
            plog("SECURITY", f"ignored command from base64-blocked user {clean_user}")
            return
        _tb = self.timed_bans.get(clean_user)
        if _tb is not None:
            if time.time() < _tb: return
            self.timed_bans.pop(clean_user, None)
        _src, _ref = getattr(self._tls, "src", None) or ("youtube", None)
        if _src != "discord":
            if self._guard_payload(clean_user, msg, is_owner, source=_src, ref=_ref):
                return
        for t in self.blocked_terms:
            if t in msg.lower():
                plog("CHAIN", f"{clean_user}: message dropped by blocked term {t!r}")
                return
        steps = self._split_chain(msg)
        if not steps:
            return
        if len(steps) > 1 or steps[0][1]:
            plog("CHAIN", f"{clean_user}: {len(steps)} step(s): " + " || ".join(s[:70] for s, _ in steps))
        gated_once = False
        cmds = []
        for seg, trusted in steps:
            cmds.append((seg, trusted))
        action_chain = []
        for c, _trusted in cmds:
            parts = c.strip().split(maxsplit=1)
            if not parts: continue
            raw_cmd = parts[0].lower()
            if not raw_cmd.startswith(self.command_prefix): continue
            cmd = "!" + raw_cmd[len(self.command_prefix):]
            aliases = {"!c": "!combo", "!k": "!key", "!t": "!type", "!m": "!move", "!d": "!drag", "!w": "!wait", "!kd": "!keydown", "!ku": "!keyup", "!lc": "!click", "!rc": "!rclick", "!s": "!screenshot", "!screen": "!screenshot"}
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
                self.queue_music(url, user, is_owner, is_mod, bypass)
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
            if self.chat_paused and not is_admin: continue
            append_to_json_log(logs_file, user, f"{cmd} {arg}".strip())
            if is_admin: append_to_json_log(modlogs_file, user, f"{cmd} {arg}".strip())
            if cmd == "!help":
                self._send_help(user, is_mod, is_admin, is_owner, _src)
                continue
            if cmd == "!screenshot":
                self._cmd_screenshot(user)
                continue
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
            if cmd in self.disabled_commands and not is_admin:
                plog("CHAIN", f"{clean_user}: {cmd} is disabled - step skipped")
                continue
            if not is_admin:
                _allow, _why = self._security_gate(clean_user, cmd, arg, chain_step=gated_once, trusted=_trusted)
                gated_once = True
                if not _allow:
                    plog("CHAIN", f"{clean_user}: {cmd} blocked ({_why})")
                    dbg("security", f"blocked {clean_user}: {cmd} -> {_why}")
                    if _why and not _why.startswith("cooldown"):
                        ws = getattr(self, "_warn_seen", None)
                        if ws is None or len(ws) > 5000:
                            ws = self._warn_seen = {}
                        wk = (clean_user, _why.split(" ")[0])
                        if time.time() - ws.get(wk, 0) > 30:
                            ws[wk] = time.time()
                            self.log("[system]", f"[warn] blocked {clean_user}: {_why}", "sysmsg")
                    if _why.startswith("cooldown") or _why.startswith("spam"):
                        break
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
                             except Exception as _ex:
                                 _trace(_ex_where(), _ex)
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
                    self.ui(self.start_replay)
                continue
            if cmd == "!revert":
                if self.revert_disabled:
                    self.log("[system]", "[warn] !revert is temporarily disabled while the system recovers.", "sysmsg")
                    continue
                if is_admin: action_chain.append(("revert", "", user))
                else: self.process_vote(user, f"{self.command_prefix}revert", 2)
                continue
            if cmd in ("!plugins", "!plugin"):
                if is_owner: self._plugin_owner_cmd(arg)
                continue
            _pm = getattr(self, "plugins", None)
            if _pm is not None:
                _pm.emit("command", user, cmd, arg)
                if _pm.handle_command(cmd, arg, user, is_mod or is_admin, is_owner, _src):
                    continue
            valid_user_cmds = ["!run", "!startvm", "!type", "!send", "!key", "!combo", "!keydown", "!keyup", "!move", "!abs", "!click", "!rclick", "!mclick", "!scroll", "!drag", "!wait", "!cmd", "!roll", "!coinflip"]
            if cmd in valid_user_cmds: action_chain.append((cmd, arg, user))
        if action_chain and not is_admin:
            try: max_wait = float(self.config.get("viewer_chain_max_wait", 10))
            except Exception: max_wait = 10.0
            try: max_steps = int(self.config.get("viewer_chain_max_steps", 12))
            except Exception: max_steps = 12
            kept, waited, cut = [], 0.0, 0
            for st in action_chain:
                if len(kept) >= max_steps:
                    cut += 1
                    continue
                if str(st[0]).lower().lstrip("!") in ("wait", "w"):
                    w = _wait_seconds(st[1])
                    w = min(w, max(0.0, max_wait - waited))
                    waited += w
                    if w <= 0:
                        cut += 1
                        continue
                    st = (st[0], f"{w:g}", st[2])
                kept.append(st)
            if cut or waited >= max_wait:
                plog("CHAIN", f"{clean_user}: chain trimmed to {len(kept)} step(s), {waited:g}s of waits (viewer limits {max_steps} steps / {max_wait:g}s)")
            action_chain = kept
        if action_chain: self.trigger_command_chain(action_chain, priority=bool(is_admin))

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
                                    except Exception as _ex:
                                        _trace(_ex_where(), _ex)
                                plog("CHAT", f"connecting pytchat to video {vid}")
                                chat = pytchat.create(video_id=vid, interruptable=False)
                                plog("CHAT", f"pytchat alive={chat.is_alive()} for {vid}")
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
                                except Exception as _ex:
                                    _trace(_ex_where(), _ex)
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
                            plog("CHAT", f"fetched {len(chat_data.items)} item(s)", verbose=True)
                            if is_first_fetch:
                                plog("CHAT", f"first fetch: skipping {len(chat_data.items)} backlog message(s)")
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
                                yt_cmds_off = self._discord_exclusive()
                                if msg_lower.startswith(f"{self.command_prefix}forcefixvm") and not yt_cmds_off:
                                    if is_mod:
                                        if platform.system() == "Windows":
                                            subprocess.run(["taskkill", "/F", "/FI", f"WINDOWTITLE eq *{vm_name}*",
                                                            "/IM", "VirtualBoxVM.exe", "/T"],
                                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                        self.clear_commands()
                                        self.trigger_command(("!startvm", "", c.author.name))
                                    else: self.process_vote(c.author.name, f"{self.command_prefix}forcefixvm", 2)
                                    continue
                                _shown = self._display_text(c.message)
                                add_to_history(c.author.name, _shown, "user", is_mod, is_owner)
                                if not str(c.author.name).startswith("["):
                                    self._chat_pane_msg(c.author.name, _shown, is_mod, is_owner)
                                try: self.replay_buffer.append({"t": time.time(), "u": c.author.name, "m": _shown, "mod": is_mod, "owner": is_owner})
                                except Exception as _ex:
                                    _trace(_ex_where(), _ex)
                                console_log("CHAT", f"[{c.author.name}]{' (owner)' if is_owner else (' (mod)' if is_mod else '')}: {_shown}")
                                append_to_all_msgs_log(c.author.name, _shown)
                                self._plugin_chat(c.author.name, c.message, is_mod, is_owner, "youtube")
                                if self.listening_to_chat and not yt_cmds_off:
                                    try: self.parse_command(c.message, c.author.name, is_mod, is_owner)
                                    except Exception as parse_ex:
                                        console_log("ERROR", f"parse_command error: {parse_ex}\n{traceback.format_exc()}")
                    elif chat is not None and chat != "[DEBUG_MODE]":
                        if is_connected:
                            self.log("[system]", "disconnected from yt connecting to stream", "sysmsg")
                            is_connected = False
                        if hasattr(chat, 'terminate'):
                            try: chat.terminate()
                            except Exception as _ex:
                                _trace(_ex_where(), _ex)
                        chat = None
                        connected_url = None
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 60)
                except Exception as loop_err:
                    error_count += 1
                    console_log("ERROR", f"chat loop error #{error_count}: {loop_err}\n{traceback.format_exc()}")
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
        pats = ("virtualbox - error", "virtualbox error", "guru meditation",
                "virtualboxvm", "application error")
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            elif shutil.which("xdotool"):
                try:
                    r = subprocess.run(["xdotool", "search", "--name", "(?i)virtualbox.*(error|critical)"],
                                       capture_output=True, text=True, timeout=8)
                    for wid in (r.stdout or "").split():
                        out.append((wid, "", "virtualbox error"))
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            elif shutil.which("wmctrl"):
                try: subprocess.run(["wmctrl", "-i", "-c", wid], timeout=6)
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
        if found:
            time.sleep(2.0)
            still = list_windows()
            for wid, pid, title in still:
                console_log("SYSTEM", f"[anti-stuck] dialog '{title}' still open - force killing pid {pid or '?'}")
                self.log("[system]", "[warn] crash dialog would not close - force killing it.", "sysmsg")
                if pid and pid.isdigit():
                    try: subprocess.run(["kill", "-9", pid], timeout=8,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
            try:
                if self._vm_state() == "aborted":
                    run_vbox(["discardstate", vm_name], timeout=20)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        return len(found)

    def _dismiss_crash_dialogs(self):
        if platform.system() != "Windows":
            try: return self._dismiss_crash_dialogs_linux()
            except Exception: return 0
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return 0

        PATTERNS = ("application error", "virtualbox - error", "virtualboxvm.exe",
                    "vboxsvc.exe", "vboxheadless", "guru meditation")

        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        handled = 0

        VBOX_EXES = ("virtualboxvm.exe", "virtualbox.exe", "vboxsvc.exe",
                     "vboxheadless.exe", "vboxmanage.exe", "vboxsds.exe")

        def _pid_exe(pid):
            try:
                PROCESS_QUERY = 0x1000
                h = k32.OpenProcess(PROCESS_QUERY, False, pid)
                if not h: return ""
                buf = ctypes.create_unicode_buffer(260)
                sz = wintypes.DWORD(260)
                ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz))
                k32.CloseHandle(h)
                return os.path.basename(buf.value).lower() if ok else ""
            except Exception:
                return ""

        def window_titles():
            out = []
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def cb(hwnd, _l):
                try:
                    if not u32.IsWindowVisible(hwnd): return True
                    cls = ctypes.create_unicode_buffer(64)
                    try: u32.GetClassNameW(hwnd, cls, 64)
                    except Exception: return True
                    if (cls.value or "").lower() != "#32770":
                        return True
                    n = u32.GetWindowTextLengthW(hwnd)
                    if n <= 0: return True
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u32.GetWindowTextW(hwnd, buf, n + 1)
                    t = (buf.value or "").lower()
                    if not any(p in t for p in PATTERNS):
                        return True
                    pid = wintypes.DWORD(0)
                    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    exe = _pid_exe(pid.value)
                    if exe and exe not in VBOX_EXES and exe != "werfault.exe":
                        return True
                    out.append((hwnd, buf.value, pid.value, exe))
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                return True
            try: u32.EnumWindows(EnumProc(cb), 0)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            return out

        BM_CLICK, WM_CLOSE, WM_COMMAND, IDOK = 0x00F5, 0x0010, 0x0111, 1

        def click_ok(hwnd):

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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                return True
            try: u32.EnumChildWindows(hwnd, EnumChild(cb), 0)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            if not clicked:

                WM_KEYDOWN, WM_KEYUP, VK_RETURN, VK_SPACE = 0x0100, 0x0101, 0x0D, 0x20
                try:
                    u32.SendMessageW(hwnd, WM_COMMAND, IDOK, 0)
                    u32.SetForegroundWindow(hwnd)
                    for vk in (VK_RETURN, VK_SPACE):
                        u32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
                        u32.PostMessageW(hwnd, WM_KEYUP, vk, 0)
                    u32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            return clicked

        found = window_titles()
        for hwnd, title, pid, exe in found:
            handled += 1
            console_log("SYSTEM", f"[anti-stuck] vbox crash dialog: {title!r} (pid {pid}, {exe}) - clicking OK")
            click_ok(hwnd)

        if found:
            time.sleep(2.0)
            still = [(h, t, pd, ex) for (h, t, pd, ex) in window_titles() if u32.IsWindow(h)]
            for hwnd, title, pid, exe in still:
                if not pid or (exe and exe not in VBOX_EXES and exe != "werfault.exe"):
                    try: u32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                    except Exception: pass
                    continue
                console_log("SYSTEM", f"[anti-stuck] vbox dialog still open after 2s - killing pid {pid} ({exe})")
                self.log("[system]", "[warn] vbox crash dialog force-closed.", "sysmsg")
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                except Exception as _ex:
                    _trace(_ex_where(), _ex)

            try:
                if self._vm_state() == "aborted":
                    run_vbox(["discardstate", vm_name], timeout=20)
            except Exception as _ex:
                _trace(_ex_where(), _ex)

        try:
            subprocess.run(["taskkill", "/F", "/IM", "WerFault.exe"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        return handled

    def _crash_dialog_watcher(self):
        while self.running:
            try:
                if self.config.get("auto_recover", True) and self.config.get("auto_close_crash_dialogs", True):
                    self._dismiss_crash_dialogs()
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            time.sleep(20 if (self._idle() or self.config.get("low_power", False)) else 8)

    def _vbox_pids(self):
        pids = []
        if platform.system() != "Windows":

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
        killed = 0
        try:
            with self.input_lock:
                self.shared_kb = None
                self.shared_mouse = None
                if getattr(self, 'shared_session', None):
                    try:
                        if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                        else: self.shared_session.unlockMachine()
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
                self.shared_session = None
            if platform.system() == "Windows":
                for proc in ("VBoxSVC.exe", "VBoxSDS.exe"):
                    try:
                        r = subprocess.run(["taskkill", "/F", "/T", "/IM", str(proc)],
                                           capture_output=True, text=True, timeout=15)
                        if r.returncode == 0: killed += 1
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
            else:
                for proc in ("VBoxSVC", "VBoxXPCOMIPCD", "VBoxSDS"):
                    try:
                        subprocess.run(["pkill", "-KILL", "-f", proc], timeout=10,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        killed += 1
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)

            self.vbox = None
            self.mgr = None
            self.force_session_refresh = True
            self.efail_count = 0
            self.last_com_rebuild_time = time.time()
            time.sleep(2.5)

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

            try: run_vbox(["controlvm", vm_name, "poweroff"], timeout=12)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            if platform.system() == "Windows":

                self._dismiss_crash_dialogs()

                for pid in self._vbox_pids():
                    try:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(int(pid))],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                        killed += 1
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)

                if killed == 0:
                    try:
                        subprocess.run(["taskkill", "/F", "/T", "/FI",
                                        f"WINDOWTITLE eq *{vm_name}*", "/IM", "VirtualBoxVM.exe"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)

                if killed == 0 and self._vm_is_running():
                    try: run_vbox(["startvm", vm_name, "--type", "emergencystop"], timeout=15)
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
                    if self._vm_is_running() and len(self._vbox_pids()) == 0:
                        try:
                            subprocess.run(["taskkill", "/F", "/T", "/IM", "VirtualBoxVM.exe"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                            killed += 1
                        except Exception as _ex:
                            _trace(_ex_where(), _ex)
            else:

                for sig in ("-TERM", "-KILL"):
                    try:
                        subprocess.run(["pkill", sig, "-f", f"VirtualBoxVM.*{vm_name}"], timeout=10,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        killed += 1
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            self.shared_session = None
        self.efail_count = 0

        try:
            if self._vm_state() == "aborted":
                run_vbox(["discardstate", vm_name], timeout=20)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
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
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            time.sleep(1.0)
        if not success:
            self.log("[system]", "[error] vm failed to start after all retries! escalating.", "err")
            set_obs_scene(obs_scene_error)
        self.vm_start_time = time.time()
        return success

    def _vmware_wait_running(self, want_running, timeout=90):
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
        vm = self._vmware()
        t0 = time.time()

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
        global _vlk
        if getattr(self, "backend", "virtualbox") == "vmware":
            return self._do_vm_maintenance_inner(action, arg, user)
        _vlk = False
        ok = self._do_vm_maintenance_inner(action, arg, user)

        state = ""
        try: state = self._vm_state()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if _vlk or (not ok and state in ("aborted", "unknown")) or state == "aborted":
            self.log("[system]", "[warn] VM session is LOCKED - killing all VirtualBox processes and retrying...", "sysmsg")
            dbg("recovery", f"lock detected on '{action}' (locked={_vlk}, state={state}) - full kill + retry")
            try:
                self._kill_vbox_tasks()
                self._kill_vbox_global()
                self._dismiss_crash_dialogs()
            except Exception as e:
                dbg("recovery", "kill during lock recovery failed", e)
            time.sleep(2.0)

            try:
                if self._vm_state() in ("aborted", "saved"):
                    run_vbox(["discardstate", vm_name], timeout=20)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            _vlk = False
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
                        self.ui(self._update_vm_label)
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
                        except Exception as _ex:
                            _trace(_ex_where(), _ex)
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                self.win_session = None
                self.com_mode = ""
            if getattr(self, 'shared_session', None):
                try:
                    if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                    else: self.shared_session.unlockMachine()
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            self.shared_session = None

    def _vboxapi_get_vbox(self, mgr):
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
        mgr = self.mgr
        inner = getattr(mgr, "mgr", None)
        plat = getattr(mgr, "platform", None)

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
        if platform.system() != "Windows":
            return False
        try:
            import pythoncom
            try: pythoncom.CoInitializeEx(0)
            except Exception:
                try: pythoncom.CoInitialize()
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
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
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            self.win_session = None
            vbox = win32com.client.Dispatch("VirtualBox.VirtualBox")
            session = win32com.client.Dispatch("VirtualBox.Session")
            machine = vbox.FindMachine(vm_name)
            machine.LockMachine(session, 1)
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
            except Exception as _ex:
                _trace(_ex_where(), _ex)
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

            if platform.system() == "Windows" and not getattr(self, "_wincom_disabled", False):
                if self._wincom_connect():
                    return True
            try:
                if self.shared_session:
                    try:
                        if vbox_pkg == "virtualbox": self.shared_session.unlock_machine()
                        else: self.shared_session.unlockMachine()
                    except Exception as _ex:
                        _trace(_ex_where(), _ex)
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                self.shared_kb = None
                self.shared_mouse = None
                self.shared_session = None
                _m = str(e).lower()
                _binding = ("find attribute" in _m or "ivirtualbox" in _m or "library_ext" in _m
                            or "getsessionobject" in _m or "virtualboxmanager" in _m
                            or "no attribute" in _m or "session object" in _m
                            or ("attribute" in _m and "object at" in _m))
                if _binding:



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
                    time.sleep(0.5)
                else:
                    if time.time() - getattr(self, "_last_com_err_t", 0) > 10:
                        self._last_com_err_t = time.time()
                        console_log("ERROR", f"com session build failed: {e}")
                return False

    def _cli_put_string(self, text):
        if text and len(text) > 4000:
            text = text[:4000]
        if not text: return len(text or "")
        done = 0
        for i in range(0, len(text), 100):
            chunk = text[i:i + 100]
            to = 8 + len(chunk) * 0.15
            t0 = time.time()
            try:
                r = subprocess.run([vbox_manage_cmd, "controlvm", vm_name, "keyboardputstring", chunk],
                                   capture_output=True, text=True, timeout=to)
            except subprocess.TimeoutExpired:
                plog("TYPE", f"keyboardputstring chunk {i//100 + 1} timed out after {to:.0f}s - {len(text) - done} chars left")
                return done
            except Exception as e:
                plog("TYPE", f"keyboardputstring failed: {type(e).__name__}: {e}")
                return done
            if r.returncode != 0:
                plog("TYPE", f"keyboardputstring rc={r.returncode}: {(r.stderr or '').strip()[:160]}")
                return done
            done += len(chunk)
            self.executor_tick = time.time()
            plog("TYPE", f"cli typed {done}/{len(text)} chars ({(time.time()-t0)*1000:.0f}ms)", verbose=True)
        return done

    RUN_BOX_MAX = 240

    def _vb_type(self, text, td):
        if not text:
            return
        start = 0
        if getattr(self, "cli_input", False):
            start = self._cli_put_string(text)
            if start >= len(text):
                return
            if start:
                plog("TYPE", f"falling back to scancodes for the last {len(text) - start} chars")
        self._release_all_mods()
        for i, ch in enumerate(text[start:]):
            self._type_char(ch)
            time.sleep(td)
            if i % 40 == 0:
                self.executor_tick = time.time()
        self._release_all_mods()
        self.executor_tick = time.time()
        if len(text) > 60:
            plog("TYPE", f"typed {len(text)} chars")

    def _cli_put_scancodes(self, seq):

        if not seq: return
        try:
            hexcodes = [format(int(b) & 0xFF, "02x") for b in seq]
            subprocess.run([vbox_manage_cmd, "controlvm", vm_name, "keyboardputscancode"] + hexcodes,
                           capture_output=True, text=True, timeout=6)
        except Exception:
            pass

    def _try_vboxapi_fallback(self):

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
                        except Exception as _ex:
                            _trace(_ex_where(), _ex)
                        break
                    i += len(chunk)
                    if len(seq) > CHUNK:
                        time.sleep(0.012)
                self._com_input_fails = 0
            except Exception as e:
                emsg = str(e)
                _l = emsg.lower()



                if ("verr_pdm_no_queue_items" in _l or "could not send all scan codes" in _l
                        or "-2135228411" in _l):
                    return
                _binding = ("subscriptable" in _l or "nonetype" in _l
                            or "no attribute" in _l or "attribute" in _l
                            or isinstance(e, (TypeError, AttributeError)))
                if _binding:
                    self._com_input_fails = getattr(self, "_com_input_fails", 0) + 1

                    if platform.system() == "Windows" and getattr(self, "com_mode", "") != "wincom":
                        if self._wincom_connect():
                            try:
                                self.shared_kb.PutScancodes([int(b) for b in seq])
                                return
                            except Exception as _ex:
                                _trace(_ex_where(), _ex)
                    if self._com_input_fails >= 2 and not getattr(self, "cli_input", False):
                        self.cli_input = True
                        self.vbox_binding_broken = True
                        self.shared_kb = None
                        console_log("SYSTEM", "pyvbox keyboard proxy is broken - switching to VBoxManage CLI keyboard. fix fully with: pip install --upgrade virtualbox")
                        self.log("[system]", "[warn] switched to CLI keyboard (pyvbox mismatch). mouse needs 'pip install --upgrade virtualbox'.", "err")
                    self._cli_put_scancodes(seq)
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

        try:
            self._send_scancodes([0xAA, 0xB6, 0x9D, 0xE0, 0x9D, 0xB8, 0xE0, 0xB8])
        except Exception:
            pass

    def _type_char(self, ch):

        mods, codes = get_typed_codes(ch, keyboard_layout)
        seq = []
        for mseq in mods: seq += list(mseq)
        seq += list(codes)
        seq += self._break(codes)
        for mseq in reversed(mods): seq += self._break(mseq)
        if is_dead_key(ch, keyboard_layout):
            seq += [0x39, 0xB9]
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
        vm = self._vmware()
        dbg("vmware", f"exec {cmd} {str(arg)[:50]!r}  (client={'up' if vm.client else 'down'})")

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
        elif base == "run" and len(arg) > self.RUN_BOX_MAX:
            plog("TYPE", f"!run is {len(arg)} chars - the Windows Run box stops at ~259, sending it through a cmd window instead")
            vm.key_combo("win+r"); time.sleep(0.7); vm.type_text("cmd"); vm.press_key("enter")
            time.sleep(1.2); vm.type_text(arg); vm.press_key("enter")
            base = "cmd"
        elif base == "run":
            vm.key_combo("win+r"); time.sleep(0.7); vm.type_text(arg); vm.press_key("enter")
        elif base == "cmd":
            vm.key_combo("win+r"); time.sleep(0.7); vm.type_text("cmd"); vm.press_key("enter")
            time.sleep(1.2); vm.type_text(arg); vm.press_key("enter")
        else:
            dbg("vmware", f"command '{base}' is not mapped for the vmware backend")
            return



        try:
            mult = float(self.config.get("vmware_settle", 1.0))
        except Exception:
            mult = 1.0
        settle = {
            "combo": 0.85,
            "run": 1.20, "cmd": 1.50,
            "send": 0.70,
            "key": 0.30, "type": 0.25,
            "click": 0.20, "lclick": 0.20, "rclick": 0.20, "mclick": 0.20,
            "drag": 0.20, "scroll": 0.08, "move": 0.05, "abs": 0.05,
        }.get(base, 0.15)
        if base == "key" and str(arg).strip().lower() in ("enter", "return", "f5", "esc", "escape"):
            settle = 0.60
        settle *= max(0.0, min(mult, 5.0))
        if settle > 0:
            dbg("vmware", f"settle {settle:.2f}s after '{base}'")
            time.sleep(settle)
        st = str(getattr(vm, "status", ""))
        if "error" in st.lower() or "fail" in st.lower() or "not " in st.lower():
            if time.time() - getattr(self, "_last_vnc_warn", 0) > 20:
                self._last_vnc_warn = time.time()
                self.log("[system]", f"[warn] vmware input: {st}", "err")

    def _run_watched(self, cmd, arg, user, timeout=None):
        if timeout is None:
            n = len(str(arg or ""))
            timeout = min(900.0, 45.0 + n * 0.12 * max(1.0, float(self.config.get("vmware_settle", 1.0) or 1.0)))
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
        end = time.time() + timeout
        while not done.wait(1.0):
            self.executor_tick = time.time()
            if time.time() >= end or not self.running:
                break
        if not done.is_set():
            plog("EXEC", f"'{cmd} {str(arg)[:30]}' still running after {timeout:.0f}s - dropping the vnc session")
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
                self._vb_type(arg, _td)
                if base == "send":
                    time.sleep(max(key_delay, 0.05))
                    if getattr(self, "cli_input", False):
                        self._cli_put_scancodes(scancodes["enter"])
                        self._cli_put_scancodes(self._break(scancodes["enter"]))
                    else:
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
            elif base == "run" and len(arg) > self.RUN_BOX_MAX:
                plog("TYPE", f"!run is {len(arg)} chars - the Windows Run box stops at ~259, sending it through a cmd window instead")
                self.run_cmd_worker("cmd", arg, user)
                return
            elif base == "run":
                self._release_all_mods()
                lw = scancodes["lwin"]; rk = scancodes["r"]
                self._send_scancodes(list(lw) + list(rk) + self._break(rk) + self._break(lw))
                time.sleep(0.7)
                _td = max(type_delay if not self.ultra_speed else 0.0, 0.006)
                self._vb_type(arg, _td)
                time.sleep(0.2); self._tap(scancodes["enter"])
            elif base == "cmd":
                self._release_all_mods()
                lw = scancodes["lwin"]; rk = scancodes["r"]
                self._send_scancodes(list(lw) + list(rk) + self._break(rk) + self._break(lw))
                time.sleep(0.7)
                _td = max(type_delay if not self.ultra_speed else 0.0, 0.006)
                self._vb_type("cmd", _td)
                self._tap(scancodes["enter"]); time.sleep(1.2)
                self._vb_type(arg, _td)
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
            _done = self.__dict__.pop("_exec_done", None)
            if _done is not None:
                self._discord_press(*_done)
            try:
                try:
                    action = self.cmd_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if not action or len(action) < 3: continue
                cmd, arg, user = action[0], action[1], action[2]
                if cmd == "__wait__":
                    w = _wait_seconds(arg)
                    dbg("exec", f"wait {w}s")
                    self._exec_current = f"wait {w}s"
                    end = time.time() + w
                    while time.time() < end and self.running:
                        self.executor_tick = time.time()
                        time.sleep(max(0.0, min(0.2, end - time.time())))
                    self._exec_current = ""
                    continue
                self._exec_current = f"{cmd} {str(arg)[:40]}"
                self._exec_started = time.time()
                self._exec_done = (cmd, arg, user)
                plog("EXEC", f"> {cmd} {str(arg)[:60]!r} from {user}  (left in queue={self.cmd_queue.qsize()})")
                dbg("exec", f"START {cmd} {str(arg)[:60]!r} from {user} (queue={self.cmd_queue.qsize()})")
                base = cmd.lower()
                if base.startswith(self.command_prefix): base = base[len(self.command_prefix):]
                if base.startswith("!"): base = base[1:]
                if base in maintenance_actions:
                    self.__dict__.pop("_exec_done", None)
                    start_msg, done_msg, fail_msg = self._maint_messages(base)
                    if start_msg:
                        self._discord_maint(start_msg)
                    plog("EXEC", f"maintenance action {base} starting")
                    ok = self._do_vm_maintenance(base, arg, user)
                    plog("EXEC", f"maintenance action {base} finished in {time.time()-self._exec_started:.1f}s")
                    self._discord_maint(done_msg if ok else fail_msg, shot=bool(ok))
                    self._exec_current = ""
                    continue
                if getattr(self, 'vm_maintenance', False):
                    plog("EXEC", f"skipped {cmd} - vm maintenance in progress")
                    self._exec_current = ""
                    continue
                if getattr(self, "pico_enabled", False) and getattr(self, "pico_target", "vm") == "pico":
                    if self.pico and getattr(self.pico, "ser", None):
                        self.run_cmd_worker(cmd, arg, user)
                    self._exec_current = ""
                    continue
                if getattr(self, "backend", "virtualbox") == "vmware":
                    self._run_watched(cmd, arg, user)
                    _el = time.time() - self._exec_started
                    plog("EXEC", f"< {cmd} done in {_el*1000:.0f}ms" + ("  (SLOW)" if _el > 5 else ""))
                    self._exec_current = ""
                    continue
                if not self._vm_is_running():
                    plog_throttled("exec-novm", "EXEC", f"skipping commands - vm is not running (last: {cmd})", 15, on_change=False)
                    self._exec_current = ""
                    continue
                if getattr(self, "cli_input", False):
                    self.run_cmd_worker(cmd, arg, user)
                    _el = time.time() - self._exec_started
                    plog("EXEC", f"< {cmd} done in {_el*1000:.0f}ms (cli)" + ("  (SLOW)" if _el > 5 else ""))
                    self._exec_current = ""
                    continue
                if not self._ensure_com_session():
                    plog("EXEC", f"skipped {cmd} - no COM session to the vm (will retry session)")
                    self.force_session_refresh = True
                    time.sleep(0.2)
                    self._exec_current = ""
                    continue
                self.run_cmd_worker(cmd, arg, user)
                _el = time.time() - self._exec_started
                plog("EXEC", f"< {cmd} done in {_el*1000:.0f}ms" + ("  (SLOW)" if _el > 5 else ""))
                dbg("exec", f"DONE  {cmd} in {_el*1000:.0f}ms")
                self._exec_current = ""
            except Exception as e:
                dbg("exec", f"CRASH in {self._exec_current!r}", e)
                log_crash(f"executor '{getattr(self,'_exec_current','?')}'", e)
                console_log("ERROR", f"executor loop error: {e}")
                self.force_session_refresh = True
                time.sleep(0.5)

    def error_watcher_loop(self):
        while self.running:
            try:
                time.sleep(5)
                if getattr(self, 'vm_maintenance', False):
                    continue
                now = time.time()
                if now - getattr(self, 'executor_tick', now) > 60:
                    _dump_all_stacks(f"executor stalled on {getattr(self, '_exec_current', '') or '(idle)'!r}", to_crash_log=False)
                    self.executor_id += 1
                    self.executor_thread = _spawn(f"executor-{self.executor_id}", self.executor_loop, (self.executor_id,))
                    _stuck = getattr(self, "_exec_current", "") or "(idle)"
                    _for = time.time() - getattr(self, "_exec_started", time.time())
                    console_log("SYSTEM", f"executor stalled on {_stuck!r} for {_for:.0f}s; restarted. "
                                          f"(backend={getattr(self,'backend','virtualbox')})")
                    dbg("exec", f"STALL on {_stuck!r} after {_for:.0f}s - restarting executor")
                if now - getattr(self, 'listener_tick', now) > 90:
                    _dump_all_stacks("chat listener stalled > 90s", to_crash_log=False)
                    self.listener_id += 1
                    self.listener_thread = _spawn(f"chat-listener-{self.listener_id}", self.chat_listener_loop, (self.listener_id,))
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
        if IN_IDLE:
            console_log("SYSTEM", "would relaunch, but running in IDLE - skipping (run the .py directly for auto-restart).")
            return
        try:
            console_log("ERROR", f"self-relaunch triggered: {reason}")
            _dump_all_stacks(f"self-relaunch: {reason}")
            script_path = os.path.abspath(sys.argv[0])
            keep = [a for a in sys.argv[1:] if a.startswith("--multistream") or a in ("--no-install", "--quiet", "--console")]
            args = [sys.executable, script_path] + keep

            if "--relaunched" not in args: args.append("--relaunched")
            if platform.system() == "Windows": subprocess.Popen(args, creationflags=0x00000010, close_fds=True)
            else: subprocess.Popen(args, start_new_session=True, close_fds=True)
            plog("RELAUNCH", f"new instance started: {args}")
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        out_flush(2.0)
        os._exit(1)

    def hard_watchdog_loop(self):
        while self.running:
            try:
                hb = getattr(self, 'main_heartbeat', time.time())
                if time.time() - hb > 180:
                    plog("WATCHDOG", f"UI frozen for {time.time()-hb:.0f}s - killing and relaunching")
                    self._relaunch_self("main ui thread frozen >180s")
                try:
                    with open(heartbeat_file, "w") as f: f.write(str(int(time.time())))
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
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
        return
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
                self.ui(self._update_vm_label)
                self._do_vm_maintenance("remake2", "", "[console]")
                self.ui(self._refresh_osvote)
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
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
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if self.running:
            self.root.after(5000 if self.config.get('low_power', False) else 2500, self._eventlog_tick)

    def _load_log(self, path):
        self._eventlog_src = path
        flt = ""
        try: flt = self._eventlog_filter.get().strip().lower()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
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
                        except Exception as _ex:
                            _trace(_ex_where(), _ex)
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
        t = self._tok
        wrap = self.make_scrollable(self.tab_appear)
        self._appear_wrap = wrap
        pad = 32
        self._st_label(wrap, "Pick a theme, an accent and a text size. Changes apply right away and are saved.",
                       bg="bg", fg="muted", font=("ui", 10)).pack(anchor="w", padx=pad, pady=(22, 18))
        self._st_label(wrap, "Theme", bg="bg", fg="hi", font=("display", 14)).pack(anchor="w", padx=pad)
        grid = tk.Frame(wrap, bg=t["bg"]); grid._st = {"bg": "bg"}
        grid.pack(fill="x", padx=pad - 6, pady=(10, 24))
        self._theme_cards = {}
        cols = 4
        for c in range(cols):
            grid.columnconfigure(c, weight=1, uniform="themes")
        for i, key in enumerate(_STUDIO_ORDER):
            base = _studio_resolve(key, None)
            outer = tk.Frame(grid, bg=t["line"], cursor="hand2"); outer._st = {"bg": "line"}
            outer.grid(row=i // cols, column=i % cols, sticky="nsew", padx=6, pady=6)
            card = tk.Frame(outer, bg=t["card"], cursor="hand2"); card._st = {"bg": "card"}
            card.pack(fill="both", expand=True, padx=1, pady=1)
            sw = tk.Canvas(card, height=46, bd=0, highlightthickness=0, bg=base["bg"], cursor="hand2")
            sw._studio_skip = True
            sw.pack(fill="x", padx=12, pady=(12, 8))
            def _paint(e=None, cv=sw, b=base):
                cv.delete("all")
                w = max(cv.winfo_width(), 40)
                cv.create_rectangle(0, 0, w, 46, fill=b["bg"], outline="")
                cv.create_rectangle(0, 0, int(w * 0.22), 46, fill=b["side"], outline="")
                cv.create_rectangle(int(w * 0.28), 9, int(w * 0.94), 37, fill=b["card"], outline=b["line"])
                cv.create_rectangle(int(w * 0.33), 16, int(w * 0.62), 21, fill=b["text"], outline="")
                cv.create_rectangle(int(w * 0.33), 26, int(w * 0.50), 30, fill=b["muted"], outline="")
                cv.create_rectangle(int(w * 0.72), 15, int(w * 0.88), 31, fill=b["accent"], outline="")
                cv.create_rectangle(int(w * 0.04), 12, int(w * 0.18), 15, fill=b["accent"], outline="")
            sw.bind("<Configure>", _paint)
            nm = self._st_label(card, base["name"], fg="hi", font=("ui", 10, "semi"), anchor="w")
            nm.pack(fill="x", padx=12)
            ds = self._st_label(card, base["desc"], fg="muted", font=("ui", 9), anchor="w", justify="left", wraplength=180)
            ds.pack(fill="x", padx=12, pady=(1, 12))
            ds.bind("<Configure>", lambda e, l=ds: l.configure(wraplength=max(80, e.width - 4)))
            for w in (outer, card, sw, nm, ds):
                w.bind("<Button-1>", lambda e, k=key: self.apply_theme(k))
            _mo_hover_glow(outer, ("themecard", key))
            self._theme_cards[key] = outer
        self._st_label(wrap, "Accent", bg="bg", fg="hi", font=("display", 14)).pack(anchor="w", padx=pad)
        self._st_label(wrap, "Used for primary buttons, the active page and focus rings.", bg="bg", fg="muted",
                       font=("ui", 9)).pack(anchor="w", padx=pad, pady=(2, 0))
        arow = tk.Frame(wrap, bg=t["bg"]); arow._st = {"bg": "bg"}
        arow.pack(anchor="w", padx=pad - 4, pady=(10, 24))
        self._accent_chips = {}
        for name, col in (("Theme default", None), ("Amber", "#F2A53A"), ("Signal red", "#E5484D"), ("Green", "#3DBE7E"),
                          ("Cyan", "#22C3E6"), ("Blue", "#5B8CFF"), ("Violet", "#9D7BFF"), ("Pink", "#EC5FA8"), ("Teal", "#2CB9A6")):
            cell = tk.Frame(arow, bg=t["bg"], cursor="hand2"); cell._st = {"bg": "bg"}
            cell.pack(side="left", padx=4)
            ring = tk.Frame(cell, bg=t["bg"], cursor="hand2"); ring._studio_skip = True
            ring.pack()
            chip = tk.Frame(ring, width=34, height=34, cursor="hand2",
                            bg=(col or _STUDIO_BASE.get(self.ui_theme, _STUDIO_BASE["original"])["accent"]))
            chip._studio_skip = True
            chip.pack(padx=3, pady=3)
            lab = self._st_label(cell, name, bg="bg", fg="muted", font=("ui", 8))
            lab.pack(pady=(3, 0))
            for w in (cell, ring, chip, lab):
                w.bind("<Button-1>", lambda e, c=col: self.apply_accent(c))
            self._accent_chips[col] = (ring, chip)
        self._st_label(wrap, "Text size", bg="bg", fg="hi", font=("display", 14)).pack(anchor="w", padx=pad)
        srow = tk.Frame(wrap, bg=t["bg"]); srow._st = {"bg": "bg"}
        srow.pack(anchor="w", padx=pad - 4, pady=(10, 24))
        self._size_btns = {}
        for lbl, d in (("Compact", -1), ("Normal", 0), ("Large", 1), ("Larger", 2)):
            b = self._st_button(srow, lbl, lambda d=d: self.set_text_size(d), "neutral", 9)
            b.pack(side="left", padx=4)
            self._size_btns[d] = b
        self._st_label(wrap, "Motion", bg="bg", fg="hi", font=("display", 14)).pack(anchor="w", padx=pad)
        self._st_label(wrap, "Page transitions, button feedback, sliding notices and live indicators. Low power mode turns it off.",
                       bg="bg", fg="muted", font=("ui", 9)).pack(anchor="w", padx=pad, pady=(2, 0))
        mrow = tk.Frame(wrap, bg=t["bg"]); mrow._st = {"bg": "bg"}
        mrow.pack(anchor="w", padx=pad - 4, pady=(10, 24))
        self._motion_btns = {}
        for lbl, lv in (("Full", "full"), ("Reduced", "reduced"), ("Off", "off")):
            b = self._st_button(mrow, lbl, lambda lv=lv: self.set_motion(lv), "neutral", 9)
            b.pack(side="left", padx=4)
            self._motion_btns[lv] = b
        self._st_label(wrap, "Behaviour", bg="bg", fg="hi", font=("display", 14)).pack(anchor="w", padx=pad)
        brow = tk.Frame(wrap, bg=t["bg"]); brow._st = {"bg": "bg"}
        brow.pack(anchor="w", padx=pad, pady=(10, 8))
        self._toast_var = tk.BooleanVar(value=bool(self.config.get("ui_toasts", True)))
        def _tt():
            self.config["ui_toasts"] = bool(self._toast_var.get()); self.save_settings()
        ttk.Checkbutton(brow, text="Pop-up notices for errors, warnings and passed votes", variable=self._toast_var,
                        command=_tt).pack(anchor="w", pady=2)
        _ctk_row = tk.Frame(wrap, bg=t["bg"]); _ctk_row._st = {"bg": "bg"}
        _ctk_row.pack(anchor="w", padx=pad - 4, pady=(6, 30))
        self._st_button(_ctk_row, ("CustomTkinter entries: on" if self.config.get("use_customtkinter") else "CustomTkinter entries: off"),
                        self.toggle_ctk, "neutral", 9).pack(side="left", padx=4)
        self._st_label(_ctk_row, ("Needs a restart." if ctk_available else "Not installed: pip install customtkinter"),
                       bg="bg", fg="faint", font=("ui", 9)).pack(side="left", padx=8)
        self._refresh_appearance_marks()

    def _refresh_appearance_marks(self):
        t = self._tok
        try:
            for key, outer in getattr(self, "_theme_cards", {}).items():
                on = key == self.ui_theme
                outer._mo_lock = on
                MOTION.cancel(("themecard", key))
                MOTION.col.pop(("themecard", key), None)
                outer.configure(bg=t["accent"] if on else t["line"])
                outer._st = {"bg": "accent" if on else "line"}
                kids = outer.winfo_children()
                if kids:
                    kids[0].pack_configure(padx=2 if on else 1, pady=2 if on else 1)
            cur = self.config.get("accent_color")
            for col, (ring, chip) in getattr(self, "_accent_chips", {}).items():
                on = (col or None) == (cur or None)
                ring.configure(bg=t["hi"] if on else t["bg"])
                if col is None:
                    chip.configure(bg=_STUDIO_BASE.get(self.ui_theme, _STUDIO_BASE["original"])["accent"])
            d = int(_STUDIO.get("delta", 0))
            for k, b in getattr(self, "_size_btns", {}).items():
                b._variant = "primary" if k == d else "neutral"
                b._st = dict(getattr(b, "_st", {}) or {}, variant=b._variant)
                b.studio_style(None)
            lvn = str(self.config.get("ui_motion", "full")).lower()
            for k, b in getattr(self, "_motion_btns", {}).items():
                b._variant = "primary" if k == lvn else "neutral"
                b._st = dict(getattr(b, "_st", {}) or {}, variant=b._variant)
                b.studio_style(None)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def set_text_size(self, d):
        d = max(-1, min(2, int(d)))
        _STUDIO["delta"] = d
        self.config["ui_text_size"] = d
        self.save_settings()
        plog("UI", f"text size -> {d:+d}")
        self._dip(self._apply_tokens_everywhere)
        self.toast(f"Text size set to {({-1: 'compact', 0: 'normal', 1: 'large', 2: 'larger'})[d]}.", "ok")

    def apply_accent(self, col):
        self.config["accent_color"] = col
        if not col:
            self.config.pop("accent_color", None)
        self.save_settings()
        self._set_tokens(self.ui_theme)
        plog("UI", f"accent -> {self._tok['accent']}")
        self._dip(self._apply_tokens_everywhere)

    def _set_tokens(self, name):
        acc = self.config.get("accent_color") or ("#8B5CF6" if self.is_multistream else None)
        tok = _studio_resolve(name, acc)
        _STUDIO["tok"] = tok
        self._tok = tok
        self._theme_palette = tok
        self.ui_theme = tok["key"]
        self.accent_main = tok["accent"]
        self.accent_hover = tok["accent_hover"]
        _STUDIO["accent_seen"].add(_hx(tok["accent"]))

    def _apply_tokens_everywhere(self):
        t0 = time.time()
        try: self.root.configure(bg=self._tok["bg"])
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self._style_ttk()
        self._ttk_bg_styles = {}
        try: self.tabview.apply_tokens()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self._studio_restyle(force=True)
        self._refresh_appearance_marks()
        self._run_repaint_hooks()
        _STUDIO["gen"] = _STUDIO.get("gen", 0) + 1
        try: _win_titlebar(self.root, self._tok["dark"])
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        plog("UI", f"repainted in {(time.time()-t0)*1000:.0f}ms")

    THEMES = _STUDIO_BASE

    def apply_theme(self, name, save=True):
        if name not in _STUDIO_BASE:
            name = "original"
        def go(name=name):
            self._set_tokens(name)
            self.config["ui_theme"] = name
            if save:
                self.save_settings()
            plog("UI", f"theme -> {name} ({_STUDIO_BASE[name]['name']})")
            self._apply_tokens_everywhere()
        if save:
            self._dip(go)
        else:
            go()

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
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def send_flash_ui(self):
        txt = self.flash_entry.get().strip()
        if not txt: return
        self.send_flash(txt)
        self.flash_entry.delete(0, "end")

    def send_flash(self, text, kind="info", dur=6):
        try:
            app_flash.update({"text": text, "kind": kind, "dur": dur, "n": app_flash.get("n", 0) + 1})
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        def _post():
            try:
                host = self.config.get("relay_host", "127.0.0.1")
                port = int(self.config.get("relay_port", 8080))
                data = json.dumps({"text": text, "kind": kind, "dur": dur}).encode()
                req = urllib.request.Request(f"http://{host}:{port}/api/flash", data=data,
                                             headers={"Content-Type": "application/json"}, method="POST")
                urllib.request.urlopen(req, timeout=3)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        threading.Thread(target=_post, daemon=True).start()
        self.log("[system]", f"flashed: {text}", "sysmsg")

    def _bind_secret_replay(self):

        self._secret_clicks = []
        def _hit(_e=None):
            now = time.time()
            self._secret_clicks = [t for t in self._secret_clicks if now - t < 2.0] + [now]
            if len(self._secret_clicks) >= 5:
                self._secret_clicks = []
                try: self.tabview.select(self.tab_replay)
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                self.start_replay()
        try:
            if hasattr(self, "lbl_status"): self.lbl_status.bind("<Button-1>", _hit)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def make_scrollable(self, parent):
        t = getattr(self, "_tok", None) or _studio_resolve("original")
        canvas = tk.Canvas(parent, bg=t["bg"], bd=0, highlightthickness=0, yscrollincrement=20)
        canvas._st = {"bg": "bg"}
        vs = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=t["bg"])
        inner._st = {"bg": "bg"}
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        def _sync(first, last):
            vs.set(first, last)
            try:
                need = not (float(first) <= 0.0 and float(last) >= 1.0)
                if need and not vs.winfo_manager():
                    vs.pack(side="right", fill="y", before=canvas)
                elif not need and vs.winfo_manager():
                    vs.pack_forget()
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        canvas.configure(yscrollcommand=_sync)
        vs.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        try: self._register_scroll(canvas)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
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
        return
        def _scroll(e):
            try:
                tabs = self.tabview.tabs()
                if not tabs: return
                cur = self.tabview.index(self.tabview.select())
                nxt = cur + (1 if (getattr(e, "delta", 0) < 0 or getattr(e, "num", 0) == 5) else -1)
                nxt = max(0, min(len(tabs) - 1, nxt))
                self.tabview.select(tabs[nxt])
            except Exception as _ex:
                _trace(_ex_where(), _ex)
        try:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.tabview.side.bind(seq, _scroll)
        except Exception as _ex:
            _trace(_ex_where(), _ex)

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
        if self._tok.get("dark", True):
            self.apply_theme("daylight" if cur in ("glass", "better") else "light")
        else:
            self.apply_theme("original")

    def _minimize_window(self):
        try:
            self.root.iconify()
        except Exception:
            pass

    def _toggle_low_power(self):
        v = not self.config.get("low_power", False)
        self.config["low_power"] = v
        self.save_settings()
        try: self._apply_motion_level()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        self.log("[system]", f"low power mode {'ON - lighter on old PCs' if v else 'OFF'}.", "sysmsg")

    def _toggle_console(self, show=None):
        if platform.system() != "Windows":
            return
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if not hwnd:
                return
            if show is None:
                show = not getattr(self, "_console_shown", False)
            ctypes.windll.user32.ShowWindow(hwnd, 5 if show else 0)
            self._console_shown = show
        except Exception:
            pass

    def _vm_action(self, action, arg=""):
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
        tk.Label(wrap, text="Numbers", font=("Segoe UI", 10, "bold"), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30)
        nums = [str(n) for n in range(1, 10)] + ["0"]
        self._grid_buttons(wrap, [(k, "#27272A", lambda kk=k: self._send_cmd("!key", kk)) for k in nums], cols=10).pack(fill="x", padx=26, pady=(4, 12))
        tk.Label(wrap, text="Function keys", font=("Segoe UI", 10, "bold"), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30)
        fkeys = [f"f{i}" for i in range(1, 13)]
        self._grid_buttons(wrap, [(k, "#27272A", lambda kk=k: self._send_cmd("!key", kk)) for k in fkeys], cols=12).pack(fill="x", padx=26, pady=(0, 12))
        tk.Label(wrap, text="Combos", font=("Segoe UI", 10, "bold"), bg="#09090B", fg="#A1A1AA").pack(anchor="w", padx=30)
        combos = [("Win+R", "win+r"), ("Win+D", "win+d"), ("Win+E", "win+e"), ("Alt+Tab", "alt+tab"),
                  ("Alt+F4", "alt+f4"), ("Ctrl+C", "ctrl+c"), ("Ctrl+V", "ctrl+v"), ("Ctrl+A", "ctrl+a"),
                  ("Ctrl+Z", "ctrl+z"), ("Ctrl+Shift+Esc", "ctrl+shift+esc"), ("Ctrl+Alt+Del", "ctrl+alt+delete"), ("Win", "win")]
        self._grid_buttons(wrap, [(lbl, "#8B5CF6", lambda cc=c: self._send_cmd("!combo", cc)) for lbl, c in combos], cols=4).pack(fill="x", padx=26, pady=(4, 24))

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
        target = vm_name
        def _work():
            snaps = get_vbox_snapshots(vbox_manage_cmd, target)
            self.ui(self._apply_snaps_tab, snaps)
        self._run_bg("snaps-tab", _work)

    def _apply_snaps_tab(self, snaps):
        try:
            self.snap_cb["values"] = snaps or [""]
            if self.current_snapshot in snaps: self.snap_cb.set(self.current_snapshot)
            elif snaps: self.snap_cb.set(snaps[-1])
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _snap_set_target(self):
        s = self.snap_cb.get().strip()
        if not s: return
        self.current_snapshot = s
        try:
            with open(snap_file, "w") as f: f.write(s)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
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
        except Exception as _ex:
            _trace(_ex_where(), _ex)

    def _copy(self, text):
        try:
            self.root.clipboard_clear(); self.root.clipboard_append(text)
            self.log("[system]", f"copied: {text}", "sysmsg")
        except Exception as _ex:
            _trace(_ex_where(), _ex)

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

    # -- updates -------------------------------------------------------------
    def _update_mode(self):
        mode = str(self.config.get("update_mode", "ask")).lower()
        return mode if mode in ("ask", "auto", "off") else "ask"

    def _update_schedule(self, first=False):
        """Check on start (after the UI settles) and then every few hours. Only the first instance checks."""
        if instance_id != 1 or not self.running:
            return
        if self._update_mode() != "off" and not first:
            self._run_bg("update-check", self._update_check_work, False)
        self.root.after(15000 if first else UPDATE_CHECK_HOURS * 3600 * 1000, self._update_schedule)

    def update_check_now(self):
        self._update_set_status("Checking for updates...")
        self._run_bg("update-check", self._update_check_work, True)

    def _update_set_status(self, text, fg="muted"):
        self._update_status_text = (text, fg)
        lbl = getattr(self, "update_status", None)
        if lbl is not None:
            self.ui(lambda: lbl.configure(text=text, fg=_studio_color(fg)))

    def _update_check_work(self, manual):
        ok, why = update_supported()
        if not ok:
            self._update_set_status(f"Updates unavailable: {why}.", "faint")
            if manual:
                self.toast(f"Can't update: {why}", "bad")
            return
        try:
            info = update_check()
        except Exception as e:
            plog("UPDATE", f"check failed: {e}")
            self._update_set_status("Couldn't check for updates - try again later.", "bad")
            if manual:
                self.toast("Couldn't reach GitHub to check for updates", "bad")
            return
        self._update_info = info if info["newer"] else None
        self.ui(self._update_paint_buttons)
        if not info["newer"]:
            self._update_set_status(f"You're up to date (v{version}).", "ok")
            if manual:
                self.toast(f"YT2VM {version} is the latest version", "ok")
            return
        plog("UPDATE", f"{info['tag']} available (running {version})")
        self._update_set_status(f"Version {info['version']} is available.", "warn")
        mode = self._update_mode()
        if mode == "auto" and not manual:
            self._update_install_work(info, auto=True)
        elif manual or getattr(self, "_update_prompted", "") != info["tag"]:
            self._update_prompted = info["tag"]
            self.ui(self._update_prompt, info)

    def _update_prompt(self, info):
        notes = info.get("notes") or "No release notes."
        if len(notes) > 900:
            notes = notes[:900].rstrip() + " ..."
        if messagebox.askyesno("Update available",
                               f"YT2VM {info['version']} is available (you have {version}).\n\n{notes}\n\n"
                               "Update now? Your current version is kept as a backup, and nothing restarts until you say so.",
                               parent=self.root):
            self._run_bg("update-install", self._update_install_work, info, False)

    def update_install_now(self):
        info = getattr(self, "_update_info", None)
        if info:
            self._run_bg("update-install", self._update_install_work, info, False)

    def _update_install_work(self, info, auto=False):
        self._update_set_status(f"Downloading {info['version']}...")
        try:
            data = update_download(info)
            backup = update_install(data)
        except Exception as e:
            log_crash(f"update to {info.get('tag')}", e)
            self._update_set_status(f"Update failed: {e}", "bad")
            self.toast(f"Update failed: {e}", "bad")
            return
        plog("UPDATE", f"installed {info['tag']} - old version kept as {backup}")
        self._update_info = None
        self._update_installed = info["version"]
        self.ui(self._update_paint_buttons)
        self._update_set_status(f"Version {info['version']} is installed - restart YT2VM to use it.", "ok")
        if auto:
            self.toast(f"YT2VM {info['version']} installed - restart when it suits you", "ok")
            return
        self.ui(self._update_ask_restart, info)

    def _update_ask_restart(self, info):
        if messagebox.askyesno("Update installed",
                               f"YT2VM {info['version']} is installed.\n\nRestart now? If you're live, you can also "
                               "restart later - the update is used next time YT2VM starts.", parent=self.root):
            self._restart_app()

    def _update_restore_backup(self):
        target = os.path.abspath(sys.argv[0])
        folder = os.path.dirname(target)
        baks = sorted((f for f in os.listdir(folder) if f.startswith(os.path.basename(target) + ".bak-")),
                      key=lambda f: os.path.getmtime(os.path.join(folder, f)), reverse=True)
        if not baks:
            messagebox.showinfo("Restore previous version", "There's no backup from an earlier update.", parent=self.root)
            return
        if not messagebox.askyesno("Restore previous version", f"Replace yt2vm.py with {baks[0]} and restart?\n\n"
                                   "Turn updates to Off first if you don't want to be offered the newer version again.",
                                   parent=self.root):
            return
        try:
            shutil.copy2(target, target + ".bak-undone")
            shutil.copy2(os.path.join(folder, baks[0]), target)
        except Exception as e:
            messagebox.showerror("Restore previous version", f"Restore failed: {e}", parent=self.root)
            return
        self._restart_app()

    def _update_paint_buttons(self):
        btn = getattr(self, "update_install_btn", None)
        if btn is None:
            return
        info = getattr(self, "_update_info", None)
        if info:
            btn.configure(text=f"Install {info['version']}")
            if not btn.winfo_manager():
                btn.pack(side="left", padx=4, ipadx=8, after=self.update_check_btn)
        elif btn.winfo_manager():
            btn.pack_forget()

    def _build_update_card(self, parent):
        t = self._tok
        o, c = self._st_card(parent, "Updates")
        o.pack(fill="x", padx=26, pady=(0, 20))
        self._st_label(c, f"Running YT2VM {version}. New versions come from the releases at github.com/{UPDATE_REPO}.",
                       fg="muted", font=("ui", 9), anchor="w", justify="left", wraplength=760).pack(fill="x", padx=16)
        text, fg = getattr(self, "_update_status_text", ("Not checked yet.", "faint"))
        self.update_status = self._st_label(c, text, fg=fg, font=("ui", 10, "semi"), anchor="w", justify="left", wraplength=760)
        self.update_status.pack(fill="x", padx=16, pady=(8, 0))
        row = tk.Frame(c, bg=t["card"]); row._st = {"bg": "card"}
        row.pack(fill="x", padx=12, pady=(10, 6))
        self.update_check_btn = self._st_button(row, "Check now", self.update_check_now, "primary", 9)
        self.update_check_btn.pack(side="left", padx=4, ipadx=8)
        self.update_install_btn = self._st_button(row, "Install", self.update_install_now, "go", 9)
        self._st_button(row, "Restore previous version", self._update_restore_backup, "neutral", 9).pack(side="right", padx=4, ipadx=8)
        mrow = tk.Frame(c, bg=t["card"]); mrow._st = {"bg": "card"}
        mrow.pack(fill="x", padx=16, pady=(4, 14))
        self._st_label(mrow, "When a new version is out:", fg="muted", font=("ui", 9)).pack(side="left")
        names = {"ask": "Ask me", "auto": "Install it, I restart later", "off": "Don't check"}
        self.update_mode_cb = ttk.Combobox(mrow, values=list(names.values()), state="readonly", width=26, font=("Segoe UI", 9))
        self.update_mode_cb.set(names[self._update_mode()])
        self.update_mode_cb.pack(side="left", padx=8)

        def pick(_e=None):
            mode = {v: k for k, v in names.items()}[self.update_mode_cb.get()]
            self.config["update_mode"] = mode
            self.save_settings()
            self.toast("Update setting saved", "ok")
        self.update_mode_cb.bind("<<ComboboxSelected>>", pick)
        self._update_paint_buttons()

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
        self._build_update_card(wrap)
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
        except Exception as _ex:
            _trace(_ex_where(), _ex)
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
        except Exception as _ex:
            _trace(_ex_where(), _ex)

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
            self.ui(self._replay_update)

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
        if now - getattr(self, "last_escalation_t", 0) < 20:
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
                self._relaunch_self("auto-recovery exhausted lower levels")
        except Exception as e:
            console_log("ERROR", f"escalation failed: {e}")

    def _idle(self):
        return not (getattr(self, "listening_to_chat", False) and getattr(self, "active_url", ""))

    def vm_health_watchdog(self):
        while self.running:
            try:
                _s = 4
                if self.config.get("low_power", False): _s = 8
                if self._idle(): _s = 15
                time.sleep(_s)
                if not self.config.get("auto_recover", True):
                    continue
                if getattr(self, "backend", "virtualbox") == "vmware":
                    continue
                now = time.time()

                if getattr(self, "vm_maintenance", False):
                    if now - getattr(self, "_maint_start_t", now) > 200:
                        console_log("SYSTEM", "[anti-stuck] maintenance stuck >200s, clearing flag.")
                        self.vm_maintenance = False
                    continue
                state = self._vm_state()

                if state == "aborted":
                    self.log("[system]", "[warn] vm aborted/crashed, killing + restarting...", "sysmsg")
                    self._dismiss_crash_dialogs()
                    def _fix_aborted():
                        self._kill_vbox_tasks()
                        self._do_vm_maintenance("startvm", "", "[watchdog]")
                    threading.Thread(target=_fix_aborted, daemon=True).start()
                    self.vm_start_time = now
                    continue

                if state == "paused":
                    run_vbox(["controlvm", vm_name, "resume"], timeout=10)
                    continue

                if state in ("poweroff", "saved") and self.twenty_four_seven_mode and self.active_url:
                    if now - getattr(self, "vm_start_time", 0) > 20:
                        self.log("[system]", "[warn] vm down in 24/7 mode, auto-starting...", "sysmsg")
                        self.trigger_command(("startvm", "", "[watchdog]"))
                        self.vm_start_time = now
                    continue

                if state != "running" and not self._vm_is_running():
                    self.watchdog_action_level = 0
                    continue

                if getattr(self, "efail_count", 0) >= 4 or state == "aborted":
                    self._dismiss_crash_dialogs()

                if getattr(self, "efail_count", 0) >= 8:


                    if self.efail_count >= 20 or (self.shared_kb is None and now - getattr(self, "last_cmd_ok_t", now) > 45):
                        self.watchdog_action_level = max(getattr(self, "watchdog_action_level", 0), 2)
                        self.last_escalation_t = 0
                    self._escalate_recovery(f"E_FAIL storm ({self.efail_count})")
                    self.efail_count = 0
                    continue

                _busy = bool(getattr(self, "_exec_current", "")) and now - getattr(self, "executor_tick", 0) < 8
                if self.cmd_queue.qsize() > 3 and now - getattr(self, "last_cmd_ok_t", now) > 25 and not _busy:
                    self._escalate_recovery("commands queued but not executing")
                    continue

                if self.shared_kb is None and self.cmd_queue.qsize() > 0:
                    self.force_session_refresh = True

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
            self.queue_music(url, "[console]", True, True, True)
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

    _gff = "guide_seen.flag"

    def show_welcome_guide(self, force=False):
        if not force and os.path.exists(self._gff):
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
                except Exception as _ex:
                    _trace(_ex_where(), _ex)

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
                    with open(self._gff, "w") as f: f.write("seen")
                except Exception as _ex:
                    _trace(_ex_where(), _ex)
            try: dlg.destroy()
            except Exception as _ex:
                _trace(_ex_where(), _ex)
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
            ("OWNER", "!tob64 / !eb64", "turn the base64 filter off / on"),
            ("MOD", "!unblock <user>", "clear a base64-blocked sender"),
        ]
        self._render_help()

    def _render_help(self):
        flt = ""
        try: flt = self.help_filter.get().strip().lower()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
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

    def _freeze_watchdog(self):
        last_dump = 0
        frozen_since = None
        while self.running:
            try:
                time.sleep(2)
                last = getattr(self, "main_heartbeat", 0)
                if not last or not _MAINLOOP_LIVE[0]:
                    continue
                stalled = time.time() - last
                if stalled > 6:
                    if frozen_since is None:
                        frozen_since = last
                        plog("FROZEN", f"UI thread has not ticked for {stalled:.0f}s - Windows will show 'Not Responding'. dumping every thread:")
                        log_event("FROZEN", f"UI stalled {int(stalled)}s")
                        _dump_all_stacks(f"UI FROZEN for {int(stalled)}s")
                        last_dump = time.time()
                    elif time.time() - last_dump > 30:
                        plog("FROZEN", f"UI still frozen ({stalled:.0f}s). dumping again:")
                        _dump_all_stacks(f"UI STILL FROZEN for {int(stalled)}s")
                        last_dump = time.time()
                elif frozen_since is not None:
                    plog("FROZEN", f"UI recovered after being stuck for ~{time.time() - frozen_since:.0f}s")
                    log_event("FROZEN", "UI recovered")
                    frozen_since = None
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def _heartbeat_loop(self):
        n = 0
        while self.running:
            try:
                time.sleep(30)
                n += 1
                now = time.time()
                parts = []
                for nm, attr in (("exec", "executor_tick"), ("listen", "listener_tick"),
                                 ("ui", "main_heartbeat")):
                    t = getattr(self, attr, 0)
                    age = int(now - t) if t else -1
                    parts.append(f"{nm}={age}s")
                up = int(now - script_start_time)
                log_event("HEARTBEAT",
                          f"up={up//3600}h{(up%3600)//60:02d}m threads={_threading_module.active_count()} queue={self.cmd_queue.qsize()} "
                          f"waiting_viewers={getattr(self.cmd_queue, 'waiting_viewers', lambda: 0)()} "
                          f"dropped[old={getattr(self.cmd_queue, 'stats', {}).get('stale', 0)} per_user={getattr(self.cmd_queue, 'stats', {}).get('capped', 0)} full={getattr(self.cmd_queue, 'stats', {}).get('overflow', 0)}] "
                          f"backend={getattr(self,'backend','?')} last_tick[{' '.join(parts)}] "
                          f"mem={_rss_mb():.0f}MB ui_ticks={getattr(self,'_ui_tick_count',0)} "
                          f"worst_ui_tick={getattr(self,'_ui_worst_ms',0):.0f}ms tk_timers={getattr(self,'_pending_after',-1)} "
                          f"ui_backlog={self._ui_q.qsize()} gui_console_q={gui_log_queue.qsize()} "
                          f"msg_ids={len(getattr(self,'processed_msg_ids',()))} votes={len(getattr(self,'active_votes',{}))} "
                          f"executing={getattr(self,'_exec_current','') or '-'!r} maint={getattr(self,'vm_maintenance',False)} "
                          f"motion=[{MOTION.stats()}]")
                MOTION.worst_ms = 0.0
                self._ui_worst_ms = 0.0
                if n % 10 == 0:
                    names = sorted(t.name for t in _threading_module.enumerate())
                    plog("THREADS", ", ".join(names))
                    try:
                        top = sorted(_trace_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]
                        if top:
                            plog("SWALLOWED", "most frequent swallowed errors: " + ", ".join(f"{k}={v}" for k, v in top))
                    except Exception:
                        pass
            except Exception as _ex:
                _trace(_ex_where(), _ex)

    def start_app_threads(self):
        try:
            if not getattr(self, '_flask_started', False):
                self._flask_started = True
                plog("FLASK", f"starting overlay server on port {flask_port}")
                _spawn("flask", start_flask)
            if not getattr(self, '_music_started', False):
                self._music_started = True
                _spawn("music-engine", self.tick_music_engine)
            if not getattr(self, '_watcher_started', False):
                self._watcher_started = True
                _spawn("error-watcher", self.error_watcher_loop)
            if not getattr(self, '_hardwatchdog_started', False):
                self._hardwatchdog_started = True
                _spawn("hard-watchdog", self.hard_watchdog_loop)
            if not getattr(self, '_freezewatch_started', False):
                self._freezewatch_started = True
                _spawn("freeze-watchdog", self._freeze_watchdog)
            if not getattr(self, '_automation_started', False):
                self._automation_started = True
                _spawn("automation", self.automation_loop)
            if not getattr(self, '_health_started', False):
                self._health_started = True
                _spawn("vm-health", self.vm_health_watchdog)
            if not getattr(self, '_hb_started', False):
                self._hb_started = True
                _spawn("heartbeat", self._heartbeat_loop)
            if not getattr(self, '_dialogwatch_started', False):
                self._dialogwatch_started = True
                _spawn("dialog-watcher", self._crash_dialog_watcher)
            lt = getattr(self, 'listener_thread', None)
            if lt is None or not lt.is_alive():
                self.listener_id += 1
                if lt is not None:
                    plog("THREAD", f"chat listener was dead - starting listener #{self.listener_id}")
                self.listener_thread = _spawn(f"chat-listener-{self.listener_id}", self.chat_listener_loop, (self.listener_id,))
            et = getattr(self, 'executor_thread', None)
            if et is None or not et.is_alive():
                self.executor_id += 1
                if et is not None:
                    plog("THREAD", f"executor was dead - starting executor #{self.executor_id}")
                self.executor_thread = _spawn(f"executor-{self.executor_id}", self.executor_loop, (self.executor_id,))
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
        with open("boot_log.txt", "a", encoding="utf-8") as _bf:
            _bf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] entering main, creating window...\n")
    except Exception: pass
    try:
        plog("INIT", f"dpi awareness: {_win_dpi_aware()}")
        plog("INIT", "creating Tk root window")
        main_ui_root = tk.Tk()
        plog("INIT", f"Tk {main_ui_root.tk.call('info', 'patchlevel')} ready, threaded={main_ui_root.tk.call('info', 'exists', 'tcl_platform(threaded)')}")
        try:
            with open("boot_log.txt", "a", encoding="utf-8") as _bf:
                _bf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Tk() ok, building app...\n")
        except Exception: pass
        main_gui_application = ChatPlaysApp(main_ui_root)
        try:
            with open("boot_log.txt", "a", encoding="utf-8") as _bf:
                _bf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] app built, entering mainloop.\n")
        except Exception: pass

        if ("--relaunched" in sys.argv or "--minimized" in sys.argv
                or os.environ.get("YT2VM_MINIMIZED") == "1"):
            def _minimize_after_start():
                try:
                    main_ui_root.iconify()
                    if "--relaunched" in sys.argv:
                        console_log("SYSTEM", "recovered from a crash - running minimized so the stream is not interrupted.")
                except Exception:
                    pass

            main_ui_root.after(400, _minimize_after_start)
        plog("INIT", f"entering Tk mainloop ({time.time() - script_start_time:.2f}s after launch)")
        main_ui_root.mainloop()
        plog("SHUTDOWN", "Tk mainloop returned")
    except (KeyboardInterrupt, SystemExit):
        write_log(CRASH_LINE_LOG, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SCRIPT STOPPED NORMALLY (user closed it)\n")
        log_event("SHUTDOWN", "interrupted by user (Ctrl+C / window closed)")
        out_flush(1.0)
        try: main_gui_application.running = False
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        try: main_ui_root.destroy()
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        try: print("\nshutting down.")
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        os._exit(0)
    except Exception as fatal_error:
        log_crash("__main__", fatal_error)
        out_flush(1.5)
        try:
            with open("crash_log.txt", "w") as f: traceback.print_exc(file=f)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        try: set_obs_scene(obs_scene_error)
        except Exception as _ex:
            _trace(_ex_where(), _ex)
        if _should_respawn():
            try:
                script_path = os.path.abspath(sys.argv[0])
                args = [sys.executable, script_path] + [a for a in sys.argv[1:] if a.startswith("--multistream")]
                if platform.system() == "Windows": subprocess.Popen(args, creationflags=0x00000010, close_fds=True)
                else: subprocess.Popen(args, start_new_session=True, close_fds=True)
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            os._exit(1)
        else:
            try:
                err_root = tk.Tk(); err_root.withdraw()
                messagebox.showerror("error", f"crashed repeatedly ({fatal_error}). not respawning to avoid a boot loop.")
                err_root.destroy()
            except Exception as _ex:
                _trace(_ex_where(), _ex)
            input("press enter to exit...")
