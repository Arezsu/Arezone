from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date

from modules.theme import FONT_BIG, FONT_TITLE, ThemeMixin, big_button, fit_window, themed_frame
from modules.ui_fx import fade_in_window


class DateRangePicker(tk.Toplevel, ThemeMixin):
    def __init__(self, master, theme_name: str, start: date | None = None, end: date | None = None) -> None:
        self.theme_name = theme_name
        super().__init__(master)
        today = date.today()
        self.view_year = today.year
        self.view_month = today.month
        self.start_date = start
        self.end_date = end
        self.result: tuple[date, date] | None = None

        self.title("Elegir fechas")
        fit_window(self, 760, 600, min_width=700, min_height=560)
        self.transient(master)
        self.grab_set()
        self.apply_common_styles()
        self._build()
        self._render_days()
        self.bind("<Escape>", lambda _event: self.destroy())
        fade_in_window(self)

    def _build(self) -> None:
        c = self.colors
        self.configure(bg=c["bg"])
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        tk.Label(self, text="CALENDARIO DE FECHAS", bg=c["bg"], fg=c["text"], font=FONT_TITLE).grid(
            row=0,
            column=0,
            sticky="w",
            padx=18,
            pady=(16, 8),
        )

        top = themed_frame(self, self.theme_name, panel=True, border=True)
        top.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        top.columnconfigure(1, weight=1)
        big_button(top, "< MES", self.prev_month, self.theme_name, height=1).grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        self.month_title = tk.Label(top, text="", bg=c["panel"], fg=c["text"], font=FONT_BIG)
        self.month_title.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        big_button(top, "MES >", self.next_month, self.theme_name, height=1).grid(row=0, column=2, padx=6, pady=6, sticky="ew")

        self.grid_box = themed_frame(self, self.theme_name, panel=True, border=True)
        self.grid_box.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        self.grid_box.columnconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)
        self.grid_box.rowconfigure((1, 2, 3, 4, 5, 6), weight=1)

        bottom = themed_frame(self, self.theme_name, panel=True)
        bottom.grid(row=3, column=0, sticky="ew", padx=18, pady=(4, 14))
        bottom.columnconfigure((0, 1, 2), weight=1)
        self.selection_label = tk.Label(bottom, text="", bg=c["panel"], fg=c["muted"], font=("Segoe UI", 15, "bold"))
        self.selection_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(4, 10))
        big_button(bottom, "LIMPIAR", self.clear_selection, self.theme_name, height=1).grid(row=1, column=0, sticky="ew", padx=6)
        big_button(bottom, "ACEPTAR", self.accept, self.theme_name, height=1).grid(row=1, column=1, sticky="ew", padx=6)
        big_button(bottom, "VOLVER", self.destroy, self.theme_name, height=1, bg=c["danger"], fg="#ffffff").grid(
            row=1,
            column=2,
            sticky="ew",
            padx=6,
        )

    def prev_month(self) -> None:
        self.view_month -= 1
        if self.view_month < 1:
            self.view_month = 12
            self.view_year -= 1
        self._render_days()

    def next_month(self) -> None:
        self.view_month += 1
        if self.view_month > 12:
            self.view_month = 1
            self.view_year += 1
        self._render_days()

    def clear_selection(self) -> None:
        self.start_date = None
        self.end_date = None
        self._render_days()

    def pick_day(self, day: int) -> None:
        picked = date(self.view_year, self.view_month, day)
        if self.start_date is None or (self.start_date and self.end_date):
            self.start_date = picked
            self.end_date = None
        else:
            if picked < self.start_date:
                self.end_date = self.start_date
                self.start_date = picked
            else:
                self.end_date = picked
        self._render_days()

    def _is_selected(self, current: date) -> bool:
        if self.start_date is None:
            return False
        if self.end_date is None:
            return current == self.start_date
        return self.start_date <= current <= self.end_date

    def _render_days(self) -> None:
        c = self.colors
        for child in self.grid_box.winfo_children():
            child.destroy()

        self.month_title.config(text=f"{calendar.month_name[self.view_month].upper()} {self.view_year}")
        weekdays = ("LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM")
        for col, name in enumerate(weekdays):
            tk.Label(
                self.grid_box,
                text=name,
                bg=c["panel_alt"],
                fg=c["text"],
                font=("Segoe UI", 12, "bold"),
                padx=4,
                pady=6,
            ).grid(row=0, column=col, sticky="nsew", padx=2, pady=2)

        month_data = calendar.Calendar(firstweekday=0).monthdayscalendar(self.view_year, self.view_month)
        for row_idx, week in enumerate(month_data, start=1):
            for col_idx, day in enumerate(week):
                if day == 0:
                    tk.Label(self.grid_box, text="", bg=c["panel"]).grid(row=row_idx, column=col_idx, sticky="nsew", padx=2, pady=2)
                    continue
                current = date(self.view_year, self.view_month, day)
                selected = self._is_selected(current)
                bg = c["primary"] if selected else c["button"]
                fg = c["primary_text"] if selected else c["button_text"]
                tk.Button(
                    self.grid_box,
                    text=str(day),
                    command=lambda d=day: self.pick_day(d),
                    bg=bg,
                    fg=fg,
                    activebackground=c["primary"],
                    activeforeground=c["primary_text"],
                    relief="raised",
                    bd=2,
                    font=("Segoe UI", 12, "bold"),
                ).grid(row=row_idx, column=col_idx, sticky="nsew", padx=2, pady=2, ipady=4)

        if self.start_date and self.end_date:
            text = f"Desde: {self.start_date.isoformat()}  Hasta: {self.end_date.isoformat()}"
        elif self.start_date:
            text = f"Desde: {self.start_date.isoformat()}  (seleccione fecha final)"
        else:
            text = "Seleccione fecha inicial y fecha final."
        self.selection_label.config(text=text)

    def accept(self) -> None:
        if self.start_date is None:
            return
        final_end = self.end_date or self.start_date
        self.result = (self.start_date, final_end)
        self.destroy()
