"""
Browser artefact extractor.

Walks a mounted disk image, identifies files that match known browser-artefact
filenames inside per-user browser profile folders, and copies them out into a
structured output directory grouped as <output>/<user>/<browser>/<...>.

Includes Windows long-path handling (\\?\ extended-length prefix + per-component
truncation with MD5 suffix) so artefacts buried under deep nested paths still
extract successfully.
"""

import os
import csv
import shutil
import hashlib
from datetime import datetime

# ── Artefact identification patterns ─────────────────────────────────────────
# Filenames to look for during the walk (case-insensitive substring match)
BROWSER_PATTERNS = [
    'History', 'Cookies', 'Login Data', 'Web Data', 'places.sqlite', 'favicons', 'Bookmarks',
    'Visited Links', 'Current Session', 'Last Session', 'Session Storage', 'Local Storage',
    'IndexedDB', 'Cache', 'Cache2', 'Network Action Predictor', 'Top Sites', 'Shortcuts',
    'Preferences', 'Secure Preferences', 'Extension Cookies', 'Media History', 'QuotaManager',
    'Service Worker', 'Sync Data', 'Sync Extension Settings', 'Sync Preferences',
    'Sync Secure Preferences', 'Sync Web Data', 'Tabloids', 'Tabs', 'Top Sites',
    'Web Data', 'WebCacheV01.dat', 'WebCacheV24.dat', 'WebCacheV01.tmp',
    'WebCacheV24.tmp', 'WebCacheV01.bak', 'WebCacheV24.bak',
]

# Folder fragments expected to appear somewhere in the path of a browser profile
BROWSER_DIRS = [
    'Chrome', 'Google/Chrome', 'Edge', 'Microsoft/Edge', 'Firefox', 'Mozilla/Firefox',
    'Opera', 'Brave', 'Vivaldi', 'Chromium', 'Safari', 'AppData/Local/Google/Chrome',
    'AppData/Local/Microsoft/Edge', 'AppData/Roaming/Mozilla/Firefox',
]

def _win_long(path):
    """
    Prefix an absolute path with \\?\ so Windows skips the 260-char MAX_PATH
    limit and allows paths up to 32,767 characters.  No-op on non-Windows.
    """
    if os.name != 'nt':
        return path
    path = os.path.abspath(path)
    if not path.startswith('\\\\?\\'):
        path = '\\\\?\\' + path
    return path


def _safe_dest(output_dir, user, browser, rel_path_after_browser):
    """
    Build a destination path.  If any single path component exceeds 200 chars
    (well under NTFS's 255-char per-component limit) it is truncated and given
    an 8-hex-char MD5 suffix so the name stays unique and recognisable.
    The \\?\ extended-length prefix is applied separately at copy time.
    """
    parts = rel_path_after_browser.split(os.sep)
    safe_parts = []
    for part in parts:
        if len(part) > 200:
            name, ext = os.path.splitext(part)
            h = hashlib.md5(part.encode('utf-8', errors='replace')).hexdigest()[:8]
            part = name[:190] + '_' + h + ext
        safe_parts.append(part)
    return os.path.join(output_dir, user, browser, *safe_parts)


# ── Hashing ─────────────────────────────────────────────────────────────────

# Standard column order for the manifest — matches the verification view
MANIFEST_COLUMNS = ["user", "browser", "rel_path", "size", "md5", "sha1", "sha256"]
MANIFEST_FILENAME = "manifest.csv"
# Sidecar storing the manifest's own MD5/SHA-1/SHA-256 — single point of trust:
# verifying this one digest set proves every per-file hash row is unchanged.
MANIFEST_HASH_FILENAME = "manifest.hashes"


def hash_file(path, chunk_size=1 << 20):
    """
    Stream a file once and return (md5, sha1, sha256) as lowercase hex digests.
    Returns (None, None, None) if the file cannot be opened.
    """
    md5    = hashlib.md5()
    sha1   = hashlib.sha1()
    sha256 = hashlib.sha256()
    try:
        with open(_win_long(path), "rb") as fh:
            for chunk in iter(lambda: fh.read(chunk_size), b""):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
    except Exception:
        return None, None, None
    return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()


