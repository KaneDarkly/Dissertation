from tkinter import *
from tkinter import filedialog

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
        taskbar = Frame(self.tk, bg='lightgrey', height=30)
        taskbar.pack(side=TOP, fill=X)

        # Add some buttons to the taskbar
        btn1 = Button(taskbar, text='Open File', command=self.open_file)
        btn1.pack(side=LEFT, padx=5, pady=5)

        btn2 = Button(taskbar, text='Button 2')
        btn2.pack(side=LEFT, padx=5, pady=5)

        btn3 = Button(taskbar, text='Button 3')
        btn3.pack(side=LEFT, padx=5, pady=5)

    def open_file(self):
        self.filename = filedialog.askopenfilename(initialdir="/", title="Select a File", filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
        my_label = Label(self.tk, text=self.filename)
        my_label.pack()

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
