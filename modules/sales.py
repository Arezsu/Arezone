from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from database.db import count_products, now_text
from database.migrator import migrate_inventory
from modules.activation import StoreCreatorWindow
from modules.app_config import BASE_DIR, DATA_DIR
from modules.date_picker import DateRangePicker
from modules.formatters import money, number, parse_amount
from modules.payment import PaymentWindow
from modules.ticket_print import build_sample_ticket, save_ticket, try_open_drawer, try_print_ticket
from modules.product_codes import split_primary_and_alternates
from modules.security import get_setting, hash_secret, set_setting, verify_secret
from modules.ps5_ui import PS5_BG, PS5_HINT, PS5_MUTED, PS5_PANEL, PS5_TEXT, ps5_button
from modules.theme import FONT_BIG, FONT_TITLE, THEME_CHOICES, THEMES, ThemeMixin, app_logo_label, big_button, fit_window, set_tree_theme, themed_frame
from modules.ui_fx import ask_secret, fade_in_window, play_sound, pop_in_window


class SalesFrame(ttk.Frame, ThemeMixin):
    def __init__(
        self,
        master,
        conn: sqlite3.Connection,
        config: dict,
        on_logout: Callable[[], None],
    ) -> None:
        self.theme_name = get_setting(conn, "theme", "day") or "day"
        super().__init__(master)
        self.conn = conn
        self.config = config
        self.on_logout = on_logout
        self.cart: list[dict] = []
        self.last_ticket = ""
        self.clock_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="1")
        self.product_search_var = tk.StringVar()
        self.total_var = tk.StringVar(value=money(0))
        self.seller_var = tk.StringVar(value=config.get("default_seller", "ADMIN"))
        self.customer_var = tk.StringVar(value="0")
        self.theme_var = tk.StringVar(value=self.theme_name)
        self._payment_window: PaymentWindow | None = None
        self.active_screen = "home"
        self.report_range = self._range_today()
        self.current_report_rows: list[tuple[str, str]] = []
        self.nav_buttons: list[tk.Button] = []
        self.nav_focus_index = 0
        self.home_buttons: list[tk.Button] = []
        self.home_focus_index = 0

        self.apply_common_styles()
        self._build_shell()
        self.show_home_screen()
        self._bind_shortcuts()
        self.update_clock()
        self.after(700, self.maybe_auto_import)

    def _build_shell(self) -> None:
        c = self.colors
        self.configure(style="Senior.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.header = themed_frame(self, self.theme_name)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.columnconfigure(0, weight=1)

        branding = tk.Frame(self.header, bg=c["bg"])
        branding.grid(row=0, column=0, sticky="w", padx=18, pady=10)
        app_logo_label(branding, self.theme_name, size=40, panel=False).grid(row=0, column=0, sticky="w")
        tk.Label(branding, text="AREZONE", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=1, sticky="w", padx=(10, 0))
        big_button(self.header, "DIA", lambda: self.change_theme("day"), self.theme_name, height=1).grid(row=0, column=1, padx=5, pady=10)
        big_button(self.header, "NOCHE", lambda: self.change_theme("night"), self.theme_name, height=1).grid(row=0, column=2, padx=5, pady=10)
        tk.Label(self.header, textvariable=self.clock_var, bg=c["bg"], fg=c["text"], font=FONT_BIG).grid(row=0, column=3, padx=18)

        self.theme_var.set(self.theme_name)
        tk.Label(self.header, text="Tema", bg=c["bg"], fg=c["muted"], font=("Segoe UI", 14, "bold")).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 8))
        theme_selector = ttk.Combobox(
            self.header,
            textvariable=self.theme_var,
            values=THEME_CHOICES,
            state="readonly",
            width=14,
            font=("Segoe UI", 13, "bold"),
        )
        theme_selector.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=(0, 8), ipady=4)
        theme_selector.bind("<<ComboboxSelected>>", lambda _event: self.change_theme(self.theme_var.get()))
        big_button(self.header, "[F9] TEMA", self.cycle_theme, self.theme_name, height=1).grid(row=1, column=3, padx=5, pady=(0, 8))

        self.nav = tk.Frame(self, bg=PS5_PANEL)
        self.nav.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self.nav.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self.nav_buttons = []
        self._add_nav_button("VENTAS", self.show_sales_screen, 0)
        self._add_nav_button("PRODUCTOS", self.show_products_screen, 1)
        self._add_nav_button("REPORTES", self.show_reports_screen, 2)
        self._add_nav_button("AJUSTES", self.show_settings_screen, 3)
        self._add_nav_button("[F7] INICIO", self.show_home_screen, 4)
        self._add_nav_button("[F8] INFO", self.show_about, 5)

        self.content = themed_frame(self, self.theme_name, panel=False)
        self.content.grid(row=2, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

    def _add_nav_button(self, text: str, command: Callable[[], None], column: int) -> None:
        button = ps5_button(self.nav, text, command, self.theme_name, compact=True)
        button.grid(row=0, column=column, sticky="ew", padx=3, pady=4, ipady=2)
        button.bind("<Left>", lambda _event: self._focus_nav_delta(-1))
        button.bind("<Up>", lambda _event: self._focus_nav_delta(-1))
        button.bind("<Right>", lambda _event: self._focus_nav_delta(1))
        button.bind("<Down>", lambda _event: self._focus_nav_delta(1))
        button.bind("<Return>", lambda _event: self._invoke_focused_nav())
        button.bind("<KP_Enter>", lambda _event: self._invoke_focused_nav())
        self.nav_buttons.append(button)

    def rebuild_shell(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self.apply_common_styles()
        self._build_shell()

    def clear_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def change_theme(self, theme_name: str) -> None:
        if theme_name not in THEMES:
            theme_name = "day"
        self.theme_name = theme_name
        self.theme_var.set(theme_name)
        set_setting(self.conn, "theme", theme_name)
        self.rebuild_shell()
        self.show_active_screen()
        self._fade_shell()

    def cycle_theme(self) -> None:
        choices = list(THEME_CHOICES)
        index = choices.index(self.theme_name) if self.theme_name in choices else 0
        self.change_theme(choices[(index + 1) % len(choices)])

    def show_active_screen(self) -> None:
        screens = {
            "home": self.show_home_screen,
            "sales": self.show_sales_screen,
            "products": self.show_products_screen,
            "reports": self.show_reports_screen,
            "settings": self.show_settings_screen,
        }
        screens.get(self.active_screen, self.show_home_screen)()
        self._fade_shell()

    def _fade_shell(self) -> None:
        try:
            fade_in_window(self.winfo_toplevel(), duration_ms=250, steps=10)
        except Exception:
            pass

    def _bind_shortcuts(self) -> None:
        root = self.winfo_toplevel()
        root.bind("<F1>", self._on_f1_key)
        root.bind("<F2>", lambda _event: self.show_products_screen())
        root.bind("<F3>", lambda _event: self.show_reports_screen())
        root.bind("<F4>", lambda _event: self.show_settings_screen())
        root.bind("<F5>", lambda _event: self.context_refresh())
        root.bind("<F6>", lambda _event: self.hold_sale())
        root.bind("<F7>", lambda _event: self.show_home_screen())
        root.bind("<F8>", lambda _event: self.show_about())
        root.bind("<F9>", lambda _event: self.cycle_theme())
        root.bind("<F10>", lambda _event: self.exit_module())
        root.bind("<Delete>", lambda _event: self.remove_selected_cart_item())
        root.bind("<BackSpace>", lambda _event: self.remove_selected_cart_item())
        root.bind("<KeyPress-x>", lambda _event: self.remove_selected_cart_item())
        root.bind("<KeyPress-X>", lambda _event: self.remove_selected_cart_item())
        root.bind("<Escape>", lambda _event: self.show_home_screen())
        root.bind("<Left>", lambda event: self._handle_nav_arrow(event, -1), add="+")
        root.bind("<Up>", lambda event: self._handle_nav_arrow(event, -1), add="+")
        root.bind("<Right>", lambda event: self._handle_nav_arrow(event, 1), add="+")
        root.bind("<Down>", lambda event: self._handle_nav_arrow(event, 1), add="+")
        root.bind("<Return>", self._handle_nav_enter, add="+")
        root.bind("<KP_Enter>", self._handle_nav_enter, add="+")

    def _on_f1_key(self, _event=None):
        if self._payment_window is not None and self._payment_window.winfo_exists():
            return None
        if self.active_screen == "sales":
            self.open_payment()
        else:
            self.show_sales_screen()
        return "break"

    def _handle_nav_arrow(self, event: tk.Event, delta: int):
        if self.active_screen == "home" and self.home_buttons and self._can_use_nav_keys(event):
            return self._focus_home_delta(delta)
        if not self._can_use_nav_keys(event):
            return None
        return self._focus_nav_delta(delta)

    def _handle_nav_enter(self, event: tk.Event):
        widget = self.focus_get()
        if self.active_screen == "home" and self.home_buttons:
            target = widget if widget in self.home_buttons else self.home_buttons[self.home_focus_index]
            target.invoke()
            return "break"
        if widget in self.nav_buttons:
            self._invoke_focused_nav()
            return "break"
        return None

    def _can_use_nav_keys(self, event: tk.Event) -> bool:
        widget = event.widget
        widget_class = widget.winfo_class() if hasattr(widget, "winfo_class") else ""
        if widget in self.nav_buttons or widget in self.home_buttons:
            return True
        if self.active_screen == "home" and self.home_buttons:
            return widget_class not in {"Entry", "TEntry", "Text", "Treeview", "TCombobox", "Combobox"}
        return widget_class not in {"Entry", "TEntry", "Text", "Treeview", "TCombobox", "Combobox"}

    def _focus_nav_delta(self, delta: int):
        if not self.nav_buttons:
            return "break"
        current = self.focus_get()
        if current in self.nav_buttons:
            self.nav_focus_index = self.nav_buttons.index(current)
        self.nav_focus_index = (self.nav_focus_index + delta) % len(self.nav_buttons)
        self.nav_buttons[self.nav_focus_index].focus_set()
        return "break"

    def _invoke_focused_nav(self):
        widget = self.focus_get()
        if widget in self.nav_buttons:
            widget.invoke()
            return "break"
        return None

    def _focus_home_delta(self, delta: int):
        if not self.home_buttons:
            return "break"
        current = self.focus_get()
        if current in self.home_buttons:
            self.home_focus_index = self.home_buttons.index(current)
        cols = 3
        total = len(self.home_buttons)
        row, col = divmod(self.home_focus_index, cols)
        if delta in (-1, 1):
            ncol = col + delta
            idx = row * cols + ncol
            if 0 <= ncol < cols and idx < total:
                self.home_focus_index = idx
        else:
            idx = (row + (1 if delta > 0 else -1)) * cols + col
            if 0 <= idx < total:
                self.home_focus_index = idx
        self.home_buttons[self.home_focus_index].focus_set()
        return "break"

    def context_refresh(self) -> None:
        if self.active_screen == "products":
            self.refresh_products()
        elif self.active_screen == "reports":
            self.refresh_report()
        elif self.active_screen == "sales":
            self.find_product_for_sale()
        else:
            self.show_home_screen()

    def update_clock(self) -> None:
        self.clock_var.set(datetime.now().strftime("%I:%M %p"))
        self.apply_auto_theme_if_needed()
        if self.winfo_exists():
            self.after(1000, self.update_clock)

    def apply_auto_theme_if_needed(self) -> None:
        if get_setting(self.conn, "auto_night_enabled", "1") != "1":
            return
        if self.theme_name not in {"day", "night"}:
            return
        expected = expected_theme_for_time(
            get_setting(self.conn, "night_start", "18:00") or "18:00",
            get_setting(self.conn, "night_end", "06:00") or "06:00",
        )
        if expected != self.theme_name:
            self.theme_name = expected
            self.theme_var.set(expected)
            set_setting(self.conn, "theme", expected)
            self.rebuild_shell()
            self.show_active_screen()

    def show_home_screen(self) -> None:
        self.active_screen = "home"
        self.clear_content()
        self.home_buttons = []
        root = tk.Frame(self.content, bg=PS5_BG)
        root.grid(row=0, column=0, sticky="nsew", padx=10, pady=6)
        root.columnconfigure((0, 1, 2), weight=1)
        root.rowconfigure((2, 3), weight=1)

        tk.Label(root, text="AREZONE", bg=PS5_BG, fg=PS5_TEXT, font=("Segoe UI", 26, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 2),
        )
        tk.Label(root, text=PS5_HINT, bg=PS5_BG, fg=PS5_MUTED, font=("Segoe UI", 11, "bold")).grid(
            row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 8),
        )

        cards = [
            ("VENTAS", self.show_sales_screen, True),
            ("PRODUCTOS", self.show_products_screen, False),
            ("REPORTES", self.show_reports_screen, False),
            ("AJUSTES", self.show_settings_screen, False),
            ("INFO", self.show_about, False),
            ("SALIR", self.exit_module, False),
        ]
        for index, (title, command, accent) in enumerate(cards):
            row = 2 + index // 3
            col = index % 3
            card = tk.Frame(root, bg=PS5_PANEL, highlightthickness=2, highlightbackground=PS5_PANEL)
            card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
            card.columnconfigure(0, weight=1)
            btn = ps5_button(card, title, command, self.theme_name, accent=accent, danger=(title == "SALIR"))
            btn.grid(row=0, column=0, sticky="ew", padx=8, pady=12, ipady=10)
            btn.bind("<Left>", lambda _e: self._focus_home_delta(-1))
            btn.bind("<Right>", lambda _e: self._focus_home_delta(1))
            btn.bind("<Up>", lambda _e: self._focus_home_delta(-3))
            btn.bind("<Down>", lambda _e: self._focus_home_delta(3))
            btn.bind("<Return>", lambda _e: (btn.invoke(), "break"))
            btn.bind("<KP_Enter>", lambda _e: (btn.invoke(), "break"))
            self.home_buttons.append(btn)
        if self.home_buttons:
            self.home_focus_index = 0
            self.home_buttons[0].focus_set()

        footer = tk.Frame(root, bg=PS5_PANEL)
        footer.grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=(8, 10))
        footer.columnconfigure((0, 1, 2), weight=1)
        today_start, today_end = self._range_today()
        sales_row = self.conn.execute(
            """
            SELECT COUNT(*) AS count, COALESCE(SUM(total), 0) AS total
            FROM sales
            WHERE created_at BETWEEN ? AND ? AND status = 'COMPLETED'
            """,
            (f"{today_start.isoformat()}T00:00:00", f"{today_end.isoformat()}T23:59:59"),
        ).fetchone()
        stats = [
            ("Productos", number(count_products(self.conn))),
            ("Ventas hoy", number(sales_row["count"] if sales_row else 0)),
            ("Total hoy", money(sales_row["total"] if sales_row else 0)),
        ]
        footer.columnconfigure((0, 1, 2), weight=1)
        for col, (label, value) in enumerate(stats):
            tk.Label(footer, text=label, bg=PS5_PANEL, fg=PS5_MUTED, font=("Segoe UI", 12, "bold")).grid(row=0, column=col, sticky="w", padx=12)
            tk.Label(footer, text=value, bg=PS5_PANEL, fg=PS5_TEXT, font=FONT_BIG).grid(row=1, column=col, sticky="w", padx=12, pady=(0, 6))

    def show_sales_screen(self) -> None:
        self.active_screen = "sales"
        self.clear_content()
        c = self.colors
        root = themed_frame(self.content, self.theme_name)
        root.grid(row=0, column=0, sticky="nsew", padx=16, pady=8)
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)
        root.rowconfigure(0, weight=1)

        left = themed_frame(root, self.theme_name, panel=True, border=True)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        tk.Label(left, text="VENDER", bg=c["panel"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 6))

        search = themed_frame(left, self.theme_name, panel=True)
        search.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        search.columnconfigure(0, weight=1)
        search.columnconfigure(1, weight=0)
        search.columnconfigure(2, weight=0)
        self.search_entry = tk.Entry(search, textvariable=self.search_var, font=("Segoe UI", 22, "bold"), bg=c["input_bg"], fg=c["input_text"], insertbackground=c["input_text"])
        self.search_entry.grid(row=0, column=0, sticky="ew", ipady=14, padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _event: self.add_from_input())
        self.search_entry.focus_set()
        big_button(search, "BUSCAR", self.find_product_for_sale, self.theme_name, height=1).grid(row=0, column=1, sticky="ew")
        unit_box = tk.Frame(search, bg=c["panel"], highlightthickness=1, highlightbackground=c["primary"])
        unit_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        unit_box.columnconfigure(1, weight=1)
        tk.Label(unit_box, text="UNIDAD", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", padx=(10, 8), pady=8
        )
        tk.Entry(
            unit_box,
            textvariable=self.unit_var,
            font=("Segoe UI", 18, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
            justify="center",
            width=10,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=8, ipady=6)
        tk.Label(unit_box, text="Ej: 2*lengua", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 11, "bold")).grid(
            row=0, column=2, sticky="e", padx=(0, 10)
        )

        columns = ("code", "name", "qty", "price", "total")
        self.cart_tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="extended")
        self.cart_tree.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        for col, title, width in [
            ("code", "CODIGO", 130),
            ("name", "PRODUCTO", 300),
            ("qty", "UND", 90),
            ("price", "PRECIO", 130),
            ("total", "TOTAL", 140),
        ]:
            self.cart_tree.heading(col, text=title)
            self.cart_tree.column(col, width=width, anchor="e" if col in {"qty", "price", "total"} else "w")
        set_tree_theme(self.cart_tree, self.theme_name)
        self.cart_tree.config(selectmode="extended")
        self.cart_tree.bind("<Delete>", lambda _event: self.remove_selected_cart_item())
        self.cart_tree.bind("<KeyPress-x>", lambda _event: self.remove_selected_cart_item())

        bottom = themed_frame(left, self.theme_name, panel=True)
        bottom.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 18))
        bottom.columnconfigure((0, 1), weight=1)
        tk.Label(bottom, text="TOTAL", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=0, column=0, sticky="w")
        tk.Label(bottom, textvariable=self.total_var, bg=c["panel"], fg=c["danger"], font=("Segoe UI", 36, "bold")).grid(row=0, column=1, sticky="e")
        tk.Label(bottom, text=f"Usuario: {self.seller_var.get()}    Turno: {THEMES[self.theme_name]['name']}", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 16, "bold")).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(6, 0),
        )
        tk.Label(bottom, text="Cedula / Cliente", bg=c["panel"], fg=c["text"], font=("Segoe UI", 16, "bold")).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        tk.Entry(
            bottom,
            textvariable=self.customer_var,
            font=("Segoe UI", 16, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
        ).grid(row=2, column=1, sticky="ew", pady=(8, 0), ipady=5)

        right = themed_frame(root, self.theme_name, panel=True, border=True)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure((0, 1, 2), weight=1)
        for row in range(10):
            right.rowconfigure(row, weight=1)

        for text, row, col in [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("0", 3, 0), ("00", 3, 1), ("*", 3, 2),
        ]:
            big_button(right, text, lambda value=text: self.append_search(value), self.theme_name).grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        actions = [
            ("PAGAR", self.open_payment),
            ("ELIMINAR ITEM", self.remove_selected_cart_item),
            ("BORRAR", self.clear_search),
            ("BUSCAR", self.find_product_for_sale),
            ("ESPERA", self.hold_sale),
            ("SALIR", self.show_home_screen),
        ]
        for index, (text, command) in enumerate(actions, start=4):
            big_button(
                right,
                text,
                lambda cmd=command: self.after(100, cmd),
                self.theme_name,
                bg=c["primary"] if text == "PAGAR" else None,
                fg=c["primary_text"] if text == "PAGAR" else None,
            ).grid(
                row=index,
                column=0,
                columnspan=3,
                sticky="nsew",
                padx=6,
                pady=6,
            )
        self.refresh_cart()
        self._fade_shell()

    def show_products_screen(self) -> None:
        self.active_screen = "products"
        self.clear_content()
        c = self.colors
        root = themed_frame(self.content, self.theme_name, panel=True, border=True)
        root.grid(row=0, column=0, sticky="nsew", padx=16, pady=8)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        tk.Label(root, text="MIS PRODUCTOS", bg=c["panel"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 8))
        search = themed_frame(root, self.theme_name, panel=True)
        search.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        search.columnconfigure(0, weight=1)
        tk.Entry(search, textvariable=self.product_search_var, font=("Segoe UI", 20, "bold"), bg=c["input_bg"], fg=c["input_text"], insertbackground=c["input_text"]).grid(
            row=0,
            column=0,
            sticky="ew",
            ipady=12,
            padx=(0, 8),
        )
        big_button(search, "BUSCAR", self.refresh_products, self.theme_name, height=1).grid(row=0, column=1, sticky="ew")

        self.products_tree = ttk.Treeview(root, columns=("code", "name", "price", "stock"), show="headings", selectmode="browse")
        self.products_tree.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        for col, title, width in [
            ("code", "CODIGO", 180),
            ("name", "PRODUCTO", 460),
            ("price", "PRECIO", 180),
            ("stock", "STOCK", 120),
        ]:
            self.products_tree.heading(col, text=title)
            self.products_tree.column(col, width=width, anchor="e" if col in {"price", "stock"} else "w")
        set_tree_theme(self.products_tree, self.theme_name)
        self.products_tree.bind("<Double-1>", lambda _event: self.edit_product())

        buttons = themed_frame(root, self.theme_name, panel=True)
        buttons.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 18))
        buttons.columnconfigure((0, 1, 2, 3, 4), weight=1)
        for col, (text, command) in enumerate([
            ("AGREGAR", self.add_product_dialog),
            ("EDITAR", self.edit_product),
            ("ELIMINAR", self.delete_product),
            ("ACTUALIZAR", self.refresh_products),
            ("IMPORTAR", self.manual_migration),
        ]):
            big_button(buttons, text, command, self.theme_name, height=1).grid(row=0, column=col, sticky="ew", padx=5)
        self.refresh_products()
        self._fade_shell()

    def show_reports_screen(self) -> None:
        self.active_screen = "reports"
        self.clear_content()
        c = self.colors
        root = themed_frame(self.content, self.theme_name, panel=True, border=True)
        root.grid(row=0, column=0, sticky="nsew", padx=16, pady=8)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        tk.Label(root, text="VER MIS VENTAS", bg=c["panel"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 8))
        ranges = themed_frame(root, self.theme_name, panel=True)
        ranges.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        ranges.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        for col, (text, command) in enumerate([
            ("HOY", lambda: self.set_report_range("today")),
            ("AYER", lambda: self.set_report_range("yesterday")),
            ("SEMANA", lambda: self.set_report_range("week")),
            ("MES", lambda: self.set_report_range("month")),
            ("AÑO", lambda: self.set_report_range("year")),
            ("ELEGIR", self.custom_report_range),
        ]):
            big_button(ranges, text, command, self.theme_name, height=1).grid(row=0, column=col, sticky="ew", padx=4)

        self.report_panel = themed_frame(root, self.theme_name, panel=True, border=True)
        self.report_panel.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        self.report_panel.columnconfigure(0, weight=1)

        buttons = themed_frame(root, self.theme_name, panel=True)
        buttons.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 18))
        buttons.columnconfigure((0, 1, 2, 3, 4), weight=1)
        for col, (text, command) in enumerate([
            ("GUARDAR EXCEL", self.export_report),
            ("IMPRIMIR", self.print_report),
            ("VER GRAFICA", self.chart_report),
            ("ANULAR FACTURA", self.open_void_invoice_window),
            ("VOLVER", self.show_sales_screen),
        ]):
            big_button(buttons, text, command, self.theme_name, height=1).grid(row=0, column=col, sticky="ew", padx=5)
        self.refresh_report()
        self._fade_shell()

    def show_settings_screen(self) -> None:
        self.active_screen = "settings"
        self.clear_content()
        c = self.colors
        root = themed_frame(self.content, self.theme_name, panel=True, border=True)
        root.grid(row=0, column=0, sticky="nsew", padx=16, pady=8)
        root.columnconfigure((0, 1), weight=1)
        root.rowconfigure((1, 2, 3, 4, 5), weight=1)

        tk.Label(root, text="CONFIGURACION", bg=c["panel"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(14, 8))
        cards = [
            ("IMPRESORA", self.show_printer_settings),
            ("AUTOARRANQUE", self.show_autostart_settings),
            ("HORARIO NOCHE", self.show_night_settings),
            ("DATOS DE TIENDA", self.open_store_creator),
            ("PAGOS A PROVEEDORES", self.show_brand_payments_window),
            ("CAMBIAR CLAVE", self.open_super_admin),
        ]
        cards.append(("INFO DEL SISTEMA", self.show_about))
        for index, (text, command) in enumerate(cards):
            row = 1 + index // 2
            col = index % 2
            big_button(root, text, command, self.theme_name).grid(row=row, column=col, sticky="nsew", padx=18, pady=18)
        self._fade_shell()

    def show_printer_settings(self) -> None:
        PrinterSettingsWindow(self, self.conn, self.theme_name)

    def show_autostart_settings(self) -> None:
        AutostartWindow(self, self.conn, self.theme_name)

    def show_night_settings(self) -> None:
        NightModeWindow(self, self.conn, self.theme_name)

    def show_brand_payments_window(self) -> None:
        BrandPaymentsWindow(self, self.conn, self.theme_name)

    def open_super_admin(self) -> None:
        master = ask_secret(self, "Super admin", "Clave maestra:", theme_name=self.theme_name)
        if not master:
            return
        master_hash = get_setting(self.conn, "master_hash", "") or get_setting(self.conn, "store_password_hash", "")
        if not verify_secret(master, master_hash):
            play_sound(self.conn, "error")
            messagebox.showerror("Super admin", "Clave incorrecta.")
            return
        new_password = ask_secret(self, "Clave", "Nueva clave:", theme_name=self.theme_name, show="*")
        if not new_password:
            return
        confirm = ask_secret(self, "Clave", "Repita la nueva clave:", theme_name=self.theme_name, show="*")
        if confirm != new_password:
            messagebox.showwarning("Clave", "Las claves no coinciden.")
            return
        new_hash = hash_secret(new_password.strip())
        set_setting(self.conn, "store_password_hash", new_hash)
        set_setting(self.conn, "pin_hash", new_hash)
        set_setting(self.conn, "master_hash", new_hash)
        messagebox.showinfo("Clave", "Clave actualizada.")

    def open_store_creator(self) -> None:
        StoreCreatorWindow(self, self.conn, lambda: messagebox.showinfo("Tienda", "Datos guardados."))

    def show_about(self) -> None:
        messagebox.showinfo(
            "Info AREZONE",
            "AREZONE POS\n\n"
            "Autores:\n"
            "Alejandro Sanchez Quimbayo\n\n"
            "Correo:\n"
            "AREZSUPRIV@GMAIL.COM\n\n"
            f"Tienda:\n{get_setting(self.conn, 'store_name', 'AREZONE')}",
        )

    def maybe_auto_import(self) -> None:
        if get_setting(self.conn, "excel_auto_import_done", "0") == "1":
            return
        if count_products(self.conn) > 0:
            return
        path = self.find_default_excel()
        if path is not None:
            ImportingWindow(self, self.conn, self.theme_name, path, on_done=lambda: set_setting(self.conn, "excel_auto_import_done", "1"))

    def find_default_excel(self) -> Path | None:
        name = self.config.get("source_excel", "RPTARJETA_TO_XLS.xlsx")
        for path in (BASE_DIR / name, BASE_DIR.parent / name, Path.cwd() / name):
            if path.exists():
                return path
        return None

    def manual_migration(self) -> None:
        path = self.find_default_excel()
        if path is None:
            selected = filedialog.askopenfilename(
                title="Seleccionar Excel",
                filetypes=[("Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")],
                initialdir=str(BASE_DIR.parent),
            )
            if not selected:
                return
            path = Path(selected)
        elif not messagebox.askyesno("Importar productos", f"Importar productos desde este archivo?\n\n{path}"):
            return
        ImportingWindow(self, self.conn, self.theme_name, path, on_done=self.after_import)

    def after_import(self) -> None:
        set_setting(self.conn, "excel_auto_import_done", "1")
        if hasattr(self, "products_tree") and self.products_tree.winfo_exists():
            self.refresh_products()

    def append_search(self, value: str) -> None:
        self.search_var.set(self.search_var.get() + value)
        play_sound(self.conn, "tap")

    def _format_unit_value(self, value: float) -> str:
        if value <= 0:
            return "1"
        if abs(value - round(value)) < 0.00001:
            return str(int(round(value)))
        return f"{value:.6f}".rstrip("0").rstrip(".")

    def _set_unit_value(self, value: float) -> None:
        self.unit_var.set(self._format_unit_value(value))

    def _current_unit_value(self) -> float:
        value = parse_amount(self.unit_var.get())
        return value if value > 0 else 1.0

    def clear_search(self) -> None:
        self.search_var.set("")

    def add_from_input(self) -> None:
        raw = self.search_var.get().strip()
        if not raw:
            return
        quantity = self._current_unit_value()
        code = raw
        if "*" in raw:
            left, right = raw.split("*", 1)
            try:
                quantity = float(left.replace(",", "."))
                self._set_unit_value(quantity)
                code = right.strip()
            except ValueError:
                code = raw
        product = self.find_exact_product(code)
        if product is None:
            self.search_var.set(code)
            option = messagebox.askyesnocancel(
                "Codigo no encontrado",
                "No se encontro el codigo.\n\n"
                "Si = Verificar/buscar nuevamente\n"
                "No = Crear producto nuevo\n"
                "Cancelar = Salir",
            )
            play_sound(self.conn, "warn")
            if option is True:
                self.find_product_for_sale()
            elif option is False:
                dialog = SimpleProductDialog(self, self.conn, self.theme_name, initial_code=code)
                self.wait_window(dialog)
                if dialog.saved:
                    self.refresh_products()
            return
        self.add_product_to_cart(product, quantity)
        self.clear_search()
        self._set_unit_value(1)

    def find_exact_product(self, code: str) -> dict | None:
        key = code.strip().upper()
        row = self.conn.execute(
            """
            SELECT * FROM products
            WHERE UPPER(code) = ?
               OR UPPER(COALESCE(alt_codes, '')) LIKE ?
            LIMIT 1
            """,
            (key, f"%{key}%"),
        ).fetchone()
        return dict(row) if row else None

    def find_product_for_sale(self) -> None:
        dialog = ProductPickerDialog(self, self.conn, self.theme_name, self.search_var.get())
        self.wait_window(dialog)
        if dialog.selected_product:
            self.add_product_to_cart(dialog.selected_product, self._current_unit_value())
            self.clear_search()
            self._set_unit_value(1)

    def add_product_to_cart(self, product: dict, quantity: float) -> None:
        unit_price = float(product.get("price_public") or 0)
        if unit_price <= 0:
            play_sound(self.conn, "warn")
            messagebox.showwarning("Producto", "Este producto no tiene precio.")
            return
        self.cart.append(
            {
                "code": product["code"],
                "name": product["name"],
                "quantity": quantity,
                "unit_price": unit_price,
                "price_tier": "PUBLICO",
                "cost": float(product.get("cost") or 0),
                "tax_rate": float(product.get("tax_rate") or 0),
                "has_tax": int(product.get("has_tax") or 0),
                "line_total": round(quantity * unit_price, 2),
            }
        )
        self.refresh_cart()
        play_sound(self.conn, "ok")

    def refresh_cart(self) -> None:
        if not hasattr(self, "cart_tree"):
            return
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)
        for index, item in enumerate(self.cart):
            self.cart_tree.insert(
                "",
                "end",
                iid=str(index),
                tags=("even" if index % 2 == 0 else "odd",),
                values=(item["code"], item["name"], number(item["quantity"]), money(item["unit_price"]), money(item["line_total"])),
            )
        self.total_var.set(money(sum(item["line_total"] for item in self.cart)))

    def open_payment(self) -> None:
        if not self.cart:
            play_sound(self.conn, "warn")
            messagebox.showinfo("Venta", "Agregue productos primero.")
            return
        if self._payment_window is not None and self._payment_window.winfo_exists():
            self._payment_window.lift()
            self._payment_window.focus_force()
            return
        self._payment_window = PaymentWindow(
            self,
            self.conn,
            [item.copy() for item in self.cart],
            self.seller_var.get(),
            self.customer_var.get(),
            self.theme_name,
            on_complete=self.complete_sale,
        )
        self._payment_window.bind("<Destroy>", self._clear_payment_window, add="+")

    def complete_sale(self, ticket: str) -> None:
        self.last_ticket = ticket
        self.cart.clear()
        self.refresh_cart()
        self._payment_window = None

        # Restaurar el foco al campo de búsqueda después de que PaymentWindow y messagebox se cierren
        if hasattr(self, 'search_entry'):
            self.after(500, lambda: self.search_entry.focus_force())
        
    def _clear_payment_window(self, _event=None) -> None:
        self._payment_window = None

    def hold_sale(self) -> None:
        if not self.cart:
            row = self.conn.execute("SELECT id, payload FROM held_sales ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                messagebox.showinfo("Espera", "No hay venta en espera.")
                return
            payload = json.loads(row["payload"])
            self.cart = payload.get("items", [])
            self.conn.execute("DELETE FROM held_sales WHERE id = ?", (row["id"],))
            self.conn.commit()
            self.refresh_cart()
            messagebox.showinfo("Espera", "Venta recuperada.")
            return
        if not messagebox.askyesno("Guardar venta", "Guardar esta venta en espera?"):
            return
        self.conn.execute(
            "INSERT INTO held_sales(created_at, payload) VALUES(?, ?)",
            (now_text(), json.dumps({"items": self.cart}, ensure_ascii=False)),
        )
        self.conn.commit()
        self.cart.clear()
        self.refresh_cart()
        messagebox.showinfo("Espera", "Venta guardada.")

    def clear_sale(self) -> None:
        if self.cart and messagebox.askyesno("Borrar", "Esta seguro de borrar la venta?"):
            self.cart.clear()
            self.refresh_cart()

    def remove_selected_cart_item(self) -> None:
        if not hasattr(self, "cart_tree"):
            return
        selected = self.cart_tree.selection()
        if not selected:
            play_sound(self.conn, "warn")
            return
        indexes = sorted({int(item) for item in selected if str(item).isdigit()}, reverse=True)
        names = [self.cart[index]["name"] for index in indexes if 0 <= index < len(self.cart)]
        if not names:
            return
        preview = "\n".join(f"- {name}" for name in names[:6])
        if len(names) > 6:
            preview += f"\n- ... y {len(names) - 6} mas"
        if not messagebox.askyesno("Eliminar", f"Quitar los productos seleccionados de la venta?\n\n{preview}"):
            return
        for index in indexes:
            if 0 <= index < len(self.cart):
                self.cart.pop(index)
        self.refresh_cart()
        play_sound(self.conn, "ok")

    def open_void_invoice_window(self) -> None:
        InvoiceVoidWindow(self, self.conn, self.theme_name, on_annulled=self.refresh_report)

    def refresh_products(self) -> None:
        if not hasattr(self, "products_tree"):
            return
        for row in self.products_tree.get_children():
            self.products_tree.delete(row)
        query = f"%{self.product_search_var.get().strip()}%"
        rows = self.conn.execute(
            """
            SELECT code, name, price_public, stock, alt_codes
            FROM products
            WHERE code LIKE ? OR name LIKE ? OR brand LIKE ? OR category LIKE ? OR COALESCE(alt_codes, '') LIKE ?
            ORDER BY name
            LIMIT 500
            """,
            (query, query, query, query, query),
        ).fetchall()
        for index, row in enumerate(rows):
            self.products_tree.insert(
                "",
                "end",
                iid=row["code"],
                tags=("even" if index % 2 == 0 else "odd",),
                values=(row["code"], row["name"], money(row["price_public"]), number(row["stock"])),
            )

    def selected_product_code(self) -> str | None:
        selected = self.products_tree.selection() if hasattr(self, "products_tree") else []
        return selected[0] if selected else None

    def add_product_dialog(self) -> None:
        dialog = SimpleProductDialog(self, self.conn, self.theme_name)
        self.wait_window(dialog)
        if dialog.saved:
            self.refresh_products()

    def edit_product(self) -> None:
        code = self.selected_product_code()
        if not code:
            messagebox.showinfo("Producto", "Seleccione un producto.")
            return
        row = self.conn.execute("SELECT * FROM products WHERE code = ?", (code,)).fetchone()
        if row is None:
            return
        dialog = SimpleProductDialog(self, self.conn, self.theme_name, dict(row))
        self.wait_window(dialog)
        if dialog.saved:
            self.refresh_products()

    def delete_product(self) -> None:
        code = self.selected_product_code()
        if not code:
            messagebox.showinfo("Producto", "Seleccione un producto.")
            return
        master = ask_secret(self, "Clave maestra", "Clave maestra:", theme_name=self.theme_name)
        master_hash = get_setting(self.conn, "master_hash", "")
        if not master or not verify_secret(master, master_hash):
            messagebox.showerror("Clave", "Clave incorrecta.")
            return
        if not messagebox.askyesno("Eliminar", "Esta seguro de eliminar este producto?"):
            return
        self.conn.execute("DELETE FROM products WHERE code = ?", (code,))
        self.conn.commit()
        self.refresh_products()

    def set_report_range(self, option: str) -> None:
        today = date.today()
        if option == "today":
            start = end = today
        elif option == "yesterday":
            start = end = today - timedelta(days=1)
        elif option == "week":
            start = today - timedelta(days=today.weekday())
            end = today
        elif option == "month":
            start = today.replace(day=1)
            end = today
        else:
            start = today.replace(month=1, day=1)
            end = today
        self.report_range = (start, end)
        self.refresh_report()

    def custom_report_range(self) -> None:
        picker = DateRangePicker(self, self.theme_name, self.report_range[0], self.report_range[1])
        self.wait_window(picker)
        if picker.result is None:
            return
        self.report_range = picker.result
        play_sound(self.conn, "tap")
        self.refresh_report()

    def refresh_report(self) -> None:
        if not hasattr(self, "report_panel"):
            return
        for child in self.report_panel.winfo_children():
            child.destroy()
        c = self.colors
        start, end = self.report_range
        start_dt = f"{start.isoformat()}T00:00:00"
        end_dt = f"{end.isoformat()}T23:59:59"
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count, COALESCE(SUM(total), 0) AS total, COALESCE(AVG(total), 0) AS average,
                   COALESCE(SUM(cash), 0) AS cash, COALESCE(SUM(nequi), 0) AS nequi,
                   COALESCE(SUM(pse), 0) AS pse, COALESCE(SUM(card), 0) AS card
            FROM sales
            WHERE created_at BETWEEN ? AND ? AND status = 'COMPLETED'
            """,
            (start_dt, end_dt),
        ).fetchone()
        expense_row = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE created_at BETWEEN ? AND ?
            """,
            (start_dt, end_dt),
        ).fetchone()
        brand_payment_row = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM brand_payments
            WHERE created_at BETWEEN ? AND ?
            """,
            (start_dt, end_dt),
        ).fetchone()
        cost_row = self.conn.execute(
            """
            SELECT COALESCE(SUM(si.cost * si.quantity), 0) AS cost_sum
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.created_at BETWEEN ? AND ? AND s.status = 'COMPLETED'
            """,
            (start_dt, end_dt),
        ).fetchone()
        total = float(row["total"] or 0)
        expenses_total = float(expense_row["total"] or 0)
        brand_payments_total = float(brand_payment_row["total"] or 0)
        gross_profit = total - float(cost_row["cost_sum"] or 0)
        net_profit = gross_profit - expenses_total - brand_payments_total
        values = [
            ("TOTAL VENDIDO", money(total)),
            ("NUMERO DE VENTAS", str(int(row["count"] or 0))),
            ("PROMEDIO POR VENTA", money(row["average"])),
            ("EFECTIVO", self._percent(row["cash"], total)),
            ("NEQUI", self._percent(row["nequi"], total)),
            ("GASTOS GENERALES", money(expenses_total)),
            ("PAGOS A PROVEEDORES", money(brand_payments_total)),
            ("UTILIDAD BRUTA", money(gross_profit)),
            ("UTILIDAD NETA", money(net_profit)),
        ]
        self.current_report_rows = values
        tk.Label(
            self.report_panel,
            text=f"Fechas: {start.isoformat()} a {end.isoformat()}",
            bg=c["panel"],
            fg=c["muted"],
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(14, 8))

        holder = themed_frame(self.report_panel, self.theme_name, panel=True)
        holder.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        canvas = tk.Canvas(holder, bg=c["panel"], highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scroll.set)
        body = themed_frame(canvas, self.theme_name, panel=True)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")

        for label, value in values:
            tk.Label(body, text=f"{label}: {value}", bg=c["panel"], fg=c["text"], font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=18, pady=6)

        def _sync(_event=None) -> None:
            canvas.itemconfigure(window_id, width=canvas.winfo_width())
            canvas.configure(scrollregion=canvas.bbox("all"))

        body.bind("<Configure>", _sync)
        canvas.bind("<Configure>", _sync)

    def _percent(self, amount: float, total: float) -> str:
        value = float(amount or 0)
        pct = 0 if total <= 0 else round((value / total) * 100)
        return f"{money(value)} ({pct}%)"

    def export_report(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Guardar reporte",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="reporte_arezone.csv",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Dato", "Valor"])
            writer.writerows(getattr(self, "current_report_rows", []))
        messagebox.showinfo("Reporte", "Reporte guardado.")

    def print_report(self) -> None:
        reports_dir = DATA_DIR / "reportes"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        lines = [f"{label}: {value}" for label, value in getattr(self, "current_report_rows", [])]
        path.write_text("\n".join(lines), encoding="utf-8")
        if try_print_ticket(path, get_setting(self.conn, "printer_port", "USB") or "USB"):
            messagebox.showinfo("Imprimir", "Reporte enviado a la impresora.")
        else:
            messagebox.showwarning("Imprimir", "No se pudo enviar a la impresora. Revise la configuracion.")

    def chart_report(self) -> None:
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except Exception:
            messagebox.showwarning("Grafica", "Instale matplotlib para ver graficas.")
            return
        start, end = self.report_range
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(cash), 0) AS cash, COALESCE(SUM(nequi), 0) AS nequi
            FROM sales
            WHERE created_at BETWEEN ? AND ? AND status = 'COMPLETED'
            """,
            (f"{start.isoformat()}T00:00:00", f"{end.isoformat()}T23:59:59"),
        ).fetchone()
        labels = ["Efectivo", "Nequi"]
        values = [float(row["cash"] or 0), float(row["nequi"] or 0)]
        if sum(values) <= 0:
            messagebox.showinfo("Grafica", "No hay datos para graficar.")
            return
        window = tk.Toplevel(self)
        window.title("Grafica de pagos")
        fit_window(window, 940, 640, min_width=820, min_height=560)
        figure = Figure(figsize=(8, 5), dpi=100)
        ax = figure.add_subplot(111)
        colors = ["#22c55e", "#0ea5e9"]
        ax.pie(values, labels=labels, autopct="%1.0f%%", startangle=90, colors=colors, wedgeprops={"linewidth": 1, "edgecolor": "white"})
        ax.set_title("Distribucion de pagos", fontsize=16, fontweight="bold")
        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _range_today(self) -> tuple[date, date]:
        today = date.today()
        return today, today

    def exit_module(self) -> None:
        if messagebox.askyesno("Salir", "Esta seguro de salir?"):
            self.on_logout()


