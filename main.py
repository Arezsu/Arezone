from __future__ import annotations

import os
import shutil
import sys
import tkinter as tk
import random
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


def _run_updater_if_needed() -> None:
    if not getattr(sys, "frozen", False):
        return
    app_dir = Path(sys.executable).resolve().parent
    update_dir = app_dir / "update"
    update_exe = update_dir / "AREZONE.exe"
    if not update_exe.exists():
        return
    try:
        target_exe = app_dir / "AREZONE.exe"
        if target_exe.exists() and target_exe.resolve() != update_exe.resolve():
            target_exe.unlink(missing_ok=True)
        shutil.copy2(update_exe, target_exe)
        update_exe.unlink(missing_ok=True)
        if update_dir.exists():
            try:
                os.rmdir(update_dir)
            except OSError:
                pass
    except Exception:
        pass


class ArezoneApp(tk.Tk):
    def __init__(self) -> None:
        _run_updater_if_needed()
        super().__init__()
        self.config_data = load_config()
        self._welcome_shown = False
        self.title(f"{self.config_data['app_name']} POS {self.config_data['version']}")
        self._apply_icon()
        fit_window(self, 1380, 860, min_width=1100, min_height=720)
        self.configure(bg="#dfe5ea")

        self.conn = connect()
        initialize_database(self.conn)
        ensure_runtime_settings(self.conn, self.config_data["invoice_prefix"])
        if get_setting(self.conn, "fullscreen", "0") == "1":
            self.attributes("-fullscreen", True)
            self.bind("<Escape>", lambda _event: self.attributes("-fullscreen", False))

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Configure>", lambda _event: self.update_idletasks())
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
        if not self._welcome_shown:
            self._welcome_shown = True
            self.after(450, self.show_business_welcome)

    def show_business_welcome(self) -> None:
        phrases = (
            "Cada venta bien atendida hace crecer la confianza en tu negocio.",
            "La prosperidad de un negocio nace de cuidar cada cliente y cada detalle.",
            "Hoy es una nueva oportunidad para convertir buen servicio en crecimiento.",
            "Un negocio ordenado transforma el esfuerzo diario en prosperidad.",
            "La constancia en las pequeñas ventas construye grandes resultados.",
        )
        messagebox.showinfo("AREZONE", random.choice(phrases))

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
