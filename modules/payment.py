from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Callable

from database.db import get_next_invoice_no, now_text
from modules.app_config import DATA_DIR
from modules.formatters import money, parse_amount
from modules.ticket_print import (
    build_ticket,
    calculate_tax_summary,
    save_ticket,
    try_open_drawer,
    try_print_ticket,
)
from modules.ps5_ui import PS5_BG, PS5_DANGER, PS5_FONT, PS5_HINT, PS5_MUTED, PS5_OK, PS5_PANEL, PS5_TEXT, Ps5FocusGroup, paint_ps5_row, ps5_focus_row
from modules.security import get_setting
from modules.theme import app_logo_label, apply_window_icon, fit_window, ps5_glow_button
from modules.ui_fx import fade_in_window, play_sound
PAY_WIN_W, PAY_WIN_H = 1080, 760

PAY_FONT_TITLE = ("Segoe UI", 24, "bold")
PAY_FONT_TOTAL = ("Segoe UI", 30, "bold")
PAY_FONT_ROW_LBL = ("Segoe UI", 18, "bold")
PAY_FONT_ROW_VAL = ("Segoe UI", 24, "bold")
PAY_FONT_INFO = ("Segoe UI", 16, "bold")
PAY_FONT_PRINT = ("Segoe UI", 16, "bold")