class SimpleProductDialog(tk.Toplevel, ThemeMixin):
    def __init__(
        self,
        master,
        conn: sqlite3.Connection,
        theme_name: str,
        product: dict | None = None,
        initial_code: str = "",
    ) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.product = product
        self.original_code = (product or {}).get("code", "")
        self.saved = False
        self.vars = {
            "code": tk.StringVar(value=(product or {}).get("code", initial_code)),
            "alt_codes": tk.StringVar(value=(product or {}).get("alt_codes", "")),
            "name": tk.StringVar(value=(product or {}).get("name", "")),
            "brand": tk.StringVar(value=(product or {}).get("brand", "")),
            "category": tk.StringVar(value=(product or {}).get("category", "")),
            "price": tk.StringVar(value=str((product or {}).get("price_public", ""))),
            "stock": tk.StringVar(value=str((product or {}).get("stock", 0))),
        }
        self.title("Producto")
        fit_window(self, 1080, 900, min_width=980, min_height=820)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        self._load_catalogs()
        self._bind_uppercase()
        self.bind("<Return>", lambda _event: self.save())
        self.bind("<Escape>", lambda _event: self.destroy())
        pop_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        panel = themed_frame(self, self.theme_name, panel=True, border=True)
        panel.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        panel.columnconfigure((0, 1, 2), weight=1)

        tk.Label(
            panel,
            text="AGREGAR PRODUCTO" if not self.product else "EDITAR PRODUCTO",
            bg=c["panel"],
            fg=c["text"],
            font=FONT_TITLE,
        ).grid(row=0, column=0, columnspan=3, pady=18)

        tk.Label(panel, text="REFERENCIA", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=1, column=0, sticky="w", padx=20, pady=8)
        tk.Entry(
            panel,
            textvariable=self.vars["code"],
            font=("Segoe UI", 20, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
        ).grid(row=1, column=1, columnspan=2, sticky="ew", padx=20, pady=8, ipady=9)

        tk.Label(panel, text="CODIGOS ALTERNOS", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=2, column=0, sticky="w", padx=20, pady=8)
        tk.Entry(
            panel,
            textvariable=self.vars["alt_codes"],
            font=("Segoe UI", 16, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
        ).grid(row=2, column=1, columnspan=2, sticky="ew", padx=20, pady=8, ipady=9)
        tk.Label(
            panel,
            text="Si pegas varios codigos, el primero queda como referencia principal.",
            bg=c["panel"],
            fg=c["muted"],
            font=("Segoe UI", 12, "bold"),
        ).grid(row=3, column=1, columnspan=2, sticky="w", padx=20)

        tk.Label(panel, text="NOMBRE", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=4, column=0, sticky="w", padx=20, pady=8)
        tk.Entry(
            panel,
            textvariable=self.vars["name"],
            font=("Segoe UI", 20, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
        ).grid(row=4, column=1, columnspan=2, sticky="ew", padx=20, pady=8, ipady=9)

        tk.Label(panel, text="MARCA", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=5, column=0, sticky="w", padx=20, pady=8)
        self.brand_combo = ttk.Combobox(panel, textvariable=self.vars["brand"], state="normal", font=("Segoe UI", 15, "bold"))
        self.brand_combo.grid(row=5, column=1, sticky="ew", padx=(20, 10), pady=8, ipady=6)
        big_button(panel, "NUEVA MARCA", self.add_brand, self.theme_name, height=1).grid(row=5, column=2, sticky="ew", padx=(0, 20), pady=8)

        tk.Label(panel, text="CATEGORIA", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=6, column=0, sticky="w", padx=20, pady=8)
        self.category_combo = ttk.Combobox(panel, textvariable=self.vars["category"], state="normal", font=("Segoe UI", 15, "bold"))
        self.category_combo.grid(row=6, column=1, sticky="ew", padx=(20, 10), pady=8, ipady=6)
        big_button(panel, "NUEVA CATEGORIA", self.add_category, self.theme_name, height=1).grid(row=6, column=2, sticky="ew", padx=(0, 20), pady=8)

        tk.Label(panel, text="PRECIO", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=7, column=0, sticky="w", padx=20, pady=8)
        tk.Entry(
            panel,
            textvariable=self.vars["price"],
            font=("Segoe UI", 20, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
        ).grid(row=7, column=1, columnspan=2, sticky="ew", padx=20, pady=8, ipady=9)

        tk.Label(panel, text="INVENTARIO", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=8, column=0, sticky="w", padx=20, pady=8)
        tk.Entry(
            panel,
            textvariable=self.vars["stock"],
            font=("Segoe UI", 20, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
        ).grid(row=8, column=1, columnspan=2, sticky="ew", padx=20, pady=8, ipady=9)

        buttons = themed_frame(panel, self.theme_name, panel=True)
        buttons.grid(row=9, column=0, columnspan=3, sticky="ew", padx=20, pady=20)
        buttons.columnconfigure((0, 1), weight=1)
        big_button(buttons, "GUARDAR", self.save, self.theme_name).grid(row=0, column=0, sticky="ew", padx=8)
        big_button(buttons, "SALIR", self.destroy, self.theme_name, bg=c["danger"], fg="#ffffff").grid(row=0, column=1, sticky="ew", padx=8)

    def _bind_uppercase(self) -> None:
        for key in ("code", "alt_codes", "name", "brand", "category"):
            entry_var = self.vars[key]
            entry_var.trace_add("write", lambda *_args, k=key: self._enforce_uppercase(k))

    def _enforce_uppercase(self, key: str) -> None:
        value = self.vars[key].get()
        upper = value.upper()
        if value != upper:
            self.vars[key].set(upper)

    def _load_catalogs(self) -> None:
        brands = [row["name"] for row in self.conn.execute("SELECT name FROM product_brands ORDER BY name").fetchall()]
        categories = [row["name"] for row in self.conn.execute("SELECT name FROM product_categories ORDER BY name").fetchall()]
        self.brand_combo["values"] = brands
        self.category_combo["values"] = categories

    def add_brand(self) -> None:
        name = simpledialog.askstring("Marca", "Nombre de la marca:")
        if not name:
            return
        value = name.strip().upper()
        if not value:
            return
        self.conn.execute("INSERT OR IGNORE INTO product_brands(name) VALUES(?)", (value,))
        self.conn.commit()
        self.vars["brand"].set(value)
        self._load_catalogs()

    def add_category(self) -> None:
        name = simpledialog.askstring("Categoria", "Nombre de la categoria:")
        if not name:
            return
        value = name.strip().upper()
        if not value:
            return
        self.conn.execute("INSERT OR IGNORE INTO product_categories(name) VALUES(?)", (value,))
        self.conn.commit()
        self.vars["category"].set(value)
        self._load_catalogs()

    def save(self) -> None:
        code, alt_codes = split_primary_and_alternates(self.vars["code"].get(), self.vars["alt_codes"].get())
        name = self.vars["name"].get().strip().upper()
        brand = self.vars["brand"].get().strip().upper()
        category = self.vars["category"].get().strip().upper()
        price = parse_amount(self.vars["price"].get())
        stock = parse_amount(self.vars["stock"].get())
        if not code or not name or price <= 0:
            play_sound(self.conn, "warn")
            messagebox.showwarning("Producto", "Complete referencia, nombre y precio.")
            return
        if not messagebox.askyesno("Guardar", "Â¿EstÃ¡ seguro de guardar este producto?"):
            return
        now = now_text()

        self.conn.execute("INSERT OR IGNORE INTO product_brands(name) VALUES(?)", (brand,)) if brand else None
        self.conn.execute("INSERT OR IGNORE INTO product_categories(name) VALUES(?)", (category,)) if category else None

        if self.product:
            if code != self.original_code:
                exists = self.conn.execute("SELECT code FROM products WHERE code = ?", (code,)).fetchone()
                if exists:
                    play_sound(self.conn, "error")
                    messagebox.showwarning("Producto", "La nueva referencia ya existe.")
                    return
            self.conn.execute(
                """
                UPDATE products
                SET code = ?, alt_codes = ?, name = ?, brand = ?, category = ?, stock = ?,
                    price_public = ?, price_1 = ?, price_2 = ?, updated_at = ?
                WHERE code = ?
                """,
                (code, alt_codes, name, brand, category, stock, price, price, price, now, self.original_code),
            )
        else:
            exists = self.conn.execute("SELECT code FROM products WHERE code = ?", (code,)).fetchone()
            if exists:
                play_sound(self.conn, "warn")
                messagebox.showwarning("Producto", "Ya existe un producto con esa referencia.")
                return
            self.conn.execute(
                """
                INSERT INTO products (
                    code, alt_codes, name, brand, category, stock, cost, price_public, price_1, price_2, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                """,
                (code, alt_codes, name, brand, category, stock, price, price, price, now, now),
            )
        self.conn.commit()
        self.saved = True
        play_sound(self.conn, "ok")
        self.destroy()


class ProductPickerDialog(tk.Toplevel, ThemeMixin):
    def __init__(self, master, conn: sqlite3.Connection, theme_name: str, query: str = "") -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.selected_product: dict | None = None
        self.query_var = tk.StringVar(value=query)
        self.title("Buscar producto")
        fit_window(self, 900, 620, min_width=840, min_height=560)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        self.search()
        self.bind("<Return>", lambda _event: self.select())
        self.bind("<Escape>", lambda _event: self.destroy())
        fade_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        tk.Label(self, text="BUSCAR PRODUCTO", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=18, pady=15)
        top = themed_frame(self, self.theme_name)
        top.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        top.columnconfigure(0, weight=1)
        tk.Entry(top, textvariable=self.query_var, font=("Segoe UI", 20, "bold"), bg=c["input_bg"], fg=c["input_text"], insertbackground=c["input_text"]).grid(row=0, column=0, sticky="ew", ipady=12, padx=(0, 8))
        big_button(top, "BUSCAR", self.search, self.theme_name, height=1).grid(row=0, column=1, sticky="ew")
        self.tree = ttk.Treeview(self, columns=("code", "name", "price"), show="headings")
        self.tree.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        for col, title, width in [("code", "CODIGO", 180), ("name", "PRODUCTO", 480), ("price", "PRECIO", 160)]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="e" if col == "price" else "w")
        set_tree_theme(self.tree, self.theme_name)
        self.tree.bind("<Double-1>", lambda _event: self.select())
        buttons = themed_frame(self, self.theme_name)
        buttons.grid(row=3, column=0, sticky="ew", padx=18, pady=15)
        buttons.columnconfigure((0, 1), weight=1)
        big_button(buttons, "AGREGAR", self.select, self.theme_name).grid(row=0, column=0, sticky="ew", padx=8)
        big_button(buttons, "VOLVER", self.destroy, self.theme_name, bg=c["danger"], fg="#ffffff").grid(row=0, column=1, sticky="ew", padx=8)

    def search(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        query = f"%{self.query_var.get().strip()}%"
        rows = self.conn.execute(
            """
            SELECT * FROM products
            WHERE code LIKE ? OR name LIKE ? OR brand LIKE ? OR category LIKE ? OR COALESCE(alt_codes, '') LIKE ?
            ORDER BY name
            LIMIT 100
            """,
            (query, query, query, query, query),
        ).fetchall()
        for index, row in enumerate(rows):
            self.tree.insert("", "end", iid=row["code"], tags=("even" if index % 2 == 0 else "odd",), values=(row["code"], row["name"], money(row["price_public"])))

    def select(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        row = self.conn.execute("SELECT * FROM products WHERE code = ?", (selected[0],)).fetchone()
        self.selected_product = dict(row) if row else None
        play_sound(self.conn, "ok")
        self.destroy()


class ImportingWindow(tk.Toplevel, ThemeMixin):
    def __init__(self, master, conn: sqlite3.Connection, theme_name: str, path: Path, on_done: Callable[[], None] | None = None) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.path = path
        self.on_done = on_done
        self.title("Importando productos")
        fit_window(self, 820, 480, min_width=760, min_height=420)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        pop_in_window(self)
        self.after(400, self.run_import)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        tk.Label(self, text="IMPORTANDO PRODUCTOS", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, pady=(28, 12))
        self.status = tk.Label(self, text=f"Archivo encontrado:\n{self.path}", bg=c["bg"], fg=c["text"], font=("Segoe UI", 16, "bold"))
        self.status.grid(row=1, column=0, padx=30, pady=12)
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", padx=60, pady=18, ipady=10)
        self.progress.start(10)

    def run_import(self) -> None:
        result = migrate_inventory(self.path, self.conn)
        self.progress.stop()
        if result.errors and result.total_ok == 0:
            messagebox.showerror("Importar", "\n".join(result.errors[:5]))
            self.destroy()
            return
        messagebox.showinfo(
            "Importar",
            f"Ã‚Â¡SE IMPORTARON {result.imported} PRODUCTOS!\nActualizados: {result.updated}\nOmitidos: {result.skipped}",
        )
        if self.on_done:
            self.on_done()
        self.destroy()


class PrinterSettingsWindow(tk.Toplevel, ThemeMixin):
    def __init__(self, master, conn: sqlite3.Connection, theme_name: str) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.port_var = tk.StringVar(value=get_setting(conn, "printer_port", "USB") or "USB")
        self.print_var = tk.IntVar(value=int(get_setting(conn, "auto_print", "1") == "1"))
        self.drawer_var = tk.IntVar(value=int(get_setting(conn, "auto_open_drawer", "1") == "1"))
        self.title("Impresora")
        fit_window(self, 920, 660, min_width=860, min_height=600)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        pop_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        tk.Label(self, text="IMPRESORA", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, pady=22)
        box = themed_frame(self, self.theme_name, panel=True, border=True)
        box.grid(row=1, column=0, sticky="ew", padx=35, pady=10)
        for index, port in enumerate(("USB", "COM1", "COM2", "COM3")):
            tk.Radiobutton(box, text=port, variable=self.port_var, value=port, bg=c["panel"], fg=c["text"], selectcolor=c["panel_alt"], font=FONT_BIG).grid(row=index, column=0, sticky="w", padx=25, pady=8)
        tk.Checkbutton(box, text="Imprimir siempre que venda", variable=self.print_var, bg=c["panel"], fg=c["text"], selectcolor=c["panel_alt"], font=FONT_BIG).grid(row=4, column=0, sticky="w", padx=25, pady=8)
        tk.Checkbutton(box, text="Abrir caja siempre que venda", variable=self.drawer_var, bg=c["panel"], fg=c["text"], selectcolor=c["panel_alt"], font=FONT_BIG).grid(row=5, column=0, sticky="w", padx=25, pady=8)
        buttons = themed_frame(self, self.theme_name)
        buttons.grid(row=2, column=0, sticky="ew", padx=35, pady=20)
        buttons.columnconfigure((0, 1, 2, 3), weight=1)
        for col, (text, command) in enumerate([("PROBAR", self.test_print), ("ABRIR CAJON", self.open_drawer), ("GUARDAR", self.save), ("VOLVER", self.destroy)]):
            big_button(buttons, text, command, self.theme_name, height=1).grid(row=0, column=col, sticky="ew", padx=5)

    def test_print(self) -> None:
        ticket = build_sample_ticket(self.conn)
        path = save_ticket("PRUEBA-IMPRESORA", ticket)
        sent = try_print_ticket(path, self.port_var.get())
        if sent:
            messagebox.showinfo("Impresora", "Prueba enviada a la impresora.")
        else:
            messagebox.showinfo("Impresora", f"Prueba guardada:\n{path}")

    def open_drawer(self) -> None:
        if try_open_drawer(self.port_var.get()):
            messagebox.showinfo("Caja", "Orden enviada al cajon.")
            return
        path = DATA_DIR / "caja" / "prueba_abrir_caja.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ABRIR CAJA", encoding="utf-8")
        messagebox.showinfo("Caja", "Orden de apertura guardada.")

    def save(self) -> None:
        set_setting(self.conn, "printer_port", self.port_var.get())
        set_setting(self.conn, "auto_print", str(self.print_var.get()))
        set_setting(self.conn, "auto_open_drawer", str(self.drawer_var.get()))
        messagebox.showinfo("Impresora", "Configuracion guardada.")


class AutostartWindow(tk.Toplevel, ThemeMixin):
    def __init__(self, master, conn: sqlite3.Connection, theme_name: str) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.autostart_var = tk.IntVar(value=int(get_setting(conn, "autostart", "0") == "1"))
        self.fullscreen_var = tk.IntVar(value=int(get_setting(conn, "fullscreen", "0") == "1"))
        self.title("Autoarranque")
        fit_window(self, 1040, 700, min_width=920, min_height=620)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        pop_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        tk.Label(self, text="CONFIGURACION", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, pady=22)
        box = themed_frame(self, self.theme_name, panel=True, border=True)
        box.grid(row=1, column=0, sticky="ew", padx=35, pady=10)
        tk.Checkbutton(
            box,
            text="Iniciar AREZONE cuando encienda el computador",
            variable=self.autostart_var,
            bg=c["panel"],
            fg=c["text"],
            selectcolor=c["panel_alt"],
            font=("Segoe UI", 16, "bold"),
            wraplength=840,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=25, pady=16)
        tk.Checkbutton(
            box,
            text="Pantalla completa",
            variable=self.fullscreen_var,
            bg=c["panel"],
            fg=c["text"],
            selectcolor=c["panel_alt"],
            font=("Segoe UI", 16, "bold"),
            wraplength=840,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=25, pady=16)
        buttons = themed_frame(self, self.theme_name)
        buttons.grid(row=2, column=0, sticky="ew", padx=35, pady=20)
        buttons.columnconfigure((0, 1, 2), weight=1)
        big_button(buttons, "GUARDAR", self.save, self.theme_name).grid(row=0, column=0, sticky="ew", padx=6)
        big_button(buttons, "REINICIAR", self.restart, self.theme_name).grid(row=0, column=1, sticky="ew", padx=6)
        big_button(buttons, "VOLVER", self.destroy, self.theme_name).grid(row=0, column=2, sticky="ew", padx=6)

    def save(self) -> None:
        set_setting(self.conn, "autostart", str(self.autostart_var.get()))
        set_setting(self.conn, "fullscreen", str(self.fullscreen_var.get()))
        configure_autostart(self.autostart_var.get() == 1)
        self.winfo_toplevel().attributes("-fullscreen", self.fullscreen_var.get() == 1)
        messagebox.showinfo("Configuracion", "Configuracion guardada.")

    def restart(self) -> None:
        if messagebox.askyesno("Reiniciar", "Esta seguro de reiniciar AREZONE?"):
            self.winfo_toplevel().destroy()


class NightModeWindow(tk.Toplevel, ThemeMixin):
    def __init__(self, master, conn: sqlite3.Connection, theme_name: str) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.enabled_var = tk.IntVar(value=int(get_setting(conn, "auto_night_enabled", "1") == "1"))
        self.start_var = tk.StringVar(value=get_setting(conn, "night_start", "18:00") or "18:00")
        self.end_var = tk.StringVar(value=get_setting(conn, "night_end", "06:00") or "06:00")
        self.title("Horario modo noche")
        fit_window(self, 920, 560, min_width=860, min_height=520)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        pop_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        tk.Label(self, text="HORARIO NOCHE", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, pady=22)
        box = themed_frame(self, self.theme_name, panel=True, border=True)
        box.grid(row=1, column=0, sticky="ew", padx=35, pady=10)
        box.columnconfigure(1, weight=1)
        tk.Checkbutton(
            box,
            text="Activar modo noche automatico",
            variable=self.enabled_var,
            bg=c["panel"],
            fg=c["text"],
            selectcolor=c["panel_alt"],
            font=FONT_BIG,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=25, pady=16)
        tk.Label(box, text="Empieza", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=1, column=0, sticky="w", padx=25, pady=10)
        tk.Entry(box, textvariable=self.start_var, font=("Segoe UI", 20, "bold"), bg=c["input_bg"], fg=c["input_text"]).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=25,
            pady=10,
            ipady=8,
        )
        tk.Label(box, text="Termina", bg=c["panel"], fg=c["text"], font=FONT_BIG).grid(row=2, column=0, sticky="w", padx=25, pady=10)
        tk.Entry(box, textvariable=self.end_var, font=("Segoe UI", 20, "bold"), bg=c["input_bg"], fg=c["input_text"]).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=25,
            pady=10,
            ipady=8,
        )
        tk.Label(box, text="Formato: 18:00 y 06:00", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 16, "bold")).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            padx=25,
            pady=(0, 12),
        )
        buttons = themed_frame(self, self.theme_name)
        buttons.grid(row=2, column=0, sticky="ew", padx=35, pady=20)
        buttons.columnconfigure((0, 1), weight=1)
        big_button(buttons, "GUARDAR", self.save, self.theme_name).grid(row=0, column=0, sticky="ew", padx=6)
        big_button(buttons, "VOLVER", self.destroy, self.theme_name).grid(row=0, column=1, sticky="ew", padx=6)

    def save(self) -> None:
        if parse_time_value(self.start_var.get()) is None or parse_time_value(self.end_var.get()) is None:
            messagebox.showwarning("Horario", "Use horas validas, por ejemplo 18:00 y 06:00.")
            return
        set_setting(self.conn, "auto_night_enabled", str(self.enabled_var.get()))
        set_setting(self.conn, "night_start", self.start_var.get().strip())
        set_setting(self.conn, "night_end", self.end_var.get().strip())
        messagebox.showinfo("Horario", "Horario guardado.")
        self.destroy()


class BrandPaymentsWindow(tk.Toplevel, ThemeMixin):
    def __init__(self, master, conn: sqlite3.Connection, theme_name: str) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.brand_var = tk.StringVar()
        self.amount_var = tk.StringVar(value="0")
        self.note_var = tk.StringVar()
        self.title("Pagos a proveedores")
        fit_window(self, 1120, 780, min_width=1040, min_height=720)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        self.refresh()
        pop_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        tk.Label(self, text="PAGOS A PROVEEDORES", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))

        root = themed_frame(self, self.theme_name, panel=True, border=True)
        root.grid(row=1, column=0, sticky="nsew", padx=18, pady=8)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        form = themed_frame(root, self.theme_name, panel=True)
        form.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        form.columnconfigure((1, 3), weight=1)
        tk.Label(form, text="Marca", bg=c["panel"], fg=c["text"], font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.brand_combo = ttk.Combobox(form, textvariable=self.brand_var, state="normal", font=("Segoe UI", 13, "bold"))
        self.brand_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=6, ipady=4)
        tk.Label(form, text="Monto", bg=c["panel"], fg=c["text"], font=("Segoe UI", 14, "bold")).grid(row=0, column=2, sticky="w", padx=8, pady=6)
        tk.Entry(form, textvariable=self.amount_var, font=("Segoe UI", 14, "bold"), bg=c["input_bg"], fg=c["input_text"]).grid(
            row=0,
            column=3,
            sticky="ew",
            padx=8,
            pady=6,
            ipady=4,
        )
        tk.Label(form, text="Nota", bg=c["panel"], fg=c["text"], font=("Segoe UI", 14, "bold")).grid(row=1, column=0, sticky="w", padx=8, pady=6)
        tk.Entry(form, textvariable=self.note_var, font=("Segoe UI", 13, "bold"), bg=c["input_bg"], fg=c["input_text"]).grid(
            row=1,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=8,
            pady=6,
            ipady=4,
        )

        actions = themed_frame(root, self.theme_name, panel=True)
        actions.grid(row=1, column=0, sticky="ew", padx=14, pady=6)
        actions.columnconfigure((0, 1, 2), weight=1)
        big_button(actions, "GUARDAR PAGO", self.add_payment, self.theme_name, height=1).grid(row=0, column=0, sticky="ew", padx=6)
        big_button(actions, "ELIMINAR SELECCION", self.delete_selected, self.theme_name, height=1).grid(row=0, column=1, sticky="ew", padx=6)
        big_button(actions, "VOLVER", self.destroy, self.theme_name, height=1, bg=c["danger"], fg="#ffffff").grid(row=0, column=2, sticky="ew", padx=6)

        self.tree = ttk.Treeview(root, columns=("date", "brand", "amount", "note"), show="headings", selectmode="browse")
        self.tree.grid(row=2, column=0, sticky="nsew", padx=14, pady=(6, 12))
        for col, text, width in [
            ("date", "FECHA", 170),
            ("brand", "MARCA", 220),
            ("amount", "MONTO", 140),
            ("note", "NOTA", 360),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="e" if col == "amount" else "w")
        set_tree_theme(self.tree, self.theme_name)
        self.total_label = tk.Label(root, text="", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 13, "bold"))
        self.total_label.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 10))

    def _load_brand_values(self) -> None:
        rows = self.conn.execute(
            """
            SELECT DISTINCT UPPER(TRIM(name)) AS value FROM product_brands
            UNION
            SELECT DISTINCT UPPER(TRIM(brand)) AS value FROM products WHERE TRIM(COALESCE(brand, '')) <> ''
            ORDER BY value
            """
        ).fetchall()
        self.brand_combo["values"] = [row["value"] for row in rows if row["value"]]

    def add_payment(self) -> None:
        brand = self.brand_var.get().strip().upper()
        amount = parse_amount(self.amount_var.get())
        note = self.note_var.get().strip().upper()
        if not brand or amount <= 0:
            play_sound(self.conn, "warn")
            messagebox.showwarning("Pagos", "Ingrese marca y monto vÃ¡lido.")
            return
        self.conn.execute("INSERT OR IGNORE INTO product_brands(name) VALUES(?)", (brand,))
        self.conn.execute(
            "INSERT INTO brand_payments(created_at, brand, amount, note) VALUES(?, ?, ?, ?)",
            (now_text(), brand, amount, note),
        )
        self.conn.commit()
        self.amount_var.set("0")
        self.note_var.set("")
        self.brand_var.set(brand)
        play_sound(self.conn, "ok")
        self.refresh()

    def delete_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        if not messagebox.askyesno("Pagos", "Â¿Eliminar este pago seleccionado?"):
            return
        self.conn.execute("DELETE FROM brand_payments WHERE id = ?", (selected[0],))
        self.conn.commit()
        play_sound(self.conn, "ok")
        self.refresh()

    def refresh(self) -> None:
        self._load_brand_values()
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = self.conn.execute(
            """
            SELECT id, created_at, brand, amount, note
            FROM brand_payments
            ORDER BY id DESC
            LIMIT 400
            """
        ).fetchall()
        total = 0.0
        for index, row in enumerate(rows):
            total += float(row["amount"] or 0)
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                tags=("even" if index % 2 == 0 else "odd",),
                values=(row["created_at"], row["brand"], money(row["amount"]), row["note"] or ""),
            )
        self.total_label.config(text=f"Total pagos a proveedores registrados: {money(total)}")


