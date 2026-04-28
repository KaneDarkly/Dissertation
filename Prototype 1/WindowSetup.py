from tkinter import *
from tkinter import filedialog, messagebox
from tkinter import ttk
import os
from OpenFile import mount_e01_arsenal, unmount_arsenal
from Extract_Arefacts import extract_browser_artefacts_from_mounted
from drive_utils import list_all_drives, get_newly_mounted_drive
import time


class Fullscreen_Window:

    def __init__(self):
        self.tk = Tk()
        self.frame = Frame(self.tk)
        self.frame.pack()
        self.state = False
        self.tk.bind("<F11>", self.toggle_fullscreen)
        self.tk.bind("<Escape>", self.end_fullscreen)
        self.tk.title("Prototype 1")
        # Set the window size to 1000x700 pixels and then position it in the
        # centre of the screen using a small helper.  Using `tk::PlaceWindow`
        # works on most platforms but calculating the offsets ourselves is a
        # bit more portable and gives us control over the geometry string.
        width, height = 1000, 700
        self.tk.geometry(f"{width}x{height}")
        self._center_window(width, height)
        self.taskbar = Frame(self.tk, bg='lightgrey', height=30)
        self.taskbar.pack(side=TOP, fill=X)

        btn_arsenal = Button(self.taskbar, text='Select File', command=self.store_drives_and_mount)
        btn_arsenal.pack(side=LEFT, padx=5, pady=5)

        #btn_unmount = Button(self.taskbar, text='Unmount AIM Z:', command=lambda: unmount_arsenal(self))
        #btn_unmount.pack(side=LEFT, padx=5, pady=5)

        #btn_extract = Button(self.taskbar, text='Extract Browser Artefacts', command=self.extract_artefacts_mounted_gui)
        #btn_extract.pack(side=LEFT, padx=5, pady=5)

    def store_drives_and_mount(self):
        self.drives_before_mount = list_all_drives()
        mount_e01_arsenal(self)
        # Pass a callback to unmount after extraction completes
        self.extract_artefacts_mounted_gui(lambda: unmount_arsenal(self))


    def extract_artefacts_mounted_gui(self, on_complete=None):
        # Use the drives stored at mount time as the 'before' set
        drives_before = getattr(self, 'drives_before_mount', None)
        if drives_before is None:
            messagebox.showinfo("Info", "Please use the 'Mount E01' button before extracting artefacts.")
            return
        messagebox.showinfo("Mount Image", "If you haven't already, mount your E01 image now using Arsenal Image Mounter, then click OK.")
        drives_after = list_all_drives()
        new_drives = drives_after - drives_before
        if not new_drives:
            messagebox.showerror("No New Drive Detected", "No new drive was detected. Please ensure the image is mounted.")
            return
        # If more than one new drive, prompt user to select
        user_folders = ["Users", "Documents", "Users\Public", "Users\Default"]
        drive_options = []
        for drive in sorted(new_drives):
            found_user_data = False
            for folder in user_folders:
                if os.path.exists(os.path.join(drive, folder)):
                    found_user_data = True
                    break
            label = f"{drive} - {'User folders found' if found_user_data else 'No user folders'}"
            drive_options.append((drive, label, found_user_data))
        if len(drive_options) == 1:
            selected_drive = drive_options[0][0]
        else:
            # Prompt user to select from the list
            import tkinter.simpledialog
            options_text = "\n".join(f"{i+1}. {label}" for i, (_, label, _) in enumerate(drive_options))
            choice = tkinter.simpledialog.askstring(
                "Select Drive",
                f"Multiple new drives detected.\nSelect the number of the drive to use:\n\n{options_text}"
            )
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(drive_options):
                    raise ValueError
                selected_drive = drive_options[idx][0]
            except Exception:
                messagebox.showerror("Invalid Selection", "No valid drive selected.")
                return
        # Step 3: Check for user folders (e.g., Users, Documents) on selected drive
        found_user_data = False
        for folder in user_folders:
            if os.path.exists(os.path.join(selected_drive, folder)):
                found_user_data = True
                break
        if not found_user_data:
            if not messagebox.askyesno("Drive Check", f"The selected drive ({selected_drive}) does not appear to contain typical user folders. Continue anyway?"):
                return
        # Step 4: Prompt for output folder
        output_dir = filedialog.askdirectory(title="Select Output Directory for Artefacts")
        if not output_dir:
            return
        # Step 5: Create a subfolder for this extraction
        import datetime
        session_folder = os.path.join(output_dir, f"artefacts_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(session_folder, exist_ok=True)
        import threading
        progress = Toplevel(self.tk)
        progress.title("Extracting Artefacts")
        Label(progress, text="Extracting browser artefacts...").pack(padx=10, pady=10)
        pb = ttk.Progressbar(progress, orient="horizontal", length=400, mode="determinate")
        pb.pack(padx=10, pady=10)
        pb['value'] = 0
        pb['maximum'] = 1
        progress.update()

        def progress_callback(done, total):
            pb['maximum'] = total
            pb['value'] = done
            progress.update()

        fail_log_path = os.path.join(session_folder, "failed_copies.txt")

        def do_extraction():
            try:
                artefacts, failed = extract_browser_artefacts_from_mounted(selected_drive, session_folder, progress_callback, fail_log_path)
            except Exception as e:
                artefacts, failed = [], 0
                with open(fail_log_path, 'a', encoding='utf-8') as flog:
                    flog.write(f"Critical error: {e}\n")
            progress.destroy()
            if artefacts:
                msg = f"Found and copied {len(artefacts)} artefact(s).\nFailed to copy: {failed}\nSee: {session_folder}"
                if failed:
                    msg += f"\nSee failed_copies.txt for details."
                self.tk.after(0, lambda: messagebox.showinfo("Extraction Complete", msg))
            else:
                self.tk.after(0, lambda: messagebox.showinfo("No Artefacts Found", "No browser artefacts were found in the mounted drive."))
            # Call the on_complete callback if provided
            if on_complete:
                self.tk.after(0, on_complete)

        threading.Thread(target=do_extraction, daemon=True).start()

    def toggle_fullscreen(self, event=None):
        self.state = not self.state  # Just toggling the boolean
        self.tk.attributes("-fullscreen", self.state)
        return "break"

    def _center_window(self, width, height):
        self.tk.update_idletasks()
        screen_w = self.tk.winfo_screenwidth()
        screen_h = self.tk.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        self.tk.geometry(f"{width}x{height}+{x}+{y}")

    def end_fullscreen(self, event=None):
        self.state = False
        self.tk.attributes("-fullscreen", False)
        return "break"

def Create_Window():
    w = Fullscreen_Window()
    w.tk.mainloop()
    return w.tk
