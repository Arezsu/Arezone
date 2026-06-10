from __future__ import annotations

import tkinter as tk
from tkinter import StringVar
from typing import Callable

from modules.theme import ps5_glow_button

PS5_BG = "#0a0a0c"
PS5_PANEL = "#141419"
PS5_ROW = "#1c1c24"
PS5_FOCUS_ALT = "#5ac8fa"
PS5_TEXT = "#f0f0f5"
PS5_MUTED = "#8b8b9a"
PS5_OK = "#2d9cdb"
PS5_DANGER = "#e8214a"
PS5_FONT = ("Segoe UI", 12, "bold")
PS5_FONT_BIG = ("Segoe UI", 15, "bold")
PS5_HINT = "Flechas + Enter o mouse  |  F1 pagar  |  F2 volver"


def ps5_button(
    parent,
    text: str,
    command: Callable[[], None],
    theme_name: str = "night",
    *,
    accent: bool = False,
    danger: bool = False,
    compact: bool = False,
) -> tk.Button:
    bg = PS5_OK if accent else None
    return ps5_glow_button(parent, text, command, theme_name, bg=bg, danger=danger, compact=compact)


def ps5_focus_row(
    parent,
    title: str,
    value_text: StringVar,
    *,
    label_font: tuple[str, int, str] | None = None,
    value_font: tuple[str, int, str] | None = None,
    row_pady: int = 1,
    inner_pad: int = 2,
) -> tuple[tk.Frame, tk.Label]:
    row = tk.Frame(parent, bg=PS5_ROW, highlightthickness=2, highlightbackground=PS5_ROW)
    row.pack(fill="x", pady=row_pady, padx=1)
    tk.Label(
        row,
        text=title,
        bg=PS5_ROW,
        fg=PS5_MUTED,
        font=label_font or PS5_FONT,
        anchor="w",
    ).pack(side="left", padx=10, pady=inner_pad)
    val = tk.Label(
        row,
        textvariable=value_text,
        bg=PS5_ROW,
        fg=PS5_TEXT,
        font=value_font or PS5_FONT_BIG,
        anchor="e",
    )
    val.pack(side="right", padx=10, pady=inner_pad)
    return row, val


def paint_ps5_row(row: tk.Frame, focused: bool) -> None:
    bg = "#1a3a52" if focused else PS5_ROW
    border = PS5_FOCUS_ALT if focused else PS5_ROW
    row.configure(bg=bg, highlightbackground=border, highlightcolor=border, highlightthickness=4 if focused else 2)
    for child in row.winfo_children():
        try:
            child.configure(bg=bg)
        except tk.TclError:
            pass


class Ps5FocusGroup:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.index = 0

    def focus(self, idx: int) -> None:
        self.index = idx % len(self.items)
        for i, item in enumerate(self.items):
            fn = item.get("paint")
            if fn:
                fn(i == self.index)

    def move(self, delta: int) -> None:
        self.focus(self.index + delta)

    def activate(self) -> None:
        act = self.items[self.index].get("activate")
        if act:
            act()
