from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from modules.security import get_setting, hash_secret, set_setting, verify_secret
from modules.theme import FONT_BIG, FONT_TITLE, ThemeMixin, app_logo_label, big_button, themed_frame
from modules.ui_fx import ask_secret


class LoginFrame(ttk.Frame, ThemeMixin):
    def __init__(self, master, conn, on_success: Callable[[], None]) -> None:
        self.theme_name = get_setting(conn, "theme", "day") or "day"
        super().__init__(master)
        self.conn = conn
        self.on_success = on_success
        self.pin_var = tk.StringVar()
        self.apply_common_styles()
        self._build()

    def _build(self) -> None:
        c = self.colors
        self.configure(style="Senior.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        card = themed_frame(self, self.theme_name, panel=True, border=True)
        card.grid(row=0, column=0, sticky="nsew", padx=48, pady=32)
        card.columnconfigure((0, 1, 2), weight=1)
        card.rowconfigure(7, weight=1)

        branding = tk.Frame(card, bg=c["panel"])
        branding.grid(row=0, column=0, columnspan=3, sticky="ew", padx=42, pady=(28, 8))
        branding.columnconfigure(1, weight=1)
        app_logo_label(branding, self.theme_name, size=46, panel=True).grid(row=0, column=0, sticky="w")
        tk.Label(branding, text="AREZONE", bg=c["panel"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=1, sticky="w", padx=(12, 0))
        tk.Label(branding, text=self._version_label(), bg=c["panel"], fg=c["muted"], font=("Segoe UI", 12)).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(2, 0))
        tk.Label(card, text="Ingrese su clave", bg=c["panel"], fg=c["muted"], font=FONT_BIG).grid(row=1, column=0, columnspan=3, pady=(0, 18))

        entry = tk.Entry(
            card,
            textvariable=self.pin_var,
            show="*",
            justify="center",
            font=("Segoe UI", 34, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
        )
        entry.grid(row=2, column=0, columnspan=3, sticky="ew", padx=72, pady=(0, 22), ipady=16)
        entry.configure(width=18)
        entry.focus_set()
        entry.bind("<Return>", lambda _event: self.try_login())

        keys = [
            ("1", 3, 0), ("2", 3, 1), ("3", 3, 2),
            ("4", 4, 0), ("5", 4, 1), ("6", 4, 2),
            ("7", 5, 0), ("8", 5, 1), ("9", 5, 2),
            ("BORRAR", 6, 0), ("0", 6, 1), ("ENTRAR", 6, 2),
        ]
        for text, row, col in keys:
            command = self.try_login if text == "ENTRAR" else self.clear_pin if text == "BORRAR" else lambda value=text: self.add_digit(value)
            big_button(card, text, command, self.theme_name).grid(row=row, column=col, sticky="nsew", padx=10, pady=8)

        footer = themed_frame(card, self.theme_name, panel=True)
        footer.grid(row=7, column=0, columnspan=3, sticky="ew", padx=72, pady=(20, 32))
        footer.columnconfigure((0, 1), weight=1)
        footer.columnconfigure((0, 1), weight=1)
        big_button(footer, "CAMBIAR CLAVE", self.change_password, self.theme_name, height=1).grid(row=0, column=0, sticky="ew", padx=8)
        big_button(footer, "SALIR", self.winfo_toplevel().destroy, self.theme_name, bg=c["danger"], fg="#ffffff", height=1).grid(row=0, column=1, sticky="ew", padx=8)

    def _version_label(self) -> str:
        from modules.app_config import load_config
        try:
            return f"Versión {load_config().get('version', 'v2.0 Voicetest')}"
        except Exception:
            return "Versión v2.0 Voicetest"

    def add_digit(self, digit: str) -> None:
        current = self.pin_var.get()
        self.pin_var.set(current + digit)

    def clear_pin(self) -> None:
        self.pin_var.set("")

    def try_login(self) -> None:
        password = self.pin_var.get().strip()
        if not password:
            messagebox.showwarning("Clave", "Escriba la clave.")
            return
        stored_hash = get_setting(self.conn, "store_password_hash") or get_setting(self.conn, "pin_hash") or ""
        if stored_hash and verify_secret(password, stored_hash):
            self.on_success()
        else:
            messagebox.showerror("Clave", "Clave incorrecta.")
            self.clear_pin()

    def change_password(self) -> None:
        master = ask_secret(self, "Clave maestra", "Clave maestra:", theme_name=self.theme_name, show="*")
        if master is None:
            return
        master_hash = get_setting(self.conn, "master_hash") or get_setting(self.conn, "store_password_hash") or ""
        if not master_hash or not verify_secret(master, master_hash):
            messagebox.showerror("Clave", "Clave incorrecta.")
            return
        new_password = ask_secret(self, "Clave", "Nueva clave:", theme_name=self.theme_name, show="*")
        if not new_password or not new_password.strip():
            messagebox.showwarning("Clave", "Escriba una clave valida.")
            return
        confirm = ask_secret(self, "Clave", "Repita la clave:", theme_name=self.theme_name, show="*")
        if confirm != new_password:
            messagebox.showwarning("Clave", "Las claves no coinciden.")
            return
        if not messagebox.askyesno("Clave", "¿Está seguro de cambiar la clave?"):
            return
        new_hash = hash_secret(new_password.strip())
        set_setting(self.conn, "store_password_hash", new_hash)
        set_setting(self.conn, "pin_hash", new_hash)
        set_setting(self.conn, "master_hash", new_hash)
        messagebox.showinfo("Clave", "Clave guardada.")
