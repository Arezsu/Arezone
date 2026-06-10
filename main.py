from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


_ROOT = _app_root()

from database.db import connect, ensure_runtime_settings, initialize_database
from modules.activation import ActivationFrame
from modules.app_config import load_config
from modules.login import LoginFrame
from modules.sales import SalesFrame
from modules.security import get_setting
from modules.theme import apply_window_icon, fit_window


class ArezoneApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.config_data = load_config()
        self.title(f"{self.config_data['app_name']} POS")
        self._apply_icon()
        fit_window(self, 1280, 780, min_width=1040, min_height=650)
        self.configure(bg="#dfe5ea")

        self.conn = connect()
        initialize_database(self.conn)
        ensure_runtime_settings(self.conn, self.config_data["invoice_prefix"])
        if get_setting(self.conn, "fullscreen", "0") == "1":
            self.attributes("-fullscreen", True)
            self.bind("<Escape>", lambda _event: self.attributes("-fullscreen", False))

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.start_flow()

    def clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def start_flow(self) -> None:
        # Check if store is configured
        store_name = get_setting(self.conn, "store_name", "")
        if not store_name:
            self.show_activation()
        else:
            self.show_login()

    def show_activation(self) -> None:
        self.clear()
        ActivationFrame(self, self.conn, on_activated=self.show_login).pack(fill="both", expand=True)

    def show_login(self) -> None:
        self.clear()
        LoginFrame(self, self.conn, on_success=self.show_sales).pack(fill="both", expand=True)

    def show_sales(self) -> None:
        self.clear()
        self.config_data = load_config()
        SalesFrame(self, self.conn, self.config_data, on_logout=self.show_login).pack(
            fill="both",
            expand=True,
        )

    def on_close(self) -> None:
        if messagebox.askyesno("Salir", "Desea cerrar AREZONE?"):
            self.conn.close()
            self.destroy()

    def _apply_icon(self) -> None:
        try:
            apply_window_icon(self)
        except tk.TclError:
            pass


if __name__ == "__main__":
    app = ArezoneApp()
    app.mainloop()
