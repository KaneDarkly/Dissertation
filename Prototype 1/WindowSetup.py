from tkinter import *

def Create_Window():
    window = Tk() #initialisation of window instance
    window.geometry("400x800") #sets the size of the window
    window.title("Prototype 1") #sets the title of the window

    icon = PhotoImage(file="Logo.png")
    window.iconphoto(True, icon) #sets the icon of the window

    window.mainloop() #Displays the window