
import os
import shutil
import hashlib

# List of browser artefact file patterns to look for
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

# Common browser data directories
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


def is_browser_artefact(filename, path):
    # Check if the file matches any known browser artefact pattern
    for pattern in BROWSER_PATTERNS:
        if pattern.lower() in filename.lower():
            return True
    for bdir in BROWSER_DIRS:
        if bdir.lower() in path.lower():
            return True
    return False


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
    browser_names = [
        'Chrome', 'Edge', 'Firefox', 'Opera', 'Brave', 'Vivaldi', 'Chromium', 'Safari',
        'Google/Chrome', 'Microsoft/Edge', 'Mozilla/Firefox',
    ]
    # First, count total artefacts for progress bar
    all_candidates = []
    for dirpath, dirnames, filenames in os.walk(mount_root):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, mount_root)
            parts = rel_path.split(os.sep)
            user = None
            browser = None
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
    for idx, (full_path, user, browser, rel_path_after_browser) in enumerate(all_candidates):
        artefacts.append((full_path, user, browser, rel_path_after_browser))
        if output_dir:
            try:
                dest_path = _safe_dest(output_dir, user, browser, rel_path_after_browser)
                os.makedirs(_win_long(os.path.dirname(dest_path)), exist_ok=True)
                shutil.copy2(_win_long(full_path), _win_long(dest_path))
            except Exception as e:
                print(f"Failed to copy {full_path}: {e}")
                failed += 1
                failed_files.append(f"{full_path} -> {dest_path} : {e}")
        if progress_callback:
            progress_callback(idx + 1, total)
    # Write failed files log if requested
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