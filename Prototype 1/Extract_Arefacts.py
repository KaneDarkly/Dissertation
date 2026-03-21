
import os
import shutil

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
                        if [p.lower() for p in parts[i:i+len(b_parts)]] == [bp.lower() for bp in b_parts]:
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
                dest_path = os.path.join(output_dir, user, browser, rel_path_after_browser)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(full_path, dest_path)
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