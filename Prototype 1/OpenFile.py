"""
Arsenal Image Mounter (AIM) wrappers.

Drives the AIM command-line tool to mount/unmount E01 forensic disk images
read-only.  Mount runs in a background thread so the GUI stays responsive
while AIM attaches the volume.

The path to aim_cli.exe is resolved at runtime (not hard-coded) by:
  1. checking a small config file written next to this module,
  2. consulting PATH,
  3. recursively scanning common install roots (Program Files, Downloads, Desktop),
  4. asking the user to locate aim_cli.exe manually.
The resolved path is cached so subsequent runs find it instantly.
"""

from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import shutil
import threading

__all__ = [
    'open_file',
    'mount_e01_arsenal',
    'unmount_arsenal',
    'find_aim_cli',
]

try:
    import pyewf
except ImportError:
    pyewf = None


# ── aim_cli.exe discovery ────────────────────────────────────────────────────

AIM_EXE_NAME   = "aim_cli.exe"
# Cache file stored alongside this module so the path persists between runs
AIM_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              ".aim_cli_path")
# Roots to scan recursively (limited depth) when nothing else turns it up
AIM_SEARCH_ROOTS = [
    os.environ.get("ProgramFiles", r"C:\Program Files"),
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    os.path.expanduser(r"~\Downloads"),
    os.path.expanduser(r"~\Desktop"),
    os.path.expanduser(r"~\Documents"),
]
AIM_MAX_SCAN_DEPTH = 4   # keep the recursive walk bounded so it stays fast


def _read_cached_aim_path():
    try:
        with open(AIM_CACHE_FILE, "r", encoding="utf-8") as fh:
            path = fh.read().strip()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def _write_cached_aim_path(path):
    try:
        with open(AIM_CACHE_FILE, "w", encoding="utf-8") as fh:
            fh.write(path)
    except Exception as e:
        print(f"[AIM] Failed to cache path: {e}")


def _scan_for_aim(root, max_depth=AIM_MAX_SCAN_DEPTH):
    """
    Walk `root` up to max_depth deep, returning the first aim_cli.exe found.
    Bounded depth keeps the scan responsive even on large drives.
    """
    if not root or not os.path.isdir(root):
        return None
    root_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune anything below max_depth before descending further
        depth = dirpath.count(os.sep) - root_depth
        if depth >= max_depth:
            dirnames[:] = []
        if AIM_EXE_NAME in filenames:
            return os.path.join(dirpath, AIM_EXE_NAME)
    return None


def find_aim_cli(parent_tk=None, force_prompt=False):
    """
    Resolve the path to aim_cli.exe using cache → PATH → filesystem scan →
    user prompt (in that order).  Returns the path or None if the user cancels.

    Pass force_prompt=True to skip cache/PATH/scan and go straight to the
    file-picker (useful for a "change AIM location" menu item later).
    """
    if not force_prompt:
        # 1. Cached from a previous run
        cached = _read_cached_aim_path()
        if cached:
            return cached

        # 2. On PATH (rare, but it's the cheapest check)
        on_path = shutil.which(AIM_EXE_NAME)
        if on_path:
            _write_cached_aim_path(on_path)
            return on_path

        # 3. Bounded recursive scan of likely install roots
        for root in AIM_SEARCH_ROOTS:
            found = _scan_for_aim(root)
            if found:
                _write_cached_aim_path(found)
                return found

    # 4. Last resort — ask the user to point us at it
    if parent_tk is not None:
        messagebox.showinfo(
            "Locate Arsenal Image Mounter",
            f"{AIM_EXE_NAME} could not be found automatically.\n\n"
            "Please select aim_cli.exe in the next dialog."
        )
    picked = filedialog.askopenfilename(
        title=f"Locate {AIM_EXE_NAME}",
        filetypes=[("Arsenal Image Mounter CLI", AIM_EXE_NAME),
                   ("Executable", "*.exe"), ("All files", "*.*")],
    )
    if picked and os.path.basename(picked).lower() == AIM_EXE_NAME.lower():
        _write_cached_aim_path(picked)
        return picked
    if picked:
        messagebox.showerror(
            "Wrong File",
            f"The selected file is not {AIM_EXE_NAME}."
        )
    return None


# ── Mount / unmount ──────────────────────────────────────────────────────────

def mount_e01_arsenal(self):
    """Prompt for an .E01 file and mount it read-only via aim_cli.exe."""
    # File picker — restrict to .E01 images
    self.filename = filedialog.askopenfilename(
        initialdir=os.getcwd(), title="Select a File",
        filetypes=[("Image file", "*.e01"), ("All files", "*.*")])
    if self.filename and not self.filename.lower().endswith('.e01'):
        messagebox.showerror("Invalid File",
            "The chosen file cannot be mounted. Please select a .E01 file.")
        return
    if self.filename:
        # Resolve aim_cli.exe — falls back to a user picker if not auto-found
        aim_cli = find_aim_cli(parent_tk=self.tk)
        if not aim_cli:
            messagebox.showerror("AIM Not Found",
                "Arsenal Image Mounter CLI is required but was not located.")
            return

        # Normalise the path so AIM accepts it regardless of how it was picked
        filename = os.path.abspath(self.filename)
        filename = os.path.normpath(filename)
        cmd = [
            aim_cli,
            "--mount",
            f"--filename={filename}",
            "--readonly"   # forensic integrity — never write back to the image
        ]

        # Show success messagebox immediately; the actual mount happens off-thread
        messagebox.showinfo("Success",
            "E01 mounted as read-only using Arsenal Image Mounter.")
        def run_mount():
            # Background worker — runs AIM and surfaces any errors on the UI thread
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"[AIM] Return code: {result.returncode}")
            print(f"[AIM] Stdout: {result.stdout}")
            print(f"[AIM] Stderr: {result.stderr}")
            if result.returncode == 0:
                pass
            else:
                self.tk.after(0, lambda: messagebox.showerror(
                    "AIM Error", f"Failed to mount image:\n{result.stderr}"))

        threading.Thread(target=run_mount, daemon=True).start()


def unmount_arsenal(self):
    """Dismount every image currently attached by AIM."""
    aim_cli = find_aim_cli(parent_tk=self.tk)
    if not aim_cli:
        messagebox.showerror("AIM Not Found",
            "Arsenal Image Mounter CLI is required but was not located.")
        return
    cmd = [aim_cli, "--dismount"]
    print(f"[AIM] Running: {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[AIM] Return code: {result.returncode}")
    print(f"[AIM] Stdout: {result.stdout}")
    print(f"[AIM] Stderr: {result.stderr}")
    if result.returncode == 0:
        messagebox.showinfo("Success",
            f"Unmounted all images using Arsenal Image Mounter.")
    else:
        messagebox.showerror("AIM Error",
            f"Failed to unmount image:\n{result.stderr}")
