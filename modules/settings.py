from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

from database.db import now_text
from modules.app_config import load_config, save_config
from modules.formatters import money, parse_amount
from modules.security import (
    get_setting,
    hash_secret,
    set_setting,
    verify_secret,
)
from modules.ui_fx import ask_secret, fade_in_window


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, conn: sqlite3.Connection) -> None:
        super().__init__(master)
        self.conn = conn
        self.config_data = load_config()
        self.business_var = tk.StringVar(value=self.config_data.get("business_name", "AREZONE"))
        self.seller_var = tk.StringVar(value=self.config_data.get("default_seller", "GLORIA MENDIETA"))
        self.source_excel_var = tk.StringVar(value=self.config_data.get("source_excel", "RPTARJETA_TO_XLS.xlsx"))
        self.store_name_var = tk.StringVar(value=get_setting(self.conn, "store_name", "") or self.config_data.get("business_name", "AREZONE"))
        self.store_user_var = tk.StringVar(value=get_setting(self.conn, "store_username", "") or self.config_data.get("default_seller", "GLORIA MENDIETA"))
        self.expense_desc_var = tk.StringVar()
        self.expense_amount_var = tk.StringVar()

        self.title("Ajustes AREZONE")
        self.geometry("980x720")
        self.transient(master)
        self.grab_set()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build()
        self.load_expenses()

    def _build(self) -> None:
        tabs = ttk.Notebook(self)
        tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        tabs.bind("<<NotebookTabChanged>>", lambda _event: fade_in_window(self, duration_ms=250, steps=10))

        general = ttk.Frame(tabs, padding=14)
        security = ttk.Frame(tabs, padding=14)
        expenses = ttk.Frame(tabs, padding=14)
        tabs.add(general, text="General")
        tabs.add(security, text="Seguridad")
        tabs.add(expenses, text="Gastos")

        self._build_general(general)
        self._build_security(security)
        self._build_expenses(expenses)

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.grid(row=1, column=0, sticky="ew")
        bottom.columnconfigure((0, 1), weight=1)
        ttk.Button(bottom, text="Guardar ajustes", command=self.save_general).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(bottom, text="Cerrar", command=self.destroy).grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _build_general(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        fields = [
            ("Nombre del negocio", self.business_var),
            ("Vendedor por defecto", self.seller_var),
            ("Excel sugerido", self.source_excel_var),
        ]
        for row, (label, var) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
            ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=6)
        ttk.Label(
            parent,
            text="La migracion no se ejecuta al iniciar. Use el boton Migrar inventario cuando quiera importar.",
            foreground="#52606d",
            wraplength=620,
        ).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(18, 0))

    def _build_security(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Tienda registrada").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Label(parent, textvariable=self.store_name_var).grid(row=0, column=1, sticky="w", pady=6)
        ttk.Label(parent, text="Usuario").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Label(parent, textvariable=self.store_user_var).grid(row=1, column=1, sticky="w", pady=6)

        ttk.Button(parent, text="Cambiar clave", command=self.change_pin).grid(row=2, column=0, sticky="ew", pady=(18, 6))
        ttk.Button(parent, text="Editar tienda", command=self.edit_store).grid(
            row=2,
            column=1,
            sticky="ew",
            pady=(18, 6),
            padx=(8, 0),
        )

    def _build_expenses(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)

        ttk.Label(parent, text="Descripcion").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.expense_desc_var).grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))
        ttk.Label(parent, text="Monto").grid(row=1, column=0, sticky="w", pady=4)
        amount = ttk.Entry(parent, textvariable=self.expense_amount_var)
        amount.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))
        ttk.Button(parent, text="Agregar gasto", command=self.add_expense).grid(row=1, column=2, padx=(8, 0))

        columns = ("date", "description", "amount")
        self.expense_tree = ttk.Treeview(parent, columns=columns, show="headings")
        self.expense_tree.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        for column, title, width in [
            ("date", "Fecha", 170),
            ("description", "Descripcion", 360),
            ("amount", "Monto", 120),
        ]:
            self.expense_tree.heading(column, text=title)
            self.expense_tree.column(column, width=width, anchor="e" if column == "amount" else "w")

        ttk.Button(parent, text="Eliminar gasto seleccionado", command=self.delete_expense).grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(10, 0),
        )

    def save_general(self) -> None:
        self.config_data["business_name"] = self.business_var.get().strip() or "AREZONE"
        self.config_data["default_seller"] = self.seller_var.get().strip() or "VENDEDOR"
        self.config_data["source_excel"] = self.source_excel_var.get().strip() or "RPTARJETA_TO_XLS.xlsx"
        save_config(self.config_data)
        messagebox.showinfo("Ajustes", "Ajustes guardados. Se aplicaran completamente al volver al modulo.")

    def change_pin(self) -> None:
        if not self.verify_master():
            return
        new_pin = ask_secret(self, "Nueva clave", "Ingrese nueva clave:", theme_name=get_setting(self.conn, "theme", "day"), show="*")
        if new_pin is None:
            return
        if not new_pin.strip():
            messagebox.showwarning("Clave", "La clave no puede estar vacia.")
            return
        confirm = ask_secret(self, "Confirmar clave", "Repita la nueva clave:", theme_name=get_setting(self.conn, "theme", "day"), show="*")
        if confirm != new_pin:
            messagebox.showwarning("Clave", "Las claves no coinciden.")
            return
        new_hash = hash_secret(new_pin)
        set_setting(self.conn, "store_password_hash", new_hash)
        set_setting(self.conn, "pin_hash", new_hash)
        set_setting(self.conn, "master_hash", new_hash)
        messagebox.showinfo("Clave", "Clave actualizada.")

    def verify_master(self) -> bool:
        master = ask_secret(self, "Clave maestra", "Ingrese clave maestra:", theme_name=get_setting(self.conn, "theme", "day"), show="*")
        if master is None:
            return False
        master_hash = get_setting(self.conn, "master_hash") or get_setting(self.conn, "store_password_hash", "")
        if not master_hash or not verify_secret(master, master_hash):
            messagebox.showerror("Clave maestra", "Clave maestra incorrecta.")
            return False
        return True

    def edit_store(self) -> None:
        from modules.activation import StoreCreatorWindow

        StoreCreatorWindow(self, self.conn, self.reload_store)

    def reload_store(self) -> None:
        self.config_data = load_config()
        self.business_var.set(self.config_data.get("business_name", "AREZONE"))
        self.seller_var.set(self.config_data.get("default_seller", "GLORIA MENDIETA"))
        self.store_name_var.set(get_setting(self.conn, "store_name", "") or self.business_var.get())
        self.store_user_var.set(get_setting(self.conn, "store_username", "") or self.seller_var.get())

    def add_expense(self) -> None:
        description = self.expense_desc_var.get().strip()
        amount = parse_amount(self.expense_amount_var.get())
        if not description or amount <= 0:
            messagebox.showwarning("Gastos", "Ingrese descripcion y monto valido.")
            return
        self.conn.execute(
            "INSERT INTO expenses(created_at, description, amount) VALUES(?, ?, ?)",
            (now_text(), description, amount),
        )
        self.conn.commit()
        self.expense_desc_var.set("")
        self.expense_amount_var.set("")
        self.load_expenses()

    def load_expenses(self) -> None:
        for item in self.expense_tree.get_children():
            self.expense_tree.delete(item)
        rows = self.conn.execute(
            "SELECT id, created_at, description, amount FROM expenses ORDER BY id DESC LIMIT 200"
        ).fetchall()
        for row in rows:
            self.expense_tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(row["created_at"], row["description"], money(row["amount"])),
            )

    def delete_expense(self) -> None:
        selected = self.expense_tree.selection()
        if not selected:
            return
        if not self.verify_master():
            return
        self.conn.execute("DELETE FROM expenses WHERE id = ?", (selected[0],))
        self.conn.commit()
        self.load_expenses()