def write_manifest(manifest_path, rows):
    """Write the per-extraction manifest.csv with a metadata header."""
    try:
        with open(manifest_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(f"# Forensic Artefact Manifest\n")
            fh.write(f"# Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
            fh.write(f"# Hash algorithms: MD5, SHA-1, SHA-256\n")
            writer = csv.writer(fh)
            writer.writerow(MANIFEST_COLUMNS)
            for row in rows:
                writer.writerow(row)
    except Exception as e:
        print(f"Failed to write manifest: {e}")


def write_manifest_hashes(manifest_path):
    """
    Hash manifest.csv itself and write a small sidecar file containing its
    MD5 / SHA-1 / SHA-256 digests.  The sidecar is the single point of trust
    used by the verifier — re-hashing manifest.csv and comparing once proves
    every per-file row inside it is unaltered.
    """
    md5, sha1, sha256 = hash_file(manifest_path)
    if not md5:
        return
    sidecar = os.path.join(os.path.dirname(manifest_path), MANIFEST_HASH_FILENAME)
    try:
        with open(sidecar, "w", encoding="utf-8") as fh:
            fh.write("# Hashes of manifest.csv at extraction time.\n")
            fh.write("# Re-hash manifest.csv and compare to verify integrity.\n")
            fh.write(f"generated_utc={datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n")
            fh.write(f"md5={md5}\n")
            fh.write(f"sha1={sha1}\n")
            fh.write(f"sha256={sha256}\n")
    except Exception as e:
        print(f"Failed to write manifest hash sidecar: {e}")


def read_manifest_hashes(sidecar_path):
    """Parse manifest.hashes and return {'md5', 'sha1', 'sha256', 'generated_utc'}."""
    out = {}
    try:
        with open(sidecar_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                out[key.strip()] = val.strip().lower() if key.strip() != "generated_utc" else val.strip()
    except Exception:
        return {}
    return out


# ── Artefact detection ──────────────────────────────────────────────────────

def is_browser_artefact(filename, path):
    """True if the file's name matches BROWSER_PATTERNS or its path lies under
    one of the known BROWSER_DIRS."""
    for pattern in BROWSER_PATTERNS:
        if pattern.lower() in filename.lower():
            return True
    for bdir in BROWSER_DIRS:
        if bdir.lower() in path.lower():
            return True
    return False


# ── Main extraction routine ─────────────────────────────────────────────────

def extract_browser_artefacts_from_mounted(mount_root, output_dir=None, progress_callback=None, fail_log_path=None):
    """
    Recursively search for browser artefacts in a mounted drive and optionally copy them to output_dir.
    Only extracts artefacts inside user folders and browser folders, and groups them as output_dir/<user>/<browser>/<...>.
    Returns: List of (src_path, user, browser, rel_path_after_browser) for each artefact.
    """
    artefacts = []
    failed = 0
    failed_files = []
    total = 0
    # Browser folder names (substring matching — handles variants like
    # "Opera Software/Opera Stable" or "Google/Chrome")
    browser_names = [
        'Chrome', 'Edge', 'Firefox', 'Opera', 'Brave', 'Vivaldi', 'Chromium', 'Safari',
        'Google/Chrome', 'Microsoft/Edge', 'Mozilla/Firefox',
    ]

    # Pass 1 — walk the mounted volume and collect every candidate so we can
    # show an accurate progress bar in pass 2.
    all_candidates = []
    for dirpath, dirnames, filenames in os.walk(mount_root):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, mount_root)
            parts = rel_path.split(os.sep)
            user = None
            browser = None
            # Path must look like Users/<name>/.../<browser>/...
            if len(parts) > 2 and parts[0].lower() == 'users':
                user = parts[1]
                for b in browser_names:
                    b_parts = b.split('/')
                    for i in range(2, len(parts) - len(b_parts) + 1):
                        if all(bp.lower() in parts[i+j].lower() for j, bp in enumerate(b_parts)):
                            browser = b_parts[-1]
                            rel_path_after_browser = os.sep.join(parts[i+len(b_parts):])
                            break
                    if browser:
                        break
            if user and browser and is_browser_artefact(filename, rel_path):
                all_candidates.append((full_path, user, browser, rel_path_after_browser))
    total = len(all_candidates)

    # Pass 2 — copy each candidate into <output_dir>/<user>/<browser>/<...>
    # and hash the source file so its digest can later be re-verified.
    manifest_rows = []
    for idx, (full_path, user, browser, rel_path_after_browser) in enumerate(all_candidates):
        artefacts.append((full_path, user, browser, rel_path_after_browser))
        if output_dir:
            try:
                dest_path = _safe_dest(output_dir, user, browser, rel_path_after_browser)
                os.makedirs(_win_long(os.path.dirname(dest_path)), exist_ok=True)
                shutil.copy2(_win_long(full_path), _win_long(dest_path))

                # Hash the *destination* file (what the user will later verify)
                md5, sha1, sha256 = hash_file(dest_path)
                try:
                    size = os.path.getsize(_win_long(dest_path))
                except Exception:
                    size = 0
                manifest_rows.append([
                    user, browser, rel_path_after_browser,
                    size, md5 or "", sha1 or "", sha256 or "",
                ])
            except Exception as e:
                print(f"Failed to copy {full_path}: {e}")
                failed += 1
                failed_files.append(f"{full_path} -> {dest_path} : {e}")
        if progress_callback:
            progress_callback(idx + 1, total)

    # Write the hash manifest alongside the extracted artefacts, then hash
    # the manifest itself so the whole extraction can be verified in one go.
    if output_dir and manifest_rows:
        manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
        write_manifest(manifest_path, manifest_rows)
        write_manifest_hashes(manifest_path)

    # Write a per-session log of files that failed to copy (long-path errors etc.)
    if fail_log_path and failed_files:
        try:
            with open(fail_log_path, 'w', encoding='utf-8') as flog:
                flog.write("Failed to copy the following files:\n")
                for line in failed_files:
                    flog.write(line + "\n")
        except Exception as e:
            print(f"Failed to write fail log: {e}")
    return artefacts, failed

## Now integrated with GUI; standalone execution block removed.