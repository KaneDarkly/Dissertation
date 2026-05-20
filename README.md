# Forensic Artefact Extractor

A digital forensics tool for mounting E01 disk images, extracting browser
artefacts in a chain-of-custody-aware way, and inferring whether private /
incognito browsing took place on the source system.

Built as the artefact for a final year masters dissertation at Leeds Beckett University.

---

## What it does

1. **Mount** an `.E01` forensic disk image read-only via Arsenal Image Mounter.
2. **Extract** browser artefacts (history databases, bookmarks, downloads,
   cookies, cache metadata, etc.) for every user profile on the image into a
   structured `<output>/<user>/<browser>/` tree.
3. **Hash** every extracted file (MD5 / SHA-1 / SHA-256) into a `manifest.csv`
   and write a sidecar `manifest.hashes` so the entire extraction can be
   re-verified against tampering in a single click.
4. **View** the extracted browser SQLite databases inside the tool (table
   picker + 100-row preview).
5. **Detect** likely private-browsing sessions using three classes of signal:
   schema-level absence, cross-table inconsistency, and temporal-gap analysis
   (artefacts timestamped inside quiet windows in the visit timeline).
6. **Surface flagged artefacts** in a hierarchical viewer that shows the
   bookmarks and downloads that fell inside each suspected private window,
   alongside the gap duration and the lower-bound "active" private span.

---

## Requirements

- **Windows 10 / 11** (paths and Arsenal Image Mounter are Windows-specific).
- **Python 3.10+** (only standard library is required: `tkinter`, `sqlite3`,
  `hashlib`, `csv`, `subprocess`, `threading`).
- **[Arsenal Image Mounter](https://arsenalrecon.com/products/arsenal-image-mounter)**
  — the free CLI build is sufficient. The tool needs `aim_cli.exe` to mount
  E01 images; no specific install location is required (see *AIM discovery*
  below).
- **Administrator Privileges** (due to the requirment of temporarily mounting drives on your local machine)

No `pip install` step — everything used by the tool ships with Python's
standard library.

---

## Running

```powershell
cd "Prototype 1"
python Main.py
```

The application window will open. From the toolbar:

- **Select & Process File** — pick an `.E01` image, mount it, then select an
  output folder. The tool walks the mounted volume, copies every browser
  artefact it recognises into a timestamped session folder, and writes
  `manifest.csv` + `manifest.hashes` alongside.
- **View Artefacts** — point the tool at a previously extracted folder.
  Browse per-user / per-browser SQLite databases, see the private-browsing
  warning banner where applicable, click *Show Flagged Artefacts* for the
  hierarchical quiet-window view, or click *Verify Integrity* to confirm the
  manifest has not been altered since extraction.

---

## AIM (`aim_cli.exe`) discovery

The tool **does not** require Arsenal Image Mounter to be installed in any
specific folder. On first use it locates `aim_cli.exe` in this order:

1. Cached path from `Prototype 1/.aim_cli_path` (written automatically once
   AIM is found).
2. Anything on the system `PATH`.
3. A bounded recursive scan (depth 4) of:
   - `%ProgramFiles%`
   - `%ProgramFiles(x86)%`
   - `~\Downloads`, `~\Desktop`, `~\Documents`
4. A file-picker dialog asking the user to locate `aim_cli.exe` manually.

Whatever path is selected is cached so subsequent runs are instant.

---

## Output layout

A successful extraction produces:

```
<chosen_output>/artefacts_YYYYMMDD_HHMMSS/
├── manifest.csv          # per-file MD5 / SHA-1 / SHA-256 + size
├── manifest.hashes       # MD5 / SHA-1 / SHA-256 of manifest.csv itself
├── failed_copies.txt     # only present if any files failed to copy
└── <user>/
    └── <browser>/
        └── <profile-relative path>/
            └── <artefact files>
```

---

## Forensic integrity

- The E01 image is mounted **read-only** (`--readonly`) via Arsenal Image
  Mounter so the source evidence is never written back to.
- Browser SQLite databases are opened with `file:<path>?mode=ro` URI mode
  for the same reason — no journal files are created during analysis.
- Hashes are computed at extraction time against the **destination copy**
  (the file the user will later inspect). Re-running the integrity check
  re-hashes `manifest.csv` and compares against the sidecar — any change to
  any file's row inside the manifest changes the manifest's hash and trips
  the check, so one comparison covers the whole extraction.
- Long Windows paths are handled via the `\\?\` extended-length prefix so
  artefacts buried under deep nested profile directories still extract.

---

## Private browsing detection — what it claims and what it doesn't

Private mode is **not** something a browser writes a flag for, so it cannot
be confirmed solely from disk artefacts. The tool combines three indicator
classes to make a defensible *inference*:

| Signal | What it looks for |
| ------ | ----------------- |
| **Schema-level absence** | e.g. downloads recorded but URL/history table empty |
| **Cross-table inconsistency** | e.g. URL rows exist but visit timestamps don't |
| **Temporal-gap correlation** | bookmarks or downloads timestamped inside a quiet window of zero browsing activity |

The third signal is the strongest single indicator: bookmarks and downloaded
files survive private mode while history entries don't, so an artefact
landing in a multi-hour gap is hard to explain otherwise.

The warning banner shown in-tool always carries an explicit forensic caveat:
private browsing should be corroborated with RAM analysis, DNS cache, or
network logs where possible.

---

## Project layout

```
Prototype 1/
├── Main.py                     # entry point — boots the GUI
├── WindowSetup.py              # all Tkinter UI (toolbar, viewer, flagged
│                               #   view, integrity dialog, styling)
├── OpenFile.py                 # AIM mount/unmount wrappers + aim_cli.exe
│                               #   discovery
├── Extract_Arefacts.py         # browser-artefact walker, copier, hasher,
│                               #   manifest writer
├── private_browsing_check.py   # three-signal private-mode inference +
│                               #   structured flagged-artefact API
└── drive_utils.py              # diff-based "which drive just appeared?"
                                #   helper for post-mount detection
```

---

## Limitations

- Windows-only (path handling and AIM dependency).
- Mount step requires Arsenal Image Mounter installed and licensed for the
  user's intended purpose.
- The artefact viewer shows only the first 100 rows of each SQLite table;
  it's a triage view, not a full-database browser.
- Firefox download metadata isn't yet correlated against quiet windows
  (Firefox stores it outside `places.sqlite`); only Firefox bookmarks
  participate in temporal-gap analysis. Chromium-based browsers correlate
  both downloads and bookmarks.
- Private-mode detection produces *indicators*, not proof. See above.

---

## License & academic use

Submitted as the practical artefact for a Year 4 dissertation. Re-use for
research, teaching, or study is welcome; please cite the dissertation or
this repository if the tool informs published work.
