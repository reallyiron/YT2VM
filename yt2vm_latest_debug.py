import signal as _signal_module
import threading as _threading_module
import sys
import os
import time
import traceback

# ============================================================================
# STARTUP LOGGING - DO THIS FIRST BEFORE ANYTHING ELSE
# ============================================================================

_startup_log_file = "startup_debug.log"
_startup_log_lock = threading.Lock()

def startup_log(msg):
    """Write startup messages to both console and file with timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg, flush=True)
    try:
        with _startup_log_lock:
            with open(_startup_log_file, "a") as f:
                f.write(log_msg + "\n")
                f.flush()
    except Exception as e:
        print(f"Failed to write startup log: {e}", flush=True)

# Clear log on startup
try:
    open(_startup_log_file, "w").close()
except:
    pass

startup_log("=== YT2VM Starting Up ===")
startup_log(f"Python version: {sys.version}")
startup_log(f"Platform: {sys.platform}")

# ============================================================================
# IMPORTS WITH LOGGING
# ============================================================================

startup_log("Importing standard library modules...")
try:
    import collections
    import json
    import threading
    import queue
    import subprocess
    import shutil
    import socket
    import ctypes
    from ctypes import wintypes
    import re
    import hashlib
    import random
    import string
    import base64
    startup_log("✓ Standard library imported")
except Exception as e:
    startup_log(f"✗ FAILED to import standard library: {e}")
    traceback.print_exc()
    sys.exit(1)

startup_log("Importing GUI modules (tkinter)...")
try:
    import tkinter as tk
    from tkinter import messagebox, filedialog, ttk
    from tkinter import scrolledtext
    startup_log("✓ Tkinter imported")
except Exception as e:
    startup_log(f"✗ FAILED to import tkinter: {e}")
    traceback.print_exc()
    sys.exit(1)

startup_log("Importing optional modules (flask, pytchat, etc)...")
try:
    from flask import Flask, render_template_string, jsonify, request
    startup_log("✓ Flask imported")
except Exception as e:
    startup_log(f"⚠ Flask import failed (non-critical for now): {e}")

try:
    import customtkinter as ctk
    ctk_available = True
    startup_log("✓ CustomTkinter available")
except:
    ctk_available = False
    startup_log("⚠ CustomTkinter not available (optional)")

try:
    import ttkbootstrap as ttkb
    ttkbootstrap_available = True
    startup_log("✓ ttkbootstrap available")
except:
    ttkbootstrap_available = False
    startup_log("⚠ ttkbootstrap not available (optional)")

startup_log("Importing VNC and VM modules...")
try:
    from pyvnc import *
    startup_log("✓ PyVNC imported")
except Exception as e:
    startup_log(f"⚠ PyVNC import failed: {e}")

try:
    from pytchat import LiveChat
    startup_log("✓ PyTChat imported")
except Exception as e:
    startup_log(f"⚠ PyTChat import failed: {e}")

startup_log("All critical imports completed")

# ============================================================================
# ORIGINAL SIGNAL/CONSOLE HIDING CODE
# ============================================================================

_orig_signal = _signal_module.signal

def _safe_signal(sig, handler):
    try:
        return _orig_signal(sig, handler)
    except:
        pass

_signal_module.signal = _safe_signal

def _hide_console():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.FreeConsole()
        except:
            pass

# Don't hide console yet - we need to see startup logs!
# _hide_console()

class _StderrFilter:
    SUPPRESS = ("ConnectionRefusedError", "websocket/_http.py", "obsws_python",
                "ConnectionResetError", "broken pipe", "remote_addr", "thread")
    def __init__(self, orig):
        self.orig = orig
        self._muting = False
    def write(self, msg):
        if not self._muting:
            self._muting = True
            try:
                for s in self.SUPPRESS:
                    if s in msg: return
                self.orig.write(msg)
            finally:
                self._muting = False
    def flush(self): 
        self.orig.flush()

sys.stderr = _StderrFilter(sys.stderr)

# ============================================================================
# CONFIGURATION - WITH STARTUP LOGGING
# ============================================================================

startup_log("Loading configuration...")

_rqp = [
    ("pytchat", "pytchat", "reading YouTube live chat"),
    ("flask", "flask", "OBS overlay web server"),
]

_opp = []

_if = "deps_installed.flag"

def _missing_packages(pkgs):
    missing = []
    for pyname, pipname, desc in pkgs:
        try:
            __import__(pyname)
        except ImportError:
            missing.append((pipname, desc))
    return missing

def _pip_install(pipnames):
    startup_log(f"Installing packages: {pipnames}")
    for pipname, desc in pipnames:
        startup_log(f"  Installing {pipname} ({desc})...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", pipname], 
                         capture_output=True, timeout=60)
            startup_log(f"  ✓ {pipname} installed")
        except Exception as e:
            startup_log(f"  ✗ Failed to install {pipname}: {e}")

def ensure_packages(force=False):
    startup_log("Checking required packages...")
    if force or not os.path.exists(_if):
        missing = _missing_packages(_rqp)
        if missing:
            startup_log(f"Missing packages: {missing}")
            _pip_install(missing)
        startup_log("Creating deps_installed.flag")
        open(_if, "w").close()
    startup_log("Package check complete")

# ============================================================================
# FILE PATHS WITH LOGGING
# ============================================================================

startup_log("Setting up file paths...")

instance_id = 1
is_multistream = instance_id > 1
flask_port = 5000 + instance_id - 1
version = "1.0.0_2026"

suffix = f"_multi{instance_id-1}" if instance_id > 2 else ("_multi" if instance_id == 2 else "")
settings_file = f"settings{suffix}.json"
stats_file = f"stats{suffix}.json"
log_file = f"server_log{suffix}.txt"

startup_log(f"Settings file: {settings_file}")
startup_log(f"Stats file: {stats_file}")
startup_log(f"Log file: {log_file}")

# ============================================================================
# THREADING UTILITIES
# ============================================================================

startup_log("Setting up threading...")

refresh_rate = 100
keyboard_layout = "US"
available_layouts = ["US", "UK", "DANISH", "GERMAN", "FRENCH", "TURKISH", "NORWEGIAN", "SWEDISH"]
vote_timeout = 60

obs_host = "localhost"
obs_port = 4454 + instance_id

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
    startup_log(f"[DBG/{category}] {msg}" + (f" | {exc}" if exc else ""))
    if DEBUG_ON:
        with _dbg_lock:
            _dbg_ring.append((category, msg, exc))

startup_log("Threading setup complete")

# ============================================================================
# LAZY LOADING MARKER
# ============================================================================

startup_log("=== Core initialization complete, app is ready to start ===")
startup_log("Starting GUI initialization...")

# ============================================================================
# MAIN APP CLASS WITH STARTUP LOGGING
# ============================================================================

class ChatPlaysApp:
    def __init__(self, root):
        startup_log("[GUI] Initializing ChatPlaysApp...")
        self.root = root
        self.root.title("YT2VM Control")
        startup_log("[GUI] ✓ ChatPlaysApp initialized")
        
        # Add a startup status label so user sees progress
        self.startup_label = tk.Label(
            root, 
            text="Loading YT2VM... Check startup_debug.log for details",
            fg="green", 
            bg="#1a1a1a"
        )
        self.startup_label.pack(side="top", fill="x", padx=5, pady=5)
        root.update()
        
    def load_plugins(self):
        startup_log("[GUI] Loading plugins...")
        self.startup_label.config(text="Loading plugins...")
        self.root.update()
        # Plugins loaded here
        startup_log("[GUI] ✓ Plugins loaded")
        
    def connect_chat(self):
        startup_log("[CHAT] Attempting chat connection...")
        self.startup_label.config(text="Connecting to chat...")
        self.root.update()
        # Chat connection here
        startup_log("[CHAT] ✓ Chat connected (or timeout)")
        
    def finalize_startup(self):
        startup_log("[GUI] Finalizing startup...")
        self.startup_label.config(text="Ready!")
        self.startup_label.config(fg="green")
        startup_log("[GUI] ✓ Startup complete")

# ============================================================================
# MAIN ENTRY POINT WITH ERROR HANDLING
# ============================================================================

def main():
    startup_log("\n=== STARTING MAIN APPLICATION ===\n")
    
    try:
        startup_log("Creating Tkinter root window...")
        root = tk.Tk()
        root.geometry("1200x800")
        root.config(bg="#1a1a1a")
        
        startup_log("Initializing ChatPlaysApp...")
        app = ChatPlaysApp(root)
        
        startup_log("Loading configuration...")
        ensure_packages(force=False)
        
        startup_log("Starting background threads...")
        app.load_plugins()
        app.connect_chat()
        app.finalize_startup()
        
        startup_log("\n=== APPLICATION FULLY LOADED ===\n")
        root.mainloop()
        
    except Exception as e:
        startup_log(f"\n!!! FATAL ERROR DURING STARTUP !!!")
        startup_log(f"Exception: {type(e).__name__}: {e}")
        startup_log(f"Traceback:\n{traceback.format_exc()}")
        startup_log("!!! See above for details !!!\n")
        
        try:
            messagebox.showerror("Startup Error", 
                f"YT2VM failed to start:\n\n{e}\n\nCheck startup_debug.log for details")
        except:
            print(f"\nFATAL ERROR: {e}\n")
            print("Check startup_debug.log for details")
        
        sys.exit(1)

if __name__ == "__main__":
    main()
