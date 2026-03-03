# Source - https://stackoverflow.com/a/23840010
# Posted by Brōtsyorfuzthrāx, modified by community. See post 'Timeline' for change history
# Retrieved 2026-03-03, License - CC BY-SA 3.0

import sys
if sys.version_info[0] == 2:  # Just checking your Python version to import Tkinter properly.
    from Tkinter import *
else:
    from tkinter import *


class Fullscreen_Window:

    def __init__(self):
        self.tk = Tk()
        #self.tk.attributes('-fullscreen', True)  # This just maximizes it so we can see the window. It's nothing to do with fullscreen.
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

    def toggle_fullscreen(self, event=None):
        self.state = not self.state  # Just toggling the boolean
        self.tk.attributes("-fullscreen", self.state)
        return "break"

    def _center_window(self, width, height):
        """Position the root window in the centre of the screen.

        ``width`` and ``height`` are the intended dimensions of the window.  We
        compute the offsets based on the screen size and then update the
        geometry accordingly.  An explicit call to ``update_idletasks`` ensures
        that any pending geometry changes are processed before we query sizes.
        """
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