class PaymentWindow(tk.Toplevel):
    def __init__(
        self,
        master,
        conn: sqlite3.Connection,
        items: list[dict],
        seller: str,
        customer: str,
        theme_name: str,
        on_complete: Callable[[str], None],
        confirm_shortcut: str = "F1",
    ) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.items = items
        self.seller = seller
        self.customer = customer
        self.on_complete = on_complete
        self.confirm_shortcut = confirm_shortcut
        self.total = sum(float(item["line_total"]) for item in items)
        self.tax_summary = calculate_tax_summary(items)

        self.cash_var = tk.StringVar(value=str(int(round(self.total))))
        self.nequi_var = tk.StringVar(value="0")
        self.print_var = tk.IntVar(value=int(get_setting(self.conn, "auto_print", "1") == "1"))
        self.difference_var = tk.StringVar(value="CERO")
        self.change_var = tk.StringVar(value=money(0))
        self._replace_next = {"cash": True, "nequi": True}
        self._closing = False
        self._finishing = False
        self._confirming = False
        self.title("Pago de venta")
        fit_window(self, PAY_WIN_W, PAY_WIN_H, min_width=960, min_height=680)
        self.resizable(True, True)
        self.overrideredirect(True)
        self.configure(bg=PS5_BG)
        apply_window_icon(self)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._safe_close)
        self._build()
        self._bind_keys()
        self.update_difference()
        self._focus_group.focus(0)
        self.after(60, lambda: self.focus_set())
        fade_in_window(self)
        play_sound(self.conn, "tap")

    def _build(self) -> None:
        shell = tk.Frame(self, bg=PS5_BG, padx=12, pady=10)
        shell.pack(fill="both", expand=True)

        top = tk.Frame(shell, bg=PS5_PANEL, highlightthickness=1, highlightbackground="#2a2a35")
        top.pack(fill="x", pady=(0, 8))
        brand = tk.Frame(top, bg=PS5_PANEL)
        brand.pack(side="left", padx=12, pady=8)
        app_logo_label(brand, self.theme_name, size=40, panel=True).grid(row=0, column=0, sticky="w")
        tk.Label(brand, text="PAGO DE VENTA", bg=PS5_PANEL, fg=PS5_TEXT, font=PAY_FONT_TITLE).grid(row=0, column=1, sticky="w", padx=(10, 0))
        tk.Label(top, text=money(self.total), bg=PS5_PANEL, fg=PS5_OK, font=PAY_FONT_TOTAL).pack(side="right", padx=12, pady=8)

        row_kw = dict(label_font=PAY_FONT_ROW_LBL, value_font=PAY_FONT_ROW_VAL, row_pady=5, inner_pad=10)
        self.row_efectivo, _ = ps5_focus_row(shell, "EFECTIVO", self.cash_var, **row_kw)
        self.row_nequi, _ = ps5_focus_row(shell, "NEQUI", self.nequi_var, **row_kw)

        self.row_print = tk.Frame(shell, bg=PS5_PANEL, highlightthickness=2, highlightbackground=PS5_PANEL)
        self.row_print.pack(fill="x", pady=5)
        self.print_label = tk.Label(
            self.row_print, text="", bg=PS5_PANEL, fg=PS5_TEXT, font=PAY_FONT_PRINT, anchor="w",
        )
        self.print_label.pack(fill="x", padx=12, pady=10)
        self._sync_print_label()

        info = tk.Frame(shell, bg=PS5_BG)
        info.pack(fill="x", pady=(8, 6))
        tk.Label(info, text="FALTA", bg=PS5_BG, fg=PS5_MUTED, font=PAY_FONT_INFO).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(info, textvariable=self.difference_var, bg=PS5_BG, fg=PS5_DANGER, font=PAY_FONT_INFO).grid(
            row=0, column=1, sticky="e", pady=2,
        )
        tk.Label(info, text="CAMBIO", bg=PS5_BG, fg=PS5_MUTED, font=PAY_FONT_INFO).grid(row=1, column=0, sticky="w", pady=2)
        tk.Label(info, textvariable=self.change_var, bg=PS5_BG, fg=PS5_OK, font=PAY_FONT_INFO).grid(
            row=1, column=1, sticky="e", pady=2,
        )
        info.columnconfigure(1, weight=1)

        actions = tk.Frame(shell, bg=PS5_BG)
        actions.pack(fill="x", pady=(12, 4))
        actions.columnconfigure((0, 1), weight=1)
        tn = self.theme_name
        self.btn_pagar = ps5_glow_button(
            actions, "PAGAR", self.finish, tn,
            bg=PS5_OK, fg="#ffffff", large=True, glow_color="#5eb8e8", glow_fg="#ffffff",
        )
        self.btn_pagar.grid(row=0, column=0, sticky="ew", padx=(0, 6), ipady=6)
        self.btn_volver = ps5_glow_button(
            actions, "VOLVER", self._safe_close, tn,
            bg=PS5_DANGER, fg="#ffffff", large=True, glow_color="#ff4d6d", glow_fg="#ffffff",
        )
        self.btn_volver.grid(row=0, column=1, sticky="ew", padx=(6, 0), ipady=6)

        self.cash_var.trace_add("write", lambda *_: self.update_difference())
        self.nequi_var.trace_add("write", lambda *_: self.update_difference())

        self._focus_group = Ps5FocusGroup(
            [
                {"paint": lambda on: paint_ps5_row(self.row_efectivo, on), "activate": lambda: self._select_amount_row("cash")},
                {"paint": lambda on: paint_ps5_row(self.row_nequi, on), "activate": lambda: self._select_amount_row("nequi")},
                {"paint": self._paint_print_row, "activate": self._toggle_print},
                {"paint": lambda on: self._paint_btn(self.btn_pagar, on, 3), "activate": self.finish},
                {"paint": lambda on: self._paint_btn(self.btn_volver, on, 4), "activate": self.destroy},
            ]
        )
        self._wire_mouse()

    def _wire_mouse(self) -> None:
        self._bind_row_click(self.row_efectivo, 0, lambda: self._select_amount_row("cash"))
        self._bind_row_click(self.row_nequi, 1, lambda: self._select_amount_row("nequi"))
        self._bind_row_click(self.row_print, 2, self._toggle_print)

    def _bind_row_click(self, row: tk.Frame, slot: int, action: Callable[[], None]) -> None:
        def handler(_event=None) -> None:
            self._focus_group.focus(slot)
            action()

        targets = [row, *row.winfo_children()]
        for widget in targets:
            widget.bind("<Button-1>", handler)
            widget.configure(cursor="hand2")

    def _paint_btn(self, btn: tk.Button, on: bool, slot: int) -> None:
        if self._focus_group.index == slot and on:
            btn.focus_set()
        elif self._focus_group.index == slot:
            btn.event_generate("<FocusOut>")

    def _paint_print_row(self, on: bool) -> None:
        bg = "#1a3a52" if on else PS5_PANEL
        border = PS5_OK if on else PS5_PANEL
        self.row_print.configure(bg=bg, highlightbackground=border, highlightthickness=5 if on else 2)
        self.print_label.configure(bg=bg)

    def _select_amount_row(self, key: str) -> None:
        self.set_payment_mode(key)
        self._replace_next[key] = True
        self._focus_group.focus(0 if key == "cash" else 1)

    def _sync_print_label(self) -> None:
        mark = "[X]" if self.print_var.get() else "[ ]"
        self.print_label.configure(text=f"{mark}  Imprimir ticket")

    def _toggle_print(self) -> None:
        self.print_var.set(0 if self.print_var.get() else 1)
        self._sync_print_label()
        play_sound(self.conn, "tap")

    def _var_for_key(self, key: str) -> tk.StringVar:
        return self.cash_var if key == "cash" else self.nequi_var

    def _bind_keys(self) -> None:
        shortcut = self.confirm_shortcut.strip().strip("<>") or "F1"
        self._confirm_sequence = f"<KeyPress-{shortcut}>"
        self._global_keys = tuple(dict.fromkeys(("<F1>", "<F2>", self._confirm_sequence)))
        for seq in self._global_keys:
            self.bind_all(seq, self._on_global_key, add="+")
            self.bind_class("Entry", seq, self._on_global_key, add="+")
        for seq in ("<Key>", "<Left>", "<Right>", "<Up>", "<Down>", "<Return>", "<KP_Enter>", "<Escape>"):
            self.bind(seq, self._on_key, add="+")
        self.bind("<Destroy>", self._release_global_keys, add="+")

    def _on_global_key(self, event: tk.Event):
        if event.keysym == "F1" or event.keysym.lower() == self.confirm_shortcut.strip().strip("<>").lower():
            self.finish()
            return "break"
        if event.keysym == "F2":
            self._safe_close()
            return "break"
        return None

    def _release_global_keys(self, _event=None) -> None:
        for seq in getattr(self, "_global_keys", ()):
            try:
                self.unbind_all(seq)
            except tk.TclError:
                pass

    def _on_key(self, event: tk.Event):
        keysym = event.keysym
        if keysym in ("F1", "F2"):
            return "break"
        if keysym == "Escape":
            self._safe_close()
            return "break"
        if keysym in ("Left", "Up"):
            self._focus_group.move(-1)
            return "break"
        if keysym in ("Right", "Down"):
            self._focus_group.move(1)
            return "break"
        if keysym in ("Return", "KP_Enter"):
            self._focus_group.activate()
            return "break"
        if keysym == "space" and self._focus_group.index == 2:
            self._toggle_print()
            return "break"
        if self._focus_group.index in (0, 1):
            if keysym in ("plus", "KP_Add", "Prior"):
                self._bump_amount(1000)
                return "break"
            if keysym in ("minus", "KP_Subtract", "Next"):
                self._bump_amount(-1000)
                return "break"
            if keysym == "BackSpace":
                self._digit_backspace()
                return "break"
            if len(keysym) == 1 and keysym.isdigit():
                self._digit_append(keysym)
                return "break"
        return None

    def _active_amount_key(self) -> str:
        return "cash" if self._focus_group.index == 0 else "nequi"

    def _digit_append(self, digit: str) -> None:
        key = self._active_amount_key()
        var = self._var_for_key(key)
        raw = "".join(ch for ch in var.get() if ch.isdigit())
        if self._replace_next.get(key, False) or raw in ("", "0"):
            raw = digit
        else:
            raw = (raw + digit).lstrip("0") or "0"
        self._replace_next[key] = False
        var.set(raw)

    def _digit_backspace(self) -> None:
        key = self._active_amount_key()
        var = self._var_for_key(key)
        raw = "".join(ch for ch in var.get() if ch.isdigit())
        var.set(raw[:-1] or "0")
        self._replace_next[key] = False

    def _bump_amount(self, delta: int) -> None:
        key = self._active_amount_key()
        var = self._var_for_key(key)
        value = max(0, int(parse_amount(var.get())) + delta)
        var.set(str(value))
        self._replace_next[key] = False

    def set_payment_mode(self, mode: str) -> None:
        amount = str(int(round(self.total)))
        self.cash_var.set("0")
        self.nequi_var.set("0")
        if mode == "cash":
            self.cash_var.set(amount)
        else:
            self.nequi_var.set(amount)
        self._replace_next[mode] = True
        play_sound(self.conn, "tap")

    def paid_amount(self) -> float:
        return parse_amount(self.cash_var.get()) + parse_amount(self.nequi_var.get())

    def update_difference(self) -> None:
        paid = self.paid_amount()
        difference = round(self.total - paid, 2)
        change = round(paid - self.total, 2)
        self.difference_var.set("CERO" if difference <= 0 else money(difference))
        self.change_var.set(money(change if change > 0 else 0))

    def _safe_close(self) -> None:
        if getattr(self, "_closing", False):
            return
        self._closing = True
        self._release_global_keys()
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

    def finish(self) -> None:
        if getattr(self, "_closing", False) or getattr(self, "_finishing", False) or getattr(self, "_confirming", False):
            return
        if self.paid_amount() + 0.01 < self.total:
            play_sound(self.conn, "warn")
            messagebox.showwarning("Pago", "Falta dinero para terminar la venta.")
            return
        self._confirming = True
        try:
            confirmed = messagebox.askyesno("Terminar venta", "Esta seguro de terminar esta venta?")
        except Exception:
            confirmed = False
        self._confirming = False
        if not confirmed:
            play_sound(self.conn, "tap")
            self._closing = False
            self.deiconify()
            self.lift()
            self.focus_force()
            self.after(50, self.focus_force)
            return

        self._finishing = True

        invoice_no = get_next_invoice_no(self.conn)
        created_at = now_text()
        cur = self.conn.execute(
            """
            INSERT INTO sales (
                invoice_no, created_at, seller, customer, subtotal, tax_total, total,
                cash, nequi, pse, card, credit, cheque, other, discount, payment_type, print_ticket
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?)
            """,
            (
                invoice_no,
                created_at,
                self.seller,
                self.customer,
                self.tax_summary["base"],
                self.tax_summary["tax"],
                self.total,
                parse_amount(self.cash_var.get()),
                parse_amount(self.nequi_var.get()),
                0,
                0,
                "Mixto",
                int(self.print_var.get() == 1),
            ),
        )
        sale_id = cur.lastrowid
        for item in self.items:
            self.conn.execute(
                """
                INSERT INTO sale_items (
                    sale_id, code, name, quantity, unit_price, price_tier,
                    cost, tax_rate, has_tax, line_total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sale_id,
                    item["code"],
                    item["name"],
                    item["quantity"],
                    item["unit_price"],
                    item.get("price_tier", "PUBLICO"),
                    item.get("cost", 0),
                    item.get("tax_rate", 0),
                    item.get("has_tax", 0),
                    item["line_total"],
                ),
            )
            self.conn.execute(
                "UPDATE products SET stock = COALESCE(stock, 0) - ? WHERE code = ?",
                (item["quantity"], item["code"]),
            )
        self.conn.commit()

        paid = self.paid_amount()
        change = round(paid - self.total, 2)
        ticket = build_ticket(
            self.conn,
            invoice_no,
            created_at,
            self.seller,
            self.customer,
            self.items,
            self.total,
            cash=parse_amount(self.cash_var.get()),
            nequi=parse_amount(self.nequi_var.get()),
            change=change if change > 0 else 0.0,
        )
        if self.print_var.get() == 1:
            ticket_path = save_ticket(invoice_no, ticket)
            try_print_ticket(ticket_path, get_setting(self.conn, "printer_port", "USB") or "USB")
        if get_setting(self.conn, "auto_open_drawer", "1") == "1":
            if not try_open_drawer(get_setting(self.conn, "printer_port", "USB") or "USB"):
                save_drawer_signal(invoice_no)

        play_sound(self.conn, "ok")
        try:
            messagebox.showinfo("Venta", f"Venta {invoice_no} terminada.\n\nCambio: {self.change_var.get()}")
        except Exception:
            pass

        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

        try:
            if self.master and getattr(self.master, "winfo_exists", lambda: False)():
                self.master.after(500, lambda: self.on_complete(ticket))
            else:
                self.on_complete(ticket)
        except Exception:
            try:
                self.on_complete(ticket)
            except Exception:
                pass


def save_drawer_signal(invoice_no: str) -> Path:
    signals_dir = DATA_DIR / "caja"
    signals_dir.mkdir(parents=True, exist_ok=True)
    path = signals_dir / f"{invoice_no}_abrir_caja.txt"
    path.write_text("ABRIR CAJA", encoding="utf-8")
    return path
