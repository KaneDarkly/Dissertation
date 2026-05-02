"""
Arsenal Image Mounter (AIM) wrappers.

Drives the AIM command-line tool to mount/unmount E01 forensic disk images
read-only.  Mount runs in a background thread so the GUI stays responsive
while AIM attaches the volume.
"""

from tkinter import  filedialog, messagebox, ttk
import subprocess
import os
import threading

__all__ = [
    'open_file',
    'mount_e01_arsenal',
    'unmount_arsenal',
]
try:
    import pyewf
except ImportError:
    pyewf = None




def mount_e01_arsenal(self):
    """Prompt for an .E01 file and mount it read-only via aim_cli.exe."""
    # File picker — restrict to .E01 images
    self.filename = filedialog.askopenfilename(initialdir=os.getcwd(), title="Select a File", filetypes=[("Image file", "*.e01"), ("All files", "*.*")])
    if self.filename and not self.filename.lower().endswith('.e01'):
        messagebox.showerror("Invalid File", "The chosen file cannot be mounted. Please select a .E01 file.")
        return
    if self.filename:
        aim_cli = r"C:\Users\Joads\Downloads\Arsenal-Image-Mounter-v3.12.331\Arsenal-Image-Mounter-v3.12.331\aim_cli.exe"
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
        messagebox.showinfo("Success", "E01 mounted as read-only using Arsenal Image Mounter.")
        def run_mount():
            # Background worker — runs AIM and surfaces any errors on the UI thread
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"[AIM] Return code: {result.returncode}")
            print(f"[AIM] Stdout: {result.stdout}")
            print(f"[AIM] Stderr: {result.stderr}")
            if result.returncode == 0:
                pass
            else:
                self.tk.after(0, lambda: messagebox.showerror("AIM Error", f"Failed to mount image:\n{result.stderr}"))

        threading.Thread(target=run_mount, daemon=True).start()

def unmount_arsenal(self):
    """Dismount every image currently attached by AIM."""
    aim_cli = r"C:\Users\Joads\Downloads\Arsenal-Image-Mounter-v3.12.331\Arsenal-Image-Mounter-v3.12.331\aim_cli.exe"
    cmd = [
        aim_cli,
        "--dismount"
    ]
    print(f"[AIM] Running: {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[AIM] Return code: {result.returncode}")
    print(f"[AIM] Stdout: {result.stdout}")
    print(f"[AIM] Stderr: {result.stderr}")
    if result.returncode == 0:
        messagebox.showinfo("Success", f"Unmounted all images using Arsenal Image Mounter.")
    else:
        messagebox.showerror("AIM Error", f"Failed to unmount image:\n{result.stderr}")



