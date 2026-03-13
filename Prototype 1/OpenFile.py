
def open_file(self):
    # This is a placeholder. You can implement the original open_file logic or leave it as a stub if only Arsenal mounting is needed.
    messagebox.showinfo("Info", "Use the Arsenal Mount button to mount E01 images, or implement open_file logic here.")
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
    self.filename = filedialog.askopenfilename(initialdir=os.getcwd(), title="Select a File", filetypes=[("Image file", "*.e01"), ("All files", "*.*")])
    if self.filename and not self.filename.lower().endswith('.e01'):
        messagebox.showerror("Invalid File", "The chosen file cannot be mounted. Please select a .E01 file.")
        return
    if self.filename:
        aim_cli = r"C:\Users\Joads\Downloads\Arsenal-Image-Mounter-v3.12.331\Arsenal-Image-Mounter-v3.12.331\aim_cli.exe"
        # Normalize and absolutize the filename
        filename = os.path.abspath(self.filename)
        filename = os.path.normpath(filename)
        cmd = [
            aim_cli,
            "--mount",
            f"--filename={filename}",
            "--readonly"
        ]
        # Show a 'Mounting in progress...' label at the bottom


        # Show messagebox immediately as mounting begins
        messagebox.showinfo("Success", "E01 mounted as read-only using Arsenal Image Mounter.")
        def run_mount():
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



