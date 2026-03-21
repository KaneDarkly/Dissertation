import os
import string

def get_newly_mounted_drive(drives_before, drives_after):
    """
    Returns the drive letter of a newly mounted drive by comparing the list of drives before and after mounting.
    drives_before: set of drive letters before mounting
    drives_after: set of drive letters after mounting
    Returns: drive letter (e.g., 'Z:\\') or None
    """
    new_drives = drives_after - drives_before
    if new_drives:
        return list(new_drives)[0]  # Return the first new drive found
    return None

def list_all_drives():
    """Returns a set of all available drive letters (e.g., {'C:\\', 'D:\\', ...})"""
    drives = set()
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.add(drive)
    return drives