class InvoiceVoidWindow(tk.Toplevel, ThemeMixin):
    def __init__(
        self,
        master,
        conn: sqlite3.Connection,
        theme_name: str,
        on_annulled: Callable[[], None] | None = None,
    ) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        self.conn = conn
        self.on_annulled = on_annulled
        self.query_var = tk.StringVar()
        self.title("Anular factura")
        fit_window(self, 1260, 780, min_width=1120, min_height=700)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        self.refresh()
        pop_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        tk.Label(self, text="ANULAR FACTURAS", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))

        top = themed_frame(self, self.theme_name, panel=True, border=True)
        top.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        top.columnconfigure(0, weight=1)
        tk.Entry(
            top,
            textvariable=self.query_var,
            font=("Segoe UI", 16, "bold"),
            bg=c["input_bg"],
            fg=c["input_text"],
            insertbackground=c["input_text"],
        ).grid(row=0, column=0, sticky="ew", padx=(14, 8), pady=12, ipady=7)
        big_button(top, "BUSCAR", self.refresh, self.theme_name, height=1).grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=12)

        body = themed_frame(self, self.theme_name, panel=True, border=True)
        body.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            body,
            columns=("invoice", "date", "seller", "customer", "total", "status", "reason"),
            show="headings",
            selectmode="browse",
        )
        self.tree.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        for col, text, width in [
            ("invoice", "FACTURA", 130),
            ("date", "FECHA", 175),
            ("seller", "VENDEDOR", 150),
            ("customer", "CLIENTE", 170),
            ("total", "TOTAL", 120),
            ("status", "ESTADO", 110),
            ("reason", "MOTIVO", 240),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="e" if col == "total" else "w")
        set_tree_theme(self.tree, self.theme_name)
        self.tree.bind("<Double-1>", lambda _event: self.show_selected_sale_detail())

        actions = themed_frame(self, self.theme_name, panel=True)
        actions.grid(row=3, column=0, sticky="ew", padx=18, pady=(8, 18))
        actions.columnconfigure((0, 1, 2, 3), weight=1)
        big_button(actions, "ANULAR FACTURA", self.annul_selected, self.theme_name, height=1, bg=c["danger"], fg="#ffffff").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=5,
        )
        big_button(actions, "VER DETALLE", self.show_selected_sale_detail, self.theme_name, height=1).grid(row=0, column=1, sticky="ew", padx=5)
        big_button(actions, "RECARGAR", self.refresh, self.theme_name, height=1).grid(row=0, column=2, sticky="ew", padx=5)
        big_button(actions, "CERRAR", self.destroy, self.theme_name, height=1).grid(row=0, column=3, sticky="ew", padx=5)

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        query = f"%{self.query_var.get().strip()}%"
        rows = self.conn.execute(
            """
            SELECT id, invoice_no, created_at, seller, customer, total, status, COALESCE(voided_reason, '') AS voided_reason
            FROM sales
            WHERE invoice_no LIKE ? OR seller LIKE ? OR customer LIKE ? OR COALESCE(voided_reason, '') LIKE ?
            ORDER BY id DESC
            LIMIT 400
            """,
            (query, query, query, query),
        ).fetchall()
        for index, row in enumerate(rows):
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                tags=("even" if index % 2 == 0 else "odd",),
                values=(
                    row["invoice_no"],
                    row["created_at"],
                    row["seller"] or "",
                    row["customer"] or "PARTICULAR",
                    money(row["total"]),
                    row["status"] or "COMPLETED",
                    row["voided_reason"] or "",
                ),
            )

    def annul_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            play_sound(self.conn, "warn")
            return
        sale_id = int(selected[0])
        sale = self.conn.execute(
            "SELECT id, invoice_no, status, total FROM sales WHERE id = ?",
            (sale_id,),
        ).fetchone()
        if sale is None:
            return
        if (sale["status"] or "COMPLETED") == "ANULADA":
            messagebox.showinfo("Factura", "Esta factura ya esta anulada.")
            return
        master = ask_secret(self, "Clave maestra", "Ingrese la clave maestra para anular:", theme_name=self.theme_name)
        if master is None:
            return
        master_hash = get_setting(self.conn, "master_hash", "")
        if not verify_secret(master, master_hash):
            play_sound(self.conn, "error")
            messagebox.showerror("Factura", "Clave maestra incorrecta.")
            return
        reason = simpledialog.askstring("Motivo", f"Motivo para anular {sale['invoice_no']}:", initialvalue="ERROR DE FACTURACION")
        if reason is None:
            return
        reason = reason.strip().upper() or "SIN MOTIVO"
        if not messagebox.askyesno("Anular factura", f"Â¿Anular la factura {sale['invoice_no']}?\n\nSe restaurara el inventario."):
            return
        voided_at = now_text()
        voided_by = get_setting(self.conn, "store_username", "") or get_setting(self.conn, "store_name", "") or "ADMIN"
        try:
            items = self.conn.execute(
                "SELECT code, quantity FROM sale_items WHERE sale_id = ?",
                (sale_id,),
            ).fetchall()
            for item in items:
                self.conn.execute(
                    "UPDATE products SET stock = COALESCE(stock, 0) + ? WHERE code = ?",
                    (float(item["quantity"] or 0), item["code"]),
                )
            self.conn.execute(
                """
                UPDATE sales
                SET status = 'ANULADA', voided_at = ?, voided_reason = ?, voided_by = ?
                WHERE id = ?
                """,
                (voided_at, reason, voided_by, sale_id),
            )
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            messagebox.showerror("Factura", f"No se pudo anular la factura.\n\n{exc}")
            return
        play_sound(self.conn, "ok")
        messagebox.showinfo("Factura", f"Factura {sale['invoice_no']} anulada.")
        self.refresh()
        if self.on_annulled:
            self.on_annulled()

    def show_selected_sale_detail(self) -> None:
        selected = self.tree.selection()
        if not selected:
            play_sound(self.conn, "warn")
            return
        sale_id = int(selected[0])
        sale = self.conn.execute(
            """
            SELECT invoice_no, created_at, seller, customer, subtotal, tax_total, total, status, COALESCE(voided_reason, '') AS voided_reason
            FROM sales
            WHERE id = ?
            """,
            (sale_id,),
        ).fetchone()
        if sale is None:
            return

        items = self.conn.execute(
            """
            SELECT code, name, quantity, unit_price, line_total
            FROM sale_items
            WHERE sale_id = ?
            """,
            (sale_id,),
        ).fetchall()

        c = self.colors
        detail = tk.Toplevel(self)
        detail.title(f"Detalle factura {sale['invoice_no']}")
        fit_window(detail, 1000, 640, min_width=900, min_height=520)
        detail.transient(self)
        detail.grab_set()
        detail.configure(bg=c['bg'])
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(1, weight=1)

        header = themed_frame(detail, self.theme_name, panel=True, border=True)
        header.grid(row=0, column=0, sticky='ew', padx=18, pady=(18, 8))
        header.columnconfigure((0, 1, 2), weight=1)
        tk.Label(header, text=f"FACTURA: {sale['invoice_no']}", bg=c['panel'], fg=c['text'], font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky='w', padx=12, pady=10)
        tk.Label(header, text=f"FECHA: {sale['created_at']}", bg=c['panel'], fg=c['muted'], font=("Segoe UI", 14, "bold")).grid(row=1, column=0, sticky='w', padx=12, pady=(0, 8))
        tk.Label(header, text=f"VENDEDOR: {sale['seller'] or ''}", bg=c['panel'], fg=c['muted'], font=("Segoe UI", 14, "bold")).grid(row=0, column=1, sticky='w', padx=12, pady=10)
        tk.Label(header, text=f"CLIENTE: {sale['customer'] or 'PARTICULAR'}", bg=c['panel'], fg=c['muted'], font=("Segoe UI", 14, "bold")).grid(row=1, column=1, sticky='w', padx=12, pady=(0, 8))
        tk.Label(header, text=f"ESTADO: {sale['status'] or 'COMPLETADA'}", bg=c['panel'], fg=c['muted'], font=("Segoe UI", 14, "bold")).grid(row=0, column=2, sticky='w', padx=12, pady=10)
        tk.Label(header, text=f"TOTAL: {money(sale['total'])}", bg=c['panel'], fg=c['text'], font=("Segoe UI", 18, "bold")).grid(row=1, column=2, sticky='w', padx=12, pady=(0, 8))

        body = themed_frame(detail, self.theme_name, panel=True, border=True)
        body.grid(row=1, column=0, sticky='nsew', padx=18, pady=8)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        columns = ("code", "name", "quantity", "unit_price", "line_total")
        tree = ttk.Treeview(body, columns=columns, show='headings', selectmode='browse')
        tree.grid(row=0, column=0, sticky='nsew', padx=14, pady=14)
        for col, text, width in [
            ("code", "CODIGO", 140),
            ("name", "PRODUCTO", 360),
            ("quantity", "CANT.", 90),
            ("unit_price", "PRECIO", 130),
            ("line_total", "TOTAL", 130),
        ]:
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor='e' if col in {"quantity", "unit_price", "line_total"} else 'w')
        set_tree_theme(tree, self.theme_name)

        for item in items:
            tree.insert(
                '',
                'end',
                values=(
                    item['code'],
                    item['name'],
                    number(item['quantity']),
                    money(item['unit_price']),
                    money(item['line_total']),
                ),
            )

        footer = themed_frame(detail, self.theme_name, panel=True, border=True)
        footer.grid(row=2, column=0, sticky='ew', padx=18, pady=(0, 18))
        footer.columnconfigure(0, weight=1)
        big_button(footer, 'CERRAR', detail.destroy, self.theme_name, height=1).grid(row=0, column=0, sticky='ew', padx=18, pady=12)
        pop_in_window(detail)


def configure_autostart(enabled: bool) -> None:
    startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup_dir.mkdir(parents=True, exist_ok=True)
    batch_path = startup_dir / "AREZONE.bat"
    if not enabled:
        if batch_path.exists():
            batch_path.unlink()
        return
    if getattr(sys, "frozen", False):
        command = f'start "" "{sys.executable}"'
    else:
        command = f'start "" "{sys.executable}" "{BASE_DIR / "main.py"}"'
    batch_path.write_text(f"@echo off\n{command}\n", encoding="utf-8")


def parse_time_value(value: str) -> int | None:
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M").time()
        return parsed.hour * 60 + parsed.minute
    except ValueError:
        return None


def expected_theme_for_time(night_start: str, night_end: str) -> str:
    start = parse_time_value(night_start)
    end = parse_time_value(night_end)
    if start is None or end is None:
        return "day"
    now = datetime.now()
    current = now.hour * 60 + now.minute
    if start <= end:
        is_night = start <= current < end
    else:
        is_night = current >= start or current < end
    return "night" if is_night else "day"

