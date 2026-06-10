from __future__ import annotations

import os
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from modules.app_config import ASSETS_DIR, BASE_DIR, load_config
from modules.formatters import money, number
from modules.security import get_setting

TICKET_WIDTH = 48

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None  # type: ignore


def format_ticket_datetime(value: str) -> str:
    raw = (value or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(raw[:19], fmt)
            return dt.strftime("%H:%M %d/%m/%Y")
        except ValueError:
            continue
    return raw.replace("T", " ")[:16]


def _logo_paths() -> list[Path]:
    roots = [ASSETS_DIR, BASE_DIR / "assets"]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.insert(0, Path(meipass) / "assets")
    names = ("Arezone.ico", "AREZONE.ico", "arezone.png", "AREZONE.png", "logo.png")
    return [root / name for root in roots for name in names]


def _find_logo_path() -> Path | None:
    for path in _logo_paths():
        if path.exists():
            return path
    return None


def _ascii_banner(width: int = TICKET_WIDTH) -> list[str]:
    art = [
        r"    _    ____  ______  _   _  ______  _   _ ",
        r"   / \  |  _ \|  ____|| \ | ||  ____|| \ | |",
        r"  / _ \ | |_) | |__   |  \| || |__   |  \| |",
        r" / ___ \|  _ <|  __|  | . ` ||  __|  | . ` |",
        r"/_/   \_\_| \_\_|     |_| \_||_|     |_| \_|",
    ]
    lines = ["+" + "=" * (width - 2) + "+"]
    for row in art:
        lines.append("|" + row.center(width - 2)[: width - 2] + "|")
    lines.append("|" + "SISTEMA POS PROFESIONAL".center(width - 2) + "|")
    lines.append("+" + "=" * (width - 2) + "+")
    return lines


def _center(text: str, width: int = TICKET_WIDTH) -> str:
    return text[:width].center(width)


def _line_pair(label: str, value: str, width: int = TICKET_WIDTH) -> str:
    label = f"{label}:"
    space = max(1, width - len(label) - len(value))
    return f"{label}{' ' * space}{value}"


def calculate_tax_summary(items: list[dict]) -> dict[str, float]:
    summary = {"base": 0.0, "tax": 0.0}
    for item in items:
        total = float(item.get("line_total", 0))
        rate = float(item.get("tax_rate", 0) or 0)
        has_tax = int(item.get("has_tax", 0) or 0)
        if has_tax and rate > 0:
            base = total / (1 + (rate / 100))
            summary["base"] += base
            summary["tax"] += total - base
        else:
            summary["base"] += total
    return {key: round(value, 2) for key, value in summary.items()}


def build_ticket(
    conn,
    invoice_no: str,
    created_at: str,
    seller: str,
    customer: str,
    items: list[dict],
    total: float,
    *,
    cash: float = 0.0,
    nequi: float = 0.0,
    change: float = 0.0,
) -> str:
    config = load_config()
    store = (get_setting(conn, "store_name", "") or config.get("business_name") or "AREZONE").strip()
    nit = (get_setting(conn, "store_nit", "") or get_setting(conn, "nit", "") or "").strip()
    phone = (get_setting(conn, "store_phone", "") or get_setting(conn, "phone", "") or "").strip()
    address = (get_setting(conn, "store_address", "") or get_setting(conn, "address", "") or "").strip()
    support = (config.get("support_email") or "").strip()
    slogan = (config.get("slogan") or "POS rapido y profesional").strip()
    tax_summary = calculate_tax_summary(items)
    when = format_ticket_datetime(created_at)
    width = TICKET_WIDTH

    lines: list[str] = ["", *_ascii_banner(width), ""]
    lines.append("+" + "-" * (width - 2) + "+")
    lines.append("|" + store.upper().center(width - 2) + "|")
    lines.append("|" + "AREZONE POS".center(width - 2) + "|")
    if slogan:
        for chunk in textwrap.wrap(slogan.upper(), width=width - 4):
            lines.append("|" + chunk.center(width - 2) + "|")
    lines.append("+" + "-" * (width - 2) + "+")
    if nit:
        lines.append(_line_pair("NIT", nit[: width - 6], width))
    if phone:
        lines.append(_line_pair("TEL", phone[: width - 6], width))
    if address:
        for chunk in textwrap.wrap(address, width=width - 4):
            lines.append("|" + chunk.center(width - 2) + "|")
    lines.extend(["=" * width, "FACTURA DE VENTA".center(width), "=" * width])
    lines.append(_line_pair("FACTURA", invoice_no, width))
    lines.append(_line_pair("FECHA", when, width))
    lines.append(_line_pair("VENDEDOR", seller[: width - 11], width))
    lines.append(_line_pair("CLIENTE", (customer or "PARTICULAR")[: width - 10], width))
    lines.append("-" * width)
    lines.append("CANT  DESCRIPCION               V.UNIT      TOTAL")
    lines.append("-" * width)

    for item in items:
        qty = number(item["quantity"]).rjust(4)
        name_lines = textwrap.wrap(str(item["name"]).upper(), width=26) or [""]
        unit = money(item["unit_price"]).replace("$ ", "").rjust(10)
        line_total = money(item["line_total"]).replace("$ ", "").rjust(10)
        lines.append(f"{qty}  {name_lines[0].ljust(26)} {unit} {line_total}")
        for extra in name_lines[1:]:
            lines.append(f"      {extra}")
        code = str(item.get("code", "")).strip()
        if code:
            lines.append(f"      Ref: {code[:width - 11]}")

    lines.append("-" * width)
    lines.append(_line_pair("SUBTOTAL", money(tax_summary["base"]), width))
    if tax_summary["tax"] > 0:
        lines.append(_line_pair("IVA", money(tax_summary["tax"]), width))
    lines.append(_line_pair("TOTAL", money(total), width))
    lines.append("-" * width)
    lines.append("FORMA DE PAGO".center(width))
    if cash > 0:
        lines.append(_line_pair("EFECTIVO", money(cash), width))
    if nequi > 0:
        lines.append(_line_pair("NEQUI", money(nequi), width))
    if change > 0:
        lines.append(_line_pair("CAMBIO", money(change), width))
    lines.extend(
        [
            "=" * width,
            "GRACIAS POR SU COMPRA".center(width),
            "AREZONE - PUNTO DE VENTA".center(width),
        ]
    )
    if support:
        lines.append(_center(support, width))
    lines.append("")
    return "\n".join(lines)


def _escpos_raster_from_image(path: Path, max_width: int = 320) -> bytes:
    if Image is None:
        return b""
    try:
        img = Image.open(path).convert("L")
    except Exception:
        return b""
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, max(1, int(img.height * ratio))))
    img = img.point(lambda p: 255 if p > 160 else 0, mode="1")
    width, height = img.size
    width_bytes = (width + 7) // 8
    raster = bytearray()
    pixels = img.load()
    for y in range(height):
        for x_byte in range(width_bytes):
            byte = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if x < width and pixels[x, y] == 0:
                    byte |= 1 << (7 - bit)
            raster.append(byte)
    header = bytes([0x1D, 0x76, 0x30, 0x00, width_bytes % 256, width_bytes // 256, height % 256, height // 256])
    return header + bytes(raster)


def build_escpos_payload(text: str) -> bytes:
    parts = [b"\x1b@", b"\x1b\x61\x01"]  # init, center
    logo = _find_logo_path()
    if logo:
        raster = _escpos_raster_from_image(logo)
        if raster:
            parts.append(raster)
            parts.append(b"\n")
    parts.append(b"\x1b\x61\x00")  # left align body
    parts.append(b"\x1b\x45\x00")  # bold off
    parts.append(text.encode("cp850", errors="replace"))
    parts.append(b"\n\n\n\x1dV\x00")
    return b"".join(parts)


def save_ticket(invoice_no: str, ticket: str) -> Path:
    documents = Path.home() / "Documents"
    tickets_dir = documents / "AREZONE" / "Facturas"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    path = tickets_dir / f"{invoice_no}.txt"
    path.write_text(ticket, encoding="utf-8")
    return path


def try_print_ticket(path: Path, port: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        data = build_escpos_payload(text)
        if port.upper() == "USB" and os.name == "nt":
            return _raw_write_default_printer(data)
        if port.upper().startswith("COM"):
            import serial  # type: ignore

            with serial.Serial(port.upper(), 9600, timeout=1) as printer:
                printer.write(data)
            return True
    except Exception:
        return False
    return False


def build_sample_ticket(conn) -> str:
    sample_items = [
        {
            "code": "DEMO-001",
            "name": "Producto de prueba",
            "quantity": 1,
            "unit_price": 1000,
            "line_total": 1000,
            "tax_rate": 0,
            "has_tax": 0,
        }
    ]
    return build_ticket(
        conn,
        "PRUEBA-001",
        datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "ADMIN",
        "CLIENTE PRUEBA",
        sample_items,
        1000.0,
        cash=1000.0,
        nequi=0.0,
        change=0.0,
    )


def _raw_write_default_printer(data: bytes) -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes

        winspool = ctypes.WinDLL("winspool.drv")
        get_default = winspool.GetDefaultPrinterW
        get_default.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
        needed = ctypes.c_uint32(0)
        get_default(None, ctypes.byref(needed))
        if needed.value <= 0:
            return False
        printer_name = ctypes.create_unicode_buffer(needed.value)
        if not get_default(printer_name, ctypes.byref(needed)):
            return False
        return _raw_write_named_printer(printer_name.value, data)
    except Exception:
        return False


def _raw_write_named_printer(printer_name: str, data: bytes) -> bool:
    import ctypes

    winspool = ctypes.WinDLL("winspool.drv")
    handle = ctypes.c_void_p()
    if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer_name), ctypes.byref(handle), None):
        return False

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [
            ("pDocName", ctypes.c_wchar_p),
            ("pOutputFile", ctypes.c_wchar_p),
            ("pDatatype", ctypes.c_wchar_p),
        ]

    try:
        doc_info = DOC_INFO_1("AREZONE ticket", None, "RAW")
        if winspool.StartDocPrinterW(handle, 1, ctypes.byref(doc_info)) == 0:
            return False
        if not winspool.StartPagePrinter(handle):
            return False
        written = ctypes.c_uint32(0)
        buffer = ctypes.create_string_buffer(data)
        ok = winspool.WritePrinter(handle, buffer, len(data), ctypes.byref(written))
        winspool.EndPagePrinter(handle)
        winspool.EndDocPrinter(handle)
        return bool(ok and written.value == len(data))
    finally:
        winspool.ClosePrinter(handle)


def try_open_drawer(port: str) -> bool:
    try:
        pulse = b"\x1b\x70\x00\x19\xfa"
        if port.upper() == "USB" and os.name == "nt":
            return _raw_write_default_printer(pulse)
        if port.upper().startswith("COM"):
            import serial  # type: ignore

            with serial.Serial(port.upper(), 9600, timeout=1) as printer:
                printer.write(pulse)
            return True
    except Exception:
        return False
    return False
