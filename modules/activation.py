from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from modules.app_config import load_config, save_config
from modules.security import hash_secret, set_setting
from modules.theme import FONT_BIG, FONT_TITLE, ThemeMixin, app_logo_label, big_button, fit_window, themed_frame
from modules.ui_fx import pop_in_window


class ActivationFrame(ttk.Frame, ThemeMixin):
    def __init__(self, master, conn, on_activated: Callable[[], None]) -> None:
        self.theme_name = "day"
        super().__init__(master)
        self.conn = conn
        self.on_activated = on_activated
        self.apply_common_styles()
        self._build()

    def _build(self) -> None:
        c = self.colors
        self.configure(style="Senior.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        panel = themed_frame(self, self.theme_name, panel=True, border=True)
        panel.grid(row=0, column=0, sticky="nsew", padx=40, pady=35)
        panel.columnconfigure(0, weight=1)

        branding = tk.Frame(panel, bg=c["panel"])
        branding.grid(row=0, column=0, pady=(18, 8), sticky="w")
        app_logo_label(branding, self.theme_name, size=46, panel=True).grid(row=0, column=0, sticky="w")
        tk.Label(
            branding,
            text="CONFIGURAR AREZONE",
            bg=c["panel"],
            fg=c["text"],
            font=FONT_TITLE,
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        tk.Label(
            panel,
            text="Bienvenido a AREZONE POS",
            bg=c["panel"],
            fg=c["text"],
            font=FONT_BIG,
        ).grid(row=1, column=0, pady=8)
        tk.Label(
            panel,
            text="Registre su tienda para comenzar",
            bg=c["panel"],
            fg=c["muted"],
            font=FONT_BIG,
        ).grid(row=2, column=0, pady=(20, 8))

        buttons = themed_frame(panel, self.theme_name, panel=True)
        buttons.grid(row=3, column=0, sticky="ew", padx=65, pady=28)
        buttons.columnconfigure(0, weight=1)
        big_button(buttons, "CREAR TIENDA", self.open_store_creator, self.theme_name, bg=c["primary"], fg=c["primary_text"]).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=8,
        )

    def open_store_creator(self) -> None:
        StoreCreatorWindow(self, self.conn, self.on_activated)


class StoreCreatorWindow(tk.Toplevel, ThemeMixin):
    def __init__(self, master, conn, on_activated: Callable[[], None]) -> None:
        self.theme_name = "day"
        super().__init__(master)
        self.conn = conn
        self.on_activated = on_activated
        self.vars = {
            "store_name": tk.StringVar(),
            "nit": tk.StringVar(),
            "phone": tk.StringVar(),
            "username": tk.StringVar(value="ADMIN"),
            "password": tk.StringVar(value="1234"),
        }

        self.title("Configurar tienda AREZONE")
        fit_window(self, 1040, 760, min_width=940, min_height=700)
        self.overrideredirect(True)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        pop_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        panel = themed_frame(self, self.theme_name, panel=True, border=True)
        panel.grid(row=0, column=0, sticky="nsew", padx=22, pady=22)
        panel.columnconfigure((0, 1), weight=1)

        tk.Label(panel, text="REGISTRO DE TIENDA", bg=c["panel"], fg=c["text"], font=FONT_TITLE).grid(
            row=0,
            column=0,
            columnspan=2,
            pady=16,
        )

        fields = [
            ("Nombre", "store_name"),
            ("NIT", "nit"),
            ("Telefono", "phone"),
            ("Usuario", "username"),
            ("Contraseña", "password"),
        ]
        for row, (label, key) in enumerate(fields, start=1):
            tk.Label(panel, text=label, bg=c["panel"], fg=c["text"], font=("Segoe UI", 18, "bold")).grid(
                row=row,
                column=0,
                sticky="w",
                padx=35,
                pady=5,
            )
            tk.Entry(
                panel,
                textvariable=self.vars[key],
                show="*" if key == "password" else "",
                font=("Segoe UI", 18),
                bg=c["input_bg"],
                fg=c["input_text"],
                insertbackground=c["input_text"],
            ).grid(row=row, column=1, sticky="ew", padx=35, pady=5, ipady=8)

        buttons = themed_frame(panel, self.theme_name, panel=True)
        buttons.grid(row=6, column=0, columnspan=2, sticky="ew", padx=35, pady=(14, 10))
        buttons.columnconfigure((0, 1), weight=1)
        big_button(buttons, "GUARDAR", self.create_and_activate, self.theme_name).grid(row=0, column=0, sticky="ew", padx=8)
        big_button(buttons, "CANCELAR", self.destroy, self.theme_name, bg=c["danger"], fg="#ffffff").grid(row=0, column=1, sticky="ew", padx=8)

    def create_and_activate(self) -> None:
        if not self.validate_form():
            return
        if not messagebox.askyesno("Configurar tienda", "¿Está seguro de registrar esta tienda?"):
            return
        password_hash = hash_secret(self.vars["password"].get().strip())
        config = load_config()
        config["business_name"] = self.vars["store_name"].get().strip()
        config["default_seller"] = self.vars["username"].get().strip() or "ADMIN"
        save_config(config)
        set_setting(self.conn, "store_name", self.vars["store_name"].get().strip())
        set_setting(self.conn, "store_nit", self.vars["nit"].get().strip())
        set_setting(self.conn, "store_phone", self.vars["phone"].get().strip())
        set_setting(self.conn, "store_username", self.vars["username"].get().strip())
        set_setting(self.conn, "store_password_hash", password_hash)
        set_setting(self.conn, "pin_hash", password_hash)
        set_setting(self.conn, "master_hash", password_hash)
        messagebox.showinfo("Tienda", "Tienda registrada correctamente.")
        self.destroy()
        self.on_activated()

    def validate_form(self) -> bool:
        if not self.vars["store_name"].get().strip():
            messagebox.showwarning("Tienda", "Escriba el nombre de la tienda.")
            return False
        if not self.vars["username"].get().strip():
            messagebox.showwarning("Usuario", "Escriba el usuario administrador.")
            return False
        if not self.vars["password"].get().strip():
            messagebox.showwarning("Clave", "Escriba la contraseña.")
            return False
        return True
