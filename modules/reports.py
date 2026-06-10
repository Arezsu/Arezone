from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox, ttk

from modules.formatters import money, number
from modules.date_picker import DateRangePicker
from modules.theme import fit_window


class ReportsWindow(tk.Toplevel):
    def __init__(self, master, conn: sqlite3.Connection) -> None:
        super().__init__(master)
        self.conn = conn
        self.preset_var = tk.StringVar(value="Hoy")
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()
        self.total_var = tk.StringVar()
        self.count_var = tk.StringVar()
        self.avg_var = tk.StringVar()
        self.cost_var = tk.StringVar()
        self.expense_var = tk.StringVar()
        self.profit_var = tk.StringVar()

        self.title("Reportes AREZONE")
        fit_window(self, 1180, 760, min_width=1040, min_height=650)
        self.transient(master)
        self.grab_set()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self._build()
        self.apply_preset()

    def _build(self) -> None:
        filters = ttk.Frame(self, padding=10)
        filters.grid(row=0, column=0, sticky="ew")
        filters.columnconfigure(7, weight=1)

        ttk.Label(filters, text="Filtro").grid(row=0, column=0, padx=(0, 5))
        preset = ttk.Combobox(
            filters,
            textvariable=self.preset_var,
            values=("Hoy", "Semana", "Mes", "Ano", "Personalizado"),
            state="readonly",
            width=14,
        )
        preset.grid(row=0, column=1, padx=(0, 10))
        preset.bind("<<ComboboxSelected>>", lambda _event: self.apply_preset())

        ttk.Label(filters, text="Desde").grid(row=0, column=2, padx=(0, 5))
        ttk.Entry(filters, textvariable=self.from_var, width=12).grid(row=0, column=3, padx=(0, 10))
        ttk.Label(filters, text="Hasta").grid(row=0, column=4, padx=(0, 5))
        ttk.Entry(filters, textvariable=self.to_var, width=12).grid(row=0, column=5, padx=(0, 10))
        ttk.Button(filters, text="Actualizar", command=self.refresh).grid(row=0, column=6, padx=4)
        ttk.Button(filters, text="Elegir calendario", command=self.pick_range).grid(row=0, column=7, padx=4)
        ttk.Button(filters, text="Grafica ventas", command=self.chart_sales_by_day).grid(row=0, column=8, padx=4)
        ttk.Button(filters, text="Grafica pagos", command=self.chart_payments).grid(row=0, column=9, padx=4)

        cards = ttk.Frame(self, padding=(10, 0, 10, 10))
        cards.grid(row=1, column=0, sticky="ew")
        for col in range(6):
            cards.columnconfigure(col, weight=1)
        self._metric(cards, "Total vendido", self.total_var, 0)
        self._metric(cards, "Ventas", self.count_var, 1)
        self._metric(cards, "Promedio", self.avg_var, 2)
        self._metric(cards, "Costos", self.cost_var, 3)
        self._metric(cards, "Gastos", self.expense_var, 4)
        self._metric(cards, "Ganancia real", self.profit_var, 5)

        tabs = ttk.Notebook(self)
        tabs.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        products_tab = ttk.Frame(tabs)
        categories_tab = ttk.Frame(tabs)
        payments_tab = ttk.Frame(tabs)
        tabs.add(products_tab, text="Productos mas vendidos")
        tabs.add(categories_tab, text="Ingresos por categoria")
        tabs.add(payments_tab, text="Distribucion de pagos")

        self.product_tree = self._tree(
            products_tab,
            ("Producto", "Cantidad", "Ingreso"),
            (420, 120, 160),
        )
        self.category_tree = self._tree(
            categories_tab,
            ("Categoria", "Cantidad", "Ingreso"),
            (420, 120, 160),
        )
        self.payment_tree = self._tree(
            payments_tab,
            ("Metodo", "Total"),
            (320, 220),
        )

    def _metric(self, parent, title: str, variable: tk.StringVar, col: int) -> None:
        frame = tk.Frame(parent, bg="#f8fafc", bd=1, relief="solid")
        frame.grid(row=0, column=col, sticky="ew", padx=4)
        tk.Label(frame, text=title, bg="#f8fafc", fg="#52606d", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        tk.Label(frame, textvariable=variable, bg="#f8fafc", fg="#102a43", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=10, pady=(0, 8))

    def _tree(self, parent, headings: tuple[str, ...], widths: tuple[int, ...]) -> ttk.Treeview:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        columns = tuple(f"c{idx}" for idx, _ in enumerate(headings))
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        tree.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="e" if heading != headings[0] else "w")
        return tree

    def apply_preset(self) -> None:
        today = date.today()
        preset = self.preset_var.get()
        if preset == "Hoy":
            start = end = today
        elif preset == "Semana":
            start = today - timedelta(days=today.weekday())
            end = today
        elif preset == "Mes":
            start = today.replace(day=1)
            end = today
        elif preset == "Ano":
            start = today.replace(month=1, day=1)
            end = today
        else:
            return
        self.from_var.set(start.isoformat())
        self.to_var.set(end.isoformat())
        self.refresh()

    def pick_range(self) -> None:
        try:
            start = datetime.strptime(self.from_var.get(), "%Y-%m-%d").date()
            end = datetime.strptime(self.to_var.get(), "%Y-%m-%d").date()
        except ValueError:
            start = end = date.today()
        picker = DateRangePicker(self, "day", start, end)
        self.wait_window(picker)
        if picker.result is None:
            return
        start, end = picker.result
        self.preset_var.set("Personalizado")
        self.from_var.set(start.isoformat())
        self.to_var.set(end.isoformat())
        self.refresh()

    def range_values(self) -> tuple[str, str] | None:
        try:
            start = datetime.strptime(self.from_var.get(), "%Y-%m-%d").date()
            end = datetime.strptime(self.to_var.get(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showwarning("Fechas", "Use formato YYYY-MM-DD.")
            return None
        if start > end:
            messagebox.showwarning("Fechas", "La fecha inicial no puede ser mayor que la final.")
            return None
        return (f"{start.isoformat()}T00:00:00", f"{end.isoformat()}T23:59:59")

    def refresh(self) -> None:
        values = self.range_values()
        if values is None:
            return
        start, end = values

        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count, COALESCE(SUM(total), 0) AS total,
                   COALESCE(AVG(total), 0) AS average
            FROM sales
            WHERE created_at BETWEEN ? AND ? AND status = 'COMPLETED'
            """,
            (start, end),
        ).fetchone()
        total = float(row["total"] or 0)
        count = int(row["count"] or 0)
        average = float(row["average"] or 0)

        cost_row = self.conn.execute(
            """
            SELECT COALESCE(SUM(si.quantity * si.cost), 0) AS costs
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.created_at BETWEEN ? AND ? AND s.status = 'COMPLETED'
            """,
            (start, end),
        ).fetchone()
        costs = float(cost_row["costs"] or 0)

        expense_row = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS expenses
            FROM expenses
            WHERE created_at BETWEEN ? AND ?
            """,
            (start, end),
        ).fetchone()
        expenses = float(expense_row["expenses"] or 0)

        self.total_var.set(money(total))
        self.count_var.set(str(count))
        self.avg_var.set(money(average))
        self.cost_var.set(money(costs))
        self.expense_var.set(money(expenses))
        self.profit_var.set(money(total - costs - expenses))

        self.fill_products(start, end)
        self.fill_categories(start, end)
        self.fill_payments(start, end)

    def fill_products(self, start: str, end: str) -> None:
        self._clear(self.product_tree)
        rows = self.conn.execute(
            """
            SELECT si.name, SUM(si.quantity) AS qty, SUM(si.line_total) AS total
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.created_at BETWEEN ? AND ? AND s.status = 'COMPLETED'
            GROUP BY si.code, si.name
            ORDER BY qty DESC, total DESC
            LIMIT 100
            """,
            (start, end),
        ).fetchall()
        for row in rows:
            self.product_tree.insert("", "end", values=(row["name"], number(row["qty"]), money(row["total"])))

    def fill_categories(self, start: str, end: str) -> None:
        self._clear(self.category_tree)
        rows = self.conn.execute(
            """
            SELECT COALESCE(p.category, 'Sin categoria') AS category,
                   SUM(si.quantity) AS qty,
                   SUM(si.line_total) AS total
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            LEFT JOIN products p ON p.code = si.code
            WHERE s.created_at BETWEEN ? AND ? AND s.status = 'COMPLETED'
            GROUP BY COALESCE(p.category, 'Sin categoria')
            ORDER BY total DESC
            """,
            (start, end),
        ).fetchall()
        for row in rows:
            self.category_tree.insert("", "end", values=(row["category"], number(row["qty"]), money(row["total"])))

    def fill_payments(self, start: str, end: str) -> None:
        self._clear(self.payment_tree)
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(cash), 0) AS cash,
                   COALESCE(SUM(card), 0) AS card,
                   COALESCE(SUM(credit), 0) AS credit,
                   COALESCE(SUM(cheque), 0) AS cheque,
                   COALESCE(SUM(other), 0) AS other
            FROM sales
            WHERE created_at BETWEEN ? AND ? AND status = 'COMPLETED'
            """,
            (start, end),
        ).fetchone()
        labels = [
            ("Efectivo", row["cash"]),
            ("Tarjetas", row["card"]),
            ("Credito", row["credit"]),
            ("Cheque", row["cheque"]),
            ("Otros", row["other"]),
        ]
        for label, value in labels:
            self.payment_tree.insert("", "end", values=(label, money(value)))

    def chart_sales_by_day(self) -> None:
        values = self.range_values()
        if values is None:
            return
        start, end = values
        rows = self.conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS day, SUM(total) AS total
            FROM sales
            WHERE created_at BETWEEN ? AND ? AND status = 'COMPLETED'
            GROUP BY substr(created_at, 1, 10)
            ORDER BY day
            """,
            (start, end),
        ).fetchall()
        labels = [row["day"] for row in rows]
        values = [float(row["total"] or 0) for row in rows]
        self._show_bar_chart("Ventas por dia", labels, values)

    def chart_payments(self) -> None:
        values = self.range_values()
        if values is None:
            return
        start, end = values
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(cash), 0) AS cash,
                   COALESCE(SUM(card), 0) AS card,
                   COALESCE(SUM(credit), 0) AS credit,
                   COALESCE(SUM(cheque), 0) AS cheque,
                   COALESCE(SUM(other), 0) AS other
            FROM sales
            WHERE created_at BETWEEN ? AND ? AND status = 'COMPLETED'
            """,
            (start, end),
        ).fetchone()
        labels = ["Efectivo", "Tarjetas", "Credito", "Cheque", "Otros"]
        amounts = [float(row[key] or 0) for key in ("cash", "card", "credit", "cheque", "other")]
        self._show_pie_chart("Distribucion de pagos", labels, amounts)

    def _show_bar_chart(self, title: str, labels: list[str], values: list[float]) -> None:
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except Exception:
            messagebox.showwarning("Graficas", "Instale matplotlib para ver graficas.")
            return
        window = tk.Toplevel(self)
        window.title(title)
        figure = Figure(figsize=(8, 4), dpi=100)
        ax = figure.add_subplot(111)
        ax.bar(labels, values, color="#1c7ed6")
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=30)
        ax.set_ylabel("Ventas")
        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _show_pie_chart(self, title: str, labels: list[str], values: list[float]) -> None:
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except Exception:
            messagebox.showwarning("Graficas", "Instale matplotlib para ver graficas.")
            return
        filtered = [(label, value) for label, value in zip(labels, values) if value > 0]
        if not filtered:
            messagebox.showinfo("Graficas", "No hay pagos para graficar.")
            return
        window = tk.Toplevel(self)
        window.title(title)
        figure = Figure(figsize=(7, 4), dpi=100)
        ax = figure.add_subplot(111)
        ax.pie([value for _label, value in filtered], labels=[label for label, _value in filtered], autopct="%1.1f%%")
        ax.set_title(title)
        canvas = FigureCanvasTkAgg(figure, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _clear(self, tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)
