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

        btn_view_artefacts = Button(self.taskbar, text='View Artefacts', command=self.view_artefacts_folder)
        btn_view_artefacts.pack(side=LEFT, padx=5, pady=5)

        # Frame for artefact viewing (fills below taskbar)
        self.artefact_frame = Frame(self.tk)
        self.artefact_frame.pack(side=TOP, fill=BOTH, expand=True)

    def view_artefacts_folder(self):
        folder = filedialog.askdirectory(title="Select Extracted Artefacts Folder")
        if not folder:
            return
        # List immediate subfolders as usernames
        user_browser_map = {}
        try:
            usernames = [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]
        except Exception:
            usernames = []
        for username in usernames:
            user_path = os.path.join(folder, username)
            browser_map = {}
            for root, dirs, files in os.walk(user_path):
                for file in files:
                    lower_file = file.lower()
                    browser = None
                    if lower_file == "history":
                        if "chrome" in root.lower():
                            browser = "Chrome"
                        elif "edge" in root.lower():
                            browser = "Edge"
                        else:
                            browser = "Chrome"
                    elif lower_file == "places.sqlite":
                        browser = "Firefox"
                    if browser:
                        browser_map[browser] = os.path.join(root, file)
            if browser_map:
                user_browser_map[username] = browser_map
        self.clear_artefact_frame()
        if not user_browser_map:
            Label(self.artefact_frame, text="No browser history databases found in the selected folder.").pack(padx=10, pady=10)
            return
        self.show_user_dropdown(user_browser_map)

    def show_user_dropdown(self, user_browser_map):
        self.clear_artefact_frame()
        Label(self.artefact_frame, text="Select a user to view:").pack(padx=10, pady=10)
        user_names = list(user_browser_map.keys())
        user_var = StringVar()
        user_var.set(user_names[0])
        user_dropdown = ttk.Combobox(self.artefact_frame, textvariable=user_var, values=user_names, state="readonly")
        user_dropdown.pack(padx=10, pady=5)

        # Frame for browser and table selection/data
        browser_table_frame = Frame(self.artefact_frame)
        browser_table_frame.pack(fill=BOTH, expand=True)

        def show_selected_user(*args):
            for widget in browser_table_frame.winfo_children():
                widget.destroy()
            browser_map = user_browser_map[user_var.get()]
            self.show_browser_dropdown(browser_map, browser_table_frame)

        user_dropdown.bind("<<ComboboxSelected>>", show_selected_user)
        show_selected_user()

    def show_browser_dropdown(self, browser_map, parent_frame):
        Label(parent_frame, text="Select a browser to view:").pack(padx=10, pady=10)
        browser_names = list(browser_map.keys())
        browser_var = StringVar()
        browser_var.set(browser_names[0])
        dropdown = ttk.Combobox(parent_frame, textvariable=browser_var, values=browser_names, state="readonly")
        dropdown.pack(padx=10, pady=5)

        # Frame for table selection and data
        db_view_frame = Frame(parent_frame)
        db_view_frame.pack(fill=BOTH, expand=True)

        def show_selected_browser(*args):
            for widget in db_view_frame.winfo_children():
                widget.destroy()
            db_path = browser_map[browser_var.get()]
            self.show_database_tables(db_path, db_view_frame)

        dropdown.bind("<<ComboboxSelected>>", show_selected_browser)
        show_selected_browser()

    def show_database_tables(self, db_path, parent_frame):
        import sqlite3
        # Get all table names
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            conn.close()
        except Exception as e:
            Label(parent_frame, text=f"Could not read database tables: {e}").pack()
            return
        if not tables:
            Label(parent_frame, text="No tables found in database.").pack()
            return

        # Dropdown to select table
        table_var = StringVar()
        table_var.set(tables[0])
        dropdown = ttk.Combobox(parent_frame, textvariable=table_var, values=tables, state="readonly")
        dropdown.pack(padx=10, pady=5)

        # Frame for table view
        table_view_frame = Frame(parent_frame)
        table_view_frame.pack(fill=BOTH, expand=True)

        def show_table(table_name):
            for widget in table_view_frame.winfo_children():
                widget.destroy()
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cur.fetchall()]
                if not columns:
                    Label(table_view_frame, text="No columns found.").pack()
                    return
                tree = ttk.Treeview(table_view_frame, columns=columns, show="headings")
                for col in columns:
                    tree.heading(col, text=col)
                tree.pack(fill=BOTH, expand=True)
                cur.execute(f"SELECT * FROM {table_name} LIMIT 100")
                for row in cur.fetchall():
                    tree.insert("", END, values=row)
                conn.close()
            except Exception as e:
                Label(table_view_frame, text=f"Could not read table: {e}").pack()

        show_table(tables[0])

        def on_table_change(event):
            show_table(table_var.get())

        dropdown.bind("<<ComboboxSelected>>", on_table_change)

    def view_history_database(self, db_path):
        import sqlite3
        self.clear_artefact_frame()
        Label(self.artefact_frame, text=f"Database: {os.path.basename(db_path)}").pack(padx=10, pady=10)

        # Get all table names
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            conn.close()
        except Exception as e:
            Label(self.artefact_frame, text=f"Could not read database tables: {e}").pack()
            return
        if not tables:
            Label(self.artefact_frame, text="No tables found in database.").pack()
            return

        # Dropdown to select table
        table_var = StringVar()
        table_var.set(tables[0])
        dropdown = ttk.Combobox(self.artefact_frame, textvariable=table_var, values=tables, state="readonly")
        dropdown.pack(padx=10, pady=5)

        # Frame for table view
        table_view_frame = Frame(self.artefact_frame)
        table_view_frame.pack(fill=BOTH, expand=True)

        def show_table(table_name):
            # Clear previous table view
            for widget in table_view_frame.winfo_children():
                widget.destroy()
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                # Get columns
                cur.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cur.fetchall()]
                if not columns:
                    Label(table_view_frame, text="No columns found.").pack()
                    return
                tree = ttk.Treeview(table_view_frame, columns=columns, show="headings")
                for col in columns:
                    tree.heading(col, text=col)
                tree.pack(fill=BOTH, expand=True)
                # Get up to 100 rows
                cur.execute(f"SELECT * FROM {table_name} LIMIT 100")
                for row in cur.fetchall():
                    tree.insert("", END, values=row)
                conn.close()
            except Exception as e:
                Label(table_view_frame, text=f"Could not read table: {e}").pack()

        # Initial table display
        show_table(tables[0])

        def on_table_change(event):
            show_table(table_var.get())

        dropdown.bind("<<ComboboxSelected>>", on_table_change)

    def clear_artefact_frame(self):
        for widget in self.artefact_frame.winfo_children():
            widget.destroy()

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
            drive_options.append((drive, found_user_data))

        # Automatically select the drive with user folders
        drives_with_user_data = [drive for drive, found in drive_options if found]
        if drives_with_user_data:
            selected_drive = drives_with_user_data[0]
        else:
            # If none found, fallback to first drive and warn user
            selected_drive = drive_options[0][0]
            if not messagebox.askyesno("Drive Check", f"No user folders detected on any new drive. Continue with {selected_drive}?"):
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
