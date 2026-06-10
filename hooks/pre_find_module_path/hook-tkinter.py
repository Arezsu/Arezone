# Force tkinter discovery even when PyInstaller's Tcl/Tk probe reports a false negative.
# We manually package Tcl/Tk data in build scripts, so excluding tkinter here is incorrect.

def pre_find_module_path(hook_api):
    return
