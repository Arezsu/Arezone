from __future__ import annotations

import re
import tkinter as tk


def play_sound(conn, kind: str = "tap") -> None:
    """Audio feedback intentionally disabled for a quieter POS."""
    return


def fade_in_window(window: tk.Toplevel | tk.Tk, *, duration_ms: int = 180, steps: int = 9) -> None:
    """Window entrance with a soft slide-up and ease-out feel."""
    window.update_idletasks()
    try:
        geometry = window.geometry()
        match = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geometry)
        if match:
            width, height, x, y = map(int, match.groups())
            start_y = max(0, y + 14)
            window.geometry(f"{width}x{height}+{x}+{start_y}")
            window.attributes("-alpha", 0.0)
        else:
            window.attributes("-alpha", 0.0)
            start_y = None
            width = height = x = y = 0
    except tk.TclError:
        return

    interval = max(10, duration_ms // max(steps, 1))

    def _ease(progress: float) -> float:
        return 1 - (1 - progress) ** 3

    def _step(index: int) -> None:
        progress = min(1.0, index / steps)
        eased = _ease(progress)
        try:
            window.attributes("-alpha", eased)
            if match:
                current_y = round((start_y or y) - 14 * eased)
                window.geometry(f"{width}x{height}+{x}+{current_y}")
        except tk.TclError:
            return
        if index < steps:
            window.after(interval, lambda: _step(index + 1))

    window.after(1, lambda: _step(1))


def pop_in_window(
    window: tk.Toplevel | tk.Tk,
    *,
    duration_ms: int = 220,
    steps: int = 10,
    y_offset: int = 18,
) -> None:
    """Fade a window in while gently sliding it upward."""
    window.update_idletasks()
    try:
        geometry = window.geometry()
        match = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geometry)
        if not match:
            fade_in_window(window, duration_ms=duration_ms, steps=steps)
            return
        width, height, x, y = map(int, match.groups())
        start_y = max(0, y + y_offset)
        window.geometry(f"{width}x{height}+{x}+{start_y}")
        window.attributes("-alpha", 0.0)
    except tk.TclError:
        return

    interval = max(10, duration_ms // max(steps, 1))

    def _step(index: int) -> None:
        progress = min(1.0, index / steps)
        current_y = round(start_y - (y_offset * progress))
        try:
            window.attributes("-alpha", progress)
            window.geometry(f"{width}x{height}+{x}+{current_y}")
        except tk.TclError:
            return
        if index < steps:
            window.after(interval, lambda: _step(index + 1))

    window.after(1, lambda: _step(1))


def ask_secret(
    master,
    title: str,
    prompt: str,
    *,
    theme_name: str = "day",
    show: str = "*",
    initialvalue: str = "",
) -> str | None:
    from modules.theme import FONT_BIG, FONT_TITLE, THEMES, big_button, fit_window, themed_frame

    colors = THEMES.get(theme_name, THEMES["day"])
    result: dict[str, str | None] = {"value": None}

    dialog = tk.Toplevel(master)
    dialog.title(title)
    dialog.configure(bg=colors["bg"])
    dialog.transient(master)
    dialog.grab_set()
    fit_window(dialog, 620, 360, min_width=560, min_height=320)
    dialog.resizable(True, True)

    root = themed_frame(dialog, theme_name, panel=True, border=True)
    root.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
    dialog.columnconfigure(0, weight=1)
    dialog.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)

    tk.Label(root, text=title.upper(), bg=colors["panel"], fg=colors["text"], font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))
    tk.Label(root, text=prompt, bg=colors["panel"], fg=colors["muted"], font=FONT_BIG, wraplength=500, justify="left").grid(
        row=1,
        column=0,
        sticky="w",
        padx=18,
        pady=(0, 14),
    )

    entry_var = tk.StringVar(value=initialvalue)
    entry = tk.Entry(
        root,
        textvariable=entry_var,
        show=show,
        font=("Segoe UI", 22, "bold"),
        justify="center",
        bg=colors["input_bg"],
        fg=colors["input_text"],
        insertbackground=colors["input_text"],
    )
    entry.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18), ipady=10)
    entry.focus_set()

    buttons = themed_frame(root, theme_name, panel=True)
    buttons.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
    buttons.columnconfigure((0, 1), weight=1)

    def accept() -> None:
        result["value"] = entry_var.get()
        dialog.destroy()

    def cancel() -> None:
        dialog.destroy()

    big_button(buttons, "ACEPTAR", accept, theme_name).grid(row=0, column=0, sticky="ew", padx=6)
    big_button(buttons, "CANCELAR", cancel, theme_name, bg=colors["danger"], fg="#ffffff").grid(row=0, column=1, sticky="ew", padx=6)

    dialog.bind("<Return>", lambda _event: accept())
    dialog.bind("<Escape>", lambda _event: cancel())
    pop_in_window(dialog)
    dialog.wait_window()
    return result["value"]
