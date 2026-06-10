from __future__ import annotations


def money(value: float | int | None) -> str:
    amount = float(value or 0)
    return "$ {:,.0f}".format(amount).replace(",", ".")


def number(value: float | int | None) -> str:
    amount = float(value or 0)
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def parse_amount(value: str | float | int | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("$", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "." in text:
        decimals = text.rsplit(".", 1)[1]
        if len(decimals) == 3 and text.replace(".", "").isdigit():
            text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return 0.0
