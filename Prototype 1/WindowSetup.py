from tkinter import *
from tkinter import filedialog, messagebox
from tkinter import ttk
import os
from OpenFile import mount_e01_arsenal, unmount_arsenal
from Extract_Arefacts import (
    extract_browser_artefacts_from_mounted,
    hash_file,
    read_manifest_hashes,
    MANIFEST_FILENAME,
    MANIFEST_HASH_FILENAME,
)
from drive_utils import list_all_drives
from private_browsing_check import (
    check_private_browsing_indicators,
    get_flagged_artefacts,
    format_duration,
)
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
        # Root window + global colour defaults for the Combobox dropdown list
        # (must be set before any Combobox is created)
        self.tk = Tk()
        self.tk.configure(bg=BG)
        self.tk.option_add("*TCombobox*Listbox.background",       PANEL)
        self.tk.option_add("*TCombobox*Listbox.foreground",       TEXT)
        self.tk.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.tk.option_add("*TCombobox*Listbox.selectForeground", BG)

        # Compatibility frame retained from the original prototype
        self.frame = Frame(self.tk, bg=BG)
        self.frame.pack()

        # Window-level keybindings + title + sizing
        self.state = False
        self.tk.bind("<F11>", self.toggle_fullscreen)
        self.tk.bind("<Escape>", self.end_fullscreen)
        self.tk.title("Forensic Artefact Extractor")
        width, height = 1000, 700
        self.tk.geometry(f"{width}x{height}")
        self._center_window(width, height)

        # Build the persistent UI scaffold (styles → header → toolbar → status)
        self._apply_styles()
        self._build_header()
        self._build_toolbar()
        self._build_status_bar()  # packed BOTTOM before the expanding content area

        # Main content region — every screen (welcome, viewer, flagged view) is
        # rendered into this frame after clear_artefact_frame() wipes it.
        Frame(self.tk, bg=BORDER, height=1).pack(fill=X)
        self.artefact_frame = Frame(self.tk, bg=BG)
        self.artefact_frame.pack(side=TOP, fill=BOTH, expand=True)

        self._show_welcome()

    # ── Style sheet ──────────────────────────────────────────────────────────

    def _apply_styles(self):
        # Centralised ttk style sheet — every Combobox, Treeview, Scrollbar
        # and Progressbar in the app inherits from these definitions.
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

        # Treeview body — fieldbackground set to BORDER so the gaps between
        # cells (rendered when borderwidth>0) show as visible 1px gridlines.
        style.configure("Treeview",
            background=PANEL, foreground=TEXT,
            fieldbackground=BORDER, rowheight=28, font=FONT_MAIN,
            bordercolor=BORDER, borderwidth=1, relief="solid")
        style.configure("Treeview.Heading",
            background=BTN_BG, foreground=ACCENT,
            relief="solid", borderwidth=1, bordercolor=BORDER,
            font=("Segoe UI", 9, "bold"))
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

    # ── Feature: Hash manifest verification ──────────────────────────────────

    def _verify_integrity(self, _user_browser_map):
        """
        Single-shot integrity check.  Re-hash manifest.csv and compare to the
        MD5 / SHA-1 / SHA-256 stored in manifest.hashes at extraction time.
        If any per-file row inside the manifest had been altered, the manifest's
        own hash would change — so one comparison covers the whole extraction.
        """
        folder = getattr(self, 'loaded_artefacts_folder', None)
        if not folder:
            messagebox.showerror("No Folder Loaded",
                "Open an extracted artefacts folder first using View Artefacts.")
            return

        manifest_path = os.path.join(folder, MANIFEST_FILENAME)
        sidecar_path  = os.path.join(folder, MANIFEST_HASH_FILENAME)

        if not os.path.isfile(manifest_path):
            messagebox.showerror("Manifest Missing",
                f"No {MANIFEST_FILENAME} found in:\n{folder}\n\n"
                "Manifests are written automatically for new extractions. "
                "Older folders extracted before this feature was added will not have one.")
            return
        if not os.path.isfile(sidecar_path):
            messagebox.showerror("Hash Sidecar Missing",
                f"No {MANIFEST_HASH_FILENAME} found in:\n{folder}\n\n"
                "Without it the manifest's expected digest is unknown.")
            return

        expected = read_manifest_hashes(sidecar_path)
        if not all(k in expected for k in ("md5", "sha1", "sha256")):
            messagebox.showerror("Sidecar Unreadable",
                f"{MANIFEST_HASH_FILENAME} could not be parsed.")
            return

        self.set_status("Verifying manifest integrity...")
        actual_md5, actual_sha1, actual_sha256 = hash_file(manifest_path)

        match_md5    = actual_md5    == expected["md5"]
        match_sha1   = actual_sha1   == expected["sha1"]
        match_sha256 = actual_sha256 == expected["sha256"]
        all_match    = match_md5 and match_sha1 and match_sha256

        self._show_integrity_dialog(
            manifest_path, sidecar_path, expected,
            (actual_md5, actual_sha1, actual_sha256),
            (match_md5, match_sha1, match_sha256), all_match,
        )

        self.set_status(
            "Integrity verified: manifest unchanged." if all_match
            else "Integrity check FAILED: manifest has been modified.")

    def _show_integrity_dialog(self, manifest_path, sidecar_path,
                               expected, actual, matches, all_match):
        """Modal dialog showing the manifest's expected vs computed digests."""
        actual_md5, actual_sha1, actual_sha256 = actual
        match_md5, match_sha1, match_sha256    = matches

        dlg = Toplevel(self.tk)
        dlg.title("Integrity Verification")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        w, h = 720, 360
        x = self.tk.winfo_x() + (self.tk.winfo_width()  - w) // 2
        y = self.tk.winfo_y() + (self.tk.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        # Top accent strip — green when verified, red when tampered
        verdict_color = "#56d364" if all_match else "#ff7b72"
        Frame(dlg, bg=verdict_color, height=4).pack(fill=X)

        # Verdict header
        Label(dlg,
              text=("INTEGRITY VERIFIED" if all_match
                    else "INTEGRITY CHECK FAILED"),
              font=("Segoe UI", 14, "bold"),
              bg=BG, fg=verdict_color
              ).pack(pady=(14, 2))
        Label(dlg,
              text=("All three manifest digests match: extraction unchanged."
                    if all_match
                    else "One or more digests do not match: manifest has been altered."),
              font=FONT_SUB, bg=BG, fg=TEXT_DIM
              ).pack(pady=(0, 10))

        # Per-algorithm digest rows (expected vs computed + per-row verdict)
        body = Frame(dlg, bg=BG)
        body.pack(fill=BOTH, expand=True, padx=20)

        def digest_row(label, exp, act, ok):
            row_color = "#56d364" if ok else "#ff7b72"
            row = Frame(body, bg=PANEL)
            row.pack(fill=X, pady=4, ipady=4)
            Label(row, text=label, font=("Consolas", 9, "bold"),
                  bg=PANEL, fg=ACCENT, width=8, anchor=W
                  ).pack(side=LEFT, padx=(8, 4))
            Label(row, text="OK" if ok else "FAIL",
                  font=("Segoe UI", 9, "bold"),
                  bg=PANEL, fg=row_color, width=6, anchor=W
                  ).pack(side=LEFT)
            digests = Frame(row, bg=PANEL)
            digests.pack(side=LEFT, fill=X, expand=True, padx=(4, 8))
            Label(digests, text=f"expected:  {exp}",
                  font=("Consolas", 8), bg=PANEL, fg=TEXT, anchor=W
                  ).pack(fill=X)
            Label(digests, text=f"computed:  {act or '—'}",
                  font=("Consolas", 8), bg=PANEL, fg=row_color, anchor=W
                  ).pack(fill=X)

        digest_row("MD5",     expected["md5"],    actual_md5,    match_md5)
        digest_row("SHA-1",   expected["sha1"],   actual_sha1,   match_sha1)
        digest_row("SHA-256", expected["sha256"], actual_sha256, match_sha256)

        # Footer with file paths + close button
        meta = Frame(dlg, bg=BG)
        meta.pack(fill=X, padx=20, pady=(8, 4))
        Label(meta, text=f"Manifest:  {manifest_path}",
              font=FONT_SUB, bg=BG, fg=TEXT_DIM, anchor=W
              ).pack(fill=X)
        Label(meta, text=f"Sidecar:   {sidecar_path}",
              font=FONT_SUB, bg=BG, fg=TEXT_DIM, anchor=W
              ).pack(fill=X)
        if expected.get("generated_utc"):
            Label(meta, text=f"Generated: {expected['generated_utc']} UTC",
                  font=FONT_SUB, bg=BG, fg=TEXT_DIM, anchor=W
                  ).pack(fill=X)

        self._make_btn(dlg, "Close", dlg.destroy
                       ).pack(side=BOTTOM, pady=(4, 14))

    # ── Feature: Flagged artefacts (suspected private browsing) ──────────────

    def _view_flagged_from_map(self, user_browser_map):
        """
        Run the temporal-gap analysis against the database files already
        loaded in the artefact viewer (user_browser_map is the same structure
        produced by view_artefacts_folder).  Replaces the artefact panel with
        the hierarchical flagged-artefacts tree.
        """
        self.set_status("Scanning loaded profiles for flagged artefacts...")

        # Run the gap-detection pass on every (user, browser) database
        flagged = {}
        for username, browsers in user_browser_map.items():
            for browser_name, db_path in browsers.items():
                gaps = get_flagged_artefacts(db_path, browser_name)
                if gaps:
                    flagged[(username, browser_name)] = gaps

        self.clear_artefact_frame()

        # Header strip with title + back-to-viewer button
        nav = Frame(self.artefact_frame, bg=PANEL, height=40)
        nav.pack(fill=X)
        nav.pack_propagate(False)
        Label(nav, text="Flagged Artefacts  —  Suspected Private Browsing",
              font=FONT_HEAD, bg=PANEL, fg=TEXT
              ).pack(side=LEFT, padx=15, pady=10)
        self._make_btn(nav, "← Back to Artefact Viewer",
                       lambda: self.show_user_dropdown(user_browser_map)
                       ).pack(side=RIGHT, padx=15, pady=6)

        if not flagged:
            wrap = Frame(self.artefact_frame, bg=BG)
            wrap.pack(expand=True)
            Label(wrap,
                  text="No flagged artefacts found.\n"
                       "No bookmarks or downloads were detected inside quiet windows "
                       "across the loaded profiles.",
                  font=FONT_MAIN, bg=BG, fg=TEXT_DIM, justify=LEFT
                  ).pack(pady=30)
            self.set_status("No flagged artefacts found in loaded profiles.")
            return

        self._build_flagged_view(flagged)

        total_artefacts = sum(
            sum(len(g['downloads']) + len(g['bookmarks']) for g in gaps)
            for gaps in flagged.values())
        total_windows = sum(len(gaps) for gaps in flagged.values())
        self.set_status(
            f"{total_artefacts} flagged artefact(s) across "
            f"{total_windows} quiet window(s) in {len(flagged)} profile(s).")

    def _build_flagged_view(self, flagged_per_profile):
        """Render the three-level flagged tree: profile → quiet window → artefact."""
        # Caption sub-strip (the nav strip above already shows the title)
        sub = Frame(self.artefact_frame, bg=BG)
        sub.pack(fill=X, padx=10, pady=(8, 0))
        Label(sub,
              text="Bookmarks & downloads timestamped inside quiet history windows. "
                   "“Active” = first → last artefact within the window (confirmed private-mode duration).",
              font=FONT_SUB, bg=BG, fg=TEXT_DIM, justify=LEFT, anchor=W,
              wraplength=1100
              ).pack(fill=X)

        # Hierarchical Treeview with H + V scrollbars
        container = Frame(self.artefact_frame, bg=BG)
        container.pack(fill=BOTH, expand=True, padx=10, pady=10)

        vsb = ttk.Scrollbar(container, orient="vertical")
        hsb = ttk.Scrollbar(container, orient="horizontal")
        tree = ttk.Treeview(
            container,
            columns=("when", "title", "url"),
            show=("tree", "headings"),
            yscrollcommand=vsb.set, xscrollcommand=hsb.set,
        )
        tree.heading("#0",    text="Profile  /  Window  /  Artefact")
        tree.heading("when",  text="Timestamp (UTC)")
        tree.heading("title", text="Title  /  File")
        tree.heading("url",   text="URL")

        tree.column("#0",    width=620, minwidth=320, stretch=True)
        tree.column("when",  width=170, minwidth=140, stretch=False)
        tree.column("title", width=420, minwidth=180, stretch=True)
        tree.column("url",   width=700, minwidth=200, stretch=True)

        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)
        vsb.pack(side=RIGHT, fill=Y)
        hsb.pack(side=BOTTOM, fill=X)
        tree.pack(fill=BOTH, expand=True)

        # Per-row colouring based on row type (profile / window / artefact)
        tree.tag_configure("profile",
                           background=PANEL, foreground=ACCENT,
                           font=("Segoe UI", 10, "bold"))
        tree.tag_configure("window",
                           background="#1f1a0e", foreground="#e3b341",
                           font=("Segoe UI", 9, "bold"))
        tree.tag_configure("download", background=PANEL, foreground=TEXT)
        tree.tag_configure("bookmark", background="#12171f", foreground=TEXT)

        # Populate the tree: one profile node per (user, browser),
        # one window node per detected gap, one leaf per flagged artefact
        for (user, browser), gaps in sorted(flagged_per_profile.items()):
            n_dl = sum(len(g['downloads']) for g in gaps)
            n_bm = sum(len(g['bookmarks']) for g in gaps)
            profile_label = (f"{user}  /  {browser}    "
                             f"—  {len(gaps)} window(s),  "
                             f"{n_dl} download(s),  {n_bm} bookmark(s)")
            profile_id = tree.insert("", END,
                                     text=profile_label,
                                     tags=("profile",), open=True)

            for gap in gaps:
                gap_dur = format_duration(gap['end'] - gap['start'])
                all_times = ([d['time'] for d in gap['downloads']] +
                             [b['time'] for b in gap['bookmarks']])
                if len(all_times) >= 2:
                    a_start, a_end = min(all_times), max(all_times)
                    active_str = (f"active {format_duration(a_end - a_start)}  "
                                  f"({a_start.strftime('%H:%M')}→{a_end.strftime('%H:%M')})")
                else:
                    active_str = "single artefact"
                window_label = (f"Quiet window   "
                                f"{gap['start'].strftime('%Y-%m-%d %H:%M')}  →  "
                                f"{gap['end'].strftime('%Y-%m-%d %H:%M')}     "
                                f"(gap {gap_dur}  •  {active_str})")
                window_id = tree.insert(profile_id, END,
                                        text=window_label,
                                        tags=("window",), open=True)

                for dl in gap['downloads']:
                    tree.insert(window_id, END,
                                text="    [DOWNLOAD]",
                                values=(
                                    dl['time'].strftime("%Y-%m-%d %H:%M:%S"),
                                    dl['file'],
                                    dl['url'],
                                ),
                                tags=("download",))
                for bm in gap['bookmarks']:
                    tree.insert(window_id, END,
                                text="    [BOOKMARK]",
                                values=(
                                    bm['time'].strftime("%Y-%m-%d %H:%M:%S"),
                                    bm['title'],
                                    bm['url'],
                                ),
                                tags=("bookmark",))

    # ── Feature: View artefacts folder ───────────────────────────────────────

    def view_artefacts_folder(self):
        """Entry point for "View Artefacts": pick a previously extracted folder
        and build a {user → {browser → history-db-path}} map for the viewer."""
        folder = filedialog.askdirectory(title="Select Extracted Artefacts Folder")
        if not folder:
            return
        # Remember the loaded folder so the integrity-verifier can locate manifest.csv
        self.loaded_artefacts_folder = folder
        self.set_status(f"Loading artefacts from: {folder}")

        # Top-level entries inside the extracted folder are user names
        user_browser_map = {}
        try:
            usernames = [d for d in os.listdir(folder)
                         if os.path.isdir(os.path.join(folder, d))]
        except Exception:
            usernames = []

        # For each user, locate the History DB inside each browser sub-folder.
        # Layout produced by Extract_Arefacts.py is: <folder>/<user>/<browser>/...
        for username in usernames:
            user_path = os.path.join(folder, username)
            browser_map = {}
            for root, dirs, files in os.walk(user_path):
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
        self._make_btn(hdr, "Show Flagged Artefacts",
                       lambda: self._view_flagged_from_map(user_browser_map)
                       ).pack(side=RIGHT, padx=15, pady=6)
        self._make_btn(hdr, "Verify Integrity",
                       lambda: self._verify_integrity(user_browser_map)
                       ).pack(side=RIGHT, padx=(15, 0), pady=6)

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
        # Browser selector + the per-browser content area
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
            # Re-render on browser change: warning banner (if flagged) + tables
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
        """Build a table-picker + 100-row preview Treeview for the chosen DB."""
        import sqlite3
        # List every table in the SQLite database
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
        """Snapshot the drive list, launch Arsenal Image Mounter, then run
        extraction once the new mounted drive appears."""
        self.set_status("Storing drive list and launching Arsenal Image Mounter...")
        self.drives_before_mount = list_all_drives()
        mount_e01_arsenal(self)
        time.sleep(10)  # give AIM time to actually attach the volume
        self.extract_artefacts_mounted_gui(lambda: unmount_arsenal(self))

    def extract_artefacts_mounted_gui(self, on_complete=None):
        """Identify the newly mounted drive, ask the user where to save, and
        run the extraction in a background thread with a progress dialog."""
        # Sanity check: we need a pre-mount snapshot to diff against
        drives_before = getattr(self, 'drives_before_mount', None)
        if drives_before is None:
            messagebox.showinfo("Info", "Please use the 'Mount E01' button before extracting artefacts.")
            return
        messagebox.showinfo("Mount Image",
            "If you haven't already, mount your E01 image now using Arsenal Image Mounter, then click OK.")

        # Diff against the pre-mount snapshot to find the new volume
        drives_after = list_all_drives()
        new_drives = drives_after - drives_before
        if not new_drives:
            messagebox.showerror("No New Drive Detected",
                "No new drive was detected. Please ensure the image is mounted.")
            return

        # Prefer a new drive that actually contains user-data folders
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

        # Create a timestamped session folder so repeated extractions don't collide
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
