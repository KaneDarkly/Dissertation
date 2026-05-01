from tkinter import *
from tkinter import filedialog, messagebox
from tkinter import ttk
import os
from OpenFile import mount_e01_arsenal, unmount_arsenal
from Extract_Arefacts import extract_browser_artefacts_from_mounted
from drive_utils import list_all_drives
from private_browsing_check import check_private_browsing_indicators
import time

# ── Colour palette ────────────────────────────────────────────────────────────
BG        = "#0d1117"   # main background
PANEL     = "#161b22"   # card / panel background
TOOLBAR   = "#010409"   # header & status bar
ACCENT    = "#58a6ff"   # highlight blue
TEXT      = "#c9d1d9"   # primary text
TEXT_DIM  = "#8b949e"   # secondary / muted text
BORDER    = "#30363d"   # borders / separators
BTN_BG    = "#21262d"   # button background
BTN_HOVER = "#30363d"   # button hover background

FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_HEAD  = ("Segoe UI", 11, "bold")
FONT_MAIN  = ("Segoe UI", 10)
FONT_SUB   = ("Segoe UI",  9)
# ─────────────────────────────────────────────────────────────────────────────


class Fullscreen_Window:

    def __init__(self):
        self.tk = Tk()
        self.tk.configure(bg=BG)

        # Style the combobox dropdown list (must happen before any Combobox is created)
        self.tk.option_add("*TCombobox*Listbox.background",       PANEL)
        self.tk.option_add("*TCombobox*Listbox.foreground",       TEXT)
        self.tk.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.tk.option_add("*TCombobox*Listbox.selectForeground", BG)

        # Invisible compatibility frame (kept for parity with original)
        self.frame = Frame(self.tk, bg=BG)
        self.frame.pack()

        self.state = False
        self.tk.bind("<F11>", self.toggle_fullscreen)
        self.tk.bind("<Escape>", self.end_fullscreen)
        self.tk.title("Forensic Artefact Extractor")

        width, height = 1000, 700
        self.tk.geometry(f"{width}x{height}")
        self._center_window(width, height)

        self._apply_styles()
        self._build_header()
        self._build_toolbar()

        # Status bar must be packed from BOTTOM before the expanding content frame
        self._build_status_bar()

        Frame(self.tk, bg=BORDER, height=1).pack(fill=X)
        self.artefact_frame = Frame(self.tk, bg=BG)
        self.artefact_frame.pack(side=TOP, fill=BOTH, expand=True)

        self._show_welcome()

    # ── Style sheet ──────────────────────────────────────────────────────────

    def _apply_styles(self):
        style = ttk.Style(self.tk)
        style.theme_use("clam")

        style.configure("TCombobox",
            fieldbackground=PANEL, background=BTN_BG,
            foreground=TEXT, selectbackground=ACCENT, selectforeground=BG,
            arrowcolor=TEXT, bordercolor=BORDER,
            lightcolor=BORDER, darkcolor=BORDER, font=FONT_MAIN)
        style.map("TCombobox",
            fieldbackground=[("readonly", PANEL)],
            selectbackground=[("readonly", ACCENT)],
            foreground=[("readonly", TEXT)])

        style.configure("Treeview",
            background=PANEL, foreground=TEXT,
            fieldbackground=PANEL, rowheight=26, font=FONT_MAIN)
        style.configure("Treeview.Heading",
            background=BTN_BG, foreground=ACCENT,
            relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", BG)])
        style.map("Treeview.Heading",
            background=[("active", BTN_HOVER)])

        style.configure("Vertical.TScrollbar",
            background=BTN_BG, troughcolor=BG,
            arrowcolor=TEXT_DIM, bordercolor=BORDER)
        style.configure("Horizontal.TScrollbar",
            background=BTN_BG, troughcolor=BG,
            arrowcolor=TEXT_DIM, bordercolor=BORDER)

        style.configure("TProgressbar",
            background=ACCENT, troughcolor=PANEL,
            bordercolor=BORDER, thickness=10)

    # ── Layout builders ───────────────────────────────────────────────────────

    def _build_header(self):
        header = Frame(self.tk, bg=TOOLBAR, height=65)
        header.pack(side=TOP, fill=X)
        header.pack_propagate(False)

        title_block = Frame(header, bg=TOOLBAR)
        title_block.pack(side=LEFT, fill=Y, padx=20, pady=8)
        Label(title_block, text="FORENSIC ARTEFACT EXTRACTOR",
              font=FONT_TITLE, bg=TOOLBAR, fg=TEXT).pack(anchor=W)
        Label(title_block, text="Browser History Analysis & Evidence Collection",
              font=FONT_SUB, bg=TOOLBAR, fg=TEXT_DIM).pack(anchor=W)

        Label(header, text="v1.0  |  Prototype",
              font=FONT_SUB, bg=TOOLBAR, fg=TEXT_DIM).pack(side=RIGHT, padx=20)

        # Thin accent line beneath header
        Frame(self.tk, bg=ACCENT, height=2).pack(fill=X)

    def _build_toolbar(self):
        toolbar = Frame(self.tk, bg=PANEL, height=50)
        toolbar.pack(side=TOP, fill=X)
        toolbar.pack_propagate(False)

        Label(toolbar, text="Actions:", font=FONT_SUB,
              bg=PANEL, fg=TEXT_DIM).pack(side=LEFT, padx=(15, 5))

        self._make_btn(toolbar, "Select & Process File",
                       self.store_drives_and_mount).pack(side=LEFT, padx=5, pady=10)
        self._make_btn(toolbar, "View Artefacts",
                       self.view_artefacts_folder).pack(side=LEFT, padx=5, pady=10)

    def _build_status_bar(self):
        Frame(self.tk, bg=BORDER, height=1).pack(side=BOTTOM, fill=X)
        bar = Frame(self.tk, bg=TOOLBAR, height=26)
        bar.pack(side=BOTTOM, fill=X)
        bar.pack_propagate(False)

        self.status_var = StringVar(value="Ready")
        Label(bar, textvariable=self.status_var,
              font=FONT_SUB, bg=TOOLBAR, fg=TEXT_DIM, anchor=W
              ).pack(side=LEFT, padx=12, fill=Y)
        Label(bar, text="F11 — toggle fullscreen  |  Esc — exit fullscreen",
              font=FONT_SUB, bg=TOOLBAR, fg=TEXT_DIM
              ).pack(side=RIGHT, padx=12)

    def _show_welcome(self):
        self.clear_artefact_frame()
        wrap = Frame(self.artefact_frame, bg=BG)
        wrap.pack(expand=True)

        Label(wrap, text="Welcome to Forensic Artefact Extractor",
              font=("Segoe UI", 16, "bold"), bg=BG, fg=TEXT).pack(pady=(60, 6))
        Label(wrap,
              text="Select and process an E01 image, or load a previously extracted artefacts folder.",
              font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack()

        Frame(wrap, bg=BORDER, height=1, width=520).pack(pady=22)

        for title, desc in [
            ("Step 1  —  Select & Process File",
             "Mount an E01 disk image and automatically extract browser history databases."),
            ("Step 2  —  View Artefacts",
             "Browse and inspect previously extracted browser history databases."),
        ]:
            card = Frame(wrap, bg=PANEL, padx=22, pady=14)
            card.pack(fill=X, pady=5, ipadx=10, ipady=2)
            Label(card, text=title, font=("Segoe UI", 10, "bold"),
                  bg=PANEL, fg=ACCENT).pack(anchor=W)
            Label(card, text=desc, font=FONT_SUB,
                  bg=PANEL, fg=TEXT_DIM).pack(anchor=W, pady=(2, 0))

    # ── Widget factory helpers ────────────────────────────────────────────────

    def _make_btn(self, parent, text, command):
        btn = Button(parent, text=text, command=command,
                     bg=BTN_BG, fg=TEXT, relief=FLAT,
                     font=FONT_MAIN, padx=14, pady=5,
                     cursor="hand2", borderwidth=0,
                     activebackground=BTN_HOVER, activeforeground=TEXT)
        btn.bind("<Enter>", lambda _: btn.config(bg=BTN_HOVER))
        btn.bind("<Leave>", lambda _: btn.config(bg=BTN_BG))
        return btn

    def _section_row(self, parent):
        """Styled horizontal controls strip."""
        Frame(parent, bg=BORDER, height=1).pack(fill=X)
        row = Frame(parent, bg=PANEL)
        row.pack(fill=X)
        inner = Frame(row, bg=PANEL)
        inner.pack(fill=X, padx=15, pady=10)
        return inner

    def _make_treeview(self, parent, columns):
        """Treeview with vertical + horizontal scrollbars and row striping."""
        container = Frame(parent, bg=BG)
        container.pack(fill=BOTH, expand=True, padx=10, pady=(4, 10))

        vsb = ttk.Scrollbar(container, orient="vertical")
        hsb = ttk.Scrollbar(container, orient="horizontal")
        tree = ttk.Treeview(container, columns=columns, show="headings",
                            yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)

        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        tree.pack(fill=BOTH, expand=True)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150, minwidth=60, stretch=True)

        tree.tag_configure("odd",  background="#12171f")
        tree.tag_configure("even", background=PANEL)
        return tree

    def _show_private_browsing_warning(self, parent, indicators):
        """
        Displays an amber warning banner listing the artefact-pattern indicators
        that suggest private/incognito browsing. The banner includes a forensic
        caveat that this is inferential, not conclusive.
        """
        WARN_BG     = "#1f1a0e"
        WARN_BORDER = "#d29922"
        WARN_TEXT   = "#e3b341"
        WARN_NOTE   = "#7a6528"

        banner = Frame(parent, bg=WARN_BG, highlightbackground=WARN_BORDER,
                       highlightthickness=1)
        banner.pack(fill=X, padx=10, pady=(10, 0))

        hdr = Frame(banner, bg=WARN_BG)
        hdr.pack(fill=X, padx=14, pady=(10, 4))
        Label(hdr,
              text="[!]  POTENTIAL PRIVATE / INCOGNITO BROWSING DETECTED",
              font=("Segoe UI", 10, "bold"), bg=WARN_BG, fg=WARN_TEXT
              ).pack(side=LEFT)

        for indicator in indicators:
            Label(banner, text=f"      •  {indicator}",
                  font=FONT_SUB, bg=WARN_BG, fg=WARN_TEXT,
                  anchor=W, wraplength=900, justify=LEFT
                  ).pack(fill=X, padx=14, pady=1)

        Frame(banner, bg=WARN_BORDER, height=1).pack(fill=X, padx=14, pady=(8, 0))
        Label(banner,
              text="Forensic note:  Private browsing cannot be confirmed solely from "
                   "disk artefacts. The indicators above identify inconsistencies "
                   "characteristic of private sessions but cannot be treated as "
                   "definitive proof. Corroborate with RAM analysis, DNS cache, "
                   "or network logs where possible.",
              font=("Segoe UI", 8), bg=WARN_BG, fg=WARN_NOTE,
              wraplength=900, justify=LEFT, anchor=W
              ).pack(fill=X, padx=14, pady=(4, 10))

    def set_status(self, text):
        self.status_var.set(text)
        self.tk.update_idletasks()

    # ── Feature: View artefacts folder ───────────────────────────────────────

    def view_artefacts_folder(self):
        folder = filedialog.askdirectory(title="Select Extracted Artefacts Folder")
        if not folder:
            return
        self.set_status(f"Loading artefacts from: {folder}")

        user_browser_map = {}
        try:
            usernames = [d for d in os.listdir(folder)
                         if os.path.isdir(os.path.join(folder, d))]
        except Exception:
            usernames = []

        for username in usernames:
            user_path = os.path.join(folder, username)
            browser_map = {}
            for root, dirs, files in os.walk(user_path):
                # Extracted output is structured as username/BrowserName/...
                # so the first component below user_path is always the browser name.
                rel = os.path.relpath(root, user_path)
                browser_dir = rel.split(os.sep)[0]
                if browser_dir == '.':
                    continue
                for file in files:
                    lower_file = file.lower()
                    if lower_file in ("history", "places.sqlite"):
                        browser_map[browser_dir] = os.path.join(root, file)
            if browser_map:
                user_browser_map[username] = browser_map

        self.clear_artefact_frame()
        if not user_browser_map:
            wrap = Frame(self.artefact_frame, bg=BG)
            wrap.pack(expand=True)
            Label(wrap, text="No browser history databases found in the selected folder.",
                  font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack(pady=30)
            self.set_status("No browser history found.")
            return

        self.set_status(f"Found {len(user_browser_map)} user(s) with browser history.")
        self.show_user_dropdown(user_browser_map)

    def show_user_dropdown(self, user_browser_map):
        self.clear_artefact_frame()

        # Panel header strip
        hdr = Frame(self.artefact_frame, bg=PANEL, height=40)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(hdr, text="Browser Artefact Viewer",
              font=FONT_HEAD, bg=PANEL, fg=TEXT).pack(side=LEFT, padx=15, pady=10)

        # User selector row
        ctrl = self._section_row(self.artefact_frame)
        Label(ctrl, text="User:", font=FONT_SUB, bg=PANEL, fg=TEXT_DIM
              ).pack(side=LEFT, padx=(0, 6))
        user_names = list(user_browser_map.keys())
        user_var = StringVar(value=user_names[0])
        user_cb = ttk.Combobox(ctrl, textvariable=user_var, values=user_names,
                               state="readonly", width=28)
        user_cb.pack(side=LEFT)

        browser_table_frame = Frame(self.artefact_frame, bg=BG)
        browser_table_frame.pack(fill=BOTH, expand=True)

        def show_selected_user(*args):
            for w in browser_table_frame.winfo_children():
                w.destroy()
            self.show_browser_dropdown(user_browser_map[user_var.get()], browser_table_frame)
            self.set_status(f"Viewing user: {user_var.get()}")

        user_cb.bind("<<ComboboxSelected>>", show_selected_user)
        show_selected_user()

    def show_browser_dropdown(self, browser_map, parent_frame):
        ctrl = self._section_row(parent_frame)
        Label(ctrl, text="Browser:", font=FONT_SUB, bg=PANEL, fg=TEXT_DIM
              ).pack(side=LEFT, padx=(0, 6))
        browser_names = list(browser_map.keys())
        browser_var = StringVar(value=browser_names[0])
        browser_cb = ttk.Combobox(ctrl, textvariable=browser_var, values=browser_names,
                                  state="readonly", width=22)
        browser_cb.pack(side=LEFT)

        db_view_frame = Frame(parent_frame, bg=BG)
        db_view_frame.pack(fill=BOTH, expand=True)

        def show_selected_browser(*args):
            for w in db_view_frame.winfo_children():
                w.destroy()
            browser_name = browser_var.get()
            db_path = browser_map[browser_name]
            flagged, indicators = check_private_browsing_indicators(db_path, browser_name)
            if flagged:
                self._show_private_browsing_warning(db_view_frame, indicators)
            self.show_database_tables(db_path, db_view_frame)
            self.set_status(f"Browser: {browser_name}")

        browser_cb.bind("<<ComboboxSelected>>", show_selected_browser)
        show_selected_browser()

    def show_database_tables(self, db_path, parent_frame):
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            conn.close()
        except Exception as e:
            Label(parent_frame, text=f"Could not read database tables: {e}",
                  font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack(pady=20)
            return
        if not tables:
            Label(parent_frame, text="No tables found in database.",
                  font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack(pady=20)
            return

        ctrl = self._section_row(parent_frame)
        Label(ctrl, text="Table:", font=FONT_SUB, bg=PANEL, fg=TEXT_DIM
              ).pack(side=LEFT, padx=(0, 6))
        table_var = StringVar(value=tables[0])
        table_cb = ttk.Combobox(ctrl, textvariable=table_var, values=tables,
                                state="readonly", width=32)
        table_cb.pack(side=LEFT)

        table_view_frame = Frame(parent_frame, bg=BG)
        table_view_frame.pack(fill=BOTH, expand=True)

        def show_table(table_name):
            for w in table_view_frame.winfo_children():
                w.destroy()
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cur.fetchall()]
                if not columns:
                    Label(table_view_frame, text="No columns found.",
                          font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack(pady=20)
                    return
                tree = self._make_treeview(table_view_frame, columns)
                cur.execute(f"SELECT * FROM {table_name} LIMIT 100")
                for i, row in enumerate(cur.fetchall()):
                    tree.insert("", END, values=row,
                                tags=("odd" if i % 2 else "even",))
                conn.close()
                self.set_status(f"Table '{table_name}'  —  showing up to 100 rows")
            except Exception as e:
                Label(table_view_frame, text=f"Could not read table: {e}",
                      font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack(pady=20)

        table_cb.bind("<<ComboboxSelected>>", lambda _: show_table(table_var.get()))
        show_table(tables[0])

    def view_history_database(self, db_path):
        import sqlite3
        self.clear_artefact_frame()
        Label(self.artefact_frame,
              text=f"Database: {os.path.basename(db_path)}",
              font=FONT_HEAD, bg=BG, fg=TEXT).pack(padx=15, pady=10, anchor=W)

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            conn.close()
        except Exception as e:
            Label(self.artefact_frame, text=f"Could not read database tables: {e}",
                  font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack()
            return
        if not tables:
            Label(self.artefact_frame, text="No tables found in database.",
                  font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack()
            return

        ctrl = Frame(self.artefact_frame, bg=PANEL)
        ctrl.pack(fill=X, padx=0)
        Frame(ctrl, bg=BORDER, height=1).pack(fill=X)
        inner = Frame(ctrl, bg=PANEL)
        inner.pack(fill=X, padx=15, pady=10)
        Label(inner, text="Table:", font=FONT_SUB, bg=PANEL, fg=TEXT_DIM
              ).pack(side=LEFT, padx=(0, 6))
        table_var = StringVar(value=tables[0])
        table_cb = ttk.Combobox(inner, textvariable=table_var, values=tables,
                                state="readonly", width=32)
        table_cb.pack(side=LEFT)

        table_view_frame = Frame(self.artefact_frame, bg=BG)
        table_view_frame.pack(fill=BOTH, expand=True)

        def show_table(table_name):
            for w in table_view_frame.winfo_children():
                w.destroy()
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cur.fetchall()]
                if not columns:
                    Label(table_view_frame, text="No columns found.",
                          font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack()
                    return
                tree = self._make_treeview(table_view_frame, columns)
                cur.execute(f"SELECT * FROM {table_name} LIMIT 100")
                for i, row in enumerate(cur.fetchall()):
                    tree.insert("", END, values=row,
                                tags=("odd" if i % 2 else "even",))
                conn.close()
            except Exception as e:
                Label(table_view_frame, text=f"Could not read table: {e}",
                      font=FONT_MAIN, bg=BG, fg=TEXT_DIM).pack()

        table_cb.bind("<<ComboboxSelected>>", lambda _: show_table(table_var.get()))
        show_table(tables[0])

    # ── Utility ───────────────────────────────────────────────────────────────

    def clear_artefact_frame(self):
        for widget in self.artefact_frame.winfo_children():
            widget.destroy()

    # ── Feature: Mount & extract ──────────────────────────────────────────────

    def store_drives_and_mount(self):
        self.set_status("Storing drive list and launching Arsenal Image Mounter...")
        self.drives_before_mount = list_all_drives()
        mount_e01_arsenal(self)
        time.sleep(10)
        self.extract_artefacts_mounted_gui(lambda: unmount_arsenal(self))

    def extract_artefacts_mounted_gui(self, on_complete=None):
        drives_before = getattr(self, 'drives_before_mount', None)
        if drives_before is None:
            messagebox.showinfo("Info", "Please use the 'Mount E01' button before extracting artefacts.")
            return
        messagebox.showinfo("Mount Image",
            "If you haven't already, mount your E01 image now using Arsenal Image Mounter, then click OK.")
        drives_after = list_all_drives()
        new_drives = drives_after - drives_before
        if not new_drives:
            messagebox.showerror("No New Drive Detected",
                "No new drive was detected. Please ensure the image is mounted.")
            return

        user_folders = ["Users", "Documents", "Users\Public", "Users\Default"]
        drive_options = []
        for drive in sorted(new_drives):
            found_user_data = any(
                os.path.exists(os.path.join(drive, f)) for f in user_folders)
            drive_options.append((drive, found_user_data))

        drives_with_user_data = [d for d, found in drive_options if found]
        if drives_with_user_data:
            selected_drive = drives_with_user_data[0]
        else:
            selected_drive = drive_options[0][0]
            if not messagebox.askyesno("Drive Check",
                    f"No user folders detected on any new drive. Continue with {selected_drive}?"):
                return

        found_user_data = any(
            os.path.exists(os.path.join(selected_drive, f)) for f in user_folders)
        if not found_user_data:
            if not messagebox.askyesno("Drive Check",
                    f"The selected drive ({selected_drive}) does not appear to contain typical "
                    f"user folders. Continue anyway?"):
                return

        output_dir = filedialog.askdirectory(title="Select Output Directory for Artefacts")
        if not output_dir:
            return

        import datetime, threading
        session_folder = os.path.join(
            output_dir,
            f"artefacts_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(session_folder, exist_ok=True)

        # ── Styled progress dialog ────────────────────────────────────────────
        progress = Toplevel(self.tk)
        progress.title("Extracting Artefacts")
        progress.configure(bg=BG)
        progress.resizable(False, False)
        progress.grab_set()
        pw, ph = 480, 160
        px = self.tk.winfo_x() + (1000 - pw) // 2
        py = self.tk.winfo_y() + (700  - ph) // 2
        progress.geometry(f"{pw}x{ph}+{px}+{py}")

        Frame(progress, bg=ACCENT, height=3).pack(fill=X)
        Label(progress, text="Extracting Browser Artefacts",
              font=FONT_HEAD, bg=BG, fg=TEXT).pack(pady=(18, 4))
        Label(progress, text="Please wait while databases are being copied...",
              font=FONT_SUB, bg=BG, fg=TEXT_DIM).pack()
        pb = ttk.Progressbar(progress, orient="horizontal", length=420, mode="determinate")
        pb.pack(padx=30, pady=16)
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
                artefacts, failed = extract_browser_artefacts_from_mounted(
                    selected_drive, session_folder, progress_callback, fail_log_path)
            except Exception as e:
                artefacts, failed = [], 0
                with open(fail_log_path, 'a', encoding='utf-8') as flog:
                    flog.write(f"Critical error: {e}\n")
            progress.destroy()
            if artefacts:
                msg = (f"Found and copied {len(artefacts)} artefact(s).\n"
                       f"Failed to copy: {failed}\nSee: {session_folder}")
                if failed:
                    msg += "\nSee failed_copies.txt for details."
                self.tk.after(0, lambda: messagebox.showinfo("Extraction Complete", msg))
                self.tk.after(0, lambda: self.set_status(
                    f"Extraction complete — {len(artefacts)} artefact(s) saved."))
            else:
                self.tk.after(0, lambda: messagebox.showinfo(
                    "No Artefacts Found",
                    "No browser artefacts were found in the mounted drive."))
                self.tk.after(0, lambda: self.set_status("No artefacts found."))
            if on_complete:
                self.tk.after(0, on_complete)

        threading.Thread(target=do_extraction, daemon=True).start()

    # ── Window controls ───────────────────────────────────────────────────────

    def toggle_fullscreen(self, event=None):
        self.state = not self.state
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
